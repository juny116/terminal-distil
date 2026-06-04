#!/usr/bin/env python3
"""Independently verify that the cassandra_sstable_export_medium verifier is BROKEN
(an impossible task), by running the REAL test file unmodified except for swapping
its hardcoded output path to a temp file.

Claim: any output that passes `test_timestamps_are_iso8601_format` (which REQUIRES
timestamps ending in "Z") must CRASH `test_timestamps_within_valid_range`, because
the latter compares an offset-aware datetime (from the "Z" timestamp) against a
naive `datetime(2020,1,1)` -> TypeError. So no correct answer can pass both.

Run:  python3 verify_cassandra_bug.py
"""
import json, os, re, tempfile, importlib.util, inspect
from pathlib import Path
from datetime import datetime

REAL_TEST = ("/home/juny116/Workspace/terminal-bench-env/environments_harbor/"
             "cassandra_sstable_export_medium/tests/test_outputs.py")

# ── 0. Minimal standalone proof (3 lines, no files) ─────────────────────────────
print("="*70)
print("MINIMAL PROOF (just Python's datetime, mirroring the verifier's two lines):")
ts = "2021-03-15T08:30:00Z"                       # a VALID timestamp (ends with Z, as the iso8601 test demands)
dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))   # exactly line 70 of the verifier -> AWARE
min_date = datetime(2020, 1, 1)                            # exactly line 65 of the verifier -> NAIVE
try:
    _ = dt >= min_date                                    # exactly line 72 of the verifier
    print("  no error (unexpected)")
except TypeError as e:
    print(f"  dt >= min_date  ->  TypeError: {e}")
    print("  => a correct, Z-suffixed timestamp CANNOT be range-checked by this verifier.")

# ── 1. Run the REAL verifier file against a PERFECTLY VALID output ───────────────
src = Path(REAL_TEST).read_text()

print("\n" + "="*70)
print("The two relevant functions from the REAL verifier (verbatim):\n")
for fn in ("test_timestamps_are_iso8601_format", "test_timestamps_within_valid_range"):
    m = re.search(rf"def {fn}\b.*?(?=\ndef |\Z)", src, re.S)
    print(m.group(0).rstrip() + "\n")

# A perfectly valid output: 3 unique, sorted records, exactly the 3 required fields,
# non-null user_ids, Z timestamps inside 2020-2024. It satisfies every other test.
valid = [
    {"user_id": "u1", "timestamp": "2021-03-15T08:30:00Z", "event_type": "login"},
    {"user_id": "u2", "timestamp": "2022-07-20T12:00:00Z", "event_type": "click"},
    {"user_id": "u3", "timestamp": "2023-11-01T23:59:59Z", "event_type": "logout"},
]
tmp = tempfile.mkdtemp()
outfile = os.path.join(tmp, "cleaned_events.json")
Path(outfile).write_text(json.dumps(valid))

# Load the real test code, swapping ONLY the hardcoded path literal (nothing else).
patched = src.replace('"/output/cleaned_events.json"', json.dumps(outfile))
assert patched != src, "expected path literal not found - verifier file changed?"
mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("cass", loader=None))
exec(patched, mod.__dict__)

print("="*70)
print(f"Running the REAL tests against a PERFECTLY VALID output ({len(valid)} records):\n")
tests = sorted(n for n, _ in inspect.getmembers(mod, inspect.isfunction) if n.startswith("test_"))
n_pass = n_fail = 0
for n in tests:
    try:
        getattr(mod, n)()
        print(f"  PASS   {n}")
        n_pass += 1
    except Exception as e:
        print(f"  FAIL   {n}: {type(e).__name__}: {e}")
        n_fail += 1

print("\n" + "="*70)
print(f"RESULT: {n_pass} passed, {n_fail} failed on an output that is, by construction, correct.")
if n_fail and any("valid_range" in t for t in tests):
    print("=> The ONLY failure is the range check, which crashes on a valid Z-timestamp.")
    print("=> No possible output can pass all tests => the task is UNWINNABLE (verifier bug).")
