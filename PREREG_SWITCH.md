# Preregistrazione: switch relativo dopo un divario estremo (6/11/2026)

Origine: nota interna "Switch Equal Weight → Nasdaq 100" (5/11/2026). Tesi: quando QQQ
fa peggio di RSP di oltre l'8% in un mese, nei 3 mesi successivi lo switch RSP→QQQ guadagna.
Domanda: è un effetto generale (reversione relativa a 1 mese tra panieri) o un caso scelto a posteriori?

## Regole fissate prima di guardare i risultati
- Divario: S(t) = r21(A) − r21(B), dove r21 è il rendimento di 21 sedute con prezzi rettificati.
- z(t) = S(t) / deviazione standard di S nelle 756 sedute fino a t−1 (minimo 504).
- Scatto: z ≤ −2 → compra A e vendi B; z ≥ +2 → compra B e vendi A (si compra il perdente).
- Esecuzione: alla chiusura di t+1 (nessun look-ahead). Esito: rendimento relativo a 63 sedute,
  al netto di un costo di 0,20% per lo switch.
- Episodi indipendenti: dopo uno scatto la stessa coppia resta ferma per 63 sedute.
- Riferimento: media dello stesso trade (stessa direzione) su tutte le origini ogni 63 sedute.
- Coppie FUORI campione (la coppia QQQ/RSP della nota è esclusa dal verdetto):
  QQQ/SPY, SPY/RSP, IWM/SPY, IWF/IWD, MDY/SPY, EFA/SPY, EEM/SPY, XLK/SPY, XLF/SPY,
  XLE/SPY, XLV/SPY, XLU/SPY, XLY/XLP, SMH/SPY.

## Criterio di successo (tutti)
1. Almeno 12 mesi di calendario distinti con episodi (periodi indipendenti).
2. Vantaggio medio sul riferimento > 0 con t ≥ 2 (t calcolato sulle medie per mese, per non
   contare due volte lo stesso shock su più coppie).
3. Vantaggio > 0 anche dal 2013.
4. Più della metà delle coppie con vantaggio medio > 0.

Se fallisce: nessun segnale, la nota resta aneddotica. È un esito valido.

## Controlli sulla coppia della nota (solo descrittivi, non decidono)
Griglia soglia −6/−8/−10/−12% × orizzonte 21/42/63 sedute, entrata a t e a t+1.
