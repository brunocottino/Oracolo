"""Indice ORACOLO v1: COMPRA / VENDI / STAI FERMO, test pre-registrato (vedi PREREG_ORACOLO.md).

Lancio:  python -m lab.oracolo_index            (test storico + registro delle decisioni di oggi)
Nessun parametro stimato sui dati: regole, orizzonti e criteri sono quelli della pre-registrazione.
"""
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config
import data
import db

from .panel import _origins, stock_universe

STEP = 21
HORIZONS = (21, 63)
COST = 10 / 10000
MIN_NAMES = 10
FORWARD_LOG = os.environ.get("ORACOLO_FORWARD_LOG", os.path.join(config.BASE_DIR, "oracolo_forward.csv"))


def prices():
    db.init()
    cols = {}
    for t in stock_universe():
        try:
            cols[t] = data.get_history(t)[0]["adj"].astype(float)
        except Exception as e:
            print("salto", t, e, file=sys.stderr)
    P = pd.DataFrame(cols).sort_index()
    return P.ffill(limit=5)            # festività di mercati diversi; nessun prezzo prima della quotazione


def states(P):
    mom = P.shift(21) / P.shift(252) - 1
    sma = P.rolling(200, min_periods=200).mean()
    above = P > sma
    trend = pd.DataFrame(0, index=P.index, columns=P.columns)
    trend[(mom > 0) & above] = 1
    trend[(mom < 0) & ~above & sma.notna()] = -1
    ok = mom.notna() & sma.notna() & P.notna()
    rank = mom.where(ok).rank(axis=1, pct=True)
    st = pd.DataFrame("STAI FERMO", index=P.index, columns=P.columns)
    st[(trend == 1) & (rank > 2 / 3)] = "COMPRA"
    st[trend == -1] = "VENDI"
    return st.where(ok), mom, trend


def nw_t(s, lags):
    s = pd.Series(s).dropna()
    n = len(s)
    if n < 10:
        return None
    x = s.values - s.values.mean()
    v = (x @ x) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (x[L:] @ x[:-L]) / n
    return round(float(s.mean() / math.sqrt(v / n)), 2)


def excess_by_state(st, fwd, dates, lags):
    out = {}
    for name in ("COMPRA", "STAI FERMO", "VENDI"):
        ex, hit = [], []
        for d in dates:
            f = fwd.loc[d]
            s = st.loc[d]
            elig = f.notna() & s.notna()
            if elig.sum() < MIN_NAMES:
                continue
            m = f[elig].mean()
            sel = elig & (s == name)
            if sel.sum() == 0:
                continue
            ex.append(f[sel].mean() - m)
            hit.append((f[sel] > m).mean())
        ex = pd.Series(ex)
        out[name] = {"dates": len(ex), "excess_mean": round(float(ex.mean()), 4) if len(ex) else None,
                     "t": nw_t(ex, lags), "hit_rate": round(float(np.mean(hit)), 3) if hit else None}
    return out


def portfolios(st, fwd, dates):
    """Rendimenti per periodo di 21 sedute, con costo sul turnover dei pesi."""
    res = {k: [] for k in ("A_compra", "B_no_vendi", "benchmark")}
    prev = {k: pd.Series(dtype=float) for k in res}
    idx = []
    for d in dates:
        f = fwd.loc[d]
        s = st.loc[d]
        elig = f.notna() & s.notna()
        if elig.sum() < MIN_NAMES:
            continue
        sets = {"A_compra": elig & (s == "COMPRA"), "B_no_vendi": elig & (s != "VENDI"), "benchmark": elig}
        for k, sel in sets.items():
            w = pd.Series(1.0 / sel.sum(), index=sel[sel].index) if sel.sum() else pd.Series(dtype=float)
            turn = w.subtract(prev[k], fill_value=0).abs().sum()
            r = float((f[w.index] * w).sum()) if len(w) else 0.0
            res[k].append(r - turn * COST)
            prev[k] = w
        idx.append(d)
    return pd.DataFrame(res, index=idx)


