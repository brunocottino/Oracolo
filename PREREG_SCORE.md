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

---
## Esito (26/10/2026, parte sopra invariata). `python -m lab.score_test`
- Indici, quintili continui: **fallito** fuori campione (livello 5 +0,56%, t 0,96; Spearman 0,4). In campione passa (5: +1,41%, t 2,48).
- Azioni, quintili RSI: monotono (Spearman 1,0) ma differenza 5-1 di +0,15% a settimana (t 1,71): **fallito**.
Lettura: il vantaggio sta solo nel panico estremo; le fasce larghe lo diluiscono.
**Scala adottata (descrittiva, 29 indici 1993-2026, 1 mese):** 5 = 3 voti di panico (+3,77%, 66% rialzi, t 3,83 sul normale);
4 = 2 voti (+2,67%, 67%, t 2,46); 3 = 1 voto (+0,95%, 61%); 2 = 0 voti (+0,31%, 57%); 1 = 0 voti e RSI14 > 70 (+0,53%, 59%,
non distinguibile dal 2). Solo indici ed ETF azionari per area. Validato fuori campione solo il gradino "≥ 2 voti" (PREREG_PANICO.md).
