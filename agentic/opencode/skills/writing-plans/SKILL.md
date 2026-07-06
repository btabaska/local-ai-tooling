---
name: writing-plans
description: >-
  Use after a design is approved to turn it into an implementation plan. Breaks work into small,
  independently verifiable tasks with exact file paths and test steps. Triggers on "make a plan",
  "how should we build this", or right after the brainstorming skill saves a design.
license: MIT
---

# Writing plans — small, verifiable tasks

Write the plan for *an enthusiastic junior with no context and an aversion to testing*. If a step is
ambiguous, they'll get it wrong — so be explicit.

## Each task must have
- A one-line goal.
- **Exact file path(s)** to touch.
- What to change (function/symbol names — use Serena's `get_symbols_overview` to get them right).
- **The test first**: what test proves this task is done, and the command to run it.
- A size of roughly 5–15 minutes of work. Split anything bigger.

## Plan rules
- Enforce **TDD** (every task starts with a failing test), **YAGNI** (don't build what isn't asked),
  and **DRY** (reuse existing patterns — find them with Serena first).
- Order tasks so the suite is green after each one.
- List new dependencies separately with a one-line justification.

Save to `docs/plans/<slug>-plan.md`. Show the task list and get a "go" before executing. Then hand
off to **executing-plans**.
