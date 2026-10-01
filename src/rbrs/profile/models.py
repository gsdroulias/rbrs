"""Typed SME profile (FR-01) and extraction record schemas (FR-02).

This module sits at the bottom of the dependency graph: every other package may
import it, and it imports nothing from rbrs.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CapitalLevel = Literal["low", "low_moderate", "moderate", "high"]

# Ordinal scale used by capital gates: a profile passes a gate when its level is
# at least the gate's level.
CAPITAL_ORDER: dict[str, int] = {"low": 0, "low_moderate": 1, "moderate": 2, "high": 3}

SOURCE_NEEDED = "SOURCE_NEEDED"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Emissions(_Strict):
    tco2e: float | None = Field(default=None, ge=0.0)
    assessed: bool

    @model_validator(mode="after")
    def _unassessed_has_no_value(self) -> "Emissions":
        # An unassessed scope must stay unknown; a 0.0 would silently read as
        # "no emissions" and feed the scoring layer a substituted value.
        if not self.assessed and self.tco2e is not None:
            raise ValueError("an unassessed scope must have tco2e = null")
        if self.assessed and self.tco2e is None:
            raise ValueError("an assessed scope must report tco2e")
        return self


class ResidueStream(_Strict):
    material: str
    mass_t: float = Field(ge=0.0)
    disposition: Literal["landfill", "energy_recovery", "material_recovery"]
    moisture_content: float | None = Field(default=None, ge=0.0, lt=1.0)  # wet-basis fraction


class SMEProfile(_Strict):
    sector: str
    employees_fte: int = Field(ge=0)
    turnover_meur: float | None = Field(default=None, ge=0.0)
    scope1: Emissions
    scope2: Emissions
    scope3: Emissions
    energy_carriers: list[str]
    electricity_supply: Literal["grid", "grid_mixed", "green_tariff", "onsite"]
    thermal_fuel: str | None
    residues: list[ResidueStream]
    certifications: list[str]
    capital_availability: CapitalLevel
    maturity_level: Literal[1, 2, 3]
    logistics_mode: Literal["diesel_truck", "rail", "electric_van"]
    route_distance_km: float | None = Field(default=None, ge=0.0)
    material_type: str
    process_efficiency: Literal["low", "medium", "high"]


PROFILE_ATTRIBUTES: tuple[str, ...] = tuple(SMEProfile.model_fields)


def profile_coverage(fields_read: set[str] | list[str] | tuple[str, ...]) -> list[str]:
    """FR-16: profile attributes that no rule reads.

    `fields_read` are the dotted field paths used in rule antecedents (see
    rbrs.rules.fields_read); only the top-level attribute of each path counts.
    """
    used = {path.split(".", 1)[0] for path in fields_read}
    return [attr for attr in PROFILE_ATTRIBUTES if attr not in used]


# --- Extraction schemas (shared by LLM and manual ingestion, FR-02/FR-05) ---


class Provenance(_Strict):
    page: int = Field(ge=1)
    section: str | None = None
    quote: str


class ExtractedField(_Strict):
    field: str
    value: Any = None
    status: Literal["EXTRACTED", "ABSTAINED"]
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance | None = None
    verified_in_source: bool | None = None  # set by the deterministic check (FR-03)
    verification_note: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "ExtractedField":
        if self.status == "ABSTAINED" and self.value is not None:
            raise ValueError(f"{self.field}: an abstained field must have value = null")
        if self.status == "EXTRACTED" and self.provenance is None:
            raise ValueError(f"{self.field}: an extracted field needs provenance")
        return self


class ExtractionRecord(_Strict):
    document_id: str
    method: Literal["llm", "manual"]
    model_id: str | None = None
    prompt_version: str | None = None
    fields: list[ExtractedField]
    usage: dict[str, int | None] = Field(default_factory=dict)

    def get(self, field: str) -> ExtractedField | None:
        for f in self.fields:
            if f.field == field:
                return f
        return None
