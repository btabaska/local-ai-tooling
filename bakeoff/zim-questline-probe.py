#!/usr/bin/env python3
"""3-way chat bake-off probe: the Minish Cap library-books questline ask.

Replays the 2026-08-19 real-user failure (gamefaqs ZIM lookup that ended in a
hallucinated "there isn't a singular questline" answer after ~10 flailing
searches) against all three chat lanes under POST-FIX conditions: openzim-mcp
[reranker] extra engaged + the archive-policy paragraph in the shared system
prompt (seed-owui-chat-presets.py).

Fidelity: drives the SAME three OWUI-exposed openzim tools (zim_query /
zim_search / zim_get — specs read live from mcpo's openapi.json, so
descriptions and params match what OWUI shows the model) in a native
tool-call loop straight against the llama-swap lanes, with the system prompt
read live from the OWUI `chat` model record ({{CURRENT_DATE}} substituted).
This is the model+tools layer that OWUI's native mode sits on; the OWUI UI
shell (websocket exec, citations) is not reproduced.

Grading: marker terms that only appear in a GROUNDED answer (book titles,
NPCs, the Flippers reward), plus the tool-call trace (did it zim_get?).

Run ON rig:  OWUI_API_KEY=<admin api key> python3 bakeoff/zim-questline-probe.py
Writes:      bakeoff/results/zim-questline-probe-<date>.json (results/ is
             gitignored — raw-log convention from the q38 ctx/MTP probe).
"""
import json
import os
import time
import urllib.error
import urllib.request

LLAMA = "http://localhost:9292/v1/chat/completions"
MCPO = "http://localhost:8000/openzim"
OWUI = "http://localhost:3000"
ZIM_TOOLS = ["zim_query", "zim_search", "zim_get"]
MODELS = [
    ("chat", "gemma4-31b-qat"),
    ("chat-q38-trial", "qwen3.8-27b"),
    ("chat-gemma-26b-trial", "gemma4-26b-a4b"),
]
USER_MSG = (
    "Look up Zelda Minish Cap in gamefaqs_en_all_2020 zim, then give me "
    "detailed step by step directions on how to complete the library book "
    "questline in the minish cap"
)
# Terms that only a guide-grounded answer contains (the flail answer had none).
MARKERS = [
    "hyrulean bestiary", "picori", "history of masks", "librari",
    "flippers", "left", "hagen", "cabin",
]
HALLUCINATION_TELLS = ["isn't a singular", "no singular", "not a traditional",
                       "couldn't find", "could not find"]
# Env overrides: PROBE_MODELS=alias1,alias2 restricts the roster;
# PROBE_MAX_ROUNDS / PROBE_WALL_CAP_S resize the budget (q38 at effort medium
# was still productively reading at the default 14-round cap on 2026-08-19).
MAX_ROUNDS = int(os.environ.get("PROBE_MAX_ROUNDS", "14"))
MODEL_WALL_CAP_S = int(os.environ.get("PROBE_WALL_CAP_S", "720"))
GEN_TIMEOUT_S = 300


def http_json(url, body=None, timeout=120, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(
        url, method="POST" if body is not None else "GET",
        data=json.dumps(body).encode() if body is not None else None, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def owui_system_prompt():
    key = os.environ["OWUI_API_KEY"]
    rec = http_json(OWUI + "/api/v1/models/model?id=chat",
                    headers={"Authorization": "Bearer " + key})
    system = (rec.get("params") or {})["system"]
    return system.replace("{{CURRENT_DATE}}", time.strftime("%Y-%m-%d"))


def tool_specs():
    oa = http_json(MCPO + "/openapi.json")
    specs = []
    for name in ZIM_TOOLS:
        post = oa["paths"]["/" + name]["post"]
        ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        sch = oa["components"]["schemas"][ref.split("/")[-1]]
        specs.append({
            "type": "function",
            "function": {
                "name": name,
                "description": (post.get("description") or "")[:2000],
                "parameters": {
                    "type": "object",
                    "properties": sch.get("properties") or {},
                    "required": sch.get("required") or [],
                },
            },
        })
    return specs


def call_tool(name, args):
    try:
        out = http_json(f"{MCPO}/{name}", body=args, timeout=120)
    except urllib.error.HTTPError as e:
        return f"ERROR: HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001 - probe must survive any tool failure
        return f"ERROR: {e}"
    return out if isinstance(out, str) else json.dumps(out)


def run_model(lane, tools, system):
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": USER_MSG},
    ]
    trace, t0, final, stop = [], time.time(), None, "completed"
    for rnd in range(1, MAX_ROUNDS + 1):
        if time.time() - t0 > MODEL_WALL_CAP_S:
            stop = "wall_cap"
            break
        try:
            resp = http_json(LLAMA, body={
                "model": lane, "messages": messages,
                "tools": tools, "max_tokens": 4096,
            }, timeout=GEN_TIMEOUT_S)
        except Exception as e:  # noqa: BLE001
            stop = f"gen_error: {e}"
            break
        choice = resp["choices"][0]
        msg = choice["message"]
        # Pass the assistant turn back VERBATIM (incl. reasoning_content —
        # Gemma 4's template requires thoughts kept between function calls;
        # Qwen3.8's handles it the same way, opencode-verified).
        messages.append({k: v for k, v in msg.items() if v is not None})
        tcs = msg.get("tool_calls") or []
        if not tcs:
            final = msg.get("content") or ""
            if choice.get("finish_reason") == "length":
                stop = "length"
            break
        for tc in tcs:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            result = call_tool(name, args) if name in ZIM_TOOLS else f"ERROR: unknown tool {name}"
            trace.append({"round": rnd, "tool": name,
                          "args": json.dumps(args)[:220],
                          "result_chars": len(result)})
            messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                             "content": result})
    else:
        stop = "max_rounds"
    low = (final or "").lower()
    return {
        "lane": lane,
        "rounds_used": trace[-1]["round"] if trace else 0,
        "tool_calls": len(trace),
        "used_zim_get": any(t["tool"] == "zim_get" for t in trace),
        "elapsed_s": round(time.time() - t0, 1),
        "stop": stop,
        "marker_hits": sorted(m for m in MARKERS if m in low),
        "hallucination_tells": sorted(t for t in HALLUCINATION_TELLS if t in low),
        "trace": trace,
        "final": final,
    }


def main():
    system = owui_system_prompt()
    tools = tool_specs()
    results = {}
    roster = MODELS
    only = os.environ.get("PROBE_MODELS")
    if only:
        wanted = {a.strip() for a in only.split(",")}
        roster = [(a, l) for a, l in MODELS if a in wanted]
    for alias, lane in roster:
        print(f"=== {alias} ({lane}) ===", flush=True)
        r = run_model(lane, tools, system)
        results[alias] = r
        print(json.dumps({k: v for k, v in r.items()
                          if k not in ("final", "trace")}), flush=True)
        for t in r["trace"]:
            print("   ", t["round"], t["tool"], t["args"][:130], flush=True)
        print("--- final (head) ---", flush=True)
        print((r["final"] or "(none)")[:1200], flush=True)
        print(flush=True)
    os.makedirs("bakeoff/results", exist_ok=True)
    out = time.strftime("bakeoff/results/zim-questline-probe-%Y-%m-%d-%H%M.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
