# 05 — MCP Server Ecosystem & Local Tool Surface

**Research date:** 2026-07-30. All versions/dates verified live against GitHub/npm/PyPI/Codeberg/gitea.com APIs and primary docs on this date unless marked *unverified*.
**Target rig:** RTX 3090 Ti 24GB / 64GB / CachyOS / Docker. Local-only models behind LiteLLM (`https://llm.tabaska.us/v1`). Primary model `coder` = Qwen3.6 35B-A3B MoE, 131k ctx.
**Clients:** opencode, pi, Orca. Existing MCP: `context7` (cloud), `serena` (local), `fleet-mcp` (homegrown, via `mcpo`).

---

## 0. Three findings that change your current config

### 0.1 🔴 Your `serena` invocation is very likely broken (or about to break)

Your `opencode.json` runs:

```
uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --project {cwd}
```

**`ide-assistant` is no longer a valid context.** The contexts shipped on `main` today are, verbatim from
`https://api.github.com/repos/oraios/serena/contents/src/serena/resources/config/contexts`:

```
agent, antigravity, chatgpt, claude-code, codebuddy, codex, context.template,
copilot-cli, desktop-app, grok, ide, jb-ai-assistant, jb-copilot-plugin,
junie, oaicompat-agent, vscode
```

There is no `ide-assistant.yml`. The loader (`src/serena/config/context_mode.py`, `get_path()`) raises
`FileNotFoundError` when a name resolves to neither `~/.serena/contexts/<name>.yml` nor the bundled dir — there is **no
alias table**. The old name was renamed to **`ide`** (`https://raw.githubusercontent.com/oraios/serena/main/src/serena/resources/config/contexts/ide.yml`).

You are probably still running because `uvx --from git+…` is serving a cached older revision. The moment that cache is
invalidated, serena stops starting. **Fix: `--context ide`, and pin the version** (see §8).

Confidence: **high** that `ide-assistant.yml` is gone from `main`; **medium-high** that it hard-fails rather than warning
(I read the code path for `SerenaAgentMode.get_path`; `SerenaAgentContext` is the parallel class in the same file with
the same lookup shape). Verify locally with `serena context list`.

### 0.2 🔴 `pi` has no MCP support — by design

The premise in the brief ("pi supports MCP: local/stdio and remote/http") does not match upstream pi. From
`https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/README.md`, verbatim:

> **"No MCP. Build CLI tools with READMEs (see Skills), or build an extension that adds MCP support."**

pi ships 7 builtin tools (`read`, `write`, `edit`, `bash`, `grep`, `find`, `ls`) and extends via **Skills** (Agent Skills
standard, `/skill:name`) and **TypeScript extensions** (`pi.registerTool({...})`). Author Mario Zechner's rationale:
`https://mariozechner.at/posts/2025-11-30-pi-coding-agent/`.

**This is not a problem — it is the best news in this report.** The supported path is
[`pi-mcp-adapter`](https://pi.dev/packages/pi-mcp-adapter) (**v2.15.0**, MIT, `pi install npm:pi-mcp-adapter`,
repo `https://github.com/nicobailon/pi-mcp-adapter`), which is exactly the progressive-disclosure architecture you want
for a 30B model. See §6.2.

### 0.3 🟡 opencode has an experimental builtin `lsp` tool that overlaps ~60% of serena

Per `https://opencode.ai/docs/tools/`, opencode ships **13 builtin tools**: `bash`, `edit`, `write`, `read`, `grep`,
`glob`, **`lsp` (experimental)**, `apply_patch`, `skill`, `todowrite`, `question`, `webfetch`, `websearch`.

The `lsp` tool (enable with `OPENCODE_EXPERIMENTAL_LSP_TOOL=true`) supports `goToDefinition`, `findReferences`, `hover`,
`documentSymbol`, `workspaceSymbol`, `goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls` —
**as one tool**, versus serena's ~8 separate symbolic-read tools. If it works on your languages, that is a ~7-tool /
~900-token saving in opencode. **Action: A/B it before assuming serena is mandatory in opencode.** Confidence: **medium**
(docs confirm the tool and operations; real-world quality vs serena is unmeasured — no benchmark found).

---

## 1. Install these (ranked)

