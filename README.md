# Local AI Stack — the rig (RTX 3090 Ti) → your whole fleet

The homelab's local-first AI stack, on the rig's single **RTX 3090 Ti (24 GB)**.
Model serving is **llama-swap + llama.cpp `llama-server`** (Docker, CUDA via CDI)
behind the **LiteLLM** gateway; creative/RP frontends + ComfyUI image-gen; a
read-only ops agent over the fleet; and wiki-grounded RAG. GPU **yields to
gaming** (idle-unload + Apollo session-start force-unload hook, 182 ms measured).
No cloud fallback (rig down = AI down, accepted SPOF).

**Hardware:** i7-12700K · 64 GB RAM · RTX 3090 Ti (24 GB) · 5 TB NVMe · CachyOS.

> ## → The canonical design doc lives in the wiki
> This README is the **repo entry point** (layout, setup, rebuild, publishing).
> The **shipped design, model lineup, VRAM ceilings, bake-off, and daily-use
> guide** are the single source of truth in the wiki, kept current against the
> running stack:
>
> **https://wiki.tabaska.us/architecture/local-ai-build/**
> (source: `foss-setup/wiki/docs/architecture/local-ai-build.md`)
>
> Where anything in this repo and the wiki disagree, **the wiki is live truth.**

---

## What's running (one-screen orientation)

```
any LAN/tailnet machine
  ├── opencode / pi  ──►  https://llm.tabaska.us   (LiteLLM :4000, virtual keys)
  ├── browser        ──►  https://ai.tabaska.us    (Open WebUI :3000, RAG + fleet tools)
  ├── creative/RP    ──►  marinara / lumiverse.tabaska.us  (scoped LiteLLM keys)
  ├── image-gen      ──►  comfyui.tabaska.us  (via gpu-arbiter :8189 take-turns proxy)
  └── HA Assist / Obsidian ──► Ollama SHIM :11434 (llama3.2:3b · tag:fast · nomic)
                                     │
rig (192.168.10.12) ─ docker compose (local-ai-tooling/docker/)
  LiteLLM :4000 ──► llama-swap :8080(→9292) ──► llama-server (one proc/model,
    on-demand load, ttl idle-unload, one big model at a time + CPU embedder)
  gpu-arbiter :8189 ──► take-turns between LLM and ComfyUI image gen
  fleet-mcp :8765 (systemd, host) ──► read-only ops tools (ssh rig/mini/nas)
  mcpo :8000/fleet ──► same tools bridged into Open WebUI
```

- **Model server:** llama-swap + llama.cpp. **Ollama is decommissioned as the
  model server** — it survives *only* as a 3-model compat shim on `:11434`
  (`llama3.2:3b`, `tag:fast`, `nomic-embed-text`) for HA Assist + Obsidian.
  **Do not pull big models into the shim.**
- **Gateway:** LiteLLM (`:4000`) — stable public aliases (`coder`/`coder-strong`/
  `chat`/`fast`/`utility`/`embed`/the creative trio), per-client virtual keys,
  spend logging. Clients never change when the model behind an alias does. The
  full alias→model table + measured context ceilings are in the wiki.
- **Creative/RP:** Marinara + Lumiverse frontends, three Mistral-Small-24B
  finetunes (`cydonia`/`dolphin-venice`/`goetia`, vision-enabled), plus ComfyUI
  image-gen; the **gpu-arbiter** alternates the LLM and image model on the one
  card. Connections live in each app's DB — reseed with
  `scripts/seed-{marinara,lumiverse}-connections.sh`.
- **Ops + RAG:** `ops/` = read-only fleet-mcp tools + ollmcp/ops_probe agent;
  Open WebUI RAG over the `#homelab-wiki` collection (synced daily from Forgejo).

---

## Repo layout

