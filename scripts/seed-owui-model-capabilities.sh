#!/bin/bash
# seed-owui-model-capabilities.sh — make every OWUI model's `vision` capability
# TRUTHFUL about its llama-swap backend (2026-08-16). Rebuild parity: capability
# flags live only in the open_webui_data DB (model records), so a volume wipe
# silently reverts them — this script is their canonical source, same contract
# as seed-owui-tool-servers.sh / seed-owui-identify-plant.sh.
#
# Why it matters: the OWUI frontend embeds chat-attached images as image_url
# content parts ONLY for models whose record says vision=true. A lying flag
# 500s (text-only llama.cpp lane: "image input is not supported ... mmproj"),
# and a missing flag hides real vision (the mmproj-equipped lanes).
#
# Backend truth (llama-swap config):
#   vision  : chat-vision (gemma4-31b-qat-vision + mmproj — Plant Scout's lane,
#             split 2026-08-17), cydonia / dolphin-venice / goetia (shared
#             Mistral mmproj, 2026-07-18)
#   no vision: chat + rig-thinker (base=chat; gemma text lane since the
#             2026-08-17 split — mmproj removed, ctx back to 65536),
#             coder / code / coder-swarm / coder-strong (qwen3.6*), q38,
#             chat-creative (deckard-heretic, no mmproj), fast, utility,
#             rig-coder (base=coder; OWUI-deactivated 2026-08-17),
#             chat-q38-trial / chat-gemma-26b-trial (2026-08-19 bake-off:
#             text-only lanes — q38's VLM base and the 26B's vision tower are
#             served WITHOUT mmproj; attach images via chat-vision only)
#
# Run ON rig:  OWUI_API_KEY=<admin api key> bash scripts/seed-owui-model-capabilities.sh
# Key source:  foss-setup vault ai_stack.openwebui_rag_sync_api_key (admin).
set -euo pipefail

BASE="${OWUI_URL:-http://localhost:3000}"
[ -n "${OWUI_API_KEY:-}" ] || { echo "OWUI_API_KEY not set (vault ai_stack.openwebui_rag_sync_api_key)" >&2; exit 1; }

OWUI_URL="$BASE" python3 - <<'PY'
import json, os, urllib.error, urllib.request

BASE = os.environ["OWUI_URL"].rstrip("/")
KEY = os.environ["OWUI_API_KEY"]

VISION = {
    "chat-vision": True,
    "cydonia": True, "dolphin-venice": True, "goetia": True,
    "chat": False, "rig-thinker": False,
    "coder": False, "code": False, "coder-swarm": False, "coder-strong": False,
    "q38": False, "chat-creative": False, "fast": False, "utility": False,
    "rig-coder": False,
    "chat-q38-trial": False, "chat-gemma-26b-trial": False,
}

def api(method, path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 404):
            return None
        raise

for mid, want in sorted(VISION.items()):
    rec = api("GET", f"/api/v1/models/model?id={urllib.request.quote(mid)}")
    if rec:
        meta = rec.get("meta") or {}
        caps = meta.get("capabilities") or {}
        if caps.get("vision") is want:
            print(f"{mid:16s} ok (vision={want})")
            continue
        caps["vision"] = want
        meta["capabilities"] = caps
        # 0.11 ModelForm: access_grants is a required LIST (the access_control
        # field is gone — same schema shift as the tools API).
        body = {
            "id": rec["id"], "base_model_id": rec.get("base_model_id"),
            "name": rec.get("name") or mid, "meta": meta,
            "params": rec.get("params") or {},
            "access_grants": rec.get("access_grants") or [],
            "is_active": rec.get("is_active", True),
        }
        assert api("POST", f"/api/v1/models/model/update?id={urllib.request.quote(mid)}", body)
        print(f"{mid:16s} updated -> vision={want}")
    else:
        body = {
            "id": mid, "base_model_id": None, "name": mid,
            "meta": {"capabilities": {"vision": want}}, "params": {},
            "access_grants": [], "is_active": True,
        }
        assert api("POST", "/api/v1/models/create", body)
        print(f"{mid:16s} created -> vision={want}")
PY
