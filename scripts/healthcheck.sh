#!/usr/bin/env bash
# healthcheck.sh — Probe every endpoint + show what's loaded on the GPU. Run anytime.
set -uo pipefail

HOST="${AI_HOST:-localhost}"
KEY="${LITELLM_MASTER_KEY:-}"

ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1"; }

probe() { # url, label
  if curl -fsS -m 5 "$1" >/dev/null 2>&1; then ok "$2"; else bad "$2  ($1)"; fi
}

echo "== Endpoints (host: $HOST) =="
probe "http://$HOST:11434/api/tags"  "Ollama native API"
probe "http://$HOST:11434/v1/models" "Ollama OpenAI-compat (/v1)"
probe "http://$HOST:4000/health/liveliness" "LiteLLM gateway"
probe "http://$HOST:3000/health"     "Open WebUI"
probe "http://$HOST:8000/docs"       "mcpo tools"

echo
echo "== LiteLLM: models it exposes =="
if [[ -n "$KEY" ]]; then
  curl -fsS -m 5 -H "Authorization: Bearer $KEY" "http://$HOST:4000/v1/models" \
    | python3 -c 'import sys,json;[print("  -",m["id"]) for m in json.load(sys.stdin).get("data",[])]' 2>/dev/null \
    || echo "  (could not parse — check LITELLM_MASTER_KEY)"
else
  echo "  (set LITELLM_MASTER_KEY env to list them)"
fi

echo
echo "== GPU / loaded models =="
command -v ollama >/dev/null 2>&1 && ollama ps || echo "  (ollama not on this host)"
echo
command -v nvidia-smi >/dev/null 2>&1 && \
  nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv || true
