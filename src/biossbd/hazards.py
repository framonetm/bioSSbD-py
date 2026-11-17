"""Hazard libraries: GHS hazard statements, common biorefinery substances and
biological / process hazards that GHS does not cover.

The built-in data are *defaults for screening*. Always verify substance
classifications against the ECHA C&L Inventory or a current safety data sheet
before using them in a decision.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# GHS hazard statements -> (group, category, screening severity 1-5)
# Severity is an ordinal screening score used by this toolbox, not a GHS value.
# ---------------------------------------------------------------------------
H_STATEMENTS: dict[str, tuple[str, str, int]] = {
    # physical
    "H200": ("physical", "explosive", 5), "H201": ("physical", "explosive", 5),
    "H202": ("physical", "explosive", 5), "H203": ("physical", "explosive", 5),
    "H204": ("physical", "explosive", 4), "H205": ("physical", "explosive", 4),
    "H220": ("physical", "flammable", 5), "H221": ("physical", "flammable", 4),
    "H222": ("physical", "flammable", 4), "H223": ("physical", "flammable", 3),
    "H224": ("physical", "flammable", 5), "H225": ("physical", "flammable", 4),
    "H226": ("physical", "flammable", 3), "H228": ("physical", "flammable", 3),
    "H240": ("physical", "self-reactive", 5), "H241": ("physical", "self-reactive", 5),
    "H242": ("physical", "self-reactive", 4), "H250": ("physical", "pyrophoric", 5),
    "H251": ("physical", "self-heating", 3), "H252": ("physical", "self-heating", 2),
    "H260": ("physical", "water-reactive", 5), "H261": ("physical", "water-reactive", 4),
    "H270": ("physical", "oxidising", 4), "H271": ("physical", "oxidising", 5),
    "H272": ("physical", "oxidising", 3), "H280": ("physical", "gas under pressure", 2),
    "H281": ("physical", "gas under pressure", 2), "H290": ("physical", "corrosive to metals", 2),
    # health
    "H300": ("health", "acute toxicity", 5), "H310": ("health", "acute toxicity", 5),
    "H330": ("health", "acute toxicity", 5), "H301": ("health", "acute toxicity", 4),
    "H311": ("health", "acute toxicity", 4), "H331": ("health", "acute toxicity", 4),
    "H302": ("health", "acute toxicity", 3), "H312": ("health", "acute toxicity", 3),
    "H332": ("health", "acute toxicity", 3), "H304": ("health", "aspiration", 4),
    "H314": ("health", "corrosive", 4), "H315": ("health", "irritant", 2),
    "H317": ("health", "sensitiser", 3), "H318": ("health", "corrosive", 3),
    "H319": ("health", "irritant", 2), "H334": ("health", "sensitiser", 4),
    "H335": ("health", "irritant", 2), "H336": ("health", "narcotic", 2),
    "H340": ("health", "CMR", 5), "H341": ("health", "CMR", 4),
    "H350": ("health", "CMR", 5), "H351": ("health", "CMR", 4),
    "H360": ("health", "CMR", 5), "H361": ("health", "CMR", 4), "H362": ("health", "CMR", 3),
    "H370": ("health", "STOT", 5), "H371": ("health", "STOT", 4),
    "H372": ("health", "STOT", 4), "H373": ("health", "STOT", 3),
    # environmental
    "H400": ("environmental", "aquatic acute", 4), "H410": ("environmental", "aquatic chronic", 5),
    "H411": ("environmental", "aquatic chronic", 4), "H412": ("environmental", "aquatic chronic", 3),
    "H413": ("environmental", "aquatic chronic", 2), "H420": ("environmental", "ozone layer", 3),
}


def classify_h(code: str) -> tuple[str, str, int]:
    """Return (group, category, severity) for a hazard statement such as 'H220'.

    Combined codes ('H360D', 'H360Fd') are reduced to their first four characters.
    """
    key = code.strip().upper()[:4]
    if key not in H_STATEMENTS:
        raise KeyError(f"Unknown GHS hazard statement: {code}")
    return H_STATEMENTS[key]


# ---------------------------------------------------------------------------
# Common biorefinery substances (screening defaults; verify before use)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SubstanceData:
    name: str
    cas: str
    h_codes: tuple[str, ...]
    flash_point_c: float | None = None  # None = not flammable / gas
    lel_vol: float | None = None
    uel_vol: float | None = None
    oel_ppm: float | None = None  # occupational exposure limit, 8-h TWA
    notes: str = ""


SUBSTANCES: dict[str, SubstanceData] = {
    "methane": SubstanceData("methane", "74-82-8", ("H220", "H280"),
                             lel_vol=5.0, uel_vol=15.0, notes="Simple asphyxiant at high concentration"),
    "hydrogen sulfide": SubstanceData("hydrogen sulfide", "7783-06-4", ("H220", "H280", "H330", "H400"),
                                      lel_vol=4.0, uel_vol=44.0, oel_ppm=5.0),
    "ammonia": SubstanceData("ammonia", "7664-41-7", ("H221", "H280", "H314", "H331", "H400"),
                             lel_vol=15.0, uel_vol=28.0, oel_ppm=20.0),
    "carbon dioxide": SubstanceData("carbon dioxide", "124-38-9", ("H280",), oel_ppm=5000.0,
                                    notes="Asphyxiant in confined spaces"),
    "hydrogen": SubstanceData("hydrogen", "1333-74-0", ("H220", "H280"), lel_vol=4.0, uel_vol=75.0),
    "carbon monoxide": SubstanceData("carbon monoxide", "630-08-0",
                                     ("H220", "H280", "H331", "H360", "H372"),
                                     lel_vol=12.5, uel_vol=74.0, oel_ppm=20.0),
    "ethanol": SubstanceData("ethanol", "64-17-5", ("H225", "H319"), flash_point_c=13.0,
                             lel_vol=3.3, uel_vol=19.0, oel_ppm=1000.0),
    "methanol": SubstanceData("methanol", "67-56-1", ("H225", "H301", "H311", "H331", "H370"),
                              flash_point_c=11.0, lel_vol=6.0, uel_vol=36.0, oel_ppm=200.0),
    "sulfuric acid": SubstanceData("sulfuric acid", "7664-93-9", ("H314",)),
    "sodium hydroxide": SubstanceData("sodium hydroxide", "1310-73-2", ("H290", "H314")),
    "hydrochloric acid": SubstanceData("hydrochloric acid", "7647-01-0", ("H290", "H314", "H335")),
}


def get_substance(name: str) -> SubstanceData:
    key = name.strip().lower()
    if key not in SUBSTANCES:
        raise KeyError(
            f"'{name}' is not in the built-in library. Add it in your YAML with explicit "
            f"h_codes, or try biossbd.hazards.pubchem_h_codes('{name}')."
        )
    return SUBSTANCES[key]


# ---------------------------------------------------------------------------
# Biological and process hazards (not covered by GHS)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProcessHazard:
    key: str
    group: str  # biological | process | occupational
    description: str
    typical_stages: tuple[str, ...]
    receptors: tuple[str, ...]
    severity: int  # screening default, 1-5


PROCESS_HAZARDS: dict[str, ProcessHazard] = {h.key: h for h in (
    ProcessHazard("bioaerosols", "biological",
                  "Airborne bacteria, fungi and spores released during handling and storage of biomass",
                  ("feedstock handling", "storage"), ("workers",), 3),
    ProcessHazard("mycotoxins", "biological",
                  "Fungal toxins (e.g. ochratoxin A, aflatoxins) in coffee and cocoa residues",
                  ("feedstock handling", "end of life"), ("workers", "consumers"), 3),
    ProcessHazard("endotoxins", "biological",
                  "Endotoxins from Gram-negative bacteria in manure and dusty feedstocks",
                  ("feedstock handling",), ("workers",), 3),
    ProcessHazard("pathogens in digestate", "biological",
                  "Survival of manure-borne pathogens (E. coli, Salmonella) in digestate applied to land",
                  ("end of life",), ("public", "soil", "water"), 4),
    ProcessHazard("acidification", "process",
                  "VFA accumulation and pH drop leading to process failure and gas quality changes",
                  ("processing",), ("installation",), 4),
    ProcessHazard("foaming", "process",
                  "Foam formation blocking gas lines and causing overpressure or spills",
                  ("processing",), ("installation", "workers"), 3),
    ProcessHazard("overpressure", "process",
                  "Gas holder or digester overpressure from blocked lines or failed relief",
                  ("processing", "storage"), ("installation", "workers", "public"), 4),
    ProcessHazard("explosive atmosphere", "process",
                  "ATEX zones around gas holders, upgrading units and flares",
                  ("processing", "storage"), ("workers", "public"), 5),
    ProcessHazard("confined space", "occupational",
                  "Asphyxiation and H2S exposure during tank entry and maintenance",
                  ("processing", "maintenance"), ("workers",), 5),
    ProcessHazard("ammonia emissions", "process",
                  "NH3 volatilisation during digestate storage and spreading",
                  ("storage", "end of life"), ("air", "public"), 3),
)}


# ---------------------------------------------------------------------------
# Optional online lookup
# ---------------------------------------------------------------------------
_PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest"


def pubchem_h_codes(name: str, timeout: float = 15.0) -> list[str]:
    """Fetch GHS hazard statements for a substance name from PubChem.

    Requires internet access. PubChem aggregates several notifications; the
    union of all reported codes is returned, which is conservative.
    """
    q = urllib.parse.quote(name)
    with urllib.request.urlopen(f"{_PUBCHEM}/pug/compound/name/{q}/cids/JSON", timeout=timeout) as r:
        cid = json.load(r)["IdentifierList"]["CID"][0]
    url = f"{_PUBCHEM}/pug_view/data/compound/{cid}/JSON?heading=GHS+Classification"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        text = r.read().decode("utf-8")
    codes = sorted(set(re.findall(r"\bH\d{3}\b", text)))
    return [c for c in codes if c in H_STATEMENTS]
