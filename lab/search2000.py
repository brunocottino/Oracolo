"""Ricerca su ~2000 prove con correzione per test multipli: vedi PREREG_2000.md.
Lancio:  python -m lab.search2000
"""
import json
import math
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

import data
import db
from sources.sec_fundamentals import fundamentals
from universe import MARKETS

from .insider_test import series
from .multifactor import sp500, step

HORIZONS = (5, 21, 31, 63, 126)
DEV_START, DEV_END, HOLD_START = "2010-07-01", "2022-12-31", "2023-01-01"
MIN_NAMES = {"sp500": 50, "europa": 15, "tutte": 60, "etf": 15}


def load(tickers, with_raw=False):
    A, V, R = {}, {}, {}
    for t in tickers:
        try:
            df = data.get_history(t)[0]
        except Exception as e:
            print("salto", t, str(e)[:50], file=sys.stderr)
            continue
        A[t], V[t] = df["adj"].astype(float), df["volume"].astype(float).replace(0, np.nan)
        if with_raw:
            s = series(t)
            if s is not None:
                R[t] = s["raw_close"]
    A = pd.DataFrame(A).sort_index()
    A = A[A.index >= "2008-06-01"].ffill(limit=5)
    V = pd.DataFrame(V).reindex(A.index)
    R = pd.DataFrame(R).reindex(A.index).ffill(limit=5) if with_raw else None
    return A, V, R


def features(A, V, R=None, fund=None):
    """Genera (nome, DataFrame) uno alla volta per non tenere tutto in memoria."""
    lr = np.log(A).diff()
    mkt = lr.mean(axis=1)
    for L in (21, 63, 126, 252):
        for skip in (0, 5, 21):
            if skip < L:
                yield f"mom_{L}_{skip}", A.shift(skip) / A.shift(L) - 1
    for L in (5, 10):
        yield f"rev_{L}", -(A / A.shift(L) - 1)
    sd = {L: lr.rolling(L, min_periods=int(L * 0.8)).std() for L in (21, 63, 126, 252)}
    for L, s in sd.items():
        yield f"vol_{L}", s
    yield "volratio_21_252", sd[21] / sd[252]
    yield "volratio_63_252", sd[63] / sd[252]
    for L in (126, 252):
        yield f"dist_high_{L}", A / A.rolling(L, min_periods=int(L * 0.8)).max() - 1
    yield "dist_low_252", A / A.rolling(252, min_periods=200).min() - 1
    for L in (20, 50, 100, 200):
        yield f"dist_sma_{L}", A / A.rolling(L, min_periods=L).mean() - 1
    yield "sma_50_200", A.rolling(50).mean() / A.rolling(200).mean() - 1
    for L in (63, 126, 252):
        yield f"skew_{L}", lr.rolling(L, min_periods=int(L * 0.8)).skew()
        yield f"kurt_{L}", lr.rolling(L, min_periods=int(L * 0.8)).kurt()
    for L in (21, 63):
        yield f"max_{L}", lr.rolling(L, min_periods=int(L * 0.8)).max()
    for L in (126, 252):
        cov = lr.rolling(L, min_periods=int(L * 0.8)).cov(mkt)
        beta = cov.div(mkt.rolling(L, min_periods=int(L * 0.8)).var(), axis=0)
        yield f"beta_{L}", beta
        yield f"ivol_{L}", (lr - beta.mul(mkt, axis=0)).rolling(L, min_periods=int(L * 0.8)).std()
    yield "dvol_21_252", np.log(V.rolling(21, min_periods=15).mean()) - np.log(V.rolling(252, min_periods=200).mean())
    yield "dvol_5_63", np.log(V.rolling(5, min_periods=4).mean()) - np.log(V.rolling(63, min_periods=50).mean())
    dv = (lr.abs() / (V * A)).replace([np.inf, -np.inf], np.nan)
    for L in (21, 63):
        yield f"amihud_{L}", dv.rolling(L, min_periods=int(L * 0.7)).mean()
    peak = A.rolling(252, min_periods=200).max()
    yield "drawdown_252", A / peak - 1
    yield "days_since_high", A.rolling(252, min_periods=200).apply(lambda w: len(w) - 1 - np.argmax(w), raw=True)
    seas = sum(A.shift(252 * k - 21) / A.shift(252 * k) - 1 for k in (1, 2, 3)) / 3
    yield "seasonal_month", seas
    e = lr.sub(mkt, axis=0)
    yield "run_126", e.rolling(126, min_periods=120).sum()
    tau = (0.004 * (V / V.rolling(252, min_periods=60).mean())).clip(0, 0.2).fillna(0.004)
    av, tv = A.values, tau.values
    out = np.empty_like(av)
    out[0] = av[0]
    for i in range(1, len(av)):
        prev = np.where(np.isnan(out[i - 1]), av[i], out[i - 1])
        out[i] = (1 - tv[i]) * prev + tv[i] * av[i]
    yield "cgo", (pd.DataFrame(av, index=A.index, columns=A.columns) - pd.DataFrame(out, index=A.index, columns=A.columns)).div(A).shift(5)
    if fund is not None and R is not None:
        get = lambda k: pd.DataFrame({t: step(fund[t].get(k), A.index) for t in A if t in fund})  # noqa: E731
        ni, gp, eq, assets, sh = (get(k).reindex(columns=A.columns) for k in ("ni", "gp", "eq", "assets", "shares"))
        cap = R * sh
        yield "bp", eq.where(eq > 0) / cap
        yield "ep", ni / cap
        yield "gpa", gp / assets
        yield "roe", ni / eq.where(eq > 0)
        yield "asset_growth", -(assets / assets.shift(252) - 1)
        yield "net_issuance", -(sh / sh.shift(252) - 1)
        yield "ni_growth", ni / ni.shift(252).abs() - 1


