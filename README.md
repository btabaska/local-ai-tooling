# The Agentic Layer — getting OpenCode + Open WebUI close to Claude, on your rig

This extends the base `local-ai-stack` from "models on the network" to "agents, skills, and tools."
It's the answer to *what tooling do OpenCode and Open WebUI need to feel like Claude* — grounded in
how senior engineers actually run OpenCode (Omer Hamerman / DevOps Toolbox and the broader 2026
patterns), and scoped hard to what a **24 GB RTX 3090 Ti + i7-12700K + 64 GB** can run.

> **The one idea that shapes everything below:** a coding agent = **model × harness**. Claude ships a
> huge-context, rock-solid-tool-calling model *and* a great harness. Locally you can't match the model,
> so the **harness has to carry more weight** — and the harness's job on a 24 GB box is mostly
> *spending context wisely*, because context (VRAM for KV cache on a small model) is your scarcest
> resource. Every recommendation here is either "add a capability" or "spend fewer tokens getting it."

---

## 1. What "the workflow" actually is (DevOps Toolbox, distilled)

Omer's setup and the senior-eng consensus in 2026 aren't about one magic model — they're about a
disciplined loop and a well-built harness around a terminal agent:

- **Plan before build.** Start in a restricted **Plan** agent (no edits), agree the approach, then
  switch to **Build**. This is the single highest-leverage habit; it stops the agent thrashing.
- **Delegate to subagents.** Push narrow work (review, tests, research) to **subagents** so the main
  session's context stays clean. Each subagent has its own model, prompt, and permissions.
- **Encode conventions once.** An `AGENTS.md` per repo is the agent's onboarding doc. Detailed,
  repeatable procedures go in **skills** (loaded on demand), not in the always-on prompt.
- **One-shot the boring stuff.** Custom **/commands** for commit, test, PR-summary, release.
- **Give it senses.** **MCP servers** and **LSP** so the agent can navigate code semantically, read
  current library docs, hit git/GitHub, and drive a browser — instead of guessing.
- **Config is code.** The whole setup lives in dotfiles (`~/.config/opencode/…`) and version control.

OpenCode is the right base for this: MIT-licensed, provider-agnostic (so your model choice is free to
change), and it has surged past Claude Code in community momentum — which means the skills/plugins/MCP
ecosystem is where the energy is.

---

## 2. OpenCode's capability map

Three layers, plus the plumbing. (Config precedence: project `.opencode/` > global
`~/.config/opencode/` > org remote. Configs and markdown files both work.)

| Layer | What | Where | Notes for a 24 GB rig |
|---|---|---|---|
| **Agents** | Primary (Build, Plan) + subagents (General, Explore, Scout, + custom) | `agents/*.md` or `agent{}` in config | Subagents run in child sessions → **context isolation**. Give each the smallest model + permissions that work. |
| **Rules** | `AGENTS.md` — project conventions, always in context | repo root / global | Keep it **lean** (< ~150 lines). Reads `CLAUDE.md` too. `/init` drafts one. |
| **Skills** | `SKILL.md` playbooks, **loaded on demand** | `skills/*/SKILL.md`, also `.claude/skills/`, `.agents/skills/` | The big Claude-parity win — see §3. Progressive disclosure = cheap. |
| **Commands** | `/name` one-shot prompt templates | `commands/*.md` | Great for commit / test / PR / release. `$ARGUMENTS`, subtask flag. |
| **Plugins** | TypeScript hooks/tools, from npm or `plugins/` | `plugins/`, `plugin[]` | Extend behavior (e.g. the community skills plugin predated native skills). |
| **MCP** | External tools (local stdio or remote HTTP) | `mcp{}` in config | **Every server's schemas cost context.** Enable few; gate heavy ones per-agent. |
| **LSP** | Built-in language-server diagnostics | automatic | Runs on CPU. Pairs with Serena (§4). |
| **Permissions** | Per-tool allow/ask/deny, glob bash rules | agent + global | `read, edit, bash, task, webfetch, websearch, lsp, skill, …` |
| **Snapshots** | Auto git-based undo/redo of agent edits | automatic | Disable on huge monorepos if indexing is slow. |

Advanced move that fits your "any machine" theme: run **`opencode serve`** on the rig (headless HTTP
API, optional mDNS `opencode.local`) and attach the TUI from laptops — avoids MCP cold-boot on every
run and keeps one warm backend.

---

## 3. Skills — the closest thing to Claude's Skills, and it's the same format

