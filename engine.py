"""Motore: mette insieme
  1. il MODELLO DI BASE (volatilità e prior CAPM),
  2. la previsione UFFICIALE dal modello panel calibrato del Laboratorio
     (rendimento residuo del titolo) + il modello indici tramite il beta,
  3. "cosa c'è già nel prezzo" (opzioni, reverse DCF, VIX),
  4. il piano operativo (ingresso, stop, obiettivo, dimensione) e il SEGNALE.
Gli agenti tradizionali (Holt, Momentum, Mean reversion, Regimi, Gradient
Boosting per singolo titolo, Valutazione CFA) restano visibili come agenti
INFORMATIVI a peso 0: non sono stati validati dal banco di prova panel.
"""
import math
import time
import traceback

import numpy as np
from scipy.stats import norm

import config
import bands
import data
import fundamentals
import priced
from agents import all_agents
from lab import model as M
from universe import is_index, name_of, market_of

Z = {"q05": -1.6449, "q10": -1.2816, "q25": -0.6745, "q50": 0.0, "q75": 0.6745, "q90": 1.2816, "q95": 1.6449}
SIGNALS = ("COMPRA", "ACCUMULA SU DEBOLEZZA", "NESSUN SEGNALE", "ALLEGGERISCI / VENDI")


def build_ctx(df, ticker, rf, fund, beta, cut=None):
    d = df if cut is None else df.iloc[:cut]
    px = d["adj"].values.astype(float)
    idx = is_index(ticker)
    h = config.HORIZON_INDEX if idx else config.HORIZON_STOCK
    b = 1.0 if idx or beta is None else float(np.clip(beta, 0.3, 2.5))
    return {
        "ticker": ticker, "is_index": idx, "h": h, "px": px,
        "r": np.diff(np.log(px)), "dates": d.index.values, "rf": rf,
        "erp": config.EQUITY_RISK_PREMIUM, "beta": b,
        "prior_annual": rf + b * config.EQUITY_RISK_PREMIUM,
        "fund": fund if cut is None else None,   # niente fondamentali "di oggi" nel passato
        "high": d["high"].values, "low": d["low"].values, "close": d["close"].values,
    }


# ---------------------------------------------------------------------------
def atr(df, n=14):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    return float(np.mean(tr[-n:]))


def simulate_barriers(entry, stop, target, mu, sigma, h, n=6000):
    """Probabilità di toccare prima l'obiettivo o prima lo stop (simulazione)."""
    rng = np.random.default_rng(1)
    z = rng.standard_normal((n, h))
    paths = entry * np.exp(np.cumsum(mu / h + sigma / math.sqrt(h) * z, axis=1))
    hit_t = paths >= target
    hit_s = paths <= stop
    t_first = np.where(hit_t.any(1), hit_t.argmax(1), h + 1)
    s_first = np.where(hit_s.any(1), hit_s.argmax(1), h + 1)
    p_t = float(np.mean(t_first < s_first))
    p_s = float(np.mean(s_first < t_first))
    neither = (t_first > h) & (s_first > h)
    end_ret = float(np.mean(paths[neither, -1] / entry - 1)) if neither.any() else 0.0
    ev = p_t * (target / entry - 1) + p_s * (stop / entry - 1) + float(neither.mean()) * end_ret
    return {"p_target_first": p_t, "p_stop_first": p_s, "p_neither": float(neither.mean()), "ev": ev}


def round_trip_cost(ticker):
    C = config.COSTS
    c = 2 * (C["commission"] + (C["half_spread"] if config.LARGE_CAP_ALL else 2 * C["half_spread"]))
    if ticker.upper().endswith(".MI"):
        c += C["tobin_it"]
    return c


