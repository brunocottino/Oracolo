"""EPS trimestrali point-in-time da SEC EDGAR companyfacts (gratuito, solo User-Agent) e SUE stagionale.

Per ogni trimestre si tiene il primo valore depositato (niente riesposizioni). Disponibile da deposito + 2 giorni.
SUE = (EPS_q - EPS_{q-4}) / dev. standard delle ultime 8 sorprese (Bernard-Thomas 1989, Livnat-Mendenhall 2006)."""
import numpy as np
import pandas as pd

from .common import cached, get

URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
NAMES = ["EarningsPerShareDiluted", "EarningsPerShareBasic"]


def quarters(facts) -> pd.DataFrame:
    """Tabella end, eps, filed (un trimestre per riga, ordinata per fine periodo)."""
    for nm in NAMES:
        u = facts.get("us-gaap", {}).get(nm, {}).get("units", {}).get("USD/shares")
        if not u:
            continue
        df = pd.DataFrame([x for x in u if x.get("start") and x.get("filed")
                           and str(x.get("form", "")).startswith(("10-Q", "10-K"))])
        if df.empty:
            continue
        for c in ("start", "end", "filed"):
            df[c] = pd.to_datetime(df[c])
        df["days"] = (df["end"] - df["start"]).dt.days
        df = df.sort_values("filed")
        q = df[df["days"].between(80, 100)].groupby("end").first()[["val", "filed"]]
        fy = df[df["days"].between(350, 380)].groupby("end").first()[["val", "filed", "start"]]
        for end, r in fy.iterrows():          # Q4 mancante = anno - tre trimestri
            if end in q.index:
                continue
            inside = q[(q.index > r["start"]) & (q.index < end - pd.Timedelta(days=60))]
            if len(inside) == 3:
                q.loc[end] = [r["val"] - inside["val"].sum(), r["filed"]]
        q = q.sort_index()
        if len(q) >= 8:
            return q.rename(columns={"val": "eps"}).reset_index()
    return pd.DataFrame(columns=["end", "eps", "filed"])


def sue_table(q: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge sue e avail (= deposito + 2 giorni)."""
    q = q.copy().reset_index(drop=True)
    prev = []
    for e in q["end"]:
        m = q[(q["end"] >= e - pd.Timedelta(days=380)) & (q["end"] <= e - pd.Timedelta(days=350))]
        prev.append(m["eps"].iloc[-1] if len(m) else np.nan)
    q["surp"] = q["eps"] - np.array(prev, dtype=float)
    sd = q["surp"].shift(1).rolling(8, min_periods=4).std()
    q["sue"] = (q["surp"] / sd.where(sd > 0)).clip(-10, 10)
    q["avail"] = q["filed"] + pd.Timedelta(days=2)
    return q.dropna(subset=["sue"])


def sue_series(cik, index: pd.DatetimeIndex, fresh_days=90) -> pd.Series:
    """SUE valida a ogni data dell'indice: ultimo deposito disponibile, solo se più recente di fresh_days."""
    rows = sue_pairs(cik)
    if not rows:
        return pd.Series(np.nan, index=index)
    s = pd.Series({pd.Timestamp(a): v for a, v in rows}).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    d = pd.Series(s.index, index=s.index)
    full = s.index.union(index)
    val, when = s.reindex(full).ffill(), d.reindex(full).ffill()
    age = (full.to_series() - when).dt.days
    return val.where(age <= fresh_days).reindex(index)


def sue_pairs(cik):
    def fetch():
        f = get(URL.format(cik=int(cik)), host_gap=0.15, timeout=60).json()["facts"]
        t = sue_table(quarters(f))
        return [[str(a.date()), float(v)] for a, v in zip(t["avail"], t["sue"])]
    return cached(f"secsue:{int(cik)}", 30 * 86400, fetch)
