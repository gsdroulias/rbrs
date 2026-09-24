import pytest
from rbrs.profile.models import SMEProfile, Emissions
from rbrs.rules.models import Rule, Condition
from rbrs.inference.engine import InferenceEngine, chain_report

@pytest.fixture
def dummy_profile():
    return SMEProfile(
        sector="Manufacturing", employees_fte=10, turnover_meur=1.0,
        scope1=Emissions(tco2e=10.0, assessed=True),
        scope2=Emissions(tco2e=10.0, assessed=True),
        scope3=Emissions(tco2e=None, assessed=False),
        energy_carriers=["electricity"], electricity_supply="grid",
        thermal_fuel=None, residues=[], certifications=[],
        capital_availability="high", maturity_level=2,
        logistics_mode="diesel_truck", route_distance_km=100.0,
        material_type="wood", process_efficiency="low"
    )

def test_inference_engine_basic(dummy_profile):
    rule = Rule(
        id="R1", name="Test", consequent="ACT-1", provenance="P",
        antecedent=[Condition(field="process_efficiency", op="==", value="low")]
    )
    engine = InferenceEngine([rule])
    recs = engine.run(dummy_profile)
    
    assert "ACT-1" in recs
    assert len(engine.trace) == 1
    assert engine.trace[0].rule_id == "R1"

def test_maturity_gate_blocks_rule(dummy_profile):
    # Το προφίλ έχει maturity=2, ο κανόνας θέλει 3
    rule = Rule(
        id="R2", name="Gate", consequent="ACT-2", provenance="P", maturity_gate=3,
        antecedent=[Condition(field="process_efficiency", op="==", value="low")]
    )
    engine = InferenceEngine([rule])
    recs = engine.run(dummy_profile)
    assert len(recs) == 0

def test_chain_report():
    r1 = Rule(id="1", name="1", consequent="FACT_A", provenance="P", antecedent=[])
    r2 = Rule(id="2", name="2", consequent="ACT", provenance="P", 
              antecedent=[Condition(field="FACT_A", op="==", value=True)])
    assert chain_report([r1, r2]) is True
    assert chain_report([r1]) is False
