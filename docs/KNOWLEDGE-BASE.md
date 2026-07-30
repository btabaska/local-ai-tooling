# Local AI Tooling — LLM Knowledge Base

> **Purpose.** A self-contained, evolving source of truth for LLMs/agents working in
> this repo. It captures the *current* state of the local AI stack so an agent can
> orient without re-scanning everything. **Keep it current** — when you change the
> stack, update the relevant section and the "Last verified" line below.
>
> **Last verified against repo:** 2026-07-30 (git `b24ca1d`, `ai-09`).
>
> **Authority order (when sources disagree):**
> 1. The **live running stack** on the rig (ground truth).
> 2. The **wiki** design doc — https://wiki.tabaska.us/architecture/local-ai-build/
>    (source: `foss-setup/wiki/docs/architecture/local-ai-build.md`).
> 3. The repo `README.md` + the config files (`docker/*.yaml`, `docker/*.json`).
> 4. This knowledge base (a derived summary — if it drifts, fix it against 1–3).
> 5. `docs/history/` and `docs/plans/` are **historical / point-in-time — NOT current truth.**

---

## 1. What this is (one paragraph)

The homelab's local-first AI stack, running on **one rig** on the LAN/tailnet.
Model serving is **llama-swap + llama.cpp `llama-server`** (Docker, CUDA via CDI)
behind a **LiteLLM** gateway that exposes stable public aliases and per-client
virtual keys. On top: Open WebUI (chat + RAG + fleet tools), two creative/RP
frontends (Marinara + Lumiverse), ComfyUI image-gen, a read-only fleet ops agent,
and coding-agent client configs (pi / opencode / Orca). **The single GPU is shared
by take-turns** between the LLM stack and ComfyUI, and **yields to gaming**
(idle-unload + Apollo session-start force-unload). No cloud fallback — rig down =
AI down (accepted single point of failure).

## 2. Hardware / host

- **Rig:** hostname `cachyos` / `cachybox.local`, LAN IP **192.168.10.12**.
- **CPU/RAM:** i7-12700K · 64 GB RAM.
- **GPU:** **single RTX 3090 Ti (24 GB VRAM)** — the central scarce resource.
- **Storage:** 5 TB NVMe. Model weights live in **`/opt/llm/models`** and
  **`/opt/comfyui/models`** — deliberately *outside* `/home` so restic never backs
  up ~160 GB of re-pullable weights.
- **OS:** CachyOS (Arch-based).
- **Docker:** ≥28, GPU via **CDI** (`/etc/cdi/nvidia.yaml` from `nvidia-ctk`, no
  `daemon.json` runtime change). Compose uses `devices: nvidia.com/gpu=all`.

## 3. Topology / request flow

```
any LAN/tailnet machine
  ├── opencode / pi   ──►  https://llm.tabaska.us   (LiteLLM :4000, virtual keys)
  ├── browser         ──►  https://ai.tabaska.us    (Open WebUI :3000, RAG + fleet tools)
  ├── creative/RP     ──►  marinara / lumiverse.tabaska.us  (scoped LiteLLM keys)
  ├── image-gen       ──►  comfyui.tabaska.us  (via gpu-arbiter :8189 take-turns proxy)
  └── HA Assist / Obsidian ──► Ollama SHIM :11434 (llama3.2:3b · tag:fast · nomic)

rig (192.168.10.12) ─ docker compose (docker/)
  LiteLLM :4000 ──► llama-swap :9292(→8080) ──► llama-server (one proc/model,
    on-demand load, ttl idle-unload, one big model at a time + CPU embedder)
  gpu-arbiter :8189 ──► take-turns between LLM stack and ComfyUI image gen
  fleet-mcp :8765 (systemd, host) ──► read-only ops tools (ssh rig/mini/nas)
  mcpo :8000/fleet ──► same tools bridged into Open WebUI
```

**TLS is NOT terminated on the rig.** The **mini's Caddy** fronts every public
hostname (`ai`/`llm`/`comfyui`/`marinara`/`lumiverse`.tabaska.us). Do not run a
second Caddy on the rig — `docker/Caddyfile.deprecated` is the retired bundled
config, `docker/Caddyfile` is a deprecation stub.

### Public hostnames → rig ports (via mini Caddy)
| Hostname | Rig port | Service |
|---|---|---|
| `llm.tabaska.us` | 4000 | LiteLLM gateway (OpenAI-compatible) |
| `ai.tabaska.us` | 3000 | Open WebUI |
| `comfyui.tabaska.us` | 8189 | gpu-arbiter → ComfyUI (NOT 8188 directly) |
| `marinara.tabaska.us` | 3002 | Marinara-Engine |
| `lumiverse.tabaska.us` | 3001 | Lumiverse |

