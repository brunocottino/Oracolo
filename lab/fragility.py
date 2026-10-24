"""Test pre-registrato dell'IFC, Indice di Fragilità Comportamentale (vedi PREREG_IFC.md).

Lancio:  python -m lab.fragility
Niente parametri da tarare: componenti, target, campione e criteri sono quelli della pre-registrazione.
"""
import json
import math
import sys

import numpy as np
import pandas as pd

import config
import data
import db
from fundamentals import benchmark_for
from sources import behavior

from . import features as F
from .panel import _origins, stock_universe

H = 31
STEP = 31
COMPONENTS = ["dturn", "run", "cgo", "attn", "calm"]
CONTROLS = ["ncskew_past", "sig_past", "beta"]
MIN_NAMES = 10


def ncskew(w):
    """Asimmetria negativa (Chen-Hong-Stein 2001) dei residui demeaned di una finestra."""
    w = np.asarray(w, float)
    w = w[np.isfinite(w)]
    n = len(w)
    if n < 20:
        return np.nan
    w = w - w.mean()
    s2 = (w ** 2).sum()
    if s2 <= 0:
        return np.nan
    return float(-(n * (n - 1) ** 1.5 * (w ** 3).sum()) / ((n - 1) * (n - 2) * s2 ** 1.5))


def ticker_rows(t, origins):
    df, _ = data.get_history(t)
    px, vol = df["adj"].astype(float), df["volume"].astype(float).replace(0, np.nan)
    bench = F.align(data.get_history(benchmark_for(t))[0]["adj"].astype(float), px.index)
    r, rb = np.log(px).diff(), np.log(bench).diff().fillna(0.0)
    beta = F.rolling_beta(r, rb)
    e = r - beta.shift(1) * rb
    f = pd.DataFrame(index=px.index)
    f["dturn"] = np.log(vol.rolling(21, min_periods=15).mean()) - np.log(vol.rolling(252, min_periods=200).mean())
    f["run"] = e.rolling(126, min_periods=120).sum()
    f["cgo"] = F.capital_gains_overhang(px, df["volume"])
    wiki = behavior.extra_for(t, df).get("wiki")
    f["attn"] = F.attention_shock(wiki, px.index) if wiki is not None and len(wiki) > 200 else np.nan
    f["calm"] = -(np.log(e.rolling(21, min_periods=20).std()) - np.log(e.rolling(252, min_periods=200).std()))
    f["sig_past"] = e.rolling(252, min_periods=200).std()
    f["beta"] = beta
    ev = e.values
    rows = []
    for d in origins:
        p = px.index.searchsorted(d, side="right") - 1      # ultima seduta del titolo <= origine
        if p < 300 or (d - px.index[p]).days > 6:
            continue
        row = f.iloc[p].to_dict()
        row["ncskew_past"] = ncskew(ev[p - 125:p + 1])
        fut = ev[p + 1:p + 1 + H]
        if len(fut) == H and np.isfinite(fut).sum() >= 25:
            row["y_ncskew"] = ncskew(fut)
            s = row["sig_past"]
            row["y_crash"] = float(np.nanmin(fut) < -3.09 * s) if np.isfinite(s) else np.nan
            # diagnostica (non nei criteri): code sinistra e destra separate, in unità di σ passata
            row["y_min"] = float(np.nanmin(fut) / s) if np.isfinite(s) and s > 0 else np.nan
            row["y_max"] = float(np.nanmax(fut) / s) if np.isfinite(s) and s > 0 else np.nan
            row["y_jump_up"] = float(np.nanmax(fut) > 3.09 * s) if np.isfinite(s) else np.nan
        else:
            row["y_ncskew"] = row["y_crash"] = row["y_min"] = row["y_max"] = row["y_jump_up"] = np.nan
        row.update(ticker=t, date=d)
        rows.append(row)
    return rows


def rank(s):
    n = s.notna().sum()
    return (s.rank() - 0.5) / n - 0.5


