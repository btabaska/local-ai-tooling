#!/usr/bin/env bash
# 01-ollama-tune.sh — Configure the Ollama systemd service for network access + your 24GB 3090 Ti.
# Writes a drop-in override (same thing `systemctl edit ollama.service` produces), then reloads.
# Idempotent: re-running overwrites the drop-in cleanly.
set -euo pipefail

OVERRIDE_DIR=/etc/systemd/system/ollama.service.d
OVERRIDE_FILE=$OVERRIDE_DIR/override.conf

echo "Writing ${OVERRIDE_FILE} (requires sudo)…"
sudo mkdir -p "$OVERRIDE_DIR"
sudo tee "$OVERRIDE_FILE" >/dev/null <<'EOF'
[Service]
# --- Network exposure ---
# Listen on all interfaces so other machines on the LAN can reach the API.
# SECURITY: this API has NO authentication. Keep it LAN-only via firewall (02-firewall.sh)
# and/or front it with LiteLLM + Tailscale. See README "What you might be missing".
Environment="OLLAMA_HOST=0.0.0.0:11434"

# Allow cross-origin calls (needed by browser/Electron clients like Obsidian hitting Ollama directly).
# This is a CORS setting, not auth. Fine on a firewalled LAN.
Environment="OLLAMA_ORIGINS=*"

# --- VRAM / performance tuning for a single 24GB card ---
# Flash Attention: big KV-cache memory savings as context grows.
Environment="OLLAMA_FLASH_ATTENTION=1"
# Quantize the K/V cache to 8-bit — ~half the memory of f16, negligible quality loss.
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
# GPU-contention policy (game-13): one 3090 Ti is shared by the Apollo
# stream, the game servers, and AI inference. KEEP_ALIVE=0 unloads each
# model IMMEDIATELY after its request completes, so VRAM frees between
# requests instead of being held for the old 30m idle window. Trade-off:
# every request cold-loads its model (a few seconds' extra latency) —
# acceptable to guarantee VRAM headroom for gaming/streaming. Do not run
# heavy inference during an active Apollo session or game server.
# Regression-guarded by the rig-ollama-keepalive verification check.
Environment="OLLAMA_KEEP_ALIVE=0"
# Two 18GB models can't co-reside in 24GB, but a small (3-4B) helper + one big model can.
# =2 lets Ollama keep a small utility model AND swap the big one; it evicts to fit VRAM.
# Set =1 if you'd rather guarantee only one model ever loads (cleaner, but more swapping).
Environment="OLLAMA_MAX_LOADED_MODELS=2"
# One in-flight request per model keeps KV-cache (and VRAM) minimal. Raise only if you
# actually need concurrent generations and have headroom.
Environment="OLLAMA_NUM_PARALLEL=1"

# NOTE: We deliberately do NOT set a global OLLAMA_CONTEXT_LENGTH here. A global 64k floor
# would balloon VRAM for every model. Instead we bake num_ctx per purpose via Modelfiles
# in 03-model-variants.sh (e.g. a 64k coding model for OpenCode, an 8k model for tagging).
EOF

echo "Reloading systemd + restarting ollama…"
sudo systemctl daemon-reload
sudo systemctl restart ollama
sleep 2

echo
echo "Verifying bind address:"
if ss -tlnp 2>/dev/null | grep ':11434 ' | grep -q '0.0.0.0'; then
  echo "  ✓ ollama is listening on 0.0.0.0:11434"
else
  echo "  ! not bound to 0.0.0.0 yet — check: journalctl -u ollama -n 30"
fi
echo
echo "Local API test:"
curl -fsS http://localhost:11434/api/tags >/dev/null && echo "  ✓ /api/tags OK" || echo "  ✗ /api/tags failed"
echo "Done. From another machine, test:  curl http://<this-server-ip>:11434/api/tags"
