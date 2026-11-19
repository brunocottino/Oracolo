"""Certificati quotati in Italia: dati gratuiti, senza registrazione.

- Scheda Borsa Italiana (EuroTLX o SeDeX): prezzo, descrizione, sottostanti, scadenza, documenti.
- Condizioni definitive (PDF "Official listing documentation" su Borsa Italiana): data di fissazione,
  barriera, livello della cedola (trigger), codici Bloomberg dei sottostanti.
- Prezzi dei sottostanti: Yahoo (data.py / yfinance).

I termini non cambiano: si leggono una volta e si tengono in cache (privato/certificati_termini.json).
Se il documento non c'è (molti Vontobel SeDeX) lo stato si stima dal prezzo del certificato.
"""
import html as _html
import os
import re
import subprocess
import tempfile

import requests

BI = "https://www.borsaitaliana.it"
UA = {"User-Agent": "Mozilla/5.0"}
SCHEDE = (("EuroTLX", "/borsa/cw-e-certificates/eurotlx/scheda/{isin}.html?lang=it"),
          ("SeDeX", "/borsa/cw-e-certificates/scheda/{isin}.html?lang=it"))

# Suffissi Yahoo per i codici borsa Bloomberg più comuni
BBG = {"UQ": "", "UW": "", "UN": "", "US": "", "UR": "", "UA": "", "IM": ".MI", "FP": ".PA", "GY": ".DE",
       "GR": ".DE", "NA": ".AS", "SM": ".MC", "SQ": ".MC", "LN": ".L", "DC": ".CO", "SW": ".SW", "SE": ".SW",
       "AV": ".VI", "BB": ".BR", "HK": ".HK", "JT": ".T", "SS": ".ST", "FH": ".HE", "NO": ".OL", "ID": ".IR"}
MESI = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                    "september", "october", "november", "december"), 1)}


def numero(s):
    """'1.022,78' -> 1022.78; restituisce None se non è un numero."""
    if s is None:
        return None
    s = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _get(url, timeout=30):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r


def testo_html(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    righe = (x.strip() for x in _html.unescape(re.sub(r"<[^>]+>", "\n", h)).split("\n"))
    return " | ".join(x for x in righe if x)


def leggi_scheda(isin, h):
    """Estrae i campi utili dal testo di una scheda Borsa Italiana."""
    s = testo_html(h)

    def campo(k):
        m = re.search(re.escape(k) + r" \| ([^|]+)", s)
        return m.group(1).strip() if m else None

    ultimo, rif = numero(campo("Prezzo ultimo contratto")), numero(campo("Prezzo di riferimento"))
    pdf = sorted(set(re.findall(r'href="([^"]*official-listing-documentation/archivio[^"]*)"', h)))
    return {"isin": isin, "prezzo": ultimo if ultimo is not None else rif, "prezzo_rif": rif,
            "descrizione": campo("Descrizione"), "sottostante": campo("Sottostante"),
            "scadenza": campo("Data di scadenza"), "emittente": campo("Emittente"), "archivio": pdf}


def scheda(isin, get=_get):
    """Scheda del certificato: prova EuroTLX, poi SeDeX. None se non è quotato su nessuno dei due."""
    for mercato, path in SCHEDE:
        try:
            h = get(BI + path.format(isin=isin)).text
        except Exception:
            continue
        if isin in h and ("Dati Completi" in h or "scheda completa" in h):
            d = leggi_scheda(isin, h)
            d["mercato"] = mercato
            return d
    return None


def documenti(archivio_urls, get=_get):
    """Link ai PDF delle condizioni definitive, dalle pagine di archivio della scheda."""
    out = []
    for u in archivio_urls[:2]:
        try:
            a = get(BI + _html.unescape(u) if u.startswith("/") else _html.unescape(u)).text
        except Exception:
            continue
        out += re.findall(r'href="(/secder-listing/[^"]+\.pdf)"', a)
    return sorted(set(out))


def pdf_testo(url, get=_get):
    """Testo di un PDF: pdftotext se c'è (più fedele), altrimenti pypdf."""
    with tempfile.TemporaryDirectory() as d:
        fn = os.path.join(d, "doc.pdf")
        with open(fn, "wb") as f:
            f.write(get(BI + url if url.startswith("/") else url, timeout=120).content)
        try:
            r = subprocess.run(["pdftotext", "-layout", fn, "-"], capture_output=True, timeout=300)
            if r.returncode == 0 and r.stdout:
                return r.stdout.decode("utf-8", "ignore")
        except Exception:
            pass
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(fn).pages)


def bbg_a_yahoo(code):
    """'MSTR UQ' -> 'MSTR'; 'STLAM IM' -> 'STLAM.MI'; 'NOVOB DC' -> 'NOVO-B.CO'. None se la borsa non è nota."""
    parti = code.split()
    if len(parti) != 2 or parti[1] not in BBG:
        return None
    sym, ex = parti
    if ex == "DC" and len(sym) > 4 and sym.endswith("B"):
        sym = sym[:-1] + "-B"
    if ex == "LN" and sym.endswith("/"):
        sym = sym[:-1]
    return sym + BBG[ex]


