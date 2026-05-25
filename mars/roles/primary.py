from mars.artifact import Artifact
from mars.config import Config
from mars.models import ModelError, call_structured
from mars.roles import load_prompt
from mars.schemas import ChallengerOutput, PrimaryOutput, RebuttalOutput

SYSTEM = load_prompt("primary")
REBUTTAL_SYSTEM = load_prompt("rebuttal")


def run_primary(config: Config, artifact: Artifact) -> PrimaryOutput:
    user = "ARTIFACT TO BUILD FROM:\n\n" + artifact.as_prompt_block()
    return call_structured(
        provider=config.provider_for("primary"),
        model=config.model_for("primary"),
        system=SYSTEM,
        user=user,
        schema=PrimaryOutput,
    )


def run_rebuttal(
    config: Config,
    artifact: Artifact,
    current_proposal: str,
    challenge: ChallengerOutput,
) -> RebuttalOutput:
    """Primary responds to a round of challenges and re-states the improved idea.

    Validates that the response addresses every challenge exactly once with no unknown
    or duplicate IDs — otherwise a dropped concern would silently vanish from the loop.
    Re-prompts once with the specific mismatch before failing.
    """
    expected = [c.id for c in challenge.challenges]
    base_user = (
        "ORIGINAL ARTIFACT:\n\n"
        + artifact.as_prompt_block()
        + "\n\nCURRENT PROPOSAL (your idea as it stands):\n"
        + current_proposal
        + "\n\nPEER CHALLENGES TO RESPOND TO:\n"
        + challenge.model_dump_json(indent=2)
    )
    user = base_user
    got: list[str] = []
    for _ in range(2):
        result = call_structured(
            provider=config.provider_for("primary"),
            model=config.model_for("primary"),
            system=REBUTTAL_SYSTEM,
            user=user,
            schema=RebuttalOutput,
        )
        got = [r.challenge_id for r in result.responses]
        if sorted(got) == sorted(expected) and len(set(got)) == len(got):
            return result
        user = (
            base_user
            + "\n\nYour previous response did not address each challenge exactly once. "
            + f"Respond to exactly these challenge_ids, one item each, no extras and no "
            + f"duplicates: {expected}. You returned: {got}."
        )
    raise ModelError(
        f"Rebuttal did not map one-to-one to the round's challenges after a retry. "
        f"Expected {expected}, got {got}."
    )
