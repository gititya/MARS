"""Interactive setup wizard: configure providers, assign roles, build an artifact, run."""

import getpass
import os
import subprocess
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from mars.config import MAX_ROUNDS
from mars.keys import KEYCHAIN_ACCOUNT, PROVIDER_ENV, keychain_get

console = Console()

SUPPORTED_PROVIDERS = ["anthropic", "openai", "gemini"]

# (model_id, display label)
FRONTIER_MODELS = {
    "anthropic": ("claude-opus-4-7",                 "Claude Opus 4.7          — frontier, strongest reasoning"),
    "openai":    ("gpt-5.5",                          "GPT-5.5                  — OpenAI frontier"),
    "gemini":    ("gemini/gemini-3.1-pro-preview",    "Gemini 3.1 Pro Preview   — Google frontier"),
}
FIELD_HINTS = {
    "goal":        "the decision being made",
    "artifact":    "your proposal, PRD, or plan",
    "constraints": "hard limits and non-negotiables",
    "assumptions": "what you currently believe to be true",
    "fears":       "where you think the risk is",
    "tradeoffs":   "what you have already weighed",
    "context":     "who uses this and what system it lives in",
}

_STEP_COLORS = {1: "cyan1", 2: "green3", 3: "gold1"}


def _panel(step: int, title: str, body: str) -> Panel:
    color = _STEP_COLORS[step]
    return Panel(
        body,
        title=f"[bold {color}][{step}/3]  {title}[/bold {color}]",
        border_style=color,
        padding=(1, 2),
    )


def _keychain_store(env_name: str, value: str) -> bool:
    # Delete first (ignore failure if not found), then add fresh — more reliable than -U
    subprocess.run(
        ["security", "delete-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", env_name],
        capture_output=True,
    )
    result = subprocess.run(
        ["security", "add-generic-password", "-a", KEYCHAIN_ACCOUNT, "-s", env_name, "-w", value],
        capture_output=True,
    )
    return result.returncode == 0


def _read_file(path_str: str) -> tuple[str | None, str | None]:
    path = Path(path_str.strip())
    if not path.exists():
        return None, f"File not found: {path}"
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            if not text:
                return None, "PDF appears empty or image-only (no extractable text)."
            return text, None
        except ImportError:
            return None, "pypdf is not installed. Run: pip install 'pypdf~=4.0'"
    if suffix in (".html", ".htm"):
        from html.parser import HTMLParser
        class _Stripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self._parts: list[str] = []
            def handle_data(self, data: str) -> None:
                self._parts.append(data)
        s = _Stripper()
        s.feed(path.read_text(encoding="utf-8", errors="replace"))
        text = " ".join(s._parts).strip()
        return (text, None) if text else (None, "HTML appears empty.")
    if suffix in (".md", ".txt", ".yaml", ".yml"):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        return (text, None) if text else (None, "File is empty.")
    return None, f"Unsupported type '{suffix}'. Supported: .pdf  .html  .md  .txt"


def _edit_field(label: str, hint: str) -> str:
    """Multiline terminal input — Enter for new lines, Ctrl+D to submit."""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    kb = KeyBindings()

    @kb.add("c-d")
    def _submit(event):
        event.current_buffer.validate_and_handle()

    style = Style.from_dict({"prompt": "ansicyan bold"})

    console.print(f"\n  [bold]{label}[/bold] — [dim]{hint}[/dim]")
    console.print("  [dim]Enter for new lines. Ctrl+D when done.[/dim]")
    text = pt_prompt("  > ", multiline=True, key_bindings=kb, style=style)
    return text.strip()


def _pick_role(label: str, providers: list[str], model_tier: dict) -> tuple[str, str]:
    """Numbered menu showing provider + model. Returns (provider, model_id)."""
    console.print(f"\n  [bold]{label}[/bold]")
    for i, p in enumerate(providers, 1):
        model_id, model_label = model_tier[p]
        console.print(f"    {i}. [cyan]{p}[/cyan]  {model_label}")
    num_choices = [str(i) for i in range(1, len(providers) + 1)]
    idx = Prompt.ask("  Choice", choices=num_choices, show_choices=True)
    chosen = providers[int(idx) - 1]
    model_id, _ = model_tier[chosen]
    console.print(f"  [green]→ {chosen} / {model_id}[/green]")
    return chosen, model_id


