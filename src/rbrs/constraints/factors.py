from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class Factor(BaseModel):
    id: str
    value: float
    unit: str
    source: str

    @field_validator("source")
    def source_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Factor source cannot be empty. No hallucinations allowed.")
        return v

def load_factors(yaml_path: str | Path) -> dict[str, Factor]:
    path = Path(yaml_path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return {item["id"]: Factor(**item) for item in data}
