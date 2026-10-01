"""Intervention catalogue: the data each rule consequent needs to be scored.

Every quantity carries its own source. A value that has no source stays null and
the scoring layer reports the candidate as UNQUANTIFIED instead of guessing.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rbrs.profile.models import SOURCE_NEEDED

Scope = Literal["scope1", "scope2", "scope3"]
CRITERION_LEVELS = (0.25, 0.50, 0.75, 1.00)  # FR-10 scale for Feasibility and Cost-effectiveness


def _check_sourced(value: object, source: str, what: str) -> None:
    if value is not None and (not source.strip() or SOURCE_NEEDED in source):
        raise ValueError(f"{what} has a value but no source")


class ScopeEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Scope
    # Expected change as a fraction of that scope's current emissions;
    # negative = reduction. null = not yet sourced.
    change_fraction: float | None = Field(default=None, ge=-1.0)
    source: str = SOURCE_NEEDED

    @model_validator(mode="after")
    def _sourced(self) -> "ScopeEffect":
        _check_sourced(self.change_fraction, self.source, f"effect on {self.scope}")
        return self


class ResidueDiversion(BaseModel):
    """Diverting a residue stream that is currently burned for energy (FR-09a)."""

    model_config = ConfigDict(extra="forbid")

    material: str
    from_disposition: Literal["energy_recovery", "landfill", "material_recovery"]
    to_disposition: Literal["energy_recovery", "landfill", "material_recovery"]
    lhv_dry_factor: str
    boiler_efficiency_factor: str
    replacement_fuel_factor: str
    displaced_virgin_factor: str
    biogenic_factor: str | None = None


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    # Mitigation hierarchy (avoid > reduce > replace > offset); "enabling" marks
    # actions such as an inventory that make later mitigation measurable.
    hierarchy: Literal["avoid", "reduce", "replace", "offset", "enabling"]
    instrument: Literal["physical", "market_based"] = "physical"
    effects: list[ScopeEffect] = Field(default_factory=list)
    residue_diversion: ResidueDiversion | None = None
    feasibility: float | None = None
    feasibility_source: str = SOURCE_NEEDED
    cost_effectiveness: float | None = None
    cost_source: str = SOURCE_NEEDED
    notes: str = ""

    @model_validator(mode="after")
    def _levels_and_sources(self) -> "Intervention":
        for name in ("feasibility", "cost_effectiveness"):
            v = getattr(self, name)
            if v is not None and v not in CRITERION_LEVELS:
                raise ValueError(f"{self.id}: {name} must be one of {CRITERION_LEVELS}")
        _check_sourced(self.feasibility, self.feasibility_source, f"{self.id} feasibility")
        _check_sourced(self.cost_effectiveness, self.cost_source, f"{self.id} cost_effectiveness")
        scopes = [e.scope for e in self.effects]
        if len(scopes) != len(set(scopes)):
            raise ValueError(f"{self.id}: one effect per scope")
        return self

    def missing_data(self) -> list[str]:
        missing = [f"effect.{e.scope}" for e in self.effects if e.change_fraction is None]
        if not self.effects and self.residue_diversion is None:
            missing.append("effects")
        if self.feasibility is None:
            missing.append("feasibility")
        if self.cost_effectiveness is None:
            missing.append("cost_effectiveness")
        return missing


def load_interventions(path: str | Path) -> dict[str, Intervention]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig")) or []
    catalogue: dict[str, Intervention] = {}
    for item in data:
        iv = Intervention(**item)
        if iv.id in catalogue:
            raise ValueError(f"duplicate intervention id {iv.id}")
        catalogue[iv.id] = iv
    return catalogue
