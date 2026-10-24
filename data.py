"""Dati di mercato gratuiti.

Fonte principale: API pubblica di Yahoo Finance (nessuna chiave richiesta).
Se `yfinance` è installato viene usato per fondamentali, annunci degli utili,
giudizi degli analisti e catene di opzioni. Se manca, quelle parti si spengono
con eleganza (la piattaforma continua a funzionare con i soli prezzi).

Con ORACOLO_DEMO=1 genera dati sintetici realistici (per test offline):
prezzi con un modello a fattori (titolo = beta x indice + componente propria),
annunci utili con stima e risultato, upgrade/downgrade, VIX e VIX3M, tasso a
3 mesi (^IRX) e catene di opzioni (volatilità implicita ATM e skew).
Il generatore può INSERIRE un segnale noto (config.DEMO_SIGNAL): dopo ogni
annuncio i rendimenti residui futuri seguono la sorpresa sugli utili, con una
correlazione di rango attesa pari a config.DEMO_SIGNAL_IC. Serve a verificare
che il banco di prova trovi un segnale quando c'è e non lo inventi quando non c'è.
"""
import hashlib
import math
import threading
import time
from functools import lru_cache

import numpy as np
import pandas as pd
import requests

import config
import db

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"
SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

US_INDICES = {"^GSPC", "^NDX", "^DJI", "^RUT"}


class DataError(Exception):
    pass


def has_yfinance() -> bool:
    try:
        import yfinance  # noqa: F401
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Prezzi storici
# --------------------------------------------------------------------------
_mem, _mem_lock = {}, threading.Lock()


def _demo_tag():
    return f"demo:{config.DEMO_SIGNAL}:{config.DEMO_SIGNAL_IC}:{config.DEMO_YEARS}"


def get_history(ticker: str, years=None) -> tuple[pd.DataFrame, dict]:
    """Restituisce (DataFrame OHLCV giornaliero, meta) con colonne
    open high low close adj volume, indice di date.
    years=None o "max": tutto lo storico disponibile (default)."""
    ticker = ticker.upper().strip()
    if years in (None, "max"):
        years = None
    key = f"{ticker}:{years or 'max'}:{_demo_tag() if config.DEMO else 'live'}"
    with _mem_lock:
        hit = _mem.get(key)
    if hit and time.time() - hit[0] < config.PRICE_CACHE_TTL:
        return hit[1].copy(), dict(hit[2])
    cached = db.cache_get("price_cache", key, config.PRICE_CACHE_TTL)
    if cached:
        df = pd.DataFrame(cached["rows"], columns=cached["cols"])
        df.index = pd.to_datetime(df.pop("date"))
        meta = cached["meta"]
    else:
        df, meta = (_demo_history(ticker, years) if config.DEMO else _yahoo_history(ticker, years))
        if len(df) < 300:
            raise DataError(f"Storico insufficiente per {ticker} ({len(df)} sedute).")
        out = df.copy()
        out.insert(0, "date", out.index.strftime("%Y-%m-%d"))
        db.cache_put("price_cache", key, {"cols": list(out.columns),
                                          "rows": out.values.tolist(), "meta": meta})
    with _mem_lock:
        if len(_mem) > 400:
            _mem.clear()
        _mem[key] = (time.time(), df, meta)
    return df.copy(), dict(meta)


def _yahoo_history(ticker, years):
    rng = "max" if years is None else f"{years}y"
    try:
        r = requests.get(CHART_URL.format(t=ticker), headers=UA, timeout=30,
                         params={"range": rng, "interval": "1d",
                                 "events": "div,splits", "includeAdjustedClose": "true"})
        r.raise_for_status()
        js = r.json()["chart"]
        if js.get("error"):
            raise DataError(js["error"].get("description", "errore Yahoo"))
        res = js["result"][0]
    except DataError:
        raise
    except Exception as e:  # rete, JSON, ecc.
        raise DataError(f"Impossibile scaricare {ticker}: {e}") from e

    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
    df = pd.DataFrame({
        "open": q["open"], "high": q["high"], "low": q["low"],
        "close": q["close"], "adj": adj, "volume": q["volume"],
    }, index=pd.to_datetime(res["timestamp"], unit="s").normalize())
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    df = df[df["close"] > 0]
    df["adj"] = df["adj"].fillna(df["close"])
    for c in ("open", "high", "low"):
        df[c] = df[c].fillna(df["close"])
    df["volume"] = df["volume"].fillna(0)
    m = res.get("meta", {})
    meta = {
        "currency": m.get("currency", "USD"),
        "exchange": m.get("fullExchangeName") or m.get("exchangeName", ""),
        "name": m.get("longName") or m.get("shortName") or ticker,
        "type": m.get("instrumentType", ""),
        "price": m.get("regularMarketPrice") or float(df["close"].iloc[-1]),
        "demo": False,
    }
    return df, meta


