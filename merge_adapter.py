"""merge_adapter.py — merge a LoRA adapter into the base Qwen3.5-4B and save a full model
dir that vLLM can serve like the base. Env: identity-bias conda.

Usage: python merge_adapter.py runs/c1_all /data/juny116/terminal-distil/merged/c1_all
"""
import sys, shutil
from pathlib import Path
import torch

BASE = "/data/juny116/qwen35_4b_train"


def main():
    adapter, out = sys.argv[1], sys.argv[2]
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    print(f"[merge] base={BASE} adapter={adapter} -> {out}")
    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, trust_remote_code=True)
    model = PeftModel.from_pretrained(model, adapter)
    model = model.merge_and_unload()
    Path(out).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out, safe_serialization=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    tok.save_pretrained(out)
    # copy chat template if present as a separate file
    for f in ["chat_template.jinja"]:
        src = Path(BASE) / f
        if src.exists():
            shutil.copy(str(src), str(Path(out) / f))
    print(f"[merge] done -> {out}")


if __name__ == "__main__":
    main()
