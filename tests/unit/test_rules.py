from pathlib import Path

import pytest
from pydantic import ValidationError

from rbrs.rules import Condition, Rule, RuleBaseError, fields_read, load_interventions, load_rules, rule_stats
from tests.conftest import REPO


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "r.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_load_valid_rules(tmp_path: Path) -> None:
    rules = load_rules(
        _write(
            tmp_path,
            """
- id: TEST-1
  name: Test Rule
  antecedent:
    - {field: process_efficiency, op: "==", value: "low"}
  consequent: DO-SOMETHING
  provenance: "Test Source"
""",
        )
    )
    assert len(rules) == 1
    assert rules[0].id == "TEST-1"
    assert rules[0].module == "r"


def test_unknown_field_rejected(tmp_path: Path) -> None:
    with pytest.raises(RuleBaseError, match="unknown profile field"):
        load_rules(
            _write(
                tmp_path,
                """
- {id: X, name: x, antecedent: [{field: scope1.co2, op: ">", value: 0}], consequent: A, provenance: p}
""",
            )
        )


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    with pytest.raises(RuleBaseError, match="duplicate"):
        load_rules(
            _write(
                tmp_path,
                """
- {id: X, name: x, antecedent: [], consequent: A, provenance: p}
- {id: X, name: y, antecedent: [], consequent: B, provenance: p}
""",
            )
        )


def test_fact_must_be_derived_somewhere(tmp_path: Path) -> None:
    with pytest.raises(RuleBaseError, match="no rule derives"):
        load_rules(
            _write(
                tmp_path,
                """
- {id: X, name: x, antecedent: [{field: facts.nope, op: "==", value: true}], consequent: A, provenance: p}
""",
            )
        )


def test_any_match_attributes_checked(tmp_path: Path) -> None:
    with pytest.raises(RuleBaseError, match="unknown ResidueStream attributes"):
        load_rules(
            _write(
                tmp_path,
                """
- {id: X, name: x, antecedent: [{field: residues, op: any_match, value: {colour: red}}], consequent: A, provenance: p}
""",
            )
        )


def test_unknown_operator_rejected() -> None:
    with pytest.raises(ValidationError):
        Condition(field="sector", op="~=", value="x")  # type: ignore[arg-type]


def test_exactly_one_consequent() -> None:
    with pytest.raises(ValidationError):
        Rule(id="X", name="x", antecedent=[], provenance="p")
    with pytest.raises(ValidationError):
        Rule(id="X", name="x", antecedent=[], consequent="A", derive={"f": 1}, provenance="p")


def test_capital_gate_must_be_a_level() -> None:
    with pytest.raises(ValidationError):
        Rule(id="X", name="x", antecedent=[], consequent="A", provenance="p", capital_gate="lots")  # type: ignore[arg-type]


def test_drafts_excluded_by_default(tmp_path: Path) -> None:
    d = _write(
        tmp_path,
        """
- {id: A1, name: a, antecedent: [], consequent: A, provenance: p}
- {id: D1, name: d, status: draft, antecedent: [], consequent: B, provenance: SOURCE_NEEDED}
""",
    )
    assert [r.id for r in load_rules(d)] == ["A1"]
    assert [r.id for r in load_rules(d, include_drafts=True)] == ["A1", "D1"]


def test_rule_stats() -> None:
    rules = [
        Rule(id="1", name="A", antecedent=[], consequent="C", provenance="P"),
        Rule(id="2", name="B", antecedent=[], derive={"f": True}, provenance="SOURCE_NEEDED"),
    ]
    stats = rule_stats(rules)
    assert stats["total_rules"] == 2
    assert stats["derivation_rules"] == 1
    assert stats["unsourced_rules"] == ["2"]


def test_fields_read_includes_gates() -> None:
    r = Rule(
        id="1",
        name="A",
        antecedent=[Condition(field="scope1.tco2e", op=">", value=0)],
        consequent="C",
        provenance="P",
        maturity_gate=2,
        capital_gate="moderate",
    )
    assert fields_read([r]) == {"scope1.tco2e", "maturity_level", "capital_availability"}


def test_repository_knowledge_base_is_valid() -> None:
    rules = load_rules(REPO / "data" / "rules", include_drafts=True)
    catalogue = load_interventions(REPO / "data" / "interventions.yaml")
    assert {r.consequent for r in rules if r.consequent} <= set(catalogue)
    assert all(r.is_sourced for r in rules if r.status == "active")


def test_intervention_value_needs_a_source(tmp_path: Path) -> None:
    p = tmp_path / "i.yaml"
    p.write_text("- {id: I, name: i, hierarchy: reduce, feasibility: 0.5}\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="no source"):
        load_interventions(p)
    p.write_text("- {id: I, name: i, hierarchy: reduce, feasibility: 0.6, feasibility_source: x}\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="must be one of"):
        load_interventions(p)
