"""Riga di comando: calcola ed esporta CSV e metriche JSON.

    python -m ipb.cli --market "S&P 500" --start 2005-01-01 --horizon 10 --threshold 0.015 \
        --cost-bps 5 --out risultati --sensitivity
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT, MARKETS
from .data import DataError
from .pipeline import run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPB Extreme: calcolo ed export (prototipo di ricerca)")
    ap.add_argument("--market", default="S&P 500", choices=list(MARKETS))
    ap.add_argument("--start", default="2005-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--horizon", type=int, default=DEFAULT.default_horizon, choices=list(DEFAULT.horizons))
    ap.add_argument("--threshold", type=float, default=DEFAULT.default_threshold)
    ap.add_argument("--cost-bps", type=float, default=DEFAULT.default_cost_bps)
    ap.add_argument("--out", default="risultati")
    ap.add_argument("--sensitivity", action="store_true", help="sensibilità a orizzonti, soglie, costi e ritardi")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args(argv)
    try:
        res = run(a.market, a.start, a.end, a.horizon, a.threshold, a.cost_bps,
                  use_cache=not a.no_cache, with_sensitivity=a.sensitivity)
    except DataError as e:
        print(f"ERRORE DATI: {e}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "_" for ch in a.market).strip("_")
    res.frame.to_csv(out / f"{slug}_h{a.horizon}_results.csv")
    res.bt_metrics.to_csv(out / f"{slug}_h{a.horizon}_backtest.csv", index=False)
    if res.sensitivity_bt is not None:
        res.sensitivity_bt.to_csv(out / f"{slug}_sensitivity_backtest.csv", index=False)
        res.sensitivity_prob.to_csv(out / f"{slug}_sensitivity_probabilities.csv", index=False)
    with open(out / f"{slug}_h{a.horizon}_metrics.json", "w", encoding="utf-8") as f:
        json.dump(res.summary(), f, ensure_ascii=False, indent=2)
    s = res.summary()
    print(f"{a.market}: dati {s['data']['first']} -> {s['data']['last']} ({s['data']['rows']} sedute)")
    for w in res.warnings:
        print("AVVISO:", w)
    lt = s["latest"]
    print(f"IPB {lt['ipb']} ({lt['pressure']}), Expectation Gap {lt['expectation_gap']}, "
          f"Reaction Anomaly {lt['reaction_anomaly']}, Crowding & Fragility {lt['crowding_fragility']}, "
          f"rischio inversione (euristico) {lt['reversal_risk_score']}")
    for k in ("evaluation_direction", "evaluation_reversal"):
        e = s[k]
        print(f"{k}: {e.get('status')}; periodi indipendenti {e.get('independent_periods')}, "
              f"BSS {e.get('bss')}, BSS vs benchmark semplice {e.get('bss_vs_simple_benchmark')}, log-loss {e.get('log_loss')} vs storica {e.get('log_loss_climatology')}, "
              f"ECE max {e.get('ece_max')}")
    print("Probabilità direzione:", lt["probabilities_direction"])
    print(res.bt_metrics[["strategy", "annualized_return", "sharpe_rf0", "max_drawdown", "time_in_market"]]
          .to_string(index=False))
    print(f"File scritti in {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
