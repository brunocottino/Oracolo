"""Esecuzione completa: dati -> fattori -> target -> probabilità walk-forward -> valutazione -> backtest."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import backtest as B
from . import engine as E
from . import model as M
from .config import DEFAULT, MARKETS, Settings, version_info
from .data import load_market


@dataclass
class Result:
    market: str
    horizon: int
    threshold: float
    cost_bps: float
    frame: pd.DataFrame
    bt_metrics: pd.DataFrame
    bt_info: dict
    eval_dir: dict
    eval_rev: dict
    latest: dict
    warnings: list = field(default_factory=list)
    sensitivity_bt: pd.DataFrame | None = None
    sensitivity_prob: pd.DataFrame | None = None

    def summary(self) -> dict:
        def clean(x):
            if isinstance(x, dict):
                return {k: clean(v) for k, v in x.items()}
            if isinstance(x, (list, tuple)):
                return [clean(v) for v in x]
            if isinstance(x, (np.floating, float)):
                return None if not np.isfinite(x) else float(x)
            if isinstance(x, np.integer):
                return int(x)
            return x
        out = {
            "market": self.market, "horizon": self.horizon, "threshold": self.threshold,
            "cost_bps": self.cost_bps, "versions": version_info(),
            "data": {"first": str(self.frame.index[0].date()), "last": str(self.frame.index[-1].date()),
                     "rows": len(self.frame), "synthetic": bool(self.frame.attrs.get("synthetic", False))},
            "warnings": self.warnings, "latest": self.latest,
            "evaluation_direction": self.eval_dir, "evaluation_reversal": self.eval_rev,
            "backtest": {"info": self.bt_info, "metrics": self.bt_metrics.to_dict(orient="records")},
        }
        if self.sensitivity_prob is not None:
            out["sensitivity_probabilities"] = self.sensitivity_prob.to_dict(orient="records")
        if self.sensitivity_bt is not None:
            out["sensitivity_backtest"] = self.sensitivity_bt.to_dict(orient="records")
        return clean(out)


def model_frame(feats: pd.DataFrame, horizon: int, threshold: float, settings: Settings = DEFAULT):
    lab = E.add_labels(feats, horizon, threshold, settings.trend_lookback)
    pdir = M.walk_forward(lab, "target_dir", M.DIR_CLASSES, horizon, settings)
    prev = M.walk_forward(lab, "target_rev", M.REV_CLASSES, horizon, settings)
    sdir = M.walk_forward(lab, "target_dir", M.DIR_CLASSES, horizon, settings, M.SIMPLE_FEATURES)
    srev = M.walk_forward(lab, "target_rev", M.REV_CLASSES, horizon, settings, M.SIMPLE_FEATURES)
    frame = lab.join(pdir).join(prev)
    ev_dir = M.evaluate(frame, frame["target_dir"], M.DIR_CLASSES, M.DIR_COLS, horizon, settings, sdir)
    ev_rev = M.evaluate(frame, frame["target_rev"], M.REV_CLASSES, M.REV_COLS, horizon, settings, srev)
    return frame, ev_dir, ev_rev


def probability_sensitivity(feats: pd.DataFrame, settings: Settings = DEFAULT) -> pd.DataFrame:
    rows = []
    for h in settings.horizons:
        for th in settings.sensitivity_thresholds:
            _, ev, er = model_frame(feats, h, th, settings)
            for name, e in (("direzione", ev), ("inversione", er)):
                rows.append({"target": name, "horizon": h, "threshold": th,
                             "independent_periods": e.get("independent_periods"),
                             "bss": e.get("bss"), "bss_vs_simple": e.get("bss_vs_simple_benchmark"),
                             "log_loss": e.get("log_loss"),
                             "log_loss_climatology": e.get("log_loss_climatology"),
                             "ece_max": e.get("ece_max"), "display_ok": e.get("display_ok", False),
                             "status": e.get("status")})
    return pd.DataFrame(rows)


def run(market: str, start: str, end: str | None = None, horizon: int = DEFAULT.default_horizon,
        threshold: float = DEFAULT.default_threshold, cost_bps: float = DEFAULT.default_cost_bps,
        settings: Settings = DEFAULT, raw: pd.DataFrame | None = None, use_cache: bool = True,
        with_sensitivity: bool = False) -> Result:
    if horizon not in settings.horizons:
        raise ValueError(f"Orizzonte {horizon} non previsto: scegliere tra {settings.horizons}")
    if raw is None:
        raw = load_market(MARKETS[market], start, end, use_cache=use_cache)
    feats = E.build_features(raw)
    frame, ev_dir, ev_rev = model_frame(feats, horizon, threshold, settings)
    frame.attrs.update(raw.attrs)
    bt, bt_m, bt_info = B.run_backtest(frame, cost_bps=cost_bps, settings=settings)
    last = frame.iloc[-1]
    latest = E.latest_signal(frame, settings.pressure_band)
    latest["probabilities_direction"] = M.probability_view(last, ev_dir, M.DIR_COLS,
                                                           [M.DIR_NAMES[c] for c in M.DIR_CLASSES])
    latest["probabilities_reversal"] = M.probability_view(last, ev_rev, M.REV_COLS, ["Nessuna inversione", "Inversione"])
    res = Result(market, horizon, threshold, cost_bps, bt, bt_m, bt_info, ev_dir, ev_rev, latest,
                 list(raw.attrs.get("warnings", [])))
    if with_sensitivity:
        res.sensitivity_bt = B.sensitivity(frame, settings)
        res.sensitivity_prob = probability_sensitivity(feats, settings)
    return res
