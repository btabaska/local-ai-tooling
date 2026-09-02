#!/usr/bin/env bash
# gemma-ctx-ceiling-2026-09-01.sh — max --ctx-size that loads FULLY on GPU for the
# 2026-09-01 Gemma cutover: heretic-31B (chat + chat-vision) and HauhauCS-12B
# (chat-fast, w/ separate MTP drafter). Same methodology as ctx-ceiling-probe.sh
# (2026-07-16): production srv flags, LOADED = /health 200, OOM = process exits.
# Usage: ./gemma-ctx-ceiling-2026-09-01.sh <entry> [<entry> ...]
set -u
PORT=19999
SRV="-ngl 999 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --jinja --no-webui"
M=/models
MTP12="--spec-type draft-mtp --spec-draft-model $M/mtp-gemma4-12b-it.gguf --spec-draft-n-max 2 --ctx-checkpoints 4 --parallel 1"

# entry -> "gguf|extra flags|ladder"
declare -A E=(
  [fast-mtp]="gemma4-12b-hauhau-q4km.gguf|$MTP12|131072 163840 196608 229376 262144"
  [fast-plain]="gemma4-12b-hauhau-q4km.gguf||196608 229376 262144"
  [chat-q4ks]="gemma4-31b-heretic-q4ks.gguf||49152 57344 65536 73728 81920"
  [chat-q4km]="gemma4-31b-heretic-q4km.gguf||32768 40960 49152 57344 65536"
  [vision-q4ks]="gemma4-31b-heretic-q4ks.gguf|--mmproj $M/mmproj-gemma4-31b-heretic-bf16.gguf|32768 40960 49152 57344"
  [vision-q4km]="gemma4-31b-heretic-q4km.gguf|--mmproj $M/mmproj-gemma4-31b-heretic-bf16.gguf|24576 32768 40960 49152"
)

vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d " "; }
wait_drain() { for _ in $(seq 1 60); do [ "$(vram)" -lt 2000 ] && return 0; sleep 1; done; }

echo "== gemma ctx-ceiling probe $(date -u) =="
echo "baseline VRAM: $(vram) MiB   total: 24564 MiB"
curl -s -m 15 -X POST http://localhost:9292/api/models/unload -o /dev/null || true
wait_drain; echo

for key in "$@"; do
  IFS="|" read -r gguf extra ladder <<< "${E[$key]}"
  echo "########## $key ($gguf ${extra:+[+flags]}) ##########"
  last_ok=""
  for ctx in $ladder; do
    docker exec -d llama-swap sh -c \
      "/app/llama-server --host 127.0.0.1 --port $PORT $SRV $extra --model $M/$gguf --ctx-size $ctx > /tmp/ctxprobe-$key.log 2>&1"
    res=TIMEOUT; peak=0
    for _ in $(seq 1 300); do
      if ! docker exec llama-swap pgrep -f "port $PORT" >/dev/null 2>&1; then res=OOM; break; fi
      code=$(docker exec llama-swap curl -s -o /dev/null -w "%{http_code}" -m 3 http://127.0.0.1:$PORT/health 2>/dev/null)
      v=$(vram); [ "$v" -gt "$peak" ] && peak=$v
      [ "$code" = "200" ] && { res=LOADED; sleep 3; v=$(vram); [ "$v" -gt "$peak" ] && peak=$v; break; }
      sleep 1
    done
    docker exec llama-swap pkill -f "port $PORT" 2>/dev/null
    if [ "$res" = LOADED ]; then
      printf "  ctx=%-7s LOADED   peak=%sMiB (%.1f GiB, %sMiB free)\n" "$ctx" "$peak" \
        "$(awk "BEGIN{print $peak/1024}")" "$((24564-peak))"
      last_ok=$ctx; wait_drain
    else
      printf "  ctx=%-7s %-8s (ceiling stands at %s)\n" "$ctx" "$res" "${last_ok:-none}"
      docker exec llama-swap tail -4 /tmp/ctxprobe-$key.log 2>/dev/null | sed "s/^/    /"
      wait_drain; break
    fi
  done
  echo "  >>> $key ceiling: ${last_ok:-FAIL}"; echo
done
echo "PROBE_DONE"
