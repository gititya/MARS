# MARS — SKILL.md

## Current phase
Session 2 complete — `mars setup` wizard built and mostly working. Blocked on OpenAI Keychain key not updating correctly. Ready to resume from key fix.

## What exists
- Full CLI: `mars run`, `mars session show/list`, `mars keys status`, `mars setup`
- `mars setup` — 3-step interactive wizard:
  - Step 1: MARS description + privacy statement, API key check/add via Keychain, numbered role assignment menus (primary/adversarial/orchestrator), rounds config
  - Step 2: artifact builder — 7 fields via prompt_toolkit multiline editor (Enter=newline, Ctrl+D=submit), file loader for `artifact` field (PDF/HTML/MD/TXT, multiple files with labels, merged with `---` separator)
  - Step 3: dry run (config + artifact validation + live key ping per provider), then offer to run live
- Dry run key validation: 1-token ping per provider using cheapest model (`anthropic/claude-haiku-4-5-20251001`, `openai/gpt-4o-mini`, `gemini/gemini-2.0-flash-lite`), distinguishes invalid key vs. no credits
- Frontier models updated: `claude-opus-4-7` / `gpt-5.5` / `gemini/gemini-3.1-pro-preview` for primary+adversarial; `claude-sonnet-4-6` / `gpt-4o` / `gemini/gemini-2.5-flash` for orchestrator
- LiteLLM noise suppressed via `LITELLM_LOG=ERROR` + `litellm.suppress_debug_info = True`
- Keychain store now uses delete+add instead of `-U` (which silently fails)

## Open bugs / next steps
- **BLOCKER**: OpenAI Keychain key not updating — `security add-generic-password -U` was silently failing, reverted to delete+add in code but user still needs to manually run:
  ```
  security delete-generic-password -a mars -s OPENAI_API_KEY
  security add-generic-password -a mars -s OPENAI_API_KEY -w
  security find-generic-password -a mars -s OPENAI_API_KEY -w   # verify
  ```
- `voice-support` artifact (no .yaml extension) saved from last setup run — needs to be re-run or renamed
- Scope warning fires on voice-support artifact ("resembles bug report") — may want to review artifact content
- Changes not yet committed: `mars/setup_wizard.py` (new), `mars/__init__.py`, `mars/cli.py`, `mars/keys.py`, `pyproject.toml`, `config.example.yaml`

## Session log
- Session 1: Built full MARS CLI from PRD — config, artifact, schemas, models, roles, loop, session, output, CLI. Pushed to GitHub. Wrote README.
- Session 2: Built `mars setup` wizard. Fixed role selection (numbered menus). Switched artifact input to prompt_toolkit multiline. Added multi-file loader with labels. Added dry-run key validation. Updated frontier models. Suppressed litellm noise. Fixed Keychain update command. Blocked on OpenAI key.
- Session 3: **Product pivot — MARS reframed from "Model Adversarial Review System" (judge/gate) to "Model Adversarial Refinement System" (idea hardening).** Same adversarial mechanism, constructive objective: vague idea in → watertight idea out, no verdict. Changes: (1) added a rebuttal step — primary now defends/concedes/revises each round instead of staying silent; (2) challenger reframed from critique-quota attacker to honest peer that pairs every concern with a fix and concedes resolved points (killed the "produce NEW critiques" rule); (3) orchestrator demoted from referee (PROCEED/DISCARD verdict, dispositions, decision_blockers) to a single end-of-run synthesizer that delivers the hardened idea (hardened_idea / what_got_stronger / open_decisions / watch_items); (4) flow is now primary build → [challenge → rebuttal] × rounds → one synthesis, fixed rounds (dropped repetition early-stop). New schemas: PrimaryOutput(build), ChallengerOutput, RebuttalOutput, SynthesisOutput, Stance enum. New prompt `prompts/rebuttal.txt`. Two flagship debaters (GPT-5.5 ↔ Opus 4.7); orchestrator kept on a flagship since it now writes the deliverable (removed the cheap ORCHESTRATOR_MODELS tier from the wizard). OpenAI Keychain key fixed (bare `-w` silently stored nothing; resolved by passing the key inline). config.yaml openai model bumped gpt-4o → gpt-5.5. Codex adversarial review on the pivot raised 4 findings: fixed rebuttal 1:1 validation (high), reverted inline-key command to prompt-based (security), made cost estimate an honest lower bound; declined the session backward-compat migration (conflicts with no-backcompat rule, old format is dead). Live run on voice-support (session 20260525T212919Z) confirmed the refinement output is materially richer than the old review verdict — produces a buildable MVP, and round 2 conceded all of round 1 then went deeper instead of repeating.