def trade_plan(df, ens, ctx, ref, view, ticker):
    """Nuova regola del segnale (vedi README):
    COMPRA     p >= riferimento + 5 punti, limite inferiore di Wilson della classe di probabilità
               > frequenza storica, decile migliore dell'alfa previsto, valore atteso netto > 0
    ACCUMULA   p >= riferimento + 3 punti e stesso limite di Wilson; ingresso con ordine limite
    ALLEGGERISCI  speculare (p <= riferimento - 5 punti, decile peggiore)
    Interruttore: se il modello panel è spento, NESSUN SEGNALE per tutti."""
    R = config.SIGNAL_RULES
    p = float(df["close"].iloc[-1])
    a = atr(df)
    c = df["close"].values
    m20, s20 = c[-20:].mean(), c[-20:].std()
    supports = {
        "Minimo 20 sedute": float(df["low"].values[-20:].min()),
        "Banda di Bollinger inferiore": float(m20 - 2 * s20),
        "Media mobile 50": float(c[-50:].mean()),
        "Media mobile 200": float(c[-200:].mean()),
        "Prezzo - 1 ATR": p - a,
    }
    below = {k: v for k, v in supports.items() if p - 3 * a <= v < p}
    if below:
        lim_name, lim = max(below.items(), key=lambda kv: kv[1])
    else:
        lim_name, lim = "Prezzo - 1 ATR", p - a

    mu, sigma, h = ens["mu"], ens["sigma"], ctx["h"]
    quant = {k: p * math.exp(mu + z * sigma) for k, z in Z.items()}
    p_up = ens["p_up"]

    def plan_for(entry):
        stop = entry - R["atr_stop_mult"] * a
        target = max(quant["q75"], entry + 0.5 * (entry - stop))
        rr = (target - entry) / (entry - stop) if entry > stop else 0
        mu_e = mu + math.log(p / entry)
        sim = simulate_barriers(entry, stop, target, mu_e, sigma, h)
        return {"entry": entry, "stop": stop, "target": target, "reward_risk": rr, **sim}

    market = plan_for(p)
    limit = plan_for(lim)
    rt = round_trip_cost(ticker)
    market["ev_net"] = market["ev"] - rt
    limit["ev_net"] = limit["ev"] - rt

    edge = p_up - ref
    model_on = bool(view.get("available") and view.get("state") == "attivo")
    b = view.get("bin") or {}
    base_res = view.get("base_rate", 0.5)
    wl_buy = bool(b and b.get("wilson_lo", 0) > base_res)
    wl_sell = bool(b and b.get("wilson_hi", 1) < base_res)
    xs, oos = view.get("xs_pct"), view.get("oos_pct")
    top = bool((xs is not None and xs >= R["top_decile"]) or (oos is not None and oos >= R["top_decile"]))
    bottom = bool((xs is not None and xs <= 1 - R["top_decile"]) or (oos is not None and oos <= 1 - R["top_decile"]))
    checks = [
        {"name": "Modello panel attivo (test superati)", "ok": model_on},
        {"name": f"Probabilità ≥ riferimento + {R['buy_edge'] * 100:.0f} punti", "ok": edge >= R["buy_edge"],
         "value": edge},
        {"name": "Classe di probabilità affidabile (Wilson 95% sopra la frequenza storica)", "ok": wl_buy,
         "value": b.get("wilson_lo")},
        {"name": "Nel 10% migliore dell'alfa previsto", "ok": top, "value": xs if xs is not None else oos},
        {"name": "Valore atteso al netto dei costi > 0", "ok": market["ev_net"] > 0, "value": market["ev_net"]},
    ]
    if not model_on:
        why_off = "; ".join((view.get("reasons") or [])[:2]) or "test non superati"
        sig, use = "NESSUN SEGNALE", None
        why = (f"Il modello panel è spento ({why_off}). Finché il banco di prova non dà esito positivo "
               f"nessun titolo riceve un segnale: è un esito onesto, non un errore.")
    elif edge >= R["buy_edge"] and wl_buy and top and market["ev_net"] > 0:
        sig, use = "COMPRA", "market"
        why = (f"probabilità di rialzo {p_up:.0%} contro un riferimento del {ref:.0%} (+{edge * 100:.0f} punti), "
               f"classe di probabilità storicamente affidabile, tra i migliori 10% dell'alfa previsto, "
               f"valore atteso netto costi {market['ev_net']:+.1%}.")
    elif edge >= R["accumulate_edge"] and wl_buy and limit["ev_net"] > 0:
        sig, use = "ACCUMULA SU DEBOLEZZA", "limit"
        why = (f"vantaggio moderato ({p_up:.0%} contro {ref:.0%}): conviene entrare solo con un ordine limite "
               f"a {_it(lim)} ({lim_name.lower()}).")
    elif edge <= -R["sell_edge"] and wl_sell and bottom:
        sig, use = "ALLEGGERISCI / VENDI", None
        why = (f"probabilità di rialzo {p_up:.0%}, {abs(edge) * 100:.0f} punti sotto il riferimento ({ref:.0%}), "
               f"classe di probabilità storicamente debole, tra il 10% peggiore dell'alfa previsto.")
    else:
        sig, use = "NESSUN SEGNALE", None
        why = (f"probabilità di rialzo {p_up:.0%} contro un riferimento del {ref:.0%} "
               f"({edge * 100:+.0f} punti): il prezzo riflette già ciò che sappiamo.")
    size, kelly = 0.0, 0.0
    if use:
        pl = market if use == "market" else limit
        p_s = ref + R["kelly_shrink"] * (p_up - ref)
        bb = max(pl["reward_risk"], 0.1)
        kelly = (p_s * (1 + bb) - 1) / bb
        size = float(np.clip(kelly * R["kelly_fraction"], 0, R["max_position"]))
        if use == "limit":
            size *= 0.5
    strength = float(np.clip(abs(edge) / 0.10 * 100, 0, 100)) if model_on else 0.0
    return {
        "signal": sig, "why": why, "strength": strength, "use": use,
        "price": p, "atr": a, "atr_pct": a / p,
        "limit_name": lim_name, "limit_price": lim, "supports": supports,
        "plan_market": market, "plan_limit": limit, "cost_round_trip": rt,
        "position_size": size, "kelly_full": float(kelly), "kelly_note": "1/4 di Kelly su probabilità ridotta a metà verso il riferimento, max 10%",
        "quantiles": quant, "ref": ref, "edge": edge, "checks": checks, "model_on": model_on,
        "thresholds": {"buy": ref + R["buy_edge"], "accumulate": ref + R["accumulate_edge"],
                       "sell": ref - R["sell_edge"]},
    }


