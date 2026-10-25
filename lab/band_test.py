"""Affidabilità della forchetta attesa (bande di prezzo) a 45 e 90 giorni.
Criterio fissato prima: la banda 80% deve contenere 77-83% dei risultati, la 90% 87-93%,
fuori campione, su azioni ed ETF. Volatilità come agents/base.horizon_sigma (EWMA 0,94 + storica 3 anni).

Lancio:  python -m lab.band_test
"""
import json
import math

import numpy as np
import pandas as pd

from .horizon_test import load
from .oracolo_index import UNIVERSES
from .panel import _origins, stock_universe

H = {"45gg": 31, "90gg": 63}
Z80, Z90 = 1.2816, 1.6449


def sigma_daily(r):
    """Serie causale della volatilità giornaliera: sqrt(0,5 EWMA² + 0,5 storica 756²)."""
    ew = r.pow(2).ewm(alpha=0.06, adjust=False).mean()
    lr = r.rolling(756, min_periods=500).var()
    return np.sqrt(0.5 * ew + 0.5 * lr)


def run(tickers):
    P, _ = load(tickers)
    lp = np.log(P)
    r = lp.diff()
    sd = sigma_daily(r)
    out = {}
    for hz, h in H.items():
        dates = _origins(P.index, h)
        fut = (lp.shift(-h) - lp).loc[dates]
        s = (sd * math.sqrt(h)).loc[dates]
        z = (fut / s).stack().dropna()          # media ~0 su 45/90 gg: banda centrata sul prezzo attuale
        z = z[np.isfinite(z)]
        yrs = z.index.get_level_values(0).year
        # versione calibrata: quantili 10%/90% dei z passati già conclusi (solo dati noti alla data)
        dpos = {d: P.index.get_loc(d) for d in dates}
        zl, zh, hit = [], [], []
        for d in dates:
            past = z[[dpos[x] + h <= dpos[d] for x in z.index.get_level_values(0)]] if len(z) else z
            if len(past) < 300:
                continue
            lo, hi = np.quantile(past, 0.10), np.quantile(past, 0.90)
            cur = z[z.index.get_level_values(0) == d]
            hit += list(((cur >= lo) & (cur <= hi)).values)
            zl.append(lo); zh.append(hi)
        cal = {"cov80_calibrata": round(float(np.mean(hit)), 3), "n_calibrata": len(hit),
               "z_lo_ultimo": round(zl[-1], 2) if zl else None, "z_hi_ultimo": round(zh[-1], 2) if zh else None}
        out[hz] = {**cal, "n": int(len(z)),
                   "cov80": round(float((z.abs() <= Z80).mean()), 3),
                   "cov90": round(float((z.abs() <= Z90).mean()), 3),
                   "below80": round(float((z < -Z80).mean()), 3), "above80": round(float((z > Z80).mean()), 3),
                   "cov80_since2013": round(float((z[yrs >= 2013].abs() <= Z80).mean()), 3),
                   "worst_year_cov80": round(float(z.abs().le(Z80).groupby(yrs).mean().min()), 3)}
    return out


def main():
    res = {"azioni": run(stock_universe()), "ETF_paesi": run(UNIVERSES["paesi"]), "settori": run(UNIVERSES["settori"])}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