def _pick(label: str, options: list[str]) -> str:
    """Numbered menu — user types 1/2/3, never a free-form provider name."""
    console.print(f"\n  [bold]{label}[/bold]")
    for i, opt in enumerate(options, 1):
        console.print(f"    {i}. {opt}")
    num_choices = [str(i) for i in range(1, len(options) + 1)]
    idx = Prompt.ask("  Choice", choices=num_choices, show_choices=True)
    chosen = options[int(idx) - 1]
    console.print(f"  [green]→ {chosen}[/green]")
    return chosen


def _step1() -> tuple[dict, dict, dict]:
    console.print(_panel(
        1, "What is MARS",
        "MARS refines a vague idea into a watertight one with two frontier models.\n"
        "One builds the idea. A peer from a different provider pressure-tests it.\n"
        "The first defends or revises, and a third synthesizes the hardened result.\n\n"
        "[bold]Privacy:[/bold] your artifact is only sent to the providers you configure here.\n"
        "Sessions are saved locally at [dim]~/.mars/sessions/[/dim]. Nothing else leaves your machine.",
    ))
    console.print()

    # Key status
    console.print("[bold cyan1]API keys[/bold cyan1]")
    key_status: dict[str, str] = {}
    for p in SUPPORTED_PROVIDERS:
        env_name = PROVIDER_ENV.get(p, p.upper() + "_API_KEY")
        val = keychain_get(env_name)
        if val:
            key_status[p] = "keychain"
        elif os.environ.get(env_name):
            key_status[p] = "env"
        else:
            key_status[p] = "missing"

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("p", style="bold")
    t.add_column("s")
    for p, src in key_status.items():
        label = f"[green]✓ {src}[/green]" if src != "missing" else "[red]✗ missing[/red]"
        t.add_row(p, label)
    console.print(t)
    console.print()

    for p in SUPPORTED_PROVIDERS:
        if key_status[p] == "missing":
            env_name = PROVIDER_ENV.get(p, p.upper() + "_API_KEY")
            if Confirm.ask(f"Add [bold]{p}[/bold] key now?", default=False):
                key_val = getpass.getpass(f"  {env_name}: ")
                if key_val.strip():
                    if _keychain_store(env_name, key_val.strip()):
                        key_status[p] = "keychain"
                        console.print("  [green]Stored in Keychain.[/green]")
                    else:
                        console.print("  [red]Keychain write failed.[/red]")

    available = [p for p in SUPPORTED_PROVIDERS if key_status[p] != "missing"]
    if len(available) < 2:
        console.print("\n[red]Need keys for at least 2 providers. Add them and re-run setup.[/red]")
        raise SystemExit(1)

    # Role assignment
    console.print("[bold cyan1]Assign roles[/bold cyan1]")

    primary, primary_model = _pick_role(
        "Primary (builder) — put a frontier model here; it builds and revises the idea",
        available, FRONTIER_MODELS,
    )
    adv_opts = [p for p in available if p != primary]
    adversarial, adversarial_model = _pick_role(
        "Challenger (peer) — must differ from primary; use your other frontier model",
        adv_opts, FRONTIER_MODELS,
    )
    orchestrator, orchestrator_model = _pick_role(
        "Orchestrator — synthesizes the hardened idea (your deliverable); keep it strong",
        available, FRONTIER_MODELS,
    )

    # Rounds
    console.print()
    console.print("[bold cyan1]Rounds[/bold cyan1]")
    console.print(
        "[dim]Each round: the peer challenges the idea, then the primary defends or revises it.\n"
        "The idea gets tighter each round. More rounds = deeper refinement + higher cost.\n"
        "2 is a good default. Hard cap is 4.[/dim]"
    )
    raw = Prompt.ask("How many rounds?", choices=["1", "2", "3", "4"], default="2", show_choices=True)
    rounds_int = int(raw)

    role_models = {primary: primary_model, adversarial: adversarial_model, orchestrator: orchestrator_model}
    providers_cfg = {p: {"model": role_models.get(p, FRONTIER_MODELS[p][0])} for p in available}
    roles_cfg = {"primary": primary, "adversarial": adversarial, "orchestrator": orchestrator}
    rounds_cfg = {"default": rounds_int, "max": MAX_ROUNDS}
    return providers_cfg, roles_cfg, rounds_cfg


