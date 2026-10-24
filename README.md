# Oracolo – cosa c'è nel prezzo e cosa non ancora

Strumento personale di studio. Per ogni azione (orizzonte **45 giorni = 31 sedute**) e ogni indice
(**3 mesi = 63 sedute**) separa:

- **cosa il mercato prezza già**: probabilità di rialzo implicita nelle opzioni, movimento atteso,
  crescita implicita nel prezzo (reverse DCF), volatilità implicita, regime del VIX;
- **cosa non è ancora nel prezzo**: segnali che, in un banco di prova serio sul passato, hanno
  anticipato i rendimenti *residui* (oltre il mercato).

Il segnale (COMPRA / ACCUMULA SU DEBOLEZZA / NESSUN SEGNALE / ALLEGGERISCI) scatta solo se la seconda
parte è abbastanza grande e storicamente affidabile. Se il banco di prova non è superato, il modello è
**spento** e tutti i titoli mostrano NESSUN SEGNALE: è un esito accettabile e onesto.
Quando il modello è attivo, una precisione realistica è del **52-55%**.

> Strumento di studio a uso personale. Non è consulenza finanziaria né raccomandazione
> d'investimento. Le previsioni possono essere sbagliate.

---

## Architettura

| File | Ruolo |
|---|---|
| `data.py` | prezzi Yahoo (storico **max**), eventi (annunci utili, upgrade/downgrade) e opzioni via `yfinance`, cache SQLite; generatore demo |
| `lab/features.py` | misure di classe A, orientate come in letteratura, senza look-ahead |
| `lab/panel.py` | panel unico di tutte le azioni (e panel separato degli indici), una origine ogni 5 sedute |
| `lab/research.py` | banco di prova walk-forward: purge, embargo, holdout, calibrazione, benchmark, costi, ablation, Benjamini-Hochberg, Deflated Sharpe, registro delle prove |
| `lab/stats.py` | Newey-West, Wilson, BH, Brier/BSS/ECE, bootstrap a blocchi, Deflated Sharpe |
| `lab/model.py` | uso quotidiano del modello addestrato (pickle in `data/`) |
| `collector.py` | raccolta notturna dei dati di classe B, contatore e regola di promozione |
| `priced.py` | "cosa c'è nel prezzo": probabilità digitale con skew, reverse DCF con base rate, VIX |
| `engine.py` | previsione ufficiale, regola del segnale, piano operativo |
| `agents/` | modello di base (GARCH + Monte Carlo + CAPM + controllo ARIMA) e agenti informativi a peso 0 |
| `app.py`, `static/` | server Flask e interfaccia (Mercati, Analizza, Scanner, Portafoglio, Laboratorio, Metodo) |

## Le tre classi di dati (regola anti look-ahead)

- **Classe A – con data storica, testabili sul passato:** prezzi, VIX/VIX3M, date e risultati degli
  annunci degli utili (`Ticker.get_earnings_dates(limit=40)`), upgrade/downgrade
  (`Ticker.upgrades_downgrades`). Un annuncio conta solo da **t+2**, un giudizio dalla seduta dopo.
- **Classe B – istantanee di oggi:** revisioni e trend delle stime EPS, consenso, short interest,
  prezzo obiettivo medio, opzioni. **Non entrano nel backtest.** Ogni notte `collector.py` le salva
  in SQLite con la data. Peso 0 finché non vengono *promosse*: servono almeno **12 periodi indipendenti
  non sovrapposti (~18 mesi)**, IC con **t di Newey-West ≥ 2** e il superamento di **Benjamini-Hochberg
  al 10%**. Oggi si fanno raccolta, contatore e regola; la promozione resta una decisione manuale.
- **Classe C – bilanci:** solo informativi (scheda del titolo, Valutazione CFA). In un test storico
  andrebbero usati con 90 giorni di ritardo.

## Il banco di prova (Laboratorio)

