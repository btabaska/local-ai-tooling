# Pilot eval findings — 2026-08-14/16 (loops 1–7 + model bake-off)

## MODEL BAKE-OFF (2026-08-16, all lanes on llama.cpp b10438, identical harness/judge)

| model | overall | mean | held-out | diagnose | knowledge | ops-plan | sec/card |
|---|---|---|---|---|---|---|---|
| **coder-strong (qwen3.6-27B dense)** | **55/65** | **0.86** | **37/45 (0.85)** | **14/21** | **16/16** | 12/15 | ~190s |
| coder (qwen3.6-35B-A3B MoE) | 46/65 | 0.80 | 30/45 (0.77) | 9/21 | 15/16 | 9/15 | ~90s |
| chat (gemma4-31B, rig-thinker base) | 38/65 | 0.70 | 25/45 (0.67) | 8/21 | 15/16 | 4/15 | ~110s |
| qwen3.8-27B | — infeasible (see below) | | | | | | 600s+ |

**coder-strong is the quality king — best score ever recorded on the suite** (prior best
51/65), sweeping every category incl. best-ever diagnose and held-out. The dense 27B's
per-token compute beats the 3B-active MoE exactly where the loops said the wall was.
Cost: ~2× latency, 114k vs 262k ctx. coder [bake] 46 vs its 49–51 prior = within churn.
gemma4 trails on planning/diagnosis but holds retrieval categories (knowledge/verify/
status stay ≥0.92 across ALL models — those wins are harness+kb, not model).
Zero safety violations in all 195 bake attempts. Original why-not-tested-earlier
concession partially vindicated: the plateau was ~5-9 cards lower than the stack's
actual ceiling.

**Qwen3.8-27B verdict: NOT deployable as the agentic ops brain today; healthy otherwise.**
- xhigh (default) thinking: 6/8 cards hit the 600s timeout. reasoning_effort medium
  (native `--reasoning-effort` flag; the `--chat-template-kwargs` JSON gets mangled by
  llama-swap arg-splitting → startup crash): STILL 600s+ on agentic cards.
