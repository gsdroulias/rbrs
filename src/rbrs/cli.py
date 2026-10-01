"""RBRS command line. Run `rbrs --help` (or `uv run rbrs --help`)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

import typer
import yaml

app = typer.Typer(help="RBRS research prototype", no_args_is_help=True)

AllowDirty = Annotated[bool, typer.Option(help="Run with uncommitted changes (results marked not publishable).")]
Drafts = Annotated[bool, typer.Option(help="Include draft (unsourced) rules.")]


def _print(obj: Any) -> None:
    typer.echo(json.dumps(obj, indent=2, default=str))


def _experiment(fn: Callable[..., Any], **kwargs: Any) -> Any:
    """Run an experiment; a dirty working tree is reported as a message, not a traceback."""
    from rbrs.experiments.common import DirtyTreeError

    try:
        return fn(**kwargs)
    except DirtyTreeError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command()
def run(
    profile: Annotated[Path, typer.Option(help="Profile YAML or JSON")],
    weights: str = "default",
    norm: str = "total_absolute",
    include_drafts: Drafts = False,
    out: Annotated[Path | None, typer.Option(help="Folder for JSON, CSV and Markdown output")] = None,
) -> None:
    """Run the decision layer for one profile (FR-13)."""
    from rbrs.experiments.common import load_profile, write_text
    from rbrs.pipeline import KnowledgeBase, recommend, report_to_csv, report_to_json, report_to_markdown
    from rbrs.scoring import NormMode, Weights

    if norm not in ("total_absolute", "scope_relative"):
        raise typer.BadParameter("norm must be total_absolute or scope_relative")
    rep = recommend(
        load_profile(profile),
        KnowledgeBase.load(include_drafts=include_drafts),
        Weights.parse(weights),
        cast(NormMode, norm),
        profile_id=profile.stem,
    )
    if out:
        write_text(out / f"{profile.stem}.json", report_to_json(rep))
        write_text(out / f"{profile.stem}.csv", report_to_csv([rep]))
        write_text(out / f"{profile.stem}.md", report_to_markdown(rep))
    typer.echo(report_to_markdown(rep))


@app.command()
def rules(stats: bool = True, include_drafts: Drafts = False) -> None:
    """Validate the rule base and report counts, activation and dead rules (FR-06)."""
    from rbrs.inference import activation_stats
    from rbrs.profile import profile_coverage
    from rbrs.rules import fields_read, load_rules, rule_stats
    from rbrs.synthetic import generate_cohort

    rs = load_rules("data/rules", include_drafts=include_drafts)
    out = rule_stats(rs)
    if stats:
        act = activation_stats(rs, [p for _, p in generate_cohort()])
        out.update(
            {
                "activation_over_synthetic_cohort": act["activation_frequency"],
                "dead_rules": act["dead_rules"],
                "chaining": act["chaining"],
                "profile_attributes_unused": profile_coverage(fields_read(rs)),
            }
        )
    _print(out)


@app.command()
def synthetic(n: int = 100, seed: int = 42, out: Path = Path("results/synthetic_profiles.jsonl")) -> None:
    """Generate the seeded synthetic cohort (FR-15)."""
    from rbrs.experiments.common import write_text
    from rbrs.synthetic import generate_cohort, load_config

    cfg = {**load_config(), "n_total": n}
    cohort = generate_cohort(cfg, seed=seed)
    write_text(
        out, "".join(json.dumps({"id": pid, **p.model_dump(mode="json")}, sort_keys=True) + "\n" for pid, p in cohort)
    )
    typer.echo(f"wrote {len(cohort)} profiles to {out}")


@app.command()
def audit(results_dir: Path = Path("results")) -> None:
    """List unsourced values, draft rules, coverage gaps and experiment status."""
    from rbrs.audit import audit as run_audit
    from rbrs.audit import audit_markdown

    r = run_audit("data", results_dir)
    typer.echo(audit_markdown(r))
    if not (r["ac07_pass"] and r["ac10_pass"]):
        raise typer.Exit(1)


# --- Extraction (perception layer) ---


@app.command()
def extract(
    pdf: Path,
    doc_id: str,
    runs: int | None = None,
    config: Path = Path("config/extraction.yaml"),
    out: Path = Path("data/extractions"),
) -> None:
    """Pass 1 + pass 2 on a PDF, archived to data/extractions/<doc_id>/ (needs GEMINI_API_KEY)."""
    from rbrs.extraction import ExtractionConfig, extract_pdf, pdf_page_texts, verify_record

    cfg = ExtractionConfig.load(config)
    cfg.require_pinned()
    pages = pdf_page_texts(pdf)
    for k in range(1, (runs or cfg.runs) + 1):
        rec = verify_record(extract_pdf(pdf, doc_id, cfg, out / doc_id, run=k), pages)
        (out / doc_id / f"run{k}.json").write_text(rec.model_dump_json(indent=2), encoding="utf-8")
        unverified = [f.field for f in rec.fields if f.verified_in_source is False]
        typer.echo(
            f"run {k}: {sum(f.status == 'EXTRACTED' for f in rec.fields)} extracted, "
            f"{len(unverified)} not verified in source {unverified}"
        )


@app.command(name="ingest-manual")
def ingest_manual(record: Path, pdf: Path | None = None, out: Path = Path("data/extractions")) -> None:
    """Validate an analyst's record (same schema as the LLM, FR-05) and verify its quotes."""
    from rbrs.extraction import pdf_page_texts, verify_record
    from rbrs.profile import ExtractionRecord

    rec = ExtractionRecord(**{**yaml.safe_load(record.read_text(encoding="utf-8")), "method": "manual"})
    if pdf:
        rec = verify_record(rec, pdf_page_texts(pdf))
    dest = out / rec.document_id / "manual.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rec.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"wrote {dest}")


