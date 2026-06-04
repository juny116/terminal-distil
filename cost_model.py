"""Teacher API cost model for the locked core experiment (discussion-004).

Only the TEACHER is an API model. Student rollout/recovery, the Docker env, the verifier
(test.sh), AND the no-hint-rederive gate (#14, student-self) all run locally (free). So API
cost = teacher calls only:
  - teacher SOLVE (best-of-N) : grounds C's hints + produces arm A     [full rollout]
  - B recovery               : teacher continues from failure prefix   [full rollout]
  - C hints (k rounds)       : grounded diagnosis hints                [single call]
  - ECE judge                : earliest-critical-error per failure     [single call]
  - hint-strip judge         : leak check per C recovery               [cheap call]
NOTE: no-hint-rederive is student-self (Qwen, local) — adds local GPU time, $0 API.

Measured (jobs/, gpt teacher): full rollout ~18k input + 1.7k output (~7 turns);
single call ~13k input (mostly the failure prefix) + ~150 output.

Gate 1 update (#13-#15): raw recovery success != strict-main clean. Of usable C failures,
only a fraction survive the leak + no-hint-rederive gates -> STRICT_CLEAN_YIELD. Teacher
CALLS still happen per usable failure (solve/hint regardless of outcome), so the gate doesn't
cut call count — it raises the cost PER CLEAN-C SAMPLE and sets how many tasks you must
process to hit a target. Both views are printed below.
Edit the params/prices below; run `python3 cost_model.py`.
"""

# ── scale params (edit) ─────────────────────────────────────────────────────────
T            = 300     # tasks in the experiment subset
N_SOLVE      = 3       # best-of-N teacher attempts per task (grounding + arm A)
FAIL_FRAC    = 0.50    # student fail rate
USABLE_FRAC  = 0.55    # of failures, fraction kept after funnel (genuine+solvable)
K_HINT_AVG   = 2.0     # avg grounded-hint rounds per C failure (k<=3)
STRICT_CLEAN_YIELD = 0.30  # of usable C failures, fraction surviving leak + rederive (#15).
                           #  Gate1 slice observed 0/2 strong (tiny n); 0.30 is an optimistic
                           #  planning guess — the real number is what Gate 2 measures.
TARGET_CLEAN = 150     # desired strict-main clean-C samples (for the per-target view)

# ── per-call token footprint (measured) ─────────────────────────────────────────
ROLLOUT_IN, ROLLOUT_OUT = 18_000, 1_700      # full teacher rollout (solve / B)
CALL_IN,    CALL_OUT    = 13_000, 150         # single call (hint / ECE judge)
JUDGE_IN,   JUDGE_OUT   = 5_000,  50          # cheap leak judge

# ── price ($/1M tokens) — teacher model options ─────────────────────────────────
PRICES = {
    "Sonnet-class ($3/$15)": (3.0, 15.0),
    "Opus-class ($15/$75)":  (15.0, 75.0),
}
CACHE_INPUT_DISCOUNT = 0.33                    # cached input ~1/3 (growing prefix reused)
THINKING_OUT_MULT = 6.0                        # reasoning ~6x output tokens (rollout/judge steps)


def usd(n_in, n_out, price, cached=False, thinking=False):
    pin, pout = price
    pin = pin * (CACHE_INPUT_DISCOUNT if cached else 1.0)
    out = n_out * (THINKING_OUT_MULT if thinking else 1.0)
    return (n_in * pin + out * pout) / 1e6


def main():
    F = int(T * FAIL_FRAC)
    Fu = int(F * USABLE_FRAC)
    n_solve = T * N_SOLVE
    n_B = Fu
    n_hint = int(Fu * K_HINT_AVG)
    n_ece = Fu
    n_strip = Fu
    clean = int(Fu * STRICT_CLEAN_YIELD)       # strict-main clean-C from this T

    print(f"scale: T={T} tasks, ~{F} fail, ~{Fu} usable failures(funnel), "
          f"~{clean} strict-clean C @ yield {STRICT_CLEAN_YIELD:.0%}")
    print(f"calls: solve={n_solve} (best-of-{N_SOLVE}), B={n_B}, C-hints={n_hint} (k~{K_HINT_AVG}), "
          f"ECE={n_ece}, strip={n_strip}  (rederive=student-self, $0)\n")

    scenarios = [
        ("cache / no-thinking",              True,  False),
        ("cache / thinking SOLVE+B",         True,  "solve"),
        ("cache / thinking everywhere",      True,  True),
    ]
    for pname, price in PRICES.items():
        print(f"=== teacher = {pname} ===")
        for label, cached, thinking in scenarios:
            th_solve = thinking in (True, "solve")
            th_call  = thinking is True
            c_solve = n_solve * usd(ROLLOUT_IN, ROLLOUT_OUT, price, cached, th_solve)
            c_B     = n_B     * usd(ROLLOUT_IN, ROLLOUT_OUT, price, cached, th_solve)
            c_hint  = n_hint  * usd(CALL_IN,    CALL_OUT,    price, cached, th_call)
            c_ece   = n_ece   * usd(CALL_IN,    CALL_OUT,    price, cached, th_call)
            c_strip = n_strip * usd(JUDGE_IN,   JUDGE_OUT,   price, cached, False)
            total = c_solve + c_B + c_hint + c_ece + c_strip
            per_clean = total / clean if clean else float("nan")
            tasks_for_target = T * TARGET_CLEAN / clean if clean else float("nan")
            cost_for_target = total * TARGET_CLEAN / clean if clean else float("nan")
            print(f"  [{label:28s}] TOTAL ${total:6.0f}  (solve ${c_solve:5.0f} B ${c_B:4.0f} "
                  f"hint ${c_hint:4.0f} ECE ${c_ece:4.0f} strip ${c_strip:3.0f})")
            print(f"       → ${per_clean:5.1f}/clean-C · {TARGET_CLEAN} clean needs "
                  f"~{tasks_for_target:.0f} tasks ≈ ${cost_for_target:6.0f}")
        print()

    print("참고:")
    print(" • A(=sft_all 2,302)는 이미 수집됨 → solve 비용 상당분 sunk(재실행 안 하면 solve 차감).")
    print(" • no-hint-rederive는 student-self(local Qwen) → API $0, GPU 시간만.")
    print(" • 핵심 변수=STRICT_CLEAN_YIELD: Gate1 slice는 0/2(strong). Gate2 20-30이 실측.")
    print("   yield가 낮으면 call 수는 그대로지만 clean당 단가/목표 비용이 비례해 커짐.")


if __name__ == "__main__":
    main()
