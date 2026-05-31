"""Session management and human-readable JSON logging to ~/.mars/sessions/."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SESSIONS_DIR = Path.home() / ".mars" / "sessions"
OUTPUT_DIR = Path.home() / "Documents" / "Projects" / "MARS- output"

_STANCE_LABEL = {"accept": "Accept", "revise": "Revise", "defend": "Defend"}


def _slug(text: str, max_words: int = 6) -> str:
    words = re.sub(r"[^a-z0-9 ]", "", text.lower().strip()).split()
    return "-".join(words[:max_words])


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "_none_"


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

    def md_filename(self) -> str:
        date = self.session_id[:8]
        time = self.session_id[9:15]
        goal = self.artifact.get("goal", "")
        slug = _slug(goal) or self.session_id
        return f"{date}-{time}-{slug}.md"

    def to_markdown(self) -> str:
        a = self.artifact
        goal = a.get("goal", "")
        date_str = self.timestamp[:10]
        n_rounds = len(self.rounds)
        providers = self.config.get("providers", {})
        roles = self.config.get("roles", {})

        def _model(role: str) -> str:
            provider = roles.get(role, "")
            return providers.get(provider, {}).get("model", provider or "—")

        p_model = _model("primary")
        a_model = _model("adversarial")
        o_model = _model("orchestrator")

        lines: list[str] = []

        # --- header ---
        lines += [
            f"# MARS Adversarial Review",
            f"",
            f"> **What this is:** MARS runs a two-model adversarial loop on your idea. A *Primary* model",
            f"> builds a structured proposal; an *Adversarial* model challenges it with hard questions;",
            f"> the Primary rebuts each challenge; and an *Orchestrator* synthesises the hardened result.",
            f"> The output below is the complete record of that loop.",
            f"",
            f"| | |",
            f"|---|---|",
            f"| **Date** | {date_str} |",
            f"| **Session ID** | `{self.session_id}` |",
            f"| **Rounds** | {n_rounds} |",
            f"| **Primary model** | {p_model} |",
            f"| **Adversarial model** | {a_model} |",
            f"| **Orchestrator model** | {o_model} |",
            f"",
            f"---",
            f"",
        ]

        # --- your input ---
        lines += ["## Your Input", ""]
        lines += [f"**Goal**\n\n{goal}", ""]
        if a.get("artifact"):
            lines += [f"**Artifact**\n\n{a['artifact']}", ""]
        for field, label in [
            ("constraints", "Constraints"),
            ("assumptions", "Assumptions"),
            ("fears", "Fears"),
            ("tradeoffs", "Tradeoffs"),
            ("context", "Context"),
            ("stakeholders", "Stakeholders"),
            ("decision", "Decision"),
        ]:
            val = a.get(field)
            if val:
                lines += [f"**{label}**\n\n{val}", ""]
        lines += ["---", ""]

        # --- primary build ---
        if self.primary:
            p = self.primary
            lines += ["## Primary Build", ""]
            lines += [f"**Framing**\n\n{p.get('framing', '')}", ""]
            lines += [f"**Proposal**\n\n{p.get('proposal', '')}", ""]
            if p.get("key_choices"):
                lines += [f"**Key choices**\n\n{_bullets(p['key_choices'])}", ""]
            if p.get("assumptions"):
                lines += [f"**Assumptions**\n\n{_bullets(p['assumptions'])}", ""]
            if p.get("open_questions"):
                lines += [f"**Open questions**\n\n{_bullets(p['open_questions'])}", ""]
            lines += ["---", ""]

        # --- rounds ---
        for rnd in self.rounds:
            ch = rnd.challenge
            reb = rnd.rebuttal

            lines += [f"## Round {rnd.index} — Adversarial Challenge", ""]
            lines += ["| Concern | Why it matters | Suggestion |", "|---|---|---|"]
            for c in ch.get("challenges", []):
                concern = c.get("concern", "").replace("|", "\\|").replace("\n", " ")
                why = c.get("why_it_matters", "").replace("|", "\\|").replace("\n", " ")
                suggestion = c.get("suggestion", "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {concern} | {why} | {suggestion} |")
            lines += [""]
            if ch.get("biggest_risk"):
                lines += [f"**Biggest risk:** {ch['biggest_risk']}", ""]
            if ch.get("conceded"):
                lines += [f"**Conceded from prior round**\n\n{_bullets(ch['conceded'])}", ""]
            lines += [""]

            lines += [f"## Round {rnd.index} — Primary Rebuttal", ""]
            lines += ["| Stance | Response |", "|---|---|"]
            for r in reb.get("responses", []):
                stance = _STANCE_LABEL.get(r.get("stance", ""), r.get("stance", ""))
                response = r.get("response", "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| **{stance}** | {response} |")
            lines += ["", "---", ""]

        # --- synthesis ---
        if self.synthesis:
            s = self.synthesis
            lines += ["## Hardened Idea", ""]
            lines += [f"{s.get('hardened_idea', '')}", ""]
            if s.get("what_got_stronger"):
                lines += [f"**What got stronger**\n\n{_bullets(s['what_got_stronger'])}", ""]
            if s.get("open_decisions"):
                lines += [f"**Open decisions (your call)**\n\n{_bullets(s['open_decisions'])}", ""]
            if s.get("watch_items"):
                lines += [f"**Watch items**\n\n{_bullets(s['watch_items'])}", ""]
            lines += ["---", ""]

        if self.stop_reason:
            lines += [f"_Stop reason: {self.stop_reason}_", ""]

        return "\n".join(lines)

    def save(self) -> Path:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{self.session_id}.json"
        path.write_text(json.dumps(self.model_dump(), indent=2))
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / self.md_filename()).write_text(self.to_markdown())
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