def _seed(ticker):
    return int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)


# --------------------------------------------------------------------------
# Generatore demo
# --------------------------------------------------------------------------
def _demo_n():
    return config.DEMO_YEARS * 252


@lru_cache(maxsize=4)
def _demo_calendar(n, end):
    return pd.bdate_range(end=pd.Timestamp(end), periods=n)


def _calendar():
    return _demo_calendar(_demo_n(), str(pd.Timestamp.today().normalize().date()))


def _garch_path(rng, n, base_vol, a=0.08, b=0.90, dof=5):
    """Rendimenti con volatilità a grappoli (GARCH) e code grasse. Restituisce (eps, h)."""
    h = np.empty(n)
    e = np.empty(n)
    omega = (base_vol ** 2 / 252) * (1 - a - b)
    h[0] = base_vol ** 2 / 252
    z = rng.standard_t(dof, n) / math.sqrt(dof / (dof - 2))
    for i in range(n):
        if i:
            h[i] = omega + a * e[i - 1] ** 2 + b * h[i - 1]
        e[i] = math.sqrt(h[i]) * z[i]
    return e, h


@lru_cache(maxsize=512)
def _demo_bundle(ticker, signal, ic, n, end):
    """Genera (log-rendimenti, ohlc, eventi) in modo deterministico per ticker.
    Il segnale inserito dipende solo da (signal, ic)."""
    from universe import is_index
    rng = np.random.default_rng(_seed(ticker))
    dates = _demo_calendar(n, end)
    t = ticker.upper()
    events = {"earnings": [], "grades": []}
    if t in ("^VIX", "^VIX3M"):
        g = _demo_bundle("^GSPC", signal, ic, n, end)
        r = pd.Series(g["r"])
        lam = 0.94 if t == "^VIX" else 0.985
        var = (r ** 2).ewm(alpha=1 - lam, adjust=False).mean().values
        noise = np.zeros(n)
        for i in range(1, n):
            noise[i] = 0.9 * noise[i - 1] + rng.normal(0, 0.6)
        lvl = np.maximum(100 * np.sqrt(var * 252) * (1.18 if t == "^VIX" else 1.14) + noise, 9.0)
        return {"level": lvl, "r": None, "events": events, "kind": "level"}
    if t == "^IRX":
        x = np.empty(n)
        x[0] = 2.0
        for i in range(1, n):
            x[i] = x[i - 1] + 0.004 * (3.0 - x[i - 1]) + rng.normal(0, 0.03)
        return {"level": np.clip(x, 0.02, 7.0), "r": None, "events": events, "kind": "level"}

    if is_index(t):
        base_vol = 0.16
        e, h = _garch_path(rng, n, base_vol)
        drift = rng.uniform(0.03, 0.09)
        r = drift / 252 - 0.5 * h + e
        tt = np.arange(n)
        r += 0.0004 * np.sin(2 * np.pi * tt / rng.uniform(180, 400))
        return {"r": r, "h": h, "events": events, "kind": "index", "p0": rng.uniform(3000, 40000)}

    # ---- azione: r = alfa + beta x indice + componente propria (+ reazioni agli utili + segnale) ----
    from fundamentals import benchmark_for
    bench = _demo_bundle(benchmark_for(t), signal, ic, n, end)
    beta = rng.uniform(0.6, 1.5)
    idio_vol = rng.uniform(0.18, 0.36)
    e, h = _garch_path(rng, n, idio_vol)
    s_d = idio_vol / math.sqrt(252)
    alpha = rng.normal(0.0, 0.02) / 252
    r = alpha + beta * bench["r"] + e - 0.5 * h
    # annunci trimestrali: sorpresa z ~ N(0,1)
    pos = int(rng.integers(5, 60))
    ann = []
    while pos < n - 3:
        ann.append(pos)
        pos += int(rng.integers(58, 68))
    z = rng.normal(0, 1, len(ann))
    # reazione all'annuncio (già nel prezzo): salto il giorno dopo
    for p, zz in zip(ann, z):
        r[p + 1] += 1.8 * zz * s_d
    # segnale inserito: deriva dei residui dopo che l'informazione è disponibile (t+2)
    if signal == "sue" and ic > 0:
        a = ic / 5.2          # tarato empiricamente: IC di rango sul residuo a 31 sedute ~ ic
        for k, (p, zz) in enumerate(zip(ann, z)):
            start = p + 2
            stop = ann[k + 1] + 2 if k + 1 < len(ann) else n
            r[start:stop] += a * s_d * zz
    px = rng.uniform(20, 400) * np.exp(np.cumsum(r))
    sig_s = rng.uniform(0.001, 0.003)
    ep = rng.uniform(0.035, 0.07) / 4
    for p, zz in zip(ann, z):
        est = px[p] * ep
        events["earnings"].append({"date": str(dates[p].date()), "eps_est": round(float(est), 4),
                                   "eps_act": round(float(est + zz * sig_s * px[p]), 4)})
    # giudizi degli analisti: soprattutto titoli quotati negli USA (come su Yahoo)
    if "." not in t:
        prior = px[0] * 1.1
        pos = int(rng.integers(5, 40))
        while pos < n - 1:
            act = rng.choice(["up", "down", "main", "init"], p=[0.22, 0.2, 0.48, 0.1])
            base = px[pos]
            if act == "up":
                new = max(prior, base) * (1 + rng.uniform(0.03, 0.15))
            elif act == "down":
                new = min(prior, base * 1.1) * (1 - rng.uniform(0.03, 0.15))
            else:
                new = base * (1 + rng.uniform(-0.05, 0.2))
            events["grades"].append({"date": str(dates[pos].date()), "action": str(act),
                                     "tgt_prior": round(float(prior), 2), "tgt_new": round(float(new), 2)})
            prior = new
            pos += int(rng.exponential(35)) + 1
    return {"r": r, "h": h, "events": events, "kind": "stock", "px": px, "beta": beta, "z": z, "ann": ann}


