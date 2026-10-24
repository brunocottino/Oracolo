"""Download dati (Yahoo Finance via yfinance) con cache locale, nuovi tentativi ed errori espliciti.

Regole:
- nessun dato sintetico: se il provider fallisce e non c'è cache, si solleva DataError;
- le serie ausiliarie (volume proxy, indice di volatilità) che chiudono dopo l'indice sono
  ritardate (vedi MarketConfig.*_lag), così al giorno t entra solo ciò che era noto alla chiusura di t;
- ogni ripiego (proxy mancante, cache vecchia) finisce in `df.attrs["warnings"]`.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .config import MarketConfig

CACHE_DIR = Path(os.environ.get("IPB_CACHE_DIR", Path.home() / ".cache" / "ipb_extreme"))
CACHE_TTL_SECONDS = int(os.environ.get("IPB_CACHE_TTL", 12 * 3600))
MIN_ROWS = 300


class DataError(RuntimeError):
    """Errore dati con messaggio leggibile per l'utente."""


def _yf_download(ticker: str, start: str, end: str | None) -> pd.DataFrame:
    import yfinance as yf
    return yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False,
                       group_by="column", threads=False, multi_level_index=True)


def normalize_columns(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Colonne piatte Open/High/Low/Close/Volume anche quando yfinance restituisce un MultiIndex
    (Price, Ticker) oppure (Ticker, Price)."""
    data = data.copy()
    if isinstance(data.columns, pd.MultiIndex):
        fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
        lvl = next((i for i in range(data.columns.nlevels)
                    if fields & {str(x) for x in data.columns.get_level_values(i)}), None)
        if lvl is None:
            raise DataError(f"Formato colonne inatteso per {ticker}: {list(data.columns)[:4]}")
        other = [i for i in range(data.columns.nlevels) if i != lvl]
        if other:
            tick_vals = {str(x) for x in data.columns.get_level_values(other[0])}
            if len(tick_vals) > 1:
                if ticker not in tick_vals:
                    raise DataError(f"Il provider ha restituito ticker diversi da {ticker}: {sorted(tick_vals)}")
                data = data.xs(ticker, axis=1, level=other[0])
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(lvl)
    data.columns = [str(c).title() for c in data.columns]
    data = data.loc[:, ~pd.Index(data.columns).duplicated()]
    idx = pd.to_datetime(data.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    data.index = idx.normalize()
    data = data[~data.index.duplicated(keep="last")].sort_index()
    for c in data.columns:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    if "Close" in data:
        data = data[data["Close"].notna() & (data["Close"] > 0)]
    return data


def _cache_path(ticker: str, start: str, end: str | None) -> Path:
    safe = "".join(ch if ch.isalnum() else "_" for ch in ticker)
    return CACHE_DIR / f"{safe}_{start}_{end or 'oggi'}.csv"


def download(ticker: str, start: str, end: str | None = None, *, use_cache: bool = True,
             downloader: Callable[[str, str, str | None], pd.DataFrame] | None = None,
             retries: int = 3, backoff: float = 2.0, warnings: list | None = None) -> pd.DataFrame:
    """Scarica un ticker. Usa la cache se recente; se il provider fallisce usa una cache vecchia
    dichiarandolo in `warnings`; senza cache solleva DataError con la causa."""
    downloader = downloader or _yf_download
    path = _cache_path(ticker, start, end)
    if use_cache and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            raw = downloader(ticker, start, end)
            if raw is None or raw.empty:
                raise DataError(f"Nessun dato ricevuto per {ticker}: ticker inesistente o provider senza storico.")
            data = normalize_columns(raw, ticker)
            if data.empty or "Close" not in data:
                raise DataError(f"Dati senza prezzi di chiusura validi per {ticker}.")
            if use_cache:
                path.parent.mkdir(parents=True, exist_ok=True)
                data.to_csv(path)
            return data
        except DataError as e:
            last_err = e
            break                        # risposta valida ma vuota: inutile riprovare
        except Exception as e:           # rete, limiti di richiesta, errori del provider
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    if use_cache and path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if warnings is not None:
            warnings.append(f"{ticker}: provider non raggiungibile ({last_err}); uso dati in cache di {age_h:.0f} ore fa.")
        return pd.read_csv(path, index_col=0, parse_dates=True)
    msg = str(last_err)
    hint = " (limite di richieste del provider: riprovare tra qualche minuto)" if "rate" in msg.lower() or "429" in msg else ""
    raise DataError(f"Download fallito per {ticker}: {msg}{hint}") from last_err


def _aux(series: pd.Series, index: pd.DatetimeIndex, lag: int) -> pd.Series:
    """Allinea una serie ausiliaria al calendario dell'indice usando solo valori noti:
    prima il ritardo sul calendario della serie stessa, poi l'ultimo valore disponibile."""
    s = series.sort_index().shift(lag)
    u = s.index.union(index)
    return s.reindex(u).ffill().reindex(index)


def load_market(config: MarketConfig, start: str, end: str | None = None, *, use_cache: bool = True,
                downloader: Callable | None = None, retries: int = 3, backoff: float = 2.0) -> pd.DataFrame:
    warnings: list[str] = []
    kw = dict(use_cache=use_cache, downloader=downloader, warnings=warnings, retries=retries, backoff=backoff)
    index = download(config.index_ticker, start, end, **kw)
    out = pd.DataFrame(index=index.index)
    out["close"] = index["Close"]
    for c in ("open", "high", "low"):
        out[c] = index[c.title()] if c.title() in index else np.nan

    out["proxy_volume"] = np.nan
    if config.volume_proxy:
        try:
            proxy = download(config.volume_proxy, start, end, **kw)
            if "Volume" in proxy and proxy["Volume"].fillna(0).gt(0).any():
                # il volume non si propaga ai giorni mancanti: un volume vecchio non è il volume di oggi
                v = proxy["Volume"].replace(0, np.nan).sort_index().shift(config.volume_proxy_lag)
                out["proxy_volume"] = v.reindex(out.index)
            else:
                warnings.append(f"Volume proxy {config.volume_proxy}: volumi assenti, fattore volume escluso.")
        except DataError as e:
            warnings.append(f"Volume proxy non disponibile, fattore volume escluso. {e}")

    out["vol_index"] = np.nan
    if config.vol_ticker:
        try:
            vol = download(config.vol_ticker, start, end, **kw)
            out["vol_index"] = _aux(vol["Close"], out.index, config.vol_lag)
        except DataError as e:
            warnings.append(f"Indice di volatilità non disponibile: Expectation Gap non calcolabile. {e}")
    else:
        warnings.append("Nessun indice di volatilità configurato: Expectation Gap non calcolabile, "
                        "Reaction Anomaly e sentiment usano solo i prezzi.")

    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
    if len(out) < MIN_ROWS:
        raise DataError(f"Storico troppo corto per {config.index_ticker} ({len(out)} sedute, minimo {MIN_ROWS}). "
                        "Scegliere una data iniziale più remota o verificare il provider.")
    gaps = out.index.to_series().diff().dt.days
    if (gaps > 10).any():
        warnings.append(f"{int((gaps > 10).sum())} buchi di oltre 10 giorni nello storico di {config.index_ticker}.")
    out.attrs["warnings"] = warnings
    out.attrs["market"] = config.label
    out.attrs["synthetic"] = False
    return out
