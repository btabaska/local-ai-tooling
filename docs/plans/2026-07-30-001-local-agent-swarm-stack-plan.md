# Local agent-swarm coding stack — research synthesis & plan (2026-07-30)

> **Status:** research complete, nothing implemented. This is a plan, not a change record.
> **Scope:** make opencode / pi on the rig's single RTX 3090 Ti behave as close to Claude
> Code as possible, and support swarms of coding agents.
> **Raw research:** `docs/research/2026-07-30-local-swarm/` (10 reports, ~8,100 lines,
> every claim URL-cited by the researching agent).
>
> **Confidence legend:** **[V]** verified by me directly against source/schema/config in this
> session · **[A]** agent-reported with citation, not independently re-checked ·
> **[?]** contested or needs local measurement.

---

## 0. The one-paragraph verdict

The stack is sound; the *wiring* has silent bugs. Five defects were found in configs that
are committed and running today, each of which quietly degrades or disables something you
believe is working. Fix those first — they cost minutes and no VRAM. Beyond that: your
concurrency ceiling is **not** a memory problem (KV cache on the hybrid-attention `coder`
is 4× cheaper than a conventional 30B, measured from the published config), it is a
llama.cpp batching-efficiency problem — so the swarm should be **2–4 wide, not 8**, with
generous per-agent context, which you can now afford. The single highest-value *feature*
change is a deterministic verify-after-edit feedback loop, because with a 35B model,
forcing verification beats prompting for correctness. And there is one unresolved
blocker — whether prefix caching works at all on your hybrid model — that must be
measured before the swarm architecture is committed to.

---

## 1. Verified defects in what is running today

These were found by agents and then **confirmed by me** against live schemas/source.

### 1.1 `opencode.json` fails schema validation — 4 errors **[V]**

Validated the committed file against the live `https://opencode.ai/config.json`:

```
provider/litellm/models/{coder,coder-strong,fast,utility}
  -> Additional properties are not allowed ('tools' was unexpected)
```

The model-entry object is `additionalProperties: false`. The capability key is
**`tool_call`**, not `tools`. Consequences:

- `"tools": true` on the three coder models is not declaring tool support — it is an
  unknown key.
- `"tools": false` on `utility` is **not** disabling tool calls as intended.

The other 4 validator errors (`model`, `small_model`, `agent.*.model` "not in enum") are
**false positives** — the schema pins an enum generated from models.dev which cannot know
about custom-provider IDs. Ignore them; they are editor warnings only.

### 1.2 `temperature` is a capability boolean, not a value **[V]**

Schema: `"temperature": { "type": "boolean" }` inside the model entry. It defaults to
`false` for custom providers, and the request builder omits temperature entirely when
false. So `agent.build.temperature: 0.1` is **probably never sent** — opencode has been
running at llama-swap's server-side sampler defaults.

That is *accidentally* the correct behaviour (llama-swap already sets the Qwen model-card
values). But it is invisible and fragile. Note `bakeoff/harness.py:43` sends `0.1`
directly over the API, so **the bake-off itself was measured at the wrong temperature**
regardless.

Also: opencode's Qwen sampler auto-tune is a **substring match on the wire model id**
(`provider/transform.ts`). Your aliases are `coder`/`coder-strong` — no `qwen` substring —
so it never fires. **[A]**

### 1.3 serena is running under the wrong context **[V]**

`src/serena/config/context_mode.py:236`:

```python
"ide-assistant": "claude-code",   # legacy_name_mapping
```

`--context ide-assistant` (in `opencode.json:88`) is a **deprecation alias that silently
remaps to `claude-code`** — it does not error. You are therefore loading a
Claude-Code-specific prompt (~500 tokens **[A]**) that your local model cannot act on, and
losing `search_for_pattern` **[A]**.

Live contexts on `main` (fetched): `agent, antigravity, chatgpt, claude-code, codebuddy,
codex, copilot-cli, desktop-app, grok, ide, jb-*, junie, oaicompat-agent, vscode`.

Correct value is **`ide`** — verified from `ide.yml`, which excludes
`create_text_file, read_file, execute_shell_command, find_file, list_dir` (opencode
supplies these) and sets `single_project: true`, trimming the tool set further.
I checked `oaicompat-agent` as an alternative: it includes **all** tools except
`initial_instructions`, so it would *increase* tool count. Do not use it.

### 1.4 serena has a live HIGH-severity RCE, and you are unpinned **[V]**

> **CVE-2026-49471** · CVSS **8.3 HIGH** · GHSA-37h2-6p4f-mp3q · `serena-agent` **< 1.5.2**
> Unauthenticated Flask dashboard on hardcoded TCP **24282**; no auth, no CSRF, no Host
> validation. Chain: DNS rebinding → memory poisoning → prompt injection →
> `execute_shell_command(shell=True)` → **OS-level RCE**. Affects default installs.

`opencode.json:84` runs `uvx --from git+https://github.com/oraios/serena` with **no version
pin**. Latest is **serena-agent 1.6.1** (PyPI, verified). Pin it and pass
`--enable-web-dashboard false`. This is not theoretical on this rig: DNS rebinding is
browser-driven and the rig runs Chromium (Orca) and is a gaming machine.

