# Roadmap Oracolo: solo fonti gratuite, senza registrazioni né chiavi

Regola fissa: niente abbonamenti, account, chiavi API o siti a cui iscriversi.
Si usano solo download pubblici senza login.

## Fase 0: avvio sui dati veri
- [x] `python tests/run_all.py` (deve passare).
- [x] `python -m research --fast` con Yahoo: annota stato, IC (t), BSS ed ECE in `NOTE_RISULTATI.md`.

## Fase 1: fonti pubbliche senza chiave (`sources/`, con cache SQLite e ripiego su Yahoo)
- [ ] **FRED via CSV pubblico, senza chiave:** `https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS` (anche VXVCLS, DGS10, DTB3). Sostituisce ^VIX, ^VIX3M, ^TNX e ^IRX con storico completo.
- [ ] **SEC EDGAR companyfacts, senza chiave:** `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. Serve solo un'intestazione User-Agent fissa nel codice, nessuna registrazione. Ricava EPS trimestrali USA con la data di deposito → SUE point-in-time con storico lungo.
- [ ] **Stooq CSV, senza chiave** (`https://stooq.com/q/d/l/?s=eni.it&i=d`): seconda fonte prezzi, controllo incrociato con Yahoo. Avvisa se lo scarto supera l'1%.
- [ ] **BCE Data Portal, senza chiave** (API SDMX in CSV): €STR e rendimenti dei titoli di Stato dell'area euro → tasso privo di rischio per i titoli europei.
- [ ] Per ogni fonte: un test con una risposta salvata, che gira senza rete.

## Fase 2: robustezza con i dati gratuiti
- [ ] Survivorship bias: non eliminabile gratis. Va dichiarato nel Lab; si misura il banco di prova anche solo sugli ultimi 10 anni.
- [ ] Classe B: la raccolta notturna (stime, opzioni, short via yfinance) parte subito; dopo circa 18 mesi si verifica la regola di promozione.

## Fase 3: uso pratico (vale anche con modello spento)
- [ ] Classifica dei titoli con scostamenti di peso al massimo di ±2%, non segnali singoli.
- [ ] Peso della posizione = 0,5% di rischio / volatilità; stop a 2,5 ATR.
- [ ] Veto: niente nuovi acquisti se crescita implicita o probabilità implicita sono nel decile alto.
- [ ] Diario: decisione registrata prima dell'esecuzione e non modificabile, più portafoglio paper contro ACWI (yfinance: `ACWI`). Scheda "Diario".
- [ ] Schermata da 10 secondi: semaforo, 3 avvisi, risultato contro l'ETF.
- [ ] Dati europei marcati "qualità bassa", esclusi dalla classifica.

## Da NON fare
Fonti a pagamento o con registrazione; Qlib, Chronos/TimesFM, vectorbt, backtrader, PyPortfolioOpt, PyMC.
