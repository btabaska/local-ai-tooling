# Coding-agent clients → the coder stack

Client configs that point local coding agents at the rig's **LiteLLM** gateway
(`https://llm.tabaska.us/v1`) and its public aliases (`coder` = Qwen3.6 35B-A3B,
`coder-strong` = Qwen3.6 27B MTP, `fast` = Qwen2.5-Coder 7B, `utility` = Llama 3.2 3B).

| File | Deploy to | Tool |
|---|---|---|
| `opencode.json` (repo root — the maintained copy) | `~/.config/opencode/opencode.json` | opencode |
| `pi-models.json` | `~/.pi/agent/models.json` | pi.dev |
| `pi-auth.example.json` | `~/.pi/agent/auth.json` (chmod 0600) | pi.dev |

## The key (ai-09)

All three read a LiteLLM **virtual key scoped to coder/coder-strong/fast/utility**,
exported as `LITELLM_API_KEY`:

- `docker/.env` → `CODING_LITELLM_KEY` (canonical on-rig source; vault `ai_stack.litellm_coding_key`).
- `~/.bashrc` **and** `~/.bash_profile` export `LITELLM_API_KEY` from that value — both,
  because `~/.bashrc` early-returns for non-interactive shells while Orca spawns agents
  through `~/.bash_profile`. pi's `auth.json` (`$LITELLM_API_KEY`) and opencode's
  `{env:LITELLM_API_KEY}` both consume it.
- Mint: `curl .../key/generate -d '{"models":["coder","coder-strong","fast","utility"],...}'`.

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
