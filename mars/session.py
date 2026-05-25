"""Session management and human-readable JSON logging to ~/.mars/sessions/."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SESSIONS_DIR = Path.home() / ".mars" / "sessions"


class RoundRecord(BaseModel):
    index: int
    adversarial: dict[str, Any]
    orchestrator: dict[str, Any]


class SessionRecord(BaseModel):
    session_id: str
    timestamp: str
    config: dict[str, Any]
    artifact_hash: str
    artifact: dict[str, Any]
    primary: dict[str, Any] | None = None
    rounds: list[RoundRecord] = []
    stop_reason: str | None = None
    log: list[str] = []

    def add_log(self, message: str) -> None:
        self.log.append(message)

    @property
    def final_orchestrator(self) -> dict[str, Any] | None:
        return self.rounds[-1].orchestrator if self.rounds else None

    def save(self) -> Path:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{self.session_id}.json"
        path.write_text(json.dumps(self.model_dump(), indent=2))
        return path


def new_session(config_snapshot: dict, artifact_dump: dict) -> SessionRecord:
    now = datetime.now(timezone.utc)
    session_id = now.strftime("%Y%m%dT%H%M%SZ")
    artifact_hash = hashlib.sha256(
        json.dumps(artifact_dump, sort_keys=True).encode()
    ).hexdigest()[:12]
    return SessionRecord(
        session_id=session_id,
        timestamp=now.isoformat(),
        config=config_snapshot,
        artifact_hash=artifact_hash,
        artifact=artifact_dump,
    )


def load_session(session_id: str) -> SessionRecord:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No session found with id '{session_id}' at {path}")
    return SessionRecord.model_validate_json(path.read_text())


def list_sessions() -> list[SessionRecord]:
    if not SESSIONS_DIR.exists():
        return []
    records = []
    for path in sorted(SESSIONS_DIR.glob("*.json")):
        try:
            records.append(SessionRecord.model_validate_json(path.read_text()))
        except Exception:
            continue
    return records
