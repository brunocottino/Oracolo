"""Probabilità walk-forward, calibrazione causale e valutazione.

Regole temporali (orizzonte H):
- alla data di previsione t si addestra solo su righe i con i + H <= t: il loro target usa il
  prezzo di chiusura i + H, già noto alla chiusura di t;
- finestra espandibile, riaddestramento ogni `refit_every` sedute, nessuno shuffle;
- calibrazione: p_cal = λ·p_modello + (1-λ)·p_storica, con λ scelto minimizzando la log-loss sulle
  sole previsioni passate il cui esito era già noto in t;
- la frequenza storica (climatologia) è calcolata con la stessa regola ed è il benchmark del Brier.

Direzione (ribasso/laterale/rialzo) e inversione (sì/no) sono target e modelli separati.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import DEFAULT, Settings

MODEL_FEATURES = ["s_pressure", "s_expect", "s_reaction", "s_crowding", "z_ret20", "z_vol20"]
# Benchmark semplice: solo volatilità e trend recenti. Se il modello non lo batte, i 4 punteggi
# non aggiungono informazione oltre al regime di volatilità.
SIMPLE_FEATURES = ["z_vol20", "z_ret20"]
DIR_CLASSES = (0, 1, 2)
DIR_NAMES = {0: "Ribasso", 1: "Laterale", 2: "Rialzo"}
DIR_COLS = ["p_down", "p_flat", "p_up"]
REV_CLASSES = (0, 1)
REV_COLS = ["p_norev", "p_rev"]
LAMBDA_GRID = np.linspace(0, 1, 11)


def _climatology(y: pd.Series, horizon: int, classes) -> np.ndarray:
    """Frequenza di ogni classe tra le righe con esito noto in t (i + H <= t)."""
    out = np.full((len(y), len(classes)), np.nan)
    known = y.notna().astype(float).values
    for j, k in enumerate(classes):
        hit = (y == k).astype(float).values
        cnt = np.concatenate([np.zeros(horizon), np.cumsum(hit)[:-horizon]]) if horizon else np.cumsum(hit)
        tot = np.concatenate([np.zeros(horizon), np.cumsum(known)[:-horizon]]) if horizon else np.cumsum(known)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:, j] = np.where(tot > 0, cnt / tot, np.nan)
    return out


def _logloss_rows(p: np.ndarray, y_idx: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(p[np.arange(len(y_idx)), y_idx], 1e-6, 1))


def walk_forward(df: pd.DataFrame, target_col: str, classes, horizon: int,
                 settings: Settings = DEFAULT, features=MODEL_FEATURES) -> pd.DataFrame:
    """Restituisce, per ogni data, probabilità grezze, frequenza storica, probabilità calibrate e λ."""
    n = len(df)
    k = len(classes)
    y = df[target_col]
    X = df[list(features)]
    raw = np.full((n, k), np.nan)
    clim = _climatology(y, horizon, classes)
    cal = np.full((n, k), np.nan)
    lam = np.full(n, np.nan)
    used = [""] * n
    y_idx_all = y.map({c: i for i, c in enumerate(classes)})

    pos = 0
    while pos < n:
        end = pos - horizon + 1                       # righe 0..end-1 hanno i + H <= pos
        block = slice(pos, min(pos + settings.refit_every, n))
        if end >= settings.min_train:
            tr = df.iloc[:end]
            # copertura misurata sulle ultime min_train righe già note (non sul periodo di avvio)
            recent = tr.iloc[-settings.min_train:]
            cols = [f for f in features if recent[f].notna().mean() >= settings.min_feature_coverage]
            tr = tr.dropna(subset=cols + [target_col]) if cols else tr.iloc[0:0]
            if len(tr) >= settings.min_train and set(tr[target_col].astype(int)) >= set(classes):
                model = Pipeline([("scale", StandardScaler()),
                                  ("logit", LogisticRegression(C=settings.C, max_iter=2000))])
                model.fit(tr[cols].values, tr[target_col].astype(int).values)
                order = [list(model.named_steps["logit"].classes_).index(c) for c in classes]
                xb = X.iloc[block][cols]
                ok = xb.notna().all(axis=1).values
                if ok.any():
                    pb = model.predict_proba(xb.values[ok])[:, order]
                    idx = np.arange(block.start, block.stop)[ok]
                    raw[idx] = pb
                    for i in idx:
                        used[i] = ",".join(cols)
                # calibrazione con le sole previsioni passate già verificabili in pos
                past = np.arange(0, end)
                m = np.isfinite(raw[past]).all(axis=1) & np.isfinite(clim[past]).all(axis=1) & y.iloc[past].notna().values
                if m.sum() >= settings.min_calibration_rows:
                    pp, pc = raw[past][m], clim[past][m]
                    yi = y_idx_all.iloc[past].values[m].astype(int)
                    losses = [_logloss_rows(l_ * pp + (1 - l_) * pc, yi).mean() for l_ in LAMBDA_GRID]
                    best = float(LAMBDA_GRID[int(np.argmin(losses))])
                    bi = np.arange(block.start, block.stop)
                    ok2 = np.isfinite(raw[bi]).all(axis=1) & np.isfinite(clim[bi]).all(axis=1)
                    cal[bi[ok2]] = best * raw[bi[ok2]] + (1 - best) * clim[bi[ok2]]
                    lam[bi[ok2]] = best
        pos = block.stop

    names = DIR_COLS if k == 3 else REV_COLS
    out = pd.DataFrame(index=df.index)
    for j, nm in enumerate(names):
        out[nm + "_raw"] = raw[:, j]
        out[nm + "_clim"] = clim[:, j]
        out[nm] = cal[:, j]
    out[f"lambda_{target_col}"] = lam
    out[f"features_{target_col}"] = used
    return out


# --------------------------------------------------------------------------
# Valutazione
# --------------------------------------------------------------------------
def _scores(p, pc, yi, k):
    onehot = np.eye(k)[yi]
    brier = float(((p - onehot) ** 2).sum(axis=1).mean())
    brier_c = float(((pc - onehot) ** 2).sum(axis=1).mean())
    return {"brier": brier, "brier_climatology": brier_c,
            "bss": float(1 - brier / brier_c) if brier_c > 0 else None,
            "log_loss": float(_logloss_rows(p, yi).mean()),
            "log_loss_climatology": float(_logloss_rows(pc, yi).mean())}


def evaluate(probs: pd.DataFrame, y: pd.Series, classes, names, horizon: int,
             settings: Settings = DEFAULT, simple: pd.DataFrame | None = None) -> dict:
    """Metriche fuori campione sulle probabilità calibrate, solo dove l'esito è noto.
    Con meno di `min_independent_periods` periodi indipendenti (righe / H) non si riportano."""
    k = len(classes)
    P = probs[names].values
    PC = probs[[n + "_clim" for n in names]].values
    m = np.isfinite(P).all(axis=1) & np.isfinite(PC).all(axis=1) & y.notna().values
    PS = simple[names].values if simple is not None else None
    if PS is not None:
        m &= np.isfinite(PS).all(axis=1)      # stesso campione per modello e benchmark
    n = int(m.sum())
    n_indep = n / horizon
    res = {"rows": n, "independent_periods": round(n_indep, 1), "horizon": horizon,
           "first": str(probs.index[m][0].date()) if n else None,
           "last": str(probs.index[m][-1].date()) if n else None}
    if n_indep < settings.min_independent_periods:
        res["status"] = (f"campione insufficiente: {n_indep:.0f} periodi indipendenti "
                         f"(minimo {settings.min_independent_periods})")
        return res
    yi = y.map({c: i for i, c in enumerate(classes)}).values[m].astype(int)
    p, pc = P[m], PC[m]
    res.update(_scores(p, pc, yi, k))
    if PS is not None:
        bs = _scores(PS[m], pc, yi, k)["brier"]
        res["brier_simple_benchmark"] = bs
        res["bss_vs_simple_benchmark"] = float(1 - res["brier"] / bs) if bs > 0 else None
    # calibrazione per classe (uno contro tutti), solo bin con abbastanza osservazioni
    bins = {}
    ece_all = []
    edges = np.linspace(0, 1, 11)
    for j, nm in enumerate(names):
        hit = (yi == j).astype(float)
        b = np.clip(np.digitize(p[:, j], edges) - 1, 0, 9)
        rows, err, cnt = [], 0.0, 0
        for q in range(10):
            sel = b == q
            if sel.sum() >= settings.min_bin_count:
                rows.append({"bin": f"{edges[q]:.1f}-{edges[q + 1]:.1f}", "n": int(sel.sum()),
                             "mean_p": float(p[sel, j].mean()), "freq": float(hit[sel].mean())})
                err += sel.sum() * abs(p[sel, j].mean() - hit[sel].mean())
                cnt += sel.sum()
        bins[nm] = rows
        if cnt:
            ece_all.append(err / cnt)
    res["calibration_bins"] = bins
    res["ece_max"] = float(max(ece_all)) if ece_all else None
    # sottoperiodi: blocchi di 3 anni solari
    idx = probs.index[m]
    block = (idx.year - idx.year.min()) // 3
    subs = []
    for bval in np.unique(block):
        s = block == bval
        ni = s.sum() / horizon
        row = {"from": str(idx[s][0].date()), "to": str(idx[s][-1].date()), "rows": int(s.sum()),
               "independent_periods": round(ni, 1)}
        if ni >= 15:
            row.update({kk: vv for kk, vv in _scores(p[s], pc[s], yi[s], k).items()
                        if kk in ("brier", "brier_climatology", "bss")})
        else:
            row["status"] = "campione insufficiente"
        subs.append(row)
    res["subperiods"] = subs
    ok = (res["bss"] is not None and res["bss"] > settings.min_bss_display
          and res["ece_max"] is not None and res["ece_max"] <= settings.max_ece_display)
    res["display_ok"] = bool(ok)
    res["status"] = ("valutata: batte la frequenza storica ed è calibrata" if ok else
                     "valutata: NON batte la frequenza storica o non è calibrata; si mostra la frequenza storica")
    vs = res.get("bss_vs_simple_benchmark")
    if vs is not None:
        res["status"] += ("; aggiunge informazione rispetto al benchmark volatilità+trend" if vs > 0.005 else
                          "; NON aggiunge informazione rispetto al benchmark volatilità+trend "
                          "(lo skill viene dal regime di volatilità, non dai 4 punteggi)")
    return res


def probability_view(row: pd.Series, evaluation: dict, names, labels) -> dict:
    """Cosa mostrare oggi: probabilità calibrate solo se la valutazione storica lo consente,
    altrimenti la frequenza storica (dichiarata) o 'non disponibile'."""
    cal = [row.get(n) for n in names]
    clim = [row.get(n + "_clim") for n in names]
    if evaluation.get("display_ok") and all(pd.notna(v) for v in cal):
        return {"source": "modello calibrato walk-forward", "values": dict(zip(labels, map(float, cal)))}
    if all(pd.notna(v) for v in clim):
        return {"source": "frequenza storica (il modello non è validato: " + evaluation.get("status", "") + ")",
                "values": dict(zip(labels, map(float, clim)))}
    return {"source": "non disponibile: storico insufficiente", "values": None}
