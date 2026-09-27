---
status: "shipped"
current_state: "MARS refines rough ideas through a CLI debate loop, now on the Sep 2026 frontier lineup (GPT-6 Astra / Claude Fable 5.1) with a Frontier/Balanced tier system, a 4th provider (OpenRouter), a family-based different-debaters guard, and a `--mode frontier|balanced` runtime flag. Docker, the web app, and Gemini end-to-end were descoped 2026-07-12."
next_action: "None required — scope is settled. Optional: exercise OpenRouter on a real run; keep model IDs current as new frontier models ship (edit mars/registry.py, run python -m mars.registry)."
things_to_know:
  - "The product pivot is refinement, not pass/fail review."
  - "Debate health (accept/revise/defend mix, reopened concerns) is measured automatically via `mars session analyze`, surfaced after every `mars run`."
  - "Model IDs are single-sourced in mars/registry.py (FRONTIER_MODELS + BALANCED_MODELS); config.example.yaml regenerates via `python -m mars.registry`."
  - "The two debaters must be DIFFERENT model families (checked by mars/config.model_family), so OpenRouter can't sneak two same-family models past the guard."
  - "Docker, web app, and Gemini end-to-end were descoped 2026-07-12."
what_it_is: "CLI experiment that refines rough ideas through a multi-agent debate loop."
read_next:
  - "README.md"
  - "SKILL.md"
  - "mars/"
  - "prompts/"
agent_notes:
  - "Product direction is refinement, not pass/fail review."
  - "Do not assume the CLI should become a web app — that was descoped."
  - "Match debaters by tier (Astra↔Fable 5.1 or Sol↔Opus 5.5); crossing tiers collapses the debate."
safe_first_action: "Read README.md and SKILL.md, then inspect the current CLI flow before changing product surface."
updated_at: "2026-09-05"
updated_by: "claude"
---

## Build inbox
Free-write feature ideas, follow-ups, and "do this next" notes here. Keep coding-agent implementation detail in `SKILL.md`.
