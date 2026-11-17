"""Adapter for QSDsan / BioSTEAM results (experimental).

Build and simulate your system in QSDsan as usual (e.g. with the ADM1 process
model for anaerobic digestion), create its ``qsdsan.LCA`` and TEA objects, then
convert the results into BioSSbD indicators::

    import qsdsan as qs
    from biossbd.sustainability import indicators_from_qsdsan, indicators_from_tea

    lca = qs.LCA(system=sys, lifetime=20, lifetime_unit="yr", ...)
    tea = qs.SimpleTEA(system=sys, discount_rate=0.05, lifetime=20, ...)
    ind = indicators_from_qsdsan(lca, functional_unit=annual_biogas_MJ * 20)
    ind |= indicators_from_tea(tea)
"""
from __future__ import annotations

from ..dataquality import DataPoint

TEA_ATTRIBUTES = ("NPV", "IRR", "EAC", "annualized_CAPEX", "AOC", "TCI", "installed_equipment_cost")


def _require_qsdsan():
    try:
        import qsdsan  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on environment
        raise ImportError("QSDsan is required: pip install 'biossbd[qsdsan]'") from e


def indicators_from_qsdsan(lca, functional_unit: float = 1.0, prefix: str = "",
                           source: str = "QSDsan LCA") -> dict[str, DataPoint]:
    """Total impacts of a ``qsdsan.LCA`` divided by the functional-unit amount.

    ``functional_unit`` is the total amount of the reference flow over the
    LCA lifetime (e.g. MJ of biogas produced in 20 years).
    """
    _require_qsdsan()
    if functional_unit <= 0:
        raise ValueError("functional_unit must be positive")
    totals = lca.get_total_impacts()
    out = {}
    for key, value in totals.items():
        unit = ""
        ind = getattr(lca, "indicators", None)
        if ind:
            for i in ind:
                if getattr(i, "ID", None) == key:
                    unit = f"{getattr(i, 'unit', '')}/FU"
        out[f"{prefix}{key}"] = DataPoint(value=float(value) / functional_unit, unit=unit,
                                          source=source, evidence="modelled")
    return out


def indicators_from_tea(tea, prefix: str = "", source: str = "BioSTEAM/QSDsan TEA",
                        attributes: tuple[str, ...] = TEA_ATTRIBUTES) -> dict[str, DataPoint]:
    """Collect the economic indicators that a BioSTEAM/QSDsan TEA object exposes."""
    out = {}
    for a in attributes:
        try:
            v = getattr(tea, a)
            v = v() if callable(v) else v
            v = float(v)
        except Exception:  # attribute missing or not computable for this TEA type
            continue
        out[f"{prefix}{a}"] = DataPoint(value=v, unit="USD" if a != "IRR" else "-",
                                        source=source, evidence="modelled")
    return out
