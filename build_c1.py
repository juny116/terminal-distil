"""build_c1.py — C1 capability-arm SFT data from hint-success recoveries (discussion-004 #23).

C1 = on-policy student failure + hint-elicited STUDENT recovery, with the hint removed from
the training INPUT (the only fatal N2 form). Leaky reasoning in the recovery LABEL is allowed
(capability arm; cosmetic per #22). `--action-only` drops reasoning from the label entirely
(sidesteps the leak, tests "state -> action" directly).

Emits ONE jsonl row per recovery trajectory:
  {
    task, arm, hint_level,
    messages: [system, user(task), <failed attempt: assistant/tool ...>,
               <recovery: assistant/tool ...>],          # NO hint message anywhere
    label_turn_indices: [idx of recovery assistant turns]  # compute loss only on these
    rederive_label, hint_strip_label                      # carried for C2 cross-tagging
  }

Input turns are serialized WITHOUT reasoning_content (per-turn scratchpad, #9): prior
reasoning is never fed back. Loss is on the recovery assistant turns (their reasoning_content
+ content + tool_calls), so the model learns state -> recovery. For --action-only the label
turns keep tool_calls + content but drop reasoning_content.

Usage:
  python build_c1.py jobs/recov_amass_L2_1_teacher --task amass... --level L2 \
      [--action-only] [--rederive clean_c/amass_s2_rederive.json] -o data/c1/amass.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from recovery_agent import COMMON_FRAMING
import build_clean_c


def _strip_input_turn(m: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize a turn as INPUT: drop reasoning_content (not fed back into context)."""
    out: Dict[str, Any] = {"role": m["role"]}
    if m.get("content") is not None:
        out["content"] = m["content"]
    if m.get("tool_calls"):
        out["tool_calls"] = [
            {"type": "function",
             "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
            for tc in m["tool_calls"]
        ]
    if m.get("tool_call_id"):
        out["tool_call_id"] = m["tool_call_id"]
    return out


def _label_turn(m: Dict[str, Any], action_only: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {"role": "assistant"}
    if not action_only and m.get("reasoning_content"):
        out["reasoning_content"] = m["reasoning_content"]
    out["content"] = m.get("content") or ""
    if m.get("tool_calls"):
        out["tool_calls"] = [
            {"type": "function",
             "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
            for tc in m["tool_calls"]
        ]
    return out


def build_c1_row(traj_path: Path, task: str, level: str, action_only: bool,
                 rederive_path: Optional[Path]) -> Dict[str, Any]:
    traj = json.loads(build_clean_c._find_trajectory(traj_path).read_text())
    conv = traj["conversation"]
    frame = COMMON_FRAMING.strip()[:40]
    hint_idx = None
    for i, m in enumerate(conv):
        if m.get("role") == "user" and frame in (m.get("content") or ""):
            hint_idx = i
    if hint_idx is None:
        raise ValueError("no hint message found")

    failure_prefix = conv[:hint_idx]          # the original failed attempt (no hint)
    recovery = conv[hint_idx + 1:]            # student recovery turns

    messages: List[Dict[str, Any]] = []
    label_idx: List[int] = []
    # failure prefix: pure input (no reasoning, no loss)
    for m in failure_prefix:
        messages.append(_strip_input_turn(m))
    # recovery: assistant turns are labels (loss), tool results are input
    for m in recovery:
        if m.get("role") == "assistant":
            label_idx.append(len(messages))
            messages.append(_label_turn(m, action_only))
        else:
            messages.append(_strip_input_turn(m))

    # hygiene: assert no hint text survives anywhere
    flat = json.dumps(messages, ensure_ascii=False)
    assert frame not in flat, "hint framing leaked into C1 messages"

    rederive_label = None
    if rederive_path and rederive_path.exists():
        rederive_label = json.loads(rederive_path.read_text()).get("rederive_label")

    return {
        "task": task,
        "arm": "C1-action-only" if action_only else "C1",
        "hint_level": level,
        "n_label_turns": len(label_idx),
        "label_turn_indices": label_idx,
        "rederive_label": rederive_label,       # for C2 cross-tagging (strong => also C2)
        "messages": messages,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("traj")
    ap.add_argument("--task", required=True)
    ap.add_argument("--level", default="L2")
    ap.add_argument("--action-only", action="store_true")
    ap.add_argument("--rederive", default=None)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    row = build_c1_row(Path(args.traj), args.task, args.level, args.action_only,
                       Path(args.rederive) if args.rederive else None)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"appended {args.arm if False else row['arm']} row -> {out}  "
          f"label_turns={row['n_label_turns']}  msgs={len(row['messages'])}  "
          f"rederive={row['rederive_label']}")


if __name__ == "__main__":
    main()