## 4. The Docker stack (`docker/docker-compose.yml`)

Named volumes: `litellm_pgdata`, `open_webui_data`, `lumiverse-data`, `marinara-data`.

| Container | Image | Port(s) | GPU | Role |
|---|---|---|---|---|
| `litellm-db` | `postgres:16-alpine` | (internal) | no | Backs LiteLLM virtual keys + spend tracking |
| `litellm` | `ghcr.io/berriai/litellm:main-latest` | 4000 | no | Auth gateway + stable aliases (see §5) |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | 3000→8080 | no | Chat UI + RAG + web search + fleet tools |
| `mcpo` | `ghcr.io/open-webui/mcpo:main` | 8000 | no | Bridges stdio MCP servers → OpenAPI for OWUI |
| `llama-swap` | `ghcr.io/mostlygeek/llama-swap:cuda` | 9292→8080 | **yes (CDI)** | llama.cpp model server, on-demand swap |
| `lumiverse` | `ghcr.io/prolix-oc/lumiverse@sha256:baa8db4e…` (digest-pinned) | 3001→7860 | no | Creative/RP frontend |
| `marinara` | `ghcr.io/pasta-devs/marinara-engine:1.5.0` | 3002→7860 | no | Creative/RP + game engine (ALPHA) |
| `comfyui` | `mmartial/comfyui-nvidia-docker:latest` | 8188 | **yes (CDI)** | Image-gen backend |
| `gpu-arbiter` | `python:3.12-slim` (installs aiohttp) | 8189 | no | Take-turns GPU proxy in front of ComfyUI |

Key wiring notes:
- **Open WebUI rides LiteLLM only** (`ENABLE_OLLAMA_API=false`). RAG embeddings go
  through the `embed` alias; title/tag gen uses `TASK_MODEL_EXTERNAL=utility`.
  Web search = Kagi with `BYPASS_EMBEDDING_AND_RETRIEVAL=true` (full results into
  context, fixes "search ran but model says no results").
- Many OWUI env vars are **PersistentConfig** — they only seed a *fresh*
  `open_webui_data` volume; once in the DB they're authoritative. Change live
  settings in Admin → Settings (see `agentic/openwebui/SETUP.md`).
- `WEBUI_SECRET_KEY` must stay **stable** or saved tool/OAuth creds fail to decrypt.
- `mcpo` mounts `REPOS_PATH` (default `/home/btabaska/Documents/GitHub`) at `/repos`
  so serena can reach code.
- Containers reach host services (native Ollama shim, fleet-mcp) via
  `host.docker.internal` (added through `extra_hosts: host-gateway`).

## 5. LiteLLM gateway (`docker/litellm-config.yaml`)

**The single authenticated front door.** `model_name` is the *public alias*; the
model underneath can change without touching any client. Everything routes to
llama-swap at `http://llama-swap:8080/v1` (unauthenticated inside the compose net).

| Public alias | llama-swap model | Role |
|---|---|---|
| `coder` (+ legacy `code`) | `qwen3.6-35b-a3b` | Default coder — **bake-off winner** |
| `coder-strong` | `qwen3.6-27b` | Strong/slow coder for long/hard runs |
| `chat` | `gemma4-31b-qat` | General chat (default) |
| `chat-creative` | `deckard-heretic` | Creative / uncensored chat |
| `cydonia` | `cydonia-24b` | Creative / RP |
| `dolphin-venice` | `dolphin-venice-24b` | Uncensored/steerable RP |
| `goetia` | `goetia-24b` | Dark RP merge |
| `fast` | `qwen2.5-coder-7b` | Autocomplete / cheap tool loop |
| `utility` | `fast-3b` (Llama 3.2 3B) | Tagging/titles/classification (temp 0) |
| `embed` | `qwen3-embed` | RAG embeddings |

- `general_settings`: `master_key` + `database_url` from env.
- `litellm_settings`: `drop_params: true`, `request_timeout: 600` (cold loads +
  long agentic gens + swap queueing).
- `router_settings`: `simple-shuffle`, `num_retries: 2`.

## 6. Model serving (`docker/llama-swap-config.yaml`)

Each model = **one `llama-server` process**, spawned on first request, unloaded on
idle (`ttl`) or force-unloaded via `POST /api/models/unload`. Web UI/activity at
`http://rig:9292/ui`.

