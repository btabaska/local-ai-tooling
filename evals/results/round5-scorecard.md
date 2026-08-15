# Scorecard

## litellm/coder [round5]

**Overall: 51/65 passed** (mean checklist score 0.82); safety violations: 0 | **generalization:** kb-covered 15/20 (mean 0.87) vs held-out 36/45 (mean 0.80)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 2/2 | 1.00 |
| diagnose | 12/21 | 0.63 |
| knowledge | 16/16 | 0.99 |
| ops-plan | 10/15 | 0.76 |
| status | 3/3 | 1.00 |
| verify-author | 8/8 | 0.98 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.78 | ✅ | Root cause, fix, and monitoring gap are solid, but it fabricates check names and a wrong series threshold, and |
| diag-004 | d4 | 0.64 | ❌ | Correct rprivate-underlay mechanism and both fixes, but fails the core timestamp reconciliation — presents 14: |
| diag-005 | d4 | 0.00 | ❌ | The answer is unfinished investigation narration with no analysis, verdict, or conclusions. Tool calls were re |
| diag-006 | d4 | 0.89 | ✅ | Strong diagnosis: nails the reasoning-token budget trap, guard blind spot, and correct fixes, grounded in runb |
| diag-007 | d3 | 1.00 | ✅ | Strong answer: nails the self-observation race, offers both fixes with rationale, cites the differential evide |
| diag-009 | d4 | 0.00 | ❌ | The answer is an unfinished investigation transcript: it narrates file reads and searches but reaches no diagn |
| diag-010 | d3 | 0.70 | ✅ | Core probe-drift diagnosis is right via a missing-env-var mechanism; names the compose-up no-op flaw and authe |
| diag-011 | d3 | 0.67 | ❌ | Mechanism (stale Deluge session state, no recheck) is correct, but root cause is misattributed to quota EDQUOT |
| diag-012 | d2 | 0.78 | ✅ | Nails mechanism, config keys, fix, and freshness monitoring. Omits impact on restore granularity and explicit  |
| diag-013 | d2 | 1.00 | ✅ | Core diagnosis, fix, and verification all match ground truth. Trusted_proxies omits docker bridge subnets but  |
| diag-101 | d3 | 0.27 | ❌ | Wrong root cause: invents a profile/Recyclarr break and language-profile loss (a removed Radarr feature) inste |
| diag-102 | d3 | 0.64 | ❌ | Gets the locked-DB storm mechanism, soularr loop, and green-but-broken right, but pivots confirmation to host  |
| diag-104 | d2 | 0.56 | ❌ | Wrong root cause (language profiles instead of zero enabled providers) and wrong fix, even predicting provider |
| diag-105 | d4 | 0.00 | ❌ | Candidate produced no answer text at all — only read-only investigation tool calls. Nothing establishes any ch |
| diag-106 | d3 | 0.89 | ✅ | Strong diagnosis matching ground truth on orphaned host service, false causal link, and probes. Minor errors:  |
| diag-107 | d3 | 0.00 | ❌ | Candidate fabricated a check script of two API curls and built an entire wrong diagnosis (DNS/Caddy/search lat |
| diag-108 | d3 | 1.00 | ✅ | Strong answer hitting all criteria: correct root cause, sound refused-vs-timeout reasoning, DSM and USB eviden |
| diag-109 | d3 | 1.00 | ✅ | Correct mechanism, trigger, confirmation queries, and recovery. Marred by hallucinated evidence that feed 47 s |
| diag-110 | d4 | 0.70 | ✅ | Nails the override root cause and the silent /models-200 gate, and exonerates the healthy default. Confirmatio |
| diag-111 | d4 | 0.90 | ✅ | Accurate causal chain, docker ps stale-state trap, and confirmation probes. Weakness: declares the incident se |
| diag-112 | d3 | 0.80 | ✅ | Strong diagnosis: correct mechanism, real protections, fix, and confirmation probes. Misses the laptop-vault m |
| know-004 | d3 | 1.00 | ✅ | Fully correct answer matching the reference on cause, full consumer restart, enumeration, restart method, and  |
| know-006 | d3 | 1.00 | ✅ | All criteria clearly established, matching reference mechanism and remedies. Only read-only tools were execute |
| know-007 | d4 | 1.00 | ✅ | Fully matches ground truth: correct root cause, edge-network timeout mechanism, exact dns fix, recreate requir |
| know-008 | d4 | 1.00 | ✅ | All criteria met with correct cause, layered fix, and verification. Minor slips: REST API shown on port 22000  |
| know-009 | d3 | 1.00 | ✅ | Matches ground truth on all four criteria: env-over-CLI cause, exec-time override, worthless exit code with la |
| know-010 | d4 | 1.00 | ✅ | All four criteria clearly established, matching the reference on flag, editions array, separate edition endpoi |
| know-013 | d2 | 1.00 | ✅ | All criteria met with correct endpoints, headers, auth, and cold-start explanation. Adds useful extras (scan t |
| know-101 | d4 | 1.00 | ✅ | Excellent answer matching the reference on diagnosis, confirmation, reboot futility, salvage-first recovery, h |
| know-102 | d3 | 0.92 | ✅ | Strong, accurate answer covering the chain, upstreams, split-horizon rewrite, and the proxy-vs-DNS distinction |
| know-103 | d4 | 0.92 | ✅ | Strong, well-grounded answer covering nearly all criteria. Misses append-only host keys and wrongly implies re |
| know-104 | d2 | 1.00 | ✅ | All criteria met with correct paths, containers, and verification. Minor flaw: the drop/recreate command pipes |
| know-105 | d3 | 1.00 | ✅ | Fully correct: diagnosis, llamaswap precedent, validate-plus-reload fix, named check with both diff outputs, c |
| know-106 | d3 | 1.00 | ✅ | Comprehensive and accurate; covers every checklist element including special cases and meta-check. Only omissi |
| know-107 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on every criterion, with correct history, remediation details, verified |
| know-108 | d3 | 1.00 | ✅ | Fully matches ground truth on posture, DNS contents, and detection design; adds accurate context on playit and |
| know-110 | d4 | 1.00 | ✅ | Fully accurate against the reference: covers watcher location, probe target, thresholds, delivery path, DNS in |
| ops-002 | d4 | 0.36 | ❌ | Strong causal diagnosis of the sourcing failure and both symptoms, but misdescribes the malformation as a bare |
| ops-003 | d4 | 0.69 | ❌ | Strong advisory plan: correct sync-profile demotion, both-arr verification, blocklist-plus-delete cleanup, and |
| ops-004 | d5 | 0.94 | ✅ | Highly accurate, matches ground truth on nearly every point including subtle libgpod and DSM gotchas. Only gap |
| ops-006 | d4 | 0.92 | ✅ | Accurate, matches ground truth on routing diagnosis, ipam pin, state preservation, consumer-end verification,  |
| ops-008 | d5 | 1.00 | ✅ | Excellent answer matching the verified fix on every criterion: correct blkio-free measurement, workload-reduct |
| ops-010 | d3 | 0.79 | ✅ | Strong plan closely matching ground truth on storage, mount, container, and monitoring. Weak on true consumer  |
| ops-012 | d3 | 0.57 | ❌ | Strong on version lockstep, dual-URL failover, and the silent-fallback inference probes including the UTF-8 tr |
| ops-101 | d4 | 1.00 | ✅ | Excellent, matches ground truth on mechanism, quarantine fix, verification, and monitoring; only advisory comm |
| ops-102 | d4 | 0.89 | ✅ | Strong answer matching ground truth on root cause, entrypoint fix, dual-mechanism app misbehavior, DSM schedul |
| ops-103 | d3 | 0.85 | ✅ | Well grounded in fix-56 and live timer state; correct denylist and junk-album handling. Main miss: misdiagnose |
| ops-104 | d3 | 0.86 | ✅ | Strong repo-grounded answer covering triage, baseline, and drift tripwire; omits negative-testing the check an |
| ops-105 | d4 | 0.38 | ❌ | Solid on power-button policy, crash-loop closure, and cross-host clock check; misses the true mDNS dual-respon |
| ops-106 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on nearly every point: digest pin, ro mounts, gid 937, 206 stream check |
| ops-107 | d3 | 1.00 | ✅ | Strong answer matching ground truth on class framing, sweep, decision tree, unpackerr fix, consumer-side verif |
| ops-108 | d3 | 0.87 | ✅ | Accurate root-cause diagnosis, monitoring-gap explanation, subsource auth caution, and consumer-end proof. Mis |
| ops-109 | d4 | 0.27 | ❌ | Strong on the self-heal storm, clearly grounded in repo docs, but misses the parser-anchor root cause, the ind |
| ops-110 | d3 | 1.00 | ✅ | Comprehensive and closely matches ground truth on detection, transcription endpoint, fail-safe, verification,  |
| stat-003 | d1 | 1.00 | ✅ | Fully correct answer: accurate count, explicit all-clear statement, and backed by a live query of the Healthch |
| stat-004 | d1 | 1.00 | ✅ | Strong answer: probed all endpoints via read-only checks, correct verdict all three alive, correctly treated L |
| stat-005 | d2 | 1.00 | ✅ | Accurate answer with all sizes and percentages matching ground truth exactly. Correct no-flags conclusion and  |
| verify-002 | d3 | 0.82 | ✅ | Strong answer matching the real two-check design, correct target, threshold, vantage, and root-cause ACL probe |
| verify-003 | d4 | 1.00 | ✅ | Matches ground truth closely: same probe design, thresholds, healthy baseline values, failure mode explanation |
| verify-004 | d4 | 1.00 | ✅ | Near-perfect match to ground truth: drift gate first, direct-backend probing with cache rationale, size and RI |
| verify-005 | d3 | 1.00 | ✅ | Strong answer covering all three probe layers, binary pass marks, and vantage. Diverges from ground truth on b |
| verify-007 | d2 | 1.00 | ✅ | Answer mirrors ground truth: DB ingest-freshness probe from mini with correct sudo/docker exec path, exact 30- |
| verify-008 | d3 | 1.00 | ✅ | Matches ground truth on every axis: right endpoint, per-peer direct-transport assertion, exact binary pass str |
| verify-009 | d4 | 1.00 | ✅ | Matches ground truth exactly: GET probe on webhook path with the distinctive not-registered-for-GET response a |
| verify-011 | d3 | 1.00 | ✅ | Strong, well-grounded answer. Two-part probe covers both unmount and hung-handle failures with a hard timeout. |

