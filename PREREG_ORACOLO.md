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
