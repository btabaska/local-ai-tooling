#!/usr/bin/env python3
"""swarm.py — task gatekeeper for local-LLM agent swarms (ai-10, tier 5).

WHAT THIS IS
------------
The ~200 lines no existing tool ships. Orca already does the parts it is good at
— git worktrees, launching agents, watching them. What it does NOT do is stop two
agents from editing the same file, bound retries, or decide what is safe to run
concurrently. That is this.

    swarm.py  = plan + gatekeep + track   (this file)
    Orca      = worktrees + execution     (already deployed)

DIVISION OF LABOUR
------------------
    validate   check the DAG and prove concurrent tasks cannot collide
    next       what is safe to start right now, honouring the WIP cap
    prompt     emit the exact prompt text to paste/feed into an agent
    claim      atomically take a task (O_EXCL — two runners cannot both win)
    done/fail  record the outcome; fail applies retry-once-then-park
    status     one-screen view of the run

THE CENTRAL INVARIANT
---------------------
Any two tasks that could run at the same time must own DISJOINT file sets.
"Could run at the same time" = neither is a transitive dependency of the other.
`validate` proves this by expanding each task's `owns` globs against the real
worktree and intersecting them. This is the single check that makes a swarm safe;
everything else is bookkeeping.

WHY RETRY-ONCE-THEN-PARK
------------------------
A 35B model usually fixes its own verify failure when handed the error once — the
tier 1 Stop hook is built on the same observation and the same bound. Past that,
more attempts burn a shared GPU on a task that is not converging. Parking keeps
the worktree intact for inspection and lets the rest of the swarm proceed, which
matters overnight: one stuck task should not cost the whole window.

STATE
-----
Plain files under `.swarm/run/`, so state survives a crash and is inspectable
with `ls`. Claims are `O_EXCL` creates — the same primitive used for task
claiming in multi-agent systems generally, and the reason two runners racing for
the same task cannot both succeed.

Usage:
    ./swarm/swarm.py validate                 # ALWAYS run this before starting
    ./swarm/swarm.py next                     # what is safe to start now
    ./swarm/swarm.py prompt api-endpoints     # prompt text for one task
    ./swarm/swarm.py claim  api-endpoints
    ./swarm/swarm.py done   api-endpoints
    ./swarm/swarm.py fail   api-endpoints --reason "tsc: 3 errors"
    ./swarm/swarm.py status
    ./swarm/swarm.py reset  --all             # clear run state, keep tasks.yaml
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import socket
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("swarm.py needs PyYAML.  Arch: sudo pacman -S python-yaml   macOS: brew install pyyaml\n"
             "(scripts/install-code-intel.sh installs it too)")

# Matches the `coder-swarm` llama-swap profile: --parallel 4. Running more ribs
# than slots does not add throughput, it just queues head-of-line.
DEFAULT_WIP = 4
MAX_ATTEMPTS = 2          # 1 try + 1 retry, then park. See module docstring.
DEFAULT_TASKS = ".swarm/tasks.yaml"
RUN_DIR = ".swarm/run"


# ---------------------------------------------------------------- model


class Task:
    __slots__ = ("id", "title", "goal", "owns", "deps", "verify", "agent", "notes")

    def __init__(self, raw: dict, index: int):
        missing = [k for k in ("id", "goal", "owns") if k not in raw]
        if missing:
            raise ValueError(f"task #{index}: missing required key(s): {', '.join(missing)}")
        self.id: str = str(raw["id"])
        self.title: str = raw.get("title", self.id)
        self.goal: str = raw["goal"]
        self.owns: list[str] = list(raw["owns"])
        self.deps: list[str] = list(raw.get("deps", []))
        self.verify: str | None = raw.get("verify")
        self.agent: str = raw.get("agent", "rib")
        self.notes: str = raw.get("notes", "")
        if not self.owns:
            raise ValueError(f"task '{self.id}': `owns` is empty — a task that owns nothing "
                             "cannot be checked for collisions. List the files it may write.")


def load_tasks(path: Path) -> list[Task]:
    if not path.exists():
        sys.exit(f"no task file at {path}\nStart from swarm/tasks.example.yaml")
    doc = yaml.safe_load(path.read_text()) or {}
    raw = doc.get("tasks")
    if not raw:
        sys.exit(f"{path} has no `tasks:` list")
    tasks = [Task(t, i) for i, t in enumerate(raw)]
    seen: set[str] = set()
    for t in tasks:
        if t.id in seen:
            sys.exit(f"duplicate task id: {t.id}")
        seen.add(t.id)
    for t in tasks:
        for d in t.deps:
            if d not in seen:
                sys.exit(f"task '{t.id}' depends on unknown task '{d}'")
    return tasks


# ---------------------------------------------------------------- graph


def ancestors(task_id: str, by_id: dict[str, Task], _seen: set[str] | None = None) -> set[str]:
    """Transitive dependencies. Also the cycle detector — a task reachable from
    itself means the DAG is not a DAG."""
    _seen = _seen or set()
    out: set[str] = set()
    for d in by_id[task_id].deps:
        if d in _seen:
            continue
        _seen.add(d)
        out.add(d)
        out |= ancestors(d, by_id, _seen)
    return out


def find_cycle(tasks: list[Task], by_id: dict[str, Task]) -> str | None:
    for t in tasks:
        try:
            if t.id in ancestors(t.id, by_id):
                return t.id
        except RecursionError:
            return t.id
    return None


def expand(globs: list[str], root: Path) -> tuple[set[str], list[str]]:
    """Expand globs against the real tree.

    Returns (matched paths, globs that matched nothing). Unmatched globs are not
    an error — a task legitimately owns files it is about to create — but they
    cannot be intersected by expansion, so they fall back to literal comparison.
    """
    matched: set[str] = set()
    unmatched: list[str] = []
    for g in globs:
        hits = {str(p.relative_to(root)) for p in root.glob(g) if p.is_file()}
        if hits:
            matched |= hits
        else:
            unmatched.append(g)
    return matched, unmatched


def globs_collide(a: list[str], b: list[str], root: Path) -> list[str]:
    """Reasons tasks a and b would collide. Empty list = provably disjoint."""
    reasons: list[str] = []

    a_files, a_new = expand(a, root)
    b_files, b_new = expand(b, root)

    both = a_files & b_files
    if both:
        sample = ", ".join(sorted(both)[:4])
        reasons.append(f"{len(both)} shared existing file(s): {sample}")

    # Files that do not exist yet: compare patterns directly, both directions,
    # so `src/api/*.ts` vs `src/api/routes.ts` is caught before it bites.
    for ga in a_new:
        for gb in b_new + list(b):
            if ga == gb or fnmatch.fnmatch(gb, ga) or fnmatch.fnmatch(ga, gb):
                reasons.append(f"overlapping pattern: '{ga}' vs '{gb}'")
    for gb in b_new:
        for ga in list(a):
            if fnmatch.fnmatch(ga, gb):
                reasons.append(f"overlapping pattern: '{gb}' vs '{ga}'")

    return sorted(set(reasons))


# ---------------------------------------------------------------- run state


def run_paths(root: Path) -> dict[str, Path]:
    base = root / RUN_DIR
    return {k: base / k for k in ("claims", "done", "blocked", "attempts")}


def ensure_dirs(root: Path) -> dict[str, Path]:
    p = run_paths(root)
    for d in p.values():
        d.mkdir(parents=True, exist_ok=True)
    return p


def state_of(tid: str, p: dict[str, Path]) -> str:
    if (p["done"] / f"{tid}.json").exists():
        return "done"
    if (p["blocked"] / f"{tid}.json").exists():
        return "blocked"
    if (p["claims"] / f"{tid}.json").exists():
        return "running"
    return "ready"


def attempts_of(tid: str, p: dict[str, Path]) -> int:
    f = p["attempts"] / f"{tid}"
    return int(f.read_text().strip() or 0) if f.exists() else 0


def ready_tasks(tasks: list[Task], p: dict[str, Path]) -> list[Task]:
    states = {t.id: state_of(t.id, p) for t in tasks}
    out = []
    for t in tasks:
        if states[t.id] != "ready":
            continue
        if all(states.get(d) == "done" for d in t.deps):
            out.append(t)
    return out


# ---------------------------------------------------------------- commands


def cmd_validate(tasks, by_id, root, args) -> int:
    print(f"validating {len(tasks)} task(s) against {root}\n")
    cyc = find_cycle(tasks, by_id)
    if cyc:
        print(f"FAIL: dependency cycle involving '{cyc}'")
        return 1
    print("  dependency graph is acyclic ....... OK")

    # Only pairs with no dependency path between them can ever run concurrently.
    problems = 0
    checked = 0
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            if b.id in ancestors(a.id, by_id) or a.id in ancestors(b.id, by_id):
                continue  # ordered by deps; cannot overlap in time
            checked += 1
            reasons = globs_collide(a.owns, b.owns, root)
            if reasons:
                problems += 1
                print(f"\nFAIL: '{a.id}' and '{b.id}' can run concurrently but both own files:")
                for r in reasons:
                    print(f"        - {r}")
                print(f"      Fix: narrow `owns`, or add a dep so one waits for the other.")
    if problems:
        print(f"\n{problems} collision(s) across {checked} concurrent pair(s). "
              "Do NOT start this swarm.")
        return 1
    print(f"  {checked} concurrent pair(s) own disjoint files ....... OK")

    orphan = [t.id for t in tasks if not t.deps]
    print(f"\n{len(tasks)} tasks, {len(orphan)} with no dependencies (the first wave): "
          f"{', '.join(orphan[:6])}{' …' if len(orphan) > 6 else ''}")
    print("validate: PASS")
    return 0


def cmd_next(tasks, by_id, root, args) -> int:
    p = ensure_dirs(root)
    running = [t.id for t in tasks if state_of(t.id, p) == "running"]
    slots = args.wip - len(running)
    ready = ready_tasks(tasks, p)

    if running:
        print(f"running ({len(running)}/{args.wip}): {', '.join(running)}")
    if slots <= 0:
        print(f"WIP cap reached ({args.wip}). Finish something before starting more.")
        return 0
    if not ready:
        pending = [t.id for t in tasks if state_of(t.id, p) not in ("done", "blocked")]
        print("nothing ready." + (f" waiting on deps: {', '.join(pending)}" if pending else " all tasks complete."))
        return 0

    # Never suggest a task that collides with something already in flight.
    safe = []
    for t in ready:
        clash = next((r for r in running if globs_collide(t.owns, by_id[r].owns, root)), None)
        if clash:
            print(f"  (holding '{t.id}' — owns files overlapping running '{clash}')")
        else:
            safe.append(t)

    print(f"\nsafe to start now (up to {slots}):")
    for t in safe[:slots]:
        att = attempts_of(t.id, p)
        print(f"  {t.id:<24} {t.title}" + (f"   [attempt {att + 1}/{MAX_ATTEMPTS}]" if att else ""))
    print(f"\n  ./swarm/swarm.py prompt <id>   # then hand to Orca")
    return 0


def cmd_prompt(tasks, by_id, root, args) -> int:
    t = by_id.get(args.id) or sys.exit(f"unknown task: {args.id}")
    p = ensure_dirs(root)
    att = attempts_of(t.id, p)
    verify = t.verify or "just verify-fast"
    print(f"""You are a rib worker in an agent swarm. Do exactly one task, then stop.

