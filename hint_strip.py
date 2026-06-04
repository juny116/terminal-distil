"""hint-strip / provenance filter for arm C (Ours ②½) — discussion-004 #5/#8/#9 (locked).

C generates the recovery WITH a grounded diagnosis hint, but the TRAINING DATA must
contain only the student's own evidence-grounded recovery (reasoning + action) — no
hint message, no hint-existence references, no exact-answer leaks, and we must be able
to tell whether a diagnosis the student states was GROUNDED in a tool observation
(evidence-supported, keep) or merely echoed from the hint (hint-derived, exclude from
strict main).

KEY (Codex #8): do NOT rewrite the recovery to make it clean — a rewrite makes the
teacher the author (new contamination). We TAG and SELECT conservatively; rejected
samples are reported as coverage/yield loss.

Pipeline (per C recovery):
  1. strip the hint message(s) from the transcript (role_tag == "hint").
  2. atomize the hint into atoms: diagnosis / action_class / exact_action / gold_literal.
     (the teacher supplies these when generating the hint; heuristic fallback otherwise.)
  3. for each recovery assistant turn (reasoning_content + content + tool commands):
       - hint-reference phrase            -> LEAK (drop)
       - exact_action / gold_literal atom -> LEAK (drop): forbidden answer leak
       - diagnosis / action_class atom    -> evidence-supported if a PRIOR tool
                                             observation already contained that evidence,
                                             else hint-derived
  4. verdict: LEAK (drop) | HINT_DERIVED (exclude from strict main / C-rationalized arm)
              | CLEAN (no-reference AND no-forbidden AND diagnosis evidence-supported or
                       low-overlap) -> usable for strict main C.

Steps 1-4 are deterministic. An optional leak-only LLM judge hook can be added for a
final pass. This module needs no model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Step 3: explicit references to the injected hint / the "user" who supplied it. In arm C
# the recovery reasoning must stand on its own evidence — any phrase that points back at
# the hint message (or the user/request/instruction that carried it) is a leak. Tuned on
# real L1 recoveries (e.g. "The user is asking me to verify ...", which the narrow v1
# missed).
_HINT_REF = re.compile(
    r"\b("
    r"hint|clue|teacher|"
    r"as (mentioned|suggested|noted|pointed out|requested|asked|instructed)|"
    r"based on (the|your|this) (hint|suggestion|advice|feedback|message|request|instruction|note)|"
    r"you (mentioned|suggested|said|pointed out|asked|want|wanted|requested|told|instructed|are asking|'re asking)|"
    r"per (the|your) (hint|suggestion|request|instruction)|"
    r"the (hint|advice|user|request|instruction|message|note|prompt|reminder) "
    r"(said|says|told|asks|asked|wants|wanted|requests|requested|is asking|is requesting|"
    r"points out|is pointing out|mentions|mentioned|instructs|instructed|reminds)|"
    r"(the )?user('s)? (is asking|is requesting|asked|wants|wanted|requested|request|instruction|reminder|note)|"
    r"(i am|i'm|i was|being) (asked|instructed|told|reminded|prompted) to|"
    r"following (the|your) (hint|suggestion|advice|instruction|request)|"
    r"given (the|your) (hint|clue|reminder|instruction)|"
    r"reminded (to|that)|the reminder"
    r")\b",
    re.I,
)
_STOP = set("the a an of to and or is are be in on for with that this it your you we i this that "
            "should make sure check that not do does use using run from into then a an be".split())


@dataclass
class HintAtoms:
    """Teacher-supplied (or heuristic) decomposition of the hint. The teacher knows
    which parts are mere diagnosis vs which would leak an answer/action."""
    diagnosis: List[str] = field(default_factory=list)      # cause / what-to-check (allowed if grounded)
    action_class: List[str] = field(default_factory=list)   # high-level action class (borderline)
    exact_action: List[str] = field(default_factory=list)   # exact command/flag (forbidden)
    gold_literal: List[str] = field(default_factory=list)   # exact answer/path/patch (forbidden)


@dataclass
class TurnTag:
    index: int
    verdict: str                          # leak | hint_derived | evidence_supported | low_overlap
    reasons: List[str] = field(default_factory=list)


# Codex #12 provenance labels, plus our leak. Ordered worst -> best for strict-main.
_PROV_RANK = {"leak": 0, "hint_derived": 1, "evidence_supported": 2, "low_overlap": 3}


@dataclass
class StripResult:
    verdict: str                          # leak | hint_derived | clean
    provenance: str                       # leak | hint_derived | evidence_supported | low_overlap
    turns: List[TurnTag] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    @property
    def usable_for_strict_main(self) -> bool:
        # strict main C keeps only no-leak AND (evidence-grounded OR student's own words)
        return self.provenance in ("evidence_supported", "low_overlap")


def _toks(text: str) -> set:
    t = re.findall(r"[A-Za-z_][A-Za-z0-9_./-]{2,}", (text or "").lower())
    return {x for x in t if x not in _STOP and not x.isdigit()}


def _salient_raw(text: str) -> set:
    """ALL-CAPS markers (TODO, ERROR, JSON, FIXME) are salient even when short — they are
    exactly the identifiers graders/logs key on. Case-fold AFTER detecting caps."""
    caps = {w.lower() for w in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text or "")}
    return caps | _salient(_toks(text))


def _salient(toks: set) -> set:
    """Identifier-like tokens: paths/filenames/symbols/flags (contain . / _ - or len>=6).
    Grounding on a SHARED salient identifier (e.g. 'libmath.so', '/etc/passwd',
    'valid_range') is far more robust than fractional bag-of-words overlap — a generic
    diagnosis word ('missing') appearing in both hint and observation proves nothing,
    but a shared specific identifier means the student actually saw that object."""
    return {t for t in toks if any(c in t for c in "./_-") or len(t) >= 6}


def atomize_hint(hint: str, atoms: Optional[HintAtoms] = None) -> HintAtoms:
    """Use teacher-supplied atoms if given; else a coarse heuristic (the whole hint is
    treated as diagnosis, with any backtick/quoted command-like span flagged as
    exact_action). Heuristic is only a fallback -- the teacher should supply atoms."""
    if atoms is not None:
        return atoms
    cmds = re.findall(r"`([^`]+)`", hint) + re.findall(r"\b([a-z_][\w-]*\s+--?\w[\w-]*)", hint)
    return HintAtoms(diagnosis=[hint], action_class=[], exact_action=cmds, gold_literal=[])


def _text_of(msg: Dict[str, Any]) -> str:
    """reasoning + content of an assistant turn (the bash command field is checked
    separately so a legit path in a command doesn't false-positive a content leak)."""
    return f"{msg.get('reasoning_content') or ''}\n{msg.get('content') or ''}"


def _commands_of(msg: Dict[str, Any]) -> str:
    out = []
    for tc in msg.get("tool_calls") or []:
        f = tc.get("function") or {}
        if f.get("name") == "bash":
            out.append(f.get("arguments") or "")
    return " ".join(out)


def _atom_hit(atom: str, text_toks: set, min_frac: float = 0.6) -> bool:
    at = _toks(atom)
    if not at:
        return False
    return len(at & text_toks) / len(at) >= min_frac


def tag_recovery(
    recovery_turns: List[Dict[str, Any]],
    atoms: HintAtoms,
    llm_judge: Optional[Callable[[List[Dict[str, Any]]], bool]] = None,
) -> StripResult:
    """Tag a hint-message-stripped recovery continuation. recovery_turns is the list of
    messages AFTER the failure prefix (assistant turns interleaved with tool results).

    Provenance (Codex #12), per turn and aggregated worst-first:
      leak               — references the hint, or reproduces an exact_action/gold_literal
      hint_derived       — asserts a hint diagnosis/action whose evidence the student has
                           NOT observed in any prior tool output (echoing the hint)
      evidence_supported — asserts a hint diagnosis AFTER a prior observation contained the
                           same salient identifier (student independently saw the cause)
      low_overlap        — recovery turn with no significant hint-atom overlap (own words)
    """
    res = StripResult(verdict="clean", provenance="low_overlap")
    diag_text = " ".join(atoms.diagnosis + atoms.action_class)
    diag_salient = _salient_raw(diag_text)

    # Pass 1: collect every salient identifier the student observed in tool output during
    # THIS recovery episode. Grounding is episode-level (Codex #12 pt.3): if the student
    # saw the cause first-hand anywhere in the recovery, asserting it is evidence_supported
    # regardless of which turn an inspection vs the fix happens on.
    all_observed_salient: set = set()
    for m in recovery_turns:
        if m.get("role") == "tool":
            all_observed_salient |= _salient_raw(m.get("content") or "")
    diag_grounded = bool(diag_salient & all_observed_salient)
    grounded_ids = sorted(diag_salient & all_observed_salient)

    for i, m in enumerate(recovery_turns):
        role = m.get("role")
        if role != "assistant":
            continue

        text = _text_of(m)
        cmd = _commands_of(m)
        text_toks = _toks(text)
        cmd_toks = _toks(cmd)
        reasons: List[str] = []
        verdict = "low_overlap"

        # hint-existence reference -> leak
        if _HINT_REF.search(text):
            verdict = "leak"; reasons.append("hint-reference phrase")

        # exact_action / gold_literal overlap (check BOTH content and command) -> leak
        if verdict != "leak":
            for atom in atoms.exact_action + atoms.gold_literal:
                if _atom_hit(atom, text_toks) or _atom_hit(atom, cmd_toks):
                    verdict = "leak"; reasons.append(f"forbidden-atom leak: {atom[:40]!r}")
                    break

        # diagnosis / action_class overlap -> evidence_supported vs hint_derived.
        # A turn "states the hint diagnosis" if it shares >=2 salient identifiers with the
        # hint (robust for long sentence-atoms), or for a short atom passes fractional
        # overlap. Salient-token overlap avoids both false-negatives (long atom never hits
        # 0.5) and false-positives (one generic shared word).
        if verdict != "leak":
            turn_salient = _salient_raw(text)
            shared = diag_salient & turn_salient
            short_atom_hit = any(
                _atom_hit(a, text_toks, min_frac=0.5)
                for a in atoms.diagnosis + atoms.action_class if len(_toks(a)) <= 4
            )
            if len(shared) >= 2 or short_atom_hit:
                if diag_grounded:
                    verdict = "evidence_supported"
                    reasons.append(f"states hint diagnosis {sorted(shared)}; grounded by observed {grounded_ids}")
                else:
                    verdict = "hint_derived"
                    reasons.append(f"states hint diagnosis {sorted(shared)}; cause never observed")

        res.turns.append(TurnTag(index=i, verdict=verdict, reasons=reasons))
        if _PROV_RANK[verdict] < _PROV_RANK[res.provenance]:
            res.provenance = verdict

    if res.provenance != "leak" and llm_judge is not None:
        try:
            if llm_judge(recovery_turns):
                res.provenance = "leak"; res.reasons.append("llm-judge: references external hint")
        except Exception as e:
            res.reasons.append(f"llm-judge error: {e}")

    res.verdict = {"leak": "leak", "hint_derived": "hint_derived"}.get(res.provenance, "clean")
    res.reasons += [f"turn {t.index}: {t.verdict} ({', '.join(t.reasons)})"
                    for t in res.turns if t.verdict not in ("low_overlap", "evidence_supported")]
    return res


def strip_hint_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Step 1: remove any message marked as a hint (role_tag == 'hint')."""
    return [m for m in messages if m.get("role_tag") != "hint"]


if __name__ == "__main__":
    atoms = HintAtoms(
        diagnosis=["the build artifact libmath.so may be missing after the failed build"],
        action_class=["rebuild the library"],
        exact_action=["make"],
        gold_literal=[],
    )
    samples = {
        "clean (grounded by observation)": [
            {"role": "assistant", "reasoning_content": "I'll check the library file first.", "content": "",
             "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"ls -la libmath.so"}'}}]},
            {"role": "tool", "content": "ls: cannot access 'libmath.so': No such file or directory"},
            {"role": "assistant", "reasoning_content": "The library is missing, so I will rebuild it.", "content": "",
             "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"cd /workspace/mathlib && gcc -shared -o libmath.so mathlib.c"}'}}]},
        ],
        "leak (references the hint)": [
            {"role": "assistant", "reasoning_content": "Based on the hint, libmath.so is missing, so I'll rebuild.", "content": ""},
        ],
        "hint_derived (states diagnosis with no prior observation)": [
            {"role": "assistant", "reasoning_content": "The build artifact libmath.so is missing after the failed build; rebuild it.", "content": "",
             "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"make"}'}}]},
        ],
    }
    for name, turns in samples.items():
        r = tag_recovery(turns, atoms)
        flag = "  [strict-main OK]" if r.usable_for_strict_main else "  [excluded]"
        print(f"{name:52s} -> {r.provenance.upper():18s}{flag}")
        for ln in r.reasons:
            print(f"      {ln}")
