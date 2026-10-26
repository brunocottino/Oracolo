# Pre-registrazione: RSI ipervenduto / ipercomprato

Scritto e committato **prima** del test.
Regole: RSI14 (Wilder) < 30 = COMPRA, > 70 = VENDI. RSI2 < 10 con prezzo > media 200 sedute = COMPRA (Connors),
RSI2 > 90 = VENDI. Altrimenti STAI FERMO. Dati fino a t, ingresso dalla seduta dopo (rendimento da t a t+h).
Universi: sp500 (503), europa (azioni italiane ed europee), indici, settori, paesi. Orizzonti 5, 21, 31, 63 sedute.
Misura: come PREREG_ORIZZONTI.md (origini ogni h sedute, vantaggio sul rendimento normale del ticker, Newey-West).
Criterio (circa 80 prove): |t| ≥ 3 nel verso atteso (COMPRA > 0, VENDI < 0), stesso segno dal 2013 e
nell'holdout (ultime 504 sedute).

---
## Esito (26/10/2026, parte sopra invariata). `python -m lab.rsi_test`, 80 prove
**Passano 2 su 80:**
1. **Indici, RSI14 < 30 → 21 sedute: +2,21% sul normale (t 3,08)**; dal 2013 +3,62% (t 4,77); holdout +6,98%.
   Rendimento medio 4,03% contro 0,53% degli altri casi, 72% in rialzo (dal 2013: 80%). Campione piccolo:
   90 casi su 32 date, concentrati nelle crisi. A 45 e 90 giorni stesso segno, non significativo.
2. **S&P 500, RSI14 > 70 → 5 sedute: -0,29% (t -3,11)**; dal 2013 -0,17%; holdout negativo. Rendimento medio
   +0,06% a settimana contro +0,37% normale: utile solo per non comprare subito dopo un ipercomprato.
Non passano: RSI2 (Connors) in nessun universo; RSI su azioni europee, settori, ETF paese.
Coerente con PREREG_ANOMALIE.md e PREREG_MACRO.md (paura alta sugli indici seguita da rialzi).
