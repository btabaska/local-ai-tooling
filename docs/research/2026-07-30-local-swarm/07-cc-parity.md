# 07 — The Claude Code Parity Map

**Research date:** 2026-07-30
**Target environment:** opencode + pi against LiteLLM (`https://llm.tabaska.us/v1`), models `coder` (Qwen3.6 35B-A3B MoE, 131k ctx), `coder-strong` (Qwen3.6 27B MTP, 98k), `fast` (Qwen2.5-Coder 7B), single RTX 3090 Ti 24GB.
**Claude Code version referenced:** v2.1.x (docs cite version gates up to **v2.1.219**). Docs moved host: `docs.claude.com/en/docs/claude-code/*` now **301-redirects to `code.claude.com/docs/en/*`** (verified 2026-07-30).
**pi version referenced:** 0.82.x per user config; docs at <https://pi.dev/docs/latest>; source `github.com/badlogic/pi-mono`, published as `@earendil-works/pi-coding-agent`.

Confidence tags used throughout: **[H]** = directly sourced from official docs today; **[M]** = sourced but inferred/partially verified; **[L]/unverified** = not verified against a live source.

---

## 0. Executive framing

Three things dominate everything below:

1. **The user's existing `agentic/opencode/` files are already in opencode format, not Claude Code format.** `agents/*.md` use `mode: subagent` + `permission:` (opencode), `commands/*.md` use `agent:` + `subtask:` (opencode). Only `skills/*/SKILL.md` are in the portable **Agent Skills** format. So the porting job is *opencode → pi*, plus a *forward-compat* pass, not *CC → opencode*. (Verified by reading the files.) **[H]**
2. **Skills are already a solved, cross-vendor problem.** SKILL.md is now an open standard (<https://agentskills.io/specification>) implemented by Claude Code, opencode, pi, Codex, Gemini CLI, Cursor, Amp, Goose, OpenHands and ~40 others. **[H]**
3. **Hooks are the un-solved problem, and hooks are exactly what a 30B model needs most.** Claude Code has ~30 hook events with a deterministic JSON contract; pi has a TypeScript event bus that can do the same things but with a totally different shape; opencode has a JS/TS plugin API. Nothing speaks the CC hook JSON contract natively. This is the highest-value gap to close.

---

## 1. Claude Code's 2026 feature surface (mechanism-level)

### 1.1 Subagents — `.claude/agents/*.md` + the `Agent` tool
Source: <https://code.claude.com/docs/en/sub-agents> **[H]**

Scope/precedence (highest → lowest): managed settings → `--agents` CLI JSON → `.claude/agents/` → `~/.claude/agents/` → plugin `agents/`. Project dirs are discovered by walking **up** from cwd to repo root; scanned **recursively** (subfolders don't affect identity — identity comes only from the `name` field). Plugin subfolders *do* namespace: `agents/review/security.md` in `my-plugin` → `my-plugin:review:security`.

Frontmatter (only `name` + `description` required):

| Field | Meaning |
|---|---|
| `name` | lowercase-hyphen id; hooks receive it as `agent_type`; may not contain `:` (v2.1.218+) |
| `description` | **when Claude should delegate** — this is the routing signal |
| `tools` | allowlist; inherits all subagent-available tools if omitted |
| `disallowedTools` | denylist subtracted from the inherited/allowed set |
| `model` | `sonnet`/`opus`/`haiku`/`fable`/full id/`inherit` (default `inherit`) |
| `permissionMode` | `default`(`manual`)/`acceptEdits`/`auto`/`dontAsk`/`bypassPermissions`/`plan` |
| `maxTurns` | hard turn cap |
| `skills` | **preload full skill content** into the subagent at startup (not just descriptions) |
| `mcpServers` | per-subagent MCP servers (name ref or inline config) |
| `hooks` | lifecycle hooks scoped to this subagent |
| `memory` | `user`/`project`/`local` — subagent keeps its own auto-memory dir |
| `background` | force background execution (background is the **default** as of v2.1.198) |
| `effort` | `low`…`max` |
| `isolation` | `worktree` → temp git worktree, auto-cleaned if no changes |
| `color`, `initialPrompt` | display + auto-first-turn |

Mechanics that matter:
- Subagent gets **only its own system prompt + basic env**, *not* CC's full system prompt. Main auto-memory is **not** inherited.
- Tool filtering: `AskUserQuestion`, `EnterPlanMode`, `EndConversation`, `ScheduleWakeup`, and `ExitPlanMode` (unless `permissionMode: plan`) are stripped from every subagent; background subagents get a further-reduced built-in tool set.
- **Fork** (`context: fork`) is a distinct mode: inherits the parent conversation *and* system prompt, skips those filters.
- Delegation is *automatic* off the `description` text, or explicit via @-mention/`Agent` tool. Subagents can spawn subagents up to a depth limit; there are session and concurrency limits.
- Model resolution order: `CLAUDE_CODE_SUBAGENT_MODEL` env → per-invocation `model` param → frontmatter → main model.

### 1.2 Skills — `SKILL.md`
Sources: <https://code.claude.com/docs/en/skills>, <https://agentskills.io/specification> **[H]**

**Custom commands have been merged into skills** (2026). `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both produce `/deploy` and behave the same; `commands/` still works and supports the same frontmatter.

Locations: enterprise (managed) → `~/.claude/skills/<name>/SKILL.md` → `.claude/skills/<name>/SKILL.md` → `<plugin>/skills/<name>/SKILL.md` (namespaced `plugin:skill`). Nested `.claude/skills/` below cwd load lazily when Claude touches a file in that subtree and get a directory-qualified name (`apps/web:deploy`). Symlinked skill dirs are followed. `--add-dir` dirs *do* load skills (the one config exception).

Progressive disclosure: **descriptions only** at startup (combined `description` + `when_to_use` truncated at **1,536 chars**); the full body loads on invoke. Once loaded, the rendered content **stays in context for the rest of the session** (re-invoking identical content just adds a "already loaded" note as of v2.1.202). Auto-compaction re-attaches the most recent invocation of each skill, first **5,000 tokens** each, **25,000-token** combined budget.

CC frontmatter (superset of the open spec): `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context: fork`, `agent`, `background`, `hooks`, `paths`, `shell`.

Open-standard subset (what is portable): `name` (≤64, `[a-z0-9-]`, must match dir name, no leading/trailing/double hyphen), `description` (≤1024, required), `license`, `compatibility` (≤500), `metadata` (string map), `allowed-tools` (space-separated, experimental). Layout: `scripts/`, `references/`, `assets/`. Recommended: SKILL.md < 500 lines / < 5000 tokens.

Substitutions inside skill bodies: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$name` (from `arguments:`), `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}`. Dynamic context injection: `` !`command` `` runs **before** the skill text reaches the model and the output is substituted in. `${CLAUDE_SKILL_DIR}` is also substituted inside `allowed-tools` Bash rules so a bundled script runs prompt-free.

### 1.3 Hooks
Source: <https://code.claude.com/docs/en/hooks> **[H]**

~30 events. Config shape:

```json
{ "hooks": { "EVENT": [ { "matcher": "pattern",
  "hooks": [ { "type": "command|http|mcp_tool|prompt|agent",
               "command": "...", "args": [], "if": "Bash(git *)",
               "timeout": 600, "async": false, "asyncRewake": false,
               "statusMessage": "...", "once": false } ] } ] } }
```

Common input to every event: `session_id`, `prompt_id`, `transcript_path`, `cwd`, `permission_mode`, `effort.level`, `hook_event_name`, and in subagents `agent_id`/`agent_type`.

Common output envelope:

```json
{ "continue": true, "stopReason": "...", "suppressOutput": false,
  "systemMessage": "...", "decision": "block", "reason": "...",
  "hookSpecificOutput": { "hookEventName": "...", "additionalContext": "...",
    "permissionDecision": "allow|deny|ask|defer", "permissionDecisionReason": "...",
    "updatedInput": {}, "updatedToolOutput": "...", "displayContent": "...", "retry": true } }
```

Exit codes: **0** = success (stdout parsed as JSON if present); **2** = blocking error, stderr becomes the feedback message, stdout/JSON ignored; **other** = non-blocking error, first stderr line shown.

The blocking events (this is the load-bearing set):

| Event | Blocking | What it can do |
|---|---|---|
| `PreToolUse` | Yes | `permissionDecision: allow/deny/ask/defer`, `updatedInput`, `additionalContext` |
| `PermissionRequest` | Yes | full allow/deny decision + rule mutation |
| `UserPromptSubmit` | Yes | block prompt, inject `additionalContext` |
| `UserPromptExpansion` | Yes | block command expansion |
| `PostToolUse` / `PostToolUseFailure` | No (exit 2 shows stderr to Claude) | `updatedToolOutput`, `additionalContext` |
| `PostToolBatch` | Yes | sees the whole parallel batch before the next model call |
| `Stop` | **Yes** | `decision: block` prevents the model from stopping and feeds `reason`/`additionalContext` back |
| `SubagentStop` | Yes | same, per subagent |
| `TaskCreated` / `TaskCompleted` | Yes | veto task creation/completion |
| `PreCompact` | Yes | veto compaction |
| `ConfigChange`, `TeammateIdle`, `Elicitation*`, `WorktreeCreate` | Yes | misc |
| `SessionStart`/`Setup` | No | inject `additionalContext`, `initialUserMessage`, `watchPaths`, `sessionTitle` |
| `SessionEnd`, `Notification`, `MessageDisplay`, `PostCompact`, `SubagentStart`, `InstructionsLoaded`, `CwdChanged`, `FileChanged`, `StopFailure`, `WorktreeRemove` | No | observation/logging/display |

Matchers: `*`/empty = all; strings of `[A-Za-z0-9_,-|]` = exact or `|`/`,` list; anything else = unanchored JS regex. MCP tools match `mcp__<server>__<tool>`.
Placeholders: `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`.
Hooks merge (don't replace) across settings layers; `disableAllHooks: true` kills all but managed. Hooks can also be declared in **skill and subagent frontmatter** (`hooks:`), scoped to that component's lifetime.

> ⚠️ Correction note: a summarizer pass over `/docs/en/settings` produced a "hooks" section listing `BeforeCommand`/`AfterToolUse`/`when`/`execute`. That shape does **not** appear in the hooks reference and should be treated as a hallucination. The `/docs/en/hooks` contract above is authoritative.

### 1.4 Slash commands
Sources: <https://code.claude.com/docs/en/skills>, `/docs/en/commands` **[H]**
Merged into skills (see 1.2). Name resolution: `.claude/skills/<dir>/SKILL.md` → `/<dir>`; `.claude/commands/<file>.md` → `/<file>`; plugin skill → `/plugin:skill`. Skill stacking: `/write-tests /fix-issue 123` loads both and passes `123` to each (v2.1.199+), up to 6 skills, stopping at the first forked/non-inline skill.

### 1.5 Plugins & marketplaces
Source: <https://code.claude.com/docs/en/plugins-reference> **[H]**
A plugin is a directory with `.claude-plugin/plugin.json`. Components: `skills/` (or `commands/`, or a root `SKILL.md`), `agents/`, `hooks/hooks.json`, `.mcp.json`, `output-styles/`, plus LSP servers and monitors. Distribution via marketplaces (`.claude-plugin/marketplace.json`), install with `--plugin-dir`/`--plugin-url` or the marketplace CLI. Settings gates: `strictKnownMarketplaces`, `blockedMarketplaces`, `allowedChannelPlugins`. **A skill folder containing `.claude-plugin/plugin.json` auto-loads as a plugin named `<name>@skills-dir`**, which is how a single skill dir can also ship agents/hooks/MCP.
Security: plugin subagents ignore `hooks`, `mcpServers`, `permissionMode`.

### 1.6 MCP
Source: <https://code.claude.com/docs/en/mcp> **[H]**
Transports: stdio (local command), SSE, HTTP. Scopes: user (`~/.claude.json`), project (`.mcp.json`, committed), local. Per-project gating: `enableAllProjectMcpServers`, `enabledMcpjsonServers`, `disabledMcpjsonServers`. Tools appear as `mcp__<server>__<tool>`. MCP **resources** are @-mentionable; MCP **prompts** surface as slash commands. Tool schemas are **deferred by default** in 2026 — only names load; `ToolSearch` fetches schemas on demand. `ENABLE_TOOL_SEARCH=auto|false` controls it. MCP servers can also act as *channels* pushing messages into a session.

### 1.7 Memory hierarchy
Source: <https://code.claude.com/docs/en/memory> **[H]**
Load order (broad → specific): managed policy CLAUDE.md (`/Library/Application Support/ClaudeCode/CLAUDE.md`, `/etc/claude-code/CLAUDE.md`, `C:\Program Files\ClaudeCode\CLAUDE.md`) → `~/.claude/CLAUDE.md` → `./CLAUDE.md` or `./.claude/CLAUDE.md` → `./CLAUDE.local.md`. Ancestors load in full at launch; subdirectory CLAUDE.md loads on demand when Claude reads files there. Imports: `@path/to/file`, relative to the importing file, **max depth 4**, skipped inside code spans/fences; external imports (outside cwd) trigger a one-time approval dialog.
`.claude/rules/*.md` — recursive, optional `paths:` glob frontmatter for path-scoped rules; `~/.claude/rules/` for user-level.
**Claude Code does not read `AGENTS.md`.** The documented workaround is a `CLAUDE.md` containing `@AGENTS.md`, or a symlink.
**Auto memory** (new): Claude writes its own `~/.claude/projects/<project>/memory/MEMORY.md` + topic files; first 200 lines / 25KB loaded every session; `autoMemoryEnabled`, `autoMemoryDirectory`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. The `#` shortcut / "remember this" routes here.
Docs are explicit that CLAUDE.md is **context, not enforcement**: *"To block an action regardless of what Claude decides, use a PreToolUse hook instead."*

### 1.8 Permissions, modes, sandbox
Sources: <https://code.claude.com/docs/en/permissions>, `/docs/en/permission-modes` **[H]**
Modes: `default`(alias `manual`) | `acceptEdits` | `plan` | `auto` | `dontAsk` | `bypassPermissions`. Shift+Tab cycles. `--permission-mode X`; `--dangerously-skip-permissions` == `bypassPermissions`; refuses to run as root/sudo outside a recognized sandbox.
Rules: `permissions.allow/ask/deny`, `defaultMode`, `additionalDirectories`. Syntax `Tool(pattern)` — `Bash(git diff *)` (space before `*` matters), `Read(./.env)`, `Write(./out/**)`, `WebFetch(domain:...)`, `MCP(server)`.
**Protected paths** are never auto-approved outside bypass: `.git`, `.claude`, `.vscode`, `.idea`, `.husky`, `.cargo`, `.devcontainer`, `.yarn`, `.mvn`, plus shell rc files, `.npmrc`, `.mcp.json`, `.claude.json`, pre-commit configs, etc. `permissions.allow` cannot pre-approve these.
`auto` mode = a separate **classifier model** (Sonnet 5 by default) reviews each non-trivial action against a large published rule set; falls back to prompting after 3 consecutive / 20 total blocks. **Requires Claude models; not reproducible locally as designed.**
Sandboxing (`/docs/en/sandboxing`) is OS-level filesystem+network isolation with `sandbox.filesystem.*`, `sandbox.network.allowedDomains/deniedDomains`, `autoAllowBashIfSandboxed`.

### 1.9 Plan mode
Source: <https://code.claude.com/docs/en/permission-modes> **[H]**
Read + explore, no source edits, until you approve a plan. Enter via Shift+Tab, `/plan` prefix, `--permission-mode plan`, or `defaultMode: "plan"`. `EnterPlanMode`/`ExitPlanMode` are real tools. Approval menu: auto mode / manually approve edits / Ultraplan / keep planning; `Ctrl+G` opens the plan in `$EDITOR`. Approving switches the session's permission mode and names the session from the plan.

### 1.10 Thinking / effort / output styles
- Effort levels `low|medium|high|xhigh|max`; `effortLevel` setting, `CLAUDE_CODE_EFFORT_LEVEL`, `MAX_THINKING_TOKENS`, `alwaysThinkingEnabled`. Subagents inherit the session's thinking config (v2.1.198+). **[H]**
- Output styles (<https://code.claude.com/docs/en/output-styles>): markdown files at `~/.claude/output-styles/`, `.claude/output-styles/`, or plugin `output-styles/`; frontmatter `name`, `description`, `keep-coding-instructions` (default **false** — a custom style *removes* CC's built-in SWE instructions unless set true), `force-for-plugin`. Built-ins: Default, **Proactive**, Explanatory, Learning. They **modify the system prompt**, read once at session start; `/output-style` was removed in v2.1.91, use `/config` or the `outputStyle` setting. Do not apply to subagents (except forks). **[H]**

### 1.11 Task tracking, background work, context management
- Tool inventory (from `/docs/en/tools-reference`) includes: `Agent`, `AskUserQuestion`, `Bash`, `Edit`, `Read`, `Write`, `Glob`, `Grep`, `LSP`, `NotebookEdit`, `PowerShell`, `Skill`, `ToolSearch`, `WebFetch`, `WebSearch`, `TodoWrite`, **`TaskCreate`/`TaskGet`/`TaskList`/`TaskOutput`/`TaskStop`/`TaskUpdate`**, `EnterPlanMode`/`ExitPlanMode`, `EnterWorktree`/`ExitWorktree`, `Monitor`, `SendMessage`, `ScheduleWakeup`, `CronCreate/Delete/List`, `ListMcpResourcesTool`/`ReadMcpResourceTool`, `EndConversation`, `Artifact`. **[H]**
- Background bash via `run_in_background` on the Bash tool; `claude -p` kills background shells ~5s after the final result (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` caps waiting on background subagents, default 10min). **[H]**
- Auto-compaction: `autoCompactEnabled`, `DISABLE_AUTO_COMPACT=1`, `/compact`. Project-root CLAUDE.md is **re-read from disk and re-injected** after compaction; nested CLAUDE.md is not. Invoked skills are re-attached under the 5k/25k budgets. **[H]**
- MCP tool-schema deferral + `ToolSearch` is CC's "context editing" analogue in 2026. **[H]**
- Checkpointing (<https://code.claude.com/docs/en/checkpointing>): a snapshot before **each user prompt**, 100 most recent per session, saved with the conversation (survives resume), deleted with sessions after `cleanupPeriodDays` (30). `/rewind` or double-`Esc` → restore code / conversation / both, or "summarize from/up to here". **Does not track bash-made changes, subagent edits (except foreground forks), external edits, or symlinked/hard-linked paths.** `fileCheckpointingEnabled`. **[H]**

### 1.12 Headless / Agent SDK
Source: <https://code.claude.com/docs/en/headless> **[H]**
`claude -p "<prompt>"`; `--output-format text|json|stream-json`; `--json-schema` for structured output (result in `structured_output`); `--include-partial-messages` + `--verbose` for token streaming; `--continue` / `--resume <session_id>`; `--allowedTools`, `--permission-mode`, `--append-system-prompt(-file)`, `--system-prompt`, `--agents <json>`, `--mcp-config`, `--settings`, `--plugin-dir/--plugin-url`, `--max-turns`, `--forward-subagent-text`. New: **`--bare`** skips auto-discovery of hooks/skills/plugins/MCP/auto-memory/CLAUDE.md — recommended for CI and "will become the default for `-p`". Stream events include `system/init` (with `plugins`, `plugin_errors`, `mcp_servers`, `mcp_server_errors`, `capabilities`), `system/api_retry`, `hook_started`/`hook_progress`/`hook_response`. Subagent messages carry `parent_tool_use_id`. SIGTERM → runs `SessionEnd` hooks, exit 143.
Python/TypeScript packages exist as the Claude Agent SDK.

### 1.13 Agent teams (experimental, 2026)
Source: <https://code.claude.com/docs/en/agent-teams> **[H]**
Gated behind `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Multiple full CC sessions: a lead + teammates with a shared task list (`~/.claude/tasks/{team}/`), mailboxes (`~/.claude/teams/{team}/inboxes/{agent}.json`), file-locked task claiming, direct teammate↔teammate `SendMessage`, optional plan-approval gating, `teammateMode: in-process|auto|tmux|iterm2`. Enforcement hooks: `TeammateIdle`, `TaskCreated`, `TaskCompleted`. Token cost scales linearly with teammates.

### 1.14 Worktrees / IDE / CI
- `isolation: worktree` on subagents, `EnterWorktree`/`ExitWorktree` tools, `WorktreeCreate`/`WorktreeRemove` hooks, `/docs/en/worktrees`. **[H]**
- VS Code / JetBrains extensions with mode selectors; Remote Control; Desktop; claude.ai/code cloud sessions. **[H]**
- GitHub Actions + GitLab CI/CD integrations documented at `/docs/en/github-actions`, `/docs/en/gitlab-ci-cd`. **[M]** (index verified; page not fetched this session)

---

## 2. pi (0.82.x) — mechanism inventory

Sources: <https://pi.dev/docs/latest> and subpages; <https://github.com/badlogic/pi-mono>. **[H]** unless noted.

pi's stated design: *"Pi is a minimal agent harness. Adapt Pi to your workflows, not the other way around."* It **deliberately ships without** built-in MCP, sub-agents, permission popups, plan mode, to-dos, or background bash — the docs say so explicitly (<https://pi.dev/docs/latest/usage>). Everything is meant to be built with **extensions**.

- **Built-in tools:** `read`, `bash`, `edit`, `write`, `grep`, `find`, `ls`. Flags `--tools`, `--exclude-tools`, `--no-builtin-tools`, `--no-tools`.
- **Skills:** full Agent Skills implementation. Paths: `~/.pi/agent/skills/`, `~/.agents/skills/`, `.pi/skills/`, `.agents/skills/` (cwd + ancestors, after trust), package `skills/` dirs, `pi.skills` in package.json, `--skill <path>`. Root `.md` files in `~/.pi/agent/skills/` and `.pi/skills/` count as skills; `SKILL.md` dirs discovered recursively everywhere. Frontmatter: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`, `disable-model-invocation`. Progressive disclosure exactly as the spec. Invoked as **`/skill:<name>`**, args appended as `User: <args>`. **pi deliberately relaxes the "name must equal directory" rule** for shared skill dirs. **Critically: `"skills": ["~/.claude/skills", "~/.codex/skills"]` in settings makes pi read Claude Code's and Codex's skill directories directly.**
- **Prompt templates** (= slash commands): `~/.pi/agent/prompts/*.md`, `.pi/prompts/*.md`, package `prompts/`, settings `prompts` array, `--prompt-template`. Filename → `/name`. Frontmatter `description`, `argument-hint`. Substitution is **bash-style**: `$1`, `$2`, `$@`/`$ARGUMENTS`, `${1:-default}`, `${@:N}`, `${@:N:L}`. Discovery in `prompts/` is **non-recursive**.
- **Extensions** (the hook system): TypeScript, loaded via jiti (no build step), from `~/.pi/agent/extensions/*.ts|*/index.ts`, `.pi/extensions/*.ts|*/index.ts`, or a settings `extensions` array. Default-export a factory `(pi: ExtensionAPI) => void` (async OK).
  Events: `project_trust`, `session_start`, `session_info_changed`, `session_before_switch`, `session_before_fork`, `session_shutdown`, `resources_discover`, `before_agent_start`, `agent_start`, `agent_end`, `agent_settled`, `turn_start`, `turn_end`, `message_start/update/end`, `context`, `before_provider_headers`, `before_provider_request`, `after_provider_response`, `model_select`, `thinking_level_select`, **`tool_call`**, **`tool_result`**, `tool_execution_start/update/end`, `input`, `user_bash`.
  - `tool_call` **can block**: `return { block: true, reason: "..." }`, and `event.input` is mutable in place → this is `PreToolUse` with `deny` + `updatedInput`.
  - `tool_result` handlers **chain and can modify content/details/error status** → this is `PostToolUse` with `updatedToolOutput`.
  - `before_agent_start` returns `{ systemPrompt, message }` → system-prompt mutation + context injection.
  - `context` fires before every LLM call and can modify messages non-destructively → context editing.
  - `pi.registerTool({...})` with TypeBox params, `onUpdate` progress, cancellation signal, custom TUI render.
  - `pi.registerCommand(name, { description, getArgumentCompletions, handler })`.
  - `pi.sendMessage(...)` / `pi.sendUserMessage(...)` with `deliverAs: "steer" | "followUp" | "nextTurn"` → the mechanism for a `Stop`-hook-equivalent.
  - `ctx.ui.notify/confirm/select/input/editor/custom/setStatus/setWidget/setTitle`.
- **Instruction files:** `~/.pi/agent/AGENTS.md` (global), then **`AGENTS.md` or `CLAUDE.md`** walking up parents to cwd. Custom system prompt: `.pi/SYSTEM.md` / `~/.pi/agent/SYSTEM.md`. Disable with `--no-context-files`/`-nc`.
- **Settings:** `~/.pi/agent/settings.json` (global) and `.pi/settings.json` (project, deep-merged over global). Keys include `defaultProvider`, `defaultModel`, `defaultThinkingLevel` (off…max), `hideThinkingBlock`, theme/editor, `defaultProjectTrust`, proxy/telemetry, retry tuning, and resource arrays (`extensions`, `skills`, `prompts`, `themes`) accepting local paths, globs, and npm/git packages.
- **Security model:** **no sandbox, no permission prompts.** Tools run with the pi process's privileges. The only guard is **project trust** (`~/.pi/agent/trust.json`, `defaultProjectTrust`, `-a/--approve`, `-na/--no-approve`) — and the docs are explicit that trust is *"only an input-loading guard"* that does not protect against prompt injection. Recommended mitigation is containerization.
- **Compaction:** auto when `contextTokens > contextWindow - reserveTokens`; `reserveTokens` default **16384**, `keepRecentTokens` default **20000**, `enabled` toggle; `/compact [instructions]` manual. Tool results are **truncated to 2000 chars during summarization serialization** with a truncation marker.
- **Sessions:** tree-structured, branchable, shareable; `-c/--continue`, `-r/--resume`, `--session`, `--fork`, `--no-session`, `--name`. Documented session format at `/docs/latest/session-format`.
- **Headless/programmatic:** four modes — interactive TUI, `-p/--print`, `--mode json` (JSONL event stream: `session` header v3, `agent_start/end`, `turn_start/end`, `message_start/update/end`, `tool_execution_*`, `queue_update`, `compaction_start/end`, `auto_retry_*`), `--mode rpc` (JSON-RPC over stdin/stdout). SDK: `@earendil-works/pi-coding-agent` exporting `createAgentSession()`, `createAgentSessionRuntime()`, `ModelRuntime`, `AgentSession` (`prompt`, `steer`, `followUp`, `subscribe`, `setModel`, `cycleModel`), `SessionManager`, `DefaultResourceLoader`, `defineTool()`, `customTools`, `InteractiveMode`, `runPrintMode()`, `runRpcMode()`.
- **Local model support (best in class for this user's setup):** `~/.pi/agent/models.json` with `providers.<name>.{baseUrl, api, apiKey, models[], compat}`. `api` ∈ `openai-completions` | `openai-responses` | `anthropic-messages` | `google-generative-ai`. Model fields: `id` (required), `name`, `contextWindow` (default 128000), `maxTokens` (default 16384), `input: ["text"|"image"]`, `reasoning`, `cost`. **`compat.supportsDeveloperRole: false`** → send system prompt as `system` rather than `developer` role; **`compat.supportsReasoningEffort: false`** → don't send `reasoning_effort`. Both are required for llama.cpp-style OpenAI servers (matches the user's `clients/pi-models.json` comment). `apiKey` supports `$ENVVAR` and `!command`. Credentials live in `~/.pi/agent/auth.json`.
- **Not present:** MCP, subagents, plan mode, todos, background bash, permission prompts, checkpoint/rewind, plugin marketplace, output styles, worktree isolation. All are "build it as an extension".

---

## 3. opencode — mechanism inventory

Sources: <https://opencode.ai/docs/> plus source reading at **`anomalyco/opencode` @ `8c38d260`**. Version basis **v1.18.10, published 2026-07-30T14:43Z**. **[H]** unless noted.

> ⚠️ **Two facts that invalidate older notes.** (1) **The repo moved**: `github.com/sst/opencode` 301-redirects to **`github.com/anomalyco/opencode`**; default branch is `dev`, not `main`. (2) **Directories are now plural** in docs (`agents/`, `commands/`, `plugins/`, `skills/`, `tools/`, `modes/`, `themes/`); singular still works via literal brace globs (`{agent,agents}/**/*.md`, `{plugin,plugins}/*.{ts,js}`). Note **agents/commands are recursive (`**/*.md`) but plugins/tools are flat (`*.`)**, and a nested agent path **keeps the slash in its name** (`agents/team/reviewer.md` → agent `team/reviewer`).

- **Agents:** `.opencode/agents/*.md`, `~/.config/opencode/agents/*.md`, or `opencode.json` `agent.<name>`. Fields: `description` (**required**), `mode` (`primary`|`subagent`|`all`, default `all`), `model` (`provider/model-id`), `temperature`, `top_p`, `steps` (max agentic iterations; `maxSteps` deprecated), `prompt` (`{file:./path}`), `permission`, `tools` (**deprecated since v1.1.1** — use `permission`), `disable`, `hidden`, `color` (hex or theme name). **Any unrecognized key is passed straight through to the provider as a model option** (e.g. `reasoningEffort: high`). Built-in primaries: `build`, `plan`. Built-in subagents: `general`, `explore` (read-only), `scout` (gated on `OPENCODE_EXPERIMENTAL_SCOUT`). Hidden system agents: `compaction`, `title`, `summary`.
- **Task tool:** lowercase **`task`**, params `description`, `prompt`, `subagent_type`, plus **`task_id`** (resume the *same* subagent session with its prior messages — CC cannot do this) and **`background`** (requires `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`, else hard error; a `BackgroundJob` registry supports `extend` = pushing more context into a running task). Tool description explicitly instructs parallel launches ("use a single message with multiple tool uses"). **`subagent_depth` default is `1`** (primaries spawn subagents; subagents cannot). `permission.task` gates by agent name with globs; `deny` removes the agent from the tool description entirely, though `@`-mention still works. **opencode does NOT read `.claude/agents/`** — agent scanning covers only `~/.config/opencode`, `.opencode` (walked up), `$OPENCODE_CONFIG_DIR`.
- **Skills:** added **v1.0.186** (2025-12-22); native `skill` tool + permissions **v1.0.190**; per-agent filtering **v1.0.191**; **`.claude/skills` support v1.0.208** (2025-12-29). Six discovery paths: `.opencode/skills/`, `~/.config/opencode/skills/`, **`.claude/skills/`**, **`~/.claude/skills/`**, `.agents/skills/`, `~/.agents/skills/` — each `<name>/SKILL.md`; project paths walk up to the git worktree root. **Only 5 frontmatter fields recognized**: `name` (req), `description` (req), `license`, `compatibility`, `metadata`. **No `allowed-tools`** — CC's is silently dropped. `name` must match its directory, regex `^[a-z0-9]+(-[a-z0-9]+)*$`. Progressive disclosure via an `<available_skills>` block in the **singular `skill` tool's** description; body loads on `skill({name:"..."})`.
  - 🔴 **`"tools": {"skills*": true}` in the user's `opencode.json` is a dead key** — that syntax does not exist. The tool is `skill` (singular). Disable with `tools: { skill: false }`; gate with `permission.skill: {"*":"allow","internal-*":"deny"}`.
  - 🔑 **Undocumented: every skill is also a slash command.** The command registry registers `/<skill-name>` whose template is the SKILL.md body plus a base-directory hint. Explicit config commands and MCP prompts take precedence.
  - 🔑 **Skill tool output is never pruned during compaction** (`PRUNE_PROTECTED_TOOLS = ["skill"]`).
- **Commands:** `.opencode/commands/**/*.md`, `~/.config/opencode/commands/`, or `command` in config. Frontmatter `description`, `agent`, `model`, `subtask` (bool — forces subagent execution even for a primary agent; **if `agent` names a subagent it runs as a subtask by default**), `template` (required in JSON only). Substitution `$ARGUMENTS`, `$1..$N`, `` !`cmd` `` (bash in project root), `@file`. **`.claude/commands/` is NOT read.** Built-in server-side prompt commands include `/init` and an **undocumented `/review`** (`subtask: true`); custom commands can override built-ins.
- **Plugins (= hooks), JS/TS only:** `.opencode/plugins/*.{ts,js}`, `~/.config/opencode/plugins/*.{ts,js}` (**flat, non-recursive**), or npm packages in the `plugin` array (Bun-installed at startup, cached in `~/.cache/opencode/node_modules/`). Load order: global config → project config → global dir → project dir; all hooks run in sequence with the `output` object threaded through.
  ⚠️ **The docs' "Events" list (~30 names like `session.idle`, `file.edited`) is NOT the hook list** — those are `event.type` values delivered to the single `event` hook. The real surface is the `Hooks` interface (`packages/plugin/src/index.ts:222-335`):
  `dispose`, `event`, `config`, `tool` (register custom tools), `auth`, `provider`, **`chat.message`**, **`chat.params`** (mutate `temperature`/`topP`/`topK`/`maxOutputTokens`/`options`), `chat.headers`, **`permission.ask`** (override to `allow`/`ask`/`deny` — a real `PermissionRequest` analogue, absent from the docs' event list), `command.execute.before`, **`tool.execute.before`** (mutate `output.args`; **throw to block**), **`tool.execute.after`** (mutate `output.title`/`output`/`metadata`), **`tool.definition`** (rewrite any tool's description + JSON schema before the model sees it — no CC equivalent), `shell.env`, and experimental: `chat.messages.transform`, **`chat.system.transform`** (push onto `output.system[]`), `provider.small_model`, `session.compacting` (`output.context.push()` or replace with `output.prompt`), **`compaction.autocontinue`**, `text.complete`.
  Plugin input: `{ client, project, directory, worktree, serverUrl, $ (Bun shell), experimental_workspace }`. Kill switch: `--pure` / `OPENCODE_DISABLE_DEFAULT_PLUGINS`.
  ❌ **No config-file hook mechanism** — there is nothing like CC's `settings.json` `hooks` block with shell commands. Every hook is a JS/TS module. This is the single biggest structural difference for a converter.
- **Rules / memory:** `globalFiles = [~/.config/opencode/AGENTS.md, ~/.claude/CLAUDE.md]`; `instructionFiles = ["AGENTS.md", "CLAUDE.md", "CONTEXT.md"(deprecated)]`. 🔴 **First match wins per category — they do NOT stack.** If both `AGENTS.md` and `CLAUDE.md` exist, only `AGENTS.md` loads. 🔑 **Nested AGENTS.md is lazy and on-read**: `Instruction.resolve()` walks upward from any file the agent reads, attaching nearby `AGENTS.md`/`CLAUDE.md` once per assistant message — opencode's analogue of CC's nested CLAUDE.md, but triggered by reads rather than loaded upfront. `instructions: []` accepts paths, globs, `~/`, absolute paths and **remote HTTP(S) URLs (5s timeout)**, each prefixed `Instructions from: <path>`. ❌ No `@` imports in AGENTS.md (docs are explicit); ❌ no `#` shortcut; ❌ no path-scoped rules. Disable CC compat: `OPENCODE_DISABLE_CLAUDE_CODE=1`, `..._PROMPT=1`, `..._SKILLS=1`.
- **Permissions (richer than CC):** values `allow`/`ask`/`deny`. Keys: `read`, `edit` (covers write/edit/apply_patch), `glob`, `grep`, `list`, `bash` (matches *parsed* commands), `task`, `skill`, `lsp`, `question`, `webfetch`, `websearch`, `external_directory`, **`doom_loop`** (same tool call 3× with identical input), `todowrite`. Granular glob→action for `read, edit, glob, grep, list, bash, task, external_directory, lsp, skill`; also wildcard-matches raw tool names (`"mymcp_*": "deny"`). **Last matching rule wins** (CC is first-match) — put `"*"` first. Defaults: most `allow`; `doom_loop` and `external_directory` default `ask`; **`read` denies `*.env` / `*.env.*` by default** (allows `*.env.example`). Per-agent overrides merge and take precedence. `OPENCODE_PERMISSION` env accepts inline JSON.
  - Skip-permissions flag: documented **`--auto`**; source also accepts hidden aliases **`--yolo`** and **`--dangerously-skip-permissions`** (`const auto = args.auto || args.yolo || args["dangerously-skip-permissions"]`). **Explicit `deny` rules are still enforced in auto mode.**
  - ❌ **No OS-level sandbox.** Confinement is `permission` + managed config only. (Third-party `opencode-daytona` plugin runs sessions in remote sandboxes.)
  - Enterprise: managed config at `/etc/opencode/`, `/Library/Application Support/opencode/`, `%ProgramData%\opencode`, plus **macOS MDM `.mobileconfig`** (`ai.opencode.managed`), not user-overridable.
- **MCP:** `mcp` key; local (`command[]`, `cwd`, `environment`) / remote (`url`, `headers`, `oauth`); `timeout` default **5000 ms**. Automatic 401 detection + **Dynamic Client Registration (RFC 7591)**; tokens in `~/.local/share/opencode/mcp-auth.json`; CLI `opencode mcp auth|list|logout|debug|add`. Tools namespaced `<server>_<tool>`. **MCP prompts ARE auto-registered as `/<prompt-name>` slash commands** with declared args mapped to `$1`,`$2`. **MCP resources / `@`-mentions: no evidence — unverified-absent.**
- **Plan mode — two distinct things.** (a) The **`plan` agent**, always available, is purely a permission ruleset: `question: allow`, `plan_exit: allow`, `task: {general: deny}` (forces `explore`), `edit: {"*": deny, ".opencode/plans/*.md": allow}` — i.e. it can write its own plan file and nothing else. (b) **`OPENCODE_EXPERIMENTAL_PLAN_MODE`** adds the **`plan_exit` tool** (CLI/TUI only) and a 5-phase structured workflow prompt. `plan_exit` takes no params; on approval it synthesizes a new user message with `agent: "build"` and text *"The plan at <path> has been approved, you can now edit files. Execute the plan"* — functionally CC's `ExitPlanMode`. Plan files: `.opencode/plans/<timestamp>-<slug>.md`. ⚠️ **`plan_enter` does not exist** at v1.18.10 (orphaned `plan-enter.txt`); you can be prompted *out of* plan mode but not *into* it. `opencode run` hard-denies `question`, `plan_enter`, `plan_exit`.
- **Thinking:** `--thinking` on `opencode run` (default: interactive `true`, non-interactive `false`); `/thinking` toggles **display only**. **Actual reasoning effort is controlled by model *variants*** — `ctrl+t`, `/variants`, `--variant`.
- **Output styles: ❌ confirmed absent** (repo-wide grep). Nearest: per-agent `prompt`, AGENTS.md, themes (visual only).
- **TODO:** ⚠️ only **`todowrite`** exists — **there is no `todoread`** (the docs' permission table row is stale; `tool/todoread.txt` 404s). States include a CC-absent **`cancelled`**. Global default is `"*": "allow"`, so a **user-defined subagent gets `todowrite` unless it denies it** (only the built-ins deny it).
- **Background bash: ❌ does not exist.** Shell tool params are only `command`, `timeout?`, `workdir?`. No `run_in_background`/`BashOutput`/`KillShell`. (Background *subagents* are a different thing.)
- **Compaction:** `/compact` (alias `/summarize`) under a hidden `compaction` agent. Config `compaction.auto` (default `true`), `.prune` (default **false**), `.reserved` (defaults to `min(20_000, maxOutputTokens)`); undocumented `tail_turns` (2), `preserve_recent_tokens`. Pruning protects the most recent 40k tokens of tool output and never prunes `skill` output. Kill switches `OPENCODE_DISABLE_AUTOCOMPACT`, `OPENCODE_DISABLE_PRUNE`.
- **Undo/redo/rewind — shadow-git, more capable than CC:** snapshots live in a **separate bare git repo whose work-tree is your project** (`~/.local/share/opencode/snapshot/<projectID>/<hash>`); **your `.git` is never touched**. `/undo` steps back one user message **and restores that message's text and attachments into the prompt input** for editing; `/redo` steps forward. `POST /session/{id}/revert {messageID, partID?}` gives **sub-message granularity**; `unrevert` restores. `/timeline` lists user messages → Revert / Copy / Fork. **Revert is non-destructive until you send a new message.** `/fork` forks a session from a chosen message. Requires a git repo; disable with `"snapshot": false`.
- **Config keys:** `model`, `small_model`, `provider`, `agent`, `command`, `mcp`, `permission`, `instructions`, `plugin`, `tools`, `formatter`, `lsp`, `autoupdate`, `share`, `keybinds`, `experimental`, `compaction`, `watcher`, `snapshot`, `attachment`, `server`, `shell`, `default_agent`, `subagent_depth`, `disabled_providers`, `enabled_providers`, `enterprise`.
- **Headless:** `opencode run "<prompt>"` — **there is no `-p`** (the prompt is positional; `-p` is `--password`). Flags `-c/--continue`, `-s/--session`, `--fork`, `--share`, `-m/--model`, `--agent`, `-f/--file`, **`--format default|json`**, `--title`, `--attach <url>`, `--dir`, `--port`, `--variant`, `--thinking`, `--auto`.
  - `--format json` emits **NDJSON**: `{type, timestamp, sessionID, ...}` with types `tool_use`, `step_start`, `step_finish`, `text`, `reasoning`, `error`.
  - 🔴 **Automation gotchas:** there is **no terminal `done`/`result` event** (the loop exits when `session.status` reports `idle`; exit 1 if any `session.error`), and **permission requests are not emitted as JSON — without `--auto`, `opencode run --format json` silently auto-rejects them.**
  - `--continue` picks the first session with **no `parentID`** (skips subagent sessions).
  - Warm start: `opencode serve` + `opencode run --attach http://localhost:4096` avoids MCP cold-boot per run.
- **HTTP server / SDK:** `opencode serve`; **port default is `0`** = try 4096 then any free port (not a fixed 4096). Auth via `OPENCODE_SERVER_PASSWORD` (+ `?auth_token=<base64 user:pass>` for EventSource). SSE `/event` opens with `server.connected`, heartbeats every **10 s**. OpenAPI 3.1 at `GET /doc` (returns JSON). 🔑 **Two parallel HTTP APIs exist** — v1 unprefixed and an undocumented **v2 under `/api/`**. SDK `@opencode-ai/sdk` (ESM-only, JS/TS **only** — no Go, Python SDK planned but unshipped) exports `createOpencode`, `createOpencodeClient`, `createOpencodeServer`, `createOpencodeTui`; `/v2` subpath uses flat params and is what the CLI itself uses. **Structured output IS supported**: `format: {type:"json_schema", schema, retryCount?}` → `result.data.info.structured_output`. **ACP** (`opencode acp`) for Zed/JetBrains/Neovim; `/undo` and `/redo` unsupported there.
- **Custom tools:** `.opencode/tools/*.ts`, default export → tool named `<filename>`, named exports → `<filename>_<export>`. `tool()` is an identity function for type inference; `tool.schema` **is literally the Zod module**. Custom tools **override built-ins on name collision**.
- **🔑 Extras CC does NOT have (the important ones):**
  1. **Automatic LSP diagnostics fed back into tool results.** `edit` and `write` call the LSP after writing and **append diagnostics into the string the model sees**: `"LSP errors detected in this file, please fix:\n..."`; `write` also reports project-wide diagnostics (max 5 files). In CC the model must proactively run `tsc`/`eslint`. **34 built-in LSP servers**, several auto-installing; disabled by default (`"lsp": true`).
  2. **Auto-formatting before the diagnostics pass** — 27 built-in formatters (prettier, biome, ruff, gofmt, rustfmt, shfmt…), most gated on a config file being present; disabled by default (`"formatter": true`). CC needs a PostToolUse hook for this.
  3. **Automatic malformed-tool-call repair, always on.** Wrong-case tool names are silently case-folded; anything else is rerouted to a synthetic **`invalid`** tool that feeds the error text back to the model.
  4. `tool.definition` hook, task `task_id` resumption, `background` subagents with `extend`, MCP prompts as slash commands, the **`question`** tool (model asks the user structured multiple-choice mid-run), `doom_loop`, `opencode attach`, mDNS discovery, MDM managed prefs, `opencode export|import|stats|db`, `.ignore` to re-include gitignored paths in grep/glob.
- **Not present / weaker than CC:** no config-file hooks or exit-code protocol, **no `Stop`-hook equivalent** (`session.idle` is an `event` type, observational; the closest lever is `experimental.compaction.autocontinue`), no `todoread`, no background bash, no output styles, no plugin marketplace, no `.claude/agents` or `.claude/commands` compat, no `@import` in AGENTS.md, no path-scoped rules, no OS sandbox, no MCP resources.

### 3.1 Local-model specifics — three undocumented footguns that affect this setup

1. 🔴 **`temperature` is silently not sent for hand-declared models.** `models.<id>.temperature` is a **capability boolean**, not a value, and it **defaults to `false`** for custom providers. The request builder gates on it: `temperature: model.capabilities.temperature ? (agent.temperature ?? transform(model)) : undefined`. **The user's `agent.build.temperature: 0.1` and `agent.plan.temperature: 0.1` are therefore probably being dropped**, because `provider.litellm.models.coder` has no `"temperature": true`. **Fix: add `"temperature": true` to each model entry in `opencode.json`.**
2. **Qwen auto-temperature is a substring match on the model's *api id*, lowercased**: `if (id.includes("qwen")) return 0.55` (topP → 1). The user's ids are `coder`/`coder-strong`/`fast`/`utility` — **no `qwen` substring, so no auto-tuning happens**. Either rename the LiteLLM aliases to contain `qwen`, or set temperature explicitly (with the boolean above).
3. **`timeout` has no 300000 default** despite the docs claiming one; nothing applies it unless explicitly set. Recommended for local: `{"timeout": false, "headerTimeout": 600000, "chunkTimeout": 120000}`.

Other local-relevant knobs: `options.includeUsage` is **auto-`true`** for `@ai-sdk/openai-compatible` (set `false` if the runner chokes on `stream_options.include_usage`); `maxOutputTokens = min(model.limit.output, 32_000)`; `provider.<id>.options.setCacheKey: true` sets `promptCacheKey = <sessionID>` (useful for vLLM/SGLang prefix-cache affinity); **`small_model` family-priority auto-detection never matches a custom provider**, so setting it explicitly (which the user already does: `litellm/utility`) is required or every session title costs a full local generation. `models.<id>.tool_call` exists in the schema but **no consumer gates behavior on it — effect unverified**. `parallel_tool_calls` is **not** a config key; workaround is `models.<id>.options.parallel_tool_calls = false` (lands in the request body, **unverified end-to-end**). JSON-schema `strict` is hardcoded `false` and **only applied for `@ai-sdk/openai`/`azure`/`bedrock`, not `openai-compatible`**. There is **no Qwen-specific system prompt** — local Qwen gets `default.txt`; override with `agent.<n>.prompt`.

---

## 4. The parity matrix

Importance column = **how much this feature matters when the model is a ~30B local instead of Opus** (1 = barely, 5 = load-bearing). Reasoning in §5.

| # | Feature | Claude Code mechanism | opencode | pi | Gap-closing plan | Imp. |
|---|---|---|---|---|---|---|
| 1 | **Skills (SKILL.md)** | `.claude/skills/<n>/SKILL.md`, progressive disclosure, `Skill` tool, 1536-char description cap | **Native, and reads `.claude/skills/` + `~/.claude/skills/`.** Spec fields only | **Native**, `/skill:<name>`, and settings can point at `~/.claude/skills` | Already portable. Keep skills to the 6 spec fields; put CC-only fields under `metadata:` | **5** |
| 2 | **Skill `allowed-tools` pre-approval** | Grants tool perms for the invoking turn | Ignored (field not recognized) | Parsed (listed in frontmatter) but no permission system to apply it to | opencode: encode as `agent.<n>.permission` or a plugin that widens perms when `tool.execute.before` sees `skill` load. pi: n/a (no perms) | 2 |
| 3 | **Skill `context: fork` / run-in-subagent** | Skill runs in a forked subagent, background by default | No — but `command` with `subtask: true` is equivalent for command-shaped skills | No (no subagents) | opencode: mirror every "heavy" skill with a thin `commands/x.md` `subtask: true` wrapper. pi: extension that spawns a nested `createAgentSession()` | 3 |
| 4 | **Skill dynamic context** `` !`cmd` `` | Runs shell **before** the skill text reaches the model | Available in **commands**, not skills | Not in skills; prompt templates do arg expansion only | Wrap in a command/prompt-template that shells out, then `/skill:` the procedure | 4 |
| 5 | **Custom slash commands** | Merged into skills; `$ARGUMENTS`,`$N`,`` !`` ``,`@file` | `.opencode/commands/*.md`; `$ARGUMENTS`,`$1..$3`,`` !`` ``,`@file`, `agent`, `model`, `subtask` | `.pi/prompts/*.md`; **bash-style** `$1`,`$@`,`${1:-def}`,`${@:N:L}`; `description`,`argument-hint` only | Trivially convertible. pi loses `agent`/`subtask` (no subagents) and `` !`` `` injection | 4 |
| 6 | **Subagents (definition files)** | `.claude/agents/*.md`, 17 frontmatter fields | **Native**: `.opencode/agents/*.md`, `mode`, `model`, `temperature`, `permission`, `steps`, `top_p`, `hidden` | **None.** pi explicitly ships without subagents | opencode: direct. pi: build an extension registering a `task` tool that calls `createAgentSession()` with its own tools/system prompt, or shell out to `pi -p --mode json` | **5** |
| 7 | **Task/Agent tool + auto-delegation** | `Agent` tool; routing off `description` | `task` tool + `@mention`; gated by `permission.task` | None (buildable) | See #6 | 4 |
| 8 | **Parallel subagents** | Background by default (v2.1.198+), concurrency limits, `parent_tool_use_id` in stream | Tool description explicitly instructs parallel launches in one message; `subagent_depth` **default 1**; `background: true` behind `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`; **`task_id` resumption (CC cannot do this)** | None | On a single 24GB GPU **parallel agents are counter-productive** — they serialize on the GPU and multiply KV-cache pressure. Prefer sequential + context isolation. But `task_id` resumption is genuinely useful: continue a subagent instead of re-priming it | 2 |
| 9 | **Subagent context isolation** | Own context window, own system prompt, results summarized back | Yes | No | This is the *real* value of subagents locally: keeping 40k tokens of grep output out of a 131k window | **5** |
| 10 | **Subagent `isolation: worktree`** | Temp git worktree, auto-cleanup | No (but the user's Orca already runs agents in worktrees) | No | Keep doing it at the Orca/harness layer | 2 |
| 11 | **Hooks — PreToolUse blocking** | JSON on stdin, `permissionDecision: deny`, exit 2, `updatedInput` | `tool.execute.before`, **throw to block**, mutate `output.args`. Plus a real **`permission.ask`** hook (`output.status = allow\|ask\|deny`) = CC's `PermissionRequest` | `tool_call` → `{block:true, reason}`, `event.input` mutable | Both can do it, neither speaks the CC JSON contract. **Write one shim per host** (see §6.4) | **5** |
| 12 | **Hooks — PostToolUse feedback** | `updatedToolOutput`, `additionalContext`, exit 2 → stderr to model | `tool.execute.after` | `tool_result` — chains, can modify content/error/usage | Same shim. This is where "run the tests / lint after every edit and feed failures back" lives | **5** |
| 13 | **Hooks — `Stop` (block the agent from stopping)** | `decision: block` + `reason` re-prompts the model | **No blocking equivalent — confirmed at source.** `session.idle` is an `event` type, observational. Nearest lever is `experimental.compaction.autocontinue` | `agent_end`/`agent_settled` + `pi.sendUserMessage(..., {deliverAs:"followUp"})` → **functionally equivalent** | **pi wins here.** opencode: either an external supervisor loop around `opencode run --continue`, or a plugin that on `event: session.idle` calls `client.session.prompt()` via the SDK client it already receives — **the latter is a genuine in-process Stop hook and is the single best plugin to write** | **5** |
| 14 | **Hooks — `UserPromptSubmit` + `additionalContext`** | Inject context / block prompt | No direct event; `tui.prompt.append` is TUI-side | `input` event — can transform/intercept/handle user input | pi native. opencode: pre-process in a wrapper script or `experimental.session.compacting` | 3 |
| 15 | **Hooks — `SessionStart` context injection** | `additionalContext`, `initialUserMessage`, `watchPaths` | `session.created` (observational; injection unverified) | `session_start` + `before_agent_start` returns `{systemPrompt, message}` — **stronger than CC** | pi native | 3 |
| 16 | **Hooks — `PreCompact`/`PostCompact`** | Veto/observe compaction | `session.compacted`, `experimental.session.compacting` with `output.context.push()`/`output.prompt` — **can rewrite the compaction prompt** | `context` event (pre-LLM message rewrite) + compaction settings | Both usable; opencode's is arguably better | 3 |
| 17 | **Hooks — `SubagentStop`** | Block subagent completion | No | n/a (no subagents) | Fold verification into the subagent's own prompt + a `tool.execute.after` gate | 3 |
| 18 | **Hook config format** | Declarative JSON in settings, `matcher` regex, `if:` rules, 5 handler types (`command`/`http`/`mcp_tool`/`prompt`/`agent`), exit-code protocol | **Imperative JS/TS only** | **Imperative TS only** | Build a tiny `cc-hooks.json` interpreter as one plugin/extension per host (§6.3) | 4 |
| 19 | **Hooks in skill/agent frontmatter** | `hooks:` field scoped to component lifetime | No | No | Shim can read the field and register/unregister on skill load | 2 |
| 20 | **Plugins & marketplaces** | `.claude-plugin/plugin.json`, marketplace.json, bundles skills+agents+hooks+MCP | `plugin` array (npm/file); no marketplace, no bundle format | npm/git packages via settings `extensions`/`skills`/`prompts`/`themes` arrays + `pi.*` package.json entries | Use a git repo + npm package as the "marketplace". Low priority for one user | 1 |
| 21 | **MCP** | stdio/SSE/HTTP, `.mcp.json`, user/project/local scopes, `mcp__s__t` naming, **deferred schemas + ToolSearch** | `mcp` key, local/remote, per-agent enable | **None built in** — must write an extension | opencode: already done (context7, serena). pi: the real cost of switching to pi. Note: on a 30B model, *fewer* MCP tools is better — deferred schemas matter | 3 |
| 22 | **MCP prompts as slash commands / resources as @** | Yes | Unverified | n/a | Low value locally | 1 |
| 23 | **Memory hierarchy** | managed → user → project → local CLAUDE.md, subdir on-demand | `AGENTS.md` upward traversal + global + **CLAUDE.md fallbacks** | `~/.pi/agent/AGENTS.md` + upward `AGENTS.md`\|`CLAUDE.md` | Already compatible. Write once as `AGENTS.md`; CC reads it via `@AGENTS.md` in CLAUDE.md | 4 |
| 24 | **`@path` imports in memory** | Recursive, depth 4, external-import approval | **No** — `instructions[]` globs/URLs instead | Unverified | Pre-expand imports at deploy time with a build step, or list files in `instructions[]` | 2 |
| 25 | **Path-scoped rules (`.claude/rules/` + `paths:`)** | Loads only when touching matching files | **No** | No | Convert path-scoped rules into **skills with trigger-heavy descriptions**; or a plugin that injects on `file.edited` | 3 |
| 26 | **Auto memory (model writes its own notes)** | `~/.claude/projects/<p>/memory/MEMORY.md`, 200 lines/25KB | No | No | The user already has a `compounding-learnings` skill writing to `AGENTS.md`/`docs/lessons.md` — that *is* the port. Keep it | 3 |
| 27 | **`#` quick-memory shortcut** | Appends to memory | No | No | `/compound` command already covers it | 1 |
| 28 | **Permission rules (allow/ask/deny + patterns)** | `Tool(pattern)`, protected paths | **Strong**: 14 permission keys, glob rules, last-match-wins, per-agent | **None.** No permission prompts at all | opencode is *better* than CC here for this use case. pi requires a `tool_call` extension implementing an allow/deny table — **write this before using pi for anything beyond read-only** | **5** |
| 29 | **Permission modes** | 6 modes, Shift+Tab cycle | `--auto`; per-agent permission sets act as modes (the user's `plan` agent = plan mode) | Only `--tools`/`--exclude-tools` allowlists | opencode: define agent presets. pi: `--tools read,grep,find,ls` for a read-only mode | 4 |
| 30 | **`--dangerously-skip-permissions`** | `bypassPermissions`, root refusal, warning dialog | `--auto` | Default behavior (no perms) | n/a | 1 |
| 31 | **OS sandbox** | `sandbox.filesystem/network`, `autoAllowBashIfSandboxed` | Not documented | **Explicitly none**; docs recommend containers | User already has Docker on the rig — run agents in a container with the repo bind-mounted | 3 |
| 32 | **Plan mode** | Read-only + `ExitPlanMode` approval handshake | `plan` primary agent with `edit: deny`, `bash: deny` (**user already has this**) | **None**; approximate with `--tools read,grep,find,ls` | opencode is fine. pi: an extension registering `enter_plan_mode`/`exit_plan_mode` tools that flip a tool allowlist | **5** |
| 33 | **Extended thinking / effort** | `effortLevel`, `MAX_THINKING_TOKENS`, per-agent `effort` | Model-level; reasoning display | `defaultThinkingLevel` off…max, `--thinking`, `hideThinkingBlock`, `thinking_level_select` event | For Qwen3.6 you control this at the LiteLLM/template layer. pi's `compat.supportsReasoningEffort:false` is **required** for llama.cpp servers | 3 |
| 34 | **Output styles** | System-prompt replacement, `keep-coding-instructions` | No | `.pi/SYSTEM.md` / `~/.pi/agent/SYSTEM.md` = **full system prompt override** — stronger | pi native. opencode: `agent.<n>.prompt: {file:./x.md}` per agent | 3 |
| 35 | **Todo tracking** | `TodoWrite` + `TaskCreate/Update/List/Get/Output/Stop` | **`todowrite` only — `todoread` does not exist** (docs' permission table is stale). Adds a `cancelled` state CC lacks. Default `"*": "allow"`, so a user-defined subagent gets it unless denied | **None** ("skips … to-dos") | pi: register a `todo` tool in an extension (~40 lines) — **high value for a weak model** | 4 |
| 36 | **Background bash** | `run_in_background`, `BashOutput`, `KillShell` | Unverified | **None** | Low value locally; use tmux | 1 |
| 37 | **Auto-compaction** | Threshold-based, skills re-attached (5k/25k), CLAUDE.md re-injected | `compaction` config (auto, prune, reserved tokens) | `reserveTokens` 16384, `keepRecentTokens` 20000, `/compact [instr]`, tool results truncated to 2000 chars | Both fine. **pi's 2000-char tool-result truncation is a real advantage on a 131k window** | 4 |
| 38 | **Manual `/compact` with instructions** | Yes | Yes | Yes (`/compact <instructions>`) | Parity | 3 |
| 39 | **Context editing / tool-result clearing** | Deferred MCP schemas + `ToolSearch`; skill re-attach budget | `compaction.prune` | `context` event = arbitrary pre-call message rewriting; tool-result truncation | **pi's `context` event is the most powerful primitive of the three** for a small window | 4 |
| 40 | **Checkpointing / `/rewind`** | Pre-prompt snapshots, 100/session, restore code+conv, summarize-from-here. Misses bash-made edits, subagent edits, symlinks | **Better than CC.** Shadow bare-git repo at `~/.local/share/opencode/snapshot/<projectID>/` whose work-tree is your project — **your `.git` is untouched**, so it captures *bash-made edits too*. `/undo` restores the message text+attachments into the prompt for editing; `/redo`; `POST /session/{id}/revert {messageID, partID?}` = **sub-message granularity**; non-destructive until you send a new message; `/timeline`, `/fork`. Requires a git repo; `"snapshot": false` disables | Session **tree with forking** (`--fork`), no file snapshots | opencode already wins. Keep auto-commit-per-green-step as the durable layer | 3 |
| 41 | **Session resume/fork** | `--continue`, `--resume`, `--fork-session`, `/branch` | `-c/--continue`, `-s/--session` | `-c`, `-r`, `--session`, `--fork`, `--name`, tree-structured history | pi is strongest | 2 |
| 42 | **Headless `-p` + JSON** | `-p`, `--output-format json\|stream-json`, `--json-schema`, `--bare` | `run --format json`, `serve` HTTP API + SDK | `-p`, `--mode json` (JSONL), `--mode rpc` (JSON-RPC), full TS SDK | All three good. pi's RPC + SDK is the best embedding story; opencode's HTTP server is the best remote story | 3 |
| 43 | **Structured output (`--json-schema`)** | Yes, `structured_output` field | **Yes via SDK** — `format: {type:"json_schema", schema, retryCount?}` → `result.data.info.structured_output` (not exposed as a CLI flag) | No | Also constrain at the LiteLLM layer (guided decoding / `response_format`) — **more reliable than prompting a 30B model** | 3 |
| 44 | **Agent teams / multi-session** | Experimental; mailboxes, shared task list, file-locked claiming | No | No | Not worth it on one GPU | 1 |
| 45 | **LSP integration** | `LSP` tool | **Native `lsp` config + permission** | No (use serena MCP) | opencode advantage; the user's serena MCP covers pi | 4 |
| 46 | **Formatters** | Via hooks | **Native `formatter` config** | Extension / `tool_result` hook | opencode advantage | 3 |
| 47 | **GitHub Actions / CI** | `/docs/en/github-actions` | `opencode github install\|run` | `--mode json` in any runner | Parity enough | 2 |
| 48 | **IDE integration** | VS Code/JetBrains extensions, Remote Control | TUI/IDE/desktop | TUI only (+ TUI component lib) | n/a | 1 |
| 49 | **Doom-loop / repetition guard** | Not a first-class feature | **`doom_loop` permission key** | No | opencode advantage — **very relevant for 30B models that retry the same failing command** | 4 |
| 50 | **Deterministic model-per-role** | `model:` on agents/skills, `CLAUDE_CODE_SUBAGENT_MODEL` | `model` per agent and per command; `small_model` for titles (**family auto-detect never matches a custom provider — must be explicit**) | `--model`, `setModel()`, per-session | Route `fast` (7B) to titles/summaries, `coder-strong` to plan/review, `coder` to build. The user's config already does this correctly | 4 |
| 51 | **🔑 Auto LSP diagnostics injected into tool results** | ❌ none — model must run `tsc`/`eslint` via Bash | ✅ **`edit`/`write` append `"LSP errors detected in this file, please fix: …"` to the tool result**; `write` also reports project-wide (max 5 files). 34 built-in servers, off by default (`"lsp": true`) | ❌ (use serena MCP) | **Turn this on.** It is a free, always-on, zero-token-cost verification loop that closes within the same turn — the exact intervention a 30B model needs most | **5** |
| 52 | **🔑 Auto-format before diagnostics** | Via PostToolUse hook | ✅ native `formatter`, 27 built-ins, off by default (`"formatter": true`) | Extension | Turn on; saves the model a turn per edit | 4 |
| 53 | **🔑 Malformed tool-call repair** | Not documented as a feature | ✅ **always on** — wrong-case names silently folded; anything else routed to a synthetic `invalid` tool that feeds the error back to the model | ❌ unverified | The single biggest built-in resilience for weak local models, and a real argument for opencode over pi on a 30B | **5** |
| 54 | **`tool.definition` hook (rewrite tool schemas)** | ❌ none | ✅ rewrite any tool's description + JSON schema before the model sees it | ❌ (but `registerTool` lets you define your own) | Use it to **shrink and simplify tool descriptions** — a 30B model's tool selection improves markedly with terser schemas | 4 |
| 55 | **`question` tool (model asks the user)** | `AskUserQuestion` (stripped from subagents) | ✅ `question` tool + `permission.question` | ❌ (but `ctx.ui.select/confirm/input` exist for extensions) | Cheap way to stop a weak model guessing | 3 |

---

## 5. What is load-bearing when the model is weak — ranked

This is the section that should drive decisions. The organizing principle:

> **A frontier model uses these features as conveniences. A 30B model needs them as an external skeleton.** Opus supplies its own procedure, its own self-verification, and its own context discipline. Qwen3.6-35B-A3B supplies none of those reliably. Every CC feature that *externalizes* procedure, verification, or context management into deterministic machinery goes **up** in value. Every CC feature that merely *saves the user typing* goes **down**.

A second principle, specific to a **single 24GB GPU**: features that trade tokens for quality (parallel agents, classifier passes, big system prompts, many MCP tools) are much more expensive here than on the API, because you have one serialized generator at maybe 30–50 tok/s. Token-cheap determinism beats token-expensive intelligence.

### Tier 1 — matters far MORE with a weak model (do these first)

0. **Already-built verification loops you are not using (#51, #52, #53).** *Discovered in opencode source, not in the docs' feature list.* opencode's `edit`/`write` tools call the LSP after every write and **append diagnostics directly into the tool result the model reads** — `"LSP errors detected in this file, please fix: …"` — and `write` reports project-wide errors across up to 5 files. Formatting runs first, so the model never spends a turn on style. Separately, malformed tool calls are repaired automatically (wrong-case folded; everything else rerouted to a synthetic `invalid` tool whose error text goes back to the model). **All three are exactly the "deterministic tool feedback" a 30B model needs, they cost zero extra tokens of prompt, and LSP + formatter are both OFF BY DEFAULT.** Setting `"lsp": true, "formatter": true` is the single highest-value config change in this entire report. It also partially substitutes for #12 below: a whole class of errors gets caught and fed back without any hook at all.

1. **PostToolUse verification hooks (#12) + a `Stop`-equivalent (#13).** *Why:* the dominant failure of a 30B coding model is **claiming success without evidence** — "the test should pass now". Opus mostly self-checks; Qwen mostly doesn't. A `tool.execute.after` / `tool_result` hook that runs the test command after every edit and injects the failure text is worth more than any prompt engineering. The `Stop`-blocker is the second half: refuse to let the turn end while the suite is red. The user's `verification-before-done` skill states this rule — **but a skill is a request, a hook is a law.** CC's own docs make this exact point: *"To block an action regardless of what Claude decides, use a PreToolUse hook instead."* **pi can do the full loop today (`tool_result` + `agent_end` + `sendUserMessage({deliverAs:"followUp"})`); opencode can do the feedback half but not the blocking half.**
2. **PreToolUse deny rules / permissions (#11, #28).** *Why:* a weak model produces destructive commands more often and recovers from them worse. Deterministic denial of `git push`, `rm -rf`, force-push, and writes outside the repo removes an entire failure class at zero token cost. opencode's permission system is genuinely *better* than CC's for this. **pi has none — this is the single biggest reason not to run pi unsupervised yet.**
3. **Skills as supplied procedure (#1, #4).** *Why:* progressive disclosure exists to save context, but on a weak model its bigger job is **decision reduction**. The model doesn't have to invent a debugging method; it reads one. The user's `test-driven-development`, `systematic-debugging`, `verification-before-done` skills are exactly the right shape. Two amplifiers: (a) descriptions must be trigger-word dense, because a 30B model's skill-selection is much worse than Opus's — put literal phrases the user types into `description`; (b) `` !`cmd` `` dynamic context (#4) matters more than for Opus, because handing the model the actual `git diff`/test output beats asking it to go fetch it.
4. **Plan mode / read-only exploration (#32).** *Why:* the most expensive weak-model failure is confidently editing the wrong file. Forcing a read-only research phase with `edit: deny, bash: deny` (which the user already has) converts an expensive wrong edit into a cheap wrong paragraph. Plan mode also produces an artifact a *stronger* model or the human can check before any code moves.
5. **Context isolation via subagents (#9).** *Why:* not for parallelism — for **keeping junk out of a 131k window**. A grep sweep that returns 30k tokens degrades a 30B model's attention far more than it degrades Opus's. Delegating "find where X is defined" to a subagent that returns three lines is a quality intervention, not just a cost one. **This is the strongest argument for opencode over pi today.**

### Tier 2 — matters somewhat more

6. **Deterministic model routing (#50).** With four models on one endpoint, pinning `coder-strong` to plan/review and `fast` to titles is free quality. Opus users don't care.
7. **Todo tracking (#35).** A 30B model loses the thread on multi-step tasks much faster. An externalized checklist it must update is a cheap working-memory prosthesis. pi lacking it is a real gap.
8. **Tool-result truncation and aggressive compaction (#37, #39).** Small models degrade sharply as context fills — the effective usable window is well below the nominal 131k. pi's 2000-char tool-result truncation and `context` event are the best primitives here.
9. **Doom-loop guard (#49).** Weak models retry identical failing commands; opencode has a first-class control for it.
10. **LSP / serena grounding (#45).** Symbol-accurate navigation substitutes for the model's weaker code understanding. The user already wires serena into both.
11. **AGENTS.md discipline (#23).** Same value as for Opus, but the ≤200-line guidance is *stricter* here: a long, contradictory instruction file damages a 30B model much more.
12. **Git-commit-per-green-step instead of checkpointing (#40).** Cheaper and more reliable than CC's snapshots, and the user's TDD skill already mandates it.

### Tier 3 — matters LESS with a weak model

13. **Parallel subagents / agent teams (#8, #44).** On one GPU they serialize anyway and multiply context. Actively harmful.
14. **Auto mode / classifier permissions (#29).** Requires a Claude classifier; the local substitute (a second 30B pass) is both slower and less trustworthy than a static deny list.
15. **Extended thinking budgets (#33).** Qwen3.6's reasoning is not Opus's; long thinking mostly buys latency. And `supportsReasoningEffort:false` is *required* for llama.cpp-style servers anyway.
16. **Plugins/marketplaces, MCP prompts-as-commands, IDE integrations, background bash, structured `--json-schema` output, `#` shortcut, worktree isolation flags (#20, #22, #36, #48, #27, #10).** Convenience/distribution features. One user, one repo — near-zero value.
17. **Output styles (#34).** Changing tone is not the problem. (Exception: `keep-coding-instructions`-style *system-prompt replacement* to make prompts shorter and blunter can help a small model — that's pi's `SYSTEM.md`.)
18. **Skill `allowed-tools` (#2).** Solves prompt fatigue, not correctness.

### The one-line ranking
**turn on LSP+formatter > verification hooks > deny rules > skills-as-procedure > plan mode > context isolation > model routing > todos > compaction control > doom-loop guard > everything else.**

---

## 6. Porting the user's existing `agentic/opencode/` assets

### 6.1 What's actually there (verified by reading the files)

| Asset | Current format | Notes |
|---|---|---|
| `agents/{debugger,reviewer,tester}.md` | **opencode** (`mode: subagent`, `permission:` block) | ⚠️ **All three still point at `ollama/devstral:24b` and `ollama/code:opencode`**, but `opencode.json` now defines the `litellm/*` provider. These agents will fail or silently fall back. **Fix first.** |
| `commands/{brainstorm,commit,compound,implement,plan,review,ship}.md` | **opencode** (`description`, `agent`, `subtask`) | Clean; `review.md` uses `subtask: true` |
| `skills/*/SKILL.md` (10) | **Agent Skills spec-clean** | `name`, `description`, `license`, one `metadata`. Names match directory names. Portable as-is to CC, pi, Codex, Gemini CLI |
| `AGENTS.md`, `opencode.json` | opencode | `instructions: ["~/.config/opencode/AGENTS.md"]` |

**Verdict: the skills are already universal. The agents and commands are opencode-native.**

### 6.2 Compatibility table for the three targets

| Asset | → Claude Code | → opencode | → pi |
|---|---|---|---|
| `skills/*/SKILL.md` | ✅ drop into `.claude/skills/` verbatim | ✅ already native (also readable from `.claude/skills/`) | ✅ point `settings.json` `skills: ["<path>"]` at the directory, or symlink into `~/.pi/agent/skills/` |
| `commands/*.md` | ⚠️ rename `agent:` → n/a; `subtask: true` → `context: fork`; `$1..$3` OK; `` !`` `` and `@file` OK | ✅ native | ⚠️ → `.pi/prompts/*.md`; keep `description`; drop `agent`/`subtask`/`model`; `$ARGUMENTS`→`$@` works; **`` !`cmd` `` and `@file` are NOT supported** — must be rewritten |
| `agents/*.md` | ⚠️ `mode: subagent` → drop; `permission:{edit,bash}` → `tools:`/`disallowedTools:`/`permissionMode:`; `model:` → CC alias | ✅ native (fix the model ids) | ❌ **no subagent concept** — must become an extension |

### 6.3 What a converter would need to do

A `bin/agentsync` script (~200 lines) with three emitters. Layout facts it must respect: opencode now prefers **plural** dirs (`agents/`, `commands/`, `skills/`, `plugins/`, `tools/`) with singular kept for back-compat; **agents/commands recurse (`**/*.md`) but plugins/tools are flat (`*.`)**; and a nested agent file **keeps the slash in its name** (`agents/team/reviewer.md` → `team/reviewer`), unlike CC where identity comes only from the `name` field. The non-obvious parts:

**skills → all:** copy verbatim. Only real work: CC-only frontmatter keys (`allowed-tools`, `disable-model-invocation`, `argument-hint`, `context`, `paths`) must be **moved under `metadata:`** for opencode, because opencode recognizes *only* the six spec fields and will otherwise be lossy/noisy. For CC, emit them back to top level.

**commands ↔ skills:** CC has merged the two, so the highest-leverage move is to **author everything as a skill** and emit a thin opencode `commands/x.md` wrapper (`description` + `agent` + `subtask` + body = "Engage the **x** skill. $ARGUMENTS") — which is *exactly the pattern the user already uses*. Keep doing it; just generate the wrappers.

**opencode agent → CC agent:**
- `mode: subagent` → drop (implicit); `mode: primary` → has no CC equivalent, emit as an `--agent`-able definition
- `permission.edit: deny` → `disallowedTools: Edit, Write, NotebookEdit`
- `permission.bash: deny` → add `Bash` to `disallowedTools`
- `permission.bash: {"git push*": "deny"}` → **cannot be expressed in frontmatter**; emit a `permissions.deny: ["Bash(git push *)"]` entry into `.claude/settings.json` (note the space before `*`) or a `hooks:` PreToolUse entry
- `temperature`/`top_p` → **no CC equivalent** (CC controls this via effort); drop with a warning
- `steps` → `maxTurns`
- `model: litellm/coder` → CC alias or full id
- `hidden` → no equivalent; `color` → maps to CC `color` (named colors only, not hex)

**opencode agent → pi:** emit a TypeScript extension. Each agent becomes a registered tool:
```ts
pi.registerTool({ name: "task_reviewer", description: <the agent's description>,
  parameters: Type.Object({ prompt: Type.String() }),
  async execute(_id, { prompt }) {
    const { session } = await createAgentSession({
      systemPrompt: <agent body>, tools: ["read","grep","find","ls"],   // from permission:
      model: "litellm/coder-strong",
    });
    return { content: [{ type: "text", text: await session.prompt(prompt) }] };
  }});
```
Plus a companion `tool_call` extension implementing the deny table (`git push*`, `rm -rf*`, `sudo*`) that opencode gets for free.

**Direction of truth:** author in **opencode format + Agent Skills**, generate CC and pi. Not the reverse — opencode's `permission` block is more expressive than CC frontmatter and is what the user actually runs.

### 6.4 A CC-hooks-compatible shim (the highest-value new artifact)

Define one `hooks.json` in the CC contract subset the user actually needs — `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `UserPromptSubmit`, with `matcher`, `type: "command"`, exit-code 0/2 semantics and `hookSpecificOutput.{permissionDecision,additionalContext,updatedToolOutput}` — and write two ~150-line adapters:

- **opencode plugin**: `tool.execute.before` → build the CC JSON payload, spawn the command, exit 2 ⇒ `throw new Error(stderr)`; `tool.execute.after` → same, injecting `updatedToolOutput`. `Stop` has **no host support** — approximate with an outer supervisor that re-runs `opencode run --continue` while the verify command fails.
- **pi extension**: `tool_call` → `{block:true, reason:stderr}` on exit 2; `tool_result` → rewrite content; `agent_end`/`agent_settled` → on exit 2, `pi.sendUserMessage(stderr, {deliverAs:"followUp"})` — a **true** `Stop` hook; `input` → `UserPromptSubmit`; `before_agent_start` → `SessionStart` `additionalContext`.

Payoff: one hook script set works under Claude Code, opencode, and pi. Given §5, this is the highest-ROI thing to build.

---

## 7. Existing projects that bridge Claude Code features to open agents (2026)

| Project | URL | Status | What it gives you | Fit for a 30B local model |
|---|---|---|---|---|
| **Agent Skills standard** | <https://agentskills.io> · <https://github.com/agentskills/agentskills> (~23.7k★, active) | **Alive, the real answer** | The open SKILL.md spec + `skills-ref` validator (`skills-ref validate ./my-skill`) | ★★★★★ — validate the user's 10 skills in CI; guarantees CC/opencode/pi/Codex/Gemini portability |
| **anthropics/skills** | <https://github.com/anthropics/skills> (~165k★, active) | Alive | Reference skill collection + `spec/` + `template/`. Claude-flavored but spec-compliant | ★★★☆☆ — mine for structure/wording patterns |
| **opencode's built-in CC compat** | <https://opencode.ai/docs/skills/>, <https://opencode.ai/docs/rules/> | Alive, shipping (skills since **v1.0.186**, `.claude/skills` since **v1.0.208**) | Reads `.claude/skills/`, `~/.claude/skills/`, `CLAUDE.md`, `~/.claude/CLAUDE.md`; `OPENCODE_DISABLE_CLAUDE_CODE=1` / `..._PROMPT=1` / `..._SKILLS=1` to opt out. Does **not** read `.claude/agents/` or `.claude/commands/` | ★★★★★ — **no third-party shim needed for skills/memory** |
| **pi's CC compat** | <https://pi.dev/docs/latest/skills> | Alive | `"skills": ["~/.claude/skills","~/.codex/skills"]` in settings; reads `AGENTS.md` **or** `CLAUDE.md` | ★★★★★ |
| **claude-code-router** | <https://github.com/musistudio/claude-code-router> (~36.3k★, 734 commits, active) | Alive | Runs the **real Claude Code binary** against other providers via `http://127.0.0.1:3456`; conditional routing, fallbacks, key rotation, Docker. Explicitly lists OpenCode and Pi as supported clients | ★★★☆☆ — lets you use CC's hooks/plan mode/rewind with a local model, but you inherit CC's very long Anthropic-shaped system prompt and tool schemas, which a 30B model handles worse than opencode's leaner ones. Also check Anthropic ToS before pointing the CC client at non-Anthropic models |
| **LiteLLM `/v1/messages`** | <https://docs.litellm.ai/docs/anthropic_unified> | Alive | Anthropic-format `/v1/messages` + `/v1/messages/count_tokens` translating to `openai, anthropic, bedrock, vertex_ai, gemini, azure…`. Streaming, fallbacks, load balancing, cost tracking, thinking blocks (`budget_tokens`, `summary`) | ★★★★☆ — **the user already runs LiteLLM**, so this is a config change, not a new dependency. Caveat: guardrails are non-streaming-only; tool-use fidelity across the translation on a 30B model is the thing to actually test |
| **awesome-claude-code** | <https://github.com/hesreallyhim/awesome-claude-code> (~51.3k★) | Alive | Curated CC skills/agents/hooks/statuslines | ★★☆☆☆ — CC-specific, not cross-platform; useful as a source of hook scripts to port |

**Gap in the ecosystem (as of 2026-07-30, unverified-negative):** I found **no** maintained project that implements the *Claude Code hook JSON/exit-code contract* on top of opencode or pi. Skills portability is solved; hook portability is not. That is the space the §6.4 shim would fill.

---

## 8. Concrete recommendations, in order

**Bugs in the user's current config, found while researching — fix these first:**

- 🔴 **`"tools": {"skills*": true}` in `opencode.json` is a dead key.** The skills tool is singular `skill`; no `skills*` glob exists. It is silently doing nothing. Replace with `"permission": {"skill": {"*": "allow"}}` if you wanted to be explicit, or just delete it.
- 🔴 **`agent.build.temperature: 0.1` and `agent.plan.temperature: 0.1` are probably being dropped.** `models.<id>.temperature` is a **capability boolean defaulting to `false`** for custom providers, and the request builder omits temperature entirely when it's false. Add `"temperature": true` to each model entry under `provider.litellm.models.*`. (Also note: opencode's Qwen auto-tuning is a substring match on the model id — `coder`/`coder-strong` don't contain `qwen`, so nothing fires automatically.)
- 🔴 **All three `agents/*.md` still point at `ollama/devstral:24b` / `ollama/code:opencode`** while `opencode.json` defines only `litellm/*`. Retarget to `litellm/coder-strong` (reviewer) and `litellm/coder` (debugger, tester).
- ⚠️ **`instructions: ["~/.config/opencode/AGENTS.md"]` plus a project `AGENTS.md` is fine, but be aware AGENTS.md and CLAUDE.md do NOT stack** — first match per category wins.
- ⚠️ If you script `opencode run --format json`, **pass `--auto` or permission prompts are silently auto-rejected**, and there is **no terminal `done` event** — detect completion via `session.status == idle`.

**Then, in value order:**

1. **Set `"lsp": true` and `"formatter": true` in `opencode.json`.** Both are off by default and both give you an automatic, in-band verification loop (§5 Tier 0). Highest value per character typed in this whole report.
2. **Build the `Stop`-equivalent plugin for opencode**: on `event: session.idle`, run the verify command; if it fails, call `client.session.prompt()` with the failure text. The plugin already receives an SDK `client`, so this is a true in-process Stop hook, not an external supervisor loop.
3. **Add a `tool.execute.after` verification hook** on `edit`/`write` for anything the LSP can't catch (tests), and a `tool.execute.before` / `permission.ask` deny layer. Extend `opencode.json` `permission` with `doom_loop` and tighter bash globs.
4. **Validate all 10 skills with `skills-ref validate`** and add it to CI. Move any non-spec frontmatter under `metadata:`.
5. **Beef up skill `description` fields with literal trigger phrases** — a 30B model's skill routing is the weak link, and CC truncates at 1536 chars so there's room.
6. **Only then evaluate pi**, and only after writing (a) a permission/deny extension and (b) a todo tool — pi ships without both. pi's compensating advantages are real: `agent_end` → true `Stop` hook, `context` event for surgical context editing, `SYSTEM.md` full prompt replacement, 2000-char tool-result truncation, and `compat.supportsDeveloperRole/supportsReasoningEffort:false` for llama.cpp-style servers.
7. **Author once, generate three ways**: skills + opencode agents/commands as the source of truth; emit CC and pi artifacts with a converter. Keep the "thin command wraps a fat skill" pattern already in use.
8. **Skip**: agent teams, parallel subagents, plugin marketplaces, output styles, background bash, `--json-schema`. On one 3090 Ti they cost more than they return.
