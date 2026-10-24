"""Segnale applicato alla seduta successiva, costi, finestra comune."""
import numpy as np
import pandas as pd
import pytest

from ipb import backtest as B
from ipb import engine as E
from synthetic import make_market


def test_signal_applied_next_session_and_costs():
    idx = pd.bdate_range("2021-01-01", periods=6)
    sig = pd.Series([0, 1, 1, 0, 0, 0], index=idx, dtype=float)
    mret = pd.Series([0.0, 0.01, 0.02, -0.03, 0.04, 0.0], index=idx)
    res = B.apply_position(sig, mret, cost_bps=10, lag=1)
    assert res["position"].tolist() == [0, 0, 1, 1, 0, 0]
    assert res["turnover"].tolist() == [0, 0, 1, 0, 1, 0]
    exp = [0, 0, 0.02 - 0.001, -0.03, -0.001, 0]
    assert np.allclose(res["return"].values, exp)
    # il rendimento del giorno in cui nasce il segnale non è mai catturato
    assert res["return"].iloc[1] == 0


def test_lag_two_is_more_conservative_and_lag_zero_forbidden():
    idx = pd.bdate_range("2021-01-01", periods=4)
    sig = pd.Series([1, 0, 0, 0], index=idx, dtype=float)
    mret = pd.Series([0.05, 0.01, 0.02, 0.0], index=idx)
    assert B.apply_position(sig, mret, 0, 2)["position"].tolist() == [0, 0, 1, 0]
    with pytest.raises(ValueError):
        B.apply_position(sig, mret, 0, 0)


def test_initial_entry_pays_cost():
    idx = pd.bdate_range("2021-01-01", periods=3)
    res = B.apply_position(pd.Series(1.0, index=idx), pd.Series(0.0, index=idx), cost_bps=20, lag=1)
    assert res["turnover"].sum() == 1 and np.isclose(res["return"].sum(), -0.002)


def test_backtest_common_window_and_costs_reduce_returns():
    f = E.build_features(make_market(900, seed=11))
    f["p_up"], f["p_down"] = 0.5, 0.3
    bt0, m0, info0 = B.run_backtest(f, cost_bps=0)
    bt20, m20, _ = B.run_backtest(f, cost_bps=20)
    start = pd.Timestamp(info0["start"])
    assert start >= f["ipb"].first_valid_index() and start >= f.index[99]     # serve anche la MA100
    s0, s20 = m0.set_index("strategy"), m20.set_index("strategy")
    assert len(set(s0["observations"])) == 1                                  # stessa finestra per tutti
    assert s20.loc["IPB long/flat", "total_return"] < s0.loc["IPB long/flat", "total_return"]
    # buy & hold: il costo si paga una sola volta, il giorno dell'ingresso
    diff = (bt0["buy_hold_return"] - bt20["buy_hold_return"]).dropna()
    assert np.isclose(diff.sum(), 0.002) and (diff.abs() > 1e-12).sum() == 1
    # strategia: costo = turnover x 20 bps, giorno per giorno
    d = (bt0["strategy_return"] - bt20["strategy_return"]).dropna()
    turnover = bt20["strategy_position"].dropna().diff().abs()
    turnover.iloc[0] = abs(bt20["strategy_position"].dropna().iloc[0])
    assert np.allclose(d.values, turnover.values * 0.002)


def test_sensitivity_grid_shape():
    f = E.build_features(make_market(700, seed=12))
    s = B.sensitivity(f)
    assert len(s) == 4 * 3 * 2 * 3        # costi x soglie x ritardi x strategie (senza probabilità)
    assert set(s["execution_lag"]) == {1, 2}
