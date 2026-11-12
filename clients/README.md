# Coding-agent clients → the coder stack

Client configs that point local coding agents at the rig's **LiteLLM** gateway
(`https://llm.tabaska.us/v1`) and its public aliases (`coder` = Qwen3.6 35B-A3B,
`coder-strong` = Qwen3.6 27B MTP, `fast` = Qwen2.5-Coder 7B, `utility` = Llama 3.2 3B).

| File | Deploy to | Tool |
|---|---|---|
| `opencode.json` (repo root — the maintained copy; `clients/opencode.json` + `agentic/opencode/opencode.json` are kept byte-identical to it) | `~/.config/opencode/opencode.json` | opencode |
| `../agentic/opencode/dcp.jsonc` | `~/.config/opencode/dcp.jsonc` | opencode (DCP plugin) |
| `../agentic/opencode/notification-ntfy.json` | `~/.config/opencode/notification-ntfy.json` | opencode (ntfy plugin) |
| `pi-models.json` | `~/.pi/agent/models.json` | pi.dev |
| `pi-auth.example.json` | `~/.pi/agent/auth.json` (chmod 0600) | pi.dev |
| `pithagoras/` | see *Pithagoras* below | Pithagoras web portal (pi 1.1) |

## opencode pin + plugins (lai-05)

