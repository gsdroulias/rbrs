from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class Condition(BaseModel):
    field: str
    op: str
    value: Any

class Rule(BaseModel):
    id: str
    name: str
    antecedent: list[Condition]
    maturity_gate: int | None = None
    capital_gate: str | None = None
    consequent: str
    provenance: str

def load_rules(rules_dir: str | Path) -> list[Rule]:
    """Loads all YAML rule files from a directory and parses them."""
    path = Path(rules_dir)
    rules = []
    for yaml_file in path.glob("*.yaml"):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data:
                for item in data:
                    rules.append(Rule(**item))
    return rules

def rule_stats(rules: list[Rule]) -> dict[str, int]:
    return {"total_rules": len(rules)}