| # | Server | Purpose | Install (pinned) | Transport | Offline? | Tools (as configured) | ~Tokens | Why |
|---|---|---|---|---|---|---|---|---|
| 1 | **serena** v1.6.1 (2026-07-21) <br>`github.com/oraios/serena` | LSP-backed symbol nav + symbolic edit | `uv tool install -p 3.13 'serena-agent==1.6.1'` then `serena start-mcp-server --context ide --mode editing --mode no-memories --project {cwd}` | stdio | **Yes** (after LS download) | **~15** (from 38 classes; see §2.1) | ~1.9k | Still the best code-intelligence MCP in 2026. 30+ languages, actively shipped (v1.6.0/1.6.1 both July 2026). Symbol-level reads are the single biggest context saver for a 131k-ctx local model. |
| 2 | **docs-mcp-server** v2.4.5 (2026-07-25) <br>`github.com/arabold/docs-mcp-server` | **Offline context7 replacement** | `docker run … ghcr.io/arabold/docs-mcp-server:2.4.5 --protocol http --read-only` (+ a separate non-read-only ingest container) | stdio **or** streamable-HTTP (port 6280) | **Yes** once scraped | **3** in `--read-only` (`search_docs`, `list_libraries`, `find_version`); 10 unrestricted | ~450 | 3 tools for what context7 charges you a cloud round-trip for. Embeddings via `openai:<model>` + `OPENAI_API_BASE` → point straight at LiteLLM or Ollama. See §5. |
| 3 | **gitea-mcp** v1.5.0 (2026-07-27) <br>`gitea.com/gitea/gitea-mcp` | Forgejo issues/PRs at `git.tabaska.us` | `docker.gitea.com/gitea-mcp-server:v1.5.0 -t stdio -S issue,pull_request` (add `-r` for read-only agents) | stdio or http | **Yes** (LAN-only) | **~10** scoped (46 unscoped) | ~1.3k | **Only server here with per-tool filtering**: `-S/--scope` groups, `-O/--tools` individual names, `-r` read-only. Forgejo is a Gitea fork with a near-compatible v1 API. ⚠️ Forgejo compat is **unverified** — test first. |
| 4 | **chrome-devtools-mcp** v1.6.0 (2026-07-14) <br>`github.com/ChromeDevTools/chrome-devtools-mcp` | Browser verification (opt-in, one agent only) | `npx -y chrome-devtools-mcp@1.6.0 --slim` | stdio | **Yes** (local Chrome) | **3** with `--slim` (51 full) | ~400 | `--slim` (navigate / evaluate / screenshot) is the only browser footprint a 30B can carry. Category flags (`--categoryNetwork` etc.) let you grow deliberately. |
| 5 | **fleet-mcp** (yours) | Fleet ops, read-only | keep as-is; keep behind `mcpo` for Open WebUI | stdio → `mcpo` | Yes | your call — **keep ≤8** | — | Already read-only, which is the right shape. Enable **per-agent only**, not globally. |
| 6 | **ast-grep-mcp** <br>`github.com/ast-grep/ast-grep-mcp` (441★, pushed 2026-07-21) | Structural search/codemod where LSP has no coverage | `uvx --from git+https://github.com/ast-grep/ast-grep-mcp@<sha> ast-grep-server` | stdio | **Yes** | **4** (`dump_syntax_tree`, `test_match_code_rule`, `find_code`, `find_code_by_rule`) | ~550 | **Optional / situational.** Cheap at 4 tools, and complements serena (pattern-shaped queries LSP can't express). Self-described experimental; no tagged release found (*version unverified*). Only add if you actually do codemods. |

**Total if you install 1–4 + fleet-mcp: ~31 MCP tools ≈ 4.1k tokens**, on top of opencode's 13 builtins (~1.5–2k). ≈ 6k
of 131k context (~4.6%). That is acceptable **on token grounds** — but see §6.0 for why the *count* matters more than
the tokens.

---

## 2. Category-by-category survey

### 2.1 Code intelligence / semantic navigation

**serena — still the winner, but it has grown fat.** v1.6.1 on PyPI as `serena-agent`
(`https://pypi.org/pypi/serena-agent/json`, requires Python ≥3.11 <3.15). Source has **38 tool classes**
(counted from `src/serena/tools/*.py` on `main`):

- `file_tools` (10): `read_file`, `create_text_file`, `list_dir`, `find_file`, `replace_content`, `replace_in_files`, `delete_lines`*, `replace_lines`*, `insert_at_line`*, `search_for_pattern`
- `symbol_tools` (12): `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `find_implementations`, `find_declaration`, `get_diagnostics_for_file`, `get_diagnostics_for_symbol`*, `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol`, `restart_language_server`*
- `memory_tools` (6): `write_memory`, `read_memory`, `list_memories`, `delete_memory`, `rename_memory`, `edit_memory`
- `workflow_tools` (3): `onboarding`, `initial_instructions`, `serena_info`*
- `cmd_tools` (1): `execute_shell_command`
- `config_tools` (4): `open_dashboard`*, `activate_project`, `remove_project`*, `get_current_config`
- `query_project_tools` (2): `list_queryable_projects`*, `query_project`*

`*` = `ToolMarkerOptional` (off unless opted in) — 10 of them. So ~28 default-on.

**How to get from 28 → ~15** (all verified from the shipped YAML):
- `--context ide` excludes `create_text_file`, `read_file`, `execute_shell_command`, `find_file`, `list_dir` **and sets `single_project: true`**, which also kills `activate_project` and prunes tools to those the project config needs. → ~22
- `--mode no-memories` excludes all 6 memory tools **plus** `onboarding`. → ~15
- `--mode editing` additionally excludes `replace_lines`, `insert_at_line`, `delete_lines` (already optional).
- Anything left you dislike: `excluded_tools:` in `~/.serena/serena_config.yml` or the project's `.serena/project.yml` (the `ToolInclusionDefinition` base class exposes `excluded_tools`, `included_optional_tools`, `fixed_tools`).

Note also `--context oaicompat-agent`: *"All tools except InitialInstructionsTool … uses OpenAI compatible tool
definitions."* Since your models are served OpenAI-compatible via LiteLLM, this is worth a look **if** you see schema
rejection errors — but it excludes nothing else, so it costs you the full 28-tool surface. Prefer `ide` and fall back to
`oaicompat-agent` only on concrete tool-call failures. Also relevant: `SerenaAgentContext.structured_tool_output`
(`bool | None`, default auto) — flip to `false` if the 35B chokes on structured content.

**Competitors checked, none displace serena:**
- **opencode builtin `lsp`** — the real competitor *inside opencode only*. See §0.3.
- **ast-grep-mcp** — 4 tools, complementary not competing (syntax-pattern, not semantic).
- **Graph-based (GitNexus, CodeGraphContext, code-graph-mcp, codesight-mcp)** — surfaced in 2026 roundups
  (`https://sverklo.com/blog/practical-guide-mcp-code-intelligence/`, `https://rywalker.com/research/code-intelligence-tools`)
  but all require a build/index step and none matches serena's 30+ language LSP coverage. **Not verified individually —
  treat as unverified.** For polyglot repos serena wins on coverage.
- **Zoekt / comby / sourcegraph MCP** — no maintained, credible MCP wrapper found in this pass. `rg` via bash covers the
  lexical case at zero tool cost.

### 2.2 Docs / knowledge retrieval → see §5 (this is the big one)

### 2.3 Browser / web

| Server | Version | Default tools | Filtering | Verdict |
|---|---|---|---|---|
| **playwright-mcp** `microsoft/playwright-mcp` | npm `@playwright/mcp` **v0.0.78** | ~26–30 default (~67 total behind `--caps config,network,storage,devtools,vision,pdf,testing`) | `--caps` **group-level only**, no per-tool allowlist | ❌ **Skip.** ~3.5k tokens of schemas before doing anything (`https://www.jdhodges.com/blog/claude-code-mcp-server-token-costs/`), and a measured **~114k tokens/task over MCP vs ~27k via the Playwright CLI** (`https://bug0.com/blog/playwright-cli-vs-playwright-mcp-ai-browser-testing-2026`). The a11y-tree snapshot returned after *every* action is the real cost, not the schemas. |
| **chrome-devtools-mcp** | **v1.6.0 (2026-07-14)** | 51 across 9 categories | **`--slim` → 3 tools**, plus `--categoryPerformance/Network/Extensions/Emulation`, `--experimentalMemory/Vision/Devtools` | ✅ **Install at `--slim`.** Best filtering in the browser category. |
| **browser-use** | — | — | — | ❌ Skip. Python agent framework first, MCP second; oriented at standalone autonomous browsing with paid cloud stealth/CAPTCHA. Wrong shape. |

The 2026 trend is *away from MCP for browsers*: Microsoft shipped a **Playwright CLI** (2026-06-10) explicitly as the
token-efficient alternative, artifacts to disk, ~4× fewer tokens. **If you need real browser work, drive the CLI from
bash and spend 0 tool slots.**

### 2.4 Git / VCS / PR

- **`modelcontextprotocol/servers` git server** — still active (not archived; SQLite and Postgres reference servers *were*
  moved to `servers-archived`). `uvx mcp-server-git`, 12 tools, ~1.2k tokens, fully offline.
  **❌ Skip.** Your model already knows the git CLI cold from pretraining — that knowledge is free and composable
  (`git log --oneline -20 | rg fix`). 12 schemas cost 1.2k tokens forever and cover ~12 verbs (no rebase, stash, remote,
  cherry-pick). Also note CVE-2025-68143/68144/68145 (path traversal, argument injection, unrestricted write; fixed
  2025.12.18) — the reference servers are reference-grade. Counter-argument worth knowing: per-verb permission gating
  (`allow git_log`, `deny git_commit`) is cleaner with tools than with a bash allowlist, and tool args dodge
  shell-quoting disasters in commit messages — a genuine small-model failure mode. Net: still bash.
- **`github/github-mcp-server`** v1.8.0 (2026-07-30) — 24+ toolsets, `--toolsets`/`--read-only`, v1.8.0 adds a `fields`
  param for response-size filtering. **❌ Skip:** requires github.com, irrelevant to a self-hosted Forgejo homelab.
- **Forgejo — three candidates, and the ranking is counter-intuitive:**
  1. ✅ **`gitea-mcp` v1.5.0 (2026-07-27)** — `https://gitea.com/gitea/gitea-mcp`. 46 tools BUT the best filtering in this
     entire report: `-S/--scope` (18 scope groups), `-O/--tools` (individual named tools), `-r` read-only,
     `-t stdio|http`. Docker `docker.gitea.com/gitea-mcp-server`. **Forgejo compatibility is not officially documented**
     — Forgejo is a Gitea fork with a largely compatible v1 API so it very likely works. ***Unverified — test against
     `git.tabaska.us` before committing.***
  2. 🟡 **`goern/forgejo-mcp` v2.30.2 (2026-07-13)** — `https://codeberg.org/goern/forgejo-mcp`. Genuinely mature (1,125
     commits, biweekly releases v2.27→v2.30 across Jun–Jul 2026, 128★), Go, stdio + streamable-HTTP, `--url` for
     self-hosted instances, exposes MCP resources under a `forgejo://` scheme. **But 100+ tools and no documented
     filtering or read-only flag** — a hard no for a 35B unless you front it with a filtering proxy. ⚠️ The README claims
     migration to `git.b4mad.industries/agentic-forges/forgejo-mcp` and declares Codeberg a read-only mirror, yet
     Codeberg still published v2.30.2 on 2026-07-13; the new host refused connections during research. **Canonical home
     unverified — install from the Codeberg mirror.**
  3. ❌ **`ric_harvey/forgejo-mcp` v0.1.7** — 103 tools, no filtering, 14 commits, 0 stars, self-described "Built with
     Claude Code." Skip.

  **Fallback if Gitea-API compat fails:** put `goern/forgejo-mcp` behind MetaMCP or `mcp-proxy` and expose ~8 tools (§6.3).

### 2.5 Testing / execution / sandboxing

- ❌ **`dagger/container-use`** — latest release **v0.4.2, 2025-08-19**. ~11 months stale, still self-described
  "experimental." Not recommended for new adoption (maintenance status beyond the release feed *unverified*).
- ❌ **`pydantic/mcp-run-python`** — **archived and deprecated 2026-01-30.** Pydantic's own notice: *"there is just no
  safe way to run Python within pyodide safely"*; a sandbox-escape advisory exists
  (`https://advisories.gitlab.com/pkg/pypi/mcp-run-python`). Successor **`pydantic/monty`** (`pydantic-monty`, latest
  2026-07-24) is a Rust-hosted minimal Python for "code mode" — **no class declarations yet**, so not a test runner.
  Watch, don't install.
- 🟡 **Docker MCP Gateway** (`https://docs.docker.com/ai/mcp-gateway/`) — a proxy/aggregator that runs *other* MCP servers
  in isolated containers with credential injection and call tracing, not a sandbox for your code. Right shape for the
  security problem (§7), overkill for two clients. Docs indicate it is invite-only under Docker AI Governance —
  **availability to you unverified**.
- **Verdict: 0 tools.** You are not defending against a hostile model, you are defending against a mediocre one. The fix
  is git checkpoints + running the whole agent in a container, not a 15-tool sandbox server.

### 2.6 Memory / persistence — **skip all of it, and there's now data**

The strongest evidence in this whole report cuts *against* memory MCPs:

> **"Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?"** — Gloaguen, Mündler, Müller,
> Raychev, Vechev (ETH Zurich / DeepMind), published **2026-02-12**, `https://www.emergentmind.com/papers/2602.11988`.
> AGENTbench: 138 tasks, 12 real Python repos. **LLM-generated context files *decreased* success by ~0.5–2%.**
> Developer-written files gave only **~4%**. **Inference cost rose >20% in all settings**, **+2–4 tool steps** per task,
> reasoning tokens up to **+22%**. Decisive detail: when markdown/docs were *removed* from the repo, those same generated
> files improved performance by 2.7% — i.e. auto-generated memory mostly duplicates what the agent can already read.

Server-by-server:

| Server | State (verified) | Verdict |
|---|---|---|
| official `@modelcontextprotocol/server-memory` | **2026.7.4** (2026-07-04), active. 9 tools, JSONL file, substring search, fully offline | ❌ 9 tools (6 of them writes — the ones a 35B calls wrong) for a hand-maintained JSON file with no semantic search |
| **basic-memory** | PyPI **0.22.1** (2026-01-28), Py≥3.12. Markdown-on-disk + SQLite/`sqlite-vec`, local `fastembed`. **8 tools** in local mode, ~17–20 full | 🟡 The only defensible pick *if* pinned to the 8 local tools. Degrades gracefully — the store is grep-able markdown |
| **mem0 / OpenMemory** | **DEPRECATED/sunset** — *"OpenMemory is now deprecated and has been sunset in favor of the unified Mem0 self-hosted server"* (`https://deepwiki.com/mem0ai/mem0/15.1-openmemory-overview-and-migration`); `/openmemory` paths 404 | ❌ **Do not adopt.** Also: an LLM call on *every memory write*, contending with your 35B for 24GB of VRAM |
| **cipher** (byterover) | npm `@byterover/cipher` **0.3.0, 2025-08-28**, carries an explicit npm deprecation → `byterover-cli` | ❌ Dead |
| **memory-bank-mcp** | ~916★, **zero published releases** | ❌ Remote-mounted markdown CRUD your builtin read/write already does |

**Recommendation:** a short, *hand-written* `AGENTS.md` (the only variant that measured positive) plus a grep-able
`notes/` directory. **Zero tool slots, zero VRAM.** Revisit basic-memory only after you've measured a concrete gap.

### 2.7 Filesystem / search — **categorically redundant, install nothing**

opencode ships `read`, `write`, `edit`, `grep`, `glob`, `bash`, `apply_patch`. pi ships `read`, `write`, `edit`, `bash`,
`grep`, `find`, `ls`.

- `@modelcontextprotocol/server-filesystem` **2026.7.10** — actively released, 13 tools, offline, supports MCP Roots.
  **Adding it would roughly double your file-tool count (13 → 26) with near-total semantic overlap.** This is the classic
  small-model failure: the 35B picks `fs_read_text_file` over builtin `read`, or oscillates between `fs_search_files`
  and `grep`. ❌
- `mcollina/mcp-ripgrep` (5 tools), `benpiper/ripgrep-mcp`, `kpetrovsky/kp-ripgrep-mcp` — ❌. `rg` via builtin `bash`
  costs **zero** tool slots and composes with pipes.

### 2.8 Databases

- ✅ **`crystaldba/postgres-mcp`** — 9 tools (`list_schemas`, `list_objects`, `get_object_details`, `execute_sql`,
  `explain_query`, `get_top_queries`, `analyze_workload_indexes`, `analyze_query_indexes`, `analyze_db_health`).
  `uvx postgres-mcp` or `crystaldba/postgres-mcp`. **Has restricted (read-only, execution-time-capped) vs unrestricted
  modes — use restricted.** PG 15–17. Version number *unverified*. The index-tuning/health tools are genuinely
  differentiated vs a psql shell. **Install only if and when you actually have a DB in the loop, and only on one agent.**
- ❌ **SQLite** — the official reference server is **archived** into `modelcontextprotocol/servers-archived`.
  `sqlite3` in bash is strictly better than an unmaintained server.

### 2.9 Local vector DB (for a hand-rolled offline RAG, if docs-mcp-server isn't enough)

- 🟡 **`qdrant/mcp-server-qdrant`** (official) — PyPI **0.8.1 (2025-12-10)**, `uvx mcp-server-qdrant`, stdio/SSE/HTTP.
  **Only 2 tools** (`qdrant-store`, `qdrant-find`) — outstanding budget profile. Offline via `QDRANT_LOCAL_PATH` +
  FastEmbed (`all-MiniLM-L6-v2`). **But: FastEmbed only — you cannot point it at Ollama/LiteLLM**, and it has open
  air-gap bugs ([#615](https://github.com/qdrant/fastembed/issues/615): `HF_HUB_OFFLINE=1` bypasses the local HF cache
  and attempts an ~83MB GCS download; [#218](https://github.com/qdrant/fastembed/issues/218): hangs behind a firewall).
  Workable if you pre-warm the cache; not clean air-gap.
- 🟡 **`mhalder/qdrant-mcp-server`** (community) — **Ollama is the default embedding provider, no API keys**; Docker
  Compose for Qdrant + Ollama; `nomic-embed-text`. But **16 tools** and build-from-source. Fork and trim to 2 search
  tools if you go this way. Version *unverified*.
- ❌ **`chroma-core/chroma-mcp`** — PyPI 0.2.6, **2025-08-14** (~11 months stale), 12 tools, no local embedding endpoint.
- ❌ **LanceDB / txtai** — no canonical maintained server; several low-maturity forks; versions *unverified*.

VRAM note: `nomic-embed-text` is ~275MB and coexists fine with a 35B MoE on 24GB — unlike mem0's per-write LLM call.

---

## 3. Skip these (with reasons)

| Server | Reason |
|---|---|
| **context7** (your current) | Cloud-only. The repo is MIT but states *"The supporting components — API backend, parsing engine, and crawling engine — are private and not part of this repository."* No offline mode. Free tier cut ~6,000→1,000 req/mo + 60/hr in Jan 2026. **Violates your local-only constraint.** Replace with docs-mcp-server (§5). |
| **playwright-mcp** (unfiltered) | ~3.5k tokens of schemas; ~114k tokens/task measured vs ~27k for the CLI. |
| **`@modelcontextprotocol/server-filesystem`** | 13 tools duplicating 13 builtins. Guaranteed tool-selection confusion on a 35B. |
| **ripgrep / fd / everything MCP** | `rg`/`fd` via bash: 0 tools, composable. |
| **`mcp-server-git`** | Model already knows git CLI. 12 schemas for ~12 verbs. |
| **`github/github-mcp-server`** | github.com-only; you self-host Forgejo. |
| **memory MCPs** (official memory, mem0/OpenMemory, cipher, memory-bank) | Sunset/deprecated/stale, and the AGENTbench data says generated memory files *hurt* success and cost +20%. |
| **`dagger/container-use`** | Last release 2025-08-19. |
| **`pydantic/mcp-run-python`** | Archived + sandbox-escape advisory (2026-01-30). |
| **SQLite reference MCP** | Archived. |
| **`chroma-mcp`** | Stale, no local embedding endpoint, 12 tools. |
| **`ric_harvey/forgejo-mcp`** | 103 tools, 0 stars, 14 commits. |
| **Docker MCP Gateway** | Right idea, invite-only, overkill for 2 clients. |
| **`mcp-remote`** | If you ever reach for it: **CVE-2025-6514, CVSS 9.6**, RCE via a malicious server's `authorization_endpoint`. Fixed in **0.1.16** — pin ≥0.1.16 or avoid. |

---

## 4. Tool-budget engineering

### 4.0 The binding constraint is tool *count*, not tokens

Anthropic's own docs (`https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool`) state it plainly:

> *"Claude's ability to pick the right tool degrades once you exceed **30–50 available tools**."*
> *"A typical multiserver setup (GitHub, Slack, Sentry, Grafana, Splunk) can consume ~55k tokens in definitions before
> Claude does any work."*

That 30–50 ceiling is for a frontier model. **For a 35B-A3B MoE, budget 20–30 total tools including builtins.** With
opencode's 13 builtins already resident, that leaves you **~10–17 MCP tool slots per agent**. That is the number to
design against — not the token count.

Independent 2026 consensus lands in the same place: *"the practical ceiling before degradation is 5 to 7 connected MCP
servers"* (`https://thenewstack.io/how-to-reduce-mcp-token-bloat/`,
`https://eclipsesource.com/blogs/2026/01/22/mcp-context-overload/`). opencode's own docs say it outright: *"MCP servers
add to your context, so you want to be careful with which ones you enable."*

### 4.1 Strategy 1 — server-side filtering (do this first, it's free)

Every server that offers a filter, use it:

| Server | Flag | Effect |
|---|---|---|
| serena | `--context ide --mode no-memories --mode editing` + `excluded_tools:` | 38 → ~15 |
| docs-mcp-server | `--read-only` | 10 → 3 |
| gitea-mcp | `-S issue,pull_request` / `-O <names>` / `-r` | 46 → ~10 |
| chrome-devtools-mcp | `--slim` | 51 → 3 |
| postgres-mcp | restricted access mode | read-only + time-capped |
| playwright-mcp | `--caps` (group-level only) | limited use |

### 4.2 Strategy 2 — client-side per-agent allowlists (opencode's documented pattern)

opencode names MCP tools **`servername_toolname`** (not Claude's `mcp__server__tool`), and the `tools` key takes globs
(`*` = 0+ chars, `?` = 1 char). The documented pattern is **default-deny globally, opt-in per agent**:

```json
{ "tools": { "my-mcp*": false },
  "agent": { "my-agent": { "tools": { "my-mcp*": true } } } }
```

Two consequences you should exploit:
1. **Keep server keys short** (3–6 chars) — the prefix is repeated in every tool name and eats budget.
2. This is also your **security boundary** (§7), not just a budget lever.

### 4.3 Strategy 3 — progressive disclosure / deferred schemas

- **Anthropic Tool Search** (`tool_search_tool_regex_20251119` / `tool_search_tool_bm25_20251119`, GA on the Claude API)
  is the reference design: send every definition but mark `defer_loading: true`; the model searches names/descriptions/
  arg-names and the API expands `tool_reference` blocks inline, **preserving the prompt-cache prefix**. Claimed **>85%
  reduction**, loading only the 3–5 tools needed. For MCP, `defer_loading` is set once on the `mcp_toolset`
  `default_config`.
  ⚠️ **This is server-side on Anthropic's API and does not reach you through LiteLLM → local models.** Cite it as the
  pattern, not as a tool you can turn on.
- **The client-side equivalent that *does* work for you: `pi-mcp-adapter` v2.15.0** — see §6.2. It is Tool Search,
  implemented in the client, for local models.
- Ecosystem confirmation that this is now the default assumption: serena's unreleased changelog on `main` contains
  *"`find_symbol`: Change tool description to improve tool search results in clients that load tools dynamically."*

### 4.4 Strategy 4 — proxies/aggregators (only if you must run a 100-tool server)

Verified live today:

| Tool | Version/State | Filtering |
|---|---|---|
| **MetaMCP** `metatool-ai/metamcp` | 2,571★, pushed 2026-06-22, one docker | Three-level hierarchy Servers → **Namespaces** → Endpoints; enable/disable individual **tools**, apply middleware, **override tool names and descriptions** |
| **mcp-proxy** `sparfenyuk/mcp-proxy` | PyPI **0.12.0**, pushed 2026-07-20 | Streamable-HTTP ↔ stdio bridge; adds tool-filtering to expose a subset per client |
| **mcpo** `open-webui/mcpo` | PyPI **0.0.20**, pushed 2026-05-17 | MCP→OpenAPI (what you already use for Open WebUI). Not a filter. |
| **MCPJungle** | — | Tool Groups with include/exclude, per-client allowlists |
| **mcgravity** | — | nginx-style load balancing, not filtering |

An **April 2026 ecosystem survey of 17 gateways**
(`https://www.heyitworks.tech/blog/mcp-aggregation-gateway-proxy-tools-q1-2026`) concludes the pattern has converged on
flat aggregation + tool namespacing + one endpoint + centralized auth — and notes **no tool currently nails
per-client tool visibility *and* lightweight self-hosting together**.

**Recommendation: don't add a proxy yet.** With per-server flags + opencode per-agent allowlists you already have two
filtering layers, and a proxy adds a process, a failure mode, and an injection-relevant trust boundary. Add MetaMCP only
if the Gitea-API path fails and you're forced onto 100-tool `goern/forgejo-mcp`.

### 4.5 Strategy 5 — the CLI escape hatch

The loudest 2026 signal is vendors shipping CLIs *alongside* their own MCP servers: Microsoft's Playwright CLI
(2026-06-10), GitHub adding a `fields` response-filter in v1.8.0, pi refusing MCP outright. All three are admissions that
MCP's context cost is the binding constraint.

**Rule of thumb: if a capability has a good CLI and your model knows it from pretraining (git, rg, fd, sqlite3, psql,
docker, curl, jq), use bash. Reserve MCP tool slots for capabilities with no CLI equivalent** — LSP symbol graphs,
Forgejo issue/PR APIs, a private docs index.

---

## 5. Replacing context7 with an offline docs stack

### 5.1 context7 cannot be self-hosted — confirmed

`https://github.com/upstash/context7` is MIT, but verbatim: *"The supporting components — API backend, parsing engine,
and crawling engine — are private and not part of this repository."* The repo is the MCP shim; setup requires OAuth +
an API key from `context7.com/dashboard`; tools are `resolve-library-id` and `query-docs`. **No offline mode exists.**
Combined with the Jan-2026 free-tier cut (~6,000 → 1,000 req/mo, 60/hr), it fails your local-only requirement outright.

### 5.2 The replacement: `arabold/docs-mcp-server` v2.4.5

`https://github.com/arabold/docs-mcp-server` — 1,598★, pushed 2026-07-26, npm `@arabold/docs-mcp-server@2.4.5`
(published 2026-07-25), Node 22+, GHCR image `ghcr.io/arabold/docs-mcp-server`. Self-described *"Open-Source Alternative
to Context7, Nia, and Ref.Tools."*

**Tool surface** (read from `src/mcp/mcpServer.ts` on `main`) — **10 tools full, 3 in `--read-only`**:

- Always registered: `search_docs`, `list_libraries`, `find_version` *(all `readOnlyHint: true`)*
- Gated behind `if (!readOnly)`: `scrape_docs`, `refresh_version`, `list_jobs`, `get_job_info`, `cancel_job`,
  `remove_docs`, `fetch_url`
- Also exposes MCP **resources**: `libraries`, `versions`, `jobs`

**Local embeddings — the load-bearing detail.** From `docs/guides/embedding-models.md`, `DOCS_MCP_EMBEDDING_MODEL`
accepts `openai:<model-name>` with **`OPENAI_API_BASE`** (documented example: `http://localhost:11434/v1`). So:

```bash
DOCS_MCP_EMBEDDING_MODEL="openai:nomic-embed-text"
OPENAI_API_BASE="https://llm.tabaska.us/v1"     # your LiteLLM; or http://localhost:11434/v1 for Ollama direct
OPENAI_API_KEY="${LITELLM_API_KEY}"
DOCS_MCP_EMBEDDINGS_VECTOR_DIMENSION=768        # override when the model isn't 1536-dim
```

Embeddings are **optional** — full-text search works standalone, and switching models invalidates embeddings while
*preserving FTS*. So you can run FTS-only day one and add vectors later. Other useful config: `--store-path`,
`--read-only`, `--protocol stdio|http|auto`, ports `6280` (MCP) / `6281` (web UI) / `8080` (worker),
`DOCS_MCP_APP_TELEMETRY_ENABLED=false` (**set this**), and a scraper security block with
`DOCS_MCP_SCRAPER_SECURITY_NETWORK_ALLOWED_HOSTS` / `..._FILE_ACCESS_ALLOWED_ROOTS` allowlists.

**The two-container split (recommended):**

1. **Ingest container** — full 10 tools, run *interactively by you*, never wired to an agent:
   ```bash
   docker run --rm -v docs-mcp-data:/data \
     -e DOCS_MCP_APP_TELEMETRY_ENABLED=false \
     ghcr.io/arabold/docs-mcp-server:2.4.5 \
     scrape react https://react.dev/reference/react
   ```
2. **Serving container** — `--read-only`, 3 tools, `--network=none` after ingest, this is what agents talk to.

Ingest targets for your stack: LiteLLM, opencode, pi, Forgejo, Qwen/vLLM/llama.cpp, Docker, systemd, plus whatever
languages you write. Re-run `scrape`/`refresh_version` on a cron; the box is then fully offline for reads.

### 5.3 llms.txt / llms-full.txt in 2026 — useful, not a strategy

Adoption is real but thin: ~**8.7% of the Tranco top 1,000** as of June 2026
(`https://www.rankability.com/data/llms-txt-adoption/`), and a large slice of that is **Shopify silently pushing
`/llms.txt` and `/llms-full.txt` to every store in late April/early May 2026** — i.e. platform default, not developer
intent. Coding assistants (Cursor, Windsurf, Claude Code, Copilot, Cline, Aider) do routinely fetch both when pointed at
a docs site.

**Practical use:** treat `llms-full.txt` as a *high-quality scrape shortcut*, not a replacement for indexing. For each
library you care about, `curl -sL https://<docs-host>/llms-full.txt` first; if it 200s, feed that single markdown file to
docs-mcp-server (it accepts local files as sources) instead of crawling. If it 404s, crawl. **Mirror the files you get
into a git repo** so the offline corpus is reproducible and diffable. Confidence: **medium-high** on the adoption
numbers (single tracker + one independent crawl study, `https://caseyrb.com/blog/state-of-llms-txt-adoption/`);
**high** that treating it as a shortcut-not-strategy is correct.

---

## 6. MCP protocol state, 2026 — and what it means for you

### 6.1 Spec: **2026-07-28**, released two days ago

`https://modelcontextprotocol.io/specification/versioning` — *"The current protocol version is 2026-07-28."*
Announcement: `https://blog.modelcontextprotocol.io/posts/2026-07-28/`.

**2026-07-28** is the largest break since authorization landed
(`https://modelcontextprotocol.io/specification/2026-07-28/changelog`):
- **MCP is now stateless.** `initialize`/`notifications/initialized` handshake removed; every request carries
  `_meta.io.modelcontextprotocol/protocolVersion` + `clientCapabilities` (SEP-2575). `Mcp-Session-Id` and
  protocol-level sessions removed (SEP-2567).
- New mandatory `server/discover` RPC. `resources/subscribe` → `subscriptions/listen`. `ping`, `logging/setLevel`,
  `notifications/roots/list_changed` removed. SSE resumability (`Last-Event-ID`) removed.
- All results carry `resultType` (`"complete"` | `"input_required"`).
- **Server-initiated requests are gone.** SEP-2322 "Multi Round-Trip Requests" replaces `sampling/createMessage`,
  `elicitation/create` and `roots/list`: a server returns `resultType: "input_required"` + `inputRequests`, and the
  client **retries the original request** with `inputResponses`.

Prior revisions: **2025-11-25** (icons SEP-973, URL-mode elicitation SEP-1036, tool-calling inside sampling SEP-1577,
experimental tasks SEP-1686, OAuth Client ID Metadata Documents SEP-991, JSON Schema 2020-12 default, tool-name guidance
SEP-986) and **2025-06-18** (structured tool output / `outputSchema`, elicitation, Resource Server auth).

### Feature status

| Feature | Status as of 2026-07-28 |
|---|---|
| **Sampling** | **DEPRECATED** (SEP-2577). Migration: integrate directly with LLM provider APIs |
| **Roots** | **DEPRECATED**. Pass dirs via tool params / resource URIs / server config |
| **Logging** | **DEPRECATED**. Use stderr (stdio) or OpenTelemetry |
| **Elicitation** | Active; reworked under MRTR (`notifications/elicitation/complete`, `elicitationId` removed) |
| **Resources / Prompts** | Active; now `CacheableResult` with required `ttlMs` + `cacheScope` (SEP-2549) |
| **Structured tool output** | Active, loosened — any JSON Schema 2020-12 keyword, `structuredContent` any JSON, `$ref` rules (SEP-2106) |
| **Tasks (async)** | Moved to official extension `io.modelcontextprotocol/tasks` (SEP-2663) |
| **Icons** | Active since 2025-11-25 |

Deprecated features have **earliest removal = first revision on or after 2027-07-28** (12-month window):
`https://modelcontextprotocol.io/specification/2026-07-28/deprecated`.

### Transports

Exactly two standard bindings: **stdio** and **Streamable HTTP**
(`https://modelcontextprotocol.io/specification/2026-07-28/basic/transports`).
- **stdio: healthy, unchanged, and the right choice for you.** The spec recommends stdio framing even over Unix sockets.
- **HTTP+SSE: deprecated since 2025-03-26**, formally reclassified Deprecated under the new lifecycle policy (SEP-2596)
  with **earliest removal three months after SEP-2596 reaches Final** — the shortest window in the registry. Dead.
- 2026 work went into making Streamable HTTP stateless and header-routable (`Mcp-Method`, `Mcp-Name` now **required** on
  POST, SEP-2243) so gateways can route without parsing bodies.

### Auth — you can skip it entirely

OAuth 2.1 + RFC 9728 Protected Resource Metadata, with 2026-07-28 hardening (RFC 9207 `iss` must-validate-if-present
SEP-2468, credentials keyed by issuer SEP-2352, `application_type` required in DCR SEP-837, and **Dynamic Client
Registration itself now deprecated** in favor of Client ID Metadata Documents). **Authorization applies to HTTP
transports; stdio has no auth layer.** Run everything as stdio subprocesses and you never touch OAuth — which is also
what the spec's own security page recommends (*"Use the `stdio` transport to limit access to just the MCP client"*).

### 6.2 Client support matrix

| | opencode | pi | Claude Code |
|---|---|---|---|
| stdio MCP | ✅ `"type": "local"` | ❌ native — ✅ via `pi-mcp-adapter` | ✅ |
| HTTP MCP | ✅ `"type": "remote"` (+`headers`, `oauth`) | via adapter | ✅ |
| Tool naming | `servername_toolname` | adapter-mediated | `mcp__server__tool` |
| Per-agent allowlist | ✅ documented (`tools` globs + `agent.<n>.tools`) | ✅ `includeTools`/`excludeTools`/`directTools` | ✅ `allowedTools` |
| Sampling / elicitation / roots | ❌ none | n/a | partial |
| Lazy/deferred tool loading | ❌ | ✅ **proxy mode** | via API Tool Search |

**opencode** (`https://opencode.ai/docs/mcp-servers/`, `https://opencode.ai/docs/config/`): `timeout` defaults **5000ms**
— raise it for serena, whose first call blocks on language-server startup (serena has an `indexing_start_grace`, default
5.0s, plus `indexing_timeout` and `server_ready_timeout`). Issue **#28567** ("Full MCP client capabilities", opened
2026-05-21) documents sampling, elicitation, roots, resource subscriptions/templates, completion, tasks and cancellation
as absent or broken; **closed without resolution, no maintainer reply**. Related: #11948 (sampling), #8251 / #23066
(elicitation). Note the repo now resolves under `github.com/anomalyco/opencode` — the org move's cause is *unverified*.

**pi + `pi-mcp-adapter` v2.15.0** — the most important config in this report:

- **Proxy mode (default):** all MCP tools behind **one `mcp()` tool ≈ 200 tokens**, instead of hundreds. Actions:
  `mcp({})` list servers · `mcp({search: "screenshot navigate"})` fuzzy tool search · `mcp({describe: "tool_name"})` ·
  `mcp({tool: "...", args: {...}})` call · plus `connect`, `ui-messages`, `auth-start`, `auth-complete`.
- **Lazy lifecycle:** `"lifecycle": "lazy"` (default) — *"servers won't connect until you actually call one of their
  tools."* Also `eager`, `keep-alive`, `lazy-keep-alive`; `idleTimeout` default 10 min.
- **Metadata cached to disk** — search/list/describe work with **no live connection**, which is exactly what you want on
  a box that may be offline.
- **`directTools`** promotes chosen tools to first-class pi tools: `true` (all), `["tool_a","tool_b"]`, or omit
  (proxy-only). Plus `includeTools`/`excludeTools` glob filters.
- Config precedence: `~/.config/mcp/mcp.json` → `.mcp.json` → `~/.pi/agent/mcp.json` → `.pi/mcp.json`.

### 6.3 What breaks with local models

1. **Sampling is the classic trap, and it is now structurally closed.** A server issuing `sampling/createMessage` would
   route generation to whatever your client picks — for you, the 35B. Neither opencode nor pi implements sampling, and
   the spec deprecated it on 2026-07-28. **Don't build around it.**
2. **Schema/context bloat is the dominant real failure mode.** Symptoms reported through 2026: fabricated tool names,
   parameters conflated across servers, degraded reasoning as results crowd out instructions
   (`https://albato.com/blog/publications/embedded-mcp-context-bloat-hallucinations`).
3. **Looser JSON Schema cuts against you.** SEP-2106 now permits arbitrary 2020-12 keywords and `$ref` — great for server
   authors, bad for small models, since `$ref`/`allOf` composition is exactly what they fumble. Prefer servers with flat
   schemas and enums. If a server offers structured-output toggles (serena's `structured_tool_output`), try `false` when
   you see malformed calls.
4. **Tool-name length.** opencode's `servername_toolname` prefixing eats budget; keep server keys 3–6 chars.
5. **Model floor.** Third-party 2026 benchmarking puts sub-7B and non-tool-trained models at consistently malformed
   calls, with Qwen3-Coder 30B / Qwen3 32B / GLM-4.7 32B / Gemma 4 27B in the "works" band
   (`https://www.promptquorum.com/power-local-llm/best-local-models-tool-calling-2026` — *indicative, not authoritative*).
   Your `coder` (Qwen3.6 35B-A3B) sits comfortably above the floor; your `fast` (Qwen2.5-Coder 7B) does not — **don't
   give the 7B agent MCP tools at all.**
6. **Free win:** servers **SHOULD** now return `tools/list` in deterministic order *"to improve LLM prompt cache hit
   rates,"* and list results carry `ttlMs`. Real gains on a local box.

---

## 7. Security for an unattended homelab swarm

### 7.1 The attack classes

- **Tool poisoning / cross-server shadowing / rug-pull** — Invariant Labs, April 2025:
  `https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks`; reproducible PoCs at
  `https://github.com/invariantlabs-ai/mcp-injection-experiments`. **Internalize the WhatsApp demo:** a benign-looking
  *trivia* MCP server hid instructions in its **tool description**, and the agent used a *separate, legitimate*
  whatsapp-mcp server to read history and exfiltrate it. The poisoned description rendered as benign in every client UI
  tested. A GitHub-MCP variant exfiltrated private repo contents via a malicious **issue** (May 2025) — directly relevant
  if you point a Forgejo MCP at issues.
- **Lethal trifecta** — Simon Willison, 2025-06-16, `https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/`:
  private data + untrusted content + external communication. MCP-specific: `https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/`.
- The spec's own framing: *"descriptions of tool behavior such as annotations should be considered untrusted."*
  Full page: `https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices` (confused deputy,
  token passthrough, SSRF during OAuth discovery, state-handle hijacking, local server compromise, stdio-in-proxy
  privilege escalation).

### 7.2 Real incidents (all verified)

| Incident | Detail |
|---|---|
| **CVE-2025-6514** `mcp-remote` | OS command injection → RCE, **CVSS 9.6**, versions 0.0.5–0.1.15, **fixed 0.1.16**. Malicious server returns a crafted `authorization_endpoint` passed to `open()`. ~437k–500k downloads at disclosure. `https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/` |
| **postmark-mcp npm backdoor** | First in-the-wild malicious MCP server. **15 clean releases**, then v1.0.16 (2025-09-17) added one line BCC'ing every outgoing email to `phan@giftshop.club`. ~300 orgs. `https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/` |
| **MCPoison / Cursor** | CVE-2025-54136, CVSS 7.2, persistent code exec via unvalidated MCP config changes; fixed in Cursor 1.3 |
| **Anthropic mcp-server-git** | CVE-2025-68143/68144/68145 — path traversal, argument injection, unrestricted file write; fixed 2025.12.18 |
| **Anthropic filesystem MCP "EscapeRoute"** | CVE-2025-53109/53110 |
| **MCPJam Inspector RCE** | CVE-2026-23744 |

*(No Asana/Atlassian MCP incident found — treat any such claim as unverified.)*

### 7.3 Concrete mitigations

1. **Enforce the trifecta split at the agent level, not by prompting.** One agent class reads untrusted web/issue content
   and has **no** write/bash/egress tool; another has write+bash and **no** untrusted-content ingestion. Never both.
   opencode's `"tools": {"*_*": false}` + per-agent opt-in gives you default-deny (see §8).
2. **Never `@latest`.** postmark-mcp and every rug-pull class defeat "I audited it once" — the audit was of v1.0.15. Pin
   exact versions in the `command` array; better, pre-install and invoke a resolved local binary. **Re-read `tools/list`
   descriptions on every version bump** — descriptions are the injection surface.
3. **Containers + read-only mounts.** `docker run --rm -i --network=none --read-only -v /repo:/repo:ro …`.
   `--network=none` on any server with no business egressing kills the exfiltration leg outright. Applies cleanly to
   docs-mcp-server's *serving* container.
4. **Egress control** for servers that do need network: allowlisting proxy (Smokescreen) or per-container nftables.
   Block RFC1918, loopback and 169.254.169.254 from container namespaces — the spec's SSRF section is written for this.
5. **stdio only.** If a server insists on HTTP, bind to a Unix socket or 127.0.0.1 with a bearer token, and reject
   anything advertising HTTP+SSE.
6. **Unattended runs have no in-band human gate**, because opencode implements no elicitation. Compensate: keep
   `permission: {"bash": "ask", "edit": "ask"}` outside a scratch worktree, and run the swarm inside a git worktree you
   can `reset --hard`.
7. **A 35B is *more* likely to follow a poisoned tool description than a frontier model**, not less — small models have
   weaker instruction-hierarchy adherence, and no published mitigation changes that. Context discipline is security
   discipline: every globally-enabled server is an injection surface for every agent.

---

## 8. Ready-to-paste configs

### 8.1 opencode (`opencode.json`) — full replacement for the `mcp`/`tools`/`agent` sections

```json
{
  "$schema": "https://opencode.ai/config.json",

  "mcp": {
    "serena": {
      "type": "local",
      "enabled": true,
      "timeout": 60000,
      "command": [
        "uvx", "--from", "serena-agent==1.6.1", "serena", "start-mcp-server",
        "--context", "ide",
        "--mode", "editing",
        "--mode", "no-memories",
        "--project", "{cwd}"
      ],
      "environment": { "PYTHONUNBUFFERED": "1" }
    },

    "docs": {
      "type": "remote",
      "enabled": true,
      "url": "http://127.0.0.1:6280/mcp",
      "timeout": 30000
    },

    "forge": {
      "type": "local",
      "enabled": true,
      "timeout": 20000,
      "command": [
        "docker", "run", "--rm", "-i",
        "-e", "GITEA_HOST", "-e", "GITEA_ACCESS_TOKEN",
        "docker.gitea.com/gitea-mcp-server:v1.5.0",
        "-t", "stdio",
        "-S", "issue,pull_request"
      ],
      "environment": {
        "GITEA_HOST": "https://git.tabaska.us",
        "GITEA_ACCESS_TOKEN": "{env:FORGEJO_TOKEN}"
      }
    },

    "cdp": {
      "type": "local",
      "enabled": true,
      "timeout": 30000,
      "command": ["npx", "-y", "chrome-devtools-mcp@1.6.0", "--slim", "--headless", "--isolated"]
    },

    "fleet": {
      "type": "local",
      "enabled": true,
      "command": ["<your existing fleet-mcp command>"]
    }
  },

  "tools": {
    "serena_*": false,
    "docs_*":   false,
    "forge_*":  false,
    "cdp_*":    false,
    "fleet_*":  false
  },

  "agent": {
    "build": {
      "mode": "primary",
      "model": "litellm/coder",
      "temperature": 0.1,
      "tools": {
        "serena_*": true,
        "docs_*":   true,
        "forge_*":  true,
        "cdp_*":    false,
        "fleet_*":  false,
        "websearch": false
      },
      "permission": {
        "edit": "allow",
        "webfetch": "deny",
        "bash": { "*": "allow", "git push*": "ask", "rm -rf*": "ask", "sudo*": "ask" }
      }
    },

    "plan": {
      "mode": "primary",
      "model": "litellm/coder-strong",
      "temperature": 0.1,
      "tools": {
        "serena_find_*": true, "serena_get_symbols_overview": true,
        "serena_search_for_pattern": true, "serena_get_diagnostics_for_file": true,
        "docs_*": true,
        "forge_*": true,
        "cdp_*": false, "fleet_*": false
      },
      "permission": { "edit": "deny", "bash": "deny" }
    },

    "recon": {
      "description": "Reads untrusted content (web, issues, docs). NO write, NO bash, NO egress.",
      "mode": "subagent",
      "model": "litellm/coder",
      "temperature": 0.1,
      "tools": {
        "docs_*": true, "cdp_*": true,
        "serena_*": false, "forge_*": false, "fleet_*": false,
        "write": false, "edit": false, "bash": false, "apply_patch": false
      },
      "permission": { "edit": "deny", "bash": "deny" }
    },

    "ops": {
      "description": "Fleet ops only.",
      "mode": "subagent",
      "model": "litellm/coder",
      "tools": { "fleet_*": true, "write": false, "edit": false },
      "permission": { "edit": "deny", "bash": "deny" }
    }
  }
}
```

Notes on the above:
- `context7` is **removed** — replaced by `docs`.
- `--context ide-assistant` → `--context ide` (§0.1), and `uvx --from git+…` → **`serena-agent==1.6.1`** (pinned).
- `timeout` raised from the 5000ms default for serena and cdp; both have slow cold starts.
- `build` has `webfetch: "deny"` and `websearch: false` — that's the trifecta split: the agent with `edit`+`bash` does
  not ingest untrusted web content. `recon` does the ingesting and can't write.
- `plan` uses per-*tool* globs (`serena_find_*`) rather than the whole server — a further ~7-tool saving in the agent
  where you least need editing tools.
- `cdp`/`fleet` are off for `build` by default. Turn them on deliberately, per task.

**Estimated per-agent tool counts:** `build` ≈ 13 builtins + 15 serena + 3 docs + 10 forge = **41** — *at the upper edge;
if you see tool confusion, drop `forge_*` from `build` and delegate Forgejo work to a subagent.* `plan` ≈ 13 + ~6 + 3 + 10
= **32**. `recon` ≈ 6 (read/grep/glob/webfetch minus writes) + 3 + 3 = **~12**. `ops` ≈ **~14**.

### 8.2 pi — install the adapter, then `~/.config/mcp/mcp.json`

```bash
pi install npm:pi-mcp-adapter
```

```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": [
        "--from", "serena-agent==1.6.1", "serena", "start-mcp-server",
        "--context", "ide", "--mode", "editing", "--mode", "no-memories",
        "--project", "."
      ],
      "env": { "PYTHONUNBUFFERED": "1" },
      "lifecycle": "keep-alive",
      "directTools": [
        "find_symbol",
        "get_symbols_overview",
        "find_referencing_symbols",
        "replace_symbol_body",
        "search_for_pattern"
      ]
    },

    "docs": {
      "url": "http://127.0.0.1:6280/mcp",
      "lifecycle": "lazy",
      "directTools": ["search_docs"]
    },

    "forge": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "GITEA_HOST", "-e", "GITEA_ACCESS_TOKEN",
        "docker.gitea.com/gitea-mcp-server:v1.5.0",
        "-t", "stdio", "-S", "issue,pull_request"
      ],
      "env": {
        "GITEA_HOST": "https://git.tabaska.us",
        "GITEA_ACCESS_TOKEN": "${FORGEJO_TOKEN}"
      },
      "lifecycle": "lazy"
    },

    "cdp": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@1.6.0", "--slim", "--headless", "--isolated"],
      "lifecycle": "lazy"
    }
  },

  "settings": {
    "idleTimeout": 10,
    "directTools": false
  }
}
```

**Why this shape:** `"directTools": false` globally means everything except the 6 explicitly-promoted tools lives behind
the single `mcp()` proxy (~200 tokens). pi's resident tool surface becomes **7 builtins + 6 direct + 1 proxy = 14 tools**,
with `forge` and `cdp` reachable on demand via `mcp({search: ...})` and never loaded unless used. `lifecycle: "lazy"`
means those containers don't even start until called. **This is the single best tool-budget configuration available to
you today**, and it only exists on pi.

### 8.3 docs-mcp-server (serving + ingest)

```yaml
# docker-compose.yml — serving container (read-only, 3 tools, no egress after ingest)
services:
  docs-mcp:
    image: ghcr.io/arabold/docs-mcp-server:2.4.5
    command: ["--protocol", "http", "--host", "0.0.0.0", "--port", "6280", "--read-only"]
    ports: ["127.0.0.1:6280:6280", "127.0.0.1:6281:6281"]
    volumes: ["docs-mcp-data:/data", "docs-mcp-config:/config"]
    environment:
      DOCS_MCP_EMBEDDING_MODEL: "openai:nomic-embed-text"
      OPENAI_API_BASE: "https://llm.tabaska.us/v1"
      OPENAI_API_KEY: "${LITELLM_API_KEY}"
      DOCS_MCP_EMBEDDINGS_VECTOR_DIMENSION: "768"
      DOCS_MCP_APP_TELEMETRY_ENABLED: "false"
    restart: unless-stopped
volumes:
  docs-mcp-data:
  docs-mcp-config:
```

```bash
# Ingest — run by hand / cron, NEVER wired to an agent
docker run --rm -v docs-mcp-data:/data \
  -e DOCS_MCP_APP_TELEMETRY_ENABLED=false \
  ghcr.io/arabold/docs-mcp-server:2.4.5 \
  scrape litellm https://docs.litellm.ai/

# llms-full.txt shortcut — try this before crawling
curl -sfL https://docs.example.com/llms-full.txt -o /srv/docs-mirror/example.md \
  && docker run --rm -v docs-mcp-data:/data -v /srv/docs-mirror:/src:ro \
     ghcr.io/arabold/docs-mcp-server:2.4.5 scrape example file:///src/example.md
```

---

## 9. Confidence register

| Claim | Confidence | Basis |
|---|---|---|
| serena `ide-assistant` context no longer exists | **High** | Live directory listing of `contexts/` on `main`; `ide.yml` present, `ide-assistant.yml` absent |
| …and it hard-fails rather than warning | **Medium-high** | Read `get_path()` in `context_mode.py` (raises `FileNotFoundError`, no alias table) for the parallel Mode class |
| serena v1.6.1, 2026-07-21, `serena-agent` on PyPI | **High** | GitHub releases API + PyPI JSON API |
| serena tool inventory (38 classes, 10 optional) | **High** | Grepped `class *Tool(` across `src/serena/tools/*.py` on `main` |
| serena tool count under `ide` + `no-memories` ≈ 15 | **Medium-high** | Arithmetic over the shipped YAML exclusion lists; not empirically counted from a running `tools/list` |
| pi has no native MCP | **High** | Verbatim from upstream README |
| pi-mcp-adapter v2.15.0, proxy ≈ 200 tokens | **High** for existence/version/design; **medium** for the 200-token figure | pi.dev package page + repo; token figure is the author's claim |
| docs-mcp-server v2.4.5, 10 tools / 3 read-only | **High** | npm registry API + read `src/mcp/mcpServer.ts` on `main` |
| docs-mcp-server can use LiteLLM/Ollama for embeddings | **High** | `docs/guides/embedding-models.md`: `openai:<model>` + `OPENAI_API_BASE` |
| context7 cannot be self-hosted | **High** | Verbatim from the upstream repo |
| MCP spec 2026-07-28 + deprecations | **High** | modelcontextprotocol.io spec/changelog/deprecated pages |
| opencode per-agent `tools` allowlists work as shown | **High** | opencode.ai/docs/mcp-servers + /docs/config |
| opencode builtin `lsp` tool overlaps serena | **Medium** | Docs confirm the tool + operations; no quality comparison exists |
| gitea-mcp v1.5.0 filtering flags | **High** | gitea.com releases API + docs |
| **gitea-mcp works against Forgejo** | **Unverified** | Not officially documented; Forgejo is a Gitea fork with a compatible v1 API. **Test first** |
| goern/forgejo-mcp canonical home & true latest | **Unverified** | README claims migration off Codeberg; Codeberg still published v2.30.2 on 2026-07-13; new host refused connections |
| Playwright MCP ~114k vs ~27k tokens/task | **Medium** | Single third-party benchmark (bug0.com) |
| AGENTbench memory/context-file results | **High** | Named academic paper, ETH Zurich/DeepMind, 2026-02-12 |
| llms.txt ~8.7% top-1000 adoption | **Medium-high** | One tracker + one independent crawl study |
| ast-grep-mcp version | **Unverified** | No tagged release found; repo pushed 2026-07-21 |
| postgres-mcp version | **Unverified** | Tool list and modes verified; version number not surfaced |
| Local-model tool-calling floor (7B fails, 30B works) | **Medium** | Single third-party benchmark; directionally consistent with everything else |

---

## 10. Concrete next actions

1. **Today:** run `serena context list` on the rig. If `ide-assistant` errors, you've been on a stale uvx cache — apply
   §8.1 immediately.
2. **Today:** stand up docs-mcp-server per §8.3, ingest LiteLLM + opencode + Forgejo + your language docs, then remove
   `context7` from `opencode.json`.
3. **This week:** test `gitea-mcp v1.5.0` against `git.tabaska.us` with `-r -S issue`. If the API compat holds, adopt it.
   If not, fall back to `goern/forgejo-mcp` **behind MetaMCP** with ≤10 tools exposed.
4. **This week:** `pi install npm:pi-mcp-adapter` and move pi to the proxy config in §8.2. This is the largest single
   context win available to you.
5. **Measure, then prune:** set `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` and A/B the builtin `lsp` tool against serena's
   symbolic reads on a real task. If it holds up, cut serena down to its editing tools (or drop it in opencode entirely)
   and reclaim ~7 slots.
6. **Do not install:** any filesystem, ripgrep, git, memory, or sandbox MCP. Use bash.
