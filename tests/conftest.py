"""Shared fixtures. Numbers in the fixture knowledge base are test inputs chosen
for easy hand calculation; they are not emission factors and never reach data/."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from rbrs.pipeline import KnowledgeBase
from rbrs.profile import Emissions, ResidueStream, SMEProfile

REPO = Path(__file__).resolve().parents[1]


def make_profile(**overrides: Any) -> SMEProfile:
    base: dict[str, Any] = dict(
        sector="Manufacturing",
        employees_fte=40,
        turnover_meur=5.0,
        scope1=Emissions(tco2e=100.0, assessed=True),
        scope2=Emissions(tco2e=100.0, assessed=True),
        scope3=Emissions(tco2e=None, assessed=False),
        energy_carriers=["electricity", "natural_gas"],
        electricity_supply="grid",
        thermal_fuel="natural_gas",
        residues=[],
        certifications=[],
        capital_availability="moderate",
        maturity_level=2,
        logistics_mode="diesel_truck",
        route_distance_km=100.0,
        material_type="Steel",
        process_efficiency="medium",
    )
    base.update(overrides)
    return SMEProfile(**base)


@pytest.fixture
def profile() -> SMEProfile:
    return make_profile()


@pytest.fixture
def wood_profile() -> SMEProfile:
    return make_profile(
        maturity_level=3,
        residues=[ResidueStream(material="wood", mass_t=10.0, disposition="energy_recovery", moisture_content=0.2)],
    )


FIXTURE_RULES = """
- id: D-1
  name: fossil heat
  antecedent: [{field: thermal_fuel, op: in, value: [natural_gas, diesel]}]
  derive: {fossil_thermal: true}
  provenance: test
- id: R-LED
  name: led
  antecedent: [{field: scope2.tco2e, op: ">", value: 0}]
  consequent: INT-A
  provenance: test
- id: R-PV
  name: pv
  antecedent: [{field: scope2.tco2e, op: ">", value: 0}]
  capital_gate: moderate
  consequent: INT-B
  provenance: test
- id: R-HP
  name: heat pump (chained)
  antecedent: [{field: facts.fossil_thermal, op: "==", value: true}]
  consequent: INT-C
  provenance: test
- id: R-WOOD
  name: wood diversion
  antecedent: [{field: residues, op: any_match, value: {material: wood, disposition: energy_recovery}}]
  maturity_gate: 3
  consequent: INT-WOOD
  provenance: test
- id: R-GREEN
  name: tariff
  antecedent: [{field: electricity_supply, op: in, value: [grid]}]
  consequent: INT-GREEN
  provenance: test
- id: R-DRAFT
  name: draft rule
  status: draft
  antecedent: [{field: scope1.tco2e, op: ">", value: 0}]
  consequent: INT-A
  provenance: SOURCE_NEEDED
"""

FIXTURE_INTERVENTIONS = """
- id: INT-A
  name: A
  hierarchy: reduce
  effects: [{scope: scope2, change_fraction: -0.30, source: test}]
  feasibility: 1.00
  feasibility_source: test
  cost_effectiveness: 1.00
  cost_source: test
- id: INT-B
  name: B
  hierarchy: replace
  effects: [{scope: scope2, change_fraction: -0.50, source: test}]
  feasibility: 0.25
  feasibility_source: test
  cost_effectiveness: 0.25
  cost_source: test
- id: INT-C
  name: C (shifts scope 1 to scope 2)
  hierarchy: replace
  effects:
    - {scope: scope1, change_fraction: -0.40, source: test}
    - {scope: scope2, change_fraction: 0.10, source: test}
  feasibility: 0.50
  feasibility_source: test
  cost_effectiveness: 0.50
  cost_source: test
- id: INT-WOOD
  name: wood
  hierarchy: avoid
  residue_diversion:
    material: wood
    from_disposition: energy_recovery
    to_disposition: material_recovery
    lhv_dry_factor: lhv_dry_wood
    boiler_efficiency_factor: eta_boiler
    replacement_fuel_factor: ng
    displaced_virgin_factor: virgin
    biogenic_factor: biogenic
  feasibility: 0.75
  feasibility_source: test
  cost_effectiveness: 0.75
  cost_source: test
- id: INT-GREEN
  name: tariff
  hierarchy: replace
  instrument: market_based
  effects: [{scope: scope2, change_fraction: null}]
"""

FIXTURE_FACTORS = """
- {id: lhv_dry_wood, value: 18.0, unit: "MJ/kg", source: test}
- {id: latent_heat_vaporisation_water, value: 2.443, unit: "MJ/kg", source: test}
- {id: eta_boiler, value: 0.9, unit: fraction, source: test}
- {id: ng, value: 0.0000561, unit: "tCO2/MJ", source: test}
- {id: virgin, value: 0.5, unit: "tCO2/t", source: test}
- {id: biogenic, value: 0.000112, unit: "tCO2/MJ", source: test}
"""


def write_kb(root: Path) -> Path:
    (root / "rules").mkdir(parents=True, exist_ok=True)
    (root / "factors").mkdir(parents=True, exist_ok=True)
    (root / "rules" / "test.yaml").write_text(FIXTURE_RULES, encoding="utf-8")
    (root / "interventions.yaml").write_text(FIXTURE_INTERVENTIONS, encoding="utf-8")
    (root / "factors" / "f.yaml").write_text(FIXTURE_FACTORS, encoding="utf-8")
    return root


@pytest.fixture
def kb(tmp_path: Path) -> KnowledgeBase:
    return KnowledgeBase.load(write_kb(tmp_path / "kb"))


@pytest.fixture
def repo_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the repo's data and config in a temp dir, used as the working directory."""
    dest = tmp_path / "repo"
    for name in ("data", "config", "prompts"):
        shutil.copytree(REPO / name, dest / name, ignore=shutil.ignore_patterns("corpus"))
    monkeypatch.chdir(dest)
    return dest
