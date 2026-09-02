#!/usr/bin/env python3
"""Pin the default tool set on the chat-class models (2026-08-17).

Operator decision: every OWUI tool EXCEPT identify_plant is on by default in
plain chat, so nothing needs toggling per conversation. identify_plant stays
off here — it is Plant Scout's pinned tool (seed-owui-plant-scout.py) and only
makes sense with a photo attached.

2026-09-01 (lai-30): the bake-off trial lanes are gone; MODELS is now
`chat` (heretic-31B) + `chat-fast` (HauhauCS-12B). chat-fast carries the FULL
belt by operator decision — the schemas cost a few k tokens of its 262144
window, which it can afford far more easily than the 31B could.

Pinning is via model.info.meta.toolIds — the FRONTEND merges the list into
every chat request (Chat.svelte), same mechanism as Plant Scout. The ids are
the stable tool-server pseudo-ids from seed-owui-tool-servers.sh (keep them in
sync when servers are added/removed there!). Cost of always-on: all ~34 tool
schemas ride along in every request (a few k tokens of the 65536 chat window)
— accepted.

History: superseded seed-owui-chat-zim-tools.py (which pinned only
server:openzim after gemma, lacking any zim tools in a fresh chat, grepped its
code-exec sandbox for "zim" instead).

Read-modify-write: `chat` is a live base-model record also touched by
seed-owui-model-capabilities.sh (vision flag) — this script only edits
meta.toolIds and preserves everything else. It REPLACES the toolIds list (it
is the canonical source). Idempotent.

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

# Everything except identify_plant (Plant Scout's tool). Mirror of the
# connection list in seed-owui-tool-servers.sh.
PIN = [
    "server:time",
    "server:fetch",
    "server:openzim",
    "server:sequential-thinking",
    "server:mcp:fleet",
    "server:mcp:comfyui",
    "server:mcp:playwright",
    "server:mcp:memos",
]


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


MODELS = ["chat", "chat-fast"]

for mid in MODELS:
    rec = req("GET", "/api/v1/models/model?id=" + mid)
    assert rec, "%s model record not found — run seed-owui-model-capabilities.sh first" % mid

    meta = rec.get("meta") or {}
    if list(meta.get("toolIds") or []) == PIN:
        print("%s toolIds already pinned: %s" % (mid, PIN))
        continue

    meta["toolIds"] = list(PIN)
    form = {
        "id": mid,
        "name": rec.get("name") or mid,
        "base_model_id": rec.get("base_model_id"),
        "meta": meta,
        "params": rec.get("params") or {},
        "access_grants": rec.get("access_grants") or [],
        "is_active": rec.get("is_active", True),
    }
    assert req("POST", "/api/v1/models/model/update?id=" + mid, form)

    rec = req("GET", "/api/v1/models/model?id=" + mid)
    tools = (rec.get("meta") or {}).get("toolIds") or []
    vision = ((rec.get("meta") or {}).get("capabilities") or {}).get("vision")
    assert tools == PIN and "identify_plant" not in tools, rec
    print("verified: %s toolIds=%s vision=%s (preserved)" % (mid, tools, vision))
