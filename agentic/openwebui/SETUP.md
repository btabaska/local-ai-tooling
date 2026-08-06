# Open WebUI — the "close to Claude" chat layer

Open WebUI already runs in the base stack. These settings turn it from a chat box into something
closer to Claude's app experience: tool-using, document-grounded, with reusable "assistants." All
of this runs on your CPU/RAM — only the model itself uses the GPU.

> **Applied on this rig (2026-07-07) — the settings that fixed tool calling + web search.**
> These live in the `open_webui_data` DB (PersistentConfig), so they persist across restarts but
> are **not** reproduced by env alone — the compose env only seeds a *fresh* volume. To rebuild:
> - **External Tools (OpenAPI):** `http://mcpo:8000/time`, `/fetch`, `/context7` (add `/serena`,
>   `/sequential-thinking` after expanding mcpo). Use the `mcpo` container name, not `localhost`.
> - **Native Function Calling = Native** on tool-capable models only: `qwen3.6:64k`, `qwen3.6:27b`,
>   `qwen3.6:35b-a3b`, `devstral:24b`, `code:opencode`. Keep `gemma4*` / `tag:fast` on **Default**
>   (weak tool-callers). Attach `time`+`fetch` to each native model.
> - **Web Search → Bypass Embedding and Retrieval = ON**, engine **SearXNG**
>   (`http://192.168.10.2:8888/search?q=<query>` on the mini — no `&format=json` suffix, OWUI
>   strips it; lai-01/lai-03 replaced Kagi), result count 5, concurrent requests 5. (Seeded by
>   `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL` / `WEB_SEARCH_*` / `SEARXNG_QUERY_URL` in
>   `docker/docker-compose.yml`.) This is the fix for "search ran but the model said no results."
> - **Hybrid RAG + external reranker (lai-03):** hybrid search ON + enriched texts, TOP_K 20 →
>   reranker top 5, engine `external` → `http://llama-swap:8080/v1/rerank` model `qwen3-reranker`
>   (= rig `:9292` externally), markdown-header splitter + chunk-min-target 300, embedding batch 32.
>   Applied via the admin REST API (DB wins); seeds in compose. Full toggle list: foss-setup wiki
>   `runbooks/owui-search-rag.md`.
> - **Expanded mcpo tools:** `sequential-thinking` + `serena` added (register `http://mcpo:8000/serena`
>   and `http://mcpo:8000/sequential-thinking` in External Tools). `/repos` (host `REPOS_PATH`) is
>   mounted into mcpo so serena reaches your code.
>   ⚠️ **Serena exposes write tools** (`replace_content`, `safe_delete_symbol`, …) and `/repos` is
>   mounted read-write — a chat model with serena attached can edit your repos. If you only want
>   read-only code intel in chat, change the mount to `:ro` in `docker/docker-compose.yml` (note:
>   `:ro` disables serena's memory/onboarding writes). Serena for editing lives in OpenCode anyway.
> - Backups of the working volume live under `local-ai-tooling/backups/`.

## 1. Native tool calling (do this first)
Admin Panel → Settings → Models → pick a model → **Advanced Params → Function Calling = Native**.
This lets the model itself decide which tools to call each turn (vs the old prompt-injection method).
It only works well on tool-capable models — use your `chat` (Gemma 4) or point a model entry at
Devstral/Qwen for tool-heavy chats. Weak tool-callers will misbehave; keep those on Default.

## 2. Tools (give the model real capabilities)
Two ways to attach tools, both already wired in the base stack via **mcpo**:
- **OpenAPI tools (from mcpo):** Admin → Settings → **External Tools → +** → Type **OpenAPI**,
  URL `http://mcpo:8000/<name>` (e.g. `/serena`, `/fetch`, `/time`). One entry per mcpo subpath.
- **Native MCP (Streamable-HTTP):** Open WebUI ≥0.6.31 supports MCP directly — Type **MCP** for
  HTTP servers like Context7. Use mcpo for stdio-only servers.

Then attach tools to a model (Models → edit → Tools) or let users toggle them per-chat. Access is
permission-checked per user, so private tools stay private.

## 3. Knowledge / RAG (ground answers in your docs)
- Admin → Settings → **Documents**: set **Embedding = Ollama**, model `nomic-embed-text`.
- Turn on **Hybrid Search** (`ENABLE_RAG_HYBRID_SEARCH`) for BM25 + vector + rerank — much better
  retrieval than plain vectors. Add a reranker model if you want the top-tier quality.
- Create a **Knowledge base** (Workspace → Knowledge), upload docs, then attach it to a model or
  reference it in chat with `#`. With Native tool calling on, tell the model (in its system prompt)
  to call `query_knowledge_files` — native mode doesn't auto-inject knowledge, the model must fetch it.

## 4. Custom models = your version of Claude Projects / GPTs
Workspace → **Models → +**. A "model" here bundles: a base model + system prompt + attached tools +
attached knowledge + params. Example: a "SimplerGrants Reviewer" that uses `chat`, has the OSPO
docs knowledge base, the `serena` + `fetch` tools, and a review-focused system prompt. Reusable,
shareable to other users on the rig.

## 5. Functions (Python plugins that run in Open WebUI)
Admin → Settings → **Functions**. Three kinds worth knowing:
- **Filters** — inlet/stream/outlet hooks. Uses: an **auto-memory** filter (persist facts across
  chats — the closest thing to Claude's memory), token/cost tracking, PII redaction, translation.
- **Pipes** — custom "models"/providers or full agent pipelines (RAG, multi-step). A pipe can even
  expose multiple models (a "manifold").
- **Actions** — buttons under a message: export to PDF, summarize, trigger a webhook/CI.
- **Events** (0.10.0+) — run code on system events (signup gating, audit logging, self-install).
> Security: Functions/Tools execute arbitrary Python on the server. "Featured" ≠ vetted. Read the
> source before importing anything from the community catalog, and protect the `open_webui_data` volume.

## 6. The rest of the "Claude-like" surface (mostly toggles)
- **Web search:** Admin → Settings → Web Search → pick a provider (SearXNG self-hosted keeps it
  local; Tavily/Brave/DuckDuckGo also supported). Then use the globe icon in chat.
- **Code execution / artifacts:** Admin → Settings → **Code Execution** (Pyodide in-browser, or wire
  a Jupyter backend) renders and runs code from responses — the Open WebUI analog of artifacts.
- **Image input / vision:** attach a vision model in Ollama and Open WebUI handles image uploads.

## Suggested starting point
Enable Native tool calling on `chat`; attach `serena` + `fetch` from mcpo; set up `nomic-embed-text`
+ Hybrid Search; create one custom model for your most common workflow; add an auto-memory filter.
That covers ~80% of what people miss from Claude, all local.

---

## Custom model recipes (as built on this rig, 2026-07-07)

Two ready-to-recreate custom models. Workspace → Models → ➕, set the fields below, Save.

### Rig Coder — coding / agentic (qwen3.6:64k)
- **Base:** `qwen3.6:64k`  ·  **Tools:** serena, fetch, time  ·  **Function Calling:** Native
- **System prompt:** senior local coding assistant; use serena for symbol-level navigation before
  answering; never claim "no results" when a tool returned data; don't edit unless asked.
- **Capabilities:** Vision on, Citations on.
- **Advanced Params:** `num_ctx=65536`, `temperature=0.3`, `top_p=0.95`, `top_k=20`, `min_p=0`,
  `repeat_penalty=1.1`, `presence_penalty=0` (overrides the aggressive 1.5 baked into the model),
  `keep_alive=30m`. Leave `think` on. **Traps:** never set `format=json` or `num_gpu`; keep mirostat off.

### Rig Thinker — general / non-coding (gemma4:31b-it-qat)
- **Base:** `gemma4:31b-it-qat`  ·  **Tools:** fetch, time (no serena)  ·  **Function Calling:** Native
  (**fall back to Default if tool calls misfire** — Gemma is a weaker tool-caller).
- **System prompt:** general-purpose thinking assistant (reasoning, writing, analysis, planning);
  think step by step; use web search / fetch for current facts; never claim "no results" on data.
- **Capabilities:** Vision on (gemma4 has a vision projector), Citations on.
- **Advanced Params:** `num_ctx=49152`, `temperature=0.7`, `top_p=0.95`, `top_k=64` (Gemma's rec),
  `min_p=0`, `repeat_penalty=1.1`, `presence_penalty=0`, `keep_alive=30m`. Leave `think` on.
  ⚠️ Gemma bakes **no** `num_ctx`, so leaving it blank runs at ~4k — always set it.

### Web search: globe toggle → native `search_web` tool (0.10.x)
Web search (SearXNG, Bypass-Retrieval on) is still activated by the **🌐 globe icon**, but since
OWUI 0.10.x with Native function calling the model **does** get callable builtin `search_web` +
`fetch_url` tools (the "Agentic Research" loop): the model picks its own queries, OWUI runs them
against SearXNG and feeds results back. Requires: globe on (or model capability Web Search) + a
real UI session (builtin tools are only injected for socket sessions — bare API calls get the
`tool_calls` back to execute themselves). On `legacy` function-calling models the old flow remains:
OWUI runs the search up front and injects results; the model never sees a tool.

### VRAM curve — max `num_ctx` fully on GPU (RTX 3090 Ti 24 GB, flash-attn + q8 KV)

Measured for `gemma4:31b-it-qat` (18 GB weights); `qwen3.6:64k` behaves similarly:

| num_ctx | VRAM | Processor | Note |
|--------:|-----:|-----------|------|
| 32768 | 18 GB | 100% GPU | |
| 49152 | 18 GB | 100% GPU | **tag:fast coexists** (no eviction) — best for daily use |
| 65536 | 19 GB | 100% GPU | max solo; **evicts** the tag:fast helper |
| 73728+ | 20 GB+ | CPU offload | avoid — spills off GPU |

Rule of thumb: **≤49152** if you want the small utility model (`tag:fast`) resident alongside a big
model; **65536** is the ceiling for full-GPU speed on a single model. Above ~72k it offloads to CPU.
After a real task, run `ollama ps` — any CPU/RAM split means back the context off.
