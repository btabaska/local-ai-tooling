---
name: pr-summary
description: >-
  Summarize a pull request or a local diff into a reviewer-ready brief: what changed, why,
  risk areas, and a suggested review checklist. Use when asked to "summarize this PR",
  "write up this diff", or prep an external-contributor PR for review.
license: MIT
metadata:
  audience: maintainers
---

# PR / diff summary

<!--
  This is a portable Agent Skill (Anthropic Agent Skills spec). OpenCode discovers it via the
  native `skill` tool using ONLY the name + description above — the body below is loaded on demand.
  The SAME folder works in Claude Code, Codex, and OpenCode because they all read SKILL.md.
  A folder may also contain scripts/, references/, and assets/ that you reference from here.
-->

Produce a concise brief a human reviewer can act on in under two minutes.

## Steps
1. Gather the change set. For a local branch: `git diff --stat main...HEAD` then `git diff main...HEAD`.
   For a GitHub PR, use the github MCP/CLI if available. Keep raw diff out of your final output.
2. Use Serena to map impact: `get_symbols_overview` on touched files and `find_referencing_symbols`
   on any changed public function/type to gauge blast radius.
3. Write the brief with these sections, terse:
   - **What changed** — 2–4 bullets, plain language.
   - **Why** — the intent, inferred from the diff + PR description.
   - **Risk & blast radius** — files/callers affected, migrations, config, security-sensitive spots.
   - **Test coverage** — what's tested, what's not.
   - **Reviewer checklist** — 3–6 concrete things to verify before merging.
4. If this is an external/first-time contributor, add a **Maintainer notes** line: licensing/DCO,
   CI status, and whether it matches project conventions (see AGENTS.md).

## Output
Markdown only. No raw diffs. No praise. Flag anything that should block merge explicitly.
