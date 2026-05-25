"""Pydantic models for the structured (JSON) outputs of each role.

Using JSON output (not prose-header scraping) is what makes disposition tracking and
repetition detection reliable instead of best-effort.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"  # decision blocker
    major = "major"        # materially changes the recommendation
    minor = "minor"        # worth noting, not blocking


class Disposition(str, Enum):
    resolved = "resolved"
    refuted = "refuted"
    acceptable_risk = "acceptable_risk"
    unresolved = "unresolved"
    decision_blocker = "decision_blocker"
    requires_evidence = "requires_evidence"


class RecommendedAction(str, Enum):
    PROCEED = "PROCEED"
    PROCEED_WITH_CONDITION = "PROCEED_WITH_CONDITION"
    TEST_FIRST = "TEST_FIRST"
    ESCALATE = "ESCALATE"
    DEFER = "DEFER"
    DISCARD = "DISCARD"


class PrimaryOutput(BaseModel):
    framing: str
    recommendation: str
    tradeoffs: list[str]
    assumptions: list[str]
    uncertainty: list[str]


class Critique(BaseModel):
    id: str
    claim: str
    reasoning: str
    severity: Severity
    resolution: str  # what evidence/test would resolve it


class AdversarialOutput(BaseModel):
    critiques: list[Critique]
    missing_problem: str
    missing_assumption: str
    absent_stakeholder: str
    most_dangerous_certainty: str


class CompressedCritique(BaseModel):
    id: str
    summary: str
    disposition: Disposition
    discard_reason: str | None = None  # required when merged/discarded


class OrchestratorOutput(BaseModel):
    compressed_critiques: list[CompressedCritique]
    decision_blockers: list[str]
    unresolved_questions: list[str]
    recommended_action: RecommendedAction
    recommended_action_detail: str  # the required specifics for the chosen action
    strongest_ignored_objection: str
    operator_bias_direction: str
    new_critique_count: int = Field(
        description="How many critiques this round are genuinely new vs prior rounds."
    )
    repetition_detected: bool = Field(
        description="True if this round mostly repeats prior rounds (>~70% overlap)."
    )
