# evals

Regression checks for `mars/analysis.py` (stance distribution + concession/reopen
detection) against the real sessions MARS has actually produced. Local-only: this
needs `~/.mars/sessions/*.json` to exist on the machine running it, since session
data (Adi's actual project ideas) is never committed to this repo.

## What's here

- `expected/*.json` - hand-verified expectations for each known real session:
  aggregate accept/revise/defend counts, and `known_reopens` (round -> new
  challenge id -> prior challenge id it's secretly re-litigating, verified by
  reading the actual concern text of both challenges).
- `check_frozen_sessions.py` - loads each session by id, runs `analyze_session()`,
  and checks the result against `expected/`. A session missing locally is SKIPPED,
  not failed (fresh clone, different machine, CI).
- `live/` - a seam for a future live-eval mode; not built yet.

Run it:

```
python evals/check_frozen_sessions.py
```

## Why stance counts are exact but reopens are a recall rate, not exact match

Stance counts (accept/revise/defend) are deterministic - they're read straight off
stored rebuttal data, so `expected` and `actual` must match exactly.

The 4 sessions on file all predate the `reopens` field (they were all real runs before
the concede-then-reopen prompt/schema fix shipped), so their reopened-concern detection
runs through a best-effort lexical heuristic (word-overlap between a new challenge's
text and a previously-conceded challenge's text - see `REOPEN_SIMILARITY_THRESHOLD` in
`mars/analysis.py`). LLM critique prose paraphrases too heavily for a dependency-free
heuristic to catch every case, so `check_frozen_sessions.py` checks recall against a
documented floor (70%) instead of asserting every known pair is found. Current recall:
8/10 known reopens (80%). The 2 known misses (B2C Voice's c6->c2, CISO's c8->c4) are
real limits of lexical overlap, not bugs - both true pairs share very little
vocabulary despite being the same underlying concern.

Going forward, new sessions carry the challenger model's own explicit `reopens` field
(structured, not heuristic) - authoritative, not a guess. The heuristic exists only to
retrofit the sessions that predate that field.
