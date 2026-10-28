"""Aggiornamento automatico di Oracolo, senza Claude e senza servizi esterni.

Lancio:  python aggiorna.py            fotografia di oggi (forchetta, livelli 1-5, RSI) in data/oracolo/
         python aggiorna.py --lab      anche il Laboratorio rapido (lo fa da solo se l'ultimo ha più di 7 giorni)
Lo lancia il pianificatore del computer (installa_aggiornamento_windows.bat / setup_mac.sh).
Se Yahoo non risponde o escono pochi strumenti, la fotografia precedente resta com'è.
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "data", "oracolo")
MIN_STRUMENTI = 450
LAB_OGNI_GIORNI = 7


def log(msg):
    riga = f"{datetime.now():%Y-%m-%d %H:%M} {msg}"
    print(riga)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "aggiorna.log"), "a", encoding="utf-8") as f:
        f.write(riga + "\n")


def stato():
    try:
        return json.load(open(os.path.join(OUT, "stato.json"), encoding="utf-8"))
    except Exception:
        return {}


def fotografia():
    from lab import snapshot
    tmp = OUT + ".nuovo"
    shutil.rmtree(tmp, ignore_errors=True)
    t0 = time.time()
    snapshot.main(tmp)
    rows = json.load(open(os.path.join(tmp, "forchetta.json"), encoding="utf-8"))
    if len(rows) < MIN_STRUMENTI:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"solo {len(rows)} strumenti (minimo {MIN_STRUMENTI}): tengo la fotografia precedente")
    st = stato()
    st.update({"aggiornato": datetime.now(timezone.utc).isoformat(timespec="minutes"), "strumenti": len(rows),
               "panico": sum(1 for r in rows if (r.get("livello") or 0) >= 4),
               "ipercomprati": sum(1 for r in rows if r.get("avviso")), "secondi": round(time.time() - t0)})
    json.dump(st, open(os.path.join(tmp, "stato.json"), "w", encoding="utf-8"), ensure_ascii=False)
    shutil.rmtree(OUT, ignore_errors=True)
    os.replace(tmp, OUT)
    return st


def laboratorio_dovuto():
    ultimo = stato().get("lab")
    if not ultimo:
        return True
    return (datetime.now(timezone.utc) - datetime.fromisoformat(ultimo)).days >= LAB_OGNI_GIORNI


def laboratorio():
    from lab import research
    research.run(fast=True)
    st = stato()
    st["lab"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    os.makedirs(OUT, exist_ok=True)
    json.dump(st, open(os.path.join(OUT, "stato.json"), "w", encoding="utf-8"), ensure_ascii=False)


def main(argv):
    import db
    db.init()
    ok = True
    try:
        st = fotografia()
        log(f"fotografia ok: {st['strumenti']} strumenti, {st['panico']} in panico (livello 4-5), "
            f"{st['ipercomprati']} ipercomprati")
    except Exception as e:
        ok = False
        log(f"fotografia NON aggiornata: {str(e)[:200]}")
    if ok and ("--lab" in argv or laboratorio_dovuto()):
        try:
            laboratorio()
            log("Laboratorio rapido ok")
        except Exception as e:
            log(f"Laboratorio NON aggiornato: {str(e)[:200]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
