# opencode — full capability surface (researched 2026-07-30)

**Version researched:** `1.18.10`, published 2026-07-30T14:39Z (npm `opencode-ai@1.18.10`, `@opencode-ai/sdk@1.18.10`, `@opencode-ai/plugin@1.18.10`).
Source of truth: <https://registry.npmjs.org/opencode-ai>, <https://github.com/anomalyco/opencode/releases>.

> **Repo moved.** `github.com/sst/opencode` now 301-redirects to **`github.com/anomalyco/opencode`** (repo id 975734319, default branch `dev`, ~191k stars, last push 2026-07-30). Any bookmark/script pinned to `sst/opencode` still works via redirect but the GitHub REST API returns `301 Moved Permanently` without `-L`. Docs remain at <https://opencode.ai/docs>. Doc sources: `packages/web/src/content/docs/*.mdx` on branch `dev`.

Everything below was read from the live docs, the live JSON schema (<https://opencode.ai/config.json>), or the `dev`-branch source. Source-verified claims cite a file path.

---

## 0. Capability matrix vs Claude Code

| Capability | opencode 1.18.10 | Claude Code | Notes |
|---|---|---|---|
| Primary agents / mode switching | ✅ `mode: primary`, Tab-cycle | ✅ | `build`, `plan` built-in |
| Subagents | ✅ `mode: subagent`, `task` tool, `@mention` | ✅ | `general`, `explore`, `scout` built-in |
| Nested subagents | ⚠️ **off by default** (`subagent_depth: 1`) | ✅ (limited) | set `subagent_depth: 2` |
| Parallel subagents | ✅ (model must emit parallel tool calls) | ✅ | no framework-side concurrency cap found |
| Background subagents | ⚠️ experimental flag | ✅ | `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true` |
| Markdown agent defs | ✅ `{agent,agents}/**/*.md` | ✅ `.claude/agents/` | opencode does **not** read `.claude/agents/` |
| Per-agent model/temp/top_p/permissions/steps | ✅ | partial | opencode is richer here |
| Skills (`SKILL.md`) | ✅ incl. `.claude/skills/` compat | ✅ | see §2 for spec deltas |
| Hooks | ✅ JS/TS plugin API, ~20 typed hooks | ✅ shell hooks, 29 events | different shape; see §3 |
| MCP stdio + http + OAuth | ✅ | ✅ | opencode has DCR/RFC-7591 auto-OAuth |
| Per-agent MCP tool allowlisting | ✅ glob patterns | ✅ | |
| LSP | ✅ built-in, 30+ servers, **off by default** | ❌ (no native LSP) | opencode wins |
| LSP exposed as a model tool | ⚠️ experimental flag | ❌ | `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` |
| Custom slash commands | ✅ `{command,commands}/**/*.md` | ✅ | `$ARGUMENTS`, `$1..$n`, `` !`sh` ``, `@file` |
| `AGENTS.md` / `CLAUDE.md` | ✅ both, with precedence | ✅ `CLAUDE.md` | |
| Headless HTTP server + typed SDK | ✅ `opencode serve`, OpenAPI 3.1 | ✅ Agent SDK | opencode's is a plain REST/SSE server — easier for Orca |
| Non-interactive run | ✅ `opencode run`, `--format json` | ✅ `-p` | |
| Session fork / revert / snapshot | ✅ | partial | `POST /session/:id/fork`, `/revert` |
| Structured JSON output | ✅ SDK `format: {type:"json_schema"}` | ✅ | |
| Compaction control | ✅ config + 3 plugin hooks | ✅ `PreCompact` | opencode lets you *replace* the compaction prompt |
| Prompt-cache friendliness on local backends | ❌ known problem | n/a | see §9, issue #37489 |
| Agent "teams" / named inter-agent messaging | ❌ design issue only (#12711) | ✅ | biggest structural gap |

---

## 1. Agents & subagents

Docs: <https://opencode.ai/docs/agents/>. Source: `packages/opencode/src/tool/task.ts`, `packages/opencode/src/config/agent.ts`.

### Types
- **Primary** — you talk to it directly, Tab / `switch_agent` cycles. Built-ins: **build** (all tools), **plan** (edit + bash default to `ask`).
- **Subagent** — invoked by a primary via the `task` tool, or manually via `@name`. Built-ins: **general** (full tools except todo), **explore** (read-only codebase search), **scout** (read-only dependency/upstream-docs research; gated by `OPENCODE_EXPERIMENTAL_SCOUT`).
- **Hidden system agents**: `compaction`, `title`, `summary` — not selectable.
- `mode` accepts `primary` | `subagent` | `all`; **default is `all`** if omitted.

### Discovery paths (source-verified)
`packages/opencode/src/config/agent.ts:13` globs **`{agent,agents}/**/*.md`** — so *both* singular and plural directory names work, and nested subdirectories are supported:
- Global: `~/.config/opencode/agents/` (or `agent/`)
- Project: `.opencode/agents/` (or `agent/`)

Same pattern for commands: `packages/opencode/src/config/command.ts:15` globs `{command,commands}/**/*.md`.
Legacy `{mode,modes}/*.md` still loads as primary agents (deprecated).

**opencode does NOT read `.claude/agents/`.** Claude-Code compatibility covers `CLAUDE.md` and `.claude/skills/` only (`packages/web/src/content/docs/rules.mdx`, `skills.mdx`). Porting Claude Code subagents requires copying/symlinking the markdown into `.opencode/agents/`.

### Per-agent config keys (from <https://opencode.ai/config.json>, `$defs.AgentConfig`)
`model`, `variant`, `temperature`, `top_p`, `prompt`, `tools` (deprecated), `disable`, `description` (required), `mode`, `hidden`, `options`, `color`, `steps` (`maxSteps` deprecated), `permission`. **Unknown keys pass through to the provider as model options** — that's how you set e.g. `reasoningEffort`.

### The `task` tool
Prompt text: `packages/opencode/src/tool/task.ts` + `task.txt`. Args: `description`, `prompt`, `subagent_type`, `task_id` (resume a prior subagent session), `background`.

- **Nesting depth** — `task.ts:106-115`: it walks the parent chain, and fails with *"Subagent depth limit reached"* when `depth >= (cfg.subagent_depth ?? 1)`. **Default 1 = subagents cannot spawn subagents.** Changed in **v1.18.2** (2026-07-15): *"Stopped subagents from launching nested subagents by default, with a configurable `subagent_depth` limit."*
- **Concurrency** — no framework-imposed cap. `task.txt` instructs: *"Launch multiple agents concurrently whenever possible… use a single message with multiple tool uses."* Real parallelism is therefore entirely a function of whether your model emits **multiple tool calls in one assistant message**. On a 24GB single-GPU rig this is also the wrong thing to want: every subagent hits the same llama-swap `big` group serially anyway.
- **Background** — `background: true` requires `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`, else it errors (`task.ts:97-101`). Shipped as "Running subagents can now be sent to the background" in **v1.16.2**.
- **Resume** — pass a prior `task_id` to continue the same subagent session with its context.

### Task permissions (subagent allowlisting)
```json
{"agent":{"orchestrator":{"permission":{"task":{"*":"deny","orchestrator-*":"allow","code-reviewer":"ask"}}}}}
```
`deny` removes the subagent from the Task tool description entirely. **Last matching rule wins** — put `*` first. Users can always `@`-invoke regardless.

⚠️ **Open bug #39086** (2026-07-27, open): *"task tool missing from tool list despite `permission.task` being explicitly allowed"* — reported with a custom `@ai-sdk/openai-compatible` provider on a local proxy; the model's tool list came back without `task` at all. Directly relevant to this rig. Test before relying on orchestrator agents.

---

## 2. Skills

Docs: <https://opencode.ai/docs/skills/>. Shipped in **v1.16.0** ("Added skill discovery and file-based agent loading", 2026-06-05).

**Discovery (all six loaded, walking up from cwd to the git worktree):**
```
.opencode/skills/<name>/SKILL.md          ~/.config/opencode/skills/<name>/SKILL.md
.claude/skills/<name>/SKILL.md            ~/.claude/skills/<name>/SKILL.md
.agents/skills/<name>/SKILL.md            ~/.agents/skills/<name>/SKILL.md
```
Plus config-driven extras (schema `$defs.Config.properties.skills`, undocumented on the docs page):
```json
{"skills":{"paths":["/srv/shared-skills"],"urls":["https://example.com/.well-known/skills/"]}}
```
Remote skills are cached (v1.17.12 fixed refresh).

**Frontmatter — only these fields are recognized; unknown fields are ignored:**
`name` (required, 1–64 chars, `^[a-z0-9]+(-[a-z0-9]+)*$`, must equal the directory name), `description` (required, 1–1024 chars), `license`, `compatibility`, `metadata` (string→string map).

**Deltas from Anthropic's spec:**
- No `allowed-tools` / `disable-model-invocation` / `argument-hint` frontmatter — opencode ignores them silently. Tool gating is done externally via `permission.skill`.
- Progressive disclosure works the same way in spirit: the system prompt lists `<available_skills>` (name + description, verbose form) and the model calls `skill({name})` to load the body. `packages/opencode/src/session/system.ts` comments that agents ingest skills better when the *system prompt* is verbose and the *tool description* terse — the inverse of the tool-description-only approach.
- Skill body is returned as a tool result; bundled resource files are referenced by **filesystem path**, not `file://` (fixed v1.17.10).

**Permissions:**
```json
{"permission":{"skill":{"*":"allow","internal-*":"deny","experimental-*":"ask"}}}
```
Override per agent in frontmatter (`permission.skill.<glob>`) or in `opencode.json` under `agent.<name>.permission.skill`.

**Disabling:** `tools: {"skill": false}` — the `<available_skills>` block is then omitted entirely.

> 🐞 **Your current `opencode.json` has `"tools": {"skills*": true}` — this is a no-op.** The tool is named **`skill`** (singular; `packages/opencode/src/tool/skill.ts`). The glob `skills*` requires the literal prefix `skills`, which `skill` does not match. Skills are enabled by default anyway, so nothing is broken — but the line does nothing and should be deleted or corrected to `"skill": true`.

**Kill switches:** `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, `OPENCODE_DISABLE_CLAUDE_CODE=1`.

---

## 3. Hooks / plugins

Docs page: <https://opencode.ai/docs/plugins/> — **incomplete**. The authoritative list is the `Hooks` interface in `packages/plugin/src/index.ts` (`@opencode-ai/plugin@1.18.10`). Full set:

| Hook | Signature (input → mutable output) | Use |
|---|---|---|
| `event` | `{event: Event}` | catch-all bus subscriber (`session.idle`, `file.edited`, `permission.asked`, `lsp.client.diagnostics`, `todo.updated`, …) |
| `config` | `(config)` | mutate resolved config at load |
| `tool` | `{[name]: ToolDefinition}` | **register custom tools** (Zod schema via `tool()` helper) |
| `auth` | `AuthHook` | custom provider auth/OAuth |
| `provider` | `{id, models()}` | dynamically register models |
| `chat.message` | `{sessionID, agent, model, messageID, variant}` → `{message, parts}` | ≈ Claude Code **UserPromptSubmit** |
| **`chat.params`** | `{sessionID, agent, model, provider, message}` → `{temperature, topP, topK, maxOutputTokens, options}` | **override sampling per request** |
| `chat.headers` | … → `{headers}` | per-request HTTP headers (LiteLLM tags/routing) |
| `permission.ask` | `Permission` → `{status: "ask"\|"deny"\|"allow"}` | ≈ **PreToolUse with a decision** |
| `command.execute.before` | `{command, sessionID, arguments}` → `{parts}` | slash-command interception |
| **`tool.execute.before`** | `{tool, sessionID, callID}` → `{args}` | ≈ **PreToolUse**; throw to block |
| **`tool.execute.after`** | `{tool, sessionID, callID, args}` → `{title, output, metadata}` | ≈ **PostToolUse**; rewrite output |
| `tool.definition` | `{toolID}` → `{description, parameters}` | **rewrite tool descriptions/schemas sent to the model** |
| `shell.env` | `{cwd, sessionID, callID}` → `{env}` | inject env into all shell execution |
| `experimental.chat.messages.transform` | → `{messages}` | rewrite full message array pre-send |
| **`experimental.chat.system.transform`** | `{sessionID, model}` → `{system: string[]}` | **rewrite/trim the system prompt** |
| `experimental.text.complete` | `{sessionID, messageID, partID}` → `{text}` | post-process a completed text part |
| `experimental.session.compacting` | `{sessionID}` → `{context[], prompt?}` | ≈ **PreCompact**; `prompt` fully replaces the compaction prompt |
| `experimental.compaction.autocontinue` | `{sessionID, agent, model, provider, message, overflow}` → `{enabled}` | suppress the synthetic post-compaction "continue" turn |
| `experimental.provider.small_model` | `{provider}` → `{model}` | pick the utility model |
| `dispose` | — | cleanup |

**Loading:** files in `.opencode/plugins/` (project) and `~/.config/opencode/plugins/` (global), auto-loaded at startup; or npm packages via `"plugin": ["pkg", ["pkg", {opts}]]`. Load order: global config → project config → global dir → project dir; all hooks run in sequence. External deps go in `.opencode/package.json` (opencode runs `bun install` at startup). `--pure` disables all external plugins; `OPENCODE_DISABLE_DEFAULT_PLUGINS=1` disables the built-ins.

**Context:** `{project, directory, worktree, client, serverUrl, $, experimental_workspace}`. `$` is Bun's shell. Log via `client.app.log({body:{service,level,message,extra}})`.

### Coverage vs Claude Code's 29 hook events
| Claude Code | opencode equivalent |
|---|---|
| PreToolUse | `tool.execute.before` ✅ |
| PostToolUse / PostToolUseFailure | `tool.execute.after` ✅ (no failure-specific variant) |
| PermissionRequest / PermissionDenied | `permission.ask` ✅ + `permission.asked`/`permission.replied` events |
| UserPromptSubmit | `chat.message` ✅ |
| UserPromptExpansion | `command.execute.before` ✅ |
| SessionStart | `session.created` event ✅ |
| Stop | `session.idle` event ✅ (approximate) |
| SubagentStart / SubagentStop | ⚠️ only via `session.created`/`session.idle` on child sessions + `/session/:id/children` |
| PreCompact / PostCompact | `experimental.session.compacting` ✅ / ⚠️ `session.compacted` event |
| Notification | `tui.toast.show` ✅ (outbound only) |
| PostToolBatch, MessageDisplay, TaskCreated/Completed, TeammateIdle, InstructionsLoaded, ConfigChange, CwdChanged, WorktreeCreate/Remove, Elicitation*, Setup, StopFailure | ❌ no equivalent |
| — | opencode-only: `chat.params`, `chat.headers`, `tool.definition`, `experimental.chat.system.transform`, `shell.env`, `provider.models` |

Net: opencode has **fewer lifecycle events** but **far more mutation points** on the request itself. For a local-LLM rig the mutation points matter more than the lifecycle events.
Claude Code hook list verified at <https://code.claude.com/docs/en/hooks>.

---

## 4. MCP

Docs: <https://opencode.ai/docs/mcp-servers/>.

```json
{
  "mcp": {
    "serena": {
      "type": "local",
      "command": ["uvx","--from","git+https://github.com/oraios/serena","serena","start-mcp-server"],
      "environment": {"PYTHONUNBUFFERED":"1"},
      "cwd": "./",
      "enabled": true,
      "timeout": 15000
    },
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": {"Authorization": "Bearer ..."},
      "oauth": false,
      "enabled": true,
      "timeout": 15000
    }
  }
}
```
- `timeout` defaults to **5000 ms** for tool-list fetch — commonly too short for `uvx`-bootstrapped stdio servers on first run. `experimental.mcp_timeout` sets a global MCP request timeout.
- `cwd` added v1.17.4; workspace-relative.
- **OAuth is automatic**: 401 → discovery → Dynamic Client Registration (RFC 7591); tokens in `~/.local/share/opencode/mcp-auth.json`. `"oauth": false` disables auto-detection for API-key servers. CLI: `opencode mcp auth|logout|debug|add|list`.
- MCP servers receive the workspace as a **client root** (v1.17.6/1.17.7).
- MCP **resources** and **resource templates** are exposed as tools (v1.17.10); MCP server `instructions` are injected into the system prompt inside `<mcp_instructions>` (`session/system.ts`).
- **Code mode** (v1.17.14): an MCP adapter that runs confined orchestration scripts against connected MCP tools; the `execute` tool is hidden unless code mode is enabled. `packages/opencode/src/tool/code-mode.ts`.

**Tool filtering.** Tools are namespaced `<server>_<tool>`. Global: `{"tools":{"serena_*": false}}`. Per-agent: re-enable under `agent.<name>.tools`. Modern equivalent via permissions (glob-matched against the tool name):
```json
{"permission":{"serena_*":"allow","context7_*":"ask"}}
```

**Known limits / open bugs:**
- **#39164** (open, 2026-07-27, CachyOS reporter, opencode 1.18.5): *"MCP tools not sent to local OpenAI-compatible models (empty tools array)"* — opencode sends `tools: []` to `@ai-sdk/openai-compatible` and `@ai-sdk/openai` while the same config works on Anthropic. Logs show `WARN "MCP connection closed"` + `WARN "schema rejection" kind=Payload reason="Expected object, got undefined"`. **This is the single highest-risk open bug for this rig.**
- MCP tool schemas with no declared `properties` used to break OpenAI-compatible providers — fixed v1.17.8.
- Paginated MCP catalogs lost metadata/output schemas — fixed v1.17.14.
- Legacy MCP SDK client compat regressed and was restored in v1.18.9.

---

## 5. LSP

Docs: <https://opencode.ai/docs/lsp/>.

**LSP is DISABLED by default in 1.18.x.** If `lsp` is omitted from config, all servers are off. Enable with `"lsp": true` (all built-ins) or `"lsp": {}` (built-ins on, plus overrides).

30+ built-in servers auto-detected by file extension + requirement: `typescript`, `eslint`, `oxlint`, `pyright`, `gopls`, `rust` (rust-analyzer), `clangd`, `jdtls`, `ruby-lsp`, `bash`, `lua-ls`, `yaml-ls`, `terraform`, `nixd`, `zls`, `deno`, `svelte`, `vue`, `astro`, `php intelephense`, `csharp`, `fsharp`, `razor`, `dart`, `elixir-ls`, `gleam`, `hls`, `julials`, `kotlin-ls`, `ocaml-lsp`, `prisma`, `clojure-lsp`, `sourcekit-lsp`, `tinymist`. Auto-download suppressed by `OPENCODE_DISABLE_LSP_DOWNLOAD=true`. Python TY LSP behind `OPENCODE_EXPERIMENTAL_LSP_TY`.

Per-server entry: `{disabled, command[], extensions[], env{}, initialization{}}`.

**What the model actually sees:**
- **By default: only diagnostics**, fed back into the agent loop as tool-result feedback after edits. No symbol/def tools.
- **`lsp` tool is experimental** — requires `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` (or `OPENCODE_EXPERIMENTAL=true`), gated by `permission.lsp`. Operations: `goToDefinition`, `findReferences`, `hover`, `documentSymbol`, `workspaceSymbol`, `goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls` (`packages/opencode/src/tool/lsp.ts`).
- Server-side: `GET /lsp` (status), `GET /find/symbol?query=` (workspace symbols) — available to the SDK regardless of the model-facing tool.

The docs themselves recommend **against** LSP in many projects: *"Language servers can get out of sync, use significant memory… In many projects it is better to have the agent run lint, typecheck, or other diagnostic CLI tools directly."* On a 64GB box already running a 24GB model, `jdtls`/`rust-analyzer`-class servers are a real RAM cost.

---

## 6. Commands, rules, permissions, `@` refs

**Custom slash commands** — `{command,commands}/**/*.md` in `~/.config/opencode/` and `.opencode/`, or the `command` config key. Frontmatter/keys: `description`, `agent`, `model`, `subtask`, `template`. Body supports `$ARGUMENTS`, `$1`..`$n`, `` !`shell command` `` (output injected), `@path/to/file` (content injected). `subtask: true` forces the command to run as a subagent so it doesn't pollute the primary context — **the cheapest way to get Claude-Code-style "delegate this" behavior**. Custom commands override built-ins (`/init`, `/undo`, `/redo`, `/share`, `/help`, `/models`, `/connect`).

**Instructions files** (`packages/web/src/content/docs/rules.mdx`) — precedence:
1. Local `AGENTS.md`, then `CLAUDE.md`, walking up from cwd (first match per category wins)
2. `~/.config/opencode/AGENTS.md`
3. `~/.claude/CLAUDE.md` (unless `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1`)

Plus `"instructions": [...]` — glob patterns (`packages/*/AGENTS.md`), relative paths, and **remote URLs** (5 s fetch timeout). All are concatenated with `AGENTS.md`. opencode does **not** auto-expand `@file` references inside `AGENTS.md`; you either list them in `instructions` or instruct the model to lazily `read` them.

**Permissions** (<https://opencode.ai/docs/permissions/>) — keys: `read`, `edit` (covers `write`/`edit`/`apply_patch`), `glob`, `grep`, `list`, `bash`, `task`, `skill`, `lsp`, `question`, `webfetch`, `websearch`, `external_directory`, `todowrite`, `doom_loop`. Plus **any tool name as a glob** (`"myserver_*": "deny"`).
Granular object syntax (glob → action) for `read`/`edit`/`glob`/`grep`/`list`/`bash`/`task`/`external_directory`/`lsp`/`skill`; shorthand only for the rest. **Last matching rule wins** — always put `"*"` first.
Defaults: most `allow`; `doom_loop` and `external_directory` are `ask`; `read` allows everything except `*.env` / `*.env.*`. `doom_loop` fires when the *same tool call repeats 3× with identical input* — a genuinely useful guard for small local models that get stuck.
`--auto` / `opencode run --auto` auto-approves anything not explicitly denied. `OPENCODE_PERMISSION` env var takes inline JSON. TUI has a "yolo mode" toggle (v1.17.12).

---

## 7. Server / API / headless — the Orca integration surface

Docs: <https://opencode.ai/docs/server/>, <https://opencode.ai/docs/sdk/>.

`opencode serve [--port 4096] [--hostname 127.0.0.1] [--cors ORIGIN]...`; `OPENCODE_SERVER_PASSWORD` enables HTTP basic auth (user defaults to `opencode`, override with `OPENCODE_SERVER_USERNAME`). OpenAPI 3.1 spec at `GET /doc`. Config equivalent under `"server": {port, hostname, mdns, mdnsDomain, cors[]}`. The TUI is itself a client of this server on a random port.

**Endpoints most relevant to swarm orchestration:**
```
GET    /global/health                       {healthy, version}
GET    /event                               SSE bus (first event: server.connected)
GET    /global/event                        SSE, global
POST   /session                             {parentID?, title?}  -> Session
GET    /session, /session/:id, /session/status
GET    /session/:id/children                child (subagent) sessions
POST   /session/:id/message                 {messageID?, model?, agent?, noReply?, system?, tools?, parts, format?}  (blocks)
POST   /session/:id/prompt_async            same body, 204, no wait
POST   /session/:id/command                 {command, arguments, agent?, model?}
POST   /session/:id/shell                   {agent, model?, command}
POST   /session/:id/fork                    {messageID?}
POST   /session/:id/abort | /revert | /unrevert | /summarize | /init | /share
GET    /session/:id/diff?messageID=         FileDiff[]
POST   /session/:id/permissions/:permID     {response, remember?}   <-- programmatic approvals
GET    /agent                               list agents
GET    /command                             list commands
GET    /mcp   POST /mcp                     status / add MCP server at runtime
GET    /lsp, /formatter
GET    /find?pattern= | /find/file?query= | /find/symbol?query=
GET    /file?path= | /file/content?path= | /file/status
GET    /experimental/tool/ids
GET    /experimental/tool?provider=&model=  full JSON tool schemas for a model
PATCH  /config                              live config update
POST   /tui/*                               drive a running TUI
```

**Key points for Orca:**
- `POST /session/:id/message` accepts a **per-request `system` and `tools`** override, plus `agent` and `model`. You can drive completely different agent shapes over one server without touching config.
- `POST /session/:id/permissions/:permissionID` means a supervisor can approve/deny non-interactively — no need for `--auto`.
- `parentID` on session creation + `GET /session/:id/children` gives you the subagent tree.
- **`opencode run --attach http://localhost:4096`** reuses a warm server, avoiding MCP cold-boot on every invocation. With `uvx`-launched Serena that's tens of seconds saved per run — this is the right pattern for worktree-parallel agents.
- `opencode run --format json` emits raw JSON events for scripting. Also `--agent`, `--model`, `--variant`, `--session`, `--continue`, `--fork`, `--file`, `--title`, `--auto`, `--dir`.
- SDK: `npm i @opencode-ai/sdk`; `createOpencode({hostname,port,config})` spawns server + client, `createOpencodeClient({baseUrl})` attaches to an existing one. Structured output via `format: {type:"json_schema", schema}` (implemented as a `StructuredOutput` tool — needs a model that tool-calls reliably).
- ACP support (`opencode acp`) for Zed-style editor integration; `opencode web` for a browser UI; mDNS discovery for LAN clients.
- Sessions can carry custom metadata via API/SDK (v1.15.13) — useful for tagging Orca worktree IDs.

---

## 8. Context management

- **Compaction config** (schema `$defs.Config.properties.compaction`; only `auto`/`prune`/`reserved` are documented, the other two are schema-only):
  ```json
  {"compaction":{"auto":true,"prune":false,"reserved":10000,"tail_turns":2,"preserve_recent_tokens":24000}}
  ```
  `auto` (default `true`) compacts when the window fills; `prune` (default `false`) drops old tool outputs — `PRUNE_MINIMUM = 20_000`, `PRUNE_PROTECT = 40_000` tokens (`session/compaction.ts:28-29`); `tail_turns` (default 2) keeps the last N user turns verbatim; `reserved` is the headroom left so compaction itself doesn't overflow.
  Kill switch: `OPENCODE_DISABLE_AUTOCOMPACT=1`.
- **Tool-output truncation** (`tool_output`): defaults `max_lines: 2000`, `max_bytes: 51200`; overflow is written to a truncation dir and only a preview is returned. Lower these on a 131k local model.
- **System prompt size** — selected by substring match on `model.api.id` (`session/system.ts:27-42`):
  `muse-spark`→meta · `gpt-4|o1|o3`→beast (11.1 KB) · `codex`→codex (7.4 KB) · `gpt`→gpt (9.3 KB) · `gemini-`→gemini (15.4 KB) · `claude`→anthropic (8.2 KB) · `trinity` · `kimi` · **else → `default.txt` (8.5 KB ≈ ~2.1k tokens)**.
  Your LiteLLM aliases (`coder`, `coder-strong`, `fast`, `utility`) match none of these → you get `default.txt`, the small one. **Good — do not rename an alias to contain `gpt` or `gemini`.**
  On top of that: env block, `<available_skills>` (verbose), `<mcp_instructions>`, `<available_references>`, `AGENTS.md` + all `instructions` files, and ~17–20 tool schemas. Tool schemas dominate: Serena alone adds ~20 tools. Budget realistically **8–15k tokens of fixed prefix** with your current MCP set.
- **Per-turn injections are minimal.** `session/reminders.ts` only injects plan-mode / build-switch text; there is no Claude-Code-style `<system-reminder>` on every user turn. v1.17.9 explicitly *"stopped wrapping follow-up user messages in a steering reminder so prompt caching stays effective."* This is good news for llama.cpp prefix caching.
- **Prompt caching with OpenAI-compatible providers** (`provider/transform.ts:1254-1268`): opencode only emits a cache key when the SDK is `@ai-sdk/deepinfra`/`@ai-sdk/cerebras` (`prompt_cache_key`), or `openai`/`azure`/`xai`/`mistral`/`venice` (`promptCacheKey`), **or** when you set `provider.options.setCacheKey: true`. For `@ai-sdk/openai-compatible` it is **off by default**. llama.cpp doesn't consume `prompt_cache_key` anyway — its prefix cache is content-addressed — so the real lever is *prefix stability*, not this flag.
- ⚠️ **Open issue #37489** (2026-07-17): context cache invalidation on local backends. Reported causes: (a) switching Plan↔Build changes the **tool list**, which is part of the request prefix → full reprocess; (b) mid-history message mutation; (c) compaction discards the prefix. On a 3090 Ti reprocessing 60k tokens is a 30–60 s stall. **Practical mitigation: pick one agent per session and stay in it.**
- Session snapshots (git-backed) power `/undo` + `POST /session/:id/revert`; `"snapshot": false` disables them if indexing is slow.

---

## 9. Local / OpenAI-compatible provider problems (the important section)

### Provider config shape
`@ai-sdk/openai-compatible` targets `/v1/chat/completions`; use `@ai-sdk/openai` only if a model needs `/v1/responses`. Per-model override via `models.<id>.provider.npm`. opencode force-sets `includeUsage: true` for openai-compatible (`provider/provider.ts:1689`).

### 🐞 Bug in your current `opencode.json`
The model object's schema is **`additionalProperties: false`** (verified against <https://opencode.ai/config.json>, `$defs.ProviderConfig.properties.models.additionalProperties`). Valid model keys are:
`id, name, family, release_date, attachment, reasoning, temperature, tool_call, interleaved, cost, limit, modalities, experimental, status, provider, options, headers, variants`.

**There is no `tools` key.** Your config has `"tools": true` on `coder`, `coder-strong`, `fast` and `"tools": false` on `utility`. The correct key is **`tool_call`**. Note `toolcall` defaults to `model.tool_call ?? true` (`provider.ts:1229`), so tool calling still works by accident — but `"tools": false` on `utility` is **not** disabling tool calls as you intended, and the whole config fails `$schema` validation.

Also relevant: `models.<key>.id` sets the **wire** model id sent to LiteLLM; the map key is the opencode-side id (`provider.ts:1433`). So you can rename the opencode-side key without changing LiteLLM.

### Sampling defaults never fire for your aliases
`provider/transform.ts:525-553`: `temperature()` returns `0.55` and `topP()` returns `1` **only when `model.api.id` contains `"qwen"`**. Your wire ids are `coder`/`coder-strong` → no match → opencode sends no temperature and no top_p unless you set them.

Your `agent.build.temperature = 0.1` and `agent.plan.temperature = 0.1` are **well below** what opencode itself considers correct for Qwen (0.55). Qwen3-family MoE models at temp ≤0.2 are prone to repetition loops and degenerate tool-arg emission. Raise to ~0.5–0.7 with `top_p ~0.8–1.0`.

⚠️ **Open issue #34405** (2026-06-29, open, opencode 1.17.11): *"Agent temperature parameter is not passed to LLM API requests"* — reported specifically for a custom `@ai-sdk/openai-compatible` provider; the request body showed `top_p` but no `temperature`. **Verify with a LiteLLM request log before trusting `agent.*.temperature`.** The reliable workaround is a `chat.params` plugin hook, which sets the values after all config resolution.

### Reasoning / thinking field handling
`@ai-sdk/openai-compatible` reads **`delta.content` only**. Backends that stream thinking in `delta.reasoning` or `delta.reasoning_content` get silently dropped → **infinite silent spinner**, no text ever rendered (issue #24316 comment by `fenrir-labs76`, 2026-06-29, reproduced on qwen3.6-35b @128k).

opencode's answer is the model-level `interleaved` capability (`transform.ts:319-352`):
```json
{"models":{"coder":{"interleaved":{"field":"reasoning_content"}}}}
```
Allowed values: `"reasoning"`, `"reasoning_content"`, `"reasoning_details"`. It strips reasoning parts out of `content` and replays them on the message under `providerOptions.openaiCompatible[field]`. **Auto-detection only fires for model ids containing `deepseek`** (`provider.ts:1478-1482`) — for `coder`/`coder-strong` you must set it explicitly. `"reasoning"` as a field option was added in **v1.17.0** for vLLM. Cerebras reasoning replay fixed v1.17.14; Mistral reasoning history v1.18.5.

### Naked `<tool_call>` XML — issue #24316, still OPEN, exactly your model
*"Progress halts with qwen 3.6 35b-a3b with naked tool call in the console"* (opened 2026-04-25, **last updated 2026-07-24**, 19 comments). The model emits raw
```
<tool_call><function=read><parameter=filePath>…</parameter></function></tool_call>
```
inside the *thinking* channel; opencode renders it as text and the session stalls. Duplicates: #9674, #8877, #16488. Reported against llama.cpp **and** vLLM **and** Ollama, on Qwen3.6-35B-A3B, Qwen3.6-27B, Qwen3.5. Regression window pointed at v1.14.23 (v1.14.21 was clean). Community fixes:
- PR <https://github.com/anomalyco/opencode/pull/27984> (`fix/strip-dangling-xml-tags`, opened 2026-05-17, confirmed working by one user, **not merged as of 1.18.10**) strips trailing XML artifacts from streaming text deltas.
- Chat-template patch (llama.cpp, from commenter `hviden`) that moves a `<tool_call>` found inside `reasoning_content` out into `content`:
  ```jinja
  {%- if '<tool_call>' in reasoning_content %}
      {%- set parts = reasoning_content.split('<tool_call>', 1) %}
      {%- set reasoning_content = parts[0] | trim %}
      {%- set content = '<tool_call>' + parts[1] + (content if content else '') %}
  {%- endif %}
  ```
  (mirrors ollama/ollama#15022). Related upstream: <https://github.com/ggml-org/llama.cpp/issues/20837>.
- You can also mitigate in-process with an `experimental.text.complete` plugin hook that strips dangling XML from completed text parts.

### Other verified local-backend issues
| # | Title | State | Relevance |
|---|---|---|---|
| **39164** | MCP tools not sent to local OpenAI-compatible models (empty `tools` array), 1.18.5 | **open** | CachyOS + Ollama proxy; blocks all MCP on local models |
| **39303** | Custom `@ai-sdk/openai-compatible` models fail in **sub-agent** context — bare `Error`, no trace. Reporter's model: `Qwen3.6-35B-A3B-MTP-GGUF` | **open** (2026-07-28) | directly blocks swarms on this rig |
| **39086** | `task` tool missing despite `permission.task` allow | **open** | blocks orchestrator agents |
| **34405** | Agent `temperature` not passed to API | **open** | see above |
| **37489** | Context cache invalidation on mode switch / compaction | **open** | 30–60 s stalls locally |
| **37852** | Aborted provider stream recorded as clean stop → **subagent returns empty** | **open** | silent swarm failures |
| **39357** | Hangs indefinitely with Ollama behind a reverse proxy (SSE not delivered) | **open** | check LiteLLM/Caddy buffering |
| **38801** | `message="exiting loop"` | **open** (updated 2026-07-30) | |
| **6231** | Auto-discover models from OpenAI-compatible `/v1/models` | **open** feature req | would remove manual model lists |
| 20669 | Default agent brittle vs local tool-call quirks: `bash` fails on missing `description`; `finish_reason:"tool_calls"` with `tool_calls: []` hangs | **closed** 2026-07-03 | fixed |
| 20719 | Agent loop stops after 1 LLM call with LiteLLM→Ollama (`finish_reason: stop`) | **closed** 2026-07-04 | fixed |
| 25487 | `"text part <uuid> not found"` on 2nd round-trip via LiteLLM | **closed** 2026-07-11 | fixed |

Also fixed recently and worth knowing: OpenAI-compatible providers now accept MCP tool schemas that previously failed validation (v1.17.8); `reasoning` forced on for OpenAI-compatible reasoning models so reasoning settings apply on custom deployments (v1.17.13).

**Streaming safety net:** `provider.options.chunkTimeout` aborts a request if no SSE chunk arrives within N ms — the right guard against the #39357-class silent hang. `headerTimeout` and `timeout` (default 300000 ms) are separate.

---

## 10. Release timeline (last ~6 months) — what actually changed

| Version | Date | Highlights |
|---|---|---|
| 1.15.12–13 | 2026-05-28/30 | `acp-next`; OpenAI WebSocket transport (experimental); session metadata via API/SDK; config loads from opened location upward |
| **1.16.0** | 2026-06-05 | **Skill discovery + file-based agent loading**; managed workspace cloning; move sessions between workspaces; `run --replay` |
| 1.16.2 | 2026-06-05 | **Running subagents can be sent to the background**; edit refuses loose matches; Snowflake Cortex |
| **1.17.0** | 2026-06-10 | `fff`-backed fast file search; **`reasoning` as interleaved field for vLLM**; `X-Session-Id` header; MCP abort signals; MCP catalog pagination |
| 1.17.4–7 | 2026-06-12/14 | MCP `cwd`; v2 session API endpoints; MCP client roots; plugin client reuses active server |
| 1.17.8–9 | 2026-06-17/21 | **OpenAI-compatible accepts previously-rejected MCP tool schemas**; **stopped steering-reminder wrapping to preserve prompt caching**; agent `steps` limit honored |
| 1.17.10–12 | 2026-06-24/30 | MCP resources + resource templates as tools; MCP server instructions in context; `--mini` CLI mode; **TUI yolo mode**; skill resource paths as fs paths; **session snapshots + revert** (1.17.11) |
| 1.17.13–14 | 2026-07-01/06 | **Force reasoning mode for OpenAI-compatible reasoning models**; **code-mode MCP adapter**; `execute` hidden unless code mode |
| 1.17.15–20 | 2026-07-07/13 | Z.ai context-overflow classification; graceful handling of unavailable config dirs; Copilot routing fixes |
| **1.18.0–1** | 2026-07-14 | Desktop v2 migration complete |
| **1.18.2** | 2026-07-15 | **Subagents no longer launch nested subagents by default; `subagent_depth` introduced** |
| 1.18.3 | 2026-07-16 | Subagent picker UX |
| 1.18.4–5 | 2026-07-20/24 | Reasoning-option correctness; Mistral reasoning history + prompt caching; correct prompt cache keys per SDK |
| 1.18.6–9 | 2026-07-27/28 | MCP OAuth + newer-MCP-server compat; **restored compatibility with legacy MCP SDK clients**; reconnect MCP after expired SDK sessions |
| **1.18.10** | 2026-07-30 | Modal model discovery; desktop fixes |

---

## Working config for `https://llm.tabaska.us/v1`

This is a corrected, expanded replacement for the repo-root `opencode.json`. Changes vs current: `tools`→`tool_call`, `interleaved` added, sampling raised off 0.1, `subagent_depth: 2`, `chunkTimeout`, MCP `timeout` raised, dead `"skills*"` line removed, compaction/tool-output tuned for a 131k local window.

```jsonc
{
  "$schema": "https://opencode.ai/config.json",

  "provider": {
    "litellm": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Homelab AI (LiteLLM on rig)",
      "options": {
        "baseURL": "https://llm.tabaska.us/v1",
        "apiKey": "{env:LITELLM_API_KEY}",
        "timeout": 900000,       // 15 min; big prompts on a 3090 Ti are slow
        "headerTimeout": 120000, // llama-swap model swap can take a while
        "chunkTimeout": 180000   // abort silent SSE hangs (cf. issue #39357)
      },
      "models": {
        "coder": {
          "name": "coder — Qwen3.6 35B-A3B MoE (default, 131k)",
          "tool_call": true,                          // NOT "tools"
          "reasoning": true,
          "temperature": true,
          "interleaved": { "field": "reasoning_content" }, // llama.cpp --reasoning-format deepseek
          "limit": { "context": 131072, "output": 8192 },
          "options": { "parallel_tool_calls": true }
        },
        "coder-strong": {
          "name": "coder-strong — Qwen3.6 27B MTP (~50 t/s, 98k)",
          "tool_call": true,
          "reasoning": true,
          "temperature": true,
          "interleaved": { "field": "reasoning_content" },
          "limit": { "context": 98304, "output": 8192 }
        },
        "fast": {
          "name": "fast — Qwen2.5-Coder 7B",
          "tool_call": true,
          "temperature": true,
          "limit": { "context": 32768, "output": 4096 }
        },
        "utility": {
          "name": "utility — Llama3.2 3B (titles/tags)",
          "tool_call": false,
          "temperature": true,
          "limit": { "context": 8192, "output": 1024 }
        }
      }
    }
  },

  "model": "litellm/coder",
  "small_model": "litellm/utility",
  "default_agent": "build",

  "instructions": ["~/.config/opencode/AGENTS.md"],

  "subagent_depth": 2,

  "compaction": { "auto": true, "prune": true, "reserved": 16000, "tail_turns": 2 },
  "tool_output": { "max_lines": 600, "max_bytes": 24000 },

  "lsp": false,          // start off; see §5 — enable per-project if you want diagnostics
  "snapshot": true,
  "autoupdate": "notify",

  "agent": {
    "build": {
      "mode": "primary",
      "model": "litellm/coder",
      "temperature": 0.6,   // opencode's own Qwen default is 0.55; 0.1 causes loops
      "top_p": 0.95,
      "permission": {
        "edit": "allow",
        "webfetch": "allow",
        "external_directory": "allow",
        "task": { "*": "deny", "explore": "allow", "reviewer": "allow", "tester": "allow" },
        "bash": { "*": "allow", "git push*": "ask", "rm -rf*": "ask", "sudo*": "ask" }
      }
    },
    "plan": {
      "mode": "primary",
      "model": "litellm/coder-strong",
      "temperature": 0.5,
      "top_p": 0.95,
      "permission": { "edit": "deny", "bash": "deny" }
    }
  },

  "mcp": {
    "context7": { "type": "remote", "enabled": true, "url": "https://mcp.context7.com/mcp", "timeout": 20000 },
    "serena": {
      "type": "local",
      "enabled": true,
      "command": ["uvx","--from","git+https://github.com/oraios/serena","serena",
                  "start-mcp-server","--context","ide-assistant","--project","{cwd}"],
      "environment": { "PYTHONUNBUFFERED": "1" },
      "timeout": 30000
    }
  },

  "permission": { "edit": "ask", "bash": "ask", "doom_loop": "ask" },

  "experimental": { "mcp_timeout": 30000 }
}
```

### Markdown subagents — `.opencode/agents/reviewer.md`
```markdown
---
description: Reviews a diff for correctness and security. Read-only. Use proactively after edits.
mode: subagent
model: litellm/coder-strong
temperature: 0.4
top_p: 0.95
steps: 25
color: accent
permission:
  edit: deny
  webfetch: deny
  task: deny
  bash:
    "*": deny
    "git diff*": allow
    "git log*": allow
    "git show*": allow
---
Review only the changes in the current diff. Report findings as a numbered list with
file:line references. Do not modify files. End with a one-line APPROVE / REQUEST-CHANGES verdict.
```
Save under `.opencode/agents/` (project) or `~/.config/opencode/agents/` (global). Nested dirs work.

### Plugin — the highest-leverage file on this rig: `.opencode/plugins/local-llm.ts`
```ts
import type { Plugin } from "@opencode-ai/plugin"

// Strips the dangling XML that Qwen3.6 leaks into text on llama.cpp/vLLM (issue #24316)
const XML_LEAK = /<\/?(?:tool_call|function|parameter)(?:=[^>]*)?>/g

export const LocalLLM: Plugin = async ({ client }) => ({
  // Guarantees sampling reaches LiteLLM even if agent.temperature is dropped (issue #34405)
  "chat.params": async (input, output) => {
    if (input.provider.info.id !== "litellm") return
    if (output.temperature == null || output.temperature < 0.4) output.temperature = 0.6
    output.topP = 0.95
    output.topK = 20
  },

  // Optional: tag requests so LiteLLM can log/route per agent
  "chat.headers": async (input, output) => {
    output.headers["X-OC-Agent"] = input.agent
    output.headers["X-OC-Session"] = input.sessionID
  },

  // Trim the fixed prefix — every token here is reprocessed on every cache miss
  "experimental.chat.system.transform": async (_input, output) => {
    output.system = output.system.filter((s) => !s.includes("<available_references>"))
  },

  // Shrink verbose tool descriptions (biggest single prefix win with Serena connected)
  "tool.definition": async (input, output) => {
    if (input.toolID.startsWith("serena_") && output.description.length > 400)
      output.description = output.description.slice(0, 400)
  },

  // Clean up leaked XML before it reaches the TUI / next turn
  "experimental.text.complete": async (_input, output) => {
    if (XML_LEAK.test(output.text)) output.text = output.text.replace(XML_LEAK, "").trimEnd()
  },

  // Keep task state alive across compaction on a 131k window
  "experimental.session.compacting": async (_input, output) => {
    output.context.push(
      "## Carry forward\n- The exact task and its current status\n- Files modified so far\n- Commands that verify the work\n- Remaining steps",
    )
  },

  // Desktop-free completion signal
  event: async ({ event }) => {
    if (event.type === "session.idle") await client.app.log({ body: { service: "local-llm", level: "info", message: "session idle" } })
  },
})
```

### Headless swarm driver (Orca)
```bash
# One warm server per worktree — avoids Serena/uvx cold boot on every task
OPENCODE_SERVER_PASSWORD=$OC_PW \
OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true \
  opencode serve --port 4096 --hostname 127.0.0.1 &

opencode run --attach http://localhost:4096 -p "$OC_PW" \
  --agent build --model litellm/coder --format json --auto \
  --dir /path/to/worktree "Implement X. Verify with: bun test"
```
```ts
import { createOpencodeClient } from "@opencode-ai/sdk"
const client = createOpencodeClient({ baseUrl: "http://localhost:4096" })
const s = await client.session.create({ body: { title: "orca-task-42" } })
await client.session.promptAsync({ path: { id: s.id }, body: {
  agent: "build", model: "litellm/coder",
  parts: [{ type: "text", text: "…" }],
}})
// subscribe to GET /event (SSE) for permission.asked / session.idle
// approve via POST /session/:id/permissions/:permissionID  {response:"always"}
// inspect subagent tree via GET /session/:id/children
```

---

## Gaps: what opencode cannot do that Claude Code can

1. **No agent teams / named inter-agent messaging.** Subagents are strictly one-shot request→response children (resumable by `task_id`, but no peer messaging, no `SendMessage`). Tracked as a **design issue only**: #12711 *"Agent Teams — flat teams with named messaging, multi-model support, and TUI integration"* (open, updated 2026-07-29). Closest workaround: `opencode-workspace` / `oh-my-opencode` Team Mode.
2. **Nested subagents off by default** and capped by an integer, not a per-agent policy.
3. **Background subagents are experimental** and env-gated.
4. **No `SubagentStart`/`SubagentStop`/`PostToolBatch`/`Notification`-inbound hooks**; you reconstruct these from the SSE bus.
5. **No `.claude/agents/` compatibility** — only `CLAUDE.md` and `.claude/skills/`.
6. **Skill frontmatter is narrower** — no `allowed-tools`, no `disable-model-invocation`.
7. **LSP is not exposed to the model** without an experimental flag; even then, no rename/refactor.
8. **No hook-based deterministic gating on prompt submit** with a blocking decision (Claude Code's `UserPromptSubmit` can reject); `chat.message` mutates but doesn't block.
9. **No built-in worktree management** (Claude Code has `WorktreeCreate/Remove`); use `opencode-worktree` or Orca.
10. **`websearch` requires Exa** (`OPENCODE_ENABLE_EXA=1`) or the OpenCode provider — no offline/self-hosted search path.

### Community plugins that close gaps (from <https://opencode.ai/docs/ecosystem/>)
| Gap | Plugin |
|---|---|
| Claude Code parity, background agents, LSP/AST tools, team mode | [`oh-my-opencode`](https://github.com/code-yeongyu/oh-my-opencode) — claims *"Every hook, command, skill, MCP, plugin works here unchanged"*; 25-language LSP/AST refactor tools; v4.0 Team Mode with tmux |
| Background/async delegation | [`opencode-background-agents`](https://github.com/kdcokenny/opencode-background-agents) |
| Multi-agent orchestration bundle (16 components) | [`opencode-workspace`](https://github.com/kdcokenny/opencode-workspace) |
| Command→orchestration flow control | [`@openspoon/subtask2`](https://github.com/spoons-and-mirrors/subtask2) |
| Git worktrees | [`opencode-worktree`](https://github.com/kdcokenny/opencode-worktree) |
| **Token/context pruning** | [`opencode-dynamic-context-pruning`](https://github.com/Tarquinen/opencode-dynamic-context-pruning) — prunes obsolete tool outputs |
| Skill lazy-loading/discovery | [`opencode-skillful`](https://github.com/zenobi-us/opencode-skillful) |
| Non-interactive shell safety (prevents TTY hangs) | [`opencode-shell-strategy`](https://github.com/JRedeker/opencode-shell-strategy) |
| Background PTY processes | [`opencode-pty`](https://github.com/shekohex/opencode-pty) |
| Notifications | `opencode-notificator`, `opencode-notifier`, `opencode-notify` |
| Persistent cross-session memory | [`opencode-supermemory`](https://github.com/supermemoryai/opencode-supermemory) |
| Profile/extension management | [`ocx`](https://github.com/kdcokenny/ocx) |
Also: [`awesome-opencode`](https://github.com/awesome-opencode/awesome-opencode), <https://opencode.cafe>.

---

## Recommended actions for this rig

**Tier 1 — config correctness (do first, ~20 min)**
1. `models.*.tools` → **`tool_call`**. Current config fails `$schema` validation and `"tools": false` on `utility` is silently ignored.
2. Delete `"tools": {"skills*": true}` — the tool is `skill`, the glob matches nothing, and skills are on by default.
3. Raise `temperature` from 0.1 → ~0.6 with `top_p 0.95`. opencode's own Qwen default is 0.55/1.0 and never fires for aliases named `coder*`.
4. Add `"interleaved": {"field":"reasoning_content"}` to `coder`/`coder-strong` if llama-server runs with `--reasoning-format deepseek`; use `"reasoning"` if the field is `delta.reasoning`. Without this, thinking tokens are dropped and you get silent spinners (#24316).
5. Add `chunkTimeout` / `headerTimeout` / a long `timeout` — llama-swap model swaps routinely exceed the 300 s default and produce indistinguishable hangs.
6. Raise MCP `timeout` from the 5 s default to 20–30 s for the `uvx`-bootstrapped Serena server.

**Tier 2 — the plugin (highest leverage, ~1 h)**
7. Write `.opencode/plugins/local-llm.ts` with `chat.params` (guarantees sampling despite #34405), `experimental.text.complete` (strips leaked `<tool_call>` XML — #24316 is still open and PR #27984 is unmerged), `tool.definition` (trims Serena's descriptions), and `experimental.chat.system.transform` (trims the prefix). These four hooks address four separate open bugs/costs at once.

**Tier 3 — swarm architecture**
8. Set `subagent_depth: 2` and define 3–4 narrow markdown subagents (`explore` is built-in; add `reviewer`, `tester`) with `permission.task` allowlists on `build`. Do **not** chase wide parallelism — one GPU, one resident model, `llama-swap` `big` group is exclusive, so N concurrent subagents serialize and each one costs a fresh prefill.
9. Drive Orca through **`opencode serve` + `opencode run --attach`**, one warm server per worktree. Approve permissions via `POST /session/:id/permissions/:permissionID` instead of `--auto`. Watch `GET /event` for `session.idle`.
10. Set `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true` only if you actually want async delegation; otherwise leave it off — background subagents on a single-GPU rig mostly queue.

**Tier 4 — context economics**
11. Keep `lsp: false` (opencode's own docs recommend CLI lint/typecheck over LSP; `jdtls`/`rust-analyzer` cost RAM you don't have spare).
12. Turn on `compaction.prune: true` and lower `tool_output.max_lines` to ~600 — tool output is the fastest way to burn 131k.
13. Stay in **one agent per session**. Switching Plan↔Build changes the tool list, which changes the request prefix, which invalidates llama.cpp's prefix cache and forces a full reprocess (#37489).
14. Do not rename LiteLLM aliases to contain `gpt`, `gemini`, `claude`, `kimi`, or `trinity` — that silently swaps in a larger, wrong system prompt (`session/system.ts:27-42`).

**Tier 5 — verify before depending on**
15. Confirm the `task` tool actually appears in the model's tool list (#39086) and that subagents with your custom provider don't return bare errors (#39303).
16. Confirm MCP tools are actually being sent (#39164 — reported on CachyOS + a local OpenAI-compatible proxy, i.e. your exact stack). Check LiteLLM's request log for a non-empty `tools` array.
17. Trial `oh-my-opencode` if you want Claude-Code-shaped teams/hooks/LSP-AST tooling without writing it yourself — but audit it, it is a large surface.
