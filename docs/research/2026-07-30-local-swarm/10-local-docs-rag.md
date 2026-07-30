# Local Documentation Corpus + Retrieval for Coding Agents

**Research date:** 2026-07-30
**Rig:** RTX 3090 Ti 24 GB · 64 GB RAM · 5 TB NVMe · CachyOS/Arch · Docker · i7-12700K
**Constraint that drives everything:** the GPU is contended (llama-swap `big` group, one model at a time, must yield to gaming/ComfyUI). Any always-on retrieval service must be **CPU-only and cheap**.

> Verification policy: everything below was checked against live sources on 2026-07-30 via HTTP fetch. Claims I could not verify are explicitly marked **(unverified)**. Measured numbers were produced by actually downloading and indexing a docset during this research — those are marked **(measured)**.

---

## 0. TL;DR — the verdict

**Build this, in this order:**

1. **Mirror DevDocs archives** (`https://downloads.devdocs.io/<slug>.tar.gz`) for the stable language/framework tier. A curated 32-docset set = **442 MB** of `db_size`, ~**1.1 GB** extracted. Verified against the live manifest (820 docsets, **8.50 GB** total).
2. **Mirror `llms-full.txt` + git-cloned markdown** for the agent stack and the fast-moving Python tooling DevDocs does *not* carry (uv, ruff, pytest, SQLAlchemy, pydantic, MCP spec, LiteLLM, llama.cpp, Claude Code, opencode, pi). ~**35 MB**.
3. **Retrieval = SQLite FTS5 (BM25) over a normalized markdown tree, plus ripgrep.** Not vector RAG. **(measured)**: indexing the bash docset (132 pages, 0.54 M chars) took **5 ms**, and a BM25 query returned the exactly-correct page in **0.57 ms**. There is no CPU/GPU cost worth talking about.
4. **Expose it as a single CLI (`docs`) first**, then wrap that CLI in a 3-tool FastMCP streamable-HTTP server on the rig — same pattern as the existing `fleet_mcp.py` (:8765). opencode consumes it as `"type": "remote"`; pi consumes the **CLI via its `bash` builtin** (pi has no core MCP — see §4.3).
5. **Only if BM25 measurably fails**, add (a) a CPU reranker — `ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF` served by the *same* llama-swap CPU-pinned pattern as your existing embedder, then (b) `sqlite-vec` dense vectors using your existing `embed` alias. Both are additive to the same SQLite file.

**Do not build:** a Qdrant/Chroma/Meilisearch service, a self-hosted Firecrawl, or a Context7 mirror. Reasons in §2.4 and §1.6.

**Total disk: ~1.3 GB. Total first build: ~15–25 min wall clock, mostly download.** That is the whole point — this is a cheap, high-leverage project.

---

## 1. What to mirror, and how

### 1.1 Tier A — DevDocs archives (the backbone)

