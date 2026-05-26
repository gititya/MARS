from mars.artifact import Artifact
from mars.config import Config
from mars.models import call_structured
from mars.roles import load_prompt
from mars.schemas import ChallengerOutput, PrimaryOutput, RebuttalOutput, SynthesisOutput

SYSTEM = load_prompt("orchestrator")


def run_orchestrator(
    config: Config,
    artifact: Artifact,
    primary: PrimaryOutput,
    rounds: list[tuple[ChallengerOutput, RebuttalOutput]],
) -> SynthesisOutput:
    """Single final pass: synthesize the hardened idea from the full transcript."""
    transcript = []
    for round_idx, (challenge, rebuttal) in enumerate(rounds, start=1):
        transcript.append(
            f"=== ROUND {round_idx} - CHALLENGE ===\n"
            + challenge.model_dump_json(indent=2)
            + f"\n\n=== ROUND {round_idx} - REBUTTAL ===\n"
            + rebuttal.model_dump_json(indent=2)
        )
    user = (
        "ORIGINAL ARTIFACT:\n\n"
        + artifact.as_prompt_block()
        + "\n\nPRIMARY'S INITIAL BUILD:\n"
        + primary.model_dump_json(indent=2)
        + "\n\n"
        + "\n\n".join(transcript)
    )
    return call_structured(
        provider=config.provider_for("orchestrator"),
        model=config.model_for("orchestrator"),
        system=SYSTEM,
        user=user,
        schema=SynthesisOutput,
    )