## Need to work on (next session)

### 1. Single-source frontier model config (frictionless model updates)
**Problem:** When a new frontier model launches (GPT-6, Opus 5, etc.), MARS model IDs must be updated by hand in FOUR places: `config.yaml`, `config.example.yaml`, `FRONTIER_MODELS` in `mars/setup_wizard.py`, and `_VALIDATION_MODELS` in `mars/setup_wizard.py` (the 1-token key-ping models). This is error-prone and easy to forget.
**Goal:** one frictionless update path. Options to weigh next session: (a) a single models-registry module (e.g. `mars/registry.py`) holding frontier + validation model IDs that the wizard, the generated `config.example.yaml`, and validation all import from; (b) a `mars models` command that lists/updates defaults; (c) optional remote fetch of current model IDs. Recommendation leans (a) — smallest, no network, kills the duplication. Not yet implemented.

### 2. Builder over-agreeableness caveat ("all-accept" failure mode)
**What it is:** In the refinement loop the primary (builder) takes a stance — `accept` / `revise` / `defend` — on each peer challenge. In the first real run (session 20260525T212919Z, GPT-5.5 builder vs Opus 4.7 challenger), the builder accepted ALL 10 challenges across 2 rounds with ZERO `defend` and zero `revise`.
**Why it matters:** the whole value of the design is a genuine *peer debate* that hardens the idea. If two constructive frontier models always defer, the loop collapses from "peers debating" into "challenger dictates, builder complies." The `defend` stance becomes dead in practice, and a builder that accepts a weak or scope-bloating challenge makes the idea *worse* (adds unnecessary complexity) while looking productive. This is the exact sycophancy/agreement-collapse risk flagged when the refinement design was chosen — challenge must stay genuine, not become one-sided.
**Caveat status:** one run only — not yet confirmed as a pattern. Could be that these 6+4 challenges were simply all correct.
**Plan to address (execute next session):**
1. **Measure before fixing.** Run 3-5 refinements on varied artifacts; record the accept/revise/defend ratio. If `defend` stays ~0, it's a real pattern worth fixing. If `defend`/`revise` show up naturally, leave it alone.
2. **Prompt fix in `prompts/rebuttal.txt`.** Make defending a first-class, expected behavior: instruct the builder to genuinely judge each challenge, to `defend` when the current design is justified, and to treat accepting a wrong/overstated/scope-bloating challenge as actively weakening the idea — not as politeness. Explicitly: "accepting a weak challenge is a failure, not a courtesy."
3. **Surface it to the operator.** Consider a synthesis-level signal (in `SynthesisOutput` / orchestrator prompt) that flags "no pushback detected — builder accepted every challenge," so the user knows the debate may have been one-sided.
4. **Test model-specificity.** Swap roles (Opus builder vs GPT-5.5 challenger) to check whether the all-accept behavior is the builder model being agreeable vs. a structural prompt issue.
5. Decide whether `defend`/`revise` should ever be *required* (risky — forcing disagreement reintroduces challenge-for-its-own-sake, the thing we explicitly removed). Lean toward prompt nudges + operator visibility over hard quotas.

### 3. Docker packaging
Ship MARS as a container so anyone can run it without the venv/Python setup. Not in the original PRD — added by user. Needs: a Dockerfile, a decision on how keys are passed in (env vars, since the macOS Keychain path doesn't exist inside a Linux container), and a documented `docker run` invocation. Sessions dir would need a mounted volume to persist.

### 4. Web app (PRD Phase 2)
Browser UI over the same refinement engine. PRD spec: FastAPI backend wrapping the core Python logic, streaming round-by-round output (build → challenge → rebuttal → synthesis), an artifact input form, and a session-history view. Hard rule: the CLI core stays the single source of logic; the web app wraps `run_review`, it does not fork the pipeline.

### 5. (minor) CI hardcoded-key grep check
Open-source-checklist item from the PRD, never built. A CI step that greps source for secret patterns before merge.

### 6. (minor) Gemini third-provider path
Supported in `config.example.yaml` but never exercised under the new refinement flow. Validate a full run with Gemini in a role works end to end.

### 7. (meta) PRD is stale
`/Users/aditya/Documents/obsidian/cortex/AI-OS/adversarial-review-system-prd.md` still describes the pre-pivot adversarial-*review* product (dispositions, PROCEED/DISCARD, repetition detection — all deliberately removed). Update or supersede it to reflect the refinement system. Until then it is NOT the source of truth — this SKILL.md + the backlog memory are.
