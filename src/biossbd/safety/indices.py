"""Inherent safety indices (BioSSbD step 3: design integration and inherent safety).

Implements the Inherent Safety Index (ISI) of Heikkilä (1999),

    Heikkilä, A.-M. (1999). Inherent safety in process plant design: an
    index-based approach. VTT Publications 384.

The ISI is the sum of a chemical sub-index (worst substance per property)
and a process sub-index (worst unit per property). Lower is safer.

The scoring bands below follow the commonly cited tables of the original
method. They are exposed as module-level constants so that users can check
them against the source and adapt them; please report any discrepancy.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from pydantic import BaseModel, Field

# (upper bound, score) bands; the first band whose bound is not exceeded applies
HEAT_OF_REACTION_BANDS = ((200.0, 0), (600.0, 1), (1200.0, 2), (3000.0, 3), (float("inf"), 4))  # J/g
EXPLOSIVENESS_BANDS = ((0.0, 0), (20.0, 1), (45.0, 2), (70.0, 3), (100.0, 4))  # UEL-LEL, vol%
INVENTORY_ISBL_BANDS = ((1.0, 0), (10.0, 1), (50.0, 2), (200.0, 3), (500.0, 4), (1000.0, 5))  # t
# toxic exposure: OEL/TLV in ppm, lower limit -> higher score
TOXICITY_BANDS = ((0.1, 6), (1.0, 5), (10.0, 4), (100.0, 3), (1000.0, 2), (10000.0, 1))

MAX_CHEMICAL = 4 + 4 + 4 + 4 + 4 + 6 + 2  # 28
MAX_PROCESS = 5 + 4 + 4 + 4 + 5  # 22 (equipment and structure entered directly, 0-4 and 0-5)
MAX_ISI = MAX_CHEMICAL + MAX_PROCESS


def _band(value: float, bands: Sequence[tuple[float, int]]) -> int:
    for bound, score in bands:
        if value <= bound:
            return score
    return bands[-1][1]


def score_heat_of_reaction(j_per_g: float) -> int:
    return _band(abs(j_per_g), HEAT_OF_REACTION_BANDS)


def score_flammability(flash_point_c: float | None, boiling_point_c: float | None = None,
                       flammable_gas: bool = False) -> int:
    """0 non-flammable, 1 combustible (FP > 55 °C), 2 flammable (FP <= 55 °C),
    3 easily flammable (FP < 21 °C), 4 very flammable (FP < 0 °C and BP <= 35 °C, or a flammable gas)."""
    if flammable_gas:
        return 4
    if flash_point_c is None:
        return 0
    if flash_point_c < 0 and boiling_point_c is not None and boiling_point_c <= 35:
        return 4
    if flash_point_c < 21:
        return 3
    if flash_point_c <= 55:
        return 2
    return 1


def score_explosiveness(lel_vol: float | None, uel_vol: float | None) -> int:
    if lel_vol is None or uel_vol is None:
        return 0
    return _band(uel_vol - lel_vol, EXPLOSIVENESS_BANDS)


def score_toxicity(oel_ppm: float | None) -> int:
    if oel_ppm is None:
        return 0
    for bound, score in TOXICITY_BANDS:
        if oel_ppm <= bound:
            return score
    return 0


def score_inventory(tonnes: float) -> int:
    return _band(tonnes, INVENTORY_ISBL_BANDS)


def score_temperature(t_c: float | None) -> int:
    if t_c is None:
        return 0
    if t_c < 0:
        return 1
    if t_c < 70:
        return 0
    if t_c < 150:
        return 1
    if t_c < 300:
        return 2
    if t_c < 600:
        return 3
    return 4


def score_pressure(p_bar: float | None) -> int:
    """Absolute pressure in bar."""
    if p_bar is None:
        return 0
    if 0.5 <= p_bar <= 5:
        return 0
    if p_bar < 0.5 or p_bar <= 25:
        return 1
    if p_bar <= 50:
        return 2
    if p_bar <= 200:
        return 3
    return 4


class ChemicalInput(BaseModel):
    name: str
    flash_point_c: float | None = None
    boiling_point_c: float | None = None
    flammable_gas: bool = False
    lel_vol: float | None = None
    uel_vol: float | None = None
    oel_ppm: float | None = None
    corrosivity: int = Field(0, ge=0, le=2, description="0 carbon steel, 1 stainless, 2 better material")


class ProcessInput(BaseModel):
    name: str
    inventory_t: float = 0.0
    temperature_c: float | None = None
    pressure_bar: float | None = None
    equipment: int = Field(0, ge=0, le=4, description="Equipment safety score (Heikkilä table)")
    structure: int = Field(0, ge=0, le=5, description="Safe process structure score (Heikkilä table)")


class ISIResult(BaseModel):
    chemical: dict[str, int]
    process: dict[str, int]
    chemical_index: int
    process_index: int
    total: int
    normalised: float  # total / MAX_ISI, 0 (inherently safest) to 1


def inherent_safety_index(
    chemicals: Iterable[ChemicalInput],
    units: Iterable[ProcessInput],
    heat_main_reaction_j_g: float = 0.0,
    heat_side_reaction_j_g: float = 0.0,
    chemical_interaction: int = 0,
) -> ISIResult:
    """Heikkilä ISI for a process route (worst case per property)."""
    chems = list(chemicals)
    procs = list(units)
    if not 0 <= chemical_interaction <= 4:
        raise ValueError("chemical_interaction must be between 0 and 4")
    chem = {
        "heat_main_reaction": score_heat_of_reaction(heat_main_reaction_j_g),
        "heat_side_reaction": score_heat_of_reaction(heat_side_reaction_j_g),
        "chemical_interaction": chemical_interaction,
        "flammability": max((score_flammability(c.flash_point_c, c.boiling_point_c, c.flammable_gas)
                             for c in chems), default=0),
        "explosiveness": max((score_explosiveness(c.lel_vol, c.uel_vol) for c in chems), default=0),
        "toxic_exposure": max((score_toxicity(c.oel_ppm) for c in chems), default=0),
        "corrosivity": max((c.corrosivity for c in chems), default=0),
    }
    proc = {
        "inventory": max((score_inventory(u.inventory_t) for u in procs), default=0),
        "temperature": max((score_temperature(u.temperature_c) for u in procs), default=0),
        "pressure": max((score_pressure(u.pressure_bar) for u in procs), default=0),
        "equipment": max((u.equipment for u in procs), default=0),
        "structure": max((u.structure for u in procs), default=0),
    }
    ci, pi = sum(chem.values()), sum(proc.values())
    return ISIResult(chemical=chem, process=proc, chemical_index=ci, process_index=pi,
                     total=ci + pi, normalised=round((ci + pi) / MAX_ISI, 3))
