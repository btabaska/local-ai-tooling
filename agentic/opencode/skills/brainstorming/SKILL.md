---
name: brainstorming
description: >-
  Use BEFORE writing any code for a new feature, refactor, or non-trivial change. Turns a vague
  request into a validated design through Socratic questions, then saves a design doc. Triggers on
  "build/add/implement X", "I want a feature that…", or any fuzzy ask. Skip for one-line fixes.
license: MIT
---

# Brainstorming — design before code

The most expensive failure is building the wrong thing. Do not touch code yet.

## Do
1. Ask clarifying questions in small batches (3–5 at a time), covering: the actual goal, users,
   inputs/outputs, edge cases, error behavior, constraints, and what's explicitly *out* of scope.
2. Surface 1–3 design alternatives with tradeoffs. Recommend one and say why.
3. Present the emerging design in short sections and get explicit approval on each before moving on.
4. When approved, write a design doc to `docs/plans/<slug>-design.md` with: Problem, Goals/Non-goals,
   Approach, Key decisions (+ why), Edge cases, Open questions. Keep it tight.
5. Hand off to the **writing-plans** skill.

## Don't
- Don't write implementation code.
- Don't assume unstated requirements — ask.
- Don't proceed while an open question could change the architecture.

Stop and get a human "go" before planning.
