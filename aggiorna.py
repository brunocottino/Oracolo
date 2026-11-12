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
# Stooq dal 2026 risponde ai download automatici con una pagina anti-robot: controllo spento (sources/stooq.py resta)
STOOQ_ATTIVO = False


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


def _v(x, d=2, suf=""):
    return "n.d." if x is None else f"{x:.{d}f}".replace(".", ",") + suf


def mercati():
    """Volatilità e tassi da FRED e BCE (fonti gratuite senza chiave). Ogni fonte che non risponde dà n.d."""
    m, giu = {}, set()
    for k, mod, sid in (("vix", "fred", "VIXCLS"), ("vix3m", "fred", "VXVCLS"), ("us10y", "fred", "DGS10"),
                        ("us3m", "fred", "DTB3"), ("estr", "ecb", "estr"), ("euro10y", "ecb", "euro10y")):
        d, v = None, None
        if mod not in giu:
            try:
                from sources import ecb, fred
                d, v = (fred if mod == "fred" else ecb).ultimo(sid)
            except Exception:
                pass
            if v is None:
                giu.add(mod)  # fonte giù: non riprovo le altre serie
        m[k] = v
        m[k + "_data"] = d
    return m


def semaforo(rows, m):
    """Regola fissa e dichiarata prima: rosso se almeno 3 indici/ETF azionari sono a livello 4-5 o il VIX supera
    il VIX3M (struttura a termine invertita); giallo se almeno uno è a livello 4-5, metà sono a livello 3 o il VIX
    supera 20; altrimenti verde. Descrive il mercato, non dà ordini."""
    liv = [r["livello"] for r in rows if r.get("livello")]
    n45, n3 = sum(1 for l in liv if l >= 4), sum(1 for l in liv if l == 3)
    vix, vix3m = m.get("vix"), m.get("vix3m")
    if n45 >= 3 or (vix and vix3m and vix > vix3m):
        return "🔴 Rosso: panico diffuso", n45, n3, len(liv)
    if n45 >= 1 or (liv and n3 * 2 >= len(liv)) or (vix and vix > 20):
        return "🟡 Giallo: tensione", n45, n3, len(liv)
    return "🟢 Verde: mercati calmi", n45, n3, len(liv)


def cruscotto(rows, livelli, m, controllo):
    """Schermata da 10 secondi: semaforo, 3 avvisi, tassi e volatilità."""
    luce, n45, n3, tot = semaforo(rows, m)
    lv = {l["livello"]: l for l in livelli}
    avvisi = []
    panico = sorted((r for r in rows if (r.get("livello") or 0) >= 4), key=lambda r: -r["livello"])
    if panico:
        avvisi.append("In panico: " + ", ".join(
            f"{r['breve']} `{r['ticker']}` livello {r['livello']} (in passato {_p(lv.get(r['livello'], {}).get('rend'))}"
            f" a 1 mese, {(lv.get(r['livello'], {}).get('rialzo') or 0) * 100:.0f}% rialzi)" for r in panico[:3]) + ".")
    else:
        avvisi.append(f"Nessun indice o ETF azionario in panico; {n3} su {tot} in tensione (livello 3).")
    iper = sorted((r for r in rows if r.get("avviso")), key=lambda r: -r["rsi"])
    if iper:
        avvisi.append(f"{len(iper)} ipercomprati (RSI sopra 70); i più tirati: "
                      + ", ".join(f"{r['breve']} {r['rsi']:.0f}" for r in iper[:3]) + ".")
    fatti, fuori = controllo
    if fuori:
        avvisi.append("Prezzi da verificare (scarto con Stooq oltre l'1%): "
                      + ", ".join(f"{r['breve']} {_p(sc)}" for r, sc in fuori[:3]) + ".")
    elif fatti:
        avvisi.append(f"Prezzi Yahoo confermati da Stooq su {fatti} strumenti (scarto entro l'1%).")
    else:
        vicini = sorted((r for r in rows if r.get("livello") and r.get("stop") and r.get("prezzo")),
                        key=lambda r: r["prezzo"] / r["stop"] - 1)
        if vicini:
            avvisi.append("Più vicini allo stop (indici ed ETF): " + ", ".join(
                f"{r['breve']} {_p(r['prezzo'] / r['stop'] - 1)} sopra" for r in vicini[:3]) + ".")
    tassi = (f"VIX {_v(m.get('vix'), 1)} (a 3 mesi {_v(m.get('vix3m'), 1)}) · Treasury 10 anni {_v(m.get('us10y'), 2, '%')} · "
             f"T-bill 3 mesi {_v(m.get('us3m'), 2, '%')} · €STR {_v(m.get('estr'), 3, '%')} · Stato AAA euro 10 anni "
             f"{_v(m.get('euro10y'), 2, '%')}")
    tassi = tassi.rstrip(".")
    righe = [f"## {luce}", ""] + [f"{i}. {a}" for i, a in enumerate(avvisi, 1)] + [
        "", f"Volatilità e tassi: {tassi}. _Fonti: FRED e BCE, ultimo dato disponibile._", ""]
    from sources import common as sc_common
    for fonte, err in sc_common.ERRORI.items():
        log(f"fonte {fonte} non raggiungibile: {err}")
    info = {"fonti_errori": dict(sc_common.ERRORI), "semaforo": luce, "avvisi": avvisi, "mercati": m, "stooq_controllati": fatti, "stooq_fuori": len(fuori)}
    return righe, info


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
           "Si aggiorna da sola dal lunedì al venerdì.", ""]
    controllo = (0, [])
    if STOOQ_ATTIVO:
        from sources import stooq
        campione = sorted(rows, key=lambda r: (r["livello"] is None, r["ticker"]))
        try:
            controllo = stooq.controlla(campione)
        except Exception:
            pass
    righe, info = cruscotto(rows, livelli, mercati(), controllo)
    out += righe
    st.update(info)
    json.dump(st, open(os.path.join(OUT, "stato.json"), "w", encoding="utf-8"), ensure_ascii=False)
    out += ["## Indici ed ETF azionari per livello", "",
           "Livello: " + " · ".join(f"**{l['livello']} {l['nome']}** {_p(l['rend'])} a 1 mese, {l['rialzo'] * 100:.0f}% rialzi"
                                   for l in livelli),
           "", "_Verifica del 12/11/2026: sul campione completo dal 1993 (crollo del 2008 compreso) il vantaggio del panico "
           "sul rendimento normale non è significativo (+0,1%, t 0,1). I numeri qui sopra descrivono il passato, "
           "non sono un segnale di acquisto._", "", head]
    out += [_riga(r) for r in sorted((r for r in rows if r["livello"]), key=lambda r: (-r["livello"], r["breve"]))]
    iper = sorted((r for r in rows if r["avviso"]), key=lambda r: -r["rsi"])
    out += ["", f"## Ipercomprati ({len(iper)}): RSI 14 sopra 70, meglio aspettare prima di comprare", "", head]
    out += [_riga(r) for r in iper]
    out += ["", "## Tutti gli strumenti", ""]
    for g in sorted({r["gruppo"] for r in rows}):
        rs = sorted((r for r in rows if r["gruppo"] == g), key=lambda r: r["breve"])
        out += [f"<details><summary>{g} ({len(rs)})</summary>", "", head] + [_riga(r) for r in rs] + ["", "</details>", ""]
    out += ["", "_Uso personale, non è una raccomandazione di investimento. La forchetta 80% indica dove il prezzo "
                "resta 8 volte su 10, non la direzione. Prezzi Yahoo Finance; tassi FRED e BCE._", ""]
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
