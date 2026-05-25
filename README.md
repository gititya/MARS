# MARS — Adversarial Review System

A bounded adversarial review system for ambitious cognitive work. Not "multi-agent AI" — a
structured protocol that assigns frontier models to defined adversarial roles to surface
assumptions, contested risks, and decision pressure **before** commitment.

**The problem it solves:** single-model reasoning stabilizes around plausible narratives too
quickly. One model produces coherent, internally consistent thinking while under-attacking its
own assumptions. MARS forces cross-model adversarial pressure and a concrete decision.

## What it is

- A CLI that runs a primary → adversarial → orchestrator review over a **structured artifact**.
- Multi-provider (Anthropic, OpenAI, Gemini) with per-role model assignment.
- Bounded: hard cap of 4 rounds, repetition-triggered early termination.
- Every critique gets a disposition; every run forces one concrete decision.

## What it is NOT

- A general-purpose chatbot or Q&A tool.
- Code review or bug fixing.
- Answer synthesis, consensus building, or infinite debate.

Use it for: product direction, architecture decisions, AI/workflow strategy, high-ambiguity or
irreversible decisions. Do **not** use it for bug fixes, routine implementation, or simple
deterministic tasks.

## The three roles

- **Primary** — generates a coherent, grounded proposal: framing, recommendation, tradeoffs,
  assumptions, uncertainty. Does not defend itself.
- **Adversarial reviewer** — attacks assumptions and framing. Every critique must be falsifiable
  and state what would resolve it. Assign your strongest model here — it is load-bearing.
- **Orchestrator** — compresses critiques across rounds, assigns dispositions, detects repetition,
  and forces a final decision. Its last-round output **is** the final synthesis.

## Quickstart

```bash
# 1. Install (Python 3.11+)
pip install -e .

# 2. Set keys for the providers you'll use
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...

# 3. Configure models + role mapping
cp config.example.yaml config.yaml   # edit as needed

# 4. Dry run first — validates config + artifact, estimates cost, makes ZERO API calls
mars run --artifact examples/prd-example.yaml --config config.yaml --dry-run

# 5. Real run
mars run --artifact examples/prd-example.yaml --config config.yaml --rounds 2
```

## CLI

```bash
mars run --artifact artifact.yaml --config config.yaml   # run a review
mars run --artifact artifact.yaml --dry-run              # validate + estimate cost only
mars run --artifact artifact.yaml --rounds 3             # override rounds (1-4)
mars run --artifact artifact.yaml --yes                  # skip cost confirmation
mars session list                                        # list past sessions
mars session show <session-id>                           # re-render a past session
```

Sessions are logged as human-readable JSON to `~/.mars/sessions/`.

## Configuration

See `config.example.yaml`. Rules enforced in code:

- At least **2 providers** configured.
- Every role maps to a configured provider.
- **`primary` and `adversarial` must be different providers** — same provider gives correlated
  blind spots and defeats the purpose of adversarial review.
- `orchestrator` may share a provider with `primary` (recommended default).
- Rounds: 1–4. The cap of 4 is enforced in code; config cannot exceed it.

## Required artifact fields

All mandatory (vague prompts are rejected with a field-level error):

`goal`, `artifact`, `constraints`, `assumptions`, `fears`, `tradeoffs`, `context`.

Optional but recommended: `stakeholders`, `decision`. See `examples/` for three complete artifacts.

## Final decision

Every run forces exactly one: `PROCEED`, `PROCEED_WITH_CONDITION`, `TEST_FIRST`, `ESCALATE`,
`DEFER`, or `DISCARD` — each with required specifics. The synthesis also always includes the
strongest objection most likely to be ignored, and the operator's most likely bias direction.

## License

MIT — see `LICENSE`.
