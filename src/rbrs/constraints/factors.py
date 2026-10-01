"""Cited emission factors and physical constants (NFR-07, AC-07)."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from rbrs.profile.models import SOURCE_NEEDED


class Factor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    value: float | None
    unit: str
    source: str
    status: Literal["cited", "SOURCE_NEEDED"] = "cited"
    # False until the author has checked the value against the cited document.
    verified_by_author: bool = False
    notes: str = ""

    @field_validator("source")
    @classmethod
    def source_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Factor source cannot be empty. No hallucinations allowed.")
        return v

    @model_validator(mode="after")
    def _status_consistent(self) -> "Factor":
        if self.status == "cited" and (self.value is None or SOURCE_NEEDED in self.source):
            raise ValueError(f"{self.id}: a cited factor needs a value and a real source")
        if self.status == "SOURCE_NEEDED" and self.value is not None:
            raise ValueError(f"{self.id}: a factor without a source must not carry a value")
        return self


class MissingFactorError(LookupError):
    def __init__(self, missing: list[str]):
        super().__init__(f"factors unavailable: {missing}")
        self.missing = missing


class FactorTable:
    def __init__(self, factors: dict[str, Factor]):
        self.factors = factors

    def __contains__(self, fid: object) -> bool:
        return fid in self.factors

    def get(self, fid: str, unit: str) -> float:
        """Return a usable factor value, checking its unit; raise if unsourced or absent."""
        f = self.factors.get(fid)
        if f is None or f.value is None:
            raise MissingFactorError([fid])
        if f.unit != unit:
            raise ValueError(f"factor {fid} has unit {f.unit!r}, expected {unit!r}")
        return f.value

    def missing(self, ids: list[str]) -> list[str]:
        return [i for i in ids if i not in self.factors or self.factors[i].value is None]


def load_factors(yaml_path: str | Path) -> dict[str, Factor]:
    """Load one factor file, or every *.yaml file in a directory (sorted)."""
    path = Path(yaml_path)
    if not path.exists():
        return {}
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    out: dict[str, Factor] = {}
    for file in files:
        for item in yaml.safe_load(file.read_text(encoding="utf-8-sig")) or []:
            f = Factor(**item)
            if f.id in out:
                raise ValueError(f"duplicate factor id {f.id} in {file}")
            out[f.id] = f
    return out
