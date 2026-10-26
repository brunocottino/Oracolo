# Pre-registrazione: RSI ipervenduto / ipercomprato

Scritto e committato **prima** del test.
Regole: RSI14 (Wilder) < 30 = COMPRA, > 70 = VENDI. RSI2 < 10 con prezzo > media 200 sedute = COMPRA (Connors),
RSI2 > 90 = VENDI. Altrimenti STAI FERMO. Dati fino a t, ingresso dalla seduta dopo (rendimento da t a t+h).
Universi: sp500 (503), europa (azioni italiane ed europee), indici, settori, paesi. Orizzonti 5, 21, 31, 63 sedute.
Misura: come PREREG_ORIZZONTI.md (origini ogni h sedute, vantaggio sul rendimento normale del ticker, Newey-West).
Criterio (circa 80 prove): |t| ≥ 3 nel verso atteso (COMPRA > 0, VENDI < 0), stesso segno dal 2013 e
nell'holdout (ultime 504 sedute).
