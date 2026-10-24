"""DATI SINTETICI — SOLO PER I TEST DI CORRETTEZZA DEL CODICE.

Non rappresentano alcun mercato reale e non vanno mai usati per risultati, backtest o
probabilità. Ogni DataFrame prodotto ha attrs["synthetic"] = True.
"""
import numpy as np
import pandas as pd


def make_market(n: int = 1600, seed: int = 0, with_vix: bool = True, with_volume: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-04", periods=n)
    vol = 0.01 * np.exp(np.cumsum(rng.normal(0, 0.03, n)).clip(-1, 1))
    r = rng.normal(0.0003, 1, n) * vol
    close = 1000 * np.exp(np.cumsum(r))
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = close * (1 + rng.normal(0, 0.002, n))
    df["high"] = np.maximum(df["open"], close) * 1.003
    df["low"] = np.minimum(df["open"], close) * 0.997
    df["proxy_volume"] = rng.lognormal(16, 0.3, n) if with_volume else np.nan
    df["vol_index"] = (100 * vol * np.sqrt(252) * (1.1 + rng.normal(0, 0.05, n))) if with_vix else np.nan
    df.attrs["synthetic"] = True
    df.attrs["warnings"] = ["DATI SINTETICI — SOLO TEST"]
    return df


def yf_like(n: int = 400, seed: int = 1, ticker: str = "^TEST", layout: str = "price_ticker",
            tz: str | None = None) -> pd.DataFrame:
    """Risposta in stile yfinance (colonne MultiIndex) — SINTETICA, solo per test."""
    m = make_market(n, seed)
    flat = pd.DataFrame({"Close": m["close"], "High": m["high"], "Low": m["low"],
                         "Open": m["open"], "Volume": m["proxy_volume"]}, index=m.index)
    if tz:
        flat.index = flat.index.tz_localize(tz)
    if layout == "flat":
        return flat
    cols = [(c, ticker) for c in flat.columns] if layout == "price_ticker" else [(ticker, c) for c in flat.columns]
    flat.columns = pd.MultiIndex.from_tuples(cols)
    return flat
