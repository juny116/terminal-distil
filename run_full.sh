#!/usr/bin/env bash
# Full collection run on all environments_harbor tasks (no filtering).
#
# Usage:
#   bash run_full.sh <model> [n_concurrent] [job_label]
#
# Examples:
#   bash run_full.sh gpt-5.4-2026-03-05            # 4 concurrent, label=full
#   bash run_full.sh gpt-5.4-2026-03-05 2          # 2 concurrent (when sharing GPU with another run)
#   bash run_full.sh gpt-5.4-2026-03-05 4 v2       # custom label

set -euo pipefail

MODEL="${1:-gpt-5.4-mini}"
N_CONCURRENT="${2:-4}"
LABEL="${3:-full}"

TASKS_DIR="${TASKS_DIR:?set TASKS_DIR to terminal-bench-env/environments_harbor}"
JOBS_DIR="${JOBS_DIR:-./jobs}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY not set"; exit 1
fi

echo "Model       : $MODEL"
echo "Tasks       : ALL (~3,567)"
echo "Concurrent  : $N_CONCURRENT"
echo "Label       : $LABEL"
echo ""

MODEL_NAME="$MODEL" harbor run \
  -p "$TASKS_DIR" \
  --agent-import-path "gpt_agent:GPTAgent" \
  -e docker \
  --n-concurrent "$N_CONCURRENT" \
  --n-attempts 1 \
  -o "$JOBS_DIR/${LABEL}_${MODEL}_$(date +%Y%m%d_%H%M%S)" \
  --job-name "${LABEL}_${MODEL}"
