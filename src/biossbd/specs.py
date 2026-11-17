"""Indicator metadata shared by scoping (YAML input) and evaluation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class IndicatorSpec(BaseModel):
    """Describes one indicator used to compare alternatives.

    ``scale`` gives fixed bounds (e.g. ``(1, 5)`` for ordinal scores); without it
    the indicator is min-max normalised across the alternatives. ``weight`` is
    the weight inside its dimension. ``step`` links the indicator to a step of
    the BioSSbD methodology (1-11).
    """

    name: str
    dimension: str
    direction: Literal["max", "min"] = "max"
    unit: str = ""
    scale: tuple[float, float] | None = None
    weight: float = 1.0
    ordinal: bool = False
    step: int | None = None
    description: str = ""
