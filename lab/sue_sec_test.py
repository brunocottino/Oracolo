"""Test pre-registrato (PREREG_SUE_SEC.md): SUE stagionale da SEC EDGAR sull'S&P 500 a 31 sedute.
Lancio: python -m lab.sue_sec_test"""
import json
import sys

import pandas as pd

import config
import db
from sources.sec_eps import sue_series

from .insider_test import series
from .multifactor import evaluate, sp500
from .panel import _origins

H, START = 31, "2011-01-01"


def build():
    db.init()
    adj, sue = {}, {}
    for i, (t, cik) in enumerate(sp500()):
        try:
            px = series(t)
            if px is None:
                continue
            adj[t] = px["adj"]
            sue[t] = cik
        except Exception as e:
            print("salto", t, e, file=sys.stderr)
        print(f"\r{i + 1} {t}   ", end="", file=sys.stderr)
    A = pd.DataFrame(adj).sort_index()
    A = A[A.index >= "2009-01-01"].ffill(limit=5)
    S = {}
    for t, cik in sue.items():
        try:
            S[t] = sue_series(cik, A.index)
        except Exception as e:
            print("salto SEC", t, e, file=sys.stderr)
    return A, pd.DataFrame(S).reindex(columns=A.columns)


def main():
    A, S = build()
    cal = A.index
    hold = len(cal) - config.LAB["holdout"]
    dates = [d for d in _origins(cal, H) if d >= pd.Timestamp(START)]
    dev = [d for d in dates if cal.get_loc(d) + H < hold]
    ho = [d for d in dates if cal.get_loc(d) >= hold and cal.get_loc(d) + H < len(cal)]
    d, h = evaluate(A, S, H, dev), evaluate(A, S, H, ho)
    cov = float(S.loc[dev].notna().sum(axis=1).median())
    res = {"tickers": int(A.shape[1]), "copertura_mediana": cov, "sviluppo": d, "holdout": h}
    res["criteria"] = {"S1": d["ic"] > 0 and (d["t"] or 0) >= 2, "S2": d["ic_2016"] > 0,
                       "S3": d["top_excess"] > 0, "S4": h["ic"] >= 0}
    res["success"] = all(res["criteria"].values())
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
