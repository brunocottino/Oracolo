"""Misure (feature) di CLASSE A: hanno una data storica e si possono testare sul passato.

Regola anti look-ahead: ogni valore alla data t usa solo prezzi fino a t e solo
eventi già pubblici a t (annunci utili disponibili da t+2, giudizi degli
analisti dalla seduta successiva). Tutte le misure sono orientate come dice la
letteratura: valore alto = rendimento futuro atteso più alto (es. la volatilità
entra con il segno meno, perché i titoli meno volatili hanno reso di più).

Classi di dati:
  A  prezzi, VIX, date degli annunci utili, upgrade/downgrade  -> test sul passato
  B  istantanee di oggi (revisioni stime, consenso, short interest, prezzo obiettivo,
     opzioni) -> raccolte ogni notte (collector.py), peso 0 finché non promosse
  C  bilanci -> solo informativi; in un test storico andrebbero usati con 90 giorni di ritardo
"""
import math

import numpy as np
import pandas as pd

FUNDAMENTALS_LAG_DAYS = 90   # classe C

STOCK_FEATURES = [
    {"key": "mom_12_1", "label": "Momentum 12-1 mesi", "lit": True, "ref": "Jegadeesh-Titman 1993"},
    {"key": "res_mom", "label": "Momentum residuo / rischio", "lit": True, "ref": "Blitz-Huij-Martens 2011"},
    {"key": "fip", "label": "Regolarità del trend (frog in the pan)", "lit": True, "ref": "Da-Gurun-Warachka 2014"},
    {"key": "rev_1m", "label": "Inversione a 1 mese", "lit": True, "ref": "Jegadeesh 1990"},
    {"key": "low_vol", "label": "Bassa volatilità (63 sedute)", "lit": True, "ref": "Ang-Hodrick-Xing-Zhang 2006"},
    {"key": "high_52w", "label": "Vicinanza al massimo a 52 settimane", "lit": True, "ref": "George-Hwang 2004"},
    {"key": "low_beta", "label": "Beta basso", "lit": True, "ref": "Frazzini-Pedersen 2014"},
    {"key": "sue", "label": "Sorpresa sugli utili (SUE)", "lit": True, "ref": "Bernard-Thomas 1989"},
    {"key": "ear", "label": "Reazione all'annuncio (3 giorni)", "lit": True, "ref": "Chan-Jegadeesh-Lakonishok 1996"},
    {"key": "ea_recent", "label": "Annuncio recente (sedute, inverso)", "lit": False, "ref": "nessuna direzione documentata"},
    {"key": "upg_30", "label": "Upgrade netti 30 giorni", "lit": True, "ref": "Womack 1996"},
    {"key": "upg_90", "label": "Upgrade netti 90 giorni", "lit": True, "ref": "Jegadeesh-Kim-Krische-Lee 2004"},
    {"key": "tgt_chg_30", "label": "Variazione prezzo obiettivo 30 giorni", "lit": True, "ref": "Brav-Lehavy 2003"},
]
STOCK_FLAGS = ["f_events", "f_grades"]
EVENT_KEYS = {"sue", "ear", "ea_recent"}
GRADE_KEYS = {"upg_30", "upg_90", "tgt_chg_30"}

INDEX_FEATURES = [
    {"key": "tsmom_12", "label": "Trend 12 mesi (time-series)", "lit": True, "ref": "Moskowitz-Ooi-Pedersen 2012"},
    {"key": "tsmom_3", "label": "Trend 3 mesi (time-series)", "lit": True, "ref": "Moskowitz-Ooi-Pedersen 2012"},
    {"key": "vrp", "label": "Premio per il rischio di varianza (VIX² - realizzata)", "lit": True, "ref": "Bollerslev-Tauchen-Zhou 2009"},
    {"key": "vix_term", "label": "Rapporto VIX / VIX3M", "lit": True, "ref": "Johnson 2017 (struttura a termine del VIX)"},
]
INDEX_FLAGS = ["f_vix"]

# Classe B: istantanee raccolte ogni notte (collector.py). Peso 0 finché non promosse.
CLASS_B_FIELDS = [
    {"key": "eps_rev_30d", "label": "Revisioni stime EPS 30 gg (su - giù)"},
    {"key": "eps_trend_30d", "label": "Variazione stima EPS anno prossimo 30 gg"},
    {"key": "rec_mean", "label": "Consenso analisti (1 = compra, 5 = vendi)"},
    {"key": "short_pct_float", "label": "Short interest (% flottante)"},
    {"key": "short_change", "label": "Variazione short interest mese"},
    {"key": "days_to_cover", "label": "Giorni per coprire lo short"},
    {"key": "target_upside", "label": "Prezzo obiettivo medio vs prezzo"},
    {"key": "atm_iv", "label": "Volatilità implicita ATM (45 gg)"},
    {"key": "iv_skew", "label": "Skew della volatilità implicita"},
    {"key": "p_market", "label": "Probabilità di rialzo implicita nelle opzioni"},
]


