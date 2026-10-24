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
