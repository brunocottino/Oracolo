"""Tesi degli ospiti di "The Bull" (PREREG_BULL.md). Lancio: python -m lab.bull_test

Informativo, peso 0. Fonti gratuite senza chiave: Shiller ie_data.xls, Damodaran histimpl.xls, Yahoo ^GSPC.
"""
import os
import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "data", "ext")
URL_SHILLER = "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls"
URL_DAMO = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xls"


def _get(url, name):
    os.makedirs(EXT, exist_ok=True)
    p = os.path.join(EXT, name)
    if not os.path.exists(p):
        r = requests.get(url, timeout=60, headers={"User-Agent": "oracolo-research"})
        r.raise_for_status()
        with open(p, "wb") as f:
            f.write(r.content)
    return p


def shiller():
    x = pd.read_excel(_get(URL_SHILLER, "ie_data.xls"), sheet_name="Data", header=None, skiprows=8)
    x = x[[0, 1, 2, 3, 4, 6, 12]].copy()
    x.columns = ["date", "P", "D", "E", "CPI", "GS10", "CAPE"]
    x = x[pd.to_numeric(x["date"], errors="coerce").notna()].astype(float)
    y = np.floor(x["date"]).astype(int)
    m = np.round((x["date"] - y) * 100).astype(int)
    x.index = pd.PeriodIndex.from_fields(year=y, month=m, freq="M")
    x["D"] = x["D"].ffill()  # gli ultimi mesi non hanno ancora il dividendo
    x["CAPE"] = pd.to_numeric(x["CAPE"], errors="coerce")
    tr = (x["P"] + x["D"] / 12).div(x["P"].shift(1))  # rendimento totale nominale mensile
    x["tr_nom"] = tr.fillna(1).cumprod()
    x["tr_real"] = x["tr_nom"] / x["CPI"] * x["CPI"].iloc[0]
    x["px_real"] = x["P"] / x["CPI"]
    return x.dropna(subset=["P", "CPI"])


def damodaran():
    d = pd.read_excel(_get(URL_DAMO, "histimpl.xls"), header=None)
    d = d[d[0].astype(str).str.fullmatch(r"(19|20)\d\d")]
    out = pd.DataFrame({"erp": pd.to_numeric(d[15], errors="coerce"),
                        "tbond": pd.to_numeric(d[10], errors="coerce")})
    out.index = d[0].astype(int)
    return out


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan


def ols(y, x):
    """pendenza e t classico (usare solo su osservazioni non sovrapposte)"""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    s2 = e @ e / (len(y) - 2)
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b[1], b[1] / se, r2, len(y)


def maxdd(v):
    v = np.asarray(v, float)
    return float((v / np.maximum.accumulate(v) - 1).min())


def cagr(v, months):
    return (v[-1] / v[0]) ** (12 / months) - 1


def h1(s):
    print("\nH1 Carlson, pazienza: % finestre con rendimento totale reale > 0 (S&P dal 1871)")
    w = np.log(s["tr_real"].values)
    for h in (1, 3, 12, 60, 120, 240):
        r = w[h:] - w[:-h]
        nono = r[::h]
        print(f"  {h:>3} mesi: {np.mean(r > 0) * 100:5.1f}% (tutte le finestre)  "
              f"{np.mean(nono > 0) * 100:5.1f}% (non sovrapposte, n={len(nono)})  peggiore {np.expm1(r.min()) * 100:+.0f}%")


def h2():
    import sys
    sys.path.insert(0, HERE)
    import data, db
    db.init()
    df, _ = data.get_history("^GSPC", years=80)
    c = (df["close"] if "close" in df else df["Close"]).dropna()
    c = c[c.index >= "1950-01-01"]
    r = np.log(c).diff().dropna()
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    print(f"\nH2 Carlson/Zweig, giorni migliori: ^GSPC solo prezzo {c.index[0].date()}..{c.index[-1].date()}")
    base = np.expm1(r.sum() / yrs)
    for k in (0, 10, 20, 50):
        rr = r.drop(r.nlargest(k).index) if k else r
        print(f"  senza i {k:>2} giorni migliori: {np.expm1(rr.sum() / yrs) * 100:5.2f}% annuo")
    for k in (10, 20, 50):
        rr = r.drop(r.nlargest(k).index).drop(r.nsmallest(k).index)
        print(f"  senza i {k:>2} migliori E i {k} peggiori: {np.expm1(rr.sum() / yrs) * 100:5.2f}% annuo (base {base * 100:.2f}%)")
    best, worst = r.nlargest(20).index, r.nsmallest(20).index
    pos = {d: i for i, d in enumerate(r.index)}
    near = np.mean([min(abs(pos[b] - pos[w]) for w in worst) <= 10 for b in best])
    print(f"  dei 20 giorni migliori, a ≤10 sedute da uno dei 20 peggiori: {near * 100:.0f}%")
    vol = r.rolling(21).std().shift(1) * np.sqrt(252)
    print(f"  volatilità del mese prima: giorni migliori {vol[best].median() * 100:.0f}%, tutti i giorni {vol.median() * 100:.0f}%")


