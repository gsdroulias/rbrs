"""Assemble an SMEProfile from an extraction record plus human confirmations.

Abstained, unverified or untypeable fields are never filled in automatically:
they are returned as `needs_confirmation` and must come from `confirmations`
(an analyst's answers, keyed by field path).
"""

from typing import Any

from pydantic import ValidationError

from rbrs.extraction.schema import RESIDUE_RE, SCALAR_FIELDS, coerce, is_known_field
from rbrs.profile.models import ExtractionRecord, SMEProfile


def usable_values(record: ExtractionRecord) -> tuple[dict[str, Any], list[str]]:
    """Typed values the pipeline may use, and fields that need a person."""
    values: dict[str, Any] = {}
    review: list[str] = []
    for f in record.fields:
        if not is_known_field(f.field):
            review.append(f"{f.field} (unknown field)")
            continue
        if f.status != "EXTRACTED":
            review.append(f.field)
            continue
        if f.verified_in_source is False:
            review.append(f"{f.field} (not verified in source)")
            continue
        try:
            values[f.field] = coerce(f.field, None if f.value is None else str(f.value))
        except ValueError:
            review.append(f"{f.field} (value not typeable)")
    return values, review


def assemble_profile(
    record: ExtractionRecord, confirmations: dict[str, Any] | None = None
) -> tuple[SMEProfile | None, list[str]]:
    values, review = usable_values(record)
    values.update(confirmations or {})
    data: dict[str, Any] = {}
    for path in SCALAR_FIELDS:
        if path.startswith("scope"):
            scope = path.split(".")[0]
            v = values.get(path)
            data[scope] = {"tco2e": v, "assessed": v is not None}
        elif path in values:
            data[path] = values[path]
    streams: dict[int, dict[str, Any]] = {}
    for path, v in values.items():
        m = RESIDUE_RE.match(path)
        if m:
            streams.setdefault(int(m.group(1)), {})[m.group(2)] = v
    data["residues"] = [streams[i] for i in sorted(streams)]
    try:
        return SMEProfile(**data), sorted(set(review) - set(confirmations or {}))
    except ValidationError as exc:
        missing = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        return None, sorted(set(review) | set(missing))
