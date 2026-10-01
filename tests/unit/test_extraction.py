import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from rbrs.extraction import (
    ExtractionConfig,
    apply_threshold,
    assemble_profile,
    calibrate_threshold,
    call_gemini,
    parse_response,
    run_agreement,
    score_record,
    summarise,
    verify_record,
)
from rbrs.extraction.schema import coerce, is_known_field, numbers_in, parse_number
from rbrs.profile import ExtractedField, ExtractionRecord, Provenance

CFG = ExtractionConfig(model_id="test-model-001", prompt="prompts/extraction_v2.md")
PAGES = [
    "Company profile\nWe are a metal-working manufacturer with 45 employees (FTE).\n",
    "Emissions\nIn 2023 our Scope 1 emissions were 1,234.5 tCO2e and Scope 2 emis-\nsions 80 tCO2e.",
]


def field(name: str, value: Any, page: int, quote: str, conf: float = 0.9) -> ExtractedField:
    return ExtractedField(
        field=name, value=value, status="EXTRACTED", confidence=conf, provenance=Provenance(page=page, quote=quote)
    )


def record(*fields: ExtractedField, doc: str = "d1") -> ExtractionRecord:
    return ExtractionRecord(document_id=doc, method="llm", fields=list(fields))


def test_numbers() -> None:
    assert parse_number("1,234.5") == 1234.5
    assert parse_number("1.234,5") == 1234.5
    assert parse_number("0,150") == 0.15
    assert numbers_in("In 2023 120.5 t") == [2023.0, 120.5]
    assert coerce("employees_fte", "45") == 45
    assert coerce("energy_carriers", "electricity, diesel") == ["electricity", "diesel"]
    assert coerce("thermal_fuel", "none") is None
    with pytest.raises(ValueError):
        coerce("employees_fte", "45.5")
    assert is_known_field("residues.2.mass_t") and not is_known_field("residues.x.mass_t")


def test_call_gemini_uses_schema_and_default_temperature() -> None:
    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(
        text='{"fields": []}',
        usage_metadata=MagicMock(
            prompt_token_count=10, candidates_token_count=5, thoughts_token_count=0, cached_content_token_count=0
        ),
    )
    text, usage = call_gemini(["prompt"], CFG, client=client)
    assert text == '{"fields": []}' and usage["prompt"] == 10
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "test-model-001"
    cfg = kwargs["config"]
    assert cfg.response_json_schema is not None and cfg.temperature is None


def test_unpinned_model_refused() -> None:
    with pytest.raises(RuntimeError, match="pinned"):
        call_gemini(["p"], ExtractionConfig(model_id="SET_ME", prompt="x"), client=MagicMock())


def test_parse_response_keeps_malformed_items_as_abstentions() -> None:
    text = json.dumps(
        {
            "fields": [
                {
                    "field": "employees_fte",
                    "value": "45",
                    "status": "EXTRACTED",
                    "confidence": 0.9,
                    "page": 1,
                    "quote": "45 employees (FTE)",
                },
                {
                    "field": "turnover_meur",
                    "value": "4.2",
                    "status": "EXTRACTED",
                    "confidence": 0.8,
                    "page": None,
                    "quote": None,
                },
                {
                    "field": "sector",
                    "value": None,
                    "status": "ABSTAINED",
                    "confidence": 0.2,
                    "page": None,
                    "quote": None,
                },
            ]
        }
    )
    rec = parse_response(text, "d1", CFG, {})
    assert [f.status for f in rec.fields] == ["EXTRACTED", "ABSTAINED", "ABSTAINED"]
    assert rec.fields[1].verification_note and rec.prompt_version == "extraction_v2"


