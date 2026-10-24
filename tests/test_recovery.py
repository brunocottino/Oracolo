"""Validazione del banco di prova sui dati sintetici:
  - RECUPERO: il generatore inserisce un segnale noto (sorpresa utili, IC ~0,04 sul
    rendimento residuo a 31 sedute); il banco di prova deve trovarlo con t >= 2 e IC > 0
  - NULLO: senza segnale inserito la stessa misura non deve risultare significativa
  - percorso ATTIVO: con un segnale forte il modello si accende e produce qualche segnale;
    l'INTERRUTTORE globale spegne tutti i segnali se il modello è spento
Esecuzione:  python tests/test_recovery.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401

import numpy as np  # noqa: E402

import config  # noqa: E402
import data  # noqa: E402
import db  # noqa: E402
from lab import panel as P  # noqa: E402
from lab import research as R  # noqa: E402

db.init()
RESULTS = {}


def _set_signal(sig, ic):
    config.DEMO_SIGNAL = sig
    config.DEMO_SIGNAL_IC = ic
    data.clear_demo_cache()


def test_recover_injected_signal():
    _set_signal("sue", 0.04)
    rep, _ = R.run_panel("stocks", fast=True)
    f = {r["key"]: r for r in rep["features"]}
    sue = f["sue"]
    RESULTS["sue_ic"] = sue["ic"]
    RESULTS["sue_t"] = sue["t"]
    RESULTS["sue_n_indep"] = sue["n_indep"]
    RESULTS["stocks_state_ic004"] = rep["state"]
    RESULTS["stocks_dev"] = {k: rep["dev"].get(k) for k in ("ic", "ic_t", "bss", "ece", "n_indep")}
    print(f"    sorpresa utili: IC {sue['ic']:+.4f}, t {sue['t']:.2f}, {sue['n_indep']:.0f} periodi indipendenti; "
          f"stato modello {rep['state']}")
    assert sue["ic"] > 0 and sue["t"] >= 2
    assert sue["bh"]
    # le misure di puro rumore (giudizi degli analisti nel generatore) non devono risultare forti
    for k in ("upg_30", "upg_90"):
        assert abs(f[k]["t"]) < 3, (k, f[k]["t"])


def test_null_signal_not_found():
    _set_signal("none", 0.0)
    panel, cal, info = P.build_stock_panel()
    first = int(panel["origin_pos"].min()) + config.LAB["min_train"]
    hs = len(cal) - config.LAB["holdout"]
    op, ep = panel["origin_pos"].values, panel["end_pos"].values
    dev = (op >= first) & np.isfinite(ep) & (ep < hs)
    rows = R.feature_table(panel, dev, dev & False, [{"key": "sue", "label": "", "lit": True, "ref": ""}],
                           info["h"], info["step"])
    RESULTS["sue_null_t"] = rows[0]["t"]
    print(f"    senza segnale inserito: IC sorpresa utili {rows[0]['ic']:+.4f}, t {rows[0]['t']:.2f}")
    assert rows[0]["t"] < 2


def test_active_path_and_global_switch():
    """Verifica del meccanismo: con un segnale molto forte (IC 0,12) il modello si accende e i
    titoli estremi ricevono segnali; poi l'interruttore spegne tutto. (Con IC 0,04-0,07 su 9 anni
    la regola di Wilson, giustamente, non concede quasi mai un segnale.)"""
    _set_signal("sue", 0.12)
    out = R.run(fast=True, kinds=("stocks", "index"))
    st = out["stocks"]
    RESULTS["stocks_state_ic012"] = st["state"]
    print(f"    segnale forte: modello azioni {st['state']}; misure attive {st['live'].get('active') if st['live'] else []}")
    assert st["state"] == "attivo", st["reasons"]
    assert "sue" in st["live"]["active"]
    import engine
    from lab import model as M
    live = st["live"]
    order = np.argsort(live["xs_pred"])
    cands = [live["xs_tickers"][i] for i in list(order[:4]) + list(order[-6:])]
    sigs = {}
    for t in cands:
        o = engine.analyze(t, include_history=False)
        sigs[t] = o["plan"]["signal"]
        assert o["plan"]["model_on"]
        assert 0 <= o["plan"]["position_size"] <= 0.10
        json.dumps(o)
    print(f"    segnali sui titoli estremi: {sigs}")
    assert any(s != "NESSUN SEGNALE" for s in sigs.values())
    # interruttore globale: modello spento -> NESSUN SEGNALE per tutti, con spiegazione
    rep = db.lab_report_last("all")
    rep["stocks"]["state"] = "spento"
    rep["stocks"]["reasons"] = ["test di prova dell'interruttore"]
    rep.pop("ts", None)
    db.lab_report_put("all", rep)
    M.reload()
    for t in cands:
        o = engine.analyze(t, include_history=False)
        assert o["plan"]["signal"] == "NESSUN SEGNALE"
        assert "spento" in o["plan"]["why"]
        assert o["plan"]["position_size"] == 0
    _set_signal("sue", 0.04)


if __name__ == "__main__":
    f = common.run_module(globals())
    print("RISULTATI", json.dumps(RESULTS, default=str))
    sys.exit(1 if f else 0)