def perf(r):
    r = r.dropna()
    if len(r) < 12:
        return {}
    eq = (1 + r).cumprod()
    yrs = len(r) * STEP / 252
    return {"periods": len(r), "cagr": round(float(eq.iloc[-1] ** (1 / yrs) - 1), 4),
            "sharpe": round(float(r.mean() / r.std() * math.sqrt(252 / STEP)), 3),
            "max_dd": round(float((eq / eq.cummax() - 1).min()), 4)}


def log_today(st, P):
    """Registra le decisioni di oggi (prova sui dati futuri). Una riga per titolo, con impronta."""
    d = st.dropna(how="all").index[-1]
    rows = [{"date": str(d.date()), "ticker": t, "state": st.loc[d, t], "price": round(float(P.loc[d, t]), 4)}
            for t in st.columns if isinstance(st.loc[d, t], str)]
    exists = os.path.exists(FORWARD_LOG)
    if exists:
        with open(FORWARD_LOG) as f:
            if any(line.startswith(str(d.date()) + ",") for line in f):
                return d, rows, False
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:16]
    with open(FORWARD_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["date", "ticker", "state", "price", "logged_utc", "batch_sha256"])
        for r in rows:
            w.writerow([r["date"], r["ticker"], r["state"], r["price"], stamp, digest])
    return d, rows, True


def main():
    P = prices()
    st, mom, trend = states(P)
    cal = P.index
    dates_all = _origins(cal, STEP)
    pos = cal.get_indexer(dates_all)
    hold_start = len(cal) - config.LAB["holdout"]
    dev = [d for d, p in zip(dates_all, pos) if p + 21 < hold_start]
    hold = [d for d, p in zip(dates_all, pos) if p >= hold_start]
    post = [d for d in dev if d.year >= 2013]
    fwd = {h: P.shift(-h) / P - 1 for h in HORIZONS}

    R = {"tickers": int(P.shape[1]), "dev_dates": len(dev), "dev_from": str(dev[0].date()), "dev_to": str(dev[-1].date()),
         "holdout_dates": len(hold)}
    R["excess_21_dev"] = excess_by_state(st, fwd[21], dev, 0)
    R["excess_63_dev"] = excess_by_state(st, fwd[63], dev, 2)
    R["excess_21_post2013"] = excess_by_state(st, fwd[21], post, 0)
    pf = portfolios(st, fwd[21], dev)
    R["portfolios_dev"] = {k: perf(pf[k]) for k in pf}
    pf13 = portfolios(st, fwd[21], post)
    R["portfolios_post2013"] = {k: perf(pf13[k]) for k in pf13}
    e, p13 = R["excess_21_dev"], R["excess_21_post2013"]
    b, bm = R["portfolios_dev"]["B_no_vendi"], R["portfolios_dev"]["benchmark"]
    R["criteria"] = {
        "P1": bool(e["COMPRA"]["excess_mean"] > 0 and (e["COMPRA"]["t"] or 0) >= 2),
        "P2": bool(e["VENDI"]["excess_mean"] < 0 and (e["VENDI"]["t"] or 0) <= -2),
        "P3": bool(b["sharpe"] >= bm["sharpe"] and b["max_dd"] > bm["max_dd"]),
        "P4": bool(p13["COMPRA"]["excess_mean"] > 0 and p13["VENDI"]["excess_mean"] < 0),
    }
    R["success"] = all(R["criteria"].values())
    hold21 = [d for d in hold if cal.get_loc(d) + 21 < len(cal)]
    R["holdout_excess_21"] = excess_by_state(st, fwd[21], hold21, 0)
    pfh = portfolios(st, fwd[21], hold21)
    R["holdout_portfolios"] = {k: perf(pfh[k]) if len(pfh) >= 12 else {"periods": len(pfh),
                               "total": round(float((1 + pfh[k]).prod() - 1), 4)} for k in pfh}
    d, rows, new = log_today(st, P)
    counts = pd.Series([r["state"] for r in rows]).value_counts().to_dict()
    R["today"] = {"date": str(d.date()), "counts": counts, "logged": new,
                  "COMPRA": sorted(r["ticker"] for r in rows if r["state"] == "COMPRA")}
    print(json.dumps(R, indent=2, ensure_ascii=False))
    return R


if __name__ == "__main__":
    main()
