"""Punteggio multi-fattore (momentum, value, quality, bassa volatilità) sull'S&P 500: test pre-registrato,
vedi PREREG_MULTIFATTORE.md.   Lancio:  python -m lab.multifactor
"""
import io
import json
import math
import sys

import numpy as np
import pandas as pd
import requests

import config
import db
from sources.sec_fundamentals import fundamentals

from .insider_test import series
from .panel import _origins

H = {"45gg": 31, "90gg": 63}
START = "2011-01-01"


def sp500():
    r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", timeout=30,
                     headers={"User-Agent": "Oracolo/1.0 (https://github.com/brunocottino/Oracolo)"})
    t = pd.read_html(io.StringIO(r.text))[0]
    return [(s.replace(".", "-"), int(c)) for s, c in zip(t["Symbol"], t["CIK"])]


def step(pairs, index):
    if not pairs:
        return pd.Series(np.nan, index=index)
    s = pd.Series({pd.Timestamp(d): v for d, v in pairs}).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(s.index.union(index)).ffill().reindex(index)


def build():
    db.init()
    adj, raw, fund = {}, {}, {}
    for i, (t, cik) in enumerate(sp500()):
        try:
            px = series(t)
            f = fundamentals(cik)
        except Exception as e:
            print("salto", t, e, file=sys.stderr)
            continue
        if px is None or f is None:
            continue
        adj[t], raw[t], fund[t] = px["adj"], px["raw_close"], f
        print(f"\r{i + 1} {t}   ", end="", file=sys.stderr)
    A = pd.DataFrame(adj).sort_index()
    A = A[A.index >= "2009-01-01"].ffill(limit=5)
    R = pd.DataFrame(raw).reindex(A.index).ffill(limit=5)
    get = lambda k: pd.DataFrame({t: step(fund[t].get(k), A.index) for t in A})  # noqa: E731
    ni, gp, eq, assets, sh = (get(k) for k in ("ni", "gp", "eq", "assets", "shares"))
    cap = R * sh
    lr = np.log(A).diff()
    raw_f = {
        "mom": A.shift(21) / A.shift(252) - 1,
        "bp": eq.where(eq > 0) / cap, "ep": ni / cap,
        "gpa": gp / assets, "roe": ni / eq.where(eq > 0),
        "lowvol": -lr.rolling(252, min_periods=200).std(),
    }
    rk = {k: v.replace([np.inf, -np.inf], np.nan).rank(axis=1, pct=True) for k, v in raw_f.items()}
    fac = {"momentum": rk["mom"], "value": pd.concat([rk["bp"], rk["ep"]]).groupby(level=0).mean(),
           "quality": pd.concat([rk["gpa"], rk["roe"]]).groupby(level=0).mean(), "lowvol": rk["lowvol"]}
    stack = np.stack([f.reindex(A.index).values for f in fac.values()])
    n_ok = np.isfinite(stack).sum(axis=0)
    score = pd.DataFrame(np.where(n_ok >= 3, np.nanmean(stack, axis=0), np.nan), index=A.index, columns=A.columns)
    return A, score, fac


def nw_t(s, lags=1):
    s = pd.Series(s).dropna()
    n = len(s)
    x = s.values - s.values.mean()
    v = (x @ x) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (x[L:] @ x[:-L]) / n
    return round(float(s.mean() / math.sqrt(v / n)), 2) if n > 10 and v > 0 else None


def evaluate(A, sig, h, dates):
    fwd = A.shift(-h) / A - 1
    ic, top = {}, {}
    for d in dates:
        s, f = sig.loc[d], fwd.loc[d]
        ok = s.notna() & f.notna()
        if ok.sum() < 50:
            continue
        ic[d] = s[ok].rank().corr(f[ok].rank())
        top[d] = f[ok][s[ok] >= s[ok].quantile(2 / 3)].mean() - f[ok].mean()
    ic, top = pd.Series(ic), pd.Series(top)
    return {"dates": len(ic), "names_median": None, "ic": round(float(ic.mean()), 4), "t": nw_t(ic),
            "top_excess": round(float(top.mean()), 4), "top_t": nw_t(top),
            "ic_2016": round(float(ic[ic.index.year >= 2016].mean()), 4), "t_2016": nw_t(ic[ic.index.year >= 2016])}


def main():
    A, score, fac = build()
    cal = A.index
    hold = len(cal) - config.LAB["holdout"]
    res = {"tickers": int(A.shape[1])}
    for hz, h in H.items():
        dates = [d for d in _origins(cal, h) if d >= pd.Timestamp(START)]
        dev = [d for d in dates if cal.get_loc(d) + h < hold]
        ho = [d for d in dates if cal.get_loc(d) >= hold and cal.get_loc(d) + h < len(cal)]
        res[hz] = {"oracolo": evaluate(A, score, h, dev), "holdout": evaluate(A, score, h, ho),
                   **{k: evaluate(A, v, h, dev) for k, v in fac.items()}}
    o45, o90 = res["45gg"]["oracolo"], res["90gg"]["oracolo"]
    res["criteria"] = {"M1": o45["ic"] > 0 and (o45["t"] or 0) >= 3, "M2": o90["ic"] > 0 and (o90["t"] or 0) >= 2,
                       "M3": o45["ic_2016"] > 0 and o90["ic_2016"] > 0, "M4": o45["top_excess"] > 0}
    res["success"] = all(res["criteria"].values())
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
