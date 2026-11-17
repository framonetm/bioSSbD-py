"""Scoping analysis: define the SSbD system and check its completeness.

Implements the three elements of the Scoping Analysis in the revised EC SSbD
framework (Garmendia Aguirre et al., 2025; 2026):

1. the **SSbD system** - substances, materials, processes (units), products and
   life-cycle stages, linked along a value chain;
2. the **intended innovation** - objectives, principles, (re)design actions and
   decision criteria;
3. the **actors** along the life cycle.

From that description the module builds the *life-cycle safety matrix*
(stage x hazard x receptor), so that safety is considered at every stage and
not only where a substance is handled, and it reports scoping gaps: stages
with hazards but no planned assessment, stages outside the LCA boundary and
stages without an engaged actor.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, Field, model_validator

from .dataquality import DataPoint, as_datapoint
from .hazards import PROCESS_HAZARDS, classify_h, get_substance
from .safety.risk import RiskItem
from .specs import IndicatorSpec

DEFAULT_STAGES = ("raw material", "feedstock handling", "processing", "storage", "use", "end of life")

GROUP_RECEPTORS = {
    "physical": ("workers", "installation", "public"),
    "health": ("workers",),
    "environmental": ("environment",),
}


class Substance(BaseModel):
    name: str
    cas: str | None = None
    role: str = "intermediate"  # feedstock | intermediate | product | auxiliary | emission
    h_codes: list[str] | None = None
    flash_point_c: float | None = None
    lel_vol: float | None = None
    uel_vol: float | None = None
    oel_ppm: float | None = None

    def resolved_h_codes(self) -> list[str]:
        if self.h_codes is not None:
            return self.h_codes
        try:
            return list(get_substance(self.name).h_codes)
        except KeyError:
            return []

    def resolved(self) -> "Substance":
        """Fill missing physico-chemical data from the built-in library."""
        try:
            lib = get_substance(self.name)
        except KeyError:
            return self
        return self.model_copy(update={
            "cas": self.cas or lib.cas,
            "h_codes": self.resolved_h_codes(),
            "flash_point_c": self.flash_point_c if self.flash_point_c is not None else lib.flash_point_c,
            "lel_vol": self.lel_vol if self.lel_vol is not None else lib.lel_vol,
            "uel_vol": self.uel_vol if self.uel_vol is not None else lib.uel_vol,
            "oel_ppm": self.oel_ppm if self.oel_ppm is not None else lib.oel_ppm,
        })


class Unit(BaseModel):
    name: str
    stage: str
    substances: list[str] = Field(default_factory=list)
    process_hazards: list[str] = Field(default_factory=list)
    inventory_kg: float = 0.0
    temperature_c: float | None = None
    pressure_bar: float | None = None
    equipment_score: int = Field(0, ge=0, le=4)
    structure_score: int = Field(0, ge=0, le=5)


class Stage(BaseModel):
    name: str
    description: str = ""
    receptors: list[str] = Field(default_factory=list)
    in_lca_boundary: bool = True


class Actor(BaseModel):
    name: str
    role: str = ""
    stages: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    stage: str  # a stage name or "all"
    aspect: Literal["safety", "environmental", "socio-economic", "functionality"]
    method: str = ""
    status: Literal["planned", "done", "not needed"] = "planned"
    justification: str = ""


class Criterion(BaseModel):
    indicator: str
    operator: Literal["<=", ">=", "<", ">"]
    threshold: float
    dimension: str = ""
    note: str = ""

    def passes(self, value: float) -> bool:
        return {"<=": value <= self.threshold, ">=": value >= self.threshold,
                "<": value < self.threshold, ">": value > self.threshold}[self.operator]


class Innovation(BaseModel):
    description: str = ""
    objectives: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    design_actions: list[str] = Field(default_factory=list)
    trl: int | None = Field(default=None, ge=1, le=9)


class Alternative(BaseModel):
    """A design alternative (SSbD scenario) within the same SSbD system."""

    name: str
    description: str = ""
    substances: list[Substance] = Field(default_factory=list)
    units: list[Unit] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    indicators: dict[str, DataPoint] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_indicators(cls, data):
        if isinstance(data, dict) and "indicators" in data and data["indicators"]:
            data = dict(data)
            data["indicators"] = {k: as_datapoint(v) for k, v in data["indicators"].items()}
        return data


class SSbDSystem(BaseModel):
    name: str
    functional_unit: str = ""
    system_boundary: str = "cradle-to-grave"
    innovation: Innovation = Field(default_factory=Innovation)
    stages: list[Stage] = Field(default_factory=lambda: [Stage(name=s) for s in DEFAULT_STAGES])
    actors: list[Actor] = Field(default_factory=list)
    substances: list[Substance] = Field(default_factory=list)
    units: list[Unit] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    indicator_specs: list[IndicatorSpec] = Field(default_factory=list)
    alternatives: list[Alternative] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> "SSbDSystem":
        stage_names = {s.name for s in self.stages}
        for alt in [None, *self.alternatives]:
            subs = {s.name for s in self.substances_for(alt)}
            for u in self.units_for(alt):
                if u.stage not in stage_names:
                    raise ValueError(f"Unit '{u.name}' refers to unknown stage '{u.stage}'")
                for s in u.substances:
                    if s not in subs:
                        raise ValueError(f"Unit '{u.name}' refers to undeclared substance '{s}'")
                for h in u.process_hazards:
                    if h not in PROCESS_HAZARDS:
                        raise ValueError(f"Unit '{u.name}': unknown process hazard '{h}'. "
                                         f"Known: {sorted(PROCESS_HAZARDS)}")
        for a in self.actors:
            for s in a.stages:
                if s not in stage_names:
                    raise ValueError(f"Actor '{a.name}' refers to unknown stage '{s}'")
        for a in self.assessments:
            if a.stage != "all" and a.stage not in stage_names:
                raise ValueError(f"Assessment refers to unknown stage '{a.stage}'")
        return self

    # -- helpers ------------------------------------------------------------
    def get_alternative(self, name: str) -> Alternative:
        for a in self.alternatives:
            if a.name == name:
                return a
        raise KeyError(f"No alternative named '{name}'")

    def substances_for(self, alt: Alternative | str | None = None) -> list[Substance]:
        if isinstance(alt, str):
            alt = self.get_alternative(alt)
        return [*self.substances, *(alt.substances if alt else [])]

    def units_for(self, alt: Alternative | str | None = None) -> list[Unit]:
        if isinstance(alt, str):
            alt = self.get_alternative(alt)
        return [*self.units, *(alt.units if alt else [])]

    @property
    def alternative_names(self) -> list[str]:
        return [a.name for a in self.alternatives]


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def load_system(path: str | Path) -> SSbDSystem:
    """Load an SSbD system from a YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SSbDSystem.model_validate(data)


