"""Agente machine learning: Gradient Boosting con validazione walk-forward.

Ispirato ai modelli 'alpha' di Microsoft Qlib (github.com/microsoft/qlib), in
versione leggera: impara dal passato del titolo il legame tra indicatori
(momentum, volatilità, RSI, distanza dai massimi) e il rendimento successivo.
La sua voce nel consenso viene ridotta a zero se, nei test sul passato,
non ha mostrato capacità predittiva.
"""
import math
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor

from .base import Agent, horizon_sigma, shrunk_mu


def features(px: pd.Series) -> pd.DataFrame:
    lp = np.log(px)
    r = lp.diff()
    f = pd.DataFrame(index=px.index)
    for n in (5, 21, 63, 126, 252):
        f[f"ret{n}"] = lp.diff(n)
    f["vol21"] = r.rolling(21).std()
    f["vol63"] = r.rolling(63).std()
    f["volratio"] = f["vol21"] / f["vol63"]
    f["dist50"] = lp - lp.rolling(50).mean()
    f["dist200"] = lp - lp.rolling(200).mean()
    f["dd252"] = lp - lp.rolling(252).max()
    d = px.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return f


class GradientBoost(Agent):
    name = "Gradient Boosting (ML)"
    family = "machine learning"
    source = "scikit-learn; impostazione tipo Microsoft Qlib"
    description = ("Un modello di machine learning (alberi decisionali in sequenza) addestrato "
                   "sullo storico del titolo. Viene messo alla prova sul passato con un test "
                   "'walk-forward' (impara fino a una data, prevede dopo). Se il test non mostra "
                   "capacità predittiva, la sua opinione viene azzerata.")
    backtestable = False   # ha già una sua validazione interna

    def run(self, ctx):
        h = ctx["h"]
        px = pd.Series(ctx["px"])
        f = features(px)
        y = np.log(px).shift(-h) - np.log(px)
        data = f.join(y.rename("y")).replace([np.inf, -np.inf], np.nan)
        X_now = data.drop(columns="y").iloc[[-1]]
        train = data.dropna().iloc[::3]           # un campione ogni 3 sedute (meno sovrapposizione)
        sig_h, _ = horizon_sigma(ctx)
        base = shrunk_mu(ctx)
        if len(train) < 200 or X_now.isna().any(axis=None):
            return self.result(ctx, base, sig_h, "Storico insufficiente per addestrare il modello: neutrale.")

        Xa, ya = train.drop(columns="y").values, train["y"].values
        gap = math.ceil(h / 3)
        folds = 4
        n = len(Xa)
        start = int(n * 0.5)
        preds, reals = [], []
        model = lambda: GradientBoostingRegressor(n_estimators=120, max_depth=2, learning_rate=0.03,
                                                  subsample=0.7, min_samples_leaf=20, random_state=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            edges = np.linspace(start, n, folds + 1).astype(int)
            for i in range(folds):
                tr_end = edges[i] - gap
                te = slice(edges[i], edges[i + 1])
                m = model().fit(Xa[:tr_end], ya[:tr_end])
                preds.append(m.predict(Xa[te]))
                reals.append(ya[te])
            p_oos, r_oos = np.concatenate(preds), np.concatenate(reals)
            ic = float(spearmanr(p_oos, r_oos).statistic) if len(p_oos) > 10 else 0.0
            if not math.isfinite(ic):
                ic = 0.0
            hit = float(np.mean(np.sign(p_oos - np.median(ya)) == np.sign(r_oos - np.median(ya))))
            final = model().fit(Xa, ya)
            pred = float(final.predict(X_now.values)[0])
        shrink = float(np.clip(ic / 0.10, 0, 1))
        edge = float(np.clip(shrink * (pred - ya.mean()), -0.6 * sig_h, 0.6 * sig_h))
        mu = base + edge
        resid = r_oos - p_oos
        sig = float(np.sqrt(0.5 * np.var(resid) + 0.5 * sig_h ** 2))
        qual = "buona" if ic > 0.08 else "debole" if ic > 0.02 else "assente"
        res = self.result(ctx, mu, sig,
                          f"Capacità predittiva nei test sul passato: {qual} (correlazione di rango "
                          f"{ic:+.2f}, direzione giusta nel {hit:.0%} dei casi). Peso dato al modello "
                          f"{shrink:.0%}. Contributo alla previsione {edge:+.1%}.",
                          ic=ic, hit=hit, shrink=shrink)
        res.skill, res.skill_n = hit, len(p_oos)
        return res
