"""E11: synthetic cohort (FR-15, FR-16): rule coverage and pipeline scalability.

This shows which rules and interventions the cohort exercises and that the
pipeline runs at scale. It says nothing about whether recommendations are right.
"""

import json
import time
from collections import Counter
from typing import Any

from rbrs.experiments.common import start_run, write_csv, write_json, write_text
from rbrs.inference import activation_stats
from rbrs.pipeline import KnowledgeBase, recommend, report_rows
from rbrs.profile import profile_coverage
from rbrs.rules import fields_read
from rbrs.synthetic import generate_cohort, load_config


def run_e11(include_drafts: bool = False, allow_dirty: bool = True) -> dict[str, Any]:
    cfg = load_config()
    run = start_run(
        "E11",
        seed=cfg["seed"],
        params={"synthetic_config": "data/experiments/synthetic.yaml", "include_drafts": include_drafts},
        allow_dirty=allow_dirty,
    )
    kb = KnowledgeBase.load(include_drafts=include_drafts)
    cohort = generate_cohort(cfg)
    write_text(
        run.path("profiles.jsonl"),
        "".join(json.dumps({"id": pid, **p.model_dump(mode="json")}, sort_keys=True) + "\n" for pid, p in cohort),
    )

    t0 = time.perf_counter()
    reports = [recommend(p, kb, profile_id=pid) for pid, p in cohort]
    elapsed = time.perf_counter() - t0

    rows = [r for rep in reports for r in report_rows(rep)]
    write_csv(run.path("cohort_recommendations.csv"), rows, columns=list(rows[0]) if rows else ["profile_id"])
    freq = Counter(s.intervention_id for rep in reports for s in rep.interventions)
    stats = activation_stats(kb.rules, [p for _, p in cohort])
    unused = profile_coverage(fields_read(kb.rules))
    write_json(
        run.path("coverage.json"),
        {
            "intervention_frequency": dict(sorted(freq.items())),
            "rule_activation": stats["activation_frequency"],
            "dead_rules": stats["dead_rules"],
            "profile_attributes_unused": unused,
            "profiles_without_candidates": [rep.profile_id for rep in reports if not rep.interventions],
        },
    )
    summary = {
        "profiles": len(cohort),
        "stratified": sum(pid.startswith("SYN-S") for pid, _ in cohort),
        "intervention_frequency": dict(sorted(freq.items())),
        "dead_rules": stats["dead_rules"],
        "profile_attributes_unused": unused,
        "profiles_with_ranked_candidates": sum(bool(rep.ranking) for rep in reports),
        "runtime_seconds_not_reproducible": round(elapsed, 3),
    }
    run.finish("COMPLETED", summary)
    return summary
