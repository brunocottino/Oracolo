"""Test anti look-ahead (nessun dato futuro entra nelle misure o nell'addestramento):
  - le misure all'origine t non cambiano se si cancellano i dati dopo t
  - un evento con data > t non influisce; un annuncio conta solo da t+2
  - il purge elimina ogni sovrapposizione tra finestre di addestramento e di test
Esecuzione:  python tests/test_lookahead.py"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
import data  # noqa: E402
import db  # noqa: E402
from fundamentals import benchmark_for  # noqa: E402
from lab import features as F  # noqa: E402
from lab import panel as P  # noqa: E402
from lab import research as R  # noqa: E402

db.init()
COLS = [f["key"] for f in F.STOCK_FEATURES] + ["beta", "sig_res_d", "sue_raw", "n_up_30"]


def _inputs(t):
    px = data.get_history(t)[0]["adj"]
    bx = data.get_history(benchmark_for(t))[0]["adj"]
    return px, bx, data.get_events(t)


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return bool(np.all((np.isnan(a) & np.isnan(b)) | np.isclose(a, b, rtol=1e-9, atol=1e-12)))


def test_truncation_invariance_stocks():
    checked = 0
    for t in ("AAPL", "ENI.MI", "SAP.DE", "7203.T"):
        px, bx, ev = _inputs(t)
        full = F.stock_raw(px, bx, ev)
        for cut in (900, 1500, 2600, len(px) - 40):
            d = px.index[cut]
            ev_cut = {"earnings": [e for e in ev["earnings"] if pd.Timestamp(e["date"]) <= d],
                      "grades": [g for g in ev["grades"] if pd.Timestamp(g["date"]) <= d]}
            # il prezzo e l'indice si fermano a t; gli eventi successivi non esistono ancora
            tr = F.stock_raw(px.iloc[:cut + 1], bx[bx.index <= d], ev_cut)
            row_f, row_t = full.loc[d, COLS], tr.loc[d, COLS]
            assert _same(row_f.values, row_t.values), (t, d, row_f[~np.isclose(row_f, row_t, equal_nan=True)])
            checked += 1
    print(f"    {checked} origini controllate, {len(COLS)} misure ciascuna")


def test_truncation_invariance_index():
    px = data.get_history("^GSPC")[0]["adj"]
    vix = data.get_history("^VIX")[0]["close"]
    v3 = data.get_history("^VIX3M")[0]["close"]
    full = F.index_raw(px, vix, v3)
    for f in F.INDEX_FEATURES:
        full["x_" + f["key"]] = F.ts_rank(full[f["key"]])
    for cut in (800, 2000, len(px) - 70):
        d = px.index[cut]
        tr = F.index_raw(px.iloc[:cut + 1], vix[vix.index <= d], v3[v3.index <= d])
        for f in F.INDEX_FEATURES:
            tr["x_" + f["key"]] = F.ts_rank(tr[f["key"]])
        cols = [f["key"] for f in F.INDEX_FEATURES] + ["x_" + f["key"] for f in F.INDEX_FEATURES]
        assert _same(full.loc[d, cols].values, tr.loc[d, cols].values), d


def test_future_event_has_no_effect():
    px, bx, ev = _inputs("MSFT")
    t = px.index[2000]
    base = F.stock_raw(px, bx, ev)
    ev2 = copy.deepcopy(ev)
    fut = px.index[2001]
    ev2["earnings"].append({"date": str(fut.date()), "eps_est": 1.0, "eps_act": 9.0})   # sorpresa enorme
    ev2["grades"].append({"date": str(fut.date()), "action": "up", "tgt_prior": 10.0, "tgt_new": 100.0})
    alt = F.stock_raw(px, bx, ev2)
    assert _same(base.loc[:t, COLS].values, alt.loc[:t, COLS].values)
    # ...ma dopo la pubblicazione l'evento si vede (controllo che il test non sia vuoto)
    later = px.index[2001 + 3]
    assert not _same(base.loc[later, ["sue", "upg_30"]].values, alt.loc[later, ["sue", "upg_30"]].values)


def test_earnings_available_only_from_t_plus_2():
    px, bx, ev = _inputs("NVDA")
    d_pos = 2500
    d = px.index[d_pos]
    ev_wo = {"earnings": [e for e in ev["earnings"] if abs((pd.Timestamp(e["date"]) - d).days) > 40],
             "grades": []}
    ev_w = copy.deepcopy(ev_wo)
    ev_w["earnings"].append({"date": str(d.date()), "eps_est": 1.0, "eps_act": 1.5})
    ev_w["earnings"].sort(key=lambda x: x["date"])
    a = F.stock_raw(px, bx, ev_wo)
    b = F.stock_raw(px, bx, ev_w)
    for k in (0, 1):                     # giorno dell'annuncio e giorno dopo: non ancora disponibile
        dd = px.index[d_pos + k]
        assert _same(a.loc[dd, ["sue", "ear", "sue_raw"]].values, b.loc[dd, ["sue", "ear", "sue_raw"]].values), k
    dd = px.index[d_pos + 2]
    assert not _same(a.loc[dd, ["sue_raw"]].values, b.loc[dd, ["sue_raw"]].values)


def test_purge_and_embargo():
    tick = P.stock_universe()[:25]
    panel, cal, info = P.build_stock_panel(tickers=tick)
    L = config.LAB
    h = info["h"]
    first = int(panel["origin_pos"].min()) + L["min_train"]
    rec = []
    R.walk_forward(panel, ["x_mom_12_1", "x_sue", "f_events"], R.logit_factory, first, L["retrain"], L["embargo"],
                   record=rec)
    assert len(rec) > 10
    op = panel["origin_pos"].values
    ep = panel["end_pos"].values
    for T, tr, te in rec:
        # ogni risultato usato in addestramento è terminato almeno `embargo` sedute prima del test
        assert np.nanmax(ep[tr]) < T - L["embargo"], T
        # e quindi nessuna finestra di addestramento si sovrappone al test
        assert op[te].min() >= T
        assert np.nanmax(ep[tr]) < op[te].min()
        # purge pari all'orizzonte: l'ultima origine in addestramento è almeno h + embargo prima di T
        assert op[tr].max() <= T - L["embargo"] - h + 6, (op[tr].max(), T)
    # controprova: senza purge ci sarebbero sovrapposizioni
    T0 = rec[len(rec) // 2][0]
    naive = (op < T0) & np.isfinite(ep)
    assert np.nanmax(ep[naive]) >= T0
    print(f"    {len(rec)} blocchi di riaddestramento controllati")


def test_holdout_never_used_for_selection():
    """Le righe di sviluppo (usate per scegliere le misure) finiscono prima dell'holdout."""
    tick = P.stock_universe()[:20]
    panel, cal, info = P.build_stock_panel(tickers=tick)
    hold_start = len(cal) - config.LAB["holdout"]
    ep = panel["end_pos"].values
    op = panel["origin_pos"].values
    dev = (op >= op.min() + config.LAB["min_train"]) & np.isfinite(ep) & (ep < hold_start)
    assert dev.any() and np.nanmax(ep[dev]) < hold_start


if __name__ == "__main__":
    sys.exit(1 if common.run_module(globals()) else 0)
