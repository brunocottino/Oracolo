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

---
## Esito (25/10/2026, parte sopra invariata). `python -m lab.multifactor`, 503 titoli, 2011-2024
| | IC 45 gg (t) | IC 90 gg (t) | dal 2016, 45 gg |
|---|---|---|---|
| **Punteggio Oracolo** | -0,017 (-1,05) | -0,033 (-1,48) | -0,034 (-1,78) |
| momentum | +0,008 (0,46) | -0,001 | -0,008 |
| value | -0,024 (-1,58) | -0,027 (-1,42) | -0,020 |
| quality | +0,009 (0,94) | +0,013 (1,00) | +0,010 (0,91) |
| bassa volatilità | -0,035 (-1,50) | -0,057 (-1,81) | -0,049 (-1,74) |
Holdout 45 gg: IC -0,006. **Criteri 0 su 4: SPENTO.** Nel 2011-2024 value e bassa volatilità hanno lavorato
al contrario (decennio dei titoli growth ad alto beta; i membri attuali dell'indice sono i vincitori, survivorship);
quality è l'unico fattore positivo, ma non significativo.
