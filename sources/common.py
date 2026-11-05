"""Rete e cache comuni alle fonti."""
import threading
import time

import requests

import db

# Wikimedia e SEC chiedono un User-Agent che identifichi il programma e un recapito.
# La SEC rifiuta gli User-Agent con un URL: formato "Nome recapito".
UA = {"User-Agent": "Oracolo/1.0 (https://github.com/brunocottino/Oracolo; uso personale) oracolo@example.org"}
UA_SEC = {"User-Agent": "Oracolo uso personale oracolo@example.org"}

_last = {}
ERRORI = {}   # ultimo errore per fonte (fred, ecb, stooq...), per il registro di aggiorna.py
_lock = threading.Lock()


def get(url, host_gap=1.0, timeout=30, tries=3, **kw):
    """GET con pausa minima tra richieste allo stesso host e rispetto di Retry-After (429)."""
    host = url.split("/")[2]
    for i in range(tries):
        with _lock:
            wait = _last.get(host, 0) + host_gap - time.time()
            if wait > 0:
                time.sleep(wait)
            _last[host] = time.time()
        r = requests.get(url, headers=UA_SEC if "sec.gov" in host else UA, timeout=timeout, **kw)
        if r.status_code == 429 and i < tries - 1:
            time.sleep(min(float(r.headers.get("retry-after") or 5), 90))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()


def cached(key, ttl, fetch):
    """Valore dalla cache se più giovane di ttl secondi, altrimenti fetch() e salva.
    Se fetch fallisce e c'è una copia vecchia, usa quella."""
    hit = db.cache_get("source_cache", key, ttl)
    if hit is not None:
        return hit
    try:
        val = fetch()
    except Exception as e:
        ERRORI[key.split(":")[0]] = f"{type(e).__name__}: {str(e)[:160]}"
        old = db.cache_get("source_cache", key, 10 ** 12)
        return old
    db.cache_put("source_cache", key, val)
    return val
