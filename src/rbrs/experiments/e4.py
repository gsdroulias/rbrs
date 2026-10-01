"""E4: decision-layer runs for the case firms (FR-13)."""

from typing import Any

from rbrs.experiments.common import load_cases, start_run, write_text
from rbrs.pipeline import KnowledgeBase, recommend, report_to_csv, report_to_json, report_to_markdown
from rbrs.scoring import NormMode, Weights


def run_e4(
    cases_dir: str = "data/cases",
    weights: str = "default",
    norm: NormMode = "total_absolute",
    include_drafts: bool = False,
    allow_dirty: bool = True,
) -> dict[str, Any]:
    w = Weights.parse(weights)
    run = start_run(
        "E4",
        params={"cases_dir": cases_dir, "weights": w.model_dump(), "norm": norm, "include_drafts": include_drafts},
        allow_dirty=allow_dirty,
    )
    kb = KnowledgeBase.load(include_drafts=include_drafts)
    reports = []
    for case_id, profile in load_cases(cases_dir).items():
        rep = recommend(profile, kb, w, norm, profile_id=case_id)
        reports.append(rep)
        write_text(run.path(f"{case_id}.json"), report_to_json(rep))
        write_text(run.path(f"{case_id}.md"), report_to_markdown(rep))
    write_text(run.path("recommendations.csv"), report_to_csv(reports))
    summary = {
        r.profile_id: {
            "ranking": r.ranking,
            "unquantified": [s.intervention_id for s in r.interventions if s.status == "UNQUANTIFIED"],
        }
        for r in reports
    }
    ranked_any = any(r.ranking for r in reports)
    notes = (
        []
        if ranked_any
        else ["No candidate could be ranked: interventions lack sourced I/F/C data (see `rbrs audit`)."]
    )
    run.finish("COMPLETED" if ranked_any else "BLOCKED", summary, notes=notes)
    return summary
