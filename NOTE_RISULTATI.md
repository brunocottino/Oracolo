# Note risultati del Laboratorio

| Data | Fonte dati | Stato azioni | Periodi indip. | IC (t) | BSS | ECE | Note |
|---|---|---|---|---|---|---|---|
| 2026-10-24 | Yahoo (reale), `--fast` | SPENTO | 267 | +0,016 (t 1,46) | -0,30% | 2,1 pt | Indici SPENTI: 151 periodi, IC +0,035 (t 1,59), BSS -1,95%, ECE 6,0 pt. Nessuna misura attiva. |

### 2026-10-24: primo avvio sui dati veri (Fase 0)
- Correzione preliminare: con `range=max` Yahoo restituiva barre **mensili** (372 righe per ENI.MI) e il panel risultava vuoto. Ora `data._yahoo_history` usa `period1/period2` → storico giornaliero (7918 sedute per ENI.MI). Cache prezzi svuotata.
- Test: tutti superati (25/25, 150 s).
- **Azioni, SPENTO** (logistica L2, C=0,1): 267 periodi indipendenti, 80.980 osservazioni, 31,8 anni. IC +0,016 (t 1,46): sotto le soglie 0,02 e t ≥ 2. BSS -0,30%, ECE 2,1 punti, spread netto -0,87% per periodo, battuti 2 benchmark su 5.
  - Misure: nessuna attiva. Migliore `low_beta` IC +0,036 (t +2,67) ma non supera falsi positivi/stabilità/ablation; `ea_recent` IC -0,015 (t -2,18). Tutte le altre |t| < 1,6.
  - Copertura eventi: i fondamentali Yahoo (quoteSummary) danno 404 per i titoli non USA e "Invalid Crumb" su alcune chiamate → SUE e giudizi analisti scarsi fuori dagli USA.
- **Indici, SPENTO**: 151 periodi indipendenti, 27.008 osservazioni, 89,3 anni. IC +0,035 (t 1,59), BSS -1,95%, ECE 6,0 punti (massimo 3), battuti 0 benchmark su 3. Misure: tsmom_12 t +0,04, tsmom_3 t -1,81, vrp t +1,37, vix_term t -1,50; nessuna attiva.
- Esito valido (principio 5): tutti i titoli mostrano NESSUN SEGNALE.
| 2026-10-24 | Yahoo + Wikipedia + SEC, `--fast` | SPENTO | 267 | +0,011 (t 1,02) | -0,37% | 1,9 pt | Con 5 misure comportamentali nuove; nessuna attiva. Indici invariati. |

### 2026-10-24: misure di finanza comportamentale (fonti gratuite senza chiave)
Copertura: Wikipedia 70/73 titoli nella lingua del mercato (dal luglio 2015); SEC EDGAR 31 titoli quotati negli USA, comprese 9 ADR di mercati emergenti (10-K/10-Q/20-F dal 2009, CIK storici per XOM, GOOGL, AVGO).

| Misura | Rif. | IC | t | Esito |
|---|---|---|---|---|
| `cgo` guadagno latente sul prezzo di carico | Grinblatt-Han 2005 | +0,0093 | +0,72 | spenta |
| `pt_value` prospect theory (inverso) | Barberis-Mukherjee-Wang 2016 | -0,0014 | -0,13 | spenta |
| `attn` choc di attenzione Wikipedia (inverso) | Barber-Odean 2008 | -0,0169 | -1,75 | spenta, segno opposto |
| `lazy` somiglianza testo bilanci | Cohen-Malloy-Nguyen 2020 | -0,0172 | -1,67 | spenta, segno opposto |
| `press` cgo x choc di attenzione (ipotesi nuova, soglia t ≥ 3) | Oracolo | +0,0077 | +0,62 | spenta |

