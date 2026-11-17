"""Registry of the methods, open-source tools and public databases available for
each step of the SSbD assessment, with licence, requirements and live status.

The GUI reads this registry to offer, at every step, a choice of method or data
source and to show whether each option is ready to use on this computer.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field

import pandas as pd

STEPS = (
    "Scoping", "Hazard identification", "Risk and reliability", "Inherent safety",
    "Environmental sustainability", "Socio-economic sustainability", "Evaluation", "Documentation",
)


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    steps: tuple[str, ...]
    kind: str  # built-in | library | application | database
    licence: str
    url: str
    description: str
    packages: tuple[str, ...] = field(default_factory=tuple)  # importable modules required
    needs_internet: bool = False
    needs_app: str = ""  # external application that must be running
    install: str = ""

    def installed(self) -> bool:
        return all(importlib.util.find_spec(p) is not None for p in self.packages)

    def status(self) -> str:
        if not self.installed():
            return "not installed"
        if self.needs_app:
            return f"installed (needs {self.needs_app})"
        if self.needs_internet:
            return "ready (online)"
        return "ready"


TOOLS: tuple[Tool, ...] = (
    Tool("yaml", "SSbD system description (YAML / tables)", ("Scoping",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py",
         "Stages, actors, substances, units and assessments; life-cycle safety matrix and scoping gaps."),
    Tool("ghs-library", "Built-in GHS and process-hazard library", ("Hazard identification",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py",
         "Screening classifications for common biorefinery substances and biological/process hazards (offline)."),
    Tool("pubchem", "PubChem (NIH)", ("Scoping", "Hazard identification", "Inherent safety"), "database",
         "Public (NCBI); contributor-specific terms apply", "https://pubchem.ncbi.nlm.nih.gov",
         "Compound search by name or CAS; GHS hazard statements with notification shares; flash point, "
         "explosive limits and exposure limits.", needs_internet=True),
    Tool("risk-matrix", "Risk matrix and FMEA", ("Risk and reliability",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py", "Impact x likelihood (IEC 31010 style) and FMEA risk priority numbers."),
    Tool("isi", "Inherent Safety Index (Heikkilä 1999)", ("Inherent safety",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py", "Chemical and process sub-indices; hazardous inventory KPIs."),
    Tool("manual", "Manual entry with provenance", ("Environmental sustainability", "Socio-economic sustainability"),
         "built-in", "MIT", "https://github.com/framonetm/bioSSbD-py",
         "Enter values from literature or other software with source and evidence type."),
    Tool("openlca", "openLCA 2 (GreenDelta)", ("Environmental sustainability",), "application", "MPL-2.0",
         "https://www.openlca.org",
         "Calculate product systems with any LCIA method in the database open in openLCA "
         "(free databases on openLCA Nexus, e.g. USLCI, Agribalyse, ELCD).",
         packages=("olca_ipc", "olca_schema"), needs_app="openLCA with IPC server on port 8080",
         install="pip install olca-ipc"),
    Tool("brightway", "Brightway 2.5", ("Environmental sustainability",), "library", "BSD-3-Clause",
         "https://docs.brightway.dev",
         "Search activities in your Brightway projects and calculate LCIA scores.",
         packages=("bw2data", "bw2calc"), install='pip install "biossbd[brightway]"'),
    Tool("qsdsan", "QSDsan / BioSTEAM", ("Environmental sustainability", "Socio-economic sustainability"), "library",
         "UIUC/NCSA", "https://qsdsan.readthedocs.io",
         "Process models (incl. ADM1), TEA and LCA from Python code; results imported with the adapters.",
         packages=("qsdsan", "biosteam"), install='pip install "biossbd[qsdsan]"'),
    Tool("owid", "Our World in Data – electricity carbon intensity (Ember)", ("Environmental sustainability",),
         "database", "CC BY 4.0", "https://ourworldindata.org/grapher/carbon-intensity-electricity",
         "Latest lifecycle carbon intensity of electricity per country, for regional context.", needs_internet=True),
    Tool("biogas-chp", "Biogas CHP model (feedstock to cash flow)", ("Socio-economic sustainability",), "built-in",
         "MIT", "https://github.com/framonetm/bioSSbD-py",
         "Methane from feedstock yields, CHP electricity, CAPEX from specific cost per kWe, O&M and tariff; "
         "presets with sourced parameters (IRENA costs, GlobalPetrolPrices tariffs, literature yields)."),
    Tool("cashflow", "Screening cash-flow model", ("Socio-economic sustainability",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py", "NPV, IRR, payback, levelised cost and benefit-cost ratio."),
    Tool("mcda", "MCDA and Monte Carlo robustness", ("Evaluation",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py",
         "Weighted sum, geometric mean, TOPSIS, PROMETHEE II, maximin; rank acceptability."),
    Tool("dossier", "SSbD dossier (Markdown)", ("Documentation",), "built-in", "MIT",
         "https://github.com/framonetm/bioSSbD-py", "Documentation of scoping, safety, sustainability and evaluation."),
)


def tools_for(step: str) -> list[Tool]:
    return [t for t in TOOLS if step in t.steps]


def get(tool_id: str) -> Tool:
    for t in TOOLS:
        if t.id == tool_id:
            return t
    raise KeyError(tool_id)


def status_table() -> pd.DataFrame:
    return pd.DataFrame([{
        "tool": t.name, "steps": ", ".join(t.steps), "type": t.kind, "licence": t.licence,
        "status": t.status(), "install": t.install, "url": t.url,
    } for t in TOOLS])
