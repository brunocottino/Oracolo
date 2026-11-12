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
