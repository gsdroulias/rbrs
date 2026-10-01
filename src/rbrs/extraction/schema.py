"""Extraction targets, the LLM response schema, and value coercion.

The LLM returns every value as text; this module turns text into typed profile
values deterministically. Residue streams are flattened to `residues.N.<attr>`.
"""

import re
from typing import Any

from rbrs.profile.models import SMEProfile

SCALAR_FIELDS = (
    "sector",
    "employees_fte",
    "turnover_meur",
    "scope1.tco2e",
    "scope2.tco2e",
    "scope3.tco2e",
    "energy_carriers",
    "electricity_supply",
    "thermal_fuel",
    "certifications",
    "capital_availability",
    "maturity_level",
    "logistics_mode",
    "route_distance_km",
    "material_type",
    "process_efficiency",
)
RESIDUE_ATTRS = ("material", "mass_t", "disposition", "moisture_content")
RESIDUE_RE = re.compile(r"^residues\.(\d+)\.(material|mass_t|disposition|moisture_content)$")

FLOAT_FIELDS = {
    "turnover_meur",
    "scope1.tco2e",
    "scope2.tco2e",
    "scope3.tco2e",
    "route_distance_km",
    "mass_t",
    "moisture_content",
}
INT_FIELDS = {"employees_fte", "maturity_level"}
LIST_FIELDS = {"energy_carriers", "certifications"}
NUMERIC_FIELDS = FLOAT_FIELDS | INT_FIELDS

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": ["string", "null"]},
                    "status": {"type": "string", "enum": ["EXTRACTED", "ABSTAINED"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "page": {"type": ["integer", "null"]},
                    "section": {"type": ["string", "null"]},
                    "quote": {"type": ["string", "null"]},
                },
                "required": ["field", "value", "status", "confidence", "page", "quote"],
            },
        }
    },
    "required": ["fields"],
}


def is_known_field(path: str) -> bool:
    return path in SCALAR_FIELDS or RESIDUE_RE.match(path) is not None


def leaf_name(path: str) -> str:
    m = RESIDUE_RE.match(path)
    return m.group(2) if m else path


# Either digit groups with a thousands separator ("1,234,567.8", "1 234") or a
# plain number with an optional decimal part ("120.5", "12,5").
_NUM_RE = re.compile(r"[-+]?\d{1,3}(?:[ ,.']\d{3})+(?:[.,]\d+)?|[-+]?\d+(?:[.,]\d+)?")


def parse_number(text: str) -> float:
    """Parse '1,234.5', '1.234,5', '1 234', '12,5' and similar into a float."""
    m = _NUM_RE.search(text)
    if not m:
        raise ValueError(f"no number in {text!r}")
    s = re.sub(r"[\s']", "", m.group(0)).rstrip(".,")
    if "," in s and "." in s:
        # the right-most separator is the decimal mark
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        # "1,234" is a thousands separator; "12,5" and "0,150" are decimal commas
        thousands = len(tail) == 3 and head.lstrip("+-") not in ("", "0")
        s = s.replace(",", "") if thousands else s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    return float(s)


def numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text):
        try:
            out.append(parse_number(m.group(0)))
        except ValueError:
            continue
    return out


def coerce(path: str, text: str | None) -> Any:
    """Typed value for a field path; raises ValueError if the text does not fit."""
    if text is None:
        return None
    name = leaf_name(path)
    t = text.strip()
    if name in LIST_FIELDS:
        return [p.strip() for p in t.split(",") if p.strip()]
    if name in INT_FIELDS:
        v = parse_number(t)
        if v != int(v):
            raise ValueError(f"{path}: expected an integer, got {text!r}")
        return int(v)
    if name in FLOAT_FIELDS:
        return parse_number(t)
    if name == "thermal_fuel" and t.lower() == "none":
        return None
    return t


# Fields the profile requires but extraction may never supply (all others are optional).
REQUIRED_FIELDS = tuple(
    f
    for f in SMEProfile.model_fields
    if SMEProfile.model_fields[f].is_required() and f not in ("scope1", "scope2", "scope3", "residues")
)
