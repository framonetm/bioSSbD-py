"""Convert an SSbD system to editable tables and back (used by the GUI).

Pure pandas, no GUI dependency, so the conversions are unit-tested.
List-valued fields (receptors, substances, hazards, ...) are shown as
comma-separated text. Units, substances and risks carry an ``alternative``
column: ``(shared)`` for the common system, otherwise the alternative name.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from ..scoping import SSbDSystem

SHARED = "(shared)"

STAGE_COLS = ["name", "description", "receptors", "in_lca_boundary"]
ACTOR_COLS = ["name", "role", "stages"]
SUBSTANCE_COLS = ["alternative", "name", "cas", "role", "h_codes", "flash_point_c", "lel_vol", "uel_vol", "oel_ppm"]
UNIT_COLS = ["alternative", "name", "stage", "substances", "process_hazards", "inventory_kg",
             "temperature_c", "pressure_bar", "equipment_score", "structure_score"]
ASSESSMENT_COLS = ["stage", "aspect", "method", "status", "justification"]
CRITERION_COLS = ["indicator", "operator", "threshold", "dimension", "note"]
SPEC_COLS = ["name", "dimension", "direction", "unit", "scale_min", "scale_max", "weight", "ordinal", "step",
             "description"]
RISK_COLS = ["alternative", "name", "stage", "impact", "likelihood", "detectability", "mitigation", "description"]
ALT_COLS = ["name", "description"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _join(x) -> str:
    return ", ".join(str(i) for i in x) if x else ""


def _split(x) -> list[str]:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return []
    return [p.strip() for p in str(x).split(",") if p.strip()]


def _blank(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(x, str) and not x.strip())


def _num(x, cast=float):
    return None if _blank(x) else cast(x)


def _str(x) -> str:
    return "" if _blank(x) else str(x).strip()


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    out = []
    for r in df.to_dict("records"):
        if _blank(r.get("name", r.get("indicator", r.get("stage")))):
            continue  # skip empty rows added in the editor
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# system -> tables
# ---------------------------------------------------------------------------
def system_to_tables(system: SSbDSystem) -> dict[str, Any]:
    """Return a dict of DataFrames (plus general fields) describing the system."""
    general = {
        "name": system.name,
        "functional_unit": system.functional_unit,
        "system_boundary": system.system_boundary,
        "innovation_description": system.innovation.description,
        "objectives": "\n".join(system.innovation.objectives),
        "principles": _join(system.innovation.principles),
        "design_actions": "\n".join(system.innovation.design_actions),
        "trl": system.innovation.trl,
    }
    stages = pd.DataFrame([{"name": s.name, "description": s.description, "receptors": _join(s.receptors),
                            "in_lca_boundary": s.in_lca_boundary} for s in system.stages], columns=STAGE_COLS)
    actors = pd.DataFrame([{"name": a.name, "role": a.role, "stages": _join(a.stages)} for a in system.actors],
                          columns=ACTOR_COLS)

    def sub_row(alt, s):
        return {"alternative": alt, "name": s.name, "cas": s.cas or "", "role": s.role,
                "h_codes": _join(s.h_codes) if s.h_codes is not None else "",
                "flash_point_c": s.flash_point_c, "lel_vol": s.lel_vol, "uel_vol": s.uel_vol, "oel_ppm": s.oel_ppm}

    def unit_row(alt, u):
        return {"alternative": alt, "name": u.name, "stage": u.stage, "substances": _join(u.substances),
                "process_hazards": _join(u.process_hazards), "inventory_kg": u.inventory_kg,
                "temperature_c": u.temperature_c, "pressure_bar": u.pressure_bar,
                "equipment_score": u.equipment_score, "structure_score": u.structure_score}

    subs = [sub_row(SHARED, s) for s in system.substances]
    units = [unit_row(SHARED, u) for u in system.units]
    risks, values = [], {}
    for a in system.alternatives:
        subs += [sub_row(a.name, s) for s in a.substances]
        units += [unit_row(a.name, u) for u in a.units]
        risks += [{"alternative": a.name, "name": r.name, "stage": r.stage or "", "impact": r.impact,
                   "likelihood": r.likelihood, "detectability": r.detectability, "mitigation": r.mitigation,
                   "description": r.description} for r in a.risks]
        values[a.name] = {k: dp.value for k, dp in a.indicators.items()}

    specs = pd.DataFrame([{
        "name": s.name, "dimension": s.dimension, "direction": s.direction, "unit": s.unit,
        "scale_min": s.scale[0] if s.scale else None, "scale_max": s.scale[1] if s.scale else None,
        "weight": s.weight, "ordinal": s.ordinal, "step": s.step, "description": s.description,
    } for s in system.indicator_specs], columns=SPEC_COLS)
    spec_names = list(specs["name"]) if not specs.empty else []
    extra = sorted({k for v in values.values() for k in v} - set(spec_names))
    ind = pd.DataFrame.from_dict(values, orient="index").reindex(columns=spec_names + extra)
    ind.index.name = "alternative"

    # provenance of indicator values, kept so that a round trip does not lose it
    meta = {(a.name, k): dp.model_dump(exclude={"value"}) for a in system.alternatives
            for k, dp in a.indicators.items()}

    return {
        "general": general,
        "alternatives": pd.DataFrame([{"name": a.name, "description": a.description} for a in system.alternatives],
                                     columns=ALT_COLS),
        "stages": stages,
        "actors": actors,
        "substances": pd.DataFrame(subs, columns=SUBSTANCE_COLS),
        "units": pd.DataFrame(units, columns=UNIT_COLS),
        "assessments": pd.DataFrame([a.model_dump() for a in system.assessments], columns=ASSESSMENT_COLS),
        "criteria": pd.DataFrame([c.model_dump() for c in system.criteria], columns=CRITERION_COLS),
        "specs": specs,
        "risks": pd.DataFrame(risks, columns=RISK_COLS),
        "indicators": ind,
        "indicator_meta": meta,
    }


# ---------------------------------------------------------------------------
# tables -> system
# ---------------------------------------------------------------------------
def tables_to_dict(t: dict[str, Any]) -> dict:
    """Rebuild a plain dict (YAML-ready) from the tables. Validate with SSbDSystem.model_validate."""
    g = t["general"]
    d: dict[str, Any] = {
        "name": _str(g.get("name")) or "Untitled system",
        "functional_unit": _str(g.get("functional_unit")),
        "system_boundary": _str(g.get("system_boundary")) or "cradle-to-grave",
        "innovation": {
            "description": _str(g.get("innovation_description")),
            "objectives": [x.strip() for x in str(g.get("objectives") or "").splitlines() if x.strip()],
            "principles": _split(g.get("principles")),
            "design_actions": [x.strip() for x in str(g.get("design_actions") or "").splitlines() if x.strip()],
        },
    }
    if not _blank(g.get("trl")):
        d["innovation"]["trl"] = int(g["trl"])

    d["stages"] = [{"name": _str(r["name"]), "description": _str(r.get("description")),
                    "receptors": _split(r.get("receptors")),
                    "in_lca_boundary": bool(r.get("in_lca_boundary")) if not _blank(r.get("in_lca_boundary")) else True}
                   for r in _records(t["stages"])]
    d["actors"] = [{"name": _str(r["name"]), "role": _str(r.get("role")), "stages": _split(r.get("stages"))}
                   for r in _records(t["actors"])]

    def sub(r):
        s = {"name": _str(r["name"]), "role": _str(r.get("role")) or "intermediate"}
        if _str(r.get("cas")):
            s["cas"] = _str(r["cas"])
        if _str(r.get("h_codes")):
            s["h_codes"] = _split(r["h_codes"])
        for k in ("flash_point_c", "lel_vol", "uel_vol", "oel_ppm"):
            v = _num(r.get(k))
            if v is not None:
                s[k] = v
        return s

    def unit(r):
        u = {"name": _str(r["name"]), "stage": _str(r.get("stage")), "substances": _split(r.get("substances")),
             "process_hazards": _split(r.get("process_hazards")),
             "inventory_kg": _num(r.get("inventory_kg")) or 0.0,
             "equipment_score": _num(r.get("equipment_score"), int) or 0,
             "structure_score": _num(r.get("structure_score"), int) or 0}
        for k in ("temperature_c", "pressure_bar"):
            v = _num(r.get(k))
            if v is not None:
                u[k] = v
        return u

    subs = _records(t["substances"])
    units = _records(t["units"])
    d["substances"] = [sub(r) for r in subs if _str(r.get("alternative")) in ("", SHARED)]
    d["units"] = [unit(r) for r in units if _str(r.get("alternative")) in ("", SHARED)]
    d["assessments"] = [{"stage": _str(r["stage"]), "aspect": _str(r.get("aspect")) or "safety",
                         "method": _str(r.get("method")), "status": _str(r.get("status")) or "planned",
                         "justification": _str(r.get("justification"))} for r in _records(t["assessments"])]
    d["criteria"] = [{"indicator": _str(r["indicator"]), "operator": _str(r.get("operator")) or ">=",
                      "threshold": float(r["threshold"]), "dimension": _str(r.get("dimension")),
                      "note": _str(r.get("note"))} for r in _records(t["criteria"]) if not _blank(r.get("threshold"))]
    specs = []
    for r in _records(t["specs"]):
        s = {"name": _str(r["name"]), "dimension": _str(r.get("dimension")) or "Other",
             "direction": _str(r.get("direction")) or "max", "unit": _str(r.get("unit")),
             "weight": _num(r.get("weight")) or 1.0, "ordinal": bool(r.get("ordinal")) if not _blank(r.get("ordinal")) else False,
             "description": _str(r.get("description"))}
        lo, hi = _num(r.get("scale_min")), _num(r.get("scale_max"))
        if lo is not None and hi is not None:
            s["scale"] = [lo, hi]
        if _num(r.get("step"), int) is not None:
            s["step"] = int(r["step"])
        specs.append(s)
    d["indicator_specs"] = specs

    ind: pd.DataFrame = t["indicators"]
    meta = t.get("indicator_meta", {})
    risks = _records(t["risks"])
    alts = []
    for r in _records(t["alternatives"]):
        name = _str(r["name"])
        a = {"name": name, "description": _str(r.get("description")),
             "substances": [sub(x) for x in subs if _str(x.get("alternative")) == name],
             "units": [unit(x) for x in units if _str(x.get("alternative")) == name],
             "risks": [], "indicators": {}}
        for x in risks:
            if _str(x.get("alternative")) != name:
                continue
            rk = {"name": _str(x["name"]), "impact": int(x["impact"]), "likelihood": int(x["likelihood"]),
                  "mitigation": _str(x.get("mitigation")), "description": _str(x.get("description"))}
            if _str(x.get("stage")):
                rk["stage"] = _str(x["stage"])
            if _num(x.get("detectability"), int) is not None:
                rk["detectability"] = int(x["detectability"])
            a["risks"].append(rk)
        if ind is not None and name in ind.index:
            for k, v in ind.loc[name].items():
                if not _blank(v):
                    dp = {"value": float(v), **meta.get((name, k), {})}
                    a["indicators"][k] = dp
        alts.append(a)
    d["alternatives"] = alts
    return d


def tables_to_system(t: dict[str, Any]) -> SSbDSystem:
    return SSbDSystem.model_validate(tables_to_dict(t))
