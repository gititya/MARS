from mars.artifact import Artifact
from mars.config import Config
from mars.models import call_structured
from mars.roles import load_prompt
from mars.schemas import PrimaryOutput

SYSTEM = load_prompt("primary")


def run_primary(config: Config, artifact: Artifact) -> PrimaryOutput:
    user = "ARTIFACT UNDER REVIEW:\n\n" + artifact.as_prompt_block()
    return call_structured(
        provider=config.provider_for("primary"),
        model=config.model_for("primary"),
        system=SYSTEM,
        user=user,
        schema=PrimaryOutput,
    )