def _step2() -> Path:
    console.print(_panel(
        2, "Your artifact",
        "An artifact is the idea or plan you want refined.\n"
        "Answer 7 questions. Longer answers produce a sharper refinement.\n\n"
        "For the [bold]artifact[/bold] field you can load from a file\n"
        "(.pdf  .html  .md  .txt) instead of typing.",
    ))

    data: dict = {}
    for field, hint in FIELD_HINTS.items():
        if field == "artifact":
            console.print(f"\n  [bold]artifact[/bold] — [dim]{hint}[/dim]")
            if Confirm.ask("  Load from file?", default=False):
                console.print("  [dim]Tip: drag a file onto this window to paste its path.[/dim]")
                sections: list[str] = []
                file_num = 1
                while True:
                    console.print(f"\n  [bold]File {file_num}[/bold]")
                    raw_path = Prompt.ask("  Path (.pdf / .html / .md / .txt)").strip()
                    text, err_msg = _read_file(raw_path)
                    if err_msg:
                        console.print(f"  [red]{err_msg}[/red]")
                        continue
                    if not text:
                        console.print("  [red]File was empty.[/red]")
                        continue
                    label = Prompt.ask("  What is this file for?").strip()
                    header = f"[{label}]" if label else f"[File {file_num}: {Path(raw_path).name}]"
                    sections.append(f"{header}\n{text}")
                    console.print(f"  [green]✓ Loaded {len(text)} chars from {Path(raw_path).name}[/green]")
                    file_num += 1
                    if not Confirm.ask("  Add another file?", default=False):
                        break
                combined = "\n\n---\n\n".join(sections)
                if len(combined) > 8000:
                    combined = combined[:8000]
                    console.print("  [yellow]Truncated to 8000 chars (field limit).[/yellow]")
                data[field] = combined
            else:
                data[field] = _edit_field("artifact", hint)
        else:
            data[field] = _edit_field(field, hint)

    console.print()
    out_str = Prompt.ask("Save artifact as", default="my-idea.yaml")
    out_path = Path(out_str)
    out_path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))
    console.print(f"[green]Saved to {out_path}[/green]")
    return out_path


# Cheapest model per provider for key validation — 1-token ping, near-zero cost
_VALIDATION_MODELS = {
    "anthropic": "anthropic/claude-haiku-4-5-20251001",
    "openai":    "openai/gpt-4o-mini",
    "gemini":    "gemini/gemini-2.0-flash-lite",
}


def _validate_key(provider: str) -> tuple[bool, str]:
    """Make a 1-token completion to confirm key is valid and has credits.
    Returns (ok, message).
    """
    import litellm
    model = _VALIDATION_MODELS.get(provider, f"{provider}/default")
    try:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return True, f"[green]✓ {provider}[/green] — key valid, credits available"
    except litellm.AuthenticationError as e:
        return False, f"[red]✗ {provider}[/red] — key rejected (invalid or revoked): {e.message if hasattr(e, 'message') else str(e)}"
    except litellm.RateLimitError:
        return False, f"[red]✗ {provider}[/red] — key valid but quota or credits exhausted"
    except Exception as e:
        return False, f"[red]✗ {provider}[/red] — {type(e).__name__}: {e}"


def _estimate_cost(cfg, art, rounds: int) -> float:
    from mars.models import estimate_cost
    from mars.roles.adversarial import SYSTEM as ADV
    from mars.roles.orchestrator import SYSTEM as ORC
    from mars.roles.primary import REBUTTAL_SYSTEM as REB, SYSTEM as PRI
    block = art.as_prompt_block()
    total = estimate_cost(cfg.model_for("primary"), cfg.provider_for("primary"), "primary", PRI + block)
    for _ in range(rounds):
        total += estimate_cost(cfg.model_for("adversarial"), cfg.provider_for("adversarial"), "challenger", ADV + block)
        total += estimate_cost(cfg.model_for("primary"), cfg.provider_for("primary"), "rebuttal", REB + block)
    total += estimate_cost(cfg.model_for("orchestrator"), cfg.provider_for("orchestrator"), "synthesis", ORC + block)
    return total


