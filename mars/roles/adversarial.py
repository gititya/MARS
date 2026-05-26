from mars.artifact import Artifact
from mars.config import Config
from mars.models import call_structured
from mars.roles import load_prompt
from mars.schemas import ChallengerOutput, RebuttalOutput

SYSTEM = load_prompt("adversarial")


def _history_block(prior: list[tuple[ChallengerOutput, RebuttalOutput]]) -> str:
    if not prior:
        return ""
    lines = [
        "\n\nPRIOR EXCHANGE (your earlier challenges and the primary's responses - "
        "concede what was genuinely resolved, do not re-litigate it):"
    ]
    for round_idx, (challenge, rebuttal) in enumerate(prior, start=1):
        lines.append(f"\n--- round {round_idx} ---")
        for c in challenge.challenges:
            lines.append(f"  [{c.id}] you raised: {c.concern}")
        for r in rebuttal.responses:
            lines.append(f"  [{r.challenge_id}] primary {r.stance.value}ed: {r.response}")
    return "\n".join(lines)


def run_adversarial(
    config: Config,
    artifact: Artifact,
    current_proposal: str,
    prior: list[tuple[ChallengerOutput, RebuttalOutput]],
) -> ChallengerOutput:
    user = (
        "ORIGINAL ARTIFACT:\n\n"
        + artifact.as_prompt_block()
        + "\n\nCURRENT PROPOSAL (pressure-test this version):\n"
        + current_proposal
        + _history_block(prior)
    )
    return call_structured(
        provider=config.provider_for("adversarial"),
        model=config.model_for("adversarial"),
        system=SYSTEM,
        user=user,
        schema=ChallengerOutput,
    )
