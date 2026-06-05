#!/usr/bin/env bash
export VLLM_USE_FLASHINFER_SAMPLER=0 CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1
exec /home/juny116/anaconda3/envs/identity-bias/bin/vllm serve /data/juny116/qwen35_4b_train \
  --served-model-name base --enable-lora --lora-modules c1=/data/juny116/terminal-distil/runs/c1_all \
  --max-lora-rank 16 --host 0.0.0.0 --port 8002 --tensor-parallel-size 1 --max-model-len 120000 \
  --gpu-memory-utilization 0.85 --language-model-only \
  --enable-auto-tool-choice --tool-call-parser qwen3_xml --enable-prefix-caching
