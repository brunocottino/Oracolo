# Pre-registrazione: il livello Panico funziona su azioni ed ETF settoriali?

Scritto e committato **prima** del test. Stessa formula di PREREG_PANICO.md (RSI14 < 30, calo anomalo calibrato
"azioni" per le azioni ed "etf" per gli ETF, VIX sopra la media annua; COMPRA con almeno 2 voti), orizzonte 21 sedute.
Universi: sp500 (503 titoli), europa (azioni italiane ed europee), ETF UCITS settoriali e fattoriali.
Criterio per universo: vantaggio COMPRA sul normale del titolo > 0 con t ≥ 2 (sviluppo, fino alle ultime 504 sedute),
> 0 dal 2013 e > 0 nell'holdout. Se passa, il livello viene esteso a quell'universo.
