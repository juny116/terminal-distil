"""
Analyze existing jobs and output task names to run next.

Modes:
  unattempted  : tasks never attempted (for Phase A: cover remaining tasks)
  failed       : tasks where best reward < 1.0 (for Phase B: retry failures)
  all-status   : print per-task status summary

Usage:
  python select_tasks.py jobs/ --mode unattempted --tasks-dir <env_dir>
  python select_tasks.py jobs/ --mode failed
  python select_tasks.py jobs/ --mode all-status
"""
import argparse
import json
import os
from pathlib import Path
from collections import defaultdict


def collect_results(jobs_root: Path) -> dict:
    """Returns: {task_name: {'attempts': int, 'best_reward': float, 'task_dir_name': str}}"""
    results = defaultdict(lambda: {"attempts": 0, "best_reward": -1.0})
    for result_path in jobs_root.rglob("result.json"):
        # skip top-level job result.json (no task_name there)
        try:
            data = json.loads(result_path.read_text())
        except Exception:
            continue
        task_name = data.get("task_name")
        if not task_name:
            continue
        reward_obj = data.get("verifier_result")
        reward = (reward_obj or {}).get("rewards", {}).get("reward", -1.0)
        if reward is None:
            reward = -1.0
        results[task_name]["attempts"] += 1
        if reward > results[task_name]["best_reward"]:
            results[task_name]["best_reward"] = reward
    return dict(results)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_root", type=Path)
    ap.add_argument("--mode", choices=["unattempted", "failed", "all-status"], required=True)
    ap.add_argument(
        "--tasks-dir",
        type=Path,
        default=Path(os.environ.get("TASKS_DIR", "")),
        help="Path to environments_harbor (or set TASKS_DIR env var). Required for 'unattempted' mode.",
    )
    ap.add_argument("--output", type=Path, default=None, help="Optional file to write task names (one per line)")
    args = ap.parse_args()

    results = collect_results(args.jobs_root)

    if args.mode == "all-status":
        total = len(results)
        success = sum(1 for v in results.values() if v["best_reward"] >= 1.0)
        failed = sum(1 for v in results.values() if 0 <= v["best_reward"] < 1.0)
        attempts = sum(v["attempts"] for v in results.values())
        print(f"Tasks attempted : {total}")
        print(f"  succeeded     : {success}")
        print(f"  failed        : {failed}")
        print(f"Total attempts  : {attempts}")
        return

    if args.mode == "unattempted":
        all_tasks = {p.name for p in args.tasks_dir.iterdir() if p.is_dir()}
        attempted = set(results.keys())
        selected = sorted(all_tasks - attempted)
    else:  # failed
        selected = sorted(name for name, v in results.items() if 0 <= v["best_reward"] < 1.0)

    if args.output:
        args.output.write_text("\n".join(selected) + "\n")
        print(f"Wrote {len(selected)} task names to {args.output}", flush=True)
    else:
        for name in selected:
            print(name)


if __name__ == "__main__":
    main()
