"""The deterministic decision layer: profile -> ranked, traced recommendations.

    rules (inference) -> constraints -> I/F/C -> SAW -> tie-break -> report

This is a pure function of its inputs (NFR-02): no clock, no randomness, no I/O
other than reading the knowledge base in `KnowledgeBase.load`.
"""

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from rbrs.constraints import (
    BURDEN_SHIFTING,
    ConstraintResult,
    FactorTable,
    evaluate_constraints,
    load_factors,
)
from rbrs.inference import InferenceEngine
from rbrs.profile.models import SMEProfile
from rbrs.rules import Intervention, Rule, load_interventions, load_rules
from rbrs.scoring import Candidate, NormMode, SAWScorer, Weights, band_impact


@dataclass
class KnowledgeBase:
    rules: list[Rule]
    interventions: dict[str, Intervention]
    factors: FactorTable

    @classmethod
    def load(cls, data_dir: str | Path = "data", include_drafts: bool = False) -> "KnowledgeBase":
        d = Path(data_dir)
        kb = cls(
            rules=load_rules(d / "rules", include_drafts=include_drafts),
            interventions=load_interventions(d / "interventions.yaml"),
            factors=FactorTable(load_factors(d / "factors")),
        )
        unknown = sorted({r.consequent for r in kb.rules if r.consequent} - set(kb.interventions))
        if unknown:
            raise ValueError(f"rule consequents missing from the intervention catalogue: {unknown}")
        return kb


class ScoredIntervention(BaseModel):
    intervention_id: str
    name: str
    hierarchy: str
    rule_ids: list[str]
    status: Literal["RANKED", "UNQUANTIFIED"]
    rank: int | None = None
    decided_by: str | None = None
    impact_share: float | None = None
    impact: float | None = None
    feasibility: float | None = None
    cost_effectiveness: float | None = None
    fis: float | None = None
    net_delta_t: float | None = None
    changes_t: dict[str, float | None] = {}
    biogenic_co2_t: float | None = None
    flags: list[str] = []
    missing: list[str] = []
    details: dict[str, Any] = {}


class Report(BaseModel):
    profile_id: str
    weights: Weights
    norm: str
    interventions: list[ScoredIntervention]
    derived_facts: dict[str, Any]
    chained: bool
    trace: list[dict[str, Any]]

    @property
    def ranked(self) -> list[ScoredIntervention]:
        return [s for s in self.interventions if s.status == "RANKED"]

    @property
    def ranking(self) -> list[str]:
        return [s.intervention_id for s in self.ranked]


def impact_share(
    cr: ConstraintResult, iv: Intervention, profile: SMEProfile, norm: NormMode
) -> tuple[float | None, list[str]]:
    """Net abatement as a share of the chosen denominator (FR-11)."""
    abatement = cr.abatement_t
    if abatement is None:
        return None, []
    if norm == "total_absolute":
        if not (profile.scope1.assessed and profile.scope2.assessed):
            return None, ["total_absolute needs assessed scope1 and scope2"]
        denom = (profile.scope1.tco2e or 0.0) + (profile.scope2.tco2e or 0.0)
    else:
        # scope_relative (v7): share of the intervention's primary target scope.
        if not iv.effects:
            return None, ["scope_relative needs a declared target scope"]
        target = getattr(profile, iv.effects[0].scope)
        if not target.assessed:
            return None, [f"{iv.effects[0].scope} not assessed"]
        denom = target.tco2e or 0.0
    if denom <= 0:
        return None, ["normalisation denominator is zero"]
    return abatement / denom, []


