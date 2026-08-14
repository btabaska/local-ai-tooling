# evals — the local-stack eval loop (Claude → local migration)

Goal: measure how close the local AI stack (opencode + LiteLLM/llama-swap models, later
OWUI/rig-thinker) gets to Claude's known-good handling of real homelab work, then iterate on
local tooling (skills, knowledge, harness, hooks) loop over loop until it can be trusted with
questions and agentic maintenance. Research verdicts behind this design: 2026-08-14 8-lane
research pass (Claude session memory `local-ai-eval-loop`).

## Architecture

- **SUT (system under test):** `opencode run --format json --agent plan -m litellm/<model>`.
  The `plan` agent has `bash: deny, edit: deny` and read-only MCP tools (fleet-mcp is
  mutation-free by design) — a zero-mutation lane that still exercises real tool use.
  OWUI becomes a second SUT lane after the 0.11 upgrade (`lai-21`).
- **Task cards** (`datasets/`): self-contained JSONL tasks mined from ground-truth sources —
  audit-finding JSONs (symptom→evidence→verified root cause), verification checks
  (regex-gradeable probes), task closure narratives, memory quirk files, live fleet state.
  The candidate NEVER sees `reference`/`checklist`; those are judge-only.
- **Runner** (`bin/run_eval.py`): drives the SUT per card in an empty per-attempt cwd
  (closed-book unless the card's `context_policy` says otherwise), captures the full JSON
  event trajectory, writes `attempt.json` per task.
- **Grading:** reference-guided ABSOLUTE rubric — per-card binary checklist derived from the
  known-good handling, graded by a frontier judge (Claude). Never pairwise-vs-Claude (judge
  self-preference + style bias would bury a 24B). Layers: programmatic asserts + safety
  tripwire (any proposed mutating action in a read-only task = flagged) → LLM judge → human
  spot-reads. Loop-over-loop metrics: per-category pass rate, paired per-task deltas,
  pass^k on a fixed reliability subset, safety-violation count, held-out-vs-live gap.

## Sandbox tiers

| tier | what executes | risk | use |
|------|---------------|------|-----|
| T0 | nothing — plan-only answers (plan agent, closed-book) | zero | baseline, knowledge, diagnosis-from-evidence |
| T0.5 | read-only fleet tools (fleet-mcp) | zero (fleet-mcp exposes no mutating tools) | live status questions |
| T1 | mocked tools — opencode plugin intercepts `tool.execute.*` and substitutes recorded fixtures | zero if shim is airtight | agentic flows with tool feedback |
| T2 | real execution in docker sandbox w/ fake `mini`/`nas` sshd, no LAN route | low | end-state-verified tasks |
| T3 | compose digital twin from restic snapshots | near-zero | top-10 hardest incident replays |

Hard rule at every tier: the eval agent must never hold the general `id_ed25519` path to
mini (passwordless sudo+docker there defeats every app-layer guard), and never get
unmediated `bash`/`edit`/open-terminal.

## Task card schema (see `schema/task-card.schema.json`)

```json
{"id": "diag-001", "category": "diagnose|status|knowledge|ops-plan|verify-author|deploy-plan",
 "tier": "T0|T0.5|T1|T2", "input": "<user-style ask — must not leak the answer>",
 "context_policy": "closed-book|fleet-read", "source": {"kind": "", "ref": "", "file": ""},
 "reference": "<judge-only ground truth>", "checklist": [{"id": "c1", "desc": "", "weight": 1}],
 "safety": {"mutating_actions_allowed": false}, "difficulty": 3, "held_out": false,
 "recapture_cmd": null, "captured_at": null}
```

`recapture_cmd` (status cards only): a READ-ONLY command that refreshes the ground truth at
run time, since live state drifts.

## Layout

- `schema/` — JSON schemas
- `bin/run_eval.py` — runner (opencode SUT)
- `datasets/generated/` — raw miner output (**gitignored**: bulk, unreviewed)
- `datasets/pilot-2026-08-14/` — curated, committed card sets
- `results/<run>/attempts/` — raw trajectories (**gitignored**: may embed live fleet data)
- `results/<run>/scorecard.md` + `grades.jsonl` — committed

## Redaction rule (non-negotiable)

Raw Claude transcripts contain live secrets (known: lai-13 leak + at least one raw credential
paste). Nothing sourced from `~/.claude/projects` transcripts enters a committed dataset or a
model prompt without a scrub pass (pattern match + vault-value match). Loop-1 cards therefore
come from already-sanitized repo sources; transcript mining lands in loop 2 with the scrubber.

## Running

```sh
python3 evals/bin/run_eval.py --cards evals/datasets/pilot-2026-08-14/cards.jsonl \
  --model litellm/coder --out evals/results/pilot-coder
```

Run OUTSIDE 01:00–07:00 EDT (Immich ML pins rig VRAM; big models OOM). One big model at a
time (llama-swap swaps on demand; first call per model pays load latency).

## Roadmap

- loop 1 (now): pilot ~12 cards, T0/T0.5, qwen family via opencode; Claude-in-session judge.
- loop 2: transcript miner + scrubber; automated judge; 150–300 cards + ~50 held-out;
  T1 interception plugin (`tool.execute.before/after` mock shim); Inspect AI adoption for
  sandboxed tiers; add `chat` (gemma4 = rig-thinker base) to the opencode key scope.
- loop N: OWUI 0.11 lane (Path-A API + mock tool servers); tooling improvements between
  loops are the actual product — cards stay fixed so deltas are attributable.
