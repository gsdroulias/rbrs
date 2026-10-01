"""Extraction metrics against gold annotations (E9; E1-E3 in REQUIREMENTS).

Gold file (data/gold/<doc_id>.yaml): {field_path: value}. A null value means the
document does not state the field, so the correct behaviour is to abstain.
Fields absent from the gold file are not scored.

Per field:  TP correct value | FP wrong value or value where gold is null
            FN abstained where gold has a value | TN abstained where gold is null
"""

import math
from collections import defaultdict
from typing import Any

from rbrs.extraction.schema import coerce, leaf_name
from rbrs.profile.models import ExtractionRecord


def values_match(field: str, predicted: Any, gold: Any, rel_tol: float) -> bool:
    try:
        p = coerce(field, None if predicted is None else str(predicted))
        g = coerce(field, None if gold is None else str(gold))
    except ValueError:
        return False
    if isinstance(g, list) and isinstance(p, list):
        return {str(x).strip().lower() for x in p} == {str(x).strip().lower() for x in g}
    if isinstance(g, (int, float)) and isinstance(p, (int, float)):
        return math.isclose(float(p), float(g), rel_tol=rel_tol, abs_tol=1e-12)
    return str(p).strip().lower() == str(g).strip().lower()


def score_record(record: ExtractionRecord, gold: dict[str, Any], rel_tol: float) -> list[dict[str, Any]]:
    rows = []
    for field, g in gold.items():
        f = record.get(field)
        extracted = f is not None and f.status == "EXTRACTED"
        if g is None:
            outcome = "FP" if extracted else "TN"
        elif not extracted:
            outcome = "FN"
        else:
            assert f is not None
            outcome = "TP" if values_match(field, f.value, g, rel_tol) else "FP"
        rows.append(
            {
                "document_id": record.document_id,
                "method": record.method,
                "field": field,
                "field_group": leaf_name(field) if field.startswith("residues.") else field,
                "outcome": outcome,
                "gold": g,
                "predicted": f.value if f else None,
                "confidence": f.confidence if f else None,
                "verified_in_source": f.verified_in_source if f else None,
                "gold_null": g is None,
            }
        )
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    c: defaultdict[str, int] = defaultdict(int)
    for r in rows:
        c[r["outcome"]] += 1
    tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]
    extracted = tp + fp
    return {
        "n": len(rows),
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": tp / extracted if extracted else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "coverage": extracted / len(rows) if rows else None,
        "abstention_accuracy": tn / (tn + sum(1 for r in rows if r["gold_null"] and r["outcome"] == "FP"))
        if any(r["gold_null"] for r in rows)
        else None,
        "unsupported_value_rate": sum(1 for r in rows if r["gold_null"] and r["outcome"] == "FP") / extracted
        if extracted
        else None,
        "unverified_rate": sum(1 for r in rows if r["outcome"] in ("TP", "FP") and r["verified_in_source"] is False)
        / extracted
        if extracted
        else None,
    }


def by_field(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[r["field_group"]].append(r)
    return {k: summarise(v) for k, v in sorted(groups.items())}


def run_agreement(records: list[ExtractionRecord], rel_tol: float) -> dict[str, Any]:
    """Field-level agreement across repeated runs on one document."""
    if len(records) < 2:
        return {"runs": len(records), "fields": 0, "agreement": None}
    fields = sorted({f.field for r in records for f in r.fields})
    agree = 0
    for field in fields:
        outs = [r.get(field) for r in records]
        statuses = {o.status if o else "ABSTAINED" for o in outs}
        if statuses == {"ABSTAINED"}:
            agree += 1
        elif statuses == {"EXTRACTED"}:
            first = outs[0]
            assert first is not None
            agree += all(o is not None and values_match(field, o.value, first.value, rel_tol) for o in outs[1:])
    return {"runs": len(records), "fields": len(fields), "agreement": agree / len(fields) if fields else None}


def calibrate_threshold(rows: list[dict[str, Any]], target_precision: float) -> dict[str, Any]:
    """FR-04: the lowest confidence threshold whose precision on extracted fields
    reaches the target, computed on development-split rows only."""
    candidates = sorted({r["confidence"] for r in rows if r["confidence"] is not None and r["outcome"] in ("TP", "FP")})
    curve = []
    chosen = None
    for t in [0.0, *candidates]:
        kept = [r for r in rows if r["outcome"] in ("TP", "FP") and (r["confidence"] or 0.0) >= t]
        if not kept:
            continue
        prec = sum(r["outcome"] == "TP" for r in kept) / len(kept)
        curve.append({"threshold": t, "precision": prec, "kept": len(kept)})
        if chosen is None and prec >= target_precision:
            chosen = t
    return {"target_precision": target_precision, "threshold": chosen, "curve": curve}
