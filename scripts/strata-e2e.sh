#!/usr/bin/env bash
# strata-e2e.sh — consumer-end probe of the Strata lane (Qwen3.8-Flash-Next IQ3_S,
# 2026-10-22). Proves the chain the clients actually use:
#   OWUI-scoped LiteLLM key -> LiteLLM :4000 `strata` alias -> llama-swap `strata`
#   shim (POST /load) -> strata container -> a real completion comes back.
# Plus posture: container up + /health answers, llama-swap lists the lane.
# If the lane was NOT loaded before the probe, it is unloaded again afterwards
# (llama-swap per-model unload -> shim cmdStop -> Strata /unload) so a daily
# probe never leaves 84 GB of model holding the card/RAM away from q38.
# Prints exactly one STRATA_E2E_OK|STRATA_E2E_BAD line. Secrets come from
# docker/.env by grep (never sourced, never on argv of a long-lived process).
set -u
REPO="${REPO:-$HOME/Documents/GitHub/local-ai-tooling}"
ENVF="$REPO/docker/.env"
bad() { echo "STRATA_E2E_BAD $*"; exit 1; }

key=$(grep -s '^OPENWEBUI_LITELLM_KEY=' "$ENVF" | cut -d= -f2-)
[ -n "$key" ] || bad "no OPENWEBUI_LITELLM_KEY in docker/.env"

docker ps --format '{{.Names}}' | grep -qx strata || bad "container not running"
curl -sf -m 10 http://127.0.0.1:8090/health >/dev/null || bad "strata /health not answering"
curl -sf -m 10 http://127.0.0.1:9292/v1/models | grep -q '"strata"' || bad "llama-swap does not list strata"

was_loaded=0
curl -sf -m 10 http://127.0.0.1:9292/running | grep -q '"model":"strata"' && was_loaded=1

t0=$(date +%s)
resp=$(curl -s -m 840 http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $key" -H "Content-Type: application/json" \
  -d '{"model":"strata","messages":[{"role":"user","content":"Reply with exactly: STRATA_PROBE_OK"}],"max_tokens":64,"temperature":0,"reasoning_effort":"none"}')
dt=$(( $(date +%s) - t0 ))

if [ "$was_loaded" = 0 ]; then
  curl -s -m 360 -X POST http://127.0.0.1:9292/api/models/unload/strata >/dev/null || true
fi

echo "$resp" | grep -q 'STRATA_PROBE_OK' \
  && echo "STRATA_E2E_OK secs=$dt cold=$((1-was_loaded))" \
  || bad "secs=$dt resp=$(echo "$resp" | tr -d '\n' | tail -c 200)"
