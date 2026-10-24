"""Configurazione centrale di Oracolo.

Tutti i parametri numerici che influenzano previsioni e segnali stanno qui,
così si possono tarare senza toccare il codice degli agenti.
"""
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ORACOLO_DB", os.path.join(BASE_DIR, "data", "oracolo.sqlite"))

# DEMO=1 usa dati sintetici (utile offline o per test). In produzione lasciare 0.
DEMO = os.environ.get("ORACOLO_DEMO", "0") == "1"

# Orizzonti di previsione in giorni di borsa
HORIZON_STOCK_CAL_DAYS = 45            # azioni: 45 giorni di calendario
HORIZON_STOCK = 31                     # ~ 45 giorni di calendario
HORIZON_INDEX_CAL_DAYS = 91            # indici: 3 mesi
HORIZON_INDEX = 63                     # ~ 3 mesi di borsa
TRADING_DAYS = 252

# Ipotesi di mercato (stile CFA): premio per il rischio azionario e risk-free
EQUITY_RISK_PREMIUM = 0.05             # 5% annuo
DEFAULT_RISK_FREE = 0.04               # usato se non si riesce a leggere ^TNX
PRIOR_ANNUAL_DRIFT = 0.07              # rendimento atteso "a priori" di un'azione media

# Monte Carlo
MC_PATHS = 10000
RANDOM_SEED = 42

# Regole del segnale (vedi engine.trade_plan). Il riferimento è
# max(frequenza storica, probabilità implicita nel mercato).
SIGNAL_RULES = {
    "buy_edge": 0.05,          # COMPRA: p calibrata >= riferimento + 5 punti
    "accumulate_edge": 0.03,   # ACCUMULA SU DEBOLEZZA: >= riferimento + 3 punti
    "sell_edge": 0.05,         # ALLEGGERISCI: p <= riferimento - 5 punti
    "top_decile": 0.90,        # COMPRA solo nel decile migliore dell'alfa previsto
    "kelly_fraction": 0.25,    # quota di Kelly usata (1/4 Kelly)
    "kelly_shrink": 0.5,       # la probabilità usata da Kelly è avvicinata a metà strada al riferimento
    "max_position": 0.10,      # posizione massima suggerita (10% del portafoglio)
    "atr_stop_mult": 2.5,      # stop = ingresso - 2,5 ATR
}

# Costi di transazione (per lato, in frazione del controvalore)
COSTS = {
    "commission": 0.0010,      # commissione 0,10% per lato
    "half_spread": 0.0005,     # metà spread 0,05% (large cap)
    "tobin_it": 0.0010,        # Tobin tax italiana 0,1% sugli acquisti di titoli .MI
}

# Cache prezzi (secondi)
PRICE_CACHE_TTL = 6 * 3600
EVENTS_CACHE_TTL = 20 * 3600           # annunci utili e giudizi analisti: al massimo 1 aggiornamento al giorno

# --------------------------------------------------------------------------
# Banco di prova (Laboratorio): panel walk-forward
# --------------------------------------------------------------------------
LAB = {
    "origin_step": int(os.environ.get("ORACOLO_LAB_STEP", "5")),   # una origine ogni 5 sedute
    "min_train": 756,          # almeno 3 anni di storia prima della prima previsione
    "retrain": 63,             # riaddestramento ogni 63 sedute
    "embargo": 10,             # sedute di "pausa" tra fine addestramento e test
    "holdout": 504,            # ultime 2 annate: mai usate per scegliere, solo come interruttore
    "warmup": 252,             # sedute necessarie per calcolare le misure (12 mesi)
    "min_names": 15,           # minimo numero di titoli per data nel panel azioni
    "logit_C": 0.1,            # regolarizzazione L2 della logistica
    "hgb": {"max_depth": 3, "max_iter": 200, "learning_rate": 0.03,
            "min_samples_leaf": 500, "l2_regularization": 1.0},
    "run_challenger": os.environ.get("ORACOLO_LAB_HGB", "1") == "1",
    "ablation_retrain": 126,   # nell'ablation si riaddestra ogni 126 sedute (più rapido)
    "bootstrap": 1000,
    "isotonic_min": 2000,      # isotonica solo con almeno 2.000 previsioni passate, altrimenti Platt
    "fdr": 0.10,               # Benjamini-Hochberg al 10%
    "t_lit": 2.0,              # soglia t per fattori con letteratura
    "t_new": 3.0,              # soglia t per combinazioni nuove / senza letteratura
    "max_neg_year_share": 0.40,
    # criterio di successo globale
    "min_ic": 0.02, "min_ic_t": 2.0, "max_ece": 0.03,
    # promozione dei dati di "classe B" (istantanee raccolte ogni notte)
    "promo_periods": 12,
}
# Grandi capitalizzazioni: tutto l'universo predefinito (metà spread 0,05%)
LARGE_CAP_ALL = True

# Generatore demo: segnale noto inserito per i test di validazione.
#   ORACOLO_DEMO_SIGNAL = "sue" (default) | "none"
#   ORACOLO_DEMO_IC     = IC atteso del segnale inserito (default 0,04)
DEMO_SIGNAL = os.environ.get("ORACOLO_DEMO_SIGNAL", "sue")
DEMO_SIGNAL_IC = float(os.environ.get("ORACOLO_DEMO_IC", "0.04"))
DEMO_YEARS = int(os.environ.get("ORACOLO_DEMO_YEARS", "16"))
DATA_DIR = os.path.dirname(DB_PATH)
MODEL_PATH = os.environ.get("ORACOLO_MODEL", os.path.join(DATA_DIR, "lab_model.pkl"))

# Scanner automatico: ora (UTC) della scansione notturna
SCAN_HOUR_UTC = int(os.environ.get("ORACOLO_SCAN_HOUR", "22"))
AUTO_SCAN = os.environ.get("ORACOLO_AUTO_SCAN", "1") == "1"