def labels():
    d = {f["key"]: f for f in STOCK_FEATURES + INDEX_FEATURES}
    return d


# --------------------------------------------------------------------------
def align(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Allinea una serie a un altro calendario usando solo l'ultimo valore noto (nessun dato futuro)."""
    s = series[~series.index.duplicated(keep="last")].sort_index()
    u = s.index.union(index)
    return s.reindex(u).ffill().reindex(index)


def rolling_beta(r: pd.Series, rb: pd.Series, n=252, min_periods=200) -> pd.Series:
    cov = r.rolling(n, min_periods=min_periods).cov(rb)
    var = rb.rolling(n, min_periods=min_periods).var()
    return cov / var.replace(0, np.nan)


def stock_raw(px: pd.Series, bench: pd.Series, events: dict | None) -> pd.DataFrame:
    """Misure grezze per un titolo, una riga per seduta del titolo.
    px = prezzi rettificati del titolo, bench = indice locale (qualsiasi calendario)."""
    px = px.astype(float)
    idx = px.index
    b = align(bench.astype(float), idx)
    lp = np.log(px)
    lb = np.log(b)
    r = lp.diff()
    rb = lb.diff().fillna(0.0)
    beta = rolling_beta(r, rb)
    f = pd.DataFrame(index=idx)
    mom = lp.shift(21) - lp.shift(252)
    f["mom_12_1"] = mom
    # momentum residuo (Blitz-Huij-Martens): residui sulla finestra 12-1 con il beta di oggi
    n = 231
    Sr = r.rolling(n).sum().shift(21)
    Sb = rb.rolling(n).sum().shift(21)
    Srr = (r * r).rolling(n).sum().shift(21)
    Sbb = (rb * rb).rolling(n).sum().shift(21)
    Srb = (r * rb).rolling(n).sum().shift(21)
    res_sum = Sr - beta * Sb
    var_e = (Srr - 2 * beta * Srb + beta ** 2 * Sbb) / n - (res_sum / n) ** 2
    f["res_mom"] = res_sum / np.sqrt(var_e.clip(lower=1e-12) * n)
    pos = (r > 0).astype(float).where(r.notna()).rolling(n).mean().shift(21)
    neg = (r < 0).astype(float).where(r.notna()).rolling(n).mean().shift(21)
    f["fip"] = np.sign(mom) * (pos - neg)
    f["rev_1m"] = -(lp - lp.shift(21))
    f["low_vol"] = -r.rolling(63, min_periods=50).std()
    f["high_52w"] = lp - np.log(px.rolling(252, min_periods=200).max())
    f["low_beta"] = -beta
    f["beta"] = beta
    # residuo giornaliero con il beta del giorno prima
    e = r - beta.shift(1) * rb
    f["sig_res_d"] = e.rolling(252, min_periods=200).std()
    f["sig_d"] = r.rolling(252, min_periods=200).std()
    f["sig_b_d"] = rb.rolling(252, min_periods=200).std()
    ev = events or {}
    _event_features(f, px, e, ev.get("earnings") or [])
    _grade_features(f, ev.get("grades") or [])
    return f


def _event_features(f, px, e, earnings):
    idx = f.index
    nidx = len(idx)
    f["sue"] = np.nan
    f["ear"] = np.nan
    f["ea_recent"] = np.nan
    f["sue_raw"] = np.nan
    f["days_since_ea"] = np.nan
    rows = []
    for x in sorted(earnings, key=lambda q: q["date"]):
        if x.get("eps_est") is None or x.get("eps_act") is None:
            continue
        p = int(idx.searchsorted(pd.Timestamp(x["date"]), side="left"))
        if p < 1 or p + 1 >= nidx:      # annuncio fuori dallo storico o reazione non ancora osservata
            continue
        rows.append((p, float(x["eps_act"]) - float(x["eps_est"])))
    if not rows:
        return
    pxv = px.values
    ev = e.values
    raw, std_sue, ear, avail, ppos = [], [], [], [], []
    for i, (p, surprise) in enumerate(rows):
        s = surprise / pxv[p - 1]
        raw.append(s)
        prev = raw[max(0, i - 8):i]
        if len(prev) >= 4:
            sd = float(np.std(prev, ddof=1))
            std_sue.append(s / sd if sd > 0 else np.nan)
        else:
            std_sue.append(np.nan)
        w = ev[p - 1:p + 2]
        ear.append(float(np.nansum(w)) if np.isfinite(w).sum() >= 2 else np.nan)
        avail.append(p + 2)              # disponibile solo da t+2
        ppos.append(p)
    avail = np.array(avail)
    k = np.searchsorted(avail, np.arange(nidx), side="right") - 1
    ok = k >= 0
    kk = np.where(ok, k, 0)
    since = np.arange(nidx) - np.array(ppos)[kk]
    fresh = ok & (since <= 126)
    f["sue"] = np.where(fresh, np.array(std_sue)[kk], np.nan)
    f["sue_raw"] = np.where(fresh, np.array(raw)[kk], np.nan)
    f["ear"] = np.where(fresh, np.array(ear)[kk], np.nan)
    f["days_since_ea"] = np.where(fresh, since, np.nan)
    f["ea_recent"] = -f["days_since_ea"]


def _grade_features(f, grades):
    idx = f.index
    nidx = len(idx)
    for c in ("upg_30", "upg_90", "tgt_chg_30", "n_up_30", "n_down_30"):
        f[c] = np.nan
    if not grades:
        return
    net = np.zeros(nidx)
    ups = np.zeros(nidx)
    downs = np.zeros(nidx)
    tg_s = np.zeros(nidx)
    tg_c = np.zeros(nidx)
    anyg = np.zeros(nidx)
    for g in grades:
        p = int(idx.searchsorted(pd.Timestamp(g["date"]), side="left")) + 1   # dalla seduta successiva
        if p >= nidx:
            continue
        a = g.get("action")
        v = 1.0 if a == "up" else -1.0 if a == "down" else 0.0
        net[p] += v
        ups[p] += v > 0
        downs[p] += v < 0
        anyg[p] += 1
        tp, tn = g.get("tgt_prior"), g.get("tgt_new")
        if tp and tn and tp > 0:
            tg_s[p] += tn / tp - 1
            tg_c[p] += 1
    S = lambda a, w: pd.Series(a, index=idx).rolling(w).sum().values
    covered = np.cumsum(anyg) > 0
    f["upg_30"] = np.where(covered, S(net, "30D"), np.nan)
    f["upg_90"] = np.where(covered, S(net, "90D"), np.nan)
    f["n_up_30"] = np.where(covered, S(ups, "30D"), np.nan)
    f["n_down_30"] = np.where(covered, S(downs, "30D"), np.nan)
    c30 = S(tg_c, "30D")
    s30 = S(tg_s, "30D")
    f["tgt_chg_30"] = np.where(covered, np.where(c30 > 0, s30 / np.maximum(c30, 1), 0.0), np.nan)


def stock_targets(px: pd.Series, bench: pd.Series, beta: pd.Series, h: int) -> pd.DataFrame:
    """Obiettivo: rendimento logaritmico RESIDUO a h sedute contro l'indice locale.
    Il beta è quello stimato con i soli dati fino all'origine."""
    idx = px.index
    b = align(bench.astype(float), idx)
    lp = np.log(px.astype(float))
    lb = np.log(b)
    fwd = lp.shift(-h) - lp
    fwdb = lb.shift(-h) - lb
    out = pd.DataFrame(index=idx)
    out["fwd"] = fwd
    out["fwdb"] = fwdb
    out["y_res"] = fwd - beta * fwdb
    end = pd.Series(idx, index=idx).shift(-h)
    out["end_date"] = end
    return out


# --------------------------------------------------------------------------
def index_raw(px: pd.Series, vix: pd.Series | None = None, vix3m: pd.Series | None = None) -> pd.DataFrame:
    px = px.astype(float)
    idx = px.index
    lp = np.log(px)
    r = lp.diff()
    f = pd.DataFrame(index=idx)
    f["tsmom_12"] = lp - lp.shift(252)
    f["tsmom_3"] = lp - lp.shift(63)
    f["sig_d"] = r.rolling(252, min_periods=200).std()
    f["rv21"] = r.rolling(21).var() * 252
    if vix is not None:
        v = align(vix, idx)
        f["vix"] = v
        f["vrp"] = (v / 100.0) ** 2 - f["rv21"]
        if vix3m is not None:
            f["vix_term"] = v / align(vix3m, idx)
        else:
            f["vix_term"] = np.nan
    else:
        f["vix"] = np.nan
        f["vrp"] = np.nan
        f["vix_term"] = np.nan
    return f


def ts_rank(s: pd.Series, window=2520, min_periods=252) -> pd.Series:
    """Percentile della misura rispetto alla PROPRIA storia passata, in [-0,5; 0,5]."""
    return s.rolling(window, min_periods=min_periods).rank(pct=True) - 0.5


def index_targets(px: pd.Series, rf: pd.Series | None, rf_const: float, h: int) -> pd.DataFrame:
    """Obiettivo indici: rendimento in eccesso sul tasso a breve a h sedute."""
    idx = px.index
    lp = np.log(px.astype(float))
    fwd = lp.shift(-h) - lp
    if rf is not None:
        rr = align(rf, idx).fillna(rf_const)
    else:
        rr = pd.Series(rf_const, index=idx)
    rf_h = np.log1p(rr) * h / 252
    out = pd.DataFrame(index=idx)
    out["fwd"] = fwd
    out["rf_h"] = rf_h
    out["y_res"] = fwd - rf_h
    out["end_date"] = pd.Series(idx, index=idx).shift(-h)
    return out


# --------------------------------------------------------------------------
def xs_rank(panel: pd.DataFrame, cols, by="date") -> pd.DataFrame:
    """Rango per data in [-0,5; 0,5]; dato mancante = 0."""
    out = pd.DataFrame(index=panel.index)
    g = panel.groupby(by)
    for c in cols:
        rk = g[c].rank(method="average")
        n = g[c].transform("count")
        out["x_" + c] = ((rk - 0.5) / n - 0.5).fillna(0.0)
    return out


def rank_against(value, reference):
    """Rango di un valore rispetto a una distribuzione di riferimento (es. la sezione
    trasversale dell'ultima data), stessa scala [-0,5; 0,5]."""
    if value is None or not np.isfinite(value):
        return 0.0
    ref = np.asarray([v for v in reference if v is not None and np.isfinite(v)], float)
    n = len(ref)
    if n == 0:
        return 0.0
    below = float(np.sum(ref < value)) + 0.5 * float(np.sum(ref == value))
    return float((below + 0.5) / (n + 1) - 0.5)


def describe(key, raw: dict) -> str:
    """Frase breve, senza gergo, per il valore di una misura."""
    v = raw.get(key)
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "dato non disponibile"
    pc = lambda x, d=0: f"{x * 100:+.{d}f}%".replace(".", ",")
    if key == "mom_12_1":
        return f"rendimento 12-1 mesi {pc(math.exp(v) - 1)}"
    if key == "res_mom":
        return f"momentum residuo {v:+.1f} (rendimento oltre il mercato / rischio)".replace(".", ",")
    if key == "fip":
        return f"trend {'regolare' if v > 0.04 else 'irregolare' if v < -0.04 else 'neutro'} ({pc(v)} giorni utili)"
    if key == "rev_1m":
        return f"ultimo mese {pc(math.exp(-v) - 1)}"
    if key == "low_vol":
        return f"volatilità 3 mesi {abs(v) * math.sqrt(252) * 100:.0f}% annua"
    if key == "high_52w":
        return f"{pc(math.exp(v) - 1)} dal massimo a 52 settimane"
    if key == "low_beta":
        return f"beta {-v:.2f}".replace(".", ",")
    if key == "sue":
        return f"sorpresa utili {v:+.1f}σ".replace(".", ",")
    if key == "ear":
        return f"reazione all'annuncio {pc(v, 1)} oltre il mercato"
    if key == "ea_recent":
        return f"{-v:.0f} sedute dall'ultimo annuncio"
    if key == "upg_30":
        return f"{v:+.0f} upgrade netti in 30 giorni"
    if key == "upg_90":
        return f"{v:+.0f} upgrade netti in 90 giorni"
    if key == "tgt_chg_30":
        return f"prezzo obiettivo {pc(v, 1)} in 30 giorni"
    if key == "tsmom_12":
        return f"trend 12 mesi {pc(math.exp(v) - 1)}"
    if key == "tsmom_3":
        return f"trend 3 mesi {pc(math.exp(v) - 1)}"
    if key == "vrp":
        return f"premio di varianza {v * 100:+.1f} punti".replace(".", ",")
    if key == "vix_term":
        return f"VIX / VIX3M {v:.2f}".replace(".", ",")
    return f"{v:.3g}"
