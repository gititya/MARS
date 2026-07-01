"""Pure, offline analysis of a completed SessionRecord: stance distribution,
concession health, and reopened-concern detection.

No LLM calls, no I/O beyond what mars.session already provides. Tolerates
sessions saved before the concessions/reopens schema existed (flat
`conceded: list[str]`, no per-challenge `reopens`) via a text-similarity
heuristic instead of raising.
"""

import re
from dataclasses import dataclass, field

from mars.session import SessionRecord

# Word-overlap (Jaccard) threshold for the legacy-session heuristic, not a similarity
# score in the intuitive sense - LLM critique prose paraphrases so heavily that even a
# true reopening rarely shares more than ~15-20% of its non-stopword vocabulary with the
# concern it's reopening. Calibrated against the 4 known real sessions (see evals/): at
# 0.10 with a top-2-candidates cap, 8/9 hand-verified reopenings are recoverable, with a
# meaningful false-positive rate on unrelated challenges. This is a best-effort signal
# for pre-existing sessions only, meant to surface candidates for human review - it is
# not proof, and it is not the long-term mechanism. Going forward, new sessions carry the
# model's own explicit `reopens` field, which is authoritative.
REOPEN_SIMILARITY_THRESHOLD = 0.10
REOPEN_CANDIDATE_CAP = 2

_LEGACY_ID_RE = re.compile(r"^\s*([a-zA-Z0-9_]+)")
_STOPWORDS = frozenset(
    "the a an is are was were be been being to of in on for with and or but not no if "
    "then than that this these those it its as at by from into over under about between "
    "within without across per do does did done can could will would should may might "
    "must shall have has had i you he she we they them his her their our your my me us "
    "so such very also both either neither each own same too more most other some any "
    "all up down out off again further once here there when where why how".split()
)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS and len(w) > 2}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class StanceCounts:
    accept: int = 0
    revise: int = 0
    defend: int = 0

    @property
    def total(self) -> int:
        return self.accept + self.revise + self.defend

    def add(self, other: "StanceCounts") -> None:
        self.accept += other.accept
        self.revise += other.revise
        self.defend += other.defend

    def pct(self, stance: str) -> float:
        if self.total == 0:
            return 0.0
        return 100.0 * getattr(self, stance) / self.total


@dataclass
class ReopenMatch:
    round_index: int
    new_challenge_id: str
    prior_round_index: int
    prior_challenge_id: str
    method: str               # "structured" | "heuristic"
    confidence: float | None  # similarity ratio for heuristic matches; None for structured
    evidence: str


@dataclass
class RoundAnalysis:
    index: int
    stances: StanceCounts
    resolved_count: int = 0
    partial_count: int = 0
    legacy_flat_conceded_count: int = 0
    reopens: list[ReopenMatch] = field(default_factory=list)


@dataclass
class SessionAnalysis:
    session_id: str
    rounds: list[RoundAnalysis]
    aggregate_stances: StanceCounts
    total_reopens: int
    debate_health_flagged: bool
    debate_health_reason: str


def _stance_counts(rebuttal: dict) -> StanceCounts:
    counts = StanceCounts()
    for r in rebuttal.get("responses", []):
        stance = r.get("stance")
        if stance == "accept":
            counts.accept += 1
        elif stance == "revise":
            counts.revise += 1
        elif stance == "defend":
            counts.defend += 1
    return counts


def _legacy_conceded_ids(conceded: list[str]) -> list[str]:
    """Old sessions store conceded points as prose like 'c1 - description...' or
    'c1: description...'. Extract the leading id token where present."""
    ids = []
    for line in conceded:
        m = _LEGACY_ID_RE.match(line)
        if m:
            ids.append(m.group(1))
    return ids


def _full_text(c: dict) -> str:
    return f"{c.get('concern', '')} {c.get('why_it_matters', '')} {c.get('suggestion', '')}"


def _concern_lookup(rounds_so_far: list[dict]) -> dict[str, tuple[int, str, str]]:
    """Map challenge id -> (round_index, concern text, full text) across all rounds seen so far.
    Full text (concern + why_it_matters + suggestion) is used for heuristic matching -
    concern alone is too short and too paraphrased to compare reliably."""
    lookup: dict[str, tuple[int, str, str]] = {}
    for round_idx, challenge in enumerate(rounds_so_far, start=1):
        for c in challenge.get("challenges", []):
            lookup[c["id"]] = (round_idx, c.get("concern", ""), _full_text(c))
    return lookup


