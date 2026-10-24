"""Registro degli agenti: trova automaticamente ogni classe Agent nei moduli
di questa cartella. Gli agenti con librerie opzionali mancanti si disattivano
da soli (enabled = False) senza bloccare la piattaforma."""
import importlib
import inspect
import pkgutil

from .base import Agent, AgentResult  # noqa: F401

_AGENTS = None


def all_agents():
    global _AGENTS
    if _AGENTS is None:
        found = []
        for mod in pkgutil.iter_modules(__path__):
            if mod.name == "base":
                continue
            try:
                m = importlib.import_module(f"{__name__}.{mod.name}")
            except Exception as e:  # un agente rotto non deve fermare gli altri
                print(f"[agenti] {mod.name} non caricato: {e}")
                continue
            for _, obj in inspect.getmembers(m, inspect.isclass):
                if issubclass(obj, Agent) and obj is not Agent and obj.__module__ == m.__name__:
                    found.append(obj())
        order = ["Modello di base", "Holt", "Momentum", "Mean", "Regimi",
                 "Gradient", "Valutazione", "Prophet", "Chronos"]
        found.sort(key=lambda a: next((i for i, k in enumerate(order) if a.name.startswith(k)), 99))
        _AGENTS = found
    return _AGENTS
