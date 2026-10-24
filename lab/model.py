"""Uso quotidiano del modello panel addestrato dal Laboratorio.

Per un titolo calcola le misure di oggi, le confronta con la sezione trasversale
dell'ultima data del panel (rango in [-0,5; 0,5]) e restituisce la probabilità
calibrata che il rendimento RESIDUO a 31 sedute sia positivo, con il contributo
di ogni misura e l'affidabilità storica della classe di probabilità.
"""
import math
import os
import pickle
import threading
import time

import numpy as np
from scipy.stats import norm

import config
import db

from . import features as F

_lock = threading.Lock()
_cache = {"report": None, "report_t": 0.0, "arts": None, "arts_mtime": None}


def reload():
    with _lock:
        _cache.update(report=None, report_t=0.0, arts=None, arts_mtime=None)


def report():
    with _lock:
        if _cache["report"] is not None and time.time() - _cache["report_t"] < 30:
            return _cache["report"]
    r = db.lab_report_last("all")
    with _lock:
        _cache["report"], _cache["report_t"] = r, time.time()
    return r


def arts():
    p = config.MODEL_PATH
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return None
    with _lock:
        if _cache["arts"] is not None and _cache["arts_mtime"] == mt:
            return _cache["arts"]
    try:
        with open(p, "rb") as fh:
            a = pickle.load(fh)["arts"]
    except Exception:
        return None
    with _lock:
        _cache["arts"], _cache["arts_mtime"] = a, mt
    return a


def _feature_status(R):
    return {r["key"]: r for r in (R.get("features") or [])}


def _status_text(fr):
    if not fr:
        return "non testata"
    ic = fr.get("ic")
    t = fr.get("t")
    n = fr.get("n_indep")
    txt = (f"testata: IC {ic:+.3f}, t {t:.1f}, {n:.0f} periodi indipendenti".replace(".", ",")
           if ic is not None and t is not None and n is not None else "testata")
    return txt


def _bin_for(live, p):
    edges = np.array(live["edges"])
    j = int(np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2))
    lo = edges[j]
    for b in live["bins"]:
        if abs(b["lo"] - lo) < 1e-12:
            return b
    return min(live["bins"], key=lambda b: abs(b["p_mean"] - p)) if live["bins"] else None


def _cal_slope(cal, p):
    a, b = max(0.01, p - 0.05), min(0.99, p + 0.05)
    s = float((cal.predict([b])[0] - cal.predict([a])[0]) / (b - a))
    return float(np.clip(s, 0.3, 2.0)) if math.isfinite(s) else 1.0


def _empty(state, why, kind):
    return {"available": False, "state": state, "reasons": [why], "kind": kind}


def _predict(kind, x_now, raw_now, R, A, defs):
    live = R.get("live") or {}
    art = (A or {}).get(kind)
    fstat = _feature_status(R)
    rows = []
    if not live or not art:
        p_raw = p_cal = live.get("base_rate", 0.5) if live else 0.5
        contrib = {}
    else:
        cols = art["cols"]
        vec = np.array([[x_now.get(c, 0.0) for c in cols]])
        p_raw = float(art["model"].predict_proba(vec)[0, 1])
        p_cal = float(art["cal"].predict([p_raw])[0])
        slope = _cal_slope(art["cal"], p_raw)
        contrib = {}
        for c in cols:
            if not c.startswith("x_"):
                continue
            v2 = vec.copy()
            v2[0, cols.index(c)] = 0.0
            contrib[c[2:]] = (p_raw - float(art["model"].predict_proba(v2)[0, 1])) * slope
    for fd in defs:
        k = fd["key"]
        fr = fstat.get(k, {})
        status = fr.get("status", "non testata")
        rows.append({"key": k, "label": fd["label"], "value": raw_now.get(k),
                     "text": F.describe(k, raw_now), "rank": x_now.get("x_" + k),
                     "contrib": contrib.get(k, 0.0) if status == "attiva" or (art and art.get("kind") == "hgb") else 0.0,
                     "status": status, "tested": _status_text(fr), "reasons": fr.get("reasons", []),
                     "ic": fr.get("ic"), "t": fr.get("t"), "n_indep": fr.get("n_indep")})
    out = {"available": bool(live and art), "state": R.get("state"), "reasons": R.get("reasons", []),
           "kind": kind, "p_raw": p_raw, "p": p_cal, "rows": rows, "model": R.get("model"),
           "trained": R.get("sample", {}).get("last")}
    if live and live.get("bins"):
        b = _bin_for(live, p_cal)
        base = live.get("base_rate", 0.5)
        # intervallo al 95% centrato sulla stima, con l'ampiezza di Wilson della sua classe di probabilità
        ci = ((float(np.clip(p_cal - (b["freq"] - b["wilson_lo"]), 0.01, 0.99)),
               float(np.clip(p_cal + (b["wilson_hi"] - b["freq"]), 0.01, 0.99))) if b else None)
        out.update(base_rate=base, bin=b, ci=ci,
                   oos_pct=float(np.searchsorted(live["score_q"], p_cal) / 100.0),
                   xs_pct=float(np.mean(np.array(live["xs_pred"]) < p_cal)) if live.get("xs_pred") else None,
                   xs_n=len(live.get("xs_pred") or []), xs_date=live.get("xs_date"))
    else:
        out.update(base_rate=live.get("base_rate", 0.5) if live else 0.5, bin=None, ci=None,
                   oos_pct=None, xs_pct=None)
    return out


