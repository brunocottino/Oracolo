"""Modello di base (volatilità + prior CAPM) e agente informativo Holt.

Monte Carlo, GARCH e ARIMA prima erano tre "agenti" che votavano separatamente,
ma la loro direzione veniva tutta dallo stesso prior CAPM: contarli tre volte
gonfiava l'"accordo". Ora sono UN SOLO modello di base che fornisce:
  - sigma: la volatilità attesa sull'orizzonte (GARCH unita alla volatilità di lungo periodo)
  - il prior: rendimento atteso CAPM (risk-free + beta x premio al rischio)
  - le code: quantili da 10.000 scenari con innovazioni t di Student
  - un controllo ARIMA (memoria nei rendimenti) solo informativo.
Se sono installate le librerie di riferimento (arch, statsmodels) vengono usate;
altrimenti un'implementazione equivalente in numpy/scipy.
"""
import math
import warnings

import numpy as np
from scipy.optimize import minimize
from scipy.stats import kurtosis

import config
from .base import Agent, horizon_sigma, prior_mu, shrunk_mu

try:
    from arch import arch_model  # https://github.com/bashtage/arch
    HAS_ARCH = True
except ImportError:
    HAS_ARCH = False


# ---------------------------------------------------------------------------
def _garch_fit_numpy(r):
    """GARCH(1,1) gaussiano stimato con massima verosimiglianza."""
    x = r * 100.0
    var0 = float(np.var(x))

    def nll(p):
        mu, om, a, b = p
        if om <= 0 or a < 0 or b < 0 or a + b >= 0.999:
            return 1e10
        e = x - mu
        hh = _garch_var(e, om, a, b, var0)
        return 0.5 * np.sum(np.log(hh) + e ** 2 / hh)

    best = None
    for b0 in (0.85, 0.92):
        p0 = [float(np.mean(x)), var0 * (1 - 0.05 - b0), 0.05, b0]
        resx = minimize(nll, p0, method="Nelder-Mead", options={"maxiter": 2000, "xatol": 1e-6, "fatol": 1e-6})
        if best is None or resx.fun < best.fun:
            best = resx
    mu, om, a, b = best.x
    e = x - mu
    hh = _garch_var(e, om, a, b, var0)
    h_next = om + a * e[-1] ** 2 + b * hh[-1]
    return mu / 100, om, a, b, h_next


def _garch_var(e, om, a, b, var0):
    """Ricorsione h_t = om + a e_{t-1}^2 + b h_{t-1}, vettorizzata."""
    from scipy.signal import lfilter
    u = om + a * e[:-1] ** 2
    rest = lfilter([1.0], [1.0, -b], u, zi=[b * var0])[0]
    return np.concatenate([[var0], rest])


def garch_path(r, h):
    """Varianza giornaliera prevista per i prossimi h giorni e persistenza."""
    if HAS_ARCH:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            am = arch_model(r * 100, vol="GARCH", p=1, q=1, dist="t", rescale=False)
            fit = am.fit(disp="off")
            fc = fit.forecast(horizon=h, reindex=False)
            var_path = fc.variance.values[-1] / 1e4
            a = float(fit.params.get("alpha[1]", 0))
            b = float(fit.params.get("beta[1]", 0))
        return var_path, a + b
    _, om, a, b, h_next = _garch_fit_numpy(r)
    pers = a + b
    lr = om / (1 - pers)
    k = np.arange(h)
    return (lr + pers ** k * (h_next - lr)) / 1e4, pers


def arima_order(r, max_p=5):
    """Ordine AR scelto con il criterio di Akaike (solo per informazione)."""
    best = None
    for p in range(0, max_p + 1):
        if p == 0:
            resid = r - r.mean()
            k = 1
        else:
            Y = r[p:]
            X = np.column_stack([np.ones(len(Y))] + [r[p - i:-i] for i in range(1, p + 1)])
            coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
            resid = Y - X @ coef
            k = p + 1
        aic = len(resid) * math.log(np.var(resid)) + 2 * k
        if best is None or aic < best[0]:
            best = (aic, p)
    return best[1]


