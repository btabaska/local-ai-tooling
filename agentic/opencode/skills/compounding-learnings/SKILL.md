---
name: compounding-learnings
description: >-
  Use at the end of a task or after a review to capture durable lessons so future sessions don't
  relearn them. Writes to AGENTS.md and docs/lessons.md. Triggers on "capture what we learned",
  "compound this", "update the rules", or right after a review/merge.
license: MIT
---

# Compounding — make the next task easier than this one

This is the step that turns a good session into a system that improves. Each unit of work should leave
the next one easier. Do this while the context is fresh.

## Capture
1. Ask: what did we learn that would have saved time if the agent had known it at the start?
   Candidates: a project convention, a gotcha, a pattern to reuse, a mistake to avoid, a command that works.
2. Sort each lesson into the right home:
   - **Durable rule / convention** → append a terse line to `AGENTS.md` (the always-on context). Keep it
     one line; AGENTS.md must stay lean.
   - **Reusable procedure** (multi-step, situational) → create or update a **skill** under `.opencode/skills/`.
   - **Narrative context / decisions** → append to `docs/lessons.md` with a date and one-line title.
3. Verify the learning: ask "would the system catch or handle this automatically next time?" If not,
   the note isn't good enough — sharpen it.

## Don't
- Don't bloat AGENTS.md with prose — one-liners only; push detail into skills or lessons.md.
- Don't record one-offs that won't recur.

Small, honest notes compound. Vague ones just add noise.
