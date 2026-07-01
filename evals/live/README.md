# evals/live (seam, not implemented)

Future live-eval mode: run `mars run` against a small fixed set of artifacts (e.g.
reuse `examples/*.yaml`) and diff the resulting debate-health metrics
(`mars.analysis.analyze_session`) across prompt-tuning iterations, to catch
regressions or confirm improvements in the accept/revise/defend mix and reopen
behavior over time.

Not built. This directory just marks where it would go. It needs real API calls
(unlike `check_frozen_sessions.py`, which is free and offline), so it should stay an
explicit, opt-in step rather than something that runs automatically.
