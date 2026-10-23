#!/usr/bin/env bash
# PostToolUse(Write|Edit|Bash): run the CI lint after anything that could have touched a file.
#
# Why the whole engine and not just the edited file: edits arrive as Write, as Edit, and as sed or
# python heredocs inside Bash, and only the first two carry a file_path to inspect. `ruff check
# engine` is bugs-only (E9, F) and costs ~20ms on the full tree, so there is nothing to save by
# narrowing it. F is the family that catches what gets left behind by a patch — undefined names,
# unused variables, and F811 redefinitions, which is how a duplicated test block was once found.
#
# Why no formatter: `ruff format` is deliberately not part of this project. The lint config
# (engine/pyproject.toml, [tool.ruff.lint]) explains it — the tree has 4,400+ long lines and the
# frozen closed records must not be reformatted.
set -u
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}" || exit 0
ruff=engine/.venv/bin/ruff
[ -x "$ruff" ] || exit 0
if ! out=$("$ruff" check engine 2>&1); then
  printf 'ruff check engine failed — fix this before committing:\n%s\n' "$out" >&2
  exit 2
fi
exit 0
