import pytest
from pydantic import ValidationError

from rbrs.profile import Emissions, ExtractedField, Provenance, ResidueStream, SMEProfile, profile_coverage
from tests.conftest import make_profile


def test_valid_profile_loads() -> None:
    p = make_profile()
    assert p.sector == "Manufacturing"
    assert p.scope3.assessed is False


def test_missing_required_field_fails() -> None:
    with pytest.raises(ValidationError):
        SMEProfile(employees_fte=50)  # type: ignore[call-arg]


def test_negative_mass_rejected() -> None:
    with pytest.raises(ValidationError):
        ResidueStream(material="wood", mass_t=-5.0, disposition="landfill", moisture_content=0.2)


def test_unassessed_scope_cannot_carry_a_value() -> None:
    # The old E11 used tco2e=0.0 with assessed=False, which reads as "no emissions".
    with pytest.raises(ValidationError):
        Emissions(tco2e=0.0, assessed=False)
    with pytest.raises(ValidationError):
        Emissions(tco2e=None, assessed=True)


def test_unknown_attribute_rejected() -> None:
    with pytest.raises(ValidationError):
        make_profile(unknown_field=1)


def test_moisture_must_be_a_fraction() -> None:
    with pytest.raises(ValidationError):
        ResidueStream(material="wood", mass_t=1.0, disposition="landfill", moisture_content=20.0)


def test_profile_coverage_counts_top_level_attributes() -> None:
    unused = profile_coverage({"scope1.tco2e", "residues", "sector"})
    assert "scope1" not in unused and "residues" not in unused and "sector" not in unused
    assert "scope2" in unused and len(unused) == 17 - 3


def test_extracted_field_consistency() -> None:
    with pytest.raises(ValidationError):
        ExtractedField(field="sector", value="x", status="ABSTAINED", confidence=0.5)
    with pytest.raises(ValidationError):
        ExtractedField(field="sector", value="x", status="EXTRACTED", confidence=0.5)
    ok = ExtractedField(
        field="sector", value="x", status="EXTRACTED", confidence=0.5, provenance=Provenance(page=1, quote="x")
    )
    assert ok.verified_in_source is None
