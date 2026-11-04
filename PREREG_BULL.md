# Pre-registrazione: le tesi degli ospiti di "The Bull" (Riccardo Spada)

Scritto **prima** dei test, il 04/11/2026. Fonti gratuite senza registrazione:
Shiller `ie_data.xls` (S&P mensile dal 1871: prezzo, dividendi, utili, CPI, GS10, CAPE; file aggiornato a 09/2024),
Damodaran `histimpl.xls` (premio implicito annuale dal 1960), Yahoo `^GSPC` giornaliero dal 1950.
Rendimenti **totali reali** (dividendi reinvestiti, deflazionati con CPI) salvo dove detto.
Test informativi: nessuno entra nell'Oracolo (principio 5, peso 0). Ogni t usa periodi **non sovrapposti**.

| # | Ospite | Tesi | Misura | Ipotesi confermata se |
|---|---|---|---|---|
| H1 | Ben Carlson (ep. 200) | La pazienza vince: più è lungo l'orizzonte, più è probabile guadagnare | % finestre con rendimento reale > 0 a 1, 3, 12, 60, 120, 240 mesi | la % cresce con l'orizzonte e a 20 anni è ≥ 95% |
| H2 | Ben Carlson / Jason Zweig (ep. 224) | Uscire dal mercato fa perdere i giorni migliori | ^GSPC 1950-oggi: rendimento annuo senza i 10/20 giorni migliori; % dei 20 migliori a ≤ 10 sedute da uno dei 20 peggiori | togliere i 10 migliori dimezza o peggio il guadagno; ≥ 50% dei migliori vicino ai peggiori |
| H3 | Nick Maggiulli (ep. 221) | Investire subito batte il PAC nella maggior parte dei casi | Somma unica vs PAC in 12 rate mensili (liquidità a rendimento nominale 0), valore a 12 mesi | la somma unica vince in ≥ 60% delle finestre |
| H4 | Meb Faber (ep. 180) | La media mobile a 10 mesi riduce i ribassi senza perdere molto rendimento | Investito se prezzo > media 10 mesi a fine mese, altrimenti liquidità a 0 nominale | drawdown massimo ≤ metà del comprare-e-tenere e rendimento annuo ≥ quello di compra-e-tieni − 1,5 pt, anche dopo il 2007 (anno della pubblicazione) |
| H5 | Rob Arnott (ep. 196) / Shiller | Le valutazioni (CAPE) prevedono i rendimenti di lungo, non di breve | Regressione del rendimento reale annuo futuro su log(CAPE) a 3 mesi, 1, 10 anni | a 10 anni pendenza negativa con \|t\| ≥ 2 (finestre non sovrapposte); a 3 mesi \|t\| < 2 |
| H6 | Aswath Damodaran (ep. 299) | Premio implicito alto → rendimenti futuri più alti | Implied ERP (FCFE) a fine anno vs rendimento in eccesso sui T-bond dell'anno dopo e dei 5 anni dopo | pendenza positiva con t ≥ 2 |
| H7 | Eugene Fama | Il timing di breve non funziona con dati pubblici | già misurato: Laboratorio indici IC +0,035 (t 1,59), PREREG_MACRO 0/10 | nessun test nuovo |

Non testabili con dati gratuiti (solo teoria): Michael Green (ep. 192) e Valentin Haddad (mercati anelastici e
investimento passivo: servono i flussi dei fondi), William Bernstein (ep. 214), Robin Wigglesworth (ep. 203),
Barry Ritholtz (ep. 206), Ed Yardeni (ep. 183), Hendrik Bessembinder (ep. 270: servirebbe l'universo CRSP
con i titoli delistati; il nostro universo ha il bias di sopravvivenza).

Lancio: `python -m lab.bull_test`.

---
## Esito (04/11/2026, parte sopra invariata). `python -m lab.bull_test`
- **H1 Carlson, confermata** (con n piccolo): rendimento reale > 0 nel 61% dei mesi, 69% degli anni, 81% dei 5 anni,
  89% dei 10 anni, 99,9% dei 20 anni (peggiore -4%). I 20 anni non sovrapposti sono solo 7.
- **H2 Carlson/Zweig, metà confermata**: senza i 10 giorni migliori 8,29% → 7,12% annuo (non dimezza su 76 anni).
  Il 65% dei 20 giorni migliori è a ≤ 10 sedute da uno dei peggiori; la volatilità del mese prima è 69% contro 12%.
  Togliendo migliori **e** peggiori il rendimento sale (8,60% con 10+10): i giorni migliori arrivano nelle crisi.
- **H3 Maggiulli, confermata**: la somma unica batte il PAC a 12 mesi nel 72% delle finestre (80% dal 1990),
  +5,1 pt medi; quando perde, -6,5 pt.
- **H4 Faber, metà confermata**: con i prezzi medi mensili di Shiller il risultato sembra pieno (7,1% contro 7,0%, drawdown -37% contro -77%),
  ma la media mensile gonfia la persistenza (effetto Working). Controllo con le chiusure di fine mese di ^GSPC (solo prezzo,
  liquidità a 0): 1950-oggi 6,9% contro 8,3%, drawdown -27% contro -53%; dal 2008 7,3% contro 9,1%, drawdown -23% contro -48%.
  Il drawdown si dimezza, il rendimento perde più di 1,5 pt dal 2008. Con la liquidità remunerata la perdita scende di circa 0,3-1,5 pt.
- **H5 Arnott/Shiller, confermata**: 10 anni pendenza negativa t -2,13, R² 0,27 (n=14); 3 mesi t -1,85, R² 0,01.
  Il CAPE di 09/2024 (35,2) è sopra il 97% della storia; dopo CAPE > 30 i 10 anni hanno reso -1,1% reale annuo
  (57 mesi ma di fatto 2 episodi: 1929 e 1997-2000).
- **H6 Damodaran, metà confermata**: 1 anno t +2,29 ma R² 0,08 (n=62); 5 anni t +1,87 (n=11).
  ERP implicito di inizio 2026: 4,23%, 53° percentile dal 1960, quindi neutro.
- Nessuna tesi diventa un segnale a 31/63 sedute. L'Oracolo resta su NESSUN SEGNALE.