def dump_system(system: SSbDSystem, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(system.model_dump(exclude_defaults=True), f, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Life-cycle safety matrix
# ---------------------------------------------------------------------------
def hazard_register(system: SSbDSystem, alternative: Alternative | str | None = None) -> pd.DataFrame:
    """Long table of every hazard source per stage and unit.

    Columns: stage, unit, source, source_type, code, group, category, severity, receptors.
    """
    subs = {s.name: s for s in system.substances_for(alternative)}
    stage_receptors = {s.name: s.receptors for s in system.stages}
    rows = []
    for u in system.units_for(alternative):
        for sname in u.substances:
            for code in subs[sname].resolved_h_codes():
                group, category, sev = classify_h(code)
                rec = sorted(set(GROUP_RECEPTORS[group]) | set(stage_receptors.get(u.stage, [])))
                rows.append({"stage": u.stage, "unit": u.name, "source": sname, "source_type": "substance",
                             "code": code, "group": group, "category": category, "severity": sev,
                             "receptors": ", ".join(rec)})
        for hkey in u.process_hazards:
            h = PROCESS_HAZARDS[hkey]
            rec = sorted(set(h.receptors) | set(stage_receptors.get(u.stage, [])))
            rows.append({"stage": u.stage, "unit": u.name, "source": hkey, "source_type": h.group,
                         "code": "", "group": h.group, "category": hkey, "severity": h.severity,
                         "receptors": ", ".join(rec)})
    cols = ["stage", "unit", "source", "source_type", "code", "group", "category", "severity", "receptors"]
    return pd.DataFrame(rows, columns=cols)


def safety_matrix(system: SSbDSystem, alternative: Alternative | str | None = None,
                  by: Literal["group", "category"] = "group") -> pd.DataFrame:
    """Stage x hazard matrix with the maximum screening severity (0 = none identified).

    Rows follow the declared life-cycle order, so stages without any
    identified hazard stay visible as rows of zeros - a prompt to check
    whether they are really hazard-free or simply not yet assessed.
    """
    reg = hazard_register(system, alternative)
    stages = [s.name for s in system.stages]
    if reg.empty:
        return pd.DataFrame(0, index=pd.Index(stages, name="stage"), columns=[])
    m = reg.pivot_table(index="stage", columns=by, values="severity", aggfunc="max", fill_value=0)
    return m.reindex(stages, fill_value=0).astype(int)


def receptor_matrix(system: SSbDSystem, alternative: Alternative | str | None = None) -> pd.DataFrame:
    """Stage x receptor matrix with the maximum severity reaching each receptor."""
    reg = hazard_register(system, alternative)
    stages = [s.name for s in system.stages]
    if reg.empty:
        return pd.DataFrame(0, index=pd.Index(stages, name="stage"), columns=[])
    long = reg.assign(receptor=reg["receptors"].str.split(", ")).explode("receptor")
    m = long.pivot_table(index="stage", columns="receptor", values="severity", aggfunc="max", fill_value=0)
    return m.reindex(stages, fill_value=0).astype(int)


# ---------------------------------------------------------------------------
# Scoping gaps
# ---------------------------------------------------------------------------
def scoping_gaps(system: SSbDSystem) -> pd.DataFrame:
    """List completeness gaps of the scoping analysis.

    Checks, for every life-cycle stage:
    - a safety assessment is planned/done where hazards were identified (high priority),
      or explicitly justified as not needed;
    - stages with no identified hazard still have a safety screening (medium priority);
    - the stage is inside the environmental assessment boundary;
    - at least one actor is engaged.
    Hazards of all alternatives are considered.
    """
    alts: list = system.alternatives or [None]
    hazardous = set()
    for alt in alts:
        reg = hazard_register(system, alt)
        hazardous |= set(reg["stage"])

    def covered(stage: str, aspect: str) -> Assessment | None:
        for a in system.assessments:
            if a.aspect == aspect and a.stage in (stage, "all"):
                return a
        return None

    rows = []
    for st in system.stages:
        sa = covered(st.name, "safety")
        if sa is None:
            if st.name in hazardous:
                rows.append((st.name, "safety", "high",
                             "Hazards identified but no safety assessment planned"))
            else:
                rows.append((st.name, "safety", "medium",
                             "No hazards identified and no safety screening: confirm the stage is hazard-free"))
        elif sa.status == "not needed" and not sa.justification:
            rows.append((st.name, "safety", "medium", "Safety assessment marked 'not needed' without justification"))
        if st.in_lca_boundary:
            if covered(st.name, "environmental") is None:
                rows.append((st.name, "environmental", "medium", "Stage is in the LCA boundary but not assessed"))
        else:
            rows.append((st.name, "environmental", "low", "Stage excluded from the LCA boundary: justify exclusion"))
        if not any(st.name in a.stages for a in system.actors):
            rows.append((st.name, "actors", "medium", "No actor engaged for this stage"))
    order = {"high": 0, "medium": 1, "low": 2}
    df = pd.DataFrame(rows, columns=["stage", "aspect", "priority", "gap"])
    return df.sort_values("priority", key=lambda s: s.map(order), kind="stable").reset_index(drop=True)
