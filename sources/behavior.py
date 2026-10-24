"""Dati in più per le misure comportamentali di lab/features.py (argomento `extra`)."""
import config

from . import edgar, wiki


def extra_for(ticker, df):
    """df = storico prezzi di data.get_history. In modalità demo niente rete: solo il volume."""
    out = {"volume": df["volume"] if "volume" in df else None}
    if config.DEMO:
        return out
    try:
        out["wiki"] = wiki.pageviews(ticker)
    except Exception:
        out["wiki"] = None
    try:
        out["lazy"] = edgar.lazy_prices(ticker)
    except Exception:
        out["lazy"] = None
    return out
