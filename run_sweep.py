"""run_sweep.py — L1/L2/L3 hint content sweep over recoverable near-miss prefixes.

For each case in sweep_cases.json: run teacher recovery at L1/L2/L3 (N=1 each) + base-framing
(N=1, rederive/reproducibility baseline), thinking-ON. Records reward per (prefix, level).
Output dirs: jobs/recov_sw_<task[:16]>_<level>. No teacher API (Claude-authored hints).
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path("/home/juny116/Workspace/terminal-distil")
CASES = json.loads((ROOT / "sweep_cases.json").read_text())


def find_traj(harvest, glob):
    for h in (ROOT / "jobs" / harvest).rglob("trajectory.json"):
        if glob.strip("*") in str(h):
            return str(h)
    raise FileNotFoundError(f"{harvest}:{glob}")


def run_arm(traj, ece, task, arm, label, hint):
    env = {**os.environ, "QWEN_ENABLE_THINKING": "1"}
    p = subprocess.run(["bash", "run_recovery_arm.sh", traj, str(ece), task, arm, label, hint or ""],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    for line in (p.stdout + p.stderr).splitlines():
        if "reward=" in line:
            return line.split("reward=")[-1].strip()
    return "ERR"


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for task, cfg in CASES.items():
        if only and only not in task:
            continue
        traj = find_traj(cfg["harvest"], cfg["glob"])
        ece, short = cfg["ece"], task[:16]
        print(f"\n## {task} (ECE={ece}, {cfg['harvest']})", flush=True)
        for arm, label, hint in [
            ("base-framing", f"sw_{short}_bf", ""),
            ("teacher",      f"sw_{short}_L1", cfg["l1"]),
            ("teacher",      f"sw_{short}_L2", cfg["l2"]),
            ("teacher",      f"sw_{short}_L3", cfg["l3"]),
        ]:
            tag = label.split("_")[-1]
            print(f"  {tag:3s} reward={run_arm(traj, ece, task, arm, label, hint)}", flush=True)
    print("\nSWEEP DONE", flush=True)


if __name__ == "__main__":
    main()
