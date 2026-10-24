# Pre-registrazione: utilità dei segnali a 45 e 90 giorni (31 e 63 sedute)

Scritto e committato **prima** dei test. La domanda di Bruno: non battere il buy & hold su più anni, ma sapere se
dopo un COMPRA o un VENDI i successivi 45 / 90 giorni sono migliori o peggiori del normale per quel titolo/ETF.

## Segnali (calcolati con dati fino a t, nessun parametro stimato)
- `oracolo`: stati di Oracolo v1 (PREREG_ORACOLO.md), rango del momentum dentro l'universo.
- `ipb2`: stato long/cash del sistema IPB v2 di Bruno (isteresi 20/5), long = COMPRA, cash = VENDI.
- `sma100`: prezzo > media mobile 100 sedute = COMPRA, altrimenti VENDI.

## Universi
azioni (73 titoli), settori, paesi, indici, asset: come in PREREG_ETF.md.

## Misura
Origini ogni h sedute (h = 31 per 45 giorni, h = 63 per 90 giorni): finestre future **non sovrapposte**.
Per ogni origine e ticker: rendimento futuro r_h. Si toglie a r_h la media di r_h **di quel ticker** su tutto il
campione di sviluppo ("normale" del ticker; serve solo a valutare, non entra nel segnale).
Vantaggio dello stato = media dei rendimenti così corretti nello stato, calcolata per data e poi mediata nel tempo;
t sulle date (Newey-West, ritardo 1). Si riportano anche: rendimento medio, % di finestre in rialzo per stato.

## Criteri (per segnale, universo, orizzonte; sviluppo = finestre che finiscono prima delle ultime 504 sedute)
- U1: vantaggio COMPRA > 0 con t ≥ 3, **oppure** vantaggio VENDI < 0 con t ≤ -3 (soglia 3 per i ~60 test).
- U2: dal 2013 lo stesso stato ha lo stesso segno.
- U3: % finestre in rialzo dopo COMPRA > % dopo VENDI.
"Utile" solo se U1, U2, U3 insieme. Holdout (ultime 504 sedute) riportato una volta.