def _structured_reopens(
    round_index: int, challenge: dict, concern_lookup: dict[str, tuple[int, str, str]]
) -> list[ReopenMatch]:
    matches = []
    for c in challenge.get("challenges", []):
        for prior_id in c.get("reopens") or []:
            prior = concern_lookup.get(prior_id)
            if not prior:
                continue
            prior_round, prior_concern, _ = prior
            matches.append(
                ReopenMatch(
                    round_index=round_index,
                    new_challenge_id=c["id"],
                    prior_round_index=prior_round,
                    prior_challenge_id=prior_id,
                    method="structured",
                    confidence=None,
                    evidence=f"{c.get('concern', '')[:120]!r} reopens {prior_concern[:120]!r}",
                )
            )
    return matches


def _heuristic_reopens(
    round_index: int,
    challenge: dict,
    conceded_ids: list[str],
    concern_lookup: dict[str, tuple[int, str, str]],
) -> list[ReopenMatch]:
    """For sessions saved before `reopens` existed: flag a new challenge as a likely
    reopening if its combined concern/why/suggestion text shares enough non-stopword
    vocabulary with a challenge that was just conceded in this round's (legacy)
    `conceded` list. Best-effort only - see REOPEN_SIMILARITY_THRESHOLD docstring."""
    matches = []
    for c in challenge.get("challenges", []):
        new_text = _full_text(c)
        candidates = []
        for prior_id in conceded_ids:
            prior = concern_lookup.get(prior_id)
            if not prior:
                continue
            prior_round_idx, prior_concern, prior_full = prior
            ratio = _jaccard(new_text, prior_full)
            if ratio >= REOPEN_SIMILARITY_THRESHOLD:
                candidates.append((ratio, prior_id, prior_round_idx, prior_concern))
        candidates.sort(key=lambda x: -x[0])
        for ratio, prior_id, prior_round_idx, prior_concern in candidates[:REOPEN_CANDIDATE_CAP]:
            matches.append(
                ReopenMatch(
                    round_index=round_index,
                    new_challenge_id=c["id"],
                    prior_round_index=prior_round_idx,
                    prior_challenge_id=prior_id,
                    method="heuristic",
                    confidence=round(ratio, 2),
                    evidence=f"{c.get('concern', '')[:120]!r} ~ {prior_concern[:120]!r}",
                )
            )
    return matches


def _debate_health(aggregate: StanceCounts, rounds: list[RoundAnalysis]) -> tuple[bool, str]:
    if aggregate.total == 0 or aggregate.defend > 0:
        return False, ""
    if any(r.partial_count > 0 for r in rounds):
        return False, ""
    return (
        True,
        "No pushback detected: the primary never used defend, and every concession "
        "graded in this session was flat resolved with no partial status. This may be "
        "a genuinely strong idea, or the debate may have collapsed into one-sided agreement.",
    )


def analyze_session(session: SessionRecord) -> SessionAnalysis:
    raw_challenges = [r.challenge for r in session.rounds]
    has_structured_data = any("concessions" in c for c in raw_challenges)

    round_analyses: list[RoundAnalysis] = []
    aggregate = StanceCounts()

    for i, rnd in enumerate(session.rounds):
        challenge = rnd.challenge
        rebuttal = rnd.rebuttal
        stances = _stance_counts(rebuttal)
        aggregate.add(stances)

        concessions = challenge.get("concessions") or []
        resolved_count = sum(1 for c in concessions if c.get("status") == "resolved")
        partial_count = sum(1 for c in concessions if c.get("status") == "partial")

        concern_lookup = _concern_lookup(raw_challenges[: i + 1])
        reopens = _structured_reopens(rnd.index, challenge, concern_lookup)

        legacy_flat_count = 0
        if not has_structured_data and i > 0:
            legacy_conceded = challenge.get("conceded") or []
            legacy_flat_count = len(legacy_conceded)
            conceded_ids = _legacy_conceded_ids(legacy_conceded)
            reopens += _heuristic_reopens(rnd.index, challenge, conceded_ids, concern_lookup)

        round_analyses.append(
            RoundAnalysis(
                index=rnd.index,
                stances=stances,
                resolved_count=resolved_count,
                partial_count=partial_count,
                legacy_flat_conceded_count=legacy_flat_count,
                reopens=reopens,
            )
        )

    total_reopens = sum(len(r.reopens) for r in round_analyses)
    flagged, reason = _debate_health(aggregate, round_analyses)

    return SessionAnalysis(
        session_id=session.session_id,
        rounds=round_analyses,
        aggregate_stances=aggregate,
        total_reopens=total_reopens,
        debate_health_flagged=flagged,
        debate_health_reason=reason,
    )


def analyze_all(sessions: list[SessionRecord]) -> list[SessionAnalysis]:
    return [analyze_session(s) for s in sessions]


def aggregate_stances(analyses: list[SessionAnalysis]) -> StanceCounts:
    total = StanceCounts()
    for a in analyses:
        total.add(a.aggregate_stances)
    return total