def _step3(config_path: Path, artifact_path: Path, rounds: int) -> None:
    console.print(_panel(
        3, "Run your refinement",
        f"Config:   [bold]{config_path}[/bold]\n"
        f"Artifact: [bold]{artifact_path}[/bold]\n"
        f"Rounds:   [bold]{rounds}[/bold]",
    ))
    console.print()

    from mars.artifact import ArtifactError, load_artifact
    from mars.config import ConfigError, load_config
    from mars.keys import PROVIDER_ENV, add_command, load_keys
    from mars.loop import run_review
    from mars.output import render_session

    try:
        cfg = load_config(config_path)
        art = load_artifact(artifact_path)
    except (ConfigError, ArtifactError) as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    for w in art.scope_warnings():
        console.print(f"[yellow]Scope warning:[/yellow] {w}")

    est = _estimate_cost(cfg, art, rounds)
    console.print(
        f"[bold]Plan:[/bold] {rounds} round(s) — "
        f"primary=[cyan]{cfg.provider_for('primary')}[/cyan], "
        f"adversarial=[cyan]{cfg.provider_for('adversarial')}[/cyan], "
        f"orchestrator=[cyan]{cfg.provider_for('orchestrator')}[/cyan]"
    )
    console.print(f"[bold]Estimated cost:[/bold] ≥ ${est:.4f} (lower bound; excludes per-round transcript growth)")
    console.print()

    if Confirm.ask("Dry run first (validate config, artifact, and API keys)?", default=True):
        console.print("[green]✓ Config and artifact valid.[/green]")
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
            from mars.keys import PROVIDER_ENV, update_command
            fix_lines = []
            for p in used_providers:
                ok, _ = _validate_key(p)
                if not ok:
                    env_name = PROVIDER_ENV.get(p, p.upper() + "_API_KEY")
                    fix_lines.append(f"  {update_command(env_name)}")
            console.print(Panel(
                "[bold red]Key validation failed.[/bold red]\n\n"
                "Run the command(s) below to update your key(s), then re-run setup:\n\n"
                + "\n".join(fix_lines),
                border_style="red",
                title="[bold red]Error[/bold red]",
                padding=(1, 2),
            ))
            return
        console.print()

    if not Confirm.ask("Run now?", default=True):
        console.print()
        console.print("Run it yourself:")
        console.print(f"  [bold cyan]mars run --artifact {artifact_path} --config {config_path}[/bold cyan]")
        return

    key_status = load_keys(cfg)
    used = {cfg.provider_for(r) for r in ("primary", "adversarial", "orchestrator")}
    missing_keys = [p for p, src in key_status.items() if src == "missing" and p in used]
    if missing_keys:
        for p in missing_keys:
            env_name = PROVIDER_ENV.get(p, p.upper() + "_API_KEY")
            console.print(f"[red]Missing key for {p}. Add it: {add_command(env_name)}[/red]")
        return

    try:
        with console.status("[bold]Running refinement...[/bold]") as status:
            session = run_review(
                cfg, art, rounds,
                progress=lambda msg: status.update(f"[bold]{msg}[/bold]"),
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    render_session(session)


def run_setup() -> None:
    """Entry point for `mars setup`."""
    console.print()
    providers_cfg, roles_cfg, rounds_cfg = _step1()

    config_path = Path("config.yaml")
    console.print()
    if config_path.exists() and not Confirm.ask(
        f"[yellow]{config_path} already exists. Overwrite?[/yellow]", default=False
    ):
        console.print(f"Keeping existing {config_path}.")
    else:
        cfg_data = {"providers": providers_cfg, "roles": roles_cfg, "rounds": rounds_cfg}
        config_path.write_text(yaml.dump(cfg_data, allow_unicode=True, default_flow_style=False))
        console.print(f"[green]Config written to {config_path}[/green]")

    console.print()
    artifact_path = _step2()

    console.print()
    _step3(config_path, artifact_path, rounds_cfg["default"])
