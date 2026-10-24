"""Fattori e punteggi. Ogni valore alla data t usa solo dati noti alla chiusura di t
(finestre mobili che finiscono in t; stime di parametri ritardate di una seduta).

Punteggi:
- ipb / Pressure Score (-100..+100): pressione rialzista/ribassista da momentum, trend,
  partecipazione proxy, volume proxy e sentiment di volatilità.
- Expectation Gap (-100..+100): volatilità attesa (indice di volatilità) contro realizzata.
  Positivo = il mercato temeva più rischio di quello che si è visto. Richiede un indice di volatilità.
- Reaction Anomaly (-100..+100): reazione del prezzo diversa da quella implicita nel contesto
  (variazione della volatilità implicita); senza indice di volatilità usa solo il prezzo (dichiarato).
- Crowding & Fragility (0..100): estensione, serie di sedute nello stesso verso, compressione della
  volatilità, compiacenza, volume affollato. Punteggio euristico, NON una probabilità.
- reversal_risk (0..100): punteggio euristico di rischio inversione, NON una probabilità.

I pesi interni sono fissi e dichiarati qui (non ottimizzati sui dati).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-12
Z_WINDOW = 252
Z_MIN = 80
ANN = np.sqrt(252)


def robust_z(s: pd.Series, window: int = Z_WINDOW, min_periods: int = Z_MIN) -> pd.Series:
    """z robusto causale: (x_t - mediana) / (1,4826 * MAD) sulla finestra che termina in t."""
    def f(w):
        w = w[~np.isnan(w)]
        if len(w) < min_periods:
            return np.nan
        med = np.median(w)
        mad = np.median(np.abs(w - med))
        return (w[-1] - med) / (1.4826 * mad + EPS) if np.isfinite(w[-1]) else np.nan
    z = s.astype(float).rolling(window, min_periods=1).apply(f, raw=True)
    z[s.isna()] = np.nan
    return z.clip(-3, 3)


def squash(z: pd.Series) -> pd.Series:
    return np.tanh(z / 1.5)


def _streak(r: pd.Series) -> pd.Series:
    sgn = np.sign(r.fillna(0)).values
    out = np.zeros(len(sgn))
    for i in range(len(sgn)):
        out[i] = out[i - 1] + 1 if i and sgn[i] != 0 and sgn[i] == sgn[i - 1] else (1 if sgn[i] != 0 else 0)
    return pd.Series(out, index=r.index)


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.copy()
    c = d["close"].astype(float)
    pct = lambda n: c.pct_change(n, fill_method=None)  # noqa: E731
    d["ret_1"], d["ret_5"], d["ret_20"], d["ret_60"] = pct(1), pct(5), pct(20), pct(60)
    r = d["ret_1"]
    d["vol_20"] = r.rolling(20, min_periods=20).std() * ANN
    d["vol_60"] = r.rolling(60, min_periods=60).std() * ANN
    d["ma_50"] = c.rolling(50, min_periods=50).mean()
    d["ma_200"] = c.rolling(200, min_periods=200).mean()
    d["dist_ma50"] = c / d["ma_50"] - 1
    d["dist_ma200"] = c / d["ma_200"] - 1
    d["trend"] = d["ma_50"] / d["ma_200"] - 1

    # Partecipazione proxy: coerenza del verso su 5/20/60 sedute. NON è la breadth dei componenti.
    d["participation_proxy"] = (np.sign(d["ret_5"]) + np.sign(d["ret_20"]) + np.sign(d["ret_60"])) / 3

    v = pd.to_numeric(d.get("proxy_volume", pd.Series(np.nan, index=d.index)), errors="coerce")
    d["volume_rel"] = v / (v.rolling(20, min_periods=10).median() + EPS) - 1
    vix = pd.to_numeric(d.get("vol_index", pd.Series(np.nan, index=d.index)), errors="coerce")
    d["vol_change_5"] = vix.pct_change(5, fill_method=None)
    d["vol_level_z"] = robust_z(vix)

    # ---------------- Pressure Score (IPB) ----------------
    d["f_momentum"] = (0.45 * squash(robust_z(d["ret_5"])) + 0.35 * squash(robust_z(d["ret_20"]))
                       + 0.20 * squash(robust_z(d["ret_60"])))
    d["f_trend"] = 0.5 * squash(robust_z(d["dist_ma50"])) + 0.5 * squash(robust_z(d["dist_ma200"]))
    d["f_participation"] = d["participation_proxy"]
    d["f_volume"] = np.sign(r) * squash(robust_z(d["volume_rel"]))
    # sentiment: per riga, indice di volatilità se disponibile a quella data, altrimenti volatilità
    # realizzata (la scelta non dipende da dati futuri)
    sent_vix = -0.65 * squash(d["vol_level_z"]) - 0.35 * squash(robust_z(d["vol_change_5"]).fillna(0))
    sent_rv = -0.5 * squash(robust_z(d["vol_20"]))
    use_vix = d["vol_level_z"].notna()
    d["f_sentiment_proxy"] = sent_vix.where(use_vix, sent_rv)
    d["sentiment_source"] = np.where(use_vix, "indice di volatilità", "volatilità realizzata")

    core = d[["f_momentum", "f_trend", "f_participation", "f_sentiment_proxy"]].notna().all(axis=1)
    ipb = 100 * (0.25 * d["f_momentum"] + 0.20 * d["f_trend"] + 0.20 * d["f_participation"]
                 + 0.15 * d["f_volume"].fillna(0) + 0.20 * d["f_sentiment_proxy"])
    d["ipb"] = ipb.where(core).clip(-100, 100)       # niente valore finché i fattori principali non esistono
    d["pressure_score"] = d["ipb"]

    # ---------------- Expectation Gap ----------------
    rv21 = r.rolling(21, min_periods=21).std() * ANN
    gap_past = vix.shift(21) / 100 - rv21     # attesa di un mese fa contro ciò che è successo da allora
    vrp_now = vix / 100 - rv21                # premio di rischio di varianza di oggi
    d["expectation_gap"] = 100 * (0.5 * squash(robust_z(gap_past)) + 0.5 * squash(robust_z(vrp_now)))

    # ---------------- Reaction Anomaly ----------------
    dv = np.log(vix).diff()
    beta = (r.rolling(252, min_periods=120).cov(dv) / dv.rolling(252, min_periods=120).var()).shift(1)
    resid_ctx = r - beta * dv
    resid_px = r
    has_ctx = resid_ctx.notna()
    resid = resid_ctx.where(has_ctx, resid_px)
    sd = resid.rolling(252, min_periods=120).std().shift(1)
    u = resid / sd
    d["reaction_anomaly"] = 100 * np.tanh(u.rolling(5, min_periods=5).sum() / np.sqrt(5) / 1.5)
    d["reaction_source"] = np.where(has_ctx, "residuo vs volatilità implicita", "solo prezzo")

    # ---------------- Crowding & Fragility ----------------
    ext = squash(robust_z(d["dist_ma50"]).abs())
    streak = (_streak(r) / 8).clip(upper=1)
    compression = squash((-robust_z(np.log(d["vol_20"] / d["vol_60"]))).clip(lower=0))
    complacency_vix = squash((-d["vol_level_z"]).clip(lower=0))
    complacency_rv = squash((-robust_z(d["vol_20"])).clip(lower=0))
    complacency = complacency_vix.where(d["vol_level_z"].notna(), complacency_rv)
    crowd_vol = squash(robust_z(d["volume_rel"]).clip(lower=0)).fillna(0) * d["participation_proxy"].abs()
    cf = 100 * (0.30 * ext + 0.20 * streak + 0.20 * compression + 0.20 * complacency + 0.10 * crowd_vol)
    d["crowding_fragility"] = cf.where(ext.notna() & compression.notna() & complacency.notna()).clip(0, 100)

    # ---------------- Rischio inversione (euristico) ----------------
    momentum_div = (((d["ret_20"] > 0) & (d["ret_5"] < 0)) | ((d["ret_20"] < 0) & (d["ret_5"] > 0))).astype(float)
    vol_stress = squash(robust_z(d["vol_20"])).abs()
    vol_spike = squash(robust_z(d["vol_change_5"].abs()))
    has_spike = vol_spike.notna()
    rr = np.where(has_spike,
                  0.30 * ext + 0.25 * momentum_div + 0.25 * vol_stress + 0.20 * vol_spike.fillna(0),
                  (0.30 * ext + 0.25 * momentum_div + 0.25 * vol_stress) / 0.80)
    d["reversal_risk"] = pd.Series(100 * rr, index=d.index).where(ext.notna() & vol_stress.notna()).clip(0, 100)

    # ---------------- input del modello (scala ~[-1, 1]) ----------------
    d["s_pressure"] = d["pressure_score"] / 100
    d["s_expect"] = d["expectation_gap"] / 100
    d["s_reaction"] = d["reaction_anomaly"] / 100
    d["s_crowding"] = d["crowding_fragility"] / 100
    d["z_ret20"] = robust_z(d["ret_20"]) / 3
    d["z_vol20"] = robust_z(d["vol_20"]) / 3
    return d.replace([np.inf, -np.inf], np.nan)


SCORE_COLS = ["pressure_score", "expectation_gap", "reaction_anomaly", "crowding_fragility", "reversal_risk"]
CAUSAL_COLS = SCORE_COLS + ["ipb", "s_pressure", "s_expect", "s_reaction", "s_crowding", "z_ret20", "z_vol20"]


def add_labels(features: pd.DataFrame, horizon: int, threshold: float, trend_lookback: int = 20) -> pd.DataFrame:
    """Target separati, NaN dove il futuro non è ancora osservato:
    - target_dir: 0 ribasso, 1 laterale, 2 rialzo (rendimento a `horizon` sedute vs ±threshold);
    - target_rev: 1 se nelle prossime `horizon` sedute il prezzo si muove contro il trend delle
      ultime `trend_lookback` sedute di oltre `threshold`, 0 altrimenti."""
    d = features.copy()
    c = d["close"]
    fr = c.shift(-horizon) / c - 1
    d["future_return"] = fr
    tdir = np.select([fr < -threshold, fr > threshold], [0, 2], default=1).astype(float)
    d["target_dir"] = np.where(fr.notna(), tdir, np.nan)
    trend = np.sign(c.pct_change(trend_lookback, fill_method=None))
    rev = ((fr * trend) < -threshold).astype(float)
    d["target_rev"] = rev.where(fr.notna() & trend.notna() & (trend != 0))
    d.attrs.update(features.attrs)
    d.attrs.update(horizon=horizon, threshold=threshold)
    return d


def latest_signal(features: pd.DataFrame, pressure_band: float = 25.0) -> dict:
    valid = features.dropna(subset=["ipb"])
    if valid.empty:
        return {"date": None, "ipb": None, "pressure": "Non disponibile (storico insufficiente)",
                "reversal_risk_score": None}
    row = valid.iloc[-1]
    score = float(row["ipb"])
    pressure = "Rialzista" if score >= pressure_band else "Ribassista" if score <= -pressure_band else "Neutrale"
    val = lambda k: None if pd.isna(row.get(k)) else round(float(row[k]), 1)  # noqa: E731
    return {
        "date": str(valid.index[-1].date()),
        "ipb": round(score, 1),
        "pressure": pressure,
        "expectation_gap": val("expectation_gap"),
        "reaction_anomaly": val("reaction_anomaly"),
        "crowding_fragility": val("crowding_fragility"),
        "reversal_risk_score": val("reversal_risk"),
        "sentiment_source": row.get("sentiment_source"),
        "reaction_source": row.get("reaction_source"),
        "interpretation": "Punteggi sperimentali: non sono probabilità né raccomandazioni d'investimento.",
    }
