#!/usr/bin/env bash
# ctx-ceiling-probe.sh — measure the max --ctx-size that loads FULLY on GPU for
# each creative/RP model, mirroring the 2026-07-16 bake-off methodology.
#
# Method: for each model, ascend a 2048-aligned ctx ladder. For each rung, spawn
# a throwaway llama-server inside the llama-swap container with the PRODUCTION
# srv flags (-ngl 999, flash-attn, q8_0 KV). LOADED = /health returns 200 (all
# layers + KV allocated on GPU). OOM = the process exits before health is ready
# (cudaMalloc failure with -ngl 999 → no CPU fallback → abort). Record peak VRAM,
# kill, wait for VRAM to drain, next rung. Ceiling = last LOADED rung; we also
# record the first OOM rung. Runs at idle (unload-all first) so numbers are clean.
set -u
PORT=19999
LADDER=(65536 73728 81920 90112 98304 114688 131072)   # 2048-aligned; native max 131072
declare -A MODELS=(
  [cydonia-24b]=cydonia-24b.gguf
  [dolphin-venice-24b]=dolphin-venice-24b.gguf
  [goetia-24b]=goetia-24b.gguf
)
ORDER=(cydonia-24b dolphin-venice-24b goetia-24b)
SRV_FLAGS="-ngl 999 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --no-webui"

vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' '; }
wait_drain() { for _ in $(seq 1 30); do [ "$(vram)" -lt 2000 ] && return 0; sleep 1; done; }

echo "== ctx-ceiling probe $(date -u) =="
echo "baseline VRAM: $(vram) MiB   total: 24564 MiB"
# clean slate: evict anything llama-swap holds
curl -s -m 15 -X POST http://localhost:9292/api/models/unload -o /dev/null || true
wait_drain
echo

declare -A CEIL
for key in "${ORDER[@]}"; do
  gguf=${MODELS[$key]}
  echo "########## $key ($gguf) ##########"
  last_ok=""
  for ctx in "${LADDER[@]}"; do
    # spawn throwaway server detached inside the container
    docker exec -d llama-swap sh -c \
      "/app/llama-server --host 127.0.0.1 --port $PORT $SRV_FLAGS --model /models/$gguf --ctx-size $ctx > /tmp/ctxprobe.log 2>&1"
    res=TIMEOUT; peak=0
    for _ in $(seq 1 120); do
      if ! docker exec llama-swap pgrep -f "port $PORT" >/dev/null 2>&1; then res=OOM; break; fi
      code=$(docker exec llama-swap curl -s -o /dev/null -w '%{http_code}' -m 3 http://127.0.0.1:$PORT/health 2>/dev/null)
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
      printf "  ctx=%-7s %-8s (next rung after %s)\n" "$ctx" "$res" "${last_ok:-none}"
      echo "    --- llama-server tail ---"
      docker exec llama-swap tail -3 /tmp/ctxprobe.log 2>/dev/null | sed 's/^/    /'
      wait_drain
      break
    fi
  done
  CEIL[$key]=${last_ok:-FAIL}
  echo "  >>> $key ceiling: ${CEIL[$key]}"
  echo
done

echo "======== SUMMARY (measured max ctx that loads fully on GPU) ========"
for key in "${ORDER[@]}"; do echo "  $key: ${CEIL[$key]}"; done
echo "PROBE_DONE"
