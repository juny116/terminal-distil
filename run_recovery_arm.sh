#!/usr/bin/env bash
# Run ONE recovery arm in-env and print its reward.
# Usage: run_recovery_arm.sh <traj> <ece_ep> <task_name> <arm> <out_label> [hint]
set -euo pipefail
source /home/juny116/anaconda3/etc/profile.d/conda.sh && conda activate terminal-distil

TRAJ="$1"; ECE="$2"; TASK="$3"; ARM="$4"; LABEL="$5"; HINT="${6:-}"
PY=/home/juny116/anaconda3/envs/terminal-distil/bin/python
ENV=/home/juny116/Workspace/terminal-bench-env/environments_harbor
PREFIX="/tmp/poc_prefix/${LABEL}_${ARM}.json"
OUT="jobs/recov_${LABEL}_${ARM}"
mkdir -p /tmp/poc_prefix

$PY recovery_agent.py "$TRAJ" --ece "$ECE" --task-name "$TASK" --arm "$ARM" \
    ${HINT:+--hint "$HINT"} --output "$PREFIX" >/dev/null

STEP0_PREFIX_FILE="$PREFIX" MODEL_NAME=Qwen/Qwen3.5-4B MODEL_ENDPOINT=http://172.17.0.1:8001/v1 \
  harbor run -p "$ENV" --agent-import-path 'recovery_agent:ResumeBashAgent' \
  -e docker -i "$TASK" -n 1 -o "$OUT" --job-name "recov_${LABEL}_${ARM}" >/tmp/recov_run.log 2>&1 || true

R=$($PY - "$OUT" <<'PY'
import json,glob,sys,os
out=sys.argv[1]; rs=glob.glob(out+"/*/*/result.json")
v="ERR"
for p in rs:
    try: d=json.load(open(p)); v=(d.get("verifier_result") or {}).get("rewards",{}).get("reward")
    except: pass
print(v)
PY
)
echo "ARM=$ARM  reward=$R"
