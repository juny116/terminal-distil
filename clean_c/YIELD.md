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

## Strict-main yield (this slice)

- successful L1 recoveries: 2
- explicit-leak excluded: 1
- evidence_supported but borderline (needs no-hint-rederive audit): 1
- **unambiguously clean, audit-free: 0**

Conclusion for the funnel denominator: budget for ~50% loss to explicit leaks, and treat the
remainder as *candidates requiring the rederive pass*, not finished strict-main data. Fresh
harvest (Gate 2, 20-30 tasks) should size the denominator with this two-stage filter in mind.
