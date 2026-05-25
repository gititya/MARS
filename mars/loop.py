"""Round loop: primary -> (adversarial -> orchestrator) x rounds, with stop conditions.

The final round's orchestrator output IS the synthesis (Phase 4 and Phase 6 are merged —
no separate synthesis call). Repetition is judged by the orchestrator itself, which sees
all rounds and emits new_critique_count / repetition_detected.
"""

from typing import Callable

from mars.artifact import Artifact
from mars.config import Config
from mars.roles.adversarial import run_adversarial
from mars.roles.orchestrator import run_orchestrator
from mars.roles.primary import run_primary
from mars.schemas import AdversarialOutput
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

    progress("Primary model generating proposal...")
    primary = run_primary(config, artifact)
    session.primary = primary.model_dump(mode="json")
    session.add_log("Primary generation complete.")

    prior_adversarial: list[AdversarialOutput] = []

    for r in range(1, rounds + 1):
        progress(f"Round {r}: adversarial review...")
        adversarial = run_adversarial(config, artifact, primary, prior_adversarial)
        prior_adversarial.append(adversarial)

        progress(f"Round {r}: orchestrator compression...")
        orchestrator = run_orchestrator(config, artifact, primary, prior_adversarial)

        session.rounds.append(
            RoundRecord(
                index=r,
                adversarial=adversarial.model_dump(mode="json"),
                orchestrator=orchestrator.model_dump(mode="json"),
            )
        )
        session.add_log(
            f"Round {r}: {len(adversarial.critiques)} critiques, "
            f"new_critique_count={orchestrator.new_critique_count}, "
            f"repetition_detected={orchestrator.repetition_detected}."
        )

        if r < rounds:
            if orchestrator.repetition_detected:
                session.stop_reason = (
                    f"Early termination after round {r}: orchestrator flagged repetition "
                    f"(>~70% overlap with prior rounds)."
                )
                session.add_log(session.stop_reason)
                break
            if orchestrator.new_critique_count == 0:
                session.stop_reason = (
                    f"Early termination after round {r}: no new critiques produced."
                )
                session.add_log(session.stop_reason)
                break

    if session.stop_reason is None:
        session.stop_reason = f"Completed all {len(session.rounds)} planned round(s)."
        session.add_log(session.stop_reason)

    session.save()
    session.add_log(f"Session saved to ~/.mars/sessions/{session.session_id}.json")
    return session
