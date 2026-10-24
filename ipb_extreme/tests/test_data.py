"""Download: colonne MultiIndex, ticker fallito, cache, date mancanti, proxy assenti."""
import numpy as np
import pandas as pd
import pytest

from ipb import data as D
from ipb import engine as E
from ipb.config import MarketConfig
from synthetic import yf_like

CFG = MarketConfig("Test", "^TEST", "PRX", "^VTEST", volume_proxy_lag=1, vol_lag=1)


@pytest.mark.parametrize("layout", ["price_ticker", "ticker_price", "flat"])
def test_normalize_multiindex(layout):
    out = D.normalize_columns(yf_like(layout=layout), "^TEST")
    assert list(out.columns) == ["Close", "High", "Low", "Open", "Volume"]
    assert out.index.is_monotonic_increasing


def test_normalize_tz_and_duplicates_and_bad_rows():
    raw = yf_like(layout="flat", tz="America/New_York")
    raw = pd.concat([raw, raw.iloc[[5]]])                 # data duplicata
    raw.iloc[10, raw.columns.get_loc("Close")] = np.nan   # chiusura mancante
    raw.iloc[11, raw.columns.get_loc("Close")] = -1       # valore impossibile
    out = D.normalize_columns(raw, "^TEST")
    assert out.index.tz is None and not out.index.duplicated().any()
    assert len(out) == len(raw) - 1 - 2


def test_multi_ticker_response_rejected_if_wrong():
    a = yf_like(ticker="AAA")
    b = yf_like(ticker="BBB")
    with pytest.raises(D.DataError):
        D.normalize_columns(pd.concat([a, b], axis=1), "^TEST")


def test_failed_ticker_gives_explicit_error():
    with pytest.raises(D.DataError, match=r"Nessun dato ricevuto per \^TEST"):
        D.download("^TEST", "2010-01-01", downloader=lambda *a: pd.DataFrame(), backoff=0)
    calls = []

    def boom(*a):
        calls.append(1)
        raise ConnectionError("Too Many Requests. Rate limited")
    with pytest.raises(D.DataError, match="limite di richieste"):
        D.download("^TEST", "2010-01-01", downloader=boom, retries=3, backoff=0)
    assert len(calls) == 3


def test_cache_and_stale_fallback(monkeypatch):
    ok = lambda *a: yf_like(layout="flat")  # noqa: E731
    first = D.download("^TEST", "2010-01-01", downloader=ok)
    again = D.download("^TEST", "2010-01-01", downloader=lambda *a: pytest.fail("doveva usare la cache"))
    assert len(again) == len(first)
    monkeypatch.setattr(D, "CACHE_TTL_SECONDS", -1)        # cache scaduta
    warns = []
    stale = D.download("^TEST", "2010-01-01", downloader=lambda *a: (_ for _ in ()).throw(OSError("rete")),
                       backoff=0, warnings=warns)
    assert len(stale) == len(first) and warns and "cache" in warns[0]


def _fake(responses):
    def dl(ticker, start, end):
        r = responses[ticker]
        if isinstance(r, Exception):
            raise r
        return r
    return dl


def test_load_market_missing_dates_and_lags():
    idx_resp = yf_like(400, seed=2, ticker="^TEST")
    prx = yf_like(400, seed=3, ticker="PRX", layout="flat").iloc[::2]      # proxy con metà delle date
    vix = yf_like(400, seed=4, ticker="^VTEST", layout="flat")
    out = D.load_market(CFG, "2010-01-01", downloader=_fake({"^TEST": idx_resp, "PRX": prx, "^VTEST": vix}),
                        use_cache=False)
    assert out.index.equals(D.normalize_columns(idx_resp, "^TEST").index)
    assert out["proxy_volume"].isna().sum() >= 190            # niente volume inventato nei giorni mancanti
    d = out.index[50]
    assert out.loc[d, "vol_index"] == vix["Close"].iloc[49]    # VIX ritardato di una seduta
    f = E.build_features(out)
    assert f["ipb"].notna().sum() > 0


def test_proxy_failure_is_declared_not_silent():
    idx_resp = yf_like(400, seed=2, ticker="^TEST")
    out = D.load_market(CFG, "2010-01-01", use_cache=False, backoff=0, downloader=_fake(
        {"^TEST": idx_resp, "PRX": ConnectionError("down"), "^VTEST": pd.DataFrame()}))
    w = " ".join(out.attrs["warnings"])
    assert "Volume proxy non disponibile" in w and "Expectation Gap non calcolabile" in w
    f = E.build_features(out)
    assert f["expectation_gap"].isna().all()
    assert (f["reaction_source"] == "solo prezzo").all()


def test_index_failure_raises():
    with pytest.raises(D.DataError, match="Download fallito per \\^TEST"):
        D.load_market(CFG, "2010-01-01", use_cache=False, backoff=0,
                      downloader=_fake({"^TEST": ConnectionError("down")}))
    with pytest.raises(D.DataError, match="Nessun dato"):
        D.load_market(CFG, "2010-01-01", use_cache=False, downloader=_fake({"^TEST": pd.DataFrame()}))


def test_short_history_raises():
    with pytest.raises(D.DataError, match="troppo corto"):
        D.load_market(CFG, "2010-01-01", use_cache=False,
                      downloader=_fake({"^TEST": yf_like(100), "PRX": yf_like(100, layout="flat"),
                                        "^VTEST": yf_like(100, layout="flat")}))
