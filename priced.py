"""Cosa c'è già nel prezzo.

1. Probabilità di rialzo implicita nelle opzioni. Non si usa Breeden-Litzenberger
   (troppo rumoroso sui dati Yahoo) ma la probabilità "digitale" di Black-Scholes
   corretta per lo skew:
        P(S_T > S0) ≈ N(d2) - vega_digitale · dσ/dK
   con IV ATM interpolata alla scadenza più vicina a 45 giorni (91 per gli indici)
   e skew = pendenza della IV tra gli strike al 90% e al 110%.
   La probabilità "neutrale al rischio" diventa "reale" sostituendo il tasso privo
   di rischio con il rendimento atteso CAPM (rf + beta x premio al rischio).
   Mossa attesa = IV x radice(h / 252).
   Senza opzioni (titoli .MI e molti europei/asiatici) il "mercato" diventa
   media storica + CAPM, e la fonte viene dichiarata.
2. Reverse DCF: quale crescita annua del free cash flow per azione nei prossimi
   5 anni giustifica il prezzo di oggi (Ke = rf + beta x ERP, crescita terminale 2,5%).
   Confronto con la crescita di consenso e con la frequenza storica (base rate) di
   aziende che hanno davvero sostenuto quella crescita.
3. Volatilità implicita contro la nostra previsione; per gli indici USA il VIX.
"""
import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

import config
import data

# Quota di aziende che hanno sostenuto una crescita annua composta >= g per 5 anni.
# APPROSSIMAZIONE costruita sulla distribuzione della crescita delle vendite a 5 anni
# delle aziende USA in M. Mauboussin, D. Callahan, "The Base Rate Book" (Credit Suisse, 2016).
# Per utili e free cash flow la dispersione è maggiore: va letta come ordine di grandezza.
BASE_RATE_GROWTH = [(-0.10, 0.93), (-0.05, 0.86), (0.00, 0.73), (0.05, 0.52), (0.10, 0.31),
                    (0.15, 0.17), (0.20, 0.09), (0.25, 0.05), (0.30, 0.03), (0.40, 0.012), (0.50, 0.005)]
BASE_RATE_NOTE = ("Approssimazione da Mauboussin-Callahan, The Base Rate Book (2016), crescita delle vendite "
                  "a 5 anni delle aziende USA; per il free cash flow la dispersione è maggiore.")
G_TERMINAL = 0.025


def base_rate_share(g):
    xs = [a for a, _ in BASE_RATE_GROWTH]
    ys = [b for _, b in BASE_RATE_GROWTH]
    return float(np.interp(g, xs, ys))


def two_stage_dcf(fcf, ke, g1, g2=G_TERMINAL, years=5):
    if fcf is None or fcf <= 0 or ke <= g2 + 0.005:
        return None
    v, cf = 0.0, fcf
    for t in range(1, years + 1):
        cf *= 1 + g1
        v += cf / (1 + ke) ** t
    tv = cf * (1 + g2) / (ke - g2)
    return v + tv / (1 + ke) ** years


def implied_growth(price, fcf, ke):
    """Crescita annua del FCF per azione (5 anni) che eguaglia il prezzo (brentq)."""
    if not price or not fcf or fcf <= 0:
        return None
    fn = lambda g: two_stage_dcf(fcf, ke, g) - price
    lo, hi = -0.5, 1.5
    try:
        if fn(lo) > 0 or fn(hi) < 0:
            return None
        return float(brentq(fn, lo, hi, xtol=1e-6))
    except Exception:
        return None


# --------------------------------------------------------------------------
def options_summary(opt, target_days=45):
    """IV ATM e pendenza dello skew alla scadenza `target_days` (interpolazione in varianza totale)."""
    exps = [e for e in (opt or {}).get("expiries", []) if e.get("atm_iv") and e.get("days", 0) > 0]
    if not exps:
        return None
    exps.sort(key=lambda e: e["days"])
    days = np.array([e["days"] for e in exps], float)
    w = np.array([e["atm_iv"] ** 2 * e["days"] for e in exps])
    sk = np.array([((e.get("iv110") or e["atm_iv"]) - (e.get("iv90") or e["atm_iv"])) / 0.2 for e in exps])
    if target_days <= days[0]:
        iv, s, used = exps[0]["atm_iv"], sk[0], days[0]
    elif target_days >= days[-1]:
        iv, s, used = exps[-1]["atm_iv"], sk[-1], days[-1]
    else:
        wt = float(np.interp(target_days, days, w))
        iv = math.sqrt(wt / target_days)
        s = float(np.interp(target_days, days, sk))
        used = target_days
    return {"iv": float(iv), "dsig_dk_rel": float(s), "skew_slope": float(s), "days": float(used),
            "source": opt.get("source", "opzioni")}


