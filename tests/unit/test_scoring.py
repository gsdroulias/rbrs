from rbrs.scoring.saw import Candidate, SAWScorer

def test_saw_scoring():
    scorer = SAWScorer(w_i=0.50, w_f=0.30, w_c=0.20)
    c = Candidate(id="A", impact=1.0, feasibility=0.5, cost_effectiveness=0.5)
    # (0.50 * 1.0) + (0.30 * 0.5) + (0.20 * 0.5) = 0.50 + 0.15 + 0.10 = 0.75
    assert scorer.score(c) == 0.75

def test_tie_break_ranking():
    scorer = SAWScorer(w_i=0.5, w_f=0.5, w_c=0.0)
    # Ίδιο FIS (0.5), αλλά ο c1 έχει υψηλότερο impact
    c1 = Candidate(id="1", impact=1.0, feasibility=0.0, cost_effectiveness=0.0)
    c2 = Candidate(id="2", impact=0.0, feasibility=1.0, cost_effectiveness=0.0)
    
    ranked = scorer.rank([c1, c2])
    assert ranked[0].candidate.id == "1"
    assert ranked[1].candidate.id == "2"
