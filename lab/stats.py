"""Strumenti statistici del banco di prova.

Tutto in numpy/scipy, senza dipendenze extra:
  - IC di rango per data (Spearman) e t di Newey-West (sovrapposizione delle finestre)
  - Benjamini-Hochberg (controllo dei falsi positivi su molte prove)
  - intervallo di Wilson per una frequenza
  - calibrazione isotonica / Platt, Brier, Brier Skill Score, ECE, dati del reliability diagram
  - bootstrap a blocchi appaiato per data
  - Deflated Sharpe Ratio (Bailey & López de Prado, 2014)
"""
import math

import numpy as np
from scipy.stats import norm, rankdata, skew, kurtosis
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


# --------------------------------------------------------------------------
# IC e Newey-West
# --------------------------------------------------------------------------
def nw_t(x, lag):
    """Media, t e errore standard di Newey-West (kernel di Bartlett).
    lag = numero di periodi di sovrapposizione (h / passo delle origini)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 5:
        return (float(x.mean()) if n else float("nan")), float("nan"), float("nan")
    m = float(x.mean())
    u = x - m
    s = float(u @ u) / n
    for k in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - k / (lag + 1)) * float(u[k:] @ u[:-k]) / n
    se = math.sqrt(max(s, 1e-20) / n)
    return m, m / se, se


def rank_ic_by_date(dates, x, y, min_n=5):
    """IC di Spearman calcolato separatamente per ogni data. Restituisce (date_uniche, ic)."""
    dates = np.asarray(dates)
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    dates, x, y = dates[ok], x[ok], y[ok]
    order = np.argsort(dates, kind="stable")
    dates, x, y = dates[order], x[order], y[order]
    uniq, start = np.unique(dates, return_index=True)
    ends = list(start[1:]) + [len(dates)]
    out_d, out_ic = [], []
    for d, a, b in zip(uniq, start, ends):
        if b - a < min_n:
            continue
        xr = rankdata(x[a:b])
        yr = rankdata(y[a:b])
        xr -= xr.mean()
        yr -= yr.mean()
        den = math.sqrt(float(xr @ xr) * float(yr @ yr))
        if den <= 0:
            continue
        out_d.append(d)
        out_ic.append(float(xr @ yr) / den)
    return np.array(out_d), np.array(out_ic)


def ic_summary(dates, x, y, h, step, min_n=5):
    """IC medio, t di Newey-West, numero di date e periodi indipendenti."""
    d, ic = rank_ic_by_date(dates, x, y, min_n=min_n)
    lag = max(1, math.ceil(h / step))
    m, t, se = nw_t(ic, lag)
    return {"ic": m, "t": t, "se": se, "n_dates": int(len(ic)),
            "n_indep": float(len(ic) * step / h), "lag": lag,
            "dates": d, "series": ic}


def p_one_sided(t):
    if t is None or not math.isfinite(t):
        return 1.0
    return float(1 - norm.cdf(t))


def benjamini_hochberg(pvals, q=0.10):
    """Restituisce un array booleano: True = scoperta che sopravvive al controllo FDR."""
    p = np.asarray(pvals, float)
    n = len(p)
    if n == 0:
        return np.array([], bool)
    order = np.argsort(p)
    thr = q * (np.arange(1, n + 1) / n)
    passed = p[order] <= thr
    k = np.max(np.nonzero(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(n, bool)
    out[order[:k]] = True
    return out


def wilson(k, n, z=1.96):
    """Intervallo di Wilson al 95% per una frequenza k/n."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - hw), min(1.0, c + hw)


# --------------------------------------------------------------------------
# Probabilità: calibrazione e misure di qualità
# --------------------------------------------------------------------------
def brier(p, y):
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


class Calibrator:
    """Isotonica se ci sono almeno `iso_min` osservazioni, altrimenti Platt
    (regressione logistica sul logit della previsione), altrimenti identità."""

    def __init__(self, iso_min=2000, platt_min=200):
        self.iso_min, self.platt_min = iso_min, platt_min
        self.kind = "nessuna"
        self.m = None

    def fit(self, p, y):
        p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
        y = np.asarray(y, float)
        n = len(p)
        if n >= self.iso_min:
            self.m = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip").fit(p, y)
            self.kind = "isotonica"
        elif n >= self.platt_min and len(np.unique(y)) == 2:
            lg = np.log(p / (1 - p)).reshape(-1, 1)
            self.m = LogisticRegression(C=1e6, max_iter=500).fit(lg, y)
            self.kind = "Platt"
        else:
            self.m = None
            self.kind = "nessuna"
        return self

    def predict(self, p):
        p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
        if self.m is None:
            return p
        if self.kind == "isotonica":
            return np.clip(self.m.predict(p), 0.01, 0.99)
        lg = np.log(p / (1 - p)).reshape(-1, 1)
        return self.m.predict_proba(lg)[:, 1]


