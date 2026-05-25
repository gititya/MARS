# MARS

MARS runs a structured adversarial review over a decision before you commit to it. One model writes a grounded proposal, a second model from a different provider attacks it, and a third compresses the fight into a single concrete decision.

It exists because one model stabilizes on a plausible answer too fast. It produces something coherent and internally consistent, then under-attacks its own assumptions. MARS forces cross-model pressure: the attacker cannot share a provider with the proposer, so you do not get the same blind spots twice.

Use it for product direction, architecture calls, AI and workflow strategy, and high-stakes or hard-to-reverse decisions. Do not use it for bug fixes, routine implementation, or simple questions.

```bash
pip install -e .             # Python 3.11+
cp config.example.yaml config.yaml
mars run --artifact examples/prd-example.yaml --config config.yaml --dry-run
```

---

## How it works

1. **You write a structured artifact.** A YAML file with the decision, the proposal, your constraints, assumptions, fears, and tradeoffs. Vague prompts are rejected with a field-level error. This is the input that makes the review sharp instead of generic.
2. **You dry run first.** `--dry-run` validates the config and artifact, prints a cost estimate, and makes zero API calls. Nothing hits a provider until you confirm.
3. **The primary model proposes.** It restates the decision, recommends a direction, and names its own tradeoffs, assumptions, and points of low confidence. It does not defend itself.
4. **The adversarial model attacks.** A model from a different provider tears into the proposal. Every critique has to be falsifiable and state what would resolve it. It also names the missing problem, the unstated assumption, the absent stakeholder, and the most dangerous certainty.
5. **The orchestrator forces a decision.** It compresses the critiques, assigns a disposition to each, detects when a round just repeats the last one, and ends with one concrete action plus the objection you are most likely to ignore.

---

## Commands

```bash
mars run --artifact artifact.yaml --config config.yaml   # run a review
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
    model: gpt-4o
roles:
  primary: anthropic
  adversarial: openai
  orchestrator: anthropic
rounds:
  default: 2
  max: 4
```

Rules enforced in code, not just in the schema:

| Rule | Why |
|------|-----|
| At least 2 providers configured | The whole point is more than one model |
| Every role maps to a configured provider | No role can point at a provider you never set up |
| `primary` and `adversarial` must be different providers | Same provider gives correlated blind spots and kills the review |
| `orchestrator` may share with `primary` | Recommended default, saves a key |
| Rounds capped at 4 | Hard limit in code, config cannot raise it |

---

## Artifact fields

All required. Missing or blank fields fail before any API call.

| Field | What goes here |
|-------|----------------|
| `goal` | The decision being made or the thing under review |
| `artifact` | The proposal, PRD, design, or plan itself |
| `constraints` | Hard limits and non-negotiables |
| `assumptions` | What you currently believe to be true |
| `fears` | Where you think the risk is |
| `tradeoffs` | What you have already weighed |
| `context` | Who uses this and what system it lives in |

Optional but recommended: `stakeholders`, `decision`. See `examples/` for three complete artifacts.

---

## The three roles

- **Primary.** Writes the grounded proposal. Practical and concise. Does not pre-defend.
- **Adversarial.** Attacks the proposal and the artifact. Falsifiable critiques only, no contrarian noise. Put your strongest model here, it does the heavy lifting.
- **Orchestrator.** Compresses critiques across rounds, tracks dispositions, detects repetition, and forces the final call. Its last round is the final synthesis, there is no separate summary pass.

Each critique gets one disposition: `resolved`, `refuted`, `acceptable_risk`, `unresolved`, `decision_blocker`, or `requires_evidence`.

---

## The final decision

Every run ends with exactly one action, each with required specifics:

| Action | Comes with |
|--------|------------|
| `PROCEED` | What test or validation confirms it |
| `PROCEED_WITH_CONDITION` | The condition that must hold |
| `TEST_FIRST` | What to test and how |
| `ESCALATE` | To whom, on what question |
| `DEFER` | Until what is true |
| `DISCARD` | Why |

The synthesis also always reports the strongest objection you are most likely to dismiss, and the direction your bias is probably pulling you.

---

## Sample output

```text
============ MARS review : session 20260525T105351Z ============
Primary
  Recommendation: Build the CLI first, web app later.

Round 1 : adversarial
  major   "CLI assumes a technical user"   resolve: survey target users
  Missing problem: distribution
  Absent stakeholder: non-technical users
  Most dangerous certainty: "a CLI is enough to share"

FINAL SYNTHESIS
  ► TEST_FIRST
  Ship the CLI to 5 target users before building the web app.

  Strongest ignored objection: nobody installs CLIs
  Most likely operator bias: wants to build, not validate

Completed all 1 planned round(s).
```

---

## Cost and rounds

- Cost is estimated before every run from litellm's price map and a per-role output budget. The estimate prints first and you confirm before any calls, unless you pass `--yes`.
- Rounds default to 2 and cap at 4. If a round mostly repeats the previous one, the orchestrator flags it and the run stops early with a logged reason.

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
