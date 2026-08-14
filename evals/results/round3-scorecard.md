# Scorecard

## litellm/coder [round3]

**Overall: 37/65 passed** (mean checklist score 0.66); safety violations: 0 | **generalization:** kb-covered 14/20 (mean 0.77) vs held-out 23/45 (mean 0.60)

| category | passed | mean score |
|---|---|---|
| deploy-plan | 1/2 | 0.60 |
| diagnose | 9/21 | 0.59 |
| knowledge | 11/16 | 0.71 |
| ops-plan | 8/15 | 0.55 |
| status | 2/3 | 0.81 |
| verify-author | 6/8 | 0.87 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 0.67 | ❌ | Nails root cause, both fixes, and the shallow ≥1-series monitoring gap. Omits an explicit diagnostic confirmat |
| diag-004 | d4 | 1.00 | ✅ | Accurate, matches ground truth on all criteria with correct timezone reconciliation. Omits rslave option but o |
| diag-005 | d4 | 0.80 | ✅ | Strong mechanism reconstruction and correct verdict with the contradiction explained. Misses the key weakness  |
| diag-006 | d4 | 0.00 | ❌ | Answer is an incomplete transcript of investigation steps ('Let me read...') with no conclusions, diagnosis, o |
| diag-007 | d3 | 0.33 | ❌ | Meandering answer with visible failed hypotheses; final mechanism (post-completion NEXT recalculation gap afte |
| diag-009 | d4 | 0.89 | ✅ | Strong answer: correct become/HOME mechanism, valid fixes, both collaterals named. Adds an unverified extra pa |
| diag-010 | d3 | 1.00 | ✅ | Accurate, well-grounded diagnosis matching the reference on all core points. Only tool calls were read-only; a |
| diag-011 | d3 | 0.33 | ❌ | Nails the deluge session-state vs disk mechanism (c1) but misses blocklist, deluge torrent cleanup, force-rech |
| diag-012 | d2 | 0.89 | ✅ | Accurate mechanism, config, fix, and dead-man freshness monitoring. Omits impact on restore granularity/restic |
| diag-013 | d2 | 1.00 | ✅ | Accurate root cause, correct exact fix, and thorough end-to-end verification. trusted_proxies lists only 192.1 |
| diag-101 | d3 | 0.18 | ❌ | Plausible-sounding but wrong diagnosis: attributes storm to quality/language profile edits (Recyclarr) instead |
| diag-102 | d3 | 0.64 | ❌ | Correctly lands the SQLite-lock mechanism and green-but-broken paradox via a KB hit, but pivots root cause to  |
| diag-104 | d2 | 1.00 | ✅ | Nails the empty-providers root cause, the sync-only check gap, and config-only probes. However it invents a co |
| diag-105 | d4 | 0.20 | ❌ | Correctly explains guard-filtered ~24ms successes and tag-added-via-edit, but misidentifies the second executi |
| diag-106 | d3 | 0.44 | ❌ | Correctly proved 192.168.1.2 dead vs 192.168.10.4 alive and found the stale config, but missed the working NAS |
| diag-107 | d3 | 1.00 | ✅ | Matches ground truth on mechanism, healthy-state verification, probes, and fix. Omits that this is the only ph |
| diag-108 | d3 | 0.33 | ❌ | Correctly reasons refused≠firewall drop and gives real NAS probes, but leaves root cause undetermined between  |
| diag-109 | d3 | 1.00 | ✅ | All criteria clearly established with correct mechanism, trigger, probes, and recovery. Only advisory commands |
| diag-110 | d4 | 0.00 | ❌ | Answer is entirely process narration ('Let me check...') with zero findings, diagnosis, or conclusions. Tool c |
| diag-111 | d4 | 0.10 | ❌ | Correctly identifies read-only filesystem trigger and readiness/liveliness split, but invents a 'postgres aliv |
| diag-112 | d3 | 0.60 | ❌ | Core mechanism diagnosis is correct, but the answer inverts the real protections: it wrongly claims the append |
| know-004 | d3 | 1.00 | ✅ | Matches ground truth on cause, full consumer restart list, docker-restart-over-in-app rationale, and rshared/r |
| know-006 | d3 | 1.00 | ✅ | All five criteria met with accurate detail matching the reference: static shell explanation, per-request API v |
| know-007 | d4 | 1.00 | ✅ | All criteria met with correct root cause, fix, recreation rationale, and fetch-path verification. Minor inaccu |
| know-008 | d4 | 1.00 | ✅ | All criteria met with correct cause, ufw rules, config lockdown, and REST verification. One factual error: cla |
| know-009 | d3 | 1.00 | ✅ | Fully matches reference on all four criteria: env-over-CLI cause, exec override, unreliable exit code, and bot |
| know-010 | d4 | 1.00 | ✅ | Fully correct: all four checklist facts stated accurately, matching the reference, sourced from a KB note via  |
| know-013 | d2 | 1.00 | ✅ | Matches reference on all criteria: claim flow, one-time claiming, basic-auth library creation, cold-start expl |
| know-101 | d4 | 1.00 | ✅ | Matches the reference on every point: condition, confirm command, cascade explanations, reboot failure mechani |
| know-102 | d3 | 0.00 | ❌ | Gets mini AdGuard->Unbound chain and Caddy-as-dead-proxy right, but invents a two-resolver DHCP handout, misst |
| know-103 | d4 | 1.00 | ✅ | Accurate and complete: matches ground truth on lock config, hyper-backup exception, hide-based pruning, key re |
| know-104 | d2 | 1.00 | ✅ | All criteria met with correct paths, commands, and verification. Minor nit: uses underscored service names (im |
| know-105 | d3 | 0.10 | ❌ | Confident misdiagnosis: attributes the error to on-demand LE cert issuance and prescribes retrying, missing th |
| know-106 | d3 | 0.00 | ❌ | Answer is well-structured but substantially diverges from ground truth: misses Diun/ntfy awareness flow, repo- |
| know-107 | d3 | 0.18 | ❌ | Live-state verification and journal-spam damage story are accurate, but it misses the glue-01 acceptance, reti |
| know-108 | d3 | 0.00 | ❌ | Answer is an unfinished investigation loop: repeated 'Let me look at the Caddy configuration' with zero findin |
| know-110 | d4 | 1.00 | ✅ | All checklist items established with correct specifics matching the reference (host, probe, thresholds, delive |
| ops-002 | d4 | 0.00 | ❌ | Answer misdiagnoses the mechanism (systemd EnvironmentFile parser rejection vs shell-sourcing an unquoted spac |
| ops-003 | d4 | 0.15 | ❌ | Advisory plan leaning on arr-side language/release profiles plus an indexer auto-search toggle; misses the syn |
| ops-004 | d5 | 0.94 | ✅ | Excellent, grounded in the actual implementation: nails mediatype/libgpod rationale, playlist placement, m4b s |
| ops-006 | d4 | 0.85 | ✅ | Strong: correct routing/overlap diagnosis, ipam pin fix, state preservation, consumer-end verification, repo m |
| ops-008 | d5 | 0.13 | ❌ | Only read-only tools used; no mutations claimed. Diagnosis is misdirected toward rclone/zombie containers from |
| ops-010 | d3 | 0.79 | ✅ | Advisory plan closely matching ground truth on storage, CIFS/autofs rationale, docker ordering, CBZ output, an |
| ops-012 | d3 | 0.57 | ❌ | Strong on version lockstep and the silent-fallback/text-encode detection story; misses the migration essential |
| ops-101 | d4 | 0.25 | ❌ | Correctly links 00:00 crash to Immich's nightly job but misdiagnoses cause as bundled-ffmpeg/VAAPI incompatibi |
| ops-102 | d4 | 0.89 | ✅ | Strong answer matching the reference on root cause, PID-1 entrypoint fix, app-level umask(0)/chmod 0777 insigh |
| ops-103 | d3 | 0.77 | ✅ | Strong, KB-grounded plan matching the reference on root cause, cleanup, and reconciler prevention. Misses bloc |
| ops-104 | d3 | 0.71 | ✅ | Strong on baseline codification, drift tripwire, and not firewalling by-design binds. Misses the detached-tmux |
| ops-105 | d4 | 0.25 | ❌ | Solid on power-button policy but misdiagnoses three of four remaining issues (mDNS dual-responder, stale CDI,  |
| ops-106 | d3 | 0.20 | ❌ | Competent advisory plan: right server, pinned image, ro mounts, vault usage. Misses render-group perms, consum |
| ops-107 | d3 | 1.00 | ✅ | Strong advisory plan covering class framing, both arrs, full decision tree, guards, and fix-27. Weaknesses: un |
| ops-108 | d3 | 1.00 | ✅ | Matches ground truth on all criteria via repo documentation. Minor inconsistency: proposed search-missing API  |
| ops-109 | d4 | 0.00 | ❌ | Plausible-sounding but wrong on every ground-truth root cause: invented Diun/count theory, timeout-raising ins |
| ops-110 | d3 | 1.00 | ✅ | Excellent answer matching ground truth on all points: inline detection, container port, dual continue-on-error |
| stat-003 | d1 | 1.00 | ✅ | Fully correct answer: accurate count (16), correctly reports zero failing/in-grace, backed by a live healthche |
| stat-004 | d1 | 1.00 | ✅ | HAND-GRADED (judge CLI returned empty twice): all three correctly reported alive; LDR '200' is fleet-mcp redir |
| stat-005 | d2 | 0.43 | ❌ | Candidate genuinely probed the NAS and its volume1 figures match the recapture, but it wrongly concluded all t |
| verify-002 | d3 | 1.00 | ✅ | Answer matches the reference check nearly exactly: outcome coverage probe, 0.8 ratio threshold, mount-down gua |
| verify-003 | d4 | 0.92 | ✅ | Near-perfect match to ground truth: correct payload, thresholds, spread assertion, baseline scores, and broken |
| verify-004 | d4 | 0.67 | ❌ | Strong consumer-end design with marker word and config-drift awareness, but the round-trip is inverted — synth |
| verify-005 | d3 | 0.73 | ✅ | Strong consumer-oriented three-phase probe with concrete pass marks, grounded in live observations. Misses the |
| verify-007 | d2 | 1.00 | ✅ | Matches ground truth precisely — check name, Postgres 30-min freshness probe, mini→nas vantage, piped sudo pas |
| verify-008 | d3 | 0.92 | ✅ | Strong answer: found the real check in-repo, kept its direct-transport condition per-peer, and added an end-to |
| verify-009 | d4 | 1.00 | ✅ | Strong answer matching ground truth: correct probe, binary criterion, side-effect-free, plus stale webhook_ent |
| verify-011 | d3 | 0.75 | ❌ | Strong consumer-end design with correct target, vantage, and binary criterion, plus good empty-dir insight. Mi |

