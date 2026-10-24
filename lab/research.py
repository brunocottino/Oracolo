"""Banco di prova (Laboratorio): test walk-forward su panel.

Procedura (uguale per azioni e indici, cambia solo l'orizzonte h):
  1. un'origine ogni 5 sedute; per ogni origine le misure note quel giorno
  2. addestramento a finestra crescente, minimo 756 sedute di storia, riaddestramento
     ogni 63 sedute
  3. PURGE: in addestramento entrano solo le origini il cui risultato è già noto
     (fine finestra) almeno EMBARGO=10 sedute prima dell'inizio del test
  4. HOLDOUT: le ultime 504 sedute non servono a scegliere nulla; funzionano solo da
     interruttore (se l'IC cambia segno o il Brier Skill Score è significativamente < 0
     il modello si spegne)
  5. calibrazione sulle previsioni fuori campione dei blocchi precedenti
  6. confronto con i benchmark, costi, Deflated Sharpe, registro delle prove
Il campione effettivo è sempre dichiarato come numero di PERIODI INDIPENDENTI
(date distinte x passo / h), non come numero di righe.
"""
import hashlib
import json
import math
import os
import pickle
import threading
import time
import traceback
import warnings

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

import config
import data
import db

from . import features as F
from . import panel as P
from . import stats as S

STATE = {"running": False, "pct": 0.0, "msg": "", "started": None, "finished": None, "error": None}
_run_lock = threading.Lock()


def logit_factory():
    return LogisticRegression(C=config.LAB["logit_C"], max_iter=1000)


def hgb_factory():
    return HistGradientBoostingClassifier(random_state=0, **config.LAB["hgb"])


def _hash(cfg):
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Walk-forward
# --------------------------------------------------------------------------
def walk_forward(panel, cols, factory, first_pos, retrain, embargo, min_rows=300, record=None):
    """Previsioni fuori campione. Per il blocco che inizia a T si addestra solo su
    righe con risultato noto entro T - embargo (purge = orizzonte).
    record (lista, facoltativo): vi si annotano (T, righe di addestramento, righe di test)."""
    op = panel["origin_pos"].values
    ep = panel["end_pos"].values
    y = panel["y"].values
    X = panel[cols].values.astype(float)
    labeled = np.isfinite(ep) & np.isfinite(y)
    n = len(panel)
    p = np.full(n, np.nan)
    base = np.full(n, np.nan)
    block = np.full(n, -1, dtype=np.int64)
    last = int(op.max())
    fitted = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for T in range(int(first_pos), last + 1, int(retrain)):
            test = (op >= T) & (op < T + retrain)
            if not test.any():
                continue
            tr = labeled & (ep + embargo < T)
            if tr.sum() < min_rows:
                continue
            yt = y[tr]
            if yt.min() == yt.max():
                continue
            m = factory().fit(X[tr], yt)
            if record is not None:
                record.append((T, np.nonzero(tr)[0], np.nonzero(test)[0]))
            p[test] = m.predict_proba(X[test])[:, 1]
            base[test] = yt.mean()
            block[test] = T
            fitted += 1
    return p, base, block, fitted


def purge_ok(op, ep, T, embargo):
    """Vero per le righe utilizzabili in addestramento prima di T (usato anche dai test)."""
    return np.isfinite(ep) & (ep + embargo < T)


def fit_guarded_calibrator(p, y, order):
    """Isotonica (>= 2.000 osservazioni) o Platt, adottata SOLO se sul passato più recente
    (ultimo 30%, mai il futuro) migliora il Brier rispetto alla previsione non calibrata.
    Con segnali deboli la regressione logistica è già quasi calibrata e una calibrazione
    rumorosa peggiorerebbe le cose."""
    iso_min = config.LAB["isotonic_min"]
    n = len(p)
    if n < 400:
        return S.Calibrator(iso_min).fit(p, y), False
    cut = np.quantile(order, 0.7)
    a, b = order <= cut, order > cut
    if a.sum() < 200 or b.sum() < 100:
        return S.Calibrator(iso_min).fit(p, y), False
    c0 = S.Calibrator(iso_min).fit(p[a], y[a])
    if S.brier(c0.predict(p[b]), y[b]) < S.brier(p[b], y[b]):
        return S.Calibrator(iso_min).fit(p, y), False
    return S.Calibrator(10 ** 12, 10 ** 12).fit(p, y), True     # identità


def calibrate_wf(panel, p, block, embargo):
    """Calibrazione sequenziale: il blocco T usa solo previsioni OOS già realizzate prima di T."""
    ep = panel["end_pos"].values
    op = panel["origin_pos"].values
    y = panel["y"].values
    pc = np.full(len(p), np.nan)
    kinds = {}
    ok = np.isfinite(p) & (block >= 0) & np.isfinite(ep) & np.isfinite(y)
    for T in sorted(set(block[block >= 0].tolist())):
        test = block == T
        hist = ok & (block < T) & (ep + embargo < T)
        cal, rejected = fit_guarded_calibrator(p[hist], y[hist], op[hist])
        pc[test] = cal.predict(p[test])
        k = "nessuna (non migliorava sul passato)" if rejected else cal.kind
        kinds[k] = kinds.get(k, 0) + 1
    return pc, kinds


