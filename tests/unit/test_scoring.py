import pytest
from pydantic import ValidationError

from rbrs.scoring import Candidate, SAWScorer, Weights, band_impact


def test_saw_scoring() -> None:
    scorer = SAWScorer(w_i=0.50, w_f=0.30, w_c=0.20)
    c = Candidate(id="A", impact=1.0, feasibility=0.5, cost_effectiveness=0.5)
    assert scorer.score(c) == 0.75


def test_tie_break_ranking() -> None:
    scorer = SAWScorer(w_i=0.5, w_f=0.5, w_c=0.0)
    c1 = Candidate(id="1", impact=1.0, feasibility=0.0, cost_effectiveness=0.0)
    c2 = Candidate(id="2", impact=0.0, feasibility=1.0, cost_effectiveness=0.0)
    ranked = scorer.rank([c2, c1])
    assert [r.candidate.id for r in ranked] == ["1", "2"]
    assert ranked[0].decided_by == "tie_break:impact"


def test_decided_by_records_score_or_tie_break() -> None:
    cands = [
        Candidate(id="A", impact=0.5, feasibility=1.0, cost_effectiveness=1.0),
        Candidate(id="D", impact=1.0, feasibility=0.25, cost_effectiveness=0.25),
        Candidate(id="E", impact=0.75, feasibility=0.5, cost_effectiveness=0.5),
    ]
    ranked = SAWScorer().rank(cands)  # D and E tie at 0.625 under default weights
    assert [(r.candidate.id, r.rank, r.decided_by) for r in ranked] == [
        ("A", 1, "score"),
        ("D", 2, "tie_break:impact"),
        ("E", 3, "tie_break:impact"),
    ]
    assert SAWScorer().rank(cands[:1])[0].decided_by == "single"


def test_identical_candidates_fall_back_to_id() -> None:
    a = Candidate(id="B", impact=0.5, feasibility=0.5, cost_effectiveness=0.5)
    ranked = SAWScorer().rank([a, a.model_copy(update={"id": "A"})])
    assert [r.candidate.id for r in ranked] == ["A", "B"]
    assert ranked[0].decided_by == "tie_break:id"


@pytest.mark.parametrize(
    ("share", "level"),
    [
        (-0.1, 0.0),
        (0.0, 0.0),
        (0.01, 0.25),
        (0.0499, 0.25),
        (0.05, 0.5),
        (0.10, 0.5),
        (0.1001, 0.75),
        (0.20, 0.75),
        (0.2001, 1.0),
        (0.9, 1.0),
    ],
)
def test_impact_bands(share: float, level: float) -> None:
    assert band_impact(share) == level


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        Weights(w_i=0.5, w_f=0.5, w_c=0.5)
    with pytest.raises(ValidationError):
        SAWScorer(0.9, 0.3, -0.2)
    assert Weights.parse("default") == Weights()
    assert Weights.parse("0.6,0.24,0.16").w_i == 0.6
    with pytest.raises(ValueError):
        Weights.parse("0.5,0.5")
