"""Session management and human-readable JSON logging to ~/.mars/sessions/."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SESSIONS_DIR = Path.home() / ".mars" / "sessions"
OUTPUT_DIR = Path.home() / "Documents" / "Projects" / "MARS- output"


class RoundRecord(BaseModel):
    index: int
    challenge: dict[str, Any]
    rebuttal: dict[str, Any]


class SessionRecord(BaseModel):
    session_id: str
    timestamp: str
    config: dict[str, Any]
    artifact_hash: str
    artifact: dict[str, Any]
    primary: dict[str, Any] | None = None
    rounds: list[RoundRecord] = []
    synthesis: dict[str, Any] | None = None
    stop_reason: str | None = None
    log: list[str] = []

    def add_log(self, message: str) -> None:
        self.log.append(message)

    def save(self) -> Path:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self.model_dump(), indent=2)
        path = SESSIONS_DIR / f"{self.session_id}.json"
        path.write_text(data)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / f"{self.session_id}.json").write_text(data)
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