def block_stat(panel, block, col, embargo):
    """Media di una colonna sulle righe di addestramento di ogni blocco (es. base rate)."""
    ep = panel["end_pos"].values
    v = panel[col].values
    out = np.full(len(block), np.nan)
    ok = np.isfinite(ep) & np.isfinite(v)
    for T in sorted(set(block[block >= 0].tolist())):
        tr = ok & (ep + embargo < T)
        if tr.any():
            out[block == T] = v[tr].mean()
    return out


# --------------------------------------------------------------------------
# Valutazione
# --------------------------------------------------------------------------
def evaluate(panel, mask, p_raw, p_cal, base, h, step, reps=1000):
    y = panel["y"].values
    sub = mask & np.isfinite(p_cal) & np.isfinite(y) & np.isfinite(base)
    if sub.sum() < 50:
        return {"n_obs": int(sub.sum()), "ok": False}
    d = panel["date"].values[sub]
    yy = y[sub]
    lag = max(1, math.ceil(h / step))
    ic = S.ic_summary(d, p_raw[sub], panel["y_res"].values[sub], h, step, min_n=5)
    b = S.brier(p_cal[sub], yy)
    bb = S.brier(base[sub], yy)
    bss, lo, hi = S.bss_interval(d, p_cal[sub], base[sub], yy, block=lag, reps=reps)
    rel, edges = S.reliability(p_cal[sub], yy, eff=min(1.0, step / h))
    e = S.ece(p_cal[sub], yy, edges)
    dts = pd.to_datetime(pd.Series(d))
    years = (dts.max() - dts.min()).days / 365.25
    by_year = []
    if len(ic["series"]):
        s = pd.Series(ic["series"], index=pd.to_datetime(ic["dates"]))
        for yr, g in s.groupby(s.index.year):
            by_year.append({"year": int(yr), "ic": float(g.mean()), "n": int(len(g))})
    return {"ok": True, "n_obs": int(sub.sum()), "n_dates": ic["n_dates"], "n_indep": ic["n_indep"],
            "years": years, "first": str(dts.min().date()), "last": str(dts.max().date()),
            "ic": ic["ic"], "ic_t": ic["t"], "ic_lag": ic["lag"],
            "brier": b, "brier_base": bb, "bss": bss, "bss_lo": lo, "bss_hi": hi,
            "ece": e, "reliability": rel, "edges": [float(x) for x in edges],
            "base_rate": float(np.mean(yy)), "by_year": by_year}


def ls_spread(panel, mask, score, h, step):
    """Spread netto quintile alto - quintile basso su periodi NON sovrapposti, con turnover e costi."""
    C = config.COSTS
    side = C["commission"] + (C["half_spread"] if config.LARGE_CAP_ALL else 2 * C["half_spread"])
    sub = panel.loc[mask, ["date", "ticker", "fwd", "mi"]].copy()
    sub["s"] = score[mask]
    sub = sub[np.isfinite(sub["s"]) & np.isfinite(sub["fwd"])]
    dates = np.sort(sub["date"].unique())
    k = max(1, math.ceil(h / step))
    reb = set(dates[::k].tolist())
    groups = {d: g for d, g in sub.groupby("date") if d in reb}
    prevL, prevS = set(), set()
    net, gross, turn, allv, rdates = [], [], [], [], []
    mi_of = dict(zip(sub["ticker"], sub["mi"]))
    for d in sorted(groups):
        g = groups[d]
        if len(g) < 10:
            continue
        q = g["s"].rank(pct=True)
        Lg, Sg = g[q > 0.8], g[q <= 0.2]
        if not len(Lg) or not len(Sg):
            continue
        rl = float(np.mean(np.exp(Lg["fwd"]) - 1))
        rs = float(np.mean(np.exp(Sg["fwd"]) - 1))
        nl, ns = set(Lg["ticker"]), set(Sg["ticker"])
        toL = 1 - len(nl & prevL) / len(nl)
        toS = 1 - len(ns & prevS) / len(ns)
        cost = (toL + toS) * 2 * side
        new_long = nl - prevL
        cover = prevS - ns
        cost += C["tobin_it"] * (sum(mi_of.get(t, False) for t in new_long) / len(nl))
        if prevS:
            cost += C["tobin_it"] * (sum(mi_of.get(t, False) for t in cover) / len(prevS))
        gross.append(rl - rs)
        net.append(rl - rs - cost)
        turn.append((toL + toS) / 2)
        allv.append(float(np.mean(np.exp(g["fwd"]) - 1)))
        rdates.append(str(pd.Timestamp(d).date()))
        prevL, prevS = nl, ns
    net = np.array(net)
    if len(net) < 5:
        return {"periods": int(len(net)), "ok": False}
    m, t, _ = S.nw_t(net, 1)
    per_year = 252 / (k * step)
    return {"ok": True, "periods": int(len(net)), "mean_net": float(net.mean()), "mean_gross": float(np.mean(gross)),
            "t": t, "turnover": float(np.mean(turn)), "ann_net": float(net.mean() * per_year),
            "long_all": float(np.mean(allv)), "hit": float(np.mean(net > 0)),
            "series": [float(x) for x in net], "dates": rdates, "period_days": k * step}


