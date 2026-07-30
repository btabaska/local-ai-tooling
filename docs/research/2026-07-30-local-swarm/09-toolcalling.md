# 09 — Making Tool Calling Bulletproof with Local Models

**Research date: 2026-07-30.** Target stack: llama.cpp `llama-server` + llama-swap + LiteLLM,
clients opencode (`@ai-sdk/openai-compatible`) and pi (`openai-completions`).
Models: `coder`=Qwen3.6-35B-A3B, `coder-strong`=Qwen3.6-27B-MTP, `fast`=Qwen2.5-Coder-7B, `utility`=Llama3.2-3B.

Every claim is tagged **[verified]** (primary source cited), **[likely]** (inferred from cited
primary sources, not directly stated), or **[unverified]** (no source found; treat as hypothesis).

---

## 0. TL;DR — the "do this" checklist, ordered by impact

| # | Action | Expected impact | Confidence |
|---|--------|-----------------|-----------|
| 1 | **Pin llama.cpp build ≥ 9755** (`0ef6f06d5`, 2026-06-21). Anything older has the `Until()` GBNF/PEG boundary bug that silently produces unparseable duplicate `</parameter>` tool calls on Qwen3.6-35B-A3B and **aborts the stream**. | Removes the single largest known source of hard tool-call failures on your exact model. Reporter measured ~1 in 128 tool requests. | verified |
| 2 | **Add `--reasoning off` (or `--reasoning-budget 0`) to the `coder`/`coder-strong` llama-swap entries used for agent loops.** `enable_thinking` via `chat_template_kwargs` is deprecated + ignored since build b8322 — you currently have *no* working thinking toggle. | Eliminates the "tool call captured as `reasoning_content`, `finish_reason: length`" class of failure, and cuts 1–2k wasted tokens/turn. | verified |
| 3 | **Give the coding agents a direct lane to llama-swap; keep LiteLLM for auth/remote/observability only.** LiteLLM's `openai/` adapter maps to *OpenAI's* param set, and `drop_params: true` silently discards anything not in it (`top_k`, `min_p`, `repeat_penalty`, `grammar`, `json_schema`, `chat_template_kwargs`). There is also a documented opencode+LiteLLM loop-abort bug (`finish_reason: "stop"` instead of `"tool_calls"`). | Restores full sampler/grammar control and removes an entire class of translation bugs from the hot path. | verified |
| 4 | **Sanitize every tool schema**: no `pattern` containing PCRE shorthands (`\d \w \s \b`), no `maxLength ≥ ~2000`, no deep nesting, minimum optional fields. One bad field fails GBNF compilation and **takes down the whole request**, not just that tool. | Removes hard 400/500s that look like "the model is broken" but are grammar-compile failures. | verified |
| 5 | **Cut the tool count reaching the model.** Your opencode config loads context7 + serena MCP on top of opencode's built-ins — plausibly 40–60 tools. Prune to the ~12 the task needs. | Largest single lever on *hallucinated tool names* for sub-40B models. | likely |
| 6 | **Stop overriding the model card's sampler with `temperature: 0.1`.** `harness.py` and `opencode.json` both send 0.1; the Qwen3.6 card specifies temp 0.6 / top_p 0.95 / top_k 20 / min_p 0 for precise coding — which your llama-swap config already sets correctly and the clients then clobber. | Unclear magnitude but you are currently *not* running the configuration you think you are. Measure it. | verified (mismatch) / unverified (impact) |
| 7 | **Verify the GGUF's embedded Jinja template round-trips assistant `tool_calls`** (procedure in §5). Qwen GGUF templates have a documented history of being broken on exactly this. | Prevents silent history corruption across multi-turn agent loops. | verified |
| 8 | **Build llama.cpp with `-DLLAMA_LLGUIDANCE=ON`** and A/B it for JSON-schema-constrained paths. It is the only sampler-level upgrade available in-tree, and it is ~5x faster per token than the GBNF path in independent benchmarks. | Faster + higher-coverage constrained decoding when you *do* force schemas. | verified |
| 9 | **Extend `bakeoff/harness.py`** per §8: schema validation, failure taxonomy, N≥300 tool calls per config, direct-vs-LiteLLM A/B, adversarial schema pack, golden-replay regression corpus. | Turns "tool calling feels flaky" into a number you can regress against. | n/a |
| 10 | **Do not use external-draft-model speculative decoding (`--spec-default`) on tool-calling paths.** MTP (`--spec-type draft-mtp`) is fine — it is verified/lossless. | Avoids mid-list truncation + repetition artifacts. You are already on MTP; just don't add draft models. | verified |

---

## 1. llama.cpp tool calling — exact state as of 2026-07

### 1.1 `--jinja` is now the default

The server README currently documents:

> `--jinja, --no-jinja` — "whether to use jinja template engine for chat (default: enabled)"

— https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

So the explicit `--jinja` in your `${srv}` macro (`docker/llama-swap-config.yaml:34`) is now redundant
but harmless, and worth **keeping** as documentation-in-config against a future default flip. **[verified]**

### 1.2 The architecture changed: `peg-native` + autoparser + lazy GBNF

The 2024/2025 model of "hand-written C++ handlers per model family" is largely gone. Current llama.cpp
uses an **autoparser** that reverse-engineers the Jinja template to derive both a prompt renderer and a
**PEG (Parsing Expression Grammar) parser** for the model's output, plus a **GBNF grammar generated from
the tool JSON schemas** to constrain generation.

- `jinja::caps` extracts template capabilities (does it support a system role? does it support `tool_calls`?)
- `peg_generator::generate_parser` "creates GBNF grammars by iterating over available functions and
  resolving JSON schemas"
- Tool formats are classified as e.g. `tool_format::JSON_NATIVE` or `tool_format::TAG_WITH_JSON`
- Reasoning handling is classified as `TAG_BASED` (e.g. `<think>`), `TOOLS_ONLY`, or delimiter-style,
  with **hardcoded patches for Qwen, Granite 3.3 and DeepSeek-R1 quirks**

— https://deepwiki.com/ggml-org/llama.cpp/3.9-chat-templates-and-message-parsing **[verified]**

Practical consequence: `docs/function-calling.md` is **stale**. Its "native support" list still reads
Llama 3.1/3.2/3.3, Functionary, Hermes 2/3, Qwen 2.5, Mistral Nemo, Firefunction v2, Command R7B,
DeepSeek R1 — no Qwen3.x — because Qwen3.x is handled generically by the autoparser, not by a named handler.
Don't conclude from that doc that Qwen3.6 is unsupported.
— https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md **[verified]**

### 1.3 **Yes — llama.cpp forces tool-call syntax at the sampler level, via "lazy grammars"**

This is the answer to the highest-leverage question in the brief.

When `tools` are present and `tool_choice: "auto"`, llama.cpp installs a **lazy grammar**: generation is
unconstrained until a **trigger** (the tool-call start marker, e.g. `<tool_call>`) is emitted, at which
point a GBNF grammar derived from the tool schemas takes over and constrains every subsequent token until
the call closes. Described explicitly in issue #24807:

> "The lazy grammar is an optimization that engages constraint-based token generation when
> `tool_choice: "auto"` is set. It triggers upon detecting the tool-call start marker (`<tool_call>`)
> to prevent malformed XML generation."

— https://github.com/ggml-org/llama.cpp/issues/24807 **[verified]**

So the sampler-level guarantee exists **for the argument body**, but:

