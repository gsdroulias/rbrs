"""Pass 1 (stochastic): Gemini with schema-constrained JSON output (FR-02).

The raw response and token usage are archived next to the parsed record so the
run can be audited and re-verified without calling the model again.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from google import genai
from google.genai import types

from rbrs.extraction.schema import RESPONSE_SCHEMA
from rbrs.profile.models import ExtractedField, ExtractionRecord, Provenance


@dataclass(frozen=True)
class ExtractionConfig:
    model_id: str
    prompt: str
    thinking_level: str | None = None
    media_resolution: str | None = None
    runs: int = 3
    abstention_threshold: float | None = None
    target_precision: float = 0.95
    numeric_rel_tol: float = 0.001

    @classmethod
    def load(cls, path: str | Path = "config/extraction.yaml") -> "ExtractionConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(**data)

    @property
    def prompt_version(self) -> str:
        return Path(self.prompt).stem

    def require_pinned(self) -> None:
        if not self.model_id or self.model_id == "SET_ME":
            raise RuntimeError("set model_id in config/extraction.yaml to a pinned Gemini model ID")


def call_gemini(
    contents: list[Any], cfg: ExtractionConfig, client: Any | None = None
) -> tuple[str, dict[str, int | None]]:
    cfg.require_pinned()
    client = client or genai.Client()  # reads GEMINI_API_KEY from the environment
    config_kwargs: dict[str, Any] = {
        "response_mime_type": "application/json",
        "response_json_schema": RESPONSE_SCHEMA,
    }
    if cfg.thinking_level:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=cfg.thinking_level)
    if cfg.media_resolution:
        config_kwargs["media_resolution"] = cfg.media_resolution
    resp = client.models.generate_content(
        model=cfg.model_id,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    if not resp.text:
        raise ValueError("empty response from the model")
    u = resp.usage_metadata
    usage = {
        "prompt": getattr(u, "prompt_token_count", None),
        "output": getattr(u, "candidates_token_count", None),
        "thinking": getattr(u, "thoughts_token_count", None),
        "cached": getattr(u, "cached_content_token_count", None),
    }
    return str(resp.text), usage


def parse_response(
    text: str, document_id: str, cfg: ExtractionConfig, usage: dict[str, int | None]
) -> ExtractionRecord:
    """Turn the model's JSON into an ExtractionRecord. Malformed items are kept as
    abstentions with a note, never dropped silently."""
    data = json.loads(text)
    fields: list[ExtractedField] = []
    for item in data.get("fields", []):
        name = str(item.get("field", ""))
        conf = min(max(float(item.get("confidence") or 0.0), 0.0), 1.0)
        status = item.get("status")
        quote, page = item.get("quote"), item.get("page")
        if status == "EXTRACTED" and item.get("value") is not None and quote and isinstance(page, int) and page >= 1:
            fields.append(
                ExtractedField(
                    field=name,
                    value=item["value"],
                    status="EXTRACTED",
                    confidence=conf,
                    provenance=Provenance(page=page, section=item.get("section"), quote=quote),
                )
            )
        else:
            note = None if status == "ABSTAINED" else "model output lacked value, page or quote"
            fields.append(ExtractedField(field=name, status="ABSTAINED", confidence=conf, verification_note=note))
    return ExtractionRecord(
        document_id=document_id,
        method="llm",
        model_id=cfg.model_id,
        prompt_version=cfg.prompt_version,
        fields=fields,
        usage=usage,
    )


def extract_pdf(
    pdf_path: str | Path,
    document_id: str,
    cfg: ExtractionConfig,
    archive_dir: str | Path,
    run: int = 1,
    client: Any | None = None,
) -> ExtractionRecord:
    """Pass 1 for one PDF. Writes <archive_dir>/run<k>.response.json (raw)."""
    prompt = Path(cfg.prompt).read_text(encoding="utf-8")
    pdf = Path(pdf_path).read_bytes()
    contents: list[Any] = [types.Part.from_bytes(data=pdf, mime_type="application/pdf"), prompt]
    text, usage = call_gemini(contents, cfg, client)
    archive = Path(archive_dir)
    archive.mkdir(parents=True, exist_ok=True)
    (archive / f"run{run}.response.json").write_text(
        json.dumps(
            {"model_id": cfg.model_id, "prompt_version": cfg.prompt_version, "usage": usage, "response_text": text},
            indent=2,
        ),
        encoding="utf-8",
    )
    return parse_response(text, document_id, cfg, usage)
