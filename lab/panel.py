"""Costruzione dei panel: tutte le azioni dell'universo in un'unica tabella
(data x titolo) e gli indici in una tabella separata.

Ogni riga è un'"origine": la situazione di un titolo a una certa data, con le
misure note quel giorno e il risultato realizzato nelle h sedute successive.
Le origini sono una ogni `step` sedute del calendario comune.
"""
import numpy as np
import pandas as pd

import config
import data
from fundamentals import benchmark_for
from sources import behavior
from universe import INDICES, MARKETS, market_of

from . import features as F


def stock_universe():
    return [t for m in MARKETS.values() for t in m]


def index_universe():
    return list(INDICES.keys())


def _origins(cal: pd.DatetimeIndex, step: int) -> pd.DatetimeIndex:
    # l'ultima origine è l'ultima seduta: così la "fotografia di oggi" è nel panel
    return cal[::-1][::step][::-1]


def _finish(frames, cal, step, h):
    origins = _origins(cal, step)
    rows = []
    for t, fr in frames.items():
        fr = fr[~fr.index.duplicated(keep="last")].sort_index()
        o = fr.reindex(origins, method="ffill", tolerance=pd.Timedelta("6D"))
        o["ticker"] = t
        o["date"] = origins
        rows.append(o)
    panel = pd.concat(rows, ignore_index=True)
    panel["origin_pos"] = cal.get_indexer(panel["date"])
    ed = pd.to_datetime(panel["end_date"])
    ep = cal.searchsorted(ed.fillna(pd.Timestamp("2262-01-01")).values)
    panel["end_pos"] = np.where(ed.notna(), ep, np.nan).astype(float)
    return panel


def build_stock_panel(tickers=None, h=None, step=None, progress=None, inputs=None):
    """Restituisce (panel, calendario, info). `inputs` (facoltativo, per i test) =
    {ticker: (px, bench, events)} oppure {ticker: (px, bench, events, extra)}."""
    h = h or config.HORIZON_STOCK
    step = step or config.LAB["origin_step"]
    tickers = tickers or stock_universe()
    frames, skipped, cover = {}, [], {"earnings": 0, "grades": 0, "wiki": 0, "lazy": 0}
    bench_cache = {}
    for i, t in enumerate(tickers):
        if progress:
            progress(i / max(len(tickers), 1), f"Preparo {t}")
        try:
            if inputs is not None:
                px, bench, ev, *rest = inputs[t]
                extra = rest[0] if rest else None
            else:
                df, _ = data.get_history(t)
                px = df["adj"]
                b = benchmark_for(t)
                if b not in bench_cache:
                    bench_cache[b] = data.get_history(b)[0]["adj"]
                bench = bench_cache[b]
                ev = data.get_events(t)
                extra = behavior.extra_for(t, df)
        except Exception as e:
            skipped.append(f"{t}: {e}")
            continue
        raw = F.stock_raw(px, bench, ev, extra)
        tg = F.stock_targets(px, bench, raw["beta"], h)
        fr = raw.join(tg)
        fr["market"] = market_of(t)
        fr["mi"] = t.upper().endswith(".MI")
        if ev and ev.get("earnings"):
            cover["earnings"] += 1
        if ev and ev.get("grades"):
            cover["grades"] += 1
        if raw["attn"].notna().any():
            cover["wiki"] += 1
        if raw["lazy"].notna().any():
            cover["lazy"] += 1
        frames[t] = fr
    if not frames:
        raise data.DataError("Nessun titolo disponibile per il panel.")
    cal = pd.DatetimeIndex(sorted(set().union(*[set(f.index) for f in frames.values()])))
    panel = _finish(frames, cal, step, h)
    panel = panel[panel["mom_12_1"].notna() & panel["beta"].notna() & panel["sig_res_d"].notna()]
    cnt = panel.groupby("date")["ticker"].transform("count")
    panel = panel[cnt >= min(config.LAB["min_names"], max(5, len(frames) // 2))].copy()
    keys = [f["key"] for f in F.STOCK_FEATURES]
    X = F.xs_rank(panel, keys)
    panel = pd.concat([panel, X], axis=1)
    panel["f_events"] = panel["sue"].isna().astype(float)
    panel["f_grades"] = panel["upg_30"].isna().astype(float)
    panel["f_wiki"] = panel["attn"].isna().astype(float)
    panel["f_lazy"] = panel["lazy"].isna().astype(float)
    panel["y"] = (panel["y_res"] > 0).astype(float)
    panel["y_abs"] = (panel["fwd"] > 0).astype(float)
    panel.loc[panel["y_res"].isna(), ["y", "y_abs"]] = np.nan
    panel["sig_res_h"] = panel["sig_res_d"] * np.sqrt(h)
    panel["sig_h"] = panel["sig_d"] * np.sqrt(h)
    panel["sig_b_h"] = panel["sig_b_d"] * np.sqrt(h)
    panel = panel.reset_index(drop=True)
    info = {"n_tickers": len(frames), "skipped": skipped, "coverage": cover,
            "h": h, "step": step, "calendar_len": len(cal),
            "first": str(cal[0].date()), "last": str(cal[-1].date())}
    return panel, cal, info


def build_index_panel(tickers=None, h=None, step=None, progress=None):
    h = h or config.HORIZON_INDEX
    step = step or config.LAB["origin_step"]
    tickers = tickers or index_universe()
    try:
        vix = data.get_history("^VIX")[0]["close"]
    except Exception:
        vix = None
    try:
        vix3m = data.get_history("^VIX3M")[0]["close"]
    except Exception:
        vix3m = None
    rf = data.short_rate_series()
    frames, skipped = {}, []
    for i, t in enumerate(tickers):
        if progress:
            progress(i / max(len(tickers), 1), f"Preparo {t}")
        try:
            df, _ = data.get_history(t)
        except Exception as e:
            skipped.append(f"{t}: {e}")
            continue
        px = df["adj"]
        us = t in data.US_INDICES
        raw = F.index_raw(px, vix if us else None, vix3m if us else None)
        for f in F.INDEX_FEATURES:
            raw["x_" + f["key"]] = F.ts_rank(raw[f["key"]]).fillna(0.0)
        raw["f_vix"] = raw["vrp"].isna().astype(float)
        tg = F.index_targets(px, rf, config.DEFAULT_RISK_FREE, h)
        fr = raw.join(tg)
        fr["market"] = "Indici"
        fr["mi"] = False
        frames[t] = fr
    if not frames:
        raise data.DataError("Nessun indice disponibile.")
    cal = pd.DatetimeIndex(sorted(set().union(*[set(f.index) for f in frames.values()])))
    panel = _finish(frames, cal, step, h)
    panel = panel[panel["tsmom_12"].notna() & panel["sig_d"].notna()].copy()
    panel["y"] = (panel["y_res"] > 0).astype(float)
    panel["y_abs"] = (panel["fwd"] > 0).astype(float)
    panel.loc[panel["y_res"].isna(), ["y", "y_abs"]] = np.nan
    panel["sig_h"] = panel["sig_d"] * np.sqrt(h)
    panel = panel.reset_index(drop=True)
    info = {"n_tickers": len(frames), "skipped": skipped, "h": h, "step": step,
            "calendar_len": len(cal), "first": str(cal[0].date()), "last": str(cal[-1].date()),
            "rf_source": "^IRX / 100" if rf is not None else f"costante {config.DEFAULT_RISK_FREE:.1%}",
            "vix": vix is not None}
    return panel, cal, info
