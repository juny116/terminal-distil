"""cv2b_build.py — build a C-v2b "evidence-replay self-rationalization" prefix
(discussion-004 #19, Codex).

Gate 2 showed naive hint-strip yields 0 strict-main: with the hint in context, the
student's recovery reasoning meta-references "the user's hint". C-v2b removes the hint
AND the hint-tainted narration, keeps only the EVIDENCE the recovery gathered (inspection
commands + their observations), and asks the student to reason+act fresh in a new context
with no hint and no prior-run reference.

Construction, from a hint-success recovery trajectory:
  conversation_prefix = original failure prefix (before the hint msg)
                        + recovery INSPECTION turns up to (not incl.) the first FIX turn,
                          with hint msg removed and each assistant turn's reasoning_content
                          + content (narration) STRIPPED — only tool_calls + tool results
                          (the evidence) remain.
  replay_commands     = every bash command in that prefix (rebuilds env to the
                        post-inspection, pre-fix state — the bug is still present).
  hint                = None  (no hint, no framing meta).

The student resumes seeing: its failed attempt + a bare (command -> observation) evidence
trail, and must diagnose + fix on its own. Its fresh reasoning is the C-v2b candidate
(separate arm `C-evidence-replay`, NOT strict-main — the evidence itself was gathered under
the hint, per Codex; strict-main stays prefix-only rederive-strong).

A "fix turn" = first recovery assistant turn whose command writes/mutates state
(>, >>, tee, sed -i, alembic merge/upgrade, mv, cp, install). If there is no inspection
turn before the fix, C-v2b is N/A for that case (degenerates to prefix-only).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from recovery_agent import COMMON_FRAMING, _bash_of
import build_clean_c

_MUTATE = re.compile(
    r"(>>?\s*/|>>?\s*\w|\btee\b|\bsed\s+-i\b|\balembic\s+(merge|upgrade)\b|\bmv\b|\bcp\b|"
    r"\bpip\s+install\b|\bapt\b|\bmkdir\b|\btouch\b|\bchmod\b|\bgcc\b|\bmake\b|"
    r"\bpython3?\s+<<|\bcat\s*>)",
    re.I,
)


def _is_fix(cmds: List[str]) -> bool:
    return any(_MUTATE.search(c) for c in cmds)


def _sanitize_assistant(m: Dict[str, Any]) -> Dict[str, Any]:
    """Keep tool_calls only; drop reasoning_content + content (hint-tainted narration)."""
    out = {"role": "assistant", "content": ""}
    if m.get("tool_calls"):
        out["tool_calls"] = m["tool_calls"]
    return out


def build_cv2b_prefix(traj_path: Path, task: str) -> Optional[Dict[str, Any]]:
    traj = json.loads(build_clean_c._find_trajectory(traj_path).read_text())
    conv = traj["conversation"]
    # locate hint message (COMMON_FRAMING user msg)
    frame = COMMON_FRAMING.strip()[:40]
    hint_idx = None
    for i, m in enumerate(conv):
        if m.get("role") == "user" and frame in (m.get("content") or ""):
            hint_idx = i
    if hint_idx is None:
        return None
    failure_prefix = conv[:hint_idx]
    recovery = conv[hint_idx + 1:]

    # walk recovery, collect inspection turns until the first fix turn
    evidence: List[Dict[str, Any]] = []
    n_inspection = 0
    i = 0
    while i < len(recovery):
        m = recovery[i]
        if m.get("role") == "assistant":
            cmds = _bash_of(m)
            if _is_fix(cmds):
                break  # stop before the fix
            if cmds:                       # an inspection turn (read-only)
                evidence.append(_sanitize_assistant(m))
                n_inspection += 1
                # include the following tool result(s)
                j = i + 1
                while j < len(recovery) and recovery[j].get("role") == "tool":
                    evidence.append(recovery[j])
                    j += 1
                i = j
                continue
        i += 1

    if n_inspection == 0:
        return None  # no evidence to replay -> C-v2b N/A (would be prefix-only)

    conversation_prefix = list(failure_prefix) + evidence
    replay_commands: List[str] = []
    for m in conversation_prefix:
        if m.get("role") == "assistant":
            replay_commands.extend(_bash_of(m))

    return {
        "task_name": task,
        "arm": "cv2b-evidence-replay",
        "hint": None,
        "n_inspection_turns": n_inspection,
        "replay_commands": replay_commands,
        "conversation_prefix": conversation_prefix,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("traj", help="hint-success recovery job dir or trajectory.json")
    ap.add_argument("--task", required=True)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    p = build_cv2b_prefix(Path(args.traj), args.task)
    if p is None:
        print("C-v2b N/A (no hint msg or no inspection evidence before fix)")
        raise SystemExit(2)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(p, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}  inspection_turns={p['n_inspection_turns']}  "
          f"replay_cmds={len(p['replay_commands'])}  prefix_msgs={len(p['conversation_prefix'])}")


if __name__ == "__main__":
    main()