def feature_table(panel, mask, hold_mask, defs, h, step):
    rows = []
    for fd in defs:
        k = "x_" + fd["key"]
        sub = mask & np.isfinite(panel["y_res"].values)
        r = S.ic_summary(panel["date"].values[sub], panel[k].values[sub], panel["y_res"].values[sub], h, step)
        neg = 0.0
        if len(r["series"]):
            s = pd.Series(r["series"], index=pd.to_datetime(r["dates"]))
            ym = s.groupby(s.index.year).mean()
            neg = float((ym < 0).mean())
        hs = hold_mask & np.isfinite(panel["y_res"].values)
        rh = S.ic_summary(panel["date"].values[hs], panel[k].values[hs], panel["y_res"].values[hs], h, step)
        rows.append({**{kk: fd[kk] for kk in ("key", "label", "lit", "ref")},
                     "ic": _f(r["ic"]), "t": _f(r["t"]), "n_dates": r["n_dates"], "n_indep": r["n_indep"],
                     "neg_year_share": neg, "p": S.p_one_sided(r["t"]),
                     "holdout_ic": _f(rh["ic"]), "holdout_t": _f(rh["t"]),
                     "coverage": float(np.mean(panel.loc[mask, fd["key"]].notna())) if fd["key"] in panel else None})
    keep = S.benjamini_hochberg([r["p"] for r in rows], config.LAB["fdr"])
    for r, b in zip(rows, keep):
        r["bh"] = bool(b)
    return rows


def flag_cols(kind, keys):
    out = []
    if kind == "stocks":
        if any(k in F.EVENT_KEYS for k in keys):
            out.append("f_events")
        if any(k in F.GRADE_KEYS for k in keys):
            out.append("f_grades")
        if any(k in F.WIKI_KEYS for k in keys):
            out.append("f_wiki")
        if any(k in F.LAZY_KEYS for k in keys):
            out.append("f_lazy")
    elif any(k in ("vrp", "vix_term") for k in keys):
        out.append("f_vix")
    return out


def screen_features(rows):
    """Primo filtro: soglia t (2 con letteratura, 3 senza), Benjamini-Hochberg, stabilità per anno."""
    L = config.LAB
    for r in rows:
        thr = L["t_lit"] if r["lit"] else L["t_new"]
        reasons = []
        if r["t"] is None or r["t"] < thr:
            reasons.append(f"t {r['t'] if r['t'] is not None else float('nan'):.1f} sotto la soglia {thr:.0f}".replace(".", ","))
        if not r["bh"]:
            reasons.append("non supera il controllo dei falsi positivi (Benjamini-Hochberg 10%)")
        if r["neg_year_share"] > L["max_neg_year_share"]:
            reasons.append(f"IC negativo nel {r['neg_year_share'] * 100:.0f}% degli anni")
        r["reasons"] = reasons
    return rows


def ablation(panel, mask, kind, candidates, first_pos, h, step, embargo, retrain, reps):
    """Ablation sequenziale sulle misure che hanno superato il primo filtro, in ordine di t.
    Una misura resta solo se, togliendola dal gruppo già tenuto, il Brier fuori campione
    peggiora (bootstrap appaiato per data, p <= 0,10). Così due misure che dicono la stessa
    cosa (es. sorpresa utili e reazione all'annuncio) non si 'coprono' a vicenda."""
    lag = max(1, math.ceil(h / step))
    y = panel["y"].values
    dates = panel["date"].values
    kept, out = [], {}
    cur = None
    for k in candidates:
        cols = ["x_" + c for c in kept + [k]] + flag_cols(kind, kept + [k])
        p_new, base, _, _ = walk_forward(panel, cols, logit_factory, first_pos, retrain, embargo)
        ref = cur if cur is not None else base
        ok = mask & np.isfinite(p_new) & np.isfinite(ref) & np.isfinite(y)
        t = S.paired_brier_test(dates[ok], ref[ok], p_new[ok], y[ok], lag, reps)
        t["against"] = list(kept) if kept else ["frequenza storica"]
        out[k] = t
        if t["diff"] > 0 and t["p"] <= 0.10:
            kept.append(k)
            cur = p_new
    return out, kept


