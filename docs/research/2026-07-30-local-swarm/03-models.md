# The Model Layer — What Should Be Running on One RTX 3090 Ti in Aug 2026

**Research date:** 2026-07-30
**Rig:** RTX 3090 Ti (24 GB) · i7-12700K · 64 GB RAM · NVMe · CachyOS
**Serving:** llama.cpp `llama-server` under llama-swap, `-ngl 999 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --jinja`, one big model resident
**Goal:** swarms of concurrent local coding agents building real applications

> **Method note.** Everything below was verified against live sources on 2026-07-30 and cited inline.
> Claims I could not source are explicitly marked **unverified**. Confidence is flagged per section.
> Numbers computed by me (rather than measured by a source) are labelled **[modeled]** and the
> arithmetic is shown so you can check it.

---

## 0. TL;DR — the executive answer

1. **Your `coder` = Qwen3.6-35B-A3B choice is still correct in Aug 2026, and for swarms it is *more*
   correct than the bake-off knew.** The reason is architectural, not benchmark-driven: Qwen3.6 is a
   *hybrid linear-attention* model (only 10 of 40 layers hold a real KV cache), which makes
   multi-slot concurrency almost free on VRAM. Confidence: **high**.
2. **Your `coder-strong` = Qwen3.6-27B MTP choice is still correct, but it is a *single-agent deep
   work* model, not a swarm model.** MTP requires `--parallel 1`, so it can never be a swarm host.
   Keep it exactly as-is for one-at-a-time hard tasks. Confidence: **high**.
3. **The spec-decoding picture is more subtle than "it doesn't work on MoE."** A 19-config RTX 3090
   benchmark found every *ngram* and *classic-draft* variant is slower than baseline on
   Qwen3.6-35B-A3B — but it **never tested `draft-mtp`**, and separate Ampere-class data shows MTP
   giving **+28%** on this exact model. There is an `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`. This is worth
   a measurement. Confidence: **medium** (see §4.3 — I revised this mid-research).
4. **The real swarm ceiling on this rig is ~4–8 concurrent agent turns**, and the binding constraint
   is llama.cpp's batching efficiency, not VRAM. Confidence: **medium-high**.
5. **The one genuinely new thing worth evaluating** is `NVIDIA-Nemotron-3-Nano-30B-A3B` — its KV
   cache is **3.3× smaller than Qwen3.6's and 16× smaller than a conventional 30B MoE**, which is the
   single biggest lever on swarm concurrency. Confidence in the KV numbers: **high**; in its coding
   quality vs Qwen3.6: **low** (I could not source SWE-bench for it).
6. **The uncomfortable finding:** llama.cpp loses **3–4×** to vLLM at high concurrency on identical
   hardware, and llama.cpp showed a **60% request success rate** on a coding workload at c=64. If the
   swarm goal is serious, the runtime — not the model — is your next bottleneck. Confidence: **high**.

---

## 1. The 2026 landscape — what actually fits 24 GB

### 1.1 What changed since your 2026-07-15 bake-off

The bake-off is only ~2 weeks old and **nothing released since invalidates it**. The relevant 2026
release wave landed *before* your bake-off:

| Date | Release | Relevance to a 24 GB card |
|---|---|---|
| 2026-04-03 | Gemma 4 26B-A4B (25.2B/3.8B active MoE) | Fits. Weak agentic index. |
| 2026-04-16 | Qwen3.6-35B-A3B | **Fits. Your current `coder`.** |
| 2026-04-22 | Qwen3.6-27B (dense, MTP) | **Fits. Your current `coder-strong`.** |
| 2026-04-24 | DeepSeek V4 (1.6T Pro / 284B Flash) | Does not fit. Not close. |
| 2026-06-13 | GLM-5.2 (744B/40B active) | Does not fit. |
| 2026-01 | GLM-4.7-Flash (30B/3.6B active) | Fits. Real alternative. |
| 2026-07-02 | Laguna XS 2.1 (33B/3B active, Poolside) | Fits. Coding-specialised. Unproven. |
| 2026 (H1) | Nemotron 3 Nano 30B-A3B (31.6B/3.6B) | Fits. Best-in-class KV cache. |

