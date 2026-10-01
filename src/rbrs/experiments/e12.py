"""E12: expert validation of the rankings; E13: agreement on categorical judgements.

E12 input  data/expert/e12_rankings.csv (anonymised; never sent to an LLM, NFR-08)
    expert_id, case_id, intervention_id, rank[, impact, feasibility, cost_effectiveness]
  The system ranking for case_id comes from the pipeline on data/cases/<case_id>.yaml.
E13 input  data/expert/e13_labels.csv
    item_id, rater, label            (rater "system" is the prototype)
"""

import itertools
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from rbrs.analysis import cohen_kappa, kendall_tau_b, krippendorff_alpha, random_tau_baseline, top_k_overlap
from rbrs.experiments.common import DEFAULT_SEED, load_profile, start_run, write_csv, write_json
from rbrs.pipeline import KnowledgeBase, recommend
from rbrs.scoring import Candidate, SAWScorer

CRITERIA = ("impact", "feasibility", "cost_effectiveness")


def _consensus(df: pd.DataFrame) -> list[str]:
    mean = df.groupby("intervention_id")["rank"].mean()
    return sorted(mean.index, key=lambda i: (mean[i], i))


def run_e12(
    path: str = "data/expert/e12_rankings.csv",
    cases_dir: str = "data/cases",
    permutations: int = 10000,
    allow_dirty: bool = True,
) -> dict[str, Any]:
    run = start_run(
        "E12", seed=DEFAULT_SEED, params={"input": path, "permutations": permutations}, allow_dirty=allow_dirty
    )
    if not Path(path).exists():
        run.finish("NOT_RUN", {}, notes=[f"{path} not found: collect expert rankings first."])
        return {"status": "NOT_RUN"}
    df = pd.read_csv(path)
    kb = KnowledgeBase.load()
    per_case, rows = {}, []
    for case_id, cdf in df.groupby("case_id"):
        report = recommend(load_profile(Path(cases_dir) / f"{case_id}.yaml"), kb, profile_id=str(case_id))
        system = report.ranking
        consensus = _consensus(cdf)
        experts = sorted(cdf["expert_id"].unique())
        orders = {e: list(cdf[cdf.expert_id == e].sort_values("rank")["intervention_id"]) for e in experts}
        units = sorted(cdf["intervention_id"].unique())
        matrix = [
            [
                float(cdf[(cdf.expert_id == e) & (cdf.intervention_id == u)]["rank"].iloc[0])
                if ((cdf.expert_id == e) & (cdf.intervention_id == u)).any()
                else None
                for u in units
            ]
            for e in experts
        ]
        # Human ceiling: each expert against the consensus of the others.
        loo = (
            [kendall_tau_b(orders[e], _consensus(cdf[cdf.expert_id != e])) for e in experts] if len(experts) > 2 else []
        )
        impact_only = [
            s.intervention_id for s in sorted(report.ranked, key=lambda s: (-(s.impact or 0), s.intervention_id))
        ]
        res: dict[str, Any] = {
            "experts": len(experts),
            "system_ranking": system,
            "expert_consensus": consensus,
            "alpha_ordinal_inter_expert": krippendorff_alpha(matrix, "ordinal"),
            "tau_b_system_vs_consensus": kendall_tau_b(system, consensus),
            "top3_overlap_system_vs_consensus": top_k_overlap(system, consensus, 3),
            "tau_b_system_vs_each_expert": {e: kendall_tau_b(system, o) for e, o in orders.items()},
            "baseline_impact_only_tau_b": kendall_tau_b(impact_only, consensus),
            "baseline_random_tau_b": random_tau_baseline(consensus, permutations, DEFAULT_SEED),
            "human_leave_one_out_tau_b": [t for t in loo if t is not None],
            "unranked_by_system": sorted(set(consensus) - set(system)),
        }
        # Author-vs-expert decomposition: criterion differences, and the ranking
        # SAW gives when fed the experts' mean criterion scores.
        if set(CRITERIA) <= set(cdf.columns):
            author = {s.intervention_id: s for s in report.ranked}
            means = cdf.groupby("intervention_id")[list(CRITERIA)].mean()
            res["criterion_mean_difference_expert_minus_author"] = (
                {
                    c: float(
                        (
                            means.loc[[i for i in means.index if i in author], c]
                            - pd.Series({i: getattr(author[i], c) for i in means.index if i in author})
                        ).mean()
                    )
                    for c in CRITERIA
                }
                if author
                else None
            )
            cands = [
                Candidate(
                    id=str(i),
                    impact=float(r["impact"]),
                    feasibility=float(r["feasibility"]),
                    cost_effectiveness=float(r["cost_effectiveness"]),
                )
                for i, r in means.iterrows()
            ]
            saw_on_expert = [s.candidate.id for s in SAWScorer.from_weights(report.weights).rank(cands)]
            res["saw_on_expert_scores_tau_b_vs_consensus"] = kendall_tau_b(saw_on_expert, consensus)
        per_case[str(case_id)] = res
        rows.append({"case_id": case_id, **{k: v for k, v in res.items() if isinstance(v, (int, float)) or v is None}})
    write_json(run.path("e12_results.json"), per_case)
    write_csv(run.path("e12_summary.csv"), rows)
    run.finish(
        "COMPLETED",
        {
            c: {
                k: r[k]
                for k in ("tau_b_system_vs_consensus", "top3_overlap_system_vs_consensus", "alpha_ordinal_inter_expert")
            }
            for c, r in per_case.items()
        },
    )
    return per_case


def run_e13(path: str = "data/expert/e13_labels.csv", allow_dirty: bool = True) -> dict[str, Any]:
    run = start_run("E13", params={"input": path}, allow_dirty=allow_dirty)
    if not Path(path).exists():
        run.finish("NOT_RUN", {}, notes=[f"{path} not found: collect expert labels first."])
        return {"status": "NOT_RUN"}
    df = pd.read_csv(path)
    labels: dict[str, dict[str, str]] = defaultdict(dict)
    for r in df.itertuples():
        labels[str(r.rater)][str(r.item_id)] = str(r.label)
    raters = sorted(labels)
    pairs = []
    for a, b in itertools.combinations(raters, 2):
        items = sorted(set(labels[a]) & set(labels[b]))
        if items:
            pairs.append(
                {
                    "rater_a": a,
                    "rater_b": b,
                    "items": len(items),
                    "cohen_kappa": cohen_kappa([labels[a][i] for i in items], [labels[b][i] for i in items]),
                }
            )
    items = sorted({i for r in raters for i in labels[r]})
    codes = {lab: n for n, lab in enumerate(sorted(set(df["label"].astype(str))))}
    matrix = [[float(codes[labels[r][i]]) if i in labels[r] else None for i in items] for r in raters]
    summary = {
        "raters": raters,
        "items": len(items),
        "alpha_nominal_all": krippendorff_alpha(matrix, "nominal"),
        "pairs": pairs,
    }
    write_csv(run.path("e13_pairwise_kappa.csv"), pairs, columns=["rater_a", "rater_b", "items", "cohen_kappa"])
    write_json(run.path("e13_results.json"), summary)
    run.finish("COMPLETED", summary)
    return summary
