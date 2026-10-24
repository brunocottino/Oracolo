"""Test rapido su dati sintetici:  python tests/test_smoke.py
(compatibile anche con pytest, se installato)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401

import db  # noqa: E402
import engine  # noqa: E402
import portfolio  # noqa: E402

db.init()


def check(o):
    e, p = o["ensemble"], o["plan"]
    assert 0 <= e["p_up"] <= 1
    assert e["sigma"] > 0
    assert p["signal"] in engine.SIGNALS
    q = p["quantiles"]
    assert q["q05"] < q["q25"] < q["q50"] < q["q75"] < q["q95"]
    for pl in (p["plan_market"], p["plan_limit"]):
        assert pl["stop"] < pl["entry"] < pl["target"]
        assert abs(pl["p_target_first"] + pl["p_stop_first"] + pl["p_neither"] - 1) < 1e-6
        assert pl["ev_net"] < pl["ev"]
    assert 0 <= p["position_size"] <= 0.10
    assert 0 <= p["ref"] <= 1
    # un solo modello di base; tutti gli altri agenti sono informativi a peso 0
    base = [a for a in o["agents"] if a["family"] == "base"]
    assert len(base) == 1 and base[0]["weight"] == 1.0
    assert all(a["weight"] == 0 for a in o["agents"] if a["family"] != "base")
    assert len(o["agents"]) >= 6, [a["name"] for a in o["agents"]]
    assert o["story"] and "priced" in o and "not_priced" in o
    # senza test del Laboratorio l'interruttore impone NESSUN SEGNALE
    if o["panel"].get("state") != "attivo":
        assert p["signal"] == "NESSUN SEGNALE" and p["position_size"] == 0
    json.dumps(o)


def test_stock():
    o = engine.analyze("AAPL")
    check(o)
    assert o["horizon_days"] == 31
    assert any(a["family"] == "fondamentale" for a in o["agents"])
    assert o["priced"]["from_options"] is True
    assert o["priced"]["rdcf"]["g_implied"] is not None


def test_stock_italy_no_options():
    o = engine.analyze("ENI.MI")
    check(o)
    assert o["priced"]["from_options"] is False
    assert "nessuna opzione" in o["priced"]["source"]
    assert o["plan"]["cost_round_trip"] > 0.003          # include la Tobin tax


def test_index():
    o = engine.analyze("^GSPC")
    check(o)
    assert o["horizon_days"] == 63
    assert not any(a["family"] == "fondamentale" for a in o["agents"])
    assert o["priced"]["vix"]["level"] > 0


def test_portfolio():
    db.holding_add("ENI.MI", 100, 10.0)
    db.holding_add("MSFT", 10, 300.0)
    s = portfolio.snapshot()
    assert s["total_eur"] > 0 and s["risk"]["vol_annual"] > 0


if __name__ == "__main__":
    f = common.run_module(globals())
    print("OK" if not f else "ERRORI")
    sys.exit(1 if f else 0)
