"""Resume-from-failure-prefix agent for the hint PoC / recovery_eval (P4).

Lets us measure REAL recovery (reward 0 -> ?) from a student's own failure state:
in a fresh task env we replay the executed commands up to the earliest-critical
error (to reconstruct state), seed the model's history with the original failure
prefix, optionally inject a hint, then let the student continue. Harbor's verifier
then scores the final env state.

Usage (via harbor, one task):
    STEP0_PREFIX_FILE=/path/to/prefix.json \
    MODEL_NAME=Qwen/Qwen3.5-4B MODEL_ENDPOINT=http://172.17.0.1:8001/v1 \
    harbor run -p <env> --agent-import-path 'recovery_agent:ResumeBashAgent' \
        -e docker -i <task_name> -n 1 -o <out>

prefix.json (build with prepare_prefix below):
    {
      "task_name": ...,
      "conversation_prefix": [ ...messages up to & incl. the ECE failure obs... ],
      "replay_commands": [ "cmd1", "cmd2", ... ],   # executed bash, in order
      "hint": "..." | null,                          # arm-specific, injected as user msg
      "arm": "raw-retry|base-framing|teacher|oracle"
    }

Caveat: replay reconstructs env state by re-executing the prefix's commands.
Deterministic tasks reconstruct faithfully; commands with external/nondeterministic
effects may not. recovery_eval should flag tasks whose replay diverges.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from eval_agent import BashAgent

# A common minimal problem-framing shared by every framing-controlled arm
# (discussion-003 #5). Deliberately weak: completion-uncertainty + recheck only,
# NO diagnosis / action-class / command / path / expected answer.
COMMON_FRAMING = (
    "Before deciding the task is complete, verify the latest observation and "
    "continue if more work is needed."
)


class ResumeBashAgent(BashAgent):
    """Continue a student rollout from a saved failure prefix, with an optional hint."""

    @staticmethod
    def name() -> str:
        return "bash-agent"  # same eval key as the base student

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        prefix_file = os.environ.get("STEP0_PREFIX_FILE")
        if not prefix_file:
            raise RuntimeError("STEP0_PREFIX_FILE not set for ResumeBashAgent")
        prefix = json.loads(Path(prefix_file).read_text())

        # Seed history with the original failure prefix (system + task + the
        # assistant/tool turns up to the ECE failure observation).
        self._conversation_history = list(prefix["conversation_prefix"])
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._step_log = []
        self._n_model_responses = 0
        self._n_responses_with_tool_call = 0
        self._n_empty_tool_call_stops = 0
        self._n_invalid_arguments_json = 0

        try:
            # Reconstruct env state by replaying the executed commands (no model calls).
            for cmd in prefix.get("replay_commands", []):
                try:
                    await environment.exec(command=cmd, timeout_sec=120)
                except Exception as e:  # replay best-effort; recovery_eval flags divergence
                    self.logger.warning(f"replay failed for {cmd[:60]!r}: {e}")

            # Inject the arm-specific hint as a user message (None for raw-retry).
            hint = prefix.get("hint")
            if hint:
                self._conversation_history.append({"role": "user", "content": hint})

            await self._resume_loop(environment)
        finally:
            context.n_input_tokens = self._total_input_tokens
            context.n_output_tokens = self._total_output_tokens
            self._save_trajectory(prefix.get("task_name", ""))

    async def _resume_loop(self, environment: BaseEnvironment) -> None:
        """Like _run_conversation_loop but history is already seeded (no instruction append)."""
        start = sum(1 for m in self._conversation_history if m.get("role") == "assistant")
        for step in range(self._max_episodes):
            episode = start + step
            episode_dir = self.logs_dir / f"episode-{episode}"
            episode_dir.mkdir(parents=True, exist_ok=True)

            commands, assistant_msg = self._call_model(episode_dir)
            self._conversation_history.append(assistant_msg)

            bash_commands = [(tc_id, cmd) for name, tc_id, cmd in commands if name == "bash"]
            self._step_log.append({
                "episode": episode,
                "n_commands": len(bash_commands),
                "called_task_complete": any(n == "task_complete" for n, _, __ in commands),
                "had_tool_call": bool(commands),
                "resumed": True,
            })

            if not commands:
                self._n_empty_tool_call_stops += 1
                self.logger.info(f"No tool calls (episode {episode}), stopping")
                break
            if any(name == "task_complete" for name, _, __ in commands):
                for name, tool_call_id, _ in commands:
                    self._conversation_history.append({
                        "role": "tool", "tool_call_id": tool_call_id,
                        "content": "Task marked as complete.",
                    })
                break
            await self._execute_commands(bash_commands, environment)


# ── prefix preparation (offline) ────────────────────────────────────────────────

def _bash_of(assistant_msg: Dict[str, Any]) -> List[str]:
    out = []
    for tc in assistant_msg.get("tool_calls") or []:
        f = tc.get("function") or {}
        if f.get("name") == "bash":
            try:
                cmd = json.loads(f.get("arguments") or "{}").get("command", "")
            except json.JSONDecodeError:
                continue
            if cmd:
                out.append(cmd)
    return out


def prepare_prefix(
    trajectory_path: str,
    ece_episode: int,
    hint: str | None,
    arm: str,
    task_name: str,
) -> Dict[str, Any]:
    """Build a prefix.json dict: cut history right after the ECE episode's tool
    result, collect the bash commands to replay (episodes 0..ece_episode)."""
    t = json.loads(Path(trajectory_path).read_text())
    conv = t["conversation"]

    # Cut right before the (ece_episode+1)-th assistant message.
    a = 0
    cut = len(conv)
    for i, m in enumerate(conv):
        if m.get("role") == "assistant":
            if a == ece_episode + 1:
                cut = i
                break
            a += 1
    conversation_prefix = conv[:cut]
    replay_commands = []
    for m in conversation_prefix:
        if m.get("role") == "assistant":
            replay_commands.extend(_bash_of(m))

    return {
        "task_name": task_name,
        "arm": arm,
        "hint": hint,
        "ece_episode": ece_episode,
        "replay_commands": replay_commands,
        "conversation_prefix": conversation_prefix,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Prepare a resume prefix.json for one arm.")
    ap.add_argument("trajectory_path")
    ap.add_argument("--ece", type=int, required=True, help="earliest-critical-error episode index")
    ap.add_argument("--task-name", required=True)
    ap.add_argument("--arm", required=True, choices=["raw-retry", "base-framing", "teacher", "oracle"])
    ap.add_argument("--hint", default=None, help="arm-specific extra hint (on top of framing)")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    # Framing-controlled arms (discussion-003 #5): raw-retry gets no framing;
    # every other arm shares COMMON_FRAMING, with arm-specific info appended.
    if args.arm == "raw-retry":
        hint = None
    elif args.arm == "base-framing":
        hint = COMMON_FRAMING
    else:
        hint = COMMON_FRAMING + (" " + args.hint if args.hint else "")

    prefix = prepare_prefix(args.trajectory_path, args.ece, hint, args.arm, args.task_name)
    Path(args.output).write_text(json.dumps(prefix, ensure_ascii=False, indent=2))
    print(f"arm={args.arm}  replay_cmds={len(prefix['replay_commands'])}  "
          f"prefix_msgs={len(prefix['conversation_prefix'])}  hint={hint!r}")
    print(f"wrote {args.output}")
