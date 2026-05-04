"""
After pilot run, analyze token usage and estimate full-run cost.
Usage: python analyze_cost.py jobs/pilot_<name>/ [--input-price 0.4] [--output-price 1.6]

Default prices are GPT-4.1-mini ($/1M tokens) — update to match your model.
Check current pricing: https://platform.openai.com/docs/pricing
"""
import json
import sys
from pathlib import Path

# ---- pricing ($/1M tokens) ----
# Update these to match your actual model
DEFAULT_INPUT_PRICE = 0.40   # gpt-4.1-mini input
DEFAULT_OUTPUT_PRICE = 1.60  # gpt-4.1-mini output
TOTAL_TASKS = 3567
# --------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("jobs_dir", type=Path)
    parser.add_argument("--input-price", type=float, default=DEFAULT_INPUT_PRICE)
    parser.add_argument("--output-price", type=float, default=DEFAULT_OUTPUT_PRICE)
    args = parser.parse_args()

    trajectories = list(args.jobs_dir.rglob("trajectory.json"))
    if not trajectories:
        print("No trajectory.json files found. Did the pilot run complete?")
        sys.exit(1)

    results = []
    for traj_path in trajectories:
        data = json.loads(traj_path.read_text())
        task_name = traj_path.parent.parent.name  # jobs_dir/trial_*/logs/trajectory.json
        results.append({
            "task": task_name,
            "input_tokens": data["total_input_tokens"],
            "output_tokens": data["total_output_tokens"],
            "total_tokens": data["total_tokens"],
            "turns": data["n_turns"],
        })

    n = len(results)
    avg_input = sum(r["input_tokens"] for r in results) / n
    avg_output = sum(r["output_tokens"] for r in results) / n
    avg_total = sum(r["total_tokens"] for r in results) / n
    avg_turns = sum(r["turns"] for r in results) / n

    cost_per_task = (avg_input * args.input_price + avg_output * args.output_price) / 1_000_000
    total_cost = cost_per_task * TOTAL_TASKS
    pilot_cost = cost_per_task * n

    print(f"\n{'='*50}")
    print(f"  Pilot results: {n} tasks")
    print(f"{'='*50}")
    print(f"  Avg turns        : {avg_turns:.1f}")
    print(f"  Avg input tokens : {avg_input:,.0f}")
    print(f"  Avg output tokens: {avg_output:,.0f}")
    print(f"  Avg total tokens : {avg_total:,.0f}")
    print(f"\n  Pricing (per 1M): input=${args.input_price:.2f}  output=${args.output_price:.2f}")
    print(f"  Cost per task    : ${cost_per_task:.4f}")
    print(f"  Pilot total cost : ${pilot_cost:.2f}  ({n} tasks)")
    print(f"\n  FULL RUN estimate: ${total_cost:.2f}  ({TOTAL_TASKS} tasks)")
    print(f"{'='*50}\n")

    # also show per-task breakdown (sorted by cost)
    for r in sorted(results, key=lambda x: x["total_tokens"], reverse=True)[:5]:
        tc = (r["input_tokens"] * args.input_price + r["output_tokens"] * args.output_price) / 1_000_000
        print(f"  [{r['task'][:50]:50s}]  turns={r['turns']:3d}  tokens={r['total_tokens']:7,d}  cost=${tc:.4f}")

if __name__ == "__main__":
    main()
