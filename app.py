"""Oracolo – piattaforma di previsione multi-agente (server web).

Avvio locale:   python app.py          poi apri http://localhost:8000
Produzione:     gunicorn app:app --workers 1 --threads 8 --timeout 180
"""
import os
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

import collector
import config
import data
import db
import engine
import portfolio
import scanner
from agents import all_agents
from lab import model as lab_model
from lab import research as lab_research
from universe import INDICES, MARKETS

app = Flask(__name__, static_folder="static", static_url_path="/static")
db.init()

_cache, _cache_lock = {}, threading.Lock()


def cached_analyze(t):
    t = t.upper().strip()
    lab_ts = (lab_model.report() or {}).get("ts")
    with _cache_lock:
        hit = _cache.get(t)
        if hit and time.time() - hit[0] < 3600 and hit[1].get("lab_ts") == lab_ts:
            return hit[1]
    o = engine.analyze(t)
    with _cache_lock:
        _cache[t] = (time.time(), o)
    db.signal_put(t, o["market"], scanner.compact(o))
    return o


@app.errorhandler(data.DataError)
def data_error(e):
    return jsonify({"error": str(e)}), 404


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/analyze")
def api_analyze():
    t = request.args.get("t", "").strip()
    if not t:
        return jsonify({"error": "Indica un ticker"}), 400
    try:
        return jsonify(cached_analyze(t))
    except data.DataError as e:
        # forse è un nome: prova la ricerca
        hits = data.search(t)
        return jsonify({"error": str(e), "suggestions": hits}), 404


@app.get("/api/search")
def api_search():
    return jsonify(data.search(request.args.get("q", "")))


@app.get("/api/overview")
def api_overview():
    sigs = db.signals_all()
    by_t = {s["ticker"]: s for s in sigs}
    idx = []
    for t, n in INDICES.items():
        s = by_t.get(t)
        idx.append({**(_row(s) if s else {}), "ticker": t, "name": n})
    stocks = [s for s in sigs if not s.get("is_index")]
    edge = lambda s: (s.get("plan", {}).get("edge") or 0)
    top_buy = sorted([s for s in stocks if s.get("plan", {}).get("signal") in ("COMPRA", "ACCUMULA SU DEBOLEZZA")],
                     key=lambda s: -edge(s))[:10]
    top_sell = sorted([s for s in stocks if s.get("plan", {}).get("signal") == "ALLEGGERISCI / VENDI"],
                      key=edge)[:6]
    rep = lab_model.report() or {}
    return jsonify({
        "indices": idx, "top_buy": [_row(s) for s in top_buy], "top_sell": [_row(s) for s in top_sell],
        "last_scan": db.scan_last(), "scan": scanner.STATE, "demo": config.DEMO,
        "n_signals": len(sigs), "n_universe": len(scanner.tickers_for()),
        "lab": {"stocks": (rep.get("stocks") or {}).get("state", "non addestrato"),
                "index": (rep.get("index") or {}).get("state", "non addestrato"), "ts": rep.get("ts")},
    })


def _row(s):
    pl, en = s.get("plan", {}), s.get("ensemble", {})
    return {
        "ticker": s["ticker"], "name": s.get("name"), "market": s.get("market"), "currency": s.get("currency"),
        "price": pl.get("price"), "signal": pl.get("signal"), "strength": pl.get("strength"),
        "p_up": en.get("p_up"), "base_rate": s.get("base_rate"), "ref": pl.get("ref"),
        "p_market": (s.get("priced") or {}).get("p_market"),
        "exp_return": en.get("exp_return"), "q25": (pl.get("quantiles") or {}).get("q25"),
        "q75": (pl.get("quantiles") or {}).get("q75"), "limit_price": pl.get("limit_price"),
        "horizon": s.get("horizon_label"), "asof": s.get("asof"), "scan_ts": s.get("scan_ts"),
        "chg_1d": (s.get("metrics") or {}).get("chg_1d"), "demo": s.get("demo"),
        "model_on": pl.get("model_on"),
    }


@app.get("/api/signals")
def api_signals():
    m = request.args.get("market")
    sigs = [s for s in db.signals_all() if not m or s.get("market") == m]
    return jsonify([_row(s) for s in sorted(sigs, key=lambda s: -((s.get("plan") or {}).get("edge") or
                                                                   (s.get("ensemble") or {}).get("p_up") or 0))])


@app.post("/api/scan")
def api_scan():
    body = request.get_json(silent=True) or {}
    ok = scanner.run_scan(markets=body.get("markets"))
    return jsonify({"started": ok, "state": scanner.STATE})


@app.get("/api/scan/status")
def api_scan_status():
    return jsonify({"state": scanner.STATE, "last": db.scan_last()})


@app.get("/api/portfolio")
def api_portfolio():
    return jsonify(engine.clean(portfolio.snapshot()))


@app.post("/api/portfolio")
def api_portfolio_add():
    b = request.get_json(force=True)
    try:
        t = b["ticker"].upper().strip()
        qty, px = float(b["qty"]), float(b["avg_price"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Servono ticker, quantità e prezzo di carico"}), 400
    data.get_history(t)  # verifica che il ticker esista
    hid = db.holding_add(t, qty, px, b.get("buy_date"), b.get("note"))
    return jsonify({"id": hid})


@app.delete("/api/portfolio/<int:hid>")
def api_portfolio_del(hid):
    db.holding_delete(hid)
    return jsonify({"ok": True})


@app.post("/api/portfolio/refresh")
def api_portfolio_refresh():
    ts = sorted({h["ticker"] for h in db.holdings_list()})
    ok = scanner.run_scan(tickers=ts) if ts else False
    return jsonify({"started": ok, "state": scanner.STATE})


@app.get("/api/agents")
def api_agents():
    return jsonify([{"name": a.name, "family": a.family, "source": a.source,
                     "description": a.description, "enabled": a.enabled,
                     "applies_to": a.applies_to,
                     "role": "base" if a.family == "base" else "informativo (peso 0, non validato)"}
                    for a in all_agents()])


# ---- Laboratorio ----
def _lab_summary(r):
    """Versione per la pagina: senza le sezioni trasversali grezze (pesanti)."""
    if not r:
        return None
    out = dict(r)
    lv = dict(out.get("live") or {})
    for k in ("xs", "xs_pred", "xs_tickers", "score_q"):
        lv.pop(k, None)
    out["live"] = lv
    return out


@app.get("/api/lab/status")
def api_lab_status():
    rep = lab_model.report()
    body = {"state": lab_research.STATE, "demo": config.DEMO, "yfinance": data.has_yfinance()}
    if rep:
        body["report"] = {"ts": rep.get("ts"), "elapsed": rep.get("elapsed"), "demo": rep.get("demo"),
                          "demo_signal": rep.get("demo_signal"),
                          "stocks": _lab_summary(rep.get("stocks")), "index": _lab_summary(rep.get("index")),
                          "class_b": rep.get("class_b")}
    else:
        body["report"] = None
        try:
            body["class_b"] = collector.status()
        except Exception:
            body["class_b"] = None
    return jsonify(engine.clean(body))


@app.post("/api/lab/run")
def api_lab_run():
    body = request.get_json(silent=True) or {}
    ok = lab_research.run_async(fast=bool(body.get("fast")))
    with _cache_lock:
        _cache.clear()
    return jsonify({"started": ok, "state": lab_research.STATE})


@app.get("/api/universe")
def api_universe():
    return jsonify({"Indici": INDICES, **MARKETS})


if config.AUTO_SCAN and os.environ.get("WERKZEUG_RUN_MAIN") != "false":
    scanner.start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
