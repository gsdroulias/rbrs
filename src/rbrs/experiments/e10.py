"""E10: Monte Carlo stress test of the decision under multiplicative noise in the
extracted quantities (seeded; see data/experiments/e10.yaml)."""

from pathlib import Path
from typing import Any

import numpy as np
import yaml

from rbrs.experiments.common import load_cases, start_run, write_csv
from rbrs.experiments.compare import compare_reports
from rbrs.pipeline import KnowledgeBase, recommend
from rbrs.profile.models import SMEProfile


def perturb(profile: SMEProfile, fields: list[str], sigma: float, rng: np.random.Generator) -> SMEProfile:
    data = profile.model_dump()
    for f in fields:
        if f == "residues.mass_t":
            for r in data["residues"]:
                r["mass_t"] *= float(np.exp(rng.normal(0.0, sigma)))
            continue
        parts = f.split(".")
        holder = data
        for p in parts[:-1]:
            holder = holder[p]
        draw = float(np.exp(rng.normal(0.0, sigma)))  # always drawn, so streams stay aligned
        if holder[parts[-1]] is not None:
            holder[parts[-1]] *= draw
    return SMEProfile(**data)


def run_e10(
    config: str | Path = "data/experiments/e10.yaml",
    cases_dir: str = "data/cases",
    include_drafts: bool = False,
    allow_dirty: bool = True,
) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    run = start_run(
        "E10",
        seed=cfg["seed"],
        params={**cfg, "cases_dir": cases_dir, "include_drafts": include_drafts},
        allow_dirty=allow_dirty,
    )
    kb = KnowledgeBase.load(include_drafts=include_drafts)
    rows, summary = [], {}
    for case_id, profile in load_cases(cases_dir).items():
        base = recommend(profile, kb, profile_id=case_id)
        for sigma in cfg["sigmas"]:
            rng = np.random.default_rng([cfg["seed"], round(sigma * 1000)])
            comps = [
                compare_reports(base, recommend(perturb(profile, cfg["fields"], sigma, rng), kb))
                for _ in range(cfg["draws"])
            ]
            taus = [c["kendall_tau"] for c in comps if c["kendall_tau"] is not None]
            row = {
                "case_id": case_id,
                "sigma": sigma,
                "draws": len(comps),
                "ranked_in_base": len(base.ranking),
                "candidate_set_stable": sum(c["candidates_same"] for c in comps) / len(comps),
                "top1_stable": (sum(bool(c["top1_same"]) for c in comps) / len(comps)) if base.ranking else None,
                "mean_kendall_tau": float(np.mean(taus)) if taus else None,
                "mean_impact_band_changes": float(np.mean([c["impact_band_changes"] for c in comps])),
            }
            rows.append(row)
            summary[f"{case_id}@sigma={sigma}"] = {
                k: row[k] for k in ("candidate_set_stable", "top1_stable", "mean_kendall_tau")
            }
    write_csv(run.path("stress.csv"), rows)
    notes = (
        []
        if any(r["ranked_in_base"] for r in rows)
        else ["No case has ranked candidates, so only candidate-set stability is informative (see `rbrs audit`)."]
    )
    run.finish("COMPLETED", summary, notes=notes)
    return summary
