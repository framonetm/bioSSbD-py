"""Safety KPIs for an SSbD alternative (BioSSbD steps 1-3)."""
from __future__ import annotations

from pydantic import BaseModel

from ..scoping import Alternative, SSbDSystem, hazard_register
from .indices import ChemicalInput, ISIResult, ProcessInput, inherent_safety_index
from .risk import risk_table

HIGH_SEVERITY = 4


class SafetyKPIs(BaseModel):
    alternative: str | None
    isi: ISIResult
    hazardous_inventory_kg: float
    high_risk_units: list[str]
    n_hazard_sources: int
    max_severity: int
    top_risks: list[dict]


def safety_kpis(system: SSbDSystem, alternative: Alternative | str | None = None,
                heat_main_reaction_j_g: float = 0.0, heat_side_reaction_j_g: float = 0.0,
                chemical_interaction: int = 0) -> SafetyKPIs:
    """Compute the step-3 indicators of the BioSSbD methodology for one alternative.

    - normalised Inherent Safety Index (Heikkilä)
    - hazardous inventory mass: inventory of units holding any substance or
      process hazard with screening severity >= 4
    - high-risk units requiring active protection: units with such a hazard
    """
    if isinstance(alternative, str):
        alternative = system.get_alternative(alternative)
    subs = {s.name: s.resolved() for s in system.substances_for(alternative)}
    units = system.units_for(alternative)

    used = {n for u in units for n in u.substances}
    chems = []
    for n in sorted(used):
        s = subs[n]
        codes = s.resolved_h_codes()
        chems.append(ChemicalInput(
            name=n, flash_point_c=s.flash_point_c,
            flammable_gas=any(c in ("H220", "H221") for c in codes),
            lel_vol=s.lel_vol, uel_vol=s.uel_vol, oel_ppm=s.oel_ppm,
            corrosivity=1 if any(c in ("H290", "H314") for c in codes) else 0,
        ))
    procs = [ProcessInput(name=u.name, inventory_t=u.inventory_kg / 1000, temperature_c=u.temperature_c,
                          pressure_bar=u.pressure_bar, equipment=u.equipment_score,
                          structure=u.structure_score) for u in units]
    isi = inherent_safety_index(chems, procs, heat_main_reaction_j_g, heat_side_reaction_j_g,
                                chemical_interaction)

    reg = hazard_register(system, alternative)
    severe_units = sorted(set(reg.loc[reg["severity"] >= HIGH_SEVERITY, "unit"])) if not reg.empty else []
    inv = sum(u.inventory_kg for u in units if u.name in severe_units)
    rt = risk_table(alternative.risks) if alternative is not None else risk_table([])
    return SafetyKPIs(
        alternative=alternative.name if alternative is not None else None,
        isi=isi,
        hazardous_inventory_kg=inv,
        high_risk_units=severe_units,
        n_hazard_sources=len(reg),
        max_severity=int(reg["severity"].max()) if not reg.empty else 0,
        top_risks=rt.head(3).to_dict("records") if not rt.empty else [],
    )
