"""Impostazioni comuni dei test: dati sintetici e archivio temporaneo.
Va importato PRIMA di qualsiasi modulo della piattaforma."""
import os
import sys
import tempfile
import time
import traceback

os.environ["ORACOLO_DEMO"] = "1"
os.environ.setdefault("ORACOLO_AUTO_SCAN", "0")
if "ORACOLO_TEST_DB" not in os.environ:
    _d = tempfile.mkdtemp(prefix="oracolo_test_")
    os.environ["ORACOLO_TEST_DB"] = os.path.join(_d, "t.sqlite")
os.environ["ORACOLO_DB"] = os.environ["ORACOLO_TEST_DB"]
os.environ["ORACOLO_MODEL"] = os.path.join(os.path.dirname(os.environ["ORACOLO_TEST_DB"]), "model.pkl")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_module(mod_globals):
    """Esegue tutte le funzioni test_* del modulo e stampa un riepilogo."""
    tests = [(k, v) for k, v in mod_globals.items() if k.startswith("test_") and callable(v)]
    failed = 0
    t0 = time.time()
    for name, fn in tests:
        t1 = time.time()
        try:
            fn()
            print(f"  OK   {name}  ({time.time() - t1:.1f} s)", flush=True)
        except Exception:
            failed += 1
            print(f"  FAIL {name}", flush=True)
            traceback.print_exc()
    print(f"{len(tests) - failed}/{len(tests)} test superati in {time.time() - t0:.0f} s", flush=True)
    return failed
