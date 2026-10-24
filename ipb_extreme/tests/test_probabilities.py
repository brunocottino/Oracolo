"""Classi probabilistiche, calibrazione, soglie di campione e cosa si mostra."""
import numpy as np
import pandas as pd

from ipb import engine as E
from ipb import model as M
from ipb.config import Settings
from synthetic import make_market


def _frame(settings, n=900, seed=21):
    lab = E.add_labels(E.build_features(make_market(n, seed)), 10, 0.015)
    return lab, M.walk_forward(lab, "target_dir", M.DIR_CLASSES, 10, settings)


def test_probabilities_valid_and_sum_to_one(fast_settings):
    lab, p = _frame(fast_settings)
    for suffix in ("", "_raw", "_clim"):
        P = p[[c + suffix for c in M.DIR_COLS]].dropna().values
        assert len(P) > 50
        assert ((P >= 0) & (P <= 1)).all()
        assert np.allclose(P.sum(axis=1), 1)
    lam = p["lambda_target_dir"].dropna()
    assert ((lam >= 0) & (lam <= 1)).all()


def test_class_order_mapping(fast_settings):
    """La colonna p_up è la probabilità della classe 2 (rialzo) anche se sklearn ordina le classi."""
    lab, p = _frame(fast_settings)
    lab2 = lab.copy()
    lab2["target_dir"] = lab2["target_dir"].map({0: 2, 1: 1, 2: 0})   # scambio rialzo e ribasso
    p2 = M.walk_forward(lab2, "target_dir", M.DIR_CLASSES, 10, fast_settings)
    ok = p["p_up_raw"].notna() & p2["p_down_raw"].notna()
    assert np.allclose(p.loc[ok, "p_up_raw"], p2.loc[ok, "p_down_raw"], atol=1e-6)


def test_missing_class_gives_no_prediction(fast_settings):
    lab, _ = _frame(fast_settings)
    lab = lab.copy()
    lab.loc[lab["target_dir"] == 1, "target_dir"] = 2      # la classe "laterale" non esiste mai
    p = M.walk_forward(lab, "target_dir", M.DIR_CLASSES, 10, fast_settings)
    assert p[M.DIR_COLS + [c + "_raw" for c in M.DIR_COLS]].isna().all().all()


def test_evaluation_requires_sufficient_sample(fast_settings):
    lab, p = _frame(fast_settings)
    strict = Settings(min_independent_periods=10_000)
    ev = M.evaluate(p, lab["target_dir"], M.DIR_CLASSES, M.DIR_COLS, 10, strict)
    assert "insufficiente" in ev["status"] and "brier" not in ev
    ev2 = M.evaluate(p, lab["target_dir"], M.DIR_CLASSES, M.DIR_COLS, 10, fast_settings)
    assert {"brier", "log_loss", "bss", "subperiods", "calibration_bins"} <= set(ev2)
    for rows in ev2["calibration_bins"].values():
        assert all(r["n"] >= fast_settings.min_bin_count for r in rows)


def test_probability_view_gating():
    row = pd.Series({"p_down": .2, "p_flat": .3, "p_up": .5,
                     "p_down_clim": .3, "p_flat_clim": .4, "p_up_clim": .3})
    labels = ["Ribasso", "Laterale", "Rialzo"]
    shown = M.probability_view(row, {"display_ok": True}, M.DIR_COLS, labels)
    assert shown["source"].startswith("modello") and shown["values"]["Rialzo"] == .5
    fallback = M.probability_view(row, {"display_ok": False, "status": "x"}, M.DIR_COLS, labels)
    assert fallback["source"].startswith("frequenza storica") and fallback["values"]["Rialzo"] == .3
    empty = M.probability_view(pd.Series({c: np.nan for c in row.index}), {"display_ok": True}, M.DIR_COLS, labels)
    assert empty["values"] is None


def test_reversal_target_definition():
    idx = pd.bdate_range("2020-01-01", periods=60)
    close = pd.Series(np.r_[np.linspace(100, 120, 40), np.linspace(120, 100, 20)], index=idx)
    f = pd.DataFrame({"close": close})
    lab = E.add_labels(f, horizon=5, threshold=0.01, trend_lookback=20)
    assert lab["target_rev"].iloc[39] == 1        # trend su 20 sedute in salita, poi discesa > 1%
    assert lab["target_rev"].iloc[30] == 0        # trend in salita che continua
    assert lab["target_rev"].iloc[:20].isna().all()
