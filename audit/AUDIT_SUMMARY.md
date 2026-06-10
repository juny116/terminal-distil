# terminal-bench benchmark-bug audit — final summary (2026-06-10)

Automated subagent audit of every task with a hardcoded expected answer (the high-risk
population for test bugs). Each verdict computed by writing+running code (real answer vs
test hardcode), not LLM opinion. too_weak verdicts further verified by ACTUALLY running the
grading test against a deliberately-wrong answer.

## Population
- 3567 total tasks → **540 have hardcoded expected answers** (15%); these are where test
  bugs concentrate. (~3000 tasks check structural properties, lower bug risk for this type.)

## Result (538/540 audited)
| category | count | % of 538 |
|---|---|---|
| **hard-core bug** (unpassable / test demonstrably wrong) | 179 | **33%** |
| **too_weak** (test under-verifies; wrong answer passes) | 107 flagged → **92 execution-confirmed** | 17% confirmed |
| CLEAN | 251 (+15 refuted-too_weak) | ~49% |
| **CONFIRMED BUG (hard-core + confirmed too_weak)** | **271** | **50%** |

### hard-core breakdown
- corrupted_fixture 73 · spec_contradicts_test 60 · hardcoded_preview 46

### too_weak verification (all 107 run against a wrong answer)
- **92 TRIVIAL_PASSES** (wrong/trivial answer passed ALL grading tests → confirmed too weak)
- 15 FAILS (test correctly rejected the wrong answer — over-called; these have real
  correctness checks: SAT solvers, hash verification, MAE, etc.)
- 0 CANT_RUN. **86% of too_weak verdicts confirmed by execution.**

## Representative confirmed bugs (computed / executed)
- apt_cache: test hardcodes 4 packages from a file preview; real SCC computation = 14.
- articulation_points: test hardcodes a 5-edge toy-graph answer; real graph = 62 edges (27 nodes).
- pip_dependency: `numpy==1.24.2` and `==1.23.5` mutually exclusive but test grades 1.24.2 correct.
- aws_lambda / appium / autopsy / saga / many: an empty/fabricated answer passes ALL tests.
- corrupted_fixture pattern: binary files (.o/.so/.bai/.pyc/BMP/git-index) stored as UTF-8
  text or replaced by LLM-generated prose ("I'll generate a valid Java class file...") →
  the benchmark itself was contaminated during LLM-based generation.

## Implications
1. **~50% of hardcoded-expected terminal-bench tasks have a test bug** (computed + execution
   verified). Extrapolated to all 3567: hard-core alone ≈ 5% of the whole benchmark; the true
   rate is higher once non-hardcoded bug types are counted.
2. The static funnel misses these; only an answer-knowing audit catches them. Strong support
   for the contamination thesis and for why verifier-as-ground-truth (arm-C's reward-0→1 gate)
   is fragile.
3. **For data generation: the 271 buggy tasks must be filtered.** clean/bug task lists are in
   audit/FINAL_partition.json; the 15 refuted-too_weak are in this file (treat as usable).

## Artifacts
- audit/FINAL_partition.json — clean / bug task lists + per-bug evidence
- audit/chunk_*_result.json — per-chunk audit verdicts (12 chunks of 45)
- audit/tw_verify_*.json — too_weak execution-verification (wrong-answer test runs)
- audit/audit_workflow.js, audit/verify_tooweak.js — reusable audit loops
