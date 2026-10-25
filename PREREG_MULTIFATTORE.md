# Pre-registrazione: punteggio multi-fattore (momentum, value, quality, bassa volatilità) a 45/90 giorni

Scritto e committato **prima** dei test. Universo: membri attuali dell'S&P 500 (Wikipedia; survivorship bias dichiarato).
Bilanci: SEC EDGAR companyfacts (gratuito), solo 10-K annuali, disponibili da max(data di deposito + 2 giorni,
fine esercizio + 90 giorni) (principio C). Prezzi Yahoo.

## Fattori (rango trasversale per data, alto = meglio secondo la letteratura)
- Momentum: rendimento 12-1 mesi (Jegadeesh-Titman 1993).
- Value: media dei ranghi di patrimonio netto / capitalizzazione e utile netto / capitalizzazione (Fama-French 1992).
- Quality: media dei ranghi di utile lordo / attivo (Novy-Marx 2013) e utile netto / patrimonio netto.
- Bassa volatilità: -volatilità 252 sedute (Ang et al. 2006).
Capitalizzazione = prezzo non rettificato × azioni in circolazione (dei:EntityCommonStockSharesOutstanding).
**Punteggio Oracolo = media semplice dei 4 ranghi** (fattori mancanti esclusi, almeno 3 su 4). Pesi fissi.

## Misura
Origini ogni h sedute (h = 31 e 63), dal 2011. IC di Spearman medio (Fama-MacBeth) tra punteggio e rendimento
futuro; eccesso del terzo superiore rispetto alla media dell'universo; t di Newey-West (ritardo 1).
Sviluppo = fino alle ultime 504 sedute; holdout riportato una volta.

## Criteri
- M1: IC a 45 gg > 0 con t ≥ 3.  - M2: IC a 90 gg > 0 con t ≥ 2.
- M3: IC dal 2016 > 0 a entrambi gli orizzonti.  - M4: eccesso del terzo superiore a 45 gg > 0.
Tutti: il punteggio diventa il segnale COMPRA/STAI FERMO di Oracolo per le azioni USA (terzo superiore = COMPRA).
