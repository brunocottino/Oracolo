"""Test statistici (migliaia di simulazioni rapide):
  - falsi positivi del t di Newey-West con segnale NULLO (>= 200 simulazioni)
  - potenza con un segnale noto
  - la calibrazione riduce l'errore di calibrazione (ECE)
  - Wilson, Benjamini-Hochberg, Deflated Sharpe, regola di promozione classe B
  - probabilità digitale con skew e reverse DCF
Esecuzione:  python tests/test_stats.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401

import numpy as np  # noqa: E402
from scipy.stats import norm  # noqa: E402

from lab import stats as S  # noqa: E402

H, STEP = 31, 5
RESULTS = {}


def _null_panel(rng, n_names=30, T=2600, ic=0.0):
    """Rendimenti con code grasse; misura = momentum 12-1 (molto persistente, come nella realtà).
    Con ic > 0 il rendimento futuro dipende dalla misura con IC atteso ~ ic."""
    r = rng.standard_t(5, (T, n_names)) * 0.015
    c = np.vstack([np.zeros(n_names), np.cumsum(r, 0)])
    org = np.arange(252, T - H, STEP)
    f = c[org - 21] - c[org - 252]
    y = c[org + H] - c[org]
    if ic:
        z = (f - f.mean(1, keepdims=True)) / f.std(1, keepdims=True)
        y = y + ic * z * y.std()
    dates = np.repeat(org, n_names)
    return dates, f.ravel(), y.ravel()


def test_newey_west_false_positives():
    """Con segnale nullo, la quota di t >= 2 deve restare vicino al 2,3% teorico (soglia 7%)."""
    rng = np.random.default_rng(12345)
    n_sims = 300
    ts = []
    for _ in range(n_sims):
        d, f, y = _null_panel(rng)
        ts.append(S.ic_summary(d, f, y, H, STEP)["t"])
    ts = np.array(ts)
    fpr = float(np.mean(ts >= 2))
    fpr2 = float(np.mean(np.abs(ts) >= 2))
    RESULTS["fpr_one_sided"] = fpr
    RESULTS["fpr_two_sided"] = fpr2
    print(f"    falsi positivi su {n_sims} simulazioni nulle: t>=2 {fpr:.1%}, |t|>=2 {fpr2:.1%}")
    assert fpr <= 0.07, fpr


def test_newey_west_naive_would_fail():
    """Controprova: ignorando la sovrapposizione (lag 0) i falsi positivi esplodono."""
    rng = np.random.default_rng(7)
    ts = []
    for _ in range(100):
        d, f, y = _null_panel(rng)
        _, ic = S.rank_ic_by_date(d, f, y)
        ts.append(S.nw_t(ic, 0)[1])
    naive = float(np.mean(np.array(ts) >= 2))
    print(f"    con t ingenuo (senza correzione): t>=2 nel {naive:.0%} dei casi nulli")
    assert naive > 0.07


def test_newey_west_power():
    """Con un segnale vero (IC ~0,06 su 30 titoli) il test lo trova quasi sempre."""
    rng = np.random.default_rng(99)
    hits, ics = 0, []
    for _ in range(60):
        d, f, y = _null_panel(rng, ic=0.06)
        r = S.ic_summary(d, f, y, H, STEP)
        ics.append(r["ic"])
        hits += r["t"] >= 2
    print(f"    potenza con IC atteso 0,06: {hits / 60:.0%}, IC medio stimato {np.mean(ics):.3f}")
    assert hits / 60 >= 0.6


def _miscal(rng, n):
    p_true = rng.uniform(0.25, 0.75, n)
    y = (rng.uniform(size=n) < p_true).astype(float)
    lg = np.log(p_true / (1 - p_true))
    raw = 1 / (1 + np.exp(-(2.2 * lg + 0.25)))          # troppo sicura e spostata
    return raw, y


def test_calibration_reduces_ece():
    """Su probabilità note ma distorte, la calibrazione riduce l'ECE (isotonica e Platt)."""
    rng = np.random.default_rng(3)
    before, after = [], []
    for k in range(40):
        n = 20000 if k % 2 == 0 else 1200                   # pari: isotonica, dispari: Platt
        raw, y = _miscal(rng, n)
        h = n // 2
        cal = S.Calibrator(iso_min=2000).fit(raw[:h], y[:h])
        assert cal.kind == ("isotonica" if n >= 4000 else "Platt")
        e0 = S.ece(raw[h:], y[h:])
        e1 = S.ece(cal.predict(raw[h:]), y[h:])
        before.append(e0)
        after.append(e1)
        assert e1 < e0, (k, e0, e1)
    RESULTS["ece_before"] = float(np.mean(before))
    RESULTS["ece_after"] = float(np.mean(after))
    print(f"    ECE medio prima {np.mean(before):.3f} -> dopo {np.mean(after):.3f} (40 prove)")


def test_brier_and_reliability():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.3, 0.7, 50000)
    y = (rng.uniform(size=p.size) < p).astype(float)
    assert S.brier(p, y) < S.brier(np.full_like(p, y.mean()), y)
    bins, edges = S.reliability(p, y)
    assert len(bins) == 10 and abs(sum(b["n"] for b in bins) - p.size) == 0
    assert S.ece(p, y) < 0.01
    for b in bins:
        assert b["wilson_lo"] <= b["freq"] <= b["wilson_hi"]


