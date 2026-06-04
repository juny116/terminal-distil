"""Student rollout / eval agent for terminal-distil.

discussion-002: rewritten to use NATIVE OpenAI tool-calling (like gpt_agent.py)
instead of the hand-rolled XML `<tool_call>` regex parser. The 6/3 smoke scored
5/5 = 0.0 not because of length but because Qwen3.5-4B does not reliably emit the
`{"name":"bash","arguments":{...}}` JSON the old parser required — it emits the
chat-template's native tool format, which the regex dropped to zero commands.

Served by run_qwen35_server.sh with `--enable-auto-tool-choice
--tool-call-parser qwen3_xml` (verified: vLLM returns clean message.tool_calls).

thinking is OFF by default (project decision: recovery must surface as explicit
bash commands, not hidden <think> tokens). Toggle QWEN_ENABLE_THINKING=1 for the
secondary study.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from agent_tools import TOOLS, SYSTEM_PROMPT


class BashAgent(BaseAgent):
    """Minimal ReAct-style terminal agent using native tool calling.

    Shares the bash / task_complete tool schema and system prompt with the
    teacher (gpt_agent.py) via agent_tools, so student rollouts and injected
    teacher trajectories present the same action surface for Step 1's ①-vs-②½
    comparison and Step 0+'s first-corrective-command keying.
    """

    @staticmethod
    def name() -> str:
        return "bash-agent"

    def version(self) -> str:
        return "2.0.0"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        model_endpoint: str = "http://172.17.0.1:8001/v1",
        max_episodes: int = 1000,
        temperature: float = 0.6,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.model_endpoint = os.getenv("MODEL_ENDPOINT", model_endpoint)
        self._model_name_for_api = os.getenv("MODEL_NAME", model_name or "")
        self.temperature = temperature
        # Steps (agent episodes): give it as much room as possible; override via env.
        self._max_episodes = int(os.getenv("QWEN_MAX_EPISODES", str(max_episodes)))

        self._enable_thinking = os.getenv("QWEN_ENABLE_THINKING", "0") == "1"
        # Max generation length: keep it large so responses are never truncated
        # mid-tool-call. Server max-model-len is 120k; default leaves headroom for
        # accumulated history. Override per-run via QWEN_MAX_TOKENS.
        default_max_tokens = 49152 if self._enable_thinking else 16384
        self._max_tokens = int(os.getenv("QWEN_MAX_TOKENS", str(default_max_tokens)))

        # Conversation + accounting state
        self._conversation_history: List[Dict[str, Any]] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._step_log: List[Dict] = []
        # Guard metrics (discussion-002): for Step 0+ the smoke health signal is the
        # native tool-call rate, NOT reward. A parser/format mismatch must show up
        # here instead of masquerading as a student "failure".
        self._n_model_responses = 0
        self._n_responses_with_tool_call = 0
        self._n_empty_tool_call_stops = 0
        self._n_invalid_arguments_json = 0

        self.client = OpenAI(api_key="EMPTY", base_url=self.model_endpoint)

    async def setup(self, environment: BaseEnvironment) -> None:
        pass

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        self._conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._step_log = []
        self._n_model_responses = 0
        self._n_responses_with_tool_call = 0
        self._n_empty_tool_call_stops = 0
        self._n_invalid_arguments_json = 0

        try:
            await self._run_conversation_loop(instruction, environment)
        finally:
            context.n_input_tokens = self._total_input_tokens
            context.n_output_tokens = self._total_output_tokens
            self._save_trajectory(instruction)

    async def _run_conversation_loop(
        self, instruction: str, environment: BaseEnvironment
    ) -> None:
        for episode in range(self._max_episodes):
            episode_dir = self.logs_dir / f"episode-{episode}"
            episode_dir.mkdir(parents=True, exist_ok=True)

            if episode == 0:
                self._conversation_history.append({"role": "user", "content": instruction})

            commands, assistant_msg = self._call_model(episode_dir)
            self._conversation_history.append(assistant_msg)

            bash_commands = [(tc_id, cmd) for name, tc_id, cmd in commands if name == "bash"]
            self._step_log.append({
                "episode": episode,
                "n_commands": len(bash_commands),
                "called_task_complete": any(n == "task_complete" for n, _, __ in commands),
                "had_tool_call": bool(commands),
            })

            # No tool call at all → the model stopped acting. Record and break.
            if not commands:
                self._n_empty_tool_call_stops += 1
                self.logger.info(f"No tool calls proposed by agent (episode {episode}), stopping")
                break

            # Explicit completion via the shared task_complete tool.
            if any(name == "task_complete" for name, _, __ in commands):
                self.logger.info(f"task_complete called at episode {episode}, stopping")
                for name, tool_call_id, _ in commands:
                    self._conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": "Task marked as complete.",
                    })
                break

            await self._execute_commands(bash_commands, environment)

    def _call_model(self, episode_dir: Path) -> Tuple[List[Tuple[str, str, str]], Dict[str, Any]]:
        """One generator call with native tool calling.

        Returns (commands, assistant_message) where commands is a list of
        (tool_name, tool_call_id, command_str). command_str is "" for
        task_complete.
        """
        response = self.client.chat.completions.create(
            model=self._model_name_for_api,
            messages=self._conversation_history,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=self._max_tokens,
            temperature=self.temperature,
            extra_body={"chat_template_kwargs": {"enable_thinking": self._enable_thinking}},
        )

        if response.usage:
            self._total_input_tokens += response.usage.prompt_tokens
            self._total_output_tokens += response.usage.completion_tokens

        self._n_model_responses += 1
        msg = response.choices[0].message

        # Capture reasoning when thinking is ON. Qwen3.5 emits <think>...</think>;
        # vLLM's --reasoning-parser qwen3 silently DROPS it (empty reasoning_content),
        # so we serve WITHOUT that parser and split <think> ourselves here. Prefer a
        # populated reasoning_content if present; else split the content. The reasoning
        # is kept in the trajectory so arm C can train on (failure -> reasoning -> action).
        content = msg.content
        reasoning = getattr(msg, "reasoning_content", None) or None
        if reasoning is None and isinstance(content, str) and "</think>" in content:
            head, _, tail = content.partition("</think>")
            reasoning = head.replace("<think>", "", 1).strip()
            content = tail.strip()

        # Store reasoning under "reasoning_content": vLLM IGNORES this field on INPUT
        # (verified: +0 prompt tokens), so prior turns' thinking is NOT fed back into
        # context -- standard reasoning-agent behavior (per-turn scratchpad). The
        # thinking is still saved in the trajectory for training arm C on
        # (failure -> reasoning -> action). Using the key "reasoning" instead would
        # make vLLM RENDER it back into the prompt (+thinking tokens every turn).
        assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content}
        if reasoning:
            assistant_msg["reasoning_content"] = reasoning
        commands: List[Tuple[str, str, str]] = []

        if msg.tool_calls:
            self._n_responses_with_tool_call += 1
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            for tc in msg.tool_calls:
                if tc.function.name == "bash":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        self._n_invalid_arguments_json += 1
                        continue
                    cmd = args.get("command", "")
                    if cmd:
                        commands.append(("bash", tc.id, cmd))
                elif tc.function.name == "task_complete":
                    commands.append(("task_complete", tc.id, ""))

        (episode_dir / "response.json").write_text(
            json.dumps(
                {"reasoning": reasoning, "content": content,
                 "tool_calls": assistant_msg.get("tool_calls")},
                indent=2,
                ensure_ascii=False,
            )
        )
        return commands, assistant_msg

    async def _execute_commands(
        self,
        commands: List[Tuple[str, str]],  # (tool_call_id, command_str)
        environment: BaseEnvironment,
    ) -> None:
        for tool_call_id, command in commands:
            try:
                self.logger.info(f"Executing command: {command}")
                result = await environment.exec(command=command, timeout_sec=120)
                parts = []
                if result.stdout:
                    parts.append(f"STDOUT:\n{result.stdout}")
                if result.stderr:
                    stderr_lines = [
                        l for l in result.stderr.splitlines()
                        if "cannot set terminal process group" not in l
                        and "no job control in this shell" not in l
                    ]
                    if stderr_lines:
                        parts.append(f"STDERR:\n{chr(10).join(stderr_lines)}")
                parts.append(f"EXIT CODE: {result.return_code}")
                output = "\n".join(parts)
            except TimeoutError:
                self.logger.warning(f"Command timed out: {command}")
                output = "Command timed out after 120s"
            except Exception as e:
                self.logger.error(f"Error executing command: {e}")
                output = f"Error executing command: {e}"

            # Tool result message is required by the OpenAI tool-calling protocol.
            self._conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": self._limit_output_length(output),
            })

    def _save_trajectory(self, instruction: str) -> None:
        rate = (
            self._n_responses_with_tool_call / self._n_model_responses
            if self._n_model_responses else 0.0
        )
        summary = {
            "model": self._model_name_for_api,
            "role": "student",
            "enable_thinking": self._enable_thinking,
            "max_tokens": self._max_tokens,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "n_turns": sum(1 for m in self._conversation_history if m["role"] == "assistant"),
            # Guard metrics — Step 0+ health, not reward.
            "tool_call_stats": {
                "n_model_responses": self._n_model_responses,
                "n_responses_with_tool_call": self._n_responses_with_tool_call,
                "parsed_tool_call_rate": rate,
                "n_empty_tool_call_stops": self._n_empty_tool_call_stops,
                "n_invalid_arguments_json": self._n_invalid_arguments_json,
            },
            "step_log": self._step_log,
            "conversation": self._conversation_history,
        }
        (self.logs_dir / "trajectory.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False)
        )

    def _limit_output_length(self, output: str, max_bytes: int = 10000) -> str:
        if len(output.encode("utf-8")) <= max_bytes:
            return output
        half = max_bytes // 2
        b = output.encode("utf-8")
        first = b[:half].decode("utf-8", errors="ignore")
        last = b[-half:].decode("utf-8", errors="ignore")
        omitted = len(b) - len(first.encode()) - len(last.encode())
        return f"{first}\n[... {omitted} bytes omitted ...]\n{last}"