def decide_features(rows, abl, kept):
    for r in rows:
        a = (abl or {}).get(r["key"])
        if a is not None:
            r["ablation_p"] = a["p"]
            r["ablation_diff"] = a["diff"]
            r["ablation_against"] = a.get("against")
            if r["key"] not in kept:
                r["reasons"].append("togliendola la previsione non peggiora (ablation, p > 0,10)")
        r["status"] = "attiva" if (not r["reasons"] and r["key"] in kept) else "spenta"
    return rows


def by_group_ic(panel, mask, score, col, h, step):
    out = []
    for g, sub in panel[mask].groupby(col):
        idx = sub.index.values
        r = S.ic_summary(sub["date"].values, score[idx], sub["y_res"].values, h, step, min_n=5)
        if r["n_dates"] >= 10:
            out.append({"group": str(g), "ic": _f(r["ic"]), "t": _f(r["t"]), "n_indep": r["n_indep"]})
    return out


def by_vix_ic(panel, mask, score, h, step):
    try:
        vix = data.get_history("^VIX")[0]["close"]
    except Exception:
        return []
    sub = panel[mask].copy()
    if not len(sub):
        return []
    v = F.align(vix, pd.DatetimeIndex(sorted(sub["date"].unique())))
    sub["vix"] = sub["date"].map(v)
    q = sub["vix"].quantile([1 / 3, 2 / 3]).values
    sub["terz"] = np.where(sub["vix"] <= q[0], "VIX basso", np.where(sub["vix"] <= q[1], "VIX medio", "VIX alto"))
    out = []
    for g in ("VIX basso", "VIX medio", "VIX alto"):
        s2 = sub[sub["terz"] == g]
        idx = s2.index.values
        r = S.ic_summary(s2["date"].values, score[idx], s2["y_res"].values, h, step, min_n=5)
        out.append({"group": f"{g} (≤{q[0]:.0f})" if g == "VIX basso" else
                    f"{g} ({q[0]:.0f}-{q[1]:.0f})" if g == "VIX medio" else f"{g} (>{q[1]:.0f})",
                    "ic": _f(r["ic"]), "t": _f(r["t"]), "n_indep": r["n_indep"]})
    return out


# --------------------------------------------------------------------------
def _absolute_probs(panel, p_cal, h):
    """Dalla probabilità del residuo alla probabilità che il PREZZO salga:
    mu = beta * mu_indice (CAPM) + mu_residuo; mu_residuo = sigma_res * N^-1(p)."""
    rf = panel["rf"].values
    erp = config.EQUITY_RISK_PREMIUM
    beta = np.clip(panel["beta"].values, 0.2, 3.0)
    mu_b = (rf + erp) * h / 252 - 0.5 * panel["sig_b_h"].values ** 2
    mu_res = panel["sig_res_h"].values * norm.ppf(np.clip(p_cal, 0.01, 0.99))
    p_abs = norm.cdf((beta * mu_b + mu_res) / panel["sig_h"].values)
    mu_capm = (rf + beta * erp) * h / 252 - 0.5 * panel["sig_h"].values ** 2
    p_capm_abs = norm.cdf(mu_capm / panel["sig_h"].values)
    # CAPM sul residuo: nessun alfa, solo l'effetto della volatilità sul rendimento logaritmico
    mu_res_capm = (1 - beta) * rf * h / 252 - 0.5 * (panel["sig_h"].values ** 2 - beta * panel["sig_b_h"].values ** 2)
    p_capm_res = norm.cdf(mu_res_capm / panel["sig_res_h"].values)
    return p_abs, p_capm_abs, p_capm_res


def _bench_rows(panel, mask, items, ycol="y"):
    y = panel[ycol].values
    out = []
    for name, p, target in items:
        ok = mask & np.isfinite(p) & np.isfinite(y)
        out.append({"name": name, "target": target, "brier": S.brier(p[ok], y[ok]) if ok.any() else None,
                    "n": int(ok.sum()), "ok": ok})
    return out


def _bins_for_live(panel, mask, p_cal, h, step, edges):
    y = panel["y"].values
    ok = mask & np.isfinite(p_cal) & np.isfinite(y)
    rel, edges = S.reliability(p_cal[ok], y[ok], np.array(edges), eff=min(1.0, step / h))
    yres = panel["y_res"].values[ok]
    dts = panel["date"].values[ok]
    idx = np.clip(np.searchsorted(edges, p_cal[ok], side="right") - 1, 0, len(edges) - 2)
    C = config.COSTS
    rt = 2 * (C["commission"] + C["half_spread"])
    for b in rel:
        j = int(np.searchsorted(edges, b["lo"], side="right") - 1)
        m = idx == j
        r = np.exp(yres[m]) - 1
        b["mean_res"] = float(r.mean()) if m.any() else None
        b["mean_res_net_long"] = float(r.mean() - rt) if m.any() else None
        # periodi indipendenti: date distinte in cui la classe compare x passo / h (prudente)
        b["n_indep"] = float(len(np.unique(dts[m])) * step / h)
    return rel, [float(x) for x in edges]


