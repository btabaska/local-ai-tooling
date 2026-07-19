#!/usr/bin/env python3
"""Create/update the two ComfyUI-prompt-engineer model presets in Open WebUI.
Reads the OWUI API key from stdin (never on argv). Idempotent."""
import sys, json, urllib.request
KEY = sys.stdin.readline().strip()
BASE = "http://localhost:3000"
H = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}

def req(method, path, body=None):
    r = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode().strip()
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        print(f"  HTTP {e.code} on {method} {path}: {raw[:200]}")
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        print(f"  non-JSON on {method} {path}: {raw[:120]}")
        return None

TAG_SYS = (
"You are an expert Danbooru-tag prompt engineer for Illustrious/NoobAI-XL SDXL anime models. "
"Convert the user's scene or the recent chat into a single comma-separated tag list.\n"
"RULES:\n"
"- Output ONLY tags, lowercase, comma-separated. No sentences, no prose, no explanation.\n"
"- Real Danbooru tags; spaces not underscores. Weight sparingly, e.g. (detailed background:1.2).\n"
"- ORDER: quality tags (masterpiece, best quality, newest, absurdres, highres) -> subject count "
"(1girl/1boy/2girls) -> character, series -> appearance (hair, eyes, body) -> clothing -> "
"pose/expression/action -> setting/background -> composition & framing (cowboy shot, from above, "
"dutch angle) -> lighting (rim lighting, backlighting) -> art/style/artist tags.\n"
"- Never use negation words in the positive list.\n"
'Then a second line beginning "NEGATIVE:" with: worst quality, low quality, lowres, jpeg artifacts, '
"bad anatomy, bad hands, extra digits, missing fingers, watermark, signature, text.\n"
"Output exactly two lines (the tag list, then the NEGATIVE line). Nothing else.")

DESC_SYS = (
"You are an expert prompt engineer for natural-language diffusion models (Z-Image Turbo, Flux.2 Klein). "
"Convert the user's scene or the recent chat into ONE flowing, richly descriptive paragraph (2-5 "
"sentences, 80-150 words).\n"
"RULES:\n"
"- Plain natural English prose. NO Danbooru tags, NO comma tag-salad, NO weight syntax (these models "
'ignore (:1.2)), NO "masterpiece/best quality" boilerplate.\n'
"- Natural reading order: main subject + action -> appearance & clothing -> environment/setting -> "
"lighting and mood/time of day -> shot/composition (close-up, wide, low angle) -> artistic medium/style "
"(photoreal cinematic film still / anime cel) with concrete detail (lens, film stock, color grade if "
"photographic). Put the style reference in the first half.\n"
'- Be specific; resolve contradictions; describe only what is present. Write "avoid" items as positives '
"(sharp focus, correct anatomy, natural hands); do NOT emit a negative prompt.\n"
"- Output only the paragraph. No preamble, no quotes, no bullet points.")

PRESETS = [
    dict(id="illustrious-tagger", name="🏷️ Illustrious Tagger (NoobAI)", system=TAG_SYS, temp=0.4,
         desc="Turns a scene/RP into Danbooru tags for NoobAI-XL / Illustrious. Output goes to the anime ComfyUI workflow."),
    dict(id="scene-describer", name="🎨 Scene Describer (Z-Image/Flux)", system=DESC_SYS, temp=0.6,
         desc="Turns a scene/RP into a natural-language prompt for Z-Image Turbo / Flux.2 Klein."),
]

_list = req("GET", "/api/models") or {}
_models = _list.get("data") if isinstance(_list, dict) else _list
existing = {m.get("id") for m in (_models or [])}
for p in PRESETS:
    form = {
        "id": p["id"], "name": p["name"], "base_model_id": "chat",
        "meta": {"description": p["desc"], "profile_image_url": "/static/favicon.png",
                 "capabilities": {"vision": False, "citations": False}},
        "params": {"system": p["system"], "temperature": p["temp"]},
        "access_control": None, "is_active": True,
    }
    if p["id"] in existing:
        req("POST", "/api/v1/models/model/update?id=" + p["id"], form)
        print("updated ", p["id"])
    else:
        req("POST", "/api/v1/models/create", form)
        print("created ", p["id"])
# verify
_l2 = req("GET", "/api/models") or {}
_m2 = _l2.get("data") if isinstance(_l2, dict) else _l2
now = {m.get("id") for m in (_m2 or [])}
print("present in OWUI:", [p["id"] for p in PRESETS if p["id"] in now])
