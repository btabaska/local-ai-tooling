# 06 — LSP + Deterministic Code Intelligence as a Force Multiplier for Local Models

**Researched live 2026-07-30.** Every version/claim below was verified against upstream source,
docs, the GitHub API, npm/PyPI registries, or archlinux.org/AUR on that date, unless explicitly
marked **[unverified]**.

Rig: RTX 3090 Ti 24GB / 64GB RAM / CachyOS (Arch) / Docker; llama.cpp + LiteLLM; models 7B–35B
(`coder` = Qwen3.6 35B-A3B @131k, `coder-strong` = 27B @98k, `fast` = Qwen2.5-Coder 7B @32k).
Agents: **opencode** and **pi**, plus **serena** MCP.

---

## 0. Executive summary — what actually matters

The thesis in the brief is correct, and the 2026 tooling landscape has moved *in your favour*: the
single largest change since 2025 is that **opencode now ships a first-class LSP runtime that
auto-injects diagnostics into every `edit`/`write` tool result, plus an (experimental) `lsp` tool
with 9 semantic operations**. That covers ~70% of what you currently pay serena's token tax for.

Ranked by impact-per-token for a 7B–35B local model:

| # | Change | Impact | Token cost | Confidence |
|---|---|---|---|---|
| 1 | **Enable opencode LSP** (`"lsp": true`) → automatic post-edit diagnostics in the tool result | Highest. Closes the write→verify loop with zero model effort and zero extra tool calls. | ~0 idle; ≤20 errors/file on failure | **High** (read the source) |
| 2 | **A `just verify-fast` single-command gate**, injected via a `tool.execute.after` plugin | High. One deterministic command replaces the model's judgement about *what* to verify — and about whether it's done | ~200 tok/run on green | **High** |
| 3 | **Fix the serena config**: `--context ide-assistant` is a deprecated alias that silently resolves to `claude-code`; also trim its tool surface | High. Wrong ~500-tok system prompt referencing a tool-search feature opencode doesn't have, `search_for_pattern` excluded, and ~8,800 tok of schema you mostly don't need | **Saves ~6,500–7,000 tokens** | **High** (read `context_mode.py`, `cli.py`) |
| 4 | **Search hygiene rules in AGENTS.md** — `rg -l` first, `-m2` always, never `--json`/`-C` into context | High and free. Measured: `rg --json` is **32×** `rg -l` for identical information | **negative** (saves thousands) | **High** (measured) |
| 5 | **Pin `ruff` `select` before upgrading to 0.16.0** — defaults jumped **59 → 413 rules** | High. Otherwise every edit returns a wall of style nits and the model optimizes for those | saves 1–5k tok/edit | **High** (release notes) |
| 6 | **`tsc --noEmit` (TS7) / `ruff check` / `ty check` as CLI gates**, not just LSP | High. Whole-project truth; LSP only sees opened files. TS7 makes this per-edit-viable for the first time | 0–500 tok | **High** |
| 7 | **ast-grep** for structural search + mechanical multi-file rewrites | High for refactors; a small model is bad at regex and worse at `sed` | ~50–300 tok/query | **High** |
| 8 | **A/B your edit-tool format** (`edit` vs `apply_patch` vs serena `replace_symbol_body`) | Potentially the largest single win — see §2.9. One benchmark reports **+61 points** on a weak model from edit format alone | — | **Medium** (second-hand) |
| 9 | **repomix `--compress` repo map** regenerated on commit, *pointed to* (not inlined) from AGENTS.md | Medium-high; orientation without whole-file reads | 3–8k tok, budgetable | **Medium-high** |
| 10 | **opencode formatters** (`"formatter": true`) | Medium. Removes an entire class of trivial diff churn | 0 | **High** |
| 11 | **serena symbolic *editing* + rename** (`replace_symbol_body`, `rename_symbol`) | Medium — its *navigation* value is now largely duplicated by opencode's own `lsp` tool | ~2,000 tok trimmed | **Medium** |
| 12 | ctags / SCIP / Zoekt / semgrep | Low for a single-dev homelab; LSP + rg + ast-grep already cover it | — | **Medium** |

**Two things to do today regardless of everything else:** (a) `"lsp": true` in `opencode.json`;
(b) change `--context ide-assistant` → `--context ide` and add `--enable-web-dashboard false`
(CVE-2026-49471, CVSS 8.3 — §2.7).

---

## 1. opencode's native LSP — the current (v1.18.10) reality

