"""Raccolta notturna dei dati di CLASSE B (istantanee di oggi).

Revisioni delle stime EPS, consenso degli analisti, short interest, prezzo
obiettivo medio e opzioni esistono su Yahoo solo come "fotografia di oggi":
non si possono testare sul passato senza barare. Per questo:
  1. ogni notte si salva la fotografia in SQLite, con la data;
  2. il peso nel modello resta 0;
  3. una misura può essere PROMOSSA solo quando ha almeno 12 periodi
     indipendenti non sovrapposti (~18 mesi) E un IC con t di Newey-West >= 2
     E supera Benjamini-Hochberg al 10% insieme alle altre misure di classe B.
La promozione resta una decisione manuale: qui si fanno raccolta, conteggio e regola.
"""
import math
from datetime import date

import numpy as np
import pandas as pd

import config
import data
import db
from lab import features as F
from lab import stats as S
from universe import is_index


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def snapshot(ticker: str) -> dict:
    """Fotografia di oggi per un titolo (valori numerici)."""
    t = ticker.upper()
    out = {}
    if config.DEMO:
        rng = np.random.default_rng(data._seed(t + date.today().isoformat()))
        if not is_index(t):
            out.update(eps_rev_30d=float(rng.integers(-5, 6)), eps_trend_30d=float(rng.normal(0, 0.03)),
                       rec_mean=float(rng.uniform(1.5, 3.5)), short_pct_float=float(rng.uniform(0.005, 0.08)),
                       short_change=float(rng.normal(0, 0.1)), days_to_cover=float(rng.uniform(0.5, 6)),
                       target_upside=float(rng.normal(0.08, 0.12)))
    else:
        out.update(_yf_snapshot(t))
    try:
        import priced
        df, meta = data.get_history(t)
        opt = data.get_options(t)
        if opt:
            s = priced.options_summary(opt, 45 if not is_index(t) else 91)
            if s:
                out["atm_iv"] = s["iv"]
                out["iv_skew"] = s["skew_slope"]
                h = config.HORIZON_INDEX if is_index(t) else config.HORIZON_STOCK
                beta = 1.0
                pr = priced.digital_prob(s["iv"], s["dsig_dk_rel"], h, config.DEFAULT_RISK_FREE, beta)
                out["p_market"] = pr["p_real"]
    except Exception:
        pass
    return {k: v for k, v in out.items() if v is not None}


def _yf_snapshot(t):
    out = {}
    if is_index(t):
        return out
    try:
        import yfinance as yf
    except Exception:
        return out
    try:
        tk = yf.Ticker(t)
        info = tk.info or {}
        px = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
        tgt = _f(info.get("targetMeanPrice"))
        out["rec_mean"] = _f(info.get("recommendationMean"))
        out["short_pct_float"] = _f(info.get("shortPercentOfFloat"))
        s0, s1 = _f(info.get("sharesShort")), _f(info.get("sharesShortPriorMonth"))
        if s0 and s1:
            out["short_change"] = s0 / s1 - 1
        av = _f(info.get("averageVolume"))
        if s0 and av:
            out["days_to_cover"] = s0 / av
        if px and tgt:
            out["target_upside"] = tgt / px - 1
        try:
            rv = tk.eps_revisions
            if rv is not None and len(rv):
                row = rv.loc["+1y"] if "+1y" in rv.index else rv.iloc[0]
                out["eps_rev_30d"] = _f(row.get("upLast30days", 0)) - (_f(row.get("downLast30days", 0)) or 0)
        except Exception:
            pass
        try:
            tr = tk.eps_trend
            if tr is not None and len(tr):
                row = tr.loc["+1y"] if "+1y" in tr.index else tr.iloc[0]
                cur, ago = _f(row.get("current")), _f(row.get("30daysAgo"))
                if cur is not None and ago:
                    out["eps_trend_30d"] = cur / ago - 1
        except Exception:
            pass
    except Exception:
        pass
    return {k: v for k, v in out.items() if v is not None}