class ModelloBase(Agent):
    name = "Modello di base (volatilità e CAPM)"
    family = "base"
    source = "GARCH(1,1) (arch o MLE scipy) + Monte Carlo t di Student + controllo ARIMA"
    description = ("Non è un voto: fornisce a tutta la piattaforma l'ampiezza del rischio e il punto di "
                   "partenza. La volatilità unisce un GARCH(1,1) (dopo giorni agitati il mercato resta "
                   "agitato per un po') e la volatilità di lungo periodo. Il rendimento 'a priori' viene dal "
                   "CAPM: tasso privo di rischio + beta × premio al rischio del 5%. 10.000 scenari con code "
                   "grasse danno le probabilità degli estremi. Il controllo ARIMA dice solo se c'è memoria "
                   "nei rendimenti, senza spostare la previsione.")

    def run(self, ctx):
        r = ctx["r"][-1000:]
        h = ctx["h"]
        try:
            var_path, pers = garch_path(r, h)
            sig_g = float(math.sqrt(np.sum(var_path)))
            ann_now = math.sqrt(var_path[0] * 252)
            ann_end = math.sqrt(var_path[-1] * 252)
        except Exception:
            sig_g, pers, ann_now, ann_end = None, None, None, None
        sig_b, sig_d = horizon_sigma(ctx)
        sigma = math.sqrt(0.5 * sig_g ** 2 + 0.5 * sig_b ** 2) if sig_g else sig_b
        mu = prior_mu(ctx, daily_sigma=sigma / math.sqrt(h))
        ex_k = float(kurtosis(ctx["r"][-756:]))
        dof = float(np.clip(4 + 6 / max(ex_k, 0.2), 3, 30))
        rng = np.random.default_rng(config.RANDOM_SEED)
        z = rng.standard_t(dof, size=(config.MC_PATHS, h)) * math.sqrt((dof - 2) / dof)
        term = np.cumsum(mu / h + (sigma / math.sqrt(h)) * z, axis=1)[:, -1]
        q = np.percentile(term, [5, 25, 50, 75, 95])
        p_ar = arima_order(r)
        trend = ""
        if ann_now:
            trend = ("in calo" if ann_end < ann_now * 0.97 else "in aumento" if ann_end > ann_now * 1.03 else "stabile")
        note = (f"Volatilità annua oggi {ann_now:.0%}, prevista {trend} verso {ann_end:.0%}; " if ann_now else "") + \
               (f"rischio sull'orizzonte ±{sigma:.1%} (1 deviazione standard). "
                f"Tendenza di fondo CAPM {ctx['prior_annual']:.1%} annuo. Su 10.000 scenari 1 caso su 20 "
                f"finisce sotto {math.exp(q[0]) - 1:+.1%}. "
                + ("Nessuna memoria utile nei rendimenti passati (ARIMA)." if p_ar == 0 else
                   f"ARIMA trova una memoria di {p_ar} giorni, ma non la usiamo: non è stata validata."))
        res = self.result(ctx, mu, sigma, note, vol_now=ann_now, vol_end=ann_end, persistence=pers,
                          dof=dof, q05=float(q[0]), q95=float(q[4]), arima_order=p_ar, sigma_garch=sig_g)
        res.p_up = float((term > 0).mean())
        return res


# ---------------------------------------------------------------------------
class Holt(Agent):
    name = "Holt (trend smorzato)"
    family = "statistico"
    source = "Exponential smoothing (statsmodels / scipy)"
    description = ("Livellamento esponenziale con trend smorzato (Gardner): stima il livello e la "
                   "pendenza recente del prezzo, ma riduce la pendenza col passare dei giorni, "
                   "perché i trend non durano per sempre. Agente informativo: peso 0 finché il "
                   "banco di prova panel non lo valida.")

    def run(self, ctx):
        y = np.log(ctx["px"][-504:])
        h = ctx["h"]

        def sse(p, ret=False):
            a, b, phi = p
            l, t = y[0], y[1] - y[0]
            err = 0.0
            for v in y[1:]:
                f = l + phi * t
                e = v - f
                err += e * e
                l_new = f + a * e
                t = phi * t + a * b * e
                l = l_new
            return (l, t) if ret else err

        res = minimize(sse, [0.9, 0.05, 0.9], method="L-BFGS-B",
                       bounds=[(0.05, 1.0), (0.001, 0.3), (0.8, 0.98)])
        a, b, phi = res.x
        l, t = sse(res.x, ret=True)
        damp = sum(phi ** i for i in range(1, h + 1))
        trend_part = float(t * damp)
        sig_h, _ = horizon_sigma(ctx)
        trend_part = float(np.clip(trend_part, -0.6 * sig_h, 0.6 * sig_h))
        mu = 0.5 * trend_part + 0.5 * shrunk_mu(ctx)
        direction = "rialzista" if t > 0 else "ribassista"
        return self.result(ctx, mu, sig_h,
                           f"Pendenza recente {direction} ({t * 252:+.0%} annuo), smorzata a "
                           f"{trend_part:+.1%} sull'orizzonte (fattore di smorzamento {phi:.2f}).",
                           alpha=a, beta=b, phi=phi)
