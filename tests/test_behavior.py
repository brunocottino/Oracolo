"""Misure comportamentali e fonti nuove (sources/), senza rete:
  - parsing di risposte salvate (Wikimedia, documento SEC)
  - somiglianza dei testi e scelta del bilancio comparabile
  - prospect theory e capital gains overhang su casi noti
  - nessun look-ahead con volume, visite Wikipedia e depositi SEC
Esecuzione:  python tests/test_behavior.py"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from lab import features as F  # noqa: E402
from sources import edgar, wiki  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def test_wiki_parse():
    with open(os.path.join(FIX, "wiki_pageviews.json")) as f:
        d = wiki.parse(json.load(f))
    assert d == {"2015-07-01": 359, "2015-07-02": 268, "2015-07-03": 301}


def test_edgar_words_skip_hidden():
    with open(os.path.join(FIX, "edgar_10k.htm")) as f:
        w = edgar.words(f.read())
    assert w["beverages"] == 1 and w["snacks"] == 1 and w["revenue"] == 1
    assert "hidden" not in w and "ignored" not in w and "color" not in w


def test_edgar_similarity_pairs():
    a = Counter({"risk": 5, "demand": 3})
    assert abs(edgar.cosine(a, a) - 1) < 1e-12
    assert edgar.cosine(a, Counter({"zebra": 2})) == 0
    fl = [("2020-02-01", "10-K", "a", "d"), ("2020-05-01", "10-Q", "b", "d"), ("2020-08-01", "10-Q", "c", "d"),
          ("2020-11-01", "10-Q", "e", "d"), ("2021-02-01", "10-K", "f", "d"), ("2021-05-01", "10-Q", "g", "d")]
    texts = {"a": "alpha beta", "b": "one two", "c": "three four", "e": "five six",
             "f": "alpha beta", "g": "one two"}
    out = edgar.similarities(fl, lambda f: Counter(texts[f[2]].split()))
    # 10-K 2021 contro 10-K 2020; 10-Q maggio 2021 contro 10-Q maggio 2020 (terzo precedente)
    assert [(o["date"], o["sim"]) for o in out] == [("2021-02-01", 1.0), ("2021-05-01", 1.0)]


def test_prospect_value_cases():
    idx = pd.bdate_range("2000-01-03", periods=21 * 70)
    up = pd.Series(np.exp(np.arange(len(idx)) * 0.0005), index=idx)        # solo guadagni regolari
    tk_up = F.prospect_value(up).dropna()
    assert len(tk_up) and (tk_up > 0).all()
    rng = np.random.default_rng(1)
    noisy = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.02, len(idx)))), index=idx)
    tk = F.prospect_value(noisy).dropna()
    # avversione alle perdite: con rendimenti simmetrici il valore è negativo
    assert tk.mean() < 0


def test_cgo_reference_price():
    idx = pd.bdate_range("2000-01-03", periods=1500)
    px = pd.Series(100.0, index=idx)
    px.iloc[1000:] = 120.0
    cgo = F.capital_gains_overhang(px, None, lag=0)
    assert abs(cgo.iloc[999]) < 1e-9          # prezzo fermo: nessun guadagno latente
    assert 0 < cgo.iloc[1010] < 0.2           # dopo il rialzo il prezzo di carico insegue lentamente
    assert cgo.iloc[1499] < cgo.iloc[1010]


def _synthetic():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2012-01-02", periods=3200)
    px = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.015, len(idx)))), index=idx) * 50
    bx = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))), index=idx) * 1000
    vol = pd.Series(rng.lognormal(13, 0.4, len(idx)), index=idx)
    days = pd.date_range("2015-07-01", idx[-1])
    wk = pd.Series(rng.poisson(300, len(days)).astype(float), index=days)
    lz = [{"date": str(d.date()), "sim": float(rng.uniform(0.8, 1))} for d in idx[300::63]]
    return px, bx, vol, wk, lz


def test_behavior_no_lookahead():
    px, bx, vol, wk, lz = _synthetic()
    cols = ["cgo", "pt_value", "attn", "press", "lazy"]
    full = F.stock_raw(px, bx, None, {"volume": vol, "wiki": wk, "lazy": lz})
    checked = 0
    for cut in (1500, 2200, 3100):
        d = px.index[cut]
        ex = {"volume": vol[vol.index <= d], "wiki": wk[wk.index <= d],
              "lazy": [x for x in lz if pd.Timestamp(x["date"]) <= d]}
        tr = F.stock_raw(px.iloc[:cut + 1], bx[bx.index <= d], None, ex)
        a, b = full.loc[d, cols].values.astype(float), tr.loc[d, cols].values.astype(float)
        assert np.all((np.isnan(a) & np.isnan(b)) | np.isclose(a, b)), (d, a, b)
        assert np.isfinite(a).all(), (d, a)
        checked += 1
    # un deposito SEC conta solo da due sedute dopo
    d0 = pd.Timestamp(lz[10]["date"])
    p0 = px.index.get_loc(d0)
    assert full["lazy"].iloc[p0 + 2] == lz[10]["sim"] and full["lazy"].iloc[p0 + 1] != lz[10]["sim"]
    print(f"    {checked} origini controllate, {len(cols)} misure comportamentali")


def test_forchetta_and_risk_size():
    import bands
    idx = pd.bdate_range("2015-01-01", periods=1200)
    rng = np.random.default_rng(3)
    px = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))), index=idx)
    f = bands.forchetta(pd.DataFrame({"adj": px, "close": px}), "azioni")
    b45, b90 = f["bands"]["45 giorni"], f["bands"]["90 giorni"]
    assert b45["low"] < f["price"] < b45["high"] and b90["low"] < b45["low"] and b90["high"] > b45["high"]
    assert abs(bands.risk_size(100, 90) - 0.05) < 1e-12          # 0,5% / 10% di distanza dallo stop
    assert bands.risk_size(100, 99.99) == 0.10                     # limite massimo 10%
    assert bands.risk_size(100, 101) is None


if __name__ == "__main__":
    sys.exit(1 if common.run_module(globals()) else 0)
