#!/usr/bin/env python3
"""Seed params + the shared system prompt on the chat-class models (2026-08-19).

Canonical source for `params` on the chat lanes: the shared household system
prompt (thoroughness + tool-use policy — the gemma4 "lazy by default" fix,
probed live 2026-08-19: steering deepens thinking-channel planning and answer
completeness) plus each lane's HF-card sampler, num_ctx matching the
llama-swap lane, and native function calling (required for the pinned tool
belt on the OpenAI/LiteLLM path). The archive-lookup paragraph (added later
2026-08-19) encodes the Minish Cap post-mortem: zim_query's quoted-phrase
term-dropping, search-then-READ discipline, and no-memory-as-archive honesty.

The prompt is deliberately MODEL-AGNOSTIC (no Gemma/Qwen control tokens) so
the chat lanes differ only in the model. The 2026-08-19 3-way bake-off ended at
lai-30 (2026-09-01): the trial lanes are gone and the roster is `chat`
(heretic-31B) + `chat-fast` (HauhauCS-12B).
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

Archive lookups (the ZIM library): old guides and references use their own vocabulary — search with distinctive content phrases (item names, character names, exact in-world wording), not the game or article title. Prefer zim_search for multi-word queries; in zim_query a quoted phrase drops every other word in the query. Searching is never the last step: open the best hit with zim_get and read it before answering, paging with content_offset if needed. If the archive does not yield the answer, say so plainly — never present remembered details as if they came from the archive.

Honesty and style: plain, direct prose. Structure long answers with headings or lists when it helps. Give numbers, dates, and names only from tool output or flagged as from memory, and state uncertainty plainly — one clear caveat beats vague hedging."""

# Sampler per HF model card; num_ctx mirrors the llama-swap lane ctx (keep in
# sync with docker/llama-swap-config.yaml when a lane's measured fit changes).
PARAMS = {
    # `chat` = gemma4-31b-heretic text lane. MEASURED ceiling 2026-09-01 is
    # 65536 - identical to the gemma4-31b-qat lane it replaced at lai-30, so
    # this number did not move. Gemma 4 official sampler.
    "chat": {
        "system": SYSTEM, "function_calling": "native",
        "temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0,
        "num_ctx": 65536, "max_tokens": 32768,
    },
    # `chat-fast` = HauhauCS gemma4-12b QAT + its MTP drafter. num_ctx is the
    # full NATIVE 262144 (measured: loads at 12.5 GiB, 11.7 GiB card free) -
    # by far the roomiest lane on the rig. Sampler per the HauhauCS card
    # (temp 0.6 / top_k 64 / top_p 0.9 / min_p 0.05), which differs from the
    # Gemma-org defaults the 31B uses; the lane bakes repeat_penalty 1.1
    # server-side. Carries the same pinned tool belt as `chat` (lai-30).
    "chat-fast": {
        "system": SYSTEM, "function_calling": "native",
        "temperature": 0.6, "top_p": 0.9, "top_k": 64, "min_p": 0.05,
        "num_ctx": 262144, "max_tokens": 32768,
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
