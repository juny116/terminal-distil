# C1/C2 Capability Experiment — design (draft, 2026-06-05)

Locked framing: discussion-004 #22·#23. Goal = **make the student better** (capability),
with the mechanism/claim cleanly separable. This doc turns the C1/C2 split into a runnable
experiment, grounded in what infra actually exists.

## Arms (SFT data, all from the SAME student failure prefixes where possible)

| arm | failure source | recovery author | recovery in training INPUT? | recovery LABEL | role |
|---|---|---|---|---|---|
| **baseline** | — | — | — | — (no recovery SFT; or base model) | floor |
| **A** | injected (teacher) | teacher | n/a | teacher reason+action | TermiGen-style |
| **B** | on-policy student | **teacher** | hint/none | teacher reason+action | DAgger/OEC |
| **C1** | on-policy student | student (hint-elicited) | **hint STRIPPED** | student reason+action (leak OK) | capability |
| **C1-action-only** | on-policy student | student (hint-elicited) | hint stripped | student **action only** (no reasoning) | capability, N2↓ |
| **C2** | on-policy student | student | hint stripped | student reason+action, **rederive-strong only** | mechanism |

Invariant across all arms: **the hint is never in the training INPUT** (the deadly N2 form).
B/C share the same on-policy failure prefixes; only the recovery author differs. A uses
injected failures.

## Claims (what each comparison buys)
- **A → B**: on-policy failure states matter (vs injected).
- **B → C1**: even when expert *information* is needed, letting the *student instantiate*
  the recovery (its own action surface) is more imitable → ≥ teacher-written recovery on
  held-out pass-rate. ← **the capability headline**.
- **C1 → C2** (+ rederive funnel): the stronger "pure self-recovery / internalization"
  claim holds only on rederive-strong samples.

## Eval
- Held-out TerminalBench tasks (disjoint from training task families). Primary metric =
  **pass-rate (reward=1)**, thinking-ON, hint-free (deployment = no hint).
- Secondary: hint-free recovery rate on a held-out failure set (does the model self-recover
  from its own failures?), to directly test the "hint-dependence" worry.
- All arms evaluated with the SAME (global self-check) system prompt if we adopt C-v2c, to
  keep the policy comparison fair.

## What exists vs what's missing (infra reality)
- ✅ `build_dataset.py` — merges trajectory+result → SFT jsonl (per-task dedupe). Arm A
  already built: `data/sft_all.jsonl` (~2,302 traj).
- ✅ recovery trajectories for ~5–6 prefixes (Gate1 spark + Gate2 amass/alembic/agda/
  alloy/airflow). Enough to PROTOTYPE C1/C2 data construction, NOT to train.
- ❌ **No trainer script in repo** (no SFTTrainer/peft/accelerate). Need to build or locate
  the fine-tuning loop (LoRA/full-SFT on Qwen3.5-4B). **Blocker for any capability number.**
- ⚠️ **Scale**: pass-rate deltas need hundreds of recovery examples per arm, i.e. hundreds
  of on-policy failures × hint-elicited recovery. Current = ~6. → needs the harvest (a) +
  many authored hints.
- 🚧 **B arm needs teacher-authored recovery** = real teacher API (the stop line), OR
  Claude-as-teacher for a PoC.

## Staged plan (cheapest → most committed)
1. **C1 data builder (now, free):** `build_c1.py` — from a hint-success trajectory, strip
   the hint message from input, keep the student recovery turns (reason+action) as label.
   Emit SFT jsonl rows. Also a `--action-only` mode. PoC on the ~6 existing recoveries →
   eyeball that the rows are coherent (no hint in input; deployment-shaped).
2. **Trainer (now/next, free but real work):** stand up a minimal Qwen3.5-4B SFT loop
   (LoRA) that consumes our jsonl. Sanity: overfit a tiny set, confirm forward/backward.
3. **Scale prefixes (a):** finish the 50-task harvest + more → grow the on-policy failure
   pool and the C1 recovery set (author hints in bulk; inspection-direction style).
4. **baseline vs C1 (free, first real signal):** the cheapest capability test that needs
   NO teacher API — does adding C1 recovery data raise held-out pass-rate + hint-free
   recovery vs baseline? Answers juny116's "결국 다 배우나" directly.
5. **B vs C1 (needs teacher):** add the B arm (teacher recovery on same prefixes). This is
   where the paid teacher API (or Claude-as-teacher PoC) enters — juny116 approval gate.

## Open decisions (for juny116 / Codex)
- (D1) Trainer: build a minimal LoRA SFT here, or reuse an existing pipeline from a sibling
  project (identity-bias / adaptive_thinking have training code)?
- (D2) First capability cut = **baseline vs C1** (no teacher, runnable after trainer+scale)
  before spending on B? (recommended — answers the core question cheapest.)
- (D3) Global self-check system prompt (C-v2c): adopt across all arms now, or keep current
  system prompt and add self-check only as an ablation?
- (D4) Scale target for a first signal: how many recovery examples is "enough" (e.g. 150–300
  C1 rows) — drives how much harvest+hint authoring is needed.