- it does **not** cover the decision to call a tool at all (that's free generation), and
- until very recently the generated GBNF was *weaker* than the parser that consumed it (§1.4).

### 1.4 The Qwen3.6 tool-call bug chain — and the exact build you need

This is the most important operational finding for this stack. Qwen3.6 emits **XML-style** tool calls
(`<tool_call><function=name><parameter=filePath>…</parameter></tool_call>`), and the `until(delimiter)`
grammar construct used to bound parameter values was wrong.

| Item | Detail |
|---|---|
| **#24807** (build 9722, `159d093`) | On `Qwen3.6-35B-A3B`, the model emits a **duplicated `</parameter>`** in ~**1 of 128** tool-using requests in real multi-turn agent sessions, primarily on the reasoning variant. The lazy grammar fails to prevent it; the PEG parser then **drops the entire tool call and aborts the stream**. https://github.com/ggml-org/llama.cpp/issues/24807 |
| **PR #24839** (merged 2026-06-21) | Refactored `until()` grammar generation to use an **Aho-Corasick DFA** instead of approximate patterns. Approved by pwilkin, ngxson, ServeurpersoCom. **Did not fully fix it.** https://github.com/ggml-org/llama.cpp/pull/24839 |
| **#24863** (build 9744, `063d9c1`) | Root cause named: the **GBNF generator and the PEG parser disagree on the `Until(suffix)` boundary.** GBNF permissively allows the value to end where consumed text ends in a *proper prefix* of the suffix — so `value\n</parameter>\n</parameter>\n` is grammatically legal and the model is *never constrained against the duplicate tag*. The PEG parser greedily matches the **first** terminator, consumes it, then fails on the leftover. https://github.com/ggml-org/llama.cpp/issues/24863 |
| **PR #24869** (merged 2026-06-21) | Adds an "including variant: consume all characters up to **and including** a delimiter", closing the prefix escape. Explicitly "Fixes #24863". **Tested on llama-server version 9755 (`0ef6f06d5`).** https://github.com/ggml-org/llama.cpp/pull/24869 |

**→ Requirement: llama.cpp build ≥ 9755 (`0ef6f06d5`).** On anything older you are running a known,
reproducible, silent tool-call corruption bug against your exact primary coding model. **[verified]**

### 1.5 Other open/relevant tool-calling defects

- **#20260** — `peg-native` parser's grammar has `root ::= tool-call`, so if a **thinking model emits any
  prose before `<tool_call>`** (e.g. a Chinese transition phrase), the whole output fails to parse at the
  raw byte offset and the server returns **500**. Reproduced on `unsloth/Qwen3.5-35B-A3B-GGUF:Q8_0`,
  macOS/Metal, `--reasoning-format deepseek`. Broke Copilot Chat agent mode.
  https://github.com/ggml-org/llama.cpp/issues/20260 — **this is a direct argument for `--reasoning off`
  on agent loops.** **[verified]**
- **#20809** (b8429) — llama.cpp **falsely detects Qwen3-Instruct-2507 as a thinking model**
  (`init: chat template, thinking = 1`), so tool calls land in `reasoning_content` instead of `tool_calls`,
  and `finish_reason` returns `length` rather than `tool_calls`. **Workaround: `--reasoning off`**, after
  which the log reads `thinking = 0` and calls parse correctly. Related: #20550, #20265.
  https://github.com/ggml-org/llama.cpp/issues/20809 **[verified]**
- **#22072** (build 8831) — `unsloth/Qwen3.6-35B-A3B` emitted truncated JSON args (`{`) for a *minimal*
  schema (one required string `thread_id`, two optional ints). Closed as **not planned / stale**, no root
  cause. https://github.com/ggml-org/llama.cpp/issues/22072 **[verified — and note it is unresolved]**
- **#21316 / #22786** — Gemma 4 tool calls returned as raw native tokens in `content` instead of
  `tool_calls`. Not your models, but confirms the "raw tags leak into content" failure mode is live.
- **PR #24329 / release b9656** — hardening pass: `accept_openai_wrapper` parsing leniency so the parser
  accepts both native and OpenAI-shaped serializations; on final PEG parse failure llama.cpp now
  "surfaces a clean error and logs the unparsed fragment, rather than dumping raw parser coordinates";
  malformed JSON args are retained in a **`func_args_not_string`** variable rather than aborting the
  prompt render, enabling application-layer recovery.
  https://pseedr.com/stack/hardening-local-agentic-workflows-llamacpps-peg-native-tool-call-parsing-update
  **[verified — secondary source]**
- **Server now returns HTTP 400 with diagnostics** for malformed tool-call arguments instead of HTTP 500.
  https://buttondown.com/weekly-project-news/archive/weekly-github-report-for-llamacpp-july-07-2026-6412/
  **[verified — secondary source]** → your harness should treat 400 as *retryable model error*, 500 as
  *server bug*.

### 1.6 `tool_choice` support matrix

The server README documents `tool_choice` in **Anthropic shape**:

> `{"type": "auto"}`, `{"type": "any"}`, or `{"type": "tool", "name": "..."}`

— https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

The OpenAI-shaped string forms (`"none"` / `"auto"` / `"required"`) and OpenAI named-function form
(`{"type":"function","function":{"name":…}}`) are **not documented for `/v1/chat/completions`**.
`"auto"` is demonstrably exercised (it's what the lazy grammar keys off). **Treat `"required"` and
named-function forcing on llama.cpp as unproven — test before relying on it.** **[verified that it's
undocumented; unverified whether it works]**

Contrast — **vLLM** documents a much stronger matrix:
- `tool_choice: "required"` → "the model is guaranteed to produce at least one tool call… Arguments are
  guaranteed to be valid JSON conforming to the function's parameter schema."
- named function → structured outputs ensure validly-parsable calls
- `"auto"` → schema constraints apply **only** if `strict: true` on the tool **and**
  `VLLM_ENFORCE_STRICT_TOOL_CALLING=true`; otherwise "the model generates freely and tool calls are
  extracted from raw text", i.e. args can be malformed.

— https://docs.vllm.ai/en/latest/features/tool_calling.html **[verified]**

This is a genuine capability gap. If tool-call validity ever becomes the binding constraint and you can
afford the VRAM, vLLM with `tool_choice: "required"` + `qwen3_xml` parser is the stronger guarantee.

### 1.7 Parallel tool calls

> `parallel_tool_calls` — "Whether to enable parallel/multiple tool calls (only supported on some models,
> verification is based on jinja template)"

and from the function-calling doc: "Multiple/parallel tool calling is supported on some models but
**disabled by default**, enable it by passing `"parallel_tool_calls": true` in the completion endpoint payload."

— server README; https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md **[verified]**

**Recommendation: leave it off.** Disabled-by-default is the safer posture for a 3B-active-param MoE, and
it's one fewer axis for the parser to get wrong. Note that opencode 1.3.13 was observed *sending*
`parallel_tool_calls` unconditionally, which is part of why `drop_params: true` is load-bearing in your
LiteLLM config today. **[verified]**

### 1.8 Streaming tool-call deltas

llama.cpp implements "JSON healing for streaming structured data" — incremental emission of partial
tool-call arguments as OpenAI-style deltas.
— https://deepwiki.com/qualcomm/llama.cpp/8.2-chat-templates-and-tool-calling **[verified — secondary]**

But the failure mode in #24807 is specifically a **stream abort mid-request**, and #22072 raised the
question of "incomplete argument generation **or improper streaming concatenation**" without resolving it.
**Recommendation:** run the bake-off harness in **both** streaming and non-streaming modes and compare
malformed-call rates. If they differ, the bug is in delta reassembly, not the model. Your current
`harness.py` is non-streaming only, so it cannot see this class. **[likely]**

### 1.9 Reasoning / `<think>` separation

Current flags (server README, verbatim):

| Flag | Description |
|---|---|
| `--reasoning-format FORMAT` | "whether thought tags are allowed and/or extracted from the response, and in which format they're returned" — `none`, `deepseek`, `deepseek-legacy` (default: `auto`) |
| `-rea, --reasoning [on\|off\|auto]` | "Use reasoning/thinking in the chat ('on', 'off', or 'auto', default: 'auto')" |
| `--reasoning-budget N` | "token budget for thinking: -1 for unrestricted, **0 for immediate end**, N>0 for token budget (default: -1)" |
| `--chat-template-kwargs STRING` | "sets additional params for the json template parser, must be a valid json object string" |

**The critical regression:** since build **b8322**, setting `enable_thinking` via `--chat-template-kwargs`
(or per-request `chat_template_kwargs` / `extra_body`) is **deprecated and ignored**; the server emits a
deprecation message. The replacement `--reasoning on|off` is **startup-only** — there is **no per-request
reasoning toggle** through the OpenAI-compatible API.
— https://github.com/ggml-org/llama.cpp/discussions/23351 (open feature request; links #20182, #20409,
#13189, #20557, #21511, #22684, #22717) **[verified]**

This matters for you: unsloth's Qwen3.6 docs still tell you to use
`--chat-template-kwargs '{"enable_thinking":false}'` (https://unsloth.ai/docs/models/qwen3.6) — **that
advice is stale for llama.cpp ≥ b8322.** Use `--reasoning off` or `--reasoning-budget 0` instead.
**[verified]**

---

## 2. Constrained / structured decoding

### 2.1 What llama-server exposes

| Surface | Form |
|---|---|
| CLI | `--grammar GRAMMAR` ("BNF-like grammar to constrain generations"), `--grammar-file FNAME`, `-j/--json-schema SCHEMA`, `-jf/--json-schema-file FILE` |
| `/completion` | `grammar`, `json_schema` (e.g. `{"items":{"type":"string"},"minItems":10}`) |
| `/v1/chat/completions` | `response_format`: `{"type":"json_object"}` and schema-constrained `{"type":"json_object","schema":{…}}` |

— https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md **[verified]**

Known wart: you cannot supply `json_schema` and `grammar` simultaneously — "Either 'json_schema' or
'grammar' can be specified, but not both" (https://github.com/ggml-org/llama.cpp/issues/11847).
**[verified]** Practically this means you cannot layer a hand-written GBNF *on top of* the auto-generated
tool grammar; the tool path owns the grammar slot.

### 2.2 GBNF footguns that break tool calls (these are the ones that bite in practice)

llama.cpp compiles `pattern` regexes from your tool schemas into GBNF. Two hard failure modes:

1. **PCRE shorthand classes.** GBNF has no `\d`, `\w`, `\s`, or word boundaries `\b`. **A single offending
   field fails grammar compilation and takes down the entire request** — not just that tool.
   https://github.com/rowboatlabs/rowboat/issues/740 **[verified]**
2. **`maxLength` ≥ ~2000.** A string `maxLength: N` is emitted as `char{0,N}`. Since llama.cpp PR **#17381**
   added a repetition sanity cap (a DoS guard), llama.cpp now **generates a grammar its own parser rejects**.
   https://github.com/lemonade-sdk/lemonade/issues/2691 **[verified]**

Both of these look, from the client side, like "the model is broken". They are not. **Add a schema linter
to your tool pipeline** (§7.1).

### 2.3 Alternatives: llguidance, xgrammar, outlines

**LLGuidance is in-tree in llama.cpp but opt-in at build time:**

- Build: `cmake -B build -DLLAMA_LLGUIDANCE=ON` — **requires Rust/cargo**
- **No new CLI args.** Grammars prefixed `%llguidance` route to LLGuidance, **and so do JSON Schema
  requests (via `-j`)**
- Lark-flavoured syntax (lexer + CFG parser) rather than GBNF; a GBNF→Lark conversion script is provided
- Closely follows the JSON Schema spec (correct `additionalProperties` defaults, whitespace flexibility)
  and **errors loudly on unsupported schemas rather than silently ignoring keywords** — the opposite of
  the GBNF path's behaviour
- Performance: ~**50 µs** average token-mask computation for large tokenizers, **p99 0.5 ms**; the lexer
  handles ~99.5% of tokens

— https://github.com/ggml-org/llama.cpp/blob/master/docs/llguidance.md **[verified]**

**Server support matrix:**

| Engine | llama.cpp | vLLM | SGLang |
|---|---|---|---|
| GBNF (native) | ✅ default | ❌ | ❌ |
| llguidance / guidance | ✅ opt-in build | ✅ | ✅ |
| xgrammar | ❌ | ✅ (default) | ✅ (default) |
| outlines | ❌ | ✅ | ✅ |

— llama.cpp llguidance.md; https://docs.sglang.io/docs/advanced_features/structured_outputs;
https://docs.vllm.ai/en/latest/features/tool_calling.html **[verified]**

### 2.4 Measured impact — JSONSchemaBench (arXiv 2501.10868)

Six engines compared: Guidance, Outlines, **Llamacpp**, XGrammar, OpenAI, Gemini.

- **Coverage:** Guidance highest overall and highest compliance rate across all datasets. On GitHub-Easy,
  coverage spanned **59% (Outlines) → 96% (Guidance)**. Llamacpp excelled on domain-specific schemas
  (Washington Post: **94%**).
- **Speed (Llama-3.1-8B-Instruct, GlaiveAI):** time-per-output-token **Guidance 6.37 ms** vs
  **Llamacpp 29.98 ms** vs **Outlines 30.33 ms** — i.e. the GBNF path is ~**4.7× slower per token** than
  llguidance on that workload.
- **Grammar compile time:** Guidance **0.00–0.01 s**; Outlines **3.48–8.05 s**.
- **Quality:** constrained decoding "consistently improves the performance of downstream tasks **up to 4%**"
  — GSM8K **83.8%** constrained vs **80.1%** unconstrained — and can **speed up generation by 50%** vs
  unconstrained (fewer wasted tokens).

— https://arxiv.org/html/2501.10868v3 **[verified]**

**Takeaway:** the old folklore that "grammars dumb the model down" is not supported. Constrained decoding
is a net win on accuracy *and* often on speed. The cost is engine-dependent, and llama.cpp's default GBNF
engine is the slow one. **This is the case for the `-DLLAMA_LLGUIDANCE=ON` build.**

### 2.5 Counter-evidence: grammars guarantee syntax, not semantics

arXiv 2605.02363, "When Correct Isn't Usable: Improving Structured Output Reliability in Small Language
Models" — Llama 3.1-8B, Gemma 2-9B IT, Qwen 2.5-7B (plus GPT-4o probe):

- **NAIVE prompting (no format guidance): 77–85% task accuracy but 0% *output* accuracy** on GSM8K —
  the models solve the problem and then fail to emit parseable JSON. This is the "format gap".
- **CONSTRAINED (vLLM grammar-based): 15–52%** output accuracy on GSM8K
- **ALOLAB (iteratively optimized system prompt, no grammar): 84–87%** GSM8K, **34–40%** MATH
- Constrained decoding cost **3.6×–8.2× latency overhead**; ALOLAB ran at **0.71×–1.06×** NAIVE speed
- 29 of 30 paired McNemar comparisons favoured ALOLAB (p<0.05)
- GPT-4o: REFERENCE prompting 0% output accuracy → ALOLAB **95.2%**

— https://arxiv.org/html/2605.02363v1 **[verified]**

**Reconciling the two papers:** grammars make output *parseable*; they do not make the model put the right
*content* in the right *field*. A grammar-constrained model can happily emit
`{"path": "the file you asked about"}`. Both papers agree that a **well-engineered format prompt is the
cheapest, highest-yield intervention**, and grammar is a floor under it, not a substitute. This directly
motivates checklist item #5 and §7.

The paper's failure taxonomy is worth stealing verbatim for your harness: markdown-fence wrapping (Gemma),
LaTeX escaping (Llama). Your models will have their own signature tics — find them by logging raw output.

### 2.6 So: can you FORCE valid tool calls at the sampler level in llama.cpp today?

**Partially.** Honest answer:

- ✅ **Argument syntax is grammar-constrained** once the tool-call trigger fires (lazy grammar, §1.3).
- ✅ **Tool *name* is constrained** — the generated GBNF enumerates the available functions
  ("iterating over available functions"), so hallucinated *names* should be structurally impossible
  inside a `<tool_call>` block. **[likely — inferred from deepwiki's description of
  `peg_generator::generate_parser`; not stated as a guarantee]**
- ❌ **The decision to emit a tool call at all is unconstrained** — there is no reliable documented
  `tool_choice: "required"` on llama.cpp (§1.6).
- ❌ **The grammar has been demonstrably weaker than the parser** until build 9755 (§1.4), so "constrained"
  did not mean "correct".
- ❌ **Semantic correctness is not constrained at all** (§2.5).

Practical stance: treat the lazy grammar as a strong-but-not-total floor, pin build ≥9755, and keep a
client-side validate-and-retry layer (§7.2).

---

## 3. Sampling settings for agentic reliability

### 3.1 Model-card recommendations (Qwen3.6-35B-A3B / 27B)

From https://huggingface.co/Qwen/Qwen3.6-35B-A3B and https://unsloth.ai/docs/models/qwen3.6: **[verified]**

| Mode | temp | top_p | top_k | min_p | presence_penalty | repetition_penalty |
|---|---|---|---|---|---|---|
| Thinking — general | 1.0 | 0.95 | 20 | 0.0 | 1.5 | 1.0 |
| **Thinking — precise coding** | **0.6** | **0.95** | **20** | **0.0** | **0.0** | **1.0** |
| Non-thinking / instruct | 0.7 | 0.80 | 20 | 0.0 | 1.5 | 1.0 |

Note the model card contained an internal inconsistency (a "Best Practices" section listing
top_p 1.0 / top_k 40 / presence 2.0) that was **reconciled in late May 2026** to the values above —
https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/23. If you cached values before then, re-check.
**[verified]**

Note also: **Qwen recommends presence_penalty 0.0 specifically for precise coding**, versus 1.5 for
general thinking. Since presence/repetition penalties penalize repeated *structural* tokens (`"`, `{`,
`</parameter>`, repeated key names across parallel calls), a nonzero presence penalty is actively hostile
to structured output. The model card's own split corroborates this. **[verified that Qwen splits it;
likely as to the structural-token mechanism]**

### 3.2 What your stack actually runs — and the conflict

`docker/llama-swap-config.yaml` sets, correctly, for both Qwen3.6 entries:
`--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0` — **exactly the card's precise-coding row.** Good.

But:
- `bakeoff/harness.py:43` sends `"temperature": 0.1`
- `opencode.json` sets `"temperature": 0.1` on both the `build` and `plan` agents

Per-request values override server defaults. **You are benchmarking and coding at temp 0.1, not 0.6, and
with top_p/top_k/min_p left at whatever the client sends (likely provider defaults, possibly `top_p: 1`).**
Worse, LiteLLM's `openai/` adapter will not forward `top_k`/`min_p` at all (§4.2), so the server-side
top_k=20 / min_p=0 survive only because they're CLI defaults — but any client that *does* send `top_p`
silently replaces the tuned one. **[verified from your files + LiteLLM docs]**

### 3.3 Is greedy right for agents?

- JSONSchemaBench evaluated with **greedy decoding at zero temperature**
  (https://arxiv.org/html/2501.10868v3) — standard practice for structured-output evaluation. **[verified]**
- I found **no published study isolating temperature's effect on tool-call JSON validity**. Claims that
  "temp 0 fixes malformed JSON" are **[unverified]** folklore.
- Reasoned position **[likely]**: with a lazy grammar active, temperature cannot produce *syntactically*
  invalid arguments; it can only shift which valid string gets chosen. So temperature's real effect on
  tool calling is on *semantic* quality and on loop behaviour (getting stuck, failing to stop) — not on
  parse validity. That reframes the tuning question: pick temperature for task quality, and rely on the
  grammar + retry layer for validity.
- Argument against pure greedy: greedy decoding is the classic recipe for **repetition loops** in agent
  loops (call the same tool with the same args forever). The Qwen card's 0.6 with top_k 20 is a reasonable
  hedge. Your `fast-3b`/`utility` entry at `--temp 0` is right for classification/titles, where determinism
  is the point.

**Recommendation:** make temperature a swept axis in the harness (0.0 / 0.2 / 0.6 / 1.0) rather than
guessing, and *stop* silently overriding it in clients. Concretely: delete `"temperature": 0.1` from
`opencode.json` agents and from `harness.py`'s default body, and let llama-swap's per-model card values apply.

### 3.4 Other sampler notes

- **DRY sampler**: you use it on the RP models only. Correct — do **not** enable DRY/repetition penalties
  on coding/tool models; they punish structural repetition.
- **`fast` = Qwen2.5-Coder-7B** at `--temp 0.7 --top-p 0.8 --top-k 20 --repeat-penalty 1.05`. That
  `repeat-penalty 1.05` is the Qwen2.5 `generation_config` value, but per §3.1's logic it is a mild risk
  for JSON args. Worth an A/B at 1.0 for the tool-calling role specifically. **[likely]**
- **KV cache quantization**: llama.cpp's own function-calling doc warns extreme KV quant (`-ctk q4_0`)
  "can **substantially degrade** the model's tool calling performance"
  (https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md). You run `q8_0`/`q8_0`,
  which is not extreme — but it is a named risk axis and is *never* free. **Run one bake-off config with
  KV quant off** (or `bf16`, per unsloth's gibberish workaround) to quantify what q8_0 KV costs you in
  tool-call validity. **[verified warning; unverified magnitude at q8_0]**
- **Speculative decoding**: external-draft-model specdec (`--spec-default`) is documented to cause
  mid-list truncation with `finishReason=stop`, repetition loops, and SSE stalls in tool-calling paths
  (https://netclaw.dev/troubleshooting/llama-cpp/). **MTP is different and safe**: PR #22673 (merged
  2026-05-16, tested on Qwen3.6 27B and 35B-A3B) uses the model's *own* MTP heads and accepts draft
  tokens **only if they pass verification**, so output is unchanged
  (https://github.com/ggml-org/llama.cpp/pull/22673). Your `--spec-type draft-mtp --spec-draft-n-max 2`
  on `qwen3.6-27b` is fine. Keep `--parallel 1` as your config already notes. Watch for the **b9235 MTP
  performance regression** flagged in the July weekly report. **[verified]**

---

## 4. LiteLLM in the path

### 4.1 Does LiteLLM alter tool calls?

Your config routes `openai/qwen3.6-35b-a3b` → `http://llama-swap:8080/v1`. LiteLLM's `openai/` prefix
"routes your request to an OpenAI-compatible endpoint **using the upstream official OpenAI Python API
library**" (https://docs.litellm.ai/docs/providers/openai_compatible). **[verified]**

That means every request is (de)serialized through OpenAI's Pydantic models, and the response is
re-normalized into LiteLLM's `ModelResponse`. It is **not** a byte-transparent proxy.

### 4.2 `drop_params: true` — what it actually costs you

> "LiteLLM will drop the unsupported parameter instead of raising an exception… LiteLLM maps all supported
> openai params by provider + model."

— https://docs.litellm.ai/docs/completion/drop_params. The docs give **no warning about silent drops** and
do not state whether `tools`/`tool_choice`/`parallel_tool_calls`/`response_format` are ever dropped.
**[verified]**

The operational consequence for your stack **[likely, high confidence]**: the "supported OpenAI params"
set does not include llama.cpp-specific knobs. So through LiteLLM you very likely **cannot** send:
`top_k`, `min_p`, `repeat_penalty`, `dry_*`, `grammar`, `json_schema`, `chat_template_kwargs`,
`reasoning_budget`, or `cache_prompt`. They will be dropped **silently**, because that's the whole point
of `drop_params: true`. You will not get an error telling you your grammar was discarded.

This is the crux of the bypass argument: **the highest-leverage tool-calling interventions in llama.cpp
are exactly the params LiteLLM cannot forward.**

You keep `drop_params: true` because you have to — opencode 1.3.13 sends `parallel_tool_calls`
unconditionally and some backends reject it. But the flag is a blunt instrument.

### 4.3 Known LiteLLM bugs on the tool-call path

| Issue | Detail |
|---|---|
| **opencode #20719** | **Your exact client stack.** opencode 1.3.13 + `@ai-sdk/openai-compatible` + LiteLLM: the agent loop **exits after the first LLM call** because opencode's `session/prompt.ts` keys loop continuation on `finish_reason`, and LiteLLM returned `"stop"` where OpenAI returns `"tool_calls"`. Direct curl to the backend returned the correct value — the gateway lost it. **Closed as "not planned."** Affects LiteLLM v1.82.6+. https://github.com/anomalyco/opencode/issues/20719 (dupe of #14972; same symptom in paperclip #2525) |
| **LiteLLM #17246** | Streaming **drops `tool_calls` deltas entirely** when a response mixes text + function calls; only `delta.content` chunks are emitted. v1.80.7, PR #17652. Reported for the Responses→ChatCompletions bridge. https://github.com/BerriAI/litellm/issues/17246 |
| **LiteLLM #19700** | `drop_params` / `additional_drop_params` **not honoured at model level** when `drop_params` is set globally in `litellm_settings` — a config-hierarchy bug. v1.81.1, PR #21195. **Note: your config sets `drop_params` in `litellm_settings` exactly as in the bug report.** https://github.com/BerriAI/litellm/issues/19700 |
| **LiteLLM #21147** | Proxy misroutes `model:`-prefixed IDs to the wrong upstream. https://github.com/BerriAI/litellm/issues/21147 |

**[all verified]**

Also note `router_settings.num_retries: 2` in your config: on a **non-idempotent agentic tool call**, a
silent gateway-level retry can cause a tool to execute twice, or produce a second divergent tool call the
client never asked for. For a single-upstream, single-deployment router this buys you almost nothing and
risks duplicate side effects. **Consider `num_retries: 0` for the coder aliases** and handle retries in
the client where you can see them. **[likely]**

### 4.4 Verdict: should the coding clients bypass LiteLLM?

**Yes — add a direct lane; don't demolish the gateway.**

| | LiteLLM path | Direct llama-swap path |
|---|---|---|
| Auth | ✅ master key, virtual keys, budgets | ❌ unauthenticated (LAN/firewall only) |
| Observability | ✅ request logs, spend DB | ❌ llama-server logs only |
| Stable public aliases | ✅ `coder`, `fast`… | ⚠️ llama-swap model IDs are also stable aliases |
| Remote access | ✅ via `llm.tabaska.us` | ❌ LAN-only |
| **Sampler fidelity** | ❌ silent param drops | ✅ full `top_k`/`min_p`/`grammar`/`chat_template_kwargs` |
| **`finish_reason` fidelity** | ❌ documented corruption (#20719) | ✅ |
| **Streaming tool deltas** | ⚠️ documented drop bug (#17246) | ✅ |
| Retry side effects | ⚠️ `num_retries: 2` | ✅ none |

**Concrete recommendation:**

1. Expose llama-swap on the LAN at a second hostname (e.g. `http://rig:9292/v1`), unauthenticated behind
   the existing firewall — llama-swap already serves `/v1/chat/completions`, `/v1/models`, etc.
   (https://github.com/mostlygeek/llama-swap).
2. Point **opencode** and **pi** at that URL for `coder`/`coder-strong`. Note llama-swap's model IDs are
   `qwen3.6-35b-a3b` / `qwen3.6-27b`, so either rename the client model IDs or add aliases in
   llama-swap so `coder` resolves there too — keeping one vocabulary is worth the effort.
3. Keep LiteLLM as the **authenticated, remote, multi-client** front door for Open WebUI, HA, Obsidian,
   scripts, and anything off-LAN.
4. **Point `bakeoff/harness.py` at llama-swap directly by default** (`BAKEOFF_BASE`), and add a
   `--via-litellm` mode so the gateway's contribution to malformed-call rate is *measured*, not assumed.
   This single change makes the bake-off measure the model instead of the model-plus-gateway.

---

## 5. Chat template pitfalls + verification procedure

### 5.1 Why GGUF-embedded templates go wrong

The Jinja template baked into a GGUF is a snapshot taken at conversion time. Quantizers re-upload weights
without re-taking the snapshot; upstream fixes the template on the HF repo; the GGUF keeps the old one.
For Qwen specifically this is a documented, recurring problem:

- "tool calling chat template is broken" — https://huggingface.co/Qwen/Qwen3.5-35B-A3B/discussions/4
- Unsloth shipped "New Chat Template + Tool Calling Fixes" for Qwen3-Coder-30B-A3B —
  https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/discussions/10
- Qwen3.5-35B-A3B GGUFs were **re-uploaded** with template changes improving "chat, coding, long context,
  and tool-calling"; the fix was noted as "universal… any Qwen3.5 format and any uploader" —
  https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF/discussions/18
- Community fixes observed in the wild: **removing the `| safe` filter at two locations** (fixed Qwen Code);
  **removing the 'No user query' exception** (stopped override errors and let tool calls through without
  crashing)
- Curated corrected templates: https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates and
  https://huggingface.co/Moore2877/Qwen-Fixed-Chat-Templates-llamacpp

**[all verified]**

Override mechanism: `--chat-template-file <path>` (or `--chat-template <inline>`). Since llama.cpp's
autoparser derives **both** the renderer and the PEG output parser from the template, a wrong template
breaks tool calling in *both* directions — a subtle and important property of the new architecture.

### 5.2 Template verification procedure (run this per model, per GGUF update)

**Step 0 — record the baseline.** On llama-swap start, capture the llama-server startup log. Look for:
- the detected chat format (you want **`peg-native`** for Qwen3.6, not a generic fallback)
- `init: chat template, thinking = 0|1` — **if this says `1` for a model you intend to run
  non-thinking, you have already hit #20809.** Fix with `--reasoning off`.

**Step 1 — dump the embedded template.**
```bash
# via the server
curl -s http://rig:PORT/props | jq -r '.chat_template' > /tmp/embedded.jinja
# or from the GGUF metadata directly
python3 gguf-py/scripts/gguf_dump.py --no-tensors /models/Qwen3.6-35B-A3B-*.gguf \
  | grep -i chat_template
```
Diff it against the current `chat_template.jinja` on the upstream HF repo. **Any diff is a finding.**

**Step 2 — render-only round trip (`/apply-template`).** llama-server exposes a template-render endpoint;
POST a conversation and read back the exact prompt string without generating. Send the **four-message
tool round trip**:
```json
{"messages":[
  {"role":"system","content":"You are a coding agent."},
  {"role":"user","content":"read main.py"},
  {"role":"assistant","content":"",
   "tool_calls":[{"id":"call_1","type":"function",
     "function":{"name":"read_file","arguments":"{\"path\":\"main.py\"}"}}]},
  {"role":"tool","tool_call_id":"call_1","content":"print('hi')"},
  {"role":"user","content":"now what?"}
 ],
 "tools":[ ...your read_file schema... ]}
```
**Pass criteria** — the rendered prompt must contain, in order:
1. the tool definitions (JSON or XML per the model's format),
2. an assistant turn containing `read_file` **and** `main.py` in the model's native tool-call syntax,
3. a tool-result turn containing `print('hi')` correlated to that call,
4. a trailing generation prompt.

**Fail modes to look for:** the assistant `tool_calls` silently vanish (most common — template only
handles `message.content`); arguments rendered as a Python dict `{'path': 'main.py'}` instead of JSON;
`tool_call_id` dropped so results can't be correlated; a raised Jinja exception (e.g. the "No user query"
guard). **Any of these means the model loses its own action history every turn** — which presents as
"the model repeats the same tool call forever."

**Step 3 — live generation round trip.** POST the same payload to `/v1/chat/completions` with `tools`.
Assert: HTTP 200; `choices[0].finish_reason == "tool_calls"` when a call is made;
`message.tool_calls[0].function.arguments` parses as JSON **and validates against the tool's JSON Schema**;
`message.content` contains **no** literal `<think>`, `</think>`, `<tool_call>`, `<function=`, or
`</parameter>`; `reasoning_content` (if present) contains **no** tool-call syntax (the #20809 signature).

**Step 4 — streaming round trip.** Repeat step 3 with `"stream": true`. Reassemble `delta.tool_calls`
by index. Assert the reassembled arguments are byte-identical to the non-streaming result and that the
stream terminates with a proper `finish_reason` rather than aborting.

**Step 5 — grep the server log** for `common_chat_peg_parse: unparsed peg-native output:` — that string
is the fingerprint of #24807/#24863-class failures and should appear **zero** times.

**Step 6 — soak.** Because the known bug rate is ~**1/128**, steps 3–4 must run **≥300 tool calls** per
model before you can claim "clean." A single green run proves nothing.

**Step 7 — if any step fails:** fetch the corrected template (froggeric / Moore2877 / upstream HF),
mount it into the container, and add `--chat-template-file /models/templates/<model>.jinja` to that
model's llama-swap `cmd`. Re-run from step 2.

### 5.3 Qwen3.6 specifics

- **Tool-call format is XML**, not JSON:
  `<tool_call><function=NAME><parameter=ARG>value</parameter>...</function></tool_call>` — confirmed by the
  raw payloads in #24807/#24863. This is why the `Until()`/delimiter grammar bugs hit this family so hard;
  JSON-native families (Hermes-style) don't use `until()` the same way. **[verified]**
- **Thinking toggle**: `--reasoning off` / `--reasoning-budget 0` at startup only (§1.9). The unsloth doc's
  `--chat-template-kwargs '{"enable_thinking":false}'` is stale for llama.cpp ≥ b8322. **[verified]**
- **`preserve_thinking: true`** is recommended by Qwen for agent scenarios ("maintaining full reasoning
  context can enhance decision consistency") — but whether llama.cpp honours it through
  `--chat-template-kwargs` after the b8322 deprecation is **[unverified]**. Test it explicitly.
- **Developer role**: unsloth notes Qwen3.6 adds "developer role support… for agentic coding tools." Your
  pi config sets `supportsDeveloperRole: false`, which is the safe choice for llama.cpp OpenAI servers
  regardless. Leave it. **[verified in your config + unsloth]**
- **Do not use CUDA 13.2** — unsloth warns of gibberish output. If gibberish appears, try
  `--cache-type-k bf16 --cache-type-v bf16`. https://unsloth.ai/docs/models/qwen3.6 **[verified]**

---

## 6. Reasoning models in agent loops

### 6.1 The mechanical problem

Three separate ways thinking breaks tool calls, all documented:

1. **#20260** — prose (or a thinking remnant) before `<tool_call>` makes `root ::= tool-call` fail →
   **HTTP 500**. Hit specifically on the thinking variant.
2. **#20809** — false thinking detection routes the tool call into `reasoning_content`, and
   `finish_reason` comes back `length` instead of `tool_calls`. Clients that key their loop on
   `finish_reason` (**opencode does** — see #20719) stop dead.
3. **#24807** — the duplicate-`</parameter>` bug occurred "primarily on the **reasoning variant**."

**[all verified]** Reasoning is not neutral for tool calling on this stack; it is a documented risk multiplier.

### 6.2 The economic problem

Your own bake-off measured 35B-A3B at **73–126 tok/s** and 27B at **23–31 tok/s**
(`docker/litellm-config.yaml:17-20`). A 1–2k-token thinking block per turn × 20 turns = 20–40k tokens of
thinking per task. On `coder-strong` at ~27 tok/s that is **12–25 minutes of pure thinking per task**, on
top of the actual work. On a homelab with one GPU and a `--parallel 1` MTP constraint, that is the
dominant cost. **[verified inputs, arithmetic mine]**

### 6.3 Recommendation

**Turn thinking off for tool-heavy loops.** Concretely, since there is no per-request toggle:

```yaml
  "qwen3.6-35b-a3b":                       # agentic / tool loops — reasoning OFF
    cmd: |
      ${srv}
      --model /models/Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf
      --ctx-size 262144
      --reasoning off
      --reasoning-format none
      --temp 0.7 --top-p 0.80 --top-k 20 --min-p 0
    ttl: 120

  "qwen3.6-35b-a3b-think":                 # planning / hard reasoning — reasoning ON
    cmd: |
      ${srv}
      --model /models/Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf
      --ctx-size 262144
      --reasoning on
      --reasoning-format deepseek
      --reasoning-budget 2048
      --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0
    ttl: 120
```

Notes:
- Same GGUF, two entries. Both are in the `big` group (`swap: true, exclusive: true`), so switching costs
  an NVMe reload — seconds, per your own config comment. Acceptable for a mode switch that happens once
  per session, not per turn.
- **The sampler must change with the mode.** Reasoning-off is "non-thinking/instruct" mode, whose card
  values are temp **0.7** / top_p **0.80** / top_k 20 — *not* the 0.6/0.95 thinking-coding row. This is
  easy to get wrong.
- `--reasoning-budget 2048` on the thinking entry caps the worst case; `-1` (default) is unbounded.
- Map opencode's `build` agent → the reasoning-off entry, `plan` agent → the thinking entry. That mirrors
  the split you already have in `opencode.json`.
- Alternative single-entry compromise: keep `--reasoning on` with `--reasoning-budget 0`
  ("immediate end") — the template still takes its thinking path (so template-detected capabilities stay
  consistent) but no thinking tokens are spent. Worth A/B-ing against `--reasoning off`; they are not
  guaranteed equivalent. **[unverified equivalence]**

### 6.4 Client handling of `<think>` and `reasoning_effort`

- **`--reasoning-format deepseek`** extracts `<think>…</think>` into a separate `reasoning_content` field
  so it does **not** pollute `message.content`. `--reasoning-format none` leaves thought tags inline
  (or disallows them). For agent clients, `deepseek` (extract) or `none` + `--reasoning off` are the
  safe choices; **never** let raw `<think>` reach an OpenAI-shaped `content` field, because opencode/pi
  will treat it as the assistant's answer. **[verified]**
- **`reasoning_content` is non-standard**: `@ai-sdk/openai-compatible` and pi's `openai-completions`
  adapter will most likely ignore it, and **LiteLLM may drop it** under `drop_params`. That's fine — you
  don't want it in the loop anyway — but it means you cannot rely on it for observability through the
  gateway. **[likely]**
- **`reasoning_effort`**: pi is already configured `supportsReasoningEffort: false`
  (`clients/pi-models.json:8`), which the pi docs require for llama.cpp-style servers or reasoning
  requests error. llama.cpp does not implement `reasoning_effort`; the nearest equivalent is
  `--reasoning-budget N`, which is **server-side only**. Keep the flag false. **[verified from your file;
  llama.cpp side verified by absence in server README]**

---

## 7. Client-side mitigations

### 7.1 Schema rules (derived from the actual bugs, not folklore)

Enforce these with a linter that runs over every tool schema before it's sent:

| Rule | Why | Source |
|---|---|---|
| **No `pattern` with `\d` `\w` `\s` `\b`** | GBNF has no PCRE shorthands; one bad field fails grammar compilation and **kills the whole request** | rowboat #740 |
| **No `maxLength ≥ ~2000`** | emitted as `char{0,N}`, trips the repetition sanity cap from llama.cpp #17381 → self-rejecting grammar | lemonade #2691 |
| **Flat objects; no nested objects/arrays-of-objects** | unsloth's Qwen3.6 notes call out "improved parsing of nested objects" as a *fix*, implying nesting was the problem | unsloth Qwen3.6 docs |
| **Minimise optional fields** | #22072 failed on 1 required string + **2 optional ints** — a schema you'd call trivial | llama.cpp #22072 |
| **Avoid huge free-text args where possible** | `write_file(content)` is an unavoidable exception, but it is exactly the `until()`-delimited long-value case that broke in #24807/#24863 | llama.cpp #24863 |
| **Distinct, non-prefix tool names** | `read_file` / `read_files` / `read` invite name confusion; prefer `read_file`, `list_dir`, `apply_patch` | **[unverified — folklore, but low cost]** |

Your `harness.py` TOOLS block already satisfies most of this — it's a good baseline. Note that
`write_file.content` is precisely the long-`until()`-value shape, so **your harness will exercise the
#24863 path**; that's a feature.

### 7.2 Retry-on-invalid-tool-call

llama.cpp now returns **HTTP 400 with detailed diagnostics** for malformed tool-call arguments instead of
500 (weekly report, July 2026), and preserves malformed args in `func_args_not_string` rather than
aborting the prompt render, "enabling application-layer error recovery" (PR #24329 / release b9656).
**[verified — secondary sources]**

So the correct client policy is:

| Condition | Action |
|---|---|
| `json.loads(arguments)` fails | Re-send with a `role: tool` message: `"ERROR: your tool_call arguments were not valid JSON. Emit exactly one tool call with valid JSON."` Retry ≤2×. |
| Args parse but **fail JSON Schema validation** | Re-send with the *specific* validation error + the schema. This is the most recoverable failure. |
| **Unknown tool name** | Re-send with `"ERROR: no tool named X. Available: [...]"`. Do **not** silently ignore. |
| **HTTP 400 from llama-server** | Model-side malformed call → retry with the same feedback loop. |
| **HTTP 500 / stream abort** | Server-side bug (#24807 class) → retry the *turn* verbatim (it's stochastic, ~1/128) and log loudly. |
| `finish_reason` ∈ {`length`} with tool syntax in content/reasoning | #20809 signature → alarm, don't retry; fix `--reasoning`. |

Your current `harness.py` conflates several of these: it counts every `HTTPError` as `malformed_calls`
(line 118) and only checks `json.loads` + `isinstance(dict)` (line 147-148) without schema validation.
Both are addressed in §8.

### 7.3 Tool count

There is no published threshold I could find for Qwen3.6-class models **[unverified]**, but the direction
is well supported: TinyLLM (arXiv 2511.22138) and the BFCL v4 results both show multi-turn/many-tool
settings are where small models collapse — Qwen3-4B scores **82.58% non-live** and **75.52% live** but
only **35.25% multi-turn** (https://gorilla.cs.berkeley.edu/leaderboard.html,
https://llm-stats.com/benchmarks/bfcl-v4). **[verified]**

Your `opencode.json` enables **serena** (an LSP-backed MCP server exposing on the order of 20–25 tools),
**context7**, opencode's built-ins, and `skills*`. A plausible 40–60 tool surface for a 3B-active-param
MoE. **Actions:**
- Restrict serena to the subset you actually use, or enable it only for the `plan` agent.
- Disable `context7` for `build` (it's a docs-lookup tool; it competes for attention during editing).
- Measure it: the harness tool-count ladder in §8.4 will tell you where *your* models fall off.

### 7.4 Prompting

From arXiv 2605.02363 (§2.5), the evidence-backed points **[verified]**:
- A naive system prompt yields **0% valid structured output** on 7–9B models even at 77–85% task accuracy.
  Format instructions are not optional decoration.
- **Iteratively optimizing the system prompt against observed failures** beat grammar-constrained decoding
  (84–87% vs 15–52% on GSM8K) at **0.71–1.06×** the latency versus **3.6–8.2×** for constrained decoding.
- Failure tics are **model-specific** (markdown fences on Gemma, LaTeX escaping on Llama) — so the win
  comes from looking at *your* models' raw failures and writing counter-instructions, not from copying
  someone else's prompt.

Practical translation for your `SYSTEM` prompt in `harness.py` / `AGENTS.md`:
- State the stopping condition unambiguously and put it **last** (your "reply with the single word DONE
  and no tool call" is already good).
- Add an explicit one-call-at-a-time instruction (you have `parallel_tool_calls` off anyway).
- Add counter-instructions for observed tics once you've logged them (e.g. "Do not wrap tool calls in
  markdown code fences." "Do not describe the tool call in prose; emit it.").
- **Few-shot tool examples**: no benchmark evidence found for their effect on Qwen3.x specifically
  **[unverified]**. Given that the lazy grammar already constrains syntax, few-shot examples are better
  spent demonstrating *when* to call which tool (semantics) than *how* to format it (syntax).

---

## 8. Harness design — extending `bakeoff/harness.py`

Current harness (`/Users/btabaska/orca/workspaces/local-ai-tooling/dugong/bakeoff/harness.py`) is a solid
skeleton: real repo sandbox, 4 tools, 20-turn cap, counts turns/malformed/tok-per-sec/success. Gaps:
single run per config, `temperature: 0.1` hardcoded (line 43), non-streaming only, no schema validation,
`HTTPError` conflated with malformed calls (line 118), no sampler sweep, no direct-vs-gateway A/B,
fixed 4-tool surface, no raw-output capture.

### 8.1 Failure taxonomy (replace the single `malformed_calls` counter)

```python
FAILURE_KINDS = [
  "json_decode_error",     # arguments not parseable JSON
  "args_not_object",       # parsed but not a dict
  "schema_violation",      # jsonschema.validate failed  <-- NEW, the important one
  "unknown_tool_name",     # hallucinated function name
  "empty_args",            # {} when required fields exist
  "reasoning_leak",        # <think>/<tool_call>/<function=/</parameter> literal in content
  "toolcall_in_reasoning", # tool syntax found in reasoning_content   (#20809 signature)
  "finish_reason_mismatch",# tool_calls present but finish_reason != "tool_calls"  (#20719 signature)
  "http_400",              # server rejected malformed args (model-side)
  "http_500",              # server bug (peg parse abort, #24807 class)
  "stream_abort",          # SSE ended without finish_reason
  "duplicate_call",        # identical (name,args) as previous turn -> loop
  "no_stop",               # hit MAX_TURNS
  "hallucinated_done",     # said DONE, tests red  (already present)
]
```
`schema_violation` is the highest-value addition: it's the failure the grammar *cannot* prevent (§2.6),
and it's invisible to the current harness because `json.loads` succeeds.

### 8.2 Config matrix (the sweep)

```python
CONFIGS = {
  "endpoint":  ["direct", "litellm"],                       # A/B the gateway (§4.4)
  "stream":    [False, True],                               # A/B delta reassembly (§1.8)
  "reasoning": ["off", "on"],                                # two llama-swap entries (§6.3)
  "temp":      [0.0, 0.2, 0.6, 1.0],                         # is greedy right? (§3.3)
  "penalty":   [0.0, 1.05],                                  # presence/repeat harm to JSON (§3.4)
  "tools_n":   [4, 12, 30, 60],                              # tool-count ladder (§8.4)
  "schema":    ["clean", "adversarial"],                     # §8.3
  "kv":        ["q8_0", "f16"],                              # KV-quant cost to tool calls (§3.4)
}
```
Don't run the full cross product. Run a **one-factor-at-a-time** sweep off a fixed baseline
(direct / non-stream / reasoning off / temp 0.6 / penalty 0 / 12 tools / clean / q8_0), then cross only
the two or three factors that moved the needle.

### 8.3 Adversarial schema pack

A second tool set designed to trip the documented GBNF bugs, run as a **pure validity** test (no repo task,
just "call each tool once with plausible args"):

| Tool | Property under test | Expected failure if unpatched |
|---|---|---|
| `t_pattern` | `"pattern": "^\\d{3}-\\d{4}$"` | grammar compile failure, whole request 400/500 (rowboat #740) |
| `t_maxlen` | `"maxLength": 4096` | self-rejecting grammar (lemonade #2691) |
| `t_longval` | 8 KB code blob in a string arg | `until()` boundary / duplicate terminator (#24863) |
| `t_nested` | 3-level nested object | nested-object parse failures |
| `t_optional` | 1 required + 8 optional fields | truncated args (#22072) |
| `t_unicode` | emoji, CJK, RTL in a string arg | escaping bugs |
| `t_newlines` | value containing `\n</parameter>\n` **literally** | direct #24863 reproduction |
| `t_enum` | 40-value enum | enum grammar blowup |

`t_newlines` is the single highest-value test: it directly probes whether your build has PR #24869.

### 8.4 Tool-count ladder with decoys

Pad the real 4 tools with N plausible-but-unused decoys (`search_web`, `run_linter`, `git_commit`, …).
Metric: **`unknown_tool_name` rate** and **decoy-invocation rate** as a function of N. This is the
cleanest measurement of hallucination pressure from tool surface size, and it directly informs the MCP
pruning decision in §7.3.

### 8.5 Statistical power

The reference bug (#24807) occurs at **~1/128 tool calls**. To detect a regression of that size with any
confidence you need **≥300–400 tool calls per configuration**. At ~15 tool calls per task run, that's
**≥25 runs per config**. Report **rate with a Wilson confidence interval**, not a raw count — a single
green run is not evidence.

### 8.6 Golden-replay regression corpus

The most valuable output of the harness:

1. On **any** failure, dump the exact request (`messages` + `tools` + sampler params) and the raw response
   to `bakeoff/corpus/<hash>.json`.
2. Add a `--replay` mode that re-sends every corpus entry at **temp 0** and asserts a clean parse.
3. Wire `--replay` into whatever you run after a llama.cpp rebuild or a GGUF/template update.

This turns each observed bug into a permanent, deterministic, seconds-to-run regression test —
which is exactly what you want given llama.cpp's release cadence and the #24807→#24839→#24863→#24869
churn.

### 8.7 Server-side log correlation

Tail the llama-server log during runs and grep for:
- `common_chat_peg_parse: unparsed peg-native output:` → #24807/#24863 class
- `init: chat template, thinking =` → verify it matches intent (#20809)
- the detected chat format on startup → confirm `peg-native`, not a generic fallback
- deprecation warnings about `enable_thinking` → confirm the b8322 behaviour on your build

Attach counts to each run record. Server-side truth beats client-side inference.

### 8.8 Record these fields per run

Add to `stats`: `llamacpp_build`, `gguf_sha256` (you already have `models.manifest.yaml`),
`chat_format`, `thinking_flag`, `endpoint`, `stream`, all sampler values **as actually sent**,
`finish_reason` histogram, `reasoning_tokens`, and the failure-kind histogram. Without build + GGUF hash,
results are not comparable across weeks — and given the bug chain in §1.4, week-to-week comparability is
the entire point.

---

## 9. Concrete diffs to make now

**`docker/llama-swap-config.yaml`**
- Verify/pin llama-server image to build **≥ 9755**; add the build number to the header comment block
  alongside the existing dated notes.
- Split `qwen3.6-35b-a3b` into agentic (`--reasoning off --reasoning-format none`, temp 0.7/top_p 0.80)
  and thinking (`--reasoning on --reasoning-format deepseek --reasoning-budget 2048`, temp 0.6/top_p 0.95)
  entries. Same for `qwen3.6-27b`.
- Consider adding `--chat-template-file` overrides once §5.2 has been run.

**`docker/litellm-config.yaml`**
- Set `num_retries: 0` for the `coder`/`coder-strong` aliases (duplicate-side-effect risk on agentic calls).
- Add a comment recording *what* `drop_params: true` costs (llama.cpp-specific sampler/grammar params are
  silently discarded) so future-you doesn't debug a dropped `grammar` for an hour.
- Note the #19700 caveat: `drop_params` at `litellm_settings` level had a documented hierarchy bug through
  v1.81.1; confirm your version is past PR #21195.

**`opencode.json` / `clients/opencode.json`**
- Remove `"temperature": 0.1` from both agents (let the card values apply server-side).
- Add a second provider block pointing at llama-swap directly for `coder`/`coder-strong`.
- Scope `serena` and `context7` to the `plan` agent, or prune serena's tool list for `build`.

**`clients/pi-models.json`**
- Add the direct-to-llama-swap provider alongside the LiteLLM one. Keep
  `supportsDeveloperRole: false` / `supportsReasoningEffort: false`.

**`bakeoff/harness.py`**
- Default `BAKEOFF_BASE` → llama-swap directly; add `--via-litellm`.
- Remove the hardcoded `temperature: 0.1`; add `--temp/--top-p/--top-k/--min-p` passthrough.
- Add `jsonschema` validation of tool args; split `malformed_calls` into the §8.1 taxonomy.
- Add `--stream`, `--repeat N`, `--tools-pad N`, `--schema-pack adversarial`, `--replay`.
- Record `llamacpp_build`, `gguf_sha256`, `chat_format`, `finish_reason`.

---

## 10. Source index

**llama.cpp — docs**
- Server README (flags, `tool_choice`, `parallel_tool_calls`, grammar/json_schema/response_format): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Function calling doc (native models, `--jinja`, `--chat-template-file`, KV-quant warning): https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md
- LLGuidance integration: https://github.com/ggml-org/llama.cpp/blob/master/docs/llguidance.md
- Chat templates & message parsing architecture (autoparser, PEG, `jinja::caps`): https://deepwiki.com/ggml-org/llama.cpp/3.9-chat-templates-and-message-parsing
- Chat templates & tool calling (minja, PEG, JSON healing): https://deepwiki.com/qualcomm/llama.cpp/8.2-chat-templates-and-tool-calling

**llama.cpp — issues & PRs**
- #24807 duplicate `</parameter>`, Qwen3.6-35B-A3B, ~1/128, stream abort (build 9722): https://github.com/ggml-org/llama.cpp/issues/24807
- #24863 `Until()` GBNF/PEG boundary disagreement, root cause (build 9744): https://github.com/ggml-org/llama.cpp/issues/24863
- PR #24839 Aho-Corasick `until()` grammar, merged 2026-06-21 (partial fix): https://github.com/ggml-org/llama.cpp/pull/24839
- PR #24869 including-variant AC parser, "Fixes #24863", merged 2026-06-21, tested build 9755 `0ef6f06d5`: https://github.com/ggml-org/llama.cpp/pull/24869
- #20260 peg-native `root ::= tool-call` fails on prose-before-tool-call (thinking models): https://github.com/ggml-org/llama.cpp/issues/20260
- #20809 false thinking detection → tool calls in `reasoning_content`, `--reasoning off` workaround (b8429): https://github.com/ggml-org/llama.cpp/issues/20809
- #22072 malformed/incomplete JSON args on minimal schema, closed not-planned (build 8831): https://github.com/ggml-org/llama.cpp/issues/22072
- #21316 / #22786 Gemma 4 tool calls leaking into content: https://github.com/ggml-org/llama.cpp/issues/21316 , https://github.com/ggml-org/llama.cpp/issues/22786
- #11847 `json_schema` and `grammar` mutually exclusive: https://github.com/ggml-org/llama.cpp/issues/11847
- Discussion #23351 per-request reasoning toggle; `enable_thinking` deprecated ≥ b8322: https://github.com/ggml-org/llama.cpp/discussions/23351
- #20409 / #20182 / #13189 `enable_thinking=false` ignored: https://github.com/ggml-org/llama.cpp/issues/20409 , https://github.com/ggml-org/llama.cpp/issues/20182 , https://github.com/ggml-org/llama.cpp/issues/13189
- PR #22673 MTP support, merged 2026-05-16, tested Qwen3.6 27B + 35B-A3B: https://github.com/ggml-org/llama.cpp/pull/22673
- Weekly report July 7–14 2026 (HTTP 400 for malformed tool args; b9235 MTP regression): https://buttondown.com/weekly-project-news/archive/weekly-github-report-for-llamacpp-july-07-2026-6412/
- PR #24329 / b9656 peg-native hardening, `accept_openai_wrapper`, `func_args_not_string`: https://pseedr.com/stack/hardening-local-agentic-workflows-llamacpps-peg-native-tool-call-parsing-update

**Downstream GBNF footguns**
- rowboat #740 — PCRE shorthands (`\d`) fail GBNF compile, kill whole request: https://github.com/rowboatlabs/rowboat/issues/740
- lemonade #2691 — `maxLength ≥ ~2000` vs llama.cpp #17381 repetition cap: https://github.com/lemonade-sdk/lemonade/issues/2691
- netclaw troubleshooting (symptom→cause table, specdec artifacts): https://netclaw.dev/troubleshooting/llama-cpp/

**LiteLLM**
- opencode #20719 — loop aborts, `finish_reason: "stop"` not `"tool_calls"` (v1.82.6+), closed not-planned: https://github.com/anomalyco/opencode/issues/20719
- paperclip #2525 — same symptom: https://github.com/paperclipai/paperclip/issues/2525
- LiteLLM #17246 — streaming drops `tool_calls` on mixed text+tool (v1.80.7, PR #17652): https://github.com/BerriAI/litellm/issues/17246
- LiteLLM #19700 — `drop_params`/`additional_drop_params` hierarchy bug (v1.81.1, PR #21195): https://github.com/BerriAI/litellm/issues/19700
- LiteLLM #21147 — proxy misrouting `openai/*` model IDs: https://github.com/BerriAI/litellm/issues/21147
- drop_params docs: https://docs.litellm.ai/docs/completion/drop_params
- OpenAI-compatible provider docs: https://docs.litellm.ai/docs/providers/openai_compatible

**Models**
- Qwen3.6-35B-A3B card (sampler tables, `enable_thinking`, `preserve_thinking`, 262144 ctx / 1.01M YaRN): https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Qwen3.6-35B-A3B discussion #23 — sampler inconsistency, reconciled late May 2026: https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/23
- Unsloth Qwen3.6 run-locally (MTP flags, sampler, CUDA 13.2 warning, KV bf16 workaround): https://unsloth.ai/docs/models/qwen3.6
- Qwen3.5-35B-A3B "tool calling chat template is broken": https://huggingface.co/Qwen/Qwen3.5-35B-A3B/discussions/4
- Unsloth Qwen3-Coder-30B-A3B template + tool-calling fixes: https://huggingface.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/discussions/10
- Unsloth Qwen3.5-35B-A3B template update thread: https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF/discussions/18
- Corrected Qwen templates: https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates , https://huggingface.co/Moore2877/Qwen-Fixed-Chat-Templates-llamacpp

**Papers / benchmarks**
- JSONSchemaBench (engine comparison, coverage, TPOT, +4% quality, 50% speedup): https://arxiv.org/html/2501.10868v3
- "When Correct Isn't Usable" (small-model structured output; 0% naive; ALOLAB 84–87% vs constrained 15–52%; 3.6–8.2× overhead): https://arxiv.org/html/2605.02363v1
- TinyLLM: small LMs for agentic tasks on edge devices: https://arxiv.org/pdf/2511.22138
- BFCL v4 leaderboard (multi-turn collapse for small models): https://gorilla.cs.berkeley.edu/leaderboard.html , https://llm-stats.com/benchmarks/bfcl-v4

**Other servers**
- vLLM tool calling (`tool_choice: required` guarantees valid JSON; parser list incl. `qwen3_xml`; `VLLM_ENFORCE_STRICT_TOOL_CALLING`): https://docs.vllm.ai/en/latest/features/tool_calling.html
- SGLang structured outputs (xgrammar default, llguidance): https://docs.sglang.io/docs/advanced_features/structured_outputs
- llama-swap: https://github.com/mostlygeek/llama-swap
