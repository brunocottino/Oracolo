"""Comprare dopo un calo anomalo / vendere dopo un rialzo anomalo: test pre-registrato (PREREG_ANOMALIE.md).
Lancio:  python -m lab.anomaly_test"""
import json
import math

import numpy as np
import pandas as pd

import config

from .band_test import sigma_daily
from .horizon_test import HORIZONS, evaluate, load
from .oracolo_index import UNIVERSES
from .panel import _origins, stock_universe


def states(P, kind):
    lp = np.log(P)
    z = (lp - lp.shift(31)) / (sigma_daily(lp.diff()) * math.sqrt(31))
    lo, hi, _ = config.BANDS[kind][31]
    s = pd.DataFrame("STAI FERMO", index=P.index, columns=P.columns)
    s[z < lo] = "COMPRA"      # calo anomalo
    s[z > hi] = "VENDI"       # rialzo anomalo
    return s.where(z.notna())


def main():
    unis = {"azioni": (stock_universe(), "azioni"), "paesi": (UNIVERSES["paesi"], "etf"),
            "settori": (UNIVERSES["settori"], "etf"), "indici": (UNIVERSES["indici"], "etf")}
    out = {}
    for u, (tick, kind) in unis.items():
        P, _ = load(tick)
        sig = states(P, kind)
        cal = P.index
        hold = len(cal) - config.LAB["holdout"]
        for hz, h in HORIZONS.items():
            ds = _origins(cal, h)
            pos = cal.get_indexer(ds)
            dev = [d for d, p in zip(ds, pos) if p + h < hold]
            ho = [d for d, p in zip(ds, pos) if p >= hold and p + h < len(cal)]
            fwd = P.shift(-h) / P - 1
            norm = fwd.loc[dev].mean()
            e = {k: evaluate(sig, fwd, x, norm) for k, x in (("dev", dev), ("post2013", [d for d in dev if d.year >= 2013]), ("holdout", ho))}
            c, v = e["dev"].get("COMPRA", {}), e["dev"].get("VENDI", {})
            e["H1"] = bool((c.get("edge") or 0) > 0 and (c.get("t") or 0) >= 2 and (e["post2013"].get("COMPRA", {}).get("edge") or 0) > 0)
            e["H2"] = bool((v.get("edge") or 0) < 0 and (v.get("t") or 0) <= -2 and (e["post2013"].get("VENDI", {}).get("edge") or 0) < 0)
            out[f"{u}|{hz}"] = e
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
