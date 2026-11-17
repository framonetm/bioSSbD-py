"""Brightway 2.5 connector: browse projects, databases, activities and LCIA methods.

Background databases are whatever the user has imported into a Brightway project
(e.g. ecoinvent with a licence via ``ecoinvent_interface``, or free data such as
USLCI or Agribalyse imported with ``bw2io``). Requires ``pip install brightway25``.
"""
from __future__ import annotations

from dataclasses import dataclass

from .http import ConnectorError


@dataclass
class Activity:
    key: tuple
    name: str
    location: str = ""
    unit: str = ""
    reference_product: str = ""


def installed() -> bool:
    try:
        import bw2calc  # noqa: F401
        import bw2data  # noqa: F401
        return True
    except ImportError:
        return False


def _bd():
    if not installed():
        raise ConnectorError("Brightway is not installed: pip install brightway25")
    import bw2data as bd
    return bd


def projects() -> list[str]:
    bd = _bd()
    return sorted(p.name for p in bd.projects)


def databases(project: str) -> list[str]:
    bd = _bd()
    bd.projects.set_current(project)
    return sorted(bd.databases)


def search(project: str, database: str, query: str, limit: int = 25) -> list[Activity]:
    bd = _bd()
    bd.projects.set_current(project)
    db = bd.Database(database)
    try:
        hits = db.search(query, limit=limit)
    except Exception:  # search index not built: fall back to a scan
        q = query.lower()
        hits = [a for a in db if q in a.get("name", "").lower()][:limit]
    return [Activity(key=a.key, name=a.get("name", ""), location=a.get("location", ""), unit=a.get("unit", ""),
                     reference_product=a.get("reference product", "")) for a in hits]


def methods(project: str, contains: str = "", limit: int = 200) -> list[tuple]:
    bd = _bd()
    bd.projects.set_current(project)
    c = contains.lower()
    out = [m for m in bd.methods if c in " ".join(m).lower()]
    return sorted(out)[:limit]


def calculate(project: str, activity_key: tuple, method_list: list[tuple], amount: float = 1.0) -> dict:
    """Return {method name: DataPoint} using the shared Brightway adapter."""
    bd = _bd()
    from ..sustainability.brightway_adapter import indicators_from_brightway
    bd.projects.set_current(project)
    act = bd.get_activity(activity_key)
    names = {" | ".join(m): m for m in method_list}
    return indicators_from_brightway({act: amount}, names, source=f"Brightway: {project} / {act.get('name')}")
