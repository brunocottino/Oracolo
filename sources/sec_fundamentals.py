"""Bilanci annuali point-in-time da SEC EDGAR companyfacts (gratuito, solo User-Agent).
Ogni valore ha la data da cui era pubblico: max(deposito + 2 giorni, fine esercizio + 90 giorni) (principio C)."""
import pandas as pd

from .common import cached, get

URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FLOW = {"ni": ["NetIncomeLoss"], "gp": ["GrossProfit"]}
STOCK = {"eq": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
         "assets": ["Assets"]}


def _annual(facts, names):
    for nm in names:
        u = facts.get("us-gaap", {}).get(nm, {}).get("units", {}).get("USD")
        if not u:
            continue
        rows = [x for x in u if x.get("form") == "10-K" and x.get("fp") == "FY" and x.get("filed")]
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["end"], df["filed"] = pd.to_datetime(df["end"]), pd.to_datetime(df["filed"])
        df = df.sort_values("end").groupby("accn").tail(1)        # per deposito: l'esercizio più recente
        df["avail"] = pd.concat([df["filed"] + pd.Timedelta(days=2), df["end"] + pd.Timedelta(days=90)], axis=1).max(axis=1)
        return [[str(a.date()), float(v)] for a, v in zip(df["avail"], df["val"])]
    return []


def _shares(facts):
    u = facts.get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    return [[str((pd.Timestamp(x["filed"]) + pd.Timedelta(days=2)).date()), float(x["val"])] for x in u if x.get("filed")]


def fundamentals(cik):
    def fetch():
        f = get(URL.format(cik=int(cik)), host_gap=0.15, timeout=60).json()["facts"]
        out = {k: _annual(f, v) for k, v in {**FLOW, **STOCK}.items()}
        out["shares"] = _shares(f)
        return out
    return cached(f"secf:{int(cik)}", 30 * 86400, fetch)