# ---------------------------------------------------------------------------
def _hist_series(t):
    try:
        return data.get_history(t)[0]["close"]
    except Exception:
        return None


def analyze(ticker: str, with_backtest: bool = True, include_history: bool = True) -> dict:
    t0 = time.time()
    ticker = ticker.upper().strip()
    df, meta = data.get_history(ticker)
    rf = data.risk_free_rate()
    fund = fundamentals.get_fundamentals(ticker)
    metrics = fundamentals.price_metrics(df, ticker)
    idx = is_index(ticker)
    vix_s, vix3m_s = _hist_series("^VIX"), _hist_series("^VIX3M")
    vix = float(vix_s.iloc[-1]) if vix_s is not None else None
    vix3m = float(vix3m_s.iloc[-1]) if vix3m_s is not None else None
    us = lambda t: t in data.US_INDICES

    # ---- modello panel (previsione ufficiale) ----
    bench = bview = None
    try:
        if idx:
            view = M.index_view(ticker, df, vix_s if us(ticker) else None, vix3m_s if us(ticker) else None)
        else:
            bench = fundamentals.benchmark_for(ticker)
            bdf = data.get_history(bench)[0]
            events = data.get_events(ticker)
            view = M.stock_view(ticker, df, bdf, events)
            bview = M.index_view(bench, bdf, vix_s if us(bench) else None, vix3m_s if us(bench) else None)
    except Exception as e:
        traceback.print_exc()
        view = {"available": False, "state": "errore", "reasons": [f"errore nel calcolo delle misure: {e}"]}
    beta = 1.0 if idx else (view.get("beta") or metrics.get("beta") or 1.0)
    ctx = build_ctx(df, ticker, rf, fund, beta)
    h = ctx["h"]

    # ---- modello di base + agenti informativi (peso 0) ----
    agents = [a for a in all_agents() if a.applicable(ctx)]
    results, errors, base = [], [], None
    for a in agents:
        try:
            res = a.run(ctx)
        except Exception as e:
            errors.append({"agent": a.name, "error": str(e)})
            traceback.print_exc()
            continue
        if a.family == "base":
            res.weight = 1.0
            res.extra["status"] = "modello di base: fornisce volatilità e prior"
            base = res
        else:
            res.weight = 0.0
            res.extra["status"] = "non validato (peso 0)"
        results.append(res)
    if base is None:
        raise data.DataError("Il modello di base non è riuscito a produrre una stima.")
    sigma = base.sigma
    prior = base.mu
    model_on = bool(view.get("available") and view.get("state") == "attivo")

    # ---- cosa c'è già nel prezzo ----
    lp = np.log(df["adj"].values)
    fwd = lp[h:] - lp[:-h]
    base_rate = float(np.mean(fwd > 0))
    try:
        mk = priced.market_view(ticker, df, fund, idx, h, beta, rf, sigma,
                                vix if us(ticker) else None, vix3m if us(ticker) else None)
    except Exception as e:
        traceback.print_exc()
        mk = {"p_market": None, "source": f"non disponibile ({e})", "from_options": False}
    ref = float(max(base_rate, mk.get("p_market") or 0.0))

    # ---- informazione NON ancora nel prezzo: spostamento rispetto al riferimento ----
    # La nostra stima parte da ciò che è già nel prezzo (riferimento) e aggiunge soltanto
    # l'alfa del modello panel (e l'eventuale inclinazione del modello indici), in unità di sigma.
    # Così il confronto noi-mercato non dipende dalla forma della distribuzione (skew delle opzioni).
    est = {"model_on": model_on, "state": view.get("state"), "reasons": view.get("reasons", [])}
    z_ref = float(norm.ppf(np.clip(ref, 0.01, 0.99)))
    to_p = lambda shift: float(norm.cdf(z_ref + shift))
    ci = None
    if idx:
        rf_h = math.log1p(rf) * h / 252
        mu_q = lambda q: rf_h + sigma * float(norm.ppf(np.clip(q, 0.01, 0.99)))
        if model_on:
            mu = mu_q(view["p"])
            src = "modello indici calibrato"
            if view.get("ci"):
                ci = [to_p((mu_q(q) - prior) / sigma) for q in view["ci"]]
        else:
            mu = prior
            src = ("prior CAPM (modello indici non ancora addestrato)" if view.get("state") == "non addestrato"
                   else "prior CAPM (modello indici spento)")
        alpha = mu - prior
        est.update(source=src, alpha=alpha, index_tilt=0.0)
    else:
        mu_b63, bsrc = M.index_mu(bview or {}, rf)
        b_sig = (bview or {}).get("sig_h") or 0.08
        prior_b63 = (rf + config.EQUITY_RISK_PREMIUM) * 63 / 252 - 0.5 * b_sig ** 2
        index_tilt = beta * (mu_b63 - prior_b63) * h / 63      # 0 se il modello indici è spento
        s_res = view.get("sig_res_h") or sigma * 0.7
        br = float(norm.ppf(np.clip(view.get("base_rate", 0.5), 0.01, 0.99)))
        a_of = lambda q: s_res * (float(norm.ppf(np.clip(q, 0.01, 0.99))) - br)
        alpha = a_of(view["p"]) if model_on else 0.0
        mu = prior + index_tilt + alpha
        if model_on and view.get("ci"):
            ci = [to_p((index_tilt + a_of(q)) / sigma) for q in view["ci"]]
        idx_part = ("modello indici via beta" if bsrc == "modello indici" else "indice al prior CAPM")
        est.update(source=(f"modello panel calibrato + {idx_part}" if model_on else
                           "prior CAPM (nessun modello validato: il prezzo riflette già ciò che sappiamo)"),
                   alpha=alpha, index_tilt=index_tilt, mu_index_63=mu_b63, benchmark=bench)
        # contributi delle misure riportati in punti di probabilità di rialzo del PREZZO
        if model_on and view.get("p") is not None:
            scale = float(norm.pdf(z_ref + (mu - prior) / sigma) * (s_res / sigma) /
                          max(norm.pdf(norm.ppf(np.clip(view["p"], 0.01, 0.99))), 1e-6))
            for r in view.get("rows") or []:
                r["contrib_res"] = r["contrib"]
                r["contrib"] = r["contrib"] * scale
    shift = (mu - prior) / sigma
    p_up = to_p(shift)
    est["shift_sigma"] = shift
    ens = {"mu": mu, "sigma": sigma, "p_up": p_up, "agreement": None,
           "exp_return": math.exp(mu + 0.5 * sigma ** 2) - 1, "median_return": math.exp(mu) - 1,
           "edge_vs_base": mu - prior, "source": est["source"], "ci": ci, "prior_mu": prior,
           "p_model_normal": float(norm.cdf(mu / sigma))}
    plan = trade_plan(df, ens, ctx, ref, view, ticker)

    # ---- cosa NON è ancora nel prezzo ----
    rep = M.report() or {}
    inside = list(view.get("rows") or [])
    class_b = [{"key": f["key"], "label": f["label"], "status": f["status"], "periods": f["periods"],
                "need": f["need"], "contrib": 0.0, "classe": "B"}
               for f in ((rep.get("class_b") or {}).get("fields") or [])] if not idx else []
    story = story_text(ticker, idx, ens, plan, view, mk, est)

    kind = "etf" if (idx or str(meta.get("type", "")).upper() == "ETF") else "azioni"
    fork = bands.forchetta(df, kind)
    stop = plan["price"] - config.SIGNAL_RULES["atr_stop_mult"] * plan["atr"]
    fork["stop"] = stop
    fork["size_risk"] = bands.risk_size(plan["price"], stop)
    out = {
        "forchetta": fork,
        "ticker": ticker, "name": (fund or {}).get("name") or meta.get("name") or name_of(ticker),
        "market": market_of(ticker), "is_index": idx,
        "currency": meta.get("currency"), "exchange": meta.get("exchange"), "demo": meta.get("demo", False),
        "horizon_days": h, "horizon_label": "3 mesi" if idx else "45 giorni",
        "asof": str(df.index[-1].date()), "rf": rf, "prior_annual": ctx["prior_annual"],
        "base_rate": base_rate, "ensemble": ens, "plan": plan, "estimate": est,
        "priced": mk, "panel": {k: v for k, v in view.items() if k not in ("rows",)},
        "not_priced": inside, "class_b": class_b, "story": story, "beta": beta,
        "agents": [r.to_dict() for r in results], "errors": errors,
        "fundamentals": fund, "metrics": metrics,
        "lab_ts": rep.get("ts"),
        "elapsed": round(time.time() - t0, 2),
    }
    out["summary"] = summary_text(out)
    if include_history:
        tail = df.iloc[-260:]
        out["history"] = {"dates": [str(d.date()) for d in tail.index], "close": [float(x) for x in tail["close"]]}
    return clean(out)


