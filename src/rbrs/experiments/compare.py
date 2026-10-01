"""Comparison of two reports for the same firm (used by E8 and E10)."""

from typing import Any

from scipy.stats import kendalltau

from rbrs.pipeline import Report


def compare_reports(base: Report, other: Report) -> dict[str, Any]:
    base_c = {s.intervention_id for s in base.interventions}
    other_c = {s.intervention_id for s in other.interventions}
    common = [i for i in base.ranking if i in other.ranking]
    tau: float | None = None
    if len(common) >= 2:
        pos = {i: r for r, i in enumerate(other.ranking)}
        tau = float(kendalltau(range(len(common)), [pos[i] for i in common]).statistic)
    base_i = {s.intervention_id: s.impact for s in base.interventions}
    other_i = {s.intervention_id: s.impact for s in other.interventions}
    return {
        "candidates_same": base_c == other_c,
        "candidates_lost": sorted(base_c - other_c),
        "candidates_gained": sorted(other_c - base_c),
        "ranked_to_unquantified": sorted(set(base.ranking) - set(other.ranking) & other_c),
        "top1_same": (base.ranking[:1] == other.ranking[:1]) if base.ranking else None,
        "kendall_tau": tau,
        "impact_band_changes": sum(
            1 for i in base_i if i in other_i and base_i[i] is not None and base_i[i] != other_i[i]
        ),
        "ranked_base": len(base.ranking),
    }