OpenCode implements the **Anthropic Agent Skills spec natively**: a skill is a folder with a
`SKILL.md` (YAML frontmatter: `name`, `description`, + markdown body), optionally bundling
`scripts/`, `references/`, `assets/`. At session start the agent sees only each skill's **name +
description**; it loads the full body **only when your request matches** (semantic match, not
keywords). That lazy loading is exactly why skills are perfect for a small-context local model.

Three things worth knowing:
- **It reads `.claude/skills/` and `.agents/skills/`.** So skills are portable across OpenCode, Claude
  Code, and Codex — and your **Nava Skills Hub** artifacts and the standard docx/pptx/pdf/frontend
  skills work in OpenCode unchanged. That's a real bridge between your day job and your rig.
- **Registries exist:** `skills.sh`, `agensi.io/skills`, the `agentskills.io` spec. "Superpowers" is a
  popular collection/methodology that turns the agent into a disciplined TDD engineer (there's an
  OpenCode Superpowers plugin mode). Install narrow, repo-relevant skills — not everything.
- **Gate them per agent** to avoid context bloat: `"tools": { "skills*": false }` globally, then
  enable specific ones (or enable per built-in agent). See `malhashemi/opencode-skills` for the pattern.

An example skill is included at `opencode/skills/pr-summary/SKILL.md` — deliberately shaped around your
external-contributor PR-review flow.

---

## 4. Code-intelligence tools (these matter *more* locally than for Claude)

A local model has a small context budget, so the difference between "grep a word and dump 2,000 lines"
and "fetch the three symbols that matter" is the difference between a working agent and one that
truncates your repo mid-task. These tools buy back context:

- **Serena** *(install first — biggest single upgrade).* An MCP server that gives the model
  **IDE-grade, symbol-level** understanding via LSP: `find_symbol`, `get_symbols_overview`,
  `find_referencing_symbols`, safe `rename_symbol`. 30+ languages, runs locally (CPU). Instead of
  reading whole files, the agent asks for exactly the symbol it needs. Config is in `opencode.json`;
  install via `uvx --from git+…/serena` (⚠️ **not** via MCP marketplaces — they ship stale commands).
- **Context7** *(you already use it).* Up-to-date library docs on demand, so the model stops
  hallucinating APIs. Add `use context7` to a prompt. Remote MCP, near-zero local cost.
- **repomix.** Packs a whole (small) repo into one AI-friendly file with token counts — handy for
  one-shot "understand this project" prompts or feeding a repo to a chat model. CPU only; `npx repomix`.
- **Built-in LSP** gives OpenCode live diagnostics; Serena adds the navigation/edit tools on top. Both
  are CPU.

Rule of thumb: **Serena + Context7 on; everything else off by default**, enabled per-agent when a task
needs it. The GitHub MCP in particular is a context hog — reach for `gh` in bash or gate it to one agent.

---

## 5. Which model — the 24 GB reality (mid-2026)

Your binding constraint isn't the tooling, it's a model that does **agentic tool-calling reliably** in
24 GB. As of July 2026 the Qwen tool-calling bug that used to plague Ollama has been fixed upstream
(Unsloth/llama.cpp; works in Ollama, LM Studio, Open WebUI), which removes the old reason to default to
Devstral. Current picks for 24 GB:

| Model | ~VRAM (Q4) | Role | Why |
|---|---|---|---|
| **Qwen3.6 27B** (Apache-2.0) | ~22 GB | **Default driver** | April 2026, "flagship-level coding in a 27B dense model," 256K context, dedicated `qwen3_coder` tool parser. Best all-round Qwen that fits. |
| **Qwen3.6 35B-A3B** | ~20 GB | Speed / context | MoE (~3B active) → fast + VRAM-lean; holds full 64K on 24 GB with a little offload. |
| **Devstral Small 24B** (Mistral, Apache-2.0) | ~14 GB | Agentic alternative | Dense, agent-first, very clean multi-file diffs; the conservative pick. ~2× the KV-cache cost of the MoEs, and slower. |
| **Qwen3-Coder 30B-A3B** | ~19 GB | Dedicated coder (older gen) | The Coder-branded distil; 256K, MoE, ~64% SWE-bench. Tool-calling now fixed — re-pull a current build. |
| **Gemma 4 31B** (you run it) | ~18 GB | Coding/technical chat | Strong at coding; weaker at long-horizon orchestration/tool-calling. Wired in for your testing. |

