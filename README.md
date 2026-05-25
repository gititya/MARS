# MARS — Model Adversarial Refinement System

MARS takes a vague idea and refines it into a watertight one using two frontier models as peers. One model builds the idea out, a second model from a different provider pressure-tests it, the first defends or revises, and they iterate. A third model then synthesizes the hardened result into the version you should actually build.

It exists because one model stabilizes on a plausible answer too fast — coherent, confident, and under-tested. MARS keeps the genuine challenge (the peer is from a different provider, so you do not get correlated blind spots) but points it at *construction*: every weakness the challenger finds comes with a fix, and every fix the builder accepts feeds back into a stronger idea. The output is not a verdict — it is your idea, made tight.

Use it for product direction, architecture calls, AI and workflow strategy, and turning a half-formed idea into something buildable. Do not use it for bug fixes, routine implementation, or simple questions.

```bash
pip install -e .             # Python 3.11+
cp config.example.yaml config.yaml
mars run --artifact examples/prd-example.yaml --config config.yaml --dry-run
```

---

## How it works

1. **You write a structured artifact.** A YAML file with the idea, your constraints, assumptions, fears, and tradeoffs. Vague prompts are rejected with a field-level error. This is the input that makes the refinement sharp instead of generic.
2. **You dry run first.** `--dry-run` validates the config and artifact, prints a cost estimate, and makes zero API calls. Nothing hits a provider until you confirm.
3. **The primary builds the idea.** It restates the idea sharper than it came in, commits to concrete choices, and names its assumptions and the parts that are still soft. It builds rather than hedges, so there is something real to push on.
4. **The challenger pressure-tests it.** A frontier peer from a different provider finds the places the idea is genuinely weak — and pairs every concern with a suggested fix. It is not here to block or to nitpick; it is here to make the idea watertight.
5. **The primary defends or revises.** For each challenge it takes a stance — accept, revise, or defend — and re-states an improved proposal. That stronger version carries into the next round, where the challenger can concede what is now resolved.
6. **The orchestrator delivers the hardened idea.** After the rounds, it synthesizes the result: the watertight idea, what got stronger, the decisions that still need your judgment, and the residual risks to watch. No winner, no verdict — just your idea, tightened.

---

## Commands

```bash
mars run --artifact artifact.yaml --config config.yaml   # run a refinement
mars run --artifact artifact.yaml --dry-run              # validate and estimate cost, no API calls
mars run --artifact artifact.yaml --rounds 3             # override rounds (1 to 4)
mars run --artifact artifact.yaml --yes                  # skip the cost confirmation prompt
mars session list                                        # list past sessions
mars session show <session-id>                           # re-render a past session
```

Sessions are written as readable JSON to `~/.mars/sessions/`.

---

## Configuration

Configure one model per provider, then map the three roles to them. See `config.example.yaml`.

```yaml
providers:
  anthropic:
    model: claude-opus-4-7
  openai:
    model: gpt-5.5
roles:
  primary: openai
  adversarial: anthropic
  orchestrator: openai
rounds:
  default: 2
  max: 4
```

Put your two strongest models on `primary` and `adversarial` — they debate as peers, so a mismatch (a weak model against a frontier one) collapses the refinement. Keep the orchestrator strong too; it writes your deliverable.

Rules enforced in code, not just in the schema:

| Rule | Why |
|------|-----|
| At least 2 providers configured | The whole point is more than one model |
| Every role maps to a configured provider | No role can point at a provider you never set up |
| `primary` and `adversarial` must be different providers | The two debaters must be peers from different families, or you get correlated blind spots |
| `orchestrator` may share with `primary` | Saves a key; the orchestrator does not debate, it synthesizes |
| Rounds capped at 4 | Hard limit in code, config cannot raise it |

---

## Artifact fields

All required. Missing or blank fields fail before any API call.

