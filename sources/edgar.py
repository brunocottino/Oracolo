"""SEC EDGAR (gratuito, solo un User-Agent): somiglianza del testo di ogni bilancio con il
precedente dello stesso tipo, "lazy prices" (Cohen-Malloy-Nguyen 2020). Le società che
cambiano molto il linguaggio dei bilanci rendono meno nei mesi successivi.

10-K e 20-F (ADR, mercati emergenti) contro l'anno prima; 10-Q contro lo stesso trimestre
dell'anno prima. Si salva solo la somiglianza, mai il testo."""
import html
import math
import re
from collections import Counter

from .common import cached, get

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBM_URL = "https://data.sec.gov/submissions/{name}"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
FORMS = ("10-K", "10-Q", "20-F")
FIRST_YEAR = 2009   # prima del 2009 molti depositi sono in testo semplice o incompleti
GAP = 0.15          # SEC: massimo 10 richieste al secondo

# Società che hanno cambiato entità legale: lo storico sta sotto CIK precedenti
CIK_PAST = {"XOM": [34088], "GOOGL": [1288776], "AVGO": [1441634, 1649338]}

_RE_HIDDEN = re.compile(r"<(script|style|ix:header)[^>]*>.*?</\1>", re.S | re.I)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WORD = re.compile(r"[a-z]{3,}")


def cik_of(ticker):
    t = ticker.upper()
    if "." in t and not t.endswith(".US"):
        return None   # solo titoli quotati negli USA (comprese le ADR)
    m = cached("sec:tickers", 7 * 86400, lambda: {v["ticker"]: v["cik_str"]
                                                    for v in get(TICKERS_URL, GAP).json().values()})
    return (m or {}).get(t)


def words(text) -> Counter:
    text = _RE_HIDDEN.sub(" ", text)
    text = html.unescape(_RE_TAG.sub(" ", text)).lower()
    return Counter(_RE_WORD.findall(text))


def cosine(a: Counter, b: Counter) -> float:
    """Coseno sui pesi log(1 + conteggio): le parole frequentissime non dominano."""
    if not a or not b:
        return float("nan")
    la = {k: math.log1p(v) for k, v in a.items()}
    lb = {k: math.log1p(v) for k, v in b.items()}
    dot = sum(v * lb.get(k, 0.0) for k, v in la.items())
    na = math.sqrt(sum(v * v for v in la.values()))
    nb = math.sqrt(sum(v * v for v in lb.values()))
    return dot / (na * nb)


def filings_list(cik):
    """[(data deposito, tipo, numero accesso, documento)] dei bilanci, dal più vecchio."""
    js = get(SUBM_URL.format(name=f"CIK{cik:010d}.json"), GAP).json()
    blocks = [js["filings"]["recent"]]
    for f in js["filings"].get("files", []):
        blocks.append(get(SUBM_URL.format(name=f["name"]), GAP).json())
    out = []
    for b in blocks:
        for i, form in enumerate(b["form"]):
            if form in FORMS and int(b["filingDate"][i][:4]) >= FIRST_YEAR and b["primaryDocument"][i]:
                out.append((b["filingDate"][i], form, b["accessionNumber"][i], b["primaryDocument"][i]))
    return sorted(set(out))


def similarities(filings, fetch_words):
    """Per ogni bilancio la somiglianza con il comparabile precedente.
    fetch_words(filing) -> Counter. 10-Q: il terzo 10-Q precedente (stesso trimestre, anno prima)."""
    out, hist = [], {"10-K": [], "10-Q": [], "20-F": []}
    for fl in filings:
        d, form = fl[0], fl[1]
        try:
            w = fetch_words(fl)
        except Exception:
            continue
        past = hist[form]
        ref = past[-3] if form == "10-Q" and len(past) >= 3 else (past[-1] if form != "10-Q" and past else None)
        if ref is not None:
            out.append({"date": d, "form": form, "sim": round(cosine(w, ref), 5)})
        past.append(w)
        if len(past) > 3:
            past.pop(0)
    return out


def lazy_prices(ticker):
    cik = cik_of(ticker)
    if not cik:
        return None

    def fetch():
        fl = []
        for c in CIK_PAST.get(ticker.upper(), []) + [cik]:
            fl += [(*f, c) for f in filings_list(c)]
        fl.sort()

        def fw(f):
            url = DOC_URL.format(cik=f[4], acc=f[2].replace("-", ""), doc=f[3])
            return words(get(url, GAP, timeout=60).text)
        out = similarities(fl, fw)
        if len(fl) >= 4 and not out:
            raise RuntimeError("nessun documento scaricato")   # errore di rete: non va in cache
        return out

    return cached(f"lazy2:{ticker.upper()}", 7 * 86400, fetch)
