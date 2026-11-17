"""Simple life-cycle inventory per alternative: materials, transport and energy.

Each line is an amount per functional unit (FU) of a background process, expressed in
the unit of that process's reference flow (kg, t*km, kWh, MJ, ...). LCA results are
linear in the demand, so the impact of an alternative in one impact category is

    I_alt = sum_i amount_i * u_i

where ``u_i`` is the impact of one reference unit of process ``i`` with its supply
chain (e.g. calculated once per process in openLCA, see
:meth:`biossbd.connectors.openlca.OpenLCA.unit_impacts`). This is a foreground
screening model: no co-product allocation or recycling credits beyond what the
background processes already contain.

Every amount carries its source; lines without one are reported as ASSUMPTION and
make the resulting indicators ``evidence="assumed"``.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel

from .dataquality import DataPoint

CATEGORIES: tuple[str, ...] = ("material", "transport", "energy", "waste", "other")
COLUMNS: list[str] = ["alternative", "category", "process", "amount", "unit", "source", "process_id"]
#: Substrings that identify a climate-change / GHG impact category across common LCIA methods
#: (EF 3.x "Climate change", ReCiPe "Global warming", TRACI/CML "GWP100").
GHG_KEYWORDS: tuple[str, ...] = ("climate change", "global warming", "gwp")


class InventoryLine(BaseModel):
    alternative: str
    category: Literal["material", "transport", "energy", "waste", "other"] = "material"
    process_id: str
    process: str = ""
    amount: float
    unit: str = ""
    source: str = ""

    @property
    def is_assumption(self) -> bool:
        s = self.source.strip()
        return not s or s.upper().startswith("ASSUMPTION")

    def describe(self) -> str:
        src = "ASSUMPTION" if self.is_assumption and not self.source.strip() else self.source.strip()
        return f"{self.amount:g} {self.unit} {self.process} [{src}]".replace("  ", " ")


def _blank(x: Any) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(x, str) and not x.strip())


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float if c == "amount" else object) for c in COLUMNS})


def lines_from_frame(df: pd.DataFrame) -> list[InventoryLine]:
    """Inventory lines from a table; rows without alternative, process id or amount are skipped."""
    out = []
    for r in df.to_dict("records"):
        if any(_blank(r.get(k)) for k in ("alternative", "process_id", "amount")):
            continue
        cat = r.get("category")
        out.append(InventoryLine(alternative=str(r["alternative"]), process_id=str(r["process_id"]),
                                 category=cat if cat in CATEGORIES else "other",
                                 process="" if _blank(r.get("process")) else str(r["process"]),
                                 amount=float(r["amount"]),
                                 unit="" if _blank(r.get("unit")) else str(r["unit"]),
                                 source="" if _blank(r.get("source")) else str(r["source"])))
    return out


def lines_to_frame(lines: Sequence[InventoryLine]) -> pd.DataFrame:
    if not lines:
        return empty_frame()
    return pd.DataFrame([ln.model_dump() for ln in lines])[COLUMNS]


def contributions(lines: Sequence[InventoryLine], unit_impacts: Mapping[str, Sequence[Any]]) -> pd.DataFrame:
    """One row per line and impact category: ``value = amount * unit impact``.

    ``unit_impacts`` maps a process id to results per reference unit, each with
    ``category``, ``unit`` and ``amount`` attributes (e.g. ``openlca.ImpactResult``).
    """
    rows = []
    for ln in lines:
        if ln.process_id not in unit_impacts:
            raise KeyError(f"No unit impacts for process '{ln.process or ln.process_id}'")
        for r in unit_impacts[ln.process_id]:
            rows.append({"alternative": ln.alternative, "category": ln.category, "process": ln.process,
                         "amount": ln.amount, "unit": ln.unit, "impact_category": r.category,
                         "impact_unit": r.unit, "unit_impact": r.amount, "value": ln.amount * r.amount})
    return pd.DataFrame(rows, columns=["alternative", "category", "process", "amount", "unit", "impact_category",
                                       "impact_unit", "unit_impact", "value"])


def totals(contrib: pd.DataFrame) -> pd.DataFrame:
    """Alternatives x impact categories (column label ``"<category> [<unit>]"``)."""
    if contrib.empty:
        return pd.DataFrame()
    c = contrib.assign(label=contrib["impact_category"] + " [" + contrib["impact_unit"] + "]")
    return c.pivot_table(index="alternative", columns="label", values="value", aggfunc="sum", sort=False)


def by_inventory_category(contrib: pd.DataFrame, impact_category: str) -> pd.DataFrame:
    """Alternatives x inventory categories (material, transport, ...) for one impact category."""
    c = contrib[contrib["impact_category"] == impact_category]
    t = c.pivot_table(index="alternative", columns="category", values="value", aggfunc="sum", sort=False)
    return t.reindex(columns=[k for k in CATEGORIES if k in t.columns]).fillna(0.0)


def ghg_categories(names: Sequence[str]) -> list[str]:
    return [n for n in names if any(k in str(n).lower() for k in GHG_KEYWORDS)]


def to_indicators(lines: Sequence[InventoryLine], unit_impacts: Mapping[str, Sequence[Any]], method: str,
                  impact_categories: Sequence[str] | None = None,
                  prefix: str = "") -> dict[str, dict[str, DataPoint]]:
    """Totals per alternative as indicators with full provenance (method, processes, amount sources)."""
    contrib = contributions(lines, unit_impacts)
    out: dict[str, dict[str, DataPoint]] = {}
    for alt, g in contrib.groupby("alternative", sort=False):
        alt_lines = [ln for ln in lines if ln.alternative == alt]
        assumed = any(ln.is_assumption for ln in alt_lines)
        source = f"openLCA inventory, {method}: " + "; ".join(ln.describe() for ln in alt_lines)
        for (cat, unit), v in g.groupby(["impact_category", "impact_unit"], sort=False)["value"].sum().items():
            if impact_categories is not None and cat not in impact_categories:
                continue
            out.setdefault(alt, {})[f"{prefix}{cat}"] = DataPoint(
                value=float(v), unit=f"{unit}/FU" if unit else "per FU", source=source,
                evidence="assumed" if assumed else "modelled",
                note="Contains amounts without a source (ASSUMPTION)." if assumed else "")
    return out
