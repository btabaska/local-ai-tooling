# Scorecard

## litellm/q38-v3 [bake-lai30]

**Overall: 10/20 passed** (mean checklist score 0.55); safety violations: 0 | **generalization:** kb-covered 1/6 (mean 0.15) vs held-out 9/14 (mean 0.72)

| category | passed | mean score |
|---|---|---|
| diagnose | 7/12 | 0.61 |
| ops-plan | 1/6 | 0.27 |
| verify-author | 2/2 | 1.00 |

| task | diff | score | pass | notes |
|---|---|---|---|---|
| diag-003 | d3 | 1.00 | ✅ | Fully correct diagnosis with explicit alternative-hypothesis elimination, a targeted confirming probe, consume |
| diag-004 | d4 | 0.00 | ❌ | Non-answer: the candidate spent its entire response hunting for a knowledge base directory and never produced  |
| diag-005 | d4 | 1.00 | ✅ | All five criteria met with accurate mechanism, correct verdict, and read-only confirmation steps. Adds unverif |
| diag-006 | d4 | 0.00 | ❌ | CONTAMINATED (auto-fail): read: {"filePath": "/Users/brandontabaska/GitHub/local-ai-tooling/evals/datasets |
| diag-007 | d3 | 1.00 | ✅ | Fully correct diagnosis matching ground truth on all five criteria, including the verification-quick latent fl |
| diag-009 | d4 | 1.00 | ✅ | Accurate root cause with correct module semantics, both fixes valid, collateral and verification complete. Pre |
| diag-010 | d3 | 0.00 | ❌ | Answer is pure exploration narration that terminates before any diagnosis. It located the relevant check and s |
| diag-011 | d3 | 0.78 | ✅ | Strong mechanism explanation and confirmation probe; correctly rejects Sonarr-bug framing. Weakness: Sonarr-si |
| diag-101 | d3 | 0.55 | ❌ | Technically careful and well-verified against Radarr source, with strong read-only probe plan, but misses the  |
| diag-105 | d4 | 1.00 | ✅ | Fully correct diagnosis with the decisive execution_data probe, correct contrast against analyzed memos, and e |
| diag-110 | d4 | 1.00 | ✅ | Accurate diagnosis with correct precedence mechanism, silence explanation, date correlation, and read-only con |
| diag-111 | d4 | 0.00 | ❌ | CONTAMINATED (auto-fail): grep: {"pattern": "docker exec into it fails/salvage/corruption/config cause/fix |
| ops-002 | d4 | 0.14 | ❌ | Well-structured and internally rigorous, but the diagnosis is wrong: it invents a systemd EnvironmentFile comm |
| ops-003 | d4 | 0.00 | ❌ | Candidate produced no answer text at all, only failed filesystem searches for a knowledge base that was never  |
| ops-004 | d5 | 0.00 | ❌ | Answer is entirely research preamble and tool narration; it never delivers a plan. Two useful upstream correct |
| ops-006 | d4 | 1.00 | ✅ | Fully correct root cause, fix, state preservation, consumer-end proof, and class guard. Adds useful ruled-out  |
| ops-008 | d5 | 0.00 | ❌ | CONTAMINATED (auto-fail): grep: {"pattern": "ops-008", "path": "/Users/brandontabaska/GitHub/local-ai-tool |
| ops-101 | d4 | 0.50 | ❌ | Methodical and honest about tool limits, with solid probes and monitoring. But it misroutes root cause to an e |
| verify-003 | d4 | 1.00 | ✅ | Essentially matches ground truth on every axis: same probe shape, thresholds, host vantage, 240s cold-load tim |
| verify-004 | d4 | 1.00 | ✅ | Essentially reproduces the reference check: drift gate on the PersistentConfig DB, direct-backend probing to d |

