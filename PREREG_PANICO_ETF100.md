# Pre-registrazione: il livello Panico su 100 ETF (aree, settori, tematici)

Scritto e committato **prima** del test. Solo ETF, nessuna azione singola. Formula invariata (`lab.panic_test.panic_score`):
RSI14 < 30; calo anomalo a 31 sedute sotto il quantile calibrato; VIX del giorno prima sopra la media a 252 sedute.
**COMPRA se ≥ 2 voti**, altrimenti STAI FERMO.

## Universo (fissato ora, 100 ETF quotati negli USA, usati come proxy dei gemelli UCITS per avere storia lunga)
- **A, aree e paesi (35):** SPY QQQ DIA IWM MDY EFA EEM VGK EWJ EWG EWU EWQ EWI EWP EWL EWN EWD EWC EWA EWH EWS EWT EWY EWZ EWW INDA FXI MCHI EZA TUR EWM THD EIDO ECH ACWI
- **B, settori e fattori (30):** XLK XLF XLV XLE XLI XLY XLP XLU XLB XLRE XLC VNQ IYT KBE KRE XHB XRT XOP OIH SMH SOXX IBB XBI ITA MTUM QUAL USMV VLUE SIZE IWF
- **C, tematici (35):** ARKK ARKG ARKQ ARKW TAN ICLN PBW QCLN LIT URA URNM COPX GDX GDXJ SIL REMX HACK CIBR BOTZ ROBO SKYY CLOU FINX KWEB ESPO PHO CGW PAVE IPAY SOCL BLOK QTUM UFO NLR JETS

## Misura
Date ogni 21 sedute dal 2008-06. Vantaggio = rendimento futuro del COMPRA meno il rendimento normale dello stesso ETF,
media per data (come `lab.horizon_test.evaluate`), t di Newey-West. Holdout = ultime 504 sedute.

## Criterio di successo (per gruppo, orizzonte 21 sedute)
1. Sviluppo (prima dell'holdout): vantaggio > 0 con **t ≥ 3** (soglia alta: è circa la 50ª prova sullo stesso tipo di segnale).
2. Dal 2013 (sviluppo): vantaggio > 0.
3. Holdout: vantaggio > 0.
Se passa, il livello diventa segnale per quel gruppo; se no, resta solo informativo ("non validato").
Secondario, solo descrittivo: 63 sedute e livello 3 voti. Nessuna ritaratura dopo il test.

## Previsione dichiarata
Passa A (coerente con PREREG_PANICO.md); B e C no (PREREG_PANICO_AZIONI.md: settoriali -0,08%).

## Esito (06/11/2026, parte sopra invariata, commit 5651a55). `python -m lab.panic_etf100`, dati dal 2008-06
| Gruppo | Sviluppo 21 sedute (≥2 voti) | Dal 2013 | Holdout | Esito |
|---|---|---|---|---|
| A aree e paesi (35) | +1,60% (t 1,53), 68% rialzi | +1,27% | +2,99% | **fallito** (t < 3) |
| B settori e fattori (30) | -0,29% (t -0,20) | -1,33% | +1,22% | **fallito** |
| C tematici (35) | +0,61% (t 0,62), 54% rialzi | +0,00% | +2,10% | **fallito** |

Descrittivo: con 3 voti non va meglio che con 2 (A +0,84%, B -1,22%, C -0,69% a 21 sedute). A 63 sedute nessun t ≥ 1,1.
Lettura: sulle aree il segno resta positivo ovunque, coerente con PREREG_PANICO.md, ma dal 2008 e con soglia t ≥ 3 non basta;
settori e tematici: nessun vantaggio. **Il livello resta solo informativo per settori e tematici; per le aree resta quello già validato.**
