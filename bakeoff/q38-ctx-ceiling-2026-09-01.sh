#!/usr/bin/env bash
# q38-ctx-ceiling-2026-09-01.sh — max --ctx-size that loads FULLY on GPU, WITH MTP
# spec-decode, for the Qwen3.8-27B candidates (v3 rebuild vs ISTA GSQ-RCO IQ3_S).
# Same methodology as ctx-ceiling-probe.sh (2026-07-16): production srv flags,
# LOADED = /health 200, OOM = process exits before health. Ascending ladder.
set -u
PORT=19999
LADDER=(114688 131072 147456 163840 180224 196608 212992 229376 245760 262144)
declare -A MODELS=(
  [v3]=qwen3.8-27b-v3.gguf
  [ista-iq3s]=qwen3.8-27b-ista-iq3s-mtp.gguf
)
ORDER=(v3)
SRV_FLAGS="-ngl 999 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --no-webui"
MTP_FLAGS="--spec-type draft-mtp --spec-draft-n-max 2 --ctx-checkpoints 4 --parallel 1"

vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d " "; }
wait_drain() { for _ in $(seq 1 45); do [ "$(vram)" -lt 2000 ] && return 0; sleep 1; done; }

echo "== q38 MTP ctx-ceiling probe $(date -u) =="
echo "baseline VRAM: $(vram) MiB   total: 24564 MiB"
curl -s -m 15 -X POST http://localhost:9292/api/models/unload -o /dev/null || true
wait_drain
echo

declare -A CEIL
for key in "${ORDER[@]}"; do
  gguf=${MODELS[$key]}
  echo "########## $key ($gguf) ##########"
  last_ok=""
  for ctx in "${LADDER[@]}"; do
    docker exec -d llama-swap sh -c \
      "/app/llama-server --host 127.0.0.1 --port $PORT $SRV_FLAGS $MTP_FLAGS --model /models/$gguf --ctx-size $ctx > /tmp/ctxprobe.log 2>&1"
    res=TIMEOUT; peak=0
    for _ in $(seq 1 240); do
      if ! docker exec llama-swap pgrep -f "port $PORT" >/dev/null 2>&1; then res=OOM; break; fi
      code=$(docker exec llama-swap curl -s -o /dev/null -w "%{http_code}" -m 3 http://127.0.0.1:$PORT/health 2>/dev/null)
      v=$(vram); [ "$v" -gt "$peak" ] && peak=$v
      [ "$code" = "200" ] && { res=LOADED; sleep 2; v=$(vram); [ "$v" -gt "$peak" ] && peak=$v; break; }
      sleep 1
    done
    docker exec llama-swap pkill -f "port $PORT" 2>/dev/null
    if [ "$res" = LOADED ]; then
      gib=$(awk "BEGIN{printf \"%.1f\", $peak/1024}")
      printf "  ctx=%-7s LOADED   peak=%sMiB (%s GiB, %sMiB free)\n" "$ctx" "$peak" "$gib" "$((24564-peak))"
      last_ok=$ctx
      wait_drain
    else
      printf "  ctx=%-7s %-8s (ceiling stands at %s)\n" "$ctx" "$res" "${last_ok:-none}"
      echo "    --- llama-server tail ---"
      docker exec llama-swap tail -4 /tmp/ctxprobe.log 2>/dev/null | sed "s/^/    /"
      wait_drain
      break
    fi
  done
  CEIL[$key]=${last_ok:-FAIL}
  echo "  >>> $key MTP ceiling: ${CEIL[$key]}"
  echo
done

echo "======== SUMMARY (max ctx, MTP spec-decode, loads fully on GPU) ========"
for key in "${ORDER[@]}"; do echo "  $key: ${CEIL[$key]}"; done
echo "PROBE_DONE"
