"""Segnale Panico con tassi americani in salita: test pre-registrato (PREREG_PANICO_TASSI.md).
python -m lab.panic_rates_test"""
import json

import numpy as np
import pandas as pd

import data
import db

from .horizon_test import evaluate
from .panic_test import TICKERS, panic_score
from .search2000 import load

H = 21
SALITA = 0.50  # punti percentuali in 63 sedute


def regime(index):
    tnx = data.get_history("^TNX")[0]["close"].astype(float)
    tnx = tnx.reindex(tnx.index.union(index)).ffill()
    up = (tnx.shift(1) - tnx.shift(64)) >= SALITA  # fino a t-1
    return up.reindex(index)


def main():
    db.init()
    P, _, _ = load(TICKERS)
    P = P[P.index >= "1993-01-01"]
    sc = panic_score(P)
    sig = pd.DataFrame(np.where(sc >= 2, "COMPRA", "STAI FERMO"), index=P.index, columns=P.columns).where(sc.notna())
    up = regime(P.index)
    cal = P.index
    ds = [d for d in cal[::H] if cal.get_loc(d) + H < len(cal)]
    fwd = P.shift(-H) / P - 1
    norm = fwd.loc[ds].mean()
    res = {}
    for nome, sel in (("tassi_in_salita", [d for d in ds if up.get(d) is True or up.get(d) == True]),  # noqa: E712
                      ("tassi_non_in_salita", [d for d in ds if not bool(up.get(d))])):
        r = evaluate(sig, fwd, sel, norm)
        res[nome] = {"date": len(sel), **r}
    c = res["tassi_in_salita"].get("COMPRA", {})
    res["valido_con_tassi_in_salita"] = bool((c.get("edge") or 0) > 0 and (c.get("t") or 0) >= 1.5)
    res["date_compra_con_tassi_in_salita"] = c.get("dates", 0)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return res


if __name__ == "__main__":
    main()
