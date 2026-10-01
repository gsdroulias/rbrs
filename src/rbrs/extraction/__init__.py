"""Perception layer (L0). May import only rbrs.profile (NFR-04, enforced by import-linter)."""

from .assemble import assemble_profile, usable_values
from .evaluation import by_field, calibrate_threshold, run_agreement, score_record, summarise
from .llm import ExtractionConfig, call_gemini, extract_pdf, parse_response
from .verify import apply_threshold, normalise, pdf_page_texts, verify_record

__all__ = [
    "ExtractionConfig",
    "apply_threshold",
    "assemble_profile",
    "by_field",
    "calibrate_threshold",
    "call_gemini",
    "extract_pdf",
    "normalise",
    "parse_response",
    "pdf_page_texts",
    "run_agreement",
    "score_record",
    "summarise",
    "usable_values",
    "verify_record",
]