- **Obiettivo azioni:** rendimento logaritmico **residuo** a 31 sedute contro l'indice locale
  (`benchmark_for`), con beta stimato su 252 sedute usando solo dati precedenti. Etichetta: residuo > 0.
- **Obiettivo indici:** rendimento in eccesso sul tasso a breve (^IRX/100, altrimenti costante) a 63 sedute.
- **Misure (classe A):** momentum 12-1, momentum residuo / rischio (Blitz-Huij-Martens), "frog in the
  pan" (Da-Gurun-Warachka), inversione a 1 mese, bassa volatilità, vicinanza al massimo a 52 settimane,
  beta basso, sorpresa utili SUE, reazione all'annuncio EAR (3 giorni), sedute dall'annuncio, upgrade
  netti 30/90 giorni, variazione del prezzo obiettivo 30 giorni. Indici: trend 12 e 3 mesi, premio di
  varianza VIX² − varianza realizzata, VIX/VIX3M. Rango per data in [-0,5; 0,5], mancante = 0 + indicatore.
- **Walk-forward:** una origine ogni 5 sedute, addestramento a finestra crescente (minimo 756 sedute),
  riaddestramento ogni 63 sedute, **purge = orizzonte**, **embargo 10 sedute**.
- **Holdout:** ultime **504 sedute**, mai usate per scegliere misure o soglie. Serve solo da interruttore:
  se l'IC cambia segno o il Brier Skill Score è significativamente negativo, il modello si spegne.
- **Modello:** regressione logistica L2 (C = 0,1), cioè un composito lineare trasparente. Lo sfidante
  `HistGradientBoostingClassifier` (profondità 3, 200 iterazioni, learning rate 0,03, foglie minime 500,
  L2 = 1) viene adottato solo se batte la logistica sul Brier fuori campione (bootstrap appaiato per
  data, p < 0,05).
- **Calibrazione:** isotonica sulle previsioni OOS dei blocchi precedenti (con almeno 2.000 osservazioni),
  altrimenti Platt; si adotta in ogni blocco **solo se** migliorava il Brier sul tratto più recente del
  passato (con segnali deboli la logistica è già quasi calibrata e una calibrazione rumorosa peggiora).
- **Selezione delle misure:** t ≥ 2 (≥ 3 per misure senza letteratura), Benjamini-Hochberg al 10%,
  IC negativo in non più del 40% degli anni, poi **ablation sequenziale**: in ordine di t, una misura
  resta solo se togliendola dal gruppo il Brier peggiora (p ≤ 0,10). Così due misure che dicono la stessa
  cosa (es. SUE ed EAR) non si coprono a vicenda.
- **Benchmark:** frequenza storica (base rate), solo momentum 12-1, prior CAPM sul residuo; sul prezzo:
  sempre long e prior CAPM. Vanno battuti tutti.
- **Costi:** commissione 0,10% per lato, metà spread 0,05%, Tobin tax 0,1% sugli acquisti di titoli .MI.
  Spread quintile alto − basso netto, con rotazione, su periodi non sovrapposti; **Deflated Sharpe**
  (Bailey-López de Prado 2014) con il numero di configurazioni del registro `trials`.
- **Campione effettivo:** sempre in **periodi indipendenti** = date distinte × passo / h (non righe).
- **Criterio di successo** (sul modello finale, fuori campione): IC medio ≥ 0,02 con t ≥ 2, Brier Skill
  Score > 0, ECE ≤ 3 punti, spread netto > 0, tutti i benchmark battuti, holdout non contraddittorio.

Lancio:

```bash
python -m research            # oppure: python -m lab   (--fast per la versione rapida)
```

Gira anche da solo nella scansione notturna (se il report ha più di 20 ore) e dal pulsante
**Rilancia i test** nella scheda Laboratorio. Report JSON in SQLite (`lab_reports`), modello in
`data/lab_model.pkl`. API: `GET /api/lab/status`, `POST /api/lab/run`.

### Come leggere il Laboratorio

