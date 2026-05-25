"""Rich terminal rendering of a completed refinement session."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mars.session import SessionRecord

console = Console()

_STANCE_STYLE = {"accept": "green", "revise": "cyan", "defend": "yellow"}


def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {i}" for i in items) if items else "[dim]none[/dim]"


def render_session(session: SessionRecord) -> None:
    console.rule(f"[bold]MARS refinement — session {session.session_id}[/bold]")

    if session.primary:
        p = session.primary
        body = (
            f"[bold]Framing[/bold]\n{p['framing']}\n\n"
            f"[bold]Proposal[/bold]\n{p['proposal']}\n\n"
            f"[bold]Key choices[/bold]\n{_bullets(p['key_choices'])}\n\n"
            f"[bold]Assumptions[/bold]\n{_bullets(p['assumptions'])}\n\n"
            f"[bold]Open questions[/bold]\n{_bullets(p['open_questions'])}"
        )
        console.print(Panel(body, title="Primary build", border_style="blue"))

    for rnd in session.rounds:
        ch = rnd.challenge
        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("Concern")
        table.add_column("Why it matters")
        table.add_column("Suggestion")
        for c in ch["challenges"]:
            table.add_row(c["concern"], c["why_it_matters"], c["suggestion"])
        console.print(
            Panel(table, title=f"Round {rnd.index} — peer challenge", border_style="red")
        )
        meta = f"[bold]Biggest risk[/bold]: {ch['biggest_risk']}"
        if ch.get("conceded"):
            meta += f"\n[bold]Conceded from prior round[/bold]\n{_bullets(ch['conceded'])}"
        console.print(Panel(meta, border_style="red"))

        reb = rnd.rebuttal
        resp = Table(show_header=True, header_style="bold", expand=True)
        resp.add_column("Stance", width=8)
        resp.add_column("Response")
        for r in reb["responses"]:
            style = _STANCE_STYLE.get(r["stance"], "")
            resp.add_row(f"[{style}]{r['stance']}[/{style}]", r["response"])
        console.print(
            Panel(resp, title=f"Round {rnd.index} — primary rebuttal", border_style="cyan")
        )

    s = session.synthesis
    if s:
        body = (
            f"[bold]Hardened idea[/bold]\n{s['hardened_idea']}\n\n"
            f"[bold]What got stronger[/bold]\n{_bullets(s['what_got_stronger'])}\n\n"
            f"[bold]Open decisions (your call)[/bold]\n{_bullets(s['open_decisions'])}\n\n"
            f"[bold]Watch items[/bold]\n{_bullets(s['watch_items'])}"
        )
        console.print(Panel(body, title="HARDENED IDEA", border_style="green"))

    console.print(f"[dim]{session.stop_reason}[/dim]")


def render_session_list(sessions: list[SessionRecord]) -> None:
    if not sessions:
        console.print("[dim]No sessions yet.[/dim]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Session ID")
    table.add_column("Timestamp")
    table.add_column("Rounds")
    table.add_column("Refined")
    for s in sessions:
        table.add_row(
            s.session_id,
            s.timestamp,
            str(len(s.rounds)),
            "yes" if s.synthesis else "—",
        )
    console.print(table)
