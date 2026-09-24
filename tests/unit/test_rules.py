import pytest
from pathlib import Path
from pydantic import ValidationError
from rbrs.rules import load_rules, rule_stats, Rule

def test_load_valid_rules(tmp_path: Path):
    # Δημιουργία προσωρινού YAML για το τεστ
    rule_file = tmp_path / "test.yaml"
    rule_file.write_text("""
    - id: TEST-1
      name: Test Rule
      antecedent:
        - {field: process_efficiency, op: "==", value: "low"}
      consequent: DO-SOMETHING
      provenance: "Test Source"
    """)
    
    rules = load_rules(tmp_path)
    assert len(rules) == 1
    assert rules[0].id == "TEST-1"
    assert rules[0].antecedent[0].field == "process_efficiency"

def test_rule_stats():
    # Δοκιμή της συνάρτησης στατιστικών
    rules = [Rule(id="1", name="A", antecedent=[], consequent="C", provenance="P")]
    stats = rule_stats(rules)
    assert stats["total_rules"] == 1
