# Pre-registrazione: "weight of evidence" stile Ned Davis (ultimo test sui segnali)

Scritto e committato **prima** dei test. FRED non raggiungibile da questo ambiente (connessione chiusa,
verificato il 25/10/2026): disoccupazione e spread di credito esclusi; si usano gli equivalenti Yahoo.

## Voti (+1 rialzista / -1 ribassista), dati fino a t-1 per le serie macro (chiudono dopo l'indice)
1. Tape: prezzo dell'asset > media mobile 200 sedute.
2. Fed: tasso T-bill 3 mesi (^IRX) oggi ≤ 126 sedute fa (tassi fermi o in calo).
3. Curva: ^TNX - ^IRX > 0 (curva non invertita).
4. Sentiment: VIX < propria media 252 sedute.
Punteggio = somma (-4..+4). **COMPRA** ≥ +2, **VENDI** ≤ -2, **STAI FERMO** altrimenti. Nessun parametro stimato.

## Asset (USA, perché i voti sono macro USA)
^GSPC ^NDX ^DJI ^RUT SPY QQQ IWM e i 9 ETF settoriali XLB XLE XLF XLI XLK XLP XLU XLV XLY.

## Misura e criteri: identici a PREREG_ORIZZONTI.md
Orizzonti 31 e 63 sedute, finestre non sovrapposte, vantaggio rispetto al rendimento normale dell'asset,
t di Newey-West; utile solo se U1 (|t| ≥ 3 nel verso giusto), U2 (stesso segno dal 2013), U3 (% rialzi dopo
COMPRA > dopo VENDI). Campione dal 1990 (inizio VIX). Holdout ultime 504 sedute riportato.
Si riportano anche i 4 voti presi da soli (informativo, nessuna selezione).
**Se fallisce, si chiude la ricerca di segnali di timing con dati gratuiti.**

---
## Esito (25/10/2026; parte sopra invariata, commit dc78f9c). `python -m lab.macro_test`
Weight of evidence: 45 gg COMPRA +0,19% (t 0,55), VENDI +0,71% (t 0,60); 90 gg COMPRA -0,51%, VENDI -0,35%.
**0 combinazioni utili su 10. Ricerca di segnali di timing con dati gratuiti chiusa.**
Unico spunto (informativo, NON pre-registrato in questo verso): con VIX sopra la media (voto "sentiment" ribassista)
i 45 giorni successivi sono andati **meglio** (+0,90%, dal 2013 +1,88% t 2,34, 74% in rialzo): la paura alta
precede rialzi, in linea con la lettura contrarian del sentiment di NDR. Va pre-registrato e verificato solo sui dati futuri.
