"""E6: constraint layer (FR-09) - energy substitution, biogenic CO2, scope
shifting and additionality, computed from cited factors only (AC-05)."""

from typing import Any

from rbrs.constraints import evaluate_constraints
from rbrs.experiments.common import load_cases, start_run, write_csv, write_json
from rbrs.pipeline import KnowledgeBase, recommend
from rbrs.synthetic import generate_cohort

AC05_INTERVENTION = "INT-RESIDUE-MATERIAL"


def run_e6(cases_dir: str = "data/cases", include_drafts: bool = False, allow_dirty: bool = True) -> dict[str, Any]:
    run = start_run("E6", params={"cases_dir": cases_dir, "include_drafts": include_drafts}, allow_dirty=allow_dirty)
    kb = KnowledgeBase.load(include_drafts=include_drafts)
    cases = load_cases(cases_dir)

    # AC-05: diverting wood residues from combustion, evaluated directly for every
    # case with such a stream, whether or not the rule's gates would fire.
    iv = kb.interventions[AC05_INTERVENTION]
    rd = iv.residue_diversion
    assert rd is not None
    ac05: dict[str, Any] = {}
    for case_id, profile in cases.items():
        if not any(s.material == rd.material and s.disposition == rd.from_disposition for s in profile.residues):
            continue
        cr = evaluate_constraints(iv, profile, kb.factors)
        ac05[case_id] = {
            "status": "COMPUTED" if cr.net_delta_t is not None else "BLOCKED",
            "net_delta_t": cr.net_delta_t,
            "changes_t": cr.changes_t,
            "biogenic_co2_t_separate_line": cr.biogenic_co2_t,
            "flags": cr.flags,
            "missing": cr.missing,
            "details": cr.details,
        }
    write_json(run.path("ac05_energy_substitution.json"), ac05)

    # Constraint outcomes for every recommended candidate, cases and synthetic cohort.
    rows: list[dict[str, Any]] = []
    profiles = list(cases.items()) + generate_cohort()
    for pid, profile in profiles:
        for s in recommend(profile, kb, profile_id=pid).interventions:
            rows.append(
                {
                    "profile_id": pid,
                    "intervention_id": s.intervention_id,
                    "net_delta_t": s.net_delta_t,
                    "flags": "|".join(s.flags),
                    "missing": "|".join(s.missing),
                }
            )
    write_csv(
        run.path("constraint_outcomes.csv"),
        rows,
        columns=["profile_id", "intervention_id", "net_delta_t", "flags", "missing"],
    )
    flag_counts: dict[str, int] = {}
    for r in rows:
        for f in filter(None, r["flags"].split("|")):
            flag_counts[f] = flag_counts.get(f, 0) + 1

    computed = [k for k, v in ac05.items() if v["status"] == "COMPUTED"]
    notes = []
    if not ac05:
        notes.append(
            "AC-05 not evaluated: no case has a wood stream burned for energy. "
            "Add the manuscript case firm to data/cases/."
        )
    elif not computed:
        missing = sorted({m for v in ac05.values() for m in v["missing"]})
        notes.append(f"AC-05 blocked by missing inputs: {missing}")
    summary = {
        "ac05": {
            k: {"status": v["status"], "net_delta_t": v["net_delta_t"], "flags": v["flags"]} for k, v in ac05.items()
        },
        "flag_counts": dict(sorted(flag_counts.items())),
        "candidates_evaluated": len(rows),
    }
    run.finish("COMPLETED" if computed else "BLOCKED", summary, notes=notes)
    return summary
