# Pre-registrazione: Indice di Panico Oracolo (ispirato al Panic Index / Capitolazione, AGE Italia)

Scritto e committato **prima** del test. Formula nostra (quella di AGE Italia non è pubblica).
Per ogni indice alla data t, tre voti (1 = panico):
1. RSI14 < 30;
2. calo anomalo: rendimento delle ultime 31 sedute sotto il quantile 10% calibrato (config.BANDS["etf"]);
3. VIX (giorno prima) sopra la propria media a 252 sedute.
Punteggio 0-3. **COMPRA se ≥ 2**, altrimenti STAI FERMO.

## Campione fuori campione (indici mai usati nei test precedenti)
^AEX ^IBEX ^OMX ^ATX ^BFX ^PSI20 ^BVSP ^GSPTSE ^MXX ^MERV ^IPSA ^AXJO ^KS11 ^TWII ^JKSE ^STI ^NSEI, dal 1993.
Orizzonti 21 (principale), 31, 63 sedute; misura come PREREG_ORIZZONTI.md (vantaggio sul normale dell'indice).

## Criterio
Principale: vantaggio COMPRA a 21 sedute > 0 con t ≥ 2, e > 0 dal 2013. Se passa, il segnale Panico entra in Oracolo
per tutti gli indici e gli ETF azionari per area; poi prova sui dati futuri nel registro mensile.
