"""Artifact schema and validation.

The system rejects vague prompts: all required fields must be present and non-empty
before any API call is made. Field-level errors tell the user exactly what is missing.
A scope check warns (does not block) if the input looks like a bug report / code diff /
one-line question - the wrong shape of work for this tool.
"""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, field_validator

# Per-field character limits - prevent prompt stuffing / token waste.
FIELD_CHAR_LIMIT = 8000

REQUIRED_FIELDS = (
    "goal",
    "artifact",
    "constraints",
    "assumptions",
    "fears",
    "tradeoffs",
    "context",
)
OPTIONAL_FIELDS = ("stakeholders", "decision")

# Scope-check signals: input that looks like the wrong kind of work.
_SCOPE_PATTERNS = (
    r"\bstack ?trace\b",
    r"\btraceback\b",
    r"^\s*[-+]{3}\s",          # diff header
    r"^\s*@@.*@@",             # diff hunk
    r"\bfix this bug\b",
    r"\bnull ?pointer\b",
    r"\bexception\b",
)


def _as_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


class Artifact(BaseModel):
    goal: str
    artifact: str
    constraints: str | list[str]
    assumptions: str | list[str]
    fears: str | list[str]
    tradeoffs: str | list[str]
    context: str
    stakeholders: str | list[str] | None = None
    decision: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _not_blank_and_bounded(cls, v, info):
        if v is None:
            return v
        text = _as_text(v).strip()
        if info.field_name in REQUIRED_FIELDS and not text:
            raise ValueError(f"required field '{info.field_name}' is empty")
        if len(text) > FIELD_CHAR_LIMIT:
            raise ValueError(
                f"field '{info.field_name}' is {len(text)} chars; limit is {FIELD_CHAR_LIMIT}"
            )
        return v

    def text(self, field: str) -> str:
        return _as_text(getattr(self, field))

    def as_prompt_block(self) -> str:
        """Render the artifact as a labelled text block for the model prompts."""
        lines = []
        for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            value = getattr(self, field)
            if value is None:
                continue
            lines.append(f"## {field.upper()}\n{self.text(field)}")
        return "\n\n".join(lines)

    def scope_warnings(self) -> list[str]:
        """Non-blocking warnings if the input looks like out-of-scope work."""
        warnings: list[str] = []
        blob = f"{self.goal}\n{self.artifact}"
        for pattern in _SCOPE_PATTERNS:
            if re.search(pattern, blob, flags=re.IGNORECASE | re.MULTILINE):
                warnings.append(
                    "Input resembles a bug report / code diff / error trace. MARS is for "
                    "high-ambiguity decisions, not bug fixes or routine implementation."
                )
                break
        if len(self.artifact.split()) < 12:
            warnings.append(
                "The 'artifact' field is very short - this tool expects a real proposal, "
                "PRD, or design to review, not a one-line question."
            )
        return warnings


class ArtifactError(ValueError):
    """Raised when an artifact file is missing required fields or violates limits."""


def load_artifact(path: str | Path) -> Artifact:
    path = Path(path)
    if not path.exists():
        raise ArtifactError(f"Artifact file not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ArtifactError("Artifact file must be a YAML mapping of fields.")

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise ArtifactError(
            "Artifact is missing required field(s): " + ", ".join(missing) + ". "
            "All of these are mandatory: " + ", ".join(REQUIRED_FIELDS) + "."
        )
    try:
        return Artifact.model_validate(data)
    except ValidationError as e:
        msgs = [err["msg"].removeprefix("Value error, ") for err in e.errors()]
        raise ArtifactError("; ".join(msgs)) from None
