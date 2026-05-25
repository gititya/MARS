from mars.artifact import Artifact
from mars.config import Config
from mars.models import call_structured
from mars.roles import load_prompt
from mars.schemas import AdversarialOutput, OrchestratorOutput, PrimaryOutput

SYSTEM = load_prompt("orchestrator")


def run_orchestrator(
    config: Config,
    artifact: Artifact,
    primary: PrimaryOutput,
    all_rounds: list[AdversarialOutput],
) -> OrchestratorOutput:
    rounds_block = []
    for round_idx, output in enumerate(all_rounds, start=1):
        rounds_block.append(
            f"=== ADVERSARIAL ROUND {round_idx} ===\n" + output.model_dump_json(indent=2)
        )
    user = (
        "ARTIFACT UNDER REVIEW:\n\n"
        + artifact.as_prompt_block()
        + "\n\nPRIMARY MODEL OUTPUT:\n"
        + primary.model_dump_json(indent=2)
        + "\n\n"
        + "\n\n".join(rounds_block)
    )
    return call_structured(
        provider=config.provider_for("orchestrator"),
        model=config.model_for("orchestrator"),
        system=SYSTEM,
        user=user,
        schema=OrchestratorOutput,
    )
