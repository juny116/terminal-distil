#!/usr/bin/env bash
# Overnight: wait for C1 training -> merge -> serve C1 on GPU1:8002 -> eval on held-out
# 100 tasks (same set the base model is evaluated on by eval100_base) -> kill server.
set -uo pipefail
cd /home/juny116/Workspace/terminal-distil
PYIB=/home/juny116/anaconda3/envs/identity-bias/bin/python
VLLM=/home/juny116/anaconda3/envs/identity-bias/bin/vllm
ENV=/home/juny116/Workspace/terminal-bench-env/environments_harbor
LIST=/tmp/eval100_tasks.txt
log(){ echo "[$(date +%H:%M:%S)] $*"; }

log "waiting for TRAIN_C1 DONE..."
while ! grep -q "TRAIN_C1 DONE" /tmp/train_c1.out 2>/dev/null; do sleep 60; done
log "training done."

ADAPTER=runs/c1_all
MERGED=/data/juny116/terminal-distil/merged/c1_all
if [ ! -f "$MERGED/config.json" ]; then
  log "merging $ADAPTER -> $MERGED"
  HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 $PYIB merge_adapter.py "$ADAPTER" "$MERGED" 2>&1 | tail -3
fi
[ -f "$MERGED/config.json" ] || { log "MERGE FAILED"; echo "EVAL_C1 DONE"; exit 1; }

log "starting C1 vLLM server on GPU1:8002"
export VLLM_USE_FLASHINFER_SAMPLER=0
CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 "$VLLM" serve "$MERGED" \
  --served-model-name c1 --host 0.0.0.0 --port 8002 \
  --tensor-parallel-size 1 --max-model-len 120000 --gpu-memory-utilization 0.85 \
  --language-model-only --enable-auto-tool-choice --tool-call-parser qwen3_xml \
  --enable-prefix-caching > /tmp/c1_server.out 2>&1 &
SERVER_PID=$!
log "server pid $SERVER_PID; waiting for health..."
for i in $(seq 1 60); do
  curl -s http://172.17.0.1:8002/v1/models >/dev/null 2>&1 && { log "server up"; break; }
  sleep 15
done
curl -s http://172.17.0.1:8002/v1/models >/dev/null 2>&1 || { log "SERVER NEVER CAME UP"; kill $SERVER_PID 2>/dev/null; echo "EVAL_C1 DONE"; exit 1; }

INCLUDE=(); while IFS= read -r t; do [ -n "$t" ] && INCLUDE+=("-i" "$t"); done < "$LIST"
log "running C1 eval on $(wc -l < "$LIST") tasks..."
MODEL_NAME=c1 MODEL_ENDPOINT=http://172.17.0.1:8002/v1 QWEN_ENABLE_THINKING=1 \
  harbor run -p "$ENV" --agent-import-path 'eval_agent:BashAgent' \
  -e docker "${INCLUDE[@]}" -n 1 -o jobs/eval100_c1 --job-name eval100_c1 > /tmp/eval100_c1.out 2>&1

log "eval done; killing server $SERVER_PID"
kill $SERVER_PID 2>/dev/null
echo "EVAL_C1 DONE"
