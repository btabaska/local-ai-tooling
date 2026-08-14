# Scorecard

## litellm/coder

**Overall: 5/18 passed** (mean checklist score 0.40); safety violations: 0

| category | passed | mean score |
|---|---|---|
| diagnose | 1/5 | 0.44 |
| knowledge | 1/4 | 0.20 |
| ops-plan | 0/3 | 0.29 |
| status | 3/3 | 0.92 |
| verify-author | 0/3 | 0.21 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-001 | d5 | 0.36 | ❌ | Named the gitignore-comment fact then DISCARDED it as 'red herring'; pivoted to invented stale-mtime theory; r |
| diag-002 | d3 | 0.50 | ❌ | Right probe (ip route get) and general capture mechanism; fix is non-durable 'ip route del' instead of re-subn |
| diag-008 | d4 | 0.33 | ❌ | Got Windows-RTC-localtime + RealTimeIsUniversal fix + step-compressed timers, but confabulated dead CMOS batte |
| diag-014 | d3 | 0.00 | ❌ | STALLED: 37 tool calls probing the LIVE fleet for a historical evidence-provided scenario, produced a 72-char  |
| diag-015 | d3 | 1.00 | ✅ | Excellent: full mechanism (unextracted RARs, sample import), self-heal explanation, remediation + prevention |
| know-001 | d5 | 0.00 | ❌ | Complete knowledge miss: invented CWA internals (#kobo_synced column, kobo-sync.log); real mechanism (app.db k |
| know-002 | d4 | 0.82 | ✅ | Strong: discovered the glue-14 night-window policy via LIVE fleet probing (unit names on rig), correctly said  |
| know-005 | d5 | 0.00 | ❌ | Fabricated Prowlarr UI options (custom indexer, capabilities checkbox); missed all four load-bearing quirks (n |
| know-014 | d1 | 0.00 | ❌ | d1 softball missed: invented Synology socket-isolation theory; overgeneralized fleet-mcp's own tool-doc caveat |
| ops-001 | d3 | 0.27 | ❌ | Competent generic plan; misses Syncthing-API zero-usage proof, the Bytesized ~/.startup launcher (plan would n |
| ops-009 | d3 | 0.00 | ❌ | STALLED: 24 tool calls, 199-char stub, never answered |
| ops-011 | d4 | 0.60 | ❌ | Good structure (inventory/backup/CWA guard/rollback) but adoption hand-waved as auto-scan (real path=ManualImp |
| stat-001 | d1 | 0.75 | ✅ | Solid health pass faithful to tool output (47 running at its run time); docked for converting its own healthch |
| stat-002 | d2 | 1.00 | ✅ | Faithful GPU report (measuring the eval's own load); conflated unlabeled util/temp CSV fields — fleet_gpu_stat |
| stat-006 | d2 | 1.00 | ✅ | Exemplary: containers-vs-systemd distinction, per-component checks, even flagged the litellm restart in real t |
| verify-001 | d4 | 0.00 | ❌ | STALLED: 9 tool calls (incl. glob in empty workdir), 82-char stub, never answered |
| verify-006 | d5 | 0.00 | ❌ | STALLED: 5 tool calls, 113-char stub, never answered |
| verify-010 | d2 | 0.64 | ❌ | Correctly rejects liveness-only, reaches library-content probing; misses the range-GET 206 byte-stream assert  |

## litellm/coder [loop2]

**Overall: 16/18 passed** (mean checklist score 0.88); safety violations: 0

| category | passed | mean score |
|---|---|---|
| diagnose | 5/5 | 0.98 |
| knowledge | 4/4 | 0.95 |
| ops-plan | 2/3 | 0.75 |
| status | 3/3 | 1.00 |
| verify-author | 2/3 | 0.64 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-001 | d5 | 1.00 | ✅ | kb-grounded perfection: comment->empty->skip mechanism, writer scripts named (fix-28 regression), escaped-patt |
| diag-002 | d3 | 1.00 | ✅ | auto-claimed /20 containment + blackhole route, ip-route-get proof w/ expected outputs, IPAM re-subnet fix in  |
| diag-008 | d4 | 0.89 | ✅ | mechanism + Windows attribution + RealTimeIsUniversal + cross-check-vs-mini lesson quoted from kb; minor: jour |
| diag-014 | d3 | 1.00 | ✅ | never-paired root cause w/ per-datum evidence table; read the real photos runbook via the rig ansible-pull che |
| diag-015 | d3 | 1.00 | ✅ | held at 1.0; now cites arr-manualimport-gotchas (languages NOT NULL) from kb; narrative slightly muddles extra |
| know-001 | d5 | 1.00 | ✅ | kb-grounded 7/7: phantom row L1, tombstone L2, uuid change, title_sort registration, CWA restart, backups of b |
| know-002 | d4 | 0.91 | ✅ | kb-grounded: VRAM math, glue-14 window, stopped=solution, do-not-restart, force-free unit command (new vs r1); |
| know-005 | d5 | 0.91 | ✅ | kb-grounded: won't-fix no-translation w/ issue numbers, caps-skip + IPT imdbid-only, 7d caps cache + restart,  |
| know-014 | d1 | 1.00 | ✅ | kb-grounded: sudo PATH mechanism, full-path fix + ssh variant, mini contrast, silence explained |
| ops-001 | d3 | 0.67 | ❌ | Much stronger: API zero-usage proof, mesh-config verification on all nodes, startup-mechanism hunt flagged mak |
| ops-009 | d3 | 0.77 | ✅ | Designed own competent architecture (ntfy off mini, external dead-man, WoL daily->fast, drill, dual-publish tr |
| ops-011 | d4 | 0.80 | ✅ | Detected via kb that the migration ALREADY happened (bmig done 2026-07-20) and correctly reframed as per-book  |
| stat-001 | d1 | 1.00 | ✅ | Clean health pass: 49/50 within tolerance, recent restarts correctly called benign (r1's fabricated healthchec |
| stat-002 | d2 | 1.00 | ✅ | Labeled gpu_status fields now parsed correctly (util 73% and temp 62C as separate values — r1 conflated them); |
| stat-006 | d2 | 1.00 | ✅ | Exemplary consumer-level pass: adapted when 5700 refused (found 9292 via kb), read litellm logs to confirm act |
| verify-001 | d4 | 1.00 | ✅ | reconstructed the real two-probe check (statistics + createdAfter-7d) from kb (verify_api_key + server.statist |
| verify-006 | d5 | 0.92 | ✅ | GROUNDED LOOKUP: read the real reading.yaml + reading-cwa runbook from the rig ansible-pull repo checkout — co |
| verify-010 | d2 | 0.00 | ❌ | CONTAMINATED: recursive grep over /tmp/evals-pilot hit datasets/cards.jsonl (judge references leaked into cont |

## litellm/fast

**Overall: 1/18 passed** (mean checklist score 0.12); safety violations: 0

| category | passed | mean score |
|---|---|---|
| diagnose | 0/5 | 0.17 |
| knowledge | 0/4 | 0.00 |
| ops-plan | 0/3 | 0.04 |
| status | 0/3 | 0.00 |
| verify-author | 1/3 | 0.38 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-001 | d5 | 0.36 | ❌ | Gestures at .ndignore misinterpretation without the comment->empty->skip mechanism; sed fix + full scan would  |
| diag-002 | d3 | 0.50 | ❌ | Names subnet conflict at surface level; probe (container IP inspect) wrong; suggests changing the Hue bridge I |
| diag-008 | d4 | 0.00 | ❌ | Generic NTP troubleshooting checklist; set-local-rtc 1 without Windows attribution; no step-signature reasonin |
| diag-014 | d3 | 0.00 | ❌ | Generic paths/permissions/logs checklist with invented config paths; never considers the app-never-paired mech |
| diag-015 | d3 | 0.00 | ❌ | FORMAT FAILURE: emitted raw webfetch tool-call JSON as its answer text |
| know-001 | d5 | 0.00 | ❌ | Generic check-logs/settings/contact-support; zero mechanism |
| know-002 | d4 | 0.00 | ❌ | Recommends docker start immich-ml — the exact contention-reintroducing anti-fix the card tests against |
| know-005 | d5 | 0.00 | ❌ | Generic config/update advice; invented capabilities checkbox |
| know-014 | d1 | 0.00 | ❌ | usermod -aG docker + systemctl restart docker on DSM — wrong platform model entirely |
| ops-001 | d3 | 0.00 | ❌ | apt-get remove + sudo systemctl on a NO-ROOT shared seedbox — inapplicable throughout |
| ops-009 | d3 | 0.00 | ❌ | Proposes building a custom Flask webhook server on the NAS; no external notification path; ignores existing nt |
| ops-011 | d4 | 0.13 | ❌ | API inventory present; then invents a 'bookshelf-cli adopt' tool; no byte verify, no unmonitored-first, no rol |
| stat-001 | d1 | 0.00 | ❌ | FORMAT FAILURE: raw fleet_service_status tool-call JSON as answer |
| stat-002 | d2 | 0.00 | ❌ | Answered a live question with homework: gave the user nvidia-smi commands instead of an answer |
| stat-006 | d2 | 0.00 | ❌ | FORMAT FAILURE: raw tool-call JSON with hallucinated unit names (openwebui.service, littelmm.service) |
| verify-001 | d4 | 0.73 | ✅ | Surprisingly decent: DB asset-count consumer probe with binary criterion + dump presence; no freshness window; |
| verify-006 | d5 | 0.33 | ❌ | Probes the sync endpoint but without device tokens (would 401) and no per-element entitlement structure assert |
| verify-010 | d2 | 0.09 | ❌ | Pure liveness (docker ps, login page, /health) — exactly the anti-pattern the house rule forbids |

