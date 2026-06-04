"""gate2.py — Gate 2 strict-main funnel record + aggregator (discussion-004 #16, Codex).

Per genuine process near-miss prefix, Gate 2 runs:
    no-hint retry N=1  →  diagnosis-hint recovery k<=3  →  (if reward 1) hint_strip
      →  (if non-leak) student-self rederive N=2  →  strong / weak / observed_only / fail

This module turns the run artifacts into ONE funnel record with the metadata Codex #16
asked for, and aggregates many records into the funnel table that leads the Gate 2 report.
It is glue over build_clean_c (hint_strip provenance) + rederive_check (student-self) — no
teacher API. Claude authors each grounded hint; everything else is local.

record(...) inputs:
  prefix_id, task, failure_type
  hint_text, hint_level (L1/L2/L3), hint_strength (observation|invariant|diagnosis|action_class)
  hint_job  : the diagnosis-hint recovery job dir (reward checked from result.json)
  nohint_jobs: list of no-hint/raw-retry job dirs (same prefix) for rederive
  atoms (optional): explicit HintAtoms dict

The single source of the strict-main verdict:
  strict_main_eligible = hint recovery reward==1 AND hint_strip != leak/hint_derived
                         AND rederive == strong
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import build_clean_c
import rederive_check


def _reward(job_dir: Path) -> Optional[float]:
    return rederive_check._reward_for(job_dir)


def record(prefix_id: str, task: str, failure_type: str, hint_text: str, hint_level: str,
           hint_strength: str, hint_job: Path, nohint_jobs: List[Path],
           atoms: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    reward = _reward(hint_job)
    hint_success = (reward or 0) >= 1.0

    hint_strip_label = None
    reasoning_present = None
    core_ids: List[str] = []
    rederive_label = None
    sample_rec = None

    if hint_success:
        # hint_strip provenance via build_clean_c (writes nothing; we just use the dict)
        traj = build_clean_c._find_trajectory(hint_job)
        from hint_strip import HintAtoms
        sample_rec = build_clean_c.build(
            traj, task, hint_level, failure_type, prefix_id,
            None,
        )
        # override atoms if explicitly provided (more precise than the framing-stripped guess)
        hint_strip_label = sample_rec["provenance"]
        reasoning_present = sample_rec["reasoning_present_on_recovery_turn"]

        if hint_strip_label not in ("leak", "hint_derived"):
            # build a clean_c-style record on disk for rederive_check input
            tmp = Path(f"/tmp/gate2_sample_{prefix_id}.json")
            tmp.write_text(json.dumps(sample_rec, ensure_ascii=False))
            rd = rederive_check.check(tmp, nohint_jobs)
            rederive_label = rd["rederive_label"]
            core_ids = rd["diagnosis_salient"]

    strict = bool(hint_success and hint_strip_label not in (None, "leak", "hint_derived")
                  and rederive_label == "strong")

    exclude_reason = None
    if not hint_success:
        exclude_reason = "no_reward"
    elif hint_strip_label in ("leak", "hint_derived"):
        exclude_reason = f"hint_strip:{hint_strip_label}"
    elif rederive_label != "strong":
        exclude_reason = f"rederive:{rederive_label}"

    return {
        "prefix_id": prefix_id,
        "task": task,
        "failure_type": failure_type,
        "hint_level_used": hint_level,
        "hint_text": hint_text,
        "hint_text_hash": f"{abs(hash(hint_text)) % (10**10):010d}",
        "hint_strength": hint_strength,            # observation|invariant|diagnosis|action_class
        "hint_recovery_reward": reward,
        "reasoning_present_on_recovery_turn": reasoning_present,
        "hint_strip_label": hint_strip_label,      # leak|hint_derived|evidence_supported|low_overlap
        "rederive_label": rederive_label,          # strong|weak|observed_only|fail|None
        "core_identifiers": core_ids,
        "strict_main_eligible": strict,
        "exclude_reason": exclude_reason,
    }


def funnel(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    succ = [r for r in records if (r["hint_recovery_reward"] or 0) >= 1.0]
    non_leak = [r for r in succ if r["hint_strip_label"] not in ("leak", "hint_derived")]
    strong = [r for r in non_leak if r["rederive_label"] == "strong"]
    weak = [r for r in non_leak if r["rederive_label"] == "weak"]
    rationalized = [r for r in non_leak if r["rederive_label"] in ("observed_only", "fail")]
    return {
        "N_prefix": len(records),
        "N_hint_success": len(succ),
        "N_non_leak": len(non_leak),
        "N_rederive_strong": len(strong),
        "N_rederive_weak": len(weak),
        "N_rationalized": len(rationalized),
        "strict_main_yield_over_prefix": (len(strong) / len(records)) if records else 0.0,
        "strict_main_yield_over_hint_success": (len(strong) / len(succ)) if succ else 0.0,
    }


def print_table(records: List[Dict[str, Any]]) -> None:
    f = funnel(records)
    print("=== Gate 2 strict-main funnel ===")
    print(f"  N_prefix            {f['N_prefix']:3d}  genuine process near-miss prefixes")
    print(f"  N_hint_success      {f['N_hint_success']:3d}  k<=3 diagnosis-hint recovery reward 1")
    print(f"  N_non_leak          {f['N_non_leak']:3d}  survived hint_strip (no leak/hint_derived)")
    print(f"  N_rederive_strong   {f['N_rederive_strong']:3d}  STRICT-MAIN eligible")
    print(f"  N_rederive_weak     {f['N_rederive_weak']:3d}  C-rederive-weak (appendix)")
    print(f"  N_rationalized      {f['N_rationalized']:3d}  raw success but rederive observed_only/fail")
    print(f"  strict yield: {f['strict_main_yield_over_prefix']:.0%} of prefixes, "
          f"{f['strict_main_yield_over_hint_success']:.0%} of hint successes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("records_glob", help="glob of gate2 record json files to aggregate")
    args = ap.parse_args()
    recs = [json.loads(Path(p).read_text()) for p in sorted(glob.glob(args.records_glob))]
    print_table(recs)


if __name__ == "__main__":
    main()
