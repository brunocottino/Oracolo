"""Portafoglio personale: valore in EUR, utili/perdite, segnali sui titoli
posseduti e misure di rischio complessive (volatilità, VaR, concentrazione)."""
import math
import time

import numpy as np
import pandas as pd

import data
import db
from universe import name_of

ADVICE = {
    "COMPRA": "Segnale positivo: puoi incrementare (rispetta il peso suggerito).",
    "ACCUMULA SU DEBOLEZZA": "Mantieni; incrementa solo con ordine limite sul livello indicato.",
    "NESSUN SEGNALE": "Mantieni: nessun vantaggio statistico per cambiare.",
    "ALLEGGERISCI / VENDI": "Valuta di ridurre la posizione.",
}


def snapshot():
    rows = db.holdings_list()
    items, hist = [], {}
    fx_cache = {}
    for h in rows:
        t = h["ticker"]
        try:
            df, meta = data.get_history(t)
        except Exception as e:
            items.append({**h, "error": str(e)})
            continue
        cur = meta.get("currency") or "EUR"
        if cur not in fx_cache:
            fx_cache[cur] = data.fx_to_eur(cur)
        fx = fx_cache[cur]
        price = float(df["close"].iloc[-1])
        value = h["qty"] * price * fx
        cost = h["qty"] * h["avg_price"] * fx
        sig = db.signal_get(t)
        fresh = bool(sig and time.time() - sig["scan_ts"] < 3 * 86400)
        alerts = []
        if sig:
            pl = sig["plan"]
            stop_ref = h["avg_price"] - (pl["plan_market"]["entry"] - pl["plan_market"]["stop"])
            if price < stop_ref:
                alerts.append(f"Prezzo sotto lo stop teorico ({stop_ref:,.2f} = carico - 2,5 ATR): rivedi la posizione.")
            if price >= pl["quantiles"]["q90"] * 0.98 or (h["avg_price"] and price / h["avg_price"] - 1 > 0.25 and sig["plan"]["signal"] != "COMPRA"):
                alerts.append("Forte guadagno accumulato: valuta una presa di profitto parziale.")
        items.append({
            **h, "name": name_of(t) if name_of(t) != t else meta.get("name", t),
            "currency": cur, "fx": fx, "price": price, "value_eur": value, "cost_eur": cost,
            "pnl_eur": value - cost, "pnl_pct": (price / h["avg_price"] - 1) if h["avg_price"] else None,
            "signal": sig["plan"]["signal"] if sig else None,
            "p_up": sig["ensemble"]["p_up"] if sig else None,
            "exp_return": sig["ensemble"]["exp_return"] if sig else None,
            "signal_fresh": fresh, "advice": ADVICE.get(sig["plan"]["signal"]) if sig else
            "Segnale non ancora calcolato: premi 'Aggiorna segnali'.",
            "alerts": alerts, "demo": meta.get("demo", False),
        })
        hist[h["id"]] = df["adj"]
    total = sum(i.get("value_eur", 0) for i in items)
    for i in items:
        if "value_eur" in i:
            i["weight"] = i["value_eur"] / total if total else 0
            if i["weight"] > 0.20:
                i["alerts"].append(f"Concentrazione elevata: {i['weight']:.0%} del portafoglio.")
    return {"items": items, "total_eur": total,
            "cost_eur": sum(i.get("cost_eur", 0) for i in items),
            "pnl_eur": sum(i.get("pnl_eur", 0) for i in items),
            "risk": risk(items, hist, total)}


def risk(items, hist, total):
    valid = [i for i in items if i["id"] in hist and i.get("value_eur")]
    if len(valid) == 0 or total <= 0:
        return None
    rets = pd.DataFrame({i["id"]: np.log(hist[i["id"]].resample("W-FRI").last()).diff() for i in valid}).dropna().iloc[-104:]
    if len(rets) < 30:
        return None
    w = np.array([i["value_eur"] / total for i in valid])
    cov = rets.cov().values * 52
    vol = float(math.sqrt(w @ cov @ w))
    indiv = np.sqrt(np.diag(cov))
    div_ratio = float((w @ indiv) / vol) if vol else 1.0
    var_1m = float(1.645 * vol * math.sqrt(21 / 252) * total)
    corr = rets.corr().values
    pairs = []
    names = [i["ticker"] for i in valid]
    for a in range(len(valid)):
        for b in range(a + 1, len(valid)):
            if corr[a, b] > 0.75:
                pairs.append({"a": names[a], "b": names[b], "corr": float(corr[a, b])})
    hhi = float(np.sum(w ** 2))
    return {"vol_annual": vol, "var95_1m_eur": var_1m, "diversification_ratio": div_ratio,
            "effective_positions": 1 / hhi if hhi else 0, "high_corr_pairs": pairs,
            "note": "Rischio calcolato sui rendimenti settimanali in valuta locale degli ultimi 2 anni (escluso il rischio di cambio)."}
