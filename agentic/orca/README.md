# Running local-LLM agent swarms with Orca's native orchestration

Orca **already is** the orchestrator. It ships a first-class coordination layer —
task DAGs with dependencies, dispatch, worker lifecycle, decision gates,
concurrency caps, and a circuit breaker. Do not build a parallel one; wire the
local stack into what exists.

> Read the authoritative, version-matched guide before coordinating:
> ```sh
> orca skills list
> orca skills get orchestration     # DAGs, dispatch, worker_done, gates
> orca skills get orca-cli          # worktrees, terminals, handoffs
> ```
> Those ship with the installed CLI and track your Orca version. This file only
> covers what is **specific to this rig** — the local model profiles, the
> concurrency ceiling, and the file-collision discipline Orca leaves to you.

Verified against **Orca 1.4.161**, opencode **1.17.14+**, on the rig's RTX 3090 Ti.

---

## What Orca gives you, so you don't rebuild it

| Need | Orca command |
|---|---|
| Task DAG with dependencies | `orca orchestration task-create --spec <text> --deps '["<id>"]'` |
| What's runnable now | `orca orchestration task-list --ready --json` |
| Assign to a worker | `orca orchestration dispatch --task <id> --to <handle> --inject` |
| Block until a worker finishes | `orca orchestration check --wait --types worker_done,escalation,decision_gate --timeout-ms 900000` |
| Concurrency cap | `orca orchestration run --spec <text> --max-concurrent 4` |
| Retry bound | built in — 3 consecutive failures circuit-breaks the task to `failed` |
| Decision gates | `orca orchestration gate-create` / `gate-resolve` |
| Worker isolation | `orca worktree create --name <n> --agent opencode` |

Task statuses: `pending`, `ready`, `dispatched`, `completed`, `failed`, `blocked`.

**Preconditions:** `orca status --json` shows `runtime.state: ready`, and
**orchestration is enabled in Settings → Experimental** (it is an experimental
feature; the commands exist but will not coordinate without it).

---

## Rig-specific: the settings that matter here

### `--max-concurrent 4`

Match `coder-swarm`'s `--parallel 4`. Running more workers than llama.cpp slots
does not add throughput — it queues head-of-line. Measured on this rig: 4
concurrent requests completed in 1.691–1.695 s, i.e. genuinely parallel.

Going wider is unlikely to pay. llama.cpp aggregate throughput scales only
~1.2–1.9× from 1→8 concurrency, so 8 workers makes each ~4× slower to buy ~1.9×
total work. **Experiment 2** in `docs/plans/2026-07-30-001-*.md` measures the real
`-np` curve; adjust both numbers together if it says otherwise.

### Coordinator thinks, workers execute

| role | model | reasoning | sampler |
|---|---|---|---|
| coordinator (you) | `coder-strong` or `coder` | **on** | 0.6 / 0.95 |
| workers (ribs) | `coder-swarm` | **off** | 0.7 / 0.8 |

Decomposition is the expensive cognitive step and happens once. Workers execute
pre-decomposed tasks and run with reasoning off, because output tokens are the
scarce resource (~0.4–0.7M tok/hr rig-wide) and a measured smoke test showed
reasoning consuming an entire 5-token budget with empty `content`.

The sampler must move with the reasoning flag — 0.6/0.95 are *thinking-mode*
values and are wrong on a non-thinking profile. The `rib` agent carries the
correct pair.

### Launching a worker on the swarm profile

```sh
orca terminal create --worktree active --title <task-name> \
  --command "opencode --agent rib" --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json
orca orchestration dispatch --task <task_id> --to <handle> --inject --json
```

`--agent rib` is what pins the worker to `coder-swarm` with the right sampler and
the `worker_done` protocol. Plain `--agent opencode` gets you the `build` agent on
`coder` at 0.6/0.95 with reasoning **on** — wrong on all three counts.

Deploy the agent first: `cp agentic/opencode/agents/rib.md ~/.config/opencode/agents/`

### Keep Orca off the GPU

Run Orca with **`--disable-gpu`**. Its Chromium otherwise holds VRAM (idle ~0.4 GB,
spiking ~8 GB) against a profile with ~2.4 GB of headroom, and will OOM a fresh
model load.

