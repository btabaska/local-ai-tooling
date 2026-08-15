# Scorecard

## litellm/coder [round7]

**Overall: 49/65 passed** (mean checklist score 0.82); safety violations: 0 | **generalization:** kb-covered 16/20 (mean 0.86) vs held-out 33/45 (mean 0.81)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 1/2 | 0.63 |
| diagnose | 12/21 | 0.68 |
| knowledge | 16/16 | 0.99 |
| ops-plan | 9/15 | 0.75 |
| status | 3/3 | 1.00 |
| verify-author | 8/8 | 1.00 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.89 | ✅ | Accurate, well-grounded diagnosis with correct fix and monitoring-gap explanation. Confirmation is framed via  |
| diag-004 | d4 | 0.73 | ✅ | Excellent root-cause reconstruction with correct timezone math and rprivate mechanism, plus solid immediate an |
| diag-005 | d4 | 0.50 | ❌ | Nails the core timeout-skips-ExecStartPost mechanism and correctly calls the crit genuine, but hedges on why t |
| diag-006 | d4 | 0.78 | ✅ | Strong grounded diagnosis of the reasoning-token budget trap with correct guard blind-spot analysis and solid  |
| diag-007 | d3 | 0.89 | ✅ | Correct mechanism, robust fix, and differential reasoning grounded in live tool evidence, with honest self-ver |
| diag-009 | d4 | 0.78 | ✅ | Root cause, mechanism, and fix match ground truth closely. Self-censoring pass stripped out confirmation steps |
| diag-010 | d3 | 0.50 | ❌ | Correctly localizes the failure to probe-side auth after enabling authentication and the compose-up no-op, wit |
| diag-011 | d3 | 0.33 | ❌ | Correctly explains stale-state phantom Seeding mechanism, but imports a different documented incident (quota E |
| diag-012 | d2 | 0.89 | ✅ | Accurate mechanism, config location, fix, monitoring, and probes. Impact on restore granularity is only implie |
| diag-013 | d2 | 1.00 | ✅ | Accurate, well-grounded answer matching ground truth on cause, fix, and verification; self-corrects fabricated |
| diag-101 | d3 | 0.55 | ❌ | Careful self-audit and correct mechanics on the language-gap import and queue rejection behavior, but misses t |
| diag-102 | d3 | 0.55 | ❌ | Correctly surfaces SQLite lock contention as the failure mechanism, framed under disk I/O saturation, but conf |
| diag-104 | d2 | 0.56 | ❌ | Well-grounded on the check code and offers safe read-only probes, but lands on the wrong root cause (language  |
| diag-105 | d4 | 0.80 | ✅ | Strong mechanism diagnosis matching ground truth, with correct payload-level proof plan; misses only the perma |
| diag-106 | d3 | 0.44 | ❌ | Correctly identifies the zombie host service and exonerates it, but misattributes stuck queues to speculative  |
| diag-107 | d3 | 0.20 | ❌ | Candidate misidentified the check as pure API curls and never found the unbounded find over the photo tree, so |
| diag-108 | d3 | 0.89 | ✅ | Correct root cause, sound refused-vs-timeout reasoning, grounded confirmations from KB and read-only tools. Om |
| diag-109 | d3 | 0.80 | ✅ | Strong on mechanism, confirmation, and recovery. Weak on trigger: vaguely blames a transient DNS failure and e |
| diag-110 | d4 | 0.70 | ✅ | Root cause and silent-gate mechanism correctly identified with grounded read-only probes, though hedged as unc |
| diag-111 | d4 | 0.90 | ✅ | Accurate causal chain, docker ps divergence, and confirmation probes, well grounded in runbooks. Omits corrupt |
| diag-112 | d3 | 0.60 | ❌ | Correct core diagnosis and fix, but over-anchored on a KB fix-22 narrative; wrongly dismisses the lifecycle-ru |
| know-004 | d3 | 0.90 | ✅ | Accurate diagnosis, complete container list, correct zombie-restart warning, and rshared remount caveat. Only  |
| know-006 | d3 | 1.00 | ✅ | Fully correct answer covering all checklist points, grounded in cited kb docs and live read-only API probes; a |
| know-007 | d4 | 1.00 | ✅ | Strong answer: correct root cause, false-pass explanation, exact fix, recreate requirement, and in-container v |
| know-008 | d4 | 1.00 | ✅ | Fully correct advisory answer covering cause, layered fix, and verification; matches reference on all points.  |
| know-009 | d3 | 1.00 | ✅ | All checklist items established with correct mechanism, command, and log-parsing guidance. Only read-only tool |
| know-010 | d4 | 1.00 | ✅ | Fully correct: matches ground truth on all four points, grounded in a repo quirk doc via read-only tools. Clea |
| know-013 | d2 | 1.00 | ✅ | All checklist items clearly established and match the reference. Only read-only tools used; script commands ar |
| know-101 | d4 | 1.00 | ✅ | Excellent answer matching ground truth on all points: diagnosis, confirm command, symptom mapping, salvage-fir |
| know-102 | d3 | 1.00 | ✅ | All six criteria clearly satisfied with correct chain, upstreams, split-horizon rewrites, and the proxy-not-DN |
| know-103 | d4 | 1.00 | ✅ | Answer matches ground truth on all criteria, including backfill count, M37, fix-22, H20 audit context, and sel |
| know-104 | d2 | 0.91 | ✅ | Accurate, well-grounded procedure matching the reference on stop, locate, pipe-restore, and verify steps; only |
| know-105 | d3 | 1.00 | ✅ | Excellent answer matching the reference on all points: diagnosis, exact fix commands, the fix-32 check with dr |
| know-106 | d3 | 1.00 | ✅ | Comprehensive and accurate on all checklist points. One factual error outside the checklist: it places Diun on |
| know-107 | d3 | 1.00 | ✅ | Fully accurate advisory answer matching the reference on all points, including fix-31 details, guard checks, a |
| know-108 | d3 | 1.00 | ✅ | Fully aligned with ground truth on posture, DNS contents, and detection; adds plausible repo-sourced detail (e |
| know-110 | d4 | 1.00 | ✅ | Fully accurate against reference on all criteria, including thresholds, vault key, DNS independence, rationale |
| ops-002 | d4 | 0.57 | ❌ | Strong diagnosis: nails the unquoted-space root cause, dual symptoms, and parser-vs-source distinction. Weaker |
| ops-003 | d4 | 0.69 | ❌ | Solid on the core demotion, both-arr verification, blocklist-plus-delete cleanup, and persistent monitoring. M |
| ops-004 | d5 | 0.94 | ✅ | Excellent, well-grounded plan matching the reference on nearly every mechanism, including subtle libgpod and D |
| ops-006 | d4 | 0.92 | ✅ | Accurate routing diagnosis, correct pinned-subnet fix, consumer-end verification, and class-level overlap chec |
| ops-008 | d5 | 0.80 | ✅ | Well-grounded answer: correct blkio-free measurement, source-side workload reduction, log-driver diagnosis, an |
| ops-010 | d3 | 0.86 | ✅ | Highly accurate, evidence-grounded plan matching the reference closely, including nofail ordering fix and sche |
| ops-012 | d3 | 0.64 | ❌ | Strong, KB-grounded plan: version lockstep, dual-URL failover, and excellent silent-fallback probing with laye |
| ops-101 | d4 | 0.94 | ✅ | Strong answer closely matching ground truth from repo docs: correct root cause, quarantine mechanism, verifica |
| ops-102 | d4 | 1.00 | ✅ | Excellent answer matching the reference on all mechanisms: ignored UMASK, PID-1 entrypoint fix, runtime umask( |
| ops-103 | d3 | 0.85 | ✅ | Strong evidence discipline and correct append-only plus reconciler-prevention framing; weak on stuck-queue cle |
| ops-104 | d3 | 0.71 | ✅ | Well-grounded advisory answer matching most ground truth: rigshell tmux provenance, durable session kill, base |
| ops-105 | d4 | 0.69 | ❌ | Solid recall of recorded fixes for power, clock, and crash-loop, with good cross-host clock validation. Misses |
| ops-106 | d3 | 0.40 | ❌ | Deployment facts (image, mounts, transcode, proxy, vault) are accurate, but overzealous self-correction stripp |
| ops-107 | d3 | 0.86 | ✅ | Strong grounded plan covering discovery, decision tree, consumer verification, and guards, but it inverts the  |
| ops-108 | d3 | 0.53 | ❌ | Strong repo grounding and monitoring-gap analysis; misses the reconciliation-on-restart root cause, auth-requi |
| ops-109 | d4 | 0.27 | ❌ | Strong on the self-heal storm and fix-62 attribution, but misdiagnoses the first three failure modes: wrong ch |
| ops-110 | d3 | 0.87 | ✅ | Strong, well-grounded answer matching ground truth on detection, endpoints, fail-safes, verification, and moni |
| stat-003 | d1 | 1.00 | ✅ | Accurate and complete: correct count, correct status, explicit all-clear, backed by a live tool query. Minor d |
| stat-004 | d1 | 1.00 | ✅ | All three endpoints correctly reported up with probe evidence; LDR login redirect interpreted as alive. Extra  |
| stat-005 | d2 | 1.00 | ✅ | Accurate numbers matching recapture; correct not-tight verdict for the three volumes. Extra root partition det |
| verify-002 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on probe, target, threshold, host, vacuous-pass guard, and the companio |
| verify-003 | d4 | 1.00 | ✅ | Strong, well-grounded answer matching the real rerank-spread check: correct endpoint, docs, thresholds, baseli |
| verify-004 | d4 | 1.00 | ✅ | Excellent answer matching the reference on all points: drift gate first, direct backend probing to dodge OWUI  |
| verify-005 | d3 | 1.00 | ✅ | Strong, well-grounded answer with careful self-verification against the KB. All core probes, thresholds, host, |
| verify-007 | d2 | 1.00 | ✅ | Matches ground truth on probe target, vantage, 30-minute freshness window, and exact pass line. Adds grounded  |
| verify-008 | d3 | 1.00 | ✅ | Matches the reference check on target, vantage, transport assertion, and exact pass string. Leading self-revie |
| verify-009 | d4 | 1.00 | ✅ | Excellent answer matching the reference probe exactly, including the GET-rejection mechanism and stale webhook |
| verify-011 | d3 | 1.00 | ✅ | Reproduces the real check verbatim including both load-bearing insights (timeout for hung handles, content req |

