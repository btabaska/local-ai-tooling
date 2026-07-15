# HANDOFF — ai-01 Local-AI buildout (EXECUTED 2026-07-15)

> **Status: executed.** This is the operator handoff that drove the ai-01
> build on 2026-07-14/15. Kept for the record — the *shipped* reality is
> documented in the wiki (`architecture/local-ai-build.md`) and this repo's
> README/config comments. Where this doc and the wiki disagree, the wiki wins.

## The mandate (as issued)

Build the homelab's local-AI initiative end-to-end into a genuinely useful,
24/7, "it just works" stack on the rig's single RTX 3090 Ti (24 GB):
migrate the model server from **Ollama to llama.cpp** (llama-server managed by
**llama-swap**, LiteLLM kept as the authenticated gateway), and deliver:

1. **Agentic coding** — opencode (+ pi.dev evaluated) against local models,
   from any LAN/tailnet machine, after a real tool-calling bake-off.
2. **Ops/Q&A + RAG** — Open WebUI with RAG over the homelab wiki, kept fresh.
3. **LAN ops agent** — ollmcp + read-only MCP fleet-inspection tools,
   human-in-the-loop, Trusted-VLAN only.
4. **Skills/tools library** — versioned in this repo (ops/).

Hard constraints (all honored): 24 GB VRAM ceiling; rig-only (accepted SPOF);
**AI yields to gaming** (llama-swap idle-unload + Apollo session-start
force-unload hook); no cloud fallback; llama.cpp/llama-swap runtime (not
vLLM/Ollama); LiteLLM auth on; HA Assist must survive the Ollama decommission
(it did — via the 3-model compat shim on :11434).

Validation spikes required first (all done): (a) GPU-yield handoff latency —
measured **182 ms**; (b) RAG fit — embedder + coder co-resident at 20.4 GiB
proven; (c) exl2/TabbyAPI on Ampere — evaluated, **stay GGUF** (quant
availability for week-old models + MTP GGUFs + llama-swap swapping outweigh
exl2's single-user speed edge); (d) model bake-off — run on a real
edit→test→fix loop; **qwen3.6-35b-a3b won** (3/3 tasks, 0 malformed tool
calls, ~3x faster than the 27B dense, which stays as `coder-strong`).

## Where things landed

- `docker/docker-compose.yml` + `docker/llama-swap-config.yaml` — model server
- `docker/litellm-config.yaml` — public aliases (coder/coder-strong/chat/…)
- `scripts/gpu-yield-unload.sh` — Apollo global_prep_cmd hook
- `bakeoff/` — the reusable agentic bake-off harness + results
- `ops/` — fleet-mcp tools, ollmcp launcher, ops_probe, README
- `clients/` — opencode + pi.dev client templates
- checks: foss-setup `verification/checks.d/rig.yaml` (ai-01 block)