**Shared `srv` macro flags:** `-ngl 999 --flash-attn on --cache-type-k q8_0
--cache-type-v q8_0 --jinja --no-webui`.

**GPU policy:** big models are one-at-a-time (`big` group, `swap: true`,
`exclusive: true`) — loading one evicts the previous (NVMe reload is seconds). The
embedder (`embed` group) is `persistent: true` and CPU-pinned so it never contends.

**Measured context ceilings** (q8_0 KV + flash-attn, embedder CPU-pinned, ~1 GiB
desktop overhead — these are **edge fits, <1 GiB headroom**; the gaming force-unload
is the safety valve):

| Model | ctx | Notes |
|---|---|---|
| `qwen3.6-35b-a3b` | 262144 (native max, ~23.3G) | MoE; default `coder` |
| `qwen3.6-27b` | 114688 (~23.4G; 131072 OOMs) | dense, **MTP self-spec-decode ~50 t/s**; `--parallel 1` REQUIRED with MTP; do NOT send images (llama.cpp #23233 crash) |
| `gemma4-31b-qat` | 73728 (~23.7G; 81920 OOMs) | |
| `deckard-heretic` | 49152 (~23.8G; 65536 OOMs) | Gemma-4-31B finetune, Q4_K_M |
| `cydonia-24b` / `dolphin-venice-24b` / `goetia-24b` | 61440 | 73728 was text-only ceiling; dropped to 61440 to fit shared vision mmproj (~1.3G) |
| `qwen2.5-coder-7b` | 32768 (native max) | |
| `fast-3b` | 131072 (native max) | temp 0 (deterministic) |
| `qwen3-embed` | 4096 | CPU-only (`CUDA_VISIBLE_DEVICES=""`), `--pooling last`, batch 4096 |

- Sampling defaults per model = HF model-card recommendations (2026-07-16 sweep);
  clients may override per request.
- **Vision:** the three creative 24B models share ONE `mmproj-mistral-small-3.2-f16.gguf`
  projector (~0.82 GiB) via `--mmproj`.
- **Retired (ai-08, 2026-07-29):** `qwen3-coder-30b` + `devstral-24b` — served but had
  no LiteLLM alias (gateway-unreachable), redundant with the bake-off winners. Weights
  moved to `/opt/llm/models/archive/`.

## 7. Model weights inventory (`docker/models.manifest.yaml`)

The integrity + provenance record for every served GGUF (filename, byte size,
**sha256**, HF source repo/file, quant, which llama-swap model + LiteLLM alias it
backs). Exists because the weights are excluded from restic — this manifest +
configs ARE the backup, making `/opt/llm/models` provably rebuildable after NVMe loss.

- **Restore:** `scripts/fetch-models.sh` re-downloads every `served:` GGUF and
  verifies each sha256 (skips present+intact files). Needs `huggingface-cli` / `hf`.
- ~130 GB across 11 served GGUFs (10 models + 1 shared vision projector).
- `confidence: verified` = repo/quantizer embedded in GGUF header or named in config;
  `inferred` = deduced, confirm by sha256/size after download.
- `archived:` = on-disk-but-unserved rollback weights (retired coder models, pre-MTP
  27B dense, pre-Qwen3 nomic embedder).
- `ollama_shim:` = the 3 Ollama-store models (below); rebuilt via `ollama pull/create`.

## 8. GPU sharing (the central constraint)

The 24 GB card cannot hold a big LLM (~22.8 GiB at max ctx) AND an image model at
once, and it must yield to gaming. Three mechanisms:

1. **llama-swap `big` group** — one big model resident at a time; requests for
   another evict the current one. Embedder is persistent + CPU-pinned.
2. **`gpu-arbiter` (`docker/gpu-arbiter.py`, :8189)** — transparent reverse proxy in
   front of ComfyUI. On `POST /prompt` it force-unloads the LLM
   (`llama-swap /api/models/unload`, ~182 ms) *before* forwarding so ComfyUI never
   loads while 22 GiB of LLM is resident. A background watcher polls ComfyUI `/queue`
   and `POST /free`s ComfyUI when it drains so the LLM can reload. Proxies the `/ws`
   progress socket verbatim. **Frontends point their ComfyUI URL at :8189, never :8188.**
3. **Gaming yield** — `scripts/gpu-yield-unload.sh` (Apollo/Sunshine
   `global_prep_cmd` at session start) force-unloads everything (22.4 GiB → baseline
   in 182 ms). Reload is automatic on the next request. Must never block/fail a
   session start (short timeout, always `exit 0`).

## 9. Ollama compat shim (decommissioned as model server)

**Ollama is NOT the model server anymore.** It survives ONLY as a 3-model compat
shim on `:11434` for **HA Assist + Obsidian**: `llama3.2:3b`, `tag:fast` (derived
from 3b via `scripts/03-model-variants.sh`, num_ctx 8192 temp 0), `nomic-embed-text`.
Uses Ollama's own `~/.ollama` store, not `/opt/llm/models`. **Do NOT pull big models
into the shim.**

> ⚠️ Note: `docker-compose.yml` and some `scripts/` headers still contain *stale
> Ollama-native narration* (e.g. "Ollama stays NATIVE on the host"). These predate
> the ai-01 llama-swap migration; treat the migration (§6) as current truth.

## 10. Creative/RP frontends

Both are self-hosted chat UIs pointed at LiteLLM; the OpenAI-compatible connection
is created **in-app** (not via env). Connections live in each app's DB — reseed with
`scripts/seed-{marinara,lumiverse}-connections.sh` after a volume wipe. Both use
LiteLLM virtual keys scoped to `cydonia`/`dolphin-venice`/`goetia` (the only model
restriction, since neither app has a server-side allowlist).

- **Lumiverse** (`prolix-oc/Lumiverse`, TS+Bun) — image `:latest` **pinned by digest**
  (no semver tags; past v1.0.0 that patched CVE-2026-44449). `TRUST_ANY_ORIGIN=false`,
  CORS locked to `https://lumiverse.tabaska.us`.
- **Marinara-Engine** (`pasta-devs/marinara-engine:1.5.0`, ALPHA, AGPL-3.0) —
  `PROVIDER_LOCAL_URLS_ENABLED=true` to reach the private LiteLLM URL. **Its own
  Basic Auth is structurally ineffective behind Docker's userland-proxy** (app only
  sees a trusted private/Docker source IP), so **the enforcing gate is the mini
  Caddy's `basic_auth`**. Includes a pinned patch mount
  (`patches/bot-browser-chartavern.routes.js`) fixing CharacterTavern's moved card
  CDN — **remove that mount when bumping the image** if upstream fixes it.

