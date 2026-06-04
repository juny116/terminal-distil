"""Step 0+ failure-mining funnel (discussion-003 #7/#11/#12).

Static, cheap pass over a harvest job dir that classifies every reward-0 student
failure and reports the FUNNEL with denominators (Codex #11: no cherry-picking).
This narrows the pool to genuine, recovery-supervisable candidates BEFORE the
expensive raw-retry reproducibility pass (recovery_agent) is run on survivors.

Per failure we detect:
  - substrate_ok    : parsed_tool_call_rate high, empty-stop low (tool_call_stats)
  - completed       : did the agent call task_complete?
  - n_pass / n_fail : per-test counts from verifier/test-stdout.txt
  - fail_kinds      : exception type of each FAILED test, split into
                        assertion  -> genuine (student output violated an assert)
                        crash      -> TypeError/IndexError/JSONDecodeError/... = the
                                      TEST CODE threw = likely verifier/data bug
                                      (e.g. cassandra's aware-vs-naive datetime bug)
  - likely_verifier_bug : has crash-fails AND no assertion-fails (all failures are
                          test crashes -> the student may be correct; exclude/review)
  - likely_timeout  : not completed and (AgentTimeout exception OR very high turns)
  - near_miss_score : n_pass / (n_pass + n_fail)

Funnel:  reward-0  ->  -substrate-invalid  ->  -verifier-bug  ->  -timeout
                   ->  genuine candidates  ->  near-miss subset (score >= thresh)

Usage:  python3 mine_failures.py jobs/student_harvest50_180424 [--near-miss 0.6]
"""
import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional

# Exceptions that mean the TEST CODE itself crashed on (likely valid) data = a
# verifier/data bug candidate. Deliberately EXCLUDES FileNotFoundError/OSError,
# which usually mean the student never produced the expected output (= genuine
# student failure, not a verifier bug).
_CRASH_EXC = (
    "TypeError", "IndexError", "KeyError", "AttributeError", "ValueError",
    "JSONDecodeError", "BadGzipFile", "UnicodeDecodeError",
    "ZeroDivisionError", "OverflowError", "RecursionError", "StopIteration",
)
_MISSING_EXC = ("FileNotFoundError", "OSError", "NotADirectoryError")

# pytest summary line: "FAILED path::test_name - ExceptionType: msg..." (the
# ExceptionType here is often TRUNCATED, e.g. "TypeErr..."), so we also scan the
# (untruncated) traceback lines below.
_FAILED_RE = re.compile(r"^FAILED\s+\S+::(\S+)", re.M)
_SUMMARY_RE = re.compile(r"(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error")
# Untruncated exception names from the traceback:
#   "E       TypeError: ..."  and  "/tests/test_outputs.py:72: TypeError"
_EXC_E_RE = re.compile(r"^E\s+([A-Za-z_][\w.]*(?:Error|Exception|Iteration)):", re.M)
_EXC_LOC_RE = re.compile(r":\d+:\s+([A-Za-z_][\w.]*(?:Error|Exception|Iteration))\s*$", re.M)
_ASSERT_MSG_RE = re.compile(r"^E\s+AssertionError:\s*(.+)$", re.M)

# Tentative failure_layer keywords (discussion-003 #7/#12). A real label needs an
# LLM judge reading task+assertion; this is a cheap pre-label only.
_PROCESS_KW = (
    "unimplemented", "todo", "missing", "not exist", "does not exist", "not found",
    "no such", "is empty", "incomplete", "exit code", "nonzero", "non-zero",
    "stderr", "permission denied", "not executable", "failed to compile",
    "build failed", "did not create", "was not created", "timed out", "only",
    "at least", "expected at least",
)
_ANSWER_KW = (
    "incorrect", "does not match", "mismatch", "wrong", "should be", "should equal",
    "expected ", "accuracy", "threshold", "got ", "!=", "is before", "is after",
    "invalid result", "unexpected",
)


def _classify_exc(exc: str) -> str:
    base = exc.split(".")[-1]
    if base == "AssertionError":
        return "assertion"
    if base in _CRASH_EXC:
        return "crash"
    if base in _MISSING_EXC:
        return "missing_output"
    return "other"


