"""E8: missing-data handling. Each nullable fact is removed in turn (a scope set
to unassessed, an optional value set to null) and the decision is compared with
the complete profile. The decision layer must never substitute a value: missing
inputs have to surface as lost or UNQUANTIFIED candidates, not as changed scores."""

from collections.abc import Callable
from typing import Any

from rbrs.experiments.common import load_cases, start_run, write_csv
from rbrs.experiments.compare import compare_reports
from rbrs.pipeline import KnowledgeBase, recommend
from rbrs.profile.models import Emissions, SMEProfile
from rbrs.synthetic import generate_cohort

Perturb = Callable[[SMEProfile], SMEProfile | None]


def _unassess(scope: str) -> Perturb:
    def f(p: SMEProfile) -> SMEProfile | None:
        if not getattr(p, scope).assessed:
            return None
        return p.model_copy(update={scope: Emissions(tco2e=None, assessed=False)})

    return f


def _null(field: str) -> Perturb:
    def f(p: SMEProfile) -> SMEProfile | None:
        return None if getattr(p, field) is None else p.model_copy(update={field: None})

    return f


def _no_moisture(p: SMEProfile) -> SMEProfile | None:
    if not any(r.moisture_content is not None for r in p.residues):
        return None
    return p.model_copy(update={"residues": [r.model_copy(update={"moisture_content": None}) for r in p.residues]})


PERTURBATIONS: dict[str, Perturb] = {
    "scope1_unassessed": _unassess("scope1"),
    "scope2_unassessed": _unassess("scope2"),
    "scope3_unassessed": _unassess("scope3"),
    "turnover_null": _null("turnover_meur"),
    "route_distance_null": _null("route_distance_km"),
    "thermal_fuel_null": _null("thermal_fuel"),
    "residue_moisture_null": _no_moisture,
}


def run_e8(cases_dir: str = "data/cases", include_drafts: bool = False, allow_dirty: bool = True) -> dict[str, Any]:
    run = start_run("E8", params={"cases_dir": cases_dir, "include_drafts": include_drafts}, allow_dirty=allow_dirty)
    kb = KnowledgeBase.load(include_drafts=include_drafts)
    rows: list[dict[str, Any]] = []
    for pid, profile in list(load_cases(cases_dir).items()) + generate_cohort():
        base = recommend(profile, kb, profile_id=pid)
        for name, perturb in PERTURBATIONS.items():
            changed = perturb(profile)
            if changed is None:
                continue  # fact already missing
            c = compare_reports(base, recommend(changed, kb, profile_id=pid))
            rows.append(
                {
                    "profile_id": pid,
                    "perturbation": name,
                    **{k: v if not isinstance(v, list) else "|".join(v) for k, v in c.items()},
                }
            )
    write_csv(run.path("missing_data.csv"), rows)
    summary: dict[str, Any] = {}
    for name in PERTURBATIONS:
        sub = [r for r in rows if r["perturbation"] == name]
        if sub:
            summary[name] = {
                "profiles": len(sub),
                "candidate_set_changed": sum(not r["candidates_same"] for r in sub),
                "ranked_became_unquantified": sum(bool(r["ranked_to_unquantified"]) for r in sub),
                "top1_changed": sum(r["top1_same"] is False for r in sub),
            }
    run.finish("COMPLETED", summary)
    return summary
