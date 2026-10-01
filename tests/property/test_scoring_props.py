from hypothesis import given
from hypothesis import strategies as st

from rbrs.scoring import Candidate, SAWScorer

I_LEVELS = st.sampled_from([0.0, 0.25, 0.50, 0.75, 1.00])
FC_LEVELS = st.sampled_from([0.25, 0.50, 0.75, 1.00])
candidates = st.lists(
    st.builds(
        Candidate,
        id=st.text(min_size=1, max_size=8),
        impact=I_LEVELS,
        feasibility=FC_LEVELS,
        cost_effectiveness=FC_LEVELS,
    ),
    unique_by=lambda x: x.id,
    max_size=12,
)


@given(I_LEVELS, FC_LEVELS, FC_LEVELS)
def test_fis_is_multiple_of_025(i: float, f: float, c: float) -> None:
    # AC-02: under default weights every FIS is a multiple of 0.025
    fis = SAWScorer(w_i=0.50, w_f=0.30, w_c=0.20).score(
        Candidate(id="X", impact=i, feasibility=f, cost_effectiveness=c)
    )
    assert abs(fis / 0.025 - round(fis / 0.025)) < 1e-9
    assert 0.0 <= fis <= 1.0


@given(
    candidates,
    st.builds(Candidate, id=st.just("NEW"), impact=I_LEVELS, feasibility=FC_LEVELS, cost_effectiveness=FC_LEVELS),
)
def test_adding_a_candidate_never_changes_other_scores(cands: list[Candidate], extra: Candidate) -> None:
    # AC-03: absolute normalisation, so scores are independent of the candidate set
    cands = [c for c in cands if c.id != "NEW"]
    scorer = SAWScorer()
    before = {s.candidate.id: s.fis for s in scorer.rank(cands)}
    after = {s.candidate.id: s.fis for s in scorer.rank([*cands, extra])}
    assert all(after[k] == v for k, v in before.items())


@given(candidates, st.randoms())
def test_ranking_invariant_to_order(cands: list[Candidate], rnd: object) -> None:
    # AC-04
    shuffled = list(cands)
    rnd.shuffle(shuffled)  # type: ignore[attr-defined]
    scorer = SAWScorer()
    assert [r.candidate.id for r in scorer.rank(cands)] == [r.candidate.id for r in scorer.rank(shuffled)]


@given(
    st.lists(
        st.builds(
            Candidate,
            id=st.text(min_size=1),
            impact=st.floats(0, 1),
            feasibility=st.floats(0, 1),
            cost_effectiveness=st.floats(0, 1),
        ),
        unique_by=lambda x: x.id,
    )
)
def test_ranking_invariant_to_order_continuous(cands: list[Candidate]) -> None:
    scorer = SAWScorer()
    assert [r.candidate.id for r in scorer.rank(cands)] == [r.candidate.id for r in scorer.rank(cands[::-1])]
