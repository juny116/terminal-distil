#!/usr/bin/env bash
# Run arm B (Claude-as-teacher scripted recovery). Usage: run_b.sh <traj> <ece> <task> <bscript> <label>
set -uo pipefail
source /home/juny116/anaconda3/etc/profile.d/conda.sh && conda activate terminal-distil
TRAJ="$1"; ECE="$2"; TASK="$3"; BSCRIPT="$4"; LABEL="$5"
PY=/home/juny116/anaconda3/envs/terminal-distil/bin/python
ENV=/home/juny116/Workspace/terminal-bench-env/environments_harbor
PREFIX="/tmp/poc_prefix/b_${LABEL}.json"; mkdir -p /tmp/poc_prefix
$PY recovery_agent.py "$TRAJ" --ece "$ECE" --task-name "$TASK" --arm raw-retry --output "$PREFIX" >/dev/null
STEP0_PREFIX_FILE="$PREFIX" B_SCRIPT_FILE="$BSCRIPT" MODEL_NAME=Qwen/Qwen3.5-4B \
  MODEL_ENDPOINT=http://172.17.0.1:8001/v1 QWEN_ENABLE_THINKING=1 \
  harbor run -p "$ENV" --agent-import-path 'scripted_agent:ScriptedBashAgent' \
  -e docker -i "$TASK" -n 1 -o "jobs/b_${LABEL}" --job-name "b_${LABEL}" >/tmp/b_run.log 2>&1 || true
R=$($PY - "jobs/b_${LABEL}" <<'PY'
import json,glob,sys
for p in glob.glob(sys.argv[1]+"/**/result.json",recursive=True):
    d=json.load(open(p)); r=(d.get("verifier_result") or {}).get("rewards",{}).get("reward")
    if r is not None: print(r); break
else: print("ERR")
PY
)
echo "B $LABEL reward=$R"
