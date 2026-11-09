"""Promemoria operativo personale (uso personale, non è un consiglio per clienti).
python controllo_switch.py  →  stato dello switch RSP→QQQ e livelli MSCI World."""
import yfinance as yf

# Switch del 5/11/2026: venduto RSP, comprato QQQ (~13.000 €)
QQQ0, RSP0, EUR, SCADENZA = 647.05, 216.87, 13000, 63
# MSCI World (proxy URTH): sopra il massimo di novembre = fine dei massimi decrescenti (~4.930 indice);
# sotto il minimo del 5/11 = correzione riprende (~4.730 indice)
URTH_SU, URTH_GIU = 207.87, 199.63


def main():
    d = yf.download(["QQQ", "RSP", "URTH"], start="2026-09-01", auto_adjust=False, progress=False)["Close"].dropna()
    q, r, u = d.QQQ, d.RSP, d.URTH
    s = (q.iloc[-1] / QQQ0 - 1) - (r.iloc[-1] / RSP0 - 1)
    g = q.pct_change(21).iloc[-1] - r.pct_change(21).iloc[-1]
    n = sum(1 for x in d.index if str(x.date()) > "2026-11-05")
    k = [a for a, c in (("SCADENZA", n >= SCADENZA), ("DIVARIO RICHIUSO", g >= -0.02),
                        ("TESI SBAGLIATA", s <= -0.04)) if c]
    print(("SEGNALE: TORNARE SU RSP (" + ", ".join(k) + ") " if k else "Switch: nessun segnale. ")
          + f"Dati al {d.index[-1].date()}: switch {s:+.1%} ({s * EUR - 26:+.0f} € netti), "
          f"divario 1 mese {g:+.1%}, sedute {n}/{SCADENZA}")
    x = u.iloc[-1]
    stato = ("SOPRA il massimo di novembre: prima conferma rialzista" if x > URTH_SU else
             "SOTTO il minimo del 5/11: la correzione riprende" if x < URTH_GIU else "tra i due livelli: rumore")
    print(f"MSCI World (URTH {x:.2f}; livelli {URTH_GIU} / {URTH_SU}, indice ~4.730 / ~4.930): {stato}")


if __name__ == "__main__":
    main()
