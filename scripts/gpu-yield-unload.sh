#!/usr/bin/env bash
# gpu-yield-unload.sh — Apollo/Sunshine session-start hook (ai-01 GPU-yield).
# Force-unloads every llama.cpp model via llama-swap admin API so the full
# 24 GB is free for the game/stream. Measured 2026-07-14: 22.4 GiB -> baseline
# in 182 ms. Reload is automatic on the next LLM request (on-demand load,
# 1.3-3.3 s warm). Wired via global_prep_cmd in ~/.config/sunshine/sunshine.conf.
# MUST never block/fail a session start: short timeout, always exit 0.
curl -sm 3 -X POST http://localhost:9292/api/models/unload >/dev/null 2>&1 || true
logger -t gpu-yield "apollo session start -> llama-swap unload-all"
exit 0
