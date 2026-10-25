"""Forchetta attesa a 45 e 90 giorni e dimensione della posizione a rischio fisso.

Non dice se il prezzo salirà: dice entro quale intervallo starà con l'80% di probabilità.
Volatilità: sqrt(0,5 EWMA² + 0,5 storica 3 anni). Ampiezza e asimmetria calibrate sui risultati passati
(lab/band_test.py, 24-25/10/2026): fuori campione la banda contiene il 77-81,5% dei casi. Negli anni di crisi
(2008, 2020) la copertura scende fino al 33-65%: va detto al cliente.
"""
import math

import numpy as np

import config

H = {"45 giorni": 31, "90 giorni": 63}


def sigma_daily(r):
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    w = 0.94 ** np.arange(len(r[-500:]))[::-1]
    ew = float(np.sum(w * r[-500:] ** 2) / np.sum(w))
    lr = float(np.var(r[-756:]))
    return math.sqrt(0.5 * ew + 0.5 * lr)


def forchetta(df, kind="azioni", portfolio_risk=None):
    px = df["adj"].astype(float)
    r = np.diff(np.log(px.values))
    sd = sigma_daily(r)
    p = float(df["close"].iloc[-1])
    out = {}
    for label, h in H.items():
        z_lo, z_hi, z_mid = config.BANDS[kind][h]
        s = sd * math.sqrt(h)
        lo, hi, mid = (p * math.exp(z * s) for z in (z_lo, z_hi, z_mid))
        out[label] = {"low": lo, "high": hi, "mid": mid, "low_pct": lo / p - 1, "high_pct": hi / p - 1,
                      "mid_pct": mid / p - 1, "sessions": h}
    return {"price": p, "prob": 0.80, "kind": kind, "bands": out,
            "note": "Intervallo con l'80% di probabilità, verificato sul passato. Nelle crisi può essere superato."}


def risk_size(entry, stop, risk=None):
    """Peso in portafoglio tale che lo stop costi `risk` del portafoglio (0,5% di default)."""
    risk = config.RISK_PER_TRADE if risk is None else risk
    if not entry or not stop or stop >= entry:
        return None
    return float(min(risk / (1 - stop / entry), config.SIGNAL_RULES["max_position"]))