### 1.5 `"tools": {"skills*": true}` is a dead key **[A]**

The tool is singular `skill`; no `skills*` glob exists. Silently does nothing. Skills are
on by default. (Top-level `tools` is schema-valid as `{[k: string]: boolean}` **[V]**, so
it does not fail validation — it just matches nothing.)

### 1.6 Agent files point at a decommissioned provider **[A]**

`agentic/opencode/agents/*.md` reference `ollama/*` models; the config defines only
`litellm/*`. Ollama is decommissioned as a model server per `docs/KNOWLEDGE-BASE.md` §9.

---

## 2. The number that reframes the swarm design **[V]**

Lane 08 concluded "2–3 agents max, KV-VRAM bound." Its premise was wrong by **5.4×**.
I computed the real figures from the published `config.json` of both models.

`coder` = **Qwen3.6-35B-A3B** is hybrid linear-attention: `full_attention_interval: 4`,
`layer_types` = 30× `linear_attention` + **10× `full_attention`** out of 40 layers.
Only the 10 full-attention layers hold a real KV cache.

| | `coder` (35B-A3B) | `coder-strong` (27B) |
|---|---|---|
| layers / full-attn | 40 / **10** | 64 / **16** |
| `num_key_value_heads` × `head_dim` | 2 × 256 | 4 × 256 |
| KV per token @ q8_0 | **10,240 B** (10.0 KiB) | **32,768 B** (32.0 KiB) |
| per 1k tokens | **9.8 MiB** | **31.2 MiB** |
| KV @ 131k ctx | 1.25 GiB | 4.00 GiB |
| KV @ 262k ctx | **2.50 GiB** | 8.00 GiB |
| vs. naive all-full-attention | **4.0× cheaper** | 4.0× cheaper |

*(Lane 03 reported 20,480 B/token — that is the **f16** figure. You run
`--cache-type-k q8_0 --cache-type-v q8_0`, so 10,240 B is yours. Linear-attention layers
carry a small constant per-slot recurrent+conv state, on the order of tens of MiB per
slot — negligible here.)*

**Implication.** At 262k total context the KV cache costs **2.5 GiB**; weights dominate at
roughly 20.8 GiB. `--parallel 8 --ctx-size 262144` (8 agents × 32k each) costs the **same
2.5 GiB** as one agent at 262k. **Memory is not what limits your swarm.** Per-agent
context is nearly free on this architecture — you can hand 4–6 agents 32–43k windows
without paying for it.

`coder-strong` is 3.2× heavier per token. Keep it single-agent, deep-work only.

**What *does* limit the swarm** is llama.cpp batching efficiency: measured 1.2–1.9×
aggregate throughput from concurrency 1→8 on a 3090, vs 3.9–5.4× for vLLM **[A]**; and GPU
utilisation only ~60% through llama-server vs 90–96% under `llama-batched-bench`, the gap
being CPU-side sampling **[A]** — which matters because your 12700K already gives 10
threads to the embedder. Going 1→8 makes each agent ~4× slower to buy ~1.9× total work.

**Conclusion: 2–4 concurrent agents, generous context each.** Lane 08's recommendation
survives; its reasoning does not. The agent count is now a tunable latency/parallelism
preference, not a hard wall.

---

## 3. The blocking unknown — run this first **[?]**

**Same architectural property, opposite consequences:** the hybrid attention that makes
your KV cache cheap may be the thing that breaks prefix caching.

llama.cpp issue **#24055** (open; `bug-unconfirmed`, `stale`) reports context checkpoints
are *always* invalidated on hybrid/recurrent models. Log line, verbatim:

> "forcing full prompt re-processing due to lack of cache data (likely due to SWA or
> hybrid/recurrent memory"

Root-caused to commit `e98cb51`; reported on a Qwen3.6-27B MTP variant. This matters
enormously because prefix caching is *the* enabling mechanism for a swarm — N agents share
one long system prompt + AGENTS.md + repo map. TraceLab (~4,300 real coding-agent
sessions) measured **~96% of prompt tokens served from prefix cache** **[A]**.

**And it collides with the build-pin advice.** Two lanes independently said pin a *newer*
build; #24055 says newer builds broke hybrid checkpointing and the workaround is an
*older* one:

