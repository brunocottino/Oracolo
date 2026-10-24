"""Acquisti degli insider (SEC Form 4) a 45 e 90 giorni: test pre-registrato, vedi PREREG_INSIDER.md.

Lancio:  python -m lab.insider_test
"""
import json
import math
import sys
import time

import numpy as np
import pandas as pd
import requests

import config
import data
import db
from sources import insider
from sources.common import cached

H = {"45gg": 31, "90gg": 63}
LAGS = {"45gg": 1, "90gg": 2}
WINDOW_DAYS = 14
MIN_INSIDERS = 3
DEDUP_DAYS = 90
MAX_E2_TICKERS = 4000
MAX_PRICE_GAP = 0.25


# --------------------------------------------------------------------------
# Eventi
# --------------------------------------------------------------------------
def events(ins: pd.DataFrame):
    ins = ins.dropna(subset=["ISSUERCIK", "FILING_DATE"]).copy()
    ins["FILING_DATE"] = pd.to_datetime(ins["FILING_DATE"])
    ins["TRANS_DATE"] = pd.to_datetime(ins["TRANS_DATE"], errors="coerce")
    ins["value"] = ins["TRANS_SHARES"] * ins["TRANS_PRICEPERSHARE"]
    e1, e2 = [], []
    for cik, g in ins.groupby("ISSUERCIK"):
        g = g.sort_values("FILING_DATE")
        days = g["FILING_DATE"].drop_duplicates().tolist()
        last1 = last2 = pd.Timestamp("1900-01-01")
        for d in days:
            win = g[(g["FILING_DATE"] > d - pd.Timedelta(days=WINDOW_DAYS)) & (g["FILING_DATE"] <= d)]
            today = g[g["FILING_DATE"] == d]
            if (d - last2).days >= DEDUP_DAYS:
                e2.append(_event(cik, d, today))
                last2 = d
            if win["RPTOWNERCIK"].nunique() >= MIN_INSIDERS and (d - last1).days >= DEDUP_DAYS:
                e1.append(_event(cik, d, win))
                last1 = d
    return pd.DataFrame(e1), pd.DataFrame(e2)


def _event(cik, d, rows):
    v = rows["value"].sum()
    vwap = v / rows["TRANS_SHARES"].sum() if rows["TRANS_SHARES"].sum() > 0 else rows["TRANS_PRICEPERSHARE"].mean()
    return {"cik": cik, "date": d, "ticker": rows["ISSUERTRADINGSYMBOL"].iloc[-1],
            "trans_date": rows["TRANS_DATE"].max(), "vwap": float(vwap), "insiders": rows["RPTOWNERCIK"].nunique(),
            "value": float(v)}


# --------------------------------------------------------------------------
# Prezzi Yahoo con split (per ricostruire il prezzo non rettificato)
# --------------------------------------------------------------------------
_last = [0.0]


def chart(ticker):
    def fetch():
        wait = _last[0] + 0.35 - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        for attempt in range(4):
            r = requests.get(data.CHART_URL.format(t=ticker), headers=data.UA, timeout=30,
                             params={"period1": 1104537600, "period2": int(time.time()), "interval": "1d",
                                     "events": "splits", "includeAdjustedClose": "true"})
            if r.status_code != 429:
                break
            time.sleep(10 * (attempt + 1))
        if r.status_code == 404:
            return {"missing": True}
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
        sp = [[int(k), s["numerator"], s["denominator"]] for k, s in (res.get("events", {}).get("splits") or {}).items()]
        return {"t": res.get("timestamp") or [], "c": q["close"], "a": adj, "s": sp}
    return cached(f"yh:{ticker}", 30 * 86400, fetch)


def series(ticker):
    js = chart(ticker)
    if not js or js.get("missing") or not js.get("t"):
        return None
    idx = pd.to_datetime(js["t"], unit="s").normalize()
    df = pd.DataFrame({"close": js["c"], "adj": js["a"]}, index=idx).astype(float)
    df = df[~df.index.duplicated(keep="last")].dropna()
    df = df[df["close"] > 0]
    factor = pd.Series(1.0, index=df.index)
    for ts, num, den in js.get("s", []):
        d = pd.to_datetime(ts, unit="s").normalize()
        if den:
            factor[df.index < d] *= num / den        # prima dello split il prezzo vero era più alto
    df["raw_close"] = df["close"] * factor
    return df


# --------------------------------------------------------------------------
def nw_t(s, lags):
    s = pd.Series(s).dropna()
    n = len(s)
    if n < 10:
        return None
    x = s.values - s.values.mean()
    v = (x @ x) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (x[L:] @ x[:-L]) / n
    return round(float(s.mean() / math.sqrt(v / n)), 2) if v > 0 else None


