"""Punteggio Oracolo 1-5: test pre-registrato (PREREG_SCORE.md).  python -m lab.score_test"""
import json
import math

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import data
from universe import INDICES

from .band_test import sigma_daily
from .multifactor import sp500
from .panic_test import TICKERS as OOS
from .rsi_test import rsi
from .search2000 import load


def composite(P):
    lp = np.log(P)
    z = (lp - lp.shift(31)) / (sigma_daily(lp.diff()) * math.sqrt(31))
    vix = data.get_history("^VIX")[0]["close"].astype(float)
    vix = vix.reindex(vix.index.union(P.index)).ffill().shift(1).reindex(P.index)
    vr = np.log(vix / vix.rolling(252, min_periods=200).mean())
    parts = [(50 - rsi(P, 14)) / 20, -z, pd.DataFrame({c: vr for c in P}, index=P.index)]
    return sum(parts) / 3


def score_index(P):
    C = composite(P)
    pct = C.expanding(min_periods=500).rank(pct=True)
    return np.ceil(pct * 5).clip(1, 5).where(pct.notna())


def edge_by_score(S, fwd, dates, norm):
    out = {}
    for k in range(1, 6):
        vals = []
        for d in dates:
            s, f = S.loc[d], fwd.loc[d]
            sel = (s == k) & f.notna()
            if sel.any():
                vals.append(float((f[sel] - norm[sel]).mean()))
        v = np.array(vals)
        out[k] = {"dates": len(v), "edge": float(v.mean()) if len(v) else None,
                  "t": float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))) if len(v) > 5 and v.std() > 0 else None}
    edges = [out[k]["edge"] for k in range(1, 6)]
    out["spearman"] = float(spearmanr(range(1, 6), edges)[0]) if None not in edges else None
    return out


def main():
    res = {}
    for name, tick in (("fuori_campione", OOS), ("indici_universe", list(INDICES))):
        P, _, _ = load(tick)
        P = P[P.index >= "1993-01-01"]
        S = score_index(P)
        h = 21
        ds = [d for d in P.index[::h] if P.index.get_loc(d) + h < len(P.index)]
        fwd = P.shift(-h) / P - 1
        norm = fwd.loc[ds].mean()
        r = edge_by_score(S, fwd, ds, norm)
        r["ok"] = bool((r[5]["edge"] or 0) > 0 and (r[5]["t"] or 0) >= 2 and (r["spearman"] or 0) >= 0.8)
        res[name] = r
    P, _, _ = load([t for t, _ in sp500()])
    R = (50 - rsi(P, 14)).rank(axis=1, pct=True)
    S = np.ceil(R * 5).clip(1, 5).where(R.notna())
    h = 5
    ds = [d for d in P.index[::h] if d.year >= 2013 and P.index.get_loc(d) + h < len(P.index)]
    fwd = P.shift(-h) / P - 1
    norm = fwd.loc[ds].mean()
    r = edge_by_score(S, fwd, ds, norm)
    diff = []
    for d in ds:
        s, f = S.loc[d], fwd.loc[d]
        a, b = f[(s == 5) & f.notna()], f[(s == 1) & f.notna()]
        if len(a) and len(b):
            diff.append(a.mean() - b.mean())
    diff = np.array(diff)
    r["spread_5_1"] = float(diff.mean())
    r["t_spread"] = float(diff.mean() / (diff.std(ddof=1) / math.sqrt(len(diff))))
    r["ok"] = bool(r["spread_5_1"] > 0 and r["t_spread"] >= 3 and (r["spearman"] or 0) >= 0.8)
    res["azioni_sp500"] = r
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