def _demo_history(ticker, years):
    """Serie sintetica: NON sono dati reali."""
    n = _demo_n()
    end = str(pd.Timestamp.today().normalize().date())
    dates = _demo_calendar(n, end)
    b = _demo_bundle(ticker.upper(), config.DEMO_SIGNAL, config.DEMO_SIGNAL_IC, n, end)
    rng = np.random.default_rng(_seed(ticker) + 99)
    if b["kind"] == "level":
        close = b["level"]
        hv = np.full(n, 0.01)
    else:
        p0 = b.get("p0") or 1.0
        close = b["px"] if "px" in b else p0 * np.exp(np.cumsum(b["r"]))
        hv = b["h"]
    intr = np.abs(rng.normal(0, np.sqrt(hv))) * close
    df = pd.DataFrame({
        "open": close * np.exp(rng.normal(0, np.sqrt(hv) * 0.3)),
        "high": close + intr, "low": np.maximum(close - intr, close * 0.5), "close": close, "adj": close,
        "volume": rng.integers(100_000, 5_000_000, n).astype(float),
    }, index=dates)
    if years:
        df = df.iloc[-int(years * 252):]
    cur = "EUR" if ticker.endswith((".MI", ".PA", ".DE", ".AS", ".MC")) else "USD"
    return df, {"currency": cur, "exchange": "DEMO", "name": ticker, "type": "DEMO",
                "price": float(df["close"].iloc[-1]), "demo": True}


def demo_truth(ticker):
    """Solo per i test: parametri veri usati dal generatore (beta, sorprese)."""
    n = _demo_n()
    end = str(pd.Timestamp.today().normalize().date())
    return _demo_bundle(ticker.upper(), config.DEMO_SIGNAL, config.DEMO_SIGNAL_IC, n, end)


def clear_demo_cache():
    _demo_bundle.cache_clear()
    with _mem_lock:
        _mem.clear()


