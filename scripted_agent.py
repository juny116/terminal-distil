"""scripted_agent.py — ScriptedBashAgent for arm B (teacher recovery, Claude-as-teacher).

B = teacher authors the recovery from the same failure prefix. Without a teacher API, the
teacher is Claude: we author the recovery as a list of {reasoning, command} steps, replay the
student's failure prefix into a fresh env, then EXECUTE the teacher's commands (getting REAL
observations) and let the verifier score it. The resulting trajectory = teacher-authored
recovery (teacher reasoning + actions + real env observations), the B training signal.

Reuses ResumeBashAgent's prefix seeding + replay. Steps come from B_SCRIPT_FILE:
  {"steps": [{"reasoning": "...", "command": "..."}, ...]}  # final task_complete auto-added
No hint message is injected (the recovery IS the teacher's, not a hint to the student).
"""
import json, os
from pathlib import Path
from typing import Any, Dict, List

from recovery_agent import ResumeBashAgent


class ScriptedBashAgent(ResumeBashAgent):
    @staticmethod
    def name() -> str:
        return "bash-agent"

    async def run(self, instruction, environment, context) -> None:
        prefix_file = os.environ["STEP0_PREFIX_FILE"]
        script_file = os.environ["B_SCRIPT_FILE"]
        prefix = json.loads(Path(prefix_file).read_text())
        steps = json.loads(Path(script_file).read_text())["steps"]

        self._conversation_history = list(prefix["conversation_prefix"])
        self._total_input_tokens = self._total_output_tokens = 0
        self._step_log = []
        self._n_model_responses = self._n_responses_with_tool_call = 0
        self._n_empty_tool_call_stops = self._n_invalid_arguments_json = 0

        try:
            for cmd in prefix.get("replay_commands", []):
                try:
                    await environment.exec(command=cmd, timeout_sec=120)
                except Exception as e:
                    self.logger.warning(f"replay failed {cmd[:50]!r}: {e}")

            for i, step in enumerate(steps):
                tc_id = f"teacher_{i}"
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": step.get("reasoning", ""),
                    "tool_calls": [{
                        "id": tc_id, "type": "function",
                        "function": {"name": "bash",
                                     "arguments": json.dumps({"command": step["command"]})},
                    }],
                }
                self._conversation_history.append(assistant_msg)
                self._n_model_responses += 1
                self._n_responses_with_tool_call += 1
                await self._execute_commands([(tc_id, step["command"])], environment)

            # mark complete
            self._conversation_history.append({
                "role": "assistant", "content": "",
                "tool_calls": [{"id": "tc_done", "type": "function",
                                "function": {"name": "task_complete", "arguments": "{}"}}],
            })
            self._conversation_history.append({
                "role": "tool", "tool_call_id": "tc_done", "content": "Task marked as complete."})
        finally:
            context.n_input_tokens = self._total_input_tokens
            context.n_output_tokens = self._total_output_tokens
            self._save_trajectory(prefix.get("task_name", ""))