@dataclass
class FailRow:
    task_name: str
    n_pass: int
    n_fail: int
    near_miss_score: float
    fail_tests: List[str] = field(default_factory=list)   # failed test names
    fail_excs: List[str] = field(default_factory=list)    # exception types seen
    has_assertion_fail: bool = False
    has_crash_fail: bool = False
    likely_verifier_bug: bool = False
    completed: bool = False
    likely_timeout: bool = False
    failure_layer: str = "unknown"        # tentative: process | answer_spec | mixed | unknown
    parsed_tool_call_rate: Optional[float] = None
    substrate_ok: bool = True
    n_turns: Optional[int] = None
    trial_dir: str = ""


def _parse_verifier(stdout: str):
    n_pass = len(re.findall(r"^PASSED\b", stdout, re.M))
    failed_tests = _FAILED_RE.findall(stdout)     # [test_name, ...]
    # Untruncated exception types from the traceback (E-lines + location lines).
    exc_types = _EXC_E_RE.findall(stdout) + _EXC_LOC_RE.findall(stdout)
    s_pass = s_fail = s_err = 0
    for m in _SUMMARY_RE.finditer(stdout):
        if m.group(1):
            s_pass = int(m.group(1))
        if m.group(2):
            s_fail = int(m.group(2))
        if m.group(3):
            s_err = int(m.group(3))
    n_pass = max(n_pass, s_pass)
    n_fail = max(len(failed_tests), s_fail + s_err)
    assert_msgs = [m.lower() for m in _ASSERT_MSG_RE.findall(stdout)]
    return n_pass, n_fail, failed_tests, exc_types, assert_msgs


def _failure_layer(completed: bool, assert_msgs, near_miss_score: float) -> str:
    """Tentative process vs answer_spec pre-label (needs LLM judge to confirm)."""
    if not completed:
        return "process"          # got cut off / stopped before finishing
    blob = " ".join(assert_msgs)
    proc = any(k in blob for k in _PROCESS_KW)
    ans = any(k in blob for k in _ANSWER_KW)
    if proc and not ans:
        return "process"
    if ans and not proc:
        return "answer_spec"      # declared success, only a value/correctness assert failed
    if proc and ans:
        return "mixed"
    return "unknown"


