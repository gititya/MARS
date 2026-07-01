"""Rich terminal rendering of a completed refinement session."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mars.analysis import SessionAnalysis
from mars.session import SessionRecord

console = Console()

_STANCE_STYLE = {"accept": "green", "revise": "cyan", "defend": "yellow"}
_CONCESSION_STYLE = {"resolved": "green", "partial": "yellow"}


def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {i}" for i in items) if items else "[dim]none[/dim]"


def _concession_lines(challenge: dict) -> list[str]:
    """Render concessions (new structured format) or fall back to the legacy
    flat `conceded` prose list from sessions saved before that field existed."""
    concessions = challenge.get("concessions")
    if concessions:
        lines = []
        for c in concessions:
            style = _CONCESSION_STYLE.get(c.get("status", ""), "")
            lines.append(
                f"[{style}]{c.get('status', '')}[/{style}] {c.get('challenge_id', '')}: "
                f"{c.get('justification', '')}"
            )
        return lines
    conceded = challenge.get("conceded")
    if conceded:
        return list(conceded)
    return []


def render_session(session: SessionRecord) -> None:
    console.rule(f"[bold]MARS refinement - session {session.session_id}[/bold]")

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
            Panel(table, title=f"Round {rnd.index} - peer challenge", border_style="red")
        )
        meta = f"[bold]Biggest risk[/bold]: {ch['biggest_risk']}"
        concession_lines = _concession_lines(ch)
        if concession_lines:
            meta += f"\n[bold]Conceded from prior round[/bold]\n" + _bullets(concession_lines)
        console.print(Panel(meta, border_style="red"))

        reb = rnd.rebuttal
        resp = Table(show_header=True, header_style="bold", expand=True)
        resp.add_column("Stance", width=8)
        resp.add_column("Response")
        for r in reb["responses"]:
            style = _STANCE_STYLE.get(r["stance"], "")
            resp.add_row(f"[{style}]{r['stance']}[/{style}]", r["response"])
        console.print(
            Panel(resp, title=f"Round {rnd.index} - primary rebuttal", border_style="cyan")
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
            "yes" if s.synthesis else "-",
        )
    console.print(table)


def _stance_cell(stances) -> str:
    return (
        f"[green]{stances.accept} accept[/green] / "
        f"[cyan]{stances.revise} revise[/cyan] / "
        f"[yellow]{stances.defend} defend[/yellow]"
    )


def render_debate_health_summary(analysis: SessionAnalysis) -> None:
    """Compact one-panel summary: the operator-visible "no pushback" flag."""
    agg = analysis.aggregate_stances
    body = f"[bold]Stances[/bold]: {_stance_cell(agg)} (n={agg.total})\n"
    body += f"[bold]Reopened concerns detected[/bold]: {analysis.total_reopens}"
    style = "yellow" if analysis.debate_health_flagged else "green"
    if analysis.debate_health_flagged:
        body += f"\n\n[bold yellow]⚠ {analysis.debate_health_reason}[/bold yellow]"
    console.print(Panel(body, title="Debate health", border_style=style))


def render_analysis(analysis: SessionAnalysis) -> None:
    """Per-round stance table + reopened-concern list + health panel for one session."""
    console.rule(f"[bold]Debate-health analysis - session {analysis.session_id}[/bold]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Round")
    table.add_column("Stances")
    table.add_column("Resolved")
    table.add_column("Partial")
    table.add_column("Reopens")
    for r in analysis.rounds:
        table.add_row(
            str(r.index),
            _stance_cell(r.stances),
            str(r.resolved_count),
            str(r.partial_count),
            str(len(r.reopens)),
        )
    console.print(table)

    for r in analysis.rounds:
        for rp in r.reopens:
            conf = f" (confidence {rp.confidence})" if rp.confidence is not None else ""
            console.print(
                f"  [dim]round {rp.round_index}[/dim] [bold]{rp.new_challenge_id}[/bold] "
                f"reopens [bold]{rp.prior_challenge_id}[/bold] from round {rp.prior_round_index} "
                f"[{rp.method}]{conf}"
            )

    render_debate_health_summary(analysis)


def render_analysis_aggregate(analyses: list[SessionAnalysis]) -> None:
    """One row per session plus a totals row, for `mars session analyze` with no id."""
    if not analyses:
        console.print("[dim]No sessions yet.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Session ID")
    table.add_column("Stances")
    table.add_column("Reopens")
    table.add_column("Flagged")
    total = None
    for a in analyses:
        table.add_row(
            a.session_id,
            _stance_cell(a.aggregate_stances),
            str(a.total_reopens),
            "[yellow]yes[/yellow]" if a.debate_health_flagged else "[green]no[/green]",
        )
        if total is None:
            total = type(a.aggregate_stances)()
        total.add(a.aggregate_stances)
    console.print(table)
    if total is not None:
        console.print(f"[bold]Total across {len(analyses)} session(s)[/bold]: {_stance_cell(total)}")