def ic_stats(Fr, T, dates):
    """IC di Spearman per data sui ranghi già calcolati."""
    ics = []
    for d in dates:
        f, y = Fr.loc[d], T.loc[d]
        ok = f.notna() & y.notna()
        if ok.sum() < MIN_NAMES_CUR[0]:
            continue
        a, b = f[ok].rank(), y[ok].rank()
        if a.std() > 0 and b.std() > 0:
            ics.append(float(np.corrcoef(a, b)[0, 1]))
    s = np.array(ics)
    n = len(s)
    if n < 10:
        return None
    x = s - s.mean()
    v = (x @ x) / n + (x[1:] @ x[:-1]) / n           # Newey-West, ritardo 1
    t = s.mean() / math.sqrt(max(v, 1e-12) / n)
    return {"ic": float(s.mean()), "t": float(t), "n": n}


MIN_NAMES_CUR = [50]


def run():
    db.init()
    sp = sp500()
    eu = [t for m in ("Italia", "Europa") for t in MARKETS[m]]
    etf = list(MARKETS["ETF UCITS"])
    A_us, V_us, R_us = load([t for t, _ in sp], with_raw=True)
    fund = {}
    for t, cik in sp:
        try:
            f = fundamentals(cik)
            if f:
                fund[t] = f
        except Exception:
            pass
    A_eu, V_eu, _ = load(eu)
    A_etf, V_etf, _ = load(etf)
    unis = {
        "sp500": (A_us, V_us, R_us, fund),
        "europa": (A_eu, V_eu, None, None),
        "tutte": (pd.concat([A_us, A_eu], axis=1).ffill(limit=5), pd.concat([V_us, V_eu], axis=1), None, None),
        "etf": (A_etf, V_etf, None, None),
    }
    rows = []
    for u, (A, V, R, F) in unis.items():
        MIN_NAMES_CUR[0] = MIN_NAMES[u]
        cal = A.index
        targets = {}
        sd63 = np.log(A).diff().rolling(63, min_periods=50).std()
        for h in HORIZONS:
            ds = [d for d in cal[::h] if d >= pd.Timestamp(DEV_START)]
            fwd = A.shift(-h) / A - 1
            dev = [d for d in ds if d <= pd.Timestamp(DEV_END) and cal.get_loc(d) + h < len(cal)]
            hold = [d for d in ds if d >= pd.Timestamp(HOLD_START) and cal.get_loc(d) + h < len(cal)]
            targets[h] = (dev, hold, {"ret": fwd, "ret_vol": fwd / (sd63 * math.sqrt(h))})
        for name, X in features(A, V, R, F):
            X = X.replace([np.inf, -np.inf], np.nan)
            for h, (dev, hold, T) in targets.items():
                for tn, Y in T.items():
                    d = ic_stats(X, Y, dev)
                    if d is None:
                        continue
                    hh = ic_stats(X, Y, hold)
                    rows.append({"universo": u, "misura": name, "h": h, "target": tn, **d,
                                 "p": float(2 * norm.sf(abs(d["t"]))),
                                 "ic_hold": hh["ic"] if hh else None, "t_hold": hh["t"] if hh else None})
            print(f"{u} {name} prove {len(rows)}", file=sys.stderr, flush=True)
    R = pd.DataFrame(rows)
    m = len(R)
    R = R.sort_values("p").reset_index(drop=True)
    R["bh_limit"] = 0.05 * (np.arange(1, m + 1)) / m
    passed = R["p"] <= R["bh_limit"]
    k = passed[::-1].idxmax() if passed.any() else -1
    R["bh"] = R.index <= k if passed.any() else False
    R["t3"] = R["t"].abs() >= 3
    R["hold_ok"] = (np.sign(R["ic_hold"]) == np.sign(R["ic"])) & (R["ic_hold"].abs() >= 0.5 * R["ic"].abs())
    R["sopravvive"] = R["bh"] & R["t3"] & R["hold_ok"]
    return R


def main():
    R = run()
    R.to_csv("NOTE_2000_prove.csv", index=False)
    S = R[R["sopravvive"]]
    out = {"prove": int(len(R)), "bh": int(R["bh"].sum()), "bh_e_t3": int((R["bh"] & R["t3"]).sum()),
           "sopravvissute": int(len(S)),
           "per_famiglia": S.assign(fam=S["misura"].str.split("_").str[0]).groupby(["universo", "fam"]).size().to_dict()}
    print(json.dumps({k: (v if not isinstance(v, dict) else {str(a): b for a, b in v.items()}) for k, v in out.items()}, indent=1))
    print(S.head(40).round(4).to_string())


if __name__ == "__main__":
    main()
