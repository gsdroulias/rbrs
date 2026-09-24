import math
from hypothesis import given, strategies as st
from rbrs.scoring.saw import Candidate, SAWScorer

@given(
    st.sampled_from([0.0, 0.25, 0.50, 0.75, 1.00]),
    st.sampled_from([0.25, 0.50, 0.75, 1.00]),
    st.sampled_from([0.25, 0.50, 0.75, 1.00])
)
def test_fis_is_multiple_of_025(i, f, c):
    # AC-02: Το FIS πρέπει να είναι πολλαπλάσιο του 0.025 υπό τα default weights
    scorer = SAWScorer(w_i=0.50, w_f=0.30, w_c=0.20)
    cand = Candidate(id="X", impact=i, feasibility=f, cost_effectiveness=c)
    fis = scorer.score(cand)
    
    remainder = round(fis % 0.025, 4)
    assert remainder == 0.0 or remainder == 0.0250
    assert 0.0 <= fis <= 1.0

@given(st.lists(
    st.builds(Candidate, 
              id=st.text(min_size=1), 
              impact=st.floats(0, 1), 
              feasibility=st.floats(0, 1), 
              cost_effectiveness=st.floats(0, 1)),
    unique_by=lambda x: x.id
))
def test_ranking_invariant_to_order(candidates):
    # AC-04: Η τελική κατάταξη πρέπει να είναι ανεξάρτητη της αρχικής σειράς των δεδομένων
    scorer = SAWScorer()
    ranked1 = scorer.rank(candidates)
    ranked2 = scorer.rank(list(reversed(candidates)))
    assert [r.candidate.id for r in ranked1] == [r.candidate.id for r in ranked2]
