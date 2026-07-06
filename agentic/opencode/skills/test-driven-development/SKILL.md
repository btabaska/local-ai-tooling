---
name: test-driven-development
description: >-
  Use whenever writing or changing production code. Enforces strict RED-GREEN-REFACTOR: a failing
  test must exist before any implementation. Triggers on "implement", "write the code", "fix the bug",
  or any task that changes behavior. This is the core discipline — apply it by default.
license: MIT
---

# Test-Driven Development — the Iron Law

**No production code without a failing test first.** If you catch yourself writing implementation
before a failing test exists, delete it and start the cycle properly.

## The cycle, per unit of behavior
1. **RED** — write the smallest test that expresses the desired behavior. Run it. Watch it fail, and
   confirm it fails *for the right reason* (not a typo/import error).
2. **GREEN** — write the minimum code to make it pass. Nothing extra (YAGNI). Run the test; watch it pass.
3. **REFACTOR** — clean up names/duplication while the test stays green. Re-run.
4. **COMMIT** — commit this small, green, coherent step (use the `/commit` command).

## Rules
- One behavior at a time. Small steps beat big leaps, especially for a local model.
- A bug fix starts with a **regression test** that fails, reproducing the bug, then the fix.
- Never weaken or delete a test to make it pass. If a test is wrong, fix the test deliberately and say so.
- If you can't make the test pass, STOP and report — you may have found a real design problem.

Evidence over claims: you have not finished a step until you've *seen* the test go red then green.
