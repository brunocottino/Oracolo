# Pre-registrazione: sorpresa sugli utili da SEC EDGAR (SUE senza stime degli analisti)

Scritto **prima** del test (05/11/2026). Motivo: la SUE attuale dipende dalle stime Yahoo (poco storico, dal cloud
risponde 401). La SEC dà gli EPS trimestrali dal 2009 con la data di deposito, gratis e senza account.

## Definizione (Bernard-Thomas 1989; Livnat-Mendenhall 2006, modello stagionale)
- EPS diluito trimestrale (`EarningsPerShareDiluted`, ripiego `EarningsPerShareBasic`) dai 10-Q/10-K di companyfacts.
  Si usa il **primo** valore depositato per ogni trimestre (niente riesposizioni successive). Q4 = anno − (Q1+Q2+Q3)
  se il trimestre di 3 mesi non è riportato.
- Sorpresa = EPS_q − EPS_{q−4}; SUE = sorpresa / deviazione standard delle ultime 8 sorprese (almeno 4).
- Disponibile da deposito + 2 giorni (principio 2). Vale 90 giorni di calendario, poi è vuota.

## Misura
Universo: membri attuali S&P 500 (Wikipedia; survivorship dichiarato). Prezzi Yahoo rettificati.
Origini ogni h = 31 sedute dal 2011; IC di Spearman medio (Fama-MacBeth), t di Newey-West (ritardo 1);
eccesso del terzo superiore. Sviluppo = fino alle ultime 504 sedute; holdout riportato una volta, solo interruttore.

## Criteri (tutti)
- S1: IC a 31 sedute > 0 con t ≥ 2.  - S2: IC dal 2016 > 0.  - S3: eccesso del terzo superiore > 0.
- S4 (interruttore): IC sull'holdout ≥ 0.
Se tutti passano: la SUE SEC sostituisce quella Yahoo per i titoli USA nel Laboratorio. Altrimenti: SPENTO.
