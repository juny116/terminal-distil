"""build_b.py — B-arm SFT rows from scripted teacher-recovery trajectories.
B has NO hint message; split at the first teacher_ tool_call. label = teacher turns."""
import json, sys, glob
from pathlib import Path
import build_c1

def build_b_row(job, task, action_only=False):
    tj = glob.glob(str(Path(job)/"**"/"trajectory.json"), recursive=True)[0]
    conv = json.loads(Path(tj).read_text())["conversation"]
    # first teacher turn = first assistant with tool_call id starting 'teacher_' or 'tc_done'
    split = len(conv)
    for i,m in enumerate(conv):
        if m.get("role")=="assistant":
            ids=[tc.get("id","") for tc in (m.get("tool_calls") or [])]
            if any(x.startswith("teacher_") for x in ids):
                split=i; break
    prefix, recovery = conv[:split], conv[split:]
    messages, label_idx = [], []
    for m in prefix: messages.append(build_c1._strip_input_turn(m))
    for m in recovery:
        if m.get("role")=="assistant":
            label_idx.append(len(messages)); messages.append(build_c1._label_turn(m, action_only))
        else: messages.append(build_c1._strip_input_turn(m))
    return {"task":task,"arm":"B-action-only" if action_only else "B",
            "n_label_turns":len(label_idx),"label_turn_indices":label_idx,"messages":messages}

if __name__=="__main__":
    out=Path(sys.argv[3]); out.parent.mkdir(parents=True,exist_ok=True)
    row=build_b_row(sys.argv[1], sys.argv[2])
    with out.open("a") as f: f.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(f"B row {sys.argv[2]} label_turns={row['n_label_turns']} msgs={len(row['messages'])}")
