# Pre-registrazione: indice ORACOLO v1 (COMPRA / VENDI / STAI FERMO)

Scritto e committato **prima** di qualsiasi calcolo. Regole, orizzonti, campione e criteri non cambiano
dopo aver visto i risultati. Se i criteri falliscono, Oracolo mostra NESSUN SEGNALE (principio 5).

## Lezioni che hanno guidato le regole
- Il sistema IPB a soglie ottimizzate (long/short, giornaliero) perde contro il buy & hold in 61 titoli su 72
  fuori campione (Sharpe mediano -0,36 contro +0,74): niente short, niente operatività giornaliera, niente soglie ottimizzate.
- Nei test precedenti reggono solo effetti lenti e documentati (trend, momentum di medio periodo).
- Questa è la prova numero ~40 sullo stesso universo: il risultato va letto con questa molteplicità in mente.

## Regole (nessun parametro stimato sui dati)
Decisione ogni 21 sedute del calendario comune (circa mensile), per ogni titolo, con dati fino a t:
- `trend` = 1 se rendimento 12-1 mesi > 0 **e** prezzo > media mobile 200 sedute
  (Moskowitz-Ooi-Pedersen 2012; Faber 2007); `trend` = -1 se entrambi negativi; altrimenti 0.
- `mom` = rango trasversale del rendimento 12-1 mesi (Jegadeesh-Titman 1993).
Stato:
- **COMPRA**: trend = 1 e mom nel terzo superiore del giorno.
- **VENDI** (uscire / non tenere): trend = -1.
- **STAI FERMO** (mantieni se già in portafoglio, non aggiungere): tutti gli altri casi.
Solo posizioni lunghe. Orizzonte principale 21 sedute; secondario 63 sedute.

## Misure
- Rendimento futuro a 21 e 63 sedute (prezzi rettificati per dividendi) in eccesso rispetto alla media
  di tutti i titoli disponibili quel giorno, per stato. Media nel tempo, t di Newey-West
  (21 sedute: date non sovrapposte; 63: ritardo 2). Percentuale di titoli COMPRA che battono la media.
- Portafogli mensili, costo 10 bps per unità di turnover, cassa al 0%:
  A = equipesato su COMPRA (cassa se nessuno); B = equipesato su tutti tranne VENDI;
  benchmark = equipesato su tutti (buy & hold ribilanciato).

## Campione
73 titoli di universe.py (attuali: survivorship bias dichiarato, gonfia il benchmark e il momentum).
Sviluppo = date il cui orizzonte a 21 sedute finisce prima delle ultime 504 sedute; holdout = ultime 504
sedute, riportato una volta. Sottoperiodo post-pubblicazione: dal 2013 (dopo Moskowitz-Ooi-Pedersen 2012).

## Criteri di successo (sviluppo)
- P1: eccesso COMPRA a 21 sedute > 0 con t ≥ 2.
- P2: eccesso VENDI a 21 sedute < 0 con t ≤ -2.
- P3: portafoglio B con Sharpe ≥ benchmark **e** drawdown massimo minore.
- P4: dal 2013 gli eccessi di COMPRA e VENDI hanno lo stesso segno di P1 e P2.
Tutti e quattro: Oracolo v1 si accende. Altrimenti NESSUN SEGNALE.
Inoltre, da oggi ogni decisione viene registrata in `oracolo_forward.csv` (prova sui dati futuri, l'unica vera).

---
## Esito (aggiunto dopo il test, 24/10/2026; la parte sopra è invariata, commit 8936fea)
72 titoli (ROG.SW: 404 Yahoo), 769 date di sviluppo dal 1962 al 2024, 24 di holdout. `python -m lab.oracolo_index`.

| Criterio | Risultato | Esito |
|---|---|---|
| P1 COMPRA, eccesso a 21 sedute | +0,65% (t 3,64), titoli sopra la media 51,8% | superato |
| P2 VENDI, eccesso a 21 sedute | -0,46% (t -1,82) | **fallito** (serve t ≤ -2) |
| P3 portafoglio B vs benchmark | Sharpe 0,928 = 0,928; drawdown -47,5% vs -42,4% | **fallito** |
| P4 segni dal 2013 | COMPRA +0,05% (t 0,24), VENDI -0,51% (t -1,28) | superato solo nel segno |

A 63 sedute: COMPRA +1,99% (t 4,23), VENDI -1,37% (t -2,26).
Portafoglio A (solo COMPRA): Sharpe 1,07 contro 0,93 del benchmark, ma drawdown -48,9%; dal 2013 Sharpe 1,13 contro 1,16.
Holdout (23 periodi): COMPRA +0,53% (t 0,91), VENDI -0,96% (t -1,39).

**Esito: Oracolo v1 resta SPENTO (NESSUN SEGNALE).** Il vantaggio storico di COMPRA esiste fino al 2012 e poi
scompare (decadimento dopo la pubblicazione, McLean-Pontiff 2016). VENDI ha il segno giusto ovunque ma non
è significativo. Le decisioni di oggi sono comunque registrate in `oracolo_forward.csv` per la prova sui dati futuri.
