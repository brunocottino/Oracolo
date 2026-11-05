# Roadmap Oracolo: solo fonti gratuite, senza registrazioni né chiavi

Regola fissa: niente abbonamenti, account, chiavi API o siti a cui iscriversi.
Si usano solo download pubblici senza login.

## Fase 0: avvio sui dati veri
- [x] `python tests/run_all.py` (deve passare).
- [x] `python -m research --fast` con Yahoo: annota stato, IC (t), BSS ed ECE in `NOTE_RISULTATI.md`.

## Fase 1b: finanza comportamentale (fonti senza chiave)
- [x] Capital gains overhang (Grinblatt-Han) da prezzi e volumi, tutti i mercati.
- [x] Valore prospect theory (Barberis-Mukherjee-Wang) sugli ultimi 60 mesi.
- [x] Choc di attenzione dalle visite Wikipedia nella lingua del mercato (`sources/wiki.py`).
- [x] Lazy prices: somiglianza dei testi 10-K/10-Q/20-F da SEC EDGAR (`sources/edgar.py`).
- [x] Pressione comportamentale cgo x attenzione (ipotesi nuova, t ≥ 3).
- [ ] Allargare l'universo (più titoli medi europei ed emergenti) per avere potenza statistica.
- [ ] Ipotesi pre-registrata "attenzione = momentum a breve" da testare solo su dati futuri.

## Hosting gratuito
- [x] Dockerfile e GitHub Action per Hugging Face Space privato (`AVVIO_HF.md`).
- [ ] Creare account, Space e segreti (lo fa Bruno, 10 minuti).

## Fase 1: fonti pubbliche senza chiave (`sources/`, con cache SQLite e ripiego su Yahoo)
- [x] **FRED via CSV pubblico, senza chiave** (`sources/fred.py`, in OGGI.md; il Lab resta su Yahoo finché non si confrontano gli storici): `https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS` (anche VXVCLS, DGS10, DTB3). Sostituisce ^VIX, ^VIX3M, ^TNX e ^IRX con storico completo.
- [x] **SEC EDGAR companyfacts, senza chiave** (`sources/sec_eps.py`, testato il 05/11/2026: t 1,14, spento, vedi `PREREG_SUE_SEC.md`): `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. Serve solo un'intestazione User-Agent fissa nel codice, nessuna registrazione. Ricava EPS trimestrali USA con la data di deposito → SUE point-in-time con storico lungo.
- [x] **Stooq CSV, senza chiave** (`sources/stooq.py` pronto, ma da novembre 2026 Stooq blocca i download automatici con una pagina anti-robot: controllo spento in `aggiorna.py`) (`https://stooq.com/q/d/l/?s=eni.it&i=d`): seconda fonte prezzi, controllo incrociato con Yahoo. Avvisa se lo scarto supera l'1%.
- [x] **BCE Data Portal, senza chiave** (`sources/ecb.py`: €STR e Stato AAA 10 anni in OGGI.md; da collegare come tasso privo di rischio nel Lab) (API SDMX in CSV): €STR e rendimenti dei titoli di Stato dell'area euro → tasso privo di rischio per i titoli europei.
- [x] Per ogni fonte: un test con una risposta salvata, che gira senza rete (`tests/test_behavior.py`).

## Fase 2: robustezza con i dati gratuiti
- [ ] Survivorship bias: non eliminabile gratis. Va dichiarato nel Lab; si misura il banco di prova anche solo sugli ultimi 10 anni.
- [ ] Classe B: la raccolta notturna (stime, opzioni, short via yfinance) parte subito; dopo circa 18 mesi si verifica la regola di promozione.

## Fase 3: uso pratico (vale anche con modello spento)
- [x] Forchetta attesa 80% a 45 e 90 giorni, calibrata fuori campione (copertura 77-81,5%, `lab/band_test.py`, `bands.py`).
- [x] Scenario mediano, semaforo "movimento normale/anomalo", forchetta del portafoglio in euro, pagina "Cosa dicono i dati".
- [x] ETF UCITS al posto degli ETF USA nell'universo.
- [x] Peso della posizione a rischio fisso: stop a 2,5 ATR costa lo 0,5% del portafoglio (max 10%).
- [ ] Classifica dei titoli con scostamenti di peso al massimo di ±2%, non segnali singoli.
- [ ] Veto: niente nuovi acquisti se crescita implicita o probabilità implicita sono nel decile alto.
- [ ] Diario: decisione registrata prima dell'esecuzione e non modificabile, più portafoglio paper contro ACWI (yfinance: `ACWI`). Scheda "Diario".
- [ ] Schermata da 10 secondi: semaforo, 3 avvisi, risultato contro l'ETF. Fatti semaforo e 3 avvisi in cima a OGGI.md; manca il risultato contro l'ETF (serve il Diario).
- [ ] Dati europei marcati "qualità bassa", esclusi dalla classifica.

## Da NON fare
Fonti a pagamento o con registrazione; Qlib, Chronos/TimesFM, vectorbt, backtrader, PyPortfolioOpt, PyMC.