# --------------------------------------------------------------------------
# Eventi (classe A: hanno una data storica)
# --------------------------------------------------------------------------
def get_events(ticker: str) -> dict:
    """Annunci degli utili (stima e risultato) e giudizi degli analisti.
    Formato: {"earnings": [{date, eps_est, eps_act}], "grades": [{date, action, tgt_prior, tgt_new}],
              "source": str}. Cache SQLite al massimo giornaliera."""
    from universe import is_index
    t = ticker.upper().strip()
    if is_index(t):
        return {"earnings": [], "grades": [], "source": "non applicabile"}
    if config.DEMO:
        b = demo_truth(t)
        return {"earnings": list(b["events"]["earnings"]), "grades": list(b["events"]["grades"]),
                "source": "demo (sintetico)"}
    key = t
    cached = db.cache_get("events_cache", key, config.EVENTS_CACHE_TTL)
    if cached is not None:
        return cached
    out = _yf_events(t)
    db.cache_put("events_cache", key, out)
    return out


def _naive_dates(idx):
    idx = pd.DatetimeIndex(idx)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def _yf_events(t):
    out = {"earnings": [], "grades": [], "source": "yfinance"}
    try:
        import yfinance as yf
    except Exception:
        out["source"] = "non disponibile (yfinance non installato)"
        return out
    tk = yf.Ticker(t)
    try:
        ed = tk.get_earnings_dates(limit=40)
        if ed is not None and len(ed):
            cols = {c.lower(): c for c in ed.columns}
            ce = cols.get("eps estimate")
            ca = cols.get("reported eps")
            if ce and ca:
                d = _naive_dates(ed.index)
                for dd, est, act in zip(d, ed[ce].values, ed[ca].values):
                    if pd.notna(est) and pd.notna(act):
                        out["earnings"].append({"date": str(dd.date()), "eps_est": float(est), "eps_act": float(act)})
    except Exception as e:
        out["earnings_error"] = str(e)[:200]
    try:
        ud = tk.upgrades_downgrades
        if ud is not None and len(ud):
            ud = ud.copy()
            if "GradeDate" in ud.columns:
                ud = ud.set_index("GradeDate")
            d = _naive_dates(ud.index)
            amap = {"up": "up", "down": "down", "init": "init", "main": "main", "reit": "main"}
            for i, dd in enumerate(d):
                row = ud.iloc[i]
                act = amap.get(str(row.get("Action", "")).lower(), "main")
                tp = row.get("priorPriceTarget")
                tn = row.get("currentPriceTarget")
                out["grades"].append({
                    "date": str(dd.date()), "action": act,
                    "tgt_prior": float(tp) if pd.notna(tp) and tp else None,
                    "tgt_new": float(tn) if pd.notna(tn) and tn else None})
    except Exception as e:
        out["grades_error"] = str(e)[:200]
    out["earnings"].sort(key=lambda x: x["date"])
    out["grades"].sort(key=lambda x: x["date"])
    return out


# --------------------------------------------------------------------------
# Opzioni (classe B: solo istantanea di oggi)
# --------------------------------------------------------------------------
def get_options(ticker: str):
    """Riassunto della catena opzioni: per ogni scadenza IV ATM e IV agli strike 90% / 110%.
    Restituisce None se non ci sono opzioni (tipico per .MI e molti titoli europei/asiatici)."""
    t = ticker.upper().strip()
    if config.DEMO:
        return _demo_options(t)
    cached = db.cache_get("options_cache", t, config.EVENTS_CACHE_TTL)
    if cached is not None:
        return cached or None
    out = _yf_options(t)
    db.cache_put("options_cache", t, out or {})
    return out


def _demo_options(t):
    from universe import is_index
    if "." in t or t in ("^VIX", "^VIX3M", "^IRX"):
        return None
    if is_index(t) and t not in US_INDICES and t != "EEM":
        return None
    df, _ = get_history(t)
    r = np.log(df["adj"]).diff().dropna().values
    rng = np.random.default_rng(_seed(t + str(df.index[-1].date())))
    vol = math.sqrt(0.5 * np.var(r[-21:]) + 0.5 * np.var(r[-252:])) * math.sqrt(252)
    atm = vol * rng.uniform(1.0, 1.2)
    skew = rng.uniform(0.02, 0.08) * (1.4 if is_index(t) else 1.0)
    exps = []
    for d in (9, 23, 37, 51, 79, 107):
        a = atm * (1 + 0.04 * math.log(d / 45))
        exps.append({"days": d, "atm_iv": a, "iv90": a + skew * 0.6, "iv110": a - skew * 0.4})
    return {"spot": float(df["close"].iloc[-1]), "expiries": exps, "source": "demo (sintetico)"}


