"""Aggiornamento automatico di Oracolo, senza Claude e senza servizi esterni.

Lancio:  python aggiorna.py            fotografia di oggi (forchetta, livelli 1-5, RSI) in data/oracolo/
         python aggiorna.py --lab      anche il Laboratorio rapido (lo fa da solo se l'ultimo ha più di 7 giorni)
         python aggiorna.py --oggi     solo fotografia, più la pagina OGGI.md (GitHub Actions, oracolo-giornaliero.yml)
Lo lancia il pianificatore del computer (installa_aggiornamento_windows.bat / setup_mac.sh) o GitHub Actions.
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


def _p(x, d=1):
    return "—" if x is None else f"{x * 100:+.{d}f}%".replace(".", ",")


def _n(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _riga(r):
    return (f"| {r['breve']} `{r['ticker']}` | {r['livello'] or '—'} | {_n(r['prezzo'])} {r.get('valuta', '')} | "
            f"{_p(r['chg1'])} | {_p(r['lo45'], 0)} / {_p(r['hi45'], 0)} | {r['vol'] * 100:.0f}% | {_p(r['dd'], 0)} | "
            f"{r['rsi']:.0f} | {_n(r['stop'])} |")


def scrivi_oggi(path=os.path.join(ROOT, "OGGI.md")):
    """Pagina leggibile da telefono su github.com: livelli 1-5, ipercomprati, tutti gli strumenti per gruppo."""
    rows = json.load(open(os.path.join(OUT, "forchetta.json"), encoding="utf-8"))
    livelli = json.load(open(os.path.join(OUT, "livelli.json"), encoding="utf-8"))
    st = stato()
    head = ("| Strumento | Liv. | Prezzo | Giorno | Forchetta 45 gg | Vol. | Dal max | RSI | Stop |\n"
            "|---|---|---|---|---|---|---|---|---|")
    quando = datetime.fromisoformat(st["aggiornato"]).strftime("%d/%m/%Y %H:%M UTC")
    out = [f"# Oracolo: fotografia del {quando}", "",
           f"{len(rows)} strumenti · {st['panico']} in panico (livello 4-5) · {st['ipercomprati']} ipercomprati. "
           "Si aggiorna da sola dal lunedì al venerdì.", "",
           "## Indici ed ETF azionari per livello", "",
           "Livello: " + " · ".join(f"**{l['livello']} {l['nome']}** {_p(l['rend'])} a 1 mese, {l['rialzo'] * 100:.0f}% rialzi"
                                   for l in livelli), "", head]
    out += [_riga(r) for r in sorted((r for r in rows if r["livello"]), key=lambda r: (-r["livello"], r["breve"]))]
    iper = sorted((r for r in rows if r["avviso"]), key=lambda r: -r["rsi"])
    out += ["", f"## Ipercomprati ({len(iper)}): RSI 14 sopra 70, meglio aspettare prima di comprare", "", head]
    out += [_riga(r) for r in iper]
    out += ["", "## Tutti gli strumenti", ""]
    for g in sorted({r["gruppo"] for r in rows}):
        rs = sorted((r for r in rows if r["gruppo"] == g), key=lambda r: r["breve"])
        out += [f"<details><summary>{g} ({len(rs)})</summary>", "", head] + [_riga(r) for r in rs] + ["", "</details>", ""]
    out += ["", "_Uso personale, non è una raccomandazione di investimento. La forchetta 80% indica dove il prezzo "
                "resta 8 volte su 10, non la direzione. Prezzi Yahoo Finance._", ""]
    open(path, "w", encoding="utf-8").write("\n".join(out))


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
    if "--oggi" in argv:
        if ok:
            scrivi_oggi()
        return 0 if ok else 1
    if ok and ("--lab" in argv or laboratorio_dovuto()):
        try:
            laboratorio()
            log("Laboratorio rapido ok")
        except Exception as e:
            log(f"Laboratorio NON aggiornato: {str(e)[:200]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
