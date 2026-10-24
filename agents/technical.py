"""Agenti tecnico-quantitativi: Momentum, Mean Reversion, Regimi di mercato."""
import math

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from .base import Agent, horizon_sigma, shrunk_mu


def rsi(px, n=14):
    d = np.diff(px)
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return float((100 - 100 / (1 + rs)).fillna(50).iloc[-1])


# ---------------------------------------------------------------------------
class Momentum(Agent):
    name = "Momentum e trend"
    family = "tecnico"
    source = "Moskowitz-Ooi-Pedersen (2012), Jegadeesh-Titman (1993)"
    description = ("Il 'momentum' è uno dei fattori più documentati in finanza: ciò che è salito "
                   "negli ultimi 12 mesi (escluso l'ultimo) tende a continuare per qualche mese. "
                   "L'agente combina 4 misure: rendimento 12-1 mesi, rendimento 3 mesi, incrocio "
                   "medie mobili 50/200 e posizione rispetto alla media a 200 giorni.")

    def run(self, ctx):
        px = ctx["px"]
        sig_h, sig_d = horizon_sigma(ctx)
        vol_a = sig_d * math.sqrt(252)
        r12_1 = math.log(px[-22] / px[-253])
        r3 = math.log(px[-1] / px[-64])
        sma50, sma200 = px[-50:].mean(), px[-200:].mean()
        parts = {
            "12-1 mesi": math.tanh(r12_1 / vol_a),
            "3 mesi": math.tanh(r3 / (vol_a * math.sqrt(63 / 252))),
            "media 50/200": 1.0 if sma50 > sma200 else -1.0,
            "prezzo vs media 200": 1.0 if px[-1] > sma200 else -1.0,
        }
        score = float(np.mean(list(parts.values())))
        # premio storico del momentum: Sharpe ~0,4 annuo per segnale pieno
        edge = 0.4 * score * vol_a * ctx["h"] / 252
        mu = shrunk_mu(ctx) + edge
        pos = [k for k, v in parts.items() if v > 0]
        lab = "forte rialzo" if score > 0.5 else "rialzo" if score > 0.1 else \
              "forte ribasso" if score < -0.5 else "ribasso" if score < -0.1 else "neutro"
        return self.result(ctx, mu, sig_h,
                           f"Punteggio trend {score:+.2f} su scala da -1 a +1 ({lab}). "
                           f"Rendimento 12-1 mesi {math.exp(r12_1) - 1:+.0%}, 3 mesi {math.exp(r3) - 1:+.0%}. "
                           f"Segnali positivi: {', '.join(pos) if pos else 'nessuno'}.",
                           score=score, parts=parts)


# ---------------------------------------------------------------------------
class MeanReversion(Agent):
    name = "Mean reversion (ritorno alla media)"
    family = "tecnico"
    source = "Processo di Ornstein-Uhlenbeck, Bande di Bollinger, RSI di Wilder"
    description = ("Misura quanto il prezzo si è allontanato dalla sua media a 100 giorni e con "
                   "che velocità storicamente ci ritorna (emivita, stimata con un processo di "
                   "Ornstein-Uhlenbeck). Aggiunge RSI e Bande di Bollinger per gli eccessi di breve.")

    def run(self, ctx):
        px = ctx["px"]
        h = ctx["h"]
        sig_h, _ = horizon_sigma(ctx)
        lp = np.log(px[-756:])
        sma = pd.Series(lp).rolling(100).mean().values
        x = (lp - sma)[~np.isnan(sma)]
        x0, x1 = x[:-1], x[1:]
        phi = float(np.polyfit(x0, x1, 1)[0])
        rs = rsi(px[-300:])
        m20, s20 = px[-20:].mean(), px[-20:].std()
        z = float((px[-1] - m20) / s20) if s20 > 0 else 0.0
        dev = float(x[-1])
        if 0 < phi < 1:
            half = -math.log(2) / math.log(phi)
            exp_change = dev * (phi ** h - 1)
        else:
            half = float("inf")
            exp_change = 0.0
        reliable = half < 3 * h
        rev = exp_change * 0.5 if reliable else 0.0
        # eccessi di breve (RSI estremo) aggiungono un piccolo effetto contrarian
        if rs > 75:
            rev -= 0.1 * sig_h
        elif rs < 25:
            rev += 0.1 * sig_h
        rev = float(np.clip(rev, -0.5 * sig_h, 0.5 * sig_h))
        mu = shrunk_mu(ctx) + rev
        state = ("molto sopra" if dev > 0.08 else "sopra" if dev > 0.02 else
                 "molto sotto" if dev < -0.08 else "sotto" if dev < -0.02 else "in linea con")
        hl_txt = f"{half:.0f} sedute" if math.isfinite(half) else "non stimabile"
        return self.result(ctx, mu, sig_h,
                           f"Prezzo {state} la media a 100 giorni ({dev:+.1%}). Emivita del ritorno "
                           f"alla media {hl_txt}{'' if reliable else ' (troppo lenta, effetto ignorato)'}. "
                           f"RSI {rs:.0f}, z-score Bollinger {z:+.1f}.",
                           deviation=dev, half_life=half, rsi=rs, z20=z)