def analyze_trial(trial_dir: Path) -> Optional[FailRow]:
    rj = trial_dir / "result.json"
    if not rj.exists():
        return None
    try:
        result = json.loads(rj.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    reward = (result.get("verifier_result") or {}).get("rewards", {}).get("reward")
    if reward != 0.0:
        return None
    task = result.get("task_name") or trial_dir.name

    # verifier per-test
    so = trial_dir / "verifier" / "test-stdout.txt"
    n_pass = n_fail = 0
    failed_tests = []
    exc_types = []
    assert_msgs = []
    if so.exists():
        n_pass, n_fail, failed_tests, exc_types, assert_msgs = _parse_verifier(so.read_text(errors="ignore"))
    kinds = [_classify_exc(e) for e in exc_types]
    has_assert = "assertion" in kinds
    has_crash = "crash" in kinds
    has_missing = "missing_output" in kinds
    tot0 = n_pass + n_fail
    score0 = n_pass / tot0 if tot0 else 0.0
    # verifier-bug candidate: the test CODE crashed (TypeError/IndexError/...) with NO
    # genuine assertion failure, AND the output passed most other tests (a real bug
    # crashes one buggy check while the output is otherwise fine, e.g. cassandra 8/9).
    likely_bug = has_crash and not has_assert and score0 >= 0.5

    # trajectory: substrate + completion + turns
    completed = False
    parsed_rate = None
    substrate_ok = True
    n_turns = None
    tj = trial_dir / "agent" / "trajectory.json"
    if tj.exists():
        try:
            traj = json.loads(tj.read_text())
            tc = traj.get("tool_call_stats", {})
            parsed_rate = tc.get("parsed_tool_call_rate")
            resp = tc.get("n_model_responses") or 0
            estop = tc.get("n_empty_tool_call_stops") or 0
            substrate_ok = (parsed_rate is None or parsed_rate >= 0.9) and (
                resp == 0 or estop / max(resp, 1) <= 0.2
            )
            n_turns = traj.get("n_turns")
            completed = any(
                s.get("called_task_complete") for s in (traj.get("step_log") or [])
            )
        except (json.JSONDecodeError, OSError):
            pass

    exc_name = (result.get("exception") or result.get("error") or "")
    if isinstance(exc_name, dict):
        exc_name = json.dumps(exc_name)
    likely_timeout = (not completed) and (
        "Timeout" in str(exc_name) or (n_turns is not None and n_turns >= 40)
    )

    layer = _failure_layer(completed, assert_msgs, score0)
    return FailRow(
        task_name=task, n_pass=n_pass, n_fail=n_fail, near_miss_score=round(score0, 3),
        fail_tests=failed_tests,
        fail_excs=sorted({e.split('.')[-1] for e in exc_types}),
        has_assertion_fail=has_assert, has_crash_fail=has_crash,
        likely_verifier_bug=likely_bug, completed=completed,
        likely_timeout=likely_timeout, failure_layer=layer,
        parsed_tool_call_rate=parsed_rate,
        substrate_ok=substrate_ok, n_turns=n_turns, trial_dir=str(trial_dir),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir", type=Path)
    ap.add_argument("--near-miss", type=float, default=0.6, help="near-miss score threshold")
    ap.add_argument("--output", type=Path, default=Path("data/funnel.jsonl"))
    args = ap.parse_args()

    rows = []
    for rj in args.job_dir.rglob("result.json"):
        row = analyze_trial(rj.parent)
        if row:
            rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    total = len(rows)
    substrate_bad = [r for r in rows if not r.substrate_ok]
    survivors = [r for r in rows if r.substrate_ok]
    vbug = [r for r in survivors if r.likely_verifier_bug]
    survivors2 = [r for r in survivors if not r.likely_verifier_bug]
    timeout = [r for r in survivors2 if r.likely_timeout]
    genuine = [r for r in survivors2 if not r.likely_timeout]
    near = sorted([r for r in genuine if r.near_miss_score >= args.near_miss],
                  key=lambda r: -r.near_miss_score)

    def pct(n):
        return f"{n} ({100*n//max(total,1)}%)"

    print(f"\n{'='*60}\nSTEP 0+ FAILURE FUNNEL  ({args.job_dir})\n{'='*60}")
    print(f"  reward-0 failures            : {total}")
    print(f"  - substrate invalid (parser) : {pct(len(substrate_bad))}")
    print(f"  - likely verifier/data bug   : {pct(len(vbug))}   (test crashed, no assertion-fail)")
    print(f"  - likely timeout (interrupted): {pct(len(timeout))}")
    print(f"  = genuine student failures   : {pct(len(genuine))}")
    print(f"      of which near-miss (>={args.near_miss}) : {len(near)}")
    print(f"\n  verifier-bug candidates (test crashed, output passed most checks):")
    for r in vbug:
        print(f"    {r.near_miss_score:.2f}  {r.n_pass}/{r.n_pass+r.n_fail}  {r.task_name:42s} excs={r.fail_excs}")
    layer_counts = Counter(r.failure_layer for r in genuine)
    print(f"\n  genuine failure_layer (tentative): {dict(layer_counts)}")
    proc_near = [r for r in near if r.failure_layer == "process"]
    print(f"\n  near-miss genuine failures (recovery candidates):")
    for r in near:
        flag = "completed" if r.completed else "stopped"
        print(f"    {r.near_miss_score:.2f}  {r.n_pass}/{r.n_pass+r.n_fail}  {r.failure_layer:11s} [{flag:9s}] {r.task_name}")
    print(f"\n  => PRIMARY non-leak recovery targets (near-miss + process): {len(proc_near)}")
    for r in proc_near:
        print(f"       {r.task_name}")
    print(f"\nOutput: {args.output}  ({total} rows)")


if __name__ == "__main__":
    main()
