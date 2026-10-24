"""Utilità dei segnali a 45 e 90 giorni (31 e 63 sedute): test pre-registrato, vedi PREREG_ORIZZONTI.md.

Lancio:  python -m lab.horizon_test
"""
import json
import math
import sys

import numpy as np
import pandas as pd

import config
import data
import db

from .oracolo_index import UNIVERSES, states
from .panel import _origins, stock_universe

HORIZONS = {"45gg": 31, "90gg": 63}
MIN_NAMES = 3


# ---- IPB v2 di Bruno (stessa logica del suo codice: z-score 126, isteresi 20/5) ----
def _z(s, w=126):
    mp = max(40, w // 3)
    m, sd = s.rolling(w, min_periods=mp).mean(), s.rolling(w, min_periods=mp).std(ddof=0)
    return ((s - m) / sd.replace(0, np.nan)).clip(-3, 3) / 3


def ipb2_state(close, volume):
    r = close.pct_change()
    d = {"m5": close.pct_change(5), "m20": close.pct_change(20), "m60": close.pct_change(60)}
    d["tg"] = close.ewm(span=10, adjust=False).mean() / close.ewm(span=50, adjust=False).mean() - 1
    d["vr"] = (r.rolling(20).std() / r.rolling(60).std().replace(0, np.nan))
    rel = volume / volume.rolling(20).mean().replace(0, np.nan)
    d["sv"] = np.sign(r) * np.log1p(rel.clip(lower=0))
    z = {k: _z(v) for k, v in d.items()}
    raw = 0.15 * z["m5"] + 0.30 * z["m20"] + 0.25 * z["m60"] + 0.20 * z["tg"] + 0.10 * z["sv"] - 0.20 * z["vr"]
    ipb = (100 * np.tanh(2 * raw)).values
    out, cur = np.full(len(ipb), np.nan), 0.0
    for i, v in enumerate(ipb):
        if np.isnan(v):
            continue
        if cur == 0 and v > 20:
            cur = 1.0
        elif cur == 1 and v < 5:
            cur = 0.0
        out[i] = cur
    return pd.Series(out, index=close.index)


def load(tickers):
    db.init()
    px, st_ipb = {}, {}
    for t in tickers:
        try:
            df = data.get_history(t)[0]
        except Exception as e:
            print("salto", t, e, file=sys.stderr)
            continue
        px[t] = df["adj"].astype(float)
        vol = df["volume"].astype(float)
        st_ipb[t] = ipb2_state(px[t], vol) if vol.gt(0).mean() > 0.8 else pd.Series(np.nan, index=px[t].index)
    P = pd.DataFrame(px).sort_index().ffill(limit=5)
    I = pd.DataFrame(st_ipb).reindex(P.index).ffill(limit=5)
    return P, I


def signals(P, I):
    orc, _, _ = states(P)
    sma = P.rolling(100, min_periods=100).mean()
    s_sma = pd.DataFrame(np.where(P > sma, "COMPRA", "VENDI"), index=P.index, columns=P.columns).where(sma.notna())
    s_ipb = pd.DataFrame(np.where(I == 1, "COMPRA", "VENDI"), index=P.index, columns=P.columns).where(I.notna())
    return {"oracolo": orc, "ipb2": s_ipb, "sma100": s_sma}


def nw_t(s, lags=1):
    s = pd.Series(s).dropna()
    n = len(s)
    if n < 10:
        return None
    x = s.values - s.values.mean()
    v = (x @ x) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (x[L:] @ x[:-L]) / n
    return round(float(s.mean() / math.sqrt(v / n)), 2) if v > 0 else None


def evaluate(sig, fwd, dates, norm):
    out = {}
    for name in ("COMPRA", "STAI FERMO", "VENDI"):
        per_date, raw, up = [], [], []
        for d in dates:
            s, f = sig.loc[d], fwd.loc[d]
            sel = (s == name) & f.notna() & norm.notna()
            if sel.sum() == 0 or ((s.notna() & f.notna()).sum() < MIN_NAMES):
                continue
            per_date.append(float((f[sel] - norm[sel]).mean()))
            raw += list(f[sel].values)
        if not per_date:
            continue
        raw = np.array(raw)
        out[name] = {"dates": len(per_date), "edge": round(float(np.mean(per_date)), 4), "t": nw_t(per_date),
                     "mean_return": round(float(raw.mean()), 4), "pct_up": round(float((raw > 0).mean()), 3),
                     "obs": int(len(raw))}
    return out


def run_universe(name, tickers):
    P, I = load(tickers)
    sigs = signals(P, I)
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
        norm = fwd.loc[dev].mean()                     # rendimento "normale" del ticker nello sviluppo
        for sn, sig in sigs.items():
            e_dev, e_post, e_hold = (evaluate(sig, fwd, ds, norm) for ds in (dev, post, hold))
            c, v = e_dev.get("COMPRA", {}), e_dev.get("VENDI", {})
            u1c = c.get("edge") is not None and c["edge"] > 0 and (c.get("t") or 0) >= 3
            u1v = v.get("edge") is not None and v["edge"] < 0 and (v.get("t") or 0) <= -3
            pc, pv = e_post.get("COMPRA", {}), e_post.get("VENDI", {})
            u2 = ((not u1c) or (pc.get("edge") or 0) > 0) and ((not u1v) or (pv.get("edge") or 0) < 0) and (u1c or u1v)
            u3 = (c.get("pct_up") or 0) > (v.get("pct_up") or 1)
            res[f"{sn}|{hz}"] = {"dev": e_dev, "post2013": e_post, "holdout": e_hold,
                                 "U1": bool(u1c or u1v), "U2": bool(u2), "U3": bool(u3),
                                 "utile": bool((u1c or u1v) and u2 and u3),
                                 "dev_dates": len(dev), "dev_from": str(dev[0].date()) if dev else None}
    return res


def main():
    unis = {"azioni": stock_universe(), **UNIVERSES}
    if len(sys.argv) > 1:
        unis = {k: unis[k] for k in sys.argv[1:]}
    allres = {u: run_universe(u, t) for u, t in unis.items()}
    print(json.dumps(allres, ensure_ascii=False))
    return allres


if __name__ == "__main__":
    main()
