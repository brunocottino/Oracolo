"""Motore di rendimento: scambio di panico e beta nel panico (PREREG_RENDIMENTO.md).  python -m lab.return_test"""
import json
import sys

import numpy as np
import pandas as pd

import config
import data
import db
import universe

from .horizon_test import nw_t
from .panic_test import TICKERS as OOS, panic_score

H = 21
SAMPLES = {
    "indici": (OOS + list(universe.INDICES), "^GSPC"),
    "etf_usd": ("SPY QQQ IWM EFA EEM VGK EWJ EWG EWQ EWI EWU EWP EWL EWC EWA EWZ EWW EWH EWT EWY FXI INDA".split(), "SPY"),
}


def load(tickers):
    db.init()
    px = {}
    for t in tickers:
        try:
            px[t] = data.get_history(t)[0]["adj"].astype(float)
        except Exception as e:
            print("salto", t, str(e)[:50], file=sys.stderr)
    P = pd.DataFrame(px).sort_index()
    return P[P.index >= "1993-01-01"].ffill(limit=5)


def _split(cal, h):
    hold = len(cal) - config.LAB["holdout"]
    ds = [(d, i) for i, d in enumerate(cal) if i % h == 0 and i + h < len(cal)]
    dev = [d for d, i in ds if i + h < hold]
    return {"sviluppo": dev, "dal2013": [d for d in dev if d.year >= 2013], "holdout": [d for d, i in ds if i >= hold]}


def _stat(x, raw=None):
    if not x:
        return None
    o = {"date": len(x), "vantaggio": round(float(np.mean(x)), 4), "t": nw_t(x)}
    if raw is not None:
        o.update(casi=len(raw), pct_meglio=round(float((np.array(raw) > 0).mean()), 3))
    return o


def swap(P, bench):
    sc = panic_score(P)
    fwd = P.shift(-H) / P - 1
    out = {}
    for name, dates in _split(P.index, H).items():
        ew, sp, raw = [], [], []
        for d in dates:
            f, s = fwd.loc[d], sc.loc[d]
            ok = f.notna() & s.notna()
            sel = ok & (s >= 2)
            if ok.sum() < 5 or sel.sum() == 0:
                continue
            x = f[sel] - f[ok].mean()
            ew.append(float(x.mean()))
            raw += list(x.values)
            sb = sel.copy()
            sb[bench] = False
            if sb.any() and pd.notna(f.get(bench)):
                sp.append(float((f[sb] - f[bench]).mean()))
        out[name] = {"vs_media": _stat(ew, raw), "vs_sp500": _stat(sp)}
    return out


def beta_panic(P):
    sc = panic_score(P[["^GSPC"]])["^GSPC"]
    out = {}
    for t in ("^NDX", "^RUT"):
        out[t] = {}
        for h in (21, 63):
            spl = _split(P.index, h)
            diff = (P[t].shift(-h) / P[t]) - (P["^GSPC"].shift(-h) / P["^GSPC"])
            norm = diff.loc[spl["sviluppo"]].mean()
            for name, dates in spl.items():
                x = [float(diff[d] - norm) for d in dates if sc.get(d, 0) >= 2 and pd.notna(diff[d])]
                out[t][f"{h}|{name}"] = _stat(x, x)
    return out


def simulate(P, cost=0.001):
    sc = panic_score(P)
    cal = P.index
    dates = [d for i, d in enumerate(cal) if i % H == 0 and i + H < len(cal)]
    fwd = P.shift(-H) / P - 1
    rb, rs, w_prev = [], [], None
    for d in dates:
        f, s = fwd.loc[d], sc.loc[d]
        ok = f.notna() & s.notna()
        if ok.sum() < 5:
            continue
        base = ok / ok.sum()
        pan = ok & (s >= 2)
        w = base.astype(float)
        if pan.any():
            tilt = min(0.5, 0.25 * pan.sum())
            w = base * (1 - tilt) + pan * (tilt / pan.sum())
        turn = float((w - (w_prev if w_prev is not None else base)).abs().sum())
        w_prev = w
        rb.append(float((base * f.fillna(0)).sum()))
        rs.append(float((w * f.fillna(0)).sum()) - cost * turn)

    def m(r):
        r = np.array(r)
        eq = np.cumprod(1 + r)
        yrs = len(r) * H / 252
        return {"annuo": round(float(eq[-1] ** (1 / yrs) - 1), 4), "vol": round(float(r.std() * np.sqrt(252 / H)), 4),
                "drawdown": round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4)}
    d = np.array(rs) - np.array(rb)
    return {"base": m(rb), "scambio": m(rs), "periodi": len(rb), "anni": round(len(rb) * H / 252, 1),
            "t_differenza": nw_t(d), "periodi_con_panico": int((np.abs(d) > 1e-12).sum())}


def robustezza():
    """Verifica del Panico assoluto (PREREG_PANICO.md) dal 1993 su tutte le 21 griglie di origini.  python -m lab.return_test panico"""
    from .horizon_test import evaluate
    out = {}
    for nome, tk in (("15_fuori_campione", OOS), ("14_universe", list(universe.INDICES))):
        P = load(tk)
        sc = panic_score(P)
        sig = pd.DataFrame(np.where(sc >= 2, "COMPRA", "STAI FERMO"), index=P.index, columns=P.columns).where(sc.notna())
        cal, fwd = P.index, P.shift(-H) / P - 1
        for per, f in (("1993+", lambda d: True), ("1993-2007", lambda d: d.year < 2008), ("2008+", lambda d: d.year >= 2008),
                       ("2013+", lambda d: d.year >= 2013)):
            E, T = [], []
            for o in range(H):
                ds = [d for d in cal[o::H] if cal.get_loc(d) + H < len(cal)]
                c = evaluate(sig, fwd, [d for d in ds if f(d)], fwd.loc[ds].mean()).get("COMPRA")
                if c:
                    E.append(c["edge"]); T.append(c["t"] or 0)
            out[f"{nome}|{per}"] = {"vantaggio_medio": round(float(np.mean(E)), 4), "min": min(E), "max": max(E),
                                    "t_medio": round(float(np.mean(T)), 2), "griglie_t2": f"{sum(t >= 2 for t in T)}/{H}"}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def main():
    res, Ps = {}, {}
    for name, (tk, bench) in SAMPLES.items():
        Ps[name] = load(list(dict.fromkeys(tk)))
        res[name] = swap(Ps[name], bench)
        res[name]["strumenti"] = int(Ps[name].shape[1])

    def ok(n, k, t=None):
        v = (res[n][k] or {}).get("vs_media") or {}
        return (v.get("vantaggio") or 0) > 0 and (t is None or (v.get("t") or 0) >= t)
    res["H1_superata"] = bool(all(ok(n, "sviluppo", 2) and ok(n, "dal2013") for n in SAMPLES) and ok("etf_usd", "holdout"))
    res["H2"] = beta_panic(Ps["indici"])
    res["simulazione"] = simulate(Ps["etf_usd"])
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    robustezza() if "panico" in sys.argv[1:] else main()
