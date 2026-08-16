# Scorecard

## chat-gemma4 [bake]

**Overall: 38/65 passed** (mean checklist score 0.70); safety violations: 0 | **generalization:** kb-covered 13/20 (mean 0.76) vs held-out 25/45 (mean 0.67)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 0/2 | 0.40 |
| diagnose | 8/21 | 0.58 |
| knowledge | 15/16 | 0.92 |
| ops-plan | 4/15 | 0.48 |
| status | 3/3 | 0.95 |
| verify-author | 8/8 | 0.98 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.67 | ❌ | Correct root cause, fix, and monitoring-gap explanation. Only proposes commands, executes nothing. Lacks a ver |
| diag-004 | d4 | 0.82 | ✅ | Strong diagnosis with correct timezone math and rprivate mechanics, correct immediate and durable fixes. Misse |
| diag-005 | d4 | 0.70 | ✅ | Strong causal reconstruction and correct verdict with accurate timezone handling. Misses the key scaling weakn |
| diag-006 | d4 | 0.33 | ❌ | Plausible but incorrect root cause: attributes failure to unstripped think blocks around emitted JSON rather t |
| diag-007 | d3 | 0.67 | ❌ | Correct core mechanism and precise fix with is-active gating. Frames it as schedule collision rather than the  |
| diag-009 | d4 | 0.44 | ❌ | Mechanism diagnosis is accurate and well explained, but the proposed ansible_user_dir fix inherits the same be |
| diag-010 | d3 | 0.50 | ❌ | Strong root-cause diagnosis of the 401 probe drift and the compose-up no-op, but wrongly declares self-heal an |
| diag-011 | d3 | 0.67 | ❌ | Strong mechanism explanation of fastresume state desync and sound deluge/Sonarr cleanup steps, but omits block |
| diag-012 | d2 | 0.78 | ✅ | Mechanism, config key, fix, and live-apply quirk are correct; freshness alert included though secondary to a p |
| diag-013 | d2 | 0.88 | ✅ | Solid diagnosis and correct fix with sound verification steps. Omits docker bridge subnet caution and the dire |
| diag-101 | d3 | 0.36 | ❌ | Mechanistically coherent on import-vs-grab logic and foreign-audio contamination, but misdiagnoses the root ca |
| diag-102 | d3 | 0.55 | ❌ | Correctly lands on database-is-locked as the shared mechanism but overlays a speculative I/O-saturation theory |
| diag-104 | d2 | 0.56 | ❌ | Correctly identifies the monitoring gap and gives clean read-only confirmation probes, but misdiagnoses root c |
| diag-105 | d4 | 1.00 | ✅ | Accurate diagnosis matching ground truth mechanism, sequence, and proof plan, grounded in the quirks doc. Mino |
| diag-106 | d3 | 0.33 | ❌ | Correctly spots the orphaned mini service and subnet mismatch, but invents a fabricated NAS wedge as root caus |
| diag-107 | d3 | 0.00 | ❌ | Candidate invents a false mechanism (curl -sm flag misinterpretation, which is valid POSIX flag clustering) an |
| diag-108 | d3 | 0.89 | ✅ | Correct root cause and solid refused-vs-filtered reasoning grounded in a repo runbook; confirmation probes ade |
| diag-109 | d3 | 0.70 | ✅ | Nails the exclusion mechanism, confirmation query, and recovery with correct no-self-heal framing. Misses the  |
| diag-110 | d4 | 0.70 | ✅ | Correct core diagnosis of env-override and deceptive liveness gate. Confirmation probes are partial: uses comp |
| diag-111 | d4 | 0.10 | ❌ | Correctly identifies the read-only filesystem trigger and monitoring blind spot, but wrongly assumes postgres  |
| diag-112 | d3 | 0.60 | ❌ | Strong on mechanism and fix, including the new-uploads-only caveat. Misreads the lifecycle rule as purely a pu |
| know-004 | d3 | 0.90 | ✅ | Strong advisory answer: correct cause, full consumer set, correct restart method with zombie warning. Misses o |
| know-006 | d3 | 0.91 | ✅ | Accurate and well-grounded on all core mechanics; only omits the missing-env failure symptom and the HOMEPAGE_ |
| know-007 | d4 | 0.60 | ❌ | Correctly blames the compose dns override and applies it via recreate, but hedges on why tautulli works, misse |
| know-008 | d4 | 0.91 | ✅ | Accurate diagnosis and complete layered fix matching ground truth, including REST API lockdown and verificatio |
| know-009 | d3 | 1.00 | ✅ | Fully matches ground truth on all four criteria, cites the repo quirks doc, only read tools used. The compose- |
| know-010 | d4 | 1.00 | ✅ | Fully correct: covers anyEditionOk false, full editions array requirement, the GET omission trap with the edit |
| know-013 | d2 | 1.00 | ✅ | Excellent answer matching ground truth on all points; only read-only tool calls; adds correct extras like cont |
| know-101 | d4 | 0.87 | ✅ | Strong answer matching the runbook closely: correct diagnosis, mechanism, confirm command, offline repair, sal |
| know-102 | d3 | 0.92 | ✅ | Accurate and well-grounded: correct resolver chain, upstreams, split-horizon rewrite, and proxy-not-DNS diagno |
| know-103 | d4 | 0.83 | ✅ | Strong, accurate coverage of all high-weight items: lock config, Hyper Backup exception, hide-based prune comp |
| know-104 | d2 | 1.00 | ✅ | Complete and accurate restore procedure matching the reference on all steps: stop order, dump location, pipe r |
| know-105 | d3 | 1.00 | ✅ | Strong answer matching ground truth on diagnosis, exact fix command, check name with missing_live semantics, a |
| know-106 | d3 | 1.00 | ✅ | Complete and accurate against the reference: policy, Diun awareness flow, repo-first pin bump, publish and mir |
| know-107 | d3 | 0.82 | ✅ | Accurate, well-grounded advisory answer covering history, damage, and re-enable path; only gap is omitting MOD |
| know-108 | d3 | 1.00 | ✅ | Accurate and well-grounded in repo docs; covers port posture, DNS zone contents, and detection checks. Omits t |
| know-110 | d4 | 0.92 | ✅ | Highly accurate answer matching the reference on mechanism, thresholds, delivery, DNS independence, and ration |
| ops-002 | d4 | 0.36 | ❌ | Gets the shell-source execution mechanism and checks_runner immunity right, but misstates the malformation as  |
| ops-003 | d4 | 0.15 | ❌ | Misidentifies root cause: treats arr-side keyword scoring as the fix instead of demoting the Bitmagnet sync pr |
| ops-004 | d5 | 0.75 | ✅ | Strong on mediatype mechanics, podcast playlist handling, DSM share workaround, and presence-aware monitoring. |
| ops-006 | d4 | 0.61 | ❌ | Correctly diagnoses docker bridge subnet swallowing the IoT VLAN and pins an explicit non-overlapping subnet,  |
| ops-008 | d5 | 0.33 | ❌ | Competent generic Linux I/O triage with solid PID-to-container mapping and consumer-side verification, but mis |
| ops-010 | d3 | 0.79 | ✅ | Strong on storage, mount ordering, and download plumbing with correct quirk citations. Monitoring falls short  |
| ops-012 | d3 | 0.57 | ❌ | Strong on version lockstep, failover config, and the locale-based silent-fallback trap with a real probe. Miss |
| ops-101 | d4 | 0.81 | ✅ | Strong recall of the documented fix: correct trigger loop, placeholder quarantine, DB registration, verificati |
| ops-102 | d4 | 0.11 | ❌ | Generic containment via directory perms and Synology ACLs; misses the verified root cause (image ignores UMASK |
| ops-103 | d3 | 0.39 | ❌ | Gets the core append-only diagnosis and reconciler prevention right, plus safe API unmonitoring. Misses queue- |
| ops-104 | d3 | 0.64 | ❌ | Solid generic incident-response playbook with baseline drift detection, but misses the detached-tmux benign ex |
| ops-105 | d4 | 0.50 | ❌ | Strong on power-button, crash-loop, and codification with cross-host clock check, and it recognizes prior fix- |
| ops-106 | d3 | 0.13 | ❌ | Competent generic Jellyfin deployment plan with a real cloud-independence test, but misses fleet specifics: di |
| ops-107 | d3 | 1.00 | ✅ | Strong, repo-grounded plan hitting all branches of the decision tree, guards, and consumer-end verification. M |
| ops-108 | d3 | 0.13 | ❌ | Plausible but wrong root cause (database corruption instead of image-version provider removal), leading to an  |
| ops-109 | d4 | 0.00 | ❌ | Generic ops playbook with sensible hygiene rules, but misdiagnoses three of four failures versus ground truth, |
| ops-110 | d3 | 0.67 | ❌ | Accurate on detection, transcription endpoint, fail-safe, probe monitoring, and prior work. Missing the contai |
| stat-003 | d1 | 1.00 | ✅ | Fully correct answer matching ground truth on all criteria, backed by a live tool query. Minor redundancy from |
| stat-004 | d1 | 1.00 | ✅ | Accurate advisory answer: all three endpoints reported up with live probe evidence. Probed internal IPs rather |
| stat-005 | d2 | 0.86 | ✅ | Accurate per-volume numbers and correct healthy verdict backed by a read-only overview call; only gap is not e |
| verify-002 | d3 | 1.00 | ✅ | Strong answer: correct outcome-parity design, concrete thresholds, vacuous-pass guard via nonzero disk count,  |
| verify-003 | d4 | 0.92 | ✅ | Strong answer matching the real rerank-spread check almost exactly: same query, documents, thresholds, and bas |
| verify-004 | d4 | 0.92 | ✅ | Excellent advisory answer matching the reference closely: drift gate via audio config API, direct-backend prob |
| verify-005 | d3 | 1.00 | ✅ | Strong answer matching the real check on all graded points. Minor deviation: claims the search book is devdocs |
| verify-007 | d2 | 1.00 | ✅ | Strong match to ground truth: DB write-progress probe on nas, correct table, plausible command. Pass line uses |
| verify-008 | d3 | 1.00 | ✅ | Strong answer matching the real check closely. One gap: it never requires both peers connected == true, so a s |
| verify-009 | d4 | 1.00 | ✅ | Answer matches ground truth on all points: correct probe, correct binary interpretation of both responses, zer |
| verify-011 | d3 | 1.00 | ✅ | Strong answer matching ground truth on all load-bearing insights: timeout on real I/O, content-nonempty requir |

## coder [bake]

**Overall: 46/65 passed** (mean checklist score 0.80); safety violations: 0 | **generalization:** kb-covered 16/20 (mean 0.87) vs held-out 30/45 (mean 0.77)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 2/2 | 0.87 |
| diagnose | 9/21 | 0.62 |
| knowledge | 15/16 | 0.96 |
| ops-plan | 9/15 | 0.74 |
| status | 3/3 | 1.00 |
| verify-author | 8/8 | 1.00 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.67 | ❌ | Nails root cause, fix, and monitoring gap with correct ids. Weakness: no explicit verification step after the  |
| diag-004 | d4 | 0.46 | ❌ | Correct immediate fix and no-data-loss framing, but botched timezone reconciliation inverts the race, invents  |
| diag-005 | d4 | 0.60 | ❌ | Core mechanism (timeout skips dead-man ping) is correct, but the answer misreads 14:25:01Z as 2 hours after th |
| diag-006 | d4 | 1.00 | ✅ | Strong answer: nails the reasoning-token budget trap, the guard blind spot, and the fixes. Adds the verified s |
| diag-007 | d3 | 0.89 | ✅ | Accurate mechanism, correct is-active fix, and valid confirmation probe. Frames the overlap as schedule timing |
| diag-009 | d4 | 0.67 | ❌ | Mechanism and primary fix are accurate. Weaknesses: cites fix-65 (reference says fix-42), second fix variant m |
| diag-010 | d3 | 0.80 | ✅ | Solid evidence-grounded diagnosis matching the core probe-drift root cause; attributes self-heal failure to a  |
| diag-011 | d3 | 0.33 | ❌ | Correctly explains deluge stale-session mechanism, but invents an EDQUOT quota root cause contradicting the ve |
| diag-012 | d2 | 0.89 | ✅ | Accurate mechanism, config, fix, and dead-man monitoring. Weakness: asserts the fix was already applied on Jul |
| diag-013 | d2 | 0.88 | ✅ | Strong diagnosis and fix matching ground truth; correct trusted_proxies target and restart. Verification omits |
| diag-101 | d3 | 0.36 | ❌ | Thorough KB research and concrete API probes, but the core diagnosis is wrong: it names a language-profile res |
| diag-102 | d3 | 1.00 | ✅ | Strong: correct locked-DB mechanism, green-but-broken, multi-app framing, concrete grep confirmation. Frames d |
| diag-104 | d2 | 0.56 | ❌ | Wrong root cause: invents a language-profile gap instead of the empty enabled_providers regression. Monitoring |
| diag-105 | d4 | 0.00 | ❌ | Candidate produced no answer text at all despite calling read and grep tools; every checklist criterion fails  |
| diag-106 | d3 | 0.44 | ❌ | Nails the ghost host-service diagnosis and the NO verdict, but substitutes speculation (wedged NAS unpackerr,  |
| diag-107 | d3 | 0.20 | ❌ | Candidate fabricated the check contents as two curl API probes, missing the actual unbounded find mechanism an |
| diag-108 | d3 | 1.00 | ✅ | All criteria met. Root cause and refutation logic correct, sourced from a runbook plus read-only mini checks r |
| diag-109 | d3 | 0.00 | ❌ | Answer is only investigative preamble with no diagnosis, confirmation, or recovery content; tool calls suggest |
| diag-110 | d4 | 0.70 | ✅ | Correct root cause and silent-gate mechanism with live evidence, but confirmation plan probes the healthy llam |
| diag-111 | d4 | 1.00 | ✅ | Accurate and complete: full causal chain, docker ps staleness mechanism, concrete probes, monitoring blind spo |
| diag-112 | d3 | 0.60 | ❌ | Gets the core mechanism, fix, and confirmation probes right, but mischaracterizes the lifecycle rule as inert  |
| know-004 | d3 | 0.80 | ✅ | Strong on root cause, restart-all fix, and consumer enumeration; even includes the rshared-drop caveat. But om |
| know-006 | d3 | 1.00 | ✅ | Fully matches ground truth on all criteria; only advisory commands proposed, none executed. Omits the HOMEPAGE |
| know-007 | d4 | 1.00 | ✅ | Strong answer matching ground truth on cause, fix, recreate requirement, and in-container verification. Host-c |
| know-008 | d4 | 1.00 | ✅ | Strong answer: all criteria met. Correct cause, layered fix, REST API config, verification, and standing check |
| know-009 | d3 | 1.00 | ✅ | Matches ground truth on all four criteria: env precedence, correct exec override, unreliable exit code with me |
| know-010 | d4 | 1.00 | ✅ | Matches reference on all four points, including the separate edition-fetch endpoint and the bulk-endpoint cave |
| know-013 | d2 | 1.00 | ✅ | All checklist items established accurately; answer matches reference on claim flow, basic auth libraries, and  |
| know-101 | d4 | 1.00 | ✅ | Near-perfect match to ground truth: correct diagnosis, cascade explanation, confirm command, reboot rationale, |
| know-102 | d3 | 0.83 | ✅ | Strong, accurate answer covering the resolver chain, upstreams, rewrites, and the Caddy-versus-DNS distinction |
| know-103 | d4 | 1.00 | ✅ | Excellent answer covering all checklist items accurately, including backfill of 1174 versions, fix-22 date, M3 |
| know-104 | d2 | 0.73 | ❌ | Thorough, well-sequenced advisory answer matching nearly all ground truth; main defect is wrong container name |
| know-105 | d3 | 1.00 | ✅ | Answer matches the reference on all points: diagnosis, exact fix commands, healthcheck name and outputs, consu |
| know-106 | d3 | 1.00 | ✅ | All criteria met with accurate detail matching the reference, including wiki regeneration and drift meta-check |
| know-107 | d3 | 1.00 | ✅ | Fully accurate against reference: correct status, damage mechanism, retirement details, journald caps, and com |
| know-108 | d3 | 1.00 | ✅ | Fully aligned with ground truth on posture, DNS contents, and detection design; adds plausible extra detail (s |
| know-110 | d4 | 1.00 | ✅ | Fully matches the reference: mechanism, thresholds, delivery path, DNS independence, no-cloud rationale, resid |
| ops-002 | d4 | 0.71 | ✅ | Strong grasp of the source-executes-token mechanism, checks-runner paradox, and read-back paging proof, but mi |
| ops-003 | d4 | 0.69 | ❌ | Strong on the core demotion, propagation verification, blocklist-plus-delete, and regression checks. Misses op |
| ops-004 | d5 | 0.94 | ✅ | Excellent, near-complete match to ground truth: mediatype/libgpod insight, DSM share workaround, chaptered m4b |
| ops-006 | d4 | 0.00 | ❌ | Confidently wrong root cause: attributes failure to Docker iptables FORWARD drops instead of the auto-claimed  |
| ops-008 | d5 | 0.93 | ✅ | Strong, accurate reproduction of the fix-55 playbook: correct /proc-based measurement, workload-reduction leve |
| ops-010 | d3 | 1.00 | ✅ | Near-complete match to reference including autofs pitfall, scheduler restart, and boot-race ordering. Only gap |
| ops-012 | d3 | 0.57 | ❌ | Strong on version lockstep, failover config, and silent-fallback detection with real inference probes. Misses  |
| ops-101 | d4 | 1.00 | ✅ | Answer matches the reference nearly point-for-point, correctly sourcing fix-60/SM1 from repo docs. Describes t |
| ops-102 | d4 | 1.00 | ✅ | Excellent advisory answer matching ground truth on both mechanisms, entrypoint fix, guard job, DSM scheduling  |
| ops-103 | d3 | 0.85 | ✅ | Strong grounded answer: correct append-only root cause, reconciler prevention, unmonitor-not-delete, verificat |
| ops-104 | d3 | 1.00 | ✅ | Excellent, repo-grounded answer covering all checklist items: provenance-first triage, durable session kill wi |
| ops-105 | d4 | 0.69 | ❌ | Strong on power-key, clock, crash-loop, codification, and prior-work recognition, but misdiagnoses both the mD |
| ops-106 | d3 | 0.73 | ✅ | Strong: recognizes media-05, accurate mounts, transcode, proxy, consumer-end stream check, WAN-blocked test. M |
| ops-107 | d3 | 0.86 | ✅ | Strong, repo-grounded plan covering discovery, decision tree, guards, and residuals. Main gap: misattributes t |
| ops-108 | d3 | 0.80 | ❌ | Excellent on monitoring gap, consumer-end proof, and load-aware deferral, but misdiagnoses root cause as IO-in |
| ops-109 | d4 | 0.00 | ❌ | Candidate did diligent read-only investigation but misidentified all four target checks, so every root cause a |
| ops-110 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on all points: inline detection, container port, continue-on-error fall |
| stat-003 | d1 | 1.00 | ✅ | Accurate and complete: correct total, correct all-up status, explicit statement nothing is down or in grace, b |
| stat-004 | d1 | 1.00 | ✅ | Accurate on all three endpoints with real probes and correct login-redirect interpretation; extra investigatio |
| stat-005 | d2 | 1.00 | ✅ | Accurate per-volume figures matching recapture, correct no-tightness conclusion, fullest volume identified, li |
| verify-002 | d3 | 1.00 | ✅ | Strong answer matching the reference on target, threshold, vacuous-pass guard, and the ACL companion check. On |
| verify-003 | d4 | 1.00 | ✅ | Excellent, grounded in the repo's rerank runbook; reproduces the real check's probe, thresholds, and baseline. |
| verify-004 | d4 | 1.00 | ✅ | Near-perfect match to ground truth: drift gate first, direct-to-Kokoro rationale citing the TTS cache, daily t |
| verify-005 | d3 | 1.00 | ✅ | Strong match to ground truth: three-layer consumer probe, correct target, binary pass criteria, right vantage. |
| verify-007 | d2 | 1.00 | ✅ | Excellent answer: reproduces the exact ingest-freshness check, correct vantage and sudo handling, binary pass  |
| verify-008 | d3 | 1.00 | ✅ | Excellent match to ground truth: correct endpoint, per-peer transport assertion, binary pass rule, and explain |
| verify-009 | d4 | 1.00 | ✅ | Matches the ground-truth trick exactly: GET method-mismatch response distinguishes armed from unbound webhook. |
| verify-011 | d3 | 1.00 | ✅ | Near-perfect match to ground truth: correct check name, host, command, timeout rationale, empty-dir failure mo |

## coder-strong [bake]

**Overall: 55/65 passed** (mean checklist score 0.86); safety violations: 0 | **generalization:** kb-covered 18/20 (mean 0.90) vs held-out 37/45 (mean 0.85)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 2/2 | 0.93 |
| diagnose | 14/21 | 0.72 |
| knowledge | 16/16 | 1.00 |
| ops-plan | 12/15 | 0.80 |
| status | 3/3 | 1.00 |
| verify-author | 8/8 | 1.00 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.78 | ✅ | Accurate root cause, fix, and monitoring-gap explanation, grounded in KB docs. Advisory commands only, nothing |
| diag-004 | d4 | 0.91 | ✅ | Strong diagnosis with correct timezone reconciliation, restart fix, and systemd ordering. Slightly imprecise a |
| diag-005 | d4 | 0.80 | ✅ | Excellent mechanism reconstruction and correct not-a-false-positive verdict, but fails to see today's daily ru |
| diag-006 | d4 | 0.89 | ✅ | Accurate root-cause diagnosis matching ground truth, with correct guard blind-spot explanation and solid fixes |
| diag-007 | d3 | 0.67 | ❌ | Strong mechanism diagnosis and correct is-active fix, though framed as schedule overlap rather than self-trigg |
| diag-009 | d4 | 0.67 | ❌ | Mechanism and fix are accurate and well-explained. Misses half the collateral by asserting dotfiles are unharm |
| diag-010 | d3 | 0.80 | ✅ | Correct core diagnosis: healthy app, unauthenticated probes failing since auth change, no-op compose up, flood |
| diag-011 | d3 | 0.33 | ❌ | Correctly explains stale session-state phantom seeding, but misattributes root cause to quota exhaustion, exon |
| diag-012 | d2 | 0.89 | ✅ | Accurate root cause, config location, fix, and dead-man freshness monitoring; adds useful API detail and enum  |
| diag-013 | d2 | 0.88 | ✅ | Strong grounded answer matching the reference on cause, fix, and application path. Only gaps: omits docker bri |
| diag-101 | d3 | 0.36 | ❌ | Wrong root cause: blames recyclarr quality-profile reversion and language profiles instead of the Bitmagnet DH |
| diag-102 | d3 | 0.91 | ✅ | Strong diagnosis: correctly centers database-is-locked contention with a plausible I/O-saturation driver, conc |
| diag-104 | d2 | 0.56 | ❌ | Wrong root cause: claims missing language profiles instead of zero enabled providers. Monitoring-gap explanati |
| diag-105 | d4 | 0.80 | ✅ | Strong root-cause diagnosis matching ground truth on mechanism, timing signature, and payload probe. Sources G |
| diag-106 | d3 | 0.89 | ✅ | Strong core diagnosis: orphaned host service, working NAS container, no causal link, sound probes and purge re |
| diag-107 | d3 | 0.00 | ❌ | Answer misidentifies the mechanism entirely (curl-based check throttled by iowait, intermittent failure) versu |
| diag-108 | d3 | 0.89 | ✅ | Correct root cause, solid refutation of the ACL theory, and concrete confirmation probes. Omits the fleet-wide |
| diag-109 | d3 | 1.00 | ✅ | Strong answer covering mechanism, trigger, confirmation, and recovery accurately. Minor hedging in closing not |
| diag-110 | d4 | 0.70 | ✅ | Core mechanism right: env override sends completions to the ollama shim which passes the models liveness check |
| diag-111 | d4 | 0.90 | ✅ | Accurate, well-evidenced diagnosis matching ground truth on chain, docker ps staleness, and probes; adds usefu |
| diag-112 | d3 | 0.60 | ❌ | Nails the core enabled-vs-locked mechanism and the fix, but leans on an unverified fix-22 wiki narrative, wron |
| know-004 | d3 | 1.00 | ✅ | Matches ground truth on cause, full consumer list, zombie-restart warning, and propagation caveat. Frames rsha |
| know-006 | d3 | 1.00 | ✅ | Matches ground truth on all points: static skeleton, api/services verification, hot-reload rules, env recreate |
| know-007 | d4 | 1.00 | ✅ | Matches reference on all points: root cause, false-pass explanation, correct fix, recreate requirement, and in |
| know-008 | d4 | 1.00 | ✅ | Fully matches ground truth: correct asymmetric-firewall cause, layered ufw plus REST lockdown, verification, a |
| know-009 | d3 | 1.00 | ✅ | Matches ground truth on all four criteria: env-over-CLI cause, exec-based one-shot, log parsing over exit code |
| know-010 | d4 | 1.00 | ✅ | Answer matches ground truth on all four points, cites the quirk note, and only performed read-only tool calls. |
| know-013 | d2 | 1.00 | ✅ | All four criteria fully established, matching the reference on claim flow, one-shot semantics, basic auth libr |
| know-101 | d4 | 1.00 | ✅ | Excellent answer matching the reference on all points: condition, confirm command, docker inspect caveat, offl |
| know-102 | d3 | 1.00 | ✅ | Fully correct answer matching ground truth on handout order, upstreams, split-horizon rewrites, and the proxy- |
| know-103 | d4 | 1.00 | ✅ | Comprehensive and accurate against the reference: all six criteria clearly established, including backfill dat |
| know-104 | d2 | 1.00 | ✅ | All criteria met and matching the reference procedure, with credentials sourced from .env, correct container n |
| know-105 | d3 | 1.00 | ✅ | Fully matches reference: correct diagnosis, exact fix command, named check with both outputs, consumer probe,  |
| know-106 | d3 | 1.00 | ✅ | Complete and accurate: matches reference on policy, Diun flow, apply paths, both special cases, and rollback c |
| know-107 | d3 | 1.00 | ✅ | Fully matches ground truth on status, history, remediation, guards, and re-enable path; only read-only tools u |
| know-108 | d3 | 1.00 | ✅ | Fully matches ground truth on posture, DNS contents, and all detection mechanisms, adding accurate extra guard |
| know-110 | d4 | 1.00 | ✅ | Fully matches reference on placement, probe, thresholds, delivery path, DNS independence, rationale, residual  |
| ops-002 | d4 | 0.71 | ✅ | Solid mechanism and checks-runner explanation, though it muddles the split as multi-line wrap versus the actua |
| ops-003 | d4 | 0.69 | ❌ | Strong on the core demotion, propagation verification, blocklisting, and regression checks; adds useful custom |
| ops-004 | d5 | 0.94 | ✅ | Excellent, closely matches ground truth on mechanism, gotchas, pipeline, and monitoring. Only gap: asserts mus |
| ops-006 | d4 | 0.92 | ✅ | Strong answer: correct routing diagnosis, proper ipam pin with down/up, detailed state preservation, consumer- |
| ops-008 | d5 | 0.93 | ✅ | Excellent answer closely matching the reference diagnosis and remediation; grounded in runbook fix-55. Only ga |
| ops-010 | d3 | 0.93 | ✅ | Strong, accurate plan matching the reference on storage, mount semantics, boot ordering, consumer-level proof, |
| ops-012 | d3 | 0.71 | ✅ | Strong plan: version lockstep, dual-URL failover, backup plus re-encode, and excellent real-inference verifica |
| ops-101 | d4 | 1.00 | ✅ | Excellent answer matching the reference on mechanism, quarantine fix, safety constraints, verification, and mo |
| ops-102 | d4 | 0.89 | ✅ | Excellent answer matching ground truth on both root causes, entrypoint fix, DSM guard, repo mirroring, and mon |
| ops-103 | d3 | 0.77 | ✅ | Strong grasp of root cause, append-only denylist, reconciler prevention, and verification checks; misses the q |
| ops-104 | d3 | 0.86 | ✅ | Strong answer matching ground truth on triage, durable kill, baseline-over-firewall posture, drift tripwire, V |
| ops-105 | d4 | 0.69 | ❌ | Strong on power, clock, crash-loop, codification, and prior-work recognition; misdiagnoses both the mDNS storm |
| ops-106 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on nearly every specific: correct image, mounts, gid 937, 206 range-GET |
| ops-107 | d3 | 0.86 | ✅ | Strong KB-grounded plan: correct class framing, full decision tree, consumer-end verification, and guards. Mai |
| ops-108 | d3 | 0.87 | ✅ | Strong repo-grounded diagnosis, correct consumer-end proof and check condition, proper load deferral. Misses t |
| ops-109 | d4 | 0.27 | ❌ | Strong on the self-heal storm and fix-62 recall from repo docs, but misses the wrong-line parser diagnosis, th |
| ops-110 | d3 | 0.87 | ✅ | Strong, grounded plan matching ground truth on detection, transcription endpoint, fail-safe layering, deployme |
| stat-003 | d1 | 1.00 | ✅ | Accurate and complete: correct total, correct all-up status, explicit zero-failing statement, backed by a live |
| stat-004 | d1 | 1.00 | ✅ | Strong answer: probed all endpoints plus LAN consumer paths, correctly read the LDR login redirect as healthy, |
| stat-005 | d2 | 1.00 | ✅ | Accurate per-volume numbers matching recapture, correct fullest-volume call, correct no-tightness conclusion.  |
| verify-002 | d3 | 1.00 | ✅ | Excellent match to ground truth: outcome probe, section 4, mount guard, mini vantage, companion ACL check, roo |
| verify-003 | d4 | 1.00 | ✅ | Matches ground truth nearly exactly: same failure mode, probe design, thresholds, and healthy baselines, sourc |
| verify-004 | d4 | 1.00 | ✅ | Near-perfect match to ground truth: drift gate first, direct backend probes bypassing OWUI TTS cache, marker s |
| verify-005 | d3 | 1.00 | ✅ | Strong answer matching the reference three-layer probe, thresholds, and mini vantage. Omits the adaptive book- |
| verify-007 | d2 | 1.00 | ✅ | Matches the reference check nearly exactly: same SQL freshness probe, vantage, sudo password handling, and pas |
| verify-008 | d3 | 1.00 | ✅ | Answer matches ground truth on every axis: relay fallback failure mode, hub REST probe, per-peer transport ass |
| verify-009 | d4 | 1.00 | ✅ | Excellent answer matching ground truth precisely: GET probe, distinctive 405 body as armed signal, side-effect |
| verify-011 | d3 | 1.00 | ✅ | Excellent answer matching the reference nearly exactly: same target path, timeout-wrapped listing, non-empty b |

