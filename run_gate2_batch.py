"""Run the Gate 2 recovery funnel for each case in gate2_cases.json.

Per case: base-framing N=2 (rederive baseline / reproducibility), L1-weak N=1,
L2-strong N=2. Calls run_recovery_arm.sh (thinking-ON). Prints reward per arm.
Outputs go to jobs/recov_g2_<task>_<arm>. No teacher API (Claude authored hints).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/juny116/Workspace/terminal-distil")
CASES = json.loads((ROOT / "gate2_cases.json").read_text())


def find_traj(glob: str) -> str:
    hits = list((ROOT / "jobs/gate2_harvest").rglob("trajectory.json"))
    for h in hits:
        if Path(glob.strip("*")).name in str(h) or glob.strip("*") in str(h):
            return str(h)
    raise FileNotFoundError(glob)


def run_arm(traj, ece, task, arm, label, hint):
    cmd = ["bash", "run_recovery_arm.sh", traj, str(ece), task, arm, label, hint or ""]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       env={**__import__("os").environ, "QWEN_ENABLE_THINKING": "1"})
    out = p.stdout + p.stderr
    rew = "ERR"
    for line in out.splitlines():
        if "reward=" in line:
            rew = line.split("reward=")[-1].strip()
    return rew


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for task, cfg in CASES.items():
        if only and only not in task:
            continue
        traj = find_traj(cfg["path_glob"])
        ece = cfg["ece"]
        print(f"\n## {task} (ECE={ece})", flush=True)
        arms = [
            ("base-framing", f"g2_{task[:18]}_bf1", ""),
            ("base-framing", f"g2_{task[:18]}_bf2", ""),
            ("teacher",      f"g2_{task[:18]}_L1",  cfg["l1"]),
            ("teacher",      f"g2_{task[:18]}_L2a", cfg["l2"]),
            ("teacher",      f"g2_{task[:18]}_L2b", cfg["l2"]),
        ]
        for arm, label, hint in arms:
            rew = run_arm(traj, ece, task, arm, label, hint)
            tag = {"": "bf "}.get(hint, "L2 ") if arm == "teacher" else "bf "
            tag = "L1 " if hint == cfg["l1"] else ("L2 " if hint == cfg["l2"] else "bf ")
            print(f"  {tag} {label[-3:]} reward={rew}", flush=True)
    print("\nGATE2 BATCH DONE", flush=True)


if __name__ == "__main__":
    main()
