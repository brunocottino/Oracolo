"""Visite giornaliere alle pagine Wikipedia (API REST Wikimedia, gratuita, dal 1° luglio 2015).
Misura l'attenzione degli investitori nella lingua del mercato di casa."""
import urllib.parse
from datetime import date

import pandas as pd

from universe import WIKI

from .common import cached, get

API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/"
       "all-access/user/{art}/daily/20150701/{end}")


def parse(js) -> dict:
    """Risposta dell'API -> {"AAAA-MM-GG": visite}."""
    out = {}
    for it in js.get("items", []):
        ts = it["timestamp"]
        out[f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"] = int(it["views"])
    return out


def pageviews(ticker) -> pd.Series | None:
    m = WIKI.get(ticker.upper())
    if not m:
        return None
    lang, art = m
    end = date.today().strftime("%Y%m%d")

    def fetch():
        url = API.format(lang=lang, art=urllib.parse.quote(art, safe=""), end=end)
        return parse(get(url, host_gap=1.0).json())

    d = cached(f"wiki:{lang}:{art}", 86400, fetch)
    if not d:
        return None
    s = pd.Series(d, dtype=float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()