# ---------------------------------------------------------------------------
class Regimes(Agent):
    name = "Regimi di mercato"
    family = "machine learning"
    source = "Gaussian Mixture (scikit-learn), approccio tipo Hidden Markov"
    description = ("Classifica ogni periodo storico in 3 'regimi' (es. rialzo tranquillo, "
                   "laterale, turbolenza) in base a rendimento e volatilità del mese. Poi guarda "
                   "cosa è successo in passato dopo giornate nello stesso regime di oggi.")

    def run(self, ctx):
        px = ctx["px"]
        h = ctx["h"]
        s = pd.Series(px)
        lr = np.log(s)
        ret21 = lr.diff(21)
        vol21 = lr.diff().rolling(21).std() * math.sqrt(252)
        fwd = lr.shift(-h) - lr
        df = pd.DataFrame({"ret": ret21, "vol": vol21, "fwd": fwd}).dropna(subset=["ret", "vol"])
        X = df[["ret", "vol"]].values
        mu_x, sd_x = X.mean(0), X.std(0)
        Xs = (X - mu_x) / sd_x
        gm = GaussianMixture(3, covariance_type="full", random_state=0, n_init=2).fit(Xs)
        lab = gm.predict(Xs)
        df["reg"] = lab
        cur = int(lab[-1])
        known = df.dropna(subset=["fwd"])
        same = known[known["reg"] == cur]["fwd"]
        sig_h, _ = horizon_sigma(ctx)
        base = shrunk_mu(ctx)
        n = len(same)
        if n > 30:
            diff = float(same.mean() - known["fwd"].mean())
            k = n / (n + 250)                  # più osservazioni = più fiducia
            mu = base + k * diff
            sig = float(np.sqrt(0.5 * same.std() ** 2 + 0.5 * sig_h ** 2))
            hist_up = float((same > 0).mean())
        else:
            mu, sig, hist_up, diff = base, sig_h, None, 0.0
        c = (gm.means_[cur] * sd_x + mu_x)
        if c[1] > np.median(df["vol"]) * 1.3:
            name = "turbolento"
        elif c[0] > 0.01:
            name = "rialzo tranquillo"
        elif c[0] < -0.01:
            name = "debolezza"
        else:
            name = "laterale"
        days_in = int((lab[::-1] == cur).argmin()) if (lab != cur).any() else len(lab)
        note = (f"Regime attuale: {name} (da {days_in} sedute). "
                + (f"In passato, dopo questo regime, il prezzo è salito nel {hist_up:.0%} dei casi "
                   f"({n} osservazioni)." if hist_up is not None else "Poche osservazioni storiche: neutrale."))
        return self.result(ctx, mu, sig, note, regime=name, n=n, hist_up=hist_up)
