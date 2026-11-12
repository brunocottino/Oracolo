# Pre-registrazione: motore di rendimento (sempre investiti, senza leva, senza cassa)

Scritto e committato **prima** del test. Obiettivo dichiarato da Bruno: più rendimento, non meno rischio; niente leva.
Lezione dei test precedenti: uscire dal mercato (stop, SMA, IPB) ha sempre ridotto il rendimento; l'unico segnale
validato è il Panico sugli indici (+1,6% a 21 sedute sul normale). Ma chi è già investito al 100% non ha cassa per
comprare: la domanda utile è **relativa**. È la prova numero ~2.050 su questi dati: va letta con questa molteplicità.

## H1, scambio di panico
Quando un'area è in panico (formula invariata di PREREG_PANICO.md, almeno 2 voti), nelle 21 sedute successive
rende più della media delle altre aree? Se sì, si finanzia l'acquisto vendendo il fondo mondo, senza cassa né leva.
- Campione I (valuta locale, solo prezzo): 15 indici di PREREG_PANICO.md + 14 di universe.py, dal 1993.
- Campione II (investibile, in dollari, dividendi e cambio compresi): SPY QQQ IWM EFA EEM VGK EWJ EWG EWQ EWI EWU
  EWP EWL EWC EWA EWZ EWW EWH EWT EWY FXI INDA.
- Misura: origini ogni 21 sedute (non sovrapposte). Per ogni strumento in panico: rendimento futuro a 21 sedute meno
  la media equipesata di tutti gli strumenti disponibili quel giorno (almeno 5). Media per data, t di Newey-West (ritardo 1).
  Secondaria: contro S&P 500 (^GSPC nel campione I, SPY nel II), escluso lo strumento stesso.
- Sviluppo = fino alle ultime 504 sedute; dal 2013; holdout riportato una volta.
- **Criterio:** vantaggio > 0 con t ≥ 2 nello sviluppo in **entrambi** i campioni, > 0 dal 2013 in entrambi,
  > 0 nell'holdout del campione II.

## H2, beta nel panico
Quando l'S&P 500 è in panico (≥ 2 voti), Nasdaq 100 e Russell 2000 battono l'S&P 500 più del solito nelle 21 sedute
successive? Misura: (indice − S&P 500) a 21 sedute nelle date di panico, meno la stessa differenza media su tutte le
date di sviluppo. Dal 1993, origini ogni 21 sedute. Secondario: 63 sedute.
**Criterio (per indice):** vantaggio > 0 con t ≥ 2 a 21 sedute e > 0 dal 2013. Potenza bassa (poche decine di date): dichiarato.

## Simulazione (descrittiva, solo se H1 passa)
Campione II. Base: tutti gli ETF equipesati, ribilanciati ogni 21 sedute. Strategia: a ogni origine il 50% del
portafoglio va, in parti uguali (massimo 25% l'uno), sugli ETF in panico; il resto sulla base. Sempre investita al 100%.
Costo 10 bps per unità di turnover. Si riportano rendimento annuo, volatilità e drawdown contro la base.
Non modellata: l'imposta del 26% sulle plusvalenze realizzate con lo scambio (in pratica conviene usare i nuovi versamenti).

## Se fallisce
Nessuno scambio. Resta la conclusione dei test: sempre investiti in azionario globale a basso costo, il Panico serve
solo a decidere dove mettere i nuovi versamenti.

---
## Esito (12/11/2026, parte sopra invariata, commit 45725e6). `python -m lab.return_test`
| H1, vantaggio a 21 sedute sulla media delle aree | Sviluppo | Dal 2013 | Holdout | Contro S&P 500 (sviluppo) |
|---|---|---|---|---|
| Indici (27, valuta locale) | +0,34% (t 1,09), 126 date, 53% dei casi meglio | +0,66% (t 1,70) | -1,57% (8 date) | -0,23% (t -0,62) |
| ETF in dollari (22) | +0,43% (t 1,04), 70 date, 50% | +0,20% (t 0,34) | +0,68% (5 date) | +0,11% (t 0,19) |

**H1 respinta** (serve t ≥ 2 in entrambi). **H2 respinta:** nel panico dell'S&P 500 il Nasdaq 100 fa +0,04% (t 0,05) e il
Russell 2000 -0,53% (t -0,99) rispetto al solito, 27 date.
Simulazione (solo per misura): base 7,66% annuo, scambio 7,86% (+0,2 punti, t 0,42) in 28,5 anni, prima delle imposte:
il 26% sulle plusvalenze realizzate lo azzera. **Nessuno scambio.**

### Scoperta durante il test: il Panico "validato" non regge sul campione dichiarato
`lab/panic_test.py` dichiarava dati dal 1993 ma `search2000.load` li tagliava a giugno 2008: con il riscaldamento delle
medie il test partiva dopo il crollo del 2008, quando il panico fu seguito da altri ribassi. Verifica
(`python -m lab.return_test panico`, dal 1993, media delle 21 griglie possibili di origini, vantaggio sul normale a 21 sedute):
| Indici | 1993+ | 1993-2007 | 2008+ | 2013+ |
|---|---|---|---|---|
| 15 fuori campione | +0,06% (t 0,09), 0 griglie su 21 con t ≥ 2 | +0,43% | -0,23% | +0,38% (t 0,52) |
| 14 di universe.py | +0,83% (t 1,15), 1 su 21 | +0,63% | +1,00% | +1,79% (t 2,03), 11 su 21 |
Il +1,6% (t 2,9) dipendeva dalla data di partenza e dalla griglia. Dopo il panico gli indici salgono (63% dei casi),
ma quasi quanto in un mese qualsiasi. **Il Panico torna descrittivo, peso 0;** avviso aggiunto in OGGI.md.
