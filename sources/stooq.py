"""Stooq CSV, senza chiave: seconda fonte prezzi per un controllo incrociato con Yahoo.
Solo azioni e ETF con borsa nota (USA, Milano, Xetra, Amsterdam, Parigi, Londra); gli indici si saltano."""
import csv
import io

from sources import common

URL = "https://stooq.com/q/d/l/?s={}&i=d"
SUFFISSI = {".MI": ".it", ".DE": ".de", ".AS": ".nl", ".PA": ".fr", ".L": ".uk"}
SOGLIA = 0.01   # scarto oltre l'1%: avviso


def simbolo(ticker):
    """Ticker Yahoo -> simbolo Stooq, o None se non mappabile."""
    if ticker.startswith("^") or "=" in ticker:
        return None
    for yh, sq in SUFFISSI.items():
        if ticker.endswith(yh):
            return ticker[: -len(yh)].lower() + sq
    if "." in ticker and "-" not in ticker:
        return None
    return ticker.replace("-", ".").lower() + ".us"


def parse(text):
    """CSV Stooq -> {data: chiusura}. Una risposta 'No data' dà {}."""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out[row["Date"][:10]] = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def chiusure(ticker, ttl=12 * 3600):
    s = simbolo(ticker)
    if not s:
        return {}
    def fetch():
        t = common.get(URL.format(s), timeout=20, tries=1).text
        px = parse(t)
        if not px:
            ULTIMO_ERRORE[0] = "risposta senza prezzi: " + " ".join(t.split())[:120]
            raise ValueError(ULTIMO_ERRORE[0])
        return px
    return common.cached(f"stooq:{s}", ttl, fetch)  # None se Stooq non ha risposto


ULTIMO_ERRORE = [""]


def scarto(yahoo_px, yahoo_data, stooq_px):
    """Scarto relativo tra le chiusure dello stesso giorno, o None se manca il dato Stooq."""
    v = stooq_px.get(yahoo_data)
    if not v or not yahoo_px:
        return None
    return yahoo_px / v - 1


def controlla(rows, massimo=25, tentativi=40, errori_max=3):
    """Confronta le ultime chiusure Yahoo con Stooq su al più `massimo` strumenti (al più `tentativi` richieste;
    si ferma dopo `errori_max` mancate risposte di fila). Restituisce (controllati, [(riga, scarto) oltre soglia])."""
    fatti, fuori, provati, errori = 0, [], 0, 0
    for r in rows:
        if fatti >= massimo or provati >= tentativi or errori >= errori_max:
            break
        if not simbolo(r["ticker"]):
            continue
        provati += 1
        try:
            px = chiusure(r["ticker"])
        except Exception:
            px = None
        if px is None:
            errori += 1
            continue
        errori = 0
        sc = scarto(r.get("prezzo"), r.get("data"), px)
        if sc is None:
            continue
        fatti += 1
        if abs(sc) > SOGLIA:
            fuori.append((r, sc))
    return fatti, fuori
