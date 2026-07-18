#!/bin/bash
# seed-marinara-connections.sh — idempotently (re)create Marinara-Engine's API
# connections after a fresh install or a marinara-data volume wipe.
#
# Marinara 1.5.0 has no env-var connection seeding: connections live only in the
# encrypted SQLite DB inside the marinara-data volume. This script rebuilds them
# through the app's own REST API (unauthenticated on localhost — the enforcing
# auth gate is the mini Caddy, see docker-compose.yml).
#
# Run ON rig:   bash scripts/seed-marinara-connections.sh
# Requires:     marinara container running; docker/.env with MARINARA_LITELLM_KEY.
# Idempotent:   upserts by connection NAME (PATCH if present, POST if missing).
#
# Notes that will bite you if you change things:
# - The Flux connection's "model" field MUST NOT contain "flux" or "black-forest":
#   packages/shared inferImageSource() matches those to TogetherAI *before* the
#   comfyui base-URL rule, silently misrouting generation (POST /:id/test does
#   NOT catch this — it dispatches on base URL only). Hence "klein-9b-comfyui".
# - %placeholder% tokens stay inside JSON string quotes in the templates; the
#   app substitutes token-only (quotes preserved) and ComfyUI coerces numeric
#   strings — verified working 2026-07-18. Don't "fix" the quoting.
# - "OpenRouter Free" (__default_openrouter__) is re-seeded by the image at every
#   startup with a hardcoded upstream key; deleting it doesn't stick. We simply
#   take is_default away from it.
set -euo pipefail

API="http://localhost:3002/api/connections"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WF_DIR="$REPO/comfyui-workflows/marinara"
ENV_FILE="$REPO/docker/.env"

KEY=$(grep '^MARINARA_LITELLM_KEY=' "$ENV_FILE" | cut -d= -f2-)
[ -n "$KEY" ] || { echo "MARINARA_LITELLM_KEY missing from $ENV_FILE" >&2; exit 1; }

export SEED_KEY="$KEY"
python3 - "$API" "$WF_DIR" <<'PY'
import json, os, sys, urllib.request

api, wf_dir = sys.argv[1], sys.argv[2]
key = os.environ["SEED_KEY"]

def call(method, path="", body=None):
    req = urllib.request.Request(api + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None

def wf(name):
    with open(os.path.join(wf_dir, name)) as f:
        return f.read()

WANTED = [
    dict(name="LiteLLM Creative", provider="openai",
         baseUrl="https://llm.tabaska.us/v1", apiKey=key, model="goetia",
         maxContext=73728, isDefault=True, defaultForAgents=True),
    dict(name="Anime Image", provider="image_generation",
         baseUrl="https://comfyui.tabaska.us", model="NoobAI-XL-v1.1.safetensors",
         comfyuiWorkflow=wf("noobai-xl-anime.marinara.json")),
    dict(name="Realistic Image (Z-Image Turbo)", provider="image_generation",
         baseUrl="https://comfyui.tabaska.us", model="z_image_turbo_bf16.safetensors",
         comfyuiWorkflow=wf("z-image-turbo-realistic.marinara.json")),
    # model field deliberately avoids the substring "flux" — see header comment.
    dict(name="Realistic Image (Flux.2 Klein)", provider="image_generation",
         baseUrl="https://comfyui.tabaska.us", model="klein-9b-comfyui",
         comfyuiWorkflow=wf("flux2-klein-9b.marinara.json")),
]

existing = {c["name"]: c["id"] for c in call("GET")}
for want in WANTED:
    name = want["name"]
    if name in existing:
        cid = existing[name]
        call("PATCH", f"/{cid}", want)
        print(f"updated  {name} ({cid})")
    else:
        created = call("POST", "", want)
        cid = created["id"]
        print(f"created  {name} ({cid})")
    test = call("POST", f"/{cid}/test", {})
    ok = test.get("success")
    print(f"  test: success={ok} latencyMs={test.get('latencyMs')}")
    if not ok:
        sys.exit(f"connection test FAILED for {name}: {test}")
print("marinara connections seeded OK")
PY
