#!/usr/bin/env bash
# ops-agent.sh — interactive homelab ops agent (ai-01).
# ollmcp TUI -> LiteLLM (q38 alias) -> fleet-mcp read-only tools.
# Human-in-the-loop tool approval is ON by default in ollmcp; keep it on.
# Trusted-VLAN only: run this on the rig (or via ssh rig -t).
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
source ~/.config/fleet-mcp/env
exec ollmcp \
  --provider openai \
  --host http://localhost:4000/v1 \
  --api-key "$LITELLM_API_KEY" \
  --model "${OPS_MODEL:-q38}" \
  --servers-json ~/.config/ollmcp/fleet-servers.json
