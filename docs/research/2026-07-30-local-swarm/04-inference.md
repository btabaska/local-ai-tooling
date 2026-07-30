# 04 — Inference / Serving Layer: Maximizing Concurrent Agent Throughput on One RTX 3090 Ti

**Research date:** 2026-07-30
**Rig:** 1× RTX 3090 Ti (24 GB, GA102, **sm_86 — no native FP8/FP4 tensor cores**), i7-12700K, 64 GB DDR, NVMe, CachyOS/Arch, Docker + CDI.
**Current stack:** `llama-swap` (ghcr.io/mostlygeek/llama-swap:cuda) → one `llama-server` per model → LiteLLM front door.
**Goal:** many concurrent coding-agent turns, as fast as possible, on one card that must also yield to gaming + ComfyUI.

**Confidence legend:** 🟢 high (primary source: upstream docs / merged PR / manpage) · 🟡 medium (single credible secondary source, or primary source but indirect) · 🔴 low / unverified (SEO-blog numbers, plausible but unreproduced — treat as directional only)

---

## 0. Executive verdict (TL;DR)

1. **Stay on llama.cpp + llama-swap.** 🟡 The one thing that would justify vLLM/SGLang — 5–40× aggregate throughput at high concurrency — is measured on datacenter cards with FP16/FP8 weights that *do not fit* in 24 GB at the model sizes you actually want (27B/35B-class). At 24 GB you are forced into 4-bit, and llama.cpp's GGUF ecosystem is the only one with day-0 4-bit coverage of every model in your `llama-swap` config plus the mmproj/vision, MoE-CPU-offload, and MTP features you already depend on.
2. **But you must upgrade llama.cpp and change your flags.** Your current config is tuned for *one deep agent* (`--parallel 1`, MTP, max context). It is close to worst-case for a swarm. Three concrete changes matter more than anything else:
   - **Pin a build dated ≥ 2026-06-09** — before that, prompt-cache checkpoints were **slot-local**, so N agents sharing a system prompt got N cold prefills instead of 1. Fixed by [PR #24190](https://github.com/ggml-org/llama.cpp/pull/24190), merged 2026-06-09, closing [issue #22942](https://github.com/ggml-org/llama.cpp/issues/22942). 🟢
   - **Raise `--cache-ram`** from the 8192 MiB default into your spare 64 GB system RAM (e.g. `--cache-ram 24576`). 🟢
   - **Add a swarm profile** with `--parallel 6..8`, `--kv-unified`, and MTP **disabled** (MTP requires `--parallel 1` per your own bake-off notes, and spec-decode is counterproductive once the GPU is batch-saturated anyway).
3. **Prefix caching is the whole game.** The TraceLab trace of ~4,300 real Claude Code / Codex sessions (350k LLM steps, 430k tool calls) found **~96% of prompt tokens are served from prefix cache** in production coding-agent workloads ([arXiv:2606.30560](https://arxiv.org/abs/2606.30560), Jun 2026). 🟢 On a 24 GB card the difference between a working prefix cache and a broken one is roughly an order of magnitude in effective agent throughput — far bigger than any engine swap.
4. **Concurrency ceiling on this rig: ~6–8 usable agent slots**, and the binding constraint is **KV context, not compute.** `--ctx-size` in llama.cpp is the *total* KV budget shared across slots, so 8 agents on your measured 262144-token ceiling = 32k each. That's a fine agent context. On the 27B dense model (114688 ceiling) 8 slots = 14k each, which is not.
5. **Do add a small always-resident worker.** llama-swap's `matrix` DSL (which supersedes `groups`) can hold a ~4B worker (~3.5 GiB all-in) alongside a ~19 GiB coder. That buys you cheap tool-routing/summarization/tagging turns that never evict the coder.
6. **Consider vLLM only for one specific experiment:** a 30B-A3B-class MoE in **AWQ-INT4 + Marlin**, which is genuinely mature on Ampere and where one measured 3090 datapoint reports **168 tok/s single-stream at 32k ctx** ([ure.us, 2026-03-06](https://ure.us/articles/best-local-llm-agentic-coding/)) 🟡. If that model is your `coder`, vLLM's PagedAttention + automatic prefix caching will beat llama.cpp at ≥8 concurrency. Everything else in your zoo should stay on llama.cpp.

---

## 1. llama.cpp server, state of the art (2026-07)

### 1.1 Verified flag reference

All of the following are quoted verbatim from the current `llama-server(1)` manpage ([Debian testing](https://manpages.debian.org/testing/llama.cpp-tools/llama-server.1.en.html)) and cross-checked against [tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). 🟢

| Flag | Description (verbatim) | Default |
|---|---|---|
| `-np, --parallel N` | "number of server slots" | `-1` (auto) |
| `-cb, --cont-batching` | "whether to enable continuous batching (a.k.a dynamic batching)" | **enabled** |
| `-kvu, --kv-unified` | "use single unified KV buffer shared across all sequences" | "enabled if number of slots is auto" |
| `-no-kvu, --no-kv-unified` | hard-splits KV per slot | — |
| `--cache-prompt` / `--no-cache-prompt` | "whether to enable prompt caching" | **enabled** |
| `--cache-ram N` | "set the maximum cache size in MiB (-1 = no limit, 0 = disable)" | `8192` |
| `--cache-reuse N` | "min chunk size to attempt reusing from the cache via KV shifting, requires prompt caching to be enabled" | `0` (**off**) |
| `--cache-idle-slots` / `--no-cache-idle-slots` | "save and clear idle slots on new task (requires unified KV and cache-ram)" | **enabled** |
| `-ctxcp, --ctx-checkpoints N` | "max number of context checkpoints to create per slot" | `32` |
| `-cms, --checkpoint-min-step N` | "minimum spacing between context checkpoints in tokens (0 = no minimum)" | `256` |
| `-sps, --slot-prompt-similarity F` | "how much the prompt of a request must match the prompt of a slot in order to use that slot (0.0 = disabled)" | `0.10` |
| `--slot-save-path PATH` | "path to save slot kv cache" | disabled |
| `-c, --ctx-size N` | "size of the prompt context (0 = loaded from model)" | `0` |
| `-b, --batch-size N` | "logical maximum batch size" | `2048` |
| `-ub, --ubatch-size N` | "physical maximum batch size" | `512` |
| `-fa, --flash-attn [on\|off\|auto]` | flash attention | `auto` |
| `--swa-full` | "use full-size SWA cache" | `false` |
| `--context-shift` / `--no-context-shift` | "context shift on infinite text generation" | **disabled** |
| `-ncmoe, --n-cpu-moe N` | "keep the MoE weights of the first N layers in the CPU" | — |
| `-cmoe, --cpu-moe` | "keep all MoE weights in the CPU" | — |
| `-md, --spec-draft-model FNAME` | draft model for speculative decoding | unused |
| `--spec-type` | "comma-separated list of types of speculative decoding" (incl. `draft-mtp`) | `none` |
| `--spec-draft-n-max N` | "number of tokens to draft" | `3` |
| `-bs, --backend-sampling` | "enable backend sampling (experimental)" | disabled |
| `--jinja` / `--no-jinja` | jinja chat template engine | **enabled** |
| `--chat-template-kwargs STRING` | extra json template params | — |
| `--reasoning-format FORMAT` | thought-tag handling/extraction | — |
| `--props` | "enable changing global properties via POST /props" | disabled |
| `--slots` / `--no-slots` | slots monitoring endpoint | **enabled** |

> **Note on your existing config:** `--jinja` is now the *default*, and `--no-context-shift` is also the default. Both are harmless no-ops in your `${srv}` macro. `--flash-attn on` is worth keeping explicit (defends against `auto` picking `off` on a driver quirk).

### 1.2 How `--ctx-size` divides among slots — the number that governs your ceiling

This is the single most misunderstood thing in llama.cpp and it directly sets your concurrency ceiling.

`--ctx-size` is the **total** KV cache, not per-slot. From ggerganov in [discussion #4130](https://github.com/ggml-org/llama.cpp/discussions/4130): 🟢

> "The `--ctx-size` argument actually specifies the total size of the KV cache… if we specify `--ctx-size 8192` this means that we can process: 2 sequences… 4 sequences… 32 sequences, each of max length of 256 tokens"

The `--kv-unified` / `--no-kv-unified` distinction:

- **`--kv-unified` (default when `-np` is auto):** one shared buffer, all sequences attend only to their own tokens via masking. Heterogeneous request lengths are fine as long as the *sum* fits. 🟢
- **`--no-kv-unified`:** hard per-slot allocation of `ctx_size / n_parallel`. In [discussion #22658](https://github.com/ggml-org/llama.cpp/discussions/22658) ggerganov recommends exactly this when you want a guaranteed per-request ceiling: *"For this use case you don't need a unified KV cache. These args should work exactly as you want: `llama serve ... -np 4 --no-kv-unified -c 524288`"* 🟢

⚠️ **Caveat:** [issue #17450](https://github.com/ggml-org/llama.cpp/issues/17450) reports `kv_unified = true` being set even when not requested. Always verify in the startup log (`n_ctx_slot`) rather than assuming. 🟡

**Practical consequence for a swarm:** prefer `--kv-unified` (shared pool). A swarm has bursty, heterogeneous agents — one planner with 80k context and five workers with 8k each. A hard split wastes the planner's headroom on idle workers. Use `--no-kv-unified` only if you need hard isolation to prevent one runaway agent from starving the others.

### 1.3 Context-per-agent table for YOUR measured ceilings

Your `llama-swap-config.yaml` records measured max `--ctx-size` that fully fits on GPU (q8_0 KV, flash-attn, ~1 GiB desktop headroom). Dividing those:

| Model (your alias) | Measured total ctx | np=1 | np=2 | np=4 | np=6 | np=8 |
|---|---|---|---|---|---|---|
| `qwen3.6-35b-a3b` (MoE) | 262144 | 262k | 131k | **65k** | 43k | **32k** |
| `qwen3.6-27b` (dense, MTP) | 114688 | 114k | 57k | 28k | 19k | 14k ❌ |
| `gemma4-31b-qat` | 73728 | 73k | 36k | 18k | 12k | 9k ❌ |
| `qwen2.5-coder-7b` | 32768 | 32k | 16k | 8k | 5k | 4k ❌ |

🟢 (arithmetic on your own measured numbers)

**Verdict:** only the **35B-A3B MoE** has enough KV budget to host a real swarm. It gives 8 agents 32k each or 4 agents 65k each. This is the strongest single argument for making `coder` = the MoE (which your bake-off already concluded on quality/speed grounds anyway). The 27B dense should stay a `--parallel 1` deep-agent model.

### 1.4 The slot-local prompt cache bug — **check your image date**

This is the most important finding in this section.

[Issue #22942](https://github.com/ggml-org/llama.cpp/issues/22942), opened 2026-05-11, closed 2026-06-09: 🟢

> "Under `-np > 1`, the llama-server's prompt-cache checkpoints operate on a per-slot basis, with the slot-selection logic only consulting individual slot checkpoints. When a second request with a matching prefix routes to a different slot than the one holding the checkpoint, it undergoes a full prefill rather than leveraging the existing checkpoint elsewhere on the server."
>
> "This limitation becomes apparent in concurrent workloads—such as agent systems, RAG applications, or chat scenarios—where multiple clients share identical system prompts and prefixes but are assigned to different slots due to availability constraints."

The reporter's repro showed **~15 s cold prefill on a 3K-token prompt** that should have been **<1 s** from an existing checkpoint on another slot. Fixed by [PR #24190](https://github.com/ggml-org/llama.cpp/pull/24190) (merged by ggerganov, 2026-06-09, commit `961e9a3`), which lets idle slots export their VRAM cache to the RAM prompt cache so a later request on a *different* slot can restore it. It introduced no new flags but extends the behavior of the existing `--cache-idle-slots`.

> **Action:** `docker pull ghcr.io/mostlygeek/llama-swap:cuda` and confirm the bundled `llama-server` build post-dates 2026-06-09 (`/app/llama-server --version`). If it doesn't, your entire swarm plan is silently defeated. 🟢

### 1.5 Prompt cache / checkpoint tuning for agents

| Flag | Default | Swarm recommendation | Why |
|---|---|---|---|
| `--cache-ram` | 8192 MiB | **`24576`** (or `-1`) | Checkpoints live in **system RAM**, and you have 64 GB. 8 GiB is far too small to hold N agents' × 32k-token checkpoints. 🟢 |
| `--ctx-checkpoints` | 32 | `64`–`128` | More restore points per slot → cheaper recovery after tool-call divergence. The Claude-Code-on-llama.cpp writeup recommends `--ctx-checkpoints 128`. 🟡 ([mykolaaleksandrov.dev, Jun 2026](https://www.mykolaaleksandrov.dev/posts/2026/06/claude-code-llamacpp-prompt-cache-fix/)) |
| `--checkpoint-min-step` | 256 | `128`–`256` | Tighter spacing = finer-grained restore, more RAM. |
| `--cache-reuse` | **0 (off!)** | `256` | Enables KV-shifting reuse of *non-prefix* chunks — the case where an agent's history has a middle segment change (compaction, tool result rewrite). Off by default; this is free throughput. 🟢 |
| `--slot-prompt-similarity` | 0.10 | leave, or raise to `0.5` | Governs slot affinity. Low value = aggressive slot reuse. Post-#24190 the global RAM cache matters more than slot affinity. 🟡 |
| `--cache-idle-slots` | enabled | **keep enabled** | This is the mechanism that #24190 fixed. Requires unified KV + cache-ram. 🟢 |
| `--slot-save-path` | disabled | optional | Manual `POST /slots/{id}?action=save|restore|erase` to disk. Useful to **persist the swarm's shared prefix across your gaming/ComfyUI force-unload** — see §6.4. 🟢 |

**Disk-based checkpoint offload does NOT exist yet.** [Issue #20697](https://github.com/ggml-org/llama.cpp/issues/20697) (`--cache-disk` / `--cache-disk-max`) is **open** as of this research, with an open PR #24028. Checkpoints are RAM-only. 🟢 The manual `--slot-save-path` API is the only disk path today.

### 1.6 Agent-stability gotcha: unstable prompt prefixes

A prefix cache only works if the prefix is byte-identical. The documented failure mode for Claude Code was an attribution header block injected at the top of the system prompt, producing `"forcing full prompt re-processing due to lack of cache data"` on every single turn; the fix was `CLAUDE_CODE_ATTRIBUTION_HEADER=0`. 🟡 ([source](https://www.mykolaaleksandrov.dev/posts/2026/06/claude-code-llamacpp-prompt-cache-fix/))

**Generalize this to your stack.** Audit every client (opencode, pi, ops-agent) for:
- timestamps / dates in the system prompt
- session UUIDs, request IDs, git SHAs near the top
- randomly-ordered tool schemas (some SDKs iterate a dict)
- LiteLLM injecting headers/metadata into the body

Anything non-deterministic in the first N tokens costs you the entire cache. This is cheap to fix and worth more than any flag. 🟢 (reasoning; the specific Claude Code instance is 🟡)

Related: [issue #24055](https://github.com/ggml-org/llama.cpp/issues/24055) — context checkpoints are **always invalidated on hybrid/recurrent models**. If Qwen3.6-35B-A3B is a hybrid-attention architecture (its 262k ctx at 24 GB strongly suggests linear/hybrid attention layers), **verify checkpoints actually work on it** before committing to it as the swarm model. 🟡 — **this is the biggest open risk in this report.**

### 1.7 Speculative decoding / MTP vs. batching — they fight

Your config notes MTP gives 34.5 → 50 tok/s (1.46×) on the 27B **but requires `--parallel 1`**. This is the general shape of the tradeoff:

- Speculative decoding trades *extra compute* for *fewer sequential steps*. It wins when the GPU is idle between decode steps (batch=1, memory-bandwidth-bound).
- Under continuous batching at np≥4 the GPU is already compute-saturated, so drafting steals FLOPs from real tokens and **aggregate throughput drops**. 🟡 (well-established principle; not measured on this rig)

**Recommendation:** two distinct `llama-swap` model entries for the same weights — a `-deep` entry with MTP + `--parallel 1` + max context, and a `-swarm` entry with no spec decode + `--parallel 6..8`. See §6.

### 1.8 Throughput scaling with concurrency — measured numbers

| Source | Hardware | Model | Finding | Conf. |
|---|---|---|---|---|
| [llama.cpp discussion #18308](https://github.com/ggml-org/llama.cpp/discussions/18308) | RTX 5090 | 20B | `np=1`: **~295 tok/s** → `np=32`: **~1,430 tok/s** (**4.8×**). GPU util 90–96% under `llama-batched-bench` but only **~60% via llama-server** — the gap is CPU-side sampling overhead. | 🟢 |
| same | RTX 5090 | 20B | "diminishing returns beyond `-np 4`… no significant speedup at `-np 16`" *in the server path* | 🟢 |
| same | — | — | ggerganov: enable **`--backend-sampling`** (experimental) for sustained high parallelization | 🟢 |
| same | — | — | **Avoid `--swa-full`**: "will increase the used VRAM for the KV cache significantly for almost no benefits" | 🟢 |
| [A40 parallelism benchmark](https://medium.com/@ferraricorneloup.teo/how-many-developers-can-one-gpu-serve-benchmarking-llama-cpp-parallelism-on-a40-gpus-0ea2a8c36045) | A40 48 GB | DeepSeek-Coder-V2-Lite Q4_K_M, ctx 2048 | 8 slots → **11.2 req/s aggregate**, p95 **662 ms**; ≈1.4 req/s per slot. Conclusion: "a single A40 can comfortably support around twenty active developers" | 🟡 |
| [Red Hat, 2026-06-15](https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine) | H200 | Llama 3.1 8B | At 1 concurrent request llama.cpp ≈ vLLM. At **64 simultaneous users vLLM generated ~44× more tokens/s than llama.cpp** | 🟢 |

**Reading the tea leaves for a 3090 Ti:** the 5090 result says llama-server's *practical* knee is around `-np 4`, with the CPU sampler as the limiter, not the GPU. Your i7-12700K has 8 P-cores + 4 E-cores, and you already dedicate 10 threads to the CPU embedder. **Expect the sampler bottleneck to bite you earlier than it bit the 5090 user.** The `--backend-sampling` flag moves sampling to the GPU and is the specific lever for this. 🟡

The Red Hat 44× figure is the honest headline for "why not vLLM" — but note it's FP16 Llama-8B on an H200 with 141 GB. That workload has 10× the KV budget of your rig. **At 24 GB you cannot reach the concurrency levels where that gap opens.** Your ceiling is 6–8 agents, and at 8 the gap is much narrower than 44×.

### 1.9 Batch sizing

`--batch-size 2048` / `--ubatch-size 512` are the current defaults. For prefill-heavy agent workloads (long contexts, short outputs — exactly what TraceLab measured), larger batches help prefill throughput. One dual-3090 report claims `--batch-size 8192 --ubatch-size 4096` improved **average prefill throughput by 77%** with burst rates to 1,638 tok/s 🔴 ([sanj.dev](https://sanj.dev/post/qwen-3-6-27b-dual-rtx-3090-llama-cpp-tuning/) — content-farm-adjacent, unreproduced). Larger ubatch costs VRAM for compute buffers, which you have <1 GiB of. **Test `-b 4096 -ub 1024` and re-measure your ctx ceiling; do not raise blindly.**

---

## 2. Engine comparison for a single 24 GB Ampere card, 2026

### 2.1 Current versions (verified 2026-07-30)

| Engine | Latest | Date | Source |
|---|---|---|---|
| llama.cpp | rolling `master` | daily | — |
| llama-swap | **v244** | 2026-07-28 | [GH releases API](https://api.github.com/repos/mostlygeek/llama-swap/releases/latest) 🟢 |
| vLLM | **v0.26.0** | 2026-07-27 | [GH releases API](https://api.github.com/repos/vllm-project/vllm/releases/latest) 🟢 |
| SGLang | v0.5.15 (NGC container rel. 26.06) | Jul 2026 | [NVIDIA SGLang release notes 26.06](https://docs.nvidia.com/deeplearning/frameworks/sglang-release-notes/rel-26-06.html) 🟡 |
| LiteLLM | v1.83.14 / v1.84.0 | Jul 2026 | [LiteLLM release notes](https://docs.litellm.ai/release_notes/) 🟢 |
| ExLlamaV3 / TabbyAPI | rolling | tool-calling + reasoning landed 2026-04-12 (commit `32eed618`) | 🟡 |

### 2.2 Feature matrix

| Capability | llama.cpp | vLLM 0.26 | SGLang | ExLlamaV3/TabbyAPI | TensorRT-LLM |
|---|---|---|---|---|---|
| **Fits 24 GB at 27–35B?** | ✅ GGUF Q4/IQ4 | ✅ AWQ-INT4 / GPTQ-INT4 | ✅ AWQ-INT4 | ✅ EXL3 (SOTA at low bpw) | ⚠️ possible, painful |
| **GGUF** | native | supported but "not recommended for GPU-first production" 🟡 | limited | ❌ | ❌ |
| **Ampere sm_86 kernels** | ✅ full | ✅ AWQ+**Marlin** mature | ✅ (Triton fused-MoE needs manual tuning for sm_86) 🟡 | ✅ (Ampere is its target) | ⚠️ engine build per-GPU |
| **FP8 weights** | n/a | ✅ via FP8-Marlin **dequant-to-FP16 → compute tax** 🟢 | ⚠️ MoE FP8 W8A8 on Ampere is an [open feature request](https://github.com/sgl-project/sglang/issues/12887) 🟢 | n/a | ❌ needs Ada/Hopper |
| **Prefix caching** | prompt cache + ctx checkpoints (RAM) | ✅ automatic prefix caching (`--enable-prefix-caching`) | ✅ **RadixAttention** (radix tree, LRU/LFU/priority eviction) | prompt caching, less documented | ✅ |
| **Continuous batching** | ✅ (`-cb`, default on) | ✅ PagedAttention + chunked prefill (default on) | ✅ best-in-class | ✅ PagedAttention + ragged batching 🟡 | ✅ |
| **Tool-call parsing** | ✅ `--jinja` + minja + **PEG autoparser** + JSON healing | ✅ `--enable-auto-tool-choice --tool-call-parser <hermes\|qwen3\|...>` | ✅ `--tool-call-parser` | ✅ since 2026-04 🟡 | ⚠️ DIY |
| **Reasoning parser** | `--reasoning-format` | `--reasoning-parser` | `--reasoning-parser` | ✅ | ⚠️ |
| **Structured decoding** | GBNF + **llguidance** (JSON Schema + Lark CFG) | **xgrammar** (default), guidance, outlines, lm-format-enforcer | xgrammar / outlines | ✅ | ✅ |
| **Sleep / hot-swap** | process restart (seconds from NVMe) | ✅ **sleep mode L1/L2**, 18–200× faster than reload | ❌ | process restart | ❌ |
| **Startup time** | seconds (mmap) | tens of seconds (profiling + CUDA graph capture); `--enforce-eager` or cached `--kv-cache-memory` speeds it up | similar to vLLM | seconds–tens | **minutes** (engine build) |
| **Memory overhead** | small; ~1 GiB desktop headroom is your real constraint | CUDA ctx ~300–800 MiB/GPU 🟡 + CUDA graphs | similar | small | large |
| **Vision / mmproj** | ✅ (you use it for the Mistral trio) | partial per-model | partial | partial | ⚠️ |
| **MoE CPU offload** | ✅ `-ncmoe` / `-cmoe` | ⚠️ limited | ⚠️ limited | ❌ | ❌ |
| **Ops complexity for your zoo (9 models)** | 🟢 trivial (one YAML) | 🟡 one process per model, slow to swap | 🔴 heavier | 🟡 | 🔴 |

### 2.3 Per-engine verdicts

**llama.cpp — KEEP as primary. 🟢**
Only engine that covers your entire model zoo (GGUF quants of Qwen3.6, Gemma 4 QAT, DECKARD, three Mistral-24B RP tunes with a shared mmproj, an embedder, MTP spec-decode). Its concurrency story is real but the practical knee is ~`-np 4`, and above that the CPU sampler bites. Its prefix cache is now *architecturally correct* across slots (post-#24190) but RAM-only and with a hybrid-model caveat.

**vLLM 0.26 — WORTH ONE EXPERIMENT for the `coder` slot only. 🟡**
Ampere is genuinely well-supported: **AWQ-INT4 + Marlin is the mature 4-bit path on sm_86** — smaller files, more VRAM for KV, higher throughput, negligible quality loss. **Avoid FP8 on this card**: FP8-Marlin dequantizes to FP16 on the fly, a pure compute tax; one report measured FP8 **13% slower than AWQ-4bit** on the same MoE 🟡. Automatic prefix caching + PagedAttention is a strictly better KV story than llama.cpp for many-agent workloads. Costs: slow startup, one process per model (bad for a 9-model zoo), no vision/mmproj parity, and AWQ quants of every model you want may not exist.

*The one measured 3090 datapoint worth chasing:* [ure.us (2026-03-06)](https://ure.us/articles/best-local-llm-agentic-coding/) 🟡 — vLLM 0.17.0rc1 + Marlin, single RTX 3090:
- **Qwen3-Coder-30B-A3B-Instruct AWQ-4bit (MoE): 168.4 tok/s, 32K max ctx, 16.9 GB weights, ~7 GB KV**
- Qwen2.5-Coder-32B-Instruct AWQ-4bit (dense): 41.0 tok/s, 8K max ctx, 19.5 GB weights
- "MoE delivers 4.1× throughput"

Note the ceiling: **32K total context** on a single 3090 with vLLM. Under `--max-num-seqs 8` with prefix caching that's fine *only because* the shared prefix is stored once — which is exactly vLLM's advantage. But it's much less headroom than llama.cpp's 262144 on your MoE, and that difference is likely architectural (Q4_K/IQ4 GGUF + q8_0 KV is more VRAM-efficient than AWQ + FP16 KV).

**SGLang — SKIP on this rig. 🟡**
Best-in-class prefix caching (RadixAttention with configurable LRU/LFU/FIFO/priority eviction and refcount-protected nodes). Measured advantages are real: 29% throughput and 23% lower TTFT vs vLLM on H100 (16,215 vs 12,553 tok/s; 79 ms vs 103 ms mean TTFT), 37%/41% lower p50/p95 TTFT at 50 concurrent shared-prefix requests, up to 6.4× on prefix-heavy RAG 🟡 ([spheron](https://www.spheron.network/blog/vllm-vs-sglang-2026/), [particula](https://particula.tech/blog/sglang-vs-sglang-inference-engine-comparison)). **But**: those are datacenter numbers; sm_86 fused-MoE Triton configs need manual tuning; Ampere MoE FP8 is an open request; and SGLang's Python router has a documented GIL bottleneck (~127% CPU cap) under high concurrency 🟡 ([sglang#21061](https://github.com/sgl-project/sglang/issues/21061)). Operational cost is not justified for 6–8 agents on one card.

**ExLlamaV3 / TabbyAPI — INTERESTING DARK HORSE. 🟡**
EXL3 (QTIP/trellis-coded) is state-of-the-art quantization quality per bit — the strongest argument for squeezing a bigger/better model into 24 GB. TabbyAPI now supports PagedAttention, true continuous batching, ragged concurrent requests, cache quantization 2–8 bits, tool calling and reasoning (since 2026-04-12). It's explicitly consumer-GPU-targeted. **Blockers for you:** EXL3 quant availability lags GGUF badly for brand-new models, no mmproj/vision parity for your Mistral trio, and I found **no reproducible 3090 concurrency benchmarks** — the best source is paywalled ([kaitchup](https://kaitchup.substack.com/p/serving-exllamav3-with-tabbyapi-accuracy)). Worth a weekend, not a migration.

**TensorRT-LLM — SKIP. 🟢**
Per-GPU engine builds taking minutes, no GGUF, no practical model-swap story, and its headline features (FP8/FP4) require Ada/Hopper/Blackwell. On sm_86 you get complexity without the payoff.

---

## 3. Prefix caching — the biggest lever, in detail

### 3.1 Why it dominates

[TraceLab (arXiv:2606.30560, Jun 2026)](https://arxiv.org/abs/2606.30560) 🟢 — ~4,300 coding-agent sessions, ~350,000 LLM steps, ~430,000 tool calls, from real Claude Code and Codex usage:

> "coding-agent workloads feature long autonomous loops, long contexts with short outputs, diverse and heavily-tailed tool calls, and high but imperfect prefix cache hit rates"

Reported hit rates: **~96% of prompt tokens served from prefix cache** for both Claude and Codex; per-step breakdowns of **95.8% (Claude) / 95.7% (Codex)**, with **97.9% for tool-result continuations** and **86.9% for user-initiated steps** 🟡. Misses are dominated by **human-paced idle gaps that exceed cache eviction time** — i.e. the cache dies while you're reading the diff.

**Three implications for your rig, in priority order:**
1. **Cache capacity beats cache cleverness.** Misses come from eviction, not from bad matching. `--cache-ram 24576` (using your 64 GB) directly attacks the dominant miss cause. 🟢
2. **Your GPU arbiter is a cache assassin.** Every ComfyUI/gaming force-unload kills the entire prompt cache, and a swarm restart then pays N cold prefills of a shared 20k-token prefix. See §6.4 for the mitigation.
3. **Prefix stability is a client-side problem** (§1.6) that no server flag can fix.

### 3.2 Per-engine mechanism

| Engine | Mechanism | Enable | Scope | Storage | Notes |
|---|---|---|---|---|---|
| **llama.cpp** | prompt cache + per-slot context checkpoints, exported to a server-global RAM cache | on by default; tune `--cache-ram`, `--ctx-checkpoints`, `--checkpoint-min-step`, `--cache-reuse` | **cross-slot only on builds ≥ 2026-06-09** (PR #24190) | **RAM only** (no `--cache-disk` yet, [#20697 open](https://github.com/ggml-org/llama.cpp/issues/20697)) | ⚠️ checkpoints "always invalidated on hybrid/recurrent models" ([#24055](https://github.com/ggml-org/llama.cpp/issues/24055)) |
| **vLLM** | automatic prefix caching over PagedAttention blocks | `--enable-prefix-caching` | global, block-level | GPU; CPU/NVMe tiers via **LMCache** | block-granular = better sharing than checkpoint-granular |
| **SGLang** | **RadixAttention** radix tree | on by default (`--disable-radix-cache` to turn off) | global | GPU + **HiCache** CPU/disk tiers | `--radix-eviction-policy [lru\|lfu\|fifo\|mru\|filo\|priority]`, `--page-size` |
| **TabbyAPI/EXL3** | prompt caching + paged KV | on | global 🟡 | GPU | less documented |

### 3.3 Expected TTFT savings

- llama.cpp cross-slot restore: the #22942 repro cites **~15 s → <1 s** on a 3 K-token prompt. 🟢 Scale that: your agents will share a 15–30 K-token prefix (system prompt + AGENTS.md + repo map). At a conservative 800–1500 tok/s prefill on a 3090 Ti for a 4-bit 30B-class MoE, a 20 K prefix is **13–25 s of cold prefill**. With 8 agents that's **~2–3 minutes of pure wasted prefill per swarm launch** without a working cache, versus roughly one prefill total with it. 🟡 (arithmetic on plausible prefill rates — **measure yours** with `/slots` and the `prompt eval time` log line)
- SGLang measured: 2 K-token session, second turn **~120 ms → ~15 ms prefill** (8×) 🟡; 37% lower p50 TTFT / 41% lower p95 at 50 concurrent shared-prefix requests 🟡.

### 3.4 LiteLLM's caching layer — **do NOT enable response caching for agents** 🟢

LiteLLM's cache is a **response cache** (exact/semantic match on the request → replay a stored completion), backed by Redis or Qdrant, with a DualCache L1-in-memory / L2-Redis tiering ([docs](https://docs.litellm.ai/docs/proxy/caching), [DeepWiki](https://deepwiki.com/BerriAI/litellm/5.2-redis-integration-and-semantic-caching)).

This is **orthogonal to, and actively harmful for, agent swarms**:

- ❌ **Response caching**: two agents in a swarm that hit the same state would receive *identical* completions, collapsing the diversity that makes a swarm useful — and a stale cached tool-call would be replayed against a changed filesystem. **Leave off.**
- ❌ **Semantic caching**: strictly worse — approximate matching on coding prompts is a correctness hazard.
- ❌ `cache_control_injection_points` / auto-inject prompt caching checkpoints: this is for **Anthropic/Bedrock `cache_control` blocks**. llama.cpp does prefix caching implicitly by token match and ignores these. No effect, but it may mutate your request body and thereby **break prefix stability** (§1.6). Leave off.
- ⚠️ **New in v1.83.14: server-side "prompt compression"** that "transparently compresses long-context inputs before they hit the upstream model with no client opt-in required" 🟡. If this is on by default in `main-latest`, it would rewrite your prompts and **destroy prefix cache hits**. **Explicitly verify it is disabled.** This is a concrete action item.

**Rule: LiteLLM should be byte-transparent on the request path.** All caching value comes from llama.cpp's KV cache, not from the gateway.

---

## 4. Model swapping / multiplexing in 2026

### 4.1 llama-swap v244 (2026-07-28) — what's new since your config was written

Your config uses the **legacy `groups`** syntax. The docs now state: *"A config must use either a matrix or legacy groups, not both."* 🟡 ([configuration.md](https://github.com/mostlygeek/llama-swap/blob/main/docs/configuration.md))

Newer capabilities worth adopting:

| Feature | YAML key | Default | Use for your swarm |
|---|---|---|---|
| **Matrix DSL** | `matrix: {vars, evict_costs, sets}` | — | Declare which model *combinations* may be co-resident with a boolean expression; solver "finds the cheapest way to make it available by evicting as few (and least costly) running models as possible". **This is how you keep coder + 4B worker resident.** |
| **Selectors** | `selectors: {strategy: warm\|pin\|spillover}` | `spillover: 4` | `warm` → "best currently loaded coding model" (no swap stall). `spillover: N` → after N in-flight requests, overflow to a second target. **`warm` is excellent for a swarm behind an arbiter.** |
| **Profiles** | `profiles: {pins: {...}}` + `GET/PUT /api/profiles/active` | — | Flip the whole stack between "deep" and "swarm" mode with one API call. **Perfect fit for your two-profile plan (§6).** |
| **Per-model concurrency** | `concurrencyLimit` | `0` (default cap ~10) | Cap requests reaching upstream; excess gets **HTTP 429**. Set to match `--parallel`. |
| **Filters** | `filters: {stripParams, setParams, setParamsByID}` | — | Strip client-sent `temperature`/`top_p` to keep prompts+params deterministic. |
| **Hooks** | `hooks: {on_startup: {preload: [...]}}` | — | **Pre-warm the coder after a gaming session** so the first agent doesn't eat the cold load. |
| **Global TTL** | `globalTTL` | `0` (never) | — |
| **Graceful unload** | `unloadTimeout` | `10` s | Raise for a swarm so in-flight agent turns drain before the arbiter kills the model. |
| **Peer instances** | fully-qualified peer model names (v242) | — | Not useful — you have one rig. |
| **vLLM wrapper** | `vllm-wrapper` (v243) | — | "helps vLLM users avoid long load times by communicating with an already running vLLM" — **this is the clean way to trial vLLM without losing llama-swap.** 🟢 |
| **Metrics** | activity metrics persisted to sqlite (v236); vLLM metrics + usage (v237–240); `status` field on `/v1/models` | — | Free observability. |

Concurrency internals: llama-swap uses a **semaphore per Process** (default limit 10) with excess requests parked in the Go runtime; a global `InflightCounter`; and graceful shutdown that waits for in-flight requests 🟡 ([DeepWiki](https://deepwiki.com/mostlygeek/llama-swap/9.1-concurrency-and-request-limits)). **Important:** llama-swap does *not* do the batching — it just proxies. The real concurrency comes from `llama-server --parallel`. Make sure `concurrencyLimit` ≥ `--parallel` or llama-swap becomes the bottleneck and returns 429s.

### 4.2 Alternatives

| Tool | Verdict for this rig | Notes |
|---|---|---|
| **llama-swap v244** | ✅ **keep** | Best fit: multi-backend, matrix/selectors/profiles, unload API for your arbiter, sqlite metrics. |
| **vLLM sleep mode** | 🟡 useful *within* vLLM | `--enable-sleep-mode` + `VLLM_SERVER_DEV_MODE=1`, then `POST /sleep?level=1|2`, `POST /wake_up[?tags=weights\|kv_cache]`, `GET /is_sleeping`. **L1** offloads weights to CPU RAM + discards KV; **L2** discards both. Claimed **18–200× faster than full reload** 🟡 ([docs](https://docs.vllm.ai/en/latest/features/sleep_mode/), [blog](https://vllm.ai/blog/2025-10-26-sleep-mode)). **This is the ideal ComfyUI/gaming yield primitive** — sleep L1 frees VRAM in ~a second and wakes from RAM, vs. llama.cpp's full NVMe reload. Note L1 needs ~17 GB of your 64 GB RAM to hold the weights. Not exposed in production mode without the dev flag. |
| **LMCache** | 🟡 the CPU-RAM lever, vLLM-only | KV offload to CPU/NVMe tiers. Claimed **3–10× latency reductions**; at QPS=1, **1.9–8.1× smaller TTFT** 🟡 ([arXiv:2510.09665](https://arxiv.org/pdf/2510.09665), [vLLM production-stack tutorial](https://github.com/vllm-project/production-stack/blob/main/tutorials/05-offload-kv-cache.md)). **No llama.cpp equivalent.** If you go vLLM for `coder`, LMCache is how you buy back the 32K→bigger context. |
| **Ollama** | ❌ downgrade | `OLLAMA_NUM_PARALLEL` (default 4 or 1) + `OLLAMA_MAX_LOADED_MODELS` do give parallel + multi-model, but you lose per-model flags, MTP, mmproj sharing, and llama-swap's arbiter API. Your repo already demoted it to a compat shim — correct call. |
| **LocalAI** | ❌ | reported ~15–20% slower inference than Ollama 🔴; no advantage. |
| **RamaLama** | ❌ for you | Container-first llama.cpp wrapper (Red Hat). "Boring and predictable" is its pitch; you already have Docker + CDI + llama-swap. |
| **Nexa** | ❌ | No credible 2026 evidence found for single-GPU swarm serving. **Unverified.** |
| **KTransformers** | 🟡 niche | CPU-GPU heterogeneous MoE inference — its whole thesis is big-MoE-on-small-VRAM via expert offload to DDR. Relevant *only* if you want a model that genuinely doesn't fit 24 GB. For single-stream. Not a batching engine. |

### 4.3 VRAM math: can you keep a big coder + a small worker resident?

Budget: 24 GB card. Reserve **~1.0 GiB desktop/compositor** (your existing measured norm) + **~0.4 GiB CUDA context per llama-server process**. Two processes = ~0.8 GiB of context. **Usable: ~22.2 GiB.**

llama.cpp KV per token (non-hybrid attention):
```
bytes/token = 2 × n_layer × n_kv_head × head_dim × bytes_per_elem
  q8_0 ≈ 1.0625 B/elem   f16 = 2 B/elem   q4_0 ≈ 0.5625 B/elem
```
Worked example — a 48-layer GQA model with 4 KV heads × 128 head_dim at q8_0:
`2 × 48 × 512 × 1.0625 ≈ 52.2 KB/token` → **32 K tokens ≈ 1.6 GiB**, **262 K ≈ 13 GiB**.
*(Your 35B-A3B fitting 262144 tokens inside a 23.3 GiB total strongly implies a hybrid/linear-attention architecture with far fewer full-attention layers. **Do not trust generic KV formulas for it — use your measured ceilings.** 🟡)*

| Configuration | Weights | KV + compute | Total | Verdict |
|---|---|---|---|---|
| `qwen3.6-35b-a3b` alone @ 262144 | ~23.0 GiB (your note) | edge fit | 23.3 GiB | ✅ measured, ~0 room for a co-resident model |
| `qwen3.6-35b-a3b` @ 65536 (np=4) + 4B worker | 23.0 + 2.5 | — | **>24 GiB** | ❌ **won't fit** |
| **17 GiB-class coder (Q4_K_M 31B / Q5_K_M 24B) + 4B Q4_K_M worker @ 16k** | 17.0 + 2.5 = 19.5 | coder ~1.8 GiB (np=6 sharing ~40k) + worker ~0.3 GiB | **~22.1 GiB** | ✅ **fits, ~1 GiB spare** |
| 17 GiB coder + 4B worker, coder @ 65k | 19.5 | ~3.2 GiB | ~23.5 GiB | ⚠️ too tight with desktop |
| 30B-A3B AWQ on vLLM (single process) | 16.9 GB | ~7 GB KV | ~24 GB | ✅ measured 🟡, no room for a second model |

**Conclusions:**
- ❌ Your current `qwen3.6-35b-a3b` at 23 GiB of weights **cannot** co-reside with anything. It is a solo tenant.
- ✅ A **~17 GiB coder + ~2.5 GiB 4B worker** co-residency is real, at the cost of dropping the coder's context to ~40 K total (≈6–7 K per agent at np=6, or 10 K at np=4). That's tight for coding agents.
- 🟡 **Recommended compromise:** keep the coder solo at high context, and run the 4B worker **on CPU** like you already do for `qwen3-embed` (`CUDA_VISIBLE_DEVICES=""`, `-ngl 0 --threads N`). A 4B Q4 on a 12700K will do ~15–25 tok/s 🔴 — plenty for tagging/routing/summarizing, and it costs **zero VRAM** and never contends with the GPU or the arbiter. Your embedder proves this pattern works. **This is the highest-value, lowest-risk option.**
  - ⚠️ Reuse your hard-won lesson: `-ngl 0` alone still allocated ~2.8 GiB of CUDA batch buffers. **`CUDA_VISIBLE_DEVICES=""` is mandatory.** 🟢 (your own measurement)

---

## 5. LiteLLM gateway — what to enable for a swarm

Current: v1.83.14 / v1.84.0 (Jul 2026). You're on `main-latest`, which floats — **pin a tag** so a "prompt compression" default doesn't silently break your prefix cache.

| Feature | Enable? | Why / config |
|---|---|---|
| Virtual keys + per-key budgets | ✅ | Give each agent role its own key → per-role spend/latency attribution in the swarm. Per-member team budgets landed in production 🟡. |
| **Per-key TPM/RPM rate limits** | ✅ **important** | This is your *admission control*. An 8-agent swarm hammering an `-np 6` server just queues; limiting RPM per key gives fair scheduling instead of head-of-line blocking. Needs Redis to track limits accurately. |
| `num_retries` | ⚠️ **lower to 1** | You have `num_retries: 2`. A retry on a 600 s agentic generation is 20 minutes of wasted GPU. Retries also **re-prefill**. |
| Fallbacks | ✅ | `coder` → `coder-cpu-worker` or `fast` when the GPU is yielded to a game. Turns arbiter unloads into graceful degradation instead of 503s. |
| `routing_strategy` | change | `simple-shuffle` is meaningless with one deployment per alias. If you register the *same* model twice (deep + swarm entries), use `latency-based-routing` or `least-busy`. |
| Response caching (Redis) | ❌ | See §3.4 — wrong layer, harmful for agents. |
| Semantic caching | ❌ | Correctness hazard for code. |
| `cache_control_injection_points` / auto prompt-cache checkpoints | ❌ | Anthropic/Bedrock-specific; no effect on llama.cpp; risks mutating the request body. |
| **Prompt compression (v1.83.14+)** | ❌ **verify disabled** | "transparently compresses long-context inputs… no client opt-in required" — would obliterate prefix cache hits. |
| `drop_params: true` | ✅ keep | |
| `request_timeout: 600` | ✅ keep | |
| `/v1/responses` API | 🟡 | Supported; `/v1/messages` now routes to Responses API by default for OpenAI/Azure. For your `openai/*` → llama-swap path this is mostly irrelevant; **test before switching clients.** |
| **MCP gateway** | ✅ **real, and worth it** | LiteLLM exposes a genuine MCP Gateway: centralize MCP servers, unified auth + permission management **by Key/Team/Org**, tool discovery, works with the Responses API and Cursor/OpenAI SDK ([docs](https://docs.litellm.ai/docs/mcp), [deployment](https://docs.litellm.ai/docs/mcp_deployment)). **This is the clean replacement for your `mcpo-config.json` sidecar** and gives per-agent tool scoping — a swarm safety feature (the tester agent shouldn't get write tools). |
| Spend/observability | ✅ | You already have `database_url`. Combine with llama-swap's sqlite activity metrics. |

Suggested `litellm-config.yaml` deltas:
```yaml
litellm_settings:
  drop_params: true
  request_timeout: 600
  cache: false                 # explicit: no response caching for agents
  # verify: prompt compression / auto cache_control injection are OFF

router_settings:
  routing_strategy: least-busy   # meaningful once deep+swarm entries both exist
  num_retries: 1                 # was 2 — retries re-prefill and waste GPU-minutes
  allowed_fails: 2
  cooldown_time: 30
  fallbacks:
    - coder: ["coder-swarm", "fast"]
```

---

## 6. Concrete tuning for THIS rig

### 6.1 (a) Single deep agent — keep essentially what you have

```yaml
"coder-deep":
  name: "Qwen3.6 35B-A3B — single deep agent (max ctx)"
  cmd: |
    ${srv}
    --model /models/Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf
    --ctx-size 262144
    --parallel 1
    --kv-unified
    --cache-ram 24576
    --ctx-checkpoints 64
    --checkpoint-min-step 256
    --cache-reuse 256
    --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0
  ttl: 120
  concurrencyLimit: 2
```
Changes vs. today: `--cache-ram 24576` (from 8192 default — uses your idle 64 GB), `--cache-reuse 256` (was off), more checkpoints. All pure upside for a long agent session.

For `qwen3.6-27b`, keep MTP + `--parallel 1` exactly as-is; it is your latency king and must not be a swarm model.

### 6.2 (b) 4–8 concurrent swarm workers

```yaml
"coder-swarm":
  name: "Qwen3.6 35B-A3B — swarm (6 slots × ~43k ctx)"
  cmd: |
    /app/llama-server
    --host 127.0.0.1 --port ${PORT}
    -ngl 999
    --flash-attn on
    --cache-type-k q8_0 --cache-type-v q8_0
    --no-webui
    --model /models/Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf
    --ctx-size 262144
    --parallel 6
    --kv-unified                    # shared pool: planner can burst past 43k
    --cont-batching
    --batch-size 4096 --ubatch-size 1024
    --cache-ram 32768               # 32 GiB of your 64 GB for cross-slot checkpoints
    --ctx-checkpoints 96
    --checkpoint-min-step 128
    --cache-reuse 256
    --slot-prompt-similarity 0.1
    --backend-sampling              # EXPERIMENTAL: moves the np-scaling bottleneck off CPU
    --slot-save-path /cache/slots   # lets you persist the shared prefix across arbiter unloads
    --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0
  ttl: 300
  concurrencyLimit: 6               # must be >= --parallel or llama-swap 429s first
```

**Notably absent, on purpose:** `--spec-type draft-mtp` (requires `-np 1`, and steals FLOPs when batch-saturated), `--swa-full` (ggerganov: big VRAM cost, "almost no benefits"), and image input (llama.cpp [#23233](https://github.com/ggml-org/llama.cpp) crash per your notes).

**Why `-np 6` and not 8:** the 5090 data shows the *server* path's returns flatten past `-np 4` due to CPU sampling, and your 12700K is weaker and already gives 10 threads to the CPU embedder. Six slots × ~43 K is a better shape than eight × 32 K for coding agents. **Start at 4, measure, walk up.**

**Context-per-slot tradeoff, decided:** with `--kv-unified` you get a shared pool, so `-np 6` does not hard-cap any single agent at 43 K — it caps the *sum*. That's strictly better for a mixed planner+workers swarm. Only switch to `--no-kv-unified` if a runaway agent repeatedly starves the others.

### 6.3 Always-resident small worker — CPU, not GPU

```yaml
"worker-cpu":
  name: "Small worker (routing/tagging/summarize) — CPU-pinned, zero VRAM"
  env:
    - "CUDA_VISIBLE_DEVICES="       # MANDATORY — -ngl 0 alone still grabs ~2.8 GiB
  cmd: |
    /app/llama-server
    --host 127.0.0.1 --port ${PORT}
    -ngl 0 --threads 6
    --model /models/llama3.2-3b.gguf     # or a 4B-class Q4_K_M
    --ctx-size 32768
    --parallel 4
    --cache-ram 8192
    --jinja --no-webui
    --temp 0
  ttl: 3600
```
Put it in a **persistent, non-exclusive** group (like `qwen3-embed`) so it survives every swap and every arbiter unload. Total cost: 0 VRAM, ~3 GB RAM, ~6 CPU threads. 🟢

### 6.4 The ComfyUI / gaming arbiter interaction

Three concrete improvements:

1. **Drain, don't kill.** Raise `unloadTimeout` (default 10 s) to ~60 s for swarm entries so in-flight agent turns finish. Have `gpu-yield-unload.sh` first flip the LiteLLM fallback (so new requests go to `worker-cpu`), *then* call `POST /api/models/unload`.
2. **Persist the shared prefix across yields.** Before unload, `POST /slots/0?action=save` (needs `--slot-save-path`); after the game, `hooks.on_startup.preload` the coder and `POST /slots/0?action=restore`. This converts a several-minute cold-swarm-restart into seconds. 🟢 (API is documented; the workflow is my composition — **untested**)
3. **`--cache-ram` survives nothing.** The RAM prompt cache dies with the process. Combined with TraceLab's finding that idle-gap eviction is the dominant miss cause, the arbiter is your #1 cache killer. If you can tolerate it, raise `ttl` on the swarm entry and let the arbiter (not idle timeout) be the only thing that unloads.
4. **If you adopt vLLM for `coder`,** its **sleep mode L1** is a far better yield primitive than a process kill: `POST /sleep?level=1` frees VRAM while holding weights in CPU RAM, and `/wake_up` is claimed 18–20× faster than a fresh load 🟡. Pair it with llama-swap v243's `vllm-wrapper` so llama-swap talks to an already-running vLLM instead of restarting it. 🟢

### 6.5 Should `coder` move to vLLM/SGLang?

**Not yet — run this experiment first.** 🟡

Set up in parallel, don't migrate:
```bash
vllm serve <Qwen3-Coder-30B-A3B-class>-AWQ \
  --quantization awq_marlin \
  --max-model-len 32768 \
  --max-num-seqs 8 \
  --gpu-memory-utilization 0.92 \
  --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser qwen3 \
  --guided-decoding-backend xgrammar \
  --enable-sleep-mode \
  --kv-cache-memory <cached value from first boot>   # skips profiling+graph estimation on reboot
```
Wire it in via llama-swap's `vllm-wrapper` (v243) so you keep one front door. Measure against `coder-swarm` on: aggregate tok/s at 1/4/8 concurrency, p50/p95 TTFT with a 20 K shared prefix, and max usable context.

**Decision rule:** switch only if vLLM wins on *aggregate tok/s at 8 concurrency* **and** the 32 K context ceiling is enough for your agents. If your agents need >32 K, llama.cpp's q8_0 KV + GGUF wins on VRAM efficiency and you should stay.

**Ampere-specific rules if you do:** use **AWQ-INT4 + `awq_marlin`**; **do not use FP8** (dequant-to-FP16 compute tax on sm_86; one report: 13% slower than AWQ-4bit 🟡); don't expect NVFP4/MXFP4 (Blackwell). 🟢

---

## 7. Using the 64 GB of CPU RAM

| Technique | Available on llama.cpp? | Value here | Notes |
|---|---|---|---|
| **Prompt-cache checkpoints in RAM (`--cache-ram`)** | ✅ **yes, today** | 🟢🟢 **highest value, zero risk** | Default 8192 MiB; raise to 24–32 GiB. Directly attacks TraceLab's dominant miss cause. |
| **MoE expert offload (`-ncmoe N` / `-cmoe`)** | ✅ | 🟡 situational | Moves first-N-layers' expert weights to CPU RAM, freeing VRAM for KV/context. On a 3-B-active MoE the CPU traffic is small. **Concretely useful:** `-ncmoe 8` might free ~2–3 GiB, buying you ~40 K more shared context or room for a co-resident worker. Effects are counterintuitive and system-dependent — **must be measured** (no 3090 numbers found). |
| **Disk KV cache** | ❌ **not yet** | — | `--cache-disk` is [open feature request #20697](https://github.com/ggml-org/llama.cpp/issues/20697) (PR #24028 open). `--slot-save-path` is the manual workaround. |
| **LMCache CPU/NVMe KV tiers** | ❌ vLLM-only | 🟡 | 1.9–8.1× smaller TTFT at QPS=1; 3–10× latency reductions claimed 🟡. PCIe restores a 128 K KV in hundreds of ms; Gen5 NVMe ~2–3 s 🟡. **The single strongest argument for the vLLM experiment.** |
| **SGLang HiCache** | ❌ SGLang-only | 🟡 | Same idea, radix-tree-native. |
| **vLLM sleep L1 (weights → CPU RAM)** | ❌ vLLM-only | 🟢 for the arbiter | Needs ~17 GB RAM to hold weights; you have room. |
| **KTransformers heterogeneous MoE** | separate engine | 🔴 | Only if you want a model that flatly doesn't fit. Not a batching server. |

**Bottom line:** the *only* CPU-RAM lever available to you today on llama.cpp is `--cache-ram` (huge) and `-ncmoe` (situational). Everything else requires moving to vLLM.

---

## 8. Prioritized action list

| # | Action | Effort | Expected gain | Conf. |
|---|---|---|---|---|
| 1 | Verify `llama-server` build ≥ **2026-06-09** (PR #24190); pull latest `llama-swap:cuda` | 5 min | Makes cross-slot prefix caching work *at all* | 🟢 |
| 2 | `--cache-ram 24576..32768` on every model entry | 5 min | Directly attacks the dominant cache-miss cause | 🟢 |
| 3 | `--cache-reuse 256` (currently off by default) | 5 min | Free reuse after mid-context edits/compaction | 🟢 |
| 4 | Add a `coder-swarm` entry (`-np 6`, `--kv-unified`, no MTP); keep `coder-deep` | 30 min | The actual swarm capability | 🟢 |
| 5 | Audit clients for unstable prompt prefixes (timestamps/UUIDs/tool-order) | 1 h | Can be the difference between 96% and ~0% hit rate | 🟢 |
| 6 | Verify LiteLLM `main-latest` isn't doing prompt compression / cache_control injection; pin a version | 30 min | Prevents silent cache destruction | 🟢 |
| 7 | Move the small worker to CPU (`CUDA_VISIBLE_DEVICES=""`), persistent group | 20 min | Always-available cheap turns, 0 VRAM | 🟢 |
| 8 | Test `--backend-sampling` at `-np 6` | 30 min | Targets the measured np-scaling bottleneck | 🟡 |
| 9 | **Verify context checkpoints actually work on `qwen3.6-35b-a3b`** (issue #24055, hybrid models) | 1 h | If broken, the whole swarm plan needs a different model | 🟡 **top risk** |
| 10 | Arbiter: raise `unloadTimeout`, add `/slots?action=save|restore`, add `hooks.on_startup.preload` | 2 h | Turns yields from cache-wipes into pauses | 🟡 |
| 11 | LiteLLM: `num_retries: 1`, per-key RPM limits, fallbacks to CPU worker | 1 h | Admission control + graceful degradation | 🟢 |
| 12 | Migrate `groups:` → `matrix:` DSL + `profiles` for deep/swarm switching | 2 h | Cleaner, and `groups` is now legacy | 🟡 |
| 13 | vLLM AWQ-Marlin A/B for `coder` via `vllm-wrapper` | 1 day | Possibly large at ≥8 concurrency; possibly a context regression | 🟡 |
| 14 | Try `-ncmoe 4/8/12` sweeps to free VRAM for context | 3 h | Unknown, system-dependent | 🟡 |
| 15 | Adopt LiteLLM MCP Gateway (replace `mcpo` sidecar), scope tools per agent key | 1 day | Ops + swarm safety | 🟡 |

---

## 9. What I could NOT verify (explicitly unverified)

- **No measured llama.cpp `-np` scaling curve on a 3090/3090 Ti at 24 GB with a 27–35B 4-bit model.** The closest real data is RTX 5090 / 20B (4.8× at np=32) and A40 48 GB. **You will have to generate this yourself** — `llama-batched-bench` plus a `bakeoff/`-style harness is the right tool, and you already have `bakeoff/ctx-ceiling-probe.sh` as a template.
- **No 3090 vLLM-vs-llama.cpp head-to-head at matched quality.** The single 3090 vLLM datapoint (168 tok/s MoE AWQ) is single-stream and from a secondary source.
- **No ExLlamaV3/TabbyAPI concurrency benchmarks on a 3090.** Best source is paywalled.
- **`-ncmoe` throughput impact on Ampere:** no measured numbers found at all.
- The exact scope of PR #24190 — my two fetches gave slightly different framings (issue #22942 proposed a *server-global checkpoint pool with LCP-aware slot selection*; the merged PR describes *idle slots exporting VRAM cache to RAM*). The issue is definitively closed by it (2026-06-09), but **whether full global LCP-aware slot selection landed, or just the RAM-export half, is unconfirmed.** Read the commit before relying on the strongest interpretation.
- **Nexa** — no credible 2026 sources found.
- Several 2026 "benchmark" pages surfaced by search (markaicode, gigagpu, myaihardware, localaimaster, popularai, agenticwire) have the fingerprints of AI-generated SEO content. I have marked numbers sourced only from them 🔴 and avoided leaning on them.

---

## Sources

- [llama.cpp tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama-server(1) manpage, Debian testing](https://manpages.debian.org/testing/llama.cpp-tools/llama-server.1.en.html)
- [llama.cpp discussion #4130 — Parallelization / Batching Explanation](https://github.com/ggml-org/llama.cpp/discussions/4130)
- [llama.cpp discussion #13606 — Tutorial: KV cache reuse with llama-server](https://github.com/ggml-org/llama.cpp/discussions/13606)
- [llama.cpp discussion #18308 — Optimal parameters for parallel inference](https://github.com/ggml-org/llama.cpp/discussions/18308)
- [llama.cpp discussion #22658 — Max context per request vs unified KV](https://github.com/ggml-org/llama.cpp/discussions/22658)
- [llama.cpp issue #22942 — prompt cache checkpoints slot-local under -np > 1](https://github.com/ggml-org/llama.cpp/issues/22942)
- [llama.cpp PR #24190 (merged 2026-06-09)](https://github.com/ggml-org/llama.cpp/pull/24190)
- [llama.cpp issue #20697 — `--cache-disk` feature request (open)](https://github.com/ggml-org/llama.cpp/issues/20697)
- [llama.cpp issue #24055 — checkpoints always invalidated on hybrid/recurrent models](https://github.com/ggml-org/llama.cpp/issues/24055)
- [llama.cpp issue #17450 — kv_unified true despite not setting --kv-unified](https://github.com/ggml-org/llama.cpp/issues/17450)
- [TraceLab: Characterizing Coding Agent Workloads for LLM Serving — arXiv:2606.30560](https://arxiv.org/abs/2606.30560) · [SyFI Lab writeup](https://syfi.cs.washington.edu/blog/2026-06-25-tracelab/) · [code](https://github.com/uw-syfi/TraceLab)
- [llama-swap releases (v244, 2026-07-28)](https://github.com/mostlygeek/llama-swap/releases) · [configuration.md](https://github.com/mostlygeek/llama-swap/blob/main/docs/configuration.md) · [concurrency/DeepWiki](https://deepwiki.com/mostlygeek/llama-swap/9.1-concurrency-and-request-limits)
- [vLLM releases (v0.26.0, 2026-07-27)](https://github.com/vllm-project/vllm/releases)
- [vLLM Sleep Mode docs](https://docs.vllm.ai/en/latest/features/sleep_mode/) · [vLLM sleep mode blog](https://vllm.ai/blog/2025-10-26-sleep-mode)
- [vLLM optimization/tuning docs](https://docs.vllm.ai/en/stable/configuration/optimization/)
- [vLLM FP8 Marlin for Ampere — PR #5975](https://github.com/vllm-project/vllm/pull/5975)
- [SGLang RadixAttention concepts](https://sgl-project-sglang-93.mintlify.app/concepts/radix-attention)
- [SGLang issue #12887 — Ampere MoE FP8 W8A8 via Marlin (feature request)](https://github.com/sgl-project/sglang/issues/12887)
- [SGLang issue #21061 — SGLang vs vLLM scaling under high concurrency](https://github.com/sgl-project/sglang/issues/21061)
- [NVIDIA SGLang Release 26.06 notes](https://docs.nvidia.com/deeplearning/frameworks/sglang-release-notes/rel-26-06.html)
- [Red Hat — llama.cpp vs vLLM (2026-06-15)](https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine)
- [Benchmarking llama.cpp parallelism on A40 GPUs](https://medium.com/@ferraricorneloup.teo/how-many-developers-can-one-gpu-serve-benchmarking-llama-cpp-parallelism-on-a40-gpus-0ea2a8c36045)
- [ure.us — Local LLM Bench: MoE vs Dense on One RTX 3090 (2026-03-06)](https://ure.us/articles/best-local-llm-agentic-coding/)
- [Claude Code, llama.cpp, and the Hidden Prompt Cache Killer (Jun 2026)](https://www.mykolaaleksandrov.dev/posts/2026/06/claude-code-llamacpp-prompt-cache-fix/)
- [LMCache paper — arXiv:2510.09665](https://arxiv.org/pdf/2510.09665) · [vLLM production-stack KV offload tutorial](https://github.com/vllm-project/production-stack/blob/main/tutorials/05-offload-kv-cache.md)
- [LiteLLM MCP Gateway](https://docs.litellm.ai/docs/mcp) · [MCP deployment](https://docs.litellm.ai/docs/mcp_deployment) · [caching](https://docs.litellm.ai/docs/proxy/caching) · [routing](https://docs.litellm.ai/docs/routing) · [release notes](https://docs.litellm.ai/release_notes/)
- [ExLlamaV3](https://github.com/turboderp-org/exllamav3) · [DeepWiki](https://deepwiki.com/turboderp-org/exllamav3)
- [llama.cpp llguidance docs](https://huggingface.co/spaces/YZ-TAN/flask-llama/raw/main/llama.cpp/docs/llguidance.md) · [chat templates & tool calling / DeepWiki](https://deepwiki.com/ggml-org/llama.cpp/3.9-chat-templates-and-message-parsing)
- [SGLang vs vLLM 2026 (Spheron)](https://www.spheron.network/blog/vllm-vs-sglang-2026/) 🟡
- [KTransformers](https://github.com/kvcache-ai/ktransformers)
