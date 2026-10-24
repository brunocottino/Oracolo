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
