# Prompt per Claude Code — IPB Extreme

Implementa e migliora questo repository senza inventare dati né dichiarare validato un modello non testato.

## Obiettivo
Costruire un MVP di ricerca quantitativa per indici azionari con:
1. indice IPB -100/+100;
2. punteggio euristico di rischio inversione 0–100, chiaramente distinto da una probabilità;
3. probabilità rialzo/laterale/ribasso walk-forward a 5/10/20 sedute;
4. backtest con benchmark e costi;
5. dashboard trasparente.

## Prima di modificare
- Esamina tutti i file.
- Identifica e correggi bug di leakage temporale, allineamento delle date e download dati.
- Non eliminare le avvertenze metodologiche.
- Non usare dati sintetici come se fossero dati reali.
- Se il provider fallisce, mostra un errore esplicito.
- Aggiungi test automatici con dataset sintetico SOLO per test di correttezza del codice, marcato chiaramente come tale.

## Requisiti quantitativi
- Tutti i segnali del giorno t devono usare solo informazioni note alla chiusura di t.
- Le posizioni devono essere applicate non prima della seduta successiva.
- Per ogni previsione, il training deve escludere righe per cui il target futuro non era ancora osservabile alla data della previsione.
- Usare split cronologici e walk-forward; niente shuffle casuale.
- Calibrare le probabilità esclusivamente su dati precedenti alla data prevista. Riportare Brier score, log-loss e calibration bins solo quando il campione è sufficiente.
- Riportare metriche per sottoperiodo, non solo aggregate.
- Eseguire analisi di sensibilità su orizzonti, soglie e costi.
- Includere costi per turnover e documentare le ipotesi di esecuzione.
- Separare target di direzione e target di inversione; non chiamare "probabilità d'inversione" il punteggio euristico.
- Aggiungere veri dati breadth storici dei componenti solo se disponibili con corretta gestione dei titoli delistati; altrimenti mantenere l'etichetta "proxy".
- Evitare ottimizzazione eccessiva dei pesi. Confrontare contro benchmark semplici.
- Versionare feature, soglie e modello.

## Requisiti tecnici
- Aggiungi pytest e test per: no look-ahead, segnale applicato al giorno successivo, classi probabilistiche, date mancanti, ticker fallito e costi.
- Gestisci API di yfinance che restituiscono colonne MultiIndex.
- Aggiungi cache dati e gestione dei limiti/richieste fallite con messaggi chiari.
- Aggiungi un comando CLI per esportare CSV e metriche JSON oltre alla dashboard.
- Evita valori di probabilità presentati se non disponibili o non calibrati.
- Mantieni Python 3.11+ e documenta le dipendenze.
- Esegui tutti i test e correggi gli errori reali; non dichiarare test superati se non li hai eseguiti.
- Non aggiungere esecuzione automatica di ordini né connessioni a broker.
- Prima di concludere, fornisci riepilogo delle modifiche, comandi di avvio e limiti rimasti.

## Criterio di accettazione
Il progetto si installa, avvia la dashboard, scarica dati se il provider è disponibile, calcola i fattori, genera risultati non fuorvianti, esegue un backtest temporalmente coerente e passa i test automatici. Se un requisito non può essere verificato nell'ambiente, dichiararlo esplicitamente.
