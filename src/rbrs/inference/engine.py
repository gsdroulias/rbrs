from typing import Any

from pydantic import BaseModel

from rbrs.profile.models import SMEProfile
from rbrs.rules.models import Condition, Rule


class TraceRecord(BaseModel):
    rule_id: str
    fired_at_cycle: int
    action_triggered: str

class InferenceEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = rules
        self.memory: dict[str, Any] = {}
        self.trace: list[TraceRecord] = []
        self.fired_rules: set[str] = set()

    def load_profile(self, profile: SMEProfile) -> None:
        self.memory = profile.model_dump()
        # Υποστήριξη για nested πεδία όπως scope2.tco2e
        if profile.scope2:
            self.memory["scope2.tco2e"] = profile.scope2.tco2e

    def evaluate_condition(self, cond: Condition) -> bool:
        val = self.memory.get(cond.field)
        if cond.op == "==": return val == cond.value
        if cond.op == "!=": return val != cond.value
        if cond.op == ">": return val is not None and val > cond.value
        if cond.op == "<": return val is not None and val < cond.value
        if cond.op == "in": return val in cond.value if cond.value else False
        return False

    def is_eligible(self, rule: Rule, profile: SMEProfile) -> bool:
        if rule.id in self.fired_rules:
            return False
        if rule.maturity_gate and profile.maturity_level < rule.maturity_gate:
            return False
        for cond in rule.antecedent:
            if not self.evaluate_condition(cond):
                return False
        return True

    def run(self, profile: SMEProfile, cycle_cap: int = 10) -> list[str]:
        self.load_profile(profile)
        recommendations = []
        
        for cycle in range(cycle_cap):
            eligible = [r for r in self.rules if self.is_eligible(r, profile)]
            if not eligible:
                break  # Δεν υπάρχουν άλλοι κανόνες που να ταιριάζουν
            
            # Conflict resolution: Επιλογή του κανόνα με τις περισσότερες συνθήκες
            eligible.sort(key=lambda r: len(r.antecedent), reverse=True)
            fired_rule = eligible[0]
            
            self.fired_rules.add(fired_rule.id)
            self.trace.append(TraceRecord(
                rule_id=fired_rule.id, 
                fired_at_cycle=cycle, 
                action_triggered=fired_rule.consequent
            ))
            
            if fired_rule.consequent.startswith("FACT_"):
                self.memory[fired_rule.consequent] = True
            else:
                recommendations.append(fired_rule.consequent)
                
        return recommendations

def chain_report(rules: list[Rule]) -> bool:
    """Ελέγχει αν το rulebase κάνει πραγματικό chaining."""
    derived_facts = {r.consequent for r in rules if r.consequent.startswith("FACT_")}
    for r in rules:
        for cond in r.antecedent:
            if cond.field in derived_facts:
                return True
    return False
