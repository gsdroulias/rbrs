"""`rbrs audit`: what still stands between the prototype and publishable results.

Lists every unsourced or unverified number, draft rule, undocumented coverage
gap (AC-10) and the status of each experiment's latest manifest.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from rbrs.constraints import load_factors
from rbrs.profile import profile_coverage
from rbrs.rules import fields_read, load_interventions, load_rules


def audit(data_dir: str | Path = "data", results_dir: str | Path = "results") -> dict[str, Any]:
    d = Path(data_dir)
    factors = load_factors(d / "factors")
    interventions = load_interventions(d / "interventions.yaml")
    all_rules = load_rules(d / "rules", include_drafts=True)
    active = [r for r in all_rules if r.status == "active"]
    coverage_doc_path = d / "profile_coverage.yaml"
    documented = yaml.safe_load(coverage_doc_path.read_text(encoding="utf-8")) if coverage_doc_path.exists() else {}
    unused = profile_coverage(fields_read(active))
    used_in_active = {r.consequent for r in active if r.consequent}

    experiments = {}

    def _num(m: Path) -> tuple[int, str]:
        digits = "".join(ch for ch in m.parent.name if ch.isdigit())
        return (int(digits) if digits else 0, m.parent.name)

    for m in sorted(Path(results_dir).glob("*/manifest.json"), key=_num):
        man = json.loads(m.read_text(encoding="utf-8"))
        experiments[man.get("experiment", m.parent.name)] = {
            "status": man.get("status"),
            "publishable": man.get("publishable"),
            "git_commit": (man.get("git_commit") or "")[:10],
            "notes": man.get("notes", []),
        }
    report: dict[str, Any] = {
        "factors_source_needed": sorted(f.id for f in factors.values() if f.status == "SOURCE_NEEDED"),
        "factors_unverified": sorted(
            f.id for f in factors.values() if f.status == "cited" and not f.verified_by_author
        ),
        "interventions_missing_data": {
            i: iv.missing_data() for i, iv in sorted(interventions.items()) if iv.missing_data()
        },
        "interventions_used_by_active_rules_missing_data": sorted(
            i for i in used_in_active if interventions[i].missing_data()
        ),
        "draft_rules": sorted(r.id for r in all_rules if r.status == "draft"),
        "active_rules_unsourced": sorted(r.id for r in active if not r.is_sourced),
        "profile_attributes_unused": unused,
        "profile_attributes_unused_undocumented": sorted(set(unused) - set(documented or {})),
        "experiments": experiments,
    }
    report["ac07_pass"] = all(f.source.strip() for f in factors.values())
    report["ac10_pass"] = not report["profile_attributes_unused_undocumented"]
    report["ready_for_paper"] = (
        report["ac07_pass"]
        and report["ac10_pass"]
        and not report["factors_unverified"]
        and not report["interventions_used_by_active_rules_missing_data"]
        and not report["active_rules_unsourced"]
        and bool(experiments)
        and all(e["publishable"] for e in experiments.values())
    )
    return report


def audit_markdown(r: dict[str, Any]) -> str:
    def items(xs: Any) -> str:
        if isinstance(xs, dict):
            return "\n".join(f"- {k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in xs.items()) or "- none"
        return "\n".join(f"- {x}" for x in xs) or "- none"

    exp = (
        "\n".join(
            f"| {k} | {v['status']} | {v['publishable']} | {v['git_commit']} | {'; '.join(v['notes'])} |"
            for k, v in r["experiments"].items()
        )
        or "| (no results yet) | | | | |"
    )
    return f"""# RBRS audit

Ready for the paper: **{r["ready_for_paper"]}**  (AC-07 {r["ac07_pass"]}, AC-10 {r["ac10_pass"]})

## Factors without a source (value withheld)
{items(r["factors_source_needed"])}

## Factors not yet verified by the author against the cited document
{items(r["factors_unverified"])}

## Interventions missing data (UNQUANTIFIED until supplied)
{items(r["interventions_missing_data"])}

Used by active rules: {", ".join(r["interventions_used_by_active_rules_missing_data"]) or "none"}

## Draft rules (excluded from paper runs until sourced and set to active)
{items(r["draft_rules"])}

## Profile attributes no active rule reads
{items(r["profile_attributes_unused"])}

Undocumented (fails AC-10): {", ".join(r["profile_attributes_unused_undocumented"]) or "none"}

## Experiments

| Experiment | Status | Publishable | Commit | Notes |
|---|---|---|---|---|
{exp}
"""
