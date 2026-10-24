"""Scheda del titolo: fondamentali (via yfinance, se installato) + metriche
quantitative calcolate dai prezzi (sempre disponibili)."""
import math

import numpy as np

import config
import data
import db
from universe import is_index

BENCH = {".MI": "FTSEMIB.MI", ".PA": "^STOXX50E", ".DE": "^STOXX50E", ".AS": "^STOXX50E",
         ".MC": "^STOXX50E", ".CO": "^STOXX50E", ".SW": "^SSMI", ".L": "^FTSE",
         ".HK": "^HSI", ".T": "^N225", ".KS": "^N225", ".SS": "000300.SS"}


def benchmark_for(ticker):
    for suf, b in BENCH.items():
        if ticker.upper().endswith(suf):
            return b
    return "^GSPC"


def _f(x):
    try:
        x = float(x)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def get_fundamentals(ticker: str) -> dict:
    ticker = ticker.upper()
    if is_index(ticker):
        return {}
    cached = db.cache_get("fund_cache", ticker + (":demo" if config.DEMO else ""), 24 * 3600)
    if cached is not None:
        return cached
    out = _demo_fund(ticker) if config.DEMO else _yf_fund(ticker)
    db.cache_put("fund_cache", ticker + (":demo" if config.DEMO else ""), out)
    return out


def _yf_fund(ticker):
    try:
        import yfinance as yf  # opzionale
    except ImportError:
        return {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    price = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
    div_rate = _f(info.get("dividendRate"))
    dy = (div_rate / price) if (div_rate and price) else None
    fcf, shares = _f(info.get("freeCashflow")), _f(info.get("sharesOutstanding"))
    return {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"), "industry": info.get("industry"),
        "country": info.get("country"),
        "summary": (info.get("longBusinessSummary") or "")[:900],
        "market_cap": _f(info.get("marketCap")),
        "pe_trailing": _f(info.get("trailingPE")), "pe_forward": _f(info.get("forwardPE")),
        "pb": _f(info.get("priceToBook")), "ev_ebitda": _f(info.get("enterpriseToEbitda")),
        "dividend_yield": dy, "payout": _f(info.get("payoutRatio")),
        "eps_trailing": _f(info.get("trailingEps")), "eps_forward": _f(info.get("forwardEps")),
        "book_value": _f(info.get("bookValue")),
        "fcf_per_share": (fcf / shares) if (fcf and shares) else None,
        "earnings_growth": _f(info.get("earningsGrowth")),
        "revenue_growth": _f(info.get("revenueGrowth")),
        "roe": _f(info.get("returnOnEquity")), "profit_margin": _f(info.get("profitMargins")),
        "debt_to_equity": _f(info.get("debtToEquity")),
        "beta_provider": _f(info.get("beta")),
        "target_mean": _f(info.get("targetMeanPrice")),
        "analyst_count": _f(info.get("numberOfAnalystOpinions")),
        "recommendation": info.get("recommendationKey"),
    }


def _demo_fund(ticker):
    rng = np.random.default_rng(data._seed(ticker) + 7)
    df, meta = data.get_history(ticker)
    p = float(df["close"].iloc[-1])
    eps = p / rng.uniform(12, 35)
    return {
        "name": f"{ticker} (DEMO)", "sector": "Demo", "industry": "Dati sintetici",
        "country": "-", "summary": "Dati di esempio generati dal sistema: non sono reali.",
        "market_cap": p * rng.uniform(1e8, 3e9), "pe_trailing": p / eps,
        "pe_forward": p / (eps * rng.uniform(1.0, 1.2)), "pb": rng.uniform(1, 8),
        "ev_ebitda": rng.uniform(6, 25), "dividend_yield": rng.uniform(0, 0.05),
        "payout": rng.uniform(0.1, 0.7), "eps_trailing": eps,
        "eps_forward": eps * rng.uniform(1.0, 1.2), "book_value": p / rng.uniform(1, 6),
        "fcf_per_share": eps * rng.uniform(0.6, 1.2), "earnings_growth": rng.uniform(-0.1, 0.25),
        "revenue_growth": rng.uniform(-0.05, 0.2), "roe": rng.uniform(0.05, 0.35),
        "profit_margin": rng.uniform(0.05, 0.3), "debt_to_equity": rng.uniform(10, 150),
        "beta_provider": None, "target_mean": p * rng.uniform(0.85, 1.3),
        "analyst_count": float(rng.integers(3, 30)), "recommendation": "demo",
    }


def price_metrics(df, ticker) -> dict:
    """Metriche calcolate dai prezzi: sempre disponibili, anche senza fondamentali."""
    px = df["adj"]
    r = np.log(px).diff().dropna()
    last = float(df["close"].iloc[-1])
    yr = df.iloc[-252:]
    out = {
        "price": last,
        "chg_1d": float(px.iloc[-1] / px.iloc[-2] - 1),
        "chg_1m": float(px.iloc[-1] / px.iloc[-22] - 1),
        "chg_ytd": float(px.iloc[-1] / px[px.index.year == px.index[-1].year].iloc[0] - 1),
        "chg_1y": float(px.iloc[-1] / px.iloc[-253] - 1),
        "high_52w": float(yr["high"].max()), "low_52w": float(yr["low"].min()),
        "vol_annual": float(r.iloc[-252:].std() * math.sqrt(252)),
        "max_drawdown_1y": float((yr["adj"] / yr["adj"].cummax() - 1).min()),
        "from_high": float(last / yr["high"].max() - 1),
    }
    # beta e correlazione vs benchmark, calcolati da noi (rendimenti settimanali, 2 anni)
    if not is_index(ticker):
        bench = benchmark_for(ticker)
        try:
            bdf, _ = data.get_history(bench)
            a = np.log(df["adj"].resample("W-FRI").last()).diff()
            b = np.log(bdf["adj"].resample("W-FRI").last()).diff()
            j = a.to_frame("a").join(b.to_frame("b"), how="inner").dropna().iloc[-104:]
            if len(j) > 40:
                cov = np.cov(j["a"], j["b"])
                out["beta"] = float(cov[0, 1] / cov[1, 1])
                out["corr_bench"] = float(np.corrcoef(j["a"], j["b"])[0, 1])
                out["benchmark"] = bench
        except Exception:
            pass
    # Sharpe a 1 anno
    rf = config.DEFAULT_RISK_FREE
    out["sharpe_1y"] = float((out["chg_1y"] - rf) / out["vol_annual"]) if out["vol_annual"] else None
    return out