**Versions.** opencode `v1.18.10`, published 2026-07-30
(<https://github.com/anomalyco/opencode/releases>). Note the repo **moved from `sst/opencode` to
`anomalyco/opencode`** (191,158 stars, pushed 2026-07-30). Docs: <https://opencode.ai/docs/lsp/>.

### 1.1 LSP is OFF by default

> "LSP is disabled by default." — <https://opencode.ai/docs/lsp/>

Your current `opencode.json` (repo root and `~/.config/opencode/opencode.json`) has **no `lsp` key
at all**, so you are currently running with zero LSP. This is the single biggest gap.

### 1.2 Config schema (verified against <https://opencode.ai/config.json>)

```jsonc
"lsp": true            // enable all built-ins
"lsp": false           // or omit → disabled
"lsp": {               // enable built-ins + per-server overrides
  "<server-id>": {
    "command": ["bin", "--stdio"],   // required when defining a NEW server
    "extensions": [".ext"],          // leading dot
    "disabled": true,                // {"disabled": true} alone is also valid
    "env": { "K": "V" },
    "initialization": { /* LSP initialize options */ }
  }
}
```

### 1.3 Built-in server IDs (from `packages/opencode/src/lsp/server.ts`, `dev` branch)

47 exported server definitions. IDs relevant to your stacks:

| ID | Extensions | Binary resolution |
|---|---|---|
| `typescript` | .ts/.tsx/.js/.jsx/.mjs/.cjs/.mts/.cts | resolves workspace `typescript/lib/tsserver.js` **and** npm-installs `typescript-language-server` |
| `eslint` | same + .vue | downloads `microsoft/vscode-eslint` main.zip; requires local `eslint` dep |
| `oxlint` | ts/js/vue/astro/svelte | requires `oxlint` dep |
| `biome` | ts/js/json/css/vue/astro/svelte/graphql/html | `node_modules/.bin/biome lsp-proxy --stdio`, falls back to PATH `biome` |
| `vue` | .vue | `@vue/language-server` |
| `deno` | ts/js | PATH `deno lsp` |
| `pyright` | .py/.pyi | PATH `pyright-langserver`, else npm-installs `pyright`; auto-detects `$VIRTUAL_ENV`/`.venv`/`venv` and sets `initialization.pythonPath` |
| `ty` | .py/.pyi | **gated behind `OPENCODE_EXPERIMENTAL_LSP_TY=true`**; PATH `ty server`, else `.venv/bin/ty` |
| `gopls` | .go | requires `go` |
| `rust` | .rs | PATH `rust-analyzer` |
| `bash` | .sh/.bash/.zsh/.ksh | `bash-language-server start` |
| `yaml-ls` | .yaml/.yml | `yaml-language-server --stdio` |
| `dockerfile` | .dockerfile / `Dockerfile` | PATH `docker-langserver`, else npm `dockerfile-language-server-nodejs` |
| `terraform` | .tf/.tfvars | auto-downloads from GitHub |
| `lua-ls`, `clangd`, `jdtls`, `zls`, `nixd`, `csharp`, `razor`, `fsharp`, `sourcekit-lsp`, `svelte`, `astro`, `kotlin-ls`, `php intelephense`, `prisma`, `dart`, `ocaml-lsp`, `texlab`, `gleam`, `clojure-lsp`, `tinymist`, `haskell-language-server`, `julials`, `ruby-lsp`, `elixir-ls` | — | — |

**No basedpyright, no vtsls, no `tsc --lsp` (TS7), no marksman, no taplo built-in.** Register those
as custom servers (§3).

`OPENCODE_DISABLE_LSP_DOWNLOAD=true` blocks all the npm/GitHub auto-download paths — recommended on
a machine where you want deterministic, pacman-managed binaries.

### 1.4 Diagnostics are auto-injected into edit/write results — the killer feature

`packages/opencode/src/tool/edit.ts` (lines ~197–205):

```ts
yield* lsp.touchFile(filePath, "document")
const diagnostics = yield* lsp.diagnostics()
const block = LSP.Diagnostic.report(filePath, diagnostics[normalizedFilePath] ?? [])
if (block) output += `\n\nLSP errors detected in this file, please fix:\n${block}`
```

`write.ts` does the same and *additionally* reports errors in up to
`MAX_PROJECT_DIAGNOSTICS_FILES = 5` other files ("LSP errors detected in other files:").

Format, from `packages/opencode/src/lsp/diagnostic.ts`:

```
<diagnostics file="/abs/path.py">
ERROR [12:5] "foo" is not defined
... and N more
</diagnostics>
```

Critical details:
- **`report()` filters to `severity === 1` (ERROR) only.** Warnings/hints are dropped. Good — this
  is exactly the noise floor you want for a small model.
- **`MAX_PER_FILE = 20`**, then "... and N more". Bounded token cost.
- This is a *free* PostToolUse-equivalent. You do not need a plugin for the basic loop.

### 1.5 The `lsp` tool — 9 semantic operations, behind an experimental flag

`packages/opencode/src/tool/lsp.ts` + `lsp.txt`. Operations:

`goToDefinition`, `findReferences`, `hover`, `documentSymbol`, `workspaceSymbol`,
`goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls`.

Params: `operation`, `filePath`, `line` (1-based), `character` (1-based), `query` (workspaceSymbol).
Output is `JSON.stringify(result, null, 2)` — **raw LSP JSON, pretty-printed**. That is verbose;
see the caveat in §7.

Registration (`packages/opencode/src/tool/registry.ts:242`):

```ts
...(flags.experimentalLspTool ? [tool.lsp] : []),
```

and `packages/opencode/src/effect/runtime-flags.ts`:

```ts
experimentalLspTool: enabledByExperimental("OPENCODE_EXPERIMENTAL_LSP_TOOL"),
experimentalLspTy:   bool("OPENCODE_EXPERIMENTAL_LSP_TY"),
```

`enabledByExperimental` means: `OPENCODE_EXPERIMENTAL=true` turns it on globally, or set
`OPENCODE_EXPERIMENTAL_LSP_TOOL=true` specifically (the specific flag wins if set).

There is also a permission key: `"permission": { "lsp": "allow" }` (verified in the config schema's
`PermissionConfig`).

**This directly overlaps serena's `find_symbol` / `find_referencing_symbols` /
`get_symbols_overview`.** See §2.6 for the recommendation.

### 1.6 opencode **v2** has NO LSP

<https://opencode.ai/v2/docs/lsp> states verbatim: *"OpenCode V2 does not yet have an LSP runtime or
built-in language servers"* and *"does not currently start or download servers, expose an LSP tool,
or add diagnostics to file tool results."* The `lsp` config is validated and preserved but inert.
V2 docs recommend running lint/typecheck/compiler commands directly instead.

**Implication: stay on the v1.x line (`v1.18.10`) for LSP. If you ever migrate to v2, the entire
force-multiplier moves from "built-in" to "you must build the hook yourself" (§5).** Confidence: high.

### 1.7 Formatters (adjacent, also off by default)

<https://opencode.ai/docs/formatters/> — 26 built-in formatters in
`packages/opencode/src/format/formatter.ts` (`prettier`, `biome`, `ruff`, `oxfmt`, `gofmt`,
`rustfmt`, `shfmt`, `terraform`, `rubocop`, `nixfmt`, `zig`, `clang`, `ktlint`, `dart`, `pint`, …).
Also a `uv` formatter entry that runs `uv format -- $FILE` when ruff isn't configured (**note: `uv
format` exists in uv 0.12.x — [unverified] against uv's own docs, but it is what opencode's source
probes for**).

`ruff`'s `enabled()` requires ruff on PATH **and** either a `[tool.ruff]` section in
`pyproject.toml` / a `ruff.toml` / `.ruff.toml`, or `ruff` mentioned in
`requirements.txt`/`pyproject.toml`/`Pipfile`.

Formatting runs automatically in the background after write/edit when enabled. `"formatter": true`.

### 1.8 Plugin hooks (for anything the built-ins don't do)

<https://opencode.ai/docs/plugins/>; types in `packages/plugin/src/index.ts`.

Plugins live in `.opencode/plugin/` (project) or `~/.config/opencode/plugin/` (global) — the docs
page renders it as `plugins/`; **the source and most examples use `plugin/`. [unverified] which is
canonical in 1.18.10 — create both or check `opencode --print-logs` on startup.**

Verified `Hooks` interface members (subset):

```ts
"tool.execute.before"?: (input: {tool, sessionID, callID}, output: {args}) => Promise<void>
"tool.execute.after"?:  (input: {tool, sessionID, callID, args},
                         output: {title: string; output: string; metadata: any}) => Promise<void>
"chat.params"?, "chat.headers"?, "chat.message"?, "permission.ask"?,
"experimental.chat.system.transform"?: (input, output: {system: string[]}) => Promise<void>
"experimental.chat.messages.transform"?, "command.execute.before"?, "shell.env"?,
event?: (input: {event: Event}) => Promise<void>,
tool?: { [name]: ToolDefinition },   // register custom tools
config?, auth?, provider?, dispose?
```

Event names available to `event?:` include `file.edited`, `lsp.client.diagnostics`, `lsp.updated`,
`session.idle`, `session.compacted`, `permission.asked`, `todo.updated`, `shell.env`.

**`output.output` is a plain string you can append to** — that is the injection point for a custom
post-edit verify loop (§5.1).

Note: the old `experimental.hook.file_edited` config key is **gone** from the 2026 config schema
(top-level `experimental` now only has `disable_paste_summary`, `batch_tool`, `openTelemetry`,
`primary_tools`, `continue_loop_on_deny`, `mcp_timeout`, `policies`). Hooks = plugins now.

---

## 2. pi — no LSP, but the best hook system of the three

**Versions.** pi `v0.83.0`, released 2026-07-29. Repo is now
**`earendil-works/pi`** (was `badlogic/pi-mono`), 80,829 stars, pushed 2026-07-30. npm
`@earendil-works/pi-coding-agent@0.83.0`. You are pinned at 0.82 per `clients/README.md`.

### 2.1 No built-in LSP

pi's default toolset is **four tools: `read`, `write`, `edit`, `bash`**
(<https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md>). A code search
across `earendil-works/pi` for "lsp" returns only substring false positives (`config.ts`,
`env-api-keys.ts`, …) — **there is no LSP subsystem and no diagnostics injection.** Confidence: high.

### 2.2 `pi-lsp-client` — a third-party extension that adds one

<https://github.com/code-yeongyu/pi-lsp-client> — MIT, **13 stars**, last push 2026-07-25, no
tagged releases. Ported from "oh-my-openagent". Exposes 6 tools:

`lsp_diagnostics`, `lsp_goto_definition`, `lsp_find_references`, `lsp_symbols`,
`lsp_prepare_rename`, `lsp_rename`.

Bundles 40+ server definitions (TypeScript, pyright/basedpyright/ruff, Go, Rust, C/C++, Ruby, Bash,
YAML, Lua, Java, PHP, Dart, Swift, Kotlin, …). Custom servers via `.pi/lsp-client.json` (project) or
`~/.pi/lsp-client.json` (global): `command`, `extensions`, `priority`, `env`. Features a shared
server pool with refCount lifecycle, idle/init reaping, typed crash retry, and a `/lsp` inspector.

```bash
pi install npm:@code-yeongyu/pi-lsp-client
```

**Risk assessment: 13 stars, single maintainer, no releases.** Treat as experimental. It gives pi
*tools*, not automatic post-edit diagnostics — for that you still write a `tool_result` hook (§5.2).
Confidence: medium (README-verified; not run).

### 2.3 pi's extension/event system (the strong part)

Docs: <https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md>
(2,963 lines). Extensions are TypeScript modules in `~/.pi/agent/extensions/*.ts` (global) or
`.pi/extensions/*.ts` (project), or paths listed in `settings.json` → `extensions[]`.

Events (verbatim list): `project_trust`, `session_start`, `session_info_changed`,
`session_before_switch`, `session_before_fork`, `session_shutdown`, `resources_discover`,
`before_agent_start`, `agent_start`, `agent_end`, `agent_settled`, `turn_start`, `turn_end`,
`message_start`, `message_update`, `message_end`, **`tool_execution_start`**,
`tool_execution_update`, `tool_execution_end`, **`tool_call` (can block)**,
**`tool_result` (can modify)**, `context`, `before_provider_headers`, `before_provider_request`,
`after_provider_response`, `model_select`, `thinking_level_select`, `input`, `user_bash`,
`session_before_compact`, `session_compact`, `session_before_tree`, `session_tree`.

`tool_result` semantics (docs §"tool_result"):
- fires after execution, before `tool_execution_end` and the final tool-result message events
- handlers **chain like middleware** in extension load order
- return a **partial patch** — `{ content, details, isError, usage }`; omitted fields are preserved
- use `ctx.signal` so Esc cancels nested async work

That is a strictly *more* capable injection point than opencode's `tool.execute.after`.

### 2.4 Also relevant to your rig

`packages/coding-agent/docs/llama-cpp.md` exists in pi's docs — pi has first-class llama.cpp
guidance. Worth reading separately; out of scope for this lane.

### 2.5 opencode vs pi for LSP — verdict

| | opencode 1.18.10 | pi 0.83.0 |
|---|---|---|
| LSP runtime | **Yes**, 47 built-in servers, auto-download | No (3rd-party ext only) |
| Auto post-edit diagnostics | **Yes, built in** (errors only, ≤20/file) | No — write a `tool_result` hook |
| Semantic tools | `lsp` tool, 9 ops, experimental flag | via `pi-lsp-client` (6 tools) |
| Auto-format on edit | Yes, 26 formatters | No (hook it) |
| Hook expressiveness | good (`tool.execute.after` mutates output string) | **better** (middleware chain, patches, `sendMessage` steering) |

**Use opencode as the primary coding agent for this rig.** Its built-in loop is worth more to a 7B–35B
model than pi's superior extensibility, because it requires zero model cooperation.

### 2.6 Do you still need serena?

Once `"lsp": true` + `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` are on, opencode covers:
definition, references, hover, document symbols, workspace symbols, implementations, call hierarchy,
and automatic diagnostics. serena adds on top of that:

- **stable name-path addressing** (`Class/method`) instead of `line:col` — genuinely better for a
  small model, which is bad at counting columns
- **symbol-body editing** (`replace_symbol_body`, `insert_after_symbol`) — edits that don't depend
  on exact string matching
- **`search_for_pattern`** with symbol-aware grouping
- **memories** (`.serena/memories/`) — a persistent project knowledge store
- **`rename_symbol`** — atomic cross-file rename (opencode's `lsp` tool has no rename op)

Recommendation: **keep serena, but fix its context and trim it** (§2.7). The rename + symbol-body
edit + name-path addressing are the parts a small model benefits from most; the read-only navigation
is now duplicated by opencode's own `lsp` tool and you should not pay for both sets of schemas.

### 2.7 serena — current state and the two config bugs in your setup

**Version.** `v1.6.1`, released 2026-07-21; PyPI `serena-agent==1.6.1` (requires Python
`>=3.11,<3.15`); repo `oraios/serena` 27,210 stars, pushed **2026-07-30** — actively maintained,
with a substantial "Unreleased (main)" changelog. AUR has `serena 1.6.1-1` (1 vote).

#### 🔴 SECURITY: CVE-2026-49471 (CVSS 8.3 HIGH) — turn the dashboard off

Verified via the GitHub Security Advisory API: **GHSA-37h2-6p4f-mp3q / CVE-2026-49471**, published
**2026-07-01**, severity **high, CVSS 8.3**. Affects `serena-agent < v1.5.2`; **patched in v1.5.2+**.

> "Serena's built-in web dashboard exposes an unauthenticated Flask API on a fixed, predictable port
> (TCP 24282, hardcoded as `0x5EDA` in `constants.py`). The server has no authentication, no CSRF
> protection, and no Host header validation. A DNS rebinding attack allows a malicious webpage to
> reach this API from any browser and write arbitrary content to the agent's persistent memory store
> — which the agent reads and acts on autonomously. Combined with `execute_shell_command` (enabled by
> default in all contexts via `shell=True`), this creates a full remote code execution chain
> requiring only that the victim visit a malicious webpage while Serena is running."

The dashboard is `web_dashboard: true` **by default**. Your current `uvx --from git+…` invocation
pulls `main`, so you are almost certainly ≥1.6.1 and therefore patched — but this is a *second*
reason to pin an installed version rather than tracking a moving git ref, and a good reason to
disable the dashboard outright on a box that also serves a public LiteLLM endpoint:

```
serena start-mcp-server --enable-web-dashboard false ...
```

(`--enable-web-dashboard` is a real CLI flag; verified in `src/serena/cli.py`.)

**Install (recommended by upstream docs, <https://oraios.github.io/serena/02-usage/010_installation.html>):**

```bash
uv tool install -p 3.13 serena-agent
serena init
# update: uv tool upgrade serena-agent
```

**BUG 1 in your `opencode.json`: `--context ide-assistant` is a deprecated alias.**
`src/serena/config/context_mode.py`:

```python
legacy_name_mapping = { "ide-assistant": "claude-code" }
```

It logs a deprecation warning and silently gives you the **`claude-code`** context. That context's
prompt is ~500 tokens of Claude-Code-specific instructions ("use the tool search tool to load all of
them **right now**", "**CRITICAL**: Never use a tool before having read its schema via the
tool-search tool", "Read → FORBIDDEN for discovery", "Edit → FORBIDDEN"). opencode has no tool-search
tool, so a chunk of that is unactionable noise; and worse, `claude-code` **excludes
`search_for_pattern`** on top of the usual exclusions. For a 7B model, unactionable absolutist
instructions are actively harmful.

The official docs say plainly for opencode
(<https://oraios.github.io/serena/02-usage/030_clients.html>):
> "In most cases, the `ide` context is likely to be appropriate for such clients, i.e. add the
> arguments `--context ide` in order to reduce tool duplication."

`ide.yml` excludes `create_text_file`, `read_file`, `execute_shell_command`, `find_file`, `list_dir`
— and **keeps** `search_for_pattern`. It also sets `single_project: true`, which (with `--project`)
prunes the toolset to only what the project's configured language servers need, and disables
`activate_project`.

**BUG 2: `uvx --from git+https://github.com/oraios/serena` re-resolves the git dependency on every
MCP server launch.** That is a multi-second (sometimes multi-tens-of-seconds) startup tax on every
opencode session, plus non-reproducibility. Use the installed `serena` binary.

**Also worth knowing for a llama.cpp backend** (docs §Contexts):
> "If you are using a local server (such as Llama.cpp) which requires you to use OpenAI-compatible
> tool descriptions, use context `oaicompat-agent` instead of `agent`."

Since you go through **LiteLLM → llama.cpp**, if you ever see tool-schema errors from serena, the
lever is the context's `structured_tool_output` field (`null` = auto-detect, `true`, `false`). The
`claude-code` context hardcodes `structured_tool_output: false`; `ide` leaves it at auto. If serena
tool calls misbehave through LiteLLM, clone `ide` into a custom context with
`structured_tool_output: false`:

```bash
serena context create ide-opencode   # then edit; serena context edit ide-opencode
```

**Fixed opencode MCP block:**

```jsonc
"serena": {
  "type": "local",
  "enabled": true,
  "command": [
    "serena", "start-mcp-server",
    "--context", "ide",                    // was: ide-assistant (→ claude-code)
    "--mode", "no-onboarding",
    "--enable-web-dashboard", "false",     // CVE-2026-49471 hygiene
    "--project", "{cwd}"
  ],
  "environment": { "PYTHONUNBUFFERED": "1" }
}
```

#### Trimming serena's tool surface — and why you must

**Measured token cost of an MCP tool definition: ~240–305 tokens.** Two independent datapoints agree:
serena issue #1467 measured **8,848 tokens across 29 default-active tools** (~305/tool); the
`grepika` project self-published **2,869 tokens for 12 tools** (~239/tool). **So stock serena costs
~7,000–8,800 tokens of pure schema before the model does any work** — 5–7% of `coder`'s 131k window,
and **27% of `fast`'s 32k window**. On a llama.cpp backend that's also prefix-cache weight that must
survive every turn.

⚠️ **`--enable-tool` / `--exclude-tool` CLI flags do NOT exist.** I checked `src/serena/cli.py` and
ran a repo-wide code search: zero hits. Trimming is **config-only** — `excluded_tools` /
`included_optional_tools` in `serena_config.yml`, `project.yml`, or a custom context YAML
(`serena context create <name>` then edit).

**Recommended trim for a 7B–35B model** — keep the six tools that opencode's own `lsp` tool
*cannot* do, drop the rest:

```yaml
# ~/.serena/serena_config.yml  (or a custom context)
excluded_tools:
  # navigation now covered by opencode's built-in `lsp` tool
  - find_implementations
  - find_declaration
  - get_diagnostics_for_file        # opencode auto-injects these already
  - get_diagnostics_for_symbol
  # line-based editing covered by opencode's edit/apply_patch
  - delete_lines
  - replace_lines
  - insert_at_line
  - replace_content
  - replace_in_files
  # memory: you already keep durable knowledge in AGENTS.md
  - write_memory
  - read_memory
  - list_memories
  - delete_memory
  - rename_memory
  - edit_memory
  - onboarding
  # misc
  - restart_language_server
  - open_dashboard
  - get_current_config
  - list_queryable_projects
  - query_project
```

Leaving roughly: `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`,
`replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol`,
`search_for_pattern` — **~8 tools ≈ 2,000–2,400 tokens instead of ~8,800.**

#### The maintainers have explicitly rejected going lighter

Issue **oraios/serena#1772**, "Why MCP? Why not a skill with CLI tools?" — opened *and closed*
**2026-07-28** (verified verbatim via `gh issue view`):

> **User:** *"The problem with MCP is that they need to start a server, it's slow, and it eats
> context by loading all its tools even if the MCP isn't needed… why does it even need a server, if
> it's a local env?"*
>
> **Maintainer (MischaPanch):** *"Because language servers are stateful and so is serena."*

Closed with no further discussion. **Read: serena is architecturally committed to a wide, stateful
MCP surface and will not shed it.** If you want a small tool surface you must trim it yourself
(above) or use a CLI-shaped alternative (§2.8).

**serena's tool inventory** (from `src/serena/tools/*.py`, v1.6.1 + main):

| Module | Tools |
|---|---|
| `symbol_tools` | `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, `find_implementations`, `find_declaration`, **`get_diagnostics_for_file`**, `get_diagnostics_for_symbol`, `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, **`rename_symbol`**, `restart_language_server` |
| `file_tools` | `read_file`, `create_text_file`, `list_dir`, `find_file`, `replace_content`, `replace_in_files`, `delete_lines`, `replace_lines`, `insert_at_line`, `search_for_pattern` |
| `memory_tools` | `write_memory`, `read_memory`, `list_memories`, `delete_memory`, `rename_memory`, `edit_memory` |
| `workflow_tools` | `onboarding`, `initial_instructions`, `serena_info` |
| `cmd_tools` | `execute_shell_command` |
| `config_tools` | `open_dashboard`, `activate_project`, `remove_project`, `get_current_config` |
| `query_project_tools` | `list_queryable_projects`, `query_project` |

Note: the old `think_about_collected_information` / `think_about_task_adherence` /
`think_about_whether_you_are_done` tools **no longer exist** in v1.6.x. Good — they were pure token
overhead for a small model.

**serena does NOT auto-inject diagnostics after edits.** `EditingToolWithDiagnostics` in
`src/serena/tools/tools_base.py` has:

```python
ENABLE_DIAGNOSTICS: bool = False
"""... The feature is currently disabled, because per-edit diagnostics are a questionable feature,
since individual edits often intentionally introduce diagnostics ... that are then resolved in
subsequent edits."""
```

So opencode's built-in auto-injection is *the* automatic loop; serena's is opt-in-by-tool-call
(`get_diagnostics_for_file`). Confidence: high (read the source).

**Modes** (`src/serena/resources/config/modes/`): `planning`, `editing`, `interactive`, `one-shot`,
`onboarding`, `no-onboarding`, `no-memories`, `query-projects`, `benchmark`. Multiple modes compose;
resolution order = `base_modes` (global, always) ∪ `default_modes` (global→project→`--mode`) ∪
`added_modes` (project/`--add-mode`).

- `no-onboarding` excludes only `onboarding` (keeps memory tools). **Recommended** — onboarding on a
  35B model burns a lot of tokens producing mediocre memories; write `.serena/memories/*.md` by hand
  (or generate from repomix, §6) instead.
- `no-memories` excludes all 6 memory tools + onboarding. Use this if you'd rather put durable
  knowledge in `AGENTS.md` (which you already do) — saves ~6 tool schemas.
- `planning` excludes all write tools; pairs well with your `plan` agent.

**Languages / LSP backends** (`src/solidlsp/ls_config.py`, 70+ entries). Python has **five**
selectable backends: `python` (pyright, default), `python_basedpyright` (new in main),
`python_ty`, `python_pyrefly`, `python_jedi`. TypeScript has `typescript` (tsserver) and
`typescript_vts` (vtsls). Others: go, rust, java, kotlin, csharp(+omnisharp), ruby(+solargraph),
php(+phpactor/phpantom), cpp(+ccls), swift, dart, bash, lua/luau, nix, terraform, elixir, erlang,
ocaml, haskell, scala, julia, r, perl, clojure, zig, crystal, cue, elm, fsharp, rego, groovy, vue,
svelte, angular, powershell, markdown, latex, yaml, json, toml, ansible, solidity, html, scss, …

Note: as of main, the project config key `languages` was renamed to **`language_servers`**
(auto-migrated).

**Indexing / project config:**

```bash
serena project index          # index CWD, auto-creates project if needed
serena project create --index
serena config edit            # ~/.serena/serena_config.yml
```

Per-project data lives in `<project>/.serena/` (configurable via
`project_serena_folder_location` with `$projectDir` / `$projectFolderName` placeholders);
global data in `~/.serena` (override with `SERENA_HOME`).

**Known issues / caveats relevant to you** (from the main CHANGELOG, 2026):
- rust-analyzer memory: they had to *disable cache priming and Cargo autoreload* to cut RAM. On a
  box where VRAM/RAM is tight, rust-analyzer remains the heaviest server.
- TypeScript: `indexing_start_grace` (default 5.0s) added because on large projects the first
  `find_referencing_symbols` could race tsserver's project load and **silently return incomplete
  results**. If TS reference searches look wrong, raise `indexing_start_grace` /
  `indexing_timeout` / `server_ready_timeout` in `serena_config.yml`.
- Linux orphan processes: language servers spawned in their own session used to survive a SIGKILL/OOM
  of serena — fixed on main, but on v1.6.1 an OOM-killed serena can leave language servers running.
  **On this rig that matters**: an OOM during a model load could orphan a pyright/rust-analyzer.
  `pkill -f language-server` is a useful escape hatch.
- Tool-call timeouts used to block the executor indefinitely — fixed on main, present in v1.6.1.

**Token cost, measured by others.** serena's own evaluation
(<https://oraios.github.io/serena/04-evaluation/>, `040_glm_on_tianshou.md`, GLM 5.1 on Tianshou
~26k LOC, 2026-04-14) gives the most honest numbers I found:

> "Serena's output was 64KB (with context snippets) vs Grep's ~5KB — a tradeoff of precision vs
> verbosity."

and

> "For a 1-line tweak in a 22-line method, Edit sends ~200 chars; Serena's `replace_symbol_body`
> sends ~800 chars (the entire method body). The overhead reverses for full-body rewrites of large
> methods."

and the wins:

> "Renaming `CollectStatsBase` to `BaseCollectStats` across 4 files (10 occurrences) required 1
> Serena call vs 1 Grep + 3 Reads + 4 Edits = 8 built-in calls."

**Takeaway for a 35B/131k model: serena's `find_referencing_symbols` can blow 64KB into your context
in one call.** That is ~16k tokens — 12% of your `coder` window. Instruct the model (AGENTS.md) to
prefer `find_referencing_symbols` only when it actually needs semantic precision, and to use
`grep`/`rg` for "where is this string". This is the opposite of the `claude-code` context's advice,
which is another reason not to use that context.

### 2.8 Alternatives to serena (2026)

| Project | Stars | Last push | Verdict |
|---|---|---|---|
| [`isaacphi/mcp-language-server`](https://github.com/isaacphi/mcp-language-server) | 1,572 | **2026-03-01** (rel v0.1.1, 2025-05-16) | Semi-dormant. Thin LSP→MCP bridge. Superseded by opencode's built-in `lsp` tool for your use case. |
| [`ast-grep/ast-grep-mcp`](https://github.com/ast-grep/ast-grep-mcp) | 441 | 2026-07-21 | Official, "experimental". Structural search + rule authoring + AST dump. `uvx --from git+https://github.com/ast-grep/ast-grep-mcp ast-grep-server`. Complements serena rather than replacing it. |
| `srijanshukla18/xray` | 52 | 2025-12-11 | Dormant. |
| `nnunley/ast-grep-mcp`, `dgageot/mcp-ast-grep` | 6, 5 | 2025 | Dead; use the official one. |

**The wider 2026 landscape** (stars/dates verified via GitHub API 2026-07-30):

| Tool | ★ | Pushed | Latest rel | MCP tools | Fit for 7B–35B |
|---|---:|---|---|---:|---|
| **[bartolli/codanna](https://github.com/bartolli/codanna)** | 711 | 2026-07-26 | **v0.12.0 (2026-07-26)** | **9** | ⭐⭐⭐⭐⭐ **best alternative** |
| **[jahala/tilth](https://github.com/jahala/tilth)** | 322 | 2026-07-25 | v0.9.0 (2026-06-06) | 9 | ⭐⭐⭐⭐⭐ **only published small-model benchmarks** |
| [ast-grep/ast-grep-mcp](https://github.com/ast-grep/ast-grep-mcp) | 441 | 2026-07-21 | none (experimental) | 4 | ⭐⭐⭐⭐⭐ complement, not replacement |
| [agentika-labs/grepika](https://github.com/agentika-labs/grepika) | 132 | 2026-06-22 | v0.4.0 | 12 (**2,869 tok**) | ⭐⭐⭐⭐ |
| [isaacphi/mcp-language-server](https://github.com/isaacphi/mcp-language-server) | 1,572 | 2026-03-01 | v0.1.1 (2025-05-16) | 6 | good surface, **cold upstream** |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | **36,596** | 2026-07-30 | v0.9.0 | 15 (`--tool-profile scout`=7) | ⚠️ see caveat |
| [JetBrains/mcp-jetbrains](https://github.com/JetBrains/mcp-jetbrains) | 964 | 2025-08-18 | 2025-07-01 | dozens | superseded (JB 2026.2 bundles it) |
| [Tritlo/lsp-mcp](https://github.com/Tritlo/lsp-mcp) | 123 | 2025-07-21 | none | 9 | dormant ~12 mo |
| [wrale/mcp-server-tree-sitter](https://github.com/wrale/mcp-server-tree-sitter) | 311 | 2026-05-21 | v0.7.0 | — | 🔴 **ARCHIVED** |
| [jonrad/lsp-mcp](https://github.com/jonrad/lsp-mcp) | 191 | 2025-03-31 | none | — | 🔴 abandoned |
| `cq` | — | — | — | — | **does not exist** (likely a confusion with `ck` or CodeQL) |

**🏆 codanna is the one worth a real evaluation.** 9 tools (`get_index_info`,
`semantic_search_docs`, `semantic_search_with_context`, `search_symbols`, `search_documents`,
`find_symbol`, `get_calls`, `find_callers`, `analyze_impact`), 15 languages, tree-sitter + on-disk
index + local embeddings — **no language servers at all**, so it structurally avoids serena's whole
class of startup-race / orphan-process / stale-LSP failures. Critically for you, it has a **one-shot
CLI mode** (`codanna mcp find_symbol name:"foo"`) — meaning you can expose it via Bash/skills at
**~0 tokens of resident tool schema** instead of serena's ~8,800. Weekly releases. Confidence: high
on the facts, medium on whether it beats trimmed serena in practice (no head-to-head exists).

**🥇 tilth is the only tool in this space with published small-model evidence** — 26 tasks × 4 repos
× 160 runs vs Claude Code built-ins: Sonnet 4.6 84%→94%, Opus 4.6 91%→92%, **Haiku 4.5 54%→73%**,
cost per correct change −38% to −44%. **[unverified — vendor-published, not independently
replicated.]** But its documented small-model playbook is the transferable part:

> "Smaller models (e.g. Haiku) may **ignore tilth tools in favor of built-in Bash/Grep**. To force
> adoption, disable the overlapping built-in tools." … "**DO NOT rules at the top of MCP
> instructions reduced redundant built-in tool usage to near-zero** across all models."

That is exactly the failure mode you should expect from a 7B–35B model on your rig, and it argues
for using opencode's `"tools"` config to *disable* overlapping built-ins if you want serena used.

⚠️ **Caveat on `codebase-memory-mcp`: 36,596 stars accumulated in ~5 months** (created 2026-02-24)
is extraordinary and worth independent corroboration before adopting. Its cited preprint
(arXiv:2603.27277) was **not verified**. Confidence: low-medium.

**Verdict: serena remains the best-maintained LSP-backed MCP server** (27.2k ★, pushed daily), but
its *retrieval* value prop has been substantially eaten — by opencode's own `lsp` tool on your
stack, and industry-wide by native LSP landing in the agents themselves (Claude Code shipped a
native LSP tool in v2.0.74, 2025-12; JetBrains bundles + enables its MCP server by default as of
2026.2). **serena's durable moat is symbolic *editing* + cross-file rename + name-path addressing,
not navigation.** Configure it accordingly.

### 2.9 ⚠️ The finding that outranks everything else in this section

The highest-leverage 2026 result for small models is not about retrieval at all. **"The Harness
Problem"** (<https://stencil.so/blog/the-harness-problem>, 2026-02-12; HN 832 points) benchmarked
16 LLMs × 3 **edit-tool formats** with only four tools (read/write/edit/grep):

- Grok Code Fast 1: **6.7% → 68.3% (+61.6 points)** from changing *only the edit format*
- MiniMax M2.1: +41.7 points. **Average +15 points across 16 models.** Output tokens −61%.
- *"Patch is the worst format for nearly every model."*
- **"Smaller models benefited most disproportionately, suggesting that simpler, verifiable
  identifiers reduce cognitive overhead."**

**[unverified — I could not fetch the blog directly; this is second-hand via the research chain and
the HN thread. Treat the direction as credible and the exact numbers as unconfirmed.]**

**Implication for this rig: before optimizing retrieval, check your edit format.** opencode offers
`edit` (string-match), `write` (whole file), and `apply_patch`. If your 35B model is failing edits,
the fix is likely the edit tool, not the repo map. serena's `replace_symbol_body` is arguably a
*good* format for small models (stable name-path identifiers, no line numbers) — at the cost of
sending the whole symbol body (~800 chars vs `edit`'s ~200 for a one-line change, per the GLM eval).
**This is the single most valuable thing to A/B on your own `bakeoff/` harness.**

---

## 3. Language servers to actually install on this Arch rig

All versions below verified 2026-07-30 against archlinux.org/packages, AUR RPC v5, npm registry,
and PyPI JSON API.

### 3.1 Python — the 2026 state

#### Ground truth: the official typing-conformance suite

Computed directly from `python/typing`'s `conformance/results/results.html` (142 test files) —
<https://github.com/python/typing/tree/main/conformance/results>. **This is the number to reason
from; blog posts on this topic in 2026 are unreliable and frequently mix up the tools.**

| Checker | Version tested | Full pass | **Full-pass %** | Weighted % |
|---|---|---|---|---|
| basilisk | 0.27.0 | 141 | 99.3% | 99.3% |
| zuban | 0.8.2 | 140 | 98.6% | 98.9% |
| **pyrefly** | 1.1.0 | 135 | **95.1%** | 97.2% |
| **pyright** | 1.1.410 | 134 | **94.4%** | 96.1% |
| **ty** | **0.0.50** | 101 | **71.1%** | 81.7% |
| mypy | 2.1.0 | 83 | 58.5% | 76.8% |

⚠️ The `ty` row is pinned at **0.0.50** (2026-06-17) while ty is now 0.0.65 — its real number today
is certainly higher, but **nobody has published it**. Treat 71.1% as a lower bound, not a verdict.

| Tool | Latest | Date | Arch | Verdict for agents |
|---|---|---|---|---|
| **ruff** | **0.16.0** | 2026-07-23 | `extra/ruff 0.16.0-1` (same-day) | **Install.** `ruff server` is the LSP (native since 0.3.5, stable 0.5.3). **`astral-sh/ruff-lsp` is ARCHIVED** (`archived=true`, last push 2025-12-01, final release v0.0.62 2025-02-10). See the 0.16.0 breaking change below. |
| **pyright** | 1.1.411 | 2026-06-25 | `extra/pyright 1.1.411-1` (same-day) | **Install.** Still Node-based (`engines: node>=14`, bins `pyright` + `pyright-langserver`). opencode's built-in. The safe default. ⚠️ Cadence has slowed: 1.1.407 (2025-10-24) → 1.1.408 (**2026-01-08**) → … → 1.1.411 (2026-06-25), vs the old ~2-week cycle. |
| **basedpyright** | 1.39.9 | 2026-06-27 | AUR `basedpyright` / `basedpyright-bin` 1.39.9-1 | **Recommended over pyright for agents.** Rebased on 1.1.411 **two days** after Microsoft; ~2–3 releases/month. CLI type-checks Jupyter notebooks (pyright's CLI cannot); re-implements Pylance-only LSP features (import code-actions, semantic highlighting, inlay hints) in an open server; `reportAny`, baseline files. Not an opencode built-in — register as a custom server. |
| **ty** (Astral) | **0.0.65** | 2026-07-29 | **`extra/ty 0.0.63-1`** *(it IS in official repos)*; AUR `ty-bin 0.0.65-1` | **Still `0.0.x`.** Beta announced 2025-12-16 with "targeting a Stable 1.0 next year"; 7.5 months later there is **no 1.0, no RC, no 1.0 milestone issue**. README still warns of breaking changes between any two versions. |
| **pyrefly** (Meta) | **1.1.1** | 2026-06-18 | AUR `pyrefly` / `pyrefly-bin` 1.1.1-1 (1 vote) | **Best measured conformance (95.1%) — but see the memory blocker below.** |
| **zuban** | 0.9.0 | 2026-06-23 | AUR `zuban` / `zuban-bin` 0.9.0-1 | Dark horse: 98.6% conformance, Rust, by the author of Jedi. Three modes: `zuban check`, `zuban mypy` (drop-in), `zuban server`. ⚠️ **AGPL-3.0** and thin adoption; Posit evaluated it for Positron in Mar 2026 and chose pyrefly instead. Its "half the memory of ty/pyrefly" claim has **no benchmark page behind it — vendor claim, unverified.** |
| pylsp 1.15.0 / jedi-language-server 0.47.0 | | 2026-07-27 / 2026-05-31 | `extra/python-lsp-server`, `extra/jedi-language-server` | **Skip.** pylsp is a plugin-host that shells out and is the slowest of the set; jedi-ls does no real type checking. Only virtue: low RAM. |

#### 🚨 ruff 0.16.0 is a breaking release that WILL flood your agent

Verbatim from the release notes (<https://github.com/astral-sh/ruff/releases/tag/0.16.0>,
2026-07-23):

> "Ruff now enables a much larger set of rules by default (**413, up from 59**)."

18 opinionated `E`/`F` rules were simultaneously *removed* from defaults (`E401`, `E402`,
`E701`–`E703`, `E711`–`E714`, `E721`, `E731`, `E741`–`E743`, `F403`, `F405`, `F406`, `F722`).
Also new: Ruff **formats Python code blocks inside Markdown by default**; `# ruff: ignore[CODE]`
suppression comments alongside `noqa`; fixes rendered in `check`/`format --check` output;
`format --check` gained the linter's output formats; and JSON `filename`/`location` fields may now
be `null` instead of defaulting to `""` / row 1 col 1 (**this will break naive JSON parsers**).

**Action: pin an explicit `select` list in `pyproject.toml` before upgrading.** A 7B model handed
413 rules' worth of diagnostics after every edit will spend its entire budget on style nits instead
of the bug. Migration guide: <https://astral.sh/blog/ruff-v0.16.0>.

#### 🆕 Pyright Type Server Protocol — the most agent-relevant Python development of 2026

Pyright now ships a separate npm package **`pyright-typeserver`** exposing
`pyright-typeserver --stdio`, speaking a JSON-RPC **Type Server Protocol (TSP)** over LSP transport.
Requests: `typeServer/getComputedType`, `getDeclaredType`, `getExpectedType`, `resolveImport`,
`getPythonSearchPaths`, `getSnapshot`. From the docs
(<https://github.com/microsoft/pyright/blob/main/docs/type-server.md>):

> "Some tools instead need direct access to a Python type checker's type information … without going
> through editor-oriented requests."

That is *literally* the agent use case: "what is the type of this expression" without round-tripping
through hover. Pyrefly implements TSP too (1.2.0-dev). **Nothing in opencode/pi/serena consumes TSP
yet** — but it's the thing to watch. Confidence: high (read the doc).

#### 🚨 The pyrefly memory blocker — disqualifying on this rig

Two **open** issues, read directly:
- **facebook/pyrefly#3466** "Pyrefly consumes A LOT of memory", **open since 2026-05-19**:
  *"memory consumption grows to extreme levels — we have observed up to **20 GB of RAM** in use by
  the pyrefly process."* (Neovim + large Django monorepo.) The reporter adds that pyright and
  basedpyright index the same codebase "without approaching anywhere near this level."
- **facebook/pyrefly#2970** "Pyrefly VS Code Extension uses 100GB of memory", **open since
  2026-03-30**: *"eventually eats up 100 GB of memory … I had to kill the pyrefly process because my
  system was unresponsive."*

Also open: #4122 (crashes VS Code allocating on glibc 2.17), #1636.

**On a 64 GB box whose whole point is keeping a 23.3 GB model resident, an LSP that can reach 20 GB
is not a risk worth carrying.** By contrast **ty has no open runaway-memory report** — its memory
issues (#3808, #3190, #3445, #3062) are all *closed*. Confidence: high (issue states verified via
API).

#### Python recommendation for this rig

| Rank | What | Why |
|---|---|---|
| **1** | **`ruff` CLI** (not the LSP) in `just verify` | Sub-100 ms, no resident process. `--output-format concise`. **Pin `select` first.** |
| **2** | **`basedpyright-langserver --stdio`** as the LSP | Correctness source of truth; 94%+ conformance; notebook CLI checking; `--outputjson` for batch. Cost: Node. |
| **3** | **`ty check --output-format concise`** as a fast second gate | Instant incremental feedback, clean memory record, single static binary, no Node. **Not your only checker.** |
| 4 | zuban | Blocked on AGPL + thin adoption + unverified benchmarks |
| 5 | **pyrefly — do not use in LSP mode yet** | Best conformance, but 20 GB/100 GB open reports |

⚠️ **`ty check` has NO JSON output format** — options are `full`, `concise`, `gitlab`, `github`,
`junit`. (GitLab format is JSON but a CI-report schema, not diagnostics.) Use `concise` and parse
lines. Good scripting flags it *does* have: `--error-on-warning`, `--exit-zero`,
`--exit-zero-on-warning`, `--quiet`/`-qq`, `--no-progress`, `--watch`/`-W`.
`ty server` takes no flags beyond `--help`; stdio only.

**Corroborating signal:** serena defaults Python to **pyright** and classifies `python_ty`,
`python_pyrefly`, `python_basedpyright` and `python_jedi` all as `is_experimental()` —
*"experimental (potentially not robust), secondary (not default) or deprecated"*
(`src/solidlsp/ls_config.py`). The whole ecosystem is converging on the same answer.

⚠️ **Do not `pip install pyright`** — the PyPI package is a `nodeenv` shim that downloads its own
Node. Use `pacman -S pyright` so it uses system `nodejs`.

### 3.2 TypeScript/JavaScript — TypeScript 7 has SHIPPED

**The headline finding.** `npm view typescript` → **`typescript@7.0.2`, published 2026-07-08**, and
its `dependencies` are 20 platform binaries (`@typescript/typescript-linux-x64@7.0.2`, …). The bin
map is `{"tsc": "bin/tsc"}`. **The native Go compiler is GA and `tsc` is now that binary.**
Release: <https://github.com/microsoft/typescript-go/releases/tag/typescript/v7.0.2>.
The last JS-implementation release is TypeScript 6.0.3 (2026-04-16).

But — from `microsoft/typescript-go`'s README feature table (read 2026-07-30):

| Feature | Status |
|---|---|
| Program creation, parsing, type resolution, type checking, JSX, declaration emit, emit, watch, build mode, incremental | **done** |
| **Language service (LSP)** | **in progress** — "Nearly all features implemented." |
| API | **not ready** |

`cmd/tsgo/main.go` confirms `--lsp` and `--api` subcommands exist.

**TS7's LSP mode is the primary architecture, and `tsserver.js` is gone.** From the GA announcement
(<https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/>):

> "Your favorite code editor should easily support TypeScript 7 with its new support for the language
> server protocol (LSP)" … "TypeScript 7's new language server has reduced failing language server
> commands by over 80%, and reduced server crashes by over 60%."

Exact invocation, verified by reading `cmd/tsgo/main.go` + `cmd/tsgo/lsp.go`:

```
tsc --lsp --stdio
```

(`lsp.go` declares `-pipe`/`-socket` but assigns them to `_` and hard-fails with *"only stdio is
supported"* without `-stdio`. There is also an `--api` mode.)

Published speed/memory numbers: builds **7.7×–11.9× faster** (VS Code 125.7 s → **10.6 s**; Sentry
139.8 s → 15.7 s; Slack CI 7.5 min → 1.25 min). Memory **−6% to −26%** (VS Code 5.2 GB → 4.2 GB;
Bluesky 1.8 GB → 1.3 GB). These are whole-program `tsc` figures, not LSP steady-state.

🔧 **Zero-Node trick for agents.** npm `typescript@7.0.2` still declares `engines: {node: ">=16.20"}`
and `bin: {tsc: "bin/tsc"}` → `lib/tsc.js`, but that shim is a 30-line launcher that does:

```js
if (process.platform !== "win32" && typeof process.execve === "function") {
    process.execve(exe, [exe, ...process.argv.slice(2)]);   // Node >= v22.15.0
}
```

It **`execve`s — the Node process is replaced, not forked**, so there is zero steady-state Node
overhead. Better, skip Node entirely and run the 24 MB static Go binary:

```
./node_modules/@typescript/typescript-linux-x64/lib/tsc --lsp --stdio
```

**Therefore, in mid-2026:**
- **Typecheck gate → `tsc --noEmit` (TS7).** Biggest single speedup available to your TS loop.
  Arch's `extra/typescript` is **6.0.3-1**, a full major behind — **install TS7 via npm/pnpm.**
- **LSP → `tsc --lsp --stdio` is now the recommendation**, with two honest caveats:
  1. typescript-go's README **still** labels `Language service (LSP) | in progress | Nearly all
     features implemented` — it is the *only* row not marked `done`. And **no programmatic API until
     7.1** (*"it does not ship with an API"*); if your tooling imports `typescript` as a library,
     alias the old one: `npm i -D typescript@npm:@typescript/typescript6`.
  2. **Helix PR #16026** ("make the official TypeScript language server the default") is **still a
     draft, unmerged as of 2026-07-29** — maintainers deliberately kept `typescript-language-server`
     as the default, citing that "in progress" label. A tester in-thread: *"certainly much faster
     than the previous language server, that part is noticeable."*

  The unfinished parts are editor-grade polish (code lens, rare refactors). The features an *agent*
  needs — diagnostics, go-to-def, find-refs, hover types, rename, workspace symbols — are done and
  ~10× faster. **Register it in opencode as a custom server** (opencode's built-in `typescript` id
  resolves `tsserver.js`, which TS7 does not ship).
- **`typescript-language-server@5.3.0` (2026-05-21)** — keep as the fallback for repos pinned to
  TS ≤6; that's what opencode's built-in `typescript` server drives today. Arch's is `5.1.3-1`
  (two minors behind). Still actively maintained, but on a dead-end backend.
- `vtsls` (`@vtsls/language-server@0.3.0`, **2025-12-24**, AUR `vtsls 0.3.0-1`) — higher quality than
  typescript-language-server (Zed and LazyVim default to it; serena offers it as `typescript_vts`),
  but its last tag is 7 months old and **it also wraps `tsserver.js`, so TS7 kills it too.** Skip.
- **biome 2.5.6** (2026-07-28), `extra/biome 2.5.6-1` (same-day packaging).
  ✅ **Type-aware linting is real and shipping, using Biome's OWN inference engine — no `tsc`
  process, no tsconfig program build.** Confirmed by 2.5.6 changelog entries for *shipped* rules,
  not roadmap items: *"Fixed a performance regression in `noMisusedPromises` that caused type
  inference to run repeatedly"*, *"Improved the accuracy of type-aware lint rules by resolving more
  inferred types… `noFloatingPromises` now detects floating Promises returned by aliased callbacks"*.
  Coverage is narrower than typescript-eslint but the resource profile is exactly what you want.
  `biome lsp-proxy` exists (stdin/stdout LSP); `--reporter` supports `json`, `concise`, `github`,
  `gitlab`, `junit`, `sarif`, `summary`, … **There is no Biome 3.0** — 2.5 (2026-06-05) is the
  newest feature release (500+ rules, 73 nursery promotions, ~13% faster).
- **oxlint 1.76.0** (2026-07-27), AUR `oxlint-bin 1.76.0-1` (same-day). ✅ **Type-aware linting is now
  STABLE — and it's built on tsgo/TypeScript 7**, so you don't pay for a second type system.
  845+ rules, "50–100× faster than ESLint", used by Kibana/Sentry/Renovate. opencode has a built-in
  `oxlint` LSP server. ⚠️ **`oxc_language_server` is not published as a standalone npm package**
  (`oxlint-language-server`, `oxc-language-server`, `@oxlint/language-server` all 404) — you get it
  from the VS Code extension or by building the crate. That's the friction for a non-VS-Code agent.
- **eslint v10.8.0** (2026-07-24), `extra/eslint 10.8.0-1`. There is **no standalone
  `eslint-language-server` on npm** — but **Arch packages it directly: `extra/eslint-language-server
  3.0.24-1`**, which is cleaner than opencode's built-in path (which downloads
  `microsoft/vscode-eslint` main.zip at runtime). Also **`extra/eslint_d 15.0.2-1`** — a resident
  daemon that kills ESLint's ~1 s Node startup per invocation. **Genuinely worth it for an agent
  that lints in a loop.**

**TS/JS ranking for agents:** (1) `tsc --lsp --stdio` / `tsc --noEmit` (TS7) · (2)
`biome check --reporter concise` · (3) `oxlint` if you want max rule coverage at Rust speed ·
(4) `eslint_d` only where irreplaceable custom plugins exist · (5) `typescript-language-server` as
the TS≤6 fallback.

### 3.3 Everything else

| Server | Latest | Released | Arch pkg | Arch ver | Lag |
|---|---|---|---|---|---|
| **gopls** | `v0.23.0` | 2026-07-09 | `extra/gopls` | 0.23.0-1 | **none** |
| **rust-analyzer** | `2026-07-27` | 2026-07-27 | `extra/rust-analyzer` | 20260608-1 | ~7 wks |
| **bash-language-server** | `5.6.0` | 2025-04-13 | `extra/bash-language-server` | 5.6.0-1 | none |
| **shellcheck** | `v0.11.0` | 2025-08-04 | `extra/shellcheck` | 0.11.0-130 | none |
| **yaml-language-server** | `1.24.0` | 2026-07-07 | `extra/yaml-language-server` | 1.23.0-1 | ~3 wks |
| **vscode-json-languageserver** | VS Code 1.122 | 2026-05-28 | `extra/vscode-json-languageserver` | 1.122.0-1 | n/a |
| **dockerfile-language-server** (rcjsuen) | `0.15.0` | 2025-10-15 | `extra/dockerfile-language-server` | 0.15.0-3 | none |
| docker-language-server (Docker official) | `v0.20.1` | **2025-10-14** | AUR `docker-language-server-bin` | 0.20.1-1 | none |
| **terraform-ls** | `v0.39.0` | 2026-07-23 | AUR `terraform-ls` | 0.38.8-1 | 1 rel |
| tofu-ls (OpenTofu) | `v0.5.3` | 2026-07-08 | AUR `tofu-ls-bin` | 0.5.3-1 | none |
| **marksman** | `2026-02-08` | 2026-02-08 | `extra/marksman` | 20260208-3 | none |
| **taplo** | `0.10.0` | **2025-05-23** | `extra/taplo-cli` | 0.10.0-1 | none |
| tombi (taplo alt.) | `v1.2.4` | 2026-07-19 | *none* — `uv tool install tombi` | — | — |
| **lua-language-server** | `3.18.2` | 2026-04-14 | `extra/lua-language-server` | 3.18.2-1 | none |

Notable, and easy to get wrong:
- ⚠️ **`gopls fix` / `gopls inspect` were REMOVED in v0.23.0** → `gopls codeaction` / `gopls remote`.
  Arch already ships 0.23.0, so scripts calling `gopls fix` break **today**.
- ⭐ **gopls has a built-in MCP server** — `gopls mcp` (disk-only) or
  `gopls serve -mcp.listen=localhost:8092` (attached to a live session, sees unsaved buffers).
  `gopls mcp -instructions > CONTEXT.md`. Requires ≥v0.20. Open caveats: fd exhaustion
  (golang/go#76291), no multi-workspace daemon (#78668) — run one per repo.
- ⭐ **`shellcheck -f diff` emits a unified diff you can pipe straight to `git apply`.** Use
  `-f json1`, not the legacy `json` (which assumes tab stop 8). Prefer AUR `shellcheck-bin` (static)
  over `extra/shellcheck` (large Haskell dep tree).
- **Docker's official `docker-language-server` has NOT superseded rcjsuen's** — Docker's last release
  is 2025-10-14, and it hard-requires Buildx as a Docker CLI plugin (useless in a sandboxed agent).
  rcjsuen's is what Arch packages and it bundles a **batch JSON linter**:
  `…/dockerfile-utils/bin/dockerfile-utils lint --json`.
- **bash-language-server has had no release in ~15 months.** It just shells out to `shellcheck`
  (500 ms debounce) and `shfmt`. **For an agent, skip the LSP and call shellcheck directly** — more
  useful output, far less RAM.
- **lua-language-server has a real batch mode:** `--check <path> --logpath <dir>` writes
  `check.json`. **Set `--logpath` per-invocation** or concurrent agent runs race.

---

## 4. The install script (Arch / CachyOS)

```bash
#!/usr/bin/env bash
# 06-lsp-toolchain.sh — deterministic code intelligence for local-model coding agents
# Verified against Arch extra/ + AUR on 2026-07-30.
set -euo pipefail

# ---------- 1. Core runtimes ----------
sudo pacman -S --needed \
  nodejs npm uv go rust jq git

# ---------- 2. Language servers (official repos) ----------
sudo pacman -S --needed \
  pyright \                    # 1.1.411  Python LSP  (opencode built-in id: pyright)
  ruff \                       # 0.16.0   lint+format+LSP  ⚠️ PIN `select` FIRST (413 default rules)
  ty \                         # 0.0.63   Astral type checker — CLI gate only, LSP is experimental
  typescript-language-server \ # 5.1.3    TS<=6 fallback LSP (opencode built-in id: typescript)
  biome \                      # 2.5.6    JS/TS/JSON lint+format+LSP, type-aware rules (id: biome)
  eslint eslint-language-server eslint_d \   # 10.8.0 / 3.0.24 / 15.0.2 — eslint_d kills 1s Node startup
  gopls \                      # 0.23.0   Go  ⚠️ `gopls fix`/`inspect` REMOVED in 0.23; also has `gopls mcp`
  rust-analyzer \              # 20260608 Rust (7wk behind upstream) [RAM: 257MB-1.4GB, measured]
  bash-language-server \       # 5.6.0    Bash  (or just call shellcheck directly — cheaper)
  shellcheck \                 # 0.11.0   (`-f json1`, or `-f diff | git apply`)
  yaml-language-server \       # 1.23.0   YAML  ⚠️ open RAM bug on git-conflicted files (#216)
  lua-language-server \        # 3.18.2   (batch: --check . --logpath ./ls-log)
  marksman \                   # markdown  (register as custom opencode server)
  taplo-cli \                  # 0.10.0 TOML — ⚠️ no upstream release in ~14mo; see `tombi` below
  vscode-json-languageserver vscode-css-languageserver vscode-html-languageserver \
  tflint                       # terraform lint (--format json); terraform-ls has no batch mode

# ---------- 3. Deterministic code-intel tools ----------
sudo pacman -S --needed \
  ast-grep \      # 0.44.1 in extra (upstream 0.45.0) — structural search/rewrite
  ripgrep \       # 15.2.0
  fd \            # 10.4.2
  ctags \         # 6.2.1 universal-ctags (pkg is `ctags`, NOT `universal-ctags`)
  just \          # 1.57.0 — the canonical `just verify` entrypoint
  pre-commit \    # 4.6.1
  tokei \         # 14.0.0 — LOC census, cheap orientation
  tree-sitter-cli \
  difftastic \    # 0.69.0 — structural diffs
  hyperfine watchexec entr sd

# ---------- 4. AUR (paru/yay) ----------
paru -S --needed \
  basedpyright-bin \    # 1.39.9 — RECOMMENDED Python type authority (notebook CLI, Pylance-grade LSP)
  ty-bin \              # 0.0.65 — newer than extra/ty 0.0.63; fast second-opinion gate
  oxlint-bin \          # 1.76.0 — type-aware linting, STABLE, built on tsgo/TS7
  shellcheck-bin \      # 0.11.0 static — avoids the Haskell dep tree that extra/shellcheck pulls
  terraform-ls \        # 0.38.8 (upstream 0.39.0)
  lefthook \            # 2.1.10 — optional; faster than pre-commit for the inner loop
  repomix               # 1.17.0 — repo map / codebase digest
# NOT recommended right now:
#   pyrefly-bin   # best conformance (95.1%) BUT open 20GB (#3466) and 100GB (#2970) memory reports
#   zuban-bin     # 98.6% conformance but AGPL-3.0, thin adoption, unverified perf claims

# ---------- 5. npm-only ----------
sudo npm i -g \
  dockerfile-language-server-nodejs   # 0.15.0 — no Arch/AUR package
# Batch Dockerfile lint WITHOUT the LSP handshake, bundled in the Arch pkg:
#   /usr/lib/node_modules/dockerfile-language-server/node_modules/dockerfile-utils/bin/dockerfile-utils lint --json

# ---------- 6. Python agent tooling (uv, isolated) ----------
uv tool install -p 3.13 serena-agent   # 1.6.1  ⚠️ CVE-2026-49471 patched in >=1.5.2
serena init
uv tool install tombi                  # 1.2.4 — live taplo alternative (NOT `cargo install tombi-cli`)

# ---------- 7. Per-project, NOT global ----------
# TypeScript 7 (native Go compiler, GA 2026-07-08). Arch's extra/typescript is 6.0.3 — a major behind.
#   pnpm add -D typescript@7            # gives `tsc`; LSP via `tsc --lsp --stdio`
# Zero-Node path for agents (24MB static Go binary):
#   ./node_modules/@typescript/typescript-linux-x64/lib/tsc --lsp --stdio
# Need the old programmatic API (not shipping until TS 7.1)? alias TS6 side-by-side:
#   pnpm add -D typescript@npm:@typescript/typescript6

# ---------- 8. Optional: evaluate as serena alternatives (§2.8) ----------
# cargo install codanna        # 9 tools, no language servers, one-shot CLI mode = 0 resident schema
# npm i -g @probelabs/probe    # `probe search --max-tokens N`, `probe extract file#symbol`

# ---------- 9. Sanity ----------
for b in pyright-langserver basedpyright-langserver ruff ty tsc \
         typescript-language-server biome oxlint eslint_d gopls \
         rust-analyzer bash-language-server yaml-language-server \
         docker-langserver marksman taplo ast-grep rg fd ctags just serena; do
  command -v "$b" >/dev/null && printf '  ok  %s\n' "$b" || printf '  MISSING %s\n' "$b"
done
```

**RAM budget note.** With `coder` (~23.3 GB, <1 GiB headroom) resident on the GPU, LSP servers live
in system RAM (64 GB) — not a problem. The real constraint is *process count*: opencode spawns a
server per (root, language) pair. If you work across many worktrees (Orca does), you can end up with
6–10 pyright/tsserver processes. Mitigations: `OPENCODE_DISABLE_LSP_DOWNLOAD=true` plus explicitly
disabling servers you don't use (§7 config).

---

## 5. Automatic feedback loops — the hook designs

### 5.1 opencode: you mostly don't need a plugin

**Tier 0 (free, do this first):** `"lsp": true` + `"formatter": true`. Every `edit`/`write` now
returns `<diagnostics file="...">ERROR [l:c] msg</diagnostics>` appended to the tool output, and the
file is auto-formatted. Zero plugin code. This is opencode's equivalent of Claude Code's PostToolUse
hook, and it's already written for you.

**Tier 1 (plugin): whole-project typecheck + tests after edits.** LSP diagnostics only cover files
the server has opened. To force a project-wide gate, add
`~/.config/opencode/plugin/verify.ts`:

```ts
import type { Plugin } from "@opencode-ai/plugin"

const EDIT_TOOLS = new Set(["edit", "write", "apply_patch"])
const DEBOUNCE_MS = 4000
let last = 0

export const VerifyPlugin: Plugin = async ({ $, directory }) => {
  return {
    "tool.execute.after": async (input, output) => {
      if (!EDIT_TOOLS.has(input.tool)) return
      const now = Date.now()
      if (now - last < DEBOUNCE_MS) return   // don't run on every edit of a burst
      last = now

      // Single canonical gate. Keep it FAST (<5s) or the agent stalls.
      const res = await $`just verify-fast`.cwd(directory).nothrow().quiet()
      const text = (res.stdout?.toString() ?? "") + (res.stderr?.toString() ?? "")
      if (res.exitCode === 0) {
        output.output += `\n\n<verify status="pass" cmd="just verify-fast" />`
        return
      }
      // Budget the injection — a 7B model drowns in a 500-line traceback.
      const trimmed = text.split("\n").slice(0, 40).join("\n")
      output.output +=
        `\n\n<verify status="fail" cmd="just verify-fast">\n${trimmed}\n</verify>\n` +
        `Fix these before continuing.`
    },
  }
}
```

with a `justfile`:

```make
# fast: seconds, runs after every edit burst
verify-fast:
    ruff check --quiet .
    ty check --quiet .          # or: pyright --outputjson . | jq '.summary'
    pnpm exec tsc --noEmit

# full: the gate before "done"
verify:
    just verify-fast
    ruff format --check .
    uv run pytest -q
    pnpm biome check .
```

Design rules that matter for a small model:
1. **One command, one name.** `just verify-fast`. Don't make the model choose which checker to run.
2. **Truncate hard.** 40 lines max. A 7B model will happily spend 3k tokens re-reading a traceback.
3. **Debounce.** Multi-file refactors produce transient errors; running on every single edit teaches
   the model to thrash.
4. **Structured markers.** `<verify status="fail">` is easier for a small model to pattern-match than
   prose.
5. **Never inject on pass beyond a one-liner.** Silence is a signal.

**Tier 2:** use `event?:` with `lsp.client.diagnostics` / `file.edited` if you want out-of-band
reactions (e.g. a toast, or writing a scratch file) rather than in-band injection.

**Tier 3 (context shaping):** `"experimental.chat.system.transform"` lets you append the repo map
(§6) to the system prompt programmatically instead of hard-coding it into AGENTS.md — useful because
the map changes per-worktree.

### 5.2 pi: `tool_result` middleware

`~/.pi/agent/extensions/verify.ts`:

```ts
import type { Pi } from "@earendil-works/pi-coding-agent";

const EDIT_TOOLS = new Set(["edit", "write"]);
const DEBOUNCE_MS = 4000;
let last = 0;

export default function (pi: Pi) {
  pi.on("tool_result", async (event, ctx) => {
    if (!EDIT_TOOLS.has(event.toolName)) return;
    const now = Date.now();
    if (now - last < DEBOUNCE_MS) return;
    last = now;

    const proc = Bun.spawnSync(["just", "verify-fast"]);   // or child_process
    const out = (proc.stdout.toString() + proc.stderr.toString())
      .split("\n").slice(0, 40).join("\n");

    if (proc.exitCode === 0) {
      return { content: [...event.content,
        { type: "text", text: `\n<verify status="pass" />` }] };
    }
    return {
      content: [...event.content,
        { type: "text", text: `\n<verify status="fail">\n${out}\n</verify>` }],
      isError: false,   // keep false: the EDIT succeeded; the project is just broken
    };
  });
}
```

pi's docs state `tool_result` handlers "chain like middleware", "each handler sees the latest result
after previous handler changes", and may return **partial patches** (`content`, `details`, `isError`,
`usage`). Use `ctx.signal` for any nested async work so Esc cancels it.

Alternative, more aggressive: `pi.sendMessage({...}, { deliverAs: "steer", triggerTurn: true })`
inside `tool_result` — this *steers* the running agent rather than decorating the tool output. Use
sparingly; steering confuses small models mid-plan.

### 5.3 serena's own hooks (bonus)

serena main ships a `serena-hooks` CLI with `--client=claude-code|codex|grok` emitting native
PreToolUse allow/deny output — i.e. it can *block* the agent's built-in Read/Edit to force it onto
symbolic tools. **No opencode/pi client is supported** as of 2026-07-30. Not usable here.
Confidence: high (from the main CHANGELOG).

---

## 6. Repo maps and context compression for a small model

### 6.1 The state of the tools

| Tool | Latest | Last activity | Verdict |
|---|---|---|---|
| **repomix** (`yamadashy/repomix`) | **v1.17.0**, 2026-07-21 | pushed 2026-07-26, **27,519 ★** | **Winner.** Actively developed, tree-sitter `--compress`, real token accounting, `--token-budget`, `--mcp`, watch mode, Secretlint scanning. AUR `repomix 1.17.0-1`. |
| **gitingest** (`coderamp-labs/gitingest`, was `cyclotruc/`) | v0.3.1, 2025-07-31 | pushed 2026-07-29, 15,253 ★ | Alive but release-stale; oriented at *remote* repos/web UI. No structural compression. |
| **code2prompt** | v4.2.0, 2025-12-11 | pushed 2026-06-29, 7,511 ★ | Alive, Handlebars templates, token counting. Weaker compression story than repomix. |
| **files-to-prompt** (simonw) | 0.6, **2025-02-19** | no push since | Frozen but complete; it's a 200-line concatenator and does that job. |
| **aider** (`Aider-AI/aider`) | **v0.86.0, 2025-08-09**; pushed **2026-05-22** | 47,808 ★ | **Effectively stalled.** ~1 year without a release, ~2 months without a commit as of 2026-07-30. AUR `aider-chat 0.86.2-2`. Its *ideas* remain the best; the *tool* is no longer a live dependency. |
| **llm-context** (`cyberchitta/llm-context.py`) | `>=0.6.0` | pushed 2026-07-28, 305 ★ | Niche but alive. Rule-based (YAML+MD) selection, "smart excerpting" (structure extraction, 15+ languages), MCP server. `uv tool install "llm-context>=0.6.0"`. |
| **yek** (`mohsen1/yek`) | v0.25.5, 2026-06-29 | 2,470 ★ | Fast Rust serializer, git-priority ordering. No structural compression. |

### 6.2 aider's repo map algorithm (still the best idea)

From <https://aider.chat/docs/repomap.html>:
- Extract "key symbols defined in each file" and "the critical lines of code for each definition"
  (tree-sitter tag queries).
- Build a graph: **nodes = source files, edges = dependencies** (symbol references between files).
- Run a **graph ranking algorithm** over it to pick which definitions to include.
- Budget with `--map-tokens`, **default 1,000 tokens**; "it does expand the repo map significantly at
  times, especially when no files have been added to the chat."

Example output shape:
```
aider/commands.py:
│class Commands:
│    voice = None
│    def get_commands(self):
│    def run(self, inp):
```

The mechanism in more detail (from <https://aider.chat/2023/10/22/repomap.html> + secondary reads of
the current source — **confidence: high on the algorithm, medium on current internals**):

1. **Tag extraction** — tree-sitter parses every file; `tags.scm` queries emit **definitions** and
   **references** per symbol.
2. **Graph** — a **multi-digraph where files are nodes**; an edge runs from the file *referencing* a
   symbol to the file *defining* it. Definitions with no references get a **self-loop of weight 0.1**
   so they aren't orphaned.
3. **Ranking** — **NetworkX PageRank with *personalization*** biased toward files currently in the
   chat and files the user mentioned. **This is the clever part: the map is query-conditioned, not
   static.** Nothing else in this report has that property.
4. **Distribution** — each file's PageRank mass is spread across its outbound edges to rank
   *individual symbols*, not just files.
5. **Budget** — binary-search fitting to `--map-tokens`, rendered via `grep-ast`'s `TreeContext` with
   `│` / `⋮` elision markers.

**Can it be reused for opencode/pi?** Three routes, none great:
1. **`pdavis68/RepoMapper`** (188 ★, last push **2025-12-08**) — "based entirely on the Repo Map
   functionality in Aider.chat", works as **both CLI and MCP server**. Best direct extraction, but
   small and ~8 months stale.
2. **Import `aider.repomap.RepoMap` as a library** — pulls aider's whole dependency tree (litellm
   etc.) for one class, and the internal API stability across versions is **[unverified]**.
3. **`Aider-AI/grep-ast`** (PyPI 0.9.0, 2025-05-08, 360 ★, **dormant ~15 months**) — the rendering
   layer only. Still useful standalone: `grep-ast <pattern> <files>` shows matches *with AST
   ancestry* (enclosing class/function), which is strictly more token-efficient than `rg -C3`.

**Recommendation: reimplement it.** It is ~300 lines — tree-sitter tags → networkx PageRank →
budget-fit. You control the token budget, you get the personalization hook (bias toward the files
the current task touches), and you avoid three dormant dependencies. Confidence: medium-high.

**repomix `--compress` is the maintained equivalent of the *output shape*** (tree-sitter signature
extraction: "preserve function signatures, type definitions, and class structures while stripping
implementations"), though it does **not** do PageRank-style importance ranking — it compresses
everything you select. You supply the ranking via `--include`/`--ignore`. That's a fair trade for a
homelab.

### 6.3 Recommended repo-map pipeline

```bash
# One-shot: a compressed architectural map with a hard token ceiling
repomix \
  --compress \
  --remove-comments \
  --remove-empty-lines \
  --style markdown \
  --token-budget 8000 \
  --output .agent/repomap.md \
  --ignore "**/*.test.*,**/*.spec.*,**/__snapshots__/**,**/dist/**,**/.venv/**"

# See where the tokens are going before you tune the ignores
repomix --token-count-tree 200
```

Useful flags verified in the repomix README (2026-07-30):
`--compress`, `--remove-comments`, `--remove-empty-lines`, `--token-count-tree [threshold]`,
`--top-files-len`, `--stdout`, `--stdin`, `--split-output`, `--token-budget <N>` (*"Fail with a
non-zero exit code when the packed output exceeds N tokens. Useful as a guard in CI pipelines and
agent workflows"*), `-w/--watch` (300 ms debounce), `--mcp`, `--skill-generate` (emits a Claude Agent
Skill into `.claude/skills/<name>/`).

**Auto-regeneration** — a `post-commit` hook is the right granularity (not `post-edit`; the map is
for orientation, not for correctness):

```bash
# .git/hooks/post-commit   (or via lefthook/pre-commit)
#!/usr/bin/env bash
repomix --compress --remove-comments --style markdown \
        --token-budget 8000 --quiet --output .agent/repomap.md || true
```

**Wiring it into the agent.** Three options, best first:

1. **Don't put it in AGENTS.md.** Your own AGENTS.md comment is right — it's always in context, and
   8k tokens of map would eat 6% of `coder`'s window on every turn including turns that don't need it.
   Instead add a one-line pointer:
   ```md
   - Repo map: `.agent/repomap.md` (compressed signature map, regenerated on commit).
     Read it ONCE at the start of a task if you don't know where things live. Do not re-read it.
   ```
2. **opencode plugin, `experimental.chat.system.transform`** — inject the map into the system prompt
   only for the `plan` agent (which uses `coder-strong`), not for `build`.
3. **`repomix --mcp`** as an MCP server, so the model can pack a *subdirectory* on demand. Highest
   flexibility, but adds tool schemas — and you're already at 3 MCP servers.

**Also generate serena memories from it**: `.serena/memories/architecture.md` fed from a *smaller*
(`--token-budget 2000`) map is a better use of serena's memory system than running `onboarding`.

### 6.4 Evaluations

I found **no published benchmark** comparing repomix/gitingest/code2prompt/aider-repomap on retrieval
quality or downstream coding success, and none specific to 7B–35B local models.
serena's own evaluation (§2.7) is the closest thing, and it is agent-self-assessment on 2 codebases
with frontier models — directionally useful, not a benchmark. **Treat all "which repo map is best"
claims as unverified.** Confidence in this negative finding: medium (the web-search budget for this
session was exhausted before I could exhaust the literature; I did not find a paper, but I cannot
prove one doesn't exist).

---

## 7. Deterministic tools ranked by impact-per-token

### 7.0 The number that justifies the whole section

Measured during this research on a real 115-file / 449 KB repo (token proxy = bytes ÷ 4; treat
absolutes as ~15–25% optimistic since dense symbol/path text tokenizes worse than prose — the
*ratios* are the reliable part):

| Action | est. tokens | vs. `rg -l` |
|---|---|---|
| `cat` every tracked file (naive agent) | **112,351** | 685× |
| `rg -n 'def '` | 1,472 | 9× |
| `rg -n -m2 'def '` | 620 | 3.8× |
| `rg -l 'def '` | **164** | 1× |

The naive full-repo dump alone exceeds `coder`'s 131k window on a *tiny* repo.

And the single most actionable micro-finding in this report — same pattern, different flags:

| Variant | est. tokens | ratio |
|---|---|---|
| `rg -l` | 570 | 1× |
| `rg -c` | 601 | 1.05× |
| `rg -n` | 4,983 | 8.7× |
| **`rg --json`** | **18,450** | **32×** |
| `rg -n -C2` | 19,695 | 34× |

**`rg --json` costs 3.7× more tokens than `rg -n` and conveys identical information.** ~73% of those
tokens are JSON syntax. The same trap applies to `ruff --output-format json`, `knip --reporter json`,
`depcruise --output-type json`, `ctags --output-format=json`, and opencode's own `lsp` tool
(which returns `JSON.stringify(result, null, 2)`).

> **Rule to put in AGENTS.md: JSON output is for scripts, never for the model. Use
> `--output-format concise` / `--reporter compact` / plain `-n`.**

### Tier S — do these

**1. opencode LSP auto-diagnostics.** Covered above. Cost: ~0 tokens on green. Benefit: the model
cannot ship a syntax/type error without seeing it.

**2. `just verify-fast` as the single verification verb.** A small model's worst failure mode is
"declaring done". One named command removes the decision. Cost ~200 tok/run.

**3. `ast-grep` 0.45.0** (2026-07-23, 15,311 ★, pushed 2026-07-30; `extra/ast-grep 0.44.1-1`).
Structural search/rewrite that a 7B model can actually get right, because the pattern *is* code:
```bash
ast-grep run -p 'requests.get($URL)' -l py --json=compact       # find
ast-grep run -p 'assert $A == $B' -r 'assert $B == $A' -l py -U # rewrite in place
ast-grep scan --json=stream                                      # run rule set
```
`--json=compact` keeps output ~50–300 tokens for typical queries vs. thousands for `rg` with context.
Add rules in `sgconfig.yml` to encode your conventions as *machine-checkable* rules — then they're a
lint gate rather than an AGENTS.md sentence the model may ignore.
**Official MCP:** `uvx --from git+https://github.com/ast-grep/ast-grep-mcp ast-grep-server`
(441 ★, 2026-07-21, self-described "experimental").

**4. `ruff check --fix` / `ruff format` (0.16.0) and `biome check --write` (2.5.6).** Auto-fixing
linters remove entire categories of work from the model. Cost: 0 tokens (opencode formatters run
silently).

**5. ripgrep 15.2.0 / fd 10.4.2.** Non-negotiable baseline. The agent-optimisation is *how you
instruct it* (see §7.0 for measured numbers):
- **`rg -l <pat>` first, always.** Locate, then read. 685× cheaper than dumping the repo.
- **`rg -c`** for "is this symbol central or incidental" — same price as `-l`.
- **`rg -n -m2`** — `-m2` caps matches *per file*, bounding worst-case blowup on a common token.
  This is the single most underused flag for agent work.
- **Never `rg --json` or `-C2` into the model's context** (32× and 34× respectively).
- `--max-columns=200 --max-columns-preview` is insurance against minified/generated files, not a
  general win.

### Tier A — high value

**6. `tsc --noEmit` (TypeScript 7).** Native Go compiler, GA 2026-07-08. Whole-project truth in a
fraction of the old wall-clock. Per-project `pnpm add -D typescript@7`.

**7. `ty check` (0.0.65).** Sub-second Python type check across a whole repo. Use as a *gate*, and
keep pyright as the LSP. Its 0.0.x version is the caveat, not its speed.

**8. serena `rename_symbol` + `replace_symbol_body`.** The measured 8-calls→1-call win on cross-file
renames (§2.7) is real and is exactly the kind of multi-step bookkeeping a small model botches.

**9. `just` 1.57.0 as the canonical verb** (`extra/just 1.57.0-1`, exactly current; released
2026-07-19, 35,020 ★). Beyond §Tier-S-2, two properties matter specifically for small models:
- **`just --list` is a self-describing action menu.** Doc comments above recipes appear in the
  listing. ~150 tokens teaches the model the repo's entire verified vocabulary — no guessing between
  `npm test` / `pytest` / `make check`, no AGENTS.md drift.
- **`just --json`** exists (`--dump --dump-format json`) for harness code.
- No tab-vs-space semantics, no `.PHONY` traps, no implicit rules — i.e. none of make's failure
  modes that a 7B model reliably trips over.
Alternatives, both Arch-current: `extra/mise 2026.7.17` (tasks + toolchain pinning) and
`extra/go-task 3.52.0`. `just --list`'s ergonomics edge them out for this purpose.

**10. `grimp` 3.15 / `import-linter` 2.13** (both 2026-07-03; repo is now `python-grimp/grimp`).
`grimp` is the standout: a **queryable** import graph as a *library*, not a report generator —
`find_illegal_dependencies_for_layers()`, `find_downstream_modules('x')`,
`find_shortest_chain(a, b)`. One targeted question → a handful of module names, **~20–100 tokens**.
`import-linter` turns "don't import app.web from app.core" into a CI failure: **clean run ≈ 15
tokens, violation ≈ 100–300.** That's the ideal guardrail shape — near-zero when passing. It
directly catches the classic small-model move of "add whatever import makes the error go away",
which silently inverts your layering.

**11. `knip` 6.29.0** (2026-07-22, 11,857 ★) — unused files/exports/deps/types for TS; 150+ plugins.
Targets small-model refactor debris (orphaned exports after an edit). Use `--reporter compact`;
clean ≈ 10 tokens, typical findings 300–800.
**`dependency-cruiser` 18.1.0** (2026-07-12) — use **`--output-type err`** (violations only, clean
run ≈ 10 tokens). `--output-type json`/`dot` on a mid-size repo is tens of thousands of tokens.

### Tier B — situational

**12. pre-commit 4.6.1** (`extra/pre-commit 4.6.1-1`, exactly current) vs **lefthook 2.1.10**
(AUR, 6 votes; 8,585 ★, released 2026-07-08) vs **husky 9.1.7 (published 2024-11-18 — stagnant,
skip)**.
- pre-commit is the standard, especially in Python. Its weakness in an agent loop is **startup
  cost**: isolated per-hook virtualenvs mean a cold/invalidated cache can burn 30s+. Always scope
  it: `pre-commit run <hook-id> --files <paths>`, never bare `--all-files` mid-loop.
- lefthook is a single dependency-free Go binary with `parallel: true` — lowest friction for a
  tight inner loop.
- Either way, hooks matter *less* than `just verify`: the agent should discover problems while
  editing, not at commit time.

**13. universal-ctags 6.2.1** (`pacman -S ctags` — the package is `ctags`; `universal-ctags` is in
neither extra nor AUR). Repo pushed 2026-07-30; releases are just infrequent by design.
**The correct agent pattern is a lookup table, not context:** a 500-file repo yields 3,000–8,000
symbols ≈ **50k–200k tokens if pasted**. Instead build it once and *grep it*:
`ctags -R --output-format=json --fields=+n` then `rg '^"name"' tags` → ~20 tokens.
Value over rg: ctags answers "*where is X **defined***" with no false positives from call sites and
comments — precisely the distinction a small model wastes turns on. Largely redundant where LSP
works; valuable for languages with no server.

**14. `vulture` 2.16** (2026-03-25) — **still has a real niche**: ruff has F401 (unused imports),
F841 (unused vars), ARG, ERA — but **no unused-*function*/class detection**. Ruff does *not* subsume
vulture. ⚠️ Run at `--min-confidence 80+` or its false positives (dynamic dispatch, framework hooks)
become noise the model "fixes" by deleting live code.
**`refurb` and `bandit` ARE subsumed** by ruff's `FURB` and `S` rule sets — enable those instead of
running two more tools. `deadcode` (last publish 2024-08-09) is stale.
`pydeps` 3.0.6 / `madge` 8.0.0 (**last publish 2024-08-05**) — graphviz-oriented, superseded by
dependency-cruiser.

**15. `probe`** (`probelabs/probe`, formerly `buger/probe`) — **the most on-thesis tool found**.
675 ★, pushed 2026-07-30, Rust. "AI-friendly semantic code search… ripgrep speed with tree-sitter AST
parsing." Three primitives that are *exactly* right for a constrained window:
- `probe search <pattern> --max-tokens <n>` — **an explicit token budget on a search tool**, plus
  **session-based dedup** so it won't re-send blocks the model already saw.
- `probe extract src/main.rs#authenticate` — extract **by symbol name**, no line-number guessing.
- `probe query 'async fn $NAME($$$)' --language rust` — structural query.
MCP: `npx @probelabs/probe@latest mcp`. Install `npm i -g @probelabs/probe`.
⚠️ Version is **`v0.6.0-rc329`** — 329 release candidates, no stable 0.6.0. **Pilot; don't
hard-depend.** ⚠️ Do NOT use AUR `probe-bin` (pinned at 0.0.3). Confidence: medium on longevity.

**16. `tokei` 14.0.0** — 20-token repo census. Cheapest possible first move for orientation, before
spending anything on a repo map.

**17. Go static analysis** — `go vet` is free and ships with `extra/go 1.26.5`.
`extra/staticcheck 2026.1` (current) supports `-f json`. `extra/golangci-lint 2.12.2` (current)
aggregates the lot behind one command — the right shape for `just verify` in a Go repo.

**18. `difftastic` 0.69.0** — structural diffs. Reduces *human* review noise; its output isn't
LLM-optimised, so keep plain `git diff` for the model.

### Tier C — skip for this rig

**Zoekt.** Alive (`sourcegraph/zoekt`, 1,802 ★, pushed 2026-07-29, Apache-2.0, commit-versioned) and
**packaged: `extra/zoekt r1921.893a523`**. Fully standalone:
`zoekt-git-index -index ~/.zoekt /path/to/repo`, query via `zoekt` or `zoekt-webserver`.
**But** trigram indexing wins over ripgrep at ~1M+ files; on a single repo on NVMe, rg is faster
end-to-end because there's no index to build or keep fresh. Skip unless indexing dozens of repos.

**SCIP.** Healthy — `sourcegraph/scip` **v0.9.0 (2026-06-29)**, and indexers all live:
`scip-python` 0.6.6 (pushed 2026-07-30), `scip-typescript` 0.4.0, `scip-go` 0.2.7, `scip-clang`,
`scip-dotnet`. **LSIF is superseded** (Sourcegraph ships `scip convert` for LSIF→SCIP;
*[unverified]* — no formal deprecation notice fetched). SCIP gives precise cross-repo references
with real type resolution, **but there is no ergonomic, token-cheap local CLI to query it** — you'd
write the glue. **ctags + ast-grep + LSP gets 80% of the value at 5% of the effort** for one dev on
one box. Revisit for a large polyglot monorepo.
*(Correction to my earlier draft: `scip` did **not** move out of the Sourcegraph org — the
`scip-code/scip` name is a redirect artifact. Canonical is `sourcegraph/scip`.)*

**🔴 What actually happened to Sourcegraph** (verified via the GitHub API, 2026-07-30 — worth
stating precisely because the ecosystem story is widely garbled):
- `sourcegraph/sourcegraph` → **404**. What remains is
  `sourcegraph/sourcegraph-public-snapshot`, **archived, last push 2024-09-02**, 10,301 ★.
- `sourcegraph/cody` → **404**. Remains: `sourcegraph/cody-public-snapshot`, **archived, last push
  2025-08-01**, 3,811 ★.
- So: **the platform went private Sept 2024; Cody went private Aug 2025.** Cody wasn't loudly
  killed — it was privatized, and company energy moved to **Amp** (ampcode.com), closed-source, no
  public repo.
- **The load-bearing consequence for you: the closures did NOT touch the code-intelligence
  primitives.** `scip`, `scip-*` and `zoekt` are all still Apache-2.0, public, and pushed this week.
  Sourcegraph closed the *product*, not the *protocol*.

**comby 1.8.1** — repo alive-ish (2,664 ★, pushed 2026-06-08) but **last release 2022-06-28 — four
years**. AUR `comby 1.8.1-2`. Superseded by ast-grep on speed, language coverage, rule system and
output control. **Do not adopt in 2026.**

**Semgrep — correct the common misconception.** It is **wrong** to say "Semgrep went closed source."
Per Semgrep's own docs (<https://docs.semgrep.dev/faq/comparisons/opengrep>): **the CE engine has
been LGPL 2.1 continuously since 2020 and still is.** What changed is that **in December 2024 the
Semgrep-maintained *rules* moved to a proprietary license** limiting use to internal, non-competing,
non-SaaS contexts; inter-file taint analysis is Pro-only.
- `semgrep/semgrep` **v1.172.0** (2026-07-28), 16,054 ★ — the company is thriving.
- **`opengrep/opengrep` v1.26.0** (2026-07-24), 2,846 ★, LGPL 2.1 — a fork of the last
  fully-featured CE codebase by a 10+ vendor consortium (Aikido, Endor Labs, Jit, Orca Security …),
  launched Feb 2025, pushed 2026-07-30. **This is the OSS path if you want Semgrep-class rules.**
- Neither is in Arch official. `paru -S opengrep-bin` (AUR 1.26.0-1, **0 votes** — verify the
  PKGBUILD) or `uv tool install semgrep`.
- **Verdict: MEDIUM impact, and not part of the inner loop.** It's seconds-to-minutes and noisier
  than ast-grep. Use it for a periodic security pass; use ast-grep rules to encode conventions.

---

## 8. Concrete config changes for this repo

### 8.1 `opencode.json` — LSP + formatter + custom servers

```jsonc
{
  "$schema": "https://opencode.ai/config.json",

  // ...existing provider / model / agent blocks unchanged...

  "lsp": {
    // Built-ins you want are enabled automatically by the presence of this object.
    // Register the ones opencode has no definition for:
    "marksman":  { "command": ["marksman", "server"],       "extensions": [".md"] },
    "taplo":     { "command": ["taplo", "lsp", "stdio"],    "extensions": [".toml"] },

    // RECOMMENDED: basedpyright over pyright (notebook CLI checking, Pylance-grade LSP features)
    "pyright": { "disabled": true },
    "basedpyright": {
      "command": ["basedpyright-langserver", "--stdio"],
      "extensions": [".py", ".pyi"]
    },

    // TypeScript 7 native LSP. opencode's built-in `typescript` id resolves tsserver.js,
    // which TS7 does NOT ship — so it must be registered by hand.
    // "typescript": { "disabled": true },
    // "tsgo": {
    //   "command": ["./node_modules/@typescript/typescript-linux-x64/lib/tsc", "--lsp", "--stdio"],
    //   "extensions": [".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"]
    // },

    // Turn off servers you never use — each one is a process + RAM.
    "jdtls":     { "disabled": true },
    "csharp":    { "disabled": true },
    "razor":     { "disabled": true },
    "fsharp":    { "disabled": true },
    "julials":   { "disabled": true },
    "elixir-ls": { "disabled": true },
    "hls":       { "disabled": true },
    "ruby-lsp":  { "disabled": true }
  },

  "formatter": true,

  "permission": {
    "edit": "ask",
    "bash": "ask",
    "lsp": "allow"          // the experimental lsp tool asks by default
  },

  "mcp": {
    "serena": {
      "type": "local",
      "enabled": true,
      "command": [
        "serena", "start-mcp-server",
        "--context", "ide",            // was: ide-assistant (deprecated → claude-code)
        "--mode", "no-onboarding",
        "--project", "{cwd}"
      ],
      "environment": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

### 8.2 Environment (add to `~/.bash_profile`, next to `LITELLM_API_KEY`)

```bash
export OPENCODE_EXPERIMENTAL_LSP_TOOL=true   # enables the 9-op `lsp` tool
export OPENCODE_DISABLE_LSP_DOWNLOAD=true    # use pacman-managed binaries only
# export OPENCODE_EXPERIMENTAL_LSP_TY=true   # only if you want ty as the Python LSP
```

Caution: do **not** set the blanket `OPENCODE_EXPERIMENTAL=true` — it would also switch on
`experimentalPlanMode`, `experimentalCodeMode`, `experimentalEventSystem`, `experimentalWorkspaces`,
`experimentalBackgroundSubagents`, `experimentalReferences`, `experimentalOxfmt` and Exa search, all
at once. Enable individual flags.

### 8.3 AGENTS.md — replace the "Golden rules" LSP line

The current rule says to prefer serena over reading whole files. Update it to reflect the new
hierarchy and to guard against the 64KB `find_referencing_symbols` blowup:

```md
## Code intelligence — cheapest tool that answers the question
1. `rg -n --max-count=3` / `fd` — "where does this string appear?"
2. `ast-grep run -p '<pattern>' --json=compact` — "where does this *code shape* appear?"
3. `get_symbols_overview` (serena) — "what's in this file?" (never `read` a file to find out)
4. `find_symbol` (serena, name paths) or the `lsp` tool — "show me this definition"
5. `find_referencing_symbols` — ONLY when you need semantic precision. It can return 50k+ chars.
   For "who mentions this name", use rg.
6. `read` — only for a file you are about to edit.

After every edit, opencode appends LSP errors to the tool result and `just verify-fast` runs.
If `<verify status="fail">` appears, fix it before doing anything else. Do not claim done until
`just verify` is green and you have pasted the result.
```

---

### 8.4 The single biggest gap in the literature

The flagship 2026 local-model post — **"Qwen 3.6 27B is the sweet spot for local development"**
(<https://quesma.com/blog/qwen-36-is-awesome/>, HN 1,192 points, 2026-06-29) — is *exactly* your
model class, recommends **opencode / pi + llama.cpp**, and **makes zero mention of serena, LSP, or
code-intelligence MCP**. A commenter asked directly whether code-intelligence MCPs help; there was no
substantive reply.

**The local-model × semantic-code-intelligence intersection is essentially unexplored as of mid-2026.
No head-to-head benchmark of serena (or any alternative) on a local 7B–35B model exists.** tilth's
Haiku 4.5 numbers (54%→73%) are the closest available proxy, and they're vendor-published.

Also worth knowing for a llama.cpp rig: every MCP tool definition is **prefix-cache weight**. A
community observation on local coding agents: *"coding agents like Claude Code were basically
unusable with local models. every few turns the prefix shifts, KV cache gets invalidated."* That is
an underrated argument for a small resident tool surface — and for preferring CLI-shaped tools
(ast-grep, ripgrep, codanna's one-shot mode) invoked through `bash` over always-resident MCP schemas.

**This is a genuine opportunity: your `bakeoff/` directory is the right place to produce the first
real numbers here.** Suggested A/B matrix: {no serena, trimmed serena, full serena} ×
{opencode `lsp` on/off} × {edit vs apply_patch} on a fixed task set, scored on tokens-per-correct-
change.

---

## 9. Open questions / lowest-confidence items

1. **opencode plugin directory**: docs say `.opencode/plugins/`, source/examples use
   `plugin/`. Verify empirically on the rig.
2. **`uv format`** — opencode's formatter probes `uv format --help`; I did not verify against uv's
   own changelog that this subcommand exists in `uv 0.12.0`.
3. **Biome 2.5 type-aware linting** — partial or complete? Unverified.
4. **Sourcegraph/Cody 2026 status** — the `scip` org move is suggestive but I did not confirm.
5. **Semgrep OSS licensing 2026** — unverified.
6. **RAM figures per language server** — order-of-magnitude estimates, no published benchmark found.
7. **Whether opencode's `lsp` tool graduates from experimental** — watch
   `packages/opencode/src/effect/runtime-flags.ts` for `experimentalLspTool` disappearing.
8. **No benchmark exists** (that I found) comparing repo-map tools — or serena vs alternatives — for
   downstream coding success with small local models. See §8.4.
9. **"The Harness Problem" numbers** (§2.9) are second-hand; I could not fetch the blog directly.
   Direction credible, exact figures unconfirmed.
10. **tilth's benchmark table** is vendor-published and unreplicated.
11. **`codebase-memory-mcp`'s 36,596 stars in 5 months** — extraordinary; unverified preprint
    (arXiv:2603.27277). Corroborate before adopting.
12. **Zuban's "half the memory of ty/pyrefly"** — vendor claim with **no benchmark page behind it**.
13. **Per-server RAM figures** — only rust-analyzer publishes rigorous ongoing data
    (<https://rust-analyzer.github.io/metrics/>: ripgrep 257 MB, diesel 364 MB, webrender 553 MB,
    rust-analyzer-on-itself 1,405 MB, batch `analysis-stats` — a long-running LSP session sits
    higher). gopls auto-dumps a debug zip above 1 GB, i.e. treats that as anomalous. Everything else
    in §3 is anecdote.
14. **`ty`'s current conformance** — the official suite pins it at 0.0.50 (71.1%); nobody has
    published a number for 0.0.65.
15. **Reddit (r/LocalLLaMA, r/ChatGPTCoding) was not reachable** during this research. That is where
    7B–35B tooling is actually discussed, so it is the largest remaining coverage gap.
16. ⚠️ **`gopls fix` and `gopls inspect` were REMOVED in gopls v0.23.0** (2026-07-09), replaced by
    `gopls codeaction` / `gopls remote`. **Arch already ships 0.23.0**, so any script shelling out to
    `gopls fix` breaks today. Also note **gopls has a built-in MCP server** (`gopls mcp`, or
    `gopls serve -mcp.listen=…` to see unsaved buffers) — the most agent-native thing in this whole
    report, though it has an open fd-exhaustion issue (golang/go#76291) and no multi-workspace daemon
    (#78668), so run one per repo.
17. ⚠️ **rust-analyzer's batch CLI is the best RAM escape hatch available**: `rust-analyzer scip .`
    or `lsif .` exports a full index so an agent gets offline go-to-def/find-refs **with no resident
    server**. Also `diagnostics <path>`, `ssr '$a.foo($b) ==>> bar($a, $b)'`, `unresolved-references`.
    Upstream warns these subcommands have no stability guarantees.
18. **`taplo` has had no release in ~14 months** (0.10.0, 2025-05-23) though it isn't archived.
    ⚠️ Do not install from npm (`@taplo/cli` stuck at 0.7.0, 2024-02-01). Live alternative:
    **`tombi` v1.2.4** (2026-07-19) via `uv tool install tombi` — ⚠️ *not* `cargo install tombi-cli`
    (crates.io max is 0.0.1). Neither emits JSON diagnostics.
19. **`vscode-langservers-extracted` is effectively abandoned** (v4.10.0, 2024-05-08). On Arch prefer
    the official split packages `vscode-json-languageserver` / `vscode-css-languageserver` /
    `vscode-html-languageserver` / `eslint-language-server`, all in `extra` and tracking VS Code
    1.122.
20. **yaml-language-server #216** — *"memory usage skyrockets on git-conflicted yaml files"* — **open
    since 2020-06-11.** Guard against this if the agent operates mid-merge.
21. **terraform-ls is MPL-2.0, not BUSL** (the BUSL relicense hit the Terraform CLI, not the language
    server). It has **no batch subcommand** — use `terraform validate -json` or `tflint --format
    json`. OpenTofu's `tofu-ls` v0.5.3 (AUR `tofu-ls-bin`) is a live MPL-2.0 alternative.
