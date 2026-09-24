from typing import Any, Literal

from pydantic import BaseModel, Field


class Emissions(BaseModel):
    tco2e: float | None
    assessed: bool

class ResidueStream(BaseModel):
    material: str
    mass_t: float = Field(ge=0.0)  # ge=0.0 means Greater than or Equal to 0 (no negative mass)
    disposition: Literal["landfill", "energy_recovery", "material_recovery"]
    moisture_content: float | None

class SMEProfile(BaseModel):
    sector: str
    employees_fte: int
    turnover_meur: float | None
    scope1: Emissions
    scope2: Emissions
    scope3: Emissions
    energy_carriers: list[str]
    electricity_supply: Literal["grid", "grid_mixed", "green_tariff", "onsite"]
    thermal_fuel: str | None
    residues: list[ResidueStream]
    certifications: list[str]
    capital_availability: Literal["low", "low_moderate", "moderate", "high"]
    maturity_level: Literal[1, 2, 3]
    logistics_mode: Literal["diesel_truck", "rail", "electric_van"]
    route_distance_km: float | None
    material_type: str
    process_efficiency: Literal["low", "medium", "high"]

class Provenance(BaseModel):
    page: int
    section: str | None
    quote: str

class ExtractedField(BaseModel):
    field: str
    value: Any
    status: Literal["EXTRACTED", "ABSTAINED"]
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance | None
    verified_in_source: bool | None
