"""Esecuzione end-to-end con dati SINTETICI iniettati (solo test): pipeline, CLI, dashboard."""
import json

import pytest

from ipb import cli, pipeline
from ipb.data import DataError
from synthetic import make_market


@pytest.fixture
def fake_loader(monkeypatch):
    monkeypatch.setattr(pipeline, "load_market", lambda cfg, start, end=None, use_cache=True: make_market(1300, 31))


def test_pipeline_summary_is_json_and_versioned(fake_loader):
    res = pipeline.run("S&P 500", "2010-01-01", horizon=10)
    s = res.summary()
    json.dumps(s)
    assert s["data"]["synthetic"] is True
    assert s["versions"]["feature_version"] and s["versions"]["settings_hash"]
    assert s["latest"]["probabilities_direction"]["source"]


def test_cli_exports(fake_loader, tmp_path, capsys):
    assert cli.main(["--market", "S&P 500", "--horizon", "5", "--out", str(tmp_path)]) == 0
    names = {p.name for p in tmp_path.iterdir()}
    assert {"S_P_500_h5_results.csv", "S_P_500_h5_backtest.csv", "S_P_500_h5_metrics.json"} <= names
    assert "SINTETICI" in capsys.readouterr().out


def test_cli_data_error_exit_code(monkeypatch, tmp_path, capsys):
    def fail(*a, **k):
        raise DataError("Download fallito per ^GSPC: test")
    monkeypatch.setattr(pipeline, "load_market", fail)
    assert cli.main(["--out", str(tmp_path)]) == 2
    assert "ERRORE DATI" in capsys.readouterr().err


def test_dashboard_runs(fake_loader):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("../app.py", default_timeout=240)
    at.run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown) + " ".join(str(w.value) for w in at.warning)
    assert "SINTETICI" in text
    assert any("IPB" in m.label for m in at.metric)


def test_dashboard_shows_provider_error(monkeypatch):
    from streamlit.testing.v1 import AppTest

    def fail(*a, **k):
        raise DataError("Download fallito per ^GSPC: provider giù")
    monkeypatch.setattr(pipeline, "load_market", fail)
    at = AppTest.from_file("../app.py", default_timeout=120)
    at.run()
    at.button[0].click().run()
    assert any("provider giù" in e.value for e in at.error)
    assert not at.metric
