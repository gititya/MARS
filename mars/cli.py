"""MARS CLI — Typer entrypoint."""

import typer
from rich.console import Console

from mars.artifact import ArtifactError, load_artifact
from mars.config import ConfigError, load_config
from mars.loop import run_review
from mars.models import estimate_cost
from mars.output import render_session, render_session_list
from mars.roles.adversarial import SYSTEM as ADVERSARIAL_SYSTEM
from mars.roles.orchestrator import SYSTEM as ORCHESTRATOR_SYSTEM
from mars.roles.primary import SYSTEM as PRIMARY_SYSTEM
from mars.session import load_session, list_sessions

app = typer.Typer(help="MARS — bounded adversarial review for ambitious cognitive work.", no_args_is_help=True)
session_app = typer.Typer(help="Inspect past review sessions.", no_args_is_help=True)
app.add_typer(session_app, name="session")

console = Console()
err = Console(stderr=True)


def _fail(message: str) -> None:
    err.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(code=1)


def _estimate(config, artifact, rounds: float) -> float:
    """Approximate: artifact tokens x rates x roles x rounds (per PRD)."""
    rounds = int(rounds)
    block = artifact.as_prompt_block()
    total = 0.0
    total += estimate_cost(
        config.model_for("primary"), config.provider_for("primary"),
        "primary", PRIMARY_SYSTEM + block,
    )
    for _ in range(rounds):
        total += estimate_cost(
            config.model_for("adversarial"), config.provider_for("adversarial"),
            "adversarial", ADVERSARIAL_SYSTEM + block,
        )
        total += estimate_cost(
            config.model_for("orchestrator"), config.provider_for("orchestrator"),
            "orchestrator", ORCHESTRATOR_SYSTEM + block,
        )
    return total


@app.command()
def run(
    artifact: str = typer.Option(..., "--artifact", help="Path to the artifact YAML."),
    config: str = typer.Option("config.yaml", "--config", help="Path to the config YAML."),
    rounds: int = typer.Option(None, "--rounds", help="Override rounds (1-4)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate + estimate cost only; no API calls."),
    yes: bool = typer.Option(False, "--yes", help="Skip the cost confirmation prompt."),
):
    """Run an adversarial review session."""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        _fail(str(e))
    try:
        art = load_artifact(artifact)
    except ArtifactError as e:
        _fail(str(e))

    n_rounds = rounds if rounds is not None else cfg.rounds.default
    if not (1 <= n_rounds <= cfg.rounds.max):
        _fail(f"--rounds must be between 1 and {cfg.rounds.max} (hard cap). Got {n_rounds}.")

    for w in art.scope_warnings():
        err.print(f"[yellow]Scope warning:[/yellow] {w}")

    est = _estimate(cfg, art, n_rounds)
    console.print(
        f"[bold]Plan:[/bold] {n_rounds} round(s) — "
        f"primary=[cyan]{cfg.provider_for('primary')}[/cyan], "
        f"adversarial=[cyan]{cfg.provider_for('adversarial')}[/cyan], "
        f"orchestrator=[cyan]{cfg.provider_for('orchestrator')}[/cyan]"
    )
    console.print(f"[bold]Estimated cost:[/bold] ~${est:.4f} (approximate; output tokens are budgeted)")

    if dry_run:
        console.print("[green]Dry run OK[/green] — config and artifact valid. No API calls made.")
        raise typer.Exit(code=0)

    if not yes:
        if not typer.confirm("Proceed with API calls?"):
            console.print("Aborted.")
            raise typer.Exit(code=0)

    try:
        with console.status("[bold]Running review...[/bold]") as status:
            session = run_review(
                cfg, art, n_rounds,
                progress=lambda msg: status.update(f"[bold]{msg}[/bold]"),
            )
    except Exception as e:
        _fail(str(e))

    render_session(session)


@session_app.command("show")
def session_show(session_id: str = typer.Argument(..., help="Session ID to display.")):
    """Render a past session."""
    try:
        session = load_session(session_id)
    except FileNotFoundError as e:
        _fail(str(e))
    render_session(session)


@session_app.command("list")
def session_list():
    """List past sessions."""
    render_session_list(list_sessions())


if __name__ == "__main__":
    app()
