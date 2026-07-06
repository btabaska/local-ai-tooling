# AGENTS.md — operating rules for coding agents

<!--
  This file is ALWAYS in the model's context, so keep it lean (aim < ~150 lines). On a 24GB
  local model, every line here is context you don't get back. Put durable, high-signal rules
  only; push detailed how-tos into skills (loaded on demand) instead.
  OpenCode reads AGENTS.md; it also honors CLAUDE.md, so a repo set up for Claude Code works as-is.
  Generate a first draft in any repo by running `/init` inside OpenCode.
-->

## What this project is
<!-- One paragraph: purpose, stack, entry points. Example: -->
Python service (FastAPI) + React frontend. Backend in `app/`, frontend in `web/`, infra in `deploy/`.

## Golden rules
- Prefer **Serena's symbol tools** (`find_symbol`, `get_symbols_overview`, `find_referencing_symbols`)
  over reading whole files. Read a full file only when you must edit it.
- Make the **smallest change that satisfies the task**. No drive-by refactors.
- Always run the relevant tests/linters after a change and report the result before declaring done.
- Never commit secrets. Never run destructive commands without asking.
- If a task is ambiguous, ask ONE clarifying question in plan mode before writing code.

## Commands the agent may rely on
- Install: `uv sync` (backend), `pnpm install` (frontend)
- Test: `uv run pytest -q` · single test: `uv run pytest path::test_name`
- Lint/format: `uv run ruff check --fix` · `uv run ruff format` · `pnpm biome check --write`
- Typecheck: `uv run pyright` · `pnpm tsc --noEmit`
- Run: `uv run uvicorn app.main:app --reload` · `pnpm dev`

## Conventions
- Python: type hints required, functions small, no bare `except`.
- Commits: Conventional Commits (`feat:`, `fix:`, `chore:` …).
- Tests live next to code as `test_*.py` / `*.test.ts`.

## Do NOT
- Touch `deploy/prod/**` or anything under `secrets/`.
- Add dependencies without noting why in the PR description.
- Reformat files you didn't otherwise change.

## Workflow (skills auto-trigger — you don't have to invoke them)
For any non-trivial change, follow the loop: **brainstorm → plan → implement (TDD) → review →
compound**, then finish. The matching skills fire automatically; the `/brainstorm /plan /implement
/review /compound /ship` commands are shortcuts. Principles: plan and review are ~80% of the work;
tests come first (RED-GREEN-REFACTOR, no exceptions); verify with evidence before claiming done;
capture lessons so the next task is easier. Small, well-specified fixes can skip straight to TDD.

## Lessons (compounded)
<!-- The compounding-learnings skill appends one-line, durable lessons here. Keep them terse.
     Detailed narrative goes in docs/lessons.md; reusable procedures become skills. -->
- (none yet)
