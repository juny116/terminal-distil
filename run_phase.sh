#!/usr/bin/env bash
# Run one phase: a fresh harbor run on a subset of tasks read from a file.
#
# Usage:
#   bash run_phase.sh <model> <task_list_file> <job_label> [n_attempts]
#
# Example:
#   # Phase A — run all tasks not yet attempted, once
#   python select_tasks.py jobs/ --mode unattempted --output /tmp/remaining.txt
#   bash run_phase.sh gpt-5.4-mini /tmp/remaining.txt phaseA 1
#
#   # Phase B — retry tasks that haven't succeeded, up to 4 times each
#   python select_tasks.py jobs/ --mode failed --output /tmp/failed.txt
#   bash run_phase.sh gpt-5.4-mini /tmp/failed.txt phaseB 4

set -euo pipefail

MODEL="${1:?model name required (e.g. gpt-5.4-mini)}"
LIST="${2:?task list file required}"
LABEL="${3:?job label required}"
ATTEMPTS="${4:-1}"

TASKS_DIR="${TASKS_DIR:?set TASKS_DIR to terminal-bench-env/environments_harbor}"
JOBS_DIR="${JOBS_DIR:-./jobs}"
N_CONCURRENT=4

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY not set"; exit 1
fi
if [ ! -f "$LIST" ]; then
  echo "ERROR: task list file not found: $LIST"; exit 1
fi

# Build -i flags from task list (one task name per line)
INCLUDE_FLAGS=()
while IFS= read -r task; do
  [ -n "$task" ] && INCLUDE_FLAGS+=("-i" "$task")
done < "$LIST"

N_TASKS=$(wc -l < "$LIST")
echo "Model       : $MODEL"
echo "Tasks       : $N_TASKS"
echo "Attempts    : $ATTEMPTS  (per task)"
echo "Concurrent  : $N_CONCURRENT"
echo ""

MODEL_NAME="$MODEL" harbor run \
  -p "$TASKS_DIR" \
  --agent-import-path "gpt_agent:GPTAgent" \
  -e docker \
  --n-concurrent "$N_CONCURRENT" \
  --n-attempts "$ATTEMPTS" \
  "${INCLUDE_FLAGS[@]}" \
  -o "$JOBS_DIR/${LABEL}_${MODEL}_$(date +%Y%m%d_%H%M%S)" \
  --job-name "${LABEL}_${MODEL}"
