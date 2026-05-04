import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


# ── Tool schema ────────────────────────────────────────────────────────────────

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Execute a bash command in the terminal environment.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to execute."}
            },
            "required": ["command"],
        },
    },
}

TASK_COMPLETE_TOOL = {
    "type": "function",
    "function": {
        "name": "task_complete",
        "description": "Call this when the task is fully completed and verified.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Brief summary of what was accomplished."}
            },
            "required": ["summary"],
        },
    },
}

TOOLS = [BASH_TOOL, TASK_COMPLETE_TOOL]

SYSTEM_PROMPT = (
    "You are an expert technical assistant. "
    "Solve the given task by executing bash commands step by step. "
    "Analyze each command's output before proceeding to the next step."
)

ERROR_CATEGORIES = {
    "analysis_error": (
        "Misinterpret the current environment state or data structure. "
        "For example, read a file path wrong, miscount lines, or assume wrong data format."
    ),
    "command_error": (
        "Introduce a syntactic or formatting mistake in the bash command. "
        "For example, use a wrong flag, misspell a command name, or use wrong argument order."
    ),
    "hallucination": (
        "Assume the existence of a tool, file, or service that is not present. "
        "For example, call a non-existent binary or reference a file that doesn't exist."
    ),
    "requirement_violation": (
        "Ignore or violate an explicit task constraint. "
        "For example, overwrite a file that should not be modified, or skip a required step."
    ),
    "verification_failure": (
        "Skip checking the result of a command before proceeding. "
        "For example, assume a command succeeded without checking its exit code or output."
    ),
}

ERROR_INJECT_PROMPT = (
    "IMPORTANT: For your NEXT bash command only, deliberately make a realistic mistake.\n"
    "Error type: {category}\n"
    "Description: {description}\n"
    "The mistake should be subtle and plausible — something a real engineer might do wrong. "
    "Do NOT explain that you are making an error."
)

RECOVERY_PROMPT = (
    "The previous command resulted in an error or unexpected output. "
    "Carefully diagnose what went wrong and generate a corrective action to recover."
)

CRITIC_SYSTEM = (
    "You are evaluating whether a bash command contains a realistic mistake of the specified type. "
    "Reply with JSON only: {\"is_valid\": true/false, \"reason\": \"...\"}"
)


@dataclass
class StepMeta:
    episode: int
    intent: str          # "correct" or "error"
    error_category: Optional[str]
    prev_was_error: bool
    critic_valid: Optional[bool]
    n_commands: int


