# Pre-registrazione: comprare dopo un "calo anomalo", vendere dopo un "rialzo anomalo"?

Scritto e committato **prima** del test. Stato come nell'app (bands.py): movimento delle ultime 31 sedute
fuori dalla forchetta 80% (quantili calibrati, σ alla data). Ipotesi (inversione a breve, Jegadeesh 1990):
- H1: dopo un calo anomalo i 45/90 giorni successivi rendono più del normale del titolo.
- H2: dopo un rialzo anomalo rendono meno del normale.
Misura e campione come PREREG_ORIZZONTI.md (origini ogni h sedute, vantaggio rispetto al normale del ticker,
t di Newey-West), universi azioni, paesi, settori, indici; h = 31 e 63.
Criterio per ciascuna ipotesi: t ≥ 2 nel verso atteso nello sviluppo, stesso segno dal 2013; holdout riportato.

---
## Esito (25/10/2026). `python -m lab.anomaly_test`. Vantaggio rispetto al normale, sviluppo
| | Dopo calo anomalo 45 gg | 90 gg | Dopo rialzo anomalo 45 gg | 90 gg |
|---|---|---|---|---|
| Azioni | -0,37% (t -0,65) | +0,06% | -0,59% (t -1,23) | -0,24% |
| ETF paesi | +0,23% | +1,22% (t 0,49) | -0,38% | +0,05% |
| Settori | +1,06% (t 1,10) | +2,23% (t 1,12) | +0,01% | -0,32% |
| Indici | +0,78% (t 0,95) | +2,57% (t 1,76), 76% in rialzo | +0,26% | +1,27% |
**H1 e H2 respinte ovunque (nessun t ≥ 2).** Su indici, settori ed ETF il "calo anomalo" è sempre stato seguito da
rendimenti sopra il normale (+0,2% / +2,6%), segno coerente ma non significativo; sulle singole azioni no.
Vendere dopo un rialzo anomalo non ha mai aiutato.
