"""RSI ipervenduto / ipercomprato: test pre-registrato (PREREG_RSI.md).  Lancio: python -m lab.rsi_test"""
import json

import numpy as np
import pandas as pd

import config
from universe import MARKETS

from .horizon_test import evaluate
from .multifactor import sp500
from .oracolo_index import UNIVERSES
from .search2000 import load

H = {"5": 5, "21": 21, "45gg": 31, "90gg": 63}


def rsi(P, n):
    d = P.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def signals(P):
    r14, r2 = rsi(P, 14), rsi(P, 2)
    sma = P.rolling(200, min_periods=200).mean()
    out = {}
    s = pd.DataFrame("STAI FERMO", index=P.index, columns=P.columns)
    s[r14 < 30], s[r14 > 70] = "COMPRA", "VENDI"
    out["rsi14"] = s.where(r14.notna())
    s = pd.DataFrame("STAI FERMO", index=P.index, columns=P.columns)
    s[(r2 < 10) & (P > sma)], s[r2 > 90] = "COMPRA", "VENDI"
    out["rsi2"] = s.where(r2.notna() & sma.notna())
    return out


def main():
    unis = {"sp500": [t for t, _ in sp500()], "europa": [t for m in ("Italia", "Europa") for t in MARKETS[m]],
            "indici": UNIVERSES["indici"], "settori": UNIVERSES["settori"], "paesi": UNIVERSES["paesi"]}
    res = {}
    for u, tick in unis.items():
        P, _, _ = load(tick)
        sig = signals(P)
        cal = P.index
        hold = len(cal) - config.LAB["holdout"]
        for hz, h in H.items():
            ds = cal[::h]
            pos = cal.get_indexer(ds)
            dev = [d for d, p in zip(ds, pos) if p + h < hold and d.year >= 1995]
            ho = [d for d, p in zip(ds, pos) if p >= hold and p + h < len(cal)]
            fwd = P.shift(-h) / P - 1
            norm = fwd.loc[dev].mean()
            for sn, S in sig.items():
                e = {k: evaluate(S, fwd, x, norm) for k, x in
                     (("dev", dev), ("post2013", [d for d in dev if d.year >= 2013]), ("holdout", ho))}
                c, v = e["dev"].get("COMPRA", {}), e["dev"].get("VENDI", {})
                okc = (c.get("edge") or 0) > 0 and (c.get("t") or 0) >= 3 and \
                    (e["post2013"].get("COMPRA", {}).get("edge") or 0) > 0 and (e["holdout"].get("COMPRA", {}).get("edge") or 0) > 0
                okv = (v.get("edge") or 0) < 0 and (v.get("t") or 0) <= -3 and \
                    (e["post2013"].get("VENDI", {}).get("edge") or 0) < 0 and (e["holdout"].get("VENDI", {}).get("edge") or 0) < 0
                e.update(compra_ok=bool(okc), vendi_ok=bool(okv))
                res[f"{u}|{sn}|{hz}"] = e
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