TASK: {t.title}
{t.goal}

FILES YOU MAY MODIFY — this is a hard boundary, other agents are working in this
repo right now and edits outside this list will be discarded:
{chr(10).join('  - ' + g for g in t.owns)}

WHEN YOU ARE DONE:
  1. Run: {verify}
  2. If it fails, fix it and run again. Do not stop on a failing gate.
  3. Report what you changed in two sentences. Do not start adjacent work,
     do not refactor files you were not given, do not fix unrelated problems
     you notice — note them instead and they become their own task.
{f'{chr(10)}NOTES: {t.notes}' if t.notes else ''}
{f'{chr(10)}⚠ RETRY {att + 1}/{MAX_ATTEMPTS}. A previous attempt failed its verify gate. Read the error first.' if att else ''}""")
    return 0


def cmd_claim(tasks, by_id, root, args) -> int:
    t = by_id.get(args.id) or sys.exit(f"unknown task: {args.id}")
    p = ensure_dirs(root)
    st = state_of(t.id, p)
    if st != "ready":
        print(f"cannot claim '{t.id}': state is {st}")
        return 1
    undone = [d for d in t.deps if state_of(d, p) != "done"]
    if undone:
        print(f"cannot claim '{t.id}': unmet deps: {', '.join(undone)}")
        return 1
    rec = {"task": t.id, "host": socket.gethostname(), "pid": os.getpid(),
           "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "attempt": attempts_of(t.id, p) + 1}
    path = p["claims"] / f"{t.id}.json"
    try:
        # O_EXCL: atomic. Two runners racing this line, exactly one wins.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        print(f"cannot claim '{t.id}': already claimed by another runner")
        return 1
    with os.fdopen(fd, "w") as f:
        json.dump(rec, f, indent=2)
    print(f"claimed {t.id} (attempt {rec['attempt']}/{MAX_ATTEMPTS})")
    return 0


def cmd_done(tasks, by_id, root, args) -> int:
    t = by_id.get(args.id) or sys.exit(f"unknown task: {args.id}")
    p = ensure_dirs(root)
    (p["claims"] / f"{t.id}.json").unlink(missing_ok=True)
    (p["done"] / f"{t.id}.json").write_text(json.dumps(
        {"task": t.id, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "attempts": attempts_of(t.id, p) + 1}, indent=2))
    unblocked = [x.id for x in ready_tasks(tasks, p)]
    print(f"done: {t.id}")
    if unblocked:
        print(f"now ready: {', '.join(unblocked)}")
    return 0


def cmd_fail(tasks, by_id, root, args) -> int:
    t = by_id.get(args.id) or sys.exit(f"unknown task: {args.id}")
    p = ensure_dirs(root)
    n = attempts_of(t.id, p) + 1
    (p["attempts"] / t.id).write_text(str(n))
    (p["claims"] / f"{t.id}.json").unlink(missing_ok=True)
    if n >= MAX_ATTEMPTS:
        (p["blocked"] / f"{t.id}.json").write_text(json.dumps(
            {"task": t.id, "attempts": n, "reason": args.reason,
             "parked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2))
        print(f"PARKED {t.id} after {n} attempt(s): {args.reason}")
        print("  Worktree left intact for inspection. The rest of the swarm continues.")
        downstream = [x.id for x in tasks if t.id in ancestors(x.id, by_id)]
        if downstream:
            print(f"  ⚠ blocks downstream: {', '.join(downstream)}")
    else:
        print(f"attempt {n}/{MAX_ATTEMPTS} failed: {args.reason}")
        print(f"  Retry with the error in context:  ./swarm/swarm.py prompt {t.id}")
    return 0


def cmd_status(tasks, by_id, root, args) -> int:
    p = ensure_dirs(root)
    buckets: dict[str, list[str]] = {"running": [], "done": [], "blocked": [], "ready": [], "waiting": []}
    for t in tasks:
        st = state_of(t.id, p)
        if st == "ready" and not all(state_of(d, p) == "done" for d in t.deps):
            st = "waiting"
        buckets[st].append(t.id)
    icons = {"running": "▶", "done": "✔", "blocked": "✖", "ready": "·", "waiting": "…"}
    print(f"swarm status — {len(tasks)} task(s), WIP cap {args.wip}\n")
    for k in ("running", "ready", "waiting", "blocked", "done"):
        if buckets[k]:
            print(f"  {icons[k]} {k:<8} {len(buckets[k]):>2}  {', '.join(buckets[k])}")
    if buckets["blocked"]:
        print("\nparked tasks need a human — inspect their worktrees, then either fix the")
        print("task definition and `reset <id>`, or drop it from tasks.yaml.")
    total, done = len(tasks), len(buckets["done"])
    print(f"\nprogress: {done}/{total} ({done * 100 // total if total else 0}%)")
    return 0


def cmd_reset(tasks, by_id, root, args) -> int:
    p = ensure_dirs(root)
    ids = [t.id for t in tasks] if args.all else [args.id]
    if not args.all and args.id not in by_id:
        sys.exit(f"unknown task: {args.id}")
    n = 0
    for tid in ids:
        for d in ("claims", "done", "blocked"):
            f = p[d] / f"{tid}.json"
            if f.exists():
                f.unlink(); n += 1
        a = p["attempts"] / tid
        if a.exists():
            a.unlink(); n += 1
    print(f"reset {len(ids)} task(s), removed {n} state file(s). tasks.yaml untouched.")
    return 0


# ---------------------------------------------------------------- cli


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", default=DEFAULT_TASKS, help=f"task file (default {DEFAULT_TASKS})")
    ap.add_argument("--root", default=".", help="repo root (default .)")
    ap.add_argument("--wip", type=int, default=DEFAULT_WIP,
                    help=f"max concurrent ribs (default {DEFAULT_WIP}, matching coder-swarm's --parallel 4)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, help_ in (("validate", "prove concurrent tasks cannot collide"),
                        ("next", "what is safe to start now"),
                        ("status", "one-screen view of the run")):
        sub.add_parser(name, help=help_)
    for name, help_ in (("prompt", "emit the prompt text for a task"),
                        ("claim", "atomically take a task"),
                        ("done", "mark a task complete")):
        s = sub.add_parser(name, help=help_); s.add_argument("id")
    s = sub.add_parser("fail", help="record a failed attempt (retry once, then park)")
    s.add_argument("id"); s.add_argument("--reason", default="verify gate failed")
    s = sub.add_parser("reset", help="clear run state for a task (or --all)")
    s.add_argument("id", nargs="?"); s.add_argument("--all", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    tasks = load_tasks(Path(args.tasks) if Path(args.tasks).is_absolute() else root / args.tasks)
    by_id = {t.id: t for t in tasks}
    if args.cmd == "reset" and not args.all and not args.id:
        sys.exit("reset needs a task id or --all")
    return globals()[f"cmd_{args.cmd}"](tasks, by_id, root, args)


if __name__ == "__main__":
    sys.exit(main())