- **Pinned version: `clients/opencode.version` (1.18.10)** on BOTH machines. Mac installs via
  Homebrew (`brew upgrade opencode && brew pin opencode`); rig via the standalone installer
  (`~/.opencode/bin/opencode upgrade $(cat clients/opencode.version)`). `"autoupdate": false`
  in opencode.json stops self-updates. The 1.0.x custom-provider forwarding regressions
  (anomalyco/opencode #5674/#5210/#971) are gone in 1.18.10 — re-verify with a real
  `opencode run -m litellm/utility …` after ANY version bump.
- **Plugin array (pinned in opencode.json):** `opencode-plugin-litellm@0.8.0` (auto-discovers
  the key's aliases from `/v1/models`; non-destructive merge over the hand-curated blocks),
  `cc-safety-net@1.0.6` (zero-LLM AST destructive-command guard),
  `@tarquinen/opencode-dcp@3.1.14` (context pruning — limits are PERCENTAGES in `dcp.jsonc`
  so they fit every local window, 32k fast … 256k coder), `opencode-notify@0.3.1` (desktop
  popups), `opencode-ntfy.sh@1.1.0` (push → `https://ntfy.tabaska.us` topic **`opencode`**;
  token file `~/.config/opencode/ntfy-token`, chmod 600, from vault `ntfy.opencode_token`),
  `opencode-token-tracker@1.7.1` (usage log under `~/.config/opencode/logs/token-tracker/`).
  **Curation rule (single-GPU llama-swap): nothing that fires background/parallel LLM calls** —
  do NOT add oh-my-opencode/oh-my-openagent, swarm/orchestration plugins, vibeguard, or
  opencode-supermemory.
- **`limit.context` mirrors `docker/llama-swap-config.yaml` `--ctx-size`** (coder 262144,
  coder-swarm 49152 = 196608/4 slots, coder-strong 114688, fast 32768, utility 131072).
  If a ctx-size changes there, change opencode.json to match.
- **MCP + per-agent tool globs:** servers = context7 (hosted), `fleet` (rig fleet-mcp
  streamable-HTTP, `http://cachyos.tailb31641.ts.net:8765/mcp` — tailnet name so the Mac
  reaches it off-LAN too), serena (local uvx; Mac needs `brew install uv`). ALL tool globs
  are **off globally** (`"tools": {"serena*"/"context7*"/"fleet*": false}`) and re-enabled
  per agent: build/plan get all three; subagents (debugger/reviewer/tester/rib in
  `agentic/opencode/agents/`) stay serena-only. opencode has no lazy tool loading — the
  glob allowlist is the token knob. mcpo's OpenAPI bridges are NOT wired here (opencode
  speaks MCP, mcpo speaks OpenAPI; the stdio servers can be added as `type: local` later).
- Drift guard: verification check `opencode-config-parity` (foss-setup
  `checks.d/local-ai.yaml`) asserts rig live config == repo root copies + pinned version;
  `opencode-run-probe` (daily) does a real `opencode run` through LiteLLM — its 07:15
  "Agent Idle" ping on the `opencode` ntfy topic is EXPECTED (doubles as a heartbeat).

## The key (ai-09)

All three read a LiteLLM **virtual key (`coding-agents`) scoped to q38/utility/strata** (lai-30 collapse; `strata` added 2026-10-22),
exported as `LITELLM_API_KEY`:

- `docker/.env` → `CODING_LITELLM_KEY` (canonical on-rig source; vault `ai_stack.litellm_coding_key`
  — backfilled into the vault by lai-05; the Mac exports the same key from `~/.zshenv`).
- `~/.bashrc` **and** `~/.bash_profile` export `LITELLM_API_KEY` from that value — both,
  because `~/.bashrc` early-returns for non-interactive shells while Orca spawns agents
  through `~/.bash_profile`. opencode's `{env:LITELLM_API_KEY}` consumes it.
  **pi does NOT** — corrected 2026-09-02 (lai-30): pi interpolates nothing in
  `auth.json` (nor in `models.json`'s `apiKey`), it sends the string verbatim, so the
  old `$LITELLM_API_KEY` literal made pi 401 against the gateway from 2026-07-29
  until it was replaced with the real key. Write the real key at 0600.
- Mint: `curl .../key/generate -d '{"models":["q38","utility"],...}'` — the lai-30 roster;
  coder/coder-strong/coder-swarm/fast no longer exist.

## Orca (Stably) — the orchestrator

Orca runs these agents (opencode / pi / codex / claude) in git-worktree workspaces;
the **LLM backend is configured per-agent** (the files above), not in Orca. With the
env in `~/.bash_profile`, Orca-spawned agent shells inherit the key + `PI_MODEL=litellm/coder`
automatically, and the coder models show up in Orca's per-agent model picker.

### ⚠️ VRAM: run Orca with GPU acceleration OFF

Orca is an Electron app. Left GPU-accelerated its Chromium process holds VRAM
(idle ~0.4 GB, **spiking to ~8 GB**), and the coder-stack big models are tuned as
<1 GiB-headroom edge fits — so `coder` (needs ~23.3 GB) **OOMs on load while Orca
runs on the GPU**. Launch Orca with `--disable-gpu` (a user `.desktop` override at
`~/.local/share/applications/stably-orca.desktop` sets `Exec=stably-orca --disable-gpu %U`);
the `stably-orca` wrapper forwards it to Electron. UI renders on CPU (fine for an IDE)
and the full model budget is restored.

## Pithagoras portal + REA decompilation (Mac, 2026-11-11)

[Pithagoras](https://github.com/thecodacus/pithagoras) (hosted web UI for pi) runs **natively** on the
Mac at `http://<mac>:4100` — not in Docker, because REA's Ghidra provider needs the macOS host
(and Docker Desktop host networking is unreliable). Checkout `~/GitHub/pithagoras` (build:
`PATH=/opt/homebrew/opt/node@24/bin:$PATH npm install && npm run build`; npm 11 script approvals
live in an untracked `.npmrc` so the in-app **Update** button's `git pull` stays clean).

- **Isolated pi.** The portal uses its bundled pi **1.1.x** (`node_modules/.bin/pi`) with
  `PI_CODING_AGENT_DIR=~/.local/share/pithagoras/pi-agent` — the global `~/.pi/agent` (pi 0.82)
  is untouched. That dir holds `models.json` (= `pi-models.json`), `auth.json` (0600, the
  coding-agents key — pi interpolates nothing), `settings.json` (= `pithagoras/pi-settings.json`,
  default `litellm/strata`) and `mcp.json` (= `pithagoras/pi-mcp.json`).
- **Node.** Pinned to keg-only Homebrew `node@24` — the PATH `node` is Hermes's bundled 26.8.1,
  which REA rejects (<26.12.1) and which Hermes updates can move under better-sqlite3.
- **Service.** `pithagoras/run.sh` → `~/.local/share/pithagoras/run.sh`; plist →
  `~/Library/LaunchAgents/us.tabaska.pithagoras.plist` (KeepAlive on non-zero exit, so the
  Update button's exit-75 restarts it). `PORTAL_SECRET` in `~/.local/share/pithagoras/secret.env`
  (0600). Log: `~/.local/share/pithagoras/portal.log`. Workspace root: `~/RE` (deliberately NOT
  `~/GitHub` — pi runs with no approval prompts and has write/bash tools).
- **REA** (`rea-agents` 6.8.0, `npm i -g`, at `~/.local/bin/rea`): registered with
  `PI_CODING_AGENT_DIR=… rea setup --client pi --yes` (skill → `~/.agents/skills/reverse-engineer-anything`).
  Provider = **Ghidra 12.1.4** at `~/.local/opt/ghidra_12.1.4_PUBLIC` (sha256-verified release zip)
  + Homebrew `openjdk@21`. The release zip ships **no mac_arm_64 decompiler** — built locally with
  `support/gradle/gradlew --no-daemon buildNatives` (JAVA_HOME=openjdk@21). Check:
  `rea doctor --client pi --json` (healthy) and `pi mcp list` (rea: connected, 229 tools, codemode).
- **The portal needs `pi-mcp-adapter`** — its chats ignore pi 1.1's built-in MCP loader, so without the
  adapter `mcp.json` entries are NOT tools in the portal (the CLI test passed while portal chats had no REA).
  Installed at the portal's own pin: `PI_CODING_AGENT_DIR=… pi install npm:pi-mcp-adapter@2.18.0`
  (= `ADAPTER_SPEC` in `core/server/src/api/mcp.ts`; Settings → MCP does the same), then restart the
  portal. REA tools then appear via the `mcp` gateway tool as `rea_<tool>` (e.g. `rea_open_binary`).
- **Verified 2026-11-11:** pi → LiteLLM `strata` → REA/Ghidra recovered the key check of a stripped
  arm64 sample (`~/RE/samples/crackme`) with correct pseudocode in ~1m45s.
- ⚠ pi will also **execute** targets to corroborate static findings — don't point it at untrusted
  binaries on the host; use a VM or `EXECUTOR=container`.