- **Modello attivo / spento** e il perché (frasi con i numeri).
- **Campione effettivo**: periodi indipendenti, osservazioni, anni.
- **IC medio** (correlazione di rango per data) con **t di Newey-West**; sotto 2 non è distinguibile dal caso.
- **Brier Skill Score**: quanto le probabilità sono migliori della frequenza storica (anche +0,1% è
  già qualcosa: i segnali veri sono deboli).
- **ECE** e **diagramma di affidabilità**: quando il modello dice 55%, è andata bene il 55% delle volte?
- **Tabella delle misure**: IC, t, stato (attiva / spenta con il motivo / in raccolta n/12).
- **Benchmark**, **spread netto**, **Deflated Sharpe**, **IC per anno**, per area e per regime di VIX,
  **holdout**.

## Come nasce il segnale

1. **Riferimento** = il maggiore tra frequenza storica dei rialzi del titolo e probabilità implicita
   nel mercato (opzioni; senza opzioni media storica + CAPM, fonte dichiarata).
2. **Noi stimiamo** = riferimento + spostamento dovuto all'informazione non ancora nel prezzo (alfa del
   modello panel calibrato e, se attivo, modello indici tramite il beta), misurato in unità di sigma.
   Così il confronto noi-mercato non dipende dalla forma della distribuzione (skew).
3. **COMPRA** se: stima ≥ riferimento + 5 punti; il limite inferiore di Wilson al 95% della frequenza di
   successo nella stessa classe di probabilità (con numerosità effettiva) supera la frequenza storica;
   titolo nel 10% migliore dell'alfa previsto (oppure al 90° percentile storico); valore atteso netto
   costi > 0. **ACCUMULA SU DEBOLEZZA** con + 3 punti e lo stesso controllo di Wilson (ordine limite).
   **ALLEGGERISCI** speculare. Altrimenti **NESSUN SEGNALE**.
4. **Interruttore**: modello panel spento ⇒ NESSUN SEGNALE per tutti, con la spiegazione.
5. **Piano**: ingresso a mercato o limite sul supporto più vicino, stop 2,5 ATR, obiettivo al 75°
   percentile, probabilità obiettivo/stop da 6.000 simulazioni; peso = ¼ di Kelly su una probabilità
   avvicinata a metà strada al riferimento, massimo 10%.

Gli agenti di prima: Monte Carlo, GARCH e ARIMA sono un unico **modello di base** (sigma e prior CAPM,
niente più voti multipli). Holt, Momentum, Mean reversion, Regimi, Gradient Boosting per singolo titolo
e Valutazione CFA restano **informativi a peso 0, non validati**: un'ablation sulle loro previsioni
richiederebbe di farli girare su ogni titolo e ogni origine (troppo lento). Il prezzo obiettivo degli
analisti non entra più nel valore equo.

## Limiti onesti

- **Survivorship bias**: l'universo è quello di oggi (aziende sopravvissute e diventate grandi). I test
  sul passato sono quindi ottimistici.
- **Campione effettivo piccolo**: 70 titoli × 10-30 anni sembrano molti dati, ma a 31 sedute sono
  qualche centinaio di periodi indipendenti e i titoli sono correlati tra loro.
- **Copertura degli eventi**: Yahoo fornisce circa 40 trimestri di annunci (≈ 10 anni) e gli
  upgrade/downgrade quasi solo per i titoli USA; altrove quelle misure sono spesso mancanti.
- **Opzioni assenti** sui titoli .MI e su molti titoli europei e asiatici: lì il "mercato" è media
  storica + CAPM. La probabilità digitale con skew è un'approssimazione.
- **Base rate della crescita** (reverse DCF): tabella approssimata da Mauboussin, *The Base Rate Book*
  (2016), costruita sulle vendite; per il free cash flow la dispersione è maggiore.
- **Potenza statistica**: un segnale vero con IC 0,04 dà un t di circa 3 sull'IC, ma il miglioramento del
  Brier è dell'ordine dello 0,1% e può non risultare significativo: in quel caso il modello resta spento.

