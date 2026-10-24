"""Nessun look-ahead: fattori, target, addestramento e calibrazione usano solo dati noti in t."""
import numpy as np
import pandas as pd
import pytest

from ipb import engine as E
from ipb import model as M
from ipb.data import _aux
from synthetic import make_market


def _same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.all((np.isnan(a) & np.isnan(b)) | np.isclose(a, b, rtol=1e-9, atol=1e-12))


@pytest.mark.parametrize("with_vix", [True, False])
def test_features_truncation_invariant(with_vix):
    raw = make_market(1200, seed=3, with_vix=with_vix)
    full = E.build_features(raw)
    for cut in (450, 800, 1199):
        d = raw.index[cut]
        tr = E.build_features(raw.iloc[:cut + 1])
        assert _same(full.loc[d, E.CAUSAL_COLS].values, tr.loc[d, E.CAUSAL_COLS].values), (d, with_vix)
        assert full.loc[d, "sentiment_source"] == tr.loc[d, "sentiment_source"]


def test_future_perturbation_does_not_change_past_features():
    raw = make_market(1000, seed=4)
    alt = raw.copy()
    alt.iloc[700:, alt.columns.get_loc("close")] *= 1.5     # futuro diverso
    a, b = E.build_features(raw), E.build_features(alt)
    assert _same(a.iloc[:700][E.CAUSAL_COLS].values, b.iloc[:700][E.CAUSAL_COLS].values)


def test_ipb_not_defined_before_warmup():
    f = E.build_features(make_market(600, seed=5))
    first = f["ipb"].first_valid_index()
    assert f.index.get_loc(first) >= 199           # serve almeno la media mobile a 200 sedute


def test_labels_use_future_and_are_nan_when_unobservable():
    raw = make_market(500, seed=6)
    lab = E.add_labels(E.build_features(raw), horizon=10, threshold=0.015)
    assert lab["target_dir"].iloc[-10:].isna().all() and lab["target_rev"].iloc[-10:].isna().all()
    fr = raw["close"].iloc[110] / raw["close"].iloc[100] - 1
    assert np.isclose(lab["future_return"].iloc[100], fr)
    exp = 2 if fr > 0.015 else 0 if fr < -0.015 else 1
    assert lab["target_dir"].iloc[100] == exp


def test_walk_forward_truncation_invariant(fast_settings):
    raw = make_market(900, seed=7)
    H = 10

    def probs(df):
        lab = E.add_labels(E.build_features(df), H, 0.015)
        a = M.walk_forward(lab, "target_dir", M.DIR_CLASSES, H, fast_settings)
        b = M.walk_forward(lab, "target_rev", M.REV_CLASSES, H, fast_settings)
        return a.join(b)
    full = probs(raw)
    cols = M.DIR_COLS + [c + "_raw" for c in M.DIR_COLS] + [c + "_clim" for c in M.DIR_COLS] + M.REV_COLS
    checked = 0
    for cut in (650, 760, 899):
        d = raw.index[cut]
        tr = probs(raw.iloc[:cut + 1])
        assert _same(full.loc[d, cols].values, tr.loc[d, cols].values), d
        checked += np.isfinite(full.loc[d, cols].values.astype(float)).all()
    assert checked >= 2, "il test deve verificare probabilità effettivamente calcolate"


def test_training_ignores_targets_not_yet_observable(fast_settings):
    """Alterare i target delle righe i > t - H (esito non ancora noto in t) non cambia la previsione in t."""
    H = 10
    lab = E.add_labels(E.build_features(make_market(900, seed=8)), H, 0.015)
    base = M.walk_forward(lab, "target_dir", M.DIR_CLASSES, H, fast_settings)
    t = 780                                     # inizio di un blocco di riaddestramento (780 = 39 x 20)
    poisoned = lab.copy()
    rng = np.random.default_rng(0)
    poisoned.iloc[t - H + 1:, poisoned.columns.get_loc("target_dir")] = rng.integers(0, 3, len(lab) - (t - H + 1))
    alt = M.walk_forward(poisoned, "target_dir", M.DIR_CLASSES, H, fast_settings)
    assert np.isfinite(base[M.DIR_COLS].iloc[t]).all()
    assert _same(base[M.DIR_COLS].iloc[t].values, alt[M.DIR_COLS].iloc[t].values)
    # controllo di sensibilità del test: alterare un target già osservabile cambia la previsione
    poisoned2 = lab.copy()
    poisoned2.iloc[:t - H, poisoned2.columns.get_loc("target_dir")] = 2.0
    alt2 = M.walk_forward(poisoned2, "target_dir", M.DIR_CLASSES, H, fast_settings)
    assert not _same(base[M.DIR_COLS + [c + "_raw" for c in M.DIR_COLS]].iloc[t].values,
                     alt2[M.DIR_COLS + [c + "_raw" for c in M.DIR_COLS]].iloc[t].values)


def test_climatology_uses_only_observed_outcomes():
    y = pd.Series([0, 1, 2, 2, 2, np.nan, np.nan], dtype=float)
    c = M._climatology(y, horizon=2, classes=(0, 1, 2))
    assert np.isnan(c[1]).all()                       # in t=1 nessun esito noto (servono i+2 <= 1)
    assert np.allclose(c[2], [1, 0, 0])               # in t=2 noto solo l'esito della riga 0
    assert np.allclose(c[4], [1 / 3, 1 / 3, 1 / 3])


def test_aux_series_lag_hides_same_day_value():
    idx = pd.bdate_range("2020-01-01", periods=5)
    s = pd.Series([10.0, 11, 12, 13, 14], index=idx)
    assert _aux(s, idx, 1).tolist()[1:] == [10, 11, 12, 13]
    assert np.isnan(_aux(s, idx, 1).iloc[0])
    assert _aux(s, idx, 0).tolist() == s.tolist()
