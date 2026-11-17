"""Safety assessment: hazards, risk and reliability, inherent safety.

``safety_kpis`` lives in :mod:`biossbd.safety.assess` (imported lazily to
avoid a circular import with :mod:`biossbd.scoping`).
"""
from .indices import ChemicalInput, ISIResult, ProcessInput, inherent_safety_index
from .risk import RiskItem, classify_index, reliability_score, risk_table


def __getattr__(name):
    if name in ("safety_kpis", "SafetyKPIs"):
        from . import assess
        return getattr(assess, name)
    raise AttributeError(name)


__all__ = [
    "ChemicalInput", "ISIResult", "ProcessInput", "RiskItem", "SafetyKPIs",
    "classify_index", "inherent_safety_index", "reliability_score", "risk_table", "safety_kpis",
]