Lettura:
- Sull'orizzonte di 31 sedute l'attenzione anomala precede rendimenti più **alti**, non più bassi. È coerente con Da-Engelberg-Gao (pressione di acquisto a breve, inversione oltre l'anno), non con Barber-Odean.
- Le società che cambiano poco il testo dei bilanci hanno reso **meno**, al contrario di CMN. Con 31 titoli mega-cap e t -1,67 il risultato non è distinguibile dal rumore.
- **Non** si inverte il segno a posteriori: sarebbe data snooping. Un'eventuale ipotesi "attenzione = momentum a breve" va dichiarata prima e testata sul prossimo blocco di dati, con soglia t ≥ 3.
- Aggiungere misure deboli abbassa l'IC del modello complessivo (da +0,016 a +0,011): l'ablation le esclude correttamente.
- Limiti: universo di 73 grandi titoli, attuali (survivorship bias); i cambi di nome delle pagine Wikipedia (es. Meta, RTX) creano picchi artificiali; la rotazione del CGO è stimata dal volume relativo perché le azioni in circolazione storiche non sono gratuite.

### 2026-10-24: IFC, Indice di Fragilità Comportamentale (pre-registrato, `PREREG_IFC.md`, `python -m lab.fragility`)
Criteri formali superati (IC con NCSKEW futura +0,076, t 6,1; parziale +0,079, t 5,8; holdout +0,050), ma
le diagnostiche mostrano che predice **meno balzi al rialzo**, non più crolli, e che il segnale viene solo
da corsa passata e guadagno latente (Chen-Hong-Stein 2001). Attenzione, volume anomalo e calma: IC -0,006.
Effetto robusto in Europa e Asia/Emergenti. Nessuna previsione di direzione dei prezzi.

### 2026-10-24: Oracolo v1 COMPRA/VENDI/STAI FERMO (pre-registrato, `PREREG_ORACOLO.md`, `python -m lab.oracolo_index`)
Prima il sistema IPB a soglie ottimizzate fornito da Bruno, sui 72 titoli: Sharpe OOS mediano -0,36 contro +0,74 del
buy & hold, batte il B&H in 11 titoli su 72 (differenza t -9,4). Poi Oracolo v1 (trend + momentum, solo long, mensile):
COMPRA +0,65% al mese (t 3,6) sul totale, ma dal 2013 +0,05% (t 0,24); VENDI -0,46% (t -1,8). Criteri 2 su 4: SPENTO.
Registro delle decisioni future avviato: `oracolo_forward.csv` (prima riga 23/10/2026).

### 2026-10-24: ETF, indici, settori, classi di attivo (pre-registrato, `PREREG_ETF.md`)
IPB v2 (long/cash, isteresi, vol targeting) e Oracolo v1 su 4 universi di ETF/indici: nessun universo vira.
IPB v2 sotto il buy & hold in Sharpe ovunque; Oracolo v1 spento ovunque (asset: segni giusti, t 1,7). Le azioni restano il migliore.

### 2026-10-24: segnali a 45 e 90 giorni (pre-registrato, `PREREG_ORIZZONTI.md`, `python -m lab.horizon_test`)
Oracolo v1, IPB v2 e SMA100 su azioni, settori, paesi, indici, asset: 0 combinazioni utili su 30 (nessun |t| ≥ 3;
massimo Oracolo azioni 90 gg COMPRA +1,56%, t 1,91). Il 56-68% delle finestre sale in qualunque stato.

### 2026-10-25: acquisti insider SEC Form 4 (pre-registrato, `PREREG_INSIDER.md`)
Grappolo ≥3 insider: +0,75% su IWM a 45 gg (t 2,1), mediana negativa, holdout negativo, metà eventi senza prezzi
(survivorship, pareggio -0,4%). SPENTO.

### 2026-10-25: weight of evidence macro stile NDR (`PREREG_MACRO.md`): 0 su 10 utili. Ricerca di timing chiusa.

### 2026-10-25: forchetta attesa (`lab/band_test.py`)
Banda 80% normale: copertura 83-87% (troppo larga, sbilanciata in alto). Calibrata sul passato: 77-81,5% su azioni,
ETF paese, settori, a 45 e 90 giorni. Anno peggiore (crisi): 33-65%. In app: scheda "Forchetta attesa".

### 2026-10-25: multi-fattore S&P 500 (`PREREG_MULTIFATTORE.md`): IC -0,017 a 45 gg, spento. Quality unico positivo (t 0,9).

### 2026-10-26: RSI (`PREREG_RSI.md`): indici ipervenduti (RSI14<30) +2,2% a 1 mese (t 3,1, 72% rialzi); S&P 500 ipercomprato -0,3% a 1 settimana. Primi segnali che superano il criterio; campione indici piccolo.

### 2026-10-26: Indice di Panico (`PREREG_PANICO.md`): fuori campione su 15 indici mai usati, +1,6% sul normale a 21 sedute (t 2,9), 66% rialzi. Primo segnale validato fuori campione.

### 2026-11-05: idee dallo scanner "AI Market Intelligence Engine" (zip esterno)
Unica idea nuova: storno in trend rialzista (sotto il massimo a 60 sedute, sopra la media a 200). 22 titoli USA,
1996-2026, 227 periodi indipendenti a 31 sedute: IC -0,007 (t -0,39), holdout -0,003. SCARTATA, non aggiunta al Lab.
Il resto dello zip (RSI, medie mobili, punteggio a pesi fissi) è già coperto o già bocciato (`PREREG_RSI.md`).

### 2026-11-05: SUE da SEC EDGAR senza stime (`PREREG_SUE_SEC.md`): IC +0,010 (t 1,14) a 31 sedute, 503 titoli. SPENTO.
