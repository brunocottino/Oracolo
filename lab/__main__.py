"""Lancio da riga di comando:  python -m lab   (oppure  python -m research)
Opzioni:  --fast   versione rapida (niente modello sfidante, ablation più grossolana)
          --stocks / --index   solo uno dei due panel"""
import json
import sys
import time


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    import db
    db.init()
    from lab import research
    kinds = ("stocks", "index")
    if "--stocks" in argv:
        kinds = ("stocks",)
    if "--index" in argv:
        kinds = ("index",)
    t0 = time.time()
    stop = {"x": False}

    import threading

    def ticker():
        last = ""
        while not stop["x"]:
            m = f"{research.STATE['pct'] * 100:5.1f}%  {research.STATE['msg']}"
            if m != last:
                print(m, flush=True)
                last = m
            time.sleep(2)
    th = threading.Thread(target=ticker, daemon=True)
    th.start()
    out = research.run(fast="--fast" in argv, kinds=kinds)
    stop["x"] = True
    for k in kinds:
        r = out[k]
        d = r["dev"]
        print(f"\n== {k}: stato {r['state'].upper()}  ({r['model']})")
        if r["reasons"]:
            print("   motivi:", "; ".join(r["reasons"]))
        print(f"   periodi indipendenti {d.get('n_indep', 0):.0f}, osservazioni {d.get('n_obs')}, anni {d.get('years', 0):.1f}")
        print(f"   IC {d.get('ic')}, t {d.get('ic_t')}, BSS {d.get('bss')}, ECE {d.get('ece')}")
        for f in r["features"]:
            print(f"   {f['key']:<12} IC {f['ic'] if f['ic'] is not None else float('nan'):+.4f} "
                  f"t {f['t'] if f['t'] is not None else float('nan'):+.2f}  {f['status']}")
    print(f"\nTempo totale {time.time() - t0:.0f} s")
    if "--json" in argv:
        print(json.dumps(out)[:2000])


if __name__ == "__main__":
    main()
