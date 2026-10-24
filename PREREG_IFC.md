# Pre-registrazione: IFC, Indice di Fragilità Comportamentale

Scritto e committato **prima** di qualsiasi calcolo sui dati. Non si cambiano componenti, pesi,
target o soglie dopo aver visto i risultati. Se fallisce, si dichiara fallito.

## Perché questo indice
Lezioni dei test precedenti (NOTE_RISULTATI.md, ipb_extreme/REPORT_TEST.md): la direzione dei prezzi
è quasi imprevedibile con dati gratuiti; il rischio lo è di più. L'IFC non prova a dire se un titolo
sale o scende: stima se è **fragile**, cioè esposto a un crollo improvviso proprio (non del mercato).

## Ipotesi
Un titolo diventa fragile quando si sommano quattro stati comportamentali, ciascuno noto alla data t:
compratori attirati dall'attenzione, molti detentori in guadagno pronti a vendere, volume anomalo
(disaccordo, Chen-Hong-Stein 2001) e calma apparente dopo una corsa. La combinazione è l'ipotesi
nuova; le singole parti hanno riferimenti in letteratura.

## Componenti (rango trasversale per data, valore alto = più fragile)
1. `dturn` volume anomalo: log(media volume 21 sedute) - log(media volume 252 sedute). Chen-Hong-Stein 2001.
2. `run` corsa passata: rendimento residuo (rispetto al beta di mercato) delle ultime 126 sedute. Chen-Hong-Stein 2001.
3. `cgo` guadagno latente sul prezzo di carico stimato (Grinblatt-Han 2005), già in lab/features.py.
4. `attn` choc di attenzione Wikipedia: log visite 5 giorni - log mediana dell'anno precedente (segno +).
5. `calm` compressione della volatilità residua: -(log σ 21 sedute - log σ 252 sedute).

IFC = media dei ranghi disponibili (in [-0,5; 0,5]), richiesti almeno 3 componenti su 5. Pesi uguali, fissi.

## Target (rendimenti residui giornalieri e = r - β(t-1)·r_indice locale, nelle 31 sedute dopo t)
- **Principale:** NCSKEW futura (Chen-Hong-Stein), asimmetria negativa dei residui: più alta = più crolli.
- Secondario (solo riportato): CRASH = 1 se il minimo residuo nelle 31 sedute è sotto -3,09 σ (σ dei residui delle 252 sedute fino a t).

## Benchmark semplice (controlli)
NCSKEW passata (126 sedute), volatilità residua passata (252 sedute), beta. L'IFC deve aggiungere
informazione oltre a questi.

## Campione
73 titoli di universe.py, prezzi Yahoo, visite Wikipedia. Origini ogni 31 sedute del calendario comune
(finestre future non sovrapposte). Sviluppo = origini il cui orizzonte finisce prima delle ultime 504 sedute;
holdout = ultime 504 sedute, valutato **una sola volta**.

## Criteri di successo (tutti sul campione di sviluppo)
- S1: IC di Spearman medio (Fama-MacBeth) tra IFC e NCSKEW futura > 0 con t ≥ 3.
- S2: IC parziale (IFC e target residualizzati sui controlli, per data) > 0 con t ≥ 2.
- S3: IC medio annuo positivo in almeno il 60% degli anni.
Holdout: si riporta l'IC con il suo segno, qualunque sia.
Precisione attesa realistica: IC 0,02-0,05. Un IC molto più alto va trattato come sospetto di errore.

---
## Esito (aggiunto dopo il test, 24/10/2026; la parte sopra è invariata, commit ac583d7)
Campione: 72 titoli (ROG.SW non scaricabile: 404 Yahoo), 510 origini di sviluppo dal 1963, 17 di holdout.

| Criterio | Risultato | Esito |
|---|---|---|
| S1 IC IFC vs NCSKEW futura | +0,076, t 6,11 | superato |
| S2 IC parziale sui controlli | +0,079, t 5,80 | superato |
| S3 anni positivi | 86% di 43 | superato |
| Holdout (16 date) | +0,050, t 1,55 | segno positivo |
| Secondario: crolli (CRASH) | -0,019, t -1,55 | nessun effetto |

Benchmark: NCSKEW passata +0,017 (t 1,52), volatilità passata -0,023 (t -1,68).
Componenti: run +0,077 (t 6,1), cgo +0,085 (t 6,8), attn +0,022 (t 1,6, 9 anni), calm +0,005, dturn -0,001.

**Diagnostiche (dopo il test, non cambiano i criteri):**
- Regge nel tempo e fuori dagli USA: 2005-24 IC +0,093 (t 9,2, 20 anni positivi su 20); 1990-2004 +0,085;
  1963-89 +0,015 (circa 11 titoli per data). USA +0,057, Italia/Europa +0,083, Asia/Emergenti +0,153.
- **Non è fragilità.** Con IFC alto i crolli non aumentano (IC con CRASH +0,012, t 0,96; minimo futuro -0,027, t -1,9);
  diminuiscono i balzi al rialzo (massimo futuro -0,076, t -5,6; salti > 3σ -0,060, t -4,7).
- Tutto il segnale viene da `run` e `cgo` (correlazione dei ranghi 0,65): è l'effetto noto di Chen-Hong-Stein 2001
  (rendimenti passati alti → asimmetria futura più negativa). Le tre componenti nuove (dturn, attn, calm)
  insieme hanno IC -0,006.

**Conclusione onesta:** criteri formali superati, ipotesi comportamentale NON confermata. L'indice misura
"esaurimento del potenziale di rialzo" (meno balzi positivi dopo una corsa), non il rischio di crollo, e le parti
nuove non contribuiscono. Rinominarlo o ricombinarlo adesso sarebbe data snooping: un indice
"esaurimento del rialzo" va pre-registrato da capo e verificato solo su dati futuri.
