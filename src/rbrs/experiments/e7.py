"""E7: does forward chaining occur, and does it matter? (FR-07)

Runs the rule base over the case firms and the synthetic cohort, reports rule
activation, dead rules and chaining, and compares full chaining against a
single-pass ablation in which derived facts are never visible.
"""

from typing import Any

from rbrs.experiments.common import load_cases, start_run, write_csv, write_json
from rbrs.inference import InferenceEngine, activation_stats
from rbrs.pipeline import KnowledgeBase
from rbrs.synthetic import generate_cohort


def _analyse(include_drafts: bool, profiles: list[tuple[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    kb = KnowledgeBase.load(include_drafts=include_drafts)
    stats = activation_stats(kb.rules, [p for _, p in profiles])
    full, single = InferenceEngine(kb.rules), InferenceEngine(kb.rules, chaining=False)
    rows, differ = [], 0
    for pid, p in profiles:
        a, b = set(full.run(p).intervention_ids), set(single.run(p).intervention_ids)
        differ += a != b
        rows.append(
            {
                "profile_id": pid,
                "rule_base": "with_drafts" if include_drafts else "active",
                "candidates_chaining": "|".join(sorted(a)),
                "candidates_single_pass": "|".join(sorted(b)),
                "only_via_chaining": "|".join(sorted(a - b)),
            }
        )
    stats["ablation"] = {"profiles_where_chaining_changes_candidates": differ}
    stats["rules"] = len(kb.rules)
    return stats, rows


def run_e7(cases_dir: str = "data/cases", allow_dirty: bool = True) -> dict[str, Any]:
    run = start_run("E7", params={"cases_dir": cases_dir}, allow_dirty=allow_dirty)
    profiles = list(load_cases(cases_dir).items()) + generate_cohort()
    out, rows = {}, []
    for drafts in (False, True):
        stats, r = _analyse(drafts, profiles)
        out["with_drafts" if drafts else "active"] = stats
        rows += r
    write_json(run.path("chaining.json"), out)
    write_csv(run.path("chaining_ablation.csv"), rows)
    write_csv(
        run.path("rule_activation.csv"),
        [
            {"rule_base": base, "rule_id": rid, "firings": n}
            for base, stats in out.items()
            for rid, n in stats["activation_frequency"].items()
        ],
    )
    summary = {
        base: {
            "rules": s["rules"],
            "chaining_occurs": s["chaining"]["chaining_occurs"],
            "profiles_with_chaining": s["chaining"]["profiles_with_chaining"],
            "dead_rules": s["dead_rules"],
            "profiles_where_chaining_changes_candidates": s["ablation"]["profiles_where_chaining_changes_candidates"],
        }
        for base, s in out.items()
    }
    notes = []
    if not out["active"]["chaining"]["chaining_occurs"]:
        notes.append(
            "With the active rule base no derived fact enables another rule: "
            "the paper must not claim forward chaining for it (REQUIREMENTS, constraints)."
        )
    run.finish("COMPLETED", summary, notes=notes)
    return summary
