"""Refinement loop: primary builds, then [challenge -> rebuttal] x rounds, then synthesis.

Two frontier peers harden a vague idea into a watertight one. The primary builds,
the challenger pressure-tests, the primary defends/concedes/revises, and the improved
proposal carries into the next round. After the planned rounds, the orchestrator runs
once to synthesize the hardened idea for the operator. There is no winner, no verdict —
the output is the strengthened idea.
"""

from typing import Callable

from mars.artifact import Artifact
from mars.config import Config
from mars.roles.adversarial import run_adversarial
from mars.roles.orchestrator import run_orchestrator
from mars.roles.primary import run_primary, run_rebuttal
from mars.schemas import ChallengerOutput, RebuttalOutput
from mars.session import RoundRecord, SessionRecord, new_session

Progress = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def run_review(
    config: Config,
    artifact: Artifact,
    rounds: int,
    progress: Progress = _noop,
) -> SessionRecord:
    session = new_session(
        config_snapshot=config.model_dump(),
        artifact_dump=artifact.model_dump(),
    )
    session.add_log(f"Session {session.session_id} started. Planned rounds: {rounds}.")

    progress("Primary model building the idea...")
    primary = run_primary(config, artifact)
    session.primary = primary.model_dump(mode="json")
    session.add_log("Primary build complete.")

    current_proposal = primary.proposal
    history: list[tuple[ChallengerOutput, RebuttalOutput]] = []

    for r in range(1, rounds + 1):
        progress(f"Round {r}: peer challenge...")
        challenge = run_adversarial(config, artifact, current_proposal, history)

        progress(f"Round {r}: primary rebuttal...")
        rebuttal = run_rebuttal(config, artifact, current_proposal, challenge)
        current_proposal = rebuttal.updated_proposal

        history.append((challenge, rebuttal))
        session.rounds.append(
            RoundRecord(
                index=r,
                challenge=challenge.model_dump(mode="json"),
                rebuttal=rebuttal.model_dump(mode="json"),
            )
        )
        accepted = sum(1 for x in rebuttal.responses if x.stance.value in ("accept", "revise"))
        session.add_log(
            f"Round {r}: {len(challenge.challenges)} challenge(s), "
            f"{len(challenge.conceded)} conceded, {accepted} folded into the idea."
        )

    progress("Orchestrator synthesizing the hardened idea...")
    synthesis = run_orchestrator(config, artifact, primary, history)
    session.synthesis = synthesis.model_dump(mode="json")
    session.add_log("Synthesis complete.")

    session.stop_reason = f"Completed all {len(session.rounds)} planned round(s) of refinement."
    session.add_log(session.stop_reason)

    session.save()
    session.add_log(f"Session saved to ~/.mars/sessions/{session.session_id}.json")
    return session
