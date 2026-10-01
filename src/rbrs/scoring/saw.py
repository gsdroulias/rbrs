"""Simple Additive Weighting on an absolute discrete scale (FR-10 to FR-12)."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NormMode = Literal["total_absolute", "scope_relative"]
UNQUANTIFIED = "UNQUANTIFIED"
IMPACT_LEVELS = (0.00, 0.25, 0.50, 0.75, 1.00)

# DESIGN.md banding of the abatement share. Boundary convention (an assumption to
# confirm against the manuscript): 0.00 if share <= 0; 0.25 if share < 5%;
# 0.50 if 5% <= share <= 10%; 0.75 if 10% < share <= 20%; 1.00 if share > 20%.
IMPACT_BAND_EDGES = (0.05, 0.10, 0.20)


def band_impact(share: float) -> float:
    low, mid, high = IMPACT_BAND_EDGES
    if share <= 0:
        return 0.00
    if share < low:
        return 0.25
    if share <= mid:
        return 0.50
    if share <= high:
        return 0.75
    return 1.00


class Weights(BaseModel):
    model_config = ConfigDict(frozen=True)

    w_i: float = Field(0.50, ge=0)
    w_f: float = Field(0.30, ge=0)
    w_c: float = Field(0.20, ge=0)

    @model_validator(mode="after")
    def _sum_to_one(self) -> "Weights":
        if not math.isclose(self.w_i + self.w_f + self.w_c, 1.0, abs_tol=1e-9):
            raise ValueError("weights must sum to 1")
        return self

    @classmethod
    def parse(cls, text: str) -> "Weights":
        """'default' or 'w_i,w_f,w_c', e.g. '0.5,0.3,0.2'."""
        if text == "default":
            return cls()
        parts = [float(p) for p in text.split(",")]
        if len(parts) != 3:
            raise ValueError("weights must be 'default' or three comma-separated numbers")
        return cls(w_i=parts[0], w_f=parts[1], w_c=parts[2])


class Candidate(BaseModel):
    id: str
    impact: float
    feasibility: float
    cost_effectiveness: float


class ScoredCandidate(BaseModel):
    candidate: Candidate
    fis: float
    rank: int = 0
    # How this rank is separated from its neighbour below (the last rank: from
    # the one above): "score", "tie_break:impact", "tie_break:feasibility",
    # "tie_break:cost_effectiveness", "tie_break:id", or "single".
    decided_by: str = ""


def _separation(a: ScoredCandidate, b: ScoredCandidate) -> str:
    if a.fis != b.fis:
        return "score"
    for name in ("impact", "feasibility", "cost_effectiveness"):
        if getattr(a.candidate, name) != getattr(b.candidate, name):
            return f"tie_break:{name}"
    return "tie_break:id"


class SAWScorer:
    def __init__(self, w_i: float = 0.50, w_f: float = 0.30, w_c: float = 0.20):
        self.weights = Weights(w_i=w_i, w_f=w_f, w_c=w_c)
        self.w_i, self.w_f, self.w_c = w_i, w_f, w_c

    @classmethod
    def from_weights(cls, w: Weights) -> "SAWScorer":
        return cls(w.w_i, w.w_f, w.w_c)

    def score(self, c: Candidate) -> float:
        """Final Intervention Score. Rounded to 9 d.p. only to remove float noise,
        so that equal scores compare equal and ties are detected."""
        return round(self.w_i * c.impact + self.w_f * c.feasibility + self.w_c * c.cost_effectiveness, 9)

    def rank(self, candidates: list[Candidate]) -> list[ScoredCandidate]:
        """Sort by FIS, then higher I, higher F, higher C, then id (A-Z)."""
        scored = [ScoredCandidate(candidate=c, fis=self.score(c)) for c in candidates]
        scored.sort(
            key=lambda s: (
                -s.fis,
                -s.candidate.impact,
                -s.candidate.feasibility,
                -s.candidate.cost_effectiveness,
                s.candidate.id,
            )
        )
        for i, s in enumerate(scored):
            s.rank = i + 1
            if len(scored) == 1:
                s.decided_by = "single"
            elif i + 1 < len(scored):
                s.decided_by = _separation(s, scored[i + 1])
            else:
                s.decided_by = _separation(scored[i - 1], s)
        return scored
