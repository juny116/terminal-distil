# Gate 2 strict-main funnel — fresh harvest (thinking-ON, no teacher API)

Fresh unbiased harvest of 30 medium tasks (never previously attempted). Claude authored
grounded hints; recovery + rederive ran on the local student (Qwen3.5-4B). The question
(Codex #16): not pass-rate, but **how much of raw hint-recovery success becomes
strict-main-clean training data.**

## Harvest → near-miss → recoverable

```
30 fresh tasks  → 13 pass / 14 fail (1 errored)
14 fail → mine_failures funnel:
   3 substrate(parser)  ·  11 genuine  ·  8 near-miss (>=0.6)
8 near-miss →
   6 recoverable process near-miss
   2 BENCHMARK BUGS (student was correct, the test is wrong):
       - acl2_induction_scheme_selection: test reads output/.../files/functions.lisp,
         a path the harness never provisions → FileNotFoundError. 7/7 content checks pass.
       - alloy_scope_bitwidth_configuration: test hardcodes expected_max=4095 but the
         deployed constraints.txt maxes at 16383; the only "passing" answer contradicts
         the data file.
```

The 2 benchmark bugs (25% of near-misses) are independent confirmation of the
contamination thesis — the static funnel missed them (one crashes as FileNotFoundError,
one is a value-assertion mismatch), so **human/teacher audit catches contamination the
funnel can't.**

## The recovery funnel (6 recoverable prefixes)

| task | hint recovery | hint_strip | rederive | strict-main |
|---|---|---|---|---|
| amass_subdomain_enumeration | L2 2/2 | evidence_supported | **weak** | ✗ |
| alembic_migration_conflict | L2 2/2 | **leak** (`merge -m` exact cmd) | — | ✗ |
| agda_cubical_homotopy_types | L2 2/2 | **leak** ("the user's hint about proof_02") | — | ✗ |
| alloy_analyzer_scope_insufficient | **L1 1/1** + L2 2/2 | **leak** ("the user is asking me to cross-check") | — | ✗ |
| airflow_xcom_large_data | **L1 1/1** + L2 1/2 | evidence_supported | **fail** | ✗ |
| airtable_api_rate_limit_handling | none (L1+L2 0) | — | — | ✗ |

```
N_prefix            6   genuine process near-miss
N_hint_success      5   k<=3 diagnosis-hint recovery reward 1   (airtable failed all)
N_non_leak          2   survived hint_strip (amass, airflow)
N_rederive_strong   0   STRICT-MAIN eligible
N_rederive_weak     1   amass (C-rederive-weak / appendix)
N_rationalized      1   airflow (raw success, rederive fail)
strict-main clean yield = 0 / 6
```

## Findings

1. **Strict-main clean yield = 0/6 on fresh data** — consistent with the spark slice
   (0/2). Across 8 successful hint recoveries total (spark 2 + Gate 2 amass/alembic/agda/
   alloy/airflow 6, minus airtable), ZERO produced audit-clean strict-main data via
   single-shot hint-stripping.

2. **Two failure modes, both intrinsic:**
   - **Leak (3/5):** the recovery reasoning explicitly references the hint/user — e.g. agda:
     *"the user's comment is a hint, not necessarily the final answer"*; alloy: *"the user
     is asking me to cross-check"*. The student meta-reasons about the hint, which can't be
     stripped without rewriting (forbidden).
   - **Rederive fail/weak (2/5):** the recovery doesn't say "hint" but states a diagnosis
     the student cannot self-derive without it (amass weak, airflow fail).

3. **Not an artifact of hint strength.** alloy_analyzer leaked *even at L1-weak* (an
   observation-centered hint that didn't name the bug). So the contamination is inherent to
   the hint-elicited setup, not just over-strong hints. (alembic's leak IS partly my fault —
   the L2 hint named the exact command `alembic merge -m`; future hints should give the
   diagnosis, not the command. But weak hints still leaked via "the user…" references.)

4. **airtable = capability boundary, not data-yield:** the fix (clear the 19.0s timing
   margin) never landed at any hint level — a genuine 4B limit, correctly separated from the
   data-contamination story.

## Implication for the thesis

This is strong, fresh-data evidence for ②½'s central claim: **raw hint-based recovery
success is NOT usable training data.** It is contaminated by hint-references and
hint-derived diagnoses that survive naive stripping. The no-hint-rederive gate + leak filter
are mandatory, and the realistic strict-main yield is very low — which means either (a) a
much larger harvest, or (b) a recovery protocol that produces self-contained reasoning
(e.g. STaR-style re-derivation without the hint in context, or a rationalization pass that
is itself student-authored and rederive-gated). This is the next design question, not a
spend-the-API question.

## Caveats (need human audit, per Codex #8/#16)
- amass rederive=weak is inflated by the task-subject identifier `megacorp.com` (mentioned
  every turn); the discriminating identifier is the wildcard `example.megacorp.com`. Conservative.
- leak detection is keyword-based; the triggers here were manually verified as genuine
  ("the user's hint", "the user is asking"), not framing echoes.
