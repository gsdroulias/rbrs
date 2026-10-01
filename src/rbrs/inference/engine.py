"""Forward-chaining inference with refraction and a deterministic trace (FR-07, FR-08).

Algorithm (DESIGN.md, "Inference"):
  working memory = profile facts + derived facts (initially empty)
  repeat until no rule is eligible or the cycle cap is reached:
      eligible = rules not yet fired whose gates pass and whose antecedent holds
      conflict resolution: higher specificity (more conditions), then higher
          priority, then earlier declaration
      fire the first; assert its derived facts or record its intervention
Each rule fires at most once (refraction), so the loop ends after at most
len(rules) cycles; the cap guards against future changes to that policy.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from rbrs.profile.models import CAPITAL_ORDER, SMEProfile
from rbrs.rules.models import FACT_PREFIX, Condition, Rule

_MISSING = object()


class RuleEvaluationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TraceRecord:
    step: int  # firing order; 0 for rules that never fired
    rule_id: str
    status: Literal["fired", "not_fired"]
    reason: str
    facts_read: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateMatch:
    intervention_id: str
    rule_ids: tuple[str, ...]  # every rule that recommended it, in firing order
    via_derived_fact: bool  # True if a supporting rule read a derived fact


@dataclass
class InferenceResult:
    candidates: list[CandidateMatch]
    derived_facts: dict[str, Any]
    trace: list[TraceRecord]
    cycles: int
    terminated: bool
    chained: bool = field(default=False)  # a derived fact enabled at least one firing

    @property
    def intervention_ids(self) -> list[str]:
        return [c.intervention_id for c in self.candidates]


def chain_report(results: list[InferenceResult]) -> dict[str, Any]:
    """Summarise whether rule chaining actually occurs (FR-07)."""
    chained_rules: Counter[str] = Counter()
    for res in results:
        for t in res.trace:
            if t.status == "fired" and any(f.startswith(FACT_PREFIX) for f in t.facts_read):
                chained_rules[t.rule_id] += 1
    return {
        "profiles": len(results),
        "profiles_with_chaining": sum(r.chained for r in results),
        "chained_rule_firings": dict(sorted(chained_rules.items())),
        "chaining_occurs": bool(chained_rules),
    }


def _resolve(profile: SMEProfile, facts: dict[str, Any], path: str) -> Any:
    if path.startswith(FACT_PREFIX):
        return facts.get(path[len(FACT_PREFIX) :])
    current: Any = profile
    for part in path.split("."):
        if not isinstance(current, BaseModel) or part not in type(current).model_fields:
            return _MISSING
        current = getattr(current, part)
    return current


def _record_matches(record: Any, spec: dict[str, Any]) -> bool:
    for attr, expected in spec.items():
        actual = getattr(record, attr, _MISSING)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def evaluate_condition(cond: Condition, profile: SMEProfile, facts: dict[str, Any]) -> bool:
    val = _resolve(profile, facts, cond.field)
    if val is _MISSING:
        raise RuleEvaluationError(f"unknown field '{cond.field}'")
    op, target = cond.op, cond.value
    if op == "is_null":
        return val is None
    if op == "not_null":
        return val is not None
    if val is None:  # unknown facts never satisfy a comparison
        return False
    try:
        if op == ">":
            return bool(val > target)
        if op == ">=":
            return bool(val >= target)
        if op == "<":
            return bool(val < target)
        if op == "<=":
            return bool(val <= target)
        if op == "==":
            return bool(val == target)
        if op == "!=":
            return bool(val != target)
        if op == "in":
            return val in target
        if op == "not_in":
            return val not in target
        if op == "contains":
            return target in val
        if op == "not_contains":
            return target not in val
        if op == "any_match":
            return any(_record_matches(item, target) for item in val)
    except TypeError as exc:
        raise RuleEvaluationError(f"cannot apply '{op}' to {cond.field}={val!r}: {exc}") from exc
    raise RuleEvaluationError(f"unsupported op '{op}'")


def gate_failure(rule: Rule, profile: SMEProfile) -> str | None:
    if rule.maturity_gate is not None and profile.maturity_level < rule.maturity_gate:
        return f"maturity gate: needs >= {rule.maturity_gate}, profile has {profile.maturity_level}"
    if rule.capital_gate is not None and (
        CAPITAL_ORDER[profile.capital_availability] < CAPITAL_ORDER[rule.capital_gate]
    ):
        return f"capital gate: needs >= {rule.capital_gate}, profile has {profile.capital_availability}"
    return None


class InferenceEngine:
    def __init__(self, rules: list[Rule], max_cycles: int | None = None, chaining: bool = True):
        self.rules = list(rules)
        self.max_cycles = max_cycles if max_cycles is not None else len(self.rules) + 1
        # chaining=False is the single-pass ablation: derived facts are never visible.
        self.chaining = chaining
        self._order = {r.id: i for i, r in enumerate(self.rules)}

    def _first_failed(self, rule: Rule, profile: SMEProfile, facts: dict[str, Any]) -> str | None:
        gate = gate_failure(rule, profile)
        if gate:
            return gate
        for cond in rule.antecedent:
            if not evaluate_condition(cond, profile, facts):
                return f"antecedent: {cond.field} {cond.op} {cond.value!r} is false"
        return None

    def run(self, profile: SMEProfile) -> InferenceResult:
        facts: dict[str, Any] = {}
        visible: dict[str, Any] = facts if self.chaining else {}
        fired: dict[str, TraceRecord] = {}
        matches: dict[str, list[str]] = {}
        via_fact: dict[str, bool] = {}
        cycles = 0
        terminated = True

        while True:
            eligible = [r for r in self.rules if r.id not in fired and self._first_failed(r, profile, visible) is None]
            if not eligible:
                break
            if cycles >= self.max_cycles:
                terminated = False
                break
            cycles += 1
            rule = min(eligible, key=lambda r: (-r.specificity, -r.priority, self._order[r.id]))
            read = tuple(c.field for c in rule.antecedent)
            used_fact = any(f.startswith(FACT_PREFIX) for f in read)
            if rule.derive is not None:
                facts.update(rule.derive)
                reason = "derived " + ", ".join(f"{k}={v!r}" for k, v in rule.derive.items())
            else:
                assert rule.consequent is not None
                matches.setdefault(rule.consequent, []).append(rule.id)
                via_fact[rule.consequent] = via_fact.get(rule.consequent, False) or used_fact
                reason = f"recommends {rule.consequent}"
            fired[rule.id] = TraceRecord(cycles, rule.id, "fired", reason, read)

        trace = sorted(fired.values(), key=lambda t: t.step)
        for r in self.rules:
            if r.id not in fired:
                trace.append(TraceRecord(0, r.id, "not_fired", self._first_failed(r, profile, visible) or "cycle cap"))

        candidates = [CandidateMatch(iid, tuple(rids), via_fact[iid]) for iid, rids in matches.items()]
        chained = any(t.status == "fired" and any(f.startswith(FACT_PREFIX) for f in t.facts_read) for t in trace)
        return InferenceResult(candidates, dict(facts), trace, cycles, terminated, chained)


def activation_stats(rules: list[Rule], profiles: list[SMEProfile]) -> dict[str, Any]:
    """FR-06: how often each rule fires over a set of profiles, and which never fire."""
    engine = InferenceEngine(rules)
    results = [engine.run(p) for p in profiles]
    counts: Counter[str] = Counter(t.rule_id for res in results for t in res.trace if t.status == "fired")
    return {
        "profiles": len(profiles),
        "activation_frequency": {r.id: counts.get(r.id, 0) for r in rules},
        "dead_rules": [r.id for r in rules if counts.get(r.id, 0) == 0],
        "chaining": chain_report(results),
    }
