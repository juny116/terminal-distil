#!/usr/bin/env bash
# Raw-retry reproducibility gate (discussion-003 #7): resume each candidate from
# near its end with NO hint, N times. raw-retry pass>0 => flaky/self-recoverable
# (e.g. timeout) => EXCLUDE from the needs-hint pool. pass==0 => stable failure.
# Usage: reproducibility_gate.sh <task_pattern> <n>
set -uo pipefail
JOB=jobs/student_harvest50_180424/harvest50
PY=/home/juny116/anaconda3/envs/terminal-distil/bin/python
PAT="$1"; N="${2:-2}"
TRAJ=$(find "$JOB" -path "*${PAT}*" -name trajectory.json | head -1)
TASK=$($PY -c "import json,glob,os; d=os.path.dirname('$TRAJ'); import json as j; r=j.load(open(os.path.join(d,'..','result.json'))); print(r['task_name'])")
# auto-ECE = (#assistant steps) - 2, so we replay almost everything then continue
ECE=$($PY -c "import json; c=json.load(open('$TRAJ'))['conversation']; a=sum(1 for m in c if m.get('role')=='assistant'); print(max(0,a-2))")
echo "## $TASK  (auto-ECE=$ECE, N=$N)"
P=0
for s in $(seq 1 $N); do
  R=$(bash run_recovery_arm.sh "$TRAJ" "$ECE" "$TASK" raw-retry "gate_${PAT}_$s" "" 2>&1 | grep -oE "reward=[0-9.]+" | cut -d= -f2)
  echo "   raw-retry s$s: reward=$R"
  [ "$R" = "1.0" ] && P=$((P+1))
done
echo "   => raw-retry pass $P/$N  ($([ $P -gt 0 ] && echo 'FLAKY/self-recoverable - EXCLUDE' || echo 'stable failure - keep'))"
