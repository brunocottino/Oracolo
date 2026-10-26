# Pre-registrazione: il livello Panico funziona su azioni ed ETF settoriali?

Scritto e committato **prima** del test. Stessa formula di PREREG_PANICO.md (RSI14 < 30, calo anomalo calibrato
"azioni" per le azioni ed "etf" per gli ETF, VIX sopra la media annua; COMPRA con almeno 2 voti), orizzonte 21 sedute.
Universi: sp500 (503 titoli), europa (azioni italiane ed europee), ETF UCITS settoriali e fattoriali.
Criterio per universo: vantaggio COMPRA sul normale del titolo > 0 con t ≥ 2 (sviluppo, fino alle ultime 504 sedute),
> 0 dal 2013 e > 0 nell'holdout. Se passa, il livello viene esteso a quell'universo.

---
## Esito (26/10/2026, parte sopra invariata). Vantaggio COMPRA a 21 sedute sul normale del titolo
| Universo | Sviluppo | Dal 2013 | Holdout | Esito |
|---|---|---|---|---|
| S&P 500 | +0,30% (t 0,47), 4.300 casi | +0,36% | -1,98% | no |
| Azioni Italia ed Europa | +1,49% (t 1,25), 61% rialzi | +1,75% | +1,80% | no (non significativo) |
| ETF settoriali e fattoriali | -0,08% | -0,08% | -2,20% | no |
**Il livello resta solo per indici ed ETF azionari per area**; per sfruttarlo si usa l'ETF UCITS che replica l'indice.