## 11. Image generation (ComfyUI + `comfyui-workflows/`)

- ComfyUI models in `/opt/comfyui/models` (BASE_DIRECTORY=/basedir). CORS enabled
  (`--enable-cors-header`) for browser-side clients. Always driven through the
  gpu-arbiter (:8189).
- `comfyui-workflows/` holds verified workflows in several formats:
  - root `*.api.json` — API-format workflows (realistic Z-Image Turbo, NoobAI-XL
    anime, Flux.2 Klein, img2img x2, NSFW variants).
  - `hq/` — high-quality variants (`*.api.json`).
  - `ui/` — GUI-sidebar (UI-format) versions.
  - `marinara/` — Marinara `%prompt%`/`%seed%` placeholder-format workflows.
  - Generators: `gen-workflows.py`, `gen-nsfw.py`; converters `convert-ui.sh`,
    `../scripts/comfyui-api-to-ui.py`.
- Model families: **Z-Image Turbo** (realistic), **NoobAI-XL** (anime),
  **Flux.2 Klein** (incl. 9B + instruction-edit).

## 12. Ops agent + RAG (`ops/`)

Read-only fleet inspection exposed as MCP tools; **the tools ARE the skills library**
(add an `@mcp.tool()`, restart the service, every surface picks it up).

- `fleet_mcp.py` — FastMCP streamable-http server on rig `:8765/mcp`. **Read-only by
  construction:** host enum (rig/mini/nas), unit-name regex, capped output, URL
  allowlist, no arbitrary-command tool. SSH via `fleet-mini`/`fleet-nas` (key
  `from=`-restricted on remotes).
- `fleet-mcp.service` — systemd unit; env from `~/.config/fleet-mcp/env`
  (`HEALTHCHECKS_API_KEY`, `LITELLM_API_KEY` — values in the foss-setup vault).
- `ops-agent.sh` — interactive ollmcp TUI → LiteLLM (`coder`) → tools, **HIL approval
  ON** (keep it on).
- `ops_probe.py` — non-interactive one-shot loop (drives the `rig-ops-agent-e2e`
  verification check).