Not runnable on 24 GB (need a 2nd GPU): **Qwen3-Coder-Next** (80B/3B, ~71% SWE-bench, but ~48–52 GB at
Q4 — its 2-bit squeeze onto 24 GB is "a different model" and not worth it), and the frontier open
leaders (**GLM-5.2, Kimi K2.x, DeepSeek V4**).

Practical tuning (already baked into the base stack + configs):
- **Tool-calling reliability is model × quant × scaffold.** The Qwen fix only helps on *current* builds
  — re-pull, and on Ollama use a recent version so it picks up the fixed chat template. Low
  temperature (0.1) helps everything.
- **Context vs weights is a zero-sum fight in 24 GB.** OpenCode wants ≥64K; 20–22 GB weights + 64K KV is
  *tight*. Use `q8_0` KV + flash attention (base stack does this), watch `ollama ps`, and drop to
  49152/32768 if you see CPU offload. Qwen3.6 is 256K-native; if Ollama serves a short default context,
  set `OLLAMA_CONTEXT_LENGTH=65536`.
- **MoE is your friend on 24 GB.** The A3B models (Qwen3.6-35B-A3B, Qwen3-Coder-30B) activate ~3B params
  → faster and leaner than the dense 27B/Devstral; `--n-cpu-moe` offloads a few expert layers to CPU
  (you have the RAM) to buy back context.
- **Don't over-quantize.** For code, prefer higher quant when it fits; Q4 hurts exact-output tasks most.

Honest ceiling: the open-weight leaders that *beat* frontier Claude on some agentic benchmarks
(GLM-5.2, Kimi K2.x, Qwen3-Coder-Next 80B, DeepSeek V4) **do not fit** in 24 GB. On your rig you're in
the "very capable for individual-dev workflows, not multi-hour autonomous epics" band — which is
exactly the band the harness above is designed to maximize.

---

## 6. Open WebUI — the chat-side parity layer

Full setup in **`openwebui/SETUP.md`**. The short version of what closes the gap to Claude's app:
**Native tool calling** + **tools via mcpo** (Serena, fetch, time, sequential-thinking) + **RAG with
hybrid search** (`nomic-embed-text`) + **custom models** (your version of Projects/GPTs) + a couple of
**Functions** (an auto-memory filter ≈ Claude memory; a token tracker). All CPU/RAM.

---

## 7. Hardware scoping — what runs where

The reassuring part: **only the LLM touches the GPU.** Everything in the harness is CPU/RAM, and your
i7-12700K + 64 GB eats it for breakfast.

| On the GPU (24 GB — the real budget) | On CPU/RAM (effectively free for you) |
|---|---|
| Ollama serving one model (+ its KV cache) | OpenCode, Serena + language servers, repomix |
| A small helper model *can* co-reside (§ base stack) | LiteLLM, Open WebUI, mcpo, Postgres, Caddy |
| | All MCP servers (Node/Python), LSP diagnostics |

So the whole agentic layer adds ~nothing to VRAM pressure. Budget the GPU for the model + context;
spend CPU/RAM freely on tooling.

---

## 8. Putting it together — the recommended loop & starter kit

**Loop:** `Plan` (agree approach, read-only) → `Build` with Qwen3.6-27B (edits + bash, `git push` gated)
→ `@tester` writes/runs tests → `@reviewer` audits the diff → `/commit`. Serena answers "where/what"
throughout; Context7 answers "how does this library work."

**Starter kit (installed by `scripts/setup-agentic.sh`):**
- OpenCode + uv + repomix on each client; configs into `~/.config/opencode/`.
- Agents: tuned Build/Plan + `reviewer` + `tester` subagents.
- MCP: Serena + Context7 (heavy servers off by default).
- One command (`/commit`) and one example skill (`pr-summary`) to copy from.
- Models on the rig: `qwen3.6:27b` (default) + `qwen3.6:35b-a3b`, with `devstral:24b`, `code:opencode`, and `gemma4-code:64k` as switchable alternatives.

Then per repo: `opencode` → `/init` to draft its `AGENTS.md` → drop in `.opencode/skills/` for
project-specific playbooks (or symlink your Nava skills).

---

## 8.5 TDD + compound skill set (installed — the "close to Sonnet" engine)

The single biggest lever for closing the gap to Sonnet on local hardware isn't a bigger model — it's
**discipline**. Both Superpowers and Every's Compound Engineering are built on that thesis ("the
problem with AI coding isn't intelligence, it's discipline"). This layer ships a self-contained,
hardware-tuned blend of the two so you get it **out of the box, no plugins to wire up**.

