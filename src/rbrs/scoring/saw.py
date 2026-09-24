from pydantic import BaseModel

class Candidate(BaseModel):
    id: str
    impact: float
    feasibility: float
    cost_effectiveness: float

class ScoredCandidate(BaseModel):
    candidate: Candidate
    fis: float

class SAWScorer:
    def __init__(self, w_i: float = 0.50, w_f: float = 0.30, w_c: float = 0.20):
        self.w_i = w_i
        self.w_f = w_f
        self.w_c = w_c

    def score(self, c: Candidate) -> float:
        # Υπολογισμός Final Intervention Score (FIS)
        return round((self.w_i * c.impact) + (self.w_f * c.feasibility) + (self.w_c * c.cost_effectiveness), 4)

    def rank(self, candidates: list[Candidate]) -> list[ScoredCandidate]:
        scored = [ScoredCandidate(candidate=c, fis=self.score(c)) for c in candidates]
        
        # Tie-break: 
        # 1) Υψηλότερο FIS (descending)
        # 2) Υψηλότερο Impact (descending)
        # 3) Υψηλότερο Feasibility (descending)
        # 4) Υψηλότερο Cost-Effectiveness (descending)
        # 5) Αλφαβητικά βάσει ID (ascending) -> Σπάει την τελική ισοβαθμία (Absolute Determinism)
        
        scored.sort(
            key=lambda s: (s.fis, s.candidate.impact, s.candidate.feasibility, s.candidate.cost_effectiveness, s.candidate.id),
            reverse=True
        )
        
        # Επειδή το reverse=True αντέστρεψε και την αλφαβητική σειρά του ID,
        # πρέπει να ξαναγράψουμε το sort function ώστε το ID να ταξινομείται κανονικά (A->Z).
        # Ο πιο καθαρός τρόπος στην Python:
        scored.sort(
            key=lambda s: (-s.fis, -s.candidate.impact, -s.candidate.feasibility, -s.candidate.cost_effectiveness, s.candidate.id)
        )
        return scored
