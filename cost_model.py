"""Teacher API cost model for the locked core experiment (discussion-004).

Only the TEACHER is an API model. Student rollout/recovery, the Docker env, and the
verifier (test.sh) all run locally (free). So API cost = teacher calls only:
  - teacher SOLVE (best-of-N) : grounds C's hints + produces arm A     [full rollout]
  - B recovery               : teacher continues from failure prefix   [full rollout]
  - C hints (k rounds)       : grounded diagnosis hints                [single call]
  - ECE judge                : earliest-critical-error per failure     [single call]
  - hint-strip judge         : leak check per C recovery               [cheap call]

Measured (jobs/, gpt teacher): full rollout ~18k input + 1.7k output (~7 turns);
single call ~13k input (mostly the failure prefix) + ~150 output.
Edit the params/prices below; run `python3 cost_model.py`.
"""

# ── scale params (edit) ─────────────────────────────────────────────────────────
T            = 300     # tasks in the experiment subset
N_SOLVE      = 3       # best-of-N teacher attempts per task (grounding + arm A)
FAIL_FRAC    = 0.50    # student fail rate
USABLE_FRAC  = 0.55    # of failures, fraction kept after funnel (genuine+solvable)
K_HINT_AVG   = 2.0     # avg grounded-hint rounds per C failure (k<=3)

# ── per-call token footprint (measured) ─────────────────────────────────────────
ROLLOUT_IN, ROLLOUT_OUT = 18_000, 1_700      # full teacher rollout (solve / B)
CALL_IN,    CALL_OUT    = 13_000, 150         # single call (hint / ECE judge)
JUDGE_IN,   JUDGE_OUT   = 5_000,  50          # cheap leak judge

# ── price ($/1M tokens) — edit to your teacher model ────────────────────────────
PRICE_IN, PRICE_OUT = 3.0, 15.0               # frontier non-thinking (Sonnet/GPT-mini class)
CACHE_INPUT_DISCOUNT = 0.33                    # cached input ~1/3 (growing prefix reused)
THINKING_OUT_MULT = 6.0                        # reasoning ~6x output tokens (rollout/judge steps)


def usd(n_in, n_out, cached=False, thinking=False):
    pin = PRICE_IN * (CACHE_INPUT_DISCOUNT if cached else 1.0)
    out = n_out * (THINKING_OUT_MULT if thinking else 1.0)
    return (n_in * pin + out * PRICE_OUT) / 1e6


def main():
    F = int(T * FAIL_FRAC)
    Fu = int(F * USABLE_FRAC)
    n_solve = T * N_SOLVE
    n_B = Fu
    n_hint = int(Fu * K_HINT_AVG)
    n_ece = Fu
    n_strip = Fu

    print(f"scale: T={T} tasks, ~{F} fail, ~{Fu} usable failures(funnel)")
    print(f"calls: solve={n_solve} (best-of-{N_SOLVE}), B={n_B}, C-hints={n_hint} (k~{K_HINT_AVG}), ECE-judge={n_ece}, strip-judge={n_strip}\n")

    for label, cached, thinking in [
        ("no-cache / no-thinking", False, False),
        ("cache / no-thinking",    True,  False),
        ("cache / thinking on SOLVE+B only", True, "solve"),
        ("cache / thinking everywhere", True, True),
    ]:
        th_solve = thinking in (True, "solve")
        th_call  = thinking is True
        c_solve = n_solve * usd(ROLLOUT_IN, ROLLOUT_OUT, cached, th_solve)
        c_B     = n_B     * usd(ROLLOUT_IN, ROLLOUT_OUT, cached, th_solve)
        c_hint  = n_hint  * usd(CALL_IN,    CALL_OUT,    cached, th_call)
        c_ece   = n_ece   * usd(CALL_IN,    CALL_OUT,    cached, th_call)
        c_strip = n_strip * usd(JUDGE_IN,   JUDGE_OUT,   cached, False)
        total = c_solve + c_B + c_hint + c_ece + c_strip
        print(f"[{label}]")
        print(f"   solve ${c_solve:6.1f} | B ${c_B:5.1f} | C-hints ${c_hint:5.1f} | ECE ${c_ece:5.1f} | strip ${c_strip:4.1f}  ==>  TOTAL ${total:6.1f}")
    print("\n참고: A(=sft_all 2,302)는 이미 수집됨 → solve 비용 상당분 sunk(재실행 안 하면 차감).")
    print("      단가는 실제 teacher 모델 가격으로 바꿔서 다시 돌리세요.")


if __name__ == "__main__":
    main()
