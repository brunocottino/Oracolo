"""Diario delle decisioni: si scrive PRIMA di eseguire e non si può modificare.

Ogni voce è una riga di privato/diario.jsonl con l'impronta (hash) della voce precedente:
se qualcuno cambia una riga vecchia, la verifica lo segnala. Per correggere si aggiunge una nota.

    python diario.py apri --strumento "ETF esempio" --ticker XYZ.MI --quantita 10 --prezzo 100 \\
        --perche "Panico livello 4" --orizzonte 21 --stop 94 --obiettivo 105
    python diario.py apri --strumento "Switch B->A" --ticker A --prezzo 100 --contro B \\
        --prezzo-contro 50 --importo 10000 --perche "..." --orizzonte 91 --stop-rel -0.04
    python diario.py chiudi --rif 1 --prezzo 98 --motivo "..."
    python diario.py nota --testo "..."
    python diario.py verifica | rapporto
Con --data AAAA-MM-GG si registra una decisione passata: resta segnata come "registrata dopo".
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
PRIV = os.environ.get("ORACOLO_PRIVATO", os.path.join(ROOT, "privato"))
FILE = "diario.jsonl"


def _path():
    return os.path.join(PRIV, FILE)


def _impronta(rec):
    corpo = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def leggi():
    try:
        with open(_path(), encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []


def verifica(recs):
    prev = "0" * 64
    for i, r in enumerate(recs, 1):
        if r.get("prev") != prev or _impronta(r) != r.get("hash"):
            return False, f"La voce {r.get('id', i)} è stata modificata o la catena è rotta."
        prev = r["hash"]
    return True, "ok"


def aggiungi(tipo, **campi):
    recs = leggi()
    ok, msg = verifica(recs)
    if not ok:
        raise ValueError(msg)
    campi = {k: v for k, v in campi.items() if v is not None}
    if tipo == "apertura":
        manca = [k for k in ("strumento", "ticker", "prezzo", "perche", "orizzonte_giorni") if k not in campi]
        if "stop" not in campi and "stop_rel" not in campi:
            manca.append("stop o stop_rel")
        if manca:
            raise ValueError("Mancano: " + ", ".join(manca) + ". Una decisione senza piano non si registra.")
    if tipo == "chiusura":
        aperte = {r["id"] for r in recs if r["tipo"] == "apertura"} - {r.get("rif") for r in recs if r["tipo"] == "chiusura"}
        if campi.get("rif") not in aperte:
            raise ValueError(f"Nessuna posizione aperta con id {campi.get('rif')}. Aperte: {sorted(aperte)}")
    oggi = date.today().isoformat()
    rec = {"id": len(recs) + 1, "tipo": tipo, "registrata": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "data": campi.pop("data", None) or oggi, **campi, "prev": recs[-1]["hash"] if recs else "0" * 64}
    rec["dopo"] = rec["data"] < oggi
    rec["hash"] = _impronta(rec)
    os.makedirs(PRIV, exist_ok=True)
    with open(_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _al(s, giorno):
    s = s.dropna()
    s = s[s.index <= str(giorno)]
    return float(s.iloc[-1]) if len(s) else None


def valuta(ap, ch, loc, eur, bench):
    """Esito di una decisione rispetto al suo piano. loc/eur: DataFrame di chiusure (valuta locale / euro)."""
    fine = ch["data"] if ch else str(date.today())
    t = loc.get(ap["ticker"])
    p1 = ch["prezzo"] if ch else (_al(t, fine) if t is not None else None)
    if p1 is None:
        return None
    r = p1 / ap["prezzo"] - 1
    if ap.get("contro"):
        c = loc.get(ap["contro"])
        c1 = ch.get("prezzo_contro") if ch and ch.get("prezzo_contro") else (_al(c, fine) if c is not None else None)
        if c1 is None:
            return None
        r -= c1 / ap["prezzo_contro"] - 1
    importo = ap.get("importo") or (ap.get("quantita", 0) * ap["prezzo"])
    giorni = (date.fromisoformat(fine) - date.fromisoformat(ap["data"])).days
    stop_toccato = False
    if t is not None and not ap.get("contro") and ap.get("stop"):
        s = t.dropna()
        s = s[(s.index > ap["data"]) & (s.index <= fine)]
        stop_toccato = bool(len(s) and s.min() <= ap["stop"])
    if ap.get("stop_rel") is not None and r <= ap["stop_rel"]:
        stop_toccato = True
    b = eur.get(bench)
    rb = (_al(b, fine) / _al(b, ap["data"]) - 1) if b is not None and _al(b, ap["data"]) else None
    return {"rend": r, "euro": r * importo, "giorni": giorni, "orizzonte": ap["orizzonte_giorni"],
            "stop_toccato": stop_toccato, "bench": rb, "chiusa": bool(ch)}


def rapporto_md(recs, loc, eur, bench):
    ch = {r["rif"]: r for r in recs if r["tipo"] == "chiusura"}
    righe = ["| # | Decisione | Dal | Risultato | Giorni / piano | Piano rispettato? | ACWI stesso periodo |", "|---|---|---|---|---|---|---|"]
    for ap in (r for r in recs if r["tipo"] == "apertura"):
        v = valuta(ap, ch.get(ap["id"]), loc, eur, bench)
        if not v:
            righe.append(f"| {ap['id']} | {ap['strumento']} | {ap['data']} | prezzo non disponibile | | | |")
            continue
        note = []
        if v["chiusa"] and v["giorni"] < v["orizzonte"] and not v["stop_toccato"]:
            note.append("chiusa prima dell'orizzonte senza stop")
        if v["stop_toccato"] and not v["chiusa"]:
            note.append("**stop toccato: va chiusa**")
        if not v["chiusa"] and v["giorni"] > v["orizzonte"]:
            note.append("**orizzonte scaduto: decidi**")
        stato = "aperta" if not v["chiusa"] else "chiusa"
        righe.append(f"| {ap['id']}{'*' if ap.get('dopo') else ''} | {ap['strumento']} ({stato}) | {ap['data']} | "
                     f"{v['rend'] * 100:+.1f}% ({v['euro']:+.0f} €) | {v['giorni']} / {v['orizzonte']} | "
                     f"{'; '.join(note) or 'sì'} | {'' if v['bench'] is None else format(v['bench'] * 100, '+.1f') + '%'} |")
    if any(r.get("dopo") for r in recs):
        righe += ["", "_* registrata dopo l'operazione: vale come memoria, non come decisione presa prima._"]
    return righe


def main(argv=None):
    a = argparse.ArgumentParser(description="Diario delle decisioni")
    sub = a.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("apri")
    for k in ("strumento", "ticker", "perche", "contro", "data"):
        o.add_argument("--" + k)
    for k in ("quantita", "prezzo", "prezzo-contro", "importo", "stop", "stop-rel", "obiettivo"):
        o.add_argument("--" + k, type=float)
    o.add_argument("--orizzonte", type=int, required=True, help="giorni di calendario")
    c = sub.add_parser("chiudi")
    c.add_argument("--rif", type=int, required=True)
    c.add_argument("--prezzo", type=float, required=True)
    c.add_argument("--prezzo-contro", type=float)
    c.add_argument("--motivo")
    c.add_argument("--data")
    n = sub.add_parser("nota")
    n.add_argument("--testo", required=True)
    n.add_argument("--data")
    sub.add_parser("verifica")
    sub.add_parser("rapporto")
    x = a.parse_args(argv)
    if x.cmd == "apri":
        r = aggiungi("apertura", strumento=x.strumento, ticker=x.ticker, quantita=x.quantita, prezzo=x.prezzo,
                     contro=x.contro, prezzo_contro=x.prezzo_contro, importo=x.importo, perche=x.perche,
                     orizzonte_giorni=x.orizzonte, stop=x.stop, stop_rel=x.stop_rel, obiettivo=x.obiettivo, data=x.data)
    elif x.cmd == "chiudi":
        r = aggiungi("chiusura", rif=x.rif, prezzo=x.prezzo, prezzo_contro=x.prezzo_contro, motivo=x.motivo, data=x.data)
    elif x.cmd == "nota":
        r = aggiungi("nota", testo=x.testo, data=x.data)
    elif x.cmd == "verifica":
        print(verifica(leggi())[1])
        return
    else:
        import personale
        recs = leggi()
        tick = {r.get("ticker") for r in recs} | {r.get("contro") for r in recs} | {personale.BENCH}
        tick.discard(None)
        loc = personale.chiusure(tick)
        eur = personale.in_euro(loc, personale._valute(list(loc.columns)))
        print("\n".join(rapporto_md(recs, loc, eur, personale.BENCH)))
        return
    print(f"Registrata voce {r['id']} ({r['tipo']}).")


if __name__ == "__main__":
    main()
