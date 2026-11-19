"""Test della parte personale, senza rete e senza dati veri:
  - codici Bloomberg -> Yahoo, lettura dei termini dei certificati (Leonteq e Marex)
  - distanza dal livello della cedola sul sottostante peggiore
  - avvisi su livelli e su coppie (switch)
  - diario: piano obbligatorio, catena di hash che rileva le modifiche
Esecuzione:  python tests/test_personale.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402,F401

os.environ["ORACOLO_PRIVATO"] = tempfile.mkdtemp(prefix="oracolo_priv_")

import pandas as pd  # noqa: E402

import diario  # noqa: E402
import personale  # noqa: E402
from sources import certificati as sc  # noqa: E402

LEONTEQ = """Final Terms
      ISIN:                                                CH0000000001
      (f)    Initial Fixing Date:                  In respect of each Share, 12/03/2026
            (iii)     Barrier Level:                     In respect of each Underlying, 50 per cent of the Initial
                                                    Underlying Table
 (i)   Underlying(s)   Bloom-    ISIN            Exchange(s) Initial           Barrier          Autocall         Coupon
                       berg                                   Fixing Level     Level            Trigger          Trigger Level
                       Code                                   (100.00%)        (50.00%)*        Level(s)         (50.00%)*
                                                                                                (100.00%/
                                                                                                98.00%)*
 1     ANGLOGOL        AU UN     GB00BRXH        NYSE         will be          will be          will be          will be
       D ASHANTI                 2664                         determined       determined       determined       determined on
 2     NOVO            NOVOB DC  DK0062498       Copenhagen   will be          will be          will be          will be
       NORDISK                   333                          determined       determined       determined       determined on
 3     PAN             PAAS      CA6979001       NYSE         will be          will be          will be          will be
       AMERICAN        UN        089                          determined       determined       determined       determined on
*Levels are expressed in percentage of the Initial Fixing Level
"""

MAREX = """Securities ISIN IT0000000002
     (i)      Strike Date:                           18 November 2025.
      (v)     Barrier Level:                       In respect of each Underlying Asset, 40.00 per cent.
"""


def test_termini():
    assert sc.bbg_a_yahoo("STLAM IM") == "STLAM.MI"
    assert sc.bbg_a_yahoo("NOVOB DC") == "NOVO-B.CO"
    assert sc.bbg_a_yahoo("MSTR UQ") == "MSTR"
    assert sc.bbg_a_yahoo("XYZ ZZ") is None
    t = sc.termini_da_testo("CH0000000001", LEONTEQ)
    assert t["fissazione"] == "2026-03-12", t
    assert t["barriera"] == 50.0 and t["trigger"] == 50.0, t
    assert t["sottostanti"] == ["AU", "NOVO-B.CO", "PAAS"], t
    m = sc.termini_da_testo("IT0000000002", MAREX)
    assert m == {"fissazione": "2025-11-18", "barriera": 40.0, "trigger": 40.0, "trigger_assunto": True}, m
    assert sc.termini_da_testo("XX0000000000", LEONTEQ) == {}
    assert sc.numero("1.022,78") == 1022.78 and sc.numero("n.d.") is None
    print("termini ok")


def test_distanze():
    idx = pd.to_datetime(["2026-03-11", "2026-03-12", "2026-11-18"])
    ch = {"A": pd.Series([90, 100, 80], index=idx), "B": pd.Series([10, 10, 4], index=idx)}
    st = sc.stato_da_livelli({"fissazione": "2026-03-12", "trigger": 50, "barriera": 50, "sottostanti": ["A", "B"]}, ch)
    assert st["ticker"] == "B" and abs(st["perf"] + 0.6) < 1e-9
    assert abs(st["dist_trigger"] - (1 - 0.5 * 10 / 4)) < 1e-9 and not st["paga"]
    st = sc.stato_da_livelli({"fissazione": "2026-03-12", "trigger": 50, "sottostanti": ["A"]}, ch)
    assert st["paga"] and abs(st["dist_trigger"] - 0.375) < 1e-9
    assert sc.stato_da_prezzo(64, 100)["giudizio"] == "probabilmente non paga"
    assert sc.stato_da_prezzo(990, 1000)["giudizio"] == "probabilmente paga"
    print("distanze ok")


def test_avvisi():
    s = lambda v: pd.Series(v, index=pd.date_range("2026-11-01", periods=len(v)))  # noqa: E731
    pr = {"URTH": s([200, 197.7]), "QQQ": s([100, 94]), "RSP": s([50, 50])}
    regole = [{"nome": "sotto", "ticker": "URTH", "sotto": 198.29}, {"nome": "sopra", "ticker": "URTH", "sopra": 207.87},
              {"nome": "switch", "ticker": "QQQ", "contro": "RSP", "base": 100.0, "base_contro": 50.0, "sotto_rel": -0.04}]
    nomi = [a["nome"] for a in personale.valuta_avvisi(regole, pr)]
    assert nomi == ["sotto", "switch"], nomi
    print("avvisi ok")


def test_diario():
    try:
        diario.aggiungi("apertura", strumento="X", ticker="X", prezzo=10)
        raise AssertionError("una decisione senza piano non va registrata")
    except ValueError:
        pass
    a = diario.aggiungi("apertura", strumento="X", ticker="X", prezzo=10, perche="test", orizzonte_giorni=21,
                        stop=9, data="2026-11-02")
    assert a["dopo"] is True
    try:
        diario.aggiungi("chiusura", rif=99, prezzo=11)
        raise AssertionError("chiusura di una posizione inesistente")
    except ValueError:
        pass
    diario.aggiungi("chiusura", rif=a["id"], prezzo=11, data="2026-11-10")
    recs = diario.leggi()
    assert diario.verifica(recs)[0]
    idx = pd.date_range("2026-11-01", "2026-11-12")
    loc = pd.DataFrame({"X": [10.0] * len(idx), "ACWI": [100.0] * len(idx)}, index=idx)
    v = diario.valuta(recs[0], recs[1], loc, loc, "ACWI")
    assert abs(v["rend"] - 0.1) < 1e-9 and v["giorni"] == 8 and v["chiusa"] and not v["stop_toccato"]
    # una modifica a posteriori rompe la catena
    p = diario._path()
    righe = open(p, encoding="utf-8").read().splitlines()
    r0 = json.loads(righe[0])
    r0["stop"] = 5
    righe[0] = json.dumps(r0)
    open(p, "w", encoding="utf-8").write("\n".join(righe) + "\n")
    assert not diario.verifica(diario.leggi())[0]
    print("diario ok")


if __name__ == "__main__":
    test_termini()
    test_distanze()
    test_avvisi()
    test_diario()
    print("TEST PERSONALE SUPERATI")