def measure(ev: pd.DataFrame, bench: dict):
    rows, lost = [], {"no_yahoo": 0, "price_mismatch": 0, "no_future": 0}
    for _, e in ev.iterrows():
        try:
            px = series(e["ticker"]) if e["ticker"] else None
        except Exception:
            px = None
        if px is None or len(px) < 10:
            lost["no_yahoo"] += 1
            continue
        td = e["trans_date"] if pd.notna(e["trans_date"]) else e["date"]
        p0 = px.index.searchsorted(td, side="right") - 1
        if p0 < 0 or abs(px["raw_close"].iloc[p0] / e["vwap"] - 1) > MAX_PRICE_GAP:
            lost["price_mismatch"] += 1
            continue
        pos = px.index.searchsorted(e["date"], side="right")      # prima seduta dopo il deposito
        r = {"date": e["date"], "ticker": e["ticker"], "insiders": e["insiders"]}
        ok = False
        for hz, h in H.items():
            if pos + h < len(px):
                d0, d1 = px.index[pos], px.index[pos + h]
                ret = px["adj"].iloc[pos + h] / px["adj"].iloc[pos] - 1
                r[f"ret_{hz}"] = ret
                for bn, b in bench.items():
                    b0, b1 = b.asof(d0), b.asof(d1)
                    r[f"x_{bn}_{hz}"] = ret - (b1 / b0 - 1)
                ok = True
        if not ok:
            lost["no_future"] += 1
            continue
        rows.append(r)
    return pd.DataFrame(rows), lost


def stats(df, col, lags):
    d = df.dropna(subset=[col])
    if len(d) < 30:
        return {"events": len(d)}
    m = d.groupby(d["date"].dt.to_period("M"))[col].mean()
    return {"events": len(d), "months": len(m), "mean": round(float(d[col].mean()), 4),
            "median": round(float(d[col].median()), 4), "monthly_mean": round(float(m.mean()), 4),
            "t": nw_t(m, lags), "hit": round(float((d[col] > 0).mean()), 3)}


def report(df, hold_start):
    out = {}
    dev, hold = df[df["date"] < hold_start], df[df["date"] >= hold_start]
    post = dev[dev["date"].dt.year >= 2013]
    for name, part in (("dev", dev), ("post2013", post), ("holdout", hold)):
        out[name] = {f"{b}_{hz}": stats(part, f"x_{b}_{hz}", LAGS[hz]) for hz in H for b in ("IWM", "SPY")}
    return out


def main():
    db.init()
    ins = insider.load()
    e1, e2 = events(ins)
    print(f"acquisti validi {len(ins)}, eventi E1 {len(e1)}, E2 {len(e2)}", file=sys.stderr)
    tick2 = e2["ticker"].dropna().unique()
    if len(tick2) > MAX_E2_TICKERS:
        keep = set(np.random.default_rng(0).choice(tick2, MAX_E2_TICKERS, replace=False))
        e2 = e2[e2["ticker"].isin(keep)]
    bench = {b: series(b)["adj"] for b in ("IWM", "SPY")}
    cal = series("IWM").index
    hold_start = cal[len(cal) - config.LAB["holdout"]]
    res = {"purchases": len(ins), "holdout_from": str(hold_start.date())}
    for name, ev in (("E1_grappolo", e1), ("E2_singolo", e2)):
        df, lost = measure(ev, bench)
        r = report(df, hold_start)
        r["events_total"] = len(ev)
        r["events_measured"] = len(df)
        r["lost"] = lost
        x = r["dev"]["IWM_45gg"]
        n_lost = sum(lost.values())
        if x.get("mean") is not None and n_lost:
            r["breakeven_lost_mean_45gg"] = round(-x["mean"] * x["events"] / n_lost, 4)
        res[name] = r
        print(f"{name}: misurati {len(df)} su {len(ev)}", file=sys.stderr)
    d, p = res["E1_grappolo"]["dev"], res["E1_grappolo"]["post2013"]
    res["criteria"] = {
        "I1": bool((d["IWM_45gg"].get("monthly_mean") or 0) > 0 and (d["IWM_45gg"].get("t") or 0) >= 3),
        "I2": bool((d["IWM_90gg"].get("monthly_mean") or 0) > 0 and (d["IWM_90gg"].get("t") or 0) >= 2),
        "I3": bool((p["IWM_45gg"].get("monthly_mean") or 0) > 0 and (p["IWM_90gg"].get("monthly_mean") or 0) > 0),
        "I4": bool((d["IWM_45gg"].get("hit") or 0) > 0.5),
    }
    res["success"] = all(res["criteria"].values())
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    return res


if __name__ == "__main__":
    main()
