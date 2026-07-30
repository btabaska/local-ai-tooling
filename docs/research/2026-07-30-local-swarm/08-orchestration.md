# 08 — Multi-Agent Orchestration on ONE RTX 3090 Ti

Research date: **2026-07-30**. All claims sourced inline; anything I could not verify
against a live source is tagged **[unverified]**. Confidence tags: **[H]** high,
**[M]** medium, **[L]** low / extrapolated.

Rig under test (from this repo's `README.md` + `clients/README.md`):
i7-12700K · 64 GB RAM · **1× RTX 3090 Ti (24 GB)** · llama-swap + llama.cpp `llama-server`
behind LiteLLM at `https://llm.tabaska.us/v1`. Aliases: `coder` (Qwen3.6 35B-A3B MoE,
131k ctx), `coder-strong` (Qwen3.6 27B MTP, ~50 t/s, 98k ctx), `fast` (Qwen2.5-Coder 7B),
`utility` (Llama 3.2 3B). Hosts: **opencode**, **pi 0.82.x**, **Orca (Stably)**.
One big model resident at a time. `coder` needs ~23.3 GB → Orca must run `--disable-gpu`.

---

## 0. TL;DR — the four things that decide this

1. **Your binding constraint is KV-cache VRAM, not tokens/sec.** With `coder` occupying
   ~18–19 GB of a 24 GB card, you have roughly **4–5 GB of KV budget total, shared by all
   slots**. At q8_0 KV that is ~85–95k tokens of context *for the whole swarm*. A coding
   agent turn wants 25–40k. **That caps you at 2–3 real coding agents, 4 if you keep
   contexts under ~20k.** [M — math shown in §1, model dims **[unverified]**]
2. **llama.cpp scales concurrency badly compared to vLLM.** Measured aggregate throughput
   from concurrency 1→8 is **1.2×–1.9× for llama.cpp** vs **3.9×–5.4× for vLLM**
   ([dev.to benchmark, RTX 3090 24 GB, incl. Qwen3-Coder-30B-A3B](https://dev.to/sikamikanikobg/vllm-vs-llamacpp-vs-ollama-what-happens-when-your-model-doesnt-fit-in-24gb-vram-56eb)).
   So going from 1 agent to 8 agents makes each agent **~4× slower** to buy **~1.9×** total
   work. [H for the source; M for it generalising to your exact build]
3. **Locally, the multi-agent token multiplier converts directly into wall-clock.**
   Anthropic measures multi-agent systems at **~15× the tokens of chat** and agents at ~4×
   ([Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)).
   In the cloud that is a dollar cost you can pay to get latency back. On one GPU you have a
   **fixed ~0.4–0.7 M output tokens/hour ceiling**, so 15× tokens ≈ 15× GPU-hours, only
   ~1.9× of which batching gives back. The orchestrator+N-workers pattern is the *worst*
   fit for this rig. [H]
4. **Therefore: sequential spine, narrow parallel ribs.** Spec/plan/decompose runs
   single-threaded with fresh-context handoffs; implementation fans out to **2–3** worktree
   agents on disjoint module boundaries; verification is done by **compilers, type checkers,
   linters and tests — not by judge-LLMs**, because deterministic verifiers are free and
   LLM verifiers cost a full model pass you cannot afford. Full diagram in §5.

---

## 1. The binding constraint: KV-cache arithmetic

### 1.1 What llama.cpp actually does with slots (verified 2026-07-30)

From [`tools/server/README.md` @ master](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md):

| Flag | Documented behaviour (quoted) |
|---|---|
| `-np, --parallel` | "number of server slots (default: -1, -1 = auto)" |
| `-cb, --cont-batching` | "whether to enable continuous batching (a.k.a dynamic batching) **(default: enabled)**" |
| `-c, --ctx-size` | "size of the prompt context (default: 0, 0 = loaded from model)" — **context is a pool shared across slots**, not statically divided, when `--kv-unified` is on |
| `-kvu, --kv-unified` | "use single unified KV buffer shared across all sequences **(default: enabled if number of slots is auto)**" |
| `-b, --batch-size` | "logical maximum batch size (default: 2048)" |
| `-ub, --ubatch-size` | "physical maximum batch size (default: 512)" |
| `--cache-prompt` / `--no-cache-prompt` | prompt KV reuse across requests, **default enabled** |
| `--cache-reuse N` | "min chunk size to attempt reusing from the cache via KV shifting" (default 0 = off) |
| `-cram, --cache-ram N` | "maximum cache size in MiB" (default **8192**; `-1` unlimited, `0` off) — host-RAM spill for prompt caches |
| `-sps, --slot-prompt-similarity` | slot selection by prompt similarity, **default 0.10**, `0.0` disables |
| `--cache-type-k` / `-v` | f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1 — **default f16** |
| `--slot-save-path` | "path to save slot kv cache (default: disabled)" |
| `/slots` endpoint | on by default, disable with `--no-slots` |

Two consequences that matter enormously for a swarm:

- **`--slot-prompt-similarity` means prefix caching is per-slot, keyed by longest matching
  prefix.** The server routes an incoming request to the slot whose cached prompt best
  matches, *not* to any idle slot. If N agents share an identical 6k-token system prompt +
  AGENTS.md preamble, that prefix is materialised **once per slot**, i.e. N times, not once
  globally. There is no RadixAttention-style global prefix tree in llama.cpp. [H]
- **`--cache-ram` (default 8 GiB) is the swarm's best friend.** Evicted slot prompt states
  spill to host RAM instead of being recomputed. With 64 GB of RAM you should raise this
  aggressively (e.g. `--cache-ram 32768`) so that an agent returning after another agent
  stole its slot pays a RAM→VRAM copy instead of a 30k-token reprefill. [M — flag verified,
  the size recommendation is my extrapolation]

Contrast: **vLLM/SGLang do have automatic prefix caching (RadixAttention)** and scale
3.9×–5.4× to concurrency 8, but on a 24 GB card vLLM
"crashes with OutOfMemoryError consistently around 22.1–22.2 GB usage regardless of
quantization" ([same benchmark](https://dev.to/sikamikanikobg/vllm-vs-llamacpp-vs-ollama-what-happens-when-your-model-doesnt-fit-in-24gb-vram-56eb)),
whereas llama.cpp degrades gracefully. Given `coder` is tuned as a <1 GiB-headroom edge fit,
**switching the swarm backend to vLLM is not viable at this quant/context**. [M]

### 1.2 KV bytes per token

KV per token = `2 × n_layers × n_kv_heads × head_dim × bytes_per_element`.

Using Qwen3-30B-A3B-class dimensions (48 layers, 4 KV heads GQA, head_dim 128) as the
stand-in for `coder` — **[unverified: I could not confirm Qwen3.6 35B-A3B's exact head
config; treat the absolute numbers as ±30%]**:

`2 × 48 × 4 × 128 = 49,152` elements/token.

| KV type | Bytes/token | **Per 1k tokens** | Per 32k tokens | Per 131k tokens |
|---|---|---|---|---|
| f16 (default) | ~98 KB | **~98 MB** | ~3.1 GB | ~12.9 GB |
| q8_0 | ~52 KB | **~53 MB** | ~1.7 GB | ~6.9 GB |
| q4_0 | ~27 KB | **~28 MB** | ~0.9 GB | ~3.6 GB |

### 1.3 The slot/context table for a 24 GB card

Assume ~18.5 GB weights + ~0.8 GB compute buffers/graph → **~4.5 GB KV budget**.

| KV quant | Total KV tokens | n=1 | n=2 | n=3 | n=4 | n=6 | n=8 |
|---|---|---|---|---|---|---|---|
| f16 | ~46k | 46k | 23k | 15k | 11k | 7.6k | 5.7k |
| **q8_0** | **~85k** | 85k | **42k** | **28k** | **21k** | 14k | 10.6k |
| q4_0 | ~160k | 160k | 80k | 53k | 40k | 26k | 20k |

**Read this table as the answer to "how many agents".** A coding agent doing real work on a
mid-size repo runs 25–40k of context (repo map + open files + tool output + history).

- **q8_0 KV + n=2** → 42k/slot. Comfortable. ✅
- **q8_0 KV + n=3** → 28k/slot. Workable if you enforce aggressive context hygiene. ✅
- **q8_0 KV + n=4** → 21k/slot. Only with small, tightly scoped tasks and `/compact`-style
  discipline. ⚠️
- **n=6+** → sub-15k/slot. Agents will thrash context-shift and lose the plot. ❌

q4_0 KV buys you more slots but degrades long-context recall exactly where you need it
(tool-call fidelity, file paths). **[L — no 2026 benchmark found for q4 KV degradation on
coding agents specifically; treat as a hypothesis to measure.]**

> **Action:** run `coder` with `--cache-type-k q8_0 --cache-type-v q8_0 -np 3 -c <total>
> --cache-ram 32768 --cache-reuse 256`. Verify actual VRAM headroom before trusting the
> table above — the ~23.3 GB figure in `clients/README.md` implies the current config
> already spends most of the budget on a single big context.

---

## 2. Quantitative throughput model

### 2.1 Measured inputs

| Source | Measurement |
|---|---|
| [llama.cpp discussion #18030](https://github.com/ggml-org/llama.cpp/discussions/18030) (Dec 14–15 2025) | RTX 3090, Phi-4-mini-Q4_K_M, **128-token prompts**: batch 1 = 234.9 t/s → batch 8 = 675.2 t/s (2.9×) → batch 32 = 3048.6 t/s (13×) → saturates ~batch 128 at 3973 t/s. Prompt processing flat at ~6.6–7.2k t/s. |
| [dev.to 24 GB backend shootout](https://dev.to/sikamikanikobg/vllm-vs-llamacpp-vs-ollama-what-happens-when-your-model-doesnt-fit-in-24gb-vram-56eb) (RTX 3090, incl. Qwen3-Coder-30B-A3B) | concurrency 1→8: **llama.cpp 1.2×–1.9×**, vLLM 3.9×–5.4×, Ollama **0.57×** (regresses). |
| This repo (`opencode.json`, `clients/pi-models.json`) | `coder` is the default; `coder-strong` documented at ~50 t/s. Task brief states `coder` ≈ **100 t/s aggregate**. |

The two benchmarks disagree by an order of magnitude, and **the disagreement is the whole
story**: #18030 uses 128-token prompts on a 2.3 GB model — there is enormous spare compute
and spare VRAM, so batching is nearly free. Your workload is a ~19 GB model with 30k-token
prompts on a VRAM-saturated card, which is the dev.to regime. **Model the swarm on
1.2×–1.9×, not on 13×.** [H — this is the single most important calibration in this doc]

### 2.2 The model

Let `T(n)` = aggregate decode throughput at n concurrent agents, anchored at
`T(1) = 100 t/s` and interpolating the dev.to 1.9×-at-8 curve:

| n | T(n) aggregate | Per-agent decode | Warm turn (3k out, ~4k new prefill) | Cold turn (30k prefill) | Swarm turns/hr | Useful turns/hr after 30% coordination tax |
|---|---|---|---|---|---|---|
| 1 | 100 t/s | 100 t/s | **34 s** | 64 s | 106 | 106 |
| 2 | 135 t/s | 67 t/s | **48 s** | 82 s | 150 | 105 |
| 3 | 155 t/s | 52 t/s | **62 s** | 106 s | 174 | 122 |
| 4 | 170 t/s | 43 t/s | **75 s** | 132 s | 192 | 134 |
| 6 | 180 t/s | 30 t/s | **104 s** | 194 s | 208 | 145 |
| 8 | 190 t/s | 24 t/s | **130 s** | 254 s | 221 | 155 |

Assumptions: agent turn = ~30k input / ~3k output; warm turn benefits from per-slot prefix
cache so only ~4k tokens are new; prefill ~1000 t/s aggregate for a 3B-active MoE at 24 GB
**[L — prefill rate is extrapolated, not measured on your build]**; "coordination tax" is my
own 30% haircut for orchestrator turns, re-planning, duplicated work and merge repair, and
is **[L]**.

### 2.3 What the model says

- **Total output-token budget is ~0.36 M/hr at n=1 and ~0.68 M/hr at n=8.** That is the hard
  physical envelope of this rig. Everything else is allocation policy.
- **Aggregate turns/hour is nearly flat from n=3 onward** (174 → 221, i.e. +27% for 2.7× the
  agents), while **per-agent latency more than doubles** (62 s → 130 s).
- The KV table in §1.3 caps you at n=3 anyway with real contexts. **The throughput curve and
  the VRAM curve agree on the same answer: 2–3 workers.** [M]
- **Latency matters for correctness, not just comfort.** A 130 s turn means a 20-turn agent
  task takes 43 minutes; drift, stale assumptions and duplicated work all scale with that
  window. Slower agents are not just slower — they are worse.

### 2.4 The 15× multiplier, re-denominated

Anthropic: "agents typically use about 4× more tokens than chat interactions, and
**multi-agent systems use about 15× more tokens than chats**" and
"**token usage by itself explains 80% of the variance**"
([source](https://www.anthropic.com/engineering/multi-agent-research-system)).

On a cloud budget, 15× is a line item. Here, 15× tokens on a fixed pipe = 15× GPU-seconds,
of which batching returns at most 1.9×. **Net wall-clock penalty of naive orchestrator+N
workers on this rig: ~8×.** That is the quantitative reason the pattern loses locally even
though it wins in Anthropic's setting. [M — arithmetic is mine, inputs are sourced]

### 2.5 LiteLLM is not the bottleneck, but check one setting

[LiteLLM config settings](https://docs.litellm.ai/docs/proxy/config_settings) documents
`general_settings.max_parallel_requests` (per deployment),
`general_settings.global_max_parallel_requests` (proxy-wide), and
`router_settings.default_max_parallel_requests`. Critically:
**`NUM_WORKERS` defaults to 1** and the docs "strongly recommend setting NUM_WORKERS to the
number of vCPUs available". With a 12700K (20 threads) still at the default, the proxy is a
single uvicorn worker in front of your GPU. [H]

> **Action:** set `NUM_WORKERS=8` and — more importantly — set
> `global_max_parallel_requests` to your slot count (3). This turns LiteLLM into the swarm's
> **admission-control valve**: a runaway orchestrator that spawns 12 agents queues at the
> gateway instead of thrashing llama.cpp's slot allocator. This is the cheapest safety
> mechanism available to you.

---

## 3. Tool survey — evaluated against the single-GPU constraint

Legend for **Local endpoint**: ✅ = documented custom OpenAI-compatible base URL;
🟡 = works via the underlying agent's own config, not the orchestrator's;
❌ = vendor auth assumed.

### 3.1 Agent-native subagent systems

| Tool | Version / date verified | Local endpoint | Parallelism assumption | Isolation | Licence | Verdict for this rig |
|---|---|---|---|---|---|---|
| **Claude Code subagents** | docs live 2026-07-30; `isolation: worktree` frontmatter supported ([docs](https://code.claude.com/docs/en/sub-agents), [worktrees](https://code.claude.com/docs/en/worktrees)) | ❌ (Anthropic auth) | Own context window per subagent, results summarised back; foreground/background configurable | Own context; optional per-subagent git worktree | Proprietary | **Not usable** — no local endpoint. Steal the *conventions*, not the tool. |
| **Claude Code Agent Teams** | **experimental, off by default**, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`; described "as of v2.1.178", panel behaviour changes through v2.1.207/2.1.199 ([docs](https://code.claude.com/docs/en/agent-teams)) | ❌ | Lead + teammates, **peer-to-peer mailbox** (`~/.claude/teams/{team}/inboxes/{agent}.json`), shared task list with **file-locking task claim**; docs recommend **3–5 teammates**, "5–6 tasks per teammate" | Full separate Claude Code sessions, own context each | Proprietary | Not usable directly, but this is **the best-documented reference architecture in 2026** — copy the mailbox + shared-task-list + file-lock design. |
| **Claude Code background agents (`claude agents`, `/bg`)** | live 2026-07-30 ([docs](https://code.claude.com/docs/en/agent-view)) | ❌ | No hard concurrency limit, quota-gated; "Running 10 agents in parallel uses quota ~10x faster" | **Auto git worktree under `.claude/worktrees/`**, auto-commit + draft PR, never pushes to main | Proprietary | Reference only. The auto-PR-per-session merge model is worth copying. |
| **opencode** subagents | docs live ([opencode.ai/docs/agents](https://opencode.ai/docs/agents/)) | ✅ **already wired in this repo** (`opencode.json` → `litellm/*`) | Built-in subagents: `general`, `explore`, `scout`; invoked by Task tool or `@mention`; **docs do not promise concurrent subagent execution** — only that `general` is "useful to run multiple units of work in parallel" | Subagents get **child sessions**; per-agent `model`, `prompt`, `permission` | MIT | **Primary intra-workspace decomposition layer.** Per-agent model override lets you route cheap roles to `fast`… but see §3.5 caveat. |
| **pi** (`@earendil-works/pi-coding-agent`, pi.dev) | 0.82.x validated in this repo (`clients/pi-models.json`) | ✅ custom providers + `models.json`/`auth.json`; `compat.supportsDeveloperRole=false` + `supportsReasoningEffort=false` **required** for llama.cpp-style servers | **No subagent/delegation system documented** ([pi docs index](https://pi.dev/docs/)) | Sessions are JSONL with **branching and tree navigation**; RPC mode + JSON event stream mode for programmatic driving | — | **Best headless worker.** No orchestration of its own, which is *fine* — Orca supplies that. RPC/JSON-event mode is the cleanest automation surface of the three. |

### 3.2 Standalone orchestrators (worktree/session runners)

| Tool | Version / status verified 2026-07-30 | Local endpoint | Parallelism | Isolation | Licence | Verdict |
|---|---|---|---|---|---|---|
| **Orca (stablyai/orca)** | **v1.4.159**; Android APK 0.0.36; "works with **any CLI agent**", 30+ agents incl. Codex/Claude Code/OpenCode/**Pi**/Cline/Goose ([repo](https://github.com/stablyai/orca), [worktree docs](https://www.onorca.dev/docs/model/worktrees)) | 🟡 **effectively ✅** — model backend is configured *per agent*, not in Orca; this repo already has `PI_MODEL=litellm/coder` + `LITELLM_API_KEY` inherited via `~/.bash_profile` | User-driven; "fan one prompt across five agents… compare and merge the winner"; **no documented concurrency cap** | **Worktree-native**: every task gets `git worktree add` from a chosen start-from ref; branch name derived from workspace name; delete removes dir + branch | **MIT** | ✅ **Winner for this rig.** Agent-agnostic + worktree-native + MIT + already deployed. Must run `--disable-gpu` (Electron Chromium spikes to ~8 GB VRAM per `clients/README.md`). |
| **Conductor** | v0.77.2 ([conductor.build](https://conductor.build/)) | ❌ / undocumented | Parallel isolated workspaces | Workspaces (worktree-style) | Proprietary, **macOS-only** | ❌ Wrong OS (rig is CachyOS), no local-endpoint story. |
| **Crystal (stravu/crystal)** | **deprecated February 2026**; successor **Nimbalyst** ([Augment survey](https://www.augmentcode.com/tools/open-source-agent-orchestrators)) | ❌ | Parallel sessions | Worktree per session | — | ❌ Dead. Do not adopt. |
| **vibe-kanban (BloopAI)** | **sunsetting** (announcement linked from repo); 27.6k★, Apache-2.0; 10+ executors incl. OpenCode ([repo](https://github.com/BloopAI/vibe-kanban)) | undocumented | Kanban-driven | Worktree per workspace, `DISABLE_WORKTREE_CLEANUP` env | Apache-2.0 | ❌ Sunsetting. Mine it for the kanban-as-shared-task-list convention only. |
| **claude-squad (smtg-ai)** | 8.2k★, 219 commits, AGPL-3.0; supports Claude Code, Codex, Gemini, **Aider** with e.g. `aider --model ollama_chat/...` ([repo](https://github.com/smtg-ai/claude-squad)) | 🟡 via the wrapped agent's own flags | tmux sessions, manual review before apply | **tmux + git worktree** | AGPL-3.0 | 🟡 Viable fallback if you want a pure-TUI, no-Electron path. AGPL may matter to you. |
| **container-use / `cu` (dagger)** | 3.9k★, Apache-2.0, **marked experimental**, 49 open issues ([repo](https://github.com/dagger/container-use)) | 🟡 "works with any agent, model, or infrastructure" (unspecified) | MCP server; agent-driven | **Fresh container + own git branch per agent** — strongest isolation on the list | Apache-2.0 | 🟡 Best isolation, but containers add RAM pressure and you already have worktrees. Consider only if agents run untrusted build steps. |
| **uzi (devflowinc)** | 580★, MIT, active ([repo](https://github.com/devflowinc/uzi)) | undocumented | `--agents claude:2,codex:1`; **explicitly designed for "large numbers" of agents** | worktrees + tmux + auto port assignment from a range | MIT | 🟡 The **port-range auto-assignment** is a genuinely useful idea to copy (parallel dev servers collide otherwise). The "large numbers" premise is exactly wrong for one GPU. |
| **Composio agent-orchestrator** | v0.3.0 ([survey](https://www.augmentcode.com/tools/open-source-agent-orchestrators)) | undocumented | worktrees + tmux, autonomous PR lifecycle | worktree + tmux | — | 🟡 Unverified depth; the auto-PR lifecycle is the interesting bit. |
| **Emdash (YC W26)**, **Baton**, **Code Conductor**, **microsoft/conductor v0.1.1**, **Bernstein**, **Agent Kanban** | all catalogued in the [Augment 2026 survey](https://www.augmentcode.com/tools/open-source-agent-orchestrators) | mostly undocumented | worktree-per-task variants | worktrees | mixed | 🟡 Same category as Orca but smaller/newer. **Bernstein**'s "deterministic scheduling + task-graph + pre-merge 'Janitor' verification" and **Baton**'s "poll GitHub Issues → dispatch → reconcile" loop are the two patterns worth stealing. |

### 3.3 Agent frameworks (build-your-own orchestration)

| Framework | Status verified 2026-07-30 | Local endpoint | Fit |
|---|---|---|---|
| **Microsoft Agent Framework** | **GA**, 12.5k★, MIT; migration guides *from* AutoGen *and* Semantic Kernel; "sequential, concurrent, handoff, and group collaboration patterns"; **durable execution** via Durable Task hosting / Durable Agents ([repo](https://github.com/microsoft/agent-framework)) | not explicitly documented for OpenAI-compatible custom base URLs **[unverified]** | 🟡 The **durability/restartability/observability** story is the best in class and directly addresses your overnight-run requirement. Heavyweight for a homelab. |
| **AutoGen / AG2** | Superseded in practice by MAF (migration guide exists) | — | ❌ Legacy. Cognition's critique named AutoGen specifically. |
| **OpenHands (All-Hands-AI)** | **v1.7.2**, 82.6k★, MIT, beta; "Bring your own model" + LLM Profiles; "Self-host your way — run agents locally, in Docker, on VMs" ([repo](https://github.com/All-Hands-AI/OpenHands)) | 🟡 BYO-model documented, LiteLLM backing **[unverified in 2026 docs]** | 🟡 Strong self-host story, but it is a *whole agent*, not an orchestrator — it would replace opencode/pi rather than coordinate them. |
| **SWE-agent**, **CrewAI**, **LangGraph**, **Agno** (41.5k★, Apache-2.0), **Mastra**, **Google ADK** | all alive; Agno/LangGraph/CrewAI all support custom base URLs in general **[unverified against 2026 docs in this pass]** | 🟡 | ❌ for your goal. These orchestrate *LLM calls*, not *coding agents with filesystem+git+tools*. You would be rebuilding opencode/pi badly. |
| **Temporal-based agent runners** | durable-execution pattern; MAF ships the same idea via Durable Task | n/a | 🟡 Conceptually right for overnight runs (§8) but massive infrastructure for a homelab. Use a file-based checkpoint instead. |

### 3.4 Protocols

- **A2A (Agent2Agent)** — **v1.0 released**, governed by the **Linux Foundation**, donated by
  Google, TSC with AWS/Cisco/Google/IBM/Microsoft/Salesforce/SAP/ServiceNow
  ([a2a-protocol.org](https://a2a-protocol.org/latest/)). Explicitly **"not a sub-agent or
  tool-call protocol"**; it targets *cross-system* agent collaboration.
  **Verdict: irrelevant to a single-host swarm.** Adopting A2A here buys you an HTTP hop and
  an agent card for agents that share a filesystem. Skip. [H]
- **MCP** — remains the agent↔tool layer, complementary to A2A per the same source. You are
  already using it (`context7`, `serena` in `opencode.json`, `fleet-mcp`).
  **MCP is the right composition surface for your swarm**: expose the task queue, the lock
  registry and the spec store as MCP tools, and every agent (opencode, pi, anything Orca
  runs) gets them for free without protocol work. [M — my recommendation, not a sourced claim]

### 3.5 ⚠️ The trap: per-agent model routing does *not* work here

opencode and Orca both let you assign a different model per agent. On a normal rig you would
route the reviewer to `fast` and the implementer to `coder`. **On this rig that forces a
llama-swap model swap** — `coder` alone needs ~23.3 GB and there is no room for a second
resident model (README: "one big model at a time + CPU embedder"). A swarm that alternates
`coder` and `fast` will spend its night unloading and reloading 19 GB of weights.

**Rule: every agent in a concurrent wave must use the same alias.** Model diversity is only
available *between* sequential phases, and even then each switch costs a full model load.
[H — follows directly from this repo's own documented constraints]

---

## 4. Which topology actually wins — the evidence

### 4.1 Orchestrator + N workers (Anthropic pattern)

- **What it's for:** Anthropic's own post is explicit that this pattern targets *research*,
  and lists where it does **not** work: "most coding tasks (fewer parallelizable
  components)", tasks "requiring all agents to share the same context", and tasks with "many
  dependencies between agents"
  ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). Coding is
  named as a counter-indication *by the authors of the pattern*. [H]
- **Cost:** 15× tokens → ~8× wall-clock on this rig (§2.4).
- **Verdict:** ❌ as the primary structure. ✅ in one narrow form — **read-only research
  fan-out** (see §5).

### 4.2 Sequential pipeline with fresh-context handoffs

- Cognition's [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)
  gives the two principles verbatim: **"Share context, and share full agent traces, not just
  individual messages"** and **"Actions carry implicit decisions, and conflicting decisions
  carry bad results"**, with the Flappy Bird failure (one subagent builds Super Mario pipes)
  as the canonical illustration. Their recommendation: "just use a single-threaded linear
  agent, where the context is continuous." [H]
- Roo Code's Orchestrator/Boomerang mode implements this literally: subtasks have "separate
  conversation histories", information flows **down via the spawn prompt and up via a
  completion summary only**, execution is **sequential** (parent pauses, resumes on summary),
  and the docs state this design prevents **"context poisoning"**
  ([Roo docs](https://roocodeinc.github.io/Roo-Code/features/boomerang-tasks)). [H]
- **Verdict:** ✅ **This is the spine.** It costs ~1× tokens, needs 1 slot, and is the
  pattern with the strongest 2026 endorsement.

### 4.3 Map-reduce over independent files/modules

- Anthropic's own guidance for teams: **"Avoid file conflicts: two teammates editing the same
  file leads to overwrites. Break the work so each teammate owns a different set of files."**
  and **"Start with 3–5 teammates"**, **"5–6 tasks per teammate"**, "Three focused teammates
  often outperform five scattered ones"
  ([agent teams docs](https://code.claude.com/docs/en/agent-teams)). [H]
- Addy Osmani (2026-03-26): **"Don't run more agents than you can meaningfully review. 3–5 is
  the sweet spot"**; hierarchical decomposition (feature leads spawn specialists) gives "3×
  deeper decomposition without exploding anyone's context window"
  ([The Code Agent Orchestra](https://addyosmani.com/blog/code-agent-orchestra/)). [H]
- **Verdict:** ✅ **This is the rib.** But 3–5 is a *cloud* number. Your VRAM says 2–3.

### 4.4 Verifier/critic loops, self-consistency, best-of-N with a judge

- Osmani: **"The bottleneck is no longer generation. It's verification… knowing with
  confidence whether that output is correct is the hard part."** [H]
- **But the economics invert locally.** Best-of-N with an LLM judge costs N+1 full model
  passes on a pipe that produces 0.36–0.68 M tokens/hour. Self-consistency multiplies the
  same way. An LLM critic pass on a 3k-token diff with 30k of context is a full agent turn.
- **Verdict:** ❌ best-of-N, ❌ self-consistency, ❌ LLM-judge gates.
  ✅ **deterministic verifiers**: `tsc`/`mypy`, the test suite, the linter, the build. These
  cost CPU, which you have 20 threads of and which is otherwise idle while the GPU decodes.
  **On a single-GPU rig, moving verification from the model to the toolchain is the single
  highest-leverage architectural decision.** [M — the reasoning is mine; the "verification is
  the bottleneck" premise is sourced]

### 4.5 Hierarchical decomposition with an on-disk spec as shared memory

- Anthropic: the lead "saves [the plan] to Memory to persist the context, since if the
  context window exceeds 200,000 tokens it will be truncated", and agents "resume from where
  the agent was when the errors occurred". [H]
- Ghuntley's **Ralph loop** (`while :; do cat PROMPT.md | claude-code ; done`) is the
  extreme form: *all* state lives on disk in `PROMPT.md`, `fix_plan.md`, `specs/`,
  `AGENT.md`, deterministically re-read each iteration. Reported: a compiler for a language
  outside the model's training data, "90% done" for greenfield, one engineer delivering a
  $50k-contract MVP for $297 ([ghuntley.com/ralph](https://ghuntley.com/ralph/), 2025-07-14).
  Explicitly **not recommended for existing codebases**. [H for the source; **[unverified]**
  for the $297 figure's provenance]
- **github/spec-kit** (124.6k★, MIT) has standardised the artifact set:
  `constitution → specify → plan → tasks → implement`, producing `spec.md`, `plan.md`,
  `tasks.md` under `.specify/` + `specs/`, supporting 30+ agents
  ([repo](https://github.com/github/spec-kit)). [H]
- **Verdict:** ✅✅ **This is the shared memory.** It is free (disk), it is diffable, it
  survives crashes, and it is the only "message bus" that costs zero tokens to maintain.

### 4.6 Documented failure modes to design against

| Failure | Evidence |
|---|---|
| **Conflicting implicit decisions** | Cognition's Flappy Bird / Super Mario pipes example. [H] |
| **Context rot** — non-uniform degradation with input length | Chroma, 2025-07-14, 18 models: performance degrades with length even on trivial tasks; "shuffled haystacks show **improved** performance" vs coherent ones; LongMemEval shows big gaps between ~300-token focused and ~113k full prompts; repeated-word task degrades from **500–750 words**; Claude Opus 4 refusals from **2,500 words** ([Chroma](https://www.trychroma.com/research/context-rot)). [H] |
| **14 distinct MAS failure modes in 3 categories** (system design, inter-agent misalignment, task verification), 150 traces, κ=0.88; conclusion that "identified failures require more sophisticated solutions" — i.e. **better prompts do not fix it** | [MAST, arXiv:2503.13657](https://arxiv.org/abs/2503.13657). [H] |
| **Loop entrapment** | Osmani: agents "loop endlessly trying the same broken approach"; mitigation `MAX_ITERATIONS=8` + mandatory reflection prompts; kill criteria "reassign after 3+ stuck iterations on the same error". [H] |
| **Specification drift** | Osmani: "ambiguous requirements propagate through dozens of parallel runs, each going slightly wrong in a slightly different direction". [H] |
| **Cost compounding** | 15× baseline "compounds when something misbehaves: a subagent that recursively spawns more subagents… can multiply a single query's cost by another 10× or more" ([Nadir](https://getnadir.com/blog/multi-agent-orchestration-15x-token-cost/)). [M — secondary source] |
| **Task-status lag blocking dependents; leads shutting down early; teammates stopping on errors instead of recovering; no session resumption for in-process teammates** | All four listed as *current known limitations* of Claude Code agent teams — i.e. the best-funded implementation in the world still has them. [H] |
| **LLM-generated AGENTS.md is actively harmful** | Osmani cites ~**−3% success rate and +20% cost** for LLM-generated AGENTS.md vs **+4%** for human-curated. [M — Osmani's citation, primary study not verified in this pass] |

### 4.7 The 2026 consensus, stated plainly

The field converged on: **a single orchestrator owns continuous context and spawns ephemeral,
mostly read-only subagents that return compressed summaries; parallel *writer* swarms remain
fragile.** Writes stay single-threaded; extra agents contribute *intelligence*, not *actions*
(synthesised from the Cognition/Anthropic/Roo/Osmani sources above). The one genuine 2026
advance beyond this is **peer-to-peer teammate messaging + a shared task list with file-lock
claiming** (Claude Code agent teams), which fixes the "lead becomes a bottleneck" problem —
and Anthropic still ships it **experimental and off by default**. [M — "consensus" is an
interpretation; each component claim is sourced]

---

## 5. Recommended topology for THIS rig

**Name: sequential spine, narrow parallel ribs, deterministic gates.**

```
                        ┌──────────────────────────────────────────────┐
   YOU (human)  ───────►│  PHASE 0-2 : THE SPINE  (n=1 slot, ~1x cost) │
                        │  single-threaded, fresh-context handoffs      │
                        └──────────────────────────────────────────────┘
                                          │
  ┌───────────────────────────────────────┴───────────────────────────────────┐
  │  0. SPEC     pi/opencode, plan-mode, model=coder-strong                    │
  │              writes  specs/NNN-feature/spec.md   (human reviews & signs)   │
  │                              │  fresh context                              │
  │  1. PLAN     writes  specs/NNN-feature/plan.md + adr/NNNN-*.md             │
  │                              │  fresh context                              │
  │  2. DECOMPOSE writes tasks.yaml : a DAG of tasks, each with                │
  │               id · owns[globs] · deps[] · acceptance[shell cmds] · budget  │
  │               INVARIANT: owns[] sets are pairwise DISJOINT                 │
  └───────────────────────────────────────┬───────────────────────────────────┘
                                          │
                        ┌─────────────────▼─────────────────┐
                        │  DISPATCHER  (Orca / small script) │
                        │  WIP limit = 2..3  (hard)          │
                        │  picks ready tasks (deps met,      │
                        │  no owns[] overlap with running)   │
                        └─────────────────┬─────────────────┘
              ┌──────────────────┬────────┴────────┬──────────────────┐
              ▼                  ▼                 ▼                  ▼
      ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   (idle - do NOT
      │  RIB A        │  │  RIB B        │  │  RIB C        │    fill this slot)
      │ Orca worktree │  │ Orca worktree │  │ Orca worktree │
      │ .wt/task-a    │  │ .wt/task-b    │  │ .wt/task-c    │
      │ pi/opencode   │  │ pi/opencode   │  │ pi/opencode   │
      │ model=coder   │  │ model=coder   │  │ model=coder   │   ← SAME alias.
      │ ctx <= 28k    │  │ ctx <= 28k    │  │ ctx <= 28k    │     no swapping.
      └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
              │  each rib loops: read spec+plan+its task → edit ONLY its owns[]
              │  → run its own acceptance[] locally → commit → repeat
              ▼                  ▼                 ▼
      ╔═══════════════════════════════════════════════════════╗
      ║  DETERMINISTIC GATE   (CPU only - FREE, no GPU tokens) ║
      ║  build · typecheck · lint · unit tests · rib's         ║
      ║  acceptance[] commands.  FAIL ⇒ bounce back to the rib ║
      ║  with the raw error, iteration counter +1              ║
      ╚═══════════════════════════════════════════════════════╝
                                 │ pass
                                 ▼
                  ┌──────────────────────────────┐
                  │  INTEGRATOR  (n=1, serialized)│   ← the "single writer"
                  │  merge ribs into integration  │
                  │  branch one at a time, rerun  │
                  │  FULL suite after each merge  │
                  │  conflict ⇒ it fixes, not ribs│
                  └──────────────┬───────────────┘
                                 ▼
              ┌──────────────────────────────────────────┐
              │  REVIEW  (n=1, fresh ctx, model=coder)    │
              │  reads the DIFF ONLY + spec.md.           │
              │  writes review.md; findings become NEW    │
              │  tasks in tasks.yaml, never inline fixes  │
              └──────────────────┬───────────────────────┘
                                 ▼
                   loop to DISPATCHER until tasks.yaml drains
                                 │
                                 ▼
                        human review / PR / merge to main


  ── ORTHOGONAL, CHEAP, AND ALLOWED AT HIGHER FAN-OUT ─────────────────────────
  READ-ONLY RESEARCH FAN-OUT: opencode `explore`/`scout` subagents, or a
  4-6 way fan-out during PHASE 0/1 only. These are short (2-6k ctx), produce
  small summaries, and are the ONE place Anthropic's orchestrator+workers
  pattern earns its keep on a single GPU. They must not write code.
```

**Why this shape:**

- Slots 1–3 are the ribs. The spine, integrator and reviewer each run when the ribs are
  *not* running, so peak concurrency never exceeds 3. That matches both the §1.3 VRAM table
  and the §2.2 throughput knee.
- Writes are single-threaded *per file* (disjoint `owns[]`) and single-threaded *globally* at
  the integrator — satisfying Cognition's principle #2 without giving up parallelism where it
  is genuinely independent.
- All cross-agent communication is **files on disk**, so it costs zero GPU tokens, survives
  crashes, and is diffable by you in the morning.
- Verification is CPU. Your 12700K is otherwise idle during decode.

---

## 6. Git worktree parallelism and merge strategy

### 6.1 What the 2026 tooling agrees on

- **Worktree per task, branch derived from task name** — Orca, Claude Code, claude-squad,
  uzi, vibe-kanban, container-use all converge on this. Orca: "every task gets its own
  on-disk copy of the repo via `git worktree`"; "Deleting a worktree removes both the
  directory and the branch (with confirmation)"
  ([Orca worktree docs](https://www.onorca.dev/docs/model/worktrees)). [H]
- **Gitignored files must be copied in.** Claude Code standardised a `.worktreeinclude` file
  using `.gitignore` syntax; "Only files that match a pattern **and are also gitignored** are
  copied". Adopt this convention verbatim — it is exactly what you need for `.env` files
  carrying `LITELLM_API_KEY` into each worktree
  ([docs](https://code.claude.com/docs/en/worktrees)). [H]
- **Base-ref choice is a real decision.** Claude Code exposes `worktree.baseRef`:
  `"fresh"` (branch from remote default, clean tree) vs `"head"` (carry your unpushed work).
  Orca calls the same thing "start-from ref" (base ref / branch / SHA / remote branch).
  **For a swarm building one feature, use `head`-equivalent** so ribs share the same
  in-progress base; for independent modules use `fresh`. [H]
- **Lock running worktrees.** Claude Code runs `git worktree lock` while an agent is running
  so concurrent cleanup can't remove it, and releases on finish; a killed session's lock is
  swept. Copy this — an overnight sweep that deletes a live agent's worktree is a very
  expensive bug. [H]
- **Port collisions are a real failure mode.** uzi auto-assigns ports from a configured
  range; Emdash injects `$EMDASH_PORT` per task. If your ribs run dev servers, allocate
  ports deterministically from the task id. [H]
- **What worktrees do NOT solve:** "git worktree only provides low-level workspace isolation
  and does not solve task decomposition, dependency tracking, semantic conflicts, or merge
  selection" (2026 survey summary). Two agents can produce trees that merge cleanly with git
  and are semantically contradictory. [M — secondary source, but obviously true]

### 6.2 Merge/integration strategy for this rig

1. **Prevent, don't resolve.** The `owns[]`-disjointness invariant in `tasks.yaml` is the
   primary conflict-prevention mechanism. Textual conflicts should be near-zero; if you see
   them, the decomposition was wrong — fix `tasks.yaml`, not the merge.
2. **Serialize integration.** Merge one rib at a time into an `integration/<feature>` branch,
   running the **full** suite after each merge (not just the rib's own acceptance commands).
   This is Bernstein's "Janitor" idea and Claude Code's "single writer" in effect.
3. **The integrator owns conflict repair, not the ribs.** A rib asked to resolve a conflict
   must read the other rib's code, which blows its context and re-creates the exact
   fragmentation Cognition warns about.
4. **Shared-file changes are their own task.** If two modules need the same interface file,
   that file is a **task with a dependency**, executed before both — never concurrently.
5. **Draft PR per rib is optional but useful.** Claude Code's background agents "commit, push
   its own branch, and open a draft pull request without stopping to ask… never push to
   `main`/`master` or force-push". With Forgejo on the mini you can get the same audit trail
   for free. [H for the pattern]

---

## 7. Shared state between agents — concrete conventions

### 7.1 Layout

```
repo/
├─ AGENTS.md                     # HUMAN-CURATED. see §4.6: LLM-generated ones
│                                # measured ~-3% success / +20% cost.
├─ .worktreeinclude              # gitignore-syntax; copies .env into each worktree
├─ .swarm/                       # gitignored, machine state
│  ├─ tasks.yaml                 # THE task DAG - single source of truth
│  ├─ locks/                     # one file per claimed task, O_EXCL created
│  │   └─ T014.lock              # {agent, pid, worktree, started_at, heartbeat}
│  ├─ inbox/<agent>.jsonl        # append-only mailbox (Claude Code teams convention)
│  ├─ runs/<run-id>/
│  │   ├─ budget.json            # tokens_used, turns_used, wall_clock_s, caps
│  │   ├─ events.jsonl           # every dispatch/complete/fail/timeout
│  │   └─ <task>/transcript.jsonl
│  └─ ports.json                 # task-id -> dev-server port (uzi convention)
├─ specs/
│  └─ 014-billing/
│     ├─ spec.md                 # WHAT + acceptance criteria (human-signed)
│     ├─ plan.md                 # HOW: interfaces, file map, sequencing
│     ├─ tasks.md                # human-readable rendering of tasks.yaml
│     └─ review.md               # findings; each becomes a new task
├─ docs/adr/NNNN-*.md            # decisions that outlive the feature
└─ .claude/worktrees/  (or .orca/) # gitignored; one worktree per task
```

This is deliberately close to
[github/spec-kit](https://github.com/github/spec-kit)'s `spec.md`/`plan.md`/`tasks.md` triple
(124.6k★, MIT, 30+ agents) so that any agent already trained on the convention slots in. [H]

### 7.2 `tasks.yaml` — the one file that does the coordination

```yaml
run: 2026-07-30-billing
model: coder                     # ONE alias for the whole wave. see §3.5.
wip_limit: 3                     # == llama.cpp -np AND litellm global_max_parallel_requests
tasks:
  - id: T001
    title: "Define billing domain types"
    owns: ["src/billing/types.ts"]            # pairwise DISJOINT across concurrent tasks
    deps: []
    acceptance: ["pnpm tsc --noEmit"]
    max_iterations: 8                          # Osmani's MAX_ITERATIONS=8
    max_turns: 25
    timeout_s: 2400
  - id: T014
    title: "Invoice PDF renderer"
    owns: ["src/billing/pdf/**", "test/billing/pdf/**"]
    deps: [T001]
    acceptance: ["pnpm vitest run test/billing/pdf", "pnpm lint src/billing/pdf"]
    max_iterations: 8
    max_turns: 25
    timeout_s: 3600
```

**Rules the dispatcher enforces (not the agents — agents cannot be trusted with invariants):**

1. A task is *ready* iff all `deps` are `done` **and** its `owns[]` globs do not intersect any
   running task's `owns[]`.
2. Claiming is `open(O_CREAT|O_EXCL)` on `.swarm/locks/<id>.lock`. This is exactly what
   Anthropic ships: "Task claiming uses **file locking** to prevent race conditions when
   multiple teammates try to claim the same task simultaneously"
   ([agent teams docs](https://code.claude.com/docs/en/agent-teams)). [H]
3. Never dispatch more than `wip_limit`. Enforce it a second time at LiteLLM
   (`global_max_parallel_requests`) so a bug in the dispatcher cannot thrash the GPU.
4. A lock with a heartbeat older than N minutes is reaped and the task requeued (Claude Code
   sweeps stale `git worktree lock`s the same way; [docs](https://code.claude.com/docs/en/worktrees)).

### 7.3 Preventing two agents editing the same file — layered

| Layer | Mechanism | Strength |
|---|---|---|
| 1. Decomposition | `owns[]` disjointness invariant, checked by the dispatcher | Prevents the situation |
| 2. Filesystem | separate git worktree per task | Makes it *physically impossible* mid-flight |
| 3. Scheduling | dispatcher refuses overlapping `owns[]` | Prevents concurrent claims |
| 4. Agent prompt | "you may only edit files matching `owns[]`; anything else is a task for the integrator" | Weakest — belt and braces only |
| 5. Hook | pre-edit hook rejects writes outside `owns[]` | Deterministic, cheap. **Do this.** |

Anthropic's own advice remains the blunt version: **"Two teammates editing the same file
leads to overwrites. Break the work so each teammate owns a different set of files."** [H]

### 7.4 Message passing

Use it sparingly. The 2026 evidence is that peer messaging helps for *debate/review* and
hurts for *implementation*. Concretely:

- ✅ Allow: rib → integrator "I changed the shape of `Invoice`, T021 will need updating."
- ❌ Forbid: rib ↔ rib negotiation about design. That is what `plan.md` and the ADRs are for.
- Mailbox format: append-only JSONL at `.swarm/inbox/<agent>.jsonl`, mirroring
  `~/.claude/teams/{team}/inboxes/{agent}.json`. Note Anthropic's bug history here — before
  v2.1.207 a single malformed entry blocked delivery and error-looped once per second.
  **Validate every entry on read and drop bad ones.** [H]

---

## 8. Reliability engineering for overnight unattended runs

### 8.1 Checkpointing and resumability

- **All durable state on disk, none in agent context.** This is the Ralph insight: the loop is
  stateless; `fix_plan.md` / `tasks.yaml` *is* the memory
  ([ghuntley.com/ralph](https://ghuntley.com/ralph/)). It is also Anthropic's: the lead
  "saves [the plan] to Memory to persist the context, since if the context window exceeds
  200,000 tokens it will be truncated", and agents "resume from where the agent was when the
  errors occurred". [H]
- **Commit after every green gate.** A worktree with committed work survives a crash; an
  uncommitted one does not. Claude Code's cleanup sweep explicitly "skips a worktree that
  still holds work: changed or untracked files, or unpushed commits" — build the same rule.
- **pi's session model is your friend**: JSONL sessions with "branching and tree navigation"
  ([pi docs](https://pi.dev/docs/)), plus **RPC mode / JSON event stream mode** for
  programmatic drive. That is the cleanest resumable-worker substrate you have.
  opencode's child sessions are the equivalent. [H]
- **Known gap to design around:** Claude Code agent teams currently have **"No session
  resumption with in-process teammates"** — `/resume` and `/rewind` don't restore them. If
  the best-funded implementation can't resume teammates, don't build your night run assuming
  in-process resumption. Make every rib restartable from `tasks.yaml` + git. [H]

### 8.2 Failure detection, timeouts, loop detection

| Control | Setting | Source / rationale |
|---|---|---|
| Iteration cap | `MAX_ITERATIONS=8` per task with a mandatory reflection prompt at the cap | Osmani, explicit anti-loop recommendation [H] |
| Kill criteria | reassign/abandon after **3+ stuck iterations on the same error** | Osmani [H] |
| Turn cap | `max_turns` per task (25 is a reasonable start) | mine [L] |
| Wall-clock timeout | per task, ~2× the modelled turn time × max_turns (§2.2) | mine [L] |
| Loop detection | hash (last tool call + last error). 3 identical hashes in a row ⇒ abort task, write `blocked.md`, requeue as a human-review item | mine [L]; matches Osmani's "loop endlessly trying the same broken approach" |
| No-progress detection | `git diff --stat` empty across 3 turns ⇒ abort | mine [L] |
| Recursion guard | forbid ribs from spawning ribs. Claude Code enforces this too: **"No nested teams: teammates cannot spawn their own teammates"** | [H]. This is the guard against the "another 10×" cost blowup ([Nadir](https://getnadir.com/blog/multi-agent-orchestration-15x-token-cost/)) |
| Health probe | poll llama-server `/slots` (on by default) every 30 s; log slot occupancy | [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) [H] |

### 8.3 Budget caps that actually bind on a local rig

Your budget is **GPU-seconds**, so express caps in tokens *and* time:

```json
{
  "run_budget": {
    "max_output_tokens": 4000000,     // ~8-10h at n=3 (see §2.3)
    "max_wall_clock_s": 36000,
    "max_tasks_completed": 60,
    "per_task_output_tokens": 120000
  },
  "hard_stops": ["budget_exceeded", "3_consecutive_task_failures", "disk_below_20GB"]
}
```

Enforce at three layers:
1. **LiteLLM** — `global_max_parallel_requests: 3`, plus per-key rpm/tpm on the coding virtual
   key. LiteLLM also gives you `num_retries`, `request_timeout`, `allowed_fails` and
   `cooldown_time` ([reliability docs](https://docs.litellm.ai/docs/proxy/reliability)) and
   **spend logging** you already have. The spend log *is* your token budget meter. [H]
2. **Dispatcher** — refuses to start a new task past the budget.
3. **Agent** — `max_turns` in the harness.

### 8.4 The GPU-contention hazards unique to this rig

- **Orca must be launched `--disable-gpu`.** Per `clients/README.md`: Electron's Chromium
  holds ~0.4 GB idle, **spiking to ~8 GB**, and `coder` needs ~23.3 GB — so `coder` OOMs on
  load while Orca is GPU-accelerated. The `.desktop` override is already in place; **make the
  overnight launcher assert it** (`pgrep -af stably-orca | grep -q disable-gpu || abort`). [H]
- **gpu-arbiter / ComfyUI** takes turns with the LLM. An overnight swarm must hold the arbiter
  for its whole run or it will be interrupted mid-task. [H — from repo README]
- **Apollo/gaming yield hook force-unloads the model** (182 ms measured). If anyone starts a
  game at 2 a.m., the swarm's model vanishes. Either disable the hook for the run window or
  make the dispatcher treat model-unload as a pause-and-retry, not a failure. [H — from repo
  README; the mitigation is mine]
- **Model swaps are catastrophic mid-run.** llama-swap will happily unload 19 GB if some
  agent requests `fast`. Scope the coding virtual key to a **single alias** for the duration
  of an unattended run. [M]

### 8.5 Morning-after ergonomics

Write `.swarm/runs/<id>/SUMMARY.md` on exit: tasks done/failed/blocked, total tokens, wall
clock, the diffstat per rib, and every `blocked.md`. Anthropic's framing applies: "Letting a
team run unattended for too long increases the risk of wasted effort" — the counter is making
the wasted effort **cheap to audit**, not preventing it. [H]

---

## 9. Concrete changes to make on this rig

| # | Change | Why | Confidence |
|---|---|---|---|
| 1 | `llama-swap-config.yaml` for `coder`: add `--cache-type-k q8_0 --cache-type-v q8_0`, set `-np 3`, `--cache-ram 32768`, `--cache-reuse 256` | Buys ~2× the KV tokens; RAM spill avoids 30k reprefills; 3 slots matches the analysis | M |
| 2 | Measure, don't trust §1.3: run 1/2/3/4 concurrent 30k-context agent turns and record `/slots` + `nvidia-smi` + aggregate t/s | The model dims for Qwen3.6 35B-A3B are **[unverified]**; this is a 30-minute experiment that replaces every estimate here | H |
| 3 | LiteLLM: `NUM_WORKERS=8`, `general_settings.global_max_parallel_requests: 3` | Default is 1 uvicorn worker; the cap is your cheapest runaway-swarm circuit breaker | H |
| 4 | Keep **Orca** as the orchestration layer; assert `--disable-gpu` in the launcher | MIT, worktree-native, agent-agnostic, already integrated, and the only surveyed orchestrator whose model backend is per-agent (so LiteLLM "just works") | H |
| 5 | Use **pi** in RPC/JSON-event mode as the headless rib worker; keep **opencode** for interactive spine work | pi has no subagent system (fine — Orca supplies it) and the best programmatic surface; opencode has the subagent/permission machinery for the spine | M |
| 6 | Add `.worktreeinclude` and a `.swarm/` dispatcher (~200 lines) implementing §7.2 | Nothing surveyed does DAG + `owns[]`-disjointness + WIP limits + budget caps against a local endpoint. This is the missing 200 lines. | M |
| 7 | Add a pre-edit hook rejecting writes outside the task's `owns[]` | Deterministic enforcement of the one invariant that prevents merge chaos | M |
| 8 | Move all verification to CPU tooling; **ban LLM-judge gates, best-of-N and self-consistency** | Each costs a full model pass on a 0.4–0.7 M tok/hr pipe; `tsc`/tests cost idle CPU | M |
| 9 | Hand-write `AGENTS.md`; never let an agent generate it | ~−3% success / +20% cost for LLM-generated vs +4% human-curated (Osmani) | M |
| 10 | **Do not adopt A2A.** Expose the task queue / locks / spec store as **MCP** tools instead | A2A v1.0 is explicitly not a sub-agent protocol and targets cross-system federation | H |

---

## 10. Honest uncertainties

- **The KV table is arithmetic on assumed model dimensions.** If Qwen3.6 35B-A3B uses more KV
  heads or more layers than the 30B-A3B stand-in, the slot counts shrink. Change #2 above
  resolves this in half an hour and should be done before anything else. **[unverified]**
- **The 1.2×–1.9× concurrency scaling is one benchmark on one build.** llama.cpp moves fast;
  re-measure on your build. The `-np`-vs-`-b`/`-ub` interaction ("increasing `--parallel`
  without giving prefill more tokens-per-pass just spreads the same throughput across more
  queues") suggests tuning `-b`/`-ub` upward alongside `-np` may recover some scaling —
  **untested here**.
- **Prefill throughput (~1000 t/s) is extrapolated**, not measured for a 3B-active MoE at 30k
  prompts on a 3090 Ti. Time-to-first-token dominates cold turns; measure it.
- **The 30% "coordination tax" is my judgement**, not a measurement. The literature
  (MAST's 14 failure modes, Anthropic's known limitations list) says it is real but does not
  quantify it for coding swarms.
- **Nobody has published a swarm benchmark on a single consumer GPU.** Every number in the
  orchestration literature assumes elastic cloud capacity. This whole document is an attempt
  to translate cloud findings into a fixed-throughput regime, and that translation is the
  least-verified part of it.

---

## Sources

- [Cognition — Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Claude Code — Agent teams](https://code.claude.com/docs/en/agent-teams) · [Subagents](https://code.claude.com/docs/en/sub-agents) · [Worktrees](https://code.claude.com/docs/en/worktrees) · [Agent view / background agents](https://code.claude.com/docs/en/agent-view)
- [Addy Osmani — The Code Agent Orchestra (2026-03-26)](https://addyosmani.com/blog/code-agent-orchestra/)
- [Chroma — Context Rot (2025-07-14)](https://www.trychroma.com/research/context-rot)
- [MAST — Why Do Multi-Agent LLM Systems Fail? (arXiv:2503.13657)](https://arxiv.org/abs/2503.13657)
- [Geoffrey Huntley — Ralph (2025-07-14)](https://ghuntley.com/ralph/)
- [llama.cpp server README (master)](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp discussion #18030 — batch processing performance (Dec 2025)](https://github.com/ggml-org/llama.cpp/discussions/18030)
- [vLLM vs llama.cpp vs Ollama on 24 GB](https://dev.to/sikamikanikobg/vllm-vs-llamacpp-vs-ollama-what-happens-when-your-model-doesnt-fit-in-24gb-vram-56eb)
- [LiteLLM — config settings](https://docs.litellm.ai/docs/proxy/config_settings) · [reliability](https://docs.litellm.ai/docs/proxy/reliability)
- [Orca (stablyai/orca)](https://github.com/stablyai/orca) · [Orca worktree docs](https://www.onorca.dev/docs/model/worktrees)
- [opencode — Agents](https://opencode.ai/docs/agents/) · [pi docs](https://pi.dev/docs/)
- [Roo Code — Orchestrator / Boomerang tasks](https://roocodeinc.github.io/Roo-Code/features/boomerang-tasks)
- [github/spec-kit](https://github.com/github/spec-kit)
- [Augment — 9 Open-Source Agent Orchestrators (2026)](https://www.augmentcode.com/tools/open-source-agent-orchestrators)
- [OpenHands](https://github.com/All-Hands-AI/OpenHands) · [microsoft/agent-framework](https://github.com/microsoft/agent-framework) · [Agno](https://github.com/agno-agi/agno)
- [claude-squad](https://github.com/smtg-ai/claude-squad) · [container-use](https://github.com/dagger/container-use) · [uzi](https://github.com/devflowinc/uzi) · [vibe-kanban](https://github.com/BloopAI/vibe-kanban)
- [A2A Protocol v1.0 (Linux Foundation)](https://a2a-protocol.org/latest/)
- [Nadir — multi-agent 15× token cost](https://getnadir.com/blog/multi-agent-orchestration-15x-token-cost/)