Sources: [Qwen3.6-35B-A3B card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B),
[Qwen3.6-27B card](https://huggingface.co/Qwen/Qwen3.6-27B),
[DeepSeek V4 (deepseek.ai)](https://deepseek.ai/deepseek-v4),
[GLM-5.2 guide](https://codersera.com/blog/glm-5-2-complete-guide-2026/),
[GLM-4.7-Flash (Unsloth)](https://unsloth.ai/docs/models/tutorials/glm-4.7-flash),
[Laguna S 2.1 / XS family](https://poolside.ai/blog/introducing-laguna-s-2-1),
[Nemotron 3 Nano](https://huggingface.co/blog/nvidia/nemotron-3-nano-efficient-open-intelligent-models),
[Gemma 4 26B-A4B](https://huggingface.co/google/gemma-4-26B-A4B).

**The frontier open-weight models of 2026 (DeepSeek V4, GLM-5.x, Kimi K2.6, MiniMax M2.7) have all
moved to 200B–1.6T parameters and are permanently out of reach of a 24 GB card.** The "runs locally"
tier has consolidated on **~30B MoE with ~3B active**. That is now the standard shape, and Qwen3.6-
35B-A3B is squarely in it.

### 1.2 The candidate table

| Model | Arch (total/active) | Best quant for 24 GB | Weights GB | Native ctx | KV bytes/tok (f16) | t/s on 3090-class | Source |
|---|---|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B** | MoE 35B/3B, hybrid GatedDeltaNet+GatedAttn, 40L (10 full-attn) | UD-IQ4_NL_XL | **19.5** | 262,144 | **20,480** | **140** (CUDA, 89.6k ctx, all-GPU) | [Giles Thomas 3090 bench](https://www.gilesthomas.com/2026/07/benchmarking-qwen-3-6-35b-moe-rtx-3090) |
| Qwen3.6-35B-A3B | same | UD-Q4_K_XL | 22.4 | 262,144 | 20,480 | 135.7 baseline | [spec-dec repo](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090) |
| **Qwen3.6-27B** | Dense 27B, hybrid, 64L (16 full-attn), **MTP head** | UD-Q4_K_XL | **17.6** | 262,144 | ~32,768 [modeled] | 34.5 → **50 w/ MTP** (your measurement) | [unsloth 27B GGUF](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF) |
| GLM-4.7-Flash | MoE 30B/3.6B, MLA | UD-Q4_K_XL | ~18 | 202,752 | **54,144** | 60–80 | [Unsloth GLM-4.7-Flash](https://unsloth.ai/docs/models/tutorials/glm-4.7-flash) |
| Nemotron 3 Nano 30B-A3B | MoE 31.6B/3.6B, Mamba2 hybrid (6 attn of 52L) | Q4_K_M | ~18 (est.) | **1,000,000** | **6,144** | not measured on 3090 | [NVIDIA HF blog](https://huggingface.co/blog/nvidia/nemotron-3-nano-efficient-open-intelligent-models) |
| Gemma 4 26B-A4B | MoE 25.2B/3.8B, 128 experts | Q4_K_M | ~15 | 262,144 | not sourced | not measured | [HF card](https://huggingface.co/google/gemma-4-26B-A4B) |
| Devstral Small 2 24B | Dense 24B | Q4_K_M | 14–15 | 256,000 | not sourced | **33** | [hardware-corner](https://www.hardware-corner.net/devstral-2-hardware-requirements/) |
| Laguna XS 2.1 | MoE 33B/3B (Poolside) | GGUF availability **unverified** | ~19 (est.) | not sourced | not sourced | not measured | [Poolside](https://poolside.ai/blog/introducing-laguna-s-2-1) |
| Holo-3.1-35B-A3B | MoE 35B/3B (Qwen3.5 base), computer-use VLM | Q4_K_M | 21.3 | 262,144 | ~20,480 | not measured | [HF GGUF](https://huggingface.co/Hcompany/Holo-3.1-35B-A3B-GGUF) |
| gpt-oss-20b | MoE 21B/3.6B | MXFP4 | ~14 | 131,072 | not sourced | not measured | [HF](https://huggingface.co/openai/gpt-oss-20b) |

**Note on gpt-oss:** OpenAI has shipped **no successor** to the August 2025 gpt-oss weights as of
mid-2026 — the original release remains the current version. It is now a year-old model competing
against April-2026 releases. **Do not add it.** Confidence: **medium** (absence-of-release is
inherently harder to verify).

**Note on Holo-3.1:** genuinely the top open-weight *agentic* model on composite benchmarks
(82.6/100, #1 open-weight on [BenchLM](https://benchlm.ai/llm-agent-benchmarks)), but it is a
**GUI/computer-use** model — OSWorld-Verified 77.8%, browser/desktop automation. It is not a
repo-level coding model. Wrong tool for this job despite the headline number.

### 1.3 The architectural insight that matters most

This is the finding that reframes the whole question. **Qwen3.6 is not a conventional transformer.**

Qwen3.6-35B-A3B is `10 × (3 × (Gated DeltaNet → MoE) → 1 × (Gated Attention → MoE))` — 40 layers of
which **only 10 hold a token-indexed KV cache**. The other 30 are linear-attention layers holding a
**constant-size recurrent state that does not grow with context**.
([architecture overview](https://huggingface.co/blog/EXDai/qwen36-35b-a3b-architecture-overview),
[Qwen3.6-35B-A3B card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B))

The measured consequence, from a dedicated KV-cache comparison:

| Model | KV bytes/token (f16) | KV @ 32k ctx | Architecture |
|---|---|---|---|
| Nemotron-3-Nano-30B | **6,144** | **0.20 GB** | 6 attn layers of 52 + Mamba-2 |
| Qwen3.5/3.6-35B-A3B | **20,480** | **0.67 GB** | 10 full-attn of 40 + GatedDeltaNet |
| GLM-4.7-Flash | 54,144 | 1.77 GB | MLA compression |
| Qwen3-30B-A3B (old gen) | 98,304 | 3.22 GB | conventional GQA, 4 KV heads |

Source: [The KV-Cache of Small MoEs (kaitchup)](https://kaitchup.substack.com/p/the-kv-cache-of-small-moes-qwen3).
Confidence: **high** — I independently reproduced the Qwen3.6 figure from the published config
(2 KV heads × 256 head-dim × 2 tensors × 2 bytes × 10 layers = 20,480 B/token exactly).

**Your current model has a 4.8× smaller KV cache than the previous generation's equivalent.** This is
precisely why `--ctx-size 262144` fits in 23.3 GB on your rig, and it is the entire reason a swarm is
feasible at all on 24 GB. See §6.

---

## 2. Tool-calling and agentic reliability

### 2.1 Headline coding/agentic scores

| Model | SWE-bench Verified | SWE-bench Pro | Terminal-Bench 2.0 | LiveCodeBench v6 | Aider Polyglot | Source |
|---|---|---|---|---|---|---|
| **Qwen3.6-27B** (dense) | **77.2** | **53.5** | **59.3** | — | — | [HF card](https://huggingface.co/Qwen/Qwen3.6-27B) |
| **Qwen3.6-35B-A3B** (MoE) | 73.4 | 49.5 | 51.5 | 80.4 | **62.2** (Q8) | [HF card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B), [Aider run](https://llmkube.com/blog/m5-max-aider-polyglot-and-finops) |
| Devstral Small 2 24B | 68.0 | — | — | — | — | [Mistral](https://mistral.ai/news/devstral-2-vibe-cli/) |
| GLM-4.7-Flash | 59.2 | — | — | — | — | [Unsloth](https://unsloth.ai/docs/models/tutorials/glm-4.7-flash) |
| Gemma 4 26B-A4B | — | — | — | 77.1 | — | [HF card](https://huggingface.co/google/gemma-4-26B-A4B) |
| *(reference, does not fit)* GLM-5.2 744B | — | 62.1 | 81.0 (TB 2.1) | — | — | [codersera](https://codersera.com/blog/glm-5-2-complete-guide-2026/) |
| *(reference, does not fit)* DeepSeek V4-Pro | 80.6 | — | — | — | — | [morphllm](https://www.morphllm.com/deepseek-v4) |

**Critical observation:** your `coder-strong` (27B dense) beats your `coder` (35B-A3B) on *every*
coding benchmark — **+3.8 SWE-bench Verified, +4.0 SWE-bench Pro, +7.8 Terminal-Bench 2.0**. The MoE
wins only on speed and context. Your alias naming is therefore accurate and your bake-off's choice of
the MoE as the *default* is a throughput decision, not a capability decision. That is the right call
for swarms — but it means **quality-critical single tasks should be explicitly routed to
`coder-strong`.** Confidence: **high**.

### 2.2 Tool-calling specifically

| Model | Benchmark | Score | Date | Source |
|---|---|---|---|---|
| GLM-4.7-Flash (reasoning) | τ²-bench telecom | **98.8%** | Apr 2026 | [awesomeagents](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/) |
| Qwen3.6 35B | τ²-bench telecom | 95.03% | 2026 | [benchlm](https://benchlm.ai/benchmarks/tau2-bench) |
| GLM-4.5 (open) | BFCL v3 | 76.7–77.8% | Jun 2026 | [pricepertoken](https://pricepertoken.com/leaderboards/benchmark/bfcl-v3) |
| Qwen3 32B | BFCL v3 | 75.7% | Apr 2026 | [awesomeagents](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/) |
| GLM-4.7-Flash Thinking | BFCL v3 | 74.6% | Apr 2026 | same |
| Holo3-35B-A3B | composite agentic | 82.6/100 (#1 open) | Jul 2026 | [benchlm](https://benchlm.ai/llm-agent-benchmarks) |

**Two large caveats, both important:**

1. **τ²-bench telecom is saturated and should not drive decisions.** The leaderboard maintainers
   themselves flag the 98%+ scores as "spectacular… indicat[ing] possible overfitting," noting the
   benchmark launched with models scoring below 50%
   ([awesomeagents](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/)).
   A 98.8 vs 95.0 gap between GLM-4.7-Flash and Qwen3.6 is **noise, not signal**.
2. **BFCL v3 numbers in circulation are stale (Apr–Jun 2026) and predate Qwen3.6 entirely.** I could
   not find a BFCL v4 entry for either Qwen3.6 model. **Unverified** — treat the absence as a genuine
   gap, not as evidence of weakness. BFCL is now on v4 (holistic agentic eval, since Jul 2025);
   official leaderboard: [gorilla.cs.berkeley.edu/leaderboard.html](https://gorilla.cs.berkeley.edu/leaderboard.html).

**Your own bake-off evidence outranks all of the above.** 3/3 agentic tasks with **0 malformed tool
calls** on your actual harness is a more reliable signal for your workload than any public
leaderboard, and it is consistent with Qwen3.6's release notes claiming "improved parsing nested
objects to make tool calling succeed more" ([Unsloth Qwen3.6 docs](https://unsloth.ai/docs/models/qwen3.6)).
Confidence: **high**.

### 2.3 Known llama.cpp tool-calling landmines

| Issue | Impact | Source |
|---|---|---|
| **Qwen3.6 `chat-template-kwargs` whitespace bug** — `{"enable_thinking": false}` with a space after the colon is silently rejected; model keeps thinking and derails the tool loop | **Directly affects you** — you serve Qwen3.6 with `--jinja` | r/LocalLLaMA, 2026-05-13 (confidence: **medium**) |
| **CUDA 13.2 produces gibberish** with Qwen3.6 — use below 13.2 or 13.3+ | Check your container's CUDA version | [Unsloth Qwen3.6 docs](https://unsloth.ai/docs/models/qwen3.6) (confidence: **high**) |
| Devstral-Small-2 chained tool calls break in llama.cpp (stops mid-sequence, mixes JSON with prose, non-numeric args to numeric params) | Reason not to revive archived Devstral | [llama.cpp #17960](https://github.com/ggml-org/llama.cpp/issues/17960) (confidence: **high**) |
| Gemma 3/4 default thinking mode routes tool calls into `reasoning_content` not `content` | Affects `chat`/Gemma aliases if used agentically | community reports (confidence: **medium**) |
| Some jinja templates hard-`raise_exception` if first message isn't system; `--jinja` auto-injection can trigger it | Aborts request entirely rather than degrading | [GLM-4.5-Air GGUF disc.](https://huggingface.co/unsloth/GLM-4.5-Air-GGUF/discussions/1) (confidence: **medium**) |

**Action item:** audit how your LiteLLM→llama-swap path emits `chat-template-kwargs` for Qwen3.6, and
verify the container's CUDA version is not 13.2.

---

## 3. Swarm workers (3B–14B)

Full detail in the sub-report below; the operative conclusions for your rig:

| Model | Params | BFCL | GGUF repo | Quant | Size | Native ctx | Source |
|---|---|---|---|---|---|---|---|
| **Qwen3.5-9B** | 9B | **0.661 (v4)** | `byteshape/Qwen3.5-9B-GGUF` | Q5_K_M/Q6_K | ~6.5–7.5 GB | 128K | [llm-stats BFCL v4](https://llm-stats.com/benchmarks/bfcl-v4) |
| **Qwen3.5-4B** | 4B | **0.503 (v4)** | unsloth/bartowski mirrors | Q6_K | ~3.3 GB | 128K | same |
| Qwen3-4B-Instruct-2507 | 4B | 61.9 (v3) | `Qwen/Qwen3-4B-Instruct-2507` | Q6_K | ~3.3–4.3 GB | 128K | [HF disc.](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/discussions/18) |
| Qwen3-8B | 8B | 60.2 (v3) | `unsloth/Qwen3-8B-GGUF` | Q5_K_M | ~5.5–6.5 GB | 32K (128K YaRN) | [Qwen3 tech report](https://arxiv.org/pdf/2505.09388) |
| Granite-4.0-H-Tiny | 7B/**1B active** | 54.8 (v3, 1B class) | `bartowski/ibm-granite_granite-4.0-h-tiny-GGUF` | Q5_K_M 5.02 GB | 5.02 GB | ≥16K | [VentureBeat](https://venturebeat.com/ai/ibms-open-source-granite-4-0-nano-ai-models-are-small-enough-to-run-locally) |
| **Qwen2.5-Coder-7B** (your `fast`) | 7B | **no isolated BFCL number found — unverified** | `bartowski/Qwen2.5-Coder-7B-Instruct-GGUF` | Q5_K_M **5.44 GB** | 4.68 GB @Q4_K_M | 32K | LiveCodeBench 37.6% |
| LFM2-1.2B-Tool | 1.2B | purpose-built router | `LiquidAI/LFM2-1.2B-Tool-GGUF` | Q6_K 963 MB | 0.96 GB | — | non-standard Pythonic tool format |
| Llama-3.2-3B (your `utility`) | 3B | ~28 (BFCL, vs SmolLM3 32) | — | Q4_K_M 1.92 GB | 1.92 GB | 131K | weakest tool-caller in the table |

**Verdict on your small tier:**
- **`fast` = Qwen2.5-Coder-7B is now the weakest link.** It is a 2024-generation model with **no
  verifiable tool-calling benchmark**, running at **Q4_K_M** — the quant level where small models take
  disproportionate structured-output damage. **Replace with Qwen3.5-9B at Q5_K_M or Q6_K.**
  Confidence: **medium-high**.
- **`utility` = Llama-3.2-3B is fine for its actual job** (temp-0 tagging/titles, no tool calls). Do
  not promote it to a swarm worker — ~28 BFCL is too low. Confidence: **high**.
- **Small models need higher quants than big ones.** Community consensus in 2026 is that Q4_K_M is the
  *floor* for ≤14B and Q5_K_M/Q6_K should be the default, specifically because quantization damage
  disproportionately hurts structured output at small scale. Multiple troubleshooting guides
  recommend bumping Q4→Q5_K_XL/Q6_K_XL when malformed tool calls appear. Confidence: **medium-high**.
- **Keep active tool count under 5–10 per small worker.** Tool-call accuracy degrades with both
  context length and tool-list size on small models. Confidence: **medium**.

---

## 4. Speculative decoding / MTP in llama.cpp

### 4.1 What llama.cpp actually supports (verified against master, 2026-07-30)

`--spec-type` takes a **comma-separated, chainable** list — multiple mechanisms can run at once and
"best draft wins" ([docs/speculative.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md)):

| Value | Mechanism | Extra VRAM | Multi-slot friendly? |
|---|---|---|---|
| `draft-simple` | Classic separate draft model (`-md`) | 0.7–2.5 GB | Yes (separate ctx/seq) |
| `draft-eagle3` | EAGLE-3, reads target hidden states | moderate | Likely yes |
| `draft-mtp` | Self-speculative via model's own MTP head | ~0–2.5 GiB | **"correct but suboptimal"** |
| `draft-dflash` / `draft-dspark` | Block-diffusion drafts | — | newer, less mature |
| `ngram-simple` / `ngram-map-k` / `ngram-map-k4v` | History pattern match | **zero** | Yes |
| **`ngram-mod`** | Hash pool **shared across all server slots** | **zero** | **Yes, by design** |
| `ngram-cache` | N-gram probability table | **zero** | Yes |

Medusa is **not** supported. Confidence: **high** (primary source, live-fetched).

**Flag hygiene — relevant to your config:**
- `--spec-draft-n-max` default is now **3** (lowered from 16 by
  [PR #23269](https://github.com/ggml-org/llama.cpp/pull/23269), merged 2026-05-19). You set 2 explicitly — fine.
- **`--draft`, `--draft-max`, `--draft-min`, `--draft-n-min` are deprecated and silently ignored.**
  Your config doesn't use them. Good.
- **Rebuild if your llama.cpp predates 2026-05-20**: PR #23287 gave **+7%** MTP throughput via
  backend sampling. Free speed inside `--parallel 1`.

### 4.2 The `--parallel` + MTP interaction — your config note needs updating

Your config comment says "`--parallel 1` is REQUIRED with MTP." **That is no longer literally true,
but it is still the right setting.** Precisely:

- There is **no hard assertion or error** blocking `--parallel N>1` with `draft-mtp` on current master.
  [PR #22838](https://github.com/ggml-org/llama.cpp/pull/22838) (2026-05-11) added parallel drafting support.
- But ggerganov, verbatim in [PR #23269](https://github.com/ggml-org/llama.cpp/pull/23269):

  > "The parallel decoding with MTP enabled still remains **highly suboptimal**. With the current
  > approach, we cannot utilize the `split_equal()` logic when splitting the batches into ubatches. A
  > bigger refactoring is necessary… **For now with this PR it should be at least correct.**"

- Unsloth's live model card for `unsloth/Qwen3.6-27B-MTP-GGUF` still states: **"Use `-np 1`, and
  `--mmproj` are not yet supported with MTP."**

Confidence: **high**. **Conclusion: MTP and swarms are mutually exclusive in practice.** Multi-slot
MTP won't crash — it will just be slower than either option alone. This confirms the two-model split
in §7: MoE for swarms (`--parallel N`, no MTP), dense for deep single work (`--parallel 1`, MTP).

Also note [issue #22867 — MTP + vision causes slot corruption/OOM](https://github.com/ggml-org/llama.cpp/issues/22867),
which corroborates your existing "do NOT send images through this entry" caveat.

### 4.3 Correction: does spec decoding help the 35B-A3B MoE on Ampere?

I initially concluded "no." **On closer reading of the source, that conclusion was too strong.**

The [thc1006 RTX 3090 study](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090) tested
19 configs — **`ngram-cache`, `ngram-mod`, and classic draft with Qwen3.5-0.8B**. Every one lost to
the 135.7 tok/s baseline (best was ngram-mod-n24 at 131.1, −3.4%). But **`draft-mtp` was not among
them.** The repo's own scope note says the finding is "engine- and method-specific," citing a vLLM
MTP run on identical hardware that got **+27.5%**.

Countervailing evidence for `draft-mtp` specifically on this model:

| Setup | Hardware | Result | Source |
|---|---|---|---|
| Qwen3.6-35B-A3B, `draft-mtp` n-max=3 | 2× RTX 5090 | 244.6–296.3 tok/s, **acceptance 0.576–0.788** | [PR #23287](https://github.com/ggml-org/llama.cpp/pull/23287) |
| Qwen3.6-35B-A3B, `draft-mtp` n-max=2 | **RTX 3060 12GB (Ampere)** | 22.9 → **29.4 tok/s (+28%)** | secondary (confidence: medium) |
| Qwen3.6-27B dense, `draft-mtp` | RTX 5090 | ~79.7% acceptance | secondary (confidence: medium) |

An Ampere data point showing +28% on the exact model materially weakens the "MoE spec decoding is
dead on Ampere" story. **Revised recommendation:** `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` exists — worth
one A/B. **But** it only helps `--parallel 1`, so it is orthogonal to the swarm goal. Treat it as a
possible `coder-solo` variant, not a swarm change. Confidence: **medium**.

### 4.4 The free win: chain ngram onto MTP

`ngram-*` costs **zero VRAM**, and `ngram-mod` explicitly shares one hash pool across all server
slots ("different requests can benefit from each other" — docs/speculative.md). Chaining is supported:

```
--spec-type draft-mtp,ngram-mod,ngram-map-k4v
```

Agentic coding is exactly the repetitive workload (re-emitted file content, diffs, boilerplate) that
n-gram speculation targets. **Zero VRAM cost, no `--parallel` implications, worth testing on
`coder-strong`.** Confidence: **medium-high**.

### 4.5 Do not add a classic draft model

At <1 GiB headroom, a 0.5–1.5B draft at Q8_0 costs **~0.7–2.5 GB** (weights + its own KV cache). It
does not fit without cutting context elsewhere, and the 3090 study measured it as a **net loss**
(−10.8%) on this model anyway. Confidence: **high**.

**Benchmarking caveat:** `llama-bench` does **not** support `--spec-type`/MTP flags
([issue #22947](https://github.com/ggml-org/llama.cpp/issues/22947), closed not-planned). Any A/B must
go through `llama-server` + a client harness — i.e. your existing `bakeoff/harness.py`.

---

## 5. Quantization quality

### 5.1 The headline finding contradicts the folklore

**Measured, category-isolated KL-divergence data says tool-calling is one of the MOST
quantization-resilient capabilities — not the most fragile.**

A benchmark running ~250K tokens across 6 categories through a patched llama.cpp, measuring KL
divergence vs a BF16 reference across 50+ quants, found for Gemma 4 31B that **tool calling and
science were the most resilient categories at every size tested** (KL 0.069–0.078 at Q8_0), while
**long documents (0.466) and non-Latin scripts (0.222) degraded fastest**
([localbench](https://localbench.substack.com/p/gemma-4-31b-gguf-kl-divergence)). Confidence: **high**
for the qualitative ranking.

The widely-cited r/LocalLLaMA thread claiming Qwen3.6 Q4_K_M→Q6_K_L "fixed" coding-agent failures
**confounded three variables at once** — bit depth, calibration/imatrix quality, and runtime (Ollama
vs raw llama.cpp). The follow-up analysis concludes the *calibration* upgrade likely explains most of
the gain, and states plainly that "nobody has hard numbers"
([InsiderLLM](https://insiderllm.com/guides/qwen-3-6-q4-quant-coding-agents/)). Confidence: **low-medium**
in the original claim.

**Synthesis (confidence: medium-high):** quantization damage to agentic work shows up as **wrong tool
selection and wrong argument values on multi-step tasks — not as malformed JSON.** That failure mode
tracks general reasoning benchmarks, where the measured cliff is at **Q3, not Q4**. Peer-reviewed
support: W8A8/W4A16 is essentially lossless; at aggressive 4-bit a 32B model loses only **2.33%**,
while 1.5–7B models lose **>10%** — model size is the dominant moderator
([arXiv:2504.04823, COLM 2025](https://arxiv.org/abs/2504.04823)).

**Consequence for you:** your 24–35B models at Q4 are on the safe side of the cliff. Your **7B and 3B
models at Q4_K_M are not** — that's where the >10% degradation lives. This independently corroborates
the §3 recommendation to move the small tier to Q5_K_M/Q6_K.

### 5.2 Format comparison

| Quant | PPL retention vs BF16 | Notes |
|---|---|---|
| Q2_K | ~84% | unusable for agents |
| Q3_K_M | ~93% | **below the reliability cliff for dense models** |
| Q4_K_S | ~96.5% | |
| **Q4_K_M** | **~98%** | your 24–35B sweet spot |
| **Q5_K_M** | **~99%** | recommended for ≤14B |
| Q6_K | ~99.5% | |
| Q8_0 | ~99.8% | uploader differences vanish here |

Confidence: **medium** (recurring community figures, directionally consistent with the KL data).

**Unsloth UD vs bartowski: neither dominates.** Independent Pareto-frontier analysis found the
quality-per-GB frontier is *split* — 8/9 Unsloth UD quants on the frontier for Gemma 4, 18/23 for
Qwen 3.5 35B-A3B, but bartowski holds points too. **Recipe differences only matter at Q4 and below.**
Unsloth does claim its imatrix calibration is weighted toward "long-context chat and tool-calling
examples" (vendor claim, plausible, not independently reproduced).
([localbench Qwen3.6 35B-A3B](https://localbench.substack.com/p/qwen-36-35b-a3b-gguf-quality-benchmark),
[bartowski calibration set](https://gist.github.com/bartowski1182/82ae9b520227f57d79ba04add13d0d0d), updated Jun 2026)

**Your `coder` uses UD-IQ4_NL_XL (19.5 GB) rather than UD-Q4_K_XL (22.4 GB).** That's a deliberate
2.9 GB saving that buys your 262k context. Given the frontier data, IQ4_NL_XL from Unsloth is a
legitimate frontier point, not a compromise. **No change recommended.** Confidence: **medium-high**.

**Not applicable to your stack:** AWQ/GPTQ/EXL3 need a different runtime (vLLM/TabbyAPI/ExLlamaV3).
**FP8 is impossible regardless** — the RTX 3090 Ti is Ampere and has **no native FP8 tensor cores**.
Confidence: **high**. These formats are only an argument for switching runtimes (see §6.4).

### 5.3 KV-cache quantization — your `q8_0/q8_0` is correct

| Setting | Quality | VRAM |
|---|---|---|
| `f16 / f16` | reference | 1.0× |
| **`q8_0 / q8_0`** | **sub-0.1% PPL delta — essentially free** | **~0.53×** |
| `q4_0 K / q8_0 V` | acceptable fallback | ~0.40× |
| `q4_0 / q4_0` | **avoid** — degraded long-context behaviour "particularly for code and structured output" | ~0.27× |

**The K/V asymmetry rule still holds in 2026, unchanged: K tolerates q4 acceptably, V does not.** If
you ever need to drop below q8_0, quantize **K only**. Confidence: **medium-high**.

**Your `--cache-type-k q8_0 --cache-type-v q8_0` is the settled 2026 best practice. Do not change it.**
flash-attn is effectively a prerequisite for quantized KV to be fast — you already have it on.

Worth knowing: one user reported running Qwen3.6-35B-A3B at **Q3 weights + bf16 KV at 262,144 ctx in
23/24 GB on an actual RTX 3090 at 120 tok/s** for multi-step agentic tasks
([HF discussion](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/37)) — the inverse trade to
yours. Interesting but **anecdotal**, and it puts weights below the Q4 floor. Not recommended.

**On the horizon (do not build on yet):** TurboQuant KV compression (~3.25–4.25 bits/value, better
quality-per-bit than uniform q4_0) is **unmerged** in mainline llama.cpp
([discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969)). The llmkube bake-off
in §6.4 used it via a fork. Track it.

### 5.4 QAT

Google shipped **Gemma 4 QAT checkpoints on 2026-06-05** (~66% less VRAM at w4a16 vs BF16) — relevant
to your `chat` alias, which already runs `gemma-4-31b-it-qat-Q4_0`. **No evidence of any Qwen QAT
release** — the Qwen3.6 ecosystem is entirely PTQ+imatrix. Notably, Unsloth claims a good PTQ recipe
*beat* Google's own QAT checkpoint (71.47% vs 70.64% MMLU on Gemma 3 27B, at 2 GB smaller) — single
vendor data point, confidence: **medium**. **QAT is a floor-raiser, not a must-switch.**

---

## 6. The swarm math

This is the section that actually answers "how many agents."

### 6.1 The governing llama.cpp semantics

From the [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md):

- `-np, --parallel N` — "number of server slots (default: -1, -1 = auto)"
- `-c, --ctx-size N` — "size of the prompt context"
- `-kvu, --kv-unified` — "use single unified KV buffer shared across all sequences (default: enabled
  if number of slots is auto)"
- `-cb, --cont-batching` — continuous/dynamic batching, **enabled by default**

**The critical semantic: `--ctx-size` is a TOTAL budget divided across slots, not a per-slot budget.**
`effective_per_slot = n_ctx / n_parallel`. This is long-standing, documented behaviour
([llama.cpp #11681](https://github.com/ggml-org/llama.cpp/issues/11681) — filed Feb 2025, still open
and marked stale, i.e. working-as-intended rather than fixed). Confidence: **high**.

So on your current `coder` entry, `--ctx-size 262144` with `--parallel 8` yields **32,768 tokens per
agent**, and the *total* KV cache cost is unchanged.

### 6.2 VRAM budget for Qwen3.6-35B-A3B — reconstructed [modeled]

Let me rebuild your measured 23.3 GB from first principles to validate the model:

```
KV per token (f16)          = 2 KV heads × 256 head_dim × 2 (K,V) × 2 bytes × 10 attn layers
                            = 20,480 B/token                        [matches kaitchup exactly]
KV per token (q8_0)         ≈ 20,480 / 2 × 1.0625 (q8_0 block overhead)
                            ≈ 10,880 B/token  ≈ 10.6 KiB/token

Weights (UD-IQ4_NL_XL)      = 18.16 GiB     [your manifest: 19,500,506,080 bytes]
KV @ 262,144 tok, q8_0      = 262,144 × 10,880 = 2.85 GB = 2.66 GiB
GatedDeltaNet state/seq     ≈ 30 layers × 32 heads × 128 × 128 × 4 B ≈ 63 MB   [modeled, unverified]
Compute/graph buffers       ≈ 1.5–2.0 GiB
                            ------------------------------------------------
Total @ --parallel 1        ≈ 22.4–22.9 GiB     vs your measured 23.3 GiB  ✓
```

The model reproduces your measurement to within ~0.5 GiB, so I'll use it to project concurrency.

### 6.3 Concurrency projection

The key property: **KV cost is flat in slot count** — it is driven by *total* `--ctx-size`, which
`--parallel` merely subdivides. The only per-slot growth is the recurrent DeltaNet state (~63 MB) and
larger batch compute buffers.

| `--parallel` | `--ctx-size` | **ctx per agent** | KV total | DeltaNet state | Est. total VRAM | Verdict |
|---|---|---|---|---|---|---|
| 1 | 262,144 | 262,144 | 2.66 GiB | 0.06 | ~23.3 GiB | your current config (measured) |
| 2 | 262,144 | 131,072 | 2.66 GiB | 0.12 | ~23.4 GiB | safe |
| **4** | **262,144** | **65,536** | 2.66 GiB | 0.25 | ~23.5 GiB | **tight but viable** |
| **4** | **196,608** | **49,152** | 2.00 GiB | 0.25 | ~22.9 GiB | **recommended sweet spot** |
| 8 | 196,608 | 24,576 | 2.00 GiB | 0.50 | ~23.2 GiB | viable, ctx may pinch |
| 8 | 262,144 | 32,768 | 2.66 GiB | 0.50 | ~23.9 GiB | **likely OOM at your headroom** |
| 16 | 131,072 | 8,192 | 1.33 GiB | 1.01 | ~23.0 GiB | ctx too small for real agents |

**[modeled]** — DeltaNet state size and compute-buffer growth with batch are estimates. These need one
empirical probe run each (your `bakeoff/ctx-ceiling-probe.sh` is the right tool).

**Contrast with the previous generation:** the same exercise on a conventional-attention
Qwen3-30B-A3B (98,304 B/tok f16 → ~52,224 B/tok q8_0) gives **13.7 GiB of KV at 262k** — which,
on top of ~18 GB of weights, does not fit *at all*. **The hybrid architecture is what makes your swarm
possible.** Confidence: **high**.

### 6.4 The throughput question — does batching actually help?

Two pieces of hard evidence, pulling in opposite directions:

**Evidence FOR near-linear scaling (encouraging):** the RTX 3090 speculative-decoding study found
Qwen3.6-35B-A3B has an **expert-saturation threshold of ≈94 tokens** — below ~94 tokens in a forward
pass, you are memory-bandwidth-bound loading expert slices, and processing more tokens per pass is
nearly free ([thc1006 repo](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090)).
With `--parallel 8`, a decode step processes 8 tokens — **far** below 94. Mechanically, aggregate
throughput should scale close to linearly up to 8 slots. **[modeled inference from a measured
mechanism]** — confidence: **medium**.

**Evidence AGAINST (sobering):** a head-to-head llama.cpp vs vLLM bake-off on Qwen3.6-27B measured
([llmkube](https://llmkube.com/blog/qwen3-6-27b-bakeoff)):

| Pattern @ c=64 | llama.cpp tok/s | vLLM tok/s | Ratio |
|---|---|---|---|
| chat | 94 | 345 | 3.7× |
| coding | **133 (60% success rate)** | 377 | 2.8× |
| agentic | 72 | 262 | 3.6× |

**llama.cpp's request success rate fell to 60% on the coding pattern at c=64.** Inter-token latency
ranged 49–175 ms/token vs vLLM's steady 64–67 ms. Confidence: **high** (published methodology,
36 measured cells).

**Reconciling these:** c=64 is far past the useful range; the 94-token expert-saturation ceiling
predicts scaling breaks down somewhere well before that. The two findings are consistent if
**llama.cpp scales acceptably to ~4–8 slots and degrades badly beyond**.

### 6.5 Swarm conclusion

> **Realistic ceiling: 4–8 concurrent agent turns on Qwen3.6-35B-A3B.**
> **Recommended: `--parallel 4 --ctx-size 196608` (49,152 tokens per agent).**
> Push to `--parallel 8 --ctx-size 196608` (24,576/agent) only if your agents run short contexts.
> **VRAM is not the binding constraint — llama.cpp's batching efficiency is.**

Do not exceed 8. The failure mode past that is not OOM, it is **silent request failures and
unpredictable latency**, which is far worse for an agent swarm than being slow.

**If you want a genuinely bigger swarm, the next move is a runtime change, not a model change.**
vLLM with the FP8/NVFP4 Qwen3.6 weights buys 3–4× aggregate throughput — at the cost of losing
llama-swap's on-demand load/unload and your Apollo gaming yield hook. That is a real architectural
tradeoff, and it belongs to the serving-layer lane, not this one.

---

## 7. Recommended lineup

### 7.1 Verdict on the current lineup

| Alias | Current | Verdict | Confidence |
|---|---|---|---|
| `coder` | Qwen3.6-35B-A3B UD-IQ4_NL_XL | **KEEP.** Still the best 24 GB agentic coder in Aug 2026, and uniquely swarm-friendly. Add `--parallel`. | **high** |
| `coder-strong` | Qwen3.6-27B MTP UD-Q4_K_XL | **KEEP AS-IS.** Highest local coding scores (77.2 SWE-bench V). MTP forces `--parallel 1` — that's correct for its role. | **high** |
| `fast` | Qwen2.5-Coder-7B Q4_K_M | **REPLACE** with Qwen3.5-9B Q5_K_M/Q6_K. 2024-gen model, unverifiable tool-calling. | **medium-high** |
| `utility` | Llama-3.2-3B Q4_K_M | **KEEP** for temp-0 tagging. Do not use as a swarm worker. | **high** |
| `embed` | Qwen3-Embedding-0.6B (CPU) | **KEEP.** Out of scope, correctly CPU-pinned. | **high** |

### 7.2 The ideal 3-model lineup for agent swarms

**1. `coder` — swarm host (default, ~90% of turns)**
```yaml
model:  unsloth/Qwen3.6-35B-A3B-GGUF :: Qwen3.6-35B-A3B-UD-IQ4_NL_XL.gguf   # 19.5 GB, you have it
flags:  -ngl 999 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --jinja
        --ctx-size 196608 --parallel 4          # 49,152 tokens per agent
        --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0
expect: ~22.9 GiB @ 4 slots; ~140 t/s single-stream, ~300-500 t/s aggregate [modeled]
```
No change to weights — **only the `--parallel` / `--ctx-size` split changes.** Zero download.

**2. `coder-strong` — single deep agent (unchanged)**
```yaml
model:  unsloth/Qwen3.6-27B-GGUF :: Qwen3.6-27B-MTP-UD-Q4_K_XL.gguf   # 17.6 GB, you have it
flags:  ... --ctx-size 114688 --parallel 1
        --spec-type draft-mtp,ngram-mod,ngram-map-k4v    # ← ADD the ngram chain (zero VRAM)
        --spec-draft-n-max 2
expect: ~23.4 GiB; ~50 t/s baseline, possibly more with ngram chained. SWE-bench Verified 77.2.
```
Two low-risk improvements to an otherwise correct entry:
- **Chain `ngram-mod,ngram-map-k4v` onto MTP.** Zero VRAM, no `--parallel` implications, and agentic
  coding is the repetitive workload n-gram speculation is built for (§4.4).
- **Rebuild llama.cpp if it predates 2026-05-20** — PR #23287 is a free +7% on the MTP path (§4.1).

Your config comment "`--parallel 1` is REQUIRED with MTP" should be softened to "**strongly
recommended**" — it is no longer a hard block, just heavily suboptimal (§4.2). The practical
setting doesn't change.

**3. `fast` — swarm worker (REPLACE)**
```yaml
model:  Qwen3.5-9B GGUF at Q5_K_M or Q6_K   (~6.5-7.5 GB)
        repo: byteshape/Qwen3.5-9B-GGUF  ← VERIFY exact filename/sha before committing to manifest
flags:  ... --ctx-size 131072 --parallel 8      # 16,384 per worker
why:    BFCL v4 0.661 — the best sub-14B tool-caller found. Replaces an unbenchmarked 2024 model.
```
This is the **only new download** in the recommendation.

### 7.3 Explicitly NOT recommended

| Model | Why not |
|---|---|
| GLM-4.7-Flash | 2.6× bigger KV cache, SWE-bench 59.2 vs Qwen3.6's 73.4/77.2. Its τ²-bench 98.8 is a saturated benchmark. No reason to switch. |
| Devstral Small 2 24B | SWE-bench 68.0 (lower), **and** an open llama.cpp bug breaking chained tool calls. You already archived it — correct call. |
| gpt-oss-20b | No successor since Aug 2025. A year stale. |
| Holo-3.1-35B-A3B | Best open agentic score (82.6) but it's a GUI/computer-use VLM, not a repo coder. |
| DeepSeek V4 / GLM-5.2 / Kimi K2.6 | 284B–1.6T. Not physically possible on 24 GB. |
| Laguna XS 2.1 | Interesting (33B/3B, coding-specialised, Jul 2026) but **GGUF availability unverified** and no independent benchmarks. Watch, don't adopt. |

### 7.4 The one thing worth a spike

**`NVIDIA-Nemotron-3-Nano-30B-A3B`** — 31.6B/3.6B active, Mamba-2 hybrid, **6,144 B/token KV cache
(3.3× smaller than Qwen3.6, 16× smaller than conventional)**, 1M native context, GGUF + llama.cpp
support confirmed, claims 3.3× higher throughput than Qwen3-30B
([NVIDIA](https://huggingface.co/blog/nvidia/nemotron-3-nano-efficient-open-intelligent-models)).

At 6,144 B/tok f16 (~3,264 B/tok at q8_0), **262,144 tokens of KV costs only ~0.80 GiB** — versus
2.66 GiB for Qwen3.6. That frees ~1.9 GiB, which is the difference between `--parallel 4` and
`--parallel 12` at the same per-agent context.

**But:** I could **not source a SWE-bench Verified number for it** (NVIDIA's blog claims benchmark
leadership without publishing the coding table). **Unverified.** If its coding quality is within a few
points of Qwen3.6-35B-A3B, it is a strictly better swarm host. If it is not, it is irrelevant.
**This is a one-afternoon bake-off run on your existing harness** — highest-information-per-hour
experiment available to you.

---

### 7.5 Ranked experiment queue (highest information per hour)

| # | Experiment | Cost | Why |
|---|---|---|---|
| 1 | `--parallel 4 --ctx-size 196608` on `coder`, measure aggregate t/s + VRAM + success rate | 1 hr | The entire swarm thesis rests on this. Nobody has published it for this rig. |
| 2 | Audit CUDA version ≠ 13.2; audit `chat-template-kwargs` whitespace in the LiteLLM→llama-swap path | 30 min | Two known silent-corruption bugs that would poison every result above. |
| 3 | Chain `ngram-mod,ngram-map-k4v` onto `coder-strong` MTP | 30 min | Zero VRAM, zero risk, possible free speed. |
| 4 | Swap `fast` → Qwen3.5-9B Q5_K_M/Q6_K, re-run bake-off tool-call tasks | 2 hr | Replaces the one unbenchmarked model in the lineup. |
| 5 | Bake-off `Nemotron-3-Nano-30B-A3B` vs `coder` | 3 hr | 3.3× smaller KV = the biggest available lever on swarm width. Unproven on coding. |
| 6 | A/B `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` at `--parallel 1` | 1 hr | Resolves the §4.3 contradiction. Only helps solo mode. |
| 7 | Rebuild llama.cpp to current master | 1 hr | +7% MTP, current spec-type surface. |

---

## 8. Open questions / gaps

| Gap | Status |
|---|---|
| BFCL v4 scores for Qwen3.6-27B / 35B-A3B | **Unverified** — not present on any leaderboard found |
| Nemotron 3 Nano SWE-bench Verified | **Unverified** — NVIDIA didn't publish it |
| Laguna XS 2.1 GGUF availability + benchmarks | **Unverified** |
| DeltaNet recurrent state size per sequence | **[modeled]**, needs empirical probe |
| Aggregate t/s at `--parallel 4/8` on *this* rig | **Not measured anywhere** — needs your own probe |
| Qwen2.5-Coder-7B isolated BFCL score | **Unverified** — does not appear to exist |
| Whether the `chat-template-kwargs` whitespace bug affects your LiteLLM path | **Needs local audit** |
| **BFCL/tau-bench measured *across quant levels*** — the single most-wanted number | **Does not exist publicly.** Closest is [yrougy/llm-quant-bench](https://github.com/yrougy/llm-quant-bench) (BFCL, AST-matched, fixed 1000-sample subset across GGUF quants) — methodology public, results not extracted. Clone and read `results/*/summary.json` if you want hard numbers. |
| `draft-mtp` on 35B-A3B measured on a 3090-class card | **Unverified** — the one published 3090 study omitted it (§4.3) |
| DeepSeek / GLM / MiniMax native MTP in llama.cpp | **Unverified — likely absent.** The complete set of MTP-touching commits covers only Gemma4, qwen35, Step3.5/3.7. |
| Crossover concurrency N where batching beats spec decoding | **No published figure for llama.cpp.** Must be measured locally. |

---

## 9. Source index (primary)

**Model cards / releases:** [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) ·
[Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) ·
[unsloth 35B-A3B GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) ·
[unsloth 27B GGUF](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF) ·
[Unsloth Qwen3.6 docs](https://unsloth.ai/docs/models/qwen3.6) ·
[Nemotron 3 Nano](https://huggingface.co/blog/nvidia/nemotron-3-nano-efficient-open-intelligent-models) ·
[GLM-4.7-Flash](https://unsloth.ai/docs/models/tutorials/glm-4.7-flash) ·
[Gemma 4 26B-A4B](https://huggingface.co/google/gemma-4-26B-A4B) ·
[Devstral 2](https://mistral.ai/news/devstral-2-vibe-cli/) ·
[Laguna S/XS 2.1](https://poolside.ai/blog/introducing-laguna-s-2-1)

**Measured on 3090-class hardware:**
[Giles Thomas — Qwen3.6 35B MoE on RTX 3090](https://www.gilesthomas.com/2026/07/benchmarking-qwen-3-6-35b-moe-rtx-3090) ·
[thc1006 — spec decoding on RTX 3090 (19 configs)](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090) ·
[aminrj — Qwen3.6 on 24GB VRAM](https://aminrj.com/posts/llamacpp-qwen36-35b/) ·
[llmkube — llama.cpp vs vLLM concurrency bake-off](https://llmkube.com/blog/qwen3-6-27b-bakeoff)

**Architecture / KV cache:**
[kaitchup — KV cache of small MoEs](https://kaitchup.substack.com/p/the-kv-cache-of-small-moes-qwen3) ·
[Qwen3.6-35B-A3B architecture overview](https://huggingface.co/blog/EXDai/qwen36-35b-a3b-architecture-overview)

**llama.cpp primary:**
[server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) ·
[docs/speculative.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md) ·
[#22673 MTP](https://github.com/ggml-org/llama.cpp/pull/22673) ·
[#22838 parallel drafting](https://github.com/ggml-org/llama.cpp/pull/22838) ·
[#23269 MTP cleanup](https://github.com/ggml-org/llama.cpp/pull/23269) ·
[#23287 +7% MTP](https://github.com/ggml-org/llama.cpp/pull/23287) ·
[#11681 ctx÷parallel](https://github.com/ggml-org/llama.cpp/issues/11681) ·
[#22867 MTP+vision OOM](https://github.com/ggml-org/llama.cpp/issues/22867)

**Quantization:**
[localbench Gemma 4 31B KL-divergence](https://localbench.substack.com/p/gemma-4-31b-gguf-kl-divergence) ·
[localbench Qwen3.6 35B-A3B](https://localbench.substack.com/p/qwen-36-35b-a3b-gguf-quality-benchmark) ·
[arXiv:2504.04823 quantized reasoning (COLM 2025)](https://arxiv.org/abs/2504.04823) ·
[Unsloth Dynamic 2.0](https://unsloth.ai/docs/basics/unsloth-dynamic-2.0-ggufs)

**Benchmarks/leaderboards:**
[BFCL official (Gorilla)](https://gorilla.cs.berkeley.edu/leaderboard.html) ·
[BenchLM agent benchmarks](https://benchlm.ai/llm-agent-benchmarks) ·
[awesomeagents function-calling](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/) ·
[llm-stats BFCL v4](https://llm-stats.com/benchmarks/bfcl-v4)