def quantile_edges(p, k=10):
    """Bordi di 10 classi a uguale numerosità (le previsioni sono concentrate
    vicino al 50%: classi a larghezza fissa sarebbero quasi tutte vuote)."""
    p = np.asarray(p, float)
    e = np.unique(np.quantile(p, np.linspace(0, 1, k + 1)))
    if len(e) < 2:
        e = np.array([0.0, 1.0])
    e[0], e[-1] = 0.0, 1.0
    return e


def reliability(p, y, edges=None, k=10, eff=1.0):
    """Per ogni classe: p media prevista, frequenza osservata, conteggio, intervallo di Wilson.
    eff = quota di osservazioni "indipendenti" (es. passo/h quando le finestre si sovrappongono):
    l'intervallo usa la numerosità effettiva n x eff, non il numero di righe."""
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    if edges is None:
        edges = quantile_edges(p, k)
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    out = []
    for b in range(len(edges) - 1):
        m = idx == b
        n = int(m.sum())
        if n == 0:
            continue
        k1 = float(y[m].sum())
        lo, hi = wilson(k1 * eff, n * eff)
        out.append({"lo": float(edges[b]), "hi": float(edges[b + 1]), "p_mean": float(p[m].mean()),
                    "freq": k1 / n, "n": n, "wilson_lo": lo, "wilson_hi": hi})
    return out, edges


def ece(p, y, edges=None, k=10):
    bins, _ = reliability(p, y, edges, k)
    n = sum(b["n"] for b in bins)
    if not n:
        return float("nan")
    return float(sum(b["n"] / n * abs(b["p_mean"] - b["freq"]) for b in bins))


# --------------------------------------------------------------------------
# Bootstrap a blocchi appaiato per data
# --------------------------------------------------------------------------
def per_date_mean(dates, v):
    dates = np.asarray(dates)
    v = np.asarray(v, float)
    u, inv = np.unique(dates, return_inverse=True)
    s = np.bincount(inv, weights=v)
    c = np.bincount(inv)
    return u, s / c


def block_bootstrap_mean(x, block, reps=1000, seed=0):
    """Distribuzione bootstrap della media di una serie autocorrelata (blocchi mobili)."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 3:
        return np.array([x.mean() if n else 0.0])
    block = int(max(1, min(block, n)))
    rng = np.random.default_rng(seed)
    nb = int(math.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    return x[idx].mean(axis=1)


def paired_brier_test(dates, p_a, p_b, y, block, reps=1000, seed=0):
    """Il modello B è migliore di A? Differenza media di Brier (A - B) per data,
    con p-value bootstrap = quota di repliche in cui B NON è migliore."""
    la = (np.asarray(p_a) - y) ** 2
    lb = (np.asarray(p_b) - y) ** 2
    _, d = per_date_mean(dates, la - lb)
    bs = block_bootstrap_mean(d, block, reps, seed)
    return {"diff": float(d.mean()), "p": float(np.mean(bs <= 0)), "n_dates": int(len(d))}


def bss_interval(dates, p, p_ref, y, block, reps=1000, seed=0):
    """Brier Skill Score con intervallo bootstrap al 95% (per data, a blocchi)."""
    y = np.asarray(y, float)
    _, a = per_date_mean(dates, (np.asarray(p) - y) ** 2)
    _, b = per_date_mean(dates, (np.asarray(p_ref) - y) ** 2)
    n = len(a)
    if n < 3:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    block = int(max(1, min(block, n)))
    nb = int(math.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    bss = 1 - a[idx].mean(1) / b[idx].mean(1)
    return float(1 - a.mean() / b.mean()), float(np.quantile(bss, 0.025)), float(np.quantile(bss, 0.975))


# --------------------------------------------------------------------------
# Deflated Sharpe Ratio
# --------------------------------------------------------------------------
def deflated_sharpe(returns, n_trials, sr_var_trials=None):
    """Probabilità che lo Sharpe osservato sia reale dopo aver provato `n_trials`
    configurazioni (Bailey & López de Prado, 2014). Sharpe per periodo (non annualizzato)."""
    r = np.asarray(returns, float)
    r = r[np.isfinite(r)]
    T = len(r)
    if T < 8 or r.std() == 0:
        return {"sr": float("nan"), "sr0": float("nan"), "dsr": float("nan"), "T": T, "n_trials": n_trials}
    sr = float(r.mean() / r.std(ddof=1))
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))
    N = max(int(n_trials), 1)
    v = sr_var_trials if (sr_var_trials and sr_var_trials > 0) else 1.0 / T
    emc = 0.5772156649
    if N > 1:
        sr0 = math.sqrt(v) * ((1 - emc) * norm.ppf(1 - 1 / N) + emc * norm.ppf(1 - 1 / (N * math.e)))
    else:
        sr0 = 0.0
    den = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr * sr, 1e-12))
    dsr = float(norm.cdf((sr - sr0) * math.sqrt(T - 1) / den))
    return {"sr": sr, "sr0": float(sr0), "dsr": dsr, "T": T, "n_trials": N, "skew": g3, "kurt": g4}
