"""Experiments run end to end on a copy of the repository data."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from rbrs.experiments.e4 import run_e4
from rbrs.experiments.e5 import breakpoints, run_e5, sweep
from rbrs.experiments.e6 import run_e6
from rbrs.experiments.e7 import run_e7
from rbrs.experiments.e8 import run_e8
from rbrs.experiments.e9 import run_e9
from rbrs.experiments.e10 import run_e10
from rbrs.experiments.e11 import run_e11
from rbrs.experiments.e12 import run_e12, run_e13

AC01 = {
    "M1": (Fraction("0.5"), Fraction(1), Fraction(1)),
    "M2": (Fraction("0.75"), Fraction("0.75"), Fraction("0.5")),
    "M3": (Fraction("0.5"), Fraction("0.75"), Fraction(1)),
    "M4": (Fraction(1), Fraction("0.25"), Fraction("0.25")),
    "M5": (Fraction("0.75"), Fraction("0.5"), Fraction("0.5")),
}


def manifest(exp: str) -> dict:  # type: ignore[type-arg]
    return json.loads(Path(f"results/{exp}/manifest.json").read_text(encoding="utf-8"))


def test_ac01_exact() -> None:
    res = sweep(AC01, (3, 2), ["M1", "M2", "M3", "M4", "M5"])
    assert res["published_interval"] == [Fraction(1, 2), Fraction(6, 11)]  # [0.500, 0.545]
    assert res["published_interval_closed"] == {"lower_closed": True, "upper_closed": False}
    assert any(t["w_i"] == Fraction(1, 2) and t["ranks"] == [4, 5] for t in res["ties"])
    assert res["top_from"]["M4"] == Fraction(8, 13)  # 0.615
    assert res["top_from"]["M2"] == Fraction(7, 12)  # M2 leads on [0.583, 0.615) before solar PV
    assert Fraction(8, 13) in breakpoints(AC01, (3, 2))


@pytest.mark.usefixtures("repo_copy")
def test_e5_runs_and_passes_ac01() -> None:
    summary = run_e5()
    assert summary["ac01_all_pass"] is True
    m = manifest("E5")
    assert m["status"] == "COMPLETED" and m["seed"] == 42 and m["config_hash"]
    assert m["publishable"] is False  # not a git checkout -> cleanliness unknown


@pytest.mark.usefixtures("repo_copy")
def test_decision_layer_results_are_byte_identical_on_rerun() -> None:  # AC-09
    def snapshot() -> dict[str, bytes]:
        return {
            str(p): p.read_bytes()
            for p in sorted(Path("results").rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        }

    for fn in (run_e4, run_e5, run_e7, run_e11):
        fn()
    first = snapshot()
    for fn in (run_e4, run_e5, run_e7, run_e11):
        fn()
    assert snapshot() == first


@pytest.mark.usefixtures("repo_copy")
def test_honest_statuses_on_repository_data() -> None:
    run_e4()
    assert manifest("E4")["status"] == "BLOCKED"  # no sourced I/F/C yet
    run_e6()
    assert manifest("E6")["status"] == "BLOCKED"  # AC-05 needs the case firm and factors
    run_e7()
    assert manifest("E7")["summary"]["active"]["chaining_occurs"] is False
    run_e8()
    run_e10()
    assert manifest("E10")["status"] == "COMPLETED"
    run_e11()
    assert manifest("E11")["summary"]["stratified"] == 27
    for fn, exp in ((run_e9, "E9"), (run_e12, "E12"), (run_e13, "E13")):
        fn()
        assert manifest(exp)["status"] == "NOT_RUN"


@pytest.mark.usefixtures("repo_copy")
def test_e12_e13_with_expert_data() -> None:
    from tests.conftest import FIXTURE_FACTORS, FIXTURE_INTERVENTIONS, FIXTURE_RULES

    # Replace the knowledge base with the fixture one so the case ranks INT-A > INT-B > INT-C.
    for p in Path("data/rules").glob("*.yaml"):
        p.unlink()
    Path("data/rules/test.yaml").write_text(FIXTURE_RULES, encoding="utf-8")
    Path("data/interventions.yaml").write_text(FIXTURE_INTERVENTIONS, encoding="utf-8")
    for p in Path("data/factors").glob("*.yaml"):
        p.unlink()
    Path("data/factors/f.yaml").write_text(FIXTURE_FACTORS, encoding="utf-8")
    Path("data/cases/case_T.yaml").write_text(
        """