DevDocs is `freeCodeCamp/devdocs` (Ruby/Sinatra + client-side JS, MPL-2.0). Its README documents Docker self-hosting and `thor docs:download` (<https://github.com/freeCodeCamp/devdocs>).

**But you should not run the DevDocs container at all.** The valuable part is the archive format, which you can fetch with `curl` and index yourself.

**Verified archive layout (measured — I downloaded and extracted `bash.tar.gz` during this research):**

```
$ curl -sL -o bash.tar.gz https://downloads.devdocs.io/bash.tar.gz   # 389,283 bytes
$ tar xzf bash.tar.gz
  ├── *.html          132 files — one cleaned HTML fragment per page (no chrome, no nav)
  ├── db.json         958,336 B — { "page-slug": "<html fragment>" } for every page
  ├── index.json       51,943 B — { entries: [{name, path, type}], types: [...] }
  │                              → 508 symbol entries for bash, typed:
  │                                Builtin Commands / Functions / Manual /
  │                                Parameters and Variables / Reserved Words
  └── meta.json           200 B — {"name","slug","release":"5.3","mtime":1784459519,"db_size":958336}
```

Three things make this format excellent for our purpose:

- **`db.json` is a ready-made corpus.** One JSON file, page-slug → clean HTML fragment. No crawling, no Playwright, no rate limits, no robots.txt.
- **`index.json` is a free symbol table.** 508 typed entries for bash alone. This gives you an exact-name lookup path (`printf` → `bash-builtins#index-printf`) that is *far* more token-efficient than semantic search for API reference. Most local-docs projects miss this.
- **`meta.json` carries `release` and `mtime`** → both version pinning and staleness detection come for free (§5).

**The live manifest** (verified 2026-07-30):

```bash
curl -sL https://devdocs.io/docs.json   # 302 → /assets/docs-<sha>.json, 363 KB
```

- **820 docsets**, **8.50 GB** total `db_size`.
- Beware: `https://documents.devdocs.io/docs.json` also returns 200 but is a **stale 2018 snapshot** (318 docsets, 2.00 GB). Use `devdocs.io/docs.json` with `-L`.

**Curated set with verified sizes and freshness** (`db_size`, and DevDocs' own `mtime`):

| slug | db_size | last scraped |
|---|---:|---|
| `python~3.14` | 20.71 MB | 2026-06-25 |
| `rust` | 69.92 MB | 2026-07-12 |
| `dom` | 63.40 MB | 2025-09-15 |
| `sqlite` | 16.36 MB | 2026-04-14 |
| `numpy~2.4` | 15.30 MB | 2026-03-04 |
| `javascript` | 14.01 MB | 2026-07-09 |
| `pandas~3` | 14.76 MB | 2026-04-15 |
| `react` | 8.93 MB | 2025-10-15 |
| `postgresql~18` | 8.46 MB | 2026-03-18 |
| `django~6.1` | 7.52 MB | 2026-07-03 |
| `http` | 7.05 MB | 2026-06-21 |
| `node~24_lts` | 6.28 MB | 2026-03-04 |
| `git` | 6.14 MB | 2026-04-22 |
| `eslint` | 5.89 MB | 2026-05-26 |
| `go` | 4.69 MB | 2026-02-23 |
| `fastapi` | 4.54 MB | 2026-05-26 |
| `docker` | 4.33 MB | 2022-06-02 ⚠ stale |
| `nginx` | 2.24 MB | 2026-05-26 |
| `tailwindcss` | 2.16 MB | 2025-07-04 |
| `npm` | 2.15 MB | 2024-01-06 |
| `typescript` | 2.01 MB | 2026-04-22 |
| `redis` | 1.92 MB | 2023-04-12 |
| `webpack~5` | 1.84 MB | 2024-12-08 |
| `vue~3` | 1.52 MB | 2026-06-21 |
| `kubernetes` | 1.28 MB | 2025-06-01 |
| `flask` | 1.24 MB | 2025-02-12 |
| `svelte` | 1.02 MB | 2025-09-15 |
| `bash` | 0.96 MB | 2026-07-19 |
| `jest` | 0.73 MB | 2022-08-27 |
| `vite` | 0.69 MB | 2026-03-18 |
| `click` | 0.60 MB | 2024-06-12 |
| `man` | 143.22 MB | 2024-08-20 |

**Totals (verified):** 18-docset core = **247 MB**; 32-docset curated (above) = **442 MB**; all 820 = 8.50 GB.
**Extracted-on-disk multiplier (measured):** bash was 0.96 MB `db_size` → 2.5 MB extracted (HTML files + db.json + index.json are all shipped, i.e. the page text is stored twice). So curated ≈ **1.1 GB** extracted, or **~450 MB if you keep only `db.json` + `index.json` + `meta.json`** and delete the per-page HTML. Do the latter.

**Fetch script** (drop in `scripts/docs-sync-devdocs.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/docs/devdocs
MANIFEST=$(mktemp); curl -sL https://devdocs.io/docs.json -o "$MANIFEST"
while read -r slug; do
  want_mtime=$(jq -r --arg s "$slug" '.[]|select(.slug==$s)|.mtime' "$MANIFEST")
  have_mtime=$(jq -r '.mtime // 0' "$ROOT/$slug/meta.json" 2>/dev/null || echo 0)
  [ "$want_mtime" = "$have_mtime" ] && { echo "ok   $slug"; continue; }
  echo "sync $slug ($have_mtime -> $want_mtime)"
  mkdir -p "$ROOT/$slug"
  curl -sL "https://downloads.devdocs.io/${slug}.tar.gz" \
    | tar xz -C "$ROOT/$slug" --wildcards 'db.json' 'index.json' 'meta.json'
done < /opt/docs/devdocs.slugs
```

> ⚠ **`docker` is the one bad DevDocs entry** — last scraped 2022-06-02. Get Docker/Compose docs from `llms.txt` instead (§1.2, verified live: `https://docs.docker.com/llms.txt`, 5,710 B, `content-type: text/markdown`).

**Alternative packaging — Kiwix ZIM.** `https://download.kiwix.org/zim/devdocs/` (redirects to `lb.download.kiwix.org`) carries **800+ per-docset ZIMs**, refreshed roughly quarterly: `devdocs_en_python_2026-05.zim` 4.1 M, `devdocs_en_rust_2026-07.zim` 5.9 M, `devdocs_en_postgresql_2026-05.zim` 2.5 M, `devdocs_en_docker_2026-07.zim` 1.7 M (verified). ZIMs are smaller (compressed) and have a built-in Xapian full-text index, and `mozanunal/llm-tools-kiwix` (91★) already wraps them with `kiwix_search` / `kiwix_read` tools — but it's an **`llm` CLI plugin, not an MCP server** (verified). **Verdict: skip ZIM.** You lose `index.json`'s symbol table and gain a `libzim` dependency. Only revisit if you want offline Wikipedia/StackExchange too.

### 1.2 Tier B — `llms.txt` / `llms-full.txt`

Spec: <https://llmstxt.org/> (published 2024-09-03, by Jeremy Howard/Answer.AI). `llms.txt` = an H1 + blockquote + H2-delimited link lists; `llms-full.txt` = the whole doc corpus concatenated as one markdown file. Directories: **`directory.llmstxt.cloud`** and **`llmstxt.site`**.

**Adoption reality check (verified 2026-07-30):** `directory.llmstxt.cloud` lists **309 `llms.txt` and 252 `llms-full.txt`** entries. That is real but far from universal — treat `llms.txt` as an *opportunistic* source, not a strategy.

**Live probe results for your exact stack** (HTTP status + actual byte size, GET, 2026-07-30):

| Source | URL | Result |
|---|---|---|
| Anthropic / Claude Code | `docs.claude.com/llms-full.txt` | **200 · 25,234,887 B** ✅ |
| MCP spec + guides | `modelcontextprotocol.io/llms-full.txt` | **200 · 2,260,204 B** ✅ (v2026-07-28) |
| pydantic | `docs.pydantic.dev/latest/llms-full.txt` | **200 · 1,942,373 B** ✅ |
| Next.js | `nextjs.org/docs/llms.txt` | 200 · 42,433 B (index only; says "Next.js 16.2.12") |
| React | `react.dev/llms.txt` | 200 · 14,347 B (index only) |
| Docker | `docs.docker.com/llms.txt` | 200 · 5,710 B (index only) |
| LiteLLM | `docs.litellm.ai/llms.txt` | 200 · 7,474 B (index only) |
| uv | `docs.astral.sh/uv/llms.txt` | 200 · 5,145 B (index only) |
| ruff | `docs.astral.sh/ruff/llms.txt` | 200 · 1,773 B (index only) |
| FastAPI | `fastapi.tiangolo.com/llms.txt` | **404** ❌ |
| pytest | `docs.pytest.org/en/stable/llms.txt` | **404** ❌ |
| SQLAlchemy | `docs.sqlalchemy.org/en/20/llms.txt` | ⚠ 200 but returns **HTML** — a soft-404, not real |
| TypeScript | `typescriptlang.org/llms.txt` | **404** ❌ |
| PostgreSQL | `postgresql.org/llms.txt` | **404** ❌ |
| Node | `nodejs.org/docs/llms.txt` | **404** ❌ |
| pnpm | `pnpm.io/llms.txt` | **404** ❌ |
| opencode | `opencode.ai/llms.txt`, `/docs/llms.txt` | **404** ❌ |
| uv/ruff `llms-full.txt` | `docs.astral.sh/{uv,ruff}/llms-full.txt` | **404** ❌ (index only) |

**The `.md` suffix trick (verified, and more useful than `llms.txt`):** Mintlify- and Next.js-docs-based sites serve a markdown source for any page by appending `.md`:

| Probe | Result |
|---|---|
| `modelcontextprotocol.io/docs/develop/build-server.md` | 200 · 97,692 B markdown |
| `docs.claude.com/en/docs/claude-code/mcp.md` | 200 · 80,866 B markdown |
| `nextjs.org/docs/app/getting-started/installation.md` | 200 · 12,987 B markdown (frontmatter + MDX) |
| `react.dev/learn/thinking-in-react.md` | 200 · 23,037 B markdown |
| `docs.astral.sh/uv/getting-started/installation.md` | 404 (mkdocs-material — no `.md` route) |

So the general **bulk-fetch algorithm** for a dependency list is a 4-step cascade per package:

1. Try `<docs_root>/llms-full.txt` → done, one file.
2. Else fetch `<docs_root>/llms.txt`, parse the H2 link lists, and fetch each linked URL (Mintlify's `llms.txt` already links `.md` variants).
3. Else fetch `<docs_root>/sitemap.xml` and try `<page>.md` for each URL; if that 404s, fetch the HTML and convert (§1.5).
4. Else fall back to the source repo's `docs/` tree (§1.3).

Where do doc roots come from? Read them out of your own lockfiles: PyPI's `https://pypi.org/pypi/<name>/json` exposes `info.project_urls.Documentation`; npm's `https://registry.npmjs.org/<name>` exposes `homepage`/`repository`. That makes the whole thing dependency-driven and version-aware. **(unverified — I did not build/run this cascade end to end; the individual probes above are verified.)**

### 1.3 Tier C — git-clone the docs the web doesn't serve well

For the agent stack itself, cloning the docs directory is strictly better than scraping — it's markdown already, it's versioned, and `git pull` is the sync mechanism.

```bash
# --filter=blob:none --sparse keeps these tiny
git clone --filter=blob:none --depth=50 https://github.com/modelcontextprotocol/modelcontextprotocol   # spec + docs, MCP rev 2026-07-28
git clone --filter=blob:none --depth=50 https://github.com/anomalyco/opencode                          # NOTE: sst/opencode now 301s here
git clone --filter=blob:none --depth=50 https://github.com/earendil-works/pi                           # docs/ = rpc.md json.md sdk.md extensions.md
git clone --filter=blob:none --depth=50 https://github.com/ggml-org/llama.cpp                          # tools/server/README.md etc.
git clone --filter=blob:none --depth=50 https://github.com/BerriAI/litellm                             # docs/my-website/docs
git clone --filter=blob:none --depth=50 https://github.com/mdn/content                                 # optional; large, and `dom` docset already covers it
```

All six URLs returned 200 on 2026-07-30 (`sst/opencode` → `301 → github.com/anomalyco/opencode`).

Also worth pulling as plain archives (verified sizes, live `Content-Length` on 2026-07-30):

- **Python stdlib, plain text**: `https://docs.python.org/3/archives/python-3.14-docs-text.tar.bz2` — **3,318,652 B**, `Last-Modified: 2026-07-19`. This is the single best Python source: pre-rendered plain text, no HTML stripping needed, and complementary to the `python~3.14` docset.
- **PostgreSQL 18 manual PDF**: `https://www.postgresql.org/files/documentation/pdf/18/postgresql-18-A4.pdf` — **15,771,040 B**, `Last-Modified: 2026-05-14`. Only if you want more than the `postgresql~18` docset; PDF needs `docling`/`markitdown` to become text, so probably skip.
- **Bash source tarball** (contains the texinfo manual): `https://ftp.gnu.org/gnu/bash/bash-5.3.tar.gz` — 11,355,854 B. The `bash` docset (5.3, scraped 2026-07-19) already covers this. Skip.

### 1.4 Tier D — package-source-derived docs (the highest-value tier, and the one everyone skips)

For your *actual installed* dependency versions, the web docs are the wrong source and the installed package is the right one. This is the only tier that is **guaranteed version-correct**, and it's where local retrieval genuinely beats Context7.

- **Python**: for every dist in the project's `.venv`, harvest `README*`, `*.pyi` stubs, `py.typed` modules' `__doc__` strings, and any bundled `docs/`. `python -m pydoc -w` or a ~50-line `importlib.metadata` + `ast` walker gets module/class/function docstrings with signatures. `uv pip list --format=json` gives you the exact version to stamp on each record.
- **TypeScript/Node**: `node_modules/<pkg>/README.md` plus the `.d.ts` files. `.d.ts` is the single most useful artifact for a local model — it's the exact API surface with exact types, and it's tiny.
- **Volume**: a mid-size FastAPI project's `.venv` READMEs + stubs are typically single-digit MB; `node_modules/**/README.md` for a Next.js app is typically 10–40 MB **(unverified — depends entirely on the project)**.

Index these into a **per-project** shard of the same SQLite DB (`source='venv:<project>'`), rebuilt on lockfile change (§5).

Note that `serena` already covers *your own* code symbols via LSP — Tier D is about *dependency* symbols, which serena does not index. They're complementary, not overlapping.

### 1.5 Scrapers/converters — only for the stragglers

You need one of these only for sites that fail steps 1–3 of the cascade. Live versions as of 2026-07-30:

| Tool | Version (verified) | Verdict for this rig |
|---|---|---|
| **trafilatura** | 2.1.0 (2026-06-07, PyPI) | ✅ **Use this.** Pure Python, no browser, no models, fast on CPU. `trafilatura --markdown -u URL`. Best effort/benefit for static docs sites. |
| **markitdown** | 0.1.7 (2026-07-29, PyPI, Microsoft) | ✅ Use for the odd PDF/DOCX/EPUB. Base install is light; extras are opt-in (`[pdf]`, `[docx]`…). No MCP server in the main repo (verified). |
| **docling** | 2.117.0 (2026-07-30, PyPI, 64k★) | ⚠ Only if you need PDF layout understanding. Pulls VLM/layout models (GraniteDocling 258M). Overkill for HTML. |
| **crawl4ai** | 0.9.2 (2026-07-15) | ⚠ Requires Playwright/Chromium. Real capability (`crwl URL --deep-crawl bfs --max-pages N`, sitemap seeding, prefetch mode). Use **only** for JS-rendered docs sites. Don't run its Docker server persistently. |
| **firecrawl** | self-hostable, AGPL-3.0 (SDKs MIT) | ❌ Skip. Self-hosting needs Redis + Playwright workers, and the README explicitly says cloud has "additional features". Wrong effort/benefit here. |
| **Zeal / Dash docsets** | Zeal is Qt6, GPLv3; uses the Dash docset format | ❌ Skip as a *pipeline*. Docsets are a `.tarix`/SQLite bundle you'd have to unpack anyway, and the freeCodeCamp DevDocs archive is a cleaner, better-documented source of the same content. Zeal is a fine *human* GUI; it is not the agent path. |

### 1.6 Context7 — can you mirror it? No.

`upstash/context7` (<https://github.com/upstash/context7>) ships the **MCP server + CLI only, MIT**. The README is explicit: *"The supporting components — API backend, parsing engine, and crawling engine — are private and not part of this repository."* The corpus is not in the repo and there is no local mode or mirroring path (verified 2026-07-30).

What it serves: two tools, `resolve-library-id` (name → Context7 ID) and `query-docs` (ID + query → doc snippets). Also a REST API (`context7.com/docs/api-guide`), a hosted MCP at `https://mcp.context7.com/mcp` (what your `opencode.json` uses today), and a `ctx7` CLI.

**Implication:** you cannot replace Context7 by mirroring it — you replace it by *rebuilding* the same shape (name → source → snippets) from Tiers A–D. Which is exactly what this plan does. Keep `context7` configured as the **cloud fallback for libraries you didn't mirror**, and let the local server win for the ones you did. That is the right division of labor, and it's also the offline-resilience story.

---

## 2. Retrieval architecture — the verdict

### 2.1 The measurement that settles it

I built the whole thing at small scale during this research **(measured, on this Mac — the 12700K will be in the same order of magnitude, likely faster on the index step)**:

```
bash docset: 132 pages, 541 KB extracted text (~134 k tokens)
  HTML→text (regex strip)        : 0.02 s
  SQLite FTS5 index build        : 0.005 s   (tokenize='porter unicode61')
  BM25 query, top-5              : 0.57 ms
  Query "parameter expansion default" → #1 hit: shell-parameter-expansion  ✅ exactly right
  sqlite3 3.51.0 (FTS5 compiled in by default)
```

Extrapolating the curated corpus: 442 MB `db_size` ≈ **~500–600 MB of extracted text ≈ ~150 M tokens**, which at the measured rate is a **~10–30 s full index build** and **sub-10 ms queries**. There is no service to run, no daemon, no RAM budget, no GPU. The index file will be roughly **1.5–2× the text size** with FTS5 content storage, so budget **~1 GB** for the DB **(unverified extrapolation)**.

Against that baseline, every fancier option has to justify itself. Most can't.

### 2.2 Ranked options

**① Full-text search — DO THIS FIRST. Confidence: high.**

- **SQLite FTS5 + BM25** — zero-install (in Python's stdlib `sqlite3`), single file, trivially backed up, supports `porter unicode61` stemming, prefix queries, `snippet()`/`highlight()` built in (which gives you your token-bounded excerpts for free), and `bm25()` with per-column weights so you can boost titles/headings. It also sits in the *same file* as any future `sqlite-vec` table, so upgrading to hybrid is additive, not a migration.
- **ripgrep** — keep the markdown tree on disk next to the DB and let the agent `rg` it directly. This is the escape hatch for exact strings, error messages, and regex, and it costs nothing.
- **Tantivy / Zoekt / Meilisearch / Typesense** — all good software; all are a *service* (or an FFI dependency) that buys you very little at 500 MB of docs. Meilisearch is at **v1.51.0 (2026-07-27)** and is genuinely nice (hybrid search, typo tolerance), but it's a resident process with a RAM budget on a box whose whole design principle is "nothing resident that isn't earning its keep." Zoekt is built for *code* at Google scale, not prose. **Revisit Meilisearch only if you later want typo-tolerant search from Open WebUI for humans.**

**② Vector RAG — DO NOT DO THIS FIRST. Confidence: high.**

If/when you add it: **`sqlite-vec`** (asg017, Mozilla-Builders-backed) is the right choice specifically because it lives in the SQLite file you already have — `vec0` virtual tables, pure C, no deps, float/int8/binary vectors, metadata/partition-key filtering. Still explicitly **pre-v1 with breaking changes expected** (verified). Alternatives: LanceDB (great, but a separate embedded store), Chroma/Qdrant (services — no), pgvector (you'd need Postgres resident — no), usearch (fine, but no SQL).

Why not first:
- Embedding the corpus costs real CPU time on the persistent 0.6B embedder (§6), and every re-sync re-embeds the deltas.
- Docs queries from a coding agent are overwhelmingly *lexical* — `Depends`, `--pooling last`, `TypeError: Cannot read properties`, `pytest.fixture(scope=`. BM25 is not merely adequate at these; it is better than dense retrieval at them.
- Where dense wins is paraphrase ("how do I make FastAPI validate a nested body?" → `pydantic` model docs). That's a real gap, but it's the *second* problem, and the reranker (below) closes much of it more cheaply.

**③ Hybrid + reranking — the correct step 2. Confidence: high on the direction, medium on the magnitude.**

The best-documented quantification remains Anthropic's *Contextual Retrieval* (2024-09-19, <https://www.anthropic.com/news/contextual-retrieval>): contextual embeddings + contextual BM25 cut top-20 retrieval failure by **49%** (5.7% → 2.9%), and **adding a reranker took it to 67%** (5.7% → 1.9%). Note the shape of that result — **reranking contributed a large share of the total gain**, which is the argument for adding the reranker *before* the dense index, not after.

CPU-viable rerankers verified available as GGUF on 2026-07-30:

| Model | GGUF | Notes |
|---|---|---|
| **`Qwen3-Reranker-0.6B`** | **`ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF`** (40k downloads) | ✅ **Pick this.** Official ggml-org build. MTEB-R 65.80, **MTEB-Code 73.42**, 32k ctx, yes/no logit scoring, released 2025-06-05. |
| `bge-reranker-v2-m3` | `gpustack/bge-reranker-v2-m3-GGUF` | Solid, smaller, the model llama.cpp's own docs name as the reference reranker. |
| `jina-reranker-v2-base-multilingual` | `gpustack/...-GGUF` | Fine alternative. |

llama.cpp serves these natively: the server README documents `--reranking` ("requires a reranker model (such as bge-reranker-v2-m3) and the `--embedding --pooling rank` options"), with endpoints `/rerank`, `/v1/rerank`, `/v1/reranking` (verified). **So the reranker slots into your existing llama-swap config as a second CPU-pinned persistent model, exactly like `qwen3-embed`** — same `CUDA_VISIBLE_DEVICES=""` trick, same `-ngl 0`, and it never touches the GPU or contends with `coder`. LiteLLM can front it the same way it fronts `embed`.

**④ "Just let the model grep" — right for code, insufficient for docs. Confidence: medium-high.**

The strongest published argument is Cline's (2025-05-27, <https://cline.bot/blog/why-cline-doesnt-index-your-codebase-and-why-thats-a-good-thing>): chunking fragments interconnected logic; indexes decay on every merge; embeddings duplicate proprietary IP. Note honestly that **the post contains no benchmarks** — it's a design argument, not evidence. Claude Code, opencode, and pi all ship grep/find builtins and no code index, which is convergent industry behavior, but that's not a measurement either.

Where pure-grep breaks down for *docs*, and why you still want an index:

- **Vocabulary mismatch.** Your agent doesn't know the doc calls it "dependency injection" when it typed "how do I share a DB session." Grep returns nothing; BM25 with stemming returns something; a reranker returns the right thing.
- **No corpus map.** `rg` over 500 MB with no ranking returns hundreds of hits with no notion of which page is *about* the topic. BM25 exists precisely to rank that.
- **Token cost of iteration.** Each failed grep round-trip costs a turn. On a 131k-ctx local Qwen3.6 doing an agentic loop, three wasted `rg` calls is a meaningful fraction of the budget, and local models are notably worse than frontier models at recovering from a bad search.
- **But**: keep `rg` available anyway. For exact error strings and flag names it is strictly better, and it costs one line in AGENTS.md.

### 2.3 Recommended build, concretely

```
/opt/docs/
  raw/
    devdocs/<slug>/{db.json,index.json,meta.json}      # tier A
    llms/<source>/<name>.md                            # tier B
    repos/<org>/<repo>/                                # tier C (git)
    venv/<project>/                                    # tier D (generated)
  md/                                                  # normalized markdown tree  ← ripgrep lives here
    <source>/<doc-id>.md                               #   YAML frontmatter: source, version, url, title, mtime
  index.db                                             # SQLite: docs, chunks, chunks_fts (FTS5), symbols
                                                       #   later: chunks_vec (sqlite-vec)  — same file
```

Schema sketch:

```sql
CREATE TABLE docs(id TEXT PRIMARY KEY, source TEXT, version TEXT, title TEXT, url TEXT, path TEXT, mtime INT);
CREATE TABLE chunks(id INTEGER PRIMARY KEY, doc_id TEXT, heading TEXT, ord INT, body TEXT);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  heading, body, content='chunks', content_rowid='id', tokenize='porter unicode61');
CREATE TABLE symbols(name TEXT, type TEXT, doc_id TEXT, anchor TEXT, source TEXT);   -- from DevDocs index.json
CREATE INDEX symbols_name ON symbols(name COLLATE NOCASE);
```

**Chunking:** split on markdown headings (H2/H3), target ~1,000–1,500 characters with the heading path prepended to each chunk ("Bash > Shell Expansions > Shell Parameter Expansion"). That heading-path prefix is a poor man's contextual retrieval and it costs nothing. Store `bm25(chunks_fts, 4.0, 1.0)` weighting so headings dominate.

### 2.4 What I'm explicitly telling you not to build

- No Qdrant/Chroma/Weaviate container. Resident RAM + a second data store for 500 MB of text.
- No self-hosted Firecrawl. Redis + Playwright workers for a job `trafilatura` does synchronously.
- No DevDocs web container. You want the archives, not the Sinatra app.
- No GPU-resident embedding/reranking service. Both models are CPU-pinned or they don't ship.
- No Open WebUI knowledge-collection reuse for this. Your `#homelab-wiki` collection is the right tool for *wiki prose read by humans*; it runs every query through the embedder and doesn't give agents a citation-bearing snippet API.

---

## 3. Existing MCP servers — reuse or build?

I searched GitHub for local-docs MCP servers on 2026-07-30. Findings, with stars and last push:

| Repo | ★ | Pushed | Assessment |
|---|---:|---|---|
| **`arabold/docs-mcp-server`** | — | v**2.4.5**, 2026-07-25 | **The serious one.** Indexes websites, GitHub repos, npm, PyPI, and **local files**; probes `llms.txt` for curated links and prefers markdown; Playwright for SPAs; optional semantic search with **Ollama (local)**, OpenAI, Gemini, Azure embedders; Docker: `docker run -v docs-mcp-data:/data -p 6280:6280 ghcr.io/arabold/docs-mcp-server:latest --protocol http --host 0.0.0.0 --port 6280`. Recent releases are about vector-KNN performance, configurable embedding dimension, and an IR-grounded eval framework. |
| `Magic-Man-us/dq-toolkit` | 2 | 2026-07-25 | **Architecturally the closest to my recommendation** and worth reading even if you don't use it: all-Rust, offline, **one SQLite DB with FTS5 + porter stemming** (explicitly *not* vectors), at `~/.local/share/dq/code.db`; crates `dq-scan` (tree-sitter symbols), `dq-ingest`, `dq-mcp`; tools `search_index`, `get_record`, `goto_definition`, `find_references`, `explore_symbol`, `grep_source`, `ast_query`, `fetch_doc_page`. **Too new to depend on (2★, 44 commits) and its 8-tool surface is too wide for a 131k-ctx local model.** Steal the design, not the dependency. |
| `cyberagiinc/DevDocs` | 2,098 | — | UI-based doc-scraping MCP server. Heavier than needed; name collides with freeCodeCamp DevDocs. |
| `elblanco2/devdocs-mcp-server`, `katvito/devdocs-mcp`, `JavierDevCol/devdocs-mcp`, `jiegec/devdocs-mcp-server`, `emaland/devdocs-mcp` | 1–3 each | 2025-08 → 2026-06 | Thin wrappers over devdocs.io. All ≤3★. Hobby quality. |
| `mozanunal/llm-tools-kiwix` | 91 | — | ZIM search, but an **`llm` CLI plugin, not MCP**. |
| `g-cqd/apple-docs` | 18 | 2026-07-26 | Not your stack, but a good reference for the "CLI + MCP + static site over one local corpus" shape. |

**Verdict:** **build, but steal.** Concretely:

- **Try `arabold/docs-mcp-server` v2.4.5 first as a 30-minute spike** — it's the only mature option, it already does llms.txt-aware scraping and local-file indexing, and if its search quality is good enough you're done in an afternoon. Point its embedder at your LiteLLM `embed` alias (it speaks OpenAI-compatible + Ollama).
- **Reject it if** (a) its tool surface is too wide for your local models' context, or (b) you want the DevDocs `index.json` symbol table, `.venv`/`node_modules` Tier-D ingestion, and version-stamping tied to *your* lockfiles — none of which it does. Those are the things that make this corpus better than Context7, and they're ~300 lines of Python.

Given you already run `fleet_mcp.py` (FastMCP streamable-HTTP, :8765) and your knowledge base says *"the tools ARE the skills library"*, writing `docs_mcp.py` in the same shape is the lower-friction path and fits your existing ops/systemd/mcpo pattern exactly.

---

## 4. The MCP interface design

### 4.1 CLI first — this is the important architectural call

Write the **`docs` CLI** as the real product, and make MCP a thin wrapper over it. Reasons specific to your rig:

- **pi has no MCP in core** (verified — the README: *"Pi intentionally excludes certain features—like sub-agents, plan mode, and MCP"*). MCP in pi means installing a third-party extension. But pi has a **`bash` builtin**. A CLI works in pi *today*, with zero extension risk, at the cost of ~2 lines in `AGENTS.md`.
- **Zero token overhead.** An MCP tool schema is unconditionally in-context every turn. A CLI documented in AGENTS.md costs ~60 tokens of prose and the model already knows how to run commands. `pi-mcp-adapter`'s README makes the same point bluntly: *"A single MCP server can burn 10k+ tokens."*
- **It's testable and cron-able** without a protocol in the way.

```
docs search <query> [--source python|fastapi|mcp|venv:myproj] [--version 3.14]
                    [--limit 5] [--chars 800] [--json]
docs get <doc-id> [--section "Shell Parameter Expansion"] [--chars 4000]
docs symbol <name> [--source ...]        # exact lookup via DevDocs index.json
docs sources [--stale]                   # inventory + freshness
docs sync [--source ...]                 # the cron entrypoint
```

### 4.2 The MCP server — exactly 3 tools

Wrap the same code with FastMCP (**3.4.5**, 2026-07-27; the `mcp` Python SDK is at **2.0.0**, 2026-07-28; MCP spec revision is **2026-07-28**, per <https://modelcontextprotocol.io/specification/latest>). Serve streamable-HTTP on rig `:8766/mcp`, mirroring `fleet_mcp.py`'s security posture (trusted-VLAN-only UFW rule, read-only by construction).

```python
@mcp.tool()
def search_docs(query: str, source: str | None = None,
                limit: int = 5, mode: str = "text") -> str:
    """Search the local documentation mirror. Returns ranked snippets with
    citations. mode='text' for prose/BM25, mode='symbol' for exact API-name
    lookup (functions, flags, builtins). Use list_sources first if unsure
    which source to filter to."""

@mcp.tool()
def fetch_doc(doc_id: str, section: str | None = None,
              max_chars: int = 4000) -> str:
    """Fetch one documentation page (or one section of it) by the doc_id
    returned from search_docs. Prefer passing `section` — full pages can be
    12k+ tokens."""

@mcp.tool()
def list_sources(stale_only: bool = False) -> str:
    """List mirrored documentation sources with their pinned versions and
    last-sync dates. Use to check whether a library is mirrored locally
    before falling back to context7."""
```

Three tools, three short docstrings — budget the whole schema block at **< 600 tokens**. Compare: your knowledge base already flags that dumping 26 tool schemas into Qwen3.6's context is the failure mode to avoid.

**Design rules that matter more than the tool count:**

1. **Never return a whole page by default.** (measured) The bash docset averages 4.1 KB/page ≈ 1k tokens, but `bash-variables.html` is **49 KB ≈ 12k tokens** and `bash-builtins.html` is 47 KB. One careless `fetch_doc` eats 10% of a 131k window. Default `max_chars=4000`, hard-cap at ~8000, and make truncation visible (`… [truncated, 14 more sections — call fetch_doc with section=…]`).
2. **Every snippet carries a citation line.** `[python~3.14 · library/asyncio-task · https://docs.python.org/3/library/asyncio-task.html · synced 2026-07-19]`. This is what makes local docs *trustworthy* to a model that's used to hallucinating.
3. **Return heading paths, not raw chunks.** `Bash › Shell Expansions › Shell Parameter Expansion` orients the model without extra tokens.
4. **`search_docs` returns `doc_id`s that `fetch_doc` accepts.** Obvious, universally botched.
5. **`mode='symbol'` is the sleeper feature.** DevDocs `index.json` gives 508 typed symbols for bash alone; symbol lookup returns one anchored section instead of five fuzzy chunks. Massive token savings for API-reference questions, which are most of them.
6. **Structured output.** MCP spec 2026-07-28 supports structured tool results; but keep the human-readable markdown form too — local models parse markdown more reliably than nested JSON **(unverified — worth A/B testing with your bake-off harness)**.

### 4.3 Wiring

**opencode** (schema verified at <https://opencode.ai/docs/mcp-servers/>):

```jsonc
{
  "mcp": {
    "docs":     { "type": "remote", "enabled": true, "url": "http://rig:8766/mcp" },
    "context7": { "type": "remote", "enabled": true, "url": "https://mcp.context7.com/mcp" },
    "serena":   { "type": "local",  "enabled": true, "command": ["uvx", "..."] }
  },
  "agent": {
    "build": { "tools": { "docs_*": true, "context7_*": true } },
    "plan":  { "tools": { "docs_*": true, "context7_*": false } }   // local-only when planning
  }
}
```

opencode prefixes MCP tools with the server name, so `"docs_*"` globs work for per-agent gating.

**pi**: put this in `~/.pi/agent/AGENTS.md` (or the project `AGENTS.md`) and skip MCP entirely:

> Local documentation mirror: run `docs search "<query>" --source <lib>` before web-fetching or using context7. `docs sources` lists what's mirrored. `docs get <id> --section <heading>` fetches one section. Prefer this over guessing an API.

If you later want it as real MCP in pi, use **`pi-mcp-adapter`** (proxy-tool design, ~200 tokens for *all* servers, reads standard `.mcp.json`, supports StreamableHTTP) rather than a per-tool-registering bridge.

**Open WebUI**: expose via your existing `mcpo` (`agentic/docker/mcpo-config.json`) so the same corpus is searchable from the chat UI — one more entry alongside `/fleet`.

**Claude Code** (this repo, when Orca-launched agents run): `claude mcp add --transport http docs http://rig:8766/mcp` **(unverified — flag spelling not checked against current Claude Code docs)**.

---

## 5. Keeping it fresh

**Cadence, by tier:**

| Tier | Cadence | Trigger | Cost |
|---|---|---|---|
| A · DevDocs | weekly | `meta.json.mtime` ≠ manifest `mtime` | seconds; deltas are a few MB |
| B · llms.txt / `.md` | weekly | HTTP `ETag`/`Last-Modified` | seconds |
| C · git repos | daily | `git pull` on a `--filter=blob:none` clone | seconds |
| D · venv/node_modules | **on lockfile change** | `uv.lock` / `pnpm-lock.yaml` hash | ~1 min/project |
| index rebuild | after any sync | changed sources only | ~10–30 s full, <1 s incremental |

**systemd (user) timers** — matches how the rest of your ops layer is built:

```ini
# ~/.config/systemd/user/docs-sync.timer
[Unit] Description=Sync local documentation mirror
[Timer]
OnCalendar=Sun 04:00
Persistent=true
RandomizedDelaySec=30m
[Install] WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/docs-sync.service
[Unit] Description=docs sync
[Service]
Type=oneshot
Nice=15
IOSchedulingClass=idle
ExecStart=/usr/local/bin/docs sync --all
ExecStartPost=/usr/local/bin/docs reindex --changed
```

`Nice=15` + `IOSchedulingClass=idle` matters: this must never interfere with a game session or a `coder` load. Wire the exit status into your existing Healthchecks setup so a silently-broken mirror surfaces the same way everything else does.

**Version correctness — the part that beats Context7.** For each project, resolve the installed version from the lockfile and pin the source:

```
uv.lock: fastapi==0.121.3  →  docs search --source fastapi --version 0.121.3
```

If the mirrored docset version ≠ the installed version, **say so in the citation** rather than silently serving the wrong docs:

```
[fastapi · docset scraped 2026-05-26 · project pins 0.121.3 · ⚠ version match unconfirmed]
```

That single line is worth more than any amount of retrieval tuning, because it turns a silent wrong answer into a visible caveat the model will relay.

**Staleness detection:** `docs sources --stale` flags any source whose upstream `mtime`/`ETag` moved, or whose last successful sync is older than 2× its cadence. Also flag the known-bad ones permanently — e.g. DevDocs `docker` (last scraped 2022-06-02), `npm` (2024-01-06), `jest` (2022-08-27), `redis` (2023-04-12).

---

## 6. Embedding + reranking models on this rig, 2026

**Verdict: keep `Qwen3-Embedding-0.6B`. Confidence: high.** Nothing released since displaces it for your constraints.

Your current config (verified in `docker/llama-swap-config.yaml`): `Qwen3-Embedding-0.6B-Q8_0.gguf`, `CUDA_VISIBLE_DEVICES=""`, `-ngl 0 --threads 10`, `--embeddings --pooling last`, `--ctx-size 4096 --batch-size 4096 --ubatch-size 4096`, `ttl: 3600`. That is correct — `--pooling last` is what the Qwen3 model card specifies, and the `CUDA_VISIBLE_DEVICES=""` trick (vs `-ngl 0` alone) is a genuinely non-obvious fix your notes already document.

**Qwen3-Embedding-0.6B**: 0.6B params, **32k context**, **MRL 32→1024 dims**, MTEB-Multilingual 64.33, MTEB-English-v2 70.70, instruction-aware (1–5% gain from task instructions), last-token pooling. 10.2 M HF downloads (verified 2026-07-30).

**The 2026 field, and why each loses here:**

| Model | Released | Why not |
|---|---|---|
| **`nvidia/Nemotron-3-Embed-1B`** | **2026-07-16** | 2048-dim, 32k ctx, RTEB 72.38 — genuinely strong. But the card says **CUDA required; BF16 CPU inference not feasible**, and no GGUF. **Disqualified by your GPU-contention constraint.** |
| `google/embeddinggemma-300m` | 2025-09 | Excellent CPU story (`ggml-org/embeddinggemma-300M-GGUF`, 3.4 M downloads; QAT-q8_0 variant too) and ~2× faster than Qwen3-0.6B **(unverified)**. **But max input is 2,048 tokens** — which is *exactly the failure mode you already fixed*: your notes say nomic was dropped on 2026-07-15 because "nomic's 2048 trained ctx rejected big markdown-header chunks." Do not walk back into it. |
| `jinaai/jina-embeddings-v5-text-small` | 2026-02-18 | 677M, 1024-dim MRL, 32k ctx, MTEB-Eng-v2 71.7 (best-in-class <1B). **License is CC BY-NC 4.0**, no code-retrieval LoRA, no GGUF noted. Marginal quality gain, real license friction. |
| `BAAI/bge-m3` | 2024 | Still trending, still fine, but 8k ctx and older; Qwen3-0.6B beats it. |
| `jinaai/jina-code-embeddings-0.5b` | 2025-08-29 | Qwen2.5-Coder-0.5B base, 896-dim MRL, 32k ctx, five task prefixes (`nl2code`, `code2code`, `code2nl`, `code2completion`, `qa`). **CC-BY-NC-4.0**, no GGUF. Interesting *if* you later embed code — but for **docs** (prose + code blocks), Qwen3-Embedding is the better generalist. |
| `nomic-ai/nomic-embed-code`, `Salesforce/SFR-Embedding-Code-400M_R` | 2025 | Code-specific; same conclusion — you're indexing prose, and serena+ripgrep already handle code. |

**Reranker — add this, it's the highest-value model addition. Confidence: high.**

`ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF` (official ggml-org build, 40k downloads). Base model released 2025-06-05; **MTEB-Code 73.42**, MTEB-R 65.80, 32k context, yes/no-logit scoring, instruction-aware. Add to llama-swap as a third CPU-pinned persistent entry:

```yaml
  "qwen3-rerank":
    name: "Qwen3-Reranker-0.6B (CPU, docs rerank)"
    env: ["CUDA_VISIBLE_DEVICES="]
    cmd: |
      /app/llama-server --host 127.0.0.1 --port ${PORT}
      -ngl 0 --threads 10
      --model /models/Qwen3-Reranker-0.6B-Q8_0.gguf
      --embeddings --pooling rank --reranking
      --ctx-size 4096 --batch-size 4096 --ubatch-size 4096 --no-webui
    ttl: 3600
```

llama.cpp's server README documents exactly this combination (`--reranking` + `--embedding --pooling rank`) and exposes `/rerank`, `/v1/rerank`, `/v1/reranking` (verified). Front it in LiteLLM as a `rerank` alias next to `embed`, then have `docs search` do: FTS5 → top-30 → rerank → top-5. Latency for 30×~1k-token pairs on 10 CPU threads is likely **~1–3 s (unverified — measure it)**; keep it behind a `--rerank` flag so cheap lookups stay instant.

⚠ Note both extra CPU models compete with `--threads 10` on a 12-core/20-thread 12700K. Since both are TTL'd and only one is hot at a time, this should be fine, but if you see the embedder and reranker both resident during a wiki sync, drop each to `--threads 6`.

---

## 7. Beyond docs: your own past sessions as memory

**Verdict: worth it, but as a *source* in the same index — not a separate system. Confidence: medium.**

The cost is near zero once §2 exists: session transcripts are text, they chunk like docs, and they go into the same `chunks_fts` table with `source='sessions'`. Concretely:

- opencode stores session state under its data dir; pi stores under `~/.pi` and has explicit session accounting (0.81.0 added tool/compaction/branch-summary usage accounting) **(unverified — exact on-disk paths and formats not checked)**.
- Index **decisions and outcomes**, not raw turns. A transcript is mostly noise; what's retrievable-valuable is "we chose X over Y because Z" and "this approach failed because W." Your repo already has the right primitive for this — `agentic/opencode/skills/compounding-learnings` and the `/compound` command — and `docs/KNOWLEDGE-BASE.md` is literally the curated version.
- **Better ROI than raw-session indexing:** make the `/compound` skill write to `/opt/docs/md/decisions/` and let it be a `source` in the mirror. Then `docs search "why did we pick 35b-a3b" --source decisions` works from every agent, and it's ~10 lines of change.
- **Risk:** stale decisions are worse than no decisions, because a model will cite them confidently. Always return the date in the citation, and prune aggressively.

**Priority: after §2 and §4 are working.** Don't let it delay the docs mirror.

---

## 8. Disk and build-time estimates

| Component | Disk | First build | Confidence |
|---|---:|---:|---|
| DevDocs curated 32 docsets (`db.json`+`index.json`+`meta.json` only) | **~450 MB** | 3–8 min (download-bound) | high (verified sizes) |
| …if you keep the per-page HTML too | ~1.1 GB | same | high (measured 2.6× multiplier) |
| DevDocs 18-docset minimal core | **247 MB** | 2–4 min | high (verified) |
| DevDocs, all 820 | 8.50 GB | ~1–2 h | high (verified total) |
| `llms-full.txt` set (Anthropic 25.2 MB + MCP 2.3 MB + pydantic 1.9 MB) | **~30 MB** | < 1 min | high (verified byte counts) |
| `llms.txt`-driven page fetches (Next.js, React, Docker, uv, ruff, LiteLLM) | ~20–60 MB | 5–15 min (polite crawl) | medium |
| Git doc repos (MCP, opencode, pi, llama.cpp, LiteLLM, blobless) | ~150–400 MB | 2–5 min | medium |
| Python 3.14 plain-text docs archive | 3.3 MB gz → ~40 MB | seconds | high (verified) |
| Tier D per project (`.venv` stubs + `node_modules` READMEs/`.d.ts`) | 10–60 MB/project | ~1 min/project | low |
| Normalized markdown tree (`/opt/docs/md`) | ~500–700 MB | 2–5 min (regex strip, CPU) | medium |
| `index.db` (FTS5, content-stored) | **~0.8–1.2 GB** | **10–30 s** | medium (extrapolated from measured 5 ms / 0.54 MB) |
| *optional* `sqlite-vec` @ 1024-dim f32, ~400k chunks | ~1.6 GB (or ~400 MB int8) | **2–6 h of CPU embedding** | low |
| *optional* Qwen3-Reranker-0.6B Q8_0 weights | ~0.6 GB | download only | high |

**Recommended day-one footprint: ~1.3 GB, ~15–25 minutes wall clock**, nearly all of it download. On a 5 TB NVMe this is free. Note that the vector option is the only line item that costs *hours* — which is the whole argument for §2's ordering.

---

## 9. Build order

| Step | What | Effort | Confidence it's right |
|---|---|---|---|
| 1 | `docs-sync-devdocs.sh` — mirror 18-docset core (247 MB) | 1 h | **high** |
| 2 | `docs-normalize.py` — DevDocs `db.json` → `/opt/docs/md`, heading-aware chunking, FTS5 index + `symbols` table from `index.json` | 3 h | **high** |
| 3 | `docs` CLI — `search` / `get` / `symbol` / `sources` / `sync`, snippets with citations | 2 h | **high** |
| 4 | Add it to pi's `AGENTS.md`; wire `rg /opt/docs/md` as the escape hatch | 15 min | **high** |
| 5 | `docs_mcp.py` — FastMCP streamable-HTTP :8766, 3 tools, mirroring `fleet_mcp.py` | 2 h | **high** |
| 6 | opencode `"docs": {"type":"remote"}` + per-agent `tools` gating; mcpo entry for Open WebUI | 30 min | **high** |
| 7 | Tier B: `llms-full.txt` + `.md`-suffix cascade for the agent stack | 2 h | medium-high |
| 8 | systemd timers + Healthchecks ping + `docs sources --stale` | 1 h | **high** |
| 9 | **Measure.** Extend `bakeoff/harness.py` with ~20 real doc questions; score BM25-only vs BM25+rerank | 3 h | **high — do not skip** |
| 10 | Only if step 9 shows a gap: add `qwen3-rerank` to llama-swap | 1 h | medium |
| 11 | Only if step 9 *still* shows a gap: Tier D venv/node_modules ingestion | 4 h | medium |
| 12 | Only if 9–11 still show a gap: `sqlite-vec` dense index | 6 h + hours of CPU | low |

Step 9 is the one that makes this engineering instead of vibes, and you already own the harness that does it (`bakeoff/` chose `coder` on 2026-07-15 with exactly this method).

---

## 10. Confidence summary and open questions

**High confidence:**
- DevDocs archive format, sizes, and freshness (downloaded and inspected).
- FTS5 is fast enough by orders of magnitude (measured).
- Context7's corpus cannot be mirrored (stated outright in its README).
- Qwen3-Embedding-0.6B remains the right embedder for a CPU-pinned, GPU-contended rig in 2026.
- CLI-first is correct given pi's no-core-MCP stance.
- 3-tool MCP surface; snippets-with-citations over whole pages.

**Medium confidence:**
- Reranker gain magnitude on *your* queries (the 67% figure is Anthropic's corpus, not yours — hence step 9).
- llms.txt cascade coverage across your full dependency list.
- Index DB size extrapolation from a 0.54 MB sample.

**Low confidence / unverified:**
- Tier D volume — entirely project-dependent.
- Whether `arabold/docs-mcp-server` v2.4.5's search quality is good enough to skip building (30-minute spike answers this).
- Session-history on-disk formats for opencode and pi.
- Claude Code's exact `mcp add` flag spelling.

**Open questions worth 30 minutes each:**
1. Spike `arabold/docs-mcp-server` v2.4.5 against your LiteLLM `embed` alias — does it obviate steps 2–5?
2. Measure Qwen3-Reranker-0.6B Q8_0 throughput on 10 CPU threads at 30 pairs — is it 1 s or 10 s?
3. Does Qwen3.6-35B-A3B follow markdown tool output more reliably than MCP structured output? (bake-off harness question)

---

## Sources

- DevDocs: <https://github.com/freeCodeCamp/devdocs> · manifest <https://devdocs.io/docs.json> · archives `https://downloads.devdocs.io/<slug>.tar.gz` · scraper reference <https://raw.githubusercontent.com/freeCodeCamp/devdocs/main/docs/scraper-reference.md> · download task <https://raw.githubusercontent.com/freeCodeCamp/devdocs/main/lib/tasks/docs.thor>
- Kiwix ZIM devdocs: <https://lb.download.kiwix.org/zim/devdocs/> · <https://github.com/mozanunal/llm-tools-kiwix>
- llms.txt: <https://llmstxt.org/> · <https://directory.llmstxt.cloud/> · <https://llmstxt.site/>
- Context7: <https://github.com/upstash/context7> · <https://mcp.context7.com/mcp>
- MCP spec (rev **2026-07-28**): <https://modelcontextprotocol.io/specification/latest> · <https://modelcontextprotocol.io/llms-full.txt>
- opencode MCP config: <https://opencode.ai/docs/mcp-servers/> · repo now <https://github.com/anomalyco/opencode>
- pi: <https://github.com/earendil-works/pi> (0.83.0, 2026-07-29) · `pi-mcp-adapter` <https://github.com/nicobailon/pi-mcp-adapter>
- llama.cpp server (embeddings + `--reranking`): <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>
- Existing MCP servers: <https://github.com/arabold/docs-mcp-server> (v2.4.5, 2026-07-25) · <https://github.com/Magic-Man-us/dq-toolkit>
- Scrapers: trafilatura 2.1.0 · markitdown 0.1.7 <https://github.com/microsoft/markitdown> · docling 2.117.0 <https://github.com/docling-project/docling> · crawl4ai 0.9.2 <https://github.com/unclecode/crawl4ai> · firecrawl <https://github.com/firecrawl/firecrawl>
- Search/vector: <https://github.com/asg017/sqlite-vec> (pre-v1) · Meilisearch v1.51.0 (2026-07-27) <https://github.com/meilisearch/meilisearch/releases>
- Models: <https://huggingface.co/Qwen/Qwen3-Embedding-0.6B> · <https://huggingface.co/Qwen/Qwen3-Reranker-0.6B> · `ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF` · <https://huggingface.co/google/embeddinggemma-300m> · <https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16> (2026-07-16) · <https://huggingface.co/jinaai/jina-embeddings-v5-text-small> (2026-02-18) · <https://huggingface.co/jinaai/jina-code-embeddings-0.5b>
- Retrieval evidence: <https://www.anthropic.com/news/contextual-retrieval> (2024-09-19) · <https://cline.bot/blog/why-cline-doesnt-index-your-codebase-and-why-thats-a-good-thing> (2025-05-27)
- Zeal: <https://github.com/zealdocs/zeal>
- Python docs archive: <https://docs.python.org/3/download.html>
