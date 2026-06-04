# clean-C shape validation — yield report (Gate 1, thinking-ON)

Mini-PoC, Claude-as-teacher (no API). Goal (Codex #12): not pass-rate, but "do auditable
clean-C candidates actually materialize, and is the data shape honest?"

## Recovery success (thinking-ON vs the thinking-OFF baseline)

| task (ECE) | raw-retry | L1 diagnosis-hint | OFF baseline |
|---|---|---|---|
| spark_catalog_plugin (6) | 0/2 | **2/2** | L1 2/3 |
| ladder_capturing_go (27) | 0/2 | 0/2 | L1 0/2 |
| google_pubsub (1) | 0/2 | 0/2 | L4 0 |

thinking-ON does not hurt and recovers spark reliably (2/2). ladder/pubsub stay unrecovered
at L1 — they need multi-point hints (L2+) or are genuinely harder; not clean-C material yet.

## clean-C candidates from the 2 spark successes

Both passed the task (reward 1.0). The question is whether the *recovery data* is honest
after hint-stripping. Ran build_clean_c.py → hint_strip provenance:

| sample | provenance | strict_main | why |
|---|---|---|---|
| spark L1 s1 | **leak** | ✗ | first recovery turn opens *"The user is asking me to verify…"* — explicit hint reference in reasoning |
| spark L1 s2 | evidence_supported | ✓ (borderline) | no explicit hint reference; states "grader checks for TODO" then greps and **observes** the TODOs before fixing |

## Finding (the important one)

**Single-shot hint-stripping is not enough.** Of 2 successful L1 recoveries:
- 1/2 explicitly references the injected user/hint in its reasoning (caught → excluded).
- 1/2 doesn't say "hint" but its opening reasoning still **restates the hint's diagnosis**
  ("the grader checks for TODO comments"), attributing it to "the task description". The
  episode-grounding rule keeps it (student did observe the TODOs), but the framing is
  hint-derived.

So even the "clean" sample carries hint-derived framing in the first reasoning turn. This
directly quantifies the N2 hint-leak risk and motivates the planned verification passes:
no-hint-rederive (can the student reach the same diagnosis without the hint?),
counterfactual-hint, and provenance-tagging — *before* a sample enters strict-main.

## no-hint-rederive gate (student-self, no API) — Codex #14

The borderline s2 was put through `rederive_check.py`: does the student reach the SAME
diagnosis WITHOUT the hint? The no-hint runs = the raw-retry resumes (same prefix, no hint).

- core diagnosis identifier from the hint: **`TODO`** (the marker the grader checks for).
- both no-hint runs (N=2): `TODO` appears **only in tool observations** (the file it `cat`s
  contains TODO comments) and in a copied heredoc — **never in the student's own reasoning/
  content**. The student declares *"task is complete"* on passing the functional tests, never
  connecting the leftover TODOs to the grader failure. reward 0/2.
- **rederive label = FAIL** → s2 is **not** strict-main eligible; it is hint-derived
  (`C-rationalized`). The "grader checks for TODO" framing is the hint's genuine contribution,
  not something the student rederives alone.

So s2's exclusion is confirmed by **two independent signals**: hint_strip flags its first turn
as restating the hint diagnosis, AND no-hint-rederive shows the student can't self-derive it.

## Strict-main yield (this slice)

- successful L1 recoveries: 2
- explicit-leak excluded (hint_strip): 1
- rederive-FAIL excluded (hint-derived diagnosis): 1
- **strict-main clean, audit-passed: 0 / 2**

This is the headline: raw recovery success (2/2) and strict-main clean data (0/2) are very
different numbers. The hint contributes diagnostic information the student cannot rederive,
and naive hint-stripping leaves that hint-derived framing in the training data. **The
no-hint-rederive pass is therefore a mandatory strict-main gate**, not optional.

Conclusion for Gate 2 (20-30 fresh tasks): its primary metric is the FUNNEL RATE, not
pass-rate — `raw recovery success → −explicit leak → −rederive fail → strict clean`. Per
Codex #14, attach rederive to each success inline. If the first ~10 prefixes yield 0 strong
rederive passes, weaken the L1 hint (observation/invariant-centered, not stating the
diagnosis) before spending the rest.
