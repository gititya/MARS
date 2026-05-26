"""MARS CLI - Typer entrypoint."""

import typer
from rich.console import Console

from mars.artifact import ArtifactError, load_artifact
from mars.config import ConfigError, load_config
from mars.keys import PROVIDER_ENV, add_command, load_keys
from mars.loop import run_review
from mars.models import estimate_cost
from mars.output import render_session, render_session_list
from mars.roles.adversarial import SYSTEM as ADVERSARIAL_SYSTEM
from mars.roles.orchestrator import SYSTEM as ORCHESTRATOR_SYSTEM
from mars.roles.primary import REBUTTAL_SYSTEM, SYSTEM as PRIMARY_SYSTEM
from mars.session import load_session, list_sessions

app = typer.Typer(help="MARS - two frontier models refine a vague idea into a watertight one.", no_args_is_help=True)
session_app = typer.Typer(help="Inspect past refinement sessions.", no_args_is_help=True)
keys_app = typer.Typer(help="Check which provider API keys MARS can find.", no_args_is_help=True)
app.add_typer(session_app, name="session")
app.add_typer(keys_app, name="keys")

console = Console()
err = Console(stderr=True)


def _fail(message: str) -> None:
    err.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(code=1)


def _estimate(config, artifact, rounds: float) -> float:
    """Approximate: primary build + rounds x (challenge + rebuttal) + one synthesis."""
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
            "challenger", ADVERSARIAL_SYSTEM + block,
        )
        total += estimate_cost(
            config.model_for("primary"), config.provider_for("primary"),
            "rebuttal", REBUTTAL_SYSTEM + block,
        )
    total += estimate_cost(
        config.model_for("orchestrator"), config.provider_for("orchestrator"),
        "synthesis", ORCHESTRATOR_SYSTEM + block,
    )
    return total


@app.command()
def setup():
    """Interactive first-time setup: configure providers, assign roles, and build an artifact."""
    from mars.setup_wizard import run_setup
    run_setup()


@app.command()
def run(
    artifact: str = typer.Option(..., "--artifact", help="Path to the artifact YAML."),
    config: str = typer.Option("config.yaml", "--config", help="Path to the config YAML."),
    rounds: int = typer.Option(None, "--rounds", help="Override rounds (1-4)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate + estimate cost only; no API calls."),
    yes: bool = typer.Option(False, "--yes", help="Skip the cost confirmation prompt."),
):
    """Run an idea-refinement session."""
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
        f"[bold]Plan:[/bold] {n_rounds} round(s) - "
        f"primary=[cyan]{cfg.provider_for('primary')}[/cyan], "
        f"adversarial=[cyan]{cfg.provider_for('adversarial')}[/cyan], "
        f"orchestrator=[cyan]{cfg.provider_for('orchestrator')}[/cyan]"
    )
    console.print(
        f"[bold]Estimated cost:[/bold] ≥ ${est:.4f} "
        f"(lower bound - excludes the growing transcript each round carries forward; "
        f"actual rises with rounds)"
    )

    if dry_run:
        console.print("[green]✓ Config and artifact valid.[/green]")
        from mars.setup_wizard import _validate_key
        used_providers = {cfg.provider_for(r) for r in ("primary", "adversarial", "orchestrator")}
        load_keys(cfg)
        all_ok = True
        with console.status("Checking API keys..."):
            for p in used_providers:
                ok, msg = _validate_key(p)
                console.print(f"  {msg}")
                if not ok:
                    all_ok = False
        if not all_ok:
            from mars.keys import update_command
            for p in used_providers:
                ok, _ = _validate_key(p)
                if not ok:
                    env_name = PROVIDER_ENV.get(p, p.upper() + "_API_KEY")
                    err.print(f"  Update: {update_command(env_name)}")
            _fail("Key validation failed. Fix the issue above and retry.")
        raise typer.Exit(code=0)

    key_status = load_keys(cfg)
    used = {cfg.provider_for(r) for r in ("primary", "adversarial", "orchestrator")}
    missing = [p for p, src in key_status.items() if src == "missing" and p in used]
    if missing:
        lines = [f"No API key found (shell env or Keychain) for: {', '.join(missing)}."]
        for p in missing:
            lines.append(f"  add it with: {add_command(PROVIDER_ENV.get(p, p.upper() + '_API_KEY'))}")
        _fail("\n".join(lines))

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


@keys_app.command("status")
def keys_status(config: str = typer.Option("config.yaml", "--config", help="Path to the config YAML.")):
    """Show which configured providers have a key MARS can find. Values are never printed."""
    try:
        cfg = load_config(config)
    except ConfigError as e:
        _fail(str(e))

    status = load_keys(cfg)
    from rich.table import Table

    table = Table(show_header=True, header_style="bold")
    table.add_column("Provider")
    table.add_column("Keychain service")
    table.add_column("Source")
    label = {
        "env": "[green]shell env[/green]",
        "keychain": "[green]keychain[/green]",
        "missing": "[red]missing[/red]",
    }
    for provider, src in status.items():
        env_name = PROVIDER_ENV.get(provider, provider.upper() + "_API_KEY")
        table.add_row(provider, env_name, label.get(src, src))
    console.print(table)

    missing = [p for p, src in status.items() if src == "missing"]
    for p in missing:
        env_name = PROVIDER_ENV.get(p, p.upper() + "_API_KEY")
        console.print(f"[dim]To add {p}: {add_command(env_name)}[/dim]")


if __name__ == "__main__":
    app()