# ---------------------------------------------------------------------------
def _pp(x, d=0):
    return f"{x * 100:.{d}f}%".replace(".", ",")


def story_text(ticker, idx, ens, plan, view, mk, est):
    """La frase per l'utente: cosa prezza il mercato, cosa stimiamo noi, da dove viene la differenza."""
    days = mk.get("calendar_days", 45)
    parts = []
    pm = mk.get("p_market")
    if pm is not None:
        if mk.get("from_options"):
            s = f"Il mercato prezza il {_pp(pm)} di probabilità di rialzo e un movimento di ±{_pp(mk.get('move') or 0)} in {days} giorni"
        else:
            s = (f"Non ci sono opzioni quotate: come riferimento di mercato usiamo media storica + CAPM, "
                 f"cioè il {_pp(pm)} di probabilità di rialzo con un movimento tipico di ±{_pp(mk.get('move') or 0)} in {days} giorni")
        rd = mk.get("rdcf") or {}
        if rd.get("g_implied") is not None:
            s += f"; il prezzo implica una crescita del free cash flow del {_pp(rd['g_implied'])} annuo per 5 anni"
            if rd.get("g_consensus") is not None:
                s += f" contro il {_pp(rd['g_consensus'])} del consenso"
            if rd.get("base_rate") is not None:
                s += f" (crescita raggiunta da circa il {_pp(rd['base_rate'])} delle aziende)"
        parts.append(s + ".")
    p = ens["p_up"]
    if not est.get("model_on"):
        if est.get("state") == "non addestrato":
            parts.append("Il Laboratorio non ha ancora eseguito i test, quindi non abbiamo un modello validato. "
                         "Il prezzo riflette già ciò che sappiamo: NESSUN SEGNALE.")
        else:
            why = "; ".join((est.get("reasons") or [])[:2]) or "test non superati"
            parts.append(f"Noi non abbiamo un modello validato (il Laboratorio lo ha spento: {why}). "
                         f"Il prezzo riflette già ciò che sappiamo: NESSUN SEGNALE.")
        return " ".join(parts)
    ci = ens.get("ci")
    parts.append(f"Noi stimiamo il {_pp(p)}" + (f" (intervallo {_pp(ci[0])}–{_pp(ci[1])})" if ci else "") +
                 f"; il riferimento è il {_pp(plan['ref'])}.")
    diff = plan["edge"]
    if plan["signal"] == "NESSUN SEGNALE" and abs(plan["edge"]) < config.SIGNAL_RULES["accumulate_edge"]:
        parts.append("Il prezzo riflette già ciò che sappiamo: NESSUN SEGNALE.")
        return " ".join(parts)
    rows = [r for r in (view.get("rows") or []) if r.get("contrib") and abs(r["contrib"]) >= 0.002
            and np.sign(r["contrib"]) == np.sign(diff)]
    rows.sort(key=lambda r: -abs(r["contrib"]))
    if rows:
        parts.append(f"La differenza di {diff * 100:+.0f} punti viene da: " +
                     ", ".join(r["text"] for r in rows[:3]) + ".")
    b = view.get("bin") or {}
    if b:
        up = diff > 0
        hit = b["freq"] if up else 1 - b["freq"]
        net = b.get("mean_res_net_long") if up else (-(b.get("mean_res") or 0) - plan["cost_round_trip"])
        parts.append(f"Segnali simili hanno funzionato nel {_pp(hit)} di {b.get('n', 0):,} casi".replace(",", ".") +
                     f" (circa {b.get('n_indep', 0):.0f} periodi indipendenti)" +
                     (f", al netto dei costi {net * 100:+.1f}%".replace(".", ",") if net is not None else "") + ".")
    if plan["signal"] == "NESSUN SEGNALE":
        parts.append("Non tutte le condizioni sono soddisfatte: NESSUN SEGNALE.")
    return " ".join(parts)


