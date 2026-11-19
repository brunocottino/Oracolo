# Pre-registrazione: il segnale Panico regge con i tassi americani in salita? (19/11/2026)

Scritto prima del test. Motivo: a novembre 2026 la correzione è guidata dai tassi (Treasury 10 anni oltre il 5%);
il segnale Panico (PREREG_PANICO.md) è validato in generale, non in questo regime.

## Regole
- Segnale e campione identici a PREREG_PANICO.md: punteggio ≥ 2 = COMPRA, 15 indici fuori campione, dal 1993.
- Regime "tassi in salita" alla data t: rendimento del Treasury a 10 anni (^TNX) salito di almeno 0,50 punti
  nelle 63 sedute fino a t−1 (nessun dato futuro). Gli altri giorni = "tassi non in salita".
- Misura: vantaggio di COMPRA sul normale dell'indice a 21 sedute (come PREREG_ORIZZONTI.md), per regime.

## Criterio (deciso prima)
- Se con tassi in salita il vantaggio è > 0 con t ≥ 1,5: il segnale resta valido anche in questo regime.
- Se è ≤ 0, oppure t < 1,5 con meno di 12 date indipendenti: Oracolo aggiunge un avviso
  "segnale Panico meno affidabile con tassi in salita" accanto ai livelli 4-5 quando il regime è attivo.
- Il segnale Panico in sé non si spegne: questo test non ne cambia la validazione generale.

---
## Esito (19/11/2026, parte sopra invariata). `python -m lab.panic_rates_test`, 15 indici, dal 2008 (storico disponibile)
| Regime | COMPRA vs normale a 21 sedute | t | date | % rialzi |
|---|---|---|---|---|
| Tassi in salita (+0,50 punti in 63 sedute) | +0,72% | 0,56 | 12 | 66% |
| Tassi non in salita | +1,38% | 2,29 | 53 | 65% |
**Non dimostrato**: con tassi in salita il vantaggio resta positivo ma è metà e non significativo. Le regole scritte prima
hanno un buco (vantaggio > 0, t < 1,5, 12 date): non rientra in nessuno dei due casi, quindi l'avviso NON si aggiunge
(niente regole cambiate dopo aver visto il risultato). Da rifare con più casi; prossima versione: regola senza buchi.