def _data(s):
    s = s.strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m and m.group(2).lower() in MESI:
        return f"{m.group(3)}-{MESI[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def _codici_colonna(tabella):
    """Codici Bloomberg dalla tabella dei sottostanti (testo impaginato di pdftotext).
    Il codice sta subito prima dell'ISIN del sottostante; se la borsa è andata a capo, si cerca sotto."""
    ex = "|".join(BBG)
    righe = tabella.split("\n")
    out = []
    for k, l in enumerate(righe):
        if not re.match(r"\s*\d+\s{2,}\S", l):
            continue
        m = re.search(r"\s([A-Z][A-Z0-9/]{0,7})(?: (%s))?\s+[A-Z]{2}\d[0-9A-Z]{4,}" % ex, l)
        if not m:
            return []
        sym, borsa = m.group(1), m.group(2)
        if not borsa:
            pos = m.start(1)
            for l2 in righe[k + 1:k + 3]:
                cand = [(abs(t.start() - pos), t.group(0)) for t in re.finditer(r"\b(?:%s)\b" % ex, l2)]
                cand = [c for c in cand if c[0] <= 12]
                if cand:
                    borsa = min(cand)[1]
                    break
        if not borsa:
            return []
        out.append(sym + " " + borsa)
    return out


def termini_da_testo(isin, testo):
    """Termini del certificato dalle condizioni definitive (formati Leonteq e Marex).
    Restituisce solo i campi trovati; i livelli sono in % del prezzo di fissazione."""
    righe = testo.split("\n")
    idx = [k for k, l in enumerate(righe) if isin in l]
    if not idx:
        return {}
    w = "\n".join(righe[idx[0]:idx[0] + 1200])
    out = {}
    m = re.search(r"Initial Fixing Date:?\s+In respect of each [A-Za-z ]+?,\s*(\d{1,2}/\d{1,2}/\d{4})", w)
    m = m or re.search(r"Strike Date:?\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", w)
    if m:
        out["fissazione"] = _data(m.group(1))
    m = re.search(r"(?<!Strike )Barrier Level:?\s+In respect of (?:each|the) Underlying[^,]*,\s*(\d+(?:\.\d+)?)\s*per\s*cent", w)
    m = m or re.search(r"Strike Level:?\s+In respect of (?:each|the) Underlying[^\n]*?(\d+(?:\.\d+)?)\s*per\s*cent", w, re.S)
    if m:
        out["barriera"] = float(m.group(1))
    tab = re.search(r"Underlying Table(.*?)\*Levels", w, re.S)
    if tab:
        perc = re.findall(r"\((\d+(?:\.\d+)?)%\)\*", tab.group(1))
        if "Coupon" in tab.group(1) and perc:
            out["trigger"] = float(perc[-1])  # la colonna del livello cedola è l'ultima della tabella
        codici = _codici_colonna(tab.group(1)) or re.findall(r"\b([A-Z0-9]{1,8} (?:%s))\b" % "|".join(BBG), tab.group(1))
        tick = [bbg_a_yahoo(c) for c in dict.fromkeys(codici)]
        if tick and all(tick):
            out["sottostanti"] = tick
    m = re.search(r"Coupon Barrier Level:?\s+In respect of each Underlying Asset[^,]*,\s*(\d+(?:\.\d+)?)\s*per\s*cent", w)
    if m:
        out["trigger"] = float(m.group(1))
    if "trigger" not in out and "barriera" in out:
        out["trigger"] = out["barriera"]
        out["trigger_assunto"] = True
    return out


def stato_da_livelli(termini, chiusure):
    """Distanze del sottostante peggiore. chiusure: {ticker: pandas.Series di chiusure con indice di date}."""
    peggiore = None
    for t in termini.get("sottostanti", []):
        s = chiusure.get(t)
        if s is None or s.dropna().empty:
            return None
        s = s.dropna()
        base = s[s.index <= termini["fissazione"]]
        if base.empty:
            return None
        p0, p1 = float(base.iloc[-1]), float(s.iloc[-1])
        perf = p1 / p0 - 1
        d_trig = 1 - termini["trigger"] / 100 * p0 / p1
        d_barr = 1 - termini.get("barriera", termini["trigger"]) / 100 * p0 / p1
        if peggiore is None or perf < peggiore["perf"]:
            peggiore = {"ticker": t, "perf": perf, "dist_trigger": d_trig, "dist_barriera": d_barr}
    if peggiore is None:
        return None
    peggiore["paga"] = peggiore["dist_trigger"] >= 0
    return peggiore


def stato_da_prezzo(prezzo, nominale):
    """Stima grezza quando mancano i termini: prezzo del certificato in % del nominale."""
    if not prezzo or not nominale:
        return None
    pct = prezzo / nominale
    giudizio = ("probabilmente paga" if pct >= 0.95 else "incerto" if pct >= 0.80 else "probabilmente non paga")
    return {"prezzo_pct": pct, "giudizio": giudizio}


def prezzo_borsa_italiana(isin, get=_get):
    """Prezzo di riferimento in euro di un ETF o ETC quotato a Milano (riserva quando Yahoo non ha il dato)."""
    for path in ("/borsa/etf/scheda/{isin}.html?lang=it", "/borsa/etc-etn/scheda/{isin}.html?lang=it"):
        try:
            h = get(BI + path.format(isin=isin)).text
        except Exception:
            continue
        if isin not in h:
            continue
        s = testo_html(h)
        for k in ("Prezzo ultimo contratto", "Prezzo di riferimento"):
            m = re.search(re.escape(k) + r" \| ([\d.,]+)", s)
            if m and numero(m.group(1)):
                return numero(m.group(1))
    return None
