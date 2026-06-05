"""train_sft.py — minimal LoRA SFT for Qwen3.5-4B on our recovery jsonl (discussion-004 #23).

Consumes build_c1.py / build_b.py rows:
  { messages:[...], label_turn_indices:[...], ... }
Loss is computed ONLY on the listed label turns (the recovery assistant turns), NOT on the
failed-attempt turns or any input/tool tokens. Masking uses incremental chat-template
rendering (the template has reasoning_content->{<think>} and qwen3_xml tool_calls; the
{% generation %} mask path is unreliable here, and we need per-TURN selection anyway).

Renders match the served inference format exactly (run_qwen35_server.sh / qwen3_xml), so the
LoRA learns to emit <think>...</think> + content + <tool_call>...; tool_calls.arguments is
parsed from JSON string -> dict for the template.

Env: identity-bias conda (torch 2.11 + transformers + peft installed --no-deps).
Usage:
  CUDA_VISIBLE_DEVICES=0 python train_sft.py --data data/c1/poc.jsonl \
      --output runs/c1_poc --epochs 3 --lr 1e-4
  add --smoke to only tokenize + report (no training).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import torch

# Assembled dir: config/tokenizer (/hf/hub/hub/...) + weight shards/index (/hf/hub/...)
# symlinked together (the two HF caches were each incomplete). See run notes.
MODEL_DEFAULT = "/data/juny116/qwen35_4b_train"


def _dictify(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chat template wants tool_calls.arguments as a mapping, not a JSON string."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("tool_calls"):
            tcs = []
            for tc in m["tool_calls"]:
                f = dict(tc.get("function") or {})
                a = f.get("arguments")
                if isinstance(a, str):
                    try:
                        f["arguments"] = json.loads(a)
                    except Exception:
                        f["arguments"] = {"_raw": a}
                tcs.append({"type": "function", "function": f})
            m["tool_calls"] = tcs
        out.append(m)
    return out


def _ids(tok, messages, add_gen):
    # transformers 5.x apply_chat_template(tokenize=True) returns an Encoding, not a list;
    # render to string then tokenize (boundaries are special tokens, so prefixes are clean).
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_gen)
    return tok(text, add_special_tokens=False)["input_ids"]


def build_example(tok, row: Dict[str, Any], max_len: int) -> Dict[str, Any] | None:
    """input_ids + labels (-100 except on the recovery label turns)."""
    messages = _dictify(row["messages"])
    label_idx = set(row["label_turn_indices"])

    full_ids = _ids(tok, messages, False)
    labels = [-100] * len(full_ids)

    for t in sorted(label_idx):
        # prefix up to (not incl.) turn t, WITH the assistant generation header
        prefix = _ids(tok, messages[:t], True)
        upto = _ids(tok, messages[:t + 1], False)
        if full_ids[:len(prefix)] != prefix or upto != full_ids[:len(upto)]:
            # tokenization boundary mismatch (rare) -> skip this turn's loss safely
            continue
        for j in range(len(prefix), len(upto)):
            labels[j] = full_ids[j]

    if all(l == -100 for l in labels):
        return None
    if len(full_ids) > max_len:                 # left-truncate keeps the recovery (it's at the end)
        full_ids = full_ids[-max_len:]
        labels = labels[-max_len:]
    return {"input_ids": full_ids, "labels": labels, "attention_mask": [1] * len(full_ids)}


class JsonlSFT(torch.utils.data.Dataset):
    def __init__(self, tok, path: str, max_len: int):
        self.ex = []
        n_skip = 0
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            e = build_example(tok, json.loads(line), max_len)
            if e is None:
                n_skip += 1
            else:
                self.ex.append(e)
        print(f"[data] {len(self.ex)} examples ({n_skip} skipped) from {path}")

    def __len__(self):
        return len(self.ex)

    def __getitem__(self, i):
        return self.ex[i]


def collate(batch, pad_id):
    maxlen = max(len(b["input_ids"]) for b in batch)
    def pad(x, v):
        return [row + [v] * (maxlen - len(row)) for row in x]
    return {
        "input_ids": torch.tensor(pad([b["input_ids"] for b in batch], pad_id)),
        "labels": torch.tensor(pad([b["labels"] for b in batch], -100)),
        "attention_mask": torch.tensor(pad([b["attention_mask"] for b in batch], 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--output", default="runs/sft")
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-len", type=int, default=8192)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--smoke", action="store_true", help="tokenize + report only, no training")
    args = ap.parse_args()

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    ds = JsonlSFT(tok, args.data, args.max_len)
    if len(ds) == 0:
        raise SystemExit("no usable examples")
    # report label coverage
    tot = sum(len(e["input_ids"]) for e in ds.ex)
    lab = sum(sum(1 for l in e["labels"] if l != -100) for e in ds.ex)
    print(f"[data] total tokens={tot}  label tokens={lab} ({100*lab/tot:.1f}%)")
    if args.smoke:
        e = ds.ex[0]
        lbl = tok.decode([l for l in e["labels"] if l != -100])
        print("[smoke] first example label (decoded, first 300 chars):")
        print(lbl[:300])
        return

    from transformers import AutoModelForCausalLM, Trainer, TrainingArguments
    from peft import LoraConfig, get_peft_model

    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, trust_remote_code=True, attn_implementation="eager",
    )
    model.config.use_cache = False
    lora = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    targs = TrainingArguments(
        output_dir=args.output, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size, gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr, lr_scheduler_type="cosine", warmup_ratio=0.05,
        logging_steps=1, save_strategy="epoch", bf16=True, gradient_checkpointing=True,
        report_to=[], remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model, args=targs, train_dataset=ds,
        data_collator=lambda b: collate(b, tok.pad_token_id),
    )
    trainer.train()
    model.save_pretrained(args.output)
    tok.save_pretrained(args.output)
    print(f"[done] adapter saved -> {args.output}")


if __name__ == "__main__":
    main()
