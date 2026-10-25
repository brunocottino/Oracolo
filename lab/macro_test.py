"""Weight of evidence stile Ned Davis a 45/90 giorni: test pre-registrato, vedi PREREG_MACRO.md.

Lancio:  python -m lab.macro_test
"""
import json

import numpy as np
import pandas as pd

import config
import data

from .horizon_test import HORIZONS, evaluate, load
from .panel import _origins

ASSETS = "^GSPC ^NDX ^DJI ^RUT SPY QQQ IWM XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()
START = "1990-01-01"


def votes(P):
    m = {t: data.get_history(t)[0]["close"].astype(float) for t in ("^IRX", "^TNX", "^VIX")}
    M = pd.DataFrame(m).reindex(P.index).ffill(limit=5).shift(1)        # macro: dato del giorno prima
    sma = P.rolling(200, min_periods=200).mean()
    v = {
        "tape": np.sign((P > sma).astype(float) - 0.5).where(sma.notna()),
        "fed": pd.DataFrame({c: np.where(M["^IRX"] <= M["^IRX"].shift(126), 1.0, -1.0) for c in P}, index=P.index)
               .where(M["^IRX"].shift(126).notna(), np.nan),
        "curva": pd.DataFrame({c: np.where(M["^TNX"] - M["^IRX"] > 0, 1.0, -1.0) for c in P}, index=P.index)
                 .where(M[["^TNX", "^IRX"]].notna().all(axis=1), np.nan),
        "sentiment": pd.DataFrame({c: np.where(M["^VIX"] < M["^VIX"].rolling(252, min_periods=252).mean(), 1.0, -1.0)
                                   for c in P}, index=P.index)
                     .where(M["^VIX"].rolling(252, min_periods=252).mean().notna(), np.nan),
    }
    return v


def to_state(score, buy=2, sell=-2):
    s = pd.DataFrame("STAI FERMO", index=score.index, columns=score.columns)
    s[score >= buy] = "COMPRA"
    s[score <= sell] = "VENDI"
    return s.where(score.notna())


def main():
    P, _ = load(ASSETS)
    P = P[P.index >= START]
    v = votes(P)
    score = sum(v.values())
    sigs = {"weight_of_evidence": to_state(score)}
    sigs.update({k: to_state(x, 1, -1) for k, x in v.items()})       # voti da soli (informativo)
    cal = P.index
    hold_start = len(cal) - config.LAB["holdout"]
    res = {}
    for hz, h in HORIZONS.items():
        dates = _origins(cal, h)
        pos = cal.get_indexer(dates)
        dev = [d for d, p in zip(dates, pos) if p + h < hold_start]
        post = [d for d in dev if d.year >= 2013]
        hold = [d for d, p in zip(dates, pos) if p >= hold_start and p + h < len(cal)]
        fwd = P.shift(-h) / P - 1
        norm = fwd.loc[dev].mean()
        for sn, sig in sigs.items():
            e = {k: evaluate(sig, fwd, ds, norm) for k, ds in (("dev", dev), ("post2013", post), ("holdout", hold))}
            c, vd = e["dev"].get("COMPRA", {}), e["dev"].get("VENDI", {})
            u1c = (c.get("edge") or 0) > 0 and (c.get("t") or 0) >= 3
            u1v = (vd.get("edge") or 0) < 0 and (vd.get("t") or 0) <= -3
            pc, pv = e["post2013"].get("COMPRA", {}), e["post2013"].get("VENDI", {})
            u2 = (u1c or u1v) and ((not u1c) or (pc.get("edge") or 0) > 0) and ((not u1v) or (pv.get("edge") or 0) < 0)
            u3 = (c.get("pct_up") or 0) > (vd.get("pct_up") or 1)
            e.update(utile=bool((u1c or u1v) and u2 and u3), dev_from=str(dev[0].date()))
            res[f"{sn}|{hz}"] = e
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