**What's installed** (auto-triggering skills in `opencode/skills/`, plus agents and commands):

| Phase | Skill (auto-fires) | Command | What it enforces |
|---|---|---|---|
| Design | `brainstorming` | `/brainstorm` | Socratic Q&A → saved design doc. No code until approved. |
| Plan | `writing-plans` | `/plan` | Small, test-first tasks with exact paths (80% of the value is here). |
| Build | `test-driven-development` + `executing-plans` | `/implement` | **RED-GREEN-REFACTOR Iron Law**; inline two-pass self-review; commit per green task. |
| Review | `requesting-code-review` (→ `@reviewer`) | `/review` | One multi-lens pass (correctness/security/perf/arch/simplicity). |
| Compound | `compounding-learnings` | `/compound` | Write durable lessons into AGENTS.md / skills / `docs/lessons.md`. |
| Finish | `finishing-a-branch` | `/ship` | Full-suite verify, summary, commit/PR prep (no push without your go). |
| Always-on | `verification-before-done`, `systematic-debugging` | `/commit`, (`@debugger`) | Evidence over claims; root-cause not symptom. |

Because skills load on their **description** (progressive disclosure), you don't run any of this
manually — just describe the feature and the workflow fires. The commands are shortcuts when you want
to force a phase. Small, well-specified fixes skip straight to TDD.

**The key local adaptation.** Compound Engineering's signature `/review` **spawns 14+ specialist
agents in parallel** (security-sentinel, performance-oracle, architecture-strategist, …). On one
3090 Ti with a single loaded model that isn't parallel — it's 14 *sequential* model calls, slow and
context-heavy. So the review here is **collapsed into one structured multi-lens pass** (or 2–3
sequential focused passes for high-stakes changes), and execution uses **inline self-review** rather
than a fresh subagent per task. Same methodology, sized for your GPU. The **compound flywheel** is kept
intact — it's cheap (just writing notes) and it's what actually makes the system improve over time.

**Gemma 4 is wired in for your testing.** The config includes `gemma4:31b-it-qat` (chat/plan) and a
`gemma4-code:64k` variant built for Build mode, alongside the Qwen/Devstral roster. The default is now
Qwen3.6-27B (the Qwen tool-call bug is fixed, so there's no longer a reliability reason to prefer
Devstral), but switching Gemma 4 in is one step: `Ctrl+A` / `/models` in the TUI, or set
`"model": "ollama/gemma4-code:64k"` in `opencode.json`. A/B it against Qwen3.6 and Devstral
on your own repos and keep whatever wins.

**Want the real upstream instead?** Both support OpenCode natively — Superpowers via its bundled CLI,
Compound via `bunx @every-env/compound-plugin install compound-engineering --to opencode`. They're
maintained and battle-tested, but tuned for frontier models and cloud-scale parallel agents (Compound
can fan out 14–80 sub-agents). On your rig they'll serialize and run slowly. Reasonable path: run this
local set as your daily driver; if you later add a second GPU or lean on cloud fallback via LiteLLM,
layer the upstream plugins on top.

## 9. Install

```bash
cd local-ai-stack/agentic
chmod +x scripts/setup-agentic.sh
./scripts/setup-agentic.sh          # installs client tooling + configs; pulls models if run on the rig

# then, once per machine, edit the host in the config:
$EDITOR ~/.config/opencode/opencode.json     # cachybox.local -> your rig's IP / Tailscale name

# Open WebUI extras (chat-side parity): follow openwebui/SETUP.md
# Expanded shared tool host: docker/mcpo-config.json  (replaces the base stack's, then: docker compose restart mcpo)
```

## 10. What still won't match Claude (be honest with yourself)
- **Long-horizon autonomy.** Multi-hour, many-hundred-tool-call runs need the big models you can't fit.
  Keep tasks scoped; lean on Plan mode.
- **Tool-calling polish.** Even the best 24 GB models occasionally fumble a call where Claude wouldn't. The
  `reviewer`/`tester` gates and LiteLLM fallbacks are there to catch it.
- **Raw reasoning on gnarly bugs.** A 24 GB model will sometimes need you to point it at the answer —
  which is exactly why Serena (precise context) and a lean AGENTS.md (clear rules) matter so much.

For the things you *can* do — daily feature work, refactors, tests, reviews, PR prep, docs, all
private and offline — this setup gets genuinely close.
