from mars.artifact import Artifact
from mars.config import Config
from mars.models import call_structured
from mars.roles import load_prompt
from mars.schemas import AdversarialOutput, PrimaryOutput

SYSTEM = load_prompt("adversarial")


def _prior_block(prior: list[AdversarialOutput]) -> str:
    if not prior:
        return ""
    lines = ["\n\nPRIOR-ROUND CRITIQUES (do NOT repeat these — produce NEW critiques):"]
    for round_idx, output in enumerate(prior, start=1):
        for c in output.critiques:
            lines.append(f"  [round {round_idx}] {c.claim}")
    return "\n".join(lines)


def run_adversarial(
    config: Config,
    artifact: Artifact,
    primary: PrimaryOutput,
    prior: list[AdversarialOutput],
) -> AdversarialOutput:
    user = (
        "ARTIFACT UNDER REVIEW:\n\n"
        + artifact.as_prompt_block()
        + "\n\nPRIMARY MODEL OUTPUT:\n"
        + primary.model_dump_json(indent=2)
        + _prior_block(prior)
    )
    return call_structured(
        provider=config.provider_for("adversarial"),
        model=config.model_for("adversarial"),
        system=SYSTEM,
        user=user,
        schema=AdversarialOutput,
    )
