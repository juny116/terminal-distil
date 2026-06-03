"""Shared tool schema + system prompt for teacher (gpt_agent) and student
(eval_agent) terminal agents.

discussion-002 (D2): for a fair arm-① (injected) vs arm-②½ (student-mined)
comparison, both agents MUST present the same action surface — identical bash /
task_complete tool schema, identical system prompt, identical completion signal
(the `task_complete` tool call, not ad-hoc string matching). Keeping these here,
imported by both agents, prevents them from drifting apart.
"""

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
