"""Adapter for Brightway 2.5 LCA calculations (experimental).

Example::

    import bw2data as bd
    from biossbd.sustainability import indicators_from_brightway

    bd.projects.set_current("acod")
    act = bd.get_activity(("my_db", "biogas_production"))
    methods = {"GWP100": ("EF v3.1", "climate change", "global warming potential (GWP100)")}
    ind = indicators_from_brightway({act: 1.0}, methods)

Background data are not shipped: use a database you are licensed to use
(e.g. ecoinvent) or a free one (e.g. USLCI, Agribalyse, ELCD imports).
"""
from __future__ import annotations

from ..dataquality import DataPoint


def _require_brightway():
    try:
        import bw2calc  # noqa: F401
        import bw2data  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on environment
        raise ImportError("Brightway is required: pip install 'biossbd[brightway]'") from e


def indicators_from_brightway(demand: dict, methods: dict[str, tuple], source: str = "Brightway LCA",
                              units: dict[str, str] | None = None) -> dict[str, DataPoint]:
    """Run one LCI and several LCIA methods; return one DataPoint per method."""
    _require_brightway()
    import bw2calc as bc
    import bw2data as bd

    names = list(methods)
    first = methods[names[0]]
    if hasattr(bd, "prepare_lca_inputs"):  # Brightway 2.5
        fu, data_objs, _ = bd.prepare_lca_inputs(demand, method=first)
        lca = bc.LCA(demand=fu, data_objs=data_objs)
    else:  # pragma: no cover - legacy Brightway 2
        lca = bc.LCA(demand, first)
    lca.lci()
    out = {}
    for i, name in enumerate(names):
        if i == 0:
            lca.lcia()
        else:
            lca.switch_method(methods[name])
            lca.lcia()
        unit = (units or {}).get(name)
        if unit is None:
            try:
                unit = bd.Method(methods[name]).metadata.get("unit", "")
            except Exception:
                unit = ""
        out[name] = DataPoint(value=float(lca.score), unit=unit, source=source, evidence="modelled")
    return out
