"""Rich terminal rendering of a completed session."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mars.session import SessionRecord

console = Console()

_SEVERITY_STYLE = {"critical": "bold red", "major": "yellow", "minor": "dim"}
_DISPOSITION_STYLE = {
    "decision_blocker": "bold red",
    "requires_evidence": "yellow",
    "unresolved": "yellow",
    "acceptable_risk": "cyan",
    "refuted": "dim",
    "resolved": "green",
}
_ACTION_STYLE = {
    "PROCEED": "bold green",
    "PROCEED_WITH_CONDITION": "green",
    "TEST_FIRST": "yellow",
    "ESCALATE": "bold red",
    "DEFER": "yellow",
    "DISCARD": "red",
}


def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {i}" for i in items) if items else "[dim]none[/dim]"


def render_session(session: SessionRecord) -> None:
    console.rule(f"[bold]MARS review — session {session.session_id}[/bold]")

    if session.primary:
        p = session.primary
        body = (
            f"[bold]Framing[/bold]\n{p['framing']}\n\n"
            f"[bold]Recommendation[/bold]\n{p['recommendation']}\n\n"
            f"[bold]Tradeoffs[/bold]\n{_bullets(p['tradeoffs'])}\n\n"
            f"[bold]Assumptions[/bold]\n{_bullets(p['assumptions'])}\n\n"
            f"[bold]Uncertainty[/bold]\n{_bullets(p['uncertainty'])}"
        )
        console.print(Panel(body, title="Primary", border_style="blue"))

    for rnd in session.rounds:
        adv = rnd.adversarial
        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("Sev", width=8)
        table.add_column("Claim")
        table.add_column("Resolution")
        for c in adv["critiques"]:
            style = _SEVERITY_STYLE.get(c["severity"], "")
            table.add_row(f"[{style}]{c['severity']}[/{style}]", c["claim"], c["resolution"])
        console.print(
            Panel(table, title=f"Round {rnd.index} — adversarial", border_style="red")
        )
        openq = (
            f"[bold]Missing problem[/bold]: {adv['missing_problem']}\n"
            f"[bold]Missing assumption[/bold]: {adv['missing_assumption']}\n"
            f"[bold]Absent stakeholder[/bold]: {adv['absent_stakeholder']}\n"
            f"[bold]Most dangerous certainty[/bold]: {adv['most_dangerous_certainty']}"
        )
        console.print(Panel(openq, title=f"Round {rnd.index} — open questions", border_style="red"))

    final = session.final_orchestrator
    if final:
        disp = Table(show_header=True, header_style="bold", expand=True)
        disp.add_column("Disposition", width=18)
        disp.add_column("Critique")
        for c in final["compressed_critiques"]:
            style = _DISPOSITION_STYLE.get(c["disposition"], "")
            summary = c["summary"]
            if c.get("discard_reason"):
                summary += f"\n[dim]↳ {c['discard_reason']}[/dim]"
            disp.add_row(f"[{style}]{c['disposition']}[/{style}]", summary)
        console.print(Panel(disp, title="Compressed critiques", border_style="magenta"))

        action = final["recommended_action"]
        astyle = _ACTION_STYLE.get(action, "bold")
        synth = (
            f"[{astyle}]► {action}[/{astyle}]\n{final['recommended_action_detail']}\n\n"
            f"[bold]Decision blockers[/bold]\n{_bullets(final['decision_blockers'])}\n\n"
            f"[bold]Unresolved questions[/bold]\n{_bullets(final['unresolved_questions'])}\n\n"
            f"[bold]Strongest ignored objection[/bold]\n{final['strongest_ignored_objection']}\n\n"
            f"[bold]Most likely operator bias[/bold]\n{final['operator_bias_direction']}"
        )
        console.print(Panel(synth, title="FINAL SYNTHESIS", border_style="green"))

    console.print(f"[dim]{session.stop_reason}[/dim]")


def render_session_list(sessions: list[SessionRecord]) -> None:
    if not sessions:
        console.print("[dim]No sessions yet.[/dim]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Session ID")
    table.add_column("Timestamp")
    table.add_column("Rounds")
    table.add_column("Decision")
    for s in sessions:
        final = s.final_orchestrator
        action = final["recommended_action"] if final else "—"
        table.add_row(s.session_id, s.timestamp, str(len(s.rounds)), action)
    console.print(table)
