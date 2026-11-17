"""Risk matrices and FMEA (BioSSbD step 2: risk and reliability assessment)."""
from __future__ import annotations

from typing import Iterable

import pandas as pd
from pydantic import BaseModel, Field

RISK_CLASSES = ("Very Low", "Low", "Medium", "High", "Very High")


class RiskItem(BaseModel):
    """One risk category scored on ordinal 1-5 scales."""

    name: str
    impact: int = Field(ge=1, le=5)
    likelihood: int = Field(ge=1, le=5)
    detectability: int | None = Field(default=None, ge=1, le=10,
                                      description="FMEA detection rating (10 = hardest to detect)")
    stage: str | None = None
    description: str = ""
    mitigation: str = ""

    @property
    def risk_index(self) -> float:
        """Mean of impact and likelihood (as used in the AcoD screening study)."""
        return (self.impact + self.likelihood) / 2

    @property
    def product(self) -> int:
        """Impact x likelihood (1-25), the classic risk-matrix score."""
        return self.impact * self.likelihood

    @property
    def risk_class(self) -> str:
        return classify_index(self.risk_index)

    @property
    def rpn(self) -> int | None:
        """FMEA risk priority number: severity x occurrence x detection.

        Impact and likelihood (1-5) are rescaled to the usual FMEA 1-10 scale.
        """
        if self.detectability is None:
            return None
        return (2 * self.impact) * (2 * self.likelihood) * self.detectability


def classify_index(ri: float) -> str:
    if ri >= 4.5:
        return "Very High"
    if ri >= 3.5:
        return "High"
    if ri >= 2.5:
        return "Medium"
    if ri >= 1.5:
        return "Low"
    return "Very Low"


def risk_table(items: Iterable[RiskItem]) -> pd.DataFrame:
    rows = []
    for r in items:
        rows.append({
            "risk": r.name, "stage": r.stage, "impact": r.impact, "likelihood": r.likelihood,
            "risk_index": r.risk_index, "I_x_L": r.product, "class": r.risk_class,
            "RPN": r.rpn, "mitigation": r.mitigation,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["I_x_L", "risk_index"], ascending=False).reset_index(drop=True)


def reliability_score(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Weighted reliability score of a scenario (1-5 scale, higher = more reliable).

    Weights are normalised to sum to one, which avoids the mis-scaling that
    occurs when published weights do not add up to 1.
    """
    if not scores:
        raise ValueError("scores must not be empty")
    if weights is None:
        weights = {k: 1.0 for k in scores}
    missing = set(scores) - set(weights)
    if missing:
        raise KeyError(f"Missing weights for: {sorted(missing)}")
    total = sum(weights[k] for k in scores)
    return sum(scores[k] * weights[k] for k in scores) / total