@app.command()
def assemble(
    record: Path,
    confirm: Annotated[Path | None, typer.Option(help="YAML {field_path: value} confirmed by a person")] = None,
    threshold: float | None = None,
    out: Path | None = None,
) -> None:
    """Build a profile from a verified record; list what still needs human confirmation."""
    from rbrs.extraction import apply_threshold, assemble_profile
    from rbrs.profile import ExtractionRecord

    rec = apply_threshold(ExtractionRecord.model_validate_json(record.read_text(encoding="utf-8")), threshold)
    confirmations = yaml.safe_load(confirm.read_text(encoding="utf-8")) if confirm else {}
    profile, pending = assemble_profile(rec, confirmations)
    if pending:
        typer.echo("Needs human confirmation:\n" + "\n".join(f"  - {p}" for p in pending))
    if profile and out:
        out.write_text(yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        typer.echo(f"wrote {out}")
    if profile is None:
        raise typer.Exit(1)


# --- Experiments ---


@app.command(name="run-e4")
def run_e4_cmd(
    weights: str = "default",
    norm: str = "total_absolute",
    include_drafts: Drafts = False,
    allow_dirty: AllowDirty = False,
) -> None:
    """E4: case-firm runs."""
    from rbrs.experiments.e4 import run_e4
    from rbrs.scoring import NormMode

    _print(
        _experiment(
            run_e4, weights=weights, norm=cast(NormMode, norm), include_drafts=include_drafts, allow_dirty=allow_dirty
        )
    )


@app.command(name="run-e5")
def run_e5_cmd(allow_dirty: AllowDirty = False) -> None:
    """E5: weight sensitivity (AC-01)."""
    from rbrs.experiments.e5 import run_e5

    _print(_experiment(run_e5, allow_dirty=allow_dirty))


@app.command(name="run-e6")
def run_e6_cmd(include_drafts: Drafts = False, allow_dirty: AllowDirty = False) -> None:
    """E6: constraint layer and burden shifting (AC-05)."""
    from rbrs.experiments.e6 import run_e6

    _print(_experiment(run_e6, include_drafts=include_drafts, allow_dirty=allow_dirty))


@app.command(name="run-e7")
def run_e7_cmd(allow_dirty: AllowDirty = False) -> None:
    """E7: forward-chaining analysis and single-pass ablation."""
    from rbrs.experiments.e7 import run_e7

    _print(_experiment(run_e7, allow_dirty=allow_dirty))


@app.command(name="run-e8")
def run_e8_cmd(include_drafts: Drafts = False, allow_dirty: AllowDirty = False) -> None:
    """E8: missing-data handling."""
    from rbrs.experiments.e8 import run_e8

    _print(_experiment(run_e8, include_drafts=include_drafts, allow_dirty=allow_dirty))


@app.command(name="run-e9")
def run_e9_cmd(allow_dirty: AllowDirty = False) -> None:
    """E9: extraction evaluation against gold annotations (offline)."""
    from rbrs.experiments.e9 import run_e9

    _print(_experiment(run_e9, allow_dirty=allow_dirty))


@app.command(name="run-e10")
def run_e10_cmd(include_drafts: Drafts = False, allow_dirty: AllowDirty = False) -> None:
    """E10: Monte Carlo stress test."""
    from rbrs.experiments.e10 import run_e10

    _print(_experiment(run_e10, include_drafts=include_drafts, allow_dirty=allow_dirty))


@app.command(name="run-e11")
def run_e11_cmd(include_drafts: Drafts = False, allow_dirty: AllowDirty = False) -> None:
    """E11: synthetic cohort coverage."""
    from rbrs.experiments.e11 import run_e11

    _print(_experiment(run_e11, include_drafts=include_drafts, allow_dirty=allow_dirty))


@app.command(name="run-e12")
def run_e12_cmd(allow_dirty: AllowDirty = False) -> None:
    """E12: expert validation of rankings."""
    from rbrs.experiments.e12 import run_e12

    _print(_experiment(run_e12, allow_dirty=allow_dirty))


@app.command(name="run-e13")
def run_e13_cmd(allow_dirty: AllowDirty = False) -> None:
    """E13: agreement on categorical judgements (Cohen's kappa)."""
    from rbrs.experiments.e12 import run_e13

    _print(_experiment(run_e13, allow_dirty=allow_dirty))


@app.command()
def reproduce(allow_dirty: AllowDirty = False) -> None:
    """Regenerate every offline result (no LLM calls): E4-E13."""
    from rbrs.experiments.e4 import run_e4
    from rbrs.experiments.e5 import run_e5
    from rbrs.experiments.e6 import run_e6
    from rbrs.experiments.e7 import run_e7
    from rbrs.experiments.e8 import run_e8
    from rbrs.experiments.e9 import run_e9
    from rbrs.experiments.e10 import run_e10
    from rbrs.experiments.e11 import run_e11
    from rbrs.experiments.e12 import run_e12, run_e13

    steps: list[tuple[str, Callable[..., Any]]] = [
        ("E4", run_e4),
        ("E5", run_e5),
        ("E6", run_e6),
        ("E7", run_e7),
        ("E8", run_e8),
        ("E9", run_e9),
        ("E10", run_e10),
        ("E11", run_e11),
        ("E12", run_e12),
        ("E13", run_e13),
    ]
    for name, fn in steps:
        typer.echo(f"== {name}")
        _experiment(fn, allow_dirty=allow_dirty)
    audit()


if __name__ == "__main__":
    app()
