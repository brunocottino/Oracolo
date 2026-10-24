"""Base comune per tutti gli agenti.

Ogni agente riceve lo stesso "contesto" (prezzi, orizzonte, ipotesi CFA) e
restituisce una previsione nello stesso formato:
  - mu:    rendimento logaritmico atteso sull'orizzonte
  - sigma: deviazione standard del rendimento logaritmico sull'orizzonte
  - p_up:  probabilità che il prezzo a fine orizzonte sia sopra quello di oggi
  - nota:  spiegazione in italiano, senza gergo informatico

Per aggiungere un nuovo agente basta creare un file in /agents con una classe
che eredita da Agent: viene trovato e usato automaticamente.
"""
import math
from dataclasses import dataclass, field, asdict

import numpy as np
from scipy.stats import norm


@dataclass
class AgentResult:
    name: str
    family: str
    mu: float
    sigma: float
    p_up: float
    note: str
    source: str = ""
    extra: dict = field(default_factory=dict)
    weight: float = 1.0
    skill: float | None = None        # tasso di successo storico (0-1)
    skill_n: int = 0

    @property
    def exp_return(self):
        """Rendimento atteso semplice (non logaritmico)."""
        return math.exp(self.mu + 0.5 * self.sigma ** 2) - 1

    def to_dict(self):
        d = asdict(self)
        d["exp_return"] = self.exp_return
        d["median_return"] = math.exp(self.mu) - 1
        return d


class Agent:
    name = "agente"
    family = "statistico"
    source = ""               # libreria / repository di riferimento
    description = ""          # spiegazione per la pagina Metodologia
    applies_to = "all"        # all | stock | index
    backtestable = True       # se può essere valutato sul passato senza "sbirciare"
    enabled = True            # False se manca una libreria opzionale

    def applicable(self, ctx) -> bool:
        if self.applies_to == "stock" and ctx["is_index"]:
            return False
        if self.applies_to == "index" and not ctx["is_index"]:
            return False
        return self.enabled

    def run(self, ctx) -> AgentResult:  # pragma: no cover
        raise NotImplementedError

    # helper
    def result(self, ctx, mu, sigma, note, **extra):
        sigma = float(max(sigma, 1e-4))
        mu = float(mu)
        return AgentResult(
            name=self.name, family=self.family, mu=mu, sigma=sigma,
            p_up=float(norm.cdf(mu / sigma)), note=note, source=self.source, extra=extra,
        )


# ---------------------------------------------------------------------------
# Funzioni matematiche condivise
# ---------------------------------------------------------------------------
def ewma_vol(r, lam=0.94):
    """Volatilità giornaliera EWMA (RiskMetrics)."""
    r = np.asarray(r)[-500:]
    w = lam ** np.arange(len(r))[::-1]
    return float(math.sqrt(np.sum(w * r ** 2) / np.sum(w)))


def horizon_sigma(ctx):
    """Volatilità attesa sull'orizzonte: media tra EWMA (breve) e storica 3 anni (lunga),
    perché la volatilità tende a tornare verso la media."""
    r = ctx["r"]
    lr = float(np.std(r[-756:]))
    s = math.sqrt(0.5 * ewma_vol(r) ** 2 + 0.5 * lr ** 2)
    return s * math.sqrt(ctx["h"]), s


def prior_mu(ctx, daily_sigma=None):
    """Rendimento logaritmico 'a priori' sull'orizzonte, da CAPM:
    E[r] = risk free + beta x premio al rischio, convertito in log-drift."""
    if daily_sigma is None:
        daily_sigma = float(np.std(ctx["r"][-756:]))
    ann = ctx["prior_annual"]
    log_drift_ann = math.log1p(ann) - 0.5 * (daily_sigma ** 2) * 252
    return log_drift_ann * ctx["h"] / 252


def shrunk_mu(ctx, weight_hist=0.25):
    """Media tra il drift CAPM e quello storico (3 anni): il passato da solo
    è una stima troppo rumorosa del futuro."""
    r = ctx["r"]
    hist = float(np.mean(r[-756:])) * ctx["h"]
    return (1 - weight_hist) * prior_mu(ctx) + weight_hist * hist