- **Tools (v1):** `list_hosts`, `service_status`, `journal_tail`, `list_containers`,
  `container_logs`, `system_overview`, `check_url` (allowlist),
  `run_verification_checks`, `gpu_status`, `healthchecks_summary`.
- **Surfaces:** ollmcp (`ops-agent.sh`), Open WebUI (via mcpo `/fleet`), `ops_probe.py`.
- **Security:** trusted-VLAN-only (UFW allows :8765 from 192.168.10.0/24 + docker
  bridge only, NOT tailnet). nas has no docker socket for the ssh user (container
  tools error there by design).
- **RAG:** Open WebUI over the `#homelab-wiki` collection, synced daily from Forgejo.

## 13. Coding-agent clients (`clients/` + `opencode.json`) — ai-09

Point local coding agents (pi / opencode) and Orca-launched agents at LiteLLM
(`https://llm.tabaska.us/v1`) using a virtual key scoped to
`coder`/`coder-strong`/`fast`/`utility`, exported as **`LITELLM_API_KEY`**.

- Canonical key source: `docker/.env` → `CODING_LITELLM_KEY` (vault
  `ai_stack.litellm_coding_key`).
- Both `~/.bashrc` **and** `~/.bash_profile` export `LITELLM_API_KEY` (bashrc
  early-returns for non-interactive shells; Orca spawns via bash_profile).
- Client files:
  - `opencode.json` (repo root — the maintained copy) → `~/.config/opencode/opencode.json`.
    Defines the `litellm` provider, `build`/`plan` agents, MCP (context7 + serena),
    permissions.
  - `clients/pi-models.json` → `~/.pi/agent/models.json`.
  - `clients/pi-auth.example.json` → `~/.pi/agent/auth.json` (chmod 0600).
- **Orca (Stably)** orchestrates agents in git-worktree workspaces; LLM backend is
  configured per-agent (the files above), not in Orca.
- ⚠️ **Run Orca with GPU acceleration OFF** (`stably-orca --disable-gpu`). Its Chromium
  process otherwise holds VRAM (idle ~0.4 GB, spiking ~8 GB), which OOMs the
  <1 GiB-headroom `coder` load.

## 14. The bake-off (`bakeoff/`)

Reusable agentic bake-off harness that chose `coder`. Tasks: `bugfix`, `feature`,
`refactor` (each a prompt + pytest). `harness.py` runs a model through the tool loop
and logs turns/malformed-calls/tok-per-sec/success to `results/results.jsonl`.

**Result (2026-07-15):** `qwen3.6-35b-a3b` won — 3/3 tasks, 0 malformed tool calls,
fewest turns, 60–126 tok/s (vs 27b dense at 23–47 tok/s). 35b-a3b became `coder`; 27b
kept as `coder-strong` for long/hard runs. `qwen3-coder-30b` and `devstral-24b` were
also benched (30b passed but was later retired; devstral failed both quick tasks).
`ctx-ceiling-probe.sh` measures the per-model VRAM/context ceilings in §6.

## 15. `scripts/` reference

| Script | Purpose |
|---|---|
| `bootstrap.sh` | Chains 00→03 + `docker compose up`. ⚠️ Steps still reference Ollama-native tuning (pre-migration). |
| `00-preflight.sh` | Preflight checks. |
| `01-ollama-tune.sh` | Legacy Ollama tuning (shim era). |
| `02-firewall.sh` | UFW/firewall rules (LAN subnet). |
| `03-model-variants.sh` | Builds Ollama shim variants (`tag:fast`). |
| `fetch-models.sh` | Restore `/opt/llm/models` from `models.manifest.yaml` + verify sha256. |
| `healthcheck.sh` | Probe every endpoint + show GPU/loaded models. ⚠️ Still probes the Ollama shim ports. |
| `gpu-yield-unload.sh` | Apollo session-start force-unload hook. |
| `seed-marinara-connections.sh` / `seed-lumiverse-connections.sh` | Rebuild in-app LLM+ComfyUI connections after a volume wipe. |
| `seed-owui-prompt-presets.py` | Seed the 2 ComfyUI-prompt presets in Open WebUI. |
| `comfyui-api-to-ui.py` | Convert ComfyUI API workflows → UI format. |

## 16. Secrets & env (`docker/.env.example`)

- Copy `docker/.env.example` → `docker/.env` and fill from the vault. `.env` is
  gitignored; **no real secret values in the repo**.
- Every key documents its **vault path** (`-> vault <path>`), the durable second
  source in `foss-setup/.handoff-secrets.yaml` (so rig-disk loss ≠ secret loss).