def recommend(
    profile: SMEProfile,
    kb: KnowledgeBase,
    weights: Weights | None = None,
    norm: NormMode = "total_absolute",
    profile_id: str = "",
) -> Report:
    weights = weights or Weights()
    result = InferenceEngine(kb.rules).run(profile)

    rows: list[ScoredIntervention] = []
    candidates: list[Candidate] = []
    for match in result.candidates:
        iv = kb.interventions[match.intervention_id]
        cr = evaluate_constraints(iv, profile, kb.factors)
        share, norm_missing = impact_share(cr, iv, profile, norm)
        missing = list(cr.missing) + norm_missing
        impact: float | None = None
        if BURDEN_SHIFTING in cr.flags:
            impact = 0.00  # DESIGN.md: burden-shifting candidates get I = 0.00
        elif share is not None:
            impact = band_impact(share)
        if iv.feasibility is None:
            missing.append("feasibility (SOURCE_NEEDED)")
        if iv.cost_effectiveness is None:
            missing.append("cost_effectiveness (SOURCE_NEEDED)")
        row = ScoredIntervention(
            intervention_id=iv.id,
            name=iv.name,
            hierarchy=iv.hierarchy,
            rule_ids=list(match.rule_ids),
            status="UNQUANTIFIED",
            impact_share=share,
            impact=impact,
            feasibility=iv.feasibility,
            cost_effectiveness=iv.cost_effectiveness,
            net_delta_t=cr.net_delta_t,
            changes_t=cr.changes_t,
            biogenic_co2_t=cr.biogenic_co2_t,
            flags=cr.flags,
            missing=missing,
            details=cr.details,
        )
        if impact is not None and iv.feasibility is not None and iv.cost_effectiveness is not None:
            row.status = "RANKED"
            candidates.append(
                Candidate(id=iv.id, impact=impact, feasibility=iv.feasibility, cost_effectiveness=iv.cost_effectiveness)
            )
        rows.append(row)

    by_id = {r.intervention_id: r for r in rows}
    for sc in SAWScorer.from_weights(weights).rank(candidates):
        row = by_id[sc.candidate.id]
        row.fis, row.rank, row.decided_by = sc.fis, sc.rank, sc.decided_by

    ranked = sorted((r for r in rows if r.status == "RANKED"), key=lambda r: r.rank or 0)
    unquantified = sorted((r for r in rows if r.status == "UNQUANTIFIED"), key=lambda r: r.intervention_id)
    return Report(
        profile_id=profile_id,
        weights=weights,
        norm=norm,
        interventions=ranked + unquantified,
        derived_facts=result.derived_facts,
        chained=result.chained,
        trace=[{"step": t.step, "rule_id": t.rule_id, "status": t.status, "reason": t.reason} for t in result.trace],
    )


# --- Output formats (FR-13) ---

CSV_COLUMNS = [
    "profile_id",
    "rank",
    "intervention_id",
    "status",
    "fis",
    "impact",
    "feasibility",
    "cost_effectiveness",
    "impact_share",
    "net_delta_t",
    "decided_by",
    "flags",
    "missing",
    "rule_ids",
]


def report_rows(report: Report) -> list[dict[str, Any]]:
    return [
        {
            "profile_id": report.profile_id,
            "rank": s.rank,
            "intervention_id": s.intervention_id,
            "status": s.status,
            "fis": s.fis,
            "impact": s.impact,
            "feasibility": s.feasibility,
            "cost_effectiveness": s.cost_effectiveness,
            "impact_share": None if s.impact_share is None else round(s.impact_share, 6),
            "net_delta_t": None if s.net_delta_t is None else round(s.net_delta_t, 6),
            "decided_by": s.decided_by,
            "flags": "|".join(s.flags),
            "missing": "|".join(s.missing),
            "rule_ids": "|".join(s.rule_ids),
        }
        for s in report.interventions
    ]


def report_to_csv(reports: list[Report]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for r in reports:
        writer.writerows(report_rows(r))
    return buf.getvalue()


def report_to_json(report: Report) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.3f}".rstrip("0").rstrip(".") if v != 0 else "0"


def report_to_markdown(report: Report) -> str:
    w = report.weights
    lines = [
        f"# Recommendations: {report.profile_id or 'profile'}",
        "",
        f"Weights W_I={w.w_i}, W_F={w.w_f}, W_C={w.w_c}; normalisation `{report.norm}`.",
        "",
        "| Rank | Intervention | FIS | I | F | C | Decided by | Flags |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in report.ranked:
        lines.append(
            f"| {s.rank} | {s.intervention_id} | {_fmt(s.fis)} | {_fmt(s.impact)} | "
            f"{_fmt(s.feasibility)} | {_fmt(s.cost_effectiveness)} | {s.decided_by} | "
            f"{', '.join(s.flags) or '-'} |"
        )
    unq = [s for s in report.interventions if s.status == "UNQUANTIFIED"]
    if unq:
        lines += ["", "## Unquantified (not ranked)", ""]
        for s in unq:
            lines.append(
                f"- **{s.intervention_id}**: missing {'; '.join(s.missing) or '-'}"
                + (f"; flags {', '.join(s.flags)}" if s.flags else "")
            )
    lines += ["", "## Rule trace", ""]
    for t in report.trace:
        if t["status"] == "fired":
            lines.append(f"{t['step']}. {t['rule_id']}: {t['reason']}")
    if report.derived_facts:
        lines += ["", f"Derived facts: {report.derived_facts}"]
    return "\n".join(lines) + "\n"
