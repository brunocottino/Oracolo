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

---
## Esito (aggiunto dopo il test, 24/10/2026; la parte sopra è invariata, commit 5f2ff67)
`python -m lab.horizon_test`. Vantaggio = rendimento della finestra meno il rendimento normale del ticker;
↑ = % di finestre chiuse in rialzo. Campione di sviluppo; ultima colonna: vantaggio dal 2013 (COMPRA / VENDI).

```
universo segnale|orizz    COMPRA (vantaggio, t, %rialzo)   VENDI                            dal 2013 C / V               utile
azioni   oracolo|45gg     +0.33% t0.94 ↑60%                +0.09% t0.1 ↑56%                 +0.06% / -0.45%              no
azioni   ipb2|45gg        -0.21% t-0.6 ↑57%                +0.36% t0.87 ↑59%                +0.20% / -0.04%              no
azioni   sma100|45gg      -0.01% t-0.02 ↑58%               +0.00% t0.01 ↑58%                +0.18% / -0.21%              no
azioni   oracolo|90gg     +1.56% t1.91 ↑63%                -0.73% t-0.73 ↑59%               +0.21% / -0.14%              no
azioni   ipb2|90gg        +0.05% t0.07 ↑61%                +0.60% t0.82 ↑62%                -0.17% / +0.35%              no
azioni   sma100|90gg      -0.27% t-0.35 ↑61%               -0.36% t-0.49 ↑60%               +0.81% / -0.43%              no
settori  oracolo|45gg     -0.28% t-0.73 ↑62%               -1.00% t-1.14 ↑60%               +0.27% / -0.72%              no
settori  ipb2|45gg        -0.77% t-1.76 ↑57%               +0.31% t0.8 ↑66%                 -0.27% / +0.83%              no
settori  sma100|45gg      -0.19% t-0.56 ↑62%               -0.40% t-0.75 ↑62%               +0.26% / +0.22%              no
settori  oracolo|90gg     -0.55% t-0.66 ↑65%               -0.60% t-0.33 ↑61%               +0.61% / +1.51%              no
settori  ipb2|90gg        -0.78% t-0.97 ↑62%               -0.05% t-0.05 ↑68%               +0.39% / +0.36%              no
settori  sma100|90gg      -0.24% t-0.3 ↑66%                -0.05% t-0.04 ↑65%               +0.76% / +2.27%              no
paesi    oracolo|45gg     +0.03% t0.06 ↑61%                +0.28% t0.38 ↑60%                -0.21% / +0.20%              no
paesi    ipb2|45gg        -0.11% t-0.2 ↑58%                +0.14% t0.28 ↑60%                -0.86% / +0.06%              no
paesi    sma100|45gg      -0.13% t-0.29 ↑60%               -0.15% t-0.25 ↑58%               -0.65% / +0.23%              no
paesi    oracolo|90gg     -1.67% t-1.38 ↑64%               +0.56% t0.4 ↑57%                 -1.53% / +0.96%              no
paesi    ipb2|90gg        +0.65% t0.64 ↑62%                -0.12% t-0.11 ↑60%               -0.77% / -0.03%              no
paesi    sma100|90gg      -0.66% t-0.64 ↑64%               -0.13% t-0.1 ↑56%                -1.38% / +1.27%              no
indici   oracolo|45gg     +0.28% t0.81 ↑63%                -0.36% t-0.68 ↑54%               -0.36% / +0.16%              no
indici   ipb2|45gg        -0.45% t-1.02 ↑59%               +0.08% t0.19 ↑63%                -0.46% / +0.04%              no
indici   sma100|45gg      -0.16% t-0.51 ↑60%               +0.02% t0.05 ↑60%                -0.55% / +0.59%              no
indici   oracolo|90gg     -0.44% t-0.61 ↑66%               -0.33% t-0.28 ↑56%               -1.51% / +1.51%              no
indici   ipb2|90gg        +0.19% t0.18 ↑67%                -0.00% t-0.01 ↑67%               +0.31% / +0.63%              no
indici   sma100|90gg      -0.05% t-0.07 ↑63%               +0.63% t0.71 ↑64%                -0.53% / -0.05%              no
asset    oracolo|45gg     +0.05% t0.15 ↑60%                -0.48% t-0.8 ↑58%                -0.30% / -0.67%              no
asset    ipb2|45gg        +0.05% t0.15 ↑58%                +0.37% t1.11 ↑62%                -0.55% / -0.13%              no
asset    sma100|45gg      -0.25% t-0.8 ↑60%                +0.20% t0.5 ↑60%                 -0.54% / -0.43%              no
asset    oracolo|90gg     +0.40% t0.62 ↑65%                +0.06% t0.05 ↑60%                -0.63% / -0.01%              no
asset    ipb2|90gg        -0.50% t-0.78 ↑61%               +0.33% t0.47 ↑63%                -1.18% / -0.11%              no
asset    sma100|90gg      -0.01% t-0.01 ↑63%               +0.32% t0.34 ↑60%                -1.15% / -0.42%              no
```

**Risultato: 0 combinazioni utili su 30.** Nessun |t| arriva a 3; il massimo è Oracolo a 90 giorni sulle azioni
(COMPRA +1,56%, t 1,91), che dal 2013 scende a +0,21%.
- In ogni universo circa il 56-68% delle finestre di 45/90 giorni chiude in rialzo **qualunque sia lo stato**:
  dire VENDI significa rinunciare a finestre che salgono 3 volte su 5.
- IPB v2 è spesso al contrario: sui settori a 45 giorni dopo VENDI il 66% delle finestre sale, dopo COMPRA il 57%.
- Holdout non usato per decidere (nessun candidato da confermare).
