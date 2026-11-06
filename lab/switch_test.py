"""Switch relativo dopo un divario estremo a 1 mese: test preregistrato (PREREG_SWITCH.md).
python -m lab.switch_test"""
import json

import numpy as np
import pandas as pd

import data
import db

from .stats import nw_t

PAIRS = [("QQQ", "SPY"), ("SPY", "RSP"), ("IWM", "SPY"), ("IWF", "IWD"), ("MDY", "SPY"),
         ("EFA", "SPY"), ("EEM", "SPY"), ("XLK", "SPY"), ("XLF", "SPY"), ("XLE", "SPY"),
         ("XLV", "SPY"), ("XLU", "SPY"), ("XLY", "XLP"), ("SMH", "SPY")]
NOTE = ("QQQ", "RSP")
L, H, Z, COST, COOL = 21, 63, 2.0, 0.002, 63


def prices(tickers):
    out = {}
    for t in tickers:
        try:
            out[t] = data.get_history(t)[0]["adj"].astype(float)
        except Exception as e:
            print("salto", t, str(e)[:60])
    return pd.DataFrame(out).sort_index().ffill(limit=5)


def episodes(a, b, rule="z", thr=Z, h=H, lag=1):
    """Elenco di (data, direzione, rendimento relativo netto, riferimento)."""
    p = pd.concat([a, b], axis=1).dropna()
    pa, pb = p.iloc[:, 0], p.iloc[:, 1]
    s = pa.pct_change(L) - pb.pct_change(L)
    if rule == "z":
        sd = s.rolling(756, min_periods=504).std().shift(1)
        x = s / sd
        trig = np.where(x <= -thr, 1, np.where(x >= thr, -1, 0))
    else:  # soglia grezza a senso unico, come nella nota
        trig = np.where(s <= thr, 1, 0)
    ea, eb = pa.shift(-lag), pb.shift(-lag)
    fa, fb = pa.shift(-lag - h) / ea - 1, pb.shift(-lag - h) / eb - 1
    rel = (fa - fb).values
    base = np.nanmean(rel[::h])
    out, last = [], -10**9
    for i, d in enumerate(p.index):
        if trig[i] != 0 and i - last > COOL:
            last = i
            if np.isfinite(rel[i]):
                out.append((d, int(trig[i]), float(trig[i] * rel[i] - COST), float(trig[i] * base)))
    return out


def summary(eps):
    if not eps:
        return {"n": 0}
    df = pd.DataFrame(eps, columns=["date", "dir", "ret", "base"])
    df["edge"] = df.ret - df.base
    m = df.groupby(df.date.dt.to_period("M")).edge.mean()
    post = df[df.date.dt.year >= 2013]
    return {"n": len(df), "mesi": int(len(m)), "ret_medio": round(df.ret.mean(), 4),
            "vinti": round(float((df.ret > 0).mean()), 2), "edge": round(m.mean(), 4),
            "t": round(nw_t(m.values, 1)[1], 2),
            "edge_dal2013": round(post.edge.mean(), 4) if len(post) else None, "n_dal2013": len(post)}


def main():
    db.init()
    P = prices(sorted({t for pr in PAIRS + [NOTE] for t in pr}))
    res, allep = {"coppie": {}}, []
    for a, b in PAIRS:
        if a in P and b in P:
            e = episodes(P[a], P[b])
            allep += e
            res["coppie"][f"{a}/{b}"] = summary(e)
    tot = summary(allep)
    res["totale_fuori_campione"] = tot
    pos = [v["edge"] for v in res["coppie"].values() if v.get("n")]
    res["successo"] = bool(tot.get("mesi", 0) >= 12 and tot["edge"] > 0 and tot["t"] >= 2
                           and (tot["edge_dal2013"] or 0) > 0 and np.mean(np.array(pos) > 0) > 0.5)
    # coppia della nota: regola z e griglia della soglia grezza (descrittiva)
    a, b = P[NOTE[0]], P[NOTE[1]]
    res["nota_regola_z"] = summary(episodes(a, b))
    res["nota_griglia"] = {f"{thr:+.0%} h{h} lag{lag}": summary(episodes(a, b, "raw", thr, h, lag))
                           for thr in (-0.06, -0.08, -0.10, -0.12) for h in (21, 42, 63) for lag in (0, 1)}
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return res


if __name__ == "__main__":
    main()
