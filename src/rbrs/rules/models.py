"""YAML rule base: loading and load-time validation (FR-06)."""

from collections import Counter
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rbrs.profile.models import SOURCE_NEEDED, CapitalLevel, SMEProfile

Op = Literal[
    ">",
    ">=",
    "<",
    "<=",
    "==",
    "!=",
    "in",
    "not_in",  # scalar field in / not in a list of values
    "contains",
    "not_contains",  # list field contains / lacks a value
    "any_match",  # list of records: some record matches {attr: value | [values]}
    "is_null",
    "not_null",
]

FACT_PREFIX = "facts."


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    op: Op
    value: Any = None

    @model_validator(mode="after")
    def _value_shape(self) -> "Condition":
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"op '{self.op}' needs a list value")
        if self.op == "any_match" and not isinstance(self.value, dict):
            raise ValueError("op 'any_match' needs a mapping value")
        if self.op in ("is_null", "not_null") and self.value is not None:
            raise ValueError(f"op '{self.op}' takes no value")
        return self


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    antecedent: list[Condition]
    maturity_gate: Literal[1, 2, 3] | None = None
    capital_gate: CapitalLevel | None = None
    consequent: str | None = None  # intervention id
    derive: dict[str, Any] | None = None  # derived facts, read back as facts.<name>
    priority: int = 0
    status: Literal["active", "draft"] = "active"
    provenance: str = Field(min_length=1)
    module: str = ""  # set from the YAML file name at load

    @model_validator(mode="after")
    def _one_consequent(self) -> "Rule":
        if (self.consequent is None) == (self.derive is None):
            raise ValueError(f"{self.id}: give exactly one of 'consequent' or 'derive'")
        return self

    @property
    def is_sourced(self) -> bool:
        return SOURCE_NEEDED not in self.provenance

    @property
    def specificity(self) -> int:
        return len(self.antecedent)


class RuleBaseError(ValueError):
    pass


def _resolve_annotation(path: str) -> Any:
    """Return the type annotation of a dotted SMEProfile path, or raise KeyError."""
    model: Any = SMEProfile
    annotation: Any = None
    for part in path.split("."):
        if model is None or part not in model.model_fields:
            raise KeyError(path)
        annotation = model.model_fields[part].annotation
        model = annotation if isinstance(annotation, type) and issubclass(annotation, BaseModel) else None
    return annotation


def _list_item_model(annotation: Any) -> type[BaseModel] | None:
    if get_origin(annotation) is list:
        (item,) = get_args(annotation)
        if isinstance(item, type) and issubclass(item, BaseModel):
            return item
    return None


def validate_rules(rules: list[Rule]) -> None:
    """Load-time checks: unique ids, known profile fields, derived facts that exist."""
    errors: list[str] = []
    dupes = [rid for rid, n in Counter(r.id for r in rules).items() if n > 1]
    if dupes:
        errors.append(f"duplicate rule ids: {sorted(dupes)}")
    derived = {name for r in rules if r.derive for name in r.derive}
    for r in rules:
        for c in r.antecedent:
            if c.field.startswith(FACT_PREFIX):
                if c.field[len(FACT_PREFIX) :] not in derived:
                    errors.append(f"{r.id}: reads {c.field}, which no rule derives")
                continue
            try:
                annotation = _resolve_annotation(c.field)
            except KeyError:
                errors.append(f"{r.id}: unknown profile field '{c.field}'")
                continue
            if c.op == "any_match":
                item = _list_item_model(annotation)
                if item is None:
                    errors.append(f"{r.id}: 'any_match' needs a list-of-records field, got {c.field}")
                else:
                    unknown = set(c.value) - set(item.model_fields)
                    if unknown:
                        errors.append(f"{r.id}: unknown {item.__name__} attributes {sorted(unknown)}")
    if errors:
        raise RuleBaseError("; ".join(errors))


def load_rules(rules_dir: str | Path, include_drafts: bool = False) -> list[Rule]:
    """Load every *.yaml file in `rules_dir` in sorted file order, then declaration order.

    Draft rules (unsourced or unreviewed) are excluded unless `include_drafts`.
    """
    rules: list[Rule] = []
    for yaml_file in sorted(Path(rules_dir).glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8-sig")) or []
        for item in data:
            rules.append(Rule(**{**item, "module": yaml_file.stem}))
    validate_rules(rules)  # validate the full base so drafts cannot hide errors
    if not include_drafts:
        rules = [r for r in rules if r.status == "active"]
        validate_rules(rules)
    return rules


def fields_read(rules: list[Rule]) -> set[str]:
    """Profile fields read by antecedents and gates (derived facts excluded)."""
    read = {c.field for r in rules for c in r.antecedent if not c.field.startswith(FACT_PREFIX)}
    if any(r.maturity_gate is not None for r in rules):
        read.add("maturity_level")
    if any(r.capital_gate is not None for r in rules):
        read.add("capital_availability")
    return read


def rule_stats(rules: list[Rule]) -> dict[str, Any]:
    """Static statistics of a rule base; activation statistics live in rbrs.inference."""
    return {
        "total_rules": len(rules),
        "by_module": dict(sorted(Counter(r.module for r in rules).items())),
        "by_status": dict(sorted(Counter(r.status for r in rules).items())),
        "derivation_rules": sum(r.derive is not None for r in rules),
        "intervention_rules": sum(r.consequent is not None for r in rules),
        "unsourced_rules": sorted(r.id for r in rules if not r.is_sourced),
        "interventions": sorted({r.consequent for r in rules if r.consequent}),
    }
