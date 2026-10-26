"""Indice di Panico Oracolo: test fuori campione pre-registrato (PREREG_PANICO.md).  python -m lab.panic_test"""
import json
import math

import numpy as np
import pandas as pd

import config
import data

from .band_test import sigma_daily
from .horizon_test import evaluate
from .rsi_test import rsi
from .search2000 import load

TICKERS = "^AEX ^IBEX ^OMX ^ATX ^BFX ^PSI20 ^BVSP ^GSPTSE ^MXX ^MERV ^IPSA ^AXJO ^KS11 ^TWII ^JKSE ^STI ^NSEI".split()
H = {"21": 21, "45gg": 31, "90gg": 63}


def panic_score(P):
    lp = np.log(P)
    z = (lp - lp.shift(31)) / (sigma_daily(lp.diff()) * math.sqrt(31))
    v1 = (rsi(P, 14) < 30).astype(float)
    v2 = (z < config.BANDS["etf"][31][0]).astype(float)
    vix = data.get_history("^VIX")[0]["close"].astype(float)
    vix = vix.reindex(vix.index.union(P.index)).ffill().shift(1).reindex(P.index)
    v3 = pd.DataFrame({c: (vix > vix.rolling(252, min_periods=200).mean()).astype(float) for c in P}, index=P.index)
    ok = z.notna() & vix.rolling(252, min_periods=200).mean().reindex(P.index).notna().values[:, None]
    return (v1 + v2 + v3).where(ok)


def main():
    P, _, _ = load(TICKERS)
    P = P[P.index >= "1993-01-01"]
    sc = panic_score(P)
    sig = pd.DataFrame(np.where(sc >= 2, "COMPRA", "STAI FERMO"), index=P.index, columns=P.columns).where(sc.notna())
    cal = P.index
    res = {"indici": list(P.columns)}
    for hz, h in H.items():
        ds = [d for d in cal[::h] if cal.get_loc(d) + h < len(cal)]
        fwd = P.shift(-h) / P - 1
        norm = fwd.loc[ds].mean()
        res[hz] = {k: evaluate(sig, fwd, x, norm) for k, x in (("tutto", ds), ("dal2013", [d for d in ds if d.year >= 2013]))}
    c = res["21"]["tutto"].get("COMPRA", {})
    res["successo"] = bool((c.get("edge") or 0) > 0 and (c.get("t") or 0) >= 2 and (res["21"]["dal2013"].get("COMPRA", {}).get("edge") or 0) > 0)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
