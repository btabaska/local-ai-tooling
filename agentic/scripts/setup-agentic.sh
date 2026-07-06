#!/usr/bin/env bash
# setup-agentic.sh — Install the OpenCode agentic toolchain on a CLIENT machine and (optionally)
# pull the recommended models if run on the rig itself.
#
# Client tooling installed: opencode, uv (for Serena + uvx MCP servers), repomix.
# Configs placed into ~/.config/opencode/ (agents, commands, skills, opencode.json, AGENTS.md).
# Idempotent-ish: safe to re-run; it backs up an existing opencode.json.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"   # agentic/
OC_DIR="$HOME/.config/opencode"

info() { printf '\033[36m==>\033[0m %s\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }

# ── 1. uv (Astral) — runs Serena and any uvx-based MCP server ──────────────────
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
else ok "uv present: $(uv --version)"; fi

# ── 2. OpenCode ────────────────────────────────────────────────────────────────
if ! command -v opencode >/dev/null 2>&1; then
  info "Installing OpenCode…"
  if command -v paru >/dev/null 2>&1; then paru -S --noconfirm opencode-bin || curl -fsSL https://opencode.ai/install | bash
  else curl -fsSL https://opencode.ai/install | bash; fi
else ok "opencode present: $(opencode --version 2>/dev/null | head -1)"; fi

# ── 3. repomix — pack a repo into one AI-friendly file (one-shot context) ──────
if ! command -v repomix >/dev/null 2>&1; then
  info "Installing repomix…"
  if command -v bun >/dev/null 2>&1; then bun add -g repomix
  elif command -v npm >/dev/null 2>&1; then npm install -g repomix
  else echo "  (skip: no bun/npm — you can always use 'npx repomix' on demand)"; fi
else ok "repomix present"; fi

# ── 4. Warm Serena once (downloads language servers on first run) ──────────────
info "Priming Serena (first run fetches language servers; Ctrl-C after it prints the dashboard URL)…"
echo "    uvx --from git+https://github.com/oraios/serena serena --help"
uvx --from git+https://github.com/oraios/serena serena --help >/dev/null 2>&1 && ok "Serena reachable via uvx" || \
  echo "  (Serena will still install on first OpenCode use.)"

# ── 5. Place OpenCode configs ─────────────────────────────────────────────────
info "Installing OpenCode configs into $OC_DIR"
mkdir -p "$OC_DIR/agents" "$OC_DIR/commands" "$OC_DIR/skills"
if [[ -f "$OC_DIR/opencode.json" ]]; then
  cp "$OC_DIR/opencode.json" "$OC_DIR/opencode.json.bak.$(date +%s)"
  echo "  (backed up existing opencode.json)"
fi
cp "$HERE/opencode/opencode.json" "$OC_DIR/opencode.json"
cp "$HERE/opencode/AGENTS.md"     "$OC_DIR/AGENTS.md"
cp "$HERE/opencode/agents/"*.md   "$OC_DIR/agents/"      2>/dev/null || true
cp "$HERE/opencode/commands/"*.md "$OC_DIR/commands/"    2>/dev/null || true
cp -r "$HERE/opencode/skills/"*   "$OC_DIR/skills/"      2>/dev/null || true
ok "Configs, agents, commands, and the example skill installed"
echo "  Reminder: edit $OC_DIR/opencode.json and set your rig's host (cachybox.local -> your IP/Tailscale name)."

# ── 6. Models — only if this box IS the rig (has ollama) ──────────────────────
if command -v ollama >/dev/null 2>&1; then
  info "Ollama detected on this machine — pulling the model roster."
  ollama pull qwen3.6:27b             # DEFAULT driver — flagship-level coding, dense (~22GB)
  ollama pull qwen3.6:35b-a3b         # speed/context option — MoE ~3B active, fast + lean
  ollama pull devstral:24b            # agentic alternative, clean multi-file diffs (~14GB)
  ollama pull gemma4:31b-it-qat       # you wanted to test this (~18GB)
  ollama pull nomic-embed-text        # embeddings

  # 64k coding variants so Qwen3-Coder and Gemma can also drive Build mode (Qwen3.6 is 256K-native).
  # If Ollama serves a short default context, set OLLAMA_CONTEXT_LENGTH=65536 (see base stack 01-ollama-tune.sh).
  # 18-22GB weights + 64k KV is tight on 24GB — watch `ollama ps`; drop to 49152/32768 if it offloads to CPU.
  if ! ollama list | grep -q '^code:opencode'; then
    printf 'FROM qwen3-coder:30b\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.1\n' > /tmp/Modelfile.code
    ollama create code:opencode -f /tmp/Modelfile.code
  fi
  printf 'FROM gemma4:31b-it-qat\nPARAMETER num_ctx 65536\nPARAMETER temperature 0.1\n' > /tmp/Modelfile.g4
  ollama create gemma4-code:64k -f /tmp/Modelfile.g4
  ok "Models ready: qwen3.6:27b (default), qwen3.6:35b-a3b, devstral:24b, gemma4:31b-it-qat, gemma4-code:64k, code:opencode, nomic-embed-text"
else
  echo
  info "No Ollama here (this is a client). On the RIG, run:"
  echo "    ollama pull devstral:24b"
  echo "    # code:opencode (64k qwen3-coder) is built by the base stack's 03-model-variants.sh"
fi

echo
ok "Done. Launch: cd <a repo> && opencode  → run /init to generate its AGENTS.md, then /models to pick."
echo
info "The brainstorm→plan→TDD→review→compound skills are installed and auto-trigger. Optional upstream:"
echo "  Superpowers (TDD) and Compound Engineering both support OpenCode via their bundled CLIs —"
echo "  but they assume cloud-scale parallel agents. This local set is the hardware-tuned equivalent."
echo "  See agentic/README.md §'TDD + compound skill set' for the tradeoff before layering them on."
