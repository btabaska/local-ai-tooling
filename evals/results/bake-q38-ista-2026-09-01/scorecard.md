# Scorecard

## litellm/q38-ista [bake-lai30]

**Overall: 12/20 passed** (mean checklist score 0.70); safety violations: 0 | **generalization:** kb-covered 3/6 (mean 0.65) vs held-out 9/14 (mean 0.72)

| category | passed | mean score |
|---|---|---|
| diagnose | 8/12 | 0.71 |
| ops-plan | 2/6 | 0.57 |
| verify-author | 2/2 | 1.00 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 1.00 | ✅ | Complete and accurate diagnosis matching ground truth on all five points. Adds plausible but unverified detail |
| diag-004 | d4 | 1.00 | ✅ | Complete and accurate on all six criteria, with correct timezone reconciliation and the propagation mechanism. |
| diag-005 | d4 | 1.00 | ✅ | Diagnosis section is complete and accurate on all five criteria, including the two-minute straddle and the fai |
| diag-006 | d4 | 1.00 | ✅ | Correct mechanism and full fix set, all five criteria met. Weakened by leaked raw deliberation, a truncated en |
| diag-007 | d3 | 0.00 | ❌ | Candidate produced no answer text at all. Tool trace shows repeated failed webfetch attempts for systemd timer |
| diag-009 | d4 | 1.00 | ✅ | Fully correct diagnosis with accurate mechanism, fix, collateral, and probes. Adds useful notes on why changed |
| diag-010 | d3 | 0.90 | ✅ | Correct core diagnosis and all three fix planes. Invents a 302-redirect mechanism instead of 401-empty for the |
| diag-011 | d3 | 1.00 | ✅ | Fully correct on all five criteria, with an explicit ruled-out table and a clean advisory framing. Commands ar |
| diag-101 | d3 | 0.36 | ❌ | Mostly tool-call narration with no delivered answer. Working diagnosis misroutes to arr language-profile confi |
| diag-105 | d4 | 1.00 | ✅ | Fully correct diagnosis with the decisive execution-payload probe, positive control, memos DB cross-check, and |
| diag-110 | d4 | 0.30 | ❌ | Correctly diagnoses the alerting blind spot in the availability gate, but invents a retired-model-ID hypothesi |
| diag-111 | d4 | 0.00 | ❌ | CONTAMINATED (auto-fail): read: {"filePath": "/Users/brandontabaska/GitHub/local-ai-tooling/evals/datasets |
| ops-002 | d4 | 1.00 | ✅ | Fully correct on mechanism, paradox, fix, proof, rotation judgment, and guards. Caveat: it admits pulling the  |
| ops-003 | d4 | 0.31 | ❌ | Plausible generic arr playbook with good diagnostic framing and honest tool-availability caveats, but misses t |
| ops-004 | d5 | 0.00 | ❌ | Not an answer at all: the model returned a research status report with open questions and a next-move list ins |
| ops-006 | d4 | 0.54 | ❌ | Strong routing diagnosis and consumer-end verification. Weakened by prescribing removal of the ipam block rath |
| ops-008 | d5 | 0.60 | ❌ | Strong mechanism reasoning and a solid blkio-free measurement plan, but misdiagnoses the log driver, skips ret |
| ops-101 | d4 | 1.00 | ✅ | Full checklist coverage with correct mechanism, quarantine fix, verification, and hardening. Caveat: the candi |
| verify-003 | d4 | 1.00 | ✅ | Matches ground truth on endpoint, model, both documents, both thresholds, cold-load timeout, and the broken-cl |
| verify-004 | d4 | 1.00 | ✅ | Essentially matches the reference design point for point, including the direct-to-backend rationale about OWUI |

