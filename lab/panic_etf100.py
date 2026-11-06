"""Panico su 100 ETF, pre-registrato (PREREG_PANICO_ETF100.md).  python -m lab.panic_etf100"""
import json
import numpy as np
import pandas as pd
import config
from .horizon_test import evaluate
from .panic_test import panic_score
from .search2000 import load

GROUPS = {
    "A_aree": "SPY QQQ DIA IWM MDY EFA EEM VGK EWJ EWG EWU EWQ EWI EWP EWL EWN EWD EWC EWA EWH EWS EWT EWY EWZ EWW INDA FXI MCHI EZA TUR EWM THD EIDO ECH ACWI",
    "B_settori": "XLK XLF XLV XLE XLI XLY XLP XLU XLB XLRE XLC VNQ IYT KBE KRE XHB XRT XOP OIH SMH SOXX IBB XBI ITA MTUM QUAL USMV VLUE SIZE IWF",
    "C_tematici": "ARKK ARKG ARKQ ARKW TAN ICLN PBW QCLN LIT URA URNM COPX GDX GDXJ SIL REMX HACK CIBR BOTZ ROBO SKYY CLOU FINX KWEB ESPO PHO CGW PAVE IPAY SOCL BLOK QTUM UFO NLR JETS",
}


def run(tickers):
    P, _, _ = load(tickers)
    sc = panic_score(P)
    cal = P.index
    hold = cal[len(cal) - config.LAB["holdout"]]
    out = {"etf": int(P.shape[1]), "oggi": {t: (None if pd.isna(v) else int(v)) for t, v in sc.iloc[-1].items()}}
    for hz, h in (("21", 21), ("63", 63)):
        ds = [d for d in cal[::h] if cal.get_loc(d) + h < len(cal)]
        fwd = P.shift(-h) / P - 1
        norm = fwd.loc[ds].mean()
        res = {}
        for lv in (2, 3):
            sig = pd.DataFrame(np.where(sc >= lv, "COMPRA", "STAI FERMO"), index=cal, columns=P.columns).where(sc.notna())
            parts = {"sviluppo": [d for d in ds if d < hold], "dal2013": [d for d in ds if hold > d and d.year >= 2013],
                     "holdout": [d for d in ds if d >= hold]}
            res[f"voti>={lv}"] = {k: evaluate(sig, fwd, v, norm).get("COMPRA", {}) for k, v in parts.items()}
        out[hz] = res
    r = out["21"]["voti>=2"]
    out["successo"] = bool((r["sviluppo"].get("edge") or 0) > 0 and (r["sviluppo"].get("t") or 0) >= 3
                           and (r["dal2013"].get("edge") or 0) > 0 and (r["holdout"].get("edge") or 0) > 0)
    return out


def main():
    res = {g: run(t.split()) for g, t in GROUPS.items()}
    json.dump(res, open("data/panic_etf100.json", "w"), indent=1, default=str)
    for g, r in res.items():
        print(g, r["etf"], "ETF, successo:", r["successo"])
        for hz in ("21", "63"):
            for lv, x in r[hz].items():
                print(f"  {hz} sedute {lv}: " + " | ".join(f"{k} {v.get('edge', 0):+.2%} t {v.get('t', 0)} n {v.get('dates', 0)} rialzi {v.get('pct_up', 0):.0%}" for k, v in x.items()))


if __name__ == "__main__":
    main()