# --------------------------------------------------------------------------
def run_panel(kind, progress=None, fast=False, panel_data=None):
    """Esegue l'intero banco di prova per 'stocks' o 'index'.
    Restituisce (report, artefatti per l'uso dal vivo)."""
    L = config.LAB
    t0 = time.time()
    prog = progress or (lambda x, m="": None)
    if kind == "stocks":
        h, defs, flags = config.HORIZON_STOCK, F.STOCK_FEATURES, list(F.STOCK_FLAGS)
        if panel_data is None:
            panel, cal, info = P.build_stock_panel(progress=lambda x, m="": prog(0.25 * x, m))
        else:
            panel, cal, info = panel_data
    else:
        h, defs, flags = config.HORIZON_INDEX, F.INDEX_FEATURES, list(F.INDEX_FLAGS)
        if panel_data is None:
            panel, cal, info = P.build_index_panel(progress=lambda x, m="": prog(0.25 * x, m))
        else:
            panel, cal, info = panel_data
    step = info["step"]
    lag = max(1, math.ceil(h / step))
    reps = 300 if fast else L["bootstrap"]
    Lc = len(cal)
    hold_start = Lc - L["holdout"]
    first_pos = int(panel["origin_pos"].min()) + L["min_train"]
    keys = [d["key"] for d in defs]
    xcols = ["x_" + k for k in keys]
    full_cols = xcols + flags
    op = panel["origin_pos"].values
    ep = panel["end_pos"].values
    labeled = np.isfinite(ep) & np.isfinite(panel["y"].values)
    dev = (op >= first_pos) & labeled & (ep < hold_start)
    hold = (op >= hold_start) & labeled
    rfs = data.short_rate_series()
    if kind == "stocks":
        if rfs is not None:
            panel["rf"] = panel["date"].map(F.align(rfs, pd.DatetimeIndex(sorted(panel["date"].unique())))).fillna(
                config.DEFAULT_RISK_FREE).values
        else:
            panel["rf"] = config.DEFAULT_RISK_FREE
    trials = []

    def trial(name, cfg, metrics):
        cfg = {"panel": kind, "h": h, "step": step, **cfg}
        trials.append((name, _hash(cfg), cfg, metrics))

    # ---- 1. modello primario: logistica L2 con tutte le misure ----
    prog(0.30, "Modello primario (logistica) walk-forward")
    p_full, base, blk, nfit = walk_forward(panel, full_cols, logit_factory, first_pos, L["retrain"], L["embargo"])
    pc_full, kinds = calibrate_wf(panel, p_full, blk, L["embargo"])
    ev_full = evaluate(panel, dev, p_full, pc_full, base, h, step, reps)
    primary = {"name": "Regressione logistica L2 (C=0,1)", "p": p_full, "pc": pc_full, "eval": ev_full,
               "kind": "logit"}
    trial("logistica completa", {"model": "logit", "C": L["logit_C"], "cols": full_cols},
          {k: ev_full.get(k) for k in ("ic", "ic_t", "brier", "bss", "ece")})

    # ---- 2. sfidante: gradient boosting ----
    challenger = None
    if L["run_challenger"] and not fast:
        prog(0.40, "Modello sfidante (gradient boosting) walk-forward")
        p_h, _, blk_h, _ = walk_forward(panel, full_cols, hgb_factory, first_pos, L["retrain"], L["embargo"])
        pc_h, _ = calibrate_wf(panel, p_h, blk_h, L["embargo"])
        ok = dev & np.isfinite(pc_h) & np.isfinite(pc_full)
        test = S.paired_brier_test(panel["date"].values[ok], pc_full[ok], pc_h[ok], panel["y"].values[ok], lag, reps)
        ev_h = evaluate(panel, dev, p_h, pc_h, base, h, step, reps)
        adopt = test["diff"] > 0 and test["p"] < 0.05
        challenger = {"name": "HistGradientBoosting (profondità 3)", "brier": ev_h.get("brier"),
                      "brier_primary": ev_full.get("brier"), "diff": test["diff"], "p": test["p"],
                      "adopted": bool(adopt), "ic": ev_h.get("ic")}
        trial("gradient boosting", {"model": "hgb", **L["hgb"], "cols": full_cols},
              {k: ev_h.get(k) for k in ("ic", "ic_t", "brier", "bss", "ece")})
        if adopt:
            primary = {"name": challenger["name"], "p": p_h, "pc": pc_h, "eval": ev_h, "kind": "hgb"}

    # ---- 3. misure: IC, BH, ablation, stabilità ----
    prog(0.60, "IC delle singole misure e controllo falsi positivi")
    rows = screen_features(feature_table(panel, dev, hold, defs, h, step))
    cands = [r["key"] for r in sorted(rows, key=lambda r: -(r["t"] or -99)) if not r["reasons"]]
    prog(0.65, "Ablation (ogni misura deve migliorare la previsione)")
    abl, kept = ablation(panel, dev, kind, cands, first_pos, h, step, L["embargo"],
                         L["ablation_retrain"] if not fast else 252, reps)
    for k, a in abl.items():
        trial(f"ablation {k}", {"model": "logit", "cols": ["x_" + c for c in a["against"] if c != "frequenza storica"] + ["x_" + k],
                                "retrain": L["ablation_retrain"]}, {"brier_diff": a["diff"], "p": a["p"]})
    rows = decide_features(rows, abl, kept)
    active = [r["key"] for r in rows if r["status"] == "attiva"]

    # ---- 4. modello finale (solo misure attive) e HOLDOUT ----
    prog(0.75, "Modello finale e holdout (ultime 504 sedute)")
    sel_cols = ["x_" + k for k in active]
    if sel_cols:
        sel_cols += flag_cols(kind, active)
    use_hgb = primary["kind"] == "hgb"
    final_cols = full_cols if use_hgb else sel_cols
    holdout = {"ok": False, "tripped": False, "why": []}
    p_sel = pc_sel = None
    if final_cols:
        fac = hgb_factory if use_hgb else logit_factory
        p_sel, base_s, blk_s, _ = walk_forward(panel, final_cols, fac, first_pos, L["retrain"], L["embargo"])
        pc_sel, _ = calibrate_wf(panel, p_sel, blk_s, L["embargo"])
        ev_sel_dev = evaluate(panel, dev, p_sel, pc_sel, base_s, h, step, reps)
        ev_hold = evaluate(panel, hold, p_sel, pc_sel, base_s, h, step, reps)
        holdout = {**ev_hold, "tripped": False, "why": []}
        trial("modello finale (misure attive)", {"model": primary["kind"], "cols": final_cols},
              {k: ev_sel_dev.get(k) for k in ("ic", "ic_t", "brier", "bss", "ece")})
        if ev_hold.get("ok"):
            if ev_sel_dev.get("ic") is not None and ev_hold["ic"] is not None and \
                    np.sign(ev_hold["ic"]) != np.sign(ev_sel_dev["ic"]):
                holdout["tripped"] = True
                holdout["why"].append(f"l'IC ha cambiato segno nell'holdout ({ev_hold['ic']:+.3f})".replace(".", ","))
            if ev_hold.get("bss_hi") is not None and ev_hold["bss_hi"] < 0:
                holdout["tripped"] = True
                holdout["why"].append("Brier Skill Score significativamente negativo nell'holdout")
        fin = {"p": p_sel, "pc": pc_sel, "base": base_s, "blk": blk_s, "eval": ev_sel_dev,
               "name": ("Modello finale: " + primary["name"] +
                        ("" if use_hgb else f" su {len(active)} misure attive"))}
    else:
        holdout["why"].append("nessuna misura attiva: nulla da verificare")
        fin = {"p": primary["p"], "pc": primary["pc"], "base": base, "blk": blk, "eval": primary["eval"],
               "name": "Nessuna misura attiva: mostrato il modello completo"}
    ev = fin["eval"]

    # ---- 5. benchmark (sul modello finale) ----
    prog(0.82, "Benchmark")
    mom_col = "x_mom_12_1" if kind == "stocks" else "x_tsmom_12"
    p_m, _, blk_m, _ = walk_forward(panel, [mom_col], logit_factory, first_pos, L["retrain"], L["embargo"])
    pc_m, _ = calibrate_wf(panel, p_m, blk_m, L["embargo"])
    okm = dev & np.isfinite(pc_m)
    trial("solo momentum", {"model": "logit", "cols": [mom_col]},
          {"brier": S.brier(pc_m[okm], panel["y"].values[okm]) if okm.any() else None})
    b_model = ev.get("brier")

    def brow(name, target, b, model_b):
        return {"name": name, "target": target, "brier": b, "model": model_b,
                "beaten": bool(b is not None and model_b is not None and model_b < b)}
    bench = []
    if kind == "stocks":
        p_abs, p_capm_abs, p_capm_res = _absolute_probs(panel, fin["pc"], h)
        base_abs = block_stat(panel, fin["blk"], "y_abs", L["embargo"])
        evm_ok = dev & np.isfinite(fin["pc"])
        for b in _bench_rows(panel, evm_ok, [("Frequenza storica (base rate)", fin["base"], "residuo"),
                                             ("Solo momentum 12-1", pc_m, "residuo"),
                                             ("Prior CAPM (nessun alfa)", p_capm_res, "residuo")], "y"):
            bench.append(brow(b["name"], "residuo", b["brier"], b_model))
        ok = evm_ok & np.isfinite(p_abs)
        b_model_abs = S.brier(p_abs[ok], panel["y_abs"].values[ok]) if ok.any() else None
        for b in _bench_rows(panel, ok, [("Sempre long (frequenza dei rialzi)", base_abs, "prezzo"),
                                         ("Prior CAPM", p_capm_abs, "prezzo")], "y_abs"):
            bench.append(brow(b["name"], "prezzo", b["brier"], b_model_abs))
    else:
        mu_capm = config.EQUITY_RISK_PREMIUM * h / 252 - 0.5 * panel["sig_h"].values ** 2
        p_capm = norm.cdf(mu_capm / panel["sig_h"].values)
        evm_ok = dev & np.isfinite(fin["pc"])
        for b in _bench_rows(panel, evm_ok, [("Frequenza storica (base rate)", fin["base"], "eccesso"),
                                             ("Solo trend 12 mesi", pc_m, "eccesso"),
                                             ("Prior CAPM (premio 5%)", p_capm, "eccesso")], "y"):
            bench.append(brow(b["name"], "eccesso sul tasso a breve", b["brier"], b_model))

    # ---- 6. spread long-short, stabilità ----
    spread = None
    if kind == "stocks":
        prog(0.86, "Spread quintili e costi")
        spread = ls_spread(panel, dev, fin["p"], h, step)
    by_area = by_group_ic(panel, dev, fin["p"], "market" if kind == "stocks" else "ticker", h, step)
    by_vix = by_vix_ic(panel, dev, fin["p"], h, step)

    # ---- 7. criterio di successo (modello finale, fuori campione) ----
    crit = []
    if kind == "stocks":
        crit.append({"name": "IC medio sul residuo ≥ 0,02 con t ≥ 2", "value": ev.get("ic"), "t": ev.get("ic_t"),
                     "ok": bool(ev.get("ok") and ev["ic"] >= L["min_ic"] and (ev["ic_t"] or 0) >= L["min_ic_t"])})
    crit.append({"name": "Brier Skill Score > 0 contro la frequenza storica", "value": ev.get("bss"),
                 "ok": bool(ev.get("ok") and ev["bss"] > 0)})
    crit.append({"name": "Errore di calibrazione (ECE) ≤ 3 punti", "value": ev.get("ece"),
                 "ok": bool(ev.get("ok") and ev["ece"] <= L["max_ece"])})
    if kind == "stocks":
        crit.append({"name": "Spread quintile alto - basso, netto costi, > 0",
                     "value": spread.get("mean_net") if spread else None,
                     "ok": bool(spread and spread.get("ok") and spread["mean_net"] > 0)})
    crit.append({"name": "Tutti i benchmark battuti (Brier)", "value": sum(b["beaten"] for b in bench),
                 "of": len(bench), "ok": all(b["beaten"] for b in bench)})
    crit.append({"name": "Holdout non contraddice il test", "ok": not holdout["tripped"] and bool(final_cols),
                 "value": None})
    crit_ok = all(c["ok"] for c in crit)
    fmt = lambda x, d=3: (f"{x:+.{d}f}".replace(".", ",") if x is not None else "n.d.")
    fails = []
    if not final_cols:
        fails.append("nessuna misura ha superato i test (t, falsi positivi, stabilità, ablation)")
    for c in crit:
        if c["ok"]:
            continue
        n = c["name"]
        if n.startswith("IC"):
            fails.append(f"IC {fmt(c['value'])} con t {fmt(c.get('t'), 1)}: servono almeno 0,02 e t ≥ 2")
        elif n.startswith("Brier"):
            fails.append(f"Brier Skill Score {fmt((c['value'] or 0) * 100, 2)}%: non batte la frequenza storica")
        elif n.startswith("Errore"):
            fails.append(f"errore di calibrazione {(c['value'] or 0) * 100:.1f} punti (massimo 3)".replace(".", ","))
        elif n.startswith("Spread"):
            fails.append(f"spread netto {fmt((c['value'] or 0) * 100, 2)}% per periodo: non positivo")
        elif n.startswith("Tutti"):
            fails.append(f"battuti solo {c['value']} benchmark su {c['of']}")
        elif n.startswith("Holdout") and final_cols:
            fails.append("holdout: " + "; ".join(holdout.get("why") or ["contraddice il test"]))
    reasons = fails
    state = "attivo" if crit_ok and final_cols else "spento"

    # ---- 8. Deflated Sharpe (dopo aver registrato le prove) ----
    for name, hsh, cfg, met in trials:
        db.trial_put(kind, name, hsh, cfg, met)
    n_trials = db.trials_count(kind)
    if spread and spread.get("ok"):
        spread["dsr"] = S.deflated_sharpe(spread["series"], n_trials)

    # ---- 9. artefatti per l'uso dal vivo ----
    prog(0.92, "Modello finale per l'uso quotidiano")
    live, art = {}, None
    labeled_all = labeled & (ep + L["embargo"] < Lc)
    if final_cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fac = hgb_factory if use_hgb else logit_factory
            m = fac().fit(panel.loc[labeled_all, final_cols].values, panel.loc[labeled_all, "y"].values)
        oos = np.isfinite(p_sel) & labeled
        cal_final, _ = fit_guarded_calibrator(p_sel[oos], panel["y"].values[oos], op[oos])
        evm = dev | hold
        edges = S.quantile_edges(pc_sel[evm & np.isfinite(pc_sel)])
        bins, edges = _bins_for_live(panel, evm, pc_sel, h, step, edges)
        last_d = panel["date"].max()
        xs = panel[panel["date"] == last_d]
        xp = cal_final.predict(m.predict_proba(xs[final_cols].values)[:, 1])
        coefs = {}
        if not use_hgb:
            coefs = {c: float(v) for c, v in zip(final_cols, m.coef_[0])}
        oos_pc = pc_sel[evm & np.isfinite(pc_sel)]
        live = {"cols": final_cols, "active": active, "base_rate": float(panel.loc[labeled_all, "y"].mean()),
                "edges": edges, "bins": bins, "coef": coefs,
                "score_q": [float(x) for x in np.quantile(oos_pc, np.linspace(0, 1, 101))],
                "xs_date": str(pd.Timestamp(last_d).date()),
                "xs": {k: [_f(v) for v in xs[k].values] for k in keys},
                "xs_tickers": list(xs["ticker"].values), "xs_pred": [float(v) for v in xp],
                "calibration": cal_final.kind}
        art = {"model": m, "cal": cal_final, "cols": final_cols, "keys": keys, "kind": primary["kind"]}
    for r in rows:
        r["coef"] = live.get("coef", {}).get("x_" + r["key"]) if live else None

    sample = {"n_obs": ev.get("n_obs"), "n_dates": ev.get("n_dates"), "n_indep": ev.get("n_indep"),
              "years": ev.get("years"), "first": ev.get("first"), "last": ev.get("last"),
              "n_tickers": info["n_tickers"], "h": h, "step": step, "rows_total": int(len(panel)),
              "holdout_indep": holdout.get("n_indep"), "calendar_first": info["first"],
              "calendar_last": info["last"], "retrain": L["retrain"], "embargo": L["embargo"],
              "min_train": L["min_train"], "holdout_days": L["holdout"], "fits": nfit}
    clean_ev = {k: v for k, v in ev.items()}
    clean_hold = {k: v for k, v in holdout.items()}
    pf = primary["eval"]
    report = {"kind": kind, "state": state, "reasons": reasons, "model": primary["name"],
              "final_model": fin["name"],
              "model_kind": primary["kind"], "calibration": kinds, "sample": sample,
              "dev": clean_ev, "dev_full": {k: pf.get(k) for k in ("ic", "ic_t", "brier", "bss", "ece", "n_indep")},
              "holdout": clean_hold, "benchmarks": bench, "challenger": challenger,
              "spread": ({k: v for k, v in spread.items() if k not in ("series",)} if spread else None),
              "features": rows, "by_area": by_area, "by_vix": by_vix,
              "criterion": crit, "criterion_ok": crit_ok, "live": live, "info": info,
              "n_trials": n_trials, "elapsed": round(time.time() - t0, 1), "fast": fast}
    if spread and spread.get("ok"):
        report["spread"]["series_tail"] = spread["series"][-60:]
    return report, art


