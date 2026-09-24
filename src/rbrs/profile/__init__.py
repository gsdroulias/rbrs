from .models import Emissions, ExtractedField, Provenance, ResidueStream, SMEProfile

__all__ = [
    "Emissions",
    "ExtractedField",
    "Provenance",
    "ResidueStream",
    "SMEProfile",
]

def profile_coverage() -> list[str]:
    """Stub for FR-16: Returns a list of profile attributes never read by any rule."""
    return []
