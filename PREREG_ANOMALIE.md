# Pre-registrazione: comprare dopo un "calo anomalo", vendere dopo un "rialzo anomalo"?

Scritto e committato **prima** del test. Stato come nell'app (bands.py): movimento delle ultime 31 sedute
fuori dalla forchetta 80% (quantili calibrati, σ alla data). Ipotesi (inversione a breve, Jegadeesh 1990):
- H1: dopo un calo anomalo i 45/90 giorni successivi rendono più del normale del titolo.
- H2: dopo un rialzo anomalo rendono meno del normale.
Misura e campione come PREREG_ORIZZONTI.md (origini ogni h sedute, vantaggio rispetto al normale del ticker,
t di Newey-West), universi azioni, paesi, settori, indici; h = 31 e 63.
Criterio per ciascuna ipotesi: t ≥ 2 nel verso atteso nello sviluppo, stesso segno dal 2013; holdout riportato.
