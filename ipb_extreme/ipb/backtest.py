"""Backtest long/flat temporalmente coerente.

Ipotesi di esecuzione (documentate anche nell'export):
- il segnale è calcolato con i dati alla chiusura della seduta t;
- con execution_lag = 1 la posizione si apre alla chiusura di t e guadagna il rendimento
  close-to-close di t+1 (ordine "at the close"); con execution_lag = 2 si opera alla chiusura di t+1,
  ipotesi più prudente;
- costo = turnover (|variazione di posizione|, 1 = entrata o uscita completa) x cost_bps;
  l'ingresso iniziale paga il costo; niente tasse, finanziamento, impatto di mercato, dividendi
  (l'indice di prezzo li esclude: il buy & hold è sottostimato rispetto al total return);
- strategia e benchmark sono misurati sulla STESSA finestra: dalla prima data con segnale valido.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT, Settings

EXECUTION_NOTES = [
    "Segnale alla chiusura di t; posizione sul rendimento close-to-close successivo (execution_lag sedute).",
    "Costo per cambio di posizione in punti base sul nozionale; ingresso iniziale incluso.",
    "Esclusi tasse, finanziamento, impatto di mercato e dividendi (indice di prezzo).",
    "Strategia e benchmark valutati sulla stessa finestra temporale.",
    "Sharpe calcolato con tasso privo di rischio = 0.",
]


def metrics(returns: pd.Series, periods: int = 252) -> dict:
    r = returns.dropna()
    if len(r) < 2:
        return {"total_return": np.nan, "annualized_return": np.nan, "volatility": np.nan,
                "sharpe_rf0": np.nan, "max_drawdown": np.nan, "observations": len(r)}
    equity = (1 + r).cumprod()
    years = len(r) / periods
    sd = r.std(ddof=1)
    return {
        "total_return": float(equity.iloc[-1] - 1),
        "annualized_return": float(equity.iloc[-1] ** (1 / years) - 1) if equity.iloc[-1] > 0 else np.nan,
        "volatility": float(sd * np.sqrt(periods)),
        "sharpe_rf0": float(r.mean() * periods / (sd * np.sqrt(periods))) if sd > 0 else np.nan,
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
        "observations": len(r),
    }


def apply_position(signal: pd.Series, market_return: pd.Series, cost_bps: float, lag: int) -> pd.DataFrame:
    """signal[t] in [0, 1] noto alla chiusura di t -> posizione sul rendimento di t+lag."""
    if lag < 1:
        raise ValueError("execution_lag deve essere >= 1: un segnale di t non può guadagnare il rendimento di t")
    pos = signal.shift(lag).fillna(0.0).astype(float)
    turnover = pos.diff().abs()
    turnover.iloc[0] = abs(pos.iloc[0])
    ret = pos * market_return - turnover * cost_bps / 10000
    return pd.DataFrame({"position": pos, "turnover": turnover, "return": ret})


def strategy_signals(d: pd.DataFrame, ipb_long: float, use_probs: bool) -> pd.Series:
    sig = (d["ipb"] > ipb_long).astype(float)
    if use_probs:
        sig = sig * (d["p_up"] > d["p_down"]).astype(float)
    return sig.where(d["ipb"].notna())


def run_backtest(data: pd.DataFrame, cost_bps: float = DEFAULT.default_cost_bps,
                 settings: Settings = DEFAULT, ipb_long: float | None = None,
                 lag: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    ipb_long = settings.ipb_long if ipb_long is None else ipb_long
    lag = settings.execution_lag if lag is None else lag
    d = data.copy()
    if "ipb" not in d:
        raise ValueError("Manca la colonna ipb")
    d["market_return"] = d["close"].pct_change(fill_method=None)
    have_probs = {"p_up", "p_down"}.issubset(d.columns) and d[["p_up", "p_down"]].notna().any().all()

    strategies = {"IPB long/flat": strategy_signals(d, ipb_long, False)}
    if have_probs:
        strategies["IPB + probabilità calibrate"] = strategy_signals(d, ipb_long, True).where(d["p_up"].notna())
    ma = d["close"].rolling(100, min_periods=100).mean()
    strategies["Momentum MA100"] = (d["close"] > ma).astype(float).where(ma.notna())
    strategies["Buy & hold"] = pd.Series(1.0, index=d.index)

    # finestra comune: dalla prima data in cui TUTTI i segnali esistono
    starts = [s.first_valid_index() for s in strategies.values()]
    if any(s is None for s in starts):
        raise ValueError("Segnali insufficienti per il backtest")
    start = max(starts)
    w = d.index >= start
    rows, sub_rows = [], []
    for name, sig in strategies.items():
        res = apply_position(sig.fillna(0.0)[w], d["market_return"][w].fillna(0.0), cost_bps, lag)
        key = name.split(" ")[0].lower() if name != "Buy & hold" else "buy_hold"
        col = {"IPB long/flat": "strategy", "IPB + probabilità calibrate": "strategy_prob",
               "Momentum MA100": "momentum", "Buy & hold": "buy_hold"}.get(name, key)
        d.loc[w, f"{col}_position"] = res["position"]
        d.loc[w, f"{col}_return"] = res["return"]
        m = metrics(res["return"])
        m["avg_turnover_per_year"] = float(res["turnover"].sum() / max(len(res) / 252, 1e-9))
        m["time_in_market"] = float(res["position"].mean())
        rows.append({"strategy": name, **m})
        yrs = res.index.year
        for blk in np.unique((yrs - yrs.min()) // 3):
            s = ((yrs - yrs.min()) // 3) == blk
            mm = metrics(res["return"][s])
            sub_rows.append({"strategy": name, "from": str(res.index[s][0].date()),
                             "to": str(res.index[s][-1].date()),
                             "total_return": mm["total_return"], "sharpe_rf0": mm["sharpe_rf0"],
                             "max_drawdown": mm["max_drawdown"]})
    info = {"start": str(pd.Timestamp(start).date()), "end": str(d.index[-1].date()), "cost_bps": cost_bps,
            "execution_lag": lag, "ipb_long": ipb_long, "probabilities_used": bool(have_probs),
            "execution_notes": EXECUTION_NOTES, "subperiods": sub_rows}
    return d, pd.DataFrame(rows), info


def sensitivity(data: pd.DataFrame, settings: Settings = DEFAULT) -> pd.DataFrame:
    """Sensibilità del backtest a costi, soglia IPB e ritardo di esecuzione."""
    rows = []
    for c in settings.sensitivity_costs:
        for t in settings.sensitivity_ipb:
            for lag in settings.sensitivity_lags:
                _, m, info = run_backtest(data, cost_bps=c, settings=settings, ipb_long=t, lag=lag)
                for _, r in m.iterrows():
                    rows.append({"cost_bps": c, "ipb_long": t, "execution_lag": lag, "strategy": r["strategy"],
                                 "annualized_return": r["annualized_return"], "sharpe_rf0": r["sharpe_rf0"],
                                 "max_drawdown": r["max_drawdown"], "start": info["start"]})
    return pd.DataFrame(rows)
