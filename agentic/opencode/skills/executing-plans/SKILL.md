---
name: executing-plans
description: >-
  Use to work through an approved implementation plan task by task. Runs each task with TDD, an inline
  two-pass self-review, and a commit per green task. Triggers after writing-plans, or on "execute the
  plan", "start building", "work through the tasks".
license: MIT
---

# Executing plans — one green task at a time

Work the plan in order. Do **one task fully** before starting the next — this keeps the context small,
which matters on a local model.

## Per task
1. Re-read the task and the relevant code (prefer Serena's symbol tools over reading whole files).
2. Apply **test-driven-development** (RED → GREEN → REFACTOR).
3. **Inline self-review, two passes** (do this yourself — do not fan out to many parallel agents,
   which serialize on a single GPU):
   - Pass 1 — *spec compliance*: does this match the task and the design doc? Anything missing/extra?
   - Pass 2 — *quality*: bugs, error handling, naming, duplication, security-sensitive spots.
   Fix anything material before moving on.
4. Run the task's test(s) and the fast part of the suite. Green? `/commit`. Not green? fix, don't skip.
5. Update the plan file: check the task off, note any deviation.

## Guardrails
- If a task turns out to be wrong or too big, stop and revise the plan rather than forcing it.
- If you're touching many independent areas, consider a git worktree per stream (optional) — but for
  most solo work a single feature branch is simpler.
- After the last task, hand off to **requesting-code-review**, then **compounding-learnings**.
