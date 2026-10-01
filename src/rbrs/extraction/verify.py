"""Pass 2 (deterministic): check every quote and number against the PDF text (FR-03),
then apply the abstention threshold (FR-04)."""

import re
import unicodedata
from pathlib import Path

from rbrs.extraction.schema import NUMERIC_FIELDS, coerce, leaf_name, numbers_in
from rbrs.profile.models import ExtractedField, ExtractionRecord

_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " ", "−": "-"})


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)  # join words hyphenated across lines
    return re.sub(r"\s+", " ", t).strip().lower()


def pdf_page_texts(pdf_path: str | Path) -> list[str]:
    import pymupdf

    with pymupdf.open(str(pdf_path)) as doc:  # type: ignore[no-untyped-call]
        return [page.get_text() for page in doc]


def _value_in_quote(field: str, value: object, quote: str) -> bool:
    if leaf_name(field) in NUMERIC_FIELDS:
        try:
            target = float(coerce(field, str(value)))
        except ValueError:
            return False
        return any(abs(n - target) <= 1e-9 * max(1.0, abs(target)) for n in numbers_in(quote))
    return True  # categorical values are often paraphrased; the quote check carries them


def verify_field(f: ExtractedField, pages: list[str]) -> ExtractedField:
    if f.status != "EXTRACTED" or f.provenance is None:
        return f
    norm_pages = [normalise(p) for p in pages]
    q = normalise(f.provenance.quote)
    page = f.provenance.page
    notes = []
    on_page = 1 <= page <= len(pages) and q in norm_pages[page - 1]
    if not on_page:
        others = [i + 1 for i, p in enumerate(norm_pages) if q and q in p]
        notes.append(f"quote found on page(s) {others}, not page {page}" if others else "quote not found in the PDF")
    found = on_page or any(q and q in p for p in norm_pages)
    value_ok = _value_in_quote(f.field, f.value, f.provenance.quote)
    if not value_ok:
        notes.append("value does not appear in the quote")
    return f.model_copy(
        update={
            "verified_in_source": bool(found and value_ok),
            "verification_note": "; ".join(notes) or None,
        }
    )


def verify_record(record: ExtractionRecord, pages: list[str]) -> ExtractionRecord:
    return record.model_copy(update={"fields": [verify_field(f, pages) for f in record.fields]})


def apply_threshold(record: ExtractionRecord, threshold: float | None) -> ExtractionRecord:
    """Abstain on fields below the threshold, keeping the dropped value in the note."""
    if threshold is None:
        return record
    out = []
    for f in record.fields:
        if f.status == "EXTRACTED" and f.confidence < threshold:
            out.append(
                f.model_copy(
                    update={
                        "status": "ABSTAINED",
                        "value": None,
                        "verification_note": f"confidence {f.confidence:.2f} < threshold {threshold:.2f}; "
                        f"model value was {f.value!r}",
                    }
                )
            )
        else:
            out.append(f)
    return record.model_copy(update={"fields": out})
