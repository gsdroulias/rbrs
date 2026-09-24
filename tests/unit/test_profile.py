import pytest
from pydantic import ValidationError
from rbrs.profile.models import SMEProfile, Emissions, ResidueStream

def test_valid_profile_loads():
    profile = SMEProfile(
        sector="Manufacturing",
        employees_fte=50,
        turnover_meur=5.5,
        scope1=Emissions(tco2e=100.0, assessed=True),
        scope2=Emissions(tco2e=50.0, assessed=True),
        scope3=Emissions(tco2e=None, assessed=False),
        energy_carriers=["electricity", "diesel"],
        electricity_supply="grid_mixed",
        thermal_fuel="diesel",
        residues=[],
        certifications=["ISO14001"],
        capital_availability="moderate",
        maturity_level=2,
        logistics_mode="diesel_truck",
        route_distance_km=120.5,
        material_type="Virgin_Steel",
        process_efficiency="medium"
    )
    assert profile.sector == "Manufacturing"
    assert profile.scope3.assessed is False

def test_missing_required_field_fails():
    with pytest.raises(ValidationError):
        # Missing 'sector' and others
        SMEProfile(employees_fte=50)

def test_negative_mass_rejected():
    with pytest.raises(ValidationError):
        ResidueStream(
            material="wood",
            mass_t=-5.0,
            disposition="landfill",
            moisture_content=0.2
        )
