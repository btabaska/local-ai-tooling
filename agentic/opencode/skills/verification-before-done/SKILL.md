---
name: verification-before-done
description: >-
  Use before saying a task is complete or a bug is fixed. Requires running the actual test/command and
  showing the result — evidence, not claims. Triggers on "done", "fixed", "that should work", "ready".
license: MIT
---

# Verification before done — evidence over claims

Local models are prone to declaring victory without checking. Don't. A task is done only when you have
*run the check and seen it pass*.

## Before you say "done", confirm and show:
- The **relevant tests pass** (paste the command + the passing result).
- The **broader suite** isn't broken (run at least the fast subset).
- **Lint/typecheck** are clean (see AGENTS.md for commands).
- For a bug fix: the **regression test that reproduced it now passes**, and you can explain the root cause.
- For anything user-facing: you actually exercised it (run it, or use a browser/API tool), not just read the code.

## Never
- Never claim a fix works because it "should." Run it.
- Never hide a failing check. If something's still red, say so and either fix it or flag it explicitly.

If you can't verify (e.g., no way to run it), say exactly what you couldn't check and why.
