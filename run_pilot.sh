#!/usr/bin/env bash
# Pilot run: 30 tasks with GPT teacher to estimate cost and success rate.
# Usage: bash run_pilot.sh [model_name]
#   model_name: gpt-4.1-mini (default) or gpt-4.1 etc.

set -euo pipefail

MODEL="${1:-gpt-5.4-mini}"
TASKS_DIR="${TASKS_DIR:?set TASKS_DIR to terminal-bench-env/environments_harbor}"
JOBS_DIR="${JOBS_DIR:-./jobs}"
N_TASKS=1000
N_CONCURRENT=4

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY not set"
  exit 1
fi

echo "Model: $MODEL"
echo "Tasks: $N_TASKS  Concurrent: $N_CONCURRENT"
echo ""

MODEL_NAME="$MODEL" harbor run \
  -p "$TASKS_DIR" \
  --agent-import-path "gpt_agent:GPTAgent" \
  -e docker \
  --n-tasks "$N_TASKS" \
  --n-concurrent "$N_CONCURRENT" \
  -o "$JOBS_DIR/pilot_${MODEL}_$(date +%Y%m%d_%H%M%S)" \
  --job-name "pilot_${MODEL}"
