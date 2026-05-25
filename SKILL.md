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
