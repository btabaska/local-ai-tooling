#!/usr/bin/env bash
# Vision ceiling probe done RIGHT: success = a real image request returns 200
# with content. /health 200 is NOT sufficient - llama-server logs the CLIP
# buffer cudaMalloc failure, reports "model loaded", then SEGFAULTS on the
# first image (observed 2026-09-01 at ctx 49152 on the heretic-31B lane).
set -u
P=19998
IMG="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
for ctx in "$@"; do
  docker exec llama-swap pkill -f "port $P" 2>/dev/null; sleep 4
  docker exec -d llama-swap sh -c "/app/llama-server --host 127.0.0.1 --port $P -ngl 999 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --jinja --no-webui --model /models/gemma4-31b-heretic-q4ks.gguf --mmproj /models/mmproj-gemma4-31b-heretic-bf16.gguf --ctx-size $ctx --temp 1.0 --top-p 0.95 --top-k 64 > /tmp/vis-$ctx.log 2>&1"
  h=000
  for i in $(seq 1 120); do
    h=$(docker exec llama-swap curl -s -o /dev/null -w "%{http_code}" -m 3 http://127.0.0.1:$P/health 2>/dev/null)
    [ "$h" = "200" ] && break; sleep 2
  done
  peak=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d " ")
  clipfail=$(docker exec llama-swap grep -c "cudaMalloc failed" /tmp/vis-$ctx.log 2>/dev/null || echo 0)
  code=$(docker exec llama-swap sh -c "curl -s -o /tmp/r-$ctx -w \"%{http_code}\" -m 180 -X POST http://127.0.0.1:$P/v1/chat/completions -H \"Content-Type: application/json\" -d @- <<XX
{\"model\":\"x\",\"max_tokens\":24,\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"color?\"},{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/png;base64,$IMG\"}}]}]}
XX" 2>/dev/null)
  verdict=IMAGE_FAIL
  [ "$code" = "200" ] && verdict=IMAGE_OK
  printf "  ctx=%-7s health=%s clip_alloc_fail=%s image_http=%s  %-11s loaded_peak=%sMiB (%sMiB free)\n" \
    "$ctx" "$h" "$clipfail" "$code" "$verdict" "$peak" "$((24564-peak))"
  [ "$verdict" = "IMAGE_OK" ] && { docker exec llama-swap pkill -f "port $P" 2>/dev/null; echo "  >>> TRUE vision ceiling: $ctx"; exit 0; }
done
docker exec llama-swap pkill -f "port $P" 2>/dev/null
echo "  >>> no ctx in the ladder passed a real image request"
