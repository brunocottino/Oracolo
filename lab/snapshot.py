"""Fotografia di oggi per la pagina Oracolo: forchetta, rischio, RSI, livello Oracolo 1-5.

Lancio:  python -m lab.snapshot <cartella di uscita>
Scrive forchetta.json (una riga per strumento) e livelli.json (statistiche storiche dei livelli, PREREG_SCORE.md).
"""
import io
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import requests

import bands
import config
import data
import engine
from universe import INDICES, MARKETS, name_of

from .panic_test import panic_score
from .rsi_test import rsi

SECT = {"Information Technology": "Tecnologia", "Health Care": "Salute", "Financials": "Finanziari",
        "Industrials": "Industriali", "Consumer Discretionary": "Consumi discrezionali",
        "Consumer Staples": "Consumi di base", "Energy": "Energia", "Utilities": "Utilities",
        "Materials": "Materiali", "Communication Services": "Comunicazioni", "Real Estate": "Immobiliare"}
# Statistiche storiche per livello (29 indici, 1993-2026, 1 mese): PREREG_SCORE.md
LIVELLI = [
    {"livello": 5, "nome": "Panico forte", "rend": 0.0377, "rialzo": 0.66, "casi": 166},
    {"livello": 4, "nome": "Panico", "rend": 0.0267, "rialzo": 0.67, "casi": 331},
    {"livello": 3, "nome": "Tensione", "rend": 0.0095, "rialzo": 0.61, "casi": 2007},
    {"livello": 2, "nome": "Normale", "rend": 0.0031, "rialzo": 0.57, "casi": 3309},
    {"livello": 1, "nome": "Euforia", "rend": 0.0053, "rialzo": 0.59, "casi": 476},
]
LEVEL_GROUPS = ("Indici", "ETF azionari per area")


def etf_group(cat):
    c = cat.lower()
    if c.startswith("settore"):
        return "ETF settori"
    if c.startswith("fattore"):
        return "ETF fattori"
    if any(k in c for k in ("obbligazioni", "titoli di stato", "monetario")):
        return "ETF obbligazioni e liquidità"
    if any(k in c for k in ("oro", "materie", "immobiliare")):
        return "ETF oro, materie prime, immobili"
    return "ETF azionari per area"


def instruments():
    out = [(t, "Indici", n, "") for t, n in INDICES.items()]
    for mkt, d in MARKETS.items():
        for t, n in d.items():
            if mkt == "ETF UCITS" and " · " in n:
                cat, prod = n.split(" · ", 1)
                short = cat.replace("Settore ", "").replace("Fattore ", "")
                out.append((t, etf_group(n), short[:1].upper() + short[1:], prod))
            else:
                out.append((t, {"Asia/Emergenti": "Asia ed emergenti"}.get(mkt, mkt), n, ""))
    have = {x[0] for x in out}
    r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", timeout=30,
                     headers={"User-Agent": "Oracolo/1.0 (https://github.com/brunocottino/Oracolo)"})
    sp = pd.read_html(io.StringIO(r.text))[0]
    for s, n, g in zip(sp["Symbol"], sp["Security"], sp["GICS Sector"]):
        t = s.replace(".", "-")
        if t not in have:
            out.append((t, "S&P 500 · " + SECT.get(g, g), n, ""))
    return out


def row(t, grp, breve, prod):
    df, meta = data.get_history(t)
    kind = "etf" if (t in INDICES or t in MARKETS["ETF UCITS"]) else "azioni"
    f = bands.forchetta(df, kind)
    stop = f["price"] - config.SIGNAL_RULES["atr_stop_mult"] * engine.atr(df)
    px = df["adj"].astype(float)
    r14 = float(rsi(px.to_frame(t), 14).iloc[-1, 0])
    out = {"ticker": t, "breve": breve, "prodotto": prod, "gruppo": grp, "valuta": meta.get("currency", ""),
           "data": str(df.index[-1].date()), "prezzo": round(f["price"], 4), "mov45": round(f["move_45"], 4),
           "vol": round(bands.sigma_daily(np.diff(np.log(px.values))) * math.sqrt(252), 4),
           "dd": round(float(px.iloc[-1] / px.iloc[-252:].max() - 1), 4), "stop": round(stop, 4),
           "peso": None if t in INDICES else round(bands.risk_size(f["price"], stop) or 0, 4),
           "rsi": round(r14, 1), "livello": None, "avviso": ""}
    for lab, k in (("45 giorni", "45"), ("90 giorni", "90")):
        b = f["bands"][lab]
        out.update({"lo" + k: round(b["low_pct"], 4), "mid" + k: round(b["mid_pct"], 4), "hi" + k: round(b["high_pct"], 4)})
    if grp in LEVEL_GROUPS:
        v = panic_score(px.to_frame(t)).iloc[-1, 0]
        if v == v:
            out["livello"] = int(v) + 2 if not (v == 0 and r14 > 70) else 1
    elif not grp.startswith("ETF") and r14 > 70:
        out["avviso"] = "Ipercomprato: meglio aspettare qualche giorno prima di comprare"
    return out


def main(outdir):
    rows = []
    for t, grp, breve, prod in instruments():
        try:
            rows.append(row(t, grp, breve, prod))
        except Exception as e:
            print("salto", t, str(e)[:60], file=sys.stderr)
    os.makedirs(outdir, exist_ok=True)
    json.dump(rows, open(os.path.join(outdir, "forchetta.json"), "w"), ensure_ascii=False)
    json.dump(LIVELLI, open(os.path.join(outdir, "livelli.json"), "w"), ensure_ascii=False)
    lv = pd.Series([r["livello"] for r in rows if r["livello"]]).value_counts().to_dict()
    print(len(rows), "strumenti; livelli:", lv, "; ipercomprati:", sum(1 for r in rows if r["avviso"]),
          "; date:", pd.Series([r["data"] for r in rows]).value_counts().head(3).to_dict())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "snapshot")
