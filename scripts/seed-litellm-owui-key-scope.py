#!/usr/bin/env python3
"""Scope the open-webui LiteLLM virtual key to its chat-facing lanes (2026-08-17).

Why: the key was unrestricted (models=[]), so OWUI listed every gateway lane —
including the coder lanes (coder/code/coder-strong) that are only ever driven
from opencode. Operator decision 2026-08-17: hide them from OWUI entirely by
scoping the key; LiteLLM /v1/models for a scoped key returns only its allow-list,
so the models vanish from the OWUI selector without touching LiteLLM config
(opencode's own key still reaches them).

Allow-list = household/chat lanes + chat-vision (the 2026-08-17 gemma vision
split, Plant Scout's base) + embed/rerank (OWUI RAG) + coder-swarm/q38 (kept
per operator instruction — only the four named lanes were dropped; rig-coder is
an OWUI preset handled by its own deactivation, not a gateway lane).

Rebuild parity: key scopes live only in the litellm-db volume — re-run after a
LiteLLM DB rebuild (after re-minting keys). Reads a JSON {"master":..,"owui":..}
from stdin (never on argv); key sources: vault litellm.master_key +
ai_stack.litellm_openwebui_key. Idempotent. Rollback: OWUI_KEY_MODELS="" (or
edit ALLOW below) and re-run — [] restores the unrestricted scope.
"""
import json
import sys
import urllib.request

ALLOW = [
    "chat", "chat-vision", "chat-creative",
    "cydonia", "dolphin-venice", "goetia",
    "fast", "utility", "embed", "rerank",
    "coder-swarm", "q38",
]

sec = json.loads(sys.stdin.readline())
BASE = "http://localhost:4000"
H = {"Authorization": "Bearer " + sec["master"], "Content-Type": "application/json"}


def req(method, path, body=None):
    r = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None, headers=H)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode() or "null")


info = req("GET", "/key/info?key=" + sec["owui"])["info"]
assert info.get("key_alias") == "open-webui", info.get("key_alias")
if sorted(info.get("models") or []) == sorted(ALLOW):
    print("open-webui key scope already correct: %s" % ALLOW)
    sys.exit(0)

req("POST", "/key/update", {"key": sec["owui"], "models": ALLOW})
info = req("GET", "/key/info?key=" + sec["owui"])["info"]
assert sorted(info.get("models") or []) == sorted(ALLOW), info.get("models")
print("open-webui key scoped to: %s" % sorted(info["models"]))