def stock_view(ticker, df, bench_df, events):
    R0 = report()
    if not R0 or not R0.get("stocks"):
        return _empty("non addestrato", "Il Laboratorio non ha ancora eseguito i test: premi 'Rilancia i test'.",
                      "stocks")
    R = R0["stocks"]
    A = arts()
    raw = F.stock_raw(df["adj"], bench_df["adj"], events)
    last = raw.iloc[-1]
    raw_now = {k: (float(last[k]) if np.isfinite(last[k]) else None) for k in raw.columns
               if isinstance(last[k], (float, np.floating, int))}
    xs = (R.get("live") or {}).get("xs", {})
    x_now = {"x_" + fd["key"]: F.rank_against(raw_now.get(fd["key"]), xs.get(fd["key"], []))
             for fd in F.STOCK_FEATURES}
    x_now["f_events"] = 1.0 if raw_now.get("sue") is None else 0.0
    x_now["f_grades"] = 1.0 if raw_now.get("upg_30") is None else 0.0
    out = _predict("stocks", x_now, raw_now, R, A, F.STOCK_FEATURES)
    h = config.HORIZON_STOCK
    out["beta"] = raw_now.get("beta")
    out["sig_res_h"] = (raw_now.get("sig_res_d") or 0.02) * math.sqrt(h)
    out["sig_b_h"] = (raw_now.get("sig_b_d") or 0.01) * math.sqrt(h)
    out["raw"] = {k: raw_now.get(k) for k in ("sue", "ear", "days_since_ea", "n_up_30", "n_down_30",
                                              "upg_30", "upg_90", "tgt_chg_30")}
    out["events_source"] = (events or {}).get("source")
    out["n_earnings"] = len((events or {}).get("earnings") or [])
    out["n_grades"] = len((events or {}).get("grades") or [])
    return out


def index_view(ticker, df, vix=None, vix3m=None):
    R0 = report()
    if not R0 or not R0.get("index"):
        return _empty("non addestrato", "Il Laboratorio non ha ancora eseguito i test.", "index")
    R = R0["index"]
    A = arts()
    raw = F.index_raw(df["adj"], vix, vix3m)
    x_now = {}
    for fd in F.INDEX_FEATURES:
        x_now["x_" + fd["key"]] = float(np.nan_to_num(F.ts_rank(raw[fd["key"]]).iloc[-1], nan=0.0))
    last = raw.iloc[-1]
    raw_now = {k: (float(last[k]) if np.isfinite(last[k]) else None) for k in raw.columns}
    x_now["f_vix"] = 1.0 if raw_now.get("vrp") is None else 0.0
    out = _predict("index", x_now, raw_now, R, A, F.INDEX_FEATURES)
    out["sig_h"] = (raw_now.get("sig_d") or 0.01) * math.sqrt(config.HORIZON_INDEX)
    out["vix"] = raw_now.get("vix")
    return out


def index_mu(view, rf):
    """Rendimento logaritmico atteso dell'indice sull'orizzonte di 63 sedute.
    Dal modello indici se attivo, altrimenti dal prior CAPM."""
    h = config.HORIZON_INDEX
    sig = view.get("sig_h") or 0.08
    prior = (rf + config.EQUITY_RISK_PREMIUM) * h / 252 - 0.5 * sig ** 2
    if view.get("available") and view.get("state") == "attivo":
        rf_h = math.log1p(rf) * h / 252
        return rf_h + sig * float(norm.ppf(np.clip(view["p"], 0.01, 0.99))), "modello indici"
    return prior, "prior CAPM (modello indici spento)"
