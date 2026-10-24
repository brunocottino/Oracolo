# Pre-registrazione: acquisti degli insider (SEC Form 4) a 45 e 90 giorni

Scritto e committato **prima** di scaricare i dati e calcolare. Niente cambia dopo.

## Perché
I segnali da soli prezzi non funzionano (PREREG_ORIZZONTI.md, 0 su 30). Gli acquisti degli insider sono
un'informazione che il prezzo può non contenere ancora (Lakonishok-Lee 2001; Cohen-Malloy-Pomorski 2012;
Alldredge-Blank 2019 sugli acquisti "a grappolo"). Il codice di Bruno usava dati casuali: qui solo dati reali.

## Dati (gratuiti, senza registrazione)
SEC "Insider Transactions Data Sets", trimestri 2006Q1-2026Q1. Prezzi Yahoo. Benchmark IWM (Russell 2000)
e SPY.

Transazioni valide: modulo 4, tabella non derivati, codice `P` (acquisto sul mercato aperto), acquisizione (`A`),
prezzo ≥ 2 $, insider con ruolo Director o Officer (esclusi i soli azionisti al 10%).
Data pubblica = FILING_DATE. **Ingresso alla chiusura della prima seduta successiva alla data di deposito.**

## Eventi
- **E1, grappolo (principale):** almeno 3 insider distinti con acquisti depositati entro 14 giorni di calendario;
  evento alla data di deposito del terzo. Per la stessa società, un nuovo evento solo dopo 90 giorni.
- **E2, singolo (secondario):** ogni giorno con almeno un deposito valido, stessa regola dei 90 giorni.
  Se E2 ha più di 4000 ticker, se ne usa un campione casuale di 4000 (seme 0).

## Controllo del ticker (riciclo dei simboli)
Un evento vale solo se Yahoo ha il prezzo alla data e il prezzo di chiusura della data di transazione dista meno
del 25% dal prezzo medio pagato dagli insider. Si riporta la quota di eventi persi (survivorship bias: società
delistate assenti da Yahoo).

## Misura
Rendimento dall'ingresso a +31 sedute (45 giorni) e +63 sedute (90 giorni), meno il rendimento di IWM nello
stesso periodo (principale) e meno SPY (secondario). Media degli eventi per mese di calendario, t sui mesi
(Newey-West, ritardo 1 a 31 sedute, 2 a 63).

## Criteri (E1, sviluppo = eventi depositati prima delle ultime 504 sedute)
- I1: eccesso medio su IWM a 31 sedute > 0 con t ≥ 3.
- I2: eccesso medio su IWM a 63 sedute > 0 con t ≥ 2.
- I3: dal 2013 entrambi gli eccessi medi > 0.
- I4: più del 50% degli eventi batte IWM a 31 sedute.
Tutti: il segnale insider diventa candidato COMPRA di Oracolo per le azioni USA, poi prova sui dati futuri.
Holdout (ultime 504 sedute) riportato una volta. Si riporta il rendimento medio che gli eventi persi
dovrebbero avere per annullare il risultato.

---
## Esito (aggiunto dopo il test, 25/10/2026; parte sopra invariata, commit 7334406)
516.238 acquisti validi 2006-2026. E1 grappolo: 16.078 eventi, misurati 6.691 (persi: 7.988 senza prezzi Yahoo,
1.399 ticker non corrispondenti). Eccesso su IWM, media mensile:

| | 45 gg | 90 gg | % eventi sopra IWM (45 gg) |
|---|---|---|---|
| Sviluppo | +0,75% (t 2,13) | +1,05% (t 2,49) | 49,2% |
| Dal 2013 | +0,50% (t 1,06) | +0,53% (t 1,20) | 48,8% |
| Holdout | -0,25% (t -0,23) | -1,80% (t -1,21) | 42,9% |

Criteri: I1 no (t 2,13 < 3), I2 sì, I3 sì, I4 no. **Esito: SPENTO.**
- Media positiva ma mediana negativa: pochi grandi vincitori, la maggior parte degli eventi perde contro IWM.
- Survivorship: metà degli eventi non ha prezzi (società delistate). Basta che rendano in media -0,4% su IWM a 45 gg
  per annullare l'effetto: molto probabile, quindi il +0,75% è sovrastimato.
- E2 singolo (secondario): +0,72% a 45 gg (t 2,86), +1,09% a 90 gg (t 3,56), dal 2013 +0,90% (t 2,54), ma mediana
  negativa, 49% sopra IWM, holdout negativo e stesso problema di survivorship (pareggio -0,5%).