def _yf_options(t):
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        tk = yf.Ticker(t)
        dates = list(tk.options or [])
        if not dates:
            return None
        spot = None
        try:
            spot = float(tk.fast_info["last_price"])
        except Exception:
            pass
        if not spot:
            spot = float(get_history(t, years=1)[0]["close"].iloc[-1])
        today = pd.Timestamp.today().normalize()
        cand = sorted(dates, key=lambda d: abs((pd.Timestamp(d) - today).days - 45))[:3]
        exps = []
        for d in sorted(cand):
            days = (pd.Timestamp(d) - today).days
            if days < 5:
                continue
            ch = tk.option_chain(d)
            calls = ch.calls[(ch.calls["impliedVolatility"] > 0.01) & (ch.calls["impliedVolatility"] < 3)]
            puts = ch.puts[(ch.puts["impliedVolatility"] > 0.01) & (ch.puts["impliedVolatility"] < 3)]
            if len(calls) < 3 or len(puts) < 3:
                continue

            def iv_at(dfo, k):
                s = dfo.sort_values("strike")
                return float(np.interp(k, s["strike"].values, s["impliedVolatility"].values))
            atm = 0.5 * (iv_at(calls, spot) + iv_at(puts, spot))
            exps.append({"days": days, "atm_iv": atm, "iv90": iv_at(puts, 0.9 * spot),
                         "iv110": iv_at(calls, 1.1 * spot)})
        if not exps:
            return None
        return {"spot": spot, "expiries": exps, "source": "yfinance (catena opzioni)"}
    except Exception:
        return None


# --------------------------------------------------------------------------
# Tassi, cambi, ricerca
# --------------------------------------------------------------------------
def risk_free_rate() -> float:
    """Rendimento Treasury 10 anni (^TNX) come tasso privo di rischio (per il CAPM)."""
    if config.DEMO:
        return config.DEFAULT_RISK_FREE
    try:
        df, _ = get_history("^TNX", years=2)
        v = float(df["close"].iloc[-1]) / 100.0
        return v if 0 < v < 0.2 else config.DEFAULT_RISK_FREE
    except Exception:
        return config.DEFAULT_RISK_FREE


def short_rate_series():
    """Tasso a 3 mesi (^IRX / 100) come serie storica, per i rendimenti in eccesso degli indici.
    None se non disponibile: allora si usa la costante di config."""
    try:
        df, _ = get_history("^IRX")
        s = (df["close"] / 100.0).clip(lower=0, upper=0.2)
        return s
    except Exception:
        return None


def fx_to_eur(currency: str) -> float:
    """Quanti EUR vale 1 unità di `currency`."""
    currency = currency or "EUR"
    pence = currency in ("GBp", "GBX", "GBx")   # Londra quota in pence
    cur = "GBP" if pence else currency.upper()
    if cur == "EUR":
        return 1.0
    if config.DEMO:
        rate = {"USD": 0.92, "GBP": 1.17, "CHF": 1.05, "JPY": 0.0061, "HKD": 0.118}.get(cur, 1.0)
    else:
        rate = None
        try:
            r = requests.get(CHART_URL.format(t=f"{cur}EUR=X"), headers=UA, timeout=15,
                             params={"range": "5d", "interval": "1d"})
            rate = float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        except Exception:
            rate = None
        if not rate:
            rate = {"USD": 0.92, "GBP": 1.17, "CHF": 1.05, "JPY": 0.0061, "HKD": 0.118}.get(cur, 1.0)
    return rate / 100 if pence else rate


def search(query: str):
    """Cerca un titolo per nome (es. 'Ferrari' -> RACE.MI)."""
    if config.DEMO:
        from universe import MARKETS, INDICES
        q = query.lower()
        out = []
        for t, n in list(INDICES.items()) + [(t, n) for m in MARKETS.values() for t, n in m.items()]:
            if q in t.lower() or q in n.lower():
                out.append({"symbol": t, "name": n, "exchange": "DEMO", "type": ""})
        return out[:10]
    try:
        r = requests.get(SEARCH_URL, headers=UA, timeout=15,
                         params={"q": query, "quotesCount": 10, "newsCount": 0})
        quotes = r.json().get("quotes", [])
        return [{"symbol": x.get("symbol"), "name": x.get("longname") or x.get("shortname"),
                 "exchange": x.get("exchDisp"), "type": x.get("quoteType")}
                for x in quotes if x.get("symbol")]
    except Exception:
        return []
