"""Regression check: mars/analysis.py output on the known real sessions must match
hand-verified expectations. No API calls, no network - only parses whatever session
JSON already exists locally in ~/.mars/sessions/.

Stance counts are deterministic (derived straight from stored rebuttal data) and are
checked exactly. Reopened-concern detection for these sessions runs through the
best-effort lexical heuristic (see mars/analysis.py's REOPEN_SIMILARITY_THRESHOLD
docstring) since these sessions predate the `reopens` field - so known_reopens is
checked as a recall rate against a documented floor, not an exact match. A session
missing locally (fresh clone, CI, different machine) is reported as SKIPPED, not FAILED.

Run with:
    python evals/check_frozen_sessions.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mars.analysis import analyze_session
from mars.session import load_session

EXPECTED_DIR = Path(__file__).parent / "expected"
RECALL_FLOOR = 0.70  # below this, treat as a regression worth investigating


def _check_one(path: Path) -> tuple[bool, int, int]:
    expected = json.loads(path.read_text())
    session_id = expected["session_id"]
    try:
        session = load_session(session_id)
    except FileNotFoundError:
        print(f"SKIP  {path.stem}: session {session_id} not found locally")
        return True, 0, 0

    analysis = analyze_session(session)

    exp_stances = expected["aggregate_stances"]
    actual_stances = {
        "accept": analysis.aggregate_stances.accept,
        "revise": analysis.aggregate_stances.revise,
        "defend": analysis.aggregate_stances.defend,
    }
    stances_ok = actual_stances == exp_stances
    if not stances_ok:
        print(f"FAIL  {path.stem}: stance counts {actual_stances} != expected {exp_stances}")
    else:
        print(f"OK    {path.stem}: stance counts match {actual_stances}")

    detected = {
        (rp.round_index, rp.new_challenge_id, rp.prior_challenge_id)
        for r in analysis.rounds
        for rp in r.reopens
    }
    known = expected.get("known_reopens", [])
    hits = 0
    for pair in known:
        key = (pair["round"], pair["new_challenge_id"], pair["prior_challenge_id"])
        found = key in detected
        hits += found
        mark = "hit " if found else "MISS"
        print(f"      reopen {mark}: r{pair['round']} {pair['new_challenge_id']} -> {pair['prior_challenge_id']}")

    return stances_ok, hits, len(known)


def run() -> bool:
    all_ok = True
    total_hits = 0
    total_known = 0
    for path in sorted(EXPECTED_DIR.glob("*.json")):
        ok, hits, known = _check_one(path)
        all_ok = all_ok and ok
        total_hits += hits
        total_known += known

    recall = (total_hits / total_known) if total_known else 1.0
    print(f"\nReopen recall: {total_hits}/{total_known} ({recall:.0%}), floor is {RECALL_FLOOR:.0%}")
    if recall < RECALL_FLOOR:
        print("FAIL: recall dropped below the documented floor - likely a code regression.")
        all_ok = False

    print("PASS" if all_ok else "FAIL")
    return all_ok


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
