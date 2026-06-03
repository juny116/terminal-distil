"""Recovery-action-class key (discussion-003 P5).

Two recoveries are "the same action" iff their first corrective bash command maps
to the same key = (canon_argv0, intent_class). This keys both the gap metric (P6)
and the oracle-hint surface (P4) — the oracle reveals ONLY this class, never the
command itself (no exact argv / path / literal / patch content).

Design (locked, discussion-003 #2/#3):
  - canon_argv0: deterministic. Strip env-assignments, sudo/env/time/timeout/nice/
    nohup/command wrappers, take the first simple command's argv0, basename it,
    resolve a few aliases.
  - intent_class: rule-based primary with a confidence flag. argv0 alone is often
    enough; genuinely ambiguous commands (e.g. `python script.py`) return
    confident=False so the caller can route them to an LLM fallback. We also expose
    the intent-only key for sparse-cell analysis.

This module is pure and deterministic — no model calls. The LLM fallback is the
caller's responsibility (pass classify_intent's confident=False rows to a judge).
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Optional, Tuple

# Wrapper commands that prefix the real command; we skip them to find argv0.
_WRAPPERS = {
    "sudo", "env", "time", "nice", "nohup", "command", "exec", "builtin",
    "stdbuf", "ionice", "setsid", "xargs",
}
# `timeout 30 cmd`, `timeout --signal=KILL 30 cmd` — skip the wrapper + its numeric arg.
_TIMEOUT = {"timeout"}

# argv0 alias / canonicalization.
_ALIASES = {
    "python3": "python", "python2": "python",
    "pip3": "pip", "pip2": "pip",
    "vi": "vim", "nano": "vim", "emacs": "vim",
    "egrep": "grep", "fgrep": "grep", "rgrep": "grep", "rg": "grep", "ag": "grep",
    "fd": "find",
    "g++": "gcc", "cc": "gcc", "clang": "gcc",
    "node": "node", "nodejs": "node",
}

# intent_class rule map by canonical argv0 (discussion-003 #2).
_INTENT_BY_ARGV0 = {
    # inspect / read-only
    "cat": "inspect", "less": "inspect", "more": "inspect", "head": "inspect",
    "tail": "inspect", "grep": "inspect", "ls": "inspect", "find": "inspect",
    "stat": "inspect", "file": "inspect", "wc": "inspect", "diff": "inspect",
    "cmp": "inspect", "which": "inspect", "whereis": "inspect", "type": "inspect",
    "pwd": "inspect", "echo": "inspect", "printenv": "inspect", "env_print": "inspect",
    "awk": "inspect", "jq": "inspect", "xxd": "inspect", "hexdump": "inspect",
    "readlink": "inspect", "realpath": "inspect", "du": "inspect", "df": "inspect",
    "printf": "inspect", "nl": "inspect", "od": "inspect", "strings": "inspect",
    "objdump": "inspect", "readelf": "inspect", "sort": "inspect", "uniq": "inspect",
    "cut": "inspect", "tr": "inspect", "sqlite3": "inspect", "stat_print": "inspect",
    # edit
    "vim": "edit", "sed": "edit", "tee": "edit", "patch": "edit", "ex": "edit",
    # install
    "pip": "install", "apt": "install", "apt-get": "install", "npm": "install",
    "yarn": "install", "conda": "install", "gem": "install", "cargo": "install",
    "go": "install", "dpkg": "install", "yum": "install", "brew": "install",
    "poetry": "install",
    # run / exec / build
    "pytest": "run", "make": "run", "gcc": "run", "javac": "run", "java": "run",
    "bash": "run", "sh": "run", "ruby": "run", "perl": "run", "rustc": "run",
    "cmake": "run", "tox": "run", "unittest": "run", "mvn": "run", "gradle": "run",
    # permission
    "chmod": "permission", "chown": "permission", "chgrp": "permission",
    "umask": "permission", "setfacl": "permission",
    # network / service-remote
    "curl": "network", "wget": "network", "ssh": "network", "scp": "network",
    "nc": "network", "ping": "network", "netstat": "network", "ss": "network",
    "telnet": "network", "rsync": "network",
    # process / service
    "ps": "process", "kill": "process", "pkill": "process", "killall": "process",
    "systemctl": "process", "service": "process", "top": "process", "jobs": "process",
    "bg": "process", "fg": "process", "supervisorctl": "process",
    # fs-mutate
    "rm": "fs-mutate", "mv": "fs-mutate", "cp": "fs-mutate", "mkdir": "fs-mutate",
    "rmdir": "fs-mutate", "touch": "fs-mutate", "ln": "fs-mutate", "tar": "fs-mutate",
    "unzip": "fs-mutate", "zip": "fs-mutate", "gunzip": "fs-mutate", "gzip": "fs-mutate",
    "dd": "fs-mutate", "truncate": "fs-mutate",
}

# argv0 whose intent genuinely depends on args/context -> route to LLM fallback.
_AMBIGUOUS_ARGV0 = {"python", "node", "ruby", "perl", "git", "docker", "kubectl"}

# Leading navigation / shell-config commands that merely prefix the real action
# (`cd /path && make`, `set -e; pytest`, `export X=y; ...`). We step past these
# segments to find the meaningful first command.
_SKIP_LEADING = {
    "cd", "set", "export", "source", ".", ":", "true", "unset", "alias",
    "pushd", "popd", "shopt", "ulimit", "umask",
}

_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


@dataclass(frozen=True)
class ActionKey:
    canon_argv0: str
    intent_class: str
    confident: bool          # False -> intent came from a weak default; consider LLM fallback

    def as_tuple(self) -> Tuple[str, str]:
        return (self.canon_argv0, self.intent_class)


_SEP_RE = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")


def _segments(command: str) -> list[str]:
    """Split a compound line into simple-command segments."""
    return [s for s in _SEP_RE.split(command) if s.strip()]


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        # Unbalanced quotes etc. — fall back to whitespace split.
        return command.split()


def _segment_argv0(segment: str) -> str:
    """argv0 of a single simple command, after stripping env-assigns + wrappers."""
    toks = _tokenize(segment)
    i = 0
    while i < len(toks) and _ENV_ASSIGN.match(toks[i]):
        i += 1
    while i < len(toks):
        base = toks[i].rsplit("/", 1)[-1]
        if base in _WRAPPERS:
            i += 1
            continue
        if base in _TIMEOUT:
            i += 1
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
            if i < len(toks):
                i += 1  # the numeric duration
            continue
        break
    if i >= len(toks):
        return ""
    argv0 = toks[i].rsplit("/", 1)[-1]  # basename
    return _ALIASES.get(argv0, argv0)


def canon_argv0(command: str) -> str:
    """Canonical argv0 of the first MEANINGFUL command.

    Steps past leading navigation / shell-config segments (cd, set, export, ...)
    and pure env-assignment segments so `cd /x && make` keys as `make`, not `cd`.
    '' if nothing meaningful is extractable.
    """
    last = ""
    for seg in _segments(command):
        if seg.lstrip().startswith("#"):   # comment-only segment, not an action
            continue
        a = _segment_argv0(seg)
        if not a or a.startswith("#"):
            continue
        last = a
        if a not in _SKIP_LEADING:
            return a
    # Everything was navigation/config (e.g. a bare `cd /path`): return it as-is.
    return last


def classify_intent(command: str, argv0: Optional[str] = None) -> Tuple[str, bool]:
    """Return (intent_class, confident). confident=False -> route to LLM fallback."""
    a = argv0 if argv0 is not None else canon_argv0(command)
    if not a:
        return ("other", False)
    if a in _AMBIGUOUS_ARGV0:
        # e.g. `python -m pytest` is run, `python -c "open(...)"` may be edit/inspect.
        # Cheap refinements before giving up to the LLM fallback:
        if a == "python" and re.search(r"(?:^|\s)-m\s+(pytest|unittest|tox)\b", command):
            return ("run", True)
        if a == "git":
            return ("vcs", True)
        if a == "docker" or a == "kubectl":
            return ("container", True)
        return ("other", False)
    intent = _INTENT_BY_ARGV0.get(a)
    if intent is not None:
        return (intent, True)
    return ("other", False)


def action_key(command: str) -> ActionKey:
    """Full recovery-action-class key for a corrective bash command."""
    a = canon_argv0(command)
    intent, confident = classify_intent(command, a)
    return ActionKey(canon_argv0=a, intent_class=intent, confident=confident)


if __name__ == "__main__":
    tests = [
        "cat /tmp/rabbitmq_config.conf",
        "sudo systemctl restart nginx",
        "FOO=bar timeout 30 pytest -q tests/",
        "chmod +x ./run.sh",
        "pip install -r requirements.txt",
        "python -m pytest tests/test_x.py",
        "python script.py --flag",
        "sed -i 's/foo/bar/' config.yaml",
        "rm -rf /tmp/build && mkdir /tmp/build",
        "grep -r 'TODO' src/ | head",
        "/usr/bin/env python3 setup.py build",
        "git checkout -- broken.py",
        "curl -s http://localhost:8080/health",
    ]
    for t in tests:
        k = action_key(t)
        flag = "" if k.confident else "  <- LLM fallback"
        print(f"{t:48s} -> ({k.canon_argv0}, {k.intent_class}){flag}")
