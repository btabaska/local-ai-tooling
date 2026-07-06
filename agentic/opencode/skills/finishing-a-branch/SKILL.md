---
name: finishing-a-branch
description: >-
  Use to wrap up a completed piece of work before merge/PR. Runs the full suite, summarizes the change,
  and prepares the commit/PR. Triggers on "finish", "wrap up", "ready to merge", "open a PR", "ship it".
license: MIT
---

# Finishing a branch

Don't merge on vibes. Confirm the work is actually complete and leave a clean trail.

## Checklist
1. **Full suite green** — run the complete test suite + lint + typecheck (see AGENTS.md). Show the result.
2. **Review done** — the requesting-code-review pass ran and all blockers are resolved.
3. **Diff is clean** — no stray debug logging, no unrelated reformatting, no commented-out code, no secrets.
4. **Learnings captured** — the compounding-learnings step ran.
5. **Summary** — write a short change summary: what & why, notable decisions, test coverage, risks.
6. **Commit / PR** — use `/commit` for a Conventional Commit; for a PR, draft title + body from the
   summary and the design doc. **Do not push or merge without an explicit go from the human.**
7. **Cleanup** — if you used a worktree, note how to remove it; otherwise leave the branch ready.

Report the final state plainly. If anything is still red or unverified, say so — do not imply it's done.
