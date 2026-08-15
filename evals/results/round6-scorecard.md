# Scorecard

## litellm/coder [round6]

**Overall: 48/65 passed** (mean checklist score 0.78); safety violations: 0 | **generalization:** kb-covered 18/20 (mean 0.89) vs held-out 30/45 (mean 0.73)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 2/2 | 0.87 |
| diagnose | 8/21 | 0.52 |
| knowledge | 16/16 | 0.98 |
| ops-plan | 11/15 | 0.74 |
| status | 3/3 | 1.00 |
| verify-author | 8/8 | 1.00 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.67 | ❌ | Correct root cause, both quick fixes, and the shallow-threshold monitoring gap. Lacks a verification step and  |
| diag-004 | d4 | 0.91 | ✅ | Correct boot race, timezone math, and both fixes. Mechanism partly confused mid-answer (claims CIFS later over |
| diag-005 | d4 | 0.70 | ✅ | Solid mechanism and ExecStartPost reasoning, but misexplains the recovery as a manual or automated external pi |
| diag-006 | d4 | 0.78 | ✅ | Correctly nails the reasoning-token budget trap and a max_tokens fix, but the answer is fragmentary, skips gua |
| diag-007 | d3 | 0.89 | ✅ | Accurate and thorough: nails the self-observation race, proposes both is-active exclusion and targeted skip, a |
| diag-009 | d4 | 0.00 | ❌ | The candidate answer is completely empty and called no tools, so no checklist criterion can be established. Ze |
| diag-010 | d3 | 0.60 | ❌ | Gets the core right: healthy app, unauthenticated probe since auth change, compose-up no-op. But hallucinates  |
| diag-011 | d3 | 0.33 | ❌ | Nails the phantom-seeding mechanism but anchors on a KB quota incident, misattributing the root cause to EDQUO |
| diag-012 | d2 | 0.89 | ✅ | Accurate root cause, config location, live-apply fix, and dead-man monitoring; adds useful deployment-gap find |
| diag-013 | d2 | 1.00 | ✅ | Accurate diagnosis matching ground truth, with correct fix, apply path via API given no standing SSH, and full |
| diag-101 | d3 | 0.00 | ❌ | Candidate answer is completely empty with no tool calls. Nothing to grade; all criteria fail, including the ne |
| diag-102 | d3 | 0.55 | ❌ | Correctly identifies the locked-database mechanism and soularr crash cycle, but confirmation steps use docker  |
| diag-104 | d2 | 0.56 | ❌ | Plausible but wrong root cause: picks language-profile gap from wiki instead of empty provider list. Monitorin |
| diag-105 | d4 | 0.00 | ❌ | Candidate produced no answer text at all despite reading two KB files; every checklist criterion fails by defa |
| diag-106 | d3 | 0.33 | ❌ | Gets the core no-causation verdict and purge remediation right, but misses the wrong-subnet diagnosis, substit |
| diag-107 | d3 | 0.00 | ❌ | Confident but wrong: invents an API-only check script and blames vector search plus ML window, missing the rea |
| diag-108 | d3 | 0.89 | ✅ | Strong answer: correct root cause, sound refused-vs-timeout reasoning, matching confirmation probes, correct f |
| diag-109 | d3 | 0.20 | ❌ | Candidate invents an alternate root cause (ongoing unbound crash, dead DNS) contradicting ground truth of a re |
| diag-110 | d4 | 0.20 | ❌ | Answer is unfinished investigation narration ending mid-probe; it points toward the env override runbook but n |
| diag-111 | d4 | 0.90 | ✅ | Strong, KB-grounded diagnosis matching the reference chain, docker ps explanation, and confirmation probes; ad |
| diag-112 | d3 | 0.60 | ❌ | Strong on core mechanism, fix, and verification probes; grounded in repo docs. Miscasts the 30-day lifecycle r |
| know-004 | d3 | 1.00 | ✅ | Excellent answer matching ground truth: correct plain-bind propagation diagnosis, full seven-container restart |
| know-006 | d3 | 1.00 | ✅ | Accurate and complete against reference; covers all mechanics including the env-var gotcha. Omits the HOMEPAGE |
| know-007 | d4 | 1.00 | ✅ | Excellent advisory answer matching reference on root cause, false-pass explanation, fix, recreate requirement, |
| know-008 | d4 | 1.00 | ✅ | All criteria met with correct cause, layered lockdown, REST verification, and standing check. Minor factual sl |
| know-009 | d3 | 1.00 | ✅ | Matches ground truth on all four criteria, including the last-run parse anchored at Starting Run. All commands |
| know-010 | d4 | 1.00 | ✅ | All four criteria established, matching reference ground truth from cited quirk doc. Curl examples are advisor |
| know-013 | d2 | 0.88 | ✅ | Strong, accurate advisory answer covering claim flow, basic auth, libraries, and cold start; only miss is misa |
| know-101 | d4 | 1.00 | ✅ | Excellent answer: nails the read-only btrfs diagnosis, causal chain, confirm command, reboot futility, and ful |
| know-102 | d3 | 0.83 | ✅ | Strong answer: order, rewrites, Caddy-vs-DNS distinction, direct ports, and drill all correct. Only miss is th |
| know-103 | d4 | 1.00 | ✅ | Answer matches the reference on every criterion, including the hide-plus-retention deletion mechanics, key han |
| know-104 | d2 | 1.00 | ✅ | Fully matches the reference procedure with all five steps correct, credentials sourced from .env, and useful N |
| know-105 | d3 | 1.00 | ✅ | Excellent answer matching the reference on failure mode, exact fix commands, named check with output fields, a |
| know-106 | d3 | 1.00 | ✅ | Fully matches the reference on every criterion, adds accurate extras (rig ML version skew, DSM sudo PATH quirk |
| know-107 | d3 | 1.00 | ✅ | Accurate and complete against ground truth: current state, failure mechanism, fix-31 remediation, journald cap |
| know-108 | d3 | 1.00 | ✅ | Fully matches ground truth on all criteria, adds accurate extra checks (www NXDOMAIN, manual port mapping mode |
| know-110 | d4 | 1.00 | ✅ | Answer matches the reference on every criterion, including mechanism, thresholds, delivery path, no-cloud rati |
| ops-002 | d4 | 0.29 | ❌ | Gets the executed-token mechanism and checks-runner contrast right, but misdiagnoses the malformation as multi |
| ops-003 | d4 | 0.77 | ✅ | Strong advisory plan: correct sync-profile demotion, propagation verification, blocklist-plus-delete cleanup,  |
| ops-004 | d5 | 0.94 | ✅ | Excellent answer matching ground truth on architecture, mediatype mechanics, DSM workaround, pipeline split, a |
| ops-006 | d4 | 0.77 | ✅ | Strong, KB-grounded answer nailing root cause, ipam fix, state preservation, and class guard; omits route-tabl |
| ops-008 | d5 | 0.93 | ✅ | Strong, accurate reconstruction of the incident: correct measurement method, source-level workload reduction,  |
| ops-010 | d3 | 1.00 | ✅ | Comprehensive, matches reference on every criterion including sequel lessons (mount-unit pinning, Komga restar |
| ops-012 | d3 | 0.79 | ✅ | Strong, grounded plan that nails the version-pin rule, the UnicodeDecodeError silent-fallback trap, and consum |
| ops-101 | d4 | 1.00 | ✅ | Excellent answer matching the reference on every criterion: root cause, quarantine mechanics, asset safety, ve |
| ops-102 | d4 | 1.00 | ✅ | Answer matches ground truth on both root causes, structural entrypoint fix, guard cadence, DSM scheduling, and |
| ops-103 | d3 | 0.85 | ✅ | Well-grounded answer nailing the append-only root cause, reconciler prevention, Lidarr reconcile gap, and heal |
| ops-104 | d3 | 0.86 | ✅ | Strong, KB-grounded answer matching ground truth on tmux provenance, session-level kill, baseline allowlist, d |
| ops-105 | d4 | 0.69 | ❌ | Strong on power button, clock, crash loop, and prior-work recognition, but misdiagnoses the two core technical |
| ops-106 | d3 | 0.73 | ✅ | Strong answer: recognizes existing media-05 deployment, nails mounts, transcode, consumer-end 206 check, and W |
| ops-107 | d3 | 1.00 | ✅ | Covers every checklist item with concrete API and script detail. Minor drift: attributes root cause to a bulk  |
| ops-108 | d3 | 0.00 | ❌ | The answer is only investigative narration between tool calls; it never delivers a diagnosis, fix, verificatio |
| ops-109 | d4 | 0.27 | ❌ | Strong on the self-heal storm, correctly recovering fix-62 root causes from docs. But invents wrong diagnoses  |
| ops-110 | d3 | 1.00 | ✅ | Comprehensive and accurate against ground truth on every criterion: inline detection, container-port endpoint, |
| stat-003 | d1 | 1.00 | ✅ | Accurate and complete: correct total, correct all-up status, explicit none-failing statement, backed by a live |
| stat-004 | d1 | 1.00 | ✅ | Strong answer: probed all endpoints, correct verdicts on all three services, correctly treated the LDR login r |
| stat-005 | d2 | 1.00 | ✅ | Accurate per-volume numbers matching ground truth, correct fullest-volume and not-tight conclusions. Extra roo |
| verify-002 | d3 | 1.00 | ✅ | Excellent answer matching reference on probe, target, threshold, vacuous-pass guard, host, and companion ACL c |
| verify-003 | d4 | 1.00 | ✅ | Near-perfect match to ground truth: correct endpoint, model, query, doc pair, both thresholds, healthy baselin |
| verify-004 | d4 | 1.00 | ✅ | Near-perfect match to ground truth: drift gate, direct-backend rationale for the TTS cache trap, marker roundt |
| verify-005 | d3 | 1.00 | ✅ | Strong match to ground truth on all graded criteria. Diverges on search book (claims devdocs guaranteed presen |
| verify-007 | d2 | 1.00 | ✅ | Answer reproduces the ground-truth ingest check nearly verbatim (query, vantage, sudo piping, pass line) and c |
| verify-008 | d3 | 1.00 | ✅ | Matches ground truth on every axis: correct check name, hub vantage, per-peer direct-transport assertion, bina |
| verify-009 | d4 | 1.00 | ✅ | Essentially matches ground truth: GET probe, exact expect-match string, side-effect-free rationale, names the  |
| verify-011 | d3 | 1.00 | ✅ | Answer reproduces the real seedbox-mount-listable check exactly, including timeout and non-empty content crite |

