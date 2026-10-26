# Pre-registrazione: punteggio Oracolo da 1 a 5

Scritto e committato **prima** del test.

## Indici ed ETF azionari
Composito C(t) = media di tre misure standardizzate (dati fino a t):
(50 - RSI14) / 20;  -z31 (rendimento delle ultime 31 sedute / (σ giornaliera × √31));  log(VIX di ieri / media VIX 252).
Punteggio = quintile del percentile di C rispetto alla storia **dello stesso indice fino a t** (almeno 500 sedute):
1 = 0-20% (euforia) ... 5 = 80-100% (panico). Orizzonte 21 sedute.
Campione: i 15 indici di PREREG_PANICO.md (già usati una volta per il voto ≥2, non per il punteggio) + i 14 indici
di universe.py; risultati riportati separatamente.
**Criterio:** vantaggio sul normale del punteggio 5 > 0 con t ≥ 2 in entrambi i gruppi, e vantaggio crescente con il
punteggio (correlazione di Spearman tra punteggio e vantaggio medio ≥ 0,8) in entrambi.

## Azioni
Punteggio = quintile trasversale (per data) di (50 - RSI14) sull'S&P 500; orizzonte 5 sedute.
**Criterio:** vantaggio del 5 meno vantaggio dell'1 > 0 con t ≥ 3 dal 2013, e monotonia (Spearman ≥ 0,8).
Se il criterio fallisce, le azioni non hanno punteggio (solo l'avviso "ipercomprato" già verificato).
