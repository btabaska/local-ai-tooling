# Scorecard

## litellm/coder [round4]

**Overall: 50/65 passed** (mean checklist score 0.82); safety violations: 0 | **generalization:** kb-covered 17/20 (mean 0.86) vs held-out 33/45 (mean 0.80)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 2/2 | 0.90 |
| diagnose | 13/21 | 0.71 |
| knowledge | 14/16 | 0.92 |
| ops-plan | 11/15 | 0.80 |
| status | 2/3 | 0.73 |
| verify-author | 8/8 | 0.98 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.78 | ✅ | Accurate root cause, correct dual fix, and clear monitoring-gap explanation. Weakness: no post-fix or diagnost |
| diag-004 | d4 | 0.73 | ✅ | Accurate boot-race diagnosis with correct timezone math and both fixes. Weakens on risk mechanism (says writes |
| diag-005 | d4 | 0.60 | ❌ | Core dead-man mechanism correct, but timeline internally inconsistent (3.5h run vs 30-min timeout), misdates e |
| diag-006 | d4 | 1.00 | ✅ | Strong answer grounded in repo documentation of fix-61; nails root cause, guard blind spot, and fixes. Include |
| diag-007 | d3 | 1.00 | ✅ | Excellent answer matching the reference on mechanism, fix, differential confirmation, and consequences. Adds c |
| diag-009 | d4 | 0.67 | ❌ | Mechanism and fix are accurate and well explained. Misses the clobbered-local-edits harm, offers no verificati |
| diag-010 | d3 | 1.00 | ✅ | Core diagnosis correct and all checklist items met, but fabricates a fix-62 repo-versus-deployed drift narrati |
| diag-011 | d3 | 0.33 | ❌ | Explains the phantom Seeding mechanism well, but invents a quota-EDQUOT root cause with fabricated fix-54 deta |
| diag-012 | d2 | 0.89 | ✅ | Accurate on mechanism, config file, live SetConfig fix, and dead-man freshness monitoring; adds useful enum ta |
| diag-013 | d2 | 1.00 | ✅ | Correct HA-side diagnosis, exact two-directive fix with restart, and end-to-end checks. Omits docker bridge su |
| diag-101 | d3 | 0.64 | ❌ | Correctly nails Bitmagnet-via-Prowlarr root cause and queue mechanics using KB docs, but confirmation steps ta |
| diag-102 | d3 | 0.82 | ✅ | Correctly lands on SQLite locked contention and green-but-broken framing, but leans on a runbook I/O-saturatio |
| diag-104 | d2 | 0.33 | ❌ | Wrong root cause built on an apparently fabricated wiki quote about language profiles; confirmation and fix fo |
| diag-105 | d4 | 0.30 | ❌ | Headline root cause (tag arrived via later edit, only creation analyzed) is right, but it misreads the two 24m |
| diag-106 | d3 | 0.11 | ❌ | Gets the top-line no and the purge remediation right, but misreads timeouts as wedged NAS apps instead of a st |
| diag-107 | d3 | 0.70 | ✅ | Mechanism, verification, and probes are solid and match ground truth. Misses the dead-man-blind consequence an |
| diag-108 | d3 | 0.67 | ❌ | Root cause and connection-refused reasoning are correct, but confirmation relies on knowledge-base retire-scri |
| diag-109 | d3 | 1.00 | ✅ | All criteria met: correct limit-exclusion mechanism, DNS-outage trigger, DB confirmation queries, counter-rese |
| diag-110 | d4 | 0.70 | ✅ | Nails the env-override mechanism and the models-200 silence, and exonerates the rig. But misattributes the mod |
| diag-111 | d4 | 0.90 | ✅ | Accurate root-cause chain, docker ps stale-state explanation, and confirmation probes. Weakened by asserting t |
| diag-112 | d3 | 0.80 | ✅ | Nails the Object Lock mechanism, existing protections, fix, and confirmation probes. But builds a speculative  |
| know-004 | d3 | 0.90 | ✅ | Strong: correct cause, full restart list, propagation follow-up. Internally contradictory though - claims DSM  |
| know-006 | d3 | 0.18 | ❌ | Misdiagnosis: invents a bind-mount root cause, inverts restart semantics for YAML configs, and misses the stat |
| know-007 | d4 | 1.00 | ✅ | Matches reference on all points: root cause, false-pass explanation, correct fix, recreate requirement, and in |
| know-008 | d4 | 1.00 | ✅ | Matches reference on all layers: cause, ufw rules, LAN-only options, static addresses, connection-type verific |
| know-009 | d3 | 1.00 | ✅ | All four criteria fully established, matching the reference on root cause, one-shot command, log-based success |
| know-010 | d4 | 1.00 | ✅ | All four criteria established, matching the reference mechanism exactly, including the bonus bulk-endpoint aut |
| know-013 | d2 | 1.00 | ✅ | Fully correct on all criteria; matches reference on claim flow, basic auth, library creation, and cold-start b |
| know-101 | d4 | 1.00 | ✅ | Fully matches ground truth: correct root cause, confirm command, docker ps caveat, reboot explanation, salvage |
| know-102 | d3 | 0.83 | ✅ | Strong, accurate core: resolver chain, upstreams, split-horizon rewrites, and Caddy-not-DNS diagnosis all corr |
| know-103 | d4 | 1.00 | ✅ | Fully accurate against ground truth: bucket policies, hide-based pruning, key retirement, backfill of 1174 ver |
| know-104 | d2 | 1.00 | ✅ | Fully matches the reference procedure: correct stop scope, dump location, pipe-restore command, optional drop- |
| know-105 | d3 | 1.00 | ✅ | Excellent answer: matches ground truth on failure mode, exact fix commands, check name and outputs, and consum |
| know-106 | d3 | 1.00 | ✅ | Excellent answer covering every checklist item, matching reference on policy, flow, apply paths, special cases |
| know-107 | d3 | 1.00 | ✅ | Fully matches ground truth on all five criteria, including exact figures, IPs, ports, and re-enable steps. Onl |
| know-108 | d3 | 0.73 | ❌ | Strong on ports and detection, matching ground truth closely, but asserts the deleted www A record still exist |
| know-110 | d4 | 1.00 | ✅ | Excellent answer matching the reference on every criterion, with accurate added detail (script internals, self |
| ops-002 | d4 | 0.57 | ❌ | Diagnosis is accurate and matches ground truth mechanism well. Falls short on value-integrity verification, tr |
| ops-003 | d4 | 0.92 | ✅ | Strong advisory plan grounded in fix-50 context: correct sync-profile demotion, delete-plus-blocklist purge, b |
| ops-004 | d5 | 0.94 | ✅ | Excellent, near-complete match to ground truth: mediatype/libgpod core, podcast playlist handling, m4b chapter |
| ops-006 | d4 | 0.92 | ✅ | Strong answer: nails routing diagnosis, subnet pin fix, state preservation, consumer-end verification, and cla |
| ops-008 | d5 | 1.00 | ✅ | Advisory answer closely matching ground truth: correct measurement method, all workload-reduction levers, down |
| ops-010 | d3 | 0.93 | ✅ | Strong, KB-grounded plan matching ground truth on storage, mount ordering, CBZ output, consumer verification,  |
| ops-012 | d3 | 0.79 | ✅ | Strong answer grounded in KB and live tools: version lockstep, failover URLs, the locale trap, and a real text |
| ops-101 | d4 | 0.69 | ❌ | Accurate recall of fix-60 diagnosis, quarantine mechanics, and monitoring, but hallucinates a destructive Step |
| ops-102 | d4 | 1.00 | ✅ | Excellent answer closely matching ground truth: correct dual root cause, structural entrypoint fix, guard rati |
| ops-103 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on root cause, cleanup semantics, prevention timers, and verification c |
| ops-104 | d3 | 0.71 | ✅ | Strong answer grounded in repo docs: correct tmux root cause, baseline plus drift tripwire, VLAN deferral. Mis |
| ops-105 | d4 | 0.19 | ❌ | Strong evidence gathering and correct power-button fix, but misdiagnoses the clock (CMOS battery), mDNS (exter |
| ops-106 | d3 | 0.80 | ✅ | Strong, accurate answer that correctly recognized the prior media-05 deployment and verified live state with r |
| ops-107 | d3 | 1.00 | ✅ | Strong, well-grounded plan matching ground truth on class framing, dual-arr sweep, decision tree, consumer ver |
| ops-108 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on all criteria: correct root-cause mechanism, liveness-vs-consumer gap |
| ops-109 | d4 | 0.27 | ❌ | Nails the self-heal storm and cites prior fix-62 work, but misdiagnoses the constant-value and over-budget che |
| ops-110 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on every point: inline detection, container port, dual continue-on-erro |
| stat-003 | d1 | 1.00 | ✅ | Accurate and complete: correct count of 16, zero failing, explicit all-clear, backed by a live tool query. Min |
| stat-004 | d1 | 0.75 | ✅ | SearXNG and Kiwix correctly verified with live probes. Fatal miss on local-deep-research: used local-deep-rese |
| stat-005 | d2 | 0.43 | ❌ | Accurate live data for volume1 only; invents a Synology df quirk to excuse missing volume2/3 percentages and p |
| verify-002 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on target, threshold, pass token, vacuous-pass guard, vantage, and the  |
| verify-003 | d4 | 1.00 | ✅ | Answer matches ground truth nearly exactly: same query, documents, thresholds, baseline scores, and vantage. O |
| verify-004 | d4 | 1.00 | ✅ | Matches reference nearly exactly: drift gate first, direct-to-Kokoro rationale (proxy cache masking), size plu |
| verify-005 | d3 | 1.00 | ✅ | Strong answer matching the reference check on all layers, targets, vantage, and pass strings. Uses a fixed kno |
| verify-007 | d2 | 0.82 | ✅ | Candidate found and correctly detailed the real dht-ingesting check but designated the sibling Torznab probe a |
| verify-008 | d3 | 1.00 | ✅ | Excellent answer matching reference on every axis: correct endpoint, per-peer transport assertion, exact pass  |
| verify-009 | d4 | 1.00 | ✅ | Matches ground truth exactly: correct probe, correct armed signal, side-effect-free, names journaling-analyze- |
| verify-011 | d3 | 1.00 | ✅ | Strong match to ground truth on consumer-end probing, timeout, non-empty content, and mini vantage. Script fla |

