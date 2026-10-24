"""Esegue tutti i test, ognuno in un processo separato con un archivio temporaneo proprio.
    python tests/run_all.py"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["test_smoke.py", "test_lookahead.py", "test_behavior.py", "test_stats.py", "test_recovery.py"]


def main():
    t0 = time.time()
    bad = []
    for f in FILES:
        print(f"\n=== {f}", flush=True)
        env = dict(os.environ)
        env["ORACOLO_TEST_DB"] = os.path.join(tempfile.mkdtemp(prefix="oracolo_t_"), "t.sqlite")
        env.pop("ORACOLO_DEMO_IC", None)
        env.pop("ORACOLO_DEMO_SIGNAL", None)
        r = subprocess.run([sys.executable, os.path.join(HERE, f)], env=env)
        if r.returncode:
            bad.append(f)
    print(f"\nTempo totale {time.time() - t0:.0f} s. " + ("TUTTI I TEST SUPERATI" if not bad else f"FALLITI: {bad}"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
