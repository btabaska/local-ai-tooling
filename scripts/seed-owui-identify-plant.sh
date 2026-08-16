#!/bin/bash
# seed-owui-identify-plant.sh — (re)apply the identify_plant workspace tool
# (plant/species ID via bioclip-api, 2026-08-16). Rebuild parity: workspace
# tools are DB-only (open_webui_data volume), so a volume wipe silently erases
# them — this script + owui-tools/identify_plant.py are their canonical source,
# same contract as seed-owui-tool-servers.sh.
#
# The tool finds the newest image attached to the chat (verified against the
# v0.11.0 backend: __messages__[*].files / __files__), POSTs it to bioclip-api
# (docker/bioclip-api, compose-internal http://bioclip-api:8199) and returns
# ranked taxa. access_control=null => public to all household users.
#
# Run ON rig:  OWUI_API_KEY=<admin api key> bash scripts/seed-owui-identify-plant.sh
# Key source:  foss-setup vault ai_stack.openwebui_rag_sync_api_key (admin).
set -euo pipefail

BASE="${OWUI_URL:-http://localhost:3000}"
[ -n "${OWUI_API_KEY:-}" ] || { echo "OWUI_API_KEY not set (vault ai_stack.openwebui_rag_sync_api_key)" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_DIR/owui-tools/identify_plant.py"
[ -f "$SRC" ] || { echo "missing $SRC" >&2; exit 1; }

payload=$(python3 - "$SRC" <<'PY'
import json, sys

content = open(sys.argv[1]).read()
print(json.dumps({
    "id": "identify_plant",
    "name": "Plant Identifier (BioCLIP 2)",
    "content": content,
    "meta": {
        "description": "Identify plants/organisms in a chat-attached photo via the local bioclip-api (BioCLIP 2, TreeOfLife-200M). Fully local, no cloud.",
        "manifest": {},
    },
    "access_control": None,
}))
PY
)

auth=(-H "Authorization: Bearer $OWUI_API_KEY" -H 'Content-Type: application/json')

if curl -sf -m 30 "${auth[@]}" "$BASE/api/v1/tools/id/identify_plant" >/dev/null 2>&1; then
  curl -sf -m 60 -X POST "${auth[@]}" --data-binary "$payload" \
    "$BASE/api/v1/tools/id/identify_plant/update" >/dev/null
  echo "updated identify_plant"
else
  curl -sf -m 60 -X POST "${auth[@]}" --data-binary "$payload" \
    "$BASE/api/v1/tools/create" >/dev/null
  echo "created identify_plant"
fi

# NOTE: access_control null (= public) rides in the ToolForm payload above for
# BOTH create and update — do not add an /access/update call; that endpoint
# switched to an access_grants schema in 0.11 and 422s this shape.
curl -sf -m 30 "${auth[@]}" "$BASE/api/v1/tools/id/identify_plant" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("access_control") is None, "tool is not public"; print("access: public")'
