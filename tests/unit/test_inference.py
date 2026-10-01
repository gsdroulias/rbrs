import pytest

from rbrs.inference import InferenceEngine, RuleEvaluationError, activation_stats, chain_report
from rbrs.profile import ResidueStream
from rbrs.rules import Condition, Rule
from tests.conftest import make_profile


def rule(
    rid: str, *conds: Condition, consequent: str | None = None, derive: dict[str, object] | None = None, **kw: object
) -> Rule:
    return Rule(id=rid, name=rid, antecedent=list(conds), consequent=consequent, derive=derive, provenance="P", **kw)  # type: ignore[arg-type]


def C(field: str, op: str, value: object = None) -> Condition:
    return Condition(field=field, op=op, value=value)  # type: ignore[arg-type]


def test_inference_engine_basic() -> None:
    engine = InferenceEngine([rule("R1", C("process_efficiency", "==", "medium"), consequent="ACT-1")])
    res = engine.run(make_profile())
    assert res.intervention_ids == ["ACT-1"]
    assert len(res.trace) == 1
    assert res.trace[0].rule_id == "R1" and res.trace[0].status == "fired"


def test_maturity_gate_blocks_rule() -> None:
    res = InferenceEngine([rule("R2", consequent="ACT-2", maturity_gate=3)]).run(make_profile(maturity_level=2))
    assert res.intervention_ids == []
    assert "maturity gate" in res.trace[0].reason


@pytest.mark.parametrize(
    ("capital", "gate", "fires"),
    [
        ("low", "low", True),
        ("low", "low_moderate", False),
        ("low_moderate", "moderate", False),  # bug in the original engine: this passed
        ("moderate", "moderate", True),
        ("high", "moderate", True),
        ("moderate", "high", False),
    ],
)
def test_capital_gate_is_ordinal(capital: str, gate: str, fires: bool) -> None:
    engine = InferenceEngine([rule("R", consequent="A", capital_gate=gate)])
    res = engine.run(make_profile(capital_availability=capital))
    assert bool(res.intervention_ids) is fires


def test_any_match_finds_residue_records() -> None:
    # Regression: `"biomass" in residues` compared a string with records and never matched.
    r = rule("R", C("residues", "any_match", {"material": "wood", "disposition": ["energy_recovery"]}), consequent="A")
    wood = ResidueStream(material="wood", mass_t=1, disposition="energy_recovery", moisture_content=0.1)
    assert InferenceEngine([r]).run(make_profile(residues=[wood])).intervention_ids == ["A"]
    assert InferenceEngine([r]).run(make_profile(residues=[])).intervention_ids == []


def test_contains_and_not_contains() -> None:
    p = make_profile(certifications=["ISO14001"])
    has = rule("R", C("certifications", "contains", "ISO14001"), consequent="A")
    lacks = rule("R", C("certifications", "not_contains", "ISO14001"), consequent="A")
    assert InferenceEngine([has]).run(p).intervention_ids
    assert not InferenceEngine([lacks]).run(p).intervention_ids


def test_unknown_value_never_satisfies_a_comparison() -> None:
    p = make_profile(route_distance_km=None)
    assert not InferenceEngine([rule("R", C("route_distance_km", ">", 0), consequent="A")]).run(p).intervention_ids
    assert not InferenceEngine([rule("R", C("route_distance_km", "<=", 0), consequent="A")]).run(p).intervention_ids
    assert InferenceEngine([rule("R", C("route_distance_km", "is_null"), consequent="A")]).run(p).intervention_ids


def test_type_errors_are_reported_not_hidden() -> None:
    with pytest.raises(RuleEvaluationError):
        InferenceEngine([rule("R", C("sector", ">", 3), consequent="A")]).run(make_profile())


def test_forward_chaining_and_ablation() -> None:
    rules = [
        rule("CONSUMER", C("facts.hot", "==", True), consequent="B"),
        rule("DERIVE", C("thermal_fuel", "==", "natural_gas"), derive={"hot": True}),
    ]
    full = InferenceEngine(rules).run(make_profile())
    assert full.intervention_ids == ["B"]
    assert full.chained and full.derived_facts == {"hot": True}
    assert [t.rule_id for t in full.trace if t.status == "fired"] == ["DERIVE", "CONSUMER"]
    assert full.candidates[0].via_derived_fact

    single = InferenceEngine(rules, chaining=False).run(make_profile())
    assert single.intervention_ids == [] and not single.chained


def test_conflict_resolution_specificity_then_priority_then_order() -> None:
    rules = [
        rule("LOW", consequent="X1"),
        rule("PRIO", consequent="X2", priority=5),
        rule("SPECIFIC", C("sector", "==", "Manufacturing"), C("maturity_level", ">=", 1), consequent="X3"),
    ]
    res = InferenceEngine(rules).run(make_profile())
    assert [t.rule_id for t in res.trace if t.status == "fired"] == ["SPECIFIC", "PRIO", "LOW"]


def test_trace_is_deterministic() -> None:
    # The old trace stored time.time(), so identical runs produced different output.
    rules = [rule("A", consequent="X"), rule("B", C("scope1.tco2e", ">", 1e9), consequent="Y")]
    assert InferenceEngine(rules).run(make_profile()).trace == InferenceEngine(rules).run(make_profile()).trace


def test_cycle_cap_reports_non_termination() -> None:
    res = InferenceEngine([rule("A", consequent="X"), rule("B", consequent="Y")], max_cycles=1).run(make_profile())
    assert not res.terminated and res.cycles == 1


def test_same_intervention_from_two_rules_listed_once() -> None:
    res = InferenceEngine([rule("A", consequent="X"), rule("B", consequent="X")]).run(make_profile())
    assert len(res.candidates) == 1 and res.candidates[0].rule_ids == ("A", "B")


def test_chain_report_and_activation_stats() -> None:
    rules = [
        rule("D", C("thermal_fuel", "==", "natural_gas"), derive={"hot": True}),
        rule("U", C("facts.hot", "==", True), consequent="B"),
        rule("DEAD", C("scope1.tco2e", ">", 1e9), consequent="Z"),
    ]
    profiles = [make_profile(), make_profile(thermal_fuel=None)]
    stats = activation_stats(rules, profiles)
    assert stats["activation_frequency"] == {"D": 1, "U": 1, "DEAD": 0}
    assert stats["dead_rules"] == ["DEAD"]
    report = chain_report([InferenceEngine(rules).run(p) for p in profiles])
    assert report["chaining_occurs"] and report["profiles_with_chaining"] == 1
