"""Agente fondamentale in stile CFA: valore intrinseco e margine di sicurezza.

Metodi (curriculum CFA Equity Valuation):
  1. DCF a due stadi sul free cash flow per azione, scontato al costo
     dell'equity da CAPM (Ke = Rf + beta x ERP).
  2. Formula di Graham rivista: V = EPS x (8,5 + 2g) x 4,4 / Y
     (Y = rendimento obbligazioni AAA ~ Rf + 0,5%).
  3. Numero di Graham: sqrt(22,5 x EPS x valore contabile per azione).
Il valore equo è una media pesata (in scala logaritmica) delle stime valide.
Il prezzo obiettivo medio degli analisti NON entra nel valore equo (è un dato di
"classe B", solo di oggi, non verificabile sul passato): resta visibile come dato.
Scheda informativa: peso 0 nella previsione finché non viene validata.
"""
import math

import numpy as np

from .base import Agent, horizon_sigma, prior_mu


def two_stage_dcf(fcf, ke, g1, g2=0.025, years=5):
    if fcf is None or fcf <= 0 or ke <= g2 + 0.01:
        return None
    v, cf = 0.0, fcf
    for t in range(1, years + 1):
        cf *= 1 + g1
        v += cf / (1 + ke) ** t
    tv = cf * (1 + g2) / (ke - g2)
    return v + tv / (1 + ke) ** years


class Valuation(Agent):
    name = "Valutazione CFA (valore intrinseco)"
    family = "fondamentale"
    source = "CFA Institute – Equity Valuation (DCF, CAPM, Graham)"
    applies_to = "stock"
    backtestable = False
    description = ("Stima quanto vale l'azienda con i metodi del programma CFA: flussi di cassa "
                   "scontati (DCF) al costo del capitale da CAPM e formule di Graham. Scheda informativa "
                   "a peso 0: i bilanci sono dati di 'classe C' (andrebbero usati con 90 giorni di ritardo "
                   "per un test storico onesto) e la valutazione non è stata validata sul passato.")

    def applicable(self, ctx):
        return super().applicable(ctx) and bool(ctx.get("fund"))

    def run(self, ctx):
        f = ctx["fund"]
        p = float(ctx["px"][-1])
        rf = ctx["rf"]
        beta = ctx.get("beta") or 1.0
        beta = float(np.clip(beta, 0.5, 2.0))
        ke = max(rf + beta * ctx["erp"], 0.06)
        g_raw = f.get("earnings_growth")
        if g_raw is None:
            g_raw = f.get("revenue_growth")
        g1 = float(np.clip(g_raw if g_raw is not None else 0.05, -0.05, 0.15))
        est = {}
        dcf = two_stage_dcf(f.get("fcf_per_share"), ke, g1)
        if dcf:
            est["DCF 2 stadi"] = (dcf, 1.0)
        eps = f.get("eps_forward") or f.get("eps_trailing")
        if eps and eps > 0:
            y = (rf + 0.005) * 100
            est["Formula di Graham"] = (eps * (8.5 + 2 * g1 * 100) * 4.4 / y, 1.0)
            bv = f.get("book_value")
            if bv and bv > 0:
                est["Numero di Graham"] = (math.sqrt(22.5 * eps * bv), 0.5)
        tgt = f.get("target_mean")
        # scarta stime assurde (oltre 3 volte o sotto un terzo del prezzo)
        valid = {k: v for k, v in est.items() if p / 3 < v[0] < p * 3}
        sig_h, _ = horizon_sigma(ctx)
        base = prior_mu(ctx)
        if not valid:
            return self.result(ctx, base, sig_h, "Fondamentali insufficienti o incoerenti per una stima affidabile: neutrale.",
                               fair_value=None, estimates={k: v[0] for k, v in est.items()}, ke=ke)
        w = np.array([v[1] for v in valid.values()])
        lv = np.array([math.log(v[0]) for v in valid.values()])
        fair = float(math.exp(np.sum(w * lv) / w.sum()))
        gap = math.log(fair / p)
        kappa = 0.30                                    # velocità di chiusura dello sconto (annua)
        closed = 1 - math.exp(-kappa * ctx["h"] / 252)
        mu = base + gap * closed
        mos = fair / p - 1
        verdict = ("sottovalutato" if mos > 0.15 else "leggermente sottovalutato" if mos > 0.05 else
                   "sopravvalutato" if mos < -0.15 else "leggermente sopravvalutato" if mos < -0.05 else
                   "correttamente valutato")
        dett = "; ".join(f"{k} {v[0]:,.2f}" for k, v in valid.items())
        return self.result(ctx, mu, sig_h,
                           f"Valore equo stimato {fair:,.2f} contro prezzo {p:,.2f}: titolo {verdict} "
                           f"({mos:+.0%}). Costo del capitale (CAPM) {ke:.1%}, crescita usata {g1:.0%}. "
                           f"Stime: {dett}."
                           + (f" Prezzo obiettivo medio degli analisti {tgt:,.2f} (solo come dato, non entra nel valore equo)."
                              if tgt else ""),
                           fair_value=fair, margin=mos, ke=ke, g=g1, target_mean=tgt,
                           estimates={k: v[0] for k, v in valid.items()},
                           entry_value=fair * 0.85)
