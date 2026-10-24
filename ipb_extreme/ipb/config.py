"""Configurazione versionata: mercati, soglie, parametri del modello.

Ogni cambiamento a feature, soglie o modello deve aggiornare la versione corrispondente:
le versioni finiscono nei file esportati (metrics.json) insieme a tutti i parametri.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

FEATURE_VERSION = "2.0.0"   # fattori IPB + 4 punteggi (pressure, expectation, reaction, crowding)
MODEL_VERSION = "2.0.0"     # logistica L2 walk-forward + calibrazione per shrinkage verso la frequenza storica
THRESHOLDS_VERSION = "2.0.0"


@dataclass(frozen=True)
class MarketConfig:
    label: str
    index_ticker: str
    volume_proxy: str | None
    vol_ticker: str | None = None
    # Sedute di ritardo per le serie ausiliarie che chiudono DOPO l'indice:
    # un dato non noto alla chiusura dell'indice al giorno t non può entrare nel segnale di t.
    volume_proxy_lag: int = 0
    vol_lag: int = 0
    notes: str = ""


MARKETS = {
    # VIX chiude alle 16:15 ET, l'S&P 500 alle 16:00: si usa il VIX del giorno prima.
    "S&P 500": MarketConfig("S&P 500", "^GSPC", "SPY", "^VIX", volume_proxy_lag=0, vol_lag=1,
                            notes="VIX ritardato di 1 seduta (chiude 15 minuti dopo l'indice)."),
    "Nasdaq-100": MarketConfig("Nasdaq-100", "^NDX", "QQQ", "^VXN", volume_proxy_lag=0, vol_lag=1,
                               notes="VXN ritardato di 1 seduta (chiude dopo l'indice)."),
    # FEZ ed EWI sono ETF quotati negli USA: chiudono ore dopo l'indice europeo.
    # ^V2TX (VSTOXX) non è disponibile su Yahoo (verificato il 24/10/2026: "possibly delisted").
    "Euro Stoxx 50": MarketConfig("Euro Stoxx 50", "^STOXX50E", "FEZ", None, volume_proxy_lag=1, vol_lag=0,
                                  notes="Volume proxy FEZ (USA) ritardato di 1 seduta; VSTOXX non disponibile su Yahoo."),
    "FTSE MIB": MarketConfig("FTSE MIB", "FTSEMIB.MI", "EWI", None, volume_proxy_lag=1, vol_lag=0,
                             notes="Volume proxy EWI (USA) ritardato di 1 seduta; nessun indice di volatilità locale."),
}


@dataclass(frozen=True)
class Settings:
    # Soglie dei punteggi
    pressure_band: float = 25.0          # |IPB| oltre questa soglia = rialzista/ribassista
    ipb_long: float = 20.0               # strategia long/flat: IPB > soglia
    # Target
    horizons: tuple = (5, 10, 20)
    default_horizon: int = 10
    default_threshold: float = 0.015     # ±1,5% sull'orizzonte = rialzo/ribasso, altrimenti laterale
    trend_lookback: int = 20             # inversione = movimento contrario al trend delle ultime 20 sedute
    # Modello walk-forward
    min_train: int = 750
    refit_every: int = 20
    C: float = 0.5
    min_feature_coverage: float = 0.9
    # Calibrazione e metriche
    min_calibration_rows: int = 250
    min_independent_periods: int = 50    # sotto questa soglia niente metriche aggregate
    min_bin_count: int = 30              # bin di calibrazione mostrati solo con >= 30 osservazioni
    max_ece_display: float = 0.05        # probabilità mostrate solo se ECE <= 5 punti...
    min_bss_display: float = 0.0         # ...e se battono la frequenza storica
    # Backtest
    default_cost_bps: float = 5.0
    execution_lag: int = 1               # 1 = segnale alla chiusura di t, posizione sul rendimento di t+1
    sensitivity_costs: tuple = (0.0, 5.0, 10.0, 20.0)
    sensitivity_ipb: tuple = (10.0, 20.0, 30.0)
    sensitivity_lags: tuple = (1, 2)
    sensitivity_thresholds: tuple = (0.01, 0.015, 0.025)
    extra: dict = field(default_factory=dict)


DEFAULT = Settings()


def version_info(settings: Settings = DEFAULT) -> dict:
    s = asdict(settings)
    blob = json.dumps(s, sort_keys=True, default=str).encode()
    return {
        "feature_version": FEATURE_VERSION,
        "model_version": MODEL_VERSION,
        "thresholds_version": THRESHOLDS_VERSION,
        "settings_hash": hashlib.sha256(blob).hexdigest()[:12],
        "settings": s,
    }
