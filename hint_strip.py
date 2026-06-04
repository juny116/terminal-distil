"""hint-strip filter for arm C (Ours ②½) — discussion-004 #2/#3 (locked).

C generates the recovery WITH a hint, but the TRAINING DATA must contain only the
student's own recovery — no hint message, and no recovery turn that REFERENCES the
hint ("based on the hint...", "the issue is likely..."). Otherwise the model would
learn to depend on a hint that is absent at test time (N2 hint-leak).

5-step mechanical filter (Codex #2):
  1. Drop the hint message entirely; keep from the assistant turn after the
     failure prefix onward.  (caller-side; `strip_hint_messages` here)
  2. Drop a recovery turn whose assistant *content* references the hint
     (phrase list).
  3. Tool-call-centric: empty/short command-description content passes; long
     natural-language reasoning is conservatively dropped.
  4. Token-overlap: if the hint's salient noun/path/command tokens are
     over-repeated in the recovery CONTENT (not the bash command field), flag.
  5. Final small-LLM judge (hook): binary "does this recovery reference seeing an
     external hint / depend on the hint sentence?" — leak only, NOT quality.

Steps 1-4 are pure/deterministic here. Step 5 is an injectable callable (so this
module needs no model). A turn/transcript is LEAK if any step 2-5 fires.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Step 2: explicit hint-reference phrases in assistant content.
_HINT_REF = re.compile(
    r"\b(hint|clue|teacher|as (mentioned|suggested|noted)|based on (the|your) (hint|suggestion|advice)"
    r"|you (mentioned|suggested|said)|per (the|your) (hint|suggestion)|the (hint|advice) (said|says|told)"
    r"|following (the|your) (hint|suggestion|advice)|as you (pointed out|hinted))\b",
    re.I,
)
# Softer "the issue is likely ..." style that echoes a diagnosis we may have fed.
_DIAG_ECHO = re.compile(r"\bthe (issue|problem|error|bug|cause) (is|was|seems|appears|might be|is likely)\b", re.I)

# Step 3: a content field longer than this many chars is "long NL reasoning".
_LONG_CONTENT_CHARS = 220
# Step 4: overlap threshold (fraction of hint's salient tokens echoed in content).
_OVERLAP_FRAC = 0.5
_STOP = set("the a an of to and or is are be in on for with that this it your you we i "
            "should make sure check that not do does use using run from into then".split())


@dataclass
class TurnVerdict:
    index: int
    leak: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class StripResult:
    clean: bool                         # transcript is clean (no leak) -> usable for training
    turns: List[TurnVerdict] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)  # transcript-level reasons


def _salient_tokens(text: str) -> set:
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]{2,}", (text or "").lower())
    return {t for t in toks if t not in _STOP and not t.isdigit()}


def strip_hint_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Step 1: remove any injected hint message(s). Convention: the hint is a
    user/system message tagged with metadata {"role_tag": "hint"} OR is the last
    user message before the recovery continuation. We drop messages explicitly
    marked as hints; callers should mark them when injecting."""
    return [m for m in messages if m.get("role_tag") != "hint"]


def _content_of(msg: Dict[str, Any]) -> str:
    c = msg.get("content")
    return c if isinstance(c, str) else ""


def check_turn(msg: Dict[str, Any], hint: str) -> TurnVerdict:
    """Steps 2-4 on a single recovery assistant turn. (Step 5 done at transcript level.)"""
    idx = msg.get("_idx", -1)
    reasons: List[str] = []
    content = _content_of(msg)

    if msg.get("role") != "assistant":
        return TurnVerdict(index=idx, leak=False)

    # Step 2: explicit hint-reference phrases.
    if _HINT_REF.search(content):
        reasons.append("hint-reference phrase")
    if _DIAG_ECHO.search(content):
        reasons.append("diagnosis-echo phrase")

    # Step 3: long NL reasoning in content (tool-call data should be ~commands).
    if len(content) > _LONG_CONTENT_CHARS:
        reasons.append(f"long NL content ({len(content)} chars)")

    # Step 4: token overlap of hint's salient tokens into CONTENT (not tool args).
    if hint and content:
        ht = _salient_tokens(hint)
        ct = _salient_tokens(content)
        if ht:
            frac = len(ht & ct) / len(ht)
            if frac >= _OVERLAP_FRAC:
                reasons.append(f"hint-token overlap {frac:.0%}")
    return TurnVerdict(index=idx, leak=bool(reasons), reasons=reasons)


def filter_recovery(
    recovery_turns: List[Dict[str, Any]],
    hint: str,
    llm_judge: Optional[Callable[[List[Dict[str, Any]], str], bool]] = None,
) -> StripResult:
    """Run steps 2-5 on the recovery continuation (already hint-message-stripped).

    `recovery_turns`: messages AFTER the failure prefix (assistant tool-calls +
    tool results), with the hint message already removed (step 1).
    `llm_judge(turns, hint) -> True if it LEAKS` is the optional step-5 hook.
    Returns clean=True only if NO step fired. We reject the whole transcript on any
    leak (conservative: a leaked turn poisons the trajectory)."""
    res = StripResult(clean=True)
    for i, m in enumerate(recovery_turns):
        m = {**m, "_idx": i}
        v = check_turn(m, hint)
        res.turns.append(v)
        if v.leak:
            res.clean = False
    if res.clean and llm_judge is not None:
        try:
            if llm_judge(recovery_turns, hint):
                res.clean = False
                res.reasons.append("llm-judge: references external hint")
        except Exception as e:           # judge failure -> be conservative, keep but flag
            res.reasons.append(f"llm-judge error: {e}")
    if not res.clean:
        res.reasons = [f"turn {v.index}: {', '.join(v.reasons)}" for v in res.turns if v.leak] + res.reasons
    return res


if __name__ == "__main__":
    HINT = "Your last command exited non-zero; verify the build artifact (libmath.so) exists before finishing."
    samples = [
        # clean: pure command, short desc
        [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"cd /workspace/mathlib && make"}'}}]},
         {"role": "tool", "content": "EXIT CODE: 0"}],
        # leak: references the hint
        [{"role": "assistant", "content": "Based on the hint, the issue is likely that libmath.so is missing, so I'll rebuild it."}],
        # leak: long NL reasoning echoing hint tokens
        [{"role": "assistant", "content": "Since the last command exited non-zero, the build artifact libmath.so probably does not exist; I should verify the build artifact and the libmath.so file before finishing the task properly here."}],
        # clean-ish: short natural sentence, no hint words, low overlap
        [{"role": "assistant", "content": "Let me re-run the build.", "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"make"}'}}]}],
    ]
    for i, turns in enumerate(samples):
        r = filter_recovery(turns, HINT)
        print(f"sample {i}: {'CLEAN' if r.clean else 'LEAK'}  {('- '+'; '.join(r.reasons)) if not r.clean else ''}")
