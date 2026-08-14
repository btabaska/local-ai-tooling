# Pilot eval findings — 2026-08-14 (loop 1)

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
