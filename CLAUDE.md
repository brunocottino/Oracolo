# Oracolo: contesto per Claude Code

App Python/Flask personale di previsione su azioni (45 giorni, h=31 sedute) e indici (3 mesi, h=63).
Utente: Bruno, private banker italiano, studia per il CFA. Rispondi in italiano, conciso, con i numeri.
Uso personale: mai consigli per clienti, il disclaimer resta sempre.

## Regola fissa
Solo fonti gratuite senza registrazione, account o chiavi API. Non proporre mai servizi a pagamento.

## Regole per risparmiare token
- NON rileggere tutto il progetto. Apri solo i file del compito (la mappa è qui sotto).
- Niente subagenti salvo richiesta esplicita.
- Modifiche piccole e mirate, poi `python tests/run_all.py`. Riporta solo l'esito e i numeri chiave.
- Se un comando lungo (banco di prova) supera i 10 minuti, usa `--fast` o meno titoli.
- Non stampare file interi né output lunghi: usa grep, tail, head.

## Mappa
- `app.py`: API Flask + `static/` (index.html, app.js, style.css): interfaccia mobile, 6 schede.
- `engine.py`: analisi del singolo titolo, piano operativo, regola del segnale (`trade_plan`).
- `lab/`: banco di prova panel walk-forward (`features.py`, `panel.py`, `model.py`, `stats.py`, `research.py`). Lancio: `python -m research` (`--fast`).
- `priced.py`: "cosa c'è nel prezzo" (probabilità implicita nelle opzioni, reverse DCF, VIX).
- `data.py`: download prezzi ed eventi (Yahoo/yfinance) + generatore demo. Le nuove fonti vanno in `sources/`.
- `aggiorna.py`: aggiornamento automatico senza Claude (fotografia giornaliera in `data/oracolo/`, Laboratorio rapido ogni 7 giorni); lo lancia il pianificatore del PC (`installa_aggiornamento_windows.bat`, cron in `setup_mac.sh`). Pagina: `/oracolo`.
- `collector.py`: istantanee notturne di classe B (stime, short, opzioni) → tabella `snapshots`.
- `config.py`: tutti i parametri (soglie, costi, LAB). `universe.py`: titoli e indici.
- `agents/`: agenti informativi (peso 0); solo il "modello di base" fornisce σ.
- `tests/run_all.py`: tutti i test (~3 min, usa ORACOLO_DEMO=1 da sé).

## Principi da NON violare
1. Classi di dati:
   - A (con data storica): si backtesta.
   - B (istantanee di oggi): solo raccolta, peso 0 finché non ci sono ≥12 periodi indipendenti con t≥2 e BH superato.
   - C (bilanci): ritardo di 90 giorni.
2. Niente look-ahead: una feature all'origine t usa solo dati ≤ t (eventi da t+2).
3. Campione dichiarato in periodi indipendenti, non in righe.
4. Holdout (ultime 504 sedute) usato solo come interruttore, mai per tarare.
5. Se il criterio di successo fallisce, tutti i titoli mostrano NESSUN SEGNALE. È un esito valido.
6. Precisione realistica 52-55%: diffida di risultati migliori (overfitting).

## Piano in corso
Vedi `ROADMAP.md`. Lavora una fase per volta e spunta le caselle completate.
