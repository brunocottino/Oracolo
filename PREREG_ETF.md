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