| Field | What goes here |
|-------|----------------|
| `goal` | The idea or thing you want to build |
| `artifact` | The idea, proposal, PRD, design, or plan itself |
| `constraints` | Hard limits and non-negotiables |
| `assumptions` | What you currently believe to be true |
| `fears` | Where you think the risk is |
| `tradeoffs` | What you have already weighed |
| `context` | Who uses this and what system it lives in |

Optional but recommended: `stakeholders`, `decision`. See `examples/` for three complete artifacts.

---

## The three roles

- **Primary (builder).** Builds the idea out concretely, then defends or revises it each round. Put a frontier model here.
- **Challenger (peer).** Pressure-tests the current idea — genuine weaknesses only, each paired with a fix, no nitpick quota. Must be a frontier model from a different provider; it is a peer, not a junior reviewer.
- **Orchestrator.** Runs once at the end and synthesizes the hardened idea for you. It does not referee the debate or pick a winner — it delivers the result.

Each round, the builder takes a stance on every challenge: `accept` (fold in the fix), `revise` (adjust), or `defend` (hold, with reasoning). The challenger can `concede` points the builder has genuinely answered.

---

## What you get back

A run does not end with a verdict. It ends with the hardened idea:

| Output | What it is |
|--------|------------|
| **Hardened idea** | The watertight version, written as the thing to actually build |
| **What got stronger** | The concrete improvements the refinement produced |
| **Open decisions** | The calls that genuinely need your judgment — real tradeoffs the models could not settle for you |
| **Watch items** | Residual risks worth tracking while you build |

---

## Sample output

```text
============ MARS refinement : session 20260525T105351Z ============
Primary build
  Proposal: A CLI that hardens product ideas via two-model debate.

Round 1 : peer challenge
  Concern: "assumes the user can write a structured artifact"
    why: vague input produces vague refinement
    fix: add a guided wizard that builds the artifact from prompts

Round 1 : primary rebuttal
  accept  "added a setup wizard that elicits the 7 fields"

HARDENED IDEA
  A CLI where two frontier peers turn a rough idea into a buildable one,
  with a guided wizard so the input is always structured.

  What got stronger: input quality, concrete role assignment
  Open decisions (your call): which providers to default to
  Watch items: cost per run at 4 rounds

Completed all 1 planned round(s) of refinement.
```

---

## Cost and rounds

- Cost is estimated before every run from litellm's price map and a per-role output budget. A run is the primary build, then each round's challenge and rebuttal, then one synthesis. The estimate prints first and you confirm before any calls, unless you pass `--yes`.
- Rounds default to 2 and cap at 4. Each round deepens the refinement; more rounds means a tighter idea at higher cost.

---

## Out of scope

- General chat or question answering
- Code review or bug fixing
- Consensus building, answer averaging, or roleplay
- Real-time multi-user collaboration
- Deterministic task automation

---

## API keys

MARS needs one key per provider you map a role to. The recommended place to put them is the macOS Keychain, scoped to MARS.

Store each key under the account `mars`, with the service name equal to the provider's variable. The command below prompts for the key with hidden input and a retype, so it never lands in your shell history:

```bash
security add-generic-password -a mars -s ANTHROPIC_API_KEY -w
security add-generic-password -a mars -s OPENAI_API_KEY -w
```

Then confirm MARS can see them. Values are never printed, only whether each key was found:

```bash
mars keys status --config config.yaml
```

A Keychain entry under account `mars` always wins over a shell variable of the same name, so a dedicated MARS key takes precedence over a stale or shared global key. If there is no Keychain entry, MARS falls back to the shell environment, which is handy on CI or non-macOS machines.

To rotate or remove a key:

```bash
security add-generic-password -a mars -s OPENAI_API_KEY -w -U   # update in place
security delete-generic-password -a mars -s OPENAI_API_KEY      # remove
```

---

## Security

- No keys in code. Keys come from the macOS Keychain (account `mars`) or environment variables, read at startup.
- `.env`, session logs, and credential files are gitignored. Only `.env.example` is tracked.
- Session logs are written locally to `~/.mars/sessions/` and never sent anywhere.

---

## License

MIT. See `LICENSE`.
