# Pre-registrazione: azioni contro ETF, indici e settori ("se va meglio, viriamo")

Scritto e committato **prima** dei test. Universi, regole e criteri non cambiano dopo.

## Universi (dati Yahoo gratuiti, prezzi rettificati; gli indici sono di solo prezzo)
- `settori`: XLB XLE XLF XLI XLK XLP XLU XLV XLY XLRE XLC (ETF settoriali USA).
- `paesi`: SPY QQQ IWM EFA EEM VGK EWJ EWG EWQ EWI EWU EWP EWL EWC EWA EWZ EWW EWH EWT EWY FXI INDA.
- `indici`: i 15 indici di universe.py.
- `asset`: SPY EFA EEM TLT IEF LQD HYG GLD SLV DBC VNQ TIP (classi di attivo).
- `azioni`: i 73 titoli di universe.py (riferimento, già testato).

## Test A: sistema IPB v2 di Bruno (long/cash, isteresi 20/5, volatility targeting 15%), codice invariato
Per ogni ticker: dati dal 2018, test sull'ultimo 30%, 10 bps. Variante con dati dal 2000 (stesso codice), per avere
più anni di test. Misure: Sharpe e drawdown massimo fuori campione contro buy & hold e SMA 100.
**Vira** se in un universo: Sharpe IPB mediano > Sharpe B&H mediano, IPB batte B&H in almeno il 60% dei ticker,
e drawdown mediano IPB minore di quello B&H, **in entrambe** le varianti (2018 e 2000).

## Test B: Oracolo v1 (regole di PREREG_ORACOLO.md, invariate) dentro ogni universo
Rango del momentum 12-1 calcolato tra i membri dell'universo; MIN_NAMES abbassato a 5 per gli universi piccoli
(unica modifica, necessaria perché i settori sono 9-11).
**Vira** se un universo supera P1-P4 di PREREG_ORACOLO.md.

## Lettura
Sono ~10 prove in più: un singolo successo con t vicino a 2 va trattato come probabile caso.

---
## Esito (aggiunto dopo i test, 24/10/2026; la parte sopra è invariata, commit 41ef96a)

### Test A: IPB v2 di Bruno, fuori campione (mediane per universo)
| Universo | Dati dal | n | Sharpe IPB | Sharpe B&H | Sharpe SMA100 | IPB > B&H | DD IPB | DD B&H | Vira |
|---|---|---|---|---|---|---|---|---|---|
| settori | 2018 | 11 | 0,27 | 0,83 | 0,20 | 0% | -13,3% | -18,0% | no |
| paesi | 2018 | 22 | 0,01 | 1,00 | 0,62 | 5% | -12,1% | -18,0% | no |
| indici | 2018 | 14 | 0,05 | 0,86 | 0,27 | 0% | -10,6% | -17,3% | no |
| asset | 2018 | 12 | -0,13 | 0,96 | 0,46 | 0% | -13,6% | -16,6% | no |
| azioni | 2018 | 72 | 0,32 | 0,74 | 0,39 | 32% | -14,3% | -32,2% | no |
| settori | 2000 | 11 | 0,37 | 0,60 | 0,15 | 9% | -17,6% | -36,1% | no |
| paesi | 2000 | 22 | 0,13 | 0,56 | 0,45 | 9% | -22,9% | -40,2% | no |
| indici | 2000 | 14 | 0,16 | 0,60 | 0,35 | 14% | -21,6% | -36,3% | no |
| asset | 2000 | 12 | -0,02 | 0,50 | 0,11 | 0% | -22,6% | -30,5% | no |
| azioni | 2000 | 72 | 0,37 | 0,61 | 0,37 | 15% | -22,4% | -50,9% | no |
Il drawdown minore è meccanico: il sistema è investito circa il 40% del tempo e con esposizione ridotta.
Lo Sharpe resta sotto il buy & hold ovunque. Il v2 migliora molto il v1 sulle azioni (0,32 contro -0,36).

### Test B: Oracolo v1 dentro ogni universo (eccesso a 21 sedute, sviluppo)
| Universo | COMPRA | VENDI | Dal 2013 COMPRA | Criteri | Esito |
|---|---|---|---|---|---|
| settori | -0,06% (t -0,36) | -0,30% (t -0,76) | +0,00% (t 0,02) | 0/4 | spento |
| paesi | +0,16% (t 1,13) | +0,13% (t 0,53) | +0,05% (t 0,28) | 0/4 | spento |
| indici (dal 1928) | +0,10% (t 0,90) | +0,02% (t 0,10) | -0,13% (t -0,89) | 0/4 | spento |
| asset | +0,33% (t 1,66) | -0,26% (t -0,96) | +0,26% (t 1,21) | 1/4 | spento |
| azioni (riferimento) | +0,65% (t 3,64) | -0,46% (t -1,82) | +0,05% (t 0,24) | 2/4 | spento |

**Conclusione: non si vira.** ETF, indici e settori non vanno meglio delle azioni; le azioni restano l'universo
migliore. Le classi di attivo hanno i segni attesi dal trend (COMPRA +, VENDI -) anche dopo il 2013, ma senza
significatività (t 1,2-1,7).
