---
name: requesting-code-review
description: >-
  Use to review a completed change before merge. Runs a single multi-lens review (security, correctness,
  performance, architecture, simplicity) and returns prioritized findings. Triggers on "review this",
  "is this ready to merge", or after executing-plans finishes.
license: MIT
---

# Code review — one pass, many lenses

Compound-engineering style review normally fans out to a dozen parallel specialist agents. On a single
GPU that just serializes into a dozen slow calls, so here we run **one structured pass covering all
lenses** (or hand to the `@reviewer` subagent). For high-stakes changes, do 2–3 focused sequential
passes instead of one.

## Review the diff through these lenses, in priority order
1. **Correctness** — logic bugs, off-by-one, wrong assumptions, unhandled cases, race conditions.
2. **Security** — injection, authz/authn, secrets, unsafe deserialization, SSRF (OWASP-ish).
3. **Data integrity** — migrations, transactions, N+1 queries, nullability.
4. **Architecture** — boundaries, dependency direction, does it fit existing patterns (check via Serena).
5. **Simplicity** — dead code, needless abstraction, duplication (YAGNI/DRY).
6. **Tests** — do they actually cover the change and its edge cases?

## Output
A prioritized list. Each finding: **severity** (blocker / major / minor), **file:line + symbol**,
**why it matters** (one line), **fix** (concrete). End with a verdict: SHIP / SHIP WITH NITS / NEEDS WORK.
**Blockers must be fixed and re-reviewed before finishing.** Then hand off to **compounding-learnings**.
