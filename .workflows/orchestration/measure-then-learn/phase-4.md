# Phase 4: Survivorship check runnable here; EODHD top-up

**Plan set:** `MEASURE_THEN_LEARN_PLAN.md`
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Satisfies:** R3 — the survivorship check runs from any worktree on this machine, and what EODHD still offers is pulled before the key expires on 2026-11-10
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands` (plus `lab/survivorship_check.py`, skills, a runbook and data operations)

---

## Goal

`lab survivorship` and `survivorship_store` stop assuming they run in the main checkout. Every
default that names the survivorship-check store, the dev store it is built from, or the EODHD
cache now honours an environment variable (`SEER_SV_STORE`, `SEER_RESEARCH_STORE`,
`SEER_EODHD_CACHE`), the same way `--store` already honours `$SEER_RESEARCH_STORE`. The skills
export `SEER_SV_STORE`, so a Sera child in a worktree can keep a survivorship-check promise on the
day it makes it. That promise is what failed for M0117 (lab insight 208). Last, the alias top-up
is run once more against EODHD, the store is rebuilt against the current dev store, and a runbook
records how to do both, plus the coverage before and after.

## Facts measured while planning (2026-10-12, main checkout)

These shape the steps. The implementer re-checks them in Step 7 and does not need to rediscover them.

- `/home/miftah/seer/engine/.research-sv/manifest.json` was built 2026-10-10 20:21. It has
  `purpose: survivorship-check`, 989 of 1061 symbols served, 3,620,001 bar rows, and fingerprint
  `9de54476…`. Its coverage report names source price fingerprint `5451195f…`. Member-day coverage
  across 1996-2015 is 58.6% before and 89.0% after.
- The dev store `/home/miftah/seer/engine/.research` was rebuilt later, at 20:56 on 2026-10-10.
  Its `fundamentals.csv`, `fx.csv` and `market_series.csv` shas are **identical** to the sv
  store's, including the `T13W` series that phase 2 reads. Its price fingerprint is still
  `5451195f…` (research.py:440-455 documents this). So the sv store is not stale on price. The
  rebuild below exists to take in any new alias data and to prove the build runs from a worktree.
- The EODHD cache `/home/miftah/seer/engine/.cache/eodhd/` holds `eod/` (522 files, one per symbol
  the dev store cannot serve), `splits/`, `dividends/`, `market/`, `alias/` (129 probe files), and
  `symbols-US-{delisted,live}.json` (fetched 2026-10-10 17:51). The alias fetch **already ran
  once**. In the store's `alias_report.csv`, 200 members were targeted, 128 were accepted and 72
  were not. All of the 72 have reasons that more fetching cannot fix: "no candidate fits", an
  ambiguous pair, or "the source store has bars but none on a member day".
- `--fetch-aliases` (`commands/survivorship_store.py:445-520`, `survivorship_alias.fetch`) is the
  command's only network path. It probes at most `MAX_CANDIDATES = 4` codes per member and writes
  under `<cache>/alias/` only. It skips codes it has already cached unless `--refetch` is passed.
  The global `--dry-run` prints how many codes it *would* probe and fetches nothing. A second run
  is therefore expected to make close to zero calls. It is still worth running before 2026-11-10
  because it is the one cheap way to confirm nothing is left unfetched.
- **No other EODHD fetch is worth making for the unserved names.** The primary `eod/` cache
  already has a file for all 522 symbols. The remaining unserved reasons are of three kinds. (a)
  "eodhd has no daily series for X.US": the alias probe already looked for those under the
  delisted and live symbol lists. (b) A ticker that was reused by a later company: aliases cover
  this, and the cases still unmatched are resolver decisions, not missing data. (c) "the source
  store has bars but none on a member day": a dev-store matter, not an EODHD one. Re-fetching
  history for delisted names would return the same frozen bars. This is recorded in the runbook.
- `engine/.research-sv.bak-*` is **not** gitignored (`.gitignore:33-35` covers only
  `.research-sv/`, `.research-sv.tmp/` and `.research-sv.old/`). A 331 MB backup at
  `/home/miftah/seer/engine/.research-sv.bak-20261012` would sit untracked in main's `git status`,
  where a later `git add -A` could pick it up. **So the backup goes outside the repo:**
  `/home/miftah/seer-backups/research-sv.bak-20261012`. This is a deliberate deviation from the
  phase scope's suggested path. Free disk space is 904 GB.
- The worktree `/home/miftah/.worktrees/seer/measure-then-learn` has no `engine/.venv`.
- Lab DB `/home/miftah/seer/lab/lab.sqlite` holds 5 dev trials for M0117 and 5 for M0069.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- environment variable `SEER_SV_STORE`, the default for `lab survivorship --sv-store` and `survivorship_store --out`
- environment variable `SEER_EODHD_CACHE`, the default for `survivorship_store --cache`
- `survivorship_store --source` now also honours the existing `SEER_RESEARCH_STORE`
- test file `engine/tests/test_sv_store_env.py`
- runbook `docs/runbooks/survivorship-store.md`

**Signature changes:** none. Only the argparse defaults and help strings change, and the
`peek_purpose` error text.
**Requires (from earlier phases):** nothing (independent of phases 1-3).
**Leaves alone (owned by others):**
- `research.py`. `SV_STORE_DIR`, `STORE_DIR` and `CACHE_DIR` constants are unchanged; the env
  lookup is inline in the commands, mirroring the existing `SEER_RESEARCH_STORE` pattern, so
  phase 2 can edit `research.py` without a conflict.
- `survivorship.py` (cleaning rules), `survivorship_alias.py` (resolver), `lab/hardgate.py`, and
  the dev store `engine/.research`. This phase writes nothing to the dev store.
- `sim/*`, `backtest/*`, `paper/*` (phases 1-2); presets and `web/lib` (phase 3); lab methods and
  runs (phases 5 and 7); `strategies/*` (phase 6).

**Provides to later phases:** phase 5 can run
`SEER_SV_STORE=/home/miftah/seer/engine/.research-sv … lab survivorship M01NN` from its worktree,
and the rebuilt sv store keeps `market_series.csv` (the `T13W` series phase 2's cash lever reads),
byte-identical to the dev store's (Step 7.6), so cash-yield variants re-run there.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/lab.py:101-102, 393-397` | modify | the module docstring names `SEER_SV_STORE`; the `--sv-store` default honours `$SEER_SV_STORE`; help text updated |
| `engine/src/seer_engine/lab/survivorship_check.py:199-203` | modify | the missing-manifest error names `SEER_RESEARCH_STORE` / `SEER_SV_STORE` |
| `engine/src/seer_engine/commands/survivorship_store.py:1-10, 39-44, 92-98` | modify | docstring; `import os`; `--out`/`--source`/`--cache` defaults honour `SEER_SV_STORE`/`SEER_RESEARCH_STORE`/`SEER_EODHD_CACHE` |
| `engine/tests/test_sv_store_env.py` | create | env fallback, explicit flag beats env, empty env falls back, help formats, error names the var |
| `engine/tests/test_lab_survivorship.py:393` | modify | the opt-in live test reads `SEER_SV_STORE` first (keeps `SEER_RESEARCH_SV_STORE` as a fallback) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md:31, 256-259` | modify | the child's export line adds `SEER_SV_STORE`; the "if missing" paragraph points at the env var and the runbook |
| `.claude/skills/sera-the-explorer/SKILL.md:24-30, 49` | modify | the env block and preflight name `SEER_SV_STORE` and the sv store |
| `docs/runbooks/survivorship-store.md` | create | build/refresh/alias-fetch commands, env vars, the 2026-11-10 deadline, coverage before/after |

Data (not tracked by git): `/home/miftah/seer/engine/.cache/eodhd/alias/` (possible new probe
files), `/home/miftah/seer/engine/.research-sv/` (rebuilt), and
`/home/miftah/seer-backups/research-sv.bak-20261012/` (backup).

## Implementation Steps

Shell shorthands used below:

```bash
W=/home/miftah/.worktrees/seer/measure-then-learn
M=/home/miftah/seer
PY=$W/engine/.venv/bin/python
```

### Step 0: Give the worktree its own venv
**File:** none (`$W/engine/.venv`, gitignored)
**Change:** CLAUDE.md requires each worktree to have its own venv. The main checkout's venv would
test the wrong tree.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
test -x engine/.venv/bin/python || python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -q -e 'engine[dev]'
```
**Impact:** none on tracked files.

### Step 1: `lab survivorship --sv-store` honours `$SEER_SV_STORE`
**File:** `engine/src/seer_engine/commands/lab.py:393-397`
**Change:** replace the `--sv-store` argument. `os` is already imported (line 195 uses
`os.environ`). The help string contains no `%`, so no escaping is needed.
**Code:** replace

```python
    s.add_argument(
        "--sv-store",
        type=Path,
        default=research.SV_STORE_DIR,
        help=f"the survivorship-check store (default: {research.SV_STORE_DIR}); refused unless "
             "its manifest says purpose survivorship-check",
    )
```

with

```python
    s.add_argument(
        "--sv-store",
        type=Path,
        default=Path(os.environ.get("SEER_SV_STORE") or research.SV_STORE_DIR),
        help=f"the survivorship-check store (default: {research.SV_STORE_DIR}, or "
             "$SEER_SV_STORE); refused unless its manifest says purpose survivorship-check. From a "
             "worktree, export SEER_SV_STORE to the main checkout's engine/.research-sv",
    )
```

**File:** `engine/src/seer_engine/commands/lab.py:101-102` (module docstring)
**Change:** replace

```
Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db and
SEER_RESEARCH_STORE sets --store.
```

with

```
Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db,
SEER_RESEARCH_STORE sets --store, and SEER_SV_STORE sets lab survivorship's --sv-store. A
worktree has none of the three stores of its own, so a child exports all three to the main
checkout's.
```

**Impact:** with the variable unset, the default is unchanged. An empty string also falls back,
because of `or`.

### Step 2: The missing-store error names the variables
**File:** `engine/src/seer_engine/lab/survivorship_check.py:199-203`
**Change:** replace the `except ValueError` branch of `peek_purpose`. It is reached for both
stores, so it names both variables.
**Code:** the full function after the change:

```python
def peek_purpose(store_dir: Path) -> str | None:
    """The manifest's ``purpose`` without loading a bar: ``research.declared_purpose``, with its
    refusals (no manifest, not JSON, an unknown purpose) as ``store.LabError``.

    The usual refusal is a missing manifest in a worktree: both stores are gitignored and live
    only in the main checkout, and the defaults are derived from the running module's own repo
    root. So the message names the two variables that point a worktree at the main checkout
    (lab insight 208: M0117's promised check was skipped because nothing said how to reach it)."""
    try:
        return research.declared_purpose(Path(store_dir))
    except OSError as e:
        raise store.LabError(f"{store_dir}: cannot read the manifest ({e})") from e
    except ValueError as e:
        raise store.LabError(
            f"{e}. Point the flag at a built store. Both stores live in the main checkout "
            f"(engine/.research and engine/.research-sv); from a worktree, export "
            f"SEER_RESEARCH_STORE and SEER_SV_STORE to them"
        ) from e
```

**Impact:** message text only. Exit code 2 is unchanged.
`test_cli_refuses_the_same_store_twice_and_a_missing_manifest` (test_lab_survivorship.py:318)
asserts only the exit code, so it still passes.

### Step 3: `survivorship_store` defaults honour the variables
**File:** `engine/src/seer_engine/commands/survivorship_store.py`

(a) **Imports, lines 39-44:** add `import os` after `import logging`:

```python
import argparse
import logging
import os
import shutil
from collections.abc import Mapping, Sequence
```

(b) **Module docstring, lines 1-10:** replace the opening paragraph with

```
"""survivorship_store -- build the survivorship-check store from the EODHD cache. No network.

    python -m seer_engine survivorship_store            # clean every cached series, print the coverage report; writes nothing
    python -m seer_engine survivorship_store --build    # write the store at --out (default engine/.research-sv)
    python -m seer_engine survivorship_store --report   # print the reports of the store already at --out

The store is ``--source`` (default the dev store, ``engine/.research``, read only) plus a cleaned
EODHD series for every member the dev store could not serve, read from ``--cache`` (default
``engine/.cache/eodhd``: ``eod/``, ``splits/``, ``dividends/``). ``seer_engine.survivorship`` holds
the cleaning rules; this module only reads, merges and writes.

The three defaults derive from the running module's repo root, and all three directories are
gitignored, so in a worktree they name directories that do not exist. ``$SEER_SV_STORE`` sets
``--out``, ``$SEER_RESEARCH_STORE`` sets ``--source`` (the variable ``lab`` already reads for
``--store``) and ``$SEER_EODHD_CACHE`` sets ``--cache``. A worktree exports them to the main
checkout's directories; ``docs/runbooks/survivorship-store.md`` has the commands.
```

The rest of the docstring ("What lands in ``--out``…" to the end) is unchanged.

(c) **`add_arguments`, lines 92-98:** the full function after the change:

```python
def add_arguments(p: argparse.ArgumentParser) -> None:
    out = Path(os.environ.get("SEER_SV_STORE") or research.SV_STORE_DIR)
    source = Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR)
    cache = Path(os.environ.get("SEER_EODHD_CACHE") or CACHE_DIR)
    p.add_argument("--build", action="store_true", help="write the store at --out")
    p.add_argument("--report", action="store_true", help="print the reports of the store at --out")
    p.add_argument(
        "--out", type=Path, default=out,
        help=f"store to write (default {research.SV_STORE_DIR}, or $SEER_SV_STORE)",
    )
    p.add_argument(
        "--source", type=Path, default=source,
        help=f"dev store to start from, read only (default {research.STORE_DIR}, or $SEER_RESEARCH_STORE)",
    )
    p.add_argument(
        "--cache", type=Path, default=cache,
        help=f"EODHD cache (default {CACHE_DIR}, or $SEER_EODHD_CACHE)",
    )
    add_alias_arguments(p)
```

**Impact:** with the variables unset, behaviour is identical. `_alias_inputs`
(`survivorship_store.py:461-468`) reads `args.source` and `args.cache`, so `--fetch-aliases` and
`--resolve-aliases` follow the variables too. `_refuse_out` (line 228) already refuses an `--out`
equal to the source or to the checkout's dev or test store, so `SEER_SV_STORE` set by mistake to
the dev store is still refused. The existing tests in `test_survivorship_store.py` and
`test_survivorship_alias.py` build `argparse.Namespace` by hand, so they never see these defaults.

### Step 4: Tests for the env fallback
**File:** `engine/tests/test_sv_store_env.py` (create)
**Change:** these tests parse arguments only. There is no network, no store load and no database:
the autouse fixture in `conftest.py:57-58` keeps `SEER_ENV_FILE` and the DB URL away from
production, and nothing here reaches either.
**Code:**

```python
"""The store and cache defaults honour their environment variables (lab insight 208).

A worktree has no ``engine/.research``, ``engine/.research-sv`` or ``engine/.cache/eodhd`` of its
own: all three are gitignored, and the defaults derive from the running module's repo root. M0117's
promised survivorship check was skipped in a Sera worktree for exactly that reason. These tests pin
the fallback chain ``flag > $VAR > checkout default``. They parse arguments and nothing more, so
they cannot reach a store, the network or a database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from seer_engine import cli, research
from seer_engine.commands import survivorship_store as sv_cmd
from seer_engine.lab import store
from seer_engine.lab import survivorship_check as svc

ENV_VARS = ("SEER_SV_STORE", "SEER_RESEARCH_STORE", "SEER_EODHD_CACHE")


@pytest.fixture
def env(monkeypatch):
    """A monkeypatch with none of the three variables set, whatever the caller's shell exports."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _parse(*argv: str):
    # build_parser runs every command's add_arguments, so the env is read here, at parse time
    return cli.build_parser().parse_args(list(argv))


# ---- lab survivorship ---------------------------------------------------------------------


def test_lab_survivorship_defaults_to_this_checkout_without_the_variables(env):
    args = _parse("lab", "survivorship", "M0001")
    assert args.sv_store == research.SV_STORE_DIR
    assert args.store == research.STORE_DIR


def test_lab_survivorship_sv_store_honours_seer_sv_store(env, tmp_path):
    env.setenv("SEER_SV_STORE", str(tmp_path / "sv"))
    env.setenv("SEER_RESEARCH_STORE", str(tmp_path / "dev"))
    args = _parse("lab", "survivorship", "M0001")
    assert args.sv_store == tmp_path / "sv"
    assert args.store == tmp_path / "dev"


def test_lab_survivorship_flag_beats_the_variable(env, tmp_path):
    env.setenv("SEER_SV_STORE", str(tmp_path / "from-env"))
    args = _parse("lab", "survivorship", "M0001", "--sv-store", str(tmp_path / "from-flag"))
    assert args.sv_store == tmp_path / "from-flag"


def test_lab_survivorship_empty_variable_falls_back(env):
    env.setenv("SEER_SV_STORE", "")
    assert _parse("lab", "survivorship", "M0001").sv_store == research.SV_STORE_DIR


def test_lab_survivorship_help_formats_and_names_the_variable(env, capsys):
    with pytest.raises(SystemExit) as exc:
        _parse("lab", "survivorship", "--help")
    assert exc.value.code == 0
    assert "SEER_SV_STORE" in capsys.readouterr().out


# ---- survivorship_store -------------------------------------------------------------------


def test_survivorship_store_defaults_to_this_checkout_without_the_variables(env):
    args = _parse("survivorship_store")
    assert args.out == research.SV_STORE_DIR
    assert args.source == research.STORE_DIR
    assert args.cache == sv_cmd.CACHE_DIR


def test_survivorship_store_defaults_honour_the_variables(env, tmp_path):
    env.setenv("SEER_SV_STORE", str(tmp_path / "sv"))
    env.setenv("SEER_RESEARCH_STORE", str(tmp_path / "dev"))
    env.setenv("SEER_EODHD_CACHE", str(tmp_path / "eodhd"))
    args = _parse("survivorship_store", "--build")
    assert (args.out, args.source, args.cache) == (tmp_path / "sv", tmp_path / "dev", tmp_path / "eodhd")


def test_survivorship_store_flags_beat_the_variables(env, tmp_path):
    for var in ENV_VARS:
        env.setenv(var, str(tmp_path / "from-env"))
    args = _parse(
        "survivorship_store",
        "--out", str(tmp_path / "o"), "--source", str(tmp_path / "s"), "--cache", str(tmp_path / "c"),
    )
    assert (args.out, args.source, args.cache) == (tmp_path / "o", tmp_path / "s", tmp_path / "c")


def test_survivorship_store_help_formats_and_names_the_variables(env, capsys):
    with pytest.raises(SystemExit) as exc:
        _parse("survivorship_store", "--help")
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for var in ENV_VARS:
        assert var in out


# ---- the refusal says how to reach the main checkout --------------------------------------


def test_a_missing_store_names_both_variables(tmp_path):
    with pytest.raises(store.LabError) as exc:
        svc.peek_purpose(Path(tmp_path / "nowhere"))
    message = str(exc.value)
    assert "SEER_SV_STORE" in message and "SEER_RESEARCH_STORE" in message
```

**Impact:** new tests only. Before writing the test, the implementer checks that `cli.build_parser`
is importable with that name. It is, at `cli.py:63`. The test also relies on argparse's `--help`
going to stdout and exiting 0, which is standard.

### Step 5: The opt-in live test reads the new variable
**File:** `engine/tests/test_lab_survivorship.py:393`
**Change:** replace

```python
    sv_dir = Path(os.environ.get("SEER_RESEARCH_SV_STORE") or "/home/miftah/seer/engine/.research-sv")
```

with

```python
    sv_dir = Path(
        os.environ.get("SEER_SV_STORE")
        or os.environ.get("SEER_RESEARCH_SV_STORE")  # the name this test used before SEER_SV_STORE
        or "/home/miftah/seer/engine/.research-sv"
    )
```

**Impact:** the test is skipped unless `SEER_LAB_SURVIVORSHIP_LIVE` is set. CI is unaffected.

### Step 6: Skills export `SEER_SV_STORE`
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:31`
**Change:** replace the database row

```
| database | `lab/lab.sqlite` in this checkout | the shared one: `export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` |
```

with

```
| database | `lab/lab.sqlite` in this checkout | the shared one: `export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research SEER_SV_STORE=/home/miftah/seer/engine/.research-sv` (the last one is what lets `lab survivorship` run from the worktree) |
```

**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md:256-259`
**Change:** replace

```
     argued commit in `lab/hardgate.py`, like any other rule change. If `engine/.research-sv` is
     missing, build it offline from the EODHD cache, from the main checkout with absolute paths
     and never through a symlink: `engine/.venv/bin/python -m seer_engine survivorship_store
     --build --out "$PWD/engine/.research-sv" --source "$PWD/engine/.research"`.
```

with

```
     argued commit in `lab/hardgate.py`, like any other rule change. In a worktree (a Sera
     child), `lab survivorship` finds the check store only through `SEER_SV_STORE` (exported in
     the table at the top). Without it, the command refuses with exit 2 and names the variable.
     That is no reason to skip a check you promised: export it and run again. If
     `/home/miftah/seer/engine/.research-sv` itself is missing, build it offline from the EODHD
     cache with absolute paths and never through a symlink:
     `engine/.venv/bin/python -m seer_engine survivorship_store --build --out /home/miftah/seer/engine/.research-sv --source /home/miftah/seer/engine/.research --cache /home/miftah/seer/engine/.cache/eodhd`
     (`docs/runbooks/survivorship-store.md` has the refresh steps and the EODHD deadline).
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:24-30` (the env block)
**Change:** add one line after `LOGS=…`, inside the same fenced block:

```
SV=$REPO/engine/.research-sv                   # the survivorship-check store; children reach it via SEER_SV_STORE=$SV
```

**File:** `.claude/skills/sera-the-explorer/SKILL.md:48-49` (preflight)
**Change:** replace

```
   push, and run the tests again. Always test after staging, never before. `engine/.research/`
   present (build it if not). Then check `$TMUX`. If there is **no tmux**, don't stop: run the
```

with

```
   push, and run the tests again. Always test after staging, never before. `engine/.research/`
   present (build it if not), and `engine/.research-sv/` present
   (`$PY -m seer_engine survivorship_store --report` prints its coverage; rebuild per
   `docs/runbooks/survivorship-store.md` if it is missing). Each child exports
   `SEER_SV_STORE=$SV` from the explore skill's table, so it can keep a survivorship-check promise
   the same day. Then check `$TMUX`. If there is **no tmux**, don't stop: run the
```

**Impact:** docs only. Sera itself runs in `$REPO`, where the default already works. The variable
matters for the children.

### Step 7: Data — record the store before, back it up, top up EODHD, rebuild
**File:** none tracked. These are operations on main-checkout data, run with the worktree's code
and venv. Each command is bounded and idempotent. Run them in order and stop at the first
unexpected exit.

```bash
W=/home/miftah/.worktrees/seer/measure-then-learn
M=/home/miftah/seer
PY=$W/engine/.venv/bin/python
SCR=/tmp/claude-1000/sv-phase4; mkdir -p $SCR
cd $W

# 7.1 before: the store's own reports, kept for the runbook
$PY -m seer_engine survivorship_store --report --out $M/engine/.research-sv > $SCR/before.txt
python3 -c "import json;m=json.load(open('$M/engine/.research-sv/manifest.json'));print({k:v for k,v in m.items() if k!='files'})" >> $SCR/before.txt

# 7.2 backup, outside the repo (engine/.research-sv.bak-* is not gitignored)
mkdir -p /home/miftah/seer-backups
cp -a $M/engine/.research-sv /home/miftah/seer-backups/research-sv.bak-20261012
diff -rq $M/engine/.research-sv /home/miftah/seer-backups/research-sv.bak-20261012 && echo backup-ok

# 7.3 alias top-up: dry run first (counts codes, fetches nothing), then the real fetch
export SEER_ENV_FILE=$M/.env.local   # EODHD_API_TOKEN; valid to 2026-11-10
$PY -m seer_engine --dry-run survivorship_store --fetch-aliases \
    --source $M/engine/.research --cache $M/engine/.cache/eodhd | tee $SCR/fetch-dry.txt | head -3
$PY -m seer_engine survivorship_store --fetch-aliases \
    --source $M/engine/.research --cache $M/engine/.cache/eodhd | tee $SCR/fetch.txt | head -3
#   exit 1 = some codes failed (the rest are cached): run the same command once more; it resumes.
#   expected: "alias fetch: ~0 calls, N members accepted, M already cached, 0 failed"

# 7.4 preview the build (writes nothing), then build
$PY -m seer_engine survivorship_store \
    --out $M/engine/.research-sv --source $M/engine/.research --cache $M/engine/.cache/eodhd > $SCR/preview.txt
$PY -m seer_engine survivorship_store --build \
    --out $M/engine/.research-sv --source $M/engine/.research --cache $M/engine/.cache/eodhd | tee $SCR/build.txt | tail -3

# 7.5 after
$PY -m seer_engine survivorship_store --report --out $M/engine/.research-sv > $SCR/after.txt
python3 -c "import json;m=json.load(open('$M/engine/.research-sv/manifest.json'));print({k:v for k,v in m.items() if k!='files'})" >> $SCR/after.txt
diff <(head -30 $SCR/before.txt) <(head -30 $SCR/after.txt)

# 7.6 the cash series survived the rebuild (phase 5's -CASH variants re-run here under lab survivorship)
cmp $M/engine/.research/market_series.csv $M/engine/.research-sv/market_series.csv && echo market-series-identical
grep -c '^T13W,' $M/engine/.research-sv/market_series.csv    # expect 5722 (the dev store's count)
```

**Checks after 7.6:** `market_series.csv` is present in the rebuilt store and byte-identical to the
dev store's (7.6 prints `market-series-identical`), with the `T13W` rows the dev store has. If it is
missing or differs, stop: phase 5's cash variants could not be re-run by `lab survivorship`, which
is the promise this phase exists to keep. The manifest still says `purpose: survivorship-check`. `symbols_served` is at
least 989. The coverage report's "source store: price fingerprint" line still reads `5451195f…`,
which is the dev store's price fingerprint. If the build exits 2, the store on disk is untouched,
because the swap happens only on success (`research._swap_in`, research.py:997). Read the
message, fix the cause, and do not restore from the backup unless the directory is actually
damaged.

**Impact:** `$M/engine/.research-sv` is replaced in one swap. Anyone running `lab survivorship` in
main during the swap sees the old store or the new one, never half of each. Nothing under git
changes in the main checkout.

### Step 8: Smoke from the worktree
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
# positive: the M0117 check that could not run on 2026-10-12, now from a worktree; writes nothing
SEER_SV_STORE=/home/miftah/seer/engine/.research-sv \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
  engine/.venv/bin/python -m seer_engine lab survivorship M0117 --no-journal; echo "exit=$?"

# negative: without SEER_SV_STORE the worktree default is missing -> exit 2, message names the var
env -u SEER_SV_STORE SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
  engine/.venv/bin/python -m seer_engine lab survivorship M0117 --no-journal; echo "exit=$?"
```
Expected: the first prints the side-by-side report and `No journal entry`, with `exit=0`. The
second prints a refusal containing `SEER_SV_STORE`, with `exit=2`. Confirm that
`git -C /home/miftah/seer status --short lab/` is empty afterwards, so the DB was not written.
The dev column's "reproduced" should read yes for M0117's variants. If phases 1 or 2 have
already merged into this worktree *and* changed default simulator behaviour (they are meant to be
opt-in), it could read no. That would be their regression to report, not this phase's.

### Step 9: The runbook
**File:** `docs/runbooks/survivorship-store.md` (create; no existing runbook covers it:
`docs/runbooks/` holds only `data-pipeline.md`, `monitoring.md` and `paper-trading.md`)
**Change:** write the file below. The `after` lines in the coverage table are filled in from
`$SCR/after.txt` and `$SCR/fetch.txt` (Step 7) when this step runs. They are measured values, not
code, and the "before" values are already measured.
**Code:**

````markdown
# Runbook — the survivorship-check store

The dev store (`engine/.research`) can price only about half of the companies that were ever in
the index, and the ones it misses are mostly the ones that died. The **survivorship-check store**
(`engine/.research-sv`) is the dev store plus EODHD prices for most of those missing members.
`lab survivorship MNNNN` re-runs a method's recorded dev variants on both stores and prints them
side by side. It is a cross-check, not a gate: `lab run`, `lab test` and `lab remeasure` refuse
the store, and `lab promote` never reads it.

Both stores and the EODHD cache are gitignored and live **only in the main checkout**:

| what | path | variable that points a worktree at it |
|---|---|---|
| dev store | `/home/miftah/seer/engine/.research` | `SEER_RESEARCH_STORE` |
| survivorship-check store | `/home/miftah/seer/engine/.research-sv` | `SEER_SV_STORE` |
| EODHD cache | `/home/miftah/seer/engine/.cache/eodhd` | `SEER_EODHD_CACHE` |
| lab database | `/home/miftah/seer/lab/lab.sqlite` | `SEER_LAB_DB` |
| EODHD token | `/home/miftah/seer/.env.local` (`EODHD_API_TOKEN`) | `SEER_ENV_FILE` |

## Run the check from a worktree

```bash
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
       SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
       SEER_SV_STORE=/home/miftah/seer/engine/.research-sv
engine/.venv/bin/python -m seer_engine lab survivorship M0117 --no-journal   # report only, writes nothing
engine/.venv/bin/python -m seer_engine lab survivorship M0117                # also journals one observation
```

Without `SEER_SV_STORE`, a worktree's default points at its own missing `engine/.research-sv`,
and the command refuses with exit 2 and names the variable.

## Rebuild the store (offline)

Rebuild after the dev store's **prices** change: a new `research_store` build that moves its price
fingerprint, or new alias data. A change to `fundamentals.csv` or `market_series.csv` alone does
not move the price fingerprint. The build copies those files from the source byte for byte, so
rebuild after such a change too if the two stores' files should match.

```bash
PY=engine/.venv/bin/python   # from any checkout with its own venv
$PY -m seer_engine survivorship_store --report --out /home/miftah/seer/engine/.research-sv   # coverage now
$PY -m seer_engine survivorship_store \
    --out /home/miftah/seer/engine/.research-sv \
    --source /home/miftah/seer/engine/.research \
    --cache /home/miftah/seer/engine/.cache/eodhd           # preview: prints coverage, writes nothing
$PY -m seer_engine survivorship_store --build \
    --out /home/miftah/seer/engine/.research-sv \
    --source /home/miftah/seer/engine/.research \
    --cache /home/miftah/seer/engine/.cache/eodhd           # writes <out>.tmp, swaps it in whole
```

Use absolute paths and never a symlink for `--out`, because the swap would replace the
directory the link names. The build refuses an `--out` that is the source, the dev store or the
test store, or that holds a store with another purpose. On any failure the store on disk is left
exactly as it was. Backups go **outside** the repo (`/home/miftah/seer-backups/`), since only
`.research-sv/`, `.research-sv.tmp/` and `.research-sv.old/` are gitignored.

## Top up from EODHD (network) — before 2026-11-10

The EODHD key is valid until **2026-11-10**. After that date nothing new can be fetched, and the
cache on this PC is the only copy. Copy `engine/.cache/eodhd/` by hand to any other machine that
needs to build the store (see the `sync-research-store` skill).

```bash
export SEER_ENV_FILE=/home/miftah/seer/.env.local     # EODHD_API_TOKEN
$PY -m seer_engine --dry-run survivorship_store --fetch-aliases \
    --source /home/miftah/seer/engine/.research --cache /home/miftah/seer/engine/.cache/eodhd   # counts codes, fetches nothing
$PY -m seer_engine survivorship_store --fetch-aliases \
    --source /home/miftah/seer/engine/.research --cache /home/miftah/seer/engine/.cache/eodhd   # resumable; exit 1 = rerun
```

`--fetch-aliases` is the command's only network path. For every unserved member, it probes up to
four other EODHD codes the company may have traded under, using the delisted and live symbol
lists. It writes only under `<cache>/alias/` and skips codes already cached unless `--refetch`
is passed. Then rebuild (above).

**Nothing else is worth fetching for the members still unserved.** The primary `eod/` cache
already holds a file for every one of the 522 symbols the dev store cannot price. The rest fall
into three groups:
- EODHD has no series under any code we can match. The alias probe already searched for these.
- The ticker was reused by a later company, and no alias fits. Better matching here would be a
  change to the resolver in `survivorship_alias.py`, not more data.
- The dev store has bars but none on a member day. That is a dev-store question.

Re-fetching delisted history returns the same frozen bars.

## Coverage record

| when | symbols served | member-days covered 1996-2015 | aliases accepted / targeted | source price fingerprint |
|---|---|---|---|---|
| 2026-10-10 build | 989 / 1061 | 58.6% -> 89.0% | 128 / 200 | `5451195f…` |
| 2026-10-12 top-up + rebuild | {from after.txt manifest} | {from after.txt "all" row} | {from fetch.txt / build.txt "alias fill" line} | {from after.txt} |

2026-10-12 alias fetch: {the "alias fetch: … calls, … accepted, … already cached, … failed" line from fetch.txt}.
Backup of the 2026-10-10 store: `/home/miftah/seer-backups/research-sv.bak-20261012`.
````

The `{…}` cells are measured values copied from Step 7's output files when the runbook is written.
They are the only fill-ins, and the committed runbook must not contain braces.

**Impact:** new doc.

## Verification

**Build:** `/home/miftah/.worktrees/seer/measure-then-learn/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/measure-then-learn/engine`
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/measure-then-learn
engine/.venv/bin/pytest engine/tests/test_sv_store_env.py engine/tests/test_lab_survivorship.py engine/tests/test_survivorship_store.py engine/tests/test_survivorship_alias.py -n0 -q
engine/.venv/bin/pytest engine/tests -q        # full suite; DB tests need PG_TEST_URL (see CLAUDE.md)
```
**Manual check:** Step 8, both the positive and the negative smoke. Then
`git -C /home/miftah/seer status --short` shows nothing new: no backup directory, no DB write.
**Exit criteria:**
1. From this worktree, with `SEER_SV_STORE` set, `lab survivorship M0117 --no-journal` exits 0
   and prints both stores side by side. Without the variable, it exits 2 and names it.
2. `/home/miftah/seer/engine/.research-sv` is rebuilt on 2026-10-12. Its manifest purpose is
   `survivorship-check`, it serves at least 989 symbols, and its source price fingerprint is
   `5451195f…`. Its `market_series.csv` (with the `T13W` series) is byte-identical to the dev
   store's.
3. The alias fetch ran against EODHD before 2026-11-10 and ended with 0 failed.
4. The runbook records coverage before and after. Both skills export `SEER_SV_STORE`.

## Handoffs

- **Phase 5 (near-miss twins):** run `lab survivorship` on its twin with
  `SEER_SV_STORE=/home/miftah/seer/engine/.research-sv` exported. The sv store will be current
  once Step 7 is done. If phase 5's twin uses phase 2's cash interest, it reads `T13W` from
  `market_series.csv`, which the sv store copies byte for byte from the dev store (the shas
  match today). Phase 5 needs no rebuild unless the dev store's `market_series.csv` changes first.
- **Not owned by any phase (left as notes):**
  - `.gitignore` could add `engine/.research-sv.bak-*/` so a backup beside the store is safe.
    This phase avoids the need by backing up outside the repo.
  - `commands/market_series.py:80` and `commands/dividend_announcements.py:47` also default to
    subfolders of `engine/.cache/eodhd` and could honour `SEER_EODHD_CACHE` too. They are not on
    R3's path, so they are left alone.
  - `.claude/skills/sync-research-store/SKILL.md:117` gives a `--build` command that relies on
    `$PWD`. It is still correct in the main checkout.
  - The 72 still-unmatched alias targets, including ambiguous pairs like `ABI_old1` vs
    `ABI_old2`, would need a change to the resolver in `survivorship_alias.py`. That is a
    cleaning-rule change this phase must not make.

## Rollback

- **Code:** `git revert` the phase commit. All defaults return to the checkout-relative
  constants. The added variables are read nowhere else.
- **Data:** if the rebuilt store is wrong, run
  `rm -rf /home/miftah/seer/engine/.research-sv && cp -a /home/miftah/seer-backups/research-sv.bak-20261012 /home/miftah/seer/engine/.research-sv`,
  or rebuild with the Step 7.4 command plus `--no-aliases` to drop the alias fill. New files under
  `engine/.cache/eodhd/alias/` are additive cache entries. The build re-resolves from them every
  time, and no rollback needs to delete them.
````
