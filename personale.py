"""Parte personale di Oracolo: portafoglio reale, certificati, avvisi, diario.

Legge e scrive SOLO nella cartella privato/ (esclusa da Git: il repository è pubblico).
    python personale.py            aggiorna tutto e scrive privato/OGGI_PRIVATO.md
Lo lancia anche aggiorna.py sul PC, se la cartella privato/ esiste. Esempi dei file: esempi/privato/.
Uso personale, mai consigli per clienti.
"""
import json
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
PRIV = os.environ.get("ORACOLO_PRIVATO", os.path.join(ROOT, "privato"))
BENCH = "ACWI"  # iShares MSCI ACWI (USD), convertito in euro


def leggi(nome, default=None):
    try:
        with open(os.path.join(PRIV, nome), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def scrivi(nome, obj):
    os.makedirs(PRIV, exist_ok=True)
    with open(os.path.join(PRIV, nome), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


# ---------------------------------------------------------------- prezzi in euro
def _valute(tickers):
    """Valuta di quotazione di ogni ticker (cache in privato/valute.json)."""
    import yfinance as yf
    cache = leggi("valute.json", {}) or {}
    for t in tickers:
        if t not in cache:
            try:
                cache[t] = yf.Ticker(t).fast_info["currency"]
            except Exception:
                cache[t] = None
    scrivi("valute.json", cache)
    return cache


def in_euro(chiusure, valute):
    """Converte un DataFrame di chiusure (colonne = ticker) in euro. GBp/GBX sono pence."""
    import yfinance as yf
    out = chiusure.copy()
    serve = {("GBP" if v in ("GBp", "GBX") else v) for v in valute.values() if v and v != "EUR"}
    fx = {}
    if serve:
        f = yf.download([f"EUR{c}=X" for c in sorted(serve)], start=chiusure.index.min() - pd.Timedelta(days=10),
                        auto_adjust=False, progress=False)["Close"]
        if isinstance(f, pd.Series):
            f = f.to_frame(f"EUR{next(iter(serve))}=X")
        f = f.reindex(f.index.union(chiusure.index)).ffill().reindex(chiusure.index)
        fx = {c: f[f"EUR{c}=X"] for c in serve if f"EUR{c}=X" in f}
    for t in out.columns:
        v = valute.get(t)
        if not v or v == "EUR":
            continue
        k = "GBP" if v in ("GBp", "GBX") else v
        if k not in fx:
            out[t] = float("nan")
            continue
        out[t] = out[t] / (100.0 if v in ("GBp", "GBX") else 1.0) / fx[k]
    return out


def chiusure(tickers, start="2025-01-01", euro=False):
    import yfinance as yf
    tickers = sorted(set(t for t in tickers if t))
    if not tickers:
        return pd.DataFrame()
    c = yf.download(tickers, start=start, auto_adjust=False, progress=False)["Close"]
    if isinstance(c, pd.Series):
        c = c.to_frame(tickers[0])
    c = c.ffill(limit=5)
    return in_euro(c, _valute(tickers)) if euro else c


# ---------------------------------------------------------------- portafoglio
def portafoglio(prezzi, rete=True):
    from sources import certificati as sc
    p = leggi("portafoglio.json")
    if not p:
        return None
    righe = []
    for x in p["posizioni"]:
        s = prezzi.get(x.get("ticker"))
        px = float(s.dropna().iloc[-1]) if s is not None and not s.dropna().empty else None
        if px is None and rete and x.get("isin") and not x.get("per_cento"):
            px = sc.prezzo_borsa_italiana(x["isin"])
        stimato = px is None
        px = x["prezzo_rif"] if px is None else px
        mult = x["quantita"] / 100 if x.get("per_cento") else x["quantita"]
        righe.append({"nome": x["nome"], "tema": x["tema"], "valore": px * mult, "valore_rif": x["prezzo_rif"] * mult,
                      "carico": x["carico"] * mult, "stimato": stimato})
    return {"righe": righe, "liquidita": p.get("liquidita", 0), "data_estratto": p.get("data_estratto")}


# ---------------------------------------------------------------- certificati
def certificati(oggi_chiusure=None, rete=True):
    from sources import certificati as sc
    elenco = (leggi("certificati.json") or {}).get("certificati", [])
    if not elenco:
        return None
    termini = leggi("certificati_termini.json", {}) or {}
    out = []
    for c in elenco:
        isin = c["isin"]
        info = sc.scheda(isin) if rete else None
        t = dict(termini.get(isin, {}))
        if rete and info and info.get("archivio") and not t.get("letti"):
            try:
                for u in sc.documenti(info["archivio"]):
                    t.update(sc.termini_da_testo(isin, sc.pdf_testo(u)))
                    if t.get("fissazione"):
                        break
            except Exception as e:
                t["errore"] = str(e)[:120]
            t["letti"] = True
            termini[isin] = t
        t.update(c.get("termini", {}))
        out.append({"c": c, "info": info or {}, "termini": t})
    scrivi("certificati_termini.json", termini)
    servono = {s for x in out for s in x["termini"].get("sottostanti", [])}
    ch = chiusure(servono, start="2025-01-01") if servono else pd.DataFrame()
    risultati = []
    for x in out:
        c, info, t = x["c"], x["info"], x["termini"]
        prezzo = info.get("prezzo")
        r = {"isin": c["isin"], "nome": c["nome"], "descrizione": info.get("descrizione"), "scadenza": info.get("scadenza"),
             "prezzo": prezzo, "quantita": c["quantita"], "carico": c["carico"],
             "valore": prezzo * c["quantita"] if prezzo else None, "valore_carico": c["carico"] * c["quantita"]}
        if t.get("fissazione") and t.get("sottostanti") and t.get("trigger"):
            st = sc.stato_da_livelli(t, {k: ch[k] for k in t["sottostanti"] if k in ch})
            if st:
                r.update({"metodo": "livelli", "peggiore": st["ticker"], "perf": st["perf"],
                          "dist_trigger": st["dist_trigger"], "dist_barriera": st["dist_barriera"],
                          "paga": st["paga"], "giudizio": "paga" if st["paga"] else "non paga",
                          "trigger_assunto": t.get("trigger_assunto", False)})
        if "metodo" not in r:
            st = sc.stato_da_prezzo(prezzo, c.get("nominale"))
            r.update({"metodo": "prezzo", **(st or {"giudizio": "senza dati"})})
        risultati.append(r)
    return risultati


# ---------------------------------------------------------------- avvisi
def valuta_avvisi(regole, prezzi):
    """Regole sulle chiusure. prezzi: {ticker: Series}. Restituisce l'elenco delle regole scattate."""
    scattati = []
    for a in regole:
        s = prezzi.get(a["ticker"])
        if s is None or s.dropna().empty:
            continue
        x = float(s.dropna().iloc[-1])
        if "contro" in a:
            c = prezzi.get(a["contro"])
            if c is None or c.dropna().empty:
                continue
            rel = (x / a["base"] - 1) - (float(c.dropna().iloc[-1]) / a["base_contro"] - 1)
            if "sotto_rel" in a and rel <= a["sotto_rel"]:
                scattati.append({**a, "valore": rel})
            if "sopra_rel" in a and rel >= a["sopra_rel"]:
                scattati.append({**a, "valore": rel})
            continue
        if "sotto" in a and x <= a["sotto"]:
            scattati.append({**a, "valore": x})
        if "sopra" in a and x >= a["sopra"]:
            scattati.append({**a, "valore": x})
    return scattati


# ---------------------------------------------------------------- pagina privata
def _e(x):
    return "—" if x is None else f"{x:,.0f} €".replace(",", ".")


def _p(x, d=1):
    return "—" if x is None else f"{x * 100:+.{d}f}%".replace(".", ",")


def esegui(rete=True):
    import diario
    t0 = datetime.now(timezone.utc)
    reg = (leggi("avvisi.json") or {}).get("avvisi", [])
    port = leggi("portafoglio.json") or {"posizioni": []}
    dia = diario.leggi()
    tick = {x.get("ticker") for x in port["posizioni"]} | {a["ticker"] for a in reg} | {a.get("contro") for a in reg}
    tick |= {r.get("ticker") for r in dia} | {r.get("contro") for r in dia} | {BENCH}
    tick.discard(None)
    pr_loc = chiusure(tick) if rete else pd.DataFrame()
    pr_eur = in_euro(pr_loc, _valute(list(pr_loc.columns))) if rete else pd.DataFrame()
    righe = [f"# Oracolo personale: {t0:%d/%m/%Y %H:%M} UTC", "",
             "_Privato: questo file resta nella cartella privato/ e non va mai su GitHub._", ""]

    scattati = valuta_avvisi(reg, {k: pr_loc[k] for k in pr_loc})
    cert = certificati(rete=rete)
    allarmi = [f"**{a['nome']}**: ora {a['valore'] * 100:+.1f}%" if "contro" in a else f"**{a['nome']}**: ultimo prezzo {a['valore']:.2f}"
               for a in scattati]
    if cert:
        for r in cert:
            if r.get("metodo") == "livelli" and r["paga"] and r["dist_trigger"] < 0.05:
                allarmi.append(f"**{r['nome']}**: cedola a rischio, {r['peggiore']} solo {_p(r['dist_trigger'])} sopra il livello")
    righe += ["## Avvisi", ""] + ([f"- {a}" for a in allarmi] or ["- Nessun livello scattato."]) + [""]

    pf = portafoglio({k: pr_eur[k] for k in pr_eur}, rete) if rete else None
    if pf:
        tot = sum(r["valore"] for r in pf["righe"])
        tot_rif = sum(r["valore_rif"] for r in pf["righe"])
        temi = {}
        for r in pf["righe"]:
            temi[r["tema"]] = temi.get(r["tema"], 0) + r["valore"]
        cv = sum(r["valore"] or 0 for r in (cert or []))
        if cv:
            temi["Certificati"] = cv
        totale = sum(temi.values()) + pf["liquidita"]
        righe += ["## Portafoglio", "",
                  f"Azioni, ETF e obbligazioni: **{_e(tot)}** ({_p(tot / tot_rif - 1)} dall'estratto del {pf['data_estratto']}). "
                  f"Certificati: **{_e(cv)}**. Liquidità all'estratto: {_e(pf['liquidita'])}. Totale circa **{_e(totale)}**.", "",
                  "| Tema | Valore | Peso |", "|---|---|---|"]
        righe += [f"| {k} | {_e(v)} | {v / totale * 100:.0f}% |" for k, v in sorted(temi.items(), key=lambda kv: -kv[1])]
        stimati = [r["nome"] for r in pf["righe"] if r["stimato"]]
        if stimati:
            righe += ["", f"_Senza prezzo aggiornato (valore dell'estratto): {', '.join(stimati)}._"]
        righe += [""]

    if cert:
        righe += ["## Certificati", "", "| Certificato | Prezzo | Valore | Stato | Peggiore | Margine sulla cedola | Scadenza |",
                  "|---|---|---|---|---|---|---|"]
        ordine = sorted(cert, key=lambda r: (r.get("metodo") != "livelli", r.get("dist_trigger", 9)))
        for r in ordine:
            if r.get("metodo") == "livelli":
                stato = ("✅ paga" if r["paga"] else "❌ non paga") + (" (livello assunto)" if r.get("trigger_assunto") else "")
                righe.append(f"| {r['nome']} `{r['isin']}` | {r['prezzo'] or '—'} | {_e(r['valore'])} | {stato} | {r['peggiore']} "
                             f"({_p(r['perf'], 0)}) | {_p(r['dist_trigger'])} | {r['scadenza'] or '—'} |")
            else:
                righe.append(f"| {r['nome']} `{r['isin']}` | {r['prezzo'] or '—'} | {_e(r['valore'])} | ⚠️ {r['giudizio']} (stima dal prezzo"
                             f"{', ' + format(r['prezzo_pct'] * 100, '.0f') + '% del nominale' if r.get('prezzo_pct') else ''}) | — | — | {r['scadenza'] or '—'} |")
        n = sum(1 for r in cert if r.get("paga") is True), sum(1 for r in cert if r.get("paga") is False)
        righe += ["", f"Con i livelli dai documenti: {n[0]} pagano, {n[1]} no. Gli altri sono stime dal prezzo del certificato.", ""]

    if dia:
        ok, msg = diario.verifica(dia)
        righe += ["## Diario", "", ("Catena integra: nessuna voce modificata." if ok else f"⚠️ {msg}"), ""]
        righe += diario.rapporto_md(dia, pr_loc, pr_eur, BENCH) + [""]

    righe += ["_Uso personale, non è una raccomandazione di investimento._", ""]
    with open(os.path.join(PRIV, "OGGI_PRIVATO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(righe))
    stato = {"aggiornato": t0.isoformat(timespec="minutes"), "avvisi": allarmi,
             "certificati": len(cert or []), "diario": len(dia)}
    scrivi("stato_privato.json", stato)
    return f"{len(allarmi)} avvisi, {len(cert or [])} certificati, {len(dia)} voci di diario"


if __name__ == "__main__":
    print(esegui())