| Path | What |
|---|---|
| `docker/` | The compose stack: `docker-compose.yml`, `llama-swap-config.yaml`, `litellm-config.yaml`, `gpu-arbiter.py`, `mcpo-config.json`, `models.manifest.yaml`, `patches/`. |
| `docker/.env.example` | Every env key with its **vault path** (ai-04, full parity; zero secret values). Copy to `docker/.env` and fill from vault `ai_stack.*` / `litellm.*` / `open_webui.*`. |
| `docker/models.manifest.yaml` + `scripts/fetch-models.sh` | Model-weight inventory (sha256/source/quant/alias) + restore script — makes `/opt/llm/models` rebuildable after NVMe loss (ai-06). |
| `scripts/` | Bootstrap/tune/firewall/healthcheck, `gpu-yield-unload.sh` (Apollo hook), `fetch-models.sh`, ComfyUI + seed helpers. |
| `ops/` | fleet-mcp read-only tools + ollmcp launcher + ops_probe (see `ops/README.md`). |
| `bakeoff/` | The reusable agentic bake-off harness + results (how `coder` was chosen). |
| `comfyui-workflows/` | Verified ComfyUI API/UI workflows (realistic/anime/flux, img2img, hq variants). |
| `clients/` + `opencode.json` | opencode + pi client templates. |
| `agentic/` | Agent-layer design rationale (OpenCode harness philosophy). **Note:** its Ollama-era specifics predate the llama-swap migration — the wiki is current truth. |
| `docs/history/` | **Point-in-time build handoffs, retired — NOT current truth.** See below. |

Model weights live in **`/opt/llm/models` on the rig, outside `/home`** — restic
never backs up re-pullable weights. The manifest + configs are the backup.

---

## Setup / rebuild (rig)

Full rebuild reasoning is in the wiki. The short version:

```bash
cd ~/Documents/GitHub/local-ai-tooling

# 1. Secrets — copy the template and fill every key from the vault
cp docker/.env.example docker/.env
$EDITOR docker/.env                 # each key documents its vault path (ai-04)

# 2. Model weights (after an NVMe loss) — restore /opt/llm/models from the manifest
./scripts/fetch-models.sh           # driven by docker/models.manifest.yaml (ai-06)

# 3. Bring up the stack
cd docker && docker compose up -d

# 4. Verify
../scripts/healthcheck.sh
```

HTTPS/TLS is **not** terminated on the rig — the mini's Caddy fronts every rig
service (`ai`/`llm`/`comfyui`/`marinara`/`lumiverse`.tabaska.us). Do not run a
second Caddy on the rig (`docker/Caddyfile.deprecated` is the retired bundled
config, kept for reference only).

Monitoring: consumer-end checks live in the **foss-setup** repo
(`verification/checks.d/rig.yaml`), deployed to the mini runner.

---

## Publishing — push to BOTH remotes

This repo is dual-remoted, like the rest of the fleet (mirrors the
`home/docker-stacks` precedent + `foss-setup/scripts/docs/publish-deploy.sh`).
Every commit must land in **both**:

- `origin` → `git@github.com:btabaska/local-ai-tooling.git` (GitHub)
- `forgejo` → `forgejo:home/local-ai-tooling` (self-hosted, `git.tabaska.us`, mini:2222)

```sh
git push origin main && git push forgejo main
git push origin --tags && git push forgejo --tags   # when tags change
```

The rig's `forgejo` push uses the dedicated `~/.ssh/id_forgejo` **user** key
("rig-workstation"); verify with `ssh -T forgejo`. Pushing only GitHub leaves the
Forgejo mirror stale — the exact single-remote-island drift ai-02 closed on
2026-07-29. (The `ai-tooling-clean-pushed` check trips if this repo is left dirty
or unpushed.)

---

## Historical docs — `docs/history/`

The original build-handoff docs were **retired here** (ai-07, 2026-07-29): they
described what was *planned/built* at a point in time and, in places, the
pre-migration Ollama-native design — they no longer reflect the running stack.
They are kept for the record with historical banners; **do not treat them as
current**. Current truth = this README + the wiki design page.

- `docs/history/INSTRUCTIONS.md` — the original Ollama-native rig+MacBook setup walkthrough (pre-ai-01).
- `docs/history/HANDOFF-ai-01.md` — the ai-01 llama.cpp migration build handoff.
- `docs/history/HANDOFF-ai-02-frontend-wiring.md` — the ai-02 Marinara/Lumiverse wiring handoff (still-useful frontend quirks, captured for reference).
- `docs/history/legacy-ollama-native-README.md` — the pre-ai-01 README's Ollama-native design narrative.
