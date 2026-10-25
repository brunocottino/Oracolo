# Pre-registrazione: scenari condizionati (pessimistico / mediano / ottimistico) con Fear & Greed e IFC

Scritto e committato **prima** dei test.

## Fear & Greed di Oracolo (0 = paura estrema, 100 = euforia), solo dati gratuiti Yahoo, valori fino a t-1
Media dei ranghi percentili (finestra mobile 252 sedute) di:
1. momentum: S&P 500 / media mobile 125 sedute;
2. volatilità: -(VIX / media mobile 50 sedute);
3. beni rifugio: rendimento 20 sedute S&P 500 meno variazione 20 sedute del rendimento del Treasury 10 anni (^TNX)
   cambiata di segno (titoli di Stato che salgono = paura);
4. obbligazioni spazzatura: rendimento 20 sedute HYG meno IEF (dal 2007; prima la media usa le altre tre).
CNN Fear & Greed non usato: storico troppo corto per un test.

## Modello degli scenari
Variabile: z = rendimento logaritmico a h sedute / (σ giornaliera × √h), σ come in bands.py.
Quantili 10%, 50%, 90% di z stimati con regressione quantile lineare (sklearn QuantileRegressor, alpha 0,01)
su: Fear & Greed, regime di volatilità log(σ21/σ252), e solo per le azioni i ranghi di `run` e `cgo` (IFC).
Finestra espandibile, riaddestrata ogni 252 sedute, solo esiti già noti (purge di h sedute).
**Benchmark:** quantili empirici passati di z senza condizioni (la forchetta attuale di bands.py).

## Campione
azioni (73), ETF paesi, settori, indici; h = 31 e 63; origini ogni h sedute (non sovrapposte); dal 1993.

## Criteri
- C1: perdita pinball media (somma dei 3 quantili) inferiore al benchmark con t ≥ 3 (Diebold-Mariano sulle date,
  Newey-West ritardo 1), in almeno 3 universi su 4 per almeno un orizzonte ciascuno.
- C2: copertura della banda 10%-90% tra 77% e 83%.
- C3: miglioramento positivo anche dal 2013.
Tutti: gli scenari condizionati sostituiscono la forchetta fissa nell'app. Altrimenti resta la forchetta fissa,
con l'aggiunta dello scenario mediano (quantile 50% empirico).

---
## Esito (25/10/2026, parte sopra invariata, commit d7d6ffa). `python -m lab.scenario_test`
Miglioramento della perdita pinball rispetto alla forchetta fissa: tra -0,33% e +0,24% in tutti gli 8 casi
(t tra -1,9 e +0,8). C1 e C2 falliti: **SPENTO**, resta la forchetta fissa + scenario mediano.
Limite: copertura identica al benchmark, quindi la penalità alpha = 0,01 (pre-registrata) ha probabilmente azzerato
i coefficienti; un test con penalità diversa va pre-registrato a parte, non ritarato su questi dati.
