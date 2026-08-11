#!/bin/bash
# seed-lumiverse-connections.sh — idempotently (re)create Lumiverse's LLM +
# ComfyUI image-gen connections after a fresh install or lumiverse-data wipe.
#
# Lumiverse has no env-var connection seeding (src/env.ts) — connections live in
# /app/data/lumiverse.db, keys AES-encrypted under data/lumiverse.identity. This
# script rebuilds them through the authenticated REST API.
#
# Run ON rig:   bash scripts/seed-lumiverse-connections.sh
# Requires:     lumiverse container running; docker/.env with
#               LUMIVERSE_OWNER_PASSWORD + LUMIVERSE_LITELLM_KEY.
# Idempotent:   upserts by connection NAME.
#
# Gotchas encoded here (verified 2026-07-18):
# - Every request needs "Host: lumiverse.tabaska.us" (TRUSTED_ORIGINS gate 403s
#   anything else on rig:3001).
# - Sign-in is rate-limited (8/5min + lockout): this script signs in exactly once.
# - The comfyui-workflows/*.api.json files are wrapped as {"prompt": {...}} (raw
#   POST /prompt body shape); Lumiverse's import wants the BARE node map.
# - Workflow import fetches the target's /object_info live — ComfyUI (via the
#   gpu-arbiter, reached via its comfyui-arbiter alias :8189) must be up when this runs.
# - Field mappings are Lumiverse's parameterization (no %placeholders%): steps/
#   cfg are intentionally NOT mapped for Z-Image (8/1.0) and Flux.2 (20/4.0) —
#   those are turbo-tuned in the workflows. Flux carries width/height in BOTH
#   the latent node and the Flux2Scheduler; both must be mapped together.
set -euo pipefail

BASE="http://localhost:3001"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WF_DIR="$REPO/comfyui-workflows"
ENV_FILE="$REPO/docker/.env"