def ic_series(panel, x, y, controls=None):
    out = {}
    for d, g in panel.groupby("date"):
        g = g[[x, y] + (controls or [])].dropna()
        if len(g) < MIN_NAMES:
            continue
        a, b = rank(g[x]), rank(g[y])
        if controls:
            Z = np.column_stack([np.ones(len(g))] + [rank(g[c]).values for c in controls])
            a = a - Z @ np.linalg.lstsq(Z, a.values, rcond=None)[0]
            b = b - Z @ np.linalg.lstsq(Z, b.values, rcond=None)[0]
        if np.std(a) > 0 and np.std(b) > 0:
            out[d] = float(np.corrcoef(a, b)[0, 1])
    return pd.Series(out).sort_index()


def summary(s, lags=2):
    """Media, t di Newey-West (prudenza sull'autocorrelazione residua), anni positivi."""
    n = len(s)
    if n < 10:
        return {"n_dates": n, "ic": None, "t": None}
    x = s.values - s.values.mean()
    v = (x @ x) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (x[L:] @ x[:-L]) / n
    yr = s.groupby(s.index.year).mean()
    return {"n_dates": n, "ic": round(float(s.mean()), 4), "t": round(float(s.mean() / math.sqrt(v / n)), 2),
            "pos_years": round(float((yr > 0).mean()), 2), "years": int(len(yr))}


def build():
    db.init()
    tickers = stock_universe()
    cal = set()
    hist = {}
    for t in tickers:
        try:
            hist[t] = data.get_history(t)[0].index
            cal |= set(hist[t])
        except Exception as e:
            print("salto", t, e, file=sys.stderr)
    cal = pd.DatetimeIndex(sorted(cal))
    origins = _origins(cal, STEP)
    rows = []
    for i, t in enumerate(hist):
        rows += ticker_rows(t, origins)
        print(f"\r{i + 1}/{len(hist)} {t}      ", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    P = pd.DataFrame(rows)
    for c in COMPONENTS:
        P["r_" + c] = P.groupby("date")[c].transform(rank)
    rk = P[["r_" + c for c in COMPONENTS]]
    P["ifc"] = rk.mean(axis=1).where(rk.notna().sum(axis=1) >= 3)

    pos = cal.get_indexer(pd.DatetimeIndex(P["date"]))
    hold_start = len(cal) - config.LAB["holdout"]
    dev = P[(pos + H) < hold_start]
    hold = P[pos >= hold_start]
    return P, dev, hold, len(hist)


def main():
    P, dev, hold, n_t = build()
    hist = range(n_t)

    res = {"tickers": len(hist), "origins_dev": int(dev["date"].nunique()), "origins_holdout": int(hold["date"].nunique()),
           "dev_from": str(dev["date"].min().date()), "dev_to": str(dev["date"].max().date()),
           "coverage_attn": round(float(P["attn"].notna().mean()), 2)}
    res["S1_ifc_ncskew"] = summary(ic_series(dev, "ifc", "y_ncskew"))
    res["S2_partial"] = summary(ic_series(dev, "ifc", "y_ncskew", CONTROLS))
    res["benchmark_ncskew_past"] = summary(ic_series(dev, "ncskew_past", "y_ncskew"))
    res["benchmark_sig_past"] = summary(ic_series(dev, "sig_past", "y_ncskew"))
    res["components"] = {c: summary(ic_series(dev, c, "y_ncskew")) for c in COMPONENTS}
    res["secondary_crash"] = summary(ic_series(dev, "ifc", "y_crash"))
    terc = dev.dropna(subset=["ifc", "y_crash"]).copy()
    terc["q"] = terc.groupby("date")["ifc"].transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=False))
    res["crash_rate_by_tercile"] = {int(k): round(float(v), 4) for k, v in terc.groupby("q")["y_crash"].mean().items()}
    s1, s2 = res["S1_ifc_ncskew"], res["S2_partial"]
    res["criteria"] = {
        "S1": bool(s1["ic"] is not None and s1["ic"] > 0 and s1["t"] >= 3),
        "S2": bool(s2["ic"] is not None and s2["ic"] > 0 and s2["t"] >= 2),
        "S3": bool(s1.get("pos_years", 0) >= 0.6),
    }
    res["success"] = all(res["criteria"].values())
    res["holdout"] = summary(ic_series(hold, "ifc", "y_ncskew"), lags=0)
    res["holdout_partial"] = summary(ic_series(hold, "ifc", "y_ncskew", CONTROLS), lags=0)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    main()
