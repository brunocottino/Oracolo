# Cartella privato/ (esempi)

La parte personale di Oracolo legge i file nella cartella `privato/`, che **non va mai su GitHub** (è in `.gitignore`:
il repository è pubblico). Copia questi esempi in `privato/` sul tuo PC e mettici i tuoi dati.

- `portafoglio.json`: posizioni (ISIN, ticker Yahoo se c'è, quantità, prezzo di carico, prezzo all'estratto, tema).
  Senza ticker il prezzo arriva da Borsa Italiana (ETF ed ETC); se manca anche lì resta quello dell'estratto.
- `certificati.json`: ISIN, quantità, carico, nominale. I termini (fissazione, barriera, livello cedola, sottostanti)
  si leggono da soli dai documenti di Borsa Italiana; `termini` serve solo a correggerli o completarli.
- `avvisi.json`: livelli da sorvegliare sull'ultimo prezzo (`sotto`/`sopra`), anche per coppie (`contro`, `sotto_rel`).
  Con `"avvisi_certificati": false` non compaiono gli avvisi sulle cedole a rischio.
- `diario.jsonl`: si scrive solo con `python diario.py` (vedi l'aiuto in testa al file).

Poi: `python personale.py` → `privato/OGGI_PRIVATO.md`. Lo fa anche `aggiorna.py` sul PC ogni mattina.