def collect(tickers, progress=None):
    """Salva la fotografia di oggi per ogni titolo. Restituisce il numero di valori salvati."""
    today = date.today().isoformat()
    n = 0
    for i, t in enumerate(tickers):
        if progress:
            progress(i / max(len(tickers), 1), t)
        try:
            n += db.snapshot_put(today, t, snapshot(t))
        except Exception:
            continue
    return n


# --------------------------------------------------------------------------
def periods_from_dates(n_dates, h=None):
    """Periodi indipendenti = date distinte raccolte / h."""
    h = h or config.HORIZON_STOCK
    return int(n_dates // h)


def promotion_rule(n_periods, t_nw, bh_pass, min_periods=None, t_min=2.0):
    """Regola di promozione di una misura di classe B (tutte le condizioni insieme)."""
    min_periods = min_periods or config.LAB["promo_periods"]
    reasons = []
    if n_periods < min_periods:
        reasons.append(f"in raccolta: {n_periods}/{min_periods} periodi indipendenti")
    if t_nw is None or not math.isfinite(t_nw) or t_nw < t_min:
        reasons.append("t di Newey-West sotto 2")
    if not bh_pass:
        reasons.append("non supera Benjamini-Hochberg al 10%")
    return {"eligible": not reasons, "reasons": reasons}


def evaluate_field(field, h=None):
    """IC per data tra la misura raccolta e il rendimento residuo successivo (solo dati maturati)."""
    h = h or config.HORIZON_STOCK
    rows = db.snapshot_rows(field)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    from fundamentals import benchmark_for
    recs = []
    for t, g in df.groupby("ticker"):
        if is_index(t):
            continue
        try:
            px = data.get_history(t)[0]["adj"]
            bx = data.get_history(benchmark_for(t))[0]["adj"]
        except Exception:
            continue
        raw = F.stock_raw(px, bx, None)
        tg = F.stock_targets(px, bx, raw["beta"], h)
        a = F.align(tg["y_res"], pd.DatetimeIndex(g["date"]))
        for d, v, yv in zip(g["date"], g["value"], a.values):
            if np.isfinite(yv):
                recs.append((d, v, yv))
    if not recs:
        return {"ic": None, "t": None, "n_dates": 0}
    d, v, y = map(np.array, zip(*recs))
    r = S.ic_summary(d, v, y, h, 1, min_n=5)
    return {"ic": r["ic"], "t": r["t"], "n_dates": r["n_dates"]}


def status():
    """Contatore per misura: date raccolte, periodi indipendenti e stato rispetto alla regola."""
    by = db.snapshot_dates_by_field()
    h = config.HORIZON_STOCK
    need = config.LAB["promo_periods"]
    rows = []
    evals = {}
    for fd in F.CLASS_B_FIELDS:
        k = fd["key"]
        st = by.get(k, {"n": 0, "first": None, "last": None})
        per = periods_from_dates(st["n"], h)
        if per >= need:
            evals[k] = evaluate_field(k, h)
        rows.append({"key": k, "label": fd["label"], "dates": st["n"], "first": st["first"], "last": st["last"],
                     "periods": per, "need": need, "weight": 0.0})
    if evals:
        ps = [S.p_one_sided((evals.get(r["key"]) or {}).get("t")) for r in rows if r["key"] in evals]
        bh = dict(zip([r["key"] for r in rows if r["key"] in evals], S.benjamini_hochberg(ps, config.LAB["fdr"])))
    else:
        bh = {}
    for r in rows:
        e = evals.get(r["key"]) or {}
        rule = promotion_rule(r["periods"], e.get("t"), bh.get(r["key"], False))
        r["ic"], r["t"] = e.get("ic"), e.get("t")
        r["eligible"] = rule["eligible"]
        r["status"] = (f"in raccolta {r['periods']}/{need} periodi" if r["periods"] < need else
                       "promuovibile (decisione manuale)" if rule["eligible"] else "non supera la regola")
        r["reasons"] = rule["reasons"]
    return {"fields": rows, "h": h, "rule": f"almeno {need} periodi indipendenti (~18 mesi), t Newey-West ≥ 2, "
                                         f"Benjamini-Hochberg al 10%. Fino ad allora peso 0."}
