# L1/L2/L3 hint content sweep — results (2026-06-05)

9 recoverable near-miss prefixes (5 harvest1 + 4 harvest2), thinking-ON, proper hints
(no exact commands). Hints authored by Claude-as-teacher. base-framing = framing only, no hint.

## Recovery dose-response (the headline)

```
prefix                              none  L1   L2   L3
amass                                .    .    1    .
alembic                              .    .    .    .     (needs exact cmd / L4)
agda_cubical                         .    .    1    .
alloy_analyzer                       .    1    1    1     (easiest — recovers at all levels)
airflow_xcom                         .    .    1    1
ansible_inventory                    .    .    1    .
ansible_template                     .    .    .    ?     (4-defect, hint underspecified)
a_star_pathfinding                   .    .    1    1
ar_archive                           .    1    .    1
------------------------------------------------------
recovery rate                       0/9  2/9  6/9  4/8
                                     0%   22%  67%  50%
```

**Findings:**
1. **base-framing 0/9**: with no hint (just "verify before completing"), zero recovery. The
   hint content is doing the work, not the retry framing.
2. **Monotone-ish but L2 > L3**: none < L1 < L3 < L2. Diagnosis (L2, "what is wrong") recovers
   MORE than action-class (L3, "what class of fix") — telling the student the fault lets it
   fix in its own way; an action-class without the why is often applied wrong or underspecified.
3. **L2 diagnosis is the recovery sweet spot (67%).** L1 inspection is weak (22%) but cleaner
   provenance; L3 action-class is middling and closest to DAgger.
4. alembic recovers at NO level here — its earlier 2/2 used an exact-command hint (`alembic
   merge -m ...` = L4); the proper diagnosis-only L2 is insufficient. Honest: that task needs L4.

## Provenance / C2 funnel over the 12 successful recoveries

```
N_hint_success     12
N_non_leak          5   (evidence_supported x4 + low_overlap x1)
N_rederive_strong   0   STRICT-MAIN (C2) eligible
N_rederive_weak     1   ansible_inventory L2
N_rationalized      4   recovered but rederive fail
strict-main clean yield = 0/12
```

per-recovery: amass L2 leak · agda L2 leak · alloy L1/L2/L3 **all leak** · airflow L2/L3
evidence_supported(rederive fail) · ansible_inventory L2 evidence_supported(weak) · a_star
L2/L3 leak · ar_archive **L1 low_overlap**(cleanest) / L3 evidence_supported.

**Findings:**
5. **C2 strict yield = 0/12, even at L1.** rederive-strong never occurs — the student does not
   self-derive the diagnosis without the hint, at any hint strength. The C1/C2 split holds:
   C1 (capability) has 12 usable recoveries; C2 (mechanism) is ~0.
6. **L1 is sometimes cleaner provenance** (ar_archive L1 = low_overlap) but recovers least.
   The clean-vs-recovers tradeoff is real but C2 yield stays ~0 regardless.

## C1 dataset produced
- `data/c1/sweep.jsonl`: 12 C1 rows (input-stripped, recovery reason+action as label), tagged
  with hint_level + rederive_label for later C2 cross-tagging. Ready for B-vs-C1 training.

## Bottom line
- For **capability (C1)**: L2 diagnosis × user-msg is the best data generator (67% recovery).
  We now have ~12 C1 examples across L1/L2/L3.
- For **mechanism (C2)**: strict self-recovery remains ~0 across all hint strengths — the
  paper's C2 arm is genuinely tiny/high-precision, as expected.
- Recovery is real and hint-strength-dependent; the dose-response curve (0→22→67→50%) is a
  clean result for the paper's hint-taxonomy section.
