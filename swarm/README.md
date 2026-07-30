# swarm/ — orchestration layer for local-LLM agent swarms (ai-10, tier 5)

Everything below the orchestration layer is done and measured: correct client
configs, a verification loop, a tool budget, 4 parallel llama.cpp slots, prefix
caching at 19.3×, and a reasoning split between the deep and swarm profiles. What
was missing is the part that stops four agents editing the same file.

**Division of labour — `swarm.py` deliberately does not launch anything:**

| | responsibility |
|---|---|
| `swarm.py` | plan validation, the collision invariant, claims, retry policy, run state |
| **Orca** | git worktrees, launching agents, watching them |
| `coder-swarm` | 4 parallel slots, reasoning off, instruct sampler |

Orca is already deployed, worktree-native, and configures its model backend
per-agent — which is why it works with LiteLLM at all. Re-implementing worktree
management would be duplicated effort for no gain.

---

## The one invariant

> Any two tasks that can run at the same time must own **disjoint** file sets.

"Can run at the same time" means neither is a transitive dependency of the other.
`swarm.py validate` proves it by expanding every task's `owns` globs against the
real worktree and intersecting them, then falls back to pattern comparison for
files that do not exist yet. **Run it before every swarm.** It is the only thing
standing between a swarm and a pile of merge conflicts.

A plan that fails validation is not a plan. Fix it by narrowing `owns`, or by
adding a dependency so one task waits for the other.

## Workflow

```sh
# 0. once per repo: decompose into tasks (SPINE work — single-threaded,
#    on `coder`/`coder-strong` with reasoning ON)
cp swarm/tasks.example.yaml <target-repo>/.swarm/tasks.yaml

# 1. prove the plan is safe. non-zero exit = do not start.
./swarm/swarm.py validate

# 2. what can start right now, given the WIP cap and what is already running
./swarm/swarm.py next

# 3. for each task: claim it, get its prompt, hand it to Orca
./swarm/swarm.py claim  api-endpoints
./swarm/swarm.py prompt api-endpoints        # paste into an Orca rib worktree

# 4. record the outcome
./swarm/swarm.py done api-endpoints
./swarm/swarm.py fail api-endpoints --reason "tsc: 3 errors"

# 5. any time
./swarm/swarm.py status
```

## Retry once, then park

A 35B model usually fixes its own verify failure when handed the error once — the
tier 1 Stop hook rests on the same observation and the same bound. Past that,
further attempts burn a shared GPU on something that is not converging.

So the second `fail` **parks** the task: the worktree is left intact for
inspection, downstream tasks are named in the warning, and **the rest of the swarm
keeps running**. Overnight, one stuck task must not cost the whole window.

Unpark with `reset <id>` after fixing the task definition (or drop it from
`tasks.yaml`).

## Why claims are `O_EXCL`

`claim` creates its lock with `O_CREAT|O_EXCL`, which is atomic. Two runners
racing for the same task — you in a terminal, a cron job at 2am — cannot both
win. It is also why run state is plain files under `.swarm/run/`: it survives a
crash, and `ls` tells you the truth.

## Sizing

`--wip` defaults to **4**, matching `coder-swarm`'s `--parallel 4`. Running more
ribs than slots does not add throughput — it queues head-of-line. Measured on this
rig: 4 concurrent requests completed in 1.691–1.695 s, i.e. genuinely parallel.

Going wider is unlikely to pay: llama.cpp aggregate throughput scales only ~1.2–1.9×
from 1→8 concurrency, so 8 ribs makes each ~4× slower to buy ~1.9× total work.
**Experiment 2** in the plan measures the real `-np` curve for this card; adjust
`--wip` to match whatever it says.

## Writing a good `tasks.yaml`

- **`owns` is a write boundary, not a read boundary.** A task may read anything;
  it may only *write* what it owns. Keep the list tight — a broad glob like
  `src/**` serialises everything against it.
- **Prefer a dependency over a shared file.** If two tasks genuinely need the same
  file, they are one task, or one depends on the other.
- **Name files that do not exist yet.** `validate` handles them via pattern
  comparison, and it is how you claim a file before creating it.
- **One task = one verify gate.** If it cannot be checked mechanically, it is not
  ready to hand to a rib.
- Decomposition is spine work. Have `coder-strong` emit the file, then *read it* —
  `validate` catches collisions, not bad decomposition.

## Integration and review

Merge ribs **serially**, re-running the full suite each time — `swarm.py` does not
merge, deliberately. Parallel merges are where "all ribs passed" becomes "main is
broken". Review runs fresh-context afterwards and writes findings as *new tasks*
rather than inline fixes, so review never edits a file some rib still owns.

## Requirements

- Python 3.9+ and PyYAML (`sudo pacman -S python-yaml` / `brew install pyyaml`;
  `scripts/install-code-intel.sh` installs it)
- Orca running with **`--disable-gpu`** — its Chromium otherwise holds VRAM
  (idle ~0.4 GB, spiking ~8 GB) against a profile with ~2.4 GB of headroom
- The `rib` agent (`agentic/opencode/agents/rib.md`) deployed, which carries the
  `coder-swarm` model and the matching **temp 0.7 / top_p 0.8** instruct sampler