- Discriminator: 22k-token SINGLE-turn = 24s with sane reasoning → the model is healthy;
  the killer is multi-turn cache thrash — the DeltaNet-hybrid arch reprocesses the full
  context every tool round in llama.cpp (cf. #22746), and eval cards run 10-40 rounds.
- Keep the llama-swap entry for single-turn/chat/vision duty; DO NOT route agentic work
  to it. Revisit on: llama.cpp hybrid-cache reuse fix, an A3B-class 3.8 release, or
  independent 27B benchmarks (none exist yet — all vendor numbers).

**Infra shipped with the bake:** llama-swap b10015→b10438 (digest bump, 19/19 local-ai
checks + calibrated rerank-spread + MTP + swarm all clean — note: run the suite as
btabaska, not sudo/root: root lacks the rig ssh alias and all rig-side checks false-fail);
scoped eval LiteLLM key (vault ai_stack.litellm_eval_key) after discovering **virtual
keys are model-scoped and /v1/models listings lie** (chat+q38 403'd on completions);
q38 LiteLLM alias; one-night Immich-ML window skip (timer restored, day-off state
corrected after Persistent catch-up fired it at noon).

**Recommendation (deployment routing):** `coder-strong` = primary ops/diagnosis brain
(quality); `coder` = interactive/long-context/speed lane and coding default; gemma4 =
chat duty only; q38 = shelf until the ecosystem catches up. pass^k for coder-strong not
yet measured — queue subset ×3 before declaring its consistency.

---

# Earlier: loops 1–7

## LOOPS 6–7 (single-variable consistency experiments): both NULL — the plateau is model-bound

- **Round 6, temp 0.2**: 48/65 (0.78). Diagnose crashed 12→8/21 via reasoning spirals
  (length-empties → 600s timeouts even at 16k output); any-of-3 ceiling shrank 11→9;
  pass^3 flat 6/12. REVERTED to temp 0.6 (kept 16k output headroom).
- **Round 7, claim-grounding self-review turn**: 49/65 (0.82, held-out mean 0.81 = best);
  65/65 clean (review turn doubles as empty-recovery); organic search still 0. pass^3
  again 6/12, any-of-3 8/12 with over-pruning signs on ops cards. NOT adopted as default
  (--self-review stays opt-in).
- **The stable core is production-grade**: knowledge/verify/status/deploy ≈ 29/29 at
  best-config, and the six kb-backed subset cards are 9-for-9 runs across ALL THREE
  configurations. The six flappy diagnose/ops cards flip regardless of temperature or
  review — run-to-run reasoning paths genuinely diverge at the 35B capability boundary.
- **Program conclusion after 7 loops**: harness gains are exhausted at ~50/65 (0.82),
  held-out ~73-80%. Best config = loop-5 harness (temp 0.6, 16k output, quirks-first kb,
  fleet+search+openzim tools). Remaining levers are NOT harness: (1) a stronger base
  model in llama-swap when available; (2) **deployment routing policy** — serve
  knowledge/status/verify/runbook queries locally (measured ~95-100%), escalate novel
  incident diagnosis to Claude (local ~55-65% single-shot); (3) grow the suite from
  scrubbed transcripts; (4) OWUI lane after lai-21.

---

# Earlier: loop 5

## ROUND 5 (loop-5): 51/65 (0.82) — held-out 80%; **pass^3 says consistency is now the frontier**

Loop-5 changes (quirks-first retrieval routing + INDEX runbook router, search-adoption
nudge, all-volumes system_overview): all six targeted chronic/regression cards fixed
(know-006 0.18→1.00, stat-005 0.43→1.00 — that one was a TOOL gap, diag-106/108,
ops-101, know-108). Aggregate flat vs round 4 (paired mean −0.002) because 5 *different*
cards wobbled down — we've hit the single-sample measurement ceiling (~±5 cards churn
per run at temp 0.6). Zero judge parse errors (hardening worked). Knowledge 16/16
(0.99), status 3/3, verify 8/8, deploy 2/2; diagnose remains the discriminator.

**pass^k on the fixed 12-card subset (3 runs each): pass@1 8/12, pass-any-of-3 11/12,
pass^3 6/12.** kb-retrieval-backed cards are deterministic (6/6 stable P-P-P); every
flapper is a reasoning-heavy diagnose/ops card. diag-011 is the only 0/3 (genuine gap).
Adoption nudge barely moved organic search (2 calls, 1 card). diag-105 produced one
empty session (one-off).

→ Loop-6 lever: **sampling temperature for ops work** (0.6 → 0.2), single-variable
re-run + subset ×3. Expect flappers to consolidate; watch for any creativity loss on
planning cards.

---

# Earlier: loops 1–4

## ROUND 4 (loop-4 harness): **50/65 (mean 0.82) — held-out 51% → 73%**

Same 65 cards, loop-4 improvements (search_web via SearXNG in fleet-mcp, openzim enabled,
kb += full wiki (341 pages), diagnosis-procedure prompt, narration-aware continuation,
redirect-labeled check_url, hardened judge): **kb-covered 17/20 = 85% (0.86) vs held-out
33/45 = 73% (0.80)** — the generalization gap shrank 19pts → 12pts, and held-out mean
rose 0.60 → 0.80. Paired: +0.165 mean delta, 17 newly passing, 4 regressed, 65/65 clean
runs, zero judge parse-errors, zero safety violations (now 184 attempts total).
Categories: verify-author 8/8 (0.98), knowledge 14/16 (0.92), ops-plan 11/15, deploy 2/2,
diagnose 13/21 (0.71 — improved, still the floor).

Capability audit (user question "can it reach the buildout + web search simultaneously?"):
**yes, proven live** — one evalplan session used fleet_search_web (found Navidrome
v0.63.2, July 2026), openzim (J4125 facts from offline Wikipedia) and fleet containers
together. Reach matrix: SearXNG ✅ (new tool), ZIM ✅ (openzim), wiki ✅ (kb), webfetch ✅,
fleet ✅; LDR/maps/comfyui/playwright/context7 deliberately not wired for evals.

New loop-5 lessons:
1. **Availability ≠ adoption**: organic search_web/openzim calls across 65 cards = ZERO
   (they work when asked — the smoke proves wiring). kb+wiki satisfies the model first.
   Consider task-shaped nudges; measure whether adoption would even help.
2. **Retrieval dilution**: 2 of 4 regressions (know-006 1.00→0.18, diag-104 1.00→0.33)
   came from the wiki drowning out the quirk notes — know-006 missed the Homepage
   static-shell quirk it found in round 3 and reinvented a wrong theory. Enforce
   quirks-before-wiki reading order or rank retrieval.
3. Other 2 regressions = variance/garnish (right mechanism, confabulated side-claims
   docked) — argues for pass^k measurement on a fixed subset next loop.
4. Judge incremental-write + resume shipped (a mid-run kill previously lost 9 grades).

---

# Earlier: loops 1–3

## ROUND 3 — GENERALIZATION TEST: 65 cards (45 held-out), auto-judged

**37/65 passed (mean 0.66); kb-covered 14/20 = 70% (mean 0.77) vs held-out 23/45 = 51%
(mean 0.60). Zero safety violations across all 65.** Same loop-2 harness, no further
tuning; graded by the automated Claude judge (`bin/judge.py`, calibrated 82% verdict
agreement vs hand grades, uniformly conservative), 3 parse-failures repaired (2 re-judged,
1 hand-graded).

**Answer to "are the improvements localized?": mostly no, partly yes.**
- Held-out pass rate (51%) is ~1.8x the loop-1 baseline (28%) — the permission fix,
  grounding prompt, tool discipline, and repo-lookup behavior generalize to sources the
  kb has never seen.
- The ~19-point covered-vs-held-out gap is real but directional (n=20 vs 45, p≈0.1,
  mechanism clustering) — knowledge injection only pays where knowledge exists.
- Category signal: verify-author 6/8 and knowledge 11/16 held up on held-out cards
  (the rig's foss-setup checkout makes repo-lookup a genuine generalizing capability);
  **novel-incident diagnosis is the weak spot (9/21)** — fresh audit findings with no kb
  note land at frontier-typical infra-RCA rates (cf. ITBench <50%).
- diag-108/ops-011-class behavior recurred: candidates probe the LIVE fleet and find the
  world has moved past the card's frozen scenario (NUT already masked, journal already
  rotated) — historical diag cards need "at the time of this evidence" framing.

New harness lessons (loop-4 worklist):
1. Continuation heuristic gap: diag-006 produced >300ch of investigation narration with
   no conclusion — length is a bad completeness proxy; detect "answer-shaped" endings or
   always ask a wrap-up turn.
2. Judge robustness: 3/65 strict-JSON parse failures (unescaped quotes; one empty CLI
   response) — switch judge to a JSON-schema-enforced path or retry with escalation.
3. `fleet_check_url` follows redirects (LDR 302 reads as 200) — label redirect chains in
   tool output.
4. Public-cards fix verified in the wild: two candidates grepped the eval kit and reached
   ONLY inputs (no references) — contamination detector flagged, triaged benign.
5. Grow the kb toward the wiki (know-102 failed on specifics the wiki records; wiki-lane
   cards passed when the candidate FOUND the file — retrieval works, coverage is the gap).

---

# Loops 1–2 findings (same day, earlier)

## LOOP 2 RESULT (same day): coder 5/18 → **16/18 passed, mean 0.40 → 0.88**

Same 18 cards, same model (qwen3.6-35b `coder`), after the improvement pass:
kb injection (52 quirk memories + CLAUDE.md, grep-able in the workdir), permission
fix (headless auto-REJECT of read/grep was the real "stall" cause — `external_directory:
ask` + no `--auto`), grounding system prompt, final-answer continuation backstop, and
the fleet-mcp fixes (self-hosted healthchecks URL, labeled gpu_status, tool-vs-world
error wording). Zero stalls (was 4), zero safety violations again.

Per-category (loop1 → loop2): diagnose 1/5 → 5/5; verify 0/3 → 2/3 (1 contaminated);
knowledge 1/4 → 4/4; ops-plan 0/3 → 2/3; status 3/3 → 3/3.

New lessons from loop 2:
- **Eval-kit contamination**: verify-010's recursive grep over `/tmp/evals-pilot`
  surfaced dataset reference text; scored 0/contaminated. Fix shipped: rig now gets
  reference-stripped cards (`bin/public_cards.py`) and `judge_bundle.py` flags any
  tool call that touches datasets.
- **The world contains answer keys**: the rig's ansible-pull checkout of foss-setup
  gave candidates the real wiki/runbooks/checks (verify-006, diag-014). That is
  *correct deployed behavior* (retrieval), but verify-authoring cards measure lookup,
  not authoring, on a host that carries the repo. Acceptable; note per-card.
- **Premise-vs-reality**: ops-011 detected via kb that the readarr→Bookshelf migration
  already happened and correctly reframed the ask — historic-replay cards need either
  hypothetical framing or credit for reality-checking (the model behaved RIGHT).
- **fleet-mcp fixes verified in-run**: stat-002 now parses util/temp separately;
  stat-001 no longer converts tool-auth errors into fake findings.
- Residual gaps: house-process steps still under-applied (ops-001 declined a
  stays-retired check despite the coverage-tripwire mandate in kb — the mandates need
  stronger prompting or a checklist skill); ops planning is the weakest category.

---

# Loop-1 findings (original, kept for the record)

18 cards, 2 models, SUT = `opencode run --agent evalplan` on rig, Claude-in-session judge.
**qwen3.6-35b (`coder`): 5/18 passed, mean checklist score 0.40. qwen2.5-7b (`fast`): 1/18, 0.12.**
Safety violations: **zero** in 36 attempts (read-only lane held; no mutating attempt even proposed
where forbidden). Full verdicts: `pilot-grades.jsonl`, `pilot-scorecard.md`, per-attempt
trajectories under `results/pilot-{coder,fast}/`.

## Failure modes, ranked by fixability

1. **Tool-loop stall (35B): 4/18 cards lost (~22%).** Model announces "Let me check…", burns
   5–37 tool calls, never returns a final answer (72–199-char stubs). Harness fix, cheap:
   runner detects empty final text → continues the session with "now give your final answer";
   also consider a steps cap + explicit "you must end with a complete answer" in the agent
   prompt. This alone could take the 35B from 5/18 toward ~9/18.
2. **Knowledge gap (both models): homelab-specific quirks score ~0.** CWA Kobo tombstone,
   Prowlarr ID-translation, DSM sudo PATH, seedbox ~/.startup — all live in Claude's memory /
   repo docs, none in the local stack. The models confabulate plausible-sounding mechanisms
   instead. Fix: RAG/skills layer — feed CLAUDE.md + the 53 memory files + runbooks to the
   local agent (opencode skills or OWUI RAG). This is the core of loop 2.
3. **Confabulation under partial knowledge (35B).** diag-001 NAMED the gitignore-comment fact
   then discarded it as a "red herring"; diag-008 invented a dead CMOS battery + two-boot
   timeline. Adjacent-fact-then-wrong-mechanism is the signature 24B-class failure. Mitigation:
   knowledge injection (above) + prompt nudge "prefer the mechanism the evidence directly
   supports; do not invent components not in evidence".
4. **House-process blindness (both).** Plans omit: coverage-manifest updates, docs anti-drift,
   consumer-end verification, unmonitored-first adoption, vault-first credential flow. Fix:
   a distilled "operating mandates" skill (CLAUDE.md §standing-mandates) always in context.
5. **7B cannot drive tools at all**: 0 tool calls in 18 cards; 3 cards emitted raw tool-call
   JSON as the answer text. `fast` is unusable as an agent under opencode's native FC — demote
   to utility roles only.
6. **fleet-mcp ergonomics.** `gpu_status` returns unlabeled CSV (model conflated util% with
   temp); tool docs leak agent-oriented caveats the model repeats as user-facing facts
   ("docker tools fail on NAS by design"); healthchecks tool-auth failure was misreported as
   a real service problem. Fix: label fields, separate tool-status from world-status in
   outputs.

## What worked

- **Live-status category: 3/3 passed (35B), scores 0.75–1.0.** With read-only fleet-mcp the
  35B correctly distinguished containers-vs-systemd, caught a litellm restart in real time,
  and adapted when URLs were allowlist-blocked. Tool-grounded questions are already usable.
- **know-002 passed via live probing**: the model discovered the glue-14 GPU night-window
  policy from rig unit names — tool-grounded retrieval partially substitutes for memory.
- **diag-015 scored 1.0**: given evidence in-prompt and few tools used, the 35B produced a
  Claude-quality diagnosis (RAR/sample import) with remediation + prevention.
- The harness end-to-end: mining → cards → rig runner → trajectories → judge bundle →
  scorecard all proved out in one day.

## Environment notes

- litellm container restarted once during the coder run (exit 0, not OOM, healthy since,
  17:42:50Z) — cause unconfirmed, watch on next run.
- Mac `opencode run` CLI hangs at init (kevent64 idle wait; serve API fine) — runs happen on
  rig; upstream bug worth reporting with a repro.
- Candidate answers observe the eval's own load (GPU 92% = its own inference) and today's
  live fleet on historical-scenario cards — decide per-category whether fleet tools should be
  disabled for evidence-provided diag cards in loop 2.

## Loop-2 worklist (in order)

1. Runner: empty-answer continuation + steps cap (attacks failure mode 1).
2. Skills/RAG: memory files + standing mandates into the opencode eval agent (modes 2–4).
3. fleet-mcp output labeling + tool-vs-world status separation (mode 6).
4. Re-run the SAME 18 cards on `coder` → paired per-card deltas = loop-over-loop metric.
5. Grow the set from the remaining 40 mined cards + add `chat`/gemma4 (rig-thinker base) to
   the opencode key scope as a third candidate.
6. Automate the judge (claude CLI headless or API) so loops stop needing an interactive session.
