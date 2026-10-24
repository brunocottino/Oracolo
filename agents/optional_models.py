"""Agenti opzionali da progetti open-source su GitHub.

Si attivano solo se la libreria è installata (vedi requirements-extra.txt):
  - Prophet  (github.com/facebook/prophet)              pip install prophet
  - Chronos  (github.com/amazon-science/chronos-forecasting)
             modello "foundation" pre-addestrato su milioni di serie storiche
             pip install chronos-forecasting torch
Se non sono installate restano spente senza errori.
"""
import math
import warnings

import numpy as np
import pandas as pd

from .base import Agent, horizon_sigma, shrunk_mu

try:
    from prophet import Prophet as _Prophet
    HAS_PROPHET = True
except Exception:
    HAS_PROPHET = False

try:
    import torch
    from chronos import ChronosPipeline
    HAS_CHRONOS = True
except Exception:
    HAS_CHRONOS = False


class ProphetAgent(Agent):
    name = "Prophet (Meta)"
    family = "statistico"
    source = "github.com/facebook/prophet"
    description = ("Modello di Meta per serie storiche con trend e stagionalità (settimanale e "
                   "annuale). Utile per titoli con cicli ricorrenti.")
    enabled = HAS_PROPHET
    backtestable = False

    def run(self, ctx):
        h = ctx["h"]
        dates = ctx["dates"][-756:]
        y = np.log(ctx["px"][-756:])
        df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": y})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = _Prophet(daily_seasonality=False, weekly_seasonality=False,
                         yearly_seasonality=True, interval_width=0.8,
                         changepoint_prior_scale=0.05)
            m.fit(df)
            fut = m.make_future_dataframe(periods=h, freq="B")
            fc = m.predict(fut).iloc[-1]
        sig_h, _ = horizon_sigma(ctx)
        raw = float(fc["yhat"] - y[-1])
        raw = float(np.clip(raw, -0.6 * sig_h, 0.6 * sig_h))
        mu = 0.5 * raw + 0.5 * shrunk_mu(ctx)
        sig = max((fc["yhat_upper"] - fc["yhat_lower"]) / (2 * 1.2816), sig_h * 0.7)
        return self.result(ctx, mu, sig, f"Trend + stagionalità indicano {raw:+.1%} sull'orizzonte.")


class ChronosAgent(Agent):
    name = "Chronos (Amazon, foundation model)"
    family = "foundation model"
    source = "github.com/amazon-science/chronos-forecasting"
    description = ("Modello di intelligenza artificiale pre-addestrato da Amazon su moltissime "
                   "serie storiche. Produce direttamente una distribuzione di scenari futuri.")
    enabled = HAS_CHRONOS
    backtestable = False
    _pipe = None

    def run(self, ctx):
        if ChronosAgent._pipe is None:
            ChronosAgent._pipe = ChronosPipeline.from_pretrained(
                "amazon/chronos-t5-small", device_map="cpu", torch_dtype=torch.float32)
        h = ctx["h"]
        ctxt = torch.tensor(np.asarray(ctx["px"][-512:], dtype=np.float32))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fc = ChronosAgent._pipe.predict(ctxt, prediction_length=h, num_samples=100)
        term = np.log(fc[0, :, -1].numpy() / ctx["px"][-1])
        sig_h, _ = horizon_sigma(ctx)
        mu = float(np.clip(np.median(term), -0.6 * sig_h, 0.6 * sig_h))
        sig = float(max(np.std(term), 0.7 * sig_h))
        res = self.result(ctx, mu, sig, f"Scenario mediano del modello {math.exp(mu) - 1:+.1%}; "
                                        f"in rialzo nel {(term > 0).mean():.0%} degli scenari generati.")
        res.p_up = float((term > 0).mean())
        return res