sector: Manufacturing
employees_fte: 40
turnover_meur: 5.0
scope1: {tco2e: 100.0, assessed: true}
scope2: {tco2e: 100.0, assessed: true}
scope3: {tco2e: null, assessed: false}
energy_carriers: [electricity, natural_gas]
electricity_supply: grid_mixed
thermal_fuel: natural_gas
residues: []
certifications: []
capital_availability: moderate
maturity_level: 2
logistics_mode: diesel_truck
route_distance_km: 100.0
material_type: Steel
process_efficiency: medium
""",
        encoding="utf-8",
    )
    Path("data/expert").mkdir(exist_ok=True)
    rows = ["expert_id,case_id,intervention_id,rank,impact,feasibility,cost_effectiveness"]
    for e, order in (("E1", "ABC"), ("E2", "ABC"), ("E3", "ACB")):
        rows += [f"{e},case_T,INT-{x},{r + 1},0.75,0.75,0.75" for r, x in enumerate(order)]
    Path("data/expert/e12_rankings.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    res = run_e12(permutations=200)["case_T"]
    assert res["system_ranking"] == ["INT-A", "INT-B", "INT-C"]
    assert res["expert_consensus"] == ["INT-A", "INT-B", "INT-C"]
    assert res["tau_b_system_vs_consensus"] == pytest.approx(1.0)
    assert res["top3_overlap_system_vs_consensus"] == pytest.approx(1.0)
    assert res["tau_b_system_vs_each_expert"]["E3"] == pytest.approx(1 / 3)

    Path("data/expert/e13_labels.csv").write_text(
        "item_id,rater,label\n1,system,accept\n2,system,reject\n3,system,accept\n4,system,reject\n"
        "1,E1,accept\n2,E1,reject\n3,E1,reject\n4,E1,reject\n",
        encoding="utf-8",
    )
    out = run_e13()
    assert out["pairs"][0]["cohen_kappa"] == pytest.approx(0.5)


def _rec(doc: str, run: int, emp: str, emp_conf: float, sector_status: str = "EXTRACTED") -> str:
    from rbrs.profile import ExtractedField, ExtractionRecord, Provenance

    fields = [
        ExtractedField(
            field="employees_fte",
            value=emp,
            status="EXTRACTED",
            confidence=emp_conf,
            provenance=Provenance(page=1, quote=f"{emp} employees"),
            verified_in_source=True,
        ),
        ExtractedField(field="turnover_meur", status="ABSTAINED", confidence=0.1),
    ]
    if sector_status == "EXTRACTED":
        fields.append(
            ExtractedField(
                field="sector",
                value="Manufacturing",
                status="EXTRACTED",
                confidence=0.8,
                provenance=Provenance(page=1, quote="manufacturer"),
                verified_in_source=True,
            )
        )
    rec = ExtractionRecord(
        document_id=doc,
        method="llm",
        model_id="test-model-001",
        prompt_version="extraction_v2",
        fields=fields,
        usage={"prompt": 100, "output": 10},
    )
    return rec.model_dump_json()


@pytest.mark.usefixtures("repo_copy")
def test_e9_metrics_with_split_and_runs() -> None:
    gold = Path("data/gold")
    gold.mkdir(exist_ok=True)
    for doc in ("dev1", "dev2", "test1"):
        (gold / f"{doc}.yaml").write_text("employees_fte: 45\nturnover_meur: null\nsector: Manufacturing\n")
    (gold / "splits.yaml").write_text("dev: [dev1, dev2]\ntest: [test1]\n")
    ex = Path("data/extractions")
    for doc, emp, conf in (("dev1", "45", 0.9), ("dev2", "50", 0.4), ("test1", "45", 0.9)):
        (ex / doc).mkdir(parents=True)
        (ex / doc / "run1.json").write_text(_rec(doc, 1, emp, conf))
    (ex / "test1" / "run2.json").write_text(_rec("test1", 2, "45", 0.9, sector_status="ABSTAINED"))
    manual = json.loads(_rec("test1", 0, "45", 1.0))
    manual["method"] = "manual"
    (ex / "test1" / "manual.json").write_text(json.dumps(manual))

    summary = run_e9()
    m = manifest("E9")
    assert m["status"] == "COMPLETED" and m["model_id"] == "test-model-001"
    assert m["token_usage"] == {"prompt": 200, "output": 20}
    # dev: wrong employees value at confidence 0.4 -> threshold 0.8 reaches precision >= 0.95
    assert summary["threshold"] == 0.8
    metrics = json.loads(Path("results/E9/metrics.json").read_text())
    assert metrics["evaluated_documents"] == 1 and metrics["split"] == "test"
    assert metrics["llm_run1"]["precision"] == 1.0 and metrics["llm_run1"]["TN"] == 1
    assert metrics["run_to_run_agreement"]["test1"]["agreement"] == pytest.approx(2 / 3)
    assert metrics["manual"]["precision"] == 1.0
