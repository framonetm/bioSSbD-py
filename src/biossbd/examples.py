"""Bundled example systems (shipped inside the package)."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from .scoping import SSbDSystem, load_system


def acod_path() -> Path:
    """Path of the anaerobic co-digestion (AcoD) example YAML."""
    return Path(str(resources.files("biossbd") / "data" / "acod_system.yaml"))


def acod() -> SSbDSystem:
    return load_system(acod_path())


def empty_system_dict() -> dict:
    """A minimal starting point for a new assessment."""
    return {
        "name": "New SSbD system",
        "functional_unit": "",
        "alternatives": [{"name": "Alternative A"}, {"name": "Alternative B"}],
        "indicator_specs": [
            {"name": "Safety score", "dimension": "Safety", "scale": [1, 5], "ordinal": True},
            {"name": "GHG intensity", "dimension": "Environmental", "direction": "min", "unit": "kg CO2-eq/FU"},
            {"name": "Net present value", "dimension": "Economic", "unit": "EUR"},
        ],
    }


def tea_presets_path() -> Path:
    """Biogas-CHP techno-economic presets for the AcoD example (sourced parameters)."""
    return Path(str(resources.files("biossbd") / "data" / "acod_tea_presets.yaml"))
