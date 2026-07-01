"""Pydantic models for the structured (JSON) outputs of each role.

Using JSON output (not prose-header scraping) is what makes the rebuttal loop and
synthesis reliable instead of best-effort. The flow is constructive: the primary
builds an idea, the challenger stress-tests it to make it watertight, the primary
defends or revises, and the orchestrator synthesizes the hardened result.
"""

from enum import Enum

from pydantic import BaseModel


class Stance(str, Enum):
    accept = "accept"    # the challenge is right; fold the fix into the idea
    revise = "revise"    # partially right; adjust the idea accordingly
    defend = "defend"    # the idea holds; explain why, with reasoning


class PrimaryOutput(BaseModel):
    """The primary model's initial build of the idea."""
    framing: str              # the idea restated sharper than it came in
    proposal: str             # the built-out idea: how it would actually work
    key_choices: list[str]    # the consequential decisions this build commits to
    assumptions: list[str]    # what must hold for the build to stand
    open_questions: list[str] # what is still vague and needs resolving


class Challenge(BaseModel):
    id: str
    concern: str       # the genuine weakness, stated honestly
    why_it_matters: str
    suggestion: str    # constructive: how to strengthen or resolve it
    reopens: list[str] = []  # prior challenge id(s) this concern continues/deepens; [] if genuinely new


class ConcessionStatus(str, Enum):
    resolved = "resolved"  # verified to survive the operator's real constraints
    partial = "partial"    # real progress, but something specific is still open


class Concession(BaseModel):
    challenge_id: str
    status: ConcessionStatus
    justification: str  # the specific mechanism checked, not "now addressed"


class ChallengerOutput(BaseModel):
    """The peer challenger's pass at the current proposal."""
    challenges: list[Challenge]
    concessions: list[Concession] = []  # prior-round points graded resolved/partial (empty round 1)
    biggest_risk: str    # the single most important thing to get right


class RebuttalItem(BaseModel):
    challenge_id: str
    stance: Stance
    response: str  # the reasoning behind the stance


class RebuttalOutput(BaseModel):
    """The primary model's response to a round of challenges."""
    responses: list[RebuttalItem]
    updated_proposal: str  # the idea after folding in accepted/revised points


class SynthesisOutput(BaseModel):
    """The orchestrator's final delivery to the operator: the hardened idea."""
    hardened_idea: str            # the watertight version, the deliverable
    what_got_stronger: list[str]  # concrete improvements the debate produced
    open_decisions: list[str]     # calls that genuinely need the operator's judgment
    watch_items: list[str]        # residual risks to keep an eye on while building
