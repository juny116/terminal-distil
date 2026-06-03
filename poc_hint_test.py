"""Quick PoC (no teacher API — Claude supplies the hints) of the P4 3-arm hint
mechanism on a REAL student failure.

Case: visibility_attribute_export_medium. The student had a correct library after
episode 8-10, then ran a destructive `make clean && make ...` at ep15 that FAILED
(exit 1), deleting libmath.so, and called task_complete without checking the exit
code -> verification_failure (recoverable). ECE = ep15.

We rebuild the conversation prefix up to (and including) the ep15 failure
observation, then sample the student's NEXT action under three arms:
  A no-hint     : continue as-is
  B teacher-hint: diagnosis only (no command)         <- Claude as teacher
  C oracle-hint : recovery action class only (no cmd) <- (make, run)

Success signal = does the next action become a corrective rebuild (make) instead
of task_complete / ignoring the failure. No env/verifier here — this isolates the
behavioral effect of the hint.
"""
import json
import sys
from openai import OpenAI

from agent_tools import TOOLS

TRAJ = ("jobs/student_harvest_170814/student_harvest/"
        "visibility_attribute_export_medi__hNxbmQ5/agent/trajectory.json")

TEACHER_HINT = (
    "Before finishing, double-check that your last command actually succeeded. "
    "One of your recent commands returned a non-zero exit code, so the workspace "
    "may no longer be in the state you expect. Verify the build artifact is "
    "present and correct before declaring the task complete."
)
ORACLE_HINT = (
    "The next action you should take is a build/run action (re-run the build), "
    "then verify its result."
)

client = OpenAI(api_key="EMPTY", base_url="http://localhost:8001/v1")


def build_prefix():
    t = json.load(open(TRAJ))
    conv = t["conversation"]
    # Find the ep16 assistant message (the 17th assistant) and cut right before it,
    # so the prefix ends with ep15's failing tool result (EXIT CODE: 1).
    a = 0
    cut = len(conv)
    for i, m in enumerate(conv):
        if m.get("role") == "assistant":
            if a == 16:
                cut = i
                break
            a += 1
    return conv[:cut]


def first_action(messages):
    r = client.chat.completions.create(
        model="Qwen/Qwen3.5-4B", messages=messages, tools=TOOLS,
        tool_choice="auto", max_tokens=4096, temperature=0.6,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    msg = r.choices[0].message
    if not msg.tool_calls:
        return ("none", (msg.content or "")[:80])
    tc = msg.tool_calls[0]
    if tc.function.name == "task_complete":
        return ("task_complete", "")
    try:
        cmd = json.loads(tc.function.arguments).get("command", "")
    except Exception:
        cmd = "?"
    return ("bash", cmd[:120])


def run_arm(name, extra_msgs, n=4):
    prefix = build_prefix()
    print(f"\n=== ARM {name} ===")
    for s in range(n):
        kind, detail = first_action(prefix + extra_msgs)
        print(f"  sample {s+1}: [{kind}] {detail}")


if __name__ == "__main__":
    print("Prefix ends at ep15 failure (EXIT CODE: 1). Original next action was: "
          "cat solution.json -> task_complete (ignored the failure).")
    run_arm("A  no-hint", [])
    run_arm("B  teacher-hint (diagnosis only)",
            [{"role": "user", "content": TEACHER_HINT}])
    run_arm("C  oracle-hint (action class only)",
            [{"role": "user", "content": ORACLE_HINT}])
