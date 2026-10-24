# Oracolo online gratis su Hugging Face (Space privato)

Una sola volta, circa 10 minuti:

1. **Account:** registrati gratis su https://huggingface.co (basta l'email).
2. **Space:** in alto a destra *New → Space*. Nome `oracolo`, SDK **Docker** (modello *Blank*),
   hardware *CPU basic – free*, visibilità **Private** (lo vedi solo tu, da loggato).
3. **Token:** *Settings → Access Tokens → Create new token*, tipo **Write**. Copialo.
4. **GitHub:** nel repository `Oracolo` vai su *Settings → Secrets and variables → Actions*:
   - scheda *Secrets*: nuovo segreto `HF_TOKEN` = il token del punto 3;
   - scheda *Variables*: nuova variabile `HF_SPACE` = `tuo-nome-utente-hf/oracolo`.
5. **Primo deploy:** *Actions → Deploy su Hugging Face → Run workflow*. Da lì in poi ogni
   push su `main` aggiorna lo Space da solo.

Lo Space si costruisce in 3-5 minuti; poi l'indirizzo è
`https://huggingface.co/spaces/tuo-nome-utente-hf/oracolo` (anche dal telefono, da loggato).

Come funziona sullo Space gratuito:
- Al primo avvio parte il Laboratorio rapido (circa 10-20 minuti, scarica Yahoo, Wikipedia e
  SEC). Finché non finisce, i titoli mostrano "non addestrato".
- Il disco è temporaneo: a ogni riavvio cache e report si rifanno da capo.
- Lo Space gratuito va in pausa dopo 48 ore senza visite; si risveglia alla prima apertura
  (un minuto circa). La scansione notturna gira solo se è sveglio.
