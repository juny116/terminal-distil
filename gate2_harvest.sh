#!/usr/bin/env bash
# Gate 2 fresh student harvest (discussion-004 #14/#16) — thinking-ON, unbiased.
# Runs the student (eval_agent:BashAgent) on a fresh task list to surface genuine
# process near-miss failures. Recovery/hint/rederive are applied PER near-miss afterward
# (Claude authors the grounded hint; rederive is student-self). No teacher API here.
#
# Usage: bash gate2_harvest.sh <task_list_file> [job_label]
set -euo pipefail
source /home/juny116/anaconda3/etc/profile.d/conda.sh && conda activate terminal-distil

LIST="${1:?task list file required}"
LABEL="${2:-gate2_harvest}"
ENV=/home/juny116/Workspace/terminal-bench-env/environments_harbor
OUT="jobs/${LABEL}"

INCLUDE_FLAGS=()
while IFS= read -r t; do [ -n "$t" ] && INCLUDE_FLAGS+=("-i" "$t"); done < "$LIST"
echo "tasks=$(wc -l < "$LIST")  out=$OUT  thinking=ON"

MODEL_NAME=Qwen/Qwen3.5-4B MODEL_ENDPOINT=http://172.17.0.1:8001/v1 \
  QWEN_ENABLE_THINKING=1 \
  harbor run -p "$ENV" --agent-import-path 'eval_agent:BashAgent' \
  -e docker "${INCLUDE_FLAGS[@]}" -n 1 -o "$OUT" --job-name "$LABEL"

echo "GATE2 HARVEST DONE -> $OUT"
