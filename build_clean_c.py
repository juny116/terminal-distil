"""build_clean_c.py — turn a SUCCESSFUL arm-C recovery trajectory into an auditable
clean-C training sample (discussion-004 #12, Codex's metadata spec).

Arm C = on-policy student failure + student's OWN hint-elicited self-recovery, with the
hint STRIPPED from the training data. This script does NOT generate or rewrite anything
(Codex #8: rewriting = teacher becomes author = new contamination). It only:

  1. splits the recovery trajectory into  prefix | hint | recovery .
  2. atomizes the injected hint (framing is generic; the arm-specific suffix is the
     diagnosis atom; optional sidecar <traj>.atoms.json supplies exact_action/gold_literal).
  3. runs hint_strip.tag_recovery -> per-turn provenance + leak detection.
  4. emits the SFT serialization PREVIEW the model would actually train on:
       input  = prefix (no reasoning, no hint) + recovery observations up to turn t
       label  = turn t's reasoning_content (if any) + action
     and asserts the input contains NO hint text and NO prior reasoning (per-turn scratchpad).
  5. writes one JSON record with every field Codex #12 asked a human to audit:
       source task / prefix id / failure type / recovery mode /
       reasoning_present_on_recovery_turn / hint atoms / provenance label /
       strip result (kept|dropped + reason) / sft preview.

A human reads the record and judges "is training on this honest?". strict_main=True only
when no leak AND provenance in {evidence_supported, low_overlap}. hint_derived/leak records
are still emitted (with strict_main=False) and counted as coverage/yield loss.

Usage:
  python build_clean_c.py <recovery_job_dir_or_trajectory.json> \
      --task <name> --mode L1 --failure-type answer_spec \
      [--prefix-id <id>] [--atoms <atoms.json>] -o clean_c/<name>.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from recovery_agent import COMMON_FRAMING
from hint_strip import HintAtoms, atomize_hint, strip_hint_messages, tag_recovery


def _find_trajectory(path: Path) -> Path:
    if path.is_file():
        return path
    hits = list(path.rglob("trajectory.json"))
    if not hits:
        raise FileNotFoundError(f"no trajectory.json under {path}")
    return hits[0]


def _split(conv: List[Dict[str, Any]]) -> tuple[int, Optional[int]]:
    """Return (instruction_idx, hint_idx). hint = the user message carrying COMMON_FRAMING
    (injected recovery hint). raw-retry has no hint -> hint_idx is None and recovery starts
    right after the prefix's last message (we treat the 2nd user msg as the boundary; raw
    has none, so recovery = everything after the prefix which we can't see here -> require
    a hint for clean-C). Returns hint_idx=None if not found."""
    user_idxs = [i for i, m in enumerate(conv) if m.get("role") == "user"]
    instr = user_idxs[0] if user_idxs else 0
    frame_key = COMMON_FRAMING.strip()[:40]
    hint_idx = None
    for i in user_idxs[1:]:
        if frame_key in (conv[i].get("content") or ""):
            hint_idx = i
    return instr, hint_idx


def _arm_hint_payload(hint_text: str) -> str:
    """Strip COMMON_FRAMING off the front; what remains is the arm-specific diagnosis."""
    f = COMMON_FRAMING.strip()
    h = hint_text.strip()
    return h[len(f):].strip() if h.startswith(f) else h


def _sft_serialization(prefix: List[Dict[str, Any]], recovery: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the per-recovery-turn SFT examples and verify input hygiene.

    input  = prefix turns serialized WITHOUT reasoning_content + recovery observations so far
    label  = current assistant turn's reasoning_content (if present) + tool action
    The prefix/observation messages must carry NO reasoning_content (per-turn scratchpad)
    and NO hint text (hint already removed)."""
    def _io_msg(m: Dict[str, Any]) -> Dict[str, Any]:
        # serialize as INPUT: drop reasoning_content entirely (not fed back into context)
        out = {"role": m["role"]}
        if m.get("content") is not None:
            out["content"] = m["content"]
        if m.get("tool_calls"):
            out["tool_calls"] = [
                {"function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                for tc in m["tool_calls"]
            ]
        if m.get("tool_call_id"):
            out["tool_call_id"] = m["tool_call_id"]
        return out

    examples = []
    running_input = [_io_msg(m) for m in prefix]
    for m in recovery:
        if m.get("role") == "assistant":
            label = {}
            if m.get("reasoning_content"):
                label["reasoning_content"] = m["reasoning_content"]
            if m.get("content"):
                label["content"] = m["content"]
            if m.get("tool_calls"):
                label["tool_calls"] = [
                    {"function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                    for tc in m["tool_calls"]
                ]
            examples.append({
                "input_n_msgs": len(running_input),
                "label_has_reasoning": bool(m.get("reasoning_content")),
                "label": label,
            })
        running_input.append(_io_msg(m))

    # hygiene asserts: no reasoning_content anywhere in any example's INPUT, no hint text
    flat_input_text = json.dumps(running_input, ensure_ascii=False)
    input_has_reasoning = any("reasoning_content" in json.dumps(ex_in) for ex_in in [running_input])
    input_has_hint = COMMON_FRAMING.strip()[:40] in flat_input_text
    return {
        "n_examples": len(examples),
        "input_contains_reasoning_content": input_has_reasoning,   # must be False
        "input_contains_hint_text": input_has_hint,                # must be False
        "examples": examples,
    }


def build(traj_path: Path, task: str, mode: str, failure_type: str,
          prefix_id: Optional[str], atoms_path: Optional[Path]) -> Dict[str, Any]:
    traj = json.loads(_find_trajectory(traj_path).read_text())
    conv = traj["conversation"]
    instr_idx, hint_idx = _split(conv)
    if hint_idx is None:
        raise ValueError("no COMMON_FRAMING hint message found — is this a raw-retry run? "
                         "clean-C needs a hint-elicited recovery.")

    prefix = conv[:hint_idx]                 # student failure (replayed) — no hint
    hint_msg = conv[hint_idx]
    recovery = conv[hint_idx + 1:]           # student's own recovery turns + observations
    hint_text = hint_msg.get("content") or ""

    # atomize: explicit sidecar wins; else framing-stripped arm hint becomes the diagnosis.
    explicit = HintAtoms(**json.loads(atoms_path.read_text())) if atoms_path else None
    if explicit is None:
        payload = _arm_hint_payload(hint_text)
        explicit = atomize_hint(payload)     # diagnosis=payload + heuristic exact_action
    atoms = explicit

    stripped_recovery = strip_hint_messages(recovery)   # no-op here (hint already separated)
    strip = tag_recovery(stripped_recovery, atoms)

    recovery_assistant = [m for m in recovery if m.get("role") == "assistant"]
    reasoning_turns = [m for m in recovery_assistant if m.get("reasoning_content")]
    sft = _sft_serialization(prefix, recovery)

    final_reward = traj.get("final_reward")   # may be absent; verifier reward lives in result.json
    return {
        "source_task": task,
        "prefix_id": prefix_id or traj_path.name,
        "failure_type": failure_type,
        "recovery_mode": mode,                       # no-hint | L1 | L2 | L3
        "n_recovery_turns": len(recovery_assistant),
        "reasoning_present_on_recovery_turn": bool(reasoning_turns),
        "n_recovery_turns_with_reasoning": len(reasoning_turns),
        "hint_text": hint_text,
        "hint_atoms": {
            "diagnosis": atoms.diagnosis,
            "action_class": atoms.action_class,
            "exact_action": atoms.exact_action,
            "gold_literal": atoms.gold_literal,
        },
        "provenance": strip.provenance,              # evidence_supported|low_overlap|hint_derived|leak
        "strip_verdict": strip.verdict,              # clean | hint_derived | leak
        "strip_per_turn": [{"index": t.index, "verdict": t.verdict, "reasons": t.reasons}
                           for t in strip.turns],
        "strip_reasons": strip.reasons,
        "strict_main": strip.usable_for_strict_main,
        "sft_serialization_preview": sft,
        "audit_flags": {
            # the two that MUST be false for an honest sample:
            "input_leaks_reasoning": sft["input_contains_reasoning_content"],
            "input_leaks_hint": sft["input_contains_hint_text"],
            "recovery_references_hint": strip.provenance == "leak",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("traj", help="recovery job dir or trajectory.json")
    ap.add_argument("--task", required=True)
    ap.add_argument("--mode", default="L1", help="no-hint|L1|L2|L3")
    ap.add_argument("--failure-type", default="unknown")
    ap.add_argument("--prefix-id", default=None)
    ap.add_argument("--atoms", default=None, help="optional sidecar HintAtoms json")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()

    rec = build(Path(args.traj), args.task, args.mode, args.failure_type,
                args.prefix_id, Path(args.atoms) if args.atoms else None)
    out = json.dumps(rec, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out)
        a = rec["audit_flags"]
        print(f"wrote {args.output}")
        print(f"  provenance={rec['provenance']}  strict_main={rec['strict_main']}  "
              f"reasoning_on_recovery={rec['reasoning_present_on_recovery_turn']}")
        print(f"  audit: leaks_reasoning={a['input_leaks_reasoning']} "
              f"leaks_hint={a['input_leaks_hint']} refs_hint={a['recovery_references_hint']}")
    else:
        print(out)


if __name__ == "__main__":
    main()
