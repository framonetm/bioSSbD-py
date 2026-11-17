"""Plan-Do-Check-Act iterations (BioSSbD continuous-improvement loop).

Record the KPIs of successive design iterations and run the *Check* gate of
the BioSSbD checklist: is every tracked KPI moving in the intended direction?
"""
from __future__ import annotations

import datetime as _dt
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

Phase = Literal["Plan", "Do", "Check", "Act"]

#: Default improvement direction of the Check-phase KPIs in Table 2 of the BioSSbD paper.
DEFAULT_DIRECTIONS: dict[str, Literal["min", "max"]] = {
    "isi_normalised": "min",
    "ghg_intensity": "min",
    "hazardous_inventory_kg": "min",
    "downtime_risk": "min",
    "incident_frequency": "min",
    "energy_intensity": "min",
    "emissions_intensity": "min",
}


class Iteration(BaseModel):
    label: str
    phase: Phase
    date: _dt.date | None = None
    kpis: dict[str, float] = Field(default_factory=dict)
    changes: list[str] = Field(default_factory=list)
    decision: str = ""


class Cycle(BaseModel):
    iterations: list[Iteration] = Field(default_factory=list)
    directions: dict[str, Literal["min", "max"]] = Field(default_factory=lambda: dict(DEFAULT_DIRECTIONS))

    def add(self, it: Iteration) -> "Cycle":
        if any(i.label == it.label for i in self.iterations):
            raise ValueError(f"Iteration '{it.label}' already recorded")
        self.iterations.append(it)
        return self

    def history(self) -> pd.DataFrame:
        return pd.DataFrame({i.label: i.kpis for i in self.iterations}).T

    def check(self, before: str, after: str) -> pd.DataFrame:
        """Compare two iterations; 'improved' follows each KPI's direction."""
        a = self._get(before).kpis
        b = self._get(after).kpis
        rows = []
        for k in sorted(set(a) & set(b)):
            d = self.directions.get(k)
            delta = b[k] - a[k]
            rel = delta / a[k] if a[k] else float("nan")
            improved = None if d is None else bool(delta < 0 if d == "min" else delta > 0)
            rows.append({"kpi": k, before: a[k], after: b[k], "change": delta,
                         "relative_change": rel, "direction": d or "?", "improved": improved})
        return pd.DataFrame(rows)

    def gate(self, before: str, after: str) -> bool:
        """Check-phase gate: True if no tracked KPI got worse."""
        df = self.check(before, after)
        tracked = df[df["direction"] != "?"]
        worse = tracked[(tracked["direction"] == "min") & (tracked["change"] > 0)
                        | (tracked["direction"] == "max") & (tracked["change"] < 0)]
        return worse.empty

    def _get(self, label: str) -> Iteration:
        for i in self.iterations:
            if i.label == label:
                return i
        raise KeyError(label)
