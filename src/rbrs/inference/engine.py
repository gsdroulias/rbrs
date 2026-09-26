from typing import Any
from pydantic import BaseModel
from dataclasses import dataclass
import time

from rbrs.profile.models import SMEProfile
from rbrs.rules.models import Rule

@dataclass
class TraceRecord:
    rule_id: str
    timestamp: float
    status: str
    reason: str

def chain_report(traces: list[TraceRecord]) -> str:
    return "\n".join([f"[{t.timestamp}] {t.rule_id}: {t.status} - {t.reason}" for t in traces])

class InferenceEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = rules
        self.traces: list[TraceRecord] = []

    def _get_nested_attr(self, obj: BaseModel, path: str) -> Any:
        current = obj
        for part in path.split('.'):
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def evaluate_condition(self, condition: Any, profile: SMEProfile) -> bool:
        # Pydantic objects use dot notation instead of dictionary brackets
        field_val = self._get_nested_attr(profile, condition.field)
        op = condition.op
        target = condition.value

        if field_val is None:
            return False

        if op == ">": return field_val > target
        if op == "<": return field_val < target
        if op == "==": return field_val == target
        if op == "in": return field_val in target
        if op == "any_has": return target in field_val

        return False

    def run(self, profile: SMEProfile) -> list[str]:
        self.traces = []
        triggered_consequents = []
        
        for rule in self.rules:
            # Check gates
            if rule.maturity_gate and profile.maturity_level < rule.maturity_gate:
                self.traces.append(TraceRecord(rule.id, time.time(), "skipped", "Maturity gate failed"))
                continue
            if rule.capital_gate == "high" and profile.capital_availability != "high":
                self.traces.append(TraceRecord(rule.id, time.time(), "skipped", "Capital gate failed"))
                continue
            if rule.capital_gate == "moderate" and profile.capital_availability == "low":
                self.traces.append(TraceRecord(rule.id, time.time(), "skipped", "Capital gate failed"))
                continue

            # Evaluate antecedent
            all_passed = True
            for cond in rule.antecedent:
                if not self.evaluate_condition(cond, profile):
                    all_passed = False
                    break
            
            if all_passed:
                triggered_consequents.append(rule.consequent)
                self.traces.append(TraceRecord(rule.id, time.time(), "triggered", "All conditions met"))
            else:
                self.traces.append(TraceRecord(rule.id, time.time(), "skipped", "Antecedent failed"))

        return triggered_consequents