PW=$(grep '^LUMIVERSE_OWNER_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
KEY=$(grep '^LUMIVERSE_LITELLM_KEY=' "$ENV_FILE" | cut -d= -f2-)
[ -n "$PW" ] && [ -n "$KEY" ] || { echo "missing LUMIVERSE_* vars in $ENV_FILE" >&2; exit 1; }

export SEED_PW="$PW" SEED_KEY="$KEY"
python3 - "$BASE" "$WF_DIR" <<'PY'
import json, os, sys, urllib.request

base, wf_dir = sys.argv[1], sys.argv[2]
pw, key = os.environ["SEED_PW"], os.environ["SEED_KEY"]
HOST = "lumiverse.tabaska.us"
token = None

def call(method, path, body=None, raw_headers=False):
    req = urllib.request.Request(base + path, method=method,
        data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Host", HOST)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
        if raw_headers:
            return r.headers, (json.loads(raw) if raw else None)
        return json.loads(raw) if raw else None

# --- sign in once (bearer plugin: token arrives in set-auth-token header) ----
hdrs, _ = call("POST", "/api/auth/sign-in/username",
               {"username": "admin", "password": pw}, raw_headers=True)
token = hdrs.get("set-auth-token")
assert token, "sign-in returned no set-auth-token header"
print(f"signed in (token {len(token)} chars)")

# --- LLM connection -----------------------------------------------------------
LLM_NAME = "LiteLLM Creative"
conns = call("GET", "/api/v1/connections")["data"]  # paginated: {data,total,limit,offset}
row = next((c for c in conns if c["name"] == LLM_NAME), None)
llm_body = {"name": LLM_NAME, "provider": "custom",
            "api_url": "https://llm.tabaska.us/v1", "model": "goetia",
            "is_default": True}
if row:
    call("PUT", f"/api/v1/connections/{row['id']}", llm_body)
    cid = row["id"]; print(f"updated  {LLM_NAME} ({cid})")
else:
    created = call("POST", "/api/v1/connections", llm_body)
    cid = created["id"]; print(f"created  {LLM_NAME} ({cid})")
call("PUT", f"/api/v1/connections/{cid}/api-key", {"api_key": key})
models = call("GET", f"/api/v1/connections/{cid}/models")
print(f"  models: {sorted(m['id'] if isinstance(m, dict) else m for m in (models.get('models') if isinstance(models, dict) else models))}")

# --- image-gen connections ----------------------------------------------------
def unwrapped(fname):
    with open(os.path.join(wf_dir, fname)) as f:
        d = json.load(f)
    return d.get("prompt", d)  # unwrap the raw-/prompt-body shape

IMAGE = [
    ("Anime Image (NoobAI-XL)", "noobai-xl-anime.api.json", True, [
        {"nodeId": "6", "fieldName": "text", "mappedAs": "positive_prompt"},
        {"nodeId": "7", "fieldName": "text", "mappedAs": "negative_prompt"},
        {"nodeId": "3", "fieldName": "seed", "mappedAs": "seed"},
        {"nodeId": "3", "fieldName": "steps", "mappedAs": "steps"},
        {"nodeId": "3", "fieldName": "cfg", "mappedAs": "cfg"},
        {"nodeId": "3", "fieldName": "sampler_name", "mappedAs": "sampler_name"},
        {"nodeId": "3", "fieldName": "scheduler", "mappedAs": "scheduler"},
        {"nodeId": "3", "fieldName": "denoise", "mappedAs": "denoise"},
        {"nodeId": "5", "fieldName": "width", "mappedAs": "width"},
        {"nodeId": "5", "fieldName": "height", "mappedAs": "height"},
    ]),
    ("Realistic Image (Z-Image Turbo)", "z-image-turbo-realistic.api.json", False, [
        # no negative_prompt node (ConditioningZeroOut); steps/cfg turbo-pinned 8/1.0
        {"nodeId": "5", "fieldName": "text", "mappedAs": "positive_prompt"},
        {"nodeId": "8", "fieldName": "seed", "mappedAs": "seed"},
        {"nodeId": "7", "fieldName": "width", "mappedAs": "width"},
        {"nodeId": "7", "fieldName": "height", "mappedAs": "height"},
    ]),
    ("Realistic NSFW (CyberRealistic)", "z-image-nsfw-cyberrealistic.api.json", False, [
        {"nodeId": "5", "fieldName": "text", "mappedAs": "positive_prompt"},
        {"nodeId": "8", "fieldName": "seed", "mappedAs": "seed"},
        {"nodeId": "7", "fieldName": "width", "mappedAs": "width"},
        {"nodeId": "7", "fieldName": "height", "mappedAs": "height"},
    ]),
    ("Realistic Image (Flux.2 Klein)", "flux2-klein-9b.api.json", False, [
        # steps/cfg pinned (20/4-5); width/height live on latent node 6 AND scheduler node 8
        {"nodeId": "4", "fieldName": "text", "mappedAs": "positive_prompt"},
        {"nodeId": "5", "fieldName": "text", "mappedAs": "negative_prompt"},
        {"nodeId": "10", "fieldName": "noise_seed", "mappedAs": "seed"},
        {"nodeId": "6", "fieldName": "width", "mappedAs": "width"},
        {"nodeId": "6", "fieldName": "height", "mappedAs": "height"},
        {"nodeId": "8", "fieldName": "width", "mappedAs": "width"},
        {"nodeId": "8", "fieldName": "height", "mappedAs": "height"},
    ]),
]

img_conns = call("GET", "/api/v1/image-gen-connections")["data"]
img_by_name = {c["name"]: c["id"] for c in img_conns}
for name, fname, is_default, mappings in IMAGE:
    body = {"name": name, "provider": "comfyui",
            "api_url": "http://comfyui-arbiter:8189", "is_default": is_default}
    if name in img_by_name:
        iid = img_by_name[name]
        call("PUT", f"/api/v1/image-gen-connections/{iid}", body)
        print(f"updated  {name} ({iid})")
    else:
        created = call("POST", "/api/v1/image-gen-connections", body)
        iid = created["id"]; print(f"created  {name} ({iid})")
    call("POST", f"/api/v1/image-gen-connections/{iid}/comfyui/workflow/import",
         {"workflow": unwrapped(fname)})
    call("PUT", f"/api/v1/image-gen-connections/{iid}/comfyui/workflow/mappings",
         {"mappings": mappings})
    test = call("POST", f"/api/v1/image-gen-connections/{iid}/test", {})
    print(f"  imported {fname}, {len(mappings)} mappings, test success={test.get('success')}")
    if not test.get("success"):
        sys.exit(f"connection test FAILED for {name}: {test}")
print("lumiverse connections seeded OK")
PY
