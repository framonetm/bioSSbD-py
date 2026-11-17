"""Data points with provenance and data-quality flags.

Every number entering an SSbD assessment carries its source, the kind of
evidence behind it and (optionally) an uncertainty range, so that the
dossier can report how much each conclusion rests on measured, modelled,
literature or expert data.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EvidenceType = Literal["measured", "modelled", "literature", "expert", "assumed"]

#: Default ordinal quality score per evidence type (5 = best).
EVIDENCE_SCORE: dict[str, int] = {
    "measured": 5, "modelled": 4, "literature": 3, "expert": 2, "assumed": 1,
}


class DataPoint(BaseModel):
    """A value with unit, source and data-quality information."""

    value: float
    unit: str = ""
    source: str = ""
    evidence: EvidenceType = "assumed"
    low: float | None = None
    high: float | None = None
    note: str = ""

    @model_validator(mode="after")
    def _check_range(self) -> "DataPoint":
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError("low must not exceed high")
        return self

    @property
    def quality(self) -> int:
        return EVIDENCE_SCORE[self.evidence]

    @property
    def has_range(self) -> bool:
        return self.low is not None and self.high is not None


def as_datapoint(x: float | int | dict | DataPoint) -> DataPoint:
    """Coerce a bare number or a mapping into a DataPoint."""
    if isinstance(x, DataPoint):
        return x
    if isinstance(x, (int, float)):
        return DataPoint(value=float(x))
    return DataPoint(**x)


class QualitySummary(BaseModel):
    n: int = 0
    by_evidence: dict[str, int] = Field(default_factory=dict)
    mean_quality: float | None = None
    share_with_range: float | None = None


def summarise(points: list[DataPoint]) -> QualitySummary:
    if not points:
        return QualitySummary()
    counts: dict[str, int] = {}
    for p in points:
        counts[p.evidence] = counts.get(p.evidence, 0) + 1
    return QualitySummary(
        n=len(points),
        by_evidence=counts,
        mean_quality=round(sum(p.quality for p in points) / len(points), 2),
        share_with_range=round(sum(p.has_range for p in points) / len(points), 2),
    )