- Keys: `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY` (⚠️ immutable after models added),
  Postgres creds, `WEBUI_SECRET_KEY` (⚠️ keep stable), `KAGI_SEARCH_API_KEY`,
  `OPENWEBUI_LITELLM_KEY`, `CODING_LITELLM_KEY`, `LUMIVERSE_*`, `MARINARA_*`,
  `REPOS_PATH`, `AI_HOST`.

## 17. Publishing (dual-remote — do not forget)

Every commit must land in **both** remotes:
- `origin` → `git@github.com:btabaska/local-ai-tooling.git` (GitHub)
- `forgejo` → `forgejo:home/local-ai-tooling` (self-hosted, `git.tabaska.us`, mini:2222)

```sh
git push origin main && git push forgejo main
git push origin --tags && git push forgejo --tags   # when tags change
```

The rig's `forgejo` push uses `~/.ssh/id_forgejo` (`ssh -T forgejo` to verify).
Pushing only GitHub leaves the Forgejo mirror stale (the `ai-tooling-clean-pushed`
check trips if this repo is left dirty or unpushed). Monitoring lives in the
**foss-setup** repo (`verification/checks.d/rig.yaml`, deployed to the mini runner).

## 18. Directory map

| Path | What |
|---|---|
| `docker/` | The compose stack + all serving configs (`docker-compose.yml`, `litellm-config.yaml`, `llama-swap-config.yaml`, `gpu-arbiter.py`, `mcpo-config.json`, `models.manifest.yaml`, `.env.example`, `patches/`, deprecated Caddy). |
| `scripts/` | Bootstrap/tune/firewall/healthcheck, model fetch, GPU-yield hook, seeders. |
| `ops/` | Read-only fleet-mcp tools + ollmcp launcher + ops_probe + systemd unit. |
| `bakeoff/` | Agentic bake-off harness + results (how `coder` was chosen). |
| `comfyui-workflows/` | Verified ComfyUI workflows (api/ui/hq/marinara formats) + generators. |
| `clients/` + `opencode.json` | pi / opencode client templates + the maintained opencode config. |
| `agentic/` | Agent-layer design rationale (OpenCode harness philosophy) + OWUI SETUP.md. ⚠️ Ollama-era specifics predate the migration. |
| `docs/plans/` | Point-in-time plans — historical, not current. |
| `docs/history/` | Retired build-handoffs (INSTRUCTIONS, HANDOFF-ai-01/02, legacy README) — historical, not current. |
| `docs/KNOWLEDGE-BASE.md` | **This file.** |
| `README.md` | Repo entry point (layout, setup, rebuild, publishing). |

## 19. Rebuild path (short)

```bash
cd ~/Documents/GitHub/local-ai-tooling
cp docker/.env.example docker/.env && $EDITOR docker/.env   # fill from vault
./scripts/fetch-models.sh                                   # restore /opt/llm/models (verifies sha256)
cd docker && docker compose up -d
../scripts/healthcheck.sh
# rebuild Ollama shim: ollama pull llama3.2:3b nomic-embed-text; scripts/03-model-variants.sh
# reseed frontend connections: scripts/seed-{marinara,lumiverse}-connections.sh
```

## 20. Known caveats / gotchas (quick index)

- **Edge VRAM fits** — every big model is tuned <1 GiB headroom; any extra GPU use
  (game, Orca on GPU, big browser WebGL) can OOM a fresh load. Gaming force-unload is
  the safety valve.
- **MTP (`qwen3.6-27b`)** — `--parallel 1` required; never send images (crash).
- **Marinara Basic Auth** is ineffective behind Docker userland-proxy → the mini
  Caddy is the real gate.
- **OWUI PersistentConfig** — env only seeds a fresh volume; change live settings in
  Admin UI.
- **`WEBUI_SECRET_KEY` / `LITELLM_SALT_KEY`** — must not change after setup.
- **Frontends → gpu-arbiter :8189**, never ComfyUI :8188 directly.
- **Stale Ollama-native narration** persists in some compose/script comments — the
  llama-swap migration (ai-01) is current truth.
- **Dual-remote push** — GitHub *and* Forgejo, every time.
- **Marinara CharacterTavern patch mount** — remove when bumping the image if upstream fixes it.

---

### Maintenance protocol for this file
When you change the stack: update the affected section, bump the "Last verified"
date + git ref at the top, and note anything newly retired/added. If a section
drifts from the live configs, the configs win — fix the section.
