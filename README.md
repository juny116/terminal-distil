# terminal-distil

TermiGen-style trajectory collection and SFT dataset builder for terminal agents.

Pipeline:
1. Collect ReAct-style bash trajectories on Harbor environments using a teacher LLM (e.g. GPT-5.4).
2. Inject realistic errors per the TermiGen paper (Bernoulli intent sampling, 5 failure categories, Generator-Critic).
3. Filter successful trajectories, dedupe per task, prefer those containing recovery from injected errors.
4. Output an OpenAI-format JSONL dataset suitable for SFT (e.g. via `tokenizer.apply_chat_template`).

Reference: [TermiGen paper (arXiv:2602.07274)](https://arxiv.org/abs/2602.07274), [terminal-bench-env](https://github.com/ucsb-mlsec/terminal-bench-env).

## Requirements

- Python 3.12
- Docker + Compose v2
- `pip install harbor openai tiktoken`
- Environment variables: `OPENAI_API_KEY`, optionally `MODEL_NAME`

## Layout

```
gpt_agent.py        Harbor BaseAgent — Generator-Critic with native OpenAI tool calling.
run_pilot.sh        Small-scale pilot on N tasks.
run_full.sh         Full collection across all environments_harbor tasks.
run_phase.sh        Run a specific list of tasks (resume / retry).
select_tasks.py     Compute per-task status (unattempted / failed) from existing job results.
build_dataset.py    Merge trajectory + result, dedupe by task, output JSONL.
analyze_cost.py     Estimate full-run cost from a pilot.
```

## Usage

The collection pipeline depends on a clone of [terminal-bench-env](https://github.com/ucsb-mlsec/terminal-bench-env) (provides ~3,500 Harbor task environments).

```bash
# Required: path to the environments_harbor directory from terminal-bench-env
export TASKS_DIR=/path/to/terminal-bench-env/environments_harbor

# Optional: where to write per-trial logs/results (default: ./jobs)
export JOBS_DIR=/path/to/bulk/storage/jobs

# Required: OpenAI API key for the teacher model
export OPENAI_API_KEY=sk-...

# 1. Pilot run (sanity-check + cost estimate)
bash run_pilot.sh gpt-5.4-mini

# 2. Full collection
bash run_full.sh gpt-5.4-mini

# 3. Retry failures
python select_tasks.py jobs/ --mode failed --output /tmp/failed.txt
bash run_phase.sh gpt-5.4-mini /tmp/failed.txt phaseB 4

# 4. Build SFT dataset
python build_dataset.py jobs/ --output data/sft.jsonl
```

## Notes

- Trajectories and intermediate job artifacts are not committed (`.gitignore`); they can be large and may contain task-specific content.
- `gpt_agent.py` uses OpenAI native tool calling (`tools=[bash, task_complete]`, `tool_choice="required"`) for reliable command extraction. The trajectory is saved in OpenAI message format so a Qwen-family tokenizer's `apply_chat_template` handles the format conversion at training time.
