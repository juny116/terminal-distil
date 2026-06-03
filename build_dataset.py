"""
Merge trajectory.json + result.json across ALL jobs, dedupe by task name,
keep only one successful trajectory per task. Outputs SFT dataset (.jsonl).

Selection rule per task (when multiple successful attempts exist):
  prefer trajectory with > 0 error_steps (richer recovery data)
  break ties by lower n_turns (more efficient solution)

Usage:
    python build_dataset.py jobs/ --output data/sft_dataset.jsonl
    python build_dataset.py jobs/ --output data/sft_dataset.jsonl --min-reward 1.0
"""
import argparse
import json
from pathlib import Path
from collections import defaultdict


def load_trial(trial_dir: Path):
    result_path = trial_dir / "result.json"
    trajectory_path = trial_dir / "agent" / "trajectory.json"
    if not result_path.exists() or not trajectory_path.exists():
        return None
    try:
        result = json.loads(result_path.read_text())
        trajectory = json.loads(trajectory_path.read_text())
    except Exception:
        return None
    reward = (result.get("verifier_result") or {}).get("rewards", {}).get("reward", None)
    if reward is None:
        return None
    return {
        "task_name": result.get("task_name"),
        "reward": reward,
        "model": trajectory.get("model"),
        "epsilon": trajectory.get("epsilon"),
        "n_turns": trajectory.get("n_turns"),
        "n_error_steps": trajectory.get("n_error_steps"),
        "total_input_tokens": trajectory.get("total_input_tokens"),
        "total_output_tokens": trajectory.get("total_output_tokens"),
        # Preserve step_log + source path (discussion-002 D3): the recovery slice
        # for arm ① (which assistant tool_call was the injected error, which next
        # command was the recovery) can only be cut reliably from per-step metadata.
        # Dropping it forces a fragile re-parse of the raw conversation later.
        "step_log": trajectory.get("step_log", []),
        "source_trial_dir": str(trial_dir),
        "messages": trajectory.get("conversation", []),
    }


def selection_key(trial):
    """Higher key = better. Prefer error_steps > 0, then fewer turns."""
    has_errors = 1 if trial["n_error_steps"] > 0 else 0
    return (has_errors, -trial["n_turns"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_dirs", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, default=Path("data/sft_dataset.jsonl"))
    ap.add_argument("--min-reward", type=float, default=1.0)
    ap.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Only include trajectories from these models (space-separated). Default: all.",
    )
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    by_task: dict[str, list] = defaultdict(list)
    total_seen, total_loaded = 0, 0
    per_model_seen: dict[str, int] = defaultdict(int)

    for jobs_dir in args.jobs_dirs:
        for result_path in jobs_dir.rglob("result.json"):
            total_seen += 1
            trial = load_trial(result_path.parent)
            if trial is None:
                continue
            total_loaded += 1
            per_model_seen[trial.get("model") or "?"] += 1
            if args.models and trial.get("model") not in args.models:
                continue
            if trial["reward"] >= args.min_reward and trial["task_name"]:
                by_task[trial["task_name"]].append(trial)

    # Dedupe — pick best trajectory per task
    selected = []
    n_with_errors = 0
    per_model_selected: dict[str, int] = defaultdict(int)
    for task_name, trials in by_task.items():
        best = max(trials, key=selection_key)
        if best["n_error_steps"] > 0:
            n_with_errors += 1
        per_model_selected[best.get("model") or "?"] += 1
        selected.append(best)

    with args.output.open("w") as f:
        for trial in selected:
            f.write(json.dumps(trial, ensure_ascii=False) + "\n")

    print(f"\nTrials scanned        : {total_seen}")
    print(f"Trials loaded         : {total_loaded}")
    print(f"  per model:")
    for m, c in sorted(per_model_seen.items()):
        print(f"    {m:30s}: {c}")
    if args.models:
        print(f"  filtered to models  : {args.models}")
    print(f"\nUnique successful tasks: {len(selected)}")
    print(f"  with error steps    : {n_with_errors}  ({100*n_with_errors//max(len(selected),1)}%)")
    print(f"  clean (no errors)   : {len(selected) - n_with_errors}")
    print(f"  selected per model:")
    for m, c in sorted(per_model_selected.items()):
        print(f"    {m:30s}: {c}")
    print(f"\nOutput: {args.output}  ({args.output.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
