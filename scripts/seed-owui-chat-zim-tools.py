#!/usr/bin/env python3
"""Pin the openzim tool-server tools on the `chat` model (2026-08-17).

Why: the ZIM library tools (server:openzim -> zim_query/zim_search/zim_get via
mcpo) were only reachable in plain chat when the user remembered to toggle them
in the chat's integrations menu — a fresh chat got NO zim tools, and gemma then
improvised with whatever tools WERE active (observed: open-terminal filesystem
greps for "zim"). Pinning via model.info.meta.toolIds makes the frontend merge
them into every chat request (Chat.svelte), same mechanism as Plant Scout's
identify_plant.

Read-modify-write: `chat` is a live base-model record also touched by
seed-owui-model-capabilities.sh (vision flag) — this script only edits
meta.toolIds and preserves everything else. Idempotent.

Rebuild parity: model records are DB-only (open_webui_data volume) — re-run
after any volume rebuild, AFTER seed-owui-tool-servers.sh (ids must exist).
Reads the OWUI admin API key from stdin (never on argv);
key source: foss-setup vault ai_stack.openwebui_rag_sync_api_key.
"""
import json
import sys
import urllib.error
import urllib.request

KEY = sys.stdin.readline().strip()
BASE = "http://localhost:3000"
H = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}

PIN = ["server:openzim"]


def req(method, path, body=None):
    r = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode().strip()
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} on {method} {path}: {e.read().decode()[:200]}")
        return None
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        print(f"  non-JSON on {method} {path}: {raw[:120]}")
        return None


rec = req("GET", "/api/v1/models/model?id=chat")
assert rec, "chat model record not found — run seed-owui-model-capabilities.sh first"

meta = rec.get("meta") or {}
tools = list(meta.get("toolIds") or [])
missing = [t for t in PIN if t not in tools]
if not missing:
    print("chat toolIds already pinned: %s" % tools)
    sys.exit(0)

meta["toolIds"] = tools + missing
form = {
    "id": "chat",
    "name": rec.get("name") or "chat",
    "base_model_id": rec.get("base_model_id"),
    "meta": meta,
    "params": rec.get("params") or {},
    "access_grants": rec.get("access_grants") or [],
    "is_active": rec.get("is_active", True),
}
assert req("POST", "/api/v1/models/model/update?id=chat", form)

rec = req("GET", "/api/v1/models/model?id=chat")
tools = (rec.get("meta") or {}).get("toolIds") or []
vision = ((rec.get("meta") or {}).get("capabilities") or {}).get("vision")
assert all(t in tools for t in PIN), rec
print("verified: chat toolIds=%s vision=%s (preserved)" % (tools, vision))
