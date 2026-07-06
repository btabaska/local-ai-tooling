---
description: Stage changes and create a Conventional Commit with a well-formed message
agent: build
---

Create a git commit for the current changes.

1. Run `git status` and `git diff --staged` (and `git diff` for unstaged) to see what changed.
2. If nothing is staged, stage the files relevant to a single logical change (do not blindly `git add -A`).
3. Write a Conventional Commits message: a `type(scope): summary` subject under 72 chars, then a
   short body explaining the *why*. Types: feat, fix, chore, refactor, test, docs, perf.
4. Show me the message and the file list, then commit. Do NOT push.

$ARGUMENTS