---

## The one thing Orca does not do: file collisions

Orca isolates *worktrees*, not *files*. Its own guidance is to put parallel
workers in the **same** worktree and create a new one only on a concrete
filesystem conflict — which makes overlapping edits a live concern, not a
theoretical one.

There is no `owns` field to enforce. **The boundary goes in the task spec**, and
the `rib` agent is instructed to respect it and to `ask` rather than widen scope:

```sh
orca orchestration task-create --task-title "auth endpoints" --spec \
'Implement POST /auth/login and POST /auth/logout.

FILES YOU MAY MODIFY — other workers are running concurrently:
  - app/routes/auth.py
  - app/routes/__init__.py

Import shared types from packages/types; do NOT edit them, another task owns
them. Verify with `just verify-fast` before reporting done.' --json
```

Rules that keep a parallel wave safe:

- **Every task in the same wave names a disjoint file set.** Two tasks that need
  the same file are either one task, or one depends on the other via `--deps`.
- **Prefer a dependency over a shared file.** Chains deeper than 3–4 steps are
  discouraged by Orca's own guidance; wide-and-shallow beats deep.
- **If files genuinely cannot be separated, isolate the checkout** —
  `orca worktree create --name <n> --agent opencode --no-parent` — and merge
  serially.
- **Merge one worker at a time**, re-running the full suite between each.
  Parallel merges are where "all workers passed" becomes "main is broken".

---

## Coordinator loop

Two options. Start manual — it makes the lifecycle visible while you learn what
this hardware does.

**Manual** (full control):

```sh
orca orchestration task-create --task-title "schema"  --spec "..." --json     # -> task_a
orca orchestration task-create --task-title "types"   --spec "..." --json     # -> task_b
orca orchestration task-create --task-title "models"  --spec "..." --deps '["task_a"]' --json

orca orchestration task-list --ready --json          # what can start now

# one worker per ready task, up to 4
orca terminal create --worktree active --title schema --command "opencode --agent rib" --json
orca terminal wait --terminal <h> --for tui-idle --timeout-ms 60000 --json
orca orchestration dispatch --task task_a --to <h> --inject --json

# block until something finishes; loop once per outstanding worker
orca orchestration check --wait --types worker_done,escalation,decision_gate \
  --timeout-ms 900000 --json
```

**Automatic** (Orca drives the loop):

```sh
orca orchestration run --spec "<overall goal + decomposition guidance>" \
  --max-concurrent 4 --json
orca orchestration task-list --json      # poll progress
orca orchestration run-stop --json
```

### Waiting correctly

- A `check --wait` timeout or `{count:0}` is a **checkpoint, not a failure.**
  Real coding tasks run 15–60 minutes; on a shared local GPU at ~24 tok/s per
  slot under load, expect the upper end. Keep using rolling waits.
- **Heartbeats and terminal activity mean alive, not done.** Never kill a worker
  for being quiet.
- `check --wait` returns **one** message at a time. If N workers may finish
  together, loop N times and dispatch newly-ready tasks after each completion.
- Answer `decision_gate` messages with
  `orca orchestration reply --id <msg_id> --body <answer> --json`, then resume waiting.

---

## Handoff vs orchestration

Orca draws a sharp line, and getting it wrong creates lifecycle obligations
nobody is watching:

- **"hand off" / "give this to another agent" = ownership transfer.** Use
  `orca worktree create --agent <a> --prompt "..."` or `orca terminal send`, then
  **stop monitoring**. Do not create tasks or dispatch with `--inject`.
- **Orchestration is for supervision** — only when you actually intend to wait on
  `worker_done`, coordinate a DAG, or run decision gates.

---

## Verifying a run was really orchestrated

```sh
orca orchestration task-list --json
orca orchestration dispatch-show --task <task_id> --json
```

If work ran outside Orca orchestration, say so plainly rather than describing it
as orchestrated — there is no task/dispatch provenance to point at.

Recovery only: `orca orchestration reset --tasks|--messages|--all --json` clears
runtime-global state. Never during an active run.
