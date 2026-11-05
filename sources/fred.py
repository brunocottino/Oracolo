"""FRED (St. Louis Fed) via CSV pubblico, senza chiave né registrazione.
Serie: VIXCLS (VIX), VXVCLS (VIX a 3 mesi), DGS10 (Treasury 10 anni, %), DTB3 (T-bill 3 mesi, %).
I valori mancanti di FRED sono "." o vuoti e vengono saltati."""
import csv
import io

from sources import common

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
SERIE = {"VIXCLS": "VIX", "VXVCLS": "VIX a 3 mesi", "DGS10": "Treasury 10 anni", "DTB3": "T-bill 3 mesi"}


def parse(text):
    """CSV FRED -> {data: valore}. Accetta l'intestazione DATE o observation_date."""
    out = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or not row[0][:1].isdigit():
            continue
        try:
            out[row[0][:10]] = float(row[1])
        except ValueError:
            continue
    return out


def serie(sid, ttl=12 * 3600):
    """Storico completo della serie (dict data -> valore), con cache; {} se FRED non risponde."""
    return common.cached(f"fred:{sid}", ttl, lambda: parse(common.get(URL.format(sid), timeout=40, tries=1).text)) or {}


def ultimo(sid):
    """(data, valore) dell'ultima osservazione, o (None, None)."""
    s = serie(sid)
    if not s:
        return None, None
    d = max(s)
    return d, s[d]
