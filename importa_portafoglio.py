"""Carica un portafoglio salvato (data/portafogli/<nome>.json) nella scheda Portafoglio.

Uso:  python importa_portafoglio.py bruno            (aggiunge le posizioni con ticker Yahoo)
      python importa_portafoglio.py bruno --sostituisci   (prima svuota la scheda)

Certificati, obbligazioni e fondi senza ticker Yahoo gratuito restano solo nel file.
Se manca il prezzo di carico usa il prezzo di oggi (P&L parte da zero: correggilo a mano).
"""
import json
import sys
from pathlib import Path

import data
import db


def main(nome="bruno", sostituisci=False):
    doc = json.loads((Path(__file__).parent / "data" / "portafogli" / f"{nome}.json").read_text("utf-8"))
    db.init()
    if sostituisci:
        for h in db.holdings_list():
            db.holding_delete(h["id"])
    ok, saltati = 0, []
    for p in doc["posizioni"]:
        t = p.get("ticker")
        if not t:
            saltati.append(p["nome"])
            continue
        try:
            df, _ = data.get_history(t)
            px = p.get("prezzo_carico") or float(df["close"].iloc[-1])
        except Exception as e:  # ticker non raggiungibile: non bloccare il resto
            saltati.append(f"{p['nome']} ({t}: {e})")
            continue
        nota = f"{doc['nome']} · {p['isin']}" + ("" if p.get("prezzo_carico") else " · carico provvisorio")
        db.holding_add(t, p["qty"], px, doc.get("aggiornato"), nota)
        ok += 1
    print(f"{doc['nome']}: caricate {ok} posizioni, {len(saltati)} solo nel file.")
    for s in saltati:
        print("  -", s)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "bruno", "--sostituisci" in sys.argv)