def h3(s):
    print("\nH3 Maggiulli, somma unica vs PAC 12 mesi (liquidità a 0 nominale), valore nominale a 12 mesi")
    v = s["tr_nom"].values
    wins, diff = [], []
    for i in range(len(v) - 12):
        lump = v[i + 12] / v[i]
        dca = np.mean([v[i + 12] / v[i + k] for k in range(12)])
        wins.append(lump > dca)
        diff.append(lump - dca)
    wins, diff = np.array(wins), np.array(diff)
    print(f"  somma unica vince nel {wins.mean() * 100:.0f}% delle finestre (n={len(wins)}), "
          f"vantaggio medio {diff.mean() * 100:+.1f} pt; quando perde, in media {diff[~wins].mean() * 100:+.1f} pt")
    idx = s.index[:len(wins)]
    post = np.array([p.year >= 1990 for p in idx])
    print(f"  dal 1990: {wins[post].mean() * 100:.0f}%")


def h4(s):
    print("\nH4 Faber, media mobile 10 mesi (liquidità a 0 nominale, rendimenti reali)")
    p = s["P"]
    sig = (p > p.rolling(10).mean()).shift(1)  # decisione a fine mese, applicata al mese dopo
    ret = s["tr_nom"].pct_change()
    infl = s["CPI"].pct_change()
    ok = sig.notna() & ret.notna()
    for nome, mask in (("intero campione", ok), ("dal 2008 (dopo la pubblicazione)", ok & (s.index.year >= 2008))):
        bh = ((1 + ret[mask]) / (1 + infl[mask])).cumprod().values
        tm = ((1 + ret[mask] * sig[mask].astype(float)) / (1 + infl[mask])).cumprod().values
        n = int(mask.sum())
        print(f"  {nome}: compra-e-tieni {cagr(bh, n) * 100:.1f}% annuo, maxDD {maxdd(bh) * 100:.0f}% | "
              f"media mobile {cagr(tm, n) * 100:.1f}% annuo, maxDD {maxdd(tm) * 100:.0f}%, investito {sig[mask].mean() * 100:.0f}% del tempo")


def h5(s):
    print("\nH5 Arnott/Shiller, CAPE e rendimento reale futuro (finestre non sovrapposte)")
    w = np.log(s["tr_real"].values)
    cape = np.log(s["CAPE"].values)
    for h, nome in ((3, "3 mesi"), (12, "1 anno"), (120, "10 anni")):
        fut = np.full(len(w), np.nan)
        fut[:-h] = (w[h:] - w[:-h]) * 12 / h
        idx = np.arange(0, len(w), h)
        b, t, r2, n = ols(fut[idx], cape[idx])
        print(f"  {nome:>7}: pendenza {b * 100:+.1f} pt annui per +100% log(CAPE), t {t:+.2f}, R² {r2:.2f}, n={n}")
    last = s["CAPE"].dropna()
    q = (last < last.iloc[-1]).mean()
    print(f"  ultimo CAPE nel file ({last.index[-1]}): {last.iloc[-1]:.1f}, sopra il {q * 100:.0f}% della storia")
    hi = last.index[last > 30]
    w_s = pd.Series(w, index=s.index)
    fut10 = (w_s.shift(-120) - w_s) / 10
    print(f"  mesi con CAPE > 30 e 10 anni di futuro noti: {fut10.loc[hi].notna().sum()}, "
          f"rendimento reale medio {np.expm1(fut10.loc[hi].mean()) * 100:+.1f}% annuo")


def h6(s, d):
    print("\nH6 Damodaran, premio implicito (FCFE) a fine anno vs rendimento in eccesso sui T-bond")
    dec = s[s.index.month == 12]["tr_nom"]
    dec.index = dec.index.year
    tr = dec.pct_change().shift(-1)  # anno successivo
    dd = d.join(tr.rename("tr"), how="inner").dropna(subset=["erp"])
    dd["ex1"] = dd["tr"] - dd["tbond"]
    b, t, r2, n = ols(dd["ex1"].values, dd["erp"].values)
    print(f"  1 anno: pendenza {b:+.2f} (rendimento in eccesso per +1 pt di ERP), t {t:+.2f}, R² {r2:.2f}, n={n} ({dd.index[0]}-{dd.index[-1]})")
    lv = dec
    ex5 = {y: (lv.get(y + 5) / lv.get(y)) ** 0.2 - 1 - d.loc[y, "tbond"]
           for y in d.index if y + 5 in lv.index and y in lv.index}
    e5 = pd.Series(ex5)
    j = d.loc[e5.index[::5], "erp"]
    b, t, r2, n = ols(e5.iloc[::5].values, j.values)
    print(f"  5 anni (non sovrapposti): pendenza {b:+.2f}, t {t:+.2f}, R² {r2:.2f}, n={n}")
    print(f"  ERP implicito più recente ({d.index[-1]}): {d['erp'].iloc[-1] * 100:.2f}%, "
          f"percentile {(d['erp'] < d['erp'].iloc[-1]).mean() * 100:.0f}° dal {d.index[0]}")


def main():
    s = shiller()
    print(f"Shiller: {s.index[0]}..{s.index[-1]}, {len(s)} mesi")
    h1(s)
    h2()
    h3(s)
    h4(s)
    h5(s)
    h6(s, damodaran())


if __name__ == "__main__":
    main()
