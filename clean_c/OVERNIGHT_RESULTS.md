# Overnight pipeline results (2026-06-05 → 06-06)

Autonomous run: complete the baseline-vs-C1 capability pipeline end-to-end + arm-B PoC.

## Headline: baseline vs C1 (held-out 100 tasks, thinking-ON)

| arm | pass-rate (common 94 graded) |
|---|---|
| baseline (base Qwen3.5-4B) | **63.8%** (60/94) |
| C1 (LoRA on 12 recovery examples) | **62.8%** (59/94) |
| delta | **-1 task / -1.1 pp (noise)** |

per-task: 9 gained, 10 lost — pure churn (single seed, temp 0.6). **No capability signal.**

### Interpretation (honest)
- **This is the expected null result.** 12 C1 training examples is far too few to move a 4B
  model's general terminal pass-rate. The ±1-task delta is within single-seed noise.
- **What it DOES establish:** (1) the full pipeline works end-to-end (data → LoRA SFT →
  merge/serve → eval); (2) the LoRA did NOT break the model (62.8% ≈ 63.8%, a broken adapter
  would tank it), so training+serving are sound; (3) the scale needed for a real signal is
  clear — hundreds of recovery examples, not ~12.
- General pass-rate may also be the wrong sensitivity: a **recovery-specific eval** (resume
  from held-out failures, measure self-correction) would be more sensitive to C1 than overall
  pass-rate. Future work.

## What the overnight run produced (all committed)
1. **Pipeline (all working):** `build_c1.py` (C1 data), `train_sft.py` (LoRA SFT, per-turn
   masking), `merge_adapter.py` / `serve_c1_lora.sh` (LoRA serving), eval orchestration.
2. **Arm B (Claude-as-teacher scripted recovery):** `scripted_agent.py` — amass + a_star
   teacher recoveries both pass (reward 1.0). B-vs-C1 matched data for those prefixes.
3. **L1/L2/L3 hint dose-response** (9 prefixes): none 0/9 → L1 22% → L2 67% → L3 50%.
   Non-monotone (L2 diagnosis > L3 action-class). `clean_c/SWEEP_RESULTS.md`.
4. **Benchmark-bug finding:** ~50% of audited near-misses are benchmark bugs (student correct,
   test wrong). `clean_c/BENCHMARK_BUGS.md`.
5. **Baseline eval:** 63.8% pass-rate on 100 fresh held-out tasks (also a benchmark-bug /
   prefix-pool source).

## Infra notes (for reproduction)
- Training env: `identity-bias` conda (torch 2.11 + peft/accelerate `--no-deps`).
- Model dir assembled at `/data/juny116/qwen35_4b_train` (config+tokenizer and weights were in
  two separate incomplete HF caches).
- **Qwen3.5-4B is multimodal**: `merge_adapter.py` saves a text-only config → vLLM's qwen3_5
  class errors on missing `vision_config`. **Workaround: LoRA-serve** the assembled base with
  `--language-model-only --enable-lora --lora-modules c1=runs/c1_all`.
- **Launch vLLM via tmux** — direct tool/nohup launch hits sandbox exit 144.

## Next steps (for the morning)
- The honest path to a real capability number needs **scale**: hundreds of recovery examples.
  Given ~50% of near-misses are benchmark bugs, the recoverable-prefix yield per harvested task
  is low → this is where the teacher API (automated hint generation + bug filtering) would pay
  off, OR a recovery-specific eval that's sensitive to the small C1 set.
- Consider: B vs C1 at scale; recovery-specific eval; multi-seed eval to beat noise.
