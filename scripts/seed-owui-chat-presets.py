#!/usr/bin/env python3
"""Seed params + the shared system prompt on the chat-class models (2026-08-19).

Canonical source for `params` on the chat lanes: the shared household system
prompt (thoroughness + tool-use policy — the gemma4 "lazy by default" fix,
probed live 2026-08-19: steering deepens thinking-channel planning and answer
completeness) plus each lane's HF-card sampler, num_ctx matching the
llama-swap lane, and native function calling (required for the pinned tool
belt on the OpenAI/LiteLLM path).

The prompt is deliberately MODEL-AGNOSTIC (no Gemma/Qwen control tokens) so
the 3-way chat bake-off — chat (gemma4-31b) vs chat-q38-trial (qwen3.8-27b)
vs chat-gemma-26b-trial (gemma4-26b-a4b) — differs only in the model.
{{CURRENT_DATE}} is an OWUI prompt variable, substituted server-side per chat.

Field ownership (read-modify-write like its siblings): this script REPLACES
`params` for the listed models and preserves everything else; meta.toolIds
belongs to seed-owui-chat-tools.py, meta.capabilities.vision to
seed-owui-model-capabilities.sh. Run order after a volume rebuild:
capabilities (creates records) -> this -> chat-tools. Idempotent.

Rebuild parity: model records are DB-only (open_webui_data volume).
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

SYSTEM = """\
You are the household's private assistant, running entirely on our own hardware in Rochester, New York. Today is {{CURRENT_DATE}}.

Effort: default to thorough. Work the problem out in your reasoning first — what is actually being asked, what an expert would flag, what could go wrong — then give a complete answer with the practical details, caveats, and edge cases that matter. Keep answers brief only when the question is genuinely trivial; never shave depth off a topic that deserves it.

Tools: you have real tools (offline Wikipedia and reference libraries, URL fetch and a browser, the household's notes, image generation, current time, and more). Use them instead of guessing. Reach for reference lookups for factual or encyclopedic depth, fetch or browse for anything current or link-shaped, and the notes tools for the household's own information. Ground your answer in what the tools return and say which facts came from where; if a tool fails or comes back empty, say so and answer from your own knowledge, clearly marked. Skip tools for pure reasoning, writing, or opinion.

Honesty and style: plain, direct prose. Structure long answers with headings or lists when it helps. Give numbers, dates, and names only from tool output or flagged as from memory, and state uncertainty plainly — one clear caveat beats vague hedging."""

# Sampler per HF model card; num_ctx mirrors the llama-swap lane ctx (keep in
# sync with docker/llama-swap-config.yaml when a lane's measured fit changes).
PARAMS = {
    # gemma4-31b-qat text lane (65536 since the 2026-08-17 vision split; the
    # stale 73728 predated it)
    "chat": {
        "system": SYSTEM, "function_calling": "native",
        "temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0,
        "num_ctx": 65536, "max_tokens": 32768,
    },
    # qwen3.8-27b lane (ctx 114688 + MTP; --reasoning-effort medium baked
    # server-side). Qwen 3.8-gen thinking sampler: temp 1.0 / top_k 20.
    "chat-q38-trial": {
        "system": SYSTEM, "function_calling": "native",
        "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0,
        "num_ctx": 114688, "max_tokens": 32768,
    },
    # gemma4-26b-a4b MoE lane (Gemma 4 family sampler, same as 31B).
    "chat-gemma-26b-trial": {
        "system": SYSTEM, "function_calling": "native",
        "temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0,
        "num_ctx": 65536, "max_tokens": 32768,
    },
}


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


for mid, want in PARAMS.items():
    rec = req("GET", "/api/v1/models/model?id=" + mid)
    assert rec, "%s model record not found — run seed-owui-model-capabilities.sh first" % mid

    if rec.get("params") == want:
        print("%s params already seeded" % mid)
        continue

    form = {
        "id": mid,
        "name": rec.get("name") or mid,
        "base_model_id": rec.get("base_model_id"),
        "meta": rec.get("meta") or {},
        "params": want,
        "access_grants": rec.get("access_grants") or [],
        "is_active": rec.get("is_active", True),
    }
    assert req("POST", "/api/v1/models/model/update?id=" + mid, form)

    rec = req("GET", "/api/v1/models/model?id=" + mid)
    got = rec.get("params") or {}
    assert got.get("system") == SYSTEM and got.get("function_calling") == "native", got
    print("verified: %s params seeded (system %d chars, fc=native, num_ctx=%s)"
          % (mid, len(SYSTEM), got.get("num_ctx")))
