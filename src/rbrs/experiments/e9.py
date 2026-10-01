"""E9: extraction evaluation against gold annotations (FR-02 to FR-05).

Inputs (nothing here calls the LLM; extraction runs are archived first with
`rbrs extract`, so the evaluation is reproducible):
  data/gold/<doc_id>.yaml            gold values (null = not stated in the document)
  data/gold/splits.yaml              optional {dev: [...], test: [...]}
  data/extractions/<doc_id>/run<k>.json   verified LLM records (method llm)
  data/extractions/<doc_id>/manual.json   analyst record (method manual, FR-05)
"""

from pathlib import Path
from typing import Any

import yaml

from rbrs.experiments.common import save_figure, start_run, write_csv, write_json
from rbrs.extraction import (
    ExtractionConfig,
    apply_threshold,
    by_field,
    calibrate_threshold,
    run_agreement,
    score_record,
    summarise,
)
from rbrs.profile.models import ExtractionRecord


def load_gold(gold_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for p in sorted(gold_dir.glob("*.yaml"))
        if p.stem != "splits"
    }


def load_records(extractions_dir: Path, doc_id: str) -> dict[str, list[ExtractionRecord]]:
    d = extractions_dir / doc_id
    llm = [
        ExtractionRecord.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(d.glob("run*.json"))
        if not p.name.endswith(".response.json")
    ]
    manual_path = d / "manual.json"
    manual = (
        [ExtractionRecord.model_validate_json(manual_path.read_text(encoding="utf-8"))] if manual_path.exists() else []
    )
    return {"llm": llm, "manual": manual}


def run_e9(
    gold_dir: str = "data/gold",
    extractions_dir: str = "data/extractions",
    config: str = "config/extraction.yaml",
    allow_dirty: bool = True,
) -> dict[str, Any]:
    cfg = ExtractionConfig.load(config)
    run = start_run(
        "E9",
        params={"gold_dir": gold_dir, "extractions_dir": extractions_dir, "prompt_version": cfg.prompt_version},
        allow_dirty=allow_dirty,
    )
    gold = load_gold(Path(gold_dir))
    records = {doc: load_records(Path(extractions_dir), doc) for doc in gold}
    docs = [d for d in gold if records[d]["llm"] or records[d]["manual"]]
    if not docs:
        run.finish(
            "NOT_RUN",
            {"gold_documents": len(gold), "documents_with_extractions": 0},
            notes=[
                "No gold annotations with matching extraction records. Annotate reports in data/gold/ "
                "and archive runs with `rbrs extract` before reporting any extraction metric."
            ],
        )
        return {"status": "NOT_RUN"}

    splits_path = Path(gold_dir) / "splits.yaml"
    splits = yaml.safe_load(splits_path.read_text(encoding="utf-8")) if splits_path.exists() else {}
    dev, test = set(splits.get("dev", [])), set(splits.get("test", []))
    tol = cfg.numeric_rel_tol

    # Threshold: calibrated on dev (first LLM run of each dev document), else from config.
    calibration: dict[str, Any] = {"source": "config", "threshold": cfg.abstention_threshold}
    if dev:
        dev_rows = [
            row for d in docs if d in dev for rec in records[d]["llm"][:1] for row in score_record(rec, gold[d], tol)
        ]
        calibration = {"source": "dev split", **calibrate_threshold(dev_rows, cfg.target_precision)}
    threshold = calibration["threshold"]
    eval_docs = [d for d in docs if d in test] if test else docs

    rows: list[dict[str, Any]] = []
    for d in eval_docs:
        for i, rec in enumerate(records[d]["llm"], start=1):
            for r in score_record(apply_threshold(rec, threshold), gold[d], tol):
                rows.append({**r, "run": i})
        for rec in records[d]["manual"]:
            rows.extend({**r, "run": 0} for r in score_record(rec, gold[d], tol))
    write_csv(run.path("field_scores.csv"), rows)

    llm_first = [r for r in rows if r["method"] == "llm" and r["run"] == 1]
    manual = [r for r in rows if r["method"] == "manual"]
    agreement = {d: run_agreement(records[d]["llm"], tol) for d in eval_docs if len(records[d]["llm"]) > 1}
    usage: dict[str, int] = {}
    for d in eval_docs:
        for rec in records[d]["llm"]:
            for k, v in rec.usage.items():
                usage[k] = usage.get(k, 0) + (v or 0)
    metrics = {
        "evaluated_documents": len(eval_docs),
        "split": "test" if test else "all (no dev/test split: threshold not calibrated out of sample)",
        "threshold": threshold,
        "llm_run1": summarise(llm_first),
        "llm_run1_by_field": by_field(llm_first),
        "llm_all_runs": summarise([r for r in rows if r["method"] == "llm"]),
        "manual": summarise(manual) if manual else None,
        "manual_by_field": by_field(manual) if manual else None,
        "run_to_run_agreement": agreement,
    }
    write_json(run.path("metrics.json"), metrics)
    write_json(run.path("calibration.json"), calibration)
    if calibration.get("curve"):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.plot(
            [c["threshold"] for c in calibration["curve"]], [c["precision"] for c in calibration["curve"]], marker="."
        )
        ax.axhline(cfg.target_precision, ls="--", color="grey")
        ax.set_xlabel("confidence threshold")
        ax.set_ylabel("precision (dev)")
        save_figure(fig, run.path("fig_e9_calibration.png"))
    model_ids = sorted({rec.model_id or "" for d in eval_docs for rec in records[d]["llm"]})
    summary = {
        "documents": len(eval_docs),
        "precision": metrics["llm_run1"]["precision"],
        "recall": metrics["llm_run1"]["recall"],
        "threshold": threshold,
        "model_ids": model_ids,
    }
    run.finish("COMPLETED", summary, model_id=",".join(model_ids) or None, token_usage=usage)
    return summary