def digital_prob(iv, dsig_dk_rel, h, rf, beta, erp=None):
    """Probabilità che il prezzo tra h sedute sia sopra quello di oggi.
    p_rn: neutrale al rischio; p_real: con il rendimento atteso CAPM al posto di rf."""
    erp = config.EQUITY_RISK_PREMIUM if erp is None else erp
    T = h / 252
    sT = iv * math.sqrt(T)

    def p_for(mu):
        d2 = (mu - 0.5 * iv * iv) * T / sT
        d1 = d2 + sT
        # dσ/dK con K = S0: vega_digitale = e^{muT} * S * sqrt(T) * phi(d1) / S
        p = norm.cdf(d2) - math.exp(mu * T) * math.sqrt(T) * norm.pdf(d1) * dsig_dk_rel
        return float(np.clip(p, 0.01, 0.99))
    mu_real = rf + beta * erp
    return {"p_rn": p_for(rf), "p_real": p_for(mu_real), "move": sT, "drift": mu_real}


def hist_capm_prob(px, h, rf, beta, sigma_h):
    """Senza opzioni: media tra frequenza storica dei rialzi a h sedute e probabilità CAPM."""
    lp = np.log(np.asarray(px, float))
    fwd = lp[h:] - lp[:-h]
    freq = float(np.mean(fwd > 0)) if len(fwd) else 0.5
    mu = (rf + beta * config.EQUITY_RISK_PREMIUM) * h / 252 - 0.5 * sigma_h ** 2
    p_capm = float(norm.cdf(mu / sigma_h)) if sigma_h > 0 else 0.5
    return 0.5 * freq + 0.5 * p_capm, freq, p_capm


def market_view(ticker, df, fund, is_idx, h, beta, rf, sigma_h, vix=None, vix3m=None):
    """Quadro di 'cosa prezza il mercato' per un titolo o un indice."""
    T = h / 252
    target_days = 91 if is_idx else 45
    b = float(np.clip(beta if beta is not None else 1.0, 0.3, 2.5))
    out = {"horizon_days": h, "calendar_days": target_days}
    opt = None
    try:
        opt = data.get_options(ticker)
    except Exception:
        opt = None
    summ = options_summary(opt, target_days) if opt else None
    iv, src = None, None
    skew = summ["dsig_dk_rel"] if summ else 0.0
    if is_idx and ticker in data.US_INDICES and (vix3m is not None or vix is not None):
        v = vix3m if (vix3m is not None and h > 40) else vix
        iv = float(v) / 100.0
        src = ("VIX3M (volatilità implicita a 3 mesi dell'S&P 500)" if v is vix3m else
               "VIX (volatilità implicita a 30 giorni)")
        if summ:
            src += f" + skew dalle opzioni ({summ['source']})"
    elif summ:
        iv = summ["iv"]
        src = f"opzioni: IV ATM a {summ['days']:.0f} giorni e skew 90-110% ({summ['source']})"
    if iv:
        pr = digital_prob(iv, skew, h, rf, b)
        out.update(p_market=pr["p_real"], p_rn=pr["p_rn"], move=pr["move"], iv=iv, skew=skew,
                   source=src, from_options=True)
    else:
        p, freq, pc = hist_capm_prob(df["adj"].values, h, rf, b, sigma_h)
        out.update(p_market=p, p_rn=None, move=sigma_h, iv=None, skew=None, hist_freq=freq, p_capm=pc,
                   source="nessuna opzione quotata disponibile: media tra frequenza storica dei rialzi e CAPM",
                   from_options=False)
    out["sigma_ours_ann"] = sigma_h / math.sqrt(T)
    out["iv_vs_ours"] = (out["iv"] / out["sigma_ours_ann"] - 1) if out.get("iv") else None
    # Reverse DCF
    if not is_idx and fund:
        price = float(df["close"].iloc[-1])
        ke = max(rf + float(np.clip(b, 0.5, 2.0)) * config.EQUITY_RISK_PREMIUM, 0.06)
        g = implied_growth(price, fund.get("fcf_per_share"), ke)
        cons = fund.get("earnings_growth")
        out["rdcf"] = {"g_implied": g, "ke": ke, "g_terminal": G_TERMINAL, "fcf_ps": fund.get("fcf_per_share"),
                       "g_consensus": cons, "base_rate": base_rate_share(g) if g is not None else None,
                       "note": BASE_RATE_NOTE,
                       "why_missing": None if g is not None else
                       ("free cash flow non disponibile o negativo" if not fund.get("fcf_per_share") or
                        fund.get("fcf_per_share") <= 0 else "nessuna crescita in [-50%, +150%] giustifica il prezzo")}
    # Regime VIX per gli indici USA
    if is_idx and ticker in data.US_INDICES and vix is not None:
        try:
            hist = data.get_history("^VIX")[0]["close"].values
            pct = float(np.mean(hist <= vix))
        except Exception:
            pct = None
        ratio = (vix / vix3m) if vix3m else None
        out["vix"] = {"level": vix, "pct": pct, "vix3m": vix3m, "ratio": ratio,
                      "regime": ("stress (VIX sopra VIX3M)" if ratio and ratio > 1 else
                                 "calma (VIX sotto VIX3M)" if ratio else "n.d.")}
    return out