def test_verification_against_pdf_text() -> None:
    rec = verify_record(
        record(
            field("employees_fte", "45", 1, "with 45 employees (FTE)"),
            field("scope1.tco2e", "1234.5", 2, "Scope 1 emissions were 1,234.5 tCO2e"),
            field("scope2.tco2e", "80", 2, "Scope 2 emissions 80 tCO2e"),  # hyphenated across lines in the PDF
            field("turnover_meur", "4.2", 1, "turnover of EUR 4.2 million"),  # hallucinated quote
            field("route_distance_km", "150", 2, "Scope 2 emissions 80 tCO2e"),  # value not in quote
            field("sector", "manufacturing", 2, "metal-working manufacturer"),  # right quote, wrong page
        ),
        PAGES,
    )
    by = {f.field: f for f in rec.fields}
    assert by["employees_fte"].verified_in_source is True
    assert by["scope1.tco2e"].verified_in_source is True
    assert by["scope2.tco2e"].verified_in_source is True
    assert by["turnover_meur"].verified_in_source is False
    assert by["route_distance_km"].verified_in_source is False
    assert "not in the quote" in (by["route_distance_km"].verification_note or "") or "does not appear" in (
        by["route_distance_km"].verification_note or ""
    )
    assert by["sector"].verified_in_source is True and "page(s) [1]" in (by["sector"].verification_note or "")


def test_threshold_abstains_and_keeps_the_dropped_value() -> None:
    rec = apply_threshold(record(field("employees_fte", "45", 1, "45", conf=0.4)), 0.5)
    f = rec.fields[0]
    assert f.status == "ABSTAINED" and f.value is None and "'45'" in (f.verification_note or "")
    assert apply_threshold(rec, None) == rec


def test_assemble_routes_gaps_to_a_person() -> None:
    rec = verify_record(
        record(
            field("employees_fte", "45", 1, "45 employees"),
            field("scope1.tco2e", "1234.5", 2, "1,234.5 tCO2e"),
            field("turnover_meur", "4.2", 1, "EUR 4.2 million"),
        ),
        PAGES,
    )
    profile, pending = assemble_profile(rec)
    assert profile is None
    assert "turnover_meur (not verified in source)" in pending and "sector" in pending
    confirmations = {
        "sector": "Manufacturing",
        "scope2.tco2e": 80.0,
        "energy_carriers": ["electricity"],
        "electricity_supply": "grid",
        "thermal_fuel": None,
        "certifications": [],
        "capital_availability": "moderate",
        "maturity_level": 2,
        "logistics_mode": "diesel_truck",
        "material_type": "Steel",
        "process_efficiency": "medium",
    }
    profile, pending = assemble_profile(rec, confirmations)
    assert profile is not None
    assert profile.employees_fte == 45 and profile.scope1.tco2e == 1234.5 and profile.turnover_meur is None
    assert profile.scope3.assessed is False


def test_metrics_and_calibration() -> None:
    gold = {"employees_fte": 45, "turnover_meur": None, "scope1.tco2e": 1234.5, "sector": "Manufacturing"}
    rec = record(
        field("employees_fte", "45", 1, "45", conf=0.9),  # TP
        field("turnover_meur", "4.2", 1, "4.2", conf=0.3),  # FP: gold says not stated
        field("scope1.tco2e", "1200", 2, "1200", conf=0.6),  # FP: wrong value
    )  # sector missing -> FN
    rows = score_record(rec, gold, rel_tol=0.001)
    s = summarise(rows)
    assert (s["TP"], s["FP"], s["FN"], s["TN"]) == (1, 2, 1, 0)
    assert s["precision"] == pytest.approx(1 / 3) and s["recall"] == pytest.approx(1 / 2)
    assert s["unsupported_value_rate"] == pytest.approx(1 / 3)
    cal = calibrate_threshold(rows, target_precision=0.95)
    assert cal["threshold"] == 0.9


def test_run_agreement() -> None:
    a = record(field("employees_fte", "45", 1, "45"), field("sector", "x", 1, "x"))
    b = record(field("employees_fte", "45.0", 1, "45"), field("sector", "y", 1, "y"))
    assert run_agreement([a, b], 0.001) == {"runs": 2, "fields": 2, "agreement": 0.5}


def test_pdf_page_texts_reads_a_real_pdf(tmp_path: Any) -> None:
    import pymupdf

    from rbrs.extraction import pdf_page_texts

    path = tmp_path / "r.pdf"
    doc = pymupdf.open()
    for text in ("We employ 45 people.", "Scope 1: 1,234.5 tCO2e"):
        doc.new_page().insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    pages = pdf_page_texts(path)
    rec = verify_record(record(field("scope1.tco2e", "1234.5", 2, "Scope 1: 1,234.5 tCO2e")), pages)
    assert len(pages) == 2 and rec.fields[0].verified_in_source is True
