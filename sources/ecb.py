"""BCE Data Portal (API SDMX in CSV), senza chiave né registrazione.
€STR e rendimento a 10 anni dei titoli di Stato AAA dell'area euro: tasso privo di rischio per i titoli europei."""
import csv
import io

from sources import common

BASE = "https://data-api.ecb.europa.eu/service/data/{}?format=csvdata&lastNObservations={}"
SERIE = {
    "estr": ("EST/B.EU000A2X2A25.WT", "€STR"),
    "euro10y": ("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "Titoli di Stato AAA area euro 10 anni"),
}


def parse(text):
    """CSV SDMX della BCE -> {data: valore} dalle colonne TIME_PERIOD e OBS_VALUE."""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            out[row["TIME_PERIOD"][:10]] = float(row["OBS_VALUE"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def serie(nome, n=400, ttl=12 * 3600):
    key = SERIE[nome][0]
    return common.cached(f"ecb:{nome}:{n}", ttl, lambda: parse(common.get(BASE.format(key, n), timeout=40, tries=1).text)) or {}


def ultimo(nome):
    s = serie(nome, n=5)
    if not s:
        return None, None
    d = max(s)
    return d, s[d]
