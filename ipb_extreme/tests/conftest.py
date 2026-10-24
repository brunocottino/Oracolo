import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ipb.config import Settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Ogni test usa una cache vuota: nessun test legge dati reali scaricati."""
    from ipb import data
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path / "cache")


@pytest.fixture
def fast_settings():
    # parametri ridotti solo per velocità dei test; la logica temporale è la stessa
    return Settings(min_train=300, refit_every=20, min_calibration_rows=60, min_independent_periods=20)