# --------------------------------------------------------------------------
def run(fast=False, kinds=("stocks", "index"), save=True):
    """Lancia il banco di prova completo e salva report (SQLite) e modello (pickle)."""
    with _run_lock:
        if STATE["running"]:
            return None
        STATE.update(running=True, pct=0.0, msg="Avvio", started=time.time(), error=None)
    try:
        out = {"ts": time.time(), "demo": config.DEMO, "version": 2}
        if config.DEMO:
            out["demo_signal"] = {"signal": config.DEMO_SIGNAL, "ic": config.DEMO_SIGNAL_IC}
        arts = {}
        n = len(kinds)
        for i, k in enumerate(kinds):
            lo, hi = i / n, (i + 1) / n

            def prog(x, m="", lo=lo, hi=hi, k=k):
                STATE["pct"] = lo + (hi - lo) * x
                STATE["msg"] = ("Azioni: " if k == "stocks" else "Indici: ") + m
            rep, art = run_panel(k, prog, fast=fast)
            out[k] = rep
            arts[k] = art
        import collector
        out["class_b"] = collector.status()
        out["elapsed"] = round(time.time() - out["ts"], 1)
        out = _clean(out)
        if save:
            db.lab_report_put("all", out)
            os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
            with open(config.MODEL_PATH, "wb") as fh:
                pickle.dump({"ts": out["ts"], "arts": arts}, fh)
            from . import model as M
            M.reload()
        STATE.update(pct=1.0, msg="Completato")
        return out
    except Exception as e:
        traceback.print_exc()
        STATE["error"] = str(e)
        raise
    finally:
        STATE.update(running=False, finished=time.time())


def run_async(fast=False):
    if STATE["running"]:
        return False
    threading.Thread(target=lambda: _safe_run(fast), daemon=True).start()
    return True


def _safe_run(fast):
    try:
        run(fast=fast)
    except Exception:
        pass


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x).date())
    return x
