"""Scenari condizionati (10% / 50% / 90%) con Fear & Greed e IFC: test pre-registrato, vedi PREREG_SCENARI.md.

Lancio:  python -m lab.scenario_test
"""
import json
import math
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import QuantileRegressor

import data
from fundamentals import benchmark_for

from . import features as F
from .horizon_test import load
from .oracolo_index import UNIVERSES
from .panel import _origins, stock_universe

H = {"45gg": 31, "90gg": 63}
QS = (0.10, 0.50, 0.90)
REFIT = 252
START = "1993-01-01"


def fear_greed(index):
    g = lambda t, c="adj": data.get_history(t)[0][c].astype(float)  # noqa: E731
    spx, vix, tnx = g("^GSPC"), g("^VIX", "close"), g("^TNX", "close")
    comp = {
        "momentum": spx / spx.rolling(125).mean(),
        "volatilita": -(vix / vix.rolling(50).mean()),
        "rifugio": np.log(spx).diff(20) + tnx.diff(20) / 100,
    }
    try:
        hyg, ief = g("HYG"), g("IEF")
        comp["spazzatura"] = np.log(hyg).diff(20) - np.log(ief).diff(20)
    except Exception:
        pass
    ranks = pd.DataFrame({k: v.rolling(252, min_periods=200).rank(pct=True) for k, v in comp.items()})
    fg = 100 * ranks.mean(axis=1, skipna=True)
    u = fg.index.union(index)
    return fg.reindex(u).ffill().shift(1).reindex(index)


def sigma_daily(r):
    return np.sqrt(0.5 * r.pow(2).ewm(alpha=0.06, adjust=False).mean() + 0.5 * r.rolling(756, min_periods=500).var())


def ifc_parts(P):
    run, cgo = {}, {}
    for t in P.columns:
        df = data.get_history(t)[0]
        px = df["adj"].astype(float)
        b = F.align(data.get_history(benchmark_for(t))[0]["adj"].astype(float), px.index)
        r, rb = np.log(px).diff(), np.log(b).diff().fillna(0)
        e = r - F.rolling_beta(r, rb).shift(1) * rb
        run[t] = e.rolling(126, min_periods=120).sum()
        cgo[t] = F.capital_gains_overhang(px, df["volume"])
    f = lambda d: pd.DataFrame(d).reindex(P.index).ffill(limit=5).rank(axis=1, pct=True)  # noqa: E731
    return f(run), f(cgo)


def pinball(y, q, tau):
    d = y - q
    return np.maximum(tau * d, (tau - 1) * d)


def nw_t(s, lags=1):
    s = pd.Series(s).dropna()
    n = len(s)
    if n < 10:
        return None
    x = s.values - s.values.mean()
    v = (x @ x) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (x[L:] @ x[:-L]) / n
    return round(float(s.mean() / math.sqrt(v / n)), 2) if v > 0 else None


def run_universe(name, tickers):
    P, _ = load(tickers)
    P = P[P.index >= START]
    lp = np.log(P)
    r = lp.diff()
    sd = sigma_daily(r)
    volreg = np.log(r.rolling(21).std() / r.rolling(252, min_periods=200).std())
    fg = fear_greed(P.index)
    extra = ifc_parts(P) if name == "azioni" else None
    out = {}
    for hz, h in H.items():
        dates = _origins(P.index, h)
        pos = {d: P.index.get_loc(d) for d in dates}
        z = ((lp.shift(-h) - lp) / (sd * math.sqrt(h))).loc[dates]
        cols = {"fg": pd.DataFrame({t: fg for t in P.columns}).loc[dates] / 100, "volreg": volreg.loc[dates]}
        if extra is not None:
            cols["run"], cols["cgo"] = extra[0].loc[dates], extra[1].loc[dates]
        X = pd.concat({k: v.stack(future_stack=True) for k, v in cols.items()}, axis=1)
        X["z"] = z.stack(future_stack=True)
        X = X.dropna(subset=["fg", "volreg"] + (["run", "cgo"] if extra is not None else []))
        X = X[np.isfinite(X["volreg"])]
        X["pos"] = [pos[d] for d in X.index.get_level_values(0)]
        feats = [c for c in X.columns if c not in ("z", "pos")]
        rows = []
        refits = list(range(X["pos"].min() + 3 * REFIT, X["pos"].max() + 1, REFIT))
        for i, rp in enumerate(refits):
            nxt = refits[i + 1] if i + 1 < len(refits) else 10 ** 9
            tr = X[(X["pos"] + h <= rp) & X["z"].notna()]
            te = X[(X["pos"] >= rp) & (X["pos"] < nxt) & X["z"].notna()]
            if len(tr) < 500 or te.empty:
                continue
            pm = np.column_stack([QuantileRegressor(quantile=q, alpha=0.01, solver="highs")
                                  .fit(tr[feats].values, tr["z"].values).predict(te[feats].values) for q in QS])
            pm.sort(axis=1)
            pb = np.tile(np.quantile(tr["z"].values, QS), (len(te), 1))
            y = te["z"].values
            lm = sum(pinball(y, pm[:, j], q) for j, q in enumerate(QS))
            lb = sum(pinball(y, pb[:, j], q) for j, q in enumerate(QS))
            rows.append(pd.DataFrame({"date": te.index.get_level_values(0), "lm": lm, "lb": lb,
                                      "cov_m": (y >= pm[:, 0]) & (y <= pm[:, 2]),
                                      "cov_b": (y >= pb[:, 0]) & (y <= pb[:, 2])}))
        R = pd.concat(rows)
        per = R.groupby("date")[["lm", "lb"]].mean()
        diff = per["lb"] - per["lm"]
        post = diff[diff.index.year >= 2013]
        out[hz] = {"rows": int(len(R)), "dates": int(len(per)), "from": str(per.index[0].date()),
                   "loss_model": round(float(R["lm"].mean()), 4), "loss_bench": round(float(R["lb"].mean()), 4),
                   "improvement_pct": round(float(100 * (1 - R["lm"].mean() / R["lb"].mean())), 2),
                   "t": nw_t(diff), "cov_model": round(float(R["cov_m"].mean()), 3),
                   "cov_bench": round(float(R["cov_b"].mean()), 3),
                   "post2013_improvement": round(float(post.mean()), 4), "post2013_t": nw_t(post)}
        print(name, hz, out[hz], file=sys.stderr)
    return out


def main():
    unis = {"azioni": stock_universe(), "paesi": UNIVERSES["paesi"], "settori": UNIVERSES["settori"],
            "indici": UNIVERSES["indici"]}
    res = {u: run_universe(u, t) for u, t in unis.items()}
    passed = {u: any((r[h]["t"] or 0) >= 3 and r[h]["improvement_pct"] > 0 for h in r) for u, r in res.items()}
    c2 = all(0.77 <= r[h]["cov_model"] <= 0.83 for r in res.values() for h in r)
    c3 = all(r[h]["post2013_improvement"] > 0 for u, r in res.items() if passed[u] for h in r)
    res["criteria"] = {"C1": sum(passed.values()) >= 3, "C2": c2, "C3": c3, "C1_per_universo": passed}
    res["success"] = bool(res["criteria"]["C1"] and c2 and c3)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
