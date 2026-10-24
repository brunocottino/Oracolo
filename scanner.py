"""Scanner automatico: analizza tutto l'universo (o un mercato) in background
e salva i segnali. Gira da solo una volta al giorno all'ora configurata."""
import threading
import time
import traceback
from datetime import datetime, timezone

import config
import db
import engine
from universe import INDICES, MARKETS, market_of

STATE = {"running": False, "done": 0, "total": 0, "current": None, "started": None, "errors": []}
_lock = threading.Lock()


def compact(o):
    """Versione ridotta del risultato da salvare (niente storico prezzi)."""
    o = dict(o)
    o.pop("history", None)
    return o


def tickers_for(markets=None):
    out = []
    if not markets or "Indici" in markets:
        out += list(INDICES.keys())
    for m, d in MARKETS.items():
        if not markets or m in markets:
            out += list(d.keys())
    return out


def run_scan(markets=None, tickers=None, nightly=False):
    """nightly=True (scansione automatica): prima salva le istantanee di classe B,
    poi rilancia il banco di prova se il report ha più di 20 ore, infine analizza i titoli."""
    with _lock:
        if STATE["running"]:
            return False
        lst = tickers or tickers_for(markets)
        STATE.update(running=True, done=0, total=len(lst), current=None, started=time.time(), errors=[])

    def work():
        db.scan_log("avviata", f"{len(lst)} titoli")
        if nightly:
            try:
                import collector
                STATE["current"] = "raccolta dati di classe B"
                n = collector.collect(tickers_for())
                db.scan_log("classe B", f"{n} valori salvati")
            except Exception as e:
                STATE["errors"].append(f"raccolta classe B: {e}")
            try:
                from lab import model as M, research
                rep = M.report()
                if not rep or time.time() - rep.get("ts", 0) > 20 * 3600:
                    STATE["current"] = "banco di prova (Laboratorio)"
                    research.run()
            except Exception as e:
                STATE["errors"].append(f"Laboratorio: {e}")
                traceback.print_exc()
        for t in lst:
            STATE["current"] = t
            try:
                o = engine.analyze(t, with_backtest=True, include_history=False)
                db.signal_put(t, market_of(t), compact(o))
            except Exception as e:
                STATE["errors"].append(f"{t}: {e}")
                traceback.print_exc()
            STATE["done"] += 1
        db.scan_log("completata", f"{STATE['done']} titoli, {len(STATE['errors'])} errori")
        STATE.update(running=False, current=None)

    threading.Thread(target=work, daemon=True).start()
    return True


def start_scheduler():
    """Controlla ogni 10 minuti; lancia la scansione una volta al giorno."""
    def loop():
        last_day = None
        while True:
            now = datetime.now(timezone.utc)
            if now.hour == config.SCAN_HOUR_UTC and last_day != now.date() and not STATE["running"]:
                last_day = now.date()
                run_scan(nightly=True)
            time.sleep(600)
    threading.Thread(target=loop, daemon=True).start()
