# Pre-registrazione: ricerca su ~2000 prove con correzione per test multipli

Scritto e committato **prima** dei calcoli. Il protocollo è fisso; i risultati di ogni prova si accettano come vengono.

## Universi
- `sp500`: membri attuali dell'S&P 500 (survivorship dichiarato), bilanci SEC point-in-time.
- `europa`: azioni italiane ed europee di universe.py (solo misure di prezzo e volume).
- `tutte`: le due insieme.
- `etf`: i 34 ETF UCITS di universe.py (solo misure di prezzo).

## Misure (~60, rango trasversale per data, dati fino a t)
Momentum (12 varianti di finestra e salto), inversione 5/10/21 sedute, volatilità 21/63/126/252 e rapporti,
distanza da massimi e minimi, distanza dalle medie mobili 20/50/100/200 e incrocio 50/200, asimmetria e curtosi
63/126/252, rendimento massimo giornaliero 21/63 (effetto MAX), beta e volatilità idiosincratica 126/252,
variazione dei volumi, illiquidità di Amihud 21/63, drawdown e tempo dal massimo, stagionalità dello stesso mese,
guadagno latente (CGO) e corsa residua (IFC); solo sp500: patrimonio/prezzo, utile/prezzo, utile lordo/attivo, ROE,
crescita dell'attivo, emissione netta di azioni, crescita dell'utile.

## Prove
Ogni combinazione misura × orizzonte (5, 21, 31, 63, 126 sedute) × target (rendimento; rendimento / volatilità 63)
× universo. IC di Spearman medio su origini ogni h sedute (non sovrapposte), t di Newey-West (ritardo 1),
p bilaterale. Sviluppo: origini dal 2010-07 al 2022-12. Holdout: origini dal 2023-01 (mai usato prima di questo test).

## Criteri
1. Benjamini-Hochberg al 5% su **tutte** le prove insieme (p bilaterali).
2. Inoltre |t| ≥ 3 (Harvey-Liu-Zhu 2016).
3. Holdout: stesso segno e |IC holdout| ≥ metà di |IC sviluppo|.
Solo le misure che passano 1+2+3 diventano informazione in Oracolo (con il loro IC e il verso). Se nessuna passa,
il risultato è "nessuna" e si dichiara.

---
## Esito (25/10/2026, parte sopra invariata, commit 04961f2). `python -m lab.search2000`, dettaglio in NOTE_2000_prove.csv
1.990 prove; 125 passano Benjamini-Hochberg, 117 anche |t| ≥ 3, **19 anche l'holdout 2023-2026**. Verifica delle 19:
- 13 sugli ETF (volatilità, beta, MAX, distanza dai minimi, giorni dal massimo): premio azioni contro obbligazioni e
  monetario nello stesso universo, non selezione.
- Illiquidità (Amihud) e inversione a 1 mese: solo nell'universo misto USA+Europa; da soli non reggono o spariscono nell'holdout.
- Volatilità in aumento (σ63/σ252, segno negativo in tutti gli universi): sui rendimenti veri l'effetto è nullo
  (S&P 500, 90 gg: terzo alto -0,08% contro la media, 2023-2026 +0,02%): artefatto della scala per la volatilità.
**Nessuna misura utile.** Il segnale "calo/rialzo anomalo" viene tolto dalla pagina Oracolo.