class GPTAgent(BaseAgent):
    """
    ReAct-style terminal agent with Generator-Critic error injection.
    Uses OpenAI native tool calling for reliable command extraction.

    Architecture follows TermiGen paper (Section 3.3):
      - Bernoulli(epsilon) intent sampling per step
      - 5 failure categories for error injection
      - Critic validates injected errors
      - Recovery prompting after error steps
    """

    @staticmethod
    def name() -> str:
        return "gpt-agent"

    def version(self) -> str:
        return "1.0.0"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        max_episodes: int = 30,
        temperature: float = 0.6,
        error_injection_rate: float = 0.2,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._model_name_for_api = os.getenv("MODEL_NAME", model_name or "gpt-4.1-mini")
        self.temperature = temperature
        self._max_episodes = max_episodes
        self._epsilon = error_injection_rate

        self._conversation_history: List[ChatCompletionMessageParam] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._step_log: List[Dict] = []

        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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

        try:
            await self._run_conversation_loop(instruction, environment)
        finally:
            context.n_input_tokens = self._total_input_tokens
            context.n_output_tokens = self._total_output_tokens
            self._save_trajectory(instruction)

    async def _run_conversation_loop(self, instruction: str, environment: BaseEnvironment) -> None:
        prev_was_error = False

        for episode in range(self._max_episodes):
            episode_dir = self.logs_dir / f"episode-{episode}"
            episode_dir.mkdir(parents=True, exist_ok=True)

            # ── Step 1: Intent sampling ────────────────────────────────────────
            inject_error = (episode > 0) and (random.random() < self._epsilon)
            error_category = random.choice(list(ERROR_CATEGORIES)) if inject_error else None

            # ── Episode 0 only: append task instruction as user message ────────
            # Episodes > 0: tool results already in history — no extra user msg needed
            if episode == 0:
                self._conversation_history.append({"role": "user", "content": instruction})

            # ── Step 2: Generator call ─────────────────────────────────────────
            recovery = prev_was_error and not inject_error
            commands, assistant_msg = self._call_generator(
                episode_dir, inject_error, error_category, recovery=recovery,
            )
            self._conversation_history.append(assistant_msg)

            step_meta: Dict = {
                "episode": episode,
                "intent": "error" if inject_error else "correct",
                "error_category": error_category,
                "prev_was_error": prev_was_error,
                "critic_valid": None,
                "n_commands": len([c for c in commands if c[0] == "bash"]),
            }

            # ── Step 3: Critic validation ──────────────────────────────────────
            bash_commands = [(tc_id, cmd) for name, tc_id, cmd in commands if name == "bash"]
            if inject_error and bash_commands:
                is_valid = self._query_critic(error_category, bash_commands[0][1], episode_dir)
                step_meta["critic_valid"] = is_valid
                if not is_valid:
                    self.logger.info(f"Critic rejected error at episode {episode}, regenerating")
                    self._conversation_history.pop()
                    commands, assistant_msg = self._call_generator(
                        episode_dir, inject_error=False, error_category=None, suffix="_retry"
                    )
                    self._conversation_history.append(assistant_msg)
                    inject_error = False
                    bash_commands = [(tc_id, cmd) for name, tc_id, cmd in commands if name == "bash"]

            self._step_log.append(step_meta)

            if not commands:
                self.logger.info(f"No tool calls at episode {episode}, stopping")
                break

            # ── Check task_complete tool call ─────────────────────────────────
            if any(name == "task_complete" for name, _, __ in commands):
                self.logger.info(f"task_complete called at episode {episode}, stopping")
                for name, tool_call_id, _ in commands:
                    self._conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": "Task marked as complete.",
                    })
                break

            # ── Execute & feed tool results back ──────────────────────────────
            await self._execute_commands(bash_commands, environment)
            prev_was_error = inject_error

    # ── Generator ──────────────────────────────────────────────────────────────

    def _call_generator(
        self,
        episode_dir: Path,
        inject_error: bool,
        error_category: Optional[str],
        recovery: bool = False,
        suffix: str = "",
    ):
        """
        Call LLM with native tool calling.
        Returns (commands, assistant_message).
        Error/recovery hints are one-shot system messages — not stored in history.
        """
        messages = list(self._conversation_history)

        # Inject one-shot hints after the last tool message (not persisted in history)
        if inject_error:
            hint = ERROR_INJECT_PROMPT.format(
                category=error_category,
                description=ERROR_CATEGORIES[error_category],
            )
            messages.append({"role": "system", "content": hint})
        elif recovery:
            messages.append({"role": "system", "content": RECOVERY_PROMPT})

        response = self.client.chat.completions.create(
            model=self._model_name_for_api,
            messages=messages,
            tools=TOOLS,
            tool_choice="required",
            max_completion_tokens=4096,
            temperature=self.temperature,
        )

        if response.usage:
            self._total_input_tokens += response.usage.prompt_tokens
            self._total_output_tokens += response.usage.completion_tokens

        msg = response.choices[0].message

        # Build history-compatible message dict
        assistant_msg: Dict[str, Any] = {"role": "assistant", "content": msg.content}
        commands: List[str] = []

        if msg.tool_calls:
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
                        cmd = args.get("command", "")
                        if cmd:
                            commands.append(("bash", tc.id, cmd))
                    except json.JSONDecodeError:
                        pass
                elif tc.function.name == "task_complete":
                    commands.append(("task_complete", tc.id, ""))

        # Log
        (episode_dir / f"response{suffix}.txt").write_text(
            json.dumps({"content": msg.content, "tool_calls": assistant_msg.get("tool_calls")}, indent=2, ensure_ascii=False)
        )
        return commands, assistant_msg

    # ── Execute commands & return tool result messages ─────────────────────────

    async def _execute_commands(
        self,
        commands: List[tuple],  # List of (tool_call_id, command_str)
        environment: BaseEnvironment,
    ) -> str:
        all_outputs = []

        for tool_call_id, command in commands:
            try:
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
                output = f"Command timed out after 120s"
            except Exception as e:
                output = f"Error executing command: {e}"

            all_outputs.append(output)

            # Append tool result to history (required by OpenAI API for tool calls)
            self._conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": self._limit_output_length(output),
            })

        return "\n\n---\n\n".join(all_outputs)

    # ── Critic ─────────────────────────────────────────────────────────────────

    def _query_critic(self, error_category: str, command: str, episode_dir: Path) -> bool:
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": (
                f"Error type: {error_category}\n"
                f"Generated command: {command}\n\n"
                "Is this a realistic, plausible mistake of the specified type?"
            )},
        ]
        try:
            resp = self.client.chat.completions.create(
                model=self._model_name_for_api,
                messages=messages,
                max_completion_tokens=256,
                temperature=0.0,
            )
            if resp.usage:
                self._total_input_tokens += resp.usage.prompt_tokens
                self._total_output_tokens += resp.usage.completion_tokens
            result = json.loads(resp.choices[0].message.content.strip())
            (episode_dir / "critic.txt").write_text(json.dumps(result, indent=2))
            return bool(result.get("is_valid", True))
        except Exception:
            return True

    # ── Trajectory save ────────────────────────────────────────────────────────

    def _save_trajectory(self, instruction: str) -> None:
        summary = {
            "model": self._model_name_for_api,
            "epsilon": self._epsilon,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "n_turns": sum(1 for m in self._conversation_history if m["role"] == "assistant"),
            "n_error_steps": sum(1 for s in self._step_log if s["intent"] == "error"),
            "n_critic_calls": sum(1 for s in self._step_log if s["critic_valid"] is not None),
            "step_log": self._step_log,
            "conversation": self._conversation_history,
        }
        (self.logs_dir / "trajectory.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False)
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _limit_output_length(self, output: str, max_bytes: int = 10000) -> str:
        if len(output.encode("utf-8")) <= max_bytes:
            return output
        half = max_bytes // 2
        b = output.encode("utf-8")
        first = b[:half].decode("utf-8", errors="ignore")
        last = b[-half:].decode("utf-8", errors="ignore")
        omitted = len(b) - len(first.encode()) - len(last.encode())
        return f"{first}\n[... {omitted} bytes omitted ...]\n{last}"

    def _check_task_completion(self, content: str) -> bool:
        lower = content.lower() if content else ""
        return any(s in lower for s in [
            "task_complete: true", "task complete: true",
            "task is complete", "task completed", "finished the task",
        ])