def clean(x):
    """Rende il risultato serializzabile in JSON (niente NaN/inf, niente tipi numpy)."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, np.ndarray):
        return clean(x.tolist())
    return x


def _it(x, d=2):
    """Formato numerico italiano: 1.234,56"""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def summary_text(o):
    e, p = o["ensemble"], o["plan"]
    q = p["quantiles"]
    cur = o["currency"] or ""
    lines = [
        f"Orizzonte {o['horizon_label']}. Previsione: {e['source']}.",
        f"Probabilità di rialzo {e['p_up']:.0%} contro un riferimento del {p['ref']:.0%} "
        f"(frequenza storica del titolo {o['base_rate']:.0%}, mercato "
        f"{(o['priced'].get('p_market') or 0):.0%}). Rendimento atteso {_pp(e['exp_return'], 1)}.",
        f"Scenario centrale {_it(q['q50'])} {cur}; in 1 caso su 4 sotto {_it(q['q25'])}, "
        f"in 1 caso su 4 sopra {_it(q['q75'])}; 1 caso su 20 sotto {_it(q['q05'])}.",
        f"Segnale: {p['signal']} — {p['why']}",
    ]
    if p["use"]:
        pl = p["plan_market"] if p["use"] == "market" else p["plan_limit"]
        lines.append(
            f"Piano: ingresso {_it(pl['entry'])}, stop {_it(pl['stop'])}, obiettivo {_it(pl['target'])} "
            f"(rapporto guadagno/rischio {_it(pl['reward_risk'], 1)}). Probabilità di toccare prima "
            f"l'obiettivo {pl['p_target_first']:.0%}, prima lo stop {pl['p_stop_first']:.0%}. "
            f"Peso suggerito {p['position_size']:.1%} del portafoglio (1/4 di Kelly).")
    return lines
