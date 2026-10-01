import json

import pytest

from rbrs.constraints import ADDITIONALITY_UNVERIFIED, BURDEN_SHIFTING, SCOPE_SHIFT
from rbrs.pipeline import KnowledgeBase, recommend, report_to_csv, report_to_json, report_to_markdown
from rbrs.profile import Emissions, SMEProfile
from rbrs.scoring import Weights
from tests.conftest import REPO, make_profile


def test_end_to_end_ranking(kb: KnowledgeBase, profile: SMEProfile) -> None:
    rep = recommend(profile, kb, profile_id="p")
    # denominator scope1+scope2 = 200 t
    # INT-A: 30 t -> 15% -> I 0.75; FIS .375+.3+.2 = .875
    # INT-B: 50 t -> 25% -> I 1.00; FIS .5+.075+.05 = .625
    # INT-C: -40 +10 = 30 t net -> 15% -> I 0.75; FIS .375+.15+.1 = .625 (tie with B, B has higher I)
    assert rep.ranking == ["INT-A", "INT-B", "INT-C"]
    by = {s.intervention_id: s for s in rep.interventions}
    assert by["INT-A"].fis == pytest.approx(0.875) and by["INT-A"].decided_by == "score"
    assert by["INT-B"].fis == by["INT-C"].fis == pytest.approx(0.625)
    assert by["INT-B"].decided_by == "tie_break:impact"
    assert SCOPE_SHIFT in by["INT-C"].flags
    assert by["INT-GREEN"].status == "UNQUANTIFIED" and ADDITIONALITY_UNVERIFIED in by["INT-GREEN"].flags
    assert rep.chained and rep.derived_facts == {"fossil_thermal": True}


def test_scope_relative_mode(kb: KnowledgeBase, profile: SMEProfile) -> None:
    rep = recommend(profile, kb, norm="scope_relative")
    by = {s.intervention_id: s for s in rep.interventions}
    assert by["INT-A"].impact_share == pytest.approx(0.30)
    assert by["INT-C"].impact_share == pytest.approx(0.30)  # net 30 t over scope 1 (100 t)


def test_burden_shifting_sets_impact_to_zero(kb: KnowledgeBase, wood_profile: SMEProfile) -> None:
    by = {s.intervention_id: s for s in recommend(wood_profile, kb).interventions}
    wood = by["INT-WOOD"]
    assert BURDEN_SHIFTING in wood.flags
    assert wood.impact == 0.0 and wood.status == "RANKED"
    assert wood.fis == pytest.approx(0.3 * 0.75 + 0.2 * 0.75)


def test_unassessed_denominator_gives_unquantified(kb: KnowledgeBase) -> None:
    p = make_profile(scope1=Emissions(tco2e=None, assessed=False))
    by = {s.intervention_id: s for s in recommend(p, kb).interventions}
    assert by["INT-A"].status == "UNQUANTIFIED"
    assert any("total_absolute" in m for m in by["INT-A"].missing)


def test_weights_change_order(kb: KnowledgeBase, profile: SMEProfile) -> None:
    rep = recommend(profile, kb, Weights(w_i=1.0, w_f=0.0, w_c=0.0))
    assert rep.ranking[0] == "INT-B"


def test_pipeline_is_deterministic(kb: KnowledgeBase, profile: SMEProfile) -> None:
    assert report_to_json(recommend(profile, kb)) == report_to_json(recommend(profile, kb))  # NFR-02


def test_output_formats(kb: KnowledgeBase, profile: SMEProfile) -> None:
    rep = recommend(profile, kb, profile_id="p")
    assert json.loads(report_to_json(rep))["profile_id"] == "p"
    csv = report_to_csv([rep]).splitlines()
    assert csv[0].startswith("profile_id,rank,intervention_id") and len(csv) == 1 + len(rep.interventions)
    md = report_to_markdown(rep)
    assert "| 1 | INT-A |" in md and "Unquantified" in md


def test_unknown_consequent_rejected(tmp_path: object) -> None:
    from pathlib import Path

    from tests.conftest import write_kb

    root = write_kb(Path(str(tmp_path)) / "kb")
    (root / "rules" / "extra.yaml").write_text(
        "- {id: Z, name: z, antecedent: [], consequent: INT-NOPE, provenance: p}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="INT-NOPE"):
        KnowledgeBase.load(root)


def test_repository_case_runs() -> None:
    kb = KnowledgeBase.load(REPO / "data")
    import yaml

    p = SMEProfile(**yaml.safe_load((REPO / "data" / "cases" / "case_A.yaml").read_text(encoding="utf-8")))
    rep = recommend(p, kb)
    assert {s.intervention_id for s in rep.interventions} == {"INT-LED-EFF", "INT-ROUTE-OPT", "INT-SOLAR-PV"}