def test_wilson():
    lo, hi = S.wilson(55, 100)
    assert 0.45 < lo < 0.46 and 0.64 < hi < 0.65
    lo2, hi2 = S.wilson(550, 1000)
    assert hi2 - lo2 < hi - lo
    # copertura empirica ~95%
    rng = np.random.default_rng(0)
    cover = 0
    for _ in range(2000):
        k = rng.binomial(200, 0.53)
        a, b = S.wilson(k, 200)
        cover += a <= 0.53 <= b
    assert 0.93 <= cover / 2000 <= 0.97


def test_benjamini_hochberg():
    p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    keep = S.benjamini_hochberg(p, 0.10)
    # soglie q*i/n = 0,01 0,02 ... : il rango più alto con p <= soglia è il 6° (0,06 <= 0,06)
    assert keep[:6].all() and not keep[6:].any(), keep
    # FDR sotto controllo con tutti nulli: raramente qualcosa sopravvive
    rng = np.random.default_rng(5)
    any_fp = np.mean([S.benjamini_hochberg(rng.uniform(size=13), 0.10).any() for _ in range(2000)])
    print(f"    con 13 misure tutte nulle almeno una 'scoperta' nel {any_fp:.1%} dei casi")
    assert any_fp <= 0.12


def test_deflated_sharpe():
    rng = np.random.default_rng(2)
    r = rng.normal(0.01, 0.04, 80)
    one = S.deflated_sharpe(r, 1)["dsr"]
    many = S.deflated_sharpe(r, 200)["dsr"]
    assert many < one
    null = [S.deflated_sharpe(rng.normal(0, 0.04, 80), 50)["dsr"] for _ in range(300)]
    assert np.mean(np.array(null) > 0.95) < 0.05


def test_block_bootstrap_paired():
    rng = np.random.default_rng(4)
    n = 600
    dates = np.repeat(np.arange(n // 20), 20)
    y = (rng.uniform(size=n) < 0.5).astype(float)
    pa = np.full(n, 0.5)
    pb = np.clip(0.5 + 0.2 * (y - 0.5) + rng.normal(0, 0.01, n), 0.01, 0.99)   # B informativo
    t = S.paired_brier_test(dates, pa, pb, y, 3, 500)
    assert t["diff"] > 0 and t["p"] < 0.05
    t2 = S.paired_brier_test(dates, pb, pa, y, 3, 500)
    assert t2["p"] > 0.9


def test_promotion_rule():
    import collector
    assert not collector.promotion_rule(5, 3.0, True)["eligible"]
    assert not collector.promotion_rule(12, 1.5, True)["eligible"]
    assert not collector.promotion_rule(12, 2.5, False)["eligible"]
    assert collector.promotion_rule(12, 2.5, True)["eligible"]
    assert collector.periods_from_dates(372, 31) == 12


def test_digital_probability_and_skew():
    import priced
    iv, h, rf = 0.25, 31, 0.04
    T = h / 252
    flat = priced.digital_prob(iv, 0.0, h, rf, 1.0)
    d2 = (rf - 0.5 * iv * iv) * T / (iv * math.sqrt(T))
    assert abs(flat["p_rn"] - norm.cdf(d2)) < 1e-9
    skewed = priced.digital_prob(iv, -0.25, h, rf, 1.0)
    assert skewed["p_rn"] > flat["p_rn"]                 # skew negativo: mediana sopra lo spot
    assert flat["p_real"] > flat["p_rn"]                 # premio al rischio: probabilità reale più alta
    assert abs(flat["move"] - iv * math.sqrt(T)) < 1e-12
    # controllo Monte Carlo della correzione: smile lineare in K
    rng = np.random.default_rng(0)
    S0, slope = 100.0, -0.25
    K = np.linspace(80, 120, 401)
    sig = iv + slope * (K / S0 - 1)
    d1 = (np.log(S0 / K) + (rf + 0.5 * sig ** 2) * T) / (sig * np.sqrt(T))
    call = S0 * norm.cdf(d1) - K * np.exp(-rf * T) * norm.cdf(d1 - sig * np.sqrt(T))
    dig = -np.gradient(call, K) * np.exp(rf * T)
    p_num = float(np.interp(S0, K, dig))
    assert abs(p_num - skewed["p_rn"]) < 0.005, (p_num, skewed["p_rn"])


def test_reverse_dcf_roundtrip():
    import priced
    for g in (-0.05, 0.0, 0.07, 0.15, 0.3):
        price = priced.two_stage_dcf(5.0, 0.09, g)
        gi = priced.implied_growth(price, 5.0, 0.09)
        assert abs(gi - g) < 1e-5
    assert priced.base_rate_share(0.30) < priced.base_rate_share(0.10) < priced.base_rate_share(0.0)
    assert priced.implied_growth(100, -1.0, 0.09) is None


if __name__ == "__main__":
    f = common.run_module(globals())
    print("RISULTATI", RESULTS)
    sys.exit(1 if f else 0)
