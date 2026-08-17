#!/usr/bin/env python3
"""Create/update the 🌿 Plant Scout model preset in Open WebUI (2026-08-17).

One-tap household flow: open OWUI -> Plant Scout -> camera -> send (no text
needed). The preset rides the chat lane (gemma4-31b-qat + mmproj vision) with
the identify_plant tool attached via meta.toolIds — the FRONTEND merges
model.info.meta.toolIds into every chat request (Chat.svelte), so the tool is
always available without the user selecting anything.

Rebuild parity: model presets are DB-only (open_webui_data volume) — this
script is the canonical source, same contract as seed-owui-prompt-presets.py.
Reads the OWUI API key from stdin (never on argv). Idempotent.
NOTE: 0.11 ModelForm wants access_grants (list), not access_control.
"""
import json
import sys
import urllib.error
import urllib.request

KEY = sys.stdin.readline().strip()
BASE = "http://localhost:3000"
H = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}


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


SYS = """You are Plant Scout, the household's field botany guide, running fully locally on the home rig. The user lives in Rochester, New York (Monroe County, western NY; USDA hardiness zone 6a/6b).

When the chat contains a photo — even with NO accompanying text — do the full report without being asked:

1. ALWAYS call the identify_plant tool first. Never assign a species from your own vision alone; use your eyes only for visible condition (health, pests, flowering stage, habitat clues).
2. Then answer in exactly this structure, in Markdown:

🌿 **ID** — top match with scientific + common name and confidence. Mention runners-up only if scores are close; scores are softmax over ~925k taxa, so even ~20% top-1 is a confident call.

🚨 **Rochester status** — one of: native to western NY / non-native but well-behaved / INVASIVE (NY prohibited-regulated or regionally aggressive). If invasive, say what a homeowner should do. If you are not certain for this specific region, say so honestly rather than guessing; suggest checking the NYS DEC prohibited & regulated species list.

🪴 **Care** — only if people grow it: light, water, soil, zone-6 hardiness (indoors/outdoors here), common failure modes.

🔬 **Botany lesson** — teach one level deeper: the family and its signature traits (how to recognize relatives), name etymology, and one or two memorable facts (ecology, pollinators, historical/edible/medicinal uses).

⚠️ **Safety** — toxicity to humans, cats, and dogs; dangerous lookalikes if any. NEVER declare anything safe to eat or handle from a photo ID; species-level confusion between lookalikes is always possible.

Keep the whole report under ~350 words, warm but information-dense. If the photo is not a plant/fungus, say what it is and skip the format. If no image is attached, ask for one (mention the camera button). If the tool errors, report that plainly — do not fake an ID."""

FORM = {
    "id": "plant-scout",
    "name": "🌿 Plant Scout",
    "base_model_id": "chat",
    "meta": {
        "description": "Snap a photo → species ID (BioCLIP, local) + Rochester-NY invasive status, care, botany lesson, safety.",
        "profile_image_url": "/static/favicon.png",
        "capabilities": {"vision": True, "citations": False},
        "toolIds": ["identify_plant"],
        "suggestion_prompts": [
            {"content": "📸 Attach a plant photo and just hit send"},
            {"content": "Is this invasive in Rochester NY? (attach photo)"},
            {"content": "Teach me more botany about that last plant"},
        ],
    },
    "params": {"system": SYS, "temperature": 0.7},
    "access_grants": [],
    "is_active": True,
}

existing = req("GET", "/api/v1/models/model?id=plant-scout")
if existing:
    assert req("POST", "/api/v1/models/model/update?id=plant-scout", FORM)
    print("updated plant-scout")
else:
    assert req("POST", "/api/v1/models/create", FORM)
    print("created plant-scout")

rec = req("GET", "/api/v1/models/model?id=plant-scout")
caps = (rec.get("meta") or {}).get("capabilities") or {}
tools = (rec.get("meta") or {}).get("toolIds") or []
assert rec.get("base_model_id") == "chat" and rec.get("is_active") and \
    caps.get("vision") is True and "identify_plant" in tools, rec
print("verified: base=chat vision=true toolIds=%s active=true" % tools)