| Build | Tool calls | Prefix cache on hybrid |
|---|---|---|
| Newer (≥ 9755 / 2026-06-21) | GBNF fix: ~1/128 dropped tool calls resolved **[A]** | possibly broken (#24055) |
| Older (b9309) | ~1/128 tool calls dropped, stream aborts | works **[A]** |

Mitigating factors: the issue is `bug-unconfirmed`/`stale`; it was filed against the 27B
MTP variant, not your 35B-A3B MoE; and llama.cpp moves fast enough that a post-06-21 build
may carry both fixes.

> ### Experiment 1 (do before anything else, ~15 min)
> On a current build, load `coder`, send two identical long (~10k token) prompts back to
> back, and check whether the second prefills from cache or reprocesses. Watch for the
> "forcing full prompt re-processing" warning. **This decides whether the swarm plan is
> viable as designed.**
>
> If it fails: options are (a) find a build with both fixes, (b) accept ~1/128 tool-call
> loss with client-side retry on the older build, or (c) move `coder` to a non-hybrid
> model — at the cost of 4× the KV, which changes every number in §2.

---

## 4. Prioritised plan

### Tier 0 — free correctness fixes (minutes, no VRAM, no risk)

1. **Fix the 4 schema errors**: `tools:` → `tool_call:` on all four models; `utility` gets
   `"tool_call": false`. **[V]**
2. **Add `"temperature": true`** to each model entry so agent temperature is actually
   sent — then set it deliberately (see §5). **[V]**
3. **serena: `--context ide`, pin `serena-agent==1.6.1`, add
   `--enable-web-dashboard false`.** Security + ~500 tokens + restores
   `search_for_pattern`. **[V]**
4. **Delete `"tools": {"skills*": true}`** — dead key. **[A]**
5. **Repoint `agentic/opencode/agents/*.md` from `ollama/*` to `litellm/*`.** **[A]**
6. **Fix `bakeoff/harness.py:43`** to stop forcing `temperature: 0.1`; re-run the bake-off.
   Its previous result is not trustworthy at the sampler level. **[V]**

### Tier 1 — the deterministic feedback loop (highest feature value)

With a 35B model, **forcing verification beats prompting for correctness.** This is the
single biggest capability gap vs Claude Code, and it is closable.

**Tier 1.0 — carried over from the Tier 0 pass (cheap, do these first):**

- **7a. `interleaved: {field: "reasoning_content"}` on `coder` + `coder-strong`.**
  `@ai-sdk/openai-compatible` reads `delta.content` only, and opencode's auto-detection
  fires only for model ids containing `deepseek` (`provider.ts`) **[A]**. Without this,
  reasoning tokens are emitted by llama.cpp but never surfaced — presenting as a **silent
  infinite spinner** (opencode #24316). Schema-verified: `interleaved` accepts
  `{field: "reasoning" | "reasoning_content" | "reasoning_details"}` **[V]**. One line per
  model, both configs. ⚠ Interacts with Tier 3 item 18 — if you later set `--reasoning off`
  there is no reasoning stream to surface, so revisit this then.
- **7b. Prune `bakeoff/harness.py:MODELS`.** Still lists `qwen3-coder-30b` and
  `devstral-24b`, **retired in ai-08** with weights moved to `/opt/llm/models/archive/`.
  `--all` currently fails on 2 of 4 models. Either drop them, or gate them behind a
  `--include-archived` flag if re-benching archived weights is wanted. Blocks Experiment 3
  from running clean.

7. **`"lsp": true` + `"formatter": true`.** Both are **off by default** — opencode docs,
   verbatim: *"LSP is disabled by default"*, and omitting it *"results in all LSP servers
   being disabled."* **[V]** You currently have zero LSP. opencode's `edit`/`write` tools
   already append diagnostics directly into the tool result the model reads, and `write`
   reports project-wide across up to 5 files **[A]** — that is a PostToolUse hook that is
   already written and costs zero prompt tokens.

   *Note on the lane 01 vs 06 conflict:* opencode's docs do recommend CLI linters over LSP
   (*"it is better to have the agent run lint, typecheck… directly"* **[V]**). These are
   reconcilable — item 8 *is* the CLI approach, and works with either setting. Diagnostics
   append to tool **results** (conversation suffix), so unlike agent-switching they do
   **not** invalidate the prefix cache. Low-risk; A/B it.

8. **One `tool.execute.after` plugin** running `just verify-fast` (ruff + ty + tsc),
   truncated to ~40 lines, debounced ~4 s, silent on pass, structured markers on fail. **[A]**
9. **Close the `Stop` gap in-process**: the plugin factory receives an SDK `client`, so a
   plugin can hook `event: session.idle`, run verification, and call
   `client.session.prompt()` on failure — a genuine in-process Stop hook, no external
   supervisor needed. **[A]**
10. **`tool.definition` hook** (undocumented) rewrites any tool's description and JSON
    schema before the model sees it — no Claude Code equivalent. Use it to shrink serena's
    schemas. Stock serena costs ~8,800 tokens of schema; trimmed ≈ 2,000. **[A]**

### Tier 2 — tool budget and context hygiene

11. **Cut the tool surface to ~20–30 including built-ins.** Tool *count* is the binding
    constraint, not tokens; selection accuracy degrades past 30–50 tools even for frontier
    models, and BFCL v4 shows small models collapsing on multi-turn (Qwen3-4B: 82.6%
    non-live → **35.3% multi-turn**). **[A]**
12. **`subagent_depth: 2`** — defaults to **1**, which prevents subagents from launching
    subagents. **[V]** (schema description confirms). Required for any nested swarm.
13. **`compaction.prune: true`** (default false **[V]**), **`tool_output.max_lines: 600`**
    (default 2000 **[V]**).
14. **Add `timeout` / `headerTimeout` / `chunkTimeout`** to the provider options **[V]** and
    raise MCP `timeout` above the 5 s default — llama-swap model swaps exceed it and
    present as indistinguishable hangs. **[A]**
15. **AGENTS.md rule: "JSON output is for scripts, never for the model."** Measured:
    `rg --json` costs **32×** `rg -l` and 3.7× `rg -n` for identical information. **[A]**

### Tier 3 — serving layer (after Experiment 1 resolves)

16. **Two llama-swap profiles over the same GGUF**: `coder-deep` (`-np 1`, MTP, max ctx —
    today's config) and `coder-swarm` (`-np 4`, `--kv-unified`, `--backend-sampling`,
    **no MTP** — MTP requires `-np 1` per your own bake-off, and drafting steals FLOPs once
    batch-saturated). **[A]**
17. **Raise `--cache-ram` from the 8192 MiB default to ~24–32 GiB** and set
    `--cache-reuse 256` (defaults to **0/off**). Checkpoints live in system RAM; you have
    64 GB idle. Free. **[A]**
18. **`--reasoning off`** on agent-loop model entries. `enable_thinking` via
    `chat_template_kwargs` has been **deprecated and ignored since build b8322** — the
    unsloth docs advising it are stale, so you currently have *no working thinking toggle*.
    Replacement is startup-only `--reasoning on|off`. Sampler must change with the mode. **[A]**
19. **Protect the prefix cache from the arbiter.** Every ComfyUI/gaming force-unload wipes
    it, costing minutes of re-prefill. Use `--slot-save-path` + `POST /slots/N?action=save|restore`
    around yields. **[A]**
20. **Turn LiteLLM response caching OFF** — it is a *response* cache; replaying completions
    across swarm agents collapses diversity and can replay stale tool calls. Verify
    v1.83.14's server-side prompt compression is disabled (it rewrites long inputs with no
    client opt-in) and pin off `main-latest`. Do enable per-key RPM limits and
    `global_max_parallel_requests: 3` as a runaway-swarm circuit breaker. **[A]**

### Tier 4 — local knowledge corpus (~1.3 GB, 15–25 min, mostly download)

21. **DevDocs archives, not the container**: `curl https://downloads.devdocs.io/<slug>.tar.gz`.
    Each contains `db.json` (clean HTML), **`index.json` — a typed symbol table**, and
    `meta.json` with `release` + `mtime` (free version pinning *and* staleness detection).
    820 docsets / 8.5 GB total; an 18-docset core is **247 MB**. ⚠ the `docker` docset was
    last scraped **2022-06-02** — source Docker docs elsewhere. **[A, primary-verified by agent]**
22. **SQLite FTS5 + BM25 over normalized markdown, plus ripgrep. Not vectors.** Measured:
    5 ms to index the bash docset; **0.57 ms** query returning the correct page. Zero
    resident processes — the only option that respects GPU contention. **[A]**
23. **Step 2 is a reranker, not a vector index**: `Qwen3-Reranker-0.6B` via
    `--reranking --pooling rank`, CPU-pinned with the same `CUDA_VISIBLE_DEVICES=""` trick
    as the embedder. **[A]**
24. **Keep Qwen3-Embedding-0.6B.** EmbeddingGemma-300m caps at 2048 tokens — the exact
    reason nomic was dropped on 2026-07-15. **[A]**
25. **CLI first, MCP as a thin wrapper** (`search_docs` / `fetch_doc` / `list_sources`,
    <600 tokens of schema, never return whole pages — `bash-variables.html` alone is ~12k
    tokens). CLI-first because **pi has no MCP in core** but does have `bash`. **[A]**

### Tier 5 — swarm topology

26. **"Sequential spine, narrow parallel ribs, deterministic gates."** Single-threaded
    spec → plan → decompose with fresh-context handoffs, producing `tasks.yaml` with a hard
    invariant: **concurrent tasks' `owns[]` file globs are pairwise disjoint.** Fan out to
    **2–4** Orca worktree ribs **on the same model alias** (per-agent model routing forces a
    ~19 GB llama-swap reload — a trap on this rig). Serialized integrator merges ribs one at
    a time re-running the full suite; a fresh-context reviewer writes findings as *new
    tasks*, never inline fixes. **[A]**
27. **Move verification off the GPU.** Best-of-N, self-consistency, and LLM-judge gates each
    cost a full model pass on a ~0.4–0.7 M tok/hr pipe. `tsc`, tests, and linters cost idle
    CPU — and you have 20 threads doing nothing while the GPU decodes. **[A]**
28. **Keep Orca.** It is worktree-native, agent-agnostic, and configures the model backend
    per-agent rather than centrally — which is why your LiteLLM wiring works. Alternatives
    are worse: Conductor is macOS-only, **Crystal is deprecated (Feb 2026)**, vibe-kanban is
    sunsetting, Claude Code agent teams are Anthropic-auth-only. **Skip A2A** — v1.0 is
    explicitly not a sub-agent protocol. **[A]**
29. **Assert `--disable-gpu` in the overnight launcher** (Orca's Chromium spikes to ~8 GB;
    `coder` needs ~23.3 GB and OOMs), and treat model-unload as **pause-and-retry**, not
    failure — the Apollo gaming hook can vanish the model at 2 a.m. **[A]**

---

## 5. The LiteLLM question — unresolved architectural tension

Two lanes disagree, and it is a real design decision, not a factual dispute.

- **Lane 09: bypass LiteLLM for coding clients.** opencode issue **#20719** is your exact
  stack — opencode + `@ai-sdk/openai-compatible` + LiteLLM aborted the agent loop after one
  call because LiteLLM returned `finish_reason: "stop"` where OpenAI returns `"tool_calls"`;
  direct curl to the backend was correct. **Closed as *not planned*.** Compounding it,
  `drop_params: true` (which you set) silently discards `top_k`, `min_p`, `grammar`,
  `json_schema`, `chat_template_kwargs` — precisely the knobs that improve tool calling. **[A]**
- **Lane 04: keep LiteLLM** for auth, virtual keys, spend logging, rate limiting, fallbacks. **[A]**

**Recommended resolution:** keep LiteLLM as the front door for everything else, and add a
**direct llama-swap lane for the three local coding clients** (opencode, pi, the bake-off
harness) on the trusted VLAN. You lose per-client spend attribution for those three; you
gain tool-call fidelity and the sampler knobs. Also drop `num_retries: 2` on coder aliases —
gateway retries on non-idempotent tool calls can double-execute. **[A]**

This is a judgement call with a real tradeoff. Flagging it rather than deciding it.

---

## 6. opencode vs pi — which hosts the swarm

**Recommendation: opencode as the primary host; pi as a headless rib worker under Orca.**

Three lanes independently converged on the same fact: **pi core has no MCP, no subagents,
no plan mode, no permissions, no todos** — by design, upstream verbatim: *"No MCP. Build
CLI tools with READMEs."* **[A]** Swarm capability would come from ~4 community packages by
4 different authors, each with full system access, layered on a core shipping 2–4× per
week. That is a real supply-chain surface for an unattended overnight rig.

opencode ships subagents, MCP, permissions, skills (including `.claude/skills/`), and the
diagnostics-in-tool-result loop natively. Its checkpointing is *better* than Claude Code's
— a shadow bare-git repo whose work-tree is your project, so it captures bash-made edits,
which Claude Code's does not. **[A]**

pi's genuine advantages: an RPC mode with `steer` (mid-run redirection), a true `Stop` hook
via `agent_end`, and ~21 `compat` flags for tuning odd OpenAI servers. **[A]** Those make it
a good *worker*, driven by Orca — which already supplies the orchestration pi lacks.

⚠ **Stay on opencode 1.x** — v2 reportedly has no LSP runtime at all. **[A]**

---

## 7. Model lineup

**Keep `coder` and `coder-strong`.** The 2026 frontier open-weight wave moved to
200B–1.6T and is permanently out of reach of 24 GB; the "runs locally" tier consolidated on
~30B MoE / ~3B active, where Qwen3.6-35B-A3B sits. **[A]** The strongest argument for the
incumbent is architectural and the bake-off did not know it — §2's 4× KV reduction is the
only reason 262k context fits, and the only reason a swarm is feasible.

Worth acting on: **`coder-strong` beats `coder` on every coding benchmark** (SWE-bench
Verified 77.2 vs 73.4, Terminal-Bench 2.0 59.3 vs 51.5 **[A]**). The MoE default is a
*throughput* decision, not a capability one — so route quality-critical single tasks to
`coder-strong` explicitly.

**One replacement recommended:** `fast` = Qwen2.5-Coder-7B is a 2024-gen model at Q4_K_M
with no verifiable tool-calling benchmark, and measured KL-divergence data shows Q4 at the
7B/3B scale degrading >10% — while 24–35B at Q4 is safe. Candidate: Qwen3.5-9B at
Q5_K_M/Q6_K. **[A]** *(Contra the folklore: tool-calling is among the most quant-resilient
capabilities, not the most fragile — the problem is model scale, not the task.)*

**Two possible silent-corruption bugs to audit before trusting any measurement:** CUDA 13.2
reportedly produces gibberish with Qwen3.6, and a `chat-template-kwargs` whitespace bug can
silently keep the model thinking and derail tool loops. **[A]**

---

## 8. Experiments, in order

| # | Experiment | Why | Time |
|---|---|---|---|
| 1 | **Prefix-cache probe on `coder`** (§3) | Decides swarm viability; unblocks everything in Tier 3 | 15 min |
| 2 | `-np` scaling curve at 1/2/4/6/8 on `coder` | No published number exists for this rig+model; sets the agent count | ~1 hr |
| 3 | Re-run bake-off with corrected sampler + schema validation | Current result was measured at the wrong temperature | ~1 hr |
| 4 | Chat-template round-trip check for tool calls | Guards against the silent-corruption bugs in §7 | 30 min |
| 5 | serena trimmed (8 tools) vs opencode experimental `lsp` tool, A/B | No benchmark of serena on a local 7B–35B model exists anywhere | ~2 hr |
| 6 | `draft-mtp` speculative decoding on the MoE | Lane 03 revised its own conclusion here mid-research; genuinely open | ~1 hr |

Extend `bakeoff/harness.py` with `jsonschema` validation and **N≥300 tool calls per
config** — at a documented ~1/128 malformed-call rate, single runs prove nothing. **[A]**

---

## 9. Corrections made to agent findings

Recorded because the raw reports in `docs/research/` still contain the originals.

| Claim | Correction |
|---|---|
| Lane 05: `--context ide-assistant` raises `FileNotFoundError` | **Wrong.** It is a silent deprecation alias → `claude-code` (source line 236). Worse than a crash — it degrades silently. |
| Lane 08: KV budget ~85k tokens total → max 2–3 agents | **Premise wrong by 5.4×** (assumed 53 MiB/1k; actual 9.8 MiB/1k). Conclusion survives on throughput grounds only. |
| Lane 03: KV = 20,480 B/token | That is the **f16** figure; at your q8_0 setting it is 10,240 B. |
| Lane 01: "keep `lsp: false`" vs Lane 06: "`lsp: true` is highest impact" | Both cite real sources. Reconciled: the CLI verify hook (item 8) is the actual win and is setting-independent. |
| Lane 02: pi context/compaction misconfigured | `clients/pi-models.json` already sets `contextWindow`/`maxTokens`. Not a defect. |
| Lane 02/05: various pi package names, versions, registry counts | **Not independently verified.** Load-bearing for any pi-swarm decision — confirm existence and maintenance before adopting. |

---

## 10. Decisions taken (2026-07-30) + Tier 0 implementation record

Two decisions were delegated by the repo owner on 2026-07-30. Both are now **decided and
implemented**; the reasoning is recorded here so it can be revisited with evidence.

### Decision 1 — LiteLLM direct lane: **approved, but additive, not a replacement**

Owner's framing: *"acceptable if you think that would be an overall win."*

**Verdict: conditional win — implemented as an A/B lane, default unchanged.**

Rationale for *not* simply cutting the gateway out:
- The evidence (opencode #20719, `drop_params` eating `top_k`/`min_p`/`grammar`) is **[A]** —
  agent-cited, not reproduced on this rig. Ripping out a working front door on unreproduced
  evidence is the wrong order of operations.
- Bypassing LiteLLM **destroys the stable-alias indirection**, which `README.md` names as a
  design principle ("Clients never change when the model behind an alias does"). Direct
  clients must use llama-swap's real model names (`qwen3.6-35b-a3b`), so a future model swap
  would require editing every client — exactly the coupling LiteLLM exists to prevent.
- It also drops per-client spend logging and virtual-key scoping for those clients.

**What was implemented:** a second opencode provider, **`llamaswap`**, pointing at
`http://192.168.10.12:9292/v1` with llama-swap's real model ids, declared alongside the
existing `litellm` provider. `model` / `small_model` / both agents still default to
`litellm/*` — **nothing changes until you deliberately switch.** To A/B, set
`"model": "llamaswap/qwen3.6-35b-a3b"` and compare tool-call fidelity.

`bakeoff/harness.py` already hits `localhost:9292` directly (`BAKEOFF_BASE`), so the harness
has always been on the direct lane — which means **the bake-off never exercised the
LiteLLM path the clients actually use.** That alone justifies the A/B.

> ⚠ **Subtlety to watch during the A/B.** opencode substring-matches the *wire model id*:
> `provider/transform.ts` applies Qwen sampler defaults (0.55 / top_p 1.0) when the id
> contains `qwen`, and `session/system.ts` picks a system prompt by matching
> `gpt`/`gemini`/`claude`/`kimi` **[A]**. The `litellm` lane's ids (`coder`) match nothing;
> the `llamaswap` lane's ids (`qwen3.6-35b-a3b`) **do** contain `qwen`. So the two lanes may
> not be sampler-identical even with identical explicit config, and precedence between
> explicit `temperature` and the auto-tune is **unverified**. Check this before attributing
> any A/B delta to the gateway.

**If the direct lane wins:** restore indirection by adding `aliases:` entries in
`docker/llama-swap-config.yaml` (llama-swap supports per-model aliases) rather than
hardcoding weight-level names in clients. That is a rig-side change requiring a container
restart, so it is deliberately out of Tier 0.

### Decision 2 — swarm host: **opencode primary, pi as Orca-driven worker**

Owner delegated this outright. **Verdict: opencode.**

- Three independent lanes confirmed pi core ships **no MCP, no subagents, no plan mode, no
  permissions, no todos** — by design (upstream: *"No MCP. Build CLI tools with READMEs."*)
  **[A]**. Reaching parity means ~4 community packages from 4 authors, each with full system
  access, on a core shipping 2–4×/week.
- The intended use is **unattended overnight swarm runs with `edit: allow` and broad bash**.
  That is precisely the threat model where a 4-author dependency chain is unacceptable —
  and §1.4's serena CVE is a live demonstration of that risk materialising in this exact
  ecosystem.
- opencode ships subagents, MCP, permissions, skills (incl. `.claude/skills/`), and the
  diagnostics-in-tool-result loop natively, and its checkpointing is *better* than Claude
  Code's (shadow bare-git repo whose work-tree is the project, so it captures bash-made
  edits) **[A]**.

**pi is retained, not discarded** — as a headless rib worker under Orca, where its RPC
`steer` (mid-run redirection), true `Stop` hook via `agent_end`, and ~21 `compat` flags are
genuine advantages and Orca supplies the orchestration pi lacks. `clients/pi-models.json`
stays maintained.

**Consequence applied to the agent files:** all subagents now run on **the same alias as the
primary** (`litellm/coder`). Per-agent model routing would force a ~19 GB llama-swap reload
on every delegation — a trap on this rig **[A]**.

⚠ **Stay on opencode 1.x**; v2 reportedly has no LSP runtime **[A]**.

### Tier 0 — implemented 2026-07-30

| # | Change | Files |
|---|---|---|
| 1 | `tools:` → **`tool_call:`** on all 4 models; `utility` → `tool_call: false` | `opencode.json`, `agentic/opencode/opencode.json` |
| 2 | Added **`temperature: true`** capability to every model entry; agent `temperature` `0.1` → **`0.6`** + explicit `top_p: 0.95` (matches llama-swap's `--temp 0.6 --top-p 0.95`) | both configs |
| 3 | serena: `--context ide-assistant` → **`ide`**; `git+https://…` → **`serena-agent==1.6.1`**; added **`--enable-web-dashboard false`** (CVE-2026-49471) | both configs |
| 4 | Deleted dead **`"tools": {"skills*": true}"`** block | both configs |
| 5 | Agent models `ollama/devstral:24b` / `ollama/code:opencode` → **`litellm/coder`**; temp `0.1` → `0.6` | `agentic/opencode/agents/{debugger,tester,reviewer}.md` |
| 6 | Removed hardcoded `temperature: 0.1`; now omitted by default (server sampler applies), sweepable via `BAKEOFF_TEMP` / `BAKEOFF_TOP_P` | `bakeoff/harness.py` |
| + | Added `llamaswap` direct-lane provider (Decision 1) | both configs |
| + | `agentic/opencode/opencode.json` was a byte-identical copy carrying all 5 defects — **synced to root** to remove the drift trap | — |

**Verification performed:** re-validated `opencode.json` against the live
`https://opencode.ai/config.json` → **0 real errors** (only the 4 known model-enum false
positives from §1.1 remain). `top_p` confirmed present in `AgentConfig`. `harness.py`
byte-compiles. Both JSON files parse.

### Tier 1 — implemented 2026-07-30

Deployment target confirmed by the owner: opencode runs on **both** the rig (CachyOS,
accessed via SSH under Orca) **and** a MacBook (Orca + opencode + pi, calling the model
APIs remotely). Everything below is therefore cross-platform.

**The plugin API was verified against real type definitions** before any code was written
— `npm pack @opencode-ai/plugin@1.18.10` and `@opencode-ai/sdk@1.18.10`, reading
`dist/index.d.ts`. This upgraded several **[A]** claims to **[V]**:

| Hook | Status | Exact signature (from `Hooks` interface) |
|---|---|---|
| `tool.execute.after` | **[V]** | `(input: {tool, sessionID, callID, args}, output: {title, output, metadata})` |
| `event` | **[V]** | `(input: {event: Event})`; `EventSessionIdle = {type:"session.idle", properties:{sessionID}}` |
| `tool.definition` | **[V]** | `(input: {toolID}, output: {description, parameters})` — *"Modify tool definitions sent to LLM"*. **Absent from the docs page**; lane 07 was right that the documented event list is not the hook list. |
| `chat.params` | **[V]** | `(…, output: {temperature, topP, topK, maxOutputTokens, options})` |
| `permission.ask` | **[V]** | `(input: Permission, output: {status: "ask"\|"deny"\|"allow"})` — also undocumented |
| `client.session.prompt` | **[V]** | `{path:{id}, body:{parts:[{type:"text",text}]}}` |
| Plugin factory input | **[V]** | `{client, project, directory, worktree, serverUrl, $: BunShell}` |

| # | Change | Files |
|---|---|---|
| 7a | `interleaved: {field:"reasoning_content"}` on `coder`, `coder-strong` **and** both direct-lane equivalents | both configs |
| 7b | `MODELS` pruned to served models only; retired `qwen3-coder-30b`/`devstral-24b` moved behind `BAKEOFF_INCLUDE_ARCHIVED=1` | `bakeoff/harness.py` |
| 7 | `"lsp": true` + `"formatter": true` | both configs |
| 8 | `tool.execute.after` verify hook — debounced 4 s, 45 s hard timeout, truncated to 40 lines / 4000 chars, **silent on pass**, fires only on edit/write/patch/multiedit | `agentic/opencode/plugins/local-llm.ts` |
| 9 | `event: session.idle` Stop hook — re-verifies on idle, pushes back via `client.session.prompt`, bounded at **2 nudges/session**, fire-and-forget so it never blocks the handler | same file |
| 10 | `tool.definition` trimmer — keeps the first paragraph of over-long `serena`/`context7` descriptions, caps at 400 chars, **leaves `parameters` untouched** (trimming those would break tool calls) | same file |
| + | Cross-platform LSP/tooling installer (Arch `pacman`/`paru` + macOS `brew`), `--dry-run`/`--minimal`, resolves-check + next-steps output | `scripts/install-code-intel.sh` |

**Verify-command resolution** (first match wins; plugin disables itself silently if none):
`$OPENCODE_VERIFY_CMD` → `.opencode/verify.sh` → `just verify-fast` (only if a justfile
declares it) → auto-detected `ruff` / `tsc` **only when the binary actually resolves** →
none. The resolves-check is what makes it safe to auto-load globally: in a repo like this
one, with no Python/TS toolchain, it stays completely silent rather than erroring on every
edit.

**Verification performed:** `tsc --noEmit` in **strict mode** against the real
`@opencode-ai/plugin@1.18.10` types → **exit 0**. Both configs re-validated against the
live schema → **0 real errors**. `harness.py` byte-compiles. `install-code-intel.sh`
passes `bash -n` and its `--dry-run` correctly detects Darwin.

**Not yet wired (requires a host to run on):**
- `scripts/install-code-intel.sh` has **not been executed** on either host — on this
  MacBook, `rg`, `fd`, `ast-grep`, and `just` are all currently missing.
- The plugin is **not deployed**; it lives in the repo template dir. Deploy with
  `cp agentic/opencode/plugins/local-llm.ts ~/.config/opencode/plugins/`.
- No repo yet defines a `verify-fast` recipe, so the hook is inert until one does.
  End-to-end confirmation (break a typecheck, assert a `<verify status="fail">` block
  appears in the tool result) is still outstanding.

### Tier 2 — implemented 2026-07-30

Owner confirmed Tier 1 passed validation on-host (serena starts clean under `--context ide`
at the pinned 1.6.1; the verify loop fires). Tier 2 proceeded on that basis.

**MCP tool naming verified before writing any allowlist:** tools are registered as
**`servername_toolname`**; globs support `*` and `?`; per-agent `tools` overrides the global
map; MCP `timeout` defaults to **5000 ms** and is per-server **[V]**.

| # | Change | Detail |
|---|---|---|
| 11 | **Tool budget: default-deny MCP, opt in per agent** | Global `{"serena*": false, "context7*": false}`. `build` → serena only (editing needs symbol nav, not cloud docs). `plan` → serena + context7 (the one phase where cloud docs earn their slots). All three subagents → serena only. **context7 is now off everywhere except `plan`** — it was previously loaded into every agent and every subagent, multiplying its cost across a swarm. |
| 12 | `subagent_depth: 2` | Default **1** blocks subagents from launching subagents — i.e. blocks nested swarms outright. |
| 13 | `compaction.prune: true` (default false), `tool_output.max_lines: 600` (default 2000) | Context hygiene; long tool dumps evict working memory on a 131k window. |
| 14 | Provider `timeout` 900 s / `headerTimeout` 180 s / `chunkTimeout` 300 s; MCP `timeout` serena 30 s, context7 20 s | Deliberately **generous**. The failure being fixed is llama-swap swaps and long prefills presenting as indistinguishable hangs; a too-tight timeout causes spurious aborts, which is the worse failure mode. `headerTimeout` covers a ~23 GB model swap, `chunkTimeout` covers prefill-to-first-token on a long context. |
| 15 | AGENTS.md: no-`--json` rule + `<verify>` stop-everything rule | `rg --json` costs **32×** `rg -l` and 3.7× `rg -n` for identical information. Second rule teaches the model what the Tier 1 hook's output means. |

**Subagent grants were required, not optional:** the global default-deny applies to
subagents too, so each of `debugger`/`reviewer`/`tester` needed an explicit
`tools: {serena*: true}` in frontmatter or they would have silently lost symbol navigation.

**Verification performed:** both configs revalidated against the live schema → **0 real
errors**. All three agent files verified to retain exactly 2 frontmatter fences, one
`model:` key pointing at `litellm/coder`, and the serena grant.

**Not yet observed:** the tool-budget change alters what each agent can see, and no swarm
run has exercised it. Watch for a subagent complaining it cannot find a symbol tool — that
would mean a grant is missing or the glob is wrong.

**Not yet done / next increment** (deliberately outside Tier 0):
- The two items deferred from this pass — `interleaved` on the coder models, and pruning
  the retired models from `harness.py:MODELS` — were **promoted into Tier 1 as items 7a and
  7b** (2026-07-30, at the owner's direction). Do them first in the Tier 1 pass.
- Provider `timeout` / `headerTimeout` / `chunkTimeout`, and raising MCP `timeout` above the
  5 s default (llama-swap swaps exceed it and look like hangs) — Tier 2 item 14.
- `lsp: true` + `formatter: true` and the verify-after-edit plugin (Tier 1 — the real win).

**Nothing rig-side was touched** — no `llama-swap-config.yaml`, no `litellm-config.yaml`, no
container restarts. All Tier 0 changes are client-side and take effect when
`opencode.json` is deployed to `~/.config/opencode/opencode.json`.

---

## 11. Known limits of this research

- **WebSearch budget was exhausted (200/200) partway through**, during lanes 06 and 07.
  Both compensated with direct HTTP fetches, and lane 06's key claims were re-verified by
  me, but coverage may be thinner than the other lanes.
- Everything marked **[A]** is agent-reported with a citation but not independently
  re-checked by me. The **[V]** items — the config defects, the KV arithmetic, the serena
  context and CVE, the opencode schema and LSP defaults — are confirmed.
- Throughput figures for llama.cpp concurrency come from third-party benchmarks on similar
  but not identical hardware. Experiment 2 replaces them with real numbers.
- No benchmark exists anywhere for serena (or any code-intelligence MCP) driving a local
  7B–35B model. Experiment 5 would produce the first.
