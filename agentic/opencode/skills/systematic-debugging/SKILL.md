---
name: systematic-debugging
description: >-
  Use when investigating a bug, failure, or unexpected behavior. Enforces a reproduce → isolate →
  hypothesize → fix → verify method with evidence at each step. Triggers on "debug", "why is this
  failing", "this doesn't work", a stack trace, or a failing test you didn't expect.
license: MIT
---

# Systematic debugging — root cause, not symptom

Resist the urge to guess-and-patch. Work the method; it's faster than random edits, especially for a
local model.

## Steps
1. **Reproduce** — get a reliable, minimal repro. If you can, capture it as a **failing test** now
   (this becomes your regression test).
2. **Isolate** — narrow the surface: bisect, add targeted logging, use Serena's `find_referencing_symbols`
   to see who calls the suspect code. State what you've ruled in and out.
3. **Hypothesize** — write down the single most likely root cause and *why*. One hypothesis at a time.
4. **Test the hypothesis** — make the smallest change that would confirm or refute it. Observe the result.
5. **Fix** — implement the real fix (via TDD: the repro test goes green). Address the root cause, not the symptom.
6. **Verify** — run the repro test + suite (see verification-before-done). Explain the root cause in one line.

## Rules
- Change one thing at a time. Revert changes that don't help.
- If two hypotheses remain, design a test that distinguishes them rather than guessing.
- Capture the lesson afterward (compounding-learnings) so this class of bug is cheaper next time.
