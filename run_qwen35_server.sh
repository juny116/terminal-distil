#!/usr/bin/env bash
# Serve Qwen3.5-4B (student model) for terminal-distil.
# Adapted from identity-bias/run_qwen35.sh. Key diffs: GPU 6,7 (TP=2), port 8001
# (8000 is used by identity-bias). thinking is toggled per-REQUEST via
# chat_template_kwargs={"enable_thinking": False}; serving keeps the qwen3
# reasoning-parser so both modes work.
#
# NATIVE TOOL-CALLING (discussion-002): the student agent now uses the OpenAI
# `tools=` API (like gpt_agent.py) instead of hand-rolled XML parsing. That needs
# --enable-auto-tool-choice + a --tool-call-parser.
# VERIFIED 6/3: with tools passed natively, Qwen3.5's chat template makes the model
# emit the XML function/parameter format:
#   <tool_call><function=bash><parameter=command>...</parameter></function></tool_call>
# (NOT the Hermes JSON it freelances when tools are only described in the prompt).
# So the matching parser is `qwen3_xml`. hermes left no tool_calls — confirmed wrong.
set -euo pipefail

VLLM=/home/juny116/anaconda3/envs/identity-bias/bin/vllm

# System gcc is 13.x but CUDA 12.1 + flashinfer JIT only support gcc<=12 (and g++-12
# isn't installed). The only runtime JIT that fails is the flashinfer sampler, so we
# disable it and fall back to the native sampler (no compilation needed).
export VLLM_USE_FLASHINFER_SAMPLER=0

CUDA_VISIBLE_DEVICES=6,7 "$VLLM" serve Qwen/Qwen3.5-4B \
    --download-dir /hf/hub \
    --host 0.0.0.0 --port 8001 \
    --tensor-parallel-size 2 \
    --max-model-len 120000 \
    --gpu-memory-utilization 0.8 \
    --language-model-only \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_xml \
    --enable-prefix-caching
# NOTE: --reasoning-parser qwen3 REMOVED (2026-06-04). With thinking ON, Qwen3.5
# emits <think>...</think>, but the qwen3 reasoning parser silently DROPS it
# (reasoning_content comes back empty -> reasoning lost). For arm C we must keep the
# reasoning (train on failure -> reasoning -> action), so we serve without a reasoning
# parser and split <think> ourselves in eval_agent.py. Harmless for thinking-OFF (no
# <think> emitted). Tool calling (qwen3_xml) is independent and still works.
