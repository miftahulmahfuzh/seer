#!/usr/bin/env python3
"""PreToolUse(Bash): refuse a commit or a stage that sweeps the whole shared worktree.

Sessions share this worktree. A commit that stages everything lands whatever a peer phase left
half-written under your message, and `lab stage` writes the index, which a broad re-stage undoes.
Name the paths you own. See CLAUDE.md, "Concurrency in shared worktrees".

Quoted spans and heredoc bodies are stripped before matching, because a command that merely
*mentions* these flags -- a commit message, a test fixture, a doc being written -- is prose, not a
command. Getting that wrong is not theoretical: the first version of this hook refused the very
commit that introduced it. Flags inside quotes are never real flags; flags outside them always are.
"""

import json
import re
import sys

HEREDOC = re.compile(r"<<-?\s*[\"']?(\w+)[\"']?")

SWEEPS = (
    (
        re.compile(r"\bgit\b[^;&|]*\bcommit\b[^;&|]*(?:^| )(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?= |$)", re.MULTILINE),
        (
            "committing with -a/--all stages every change in this shared worktree, a peer"
            " phase's half-written files included."
        ),
    ),
    (
        re.compile(r"\bgit\b[^;&|]*\badd\b[^;&|]*(?:^| )(?:-A|-u|--all|--update|\.)(?= |$)", re.MULTILINE),
        (
            "staging broadly (dot, -A, -u) sweeps in a peer phase's work and undoes the index"
            " that `lab stage` wrote."
        ),
    ),
)


def strip_literals(cmd: str) -> str:
    """Remove heredoc bodies and quoted spans, leaving only text the shell would execute."""
    lines = cmd.split("\n")
    out, tag = [], None
    for line in lines:
        if tag is not None:
            if line.strip() == tag:
                tag = None
            continue
        match = HEREDOC.search(line)
        out.append(HEREDOC.sub(" ", line))
        if match:
            tag = match.group(1)
    kept = "\n".join(out)
    kept = re.sub(r"'[^']*'", " ", kept)
    return re.sub(r'"[^"]*"', " ", kept)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    bare = strip_literals(cmd)
    for pattern, why in SWEEPS:
        if pattern.search(bare):
            print(f"BLOCKED: {why} Name the paths you own instead.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