## Avvio sul tuo PC

```bash
cd oracolo
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m research        # primo banco di prova (alcuni minuti)
python app.py
```

Apri http://localhost:8000. Dal telefono, sulla stessa rete Wi-Fi: `http://IP-DEL-PC:8000`.

**Demo senza internet:** `ORACOLO_DEMO=1 python -m research` e poi `ORACOLO_DEMO=1 python app.py`.
I dati sono sintetici: il generatore crea prezzi con un modello a fattori, annunci con stima e risultato,
upgrade/downgrade (solo titoli USA), VIX, VIX3M, ^IRX e catene di opzioni (non per i titoli .MI).
Inserisce anche un **segnale noto** (deriva dei residui dopo la sorpresa utili, IC ≈ 0,04), per verificare
che il banco di prova lo trovi. Con quell'intensità il modello resta di norma *spento* (il Brier non
migliora in modo significativo): è il comportamento corretto.

## Impostazioni (variabili d'ambiente)

| Variabile | Default | Significato |
|---|---|---|
| `ORACOLO_DEMO` | 0 | 1 = dati sintetici |
| `ORACOLO_DEMO_SIGNAL` | sue | segnale inserito nel demo: `sue` oppure `none` |
| `ORACOLO_DEMO_IC` | 0.04 | intensità (IC atteso) del segnale inserito |
| `ORACOLO_DEMO_YEARS` | 16 | anni di storia sintetica |
| `ORACOLO_LAB_STEP` | 5 | passo delle origini del banco di prova |
| `ORACOLO_LAB_HGB` | 1 | 0 = salta il modello sfidante (più rapido) |
| `ORACOLO_AUTO_SCAN` | 1 | scansione automatica giornaliera |
| `ORACOLO_SCAN_HOUR` | 22 | ora UTC della scansione |
| `ORACOLO_DB` | data/oracolo.sqlite | archivio |
| `ORACOLO_MODEL` | data/lab_model.pkl | modello addestrato |

Universo titoli: `universe.py`. Soglie, costi e parametri del banco di prova: `config.py`.

## Test

```bash
python tests/run_all.py
```

- `test_recovery.py`: il banco di prova **ritrova il segnale inserito** (t ≥ 2, IC > 0), **non** lo trova
  quando non c'è, e con un segnale molto forte il modello si accende e l'interruttore spegne tutto.
- `test_stats.py`: **falsi positivi** del t di Newey-West su 300 simulazioni nulle (≤ 7%), potenza,
  la **calibrazione riduce l'ECE**, Wilson, Benjamini-Hochberg, Deflated Sharpe, probabilità digitale con
  skew (verificata con una derivata numerica), reverse DCF.
- `test_lookahead.py`: le misure all'origine t **non cambiano** se si cancellano i dati dopo t, un evento
  futuro non influisce, un annuncio conta da t+2, il **purge** elimina ogni sovrapposizione, l'holdout
  non entra nella selezione.
- `test_smoke.py`: analisi di azione USA, azione italiana (senza opzioni), indice, portafoglio.

## Pubblicazione online (gratis) su Render

1. Carica la cartella su un repository GitHub (privato).
2. Su render.com → New → Blueprint → scegli il repository (usa `render.yaml`).
3. Dopo il deploy hai un indirizzo tipo `https://oracolo.onrender.com`.

Limiti del piano gratuito: il server si addormenta dopo 15 minuti senza visite (la scansione notturna
può non partire: usa i pulsanti) e il disco non è permanente (portafoglio, istantanee di classe B e
modello si perdono a ogni riavvio: per la raccolta di classe B serve un disco persistente o il PC di casa).
Nessuna protezione con password è inclusa.

## Fonti dati

Yahoo Finance (gratuito, nessuna chiave). I dati possono essere in ritardo o incompleti. Verifica sempre
su fonti ufficiali.
