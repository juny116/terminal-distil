"""Injected error/recovery index for arm ① (discussion-003 P6).

Reads teacher trajectory.json files (which preserve step_log; verified 4233/7394
trajectories carry >=1 injected error step) and extracts, for every injected
error, the recovery the teacher took right after it:

    injected error at episode e (step_log.intent == "error")
        -> recovery = first bash command in the NEXT assistant message (episode e+1)
        -> recovery_action_key = action_class.action_key(recovery_command)

These records serve two locked purposes:
  - arm ① nearest-neighbor gap metric (P6): does a student failure's recovery
    action-class match the injected one in the same (family, stage[, type]) cell?
  - oracle-hint source (P4): the recovery-action-class of a KNOWN-GOOD recovery
    (reward == 1) for the same task — class only, never the command surface.

Reads raw trajectory.json directly (the 5/4 data/sft_all.jsonl predates step_log
preservation). Pairs each with its sibling result.json for task_name + reward.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from action_class import action_key

_DIFFICULTY = re.compile(r"_(hard|medium|easy)$")


def family_of(task_name: str) -> str:
    """Task family = task name with a trailing difficulty suffix removed."""
    return _DIFFICULTY.sub("", task_name) if task_name else task_name


def _reward_of(result: Dict[str, Any]) -> Optional[float]:
    return (result.get("verifier_result") or {}).get("rewards", {}).get("reward")


def _bash_commands(assistant_msg: Dict[str, Any]) -> List[str]:
    """All bash commands in an assistant message's native tool_calls, in order."""
    cmds: List[str] = []
    for tc in assistant_msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        if fn.get("name") != "bash":
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            continue
        cmd = (args.get("command") or "").strip()
        if cmd:
            cmds.append(cmd)
    return cmds


def _assistant_messages(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [m for m in conversation if m.get("role") == "assistant"]


@dataclass
class InjectedRecovery:
    task_name: str
    family: str
    reward: Optional[float]
    error_episode: int
    error_category: Optional[str]
    progress_stage: str            # early / mid / late, by recovery episode
    recovery_command: str          # kept for audit ONLY — never exposed as a hint
    canon_argv0: str
    intent_class: str
    intent_confident: bool
    source_trial_dir: str


def _stage(episode: int, n_episodes: int) -> str:
    if n_episodes <= 1:
        return "late"
    frac = episode / (n_episodes - 1)
    return "early" if frac < 0.34 else ("mid" if frac < 0.67 else "late")


def iter_injected_recoveries(
    trajectory: Dict[str, Any],
    task_name: str,
    reward: Optional[float],
    source_trial_dir: str,
) -> Iterator[InjectedRecovery]:
    step_log = trajectory.get("step_log") or []
    assistants = _assistant_messages(trajectory.get("conversation") or [])
    n_ep = len(assistants)
    fam = family_of(task_name)

    for s in step_log:
        if not isinstance(s, dict) or s.get("intent") != "error":
            continue
        e = s.get("episode")
        if not isinstance(e, int):
            continue
        rec_ep = e + 1
        # Recovery is the first bash command in the NEXT assistant message.
        if rec_ep >= n_ep:
            continue
        rec_cmds = _bash_commands(assistants[rec_ep])
        if not rec_cmds:
            continue
        rec = rec_cmds[0]
        k = action_key(rec)
        yield InjectedRecovery(
            task_name=task_name,
            family=fam,
            reward=reward,
            error_episode=e,
            error_category=s.get("error_category"),
            progress_stage=_stage(rec_ep, n_ep),
            recovery_command=rec,
            canon_argv0=k.canon_argv0,
            intent_class=k.intent_class,
            intent_confident=k.confident,
            source_trial_dir=source_trial_dir,
        )


def build_index(jobs_dirs: List[Path]) -> List[InjectedRecovery]:
    records: List[InjectedRecovery] = []
    n_trials = 0
    for jobs_dir in jobs_dirs:
        for traj_path in jobs_dir.rglob("trajectory.json"):
            trial_dir = traj_path.parent.parent  # .../<trial>/agent/trajectory.json
            result_path = trial_dir / "result.json"
            if not result_path.exists():
                continue
            try:
                trajectory = json.loads(traj_path.read_text())
                result = json.loads(result_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            n_trials += 1
            task_name = result.get("task_name")
            if not task_name:
                continue
            reward = _reward_of(result)
            records.extend(
                iter_injected_recoveries(trajectory, task_name, reward, str(trial_dir))
            )
    build_index.last_n_trials = n_trials  # type: ignore[attr-defined]
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_dirs", nargs="+", type=Path)
    ap.add_argument("--output", type=Path, default=Path("data/injected_index.jsonl"))
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    records = build_index(args.jobs_dirs)
    with args.output.open("w") as f:
        for r in records:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    n_trials = getattr(build_index, "last_n_trials", 0)
    from collections import Counter
    intents = Counter(r.intent_class for r in records)
    fams = Counter(r.family for r in records)
    succ = sum(1 for r in records if r.reward == 1.0)
    fallback = sum(1 for r in records if not r.intent_confident)
    print(f"trials scanned        : {n_trials}")
    print(f"injected recoveries    : {len(records)}")
    print(f"  from reward==1 (oracle-eligible): {succ}")
    print(f"  needs LLM intent fallback        : {fallback}  ({100*fallback//max(len(records),1)}%)")
    print(f"  distinct families                : {len(fams)}")
    print(f"  intent_class distribution        : {dict(intents.most_common())}")
    print(f"\nOutput: {args.output}  ({len(records)} rows)")


if __name__ == "__main__":
    main()
