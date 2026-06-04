"""rederive_check.py — student-self no-hint-rederive gate (discussion-004 #14, Codex).

The strict-main question for an arm-C sample is NOT "did the hinted recovery succeed" but
"could the student reach the same DIAGNOSIS without the hint?". If yes, the hinted recovery's
reasoning is evidence-grounded student knowledge (clean). If only the hint produces that
framing, the reasoning is hint-derived (rationalization) and must stay out of strict-main.

This runs entirely on the STUDENT (no teacher API): we compare the hint-elicited recovery's
diagnosis atoms against one or more no-hint resume trajectories from the SAME failure prefix
(raw-retry runs already are exactly this). Classification (Codex #14):

  strong : no-hint run STATES the diagnosis in its OWN reasoning/content (not merely sees the
           evidence in a tool observation) AND recovers (reward 1).
  weak   : no-hint run states the diagnosis / action-class in its own words AND observes the
           relevant evidence, but does NOT finish the task.
  fail   : no-hint run never states the diagnosis in its own words (it may incidentally see
           the evidence in an observation, but never connects it to the failure).

Crucial distinction: the diagnosis identifier appearing in a TOOL OBSERVATION or in a COMMAND
does NOT count — only the student's own reasoning_content / assistant content counts. (Real
case: spark no-hint runs `cat` a file that contains "TODO" comments and even copy them in a
heredoc, but never reason that the leftover TODOs are why the grader fails -> fail.)

Only `strong` enters strict-main. `weak` goes to a separate C-rederive-weak / natural-yield
bucket; `fail` means the hinted sample is hint-derived (exclude from strict-main).
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import re

from hint_strip import _salient_raw, _toks


def _core(text: str) -> set:
    """The DISCRIMINATIVE diagnosis identifiers only: ALL-CAPS markers (TODO, ERROR, FIXME)
    and path/symbol/dotted identifiers (table_catalog.py, valid_range, --flag). Plain long
    words ('implementation', 'contains') are NOT core — they're generic agent chatter that
    overlaps by chance and would inflate a rederive match. Strong/weak require a CORE
    identifier in the student's own voice, not a soft word."""
    caps = {w.lower() for w in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text or "")}
    ids = {t.strip("./-") for t in _toks(text) if any(c in t for c in "./_-")}
    # keep only identifiers that still look specific after stripping trailing punctuation
    ids = {t for t in ids if (any(c in t for c in "./_-") or len(t) >= 6) and len(t) >= 3}
    return caps | ids


def _load(path: Path) -> Dict[str, Any]:
    if path.is_dir():
        hits = glob.glob(str(path / "**" / "trajectory.json"), recursive=True)
        if not hits:
            raise FileNotFoundError(f"no trajectory.json under {path}")
        path = Path(hits[0])
    return json.loads(path.read_text())


def _recovery_slice(conv: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Messages after the last user turn (hint for L*, or just the resume point for raw)."""
    us = [i for i, m in enumerate(conv) if m.get("role") == "user"]
    start = (us[-1] + 1) if us else 0
    return conv[start:]


def _student_voice(msgs: List[Dict[str, Any]]) -> str:
    """ONLY the student's own reasoning_content + content — NOT tool_calls, NOT observations.
    This is where a self-derived diagnosis would live."""
    out = []
    for m in msgs:
        if m.get("role") == "assistant":
            out.append(m.get("reasoning_content") or "")
            out.append(m.get("content") or "")
    return "\n".join(out)


def _observed(msgs: List[Dict[str, Any]]) -> str:
    return "\n".join(m.get("content") or "" for m in msgs if m.get("role") == "tool")


def rederive_label(diagnosis_salient: set, nohint_conv: List[Dict[str, Any]],
                   reward: Optional[float]) -> Dict[str, Any]:
    rec = _recovery_slice(nohint_conv)
    voice = _student_voice(rec)
    obs = _observed(rec)

    # decision keys = CORE diagnosis identifiers only (caps markers / symbols / paths)
    core = diagnosis_salient
    in_voice = sorted(core & _core(voice))                # student SAID a core identifier
    in_obs_only = sorted((core & _core(obs)) - set(in_voice))  # only seen, never said
    # soft overlap reported for context but NOT used for the label
    soft_voice = sorted((_salient_raw(voice) & _salient_raw(" ".join(core))) - set(in_voice))

    stated = len(in_voice) >= 1
    recovered = (reward or 0) >= 1.0
    if stated and recovered:
        label = "strong"
    elif stated:
        label = "weak"
    else:
        label = "fail"
    return {
        "label": label,
        "recovered": recovered,
        "core_diagnosis_stated_in_student_voice": in_voice,
        "core_diagnosis_seen_only_in_observation": in_obs_only,
        "soft_overlap_in_voice_ignored": soft_voice,
    }


def _reward_for(job_dir: Path) -> Optional[float]:
    for p in glob.glob(str(job_dir / "**" / "result.json"), recursive=True):
        try:
            d = json.loads(Path(p).read_text())
            return (d.get("verifier_result") or {}).get("rewards", {}).get("reward")
        except Exception:
            pass
    return None


def check(hint_sample: Path, nohint_dirs: List[Path]) -> Dict[str, Any]:
    """hint_sample = a clean_c/*.json record (has hint_atoms) OR a hint recovery trajectory.
    nohint_dirs = raw-retry / no-hint resume job dirs for the SAME prefix."""
    rec = json.loads(hint_sample.read_text())
    if "hint_atoms" in rec:
        atoms = rec["hint_atoms"]
        diag_text = " ".join(atoms.get("diagnosis", []) + atoms.get("action_class", []))
    else:  # a raw trajectory: use its hint message
        conv = rec["conversation"]
        us = [m for m in conv if m.get("role") == "user"]
        diag_text = us[-1].get("content", "") if us else ""
    diag_salient = _core(diag_text)     # decision keys = core identifiers only

    results = []
    for d in nohint_dirs:
        conv = _load(d)["conversation"]
        results.append({"dir": str(d), **rederive_label(diag_salient, conv, _reward_for(d))})

    labels = [r["label"] for r in results]
    # aggregate: best label across no-hint seeds (any strong -> strong, etc.)
    rank = {"fail": 0, "weak": 1, "strong": 2}
    agg = max(labels, key=lambda l: rank[l]) if labels else "fail"
    return {
        "diagnosis_salient": sorted(diag_salient),
        "n_nohint_runs": len(results),
        "per_run": results,
        "rederive_label": agg,
        "strict_main_eligible": agg == "strong",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hint_sample", help="clean_c/*.json record or hint recovery trajectory")
    ap.add_argument("nohint", nargs="+", help="no-hint / raw-retry job dir(s) for same prefix")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()
    out = check(Path(args.hint_sample), [Path(p) for p in args.nohint])
    s = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(s)
        print(f"wrote {args.output}")
    print(f"rederive_label={out['rederive_label']}  strict_main_eligible={out['strict_main_eligible']}")
    print(f"  core diagnosis identifiers: {out['diagnosis_salient']}")
    for r in out["per_run"]:
        print(f"  {r['label']:6s} recovered={r['recovered']} "
              f"stated_in_voice={r['core_diagnosis_stated_in_student_voice']} "
              f"seen_only_in_obs={r['core_diagnosis_seen_only_in_observation']}")


if __name__ == "__main__":
    main()
