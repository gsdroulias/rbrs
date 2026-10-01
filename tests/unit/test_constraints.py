import pytest
from pydantic import ValidationError

from rbrs.constraints import (
    ADDITIONALITY_UNVERIFIED,
    BURDEN_SHIFTING,
    SCOPE_SHIFT,
    Factor,
    FactorTable,
    MissingFactorError,
    calculate_substitution_delta,
    evaluate_constraints,
    lhv_at_moisture,
    load_factors,
)
from rbrs.pipeline import KnowledgeBase
from rbrs.profile import Emissions, SMEProfile
from tests.conftest import REPO, make_profile


def test_factor_missing_source_fails() -> None:
    with pytest.raises(ValidationError):
        Factor(id="test", value=1.0, unit="kg", source="")


def test_factor_missing_source_fails_whitespace() -> None:
    with pytest.raises(ValidationError):
        Factor(id="test", value=1.0, unit="kg", source="   ")


def test_source_needed_factor_cannot_carry_a_value() -> None:
    with pytest.raises(ValidationError):
        Factor(id="x", value=1.0, unit="kg", source="SOURCE_NEEDED", status="SOURCE_NEEDED")
    with pytest.raises(ValidationError):
        Factor(id="x", value=1.0, unit="kg", source="SOURCE_NEEDED")  # status cited by default
    Factor(id="x", value=None, unit="kg", source="SOURCE_NEEDED", status="SOURCE_NEEDED")


def test_factor_table_checks_units_and_availability() -> None:
    t = FactorTable(
        {
            "a": Factor(id="a", value=2.0, unit="MJ/kg", source="s"),
            "b": Factor(id="b", value=None, unit="MJ/kg", source="SOURCE_NEEDED", status="SOURCE_NEEDED"),
        }
    )
    assert t.get("a", "MJ/kg") == 2.0
    with pytest.raises(ValueError, match="unit"):
        t.get("a", "MJ/t")
    with pytest.raises(MissingFactorError):
        t.get("b", "MJ/kg")
    assert t.missing(["a", "b", "c"]) == ["b", "c"]


def test_every_repository_factor_has_a_source() -> None:  # AC-07
    factors = load_factors(REPO / "data" / "factors")
    assert factors
    assert all(f.source.strip() for f in factors.values())


def test_calculate_substitution_delta() -> None:
    delta = calculate_substitution_delta(
        m_diverted_kg=1000.0,
        lhv_mj_kg=15.0,
        eta_boiler=0.8,
        ef_replacement_tco2_mj=0.0001,
        ef_displaced_virgin_tco2_kg=0.002,
    )
    # 1000*15/0.8*0.0001 - 1000*0.002 = 1.875 - 2.0
    assert delta == pytest.approx(-0.125)


def test_lhv_at_moisture() -> None:
    assert lhv_at_moisture(18.0, 0.0, 2.443) == pytest.approx(18.0)
    assert lhv_at_moisture(18.0, 0.2, 2.443) == pytest.approx(18.0 * 0.8 - 2.443 * 0.2)
    with pytest.raises(ValueError):
        lhv_at_moisture(18.0, 1.0, 2.443)


def test_energy_substitution_hand_calculation(kb: KnowledgeBase, wood_profile: SMEProfile) -> None:
    cr = evaluate_constraints(kb.interventions["INT-WOOD"], wood_profile, kb.factors)
    lhv = 18.0 * 0.8 - 2.443 * 0.2  # 13.9114 MJ/kg as received
    e_lost = 10.0 * 1000 * lhv  # MJ
    co2_repl = e_lost / 0.9 * 0.0000561  # t, natural gas replaces the lost heat
    co2_avoided = 10.0 * 0.5  # t, displaced virgin material
    assert cr.changes_t["scope1"] == pytest.approx(co2_repl)
    assert cr.changes_t["avoided_virgin_material"] == pytest.approx(-co2_avoided)
    assert cr.net_delta_t == pytest.approx(co2_repl - co2_avoided)
    assert BURDEN_SHIFTING in cr.flags  # 8.67 t added > 5 t avoided
    assert cr.biogenic_co2_t == pytest.approx(-e_lost * 0.000112)
    assert "scope1" in cr.changes_t and cr.biogenic_co2_t not in cr.changes_t.values()


def test_missing_factor_blocks_instead_of_guessing(kb: KnowledgeBase, wood_profile: SMEProfile) -> None:
    factors = FactorTable({k: v for k, v in kb.factors.factors.items() if k != "virgin"})
    cr = evaluate_constraints(kb.interventions["INT-WOOD"], wood_profile, factors)
    assert cr.net_delta_t is None
    assert "factor:virgin" in cr.missing


def test_missing_moisture_blocks(kb: KnowledgeBase, wood_profile: SMEProfile) -> None:
    p = wood_profile.model_copy(
        update={"residues": [wood_profile.residues[0].model_copy(update={"moisture_content": None})]}
    )
    cr = evaluate_constraints(kb.interventions["INT-WOOD"], p, kb.factors)
    assert cr.net_delta_t is None and any("moisture" in m for m in cr.missing)


def test_scope_shift_flagged(kb: KnowledgeBase) -> None:
    cr = evaluate_constraints(kb.interventions["INT-C"], make_profile(), kb.factors)
    assert cr.changes_t == {"scope1": pytest.approx(-40.0), "scope2": pytest.approx(10.0)}
    assert SCOPE_SHIFT in cr.flags and BURDEN_SHIFTING not in cr.flags


def test_unassessed_scope_is_not_substituted(kb: KnowledgeBase) -> None:
    p = make_profile(scope2=Emissions(tco2e=None, assessed=False))
    cr = evaluate_constraints(kb.interventions["INT-A"], p, kb.factors)
    assert cr.net_delta_t is None and "scope2 not assessed" in cr.missing


def test_market_based_instrument_flagged(kb: KnowledgeBase) -> None:
    cr = evaluate_constraints(kb.interventions["INT-GREEN"], make_profile(), kb.factors)
    assert ADDITIONALITY_UNVERIFIED in cr.flags
