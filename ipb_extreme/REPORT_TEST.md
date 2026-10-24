# Report dei test — IPB Extreme (24/10/2026)

Ambiente: Linux, Python 3.13.17, pandas 3.1.0, numpy 2.5.4, scikit-learn 1.9.1, yfinance 1.7.0,
streamlit 1.66.1, plotly 7.1.0, pytest 9.1.1. **Python 3.11 non verificato** (non disponibile qui;
il codice non usa sintassi successiva alla 3.10).

## 1. Problemi trovati nel codice originale (riprodotti su dati reali S&P 500)
| # | Problema | Effetto | Correzione |
|---|---|---|---|
| 1 | `LogisticRegression(multi_class=...)` rimosso in scikit-learn ≥ 1.7 | crash del modello (TypeError) | parametro tolto |
| 2 | `class_weight="balanced"` | probabilità non più frequenze | tolto; calibrazione causale |
| 3 | IPB con `fillna(0)` | IPB valorizzato dalla prima seduta, prima della MA200 | NaN fino all'avvio completo |
| 4 | target futuro mancante → `default=1` | ultime H sedute etichettate "laterale" | NaN se non osservabile |
| 5 | scelta della formula del sentiment su `notna().sum()` dell'intero storico | look-ahead | scelta riga per riga |
| 6 | VIX/VXN (chiusura 16:15) e FEZ/EWI (sedute USA) usati lo stesso giorno dell'indice | dati non noti alla chiusura di t | ritardo di 1 seduta per serie |
| 7 | volume del proxy riallineato senza controllo, proxy fallito → NaN silenzioso | errori nascosti | avvisi espliciti, nessun ffill del volume |
| 8 | backtest: strategia flat nel periodo di avvio contro buy & hold sempre investito | confronto distorto | finestra comune |
| 9 | `_download`: MultiIndex gestito solo con livello 0; nessun retry, nessuna cache | errori con layout diversi o limiti | normalizzazione robusta, 3 tentativi, cache con TTL |
| 10 | `^V2TX` non esiste su Yahoo | download fallito a ogni avvio | tolto dalla configurazione, dichiarato |

Bug introdotto e corretto durante il lavoro: la copertura minima delle feature (90%) era misurata su
tutta la finestra di training, quindi le feature venivano scartate per migliaia di sedute. Ora è misurata
sulle ultime `min_train` righe note. Lo hanno trovato i test.

## 2. Test automatici eseguiti: `python -m pytest` → **36 superati, 0 falliti** (30 s)
Dati sintetici solo in `tests/synthetic.py`, marcati `attrs["synthetic"] = True`; ogni test usa una cache vuota.

- `test_lookahead.py` (9): fattori invariati troncando i dati a t (con e senza indice di volatilità),
  perturbazione del futuro, IPB nullo prima della MA200, target NaN se non osservabili, probabilità
  walk-forward invariate al troncamento, target non ancora osservabili alterati senza effetto
  (con controllo che il test sia sensibile), frequenza storica solo con esiti noti, ritardo delle serie ausiliarie.
- `test_backtest.py` (5): posizione dalla seduta successiva, lag 2, lag 0 vietato, costo d'ingresso,
  costi esatti giorno per giorno, finestra comune, griglia di sensibilità.
- `test_probabilities.py` (6): probabilità in [0,1] con somma 1, ordine delle classi, classe mancante →
  nessuna previsione, metriche solo con campione sufficiente e bin con ≥ 30 osservazioni, cosa si
  mostra (modello / frequenza storica / non disponibile), definizione del target di inversione.
- `test_data.py` (11): MultiIndex nei due layout e piatto, fuso orario, date duplicate e prezzi
  invalidi, risposta con ticker sbagliati, ticker fallito con messaggio esplicito, 3 tentativi con
  limite di richieste, cache e ripiego su cache scaduta dichiarato, date mancanti nel proxy,
  proxy e indice di volatilità falliti dichiarati, errore se fallisce l'indice, storico troppo corto.
- `test_pipeline_cli_app.py` (5): riepilogo JSON versionato, export della CLI, codice d'uscita 2 su
  errore dati, dashboard (Streamlit AppTest) completa, dashboard con errore del provider.

## 3. Esecuzioni su dati reali (Yahoo, 24/10/2026, storico dal 2005, H = 10, soglia ±1,5%, 5 bps)
Numeri copiati dall'output della CLI; nessun valore stimato a mano.

| Mercato | BSS direzione | vs benchmark semplice | ECE max | Probabilità mostrate | BSS inversione | vs benchmark | Sharpe IPB | Sharpe B&H | Sharpe MA100 |
|---|---|---|---|---|---|---|---|---|---|
| S&P 500 | +2,55% | +0,64% | 3,6 | sì | +6,82% | -0,34% | -0,04 | 0,76 | 0,56 |
| Nasdaq-100 | +0,56% | +0,10% | 3,0 | sì | +5,25% | -0,09% | 0,43 | 0,91 | 0,64 |
| Euro Stoxx 50 | +0,58% | -0,54% | 6,3 | no (ECE > 5) | +2,54% | -1,07% | -0,35 | 0,42 | -0,17 |
| FTSE MIB | 0,00% | -0,06% | 2,4 | no (BSS = 0) | +0,28% | -0,13% | 0,01 | 0,29 | 0,11 |

Lettura onesta:
- Lo skill sull'**inversione** viene interamente dal regime di volatilità e trend: il benchmark semplice fa
  uguale o meglio in tutti e 4 i mercati. I quattro punteggi non aggiungono informazione sull'inversione.
- Sulla **direzione** l'unico contributo incrementale apprezzabile è sull'S&P 500 (+0,64% di BSS);
  nei sottoperiodi è circa zero nel 2010-12 e nel 2022-24.
- La strategia **IPB long/flat** ha Sharpe inferiore al buy & hold in tutti i mercati e in tutte le
  24 combinazioni di costi (0-20 bps), soglia (10/20/30) e ritardo (1/2) provate sull'S&P 500.
  Il filtro probabilistico non cambia mai la strategia sull'S&P 500 (con IPB > 20, p_rialzo > p_ribasso sempre).
- Sensibilità S&P 500: skill direzionale a 5 e 10 sedute per tutte le soglie; a 20 sedute BSS tra -0,07% e +0,69%.
- Regola di visualizzazione (BSS > 0 ed ECE ≤ 5): è permissiva, perché un BSS di +0,56% (Nasdaq) passa
  pur essendo economicamente trascurabile. Alzarla è una scelta da fare prima di guardare nuovi dati.

## 4. Verifiche end-to-end
- `streamlit run app.py --server.headless true`: endpoint di salute `ok`, pagina HTTP 200.
- Dashboard con dati **reali** (AppTest, senza mock) per S&P 500 e FTSE MIB con sensibilità: nessuna
  eccezione; 10 metriche mostrate; per il FTSE MIB l'avviso "Expectation Gap non calcolabile".
- CLI su 4 mercati: codice di uscita 0, file CSV e JSON scritti.

## 5. Non verificato
- Python 3.11 (solo 3.13 disponibile).
- Breadth reale dei componenti: non implementata (nessuno storico gratuito con delistati); resta "proxy".
- Comportamento con limiti di Yahoo prolungati: testato solo con risposte simulate.
