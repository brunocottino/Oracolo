# IPB Extreme — prototipo di ricerca quantitativa

Motore sperimentale per indici azionari: quattro punteggi comportamentali, rischio di inversione
euristico, probabilità walk-forward calibrate a 5/10/20 sedute, backtest con costi e benchmark.
**Non è consulenza finanziaria. Nessun ordine né collegamento a broker.**

## Avvio

Richiede Python 3.11+ e una connessione internet (dati Yahoo Finance via `yfinance`).

```bash
cd ipb_extreme
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m pytest                     # test automatici (dati sintetici, nessuna rete)
streamlit run app.py                 # dashboard: http://localhost:8501
python -m ipb.cli --market "S&P 500" --start 2005-01-01 --horizon 10 --out risultati --sensitivity
```

La CLI scrive in `risultati/`: `*_results.csv` (serie giornaliere), `*_backtest.csv`, `*_metrics.json`
(versioni, parametri, valutazione, backtest) e, con `--sensitivity`, le tabelle di sensibilità.
Mercati: `"S&P 500"`, `"Nasdaq-100"`, `"Euro Stoxx 50"`, `"FTSE MIB"`. Codice di uscita 2 = errore dati.

Cache: `~/.cache/ipb_extreme` (cambiabile con `IPB_CACHE_DIR`, durata `IPB_CACHE_TTL` secondi, 12 ore di default).
Se il provider fallisce si usa una copia in cache **dichiarandolo**; senza cache l'app mostra l'errore.

## Punteggi

| Punteggio | Scala | Cosa misura |
|---|---|---|
| Pressure Score (IPB) | -100/+100 | momentum, trend, partecipazione proxy, volume proxy, sentiment di volatilità |
| Expectation Gap | -100/+100 | volatilità attesa (indice di volatilità di un mese fa e di oggi) contro realizzata; serve un indice di volatilità |
| Reaction Anomaly | -100/+100 | rendimento non spiegato dalla variazione della volatilità implicita (senza indice: solo prezzo, dichiarato) |
| Crowding & Fragility | 0-100 | estensione dalla media, serie di sedute nello stesso verso, compressione della volatilità, compiacenza, volume affollato |
| Rischio inversione | 0-100 | punteggio **euristico**, non una probabilità |

Pesi interni fissi, non ottimizzati sui dati (`ipb/engine.py`).

## Probabilità

- Target separati: **direzione** (ribasso/laterale/rialzo oltre ±soglia a H sedute) e **inversione**
  (movimento contro il trend delle ultime 20 sedute oltre la soglia).
- Logistica L2 walk-forward a finestra espandibile, riaddestrata ogni 20 sedute; alla data t si
  addestra solo su righe con esito già noto (i + H <= t). Nessuno shuffle.
- Calibrazione causale: miscela con la frequenza storica, peso scelto sulle sole previsioni passate verificabili.
- Valutazione fuori campione: Brier, BSS rispetto alla frequenza storica e a un **benchmark semplice**
  (solo volatilità + trend), log-loss, bin di calibrazione (solo con almeno 30 osservazioni), sottoperiodi
  di 3 anni. Sotto 50 periodi indipendenti (righe / H) le metriche non vengono riportate.
- Le probabilità del modello si mostrano solo se battono la frequenza storica con ECE <= 5 punti;
  altrimenti si mostra la frequenza storica, dichiarata come tale.

## Backtest

Long/flat su IPB > 20 (ed eventualmente p_rialzo > p_ribasso), contro buy & hold e momentum MA100,
sulla **stessa finestra**. Segnale alla chiusura di t, posizione sul rendimento di t+1 (o t+2 con
`execution_lag=2`); costo = turnover x bps, ingresso iniziale incluso; niente tasse, finanziamento,
impatto o dividendi (indice di prezzo). Sensibilità su costi, soglia IPB e ritardo.

## Temporalità dei dati

- VIX/VXN chiudono dopo l'indice USA: ritardati di 1 seduta.
- FEZ ed EWI (ETF USA) chiudono ore dopo gli indici europei: volume ritardato di 1 seduta.
- Il volume del proxy non si propaga ai giorni mancanti; le serie di livello sì (ultimo valore noto).
- VSTOXX (`^V2TX`) non è disponibile su Yahoo: per Euro Stoxx 50 Expectation Gap non è calcolabile.

## Limiti

1. Prototipo di ricerca, non sistema d'investimento validato. Un backtest storico non garantisce il futuro.
2. La "partecipazione" è un **proxy** dal singolo indice, non la breadth dei componenti (servirebbe lo
   storico dei componenti con i delistati, non disponibile gratis).
3. Il volume viene da un ETF proxy; l'indice cash non è negoziabile.
4. Yahoo Finance non è una fonte con licenza per uso commerciale; i dati vanno controllati.
5. Più configurazioni sono state provate (sensibilità): i risultati migliori sono ottimisti per costruzione.
