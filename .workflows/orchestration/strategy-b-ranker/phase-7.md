# Phase 7: Real run on Neon, A2 byte-identity check, freeze or stop, docs

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-strategy-b-ranker.md` (§3 "Gate (P6a)", "Deployed model", "One round only"; §5 environment; §6 items 4, 7, 8, 9; §8 the owner's options)
**Satisfies:**
- R4: `backtest_wf`'s A2 report stays byte-identical on the same data. This phase does the real-data `cmp`.
- R7: one real run on Neon, with the committed report holding every §6.7 section.
- R8: freeze or stop.
- R9: the readme documents B; the suite is green with 0 skipped; CI is green with scikit-learn.

**Depends on:** Phase 6 (and so, transitively, 1–5)
**Difficulty:** NORMAL
**Package:** `docs/backtests/`, `engine/src/seer_engine/strategies/b.py` (one constant, pass branch only), `engine/data/models/` (pass only), `engine/tests`, `engine/package_readme.md`, `docs/ROADMAP.md`

---

## Goal

The `backtest_b` command from phases 1–6 runs once, for real and read-only, against Neon from the
worktree. Its three files are committed under `docs/backtests/`. Before that run, `backtest_wf` is
re-run on the 2026-10-02 data into a scratch directory, and all five A2 files must `cmp`-equal the
committed `docs/backtests/2026-10-02-strategy-a2-walkforward*`. Any difference stops the phase as a
finding.

The P6a gate then decides one of two outcomes:

- **Pass:** `STRATEGY_B_FROZEN` names the report, the committed artifact
  `engine/data/models/<END>-strategy-b.pkl`, the training cut-off and the artifact's SHA-256. The
  report is re-run so its `frozen-model:` line records that value.
- **Fail:** `STRATEGY_B_FROZEN` stays `None` and no artifact is committed. ROADMAP records that B's
  one round failed on this data, that P4 stays blocked, and the owner's options (b), (c) and (d).

In both branches, the new `tests/test_strategy_b_frozen.py` ties code, artifact and report together.
The engine readme and ROADMAP describe the result with measured numbers. The branch is pushed and
CI is green.

A failing gate still counts as a successful phase. The job is to measure honestly once, not to win.

The only source edit is the `STRATEGY_B_FROZEN` lines in `b.py`, and only on a pass. The only new
code is one test file.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `engine/tests/test_strategy_b_frozen.py`: a new test module with no importable API and **6
  tests**, all of which run in both branches.
- `docs/backtests/<END>-strategy-b-walkforward.md`, `-equity.csv` and `-equity.svg`. `backtest_b`
  generates them, and nobody edits them by hand. `<END>` is the data end of the run: the last SPY
  bar on Neon at run time, expected `2026-10-02` unless a nightly run has landed.
- **Pass only:** `engine/data/models/<END>-strategy-b.pkl`, written by `backtest_b` through
  `io.write_model_artifact`. The directory does not exist today. `.gitignore` does not ignore
  `*.pkl` (verified: `git check-ignore` returns 1), so a plain `git add` works.

**Signature changes:** none. On a **pass** only, the *value* of `strategies.b.STRATEGY_B_FROZEN`
changes from `None` to an explicit `FrozenModel(...)` literal, and its two-line placeholder comment
becomes a freeze comment naming the report. The annotation stays `FrozenModel | None`. On a **fail**,
`b.py` is not touched.

**Requires (from earlier phases):**
- Phase 1, `seer_engine.strategies.b_model`:
  - `TREE = "tree"`, `RIDGE = "ridge"`;
  - `loads(data: bytes) -> BModel`, which recomputes the digest from the estimator;
  - `BModel.kind`, `.n_features` and `.digest`;
  - `sha256(data) -> str` (hex);
  - scikit-learn pinned `>=1.9,<1.10` in `engine/pyproject.toml`.
- Phase 2, `seer_engine.strategies.b`:
  - `FEATURE_NAMES` (18 names);
  - `@dataclass(frozen=True, slots=True) FrozenModel(report: str, artifact: str, train_end: date, sha256: str)`;
  - `STRATEGY_B_FROZEN: FrozenModel | None = None` on one line, directly below a two-line
    placeholder comment. It is **not** re-exported from `seer_engine.strategies`; every reader
    (phase 6's command, this phase's test) reads `seer_engine.strategies.b.STRATEGY_B_FROZEN` at
    call time (Decision D24);
  - `date` imported at runtime (`from datetime import date`), because the pass literal calls
    `date(...)`;
  - `STRATEGY_B`, `BParams`, `SPY_SYMBOL`.
- Phase 4, `seer_engine.backtest.b_walkforward`: `B = "B"` and `B_LINEAR = "B-linear"`.
- Phase 5, `seer_engine.backtest.b_report`:
  - `report_stem(d) == f"{d.isoformat()}-strategy-b-walkforward"`;
  - `GATE_KEY = "p6a-gate"`, `GATED_KEY = "gated-model"`, `LAST_FOLD_KEY = "last-fold-model"` and
    `FROZEN_KEY = "frozen-model"`;
  - `parse_machine_line(markdown, key) -> str`, which returns the raw value of the single
    `<key>: <value>` line and raises `ValueError` unless exactly one exists (the same semantics as
    `wf_report.parse_machine_line`).

  The report always carries these four lines:
  - `p6a-gate: passed|failed`;
  - `gated-model: B|B-linear`;
  - `last-fold-model: <json object with keys kind, digest, train_end (ISO date string), rows (int),
    label_sum (a JSON string holding repr(float); read it back with float(...))>`, for the gated
    curve's last fold (Decision D23);
  - `frozen-model: null|<json object {"report", "artifact", "train_end" (ISO date), "sha256"}>`,
    taken from `STRATEGY_B_FROZEN` at run time.

  Only lines rendered from `BReport.frozen` change when `STRATEGY_B_FROZEN` changes.
- Phase 6:
  - The command line is `python -m seer_engine backtest_b [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start D] [--first-year YYYY] [--end D] [--dividends PATH]
    [--model-dir DIR]`, and every default is the committed run. `--out` defaults to
    `docs/backtests`, `--cache-dir` to `engine/.cache` (shared with `backtest_wf`), and
    `--model-dir` to `io.MODELS_DIR` = `<repo>/engine/data/models`.
  - The command is read-only and exits 0 on a pass or a fail.
  - It writes the three files via `io.write_b_report`. On a gate pass it also writes the gated
    curve's last-fold model via `io.write_model_artifact` and logs its path, its sha256 and the
    instruction to freeze.
  - It times and logs every step.
  - It reads `strategies.b.STRATEGY_B_FROZEN` at call time.
- Phases 1–6: no file under the plan index's "Out of scope" list differs from `0e91d8a`. Step 2
  proves this for A2 on real data.

**Leaves alone (owned by others):**
- every module under `strategies/` and `backtest/`, and `commands/backtest_b.py`, except, on a pass,
  the `STRATEGY_B_FROZEN` assignment and the two comment lines directly above it in `b.py`
  (phase 2);
- every test file that phases 1–6 create.

Nobody ever edits these (handover §3 Law):
- `seer_engine/sim/*`;
- `strategies/a.py`, `a2.py`, `base.py`;
- `backtest/runner.py`, `walkforward.py`, `wf_report.py`, `metrics.py`, `tuning.py`, `report.py`,
  `market.py`, `benchmark.py`;
- `commands/backtest.py`, `commands/backtest_wf.py`, `cli.py`;
- every pre-existing test file;
- `docs/backtests/2026-10-02-*`;
- `web/` and `.github/workflows/`.

The sole exception is a defect the real run exposes (see **Bug protocol**).

## Files

| File | Action | What changes |
|---|---|---|
| `docs/backtests/<END>-strategy-b-walkforward.md` | create (generated) | the P6a report |
| `docs/backtests/<END>-strategy-b-walkforward-equity.csv` | create (generated) | daily curves `date,b,b_linear,a2,spy_price,spy_tr` |
| `docs/backtests/<END>-strategy-b-walkforward-equity.svg` | create (generated) | B, B-linear, A2 and both SPY curves |
| `engine/data/models/<END>-strategy-b.pkl` | create (generated), **pass only** | `b_model.dumps` of the gated curve's last-fold model |
| `engine/src/seer_engine/strategies/b.py`, the `STRATEGY_B_FROZEN` line and the 2 comment lines above it (find them with `grep -n -B2 "^STRATEGY_B_FROZEN" engine/src/seer_engine/strategies/b.py`) | modify, **pass only** | `None` → an explicit `FrozenModel(...)` literal, plus a comment naming the report |
| `engine/tests/test_strategy_b_frozen.py` | create | 6 tests, asserting whichever branch the newest `*-strategy-b-walkforward.md` took |
| `engine/package_readme.md` (lines 4, 27, 55–82, 219/221, 493/495, 655/657, 684/685, 697, 706, 743/744, 880/882, 904; as of `0e91d8a`) | modify | B, b_model, labels, b_walkforward, b_report, io writers, the `backtest_b` command, layout, scikit-learn, module graph, reverse deps, Performance, Usage, Notes |
| `docs/ROADMAP.md` (after line 43, before line 45 `## P4`) | modify | a new `## P6a` block with the verdict sentence and the report link |

That is 8 files on a pass (4 of them generated) and 6 on a fail.

## Rules for this phase (read before Step 1)

1. **One round only, and no tuning on traded data.**
   - Run `backtest_b` with its defaults only: no `--is-start`, `--first-year`, `--end`,
     `--dividends` or `--model-dir`. `--out` and `--cache-dir` are allowed, because they change no
     number.
   - Do not edit a feature, the label, the purge, the folds, a hyperparameter, the pick threshold,
     the gate, the determinism probe, costs or the simulator to change a number.
   - Do not look at a result and then re-run with different settings. Whatever the verdict, it
     stands (handover §3 "One round only").
2. **Never hand-edit a generated file.** That covers the report files and the artifact. If one is
   wrong, the code is wrong: fix it under the **Bug protocol** and regenerate.
3. **Never `source` `.env.local`.** Its `DATABASE_URL` has an unquoted `&`. Point the engine at it
   with `SEER_ENV_FILE=/home/miftah/seer/.env.local`, because `config.REPO_ROOT` is the worktree.
   Never run raw `psql` against Neon from WSL: it hangs on IPv6. Use the engine.
4. **Use the worktree's own venv only** (`engine/.venv` inside the worktree). Never use
   `/home/miftah/seer/engine/.venv`, which tests main's tree. The single exception is the read-only
   discriminator in Step 2c.
5. **One sitting.** The A2 check and every B run must see the same Neon data.
   - The nightly job may add sessions from Mon 2026-10-05 23:00 UTC.
   - If the bars fingerprint `(max(date), count(*))` changes between Step 1's preflight and Step 7's
     post-check, discard every generated output, set `STRATEGY_B_FROZEN` back to `None` if Step 5
     ran, delete `engine/data/models/`, and restart at Step 2.
6. **The push is in scope** (Step 11). Push only `feature/strategy-b-ranker`, never `main`. Merging
   belongs to the completion handler or coordinator.

### Neon unreachable

If the preflight (Step 1c) or any run fails to connect (`psycopg.OperationalError`, a timeout, DNS,
or a `ConfigError` for the database URL), **stop**:
- Commit nothing from this phase.
- Do not write a report by hand or put placeholder files in `docs/backtests/`.
- Do not run against any other database.
- Leave `STRATEGY_B_FROZEN = None`.

Report the exact command, its exit code and the last 30 lines of its log to the caller, and say that
phase 7 is blocked on Neon access. You may retry later from Step 1.

### A2 finding (Step 2)

If any of the five A2 files differs from the committed one and Step 2c cannot show the cause is a
Neon data change, **stop**:
- Commit nothing.
- Do not run `backtest_b` for the report.
- Report `cmp` and `diff` output to the caller. A code-caused difference means some phase edited a
  path the A2 pipeline reads, which breaks the invariant "A2, v1 and the simulator are untouched".
  Name the file with
  `git diff --stat 0e91d8a -- engine/src/seer_engine/backtest engine/src/seer_engine/strategies engine/src/seer_engine/sim engine/src/seer_engine/commands`.

If Step 2c shows a data cause, it is still a finding. Stop and report it the same way, with the
diagnosis "Neon's data for ≤ 2026-10-02 changed; worktree code == main code on identical inputs".
The coordinator decides whether to continue.

### Bug protocol

A **bug** is any of these:
- a crash or a raised exception;
- a file that differs between two runs on the same data in more than the lines Step 6 allows;
- output that contradicts the plan index's interface contract or **Decisions**, for example:
  - fold windows that differ from `walkforward.folds`;
  - a curve that does not start at `prev_session(2018-01-02)`;
  - a required report section missing;
  - SPY appearing as a pick;
  - `p6a-gate:` disagreeing with the verdict sentence;
  - `gated-model:` disagreeing with the determinism-probe result in the Method section;
  - `last-fold-model` `kind` disagreeing with `gated-model`;
  - an artifact written on a failed gate;
  - candidate or labelled rows equal to 0.

A result you do not like is never a bug. When the real run exposes one:
1. Stop. Write a failing regression test on synthetic data in the owning phase's test file:
   - `test_b_model.py` (phase 1);
   - `test_indicators_b.py` or `test_strategy_b.py` (phase 2);
   - `test_backtest_labels.py` (phase 3);
   - `test_backtest_b_walkforward.py` (phase 4);
   - `test_backtest_b_report.py` (phase 5);
   - `test_backtest_b_command.py` (phase 6).
2. Fix it in the owning module only. Change nothing else.
3. Run the full suite (the Step 10 command). The fix adds tests, so the expected count grows by
   exactly the regression tests you added. Record them.
4. Commit the fix on its own, before the run commit, as
   `fix(<package>): <what> (found by the P6a real run)`. The body gives the symptom, the root
   cause, and whether any reported number changes. Repeat it in the completion report.
5. Delete `docs/backtests/*-strategy-b-walkforward*` and `engine/data/models/`, set
   `STRATEGY_B_FROZEN = None` if Step 5 ran, and restart at Step 3. You may keep the bar cache.

If the fix would change a rule, a feature, the label, a hyperparameter, the folds, the gate, the
determinism switch or the simulator, it is not a bug fix. Stop and report to the caller instead.

**Wall time.** If the whole `backtest_b` command takes more than 60 minutes, the result is still
valid (D18: a pool gathered in fold order changes no number). Record the time in the readme and add a
handoff. Do not parallelize in this phase.

## Implementation Steps

All commands run from the worktree root, `/home/miftah/.worktrees/seer/strategy-b-ranker`. Shell
state does not persist between tool calls, so start every call with:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
S=/tmp/claude-1000/-home-miftah-seer/<session-id>/scratchpad/p6a-phase7
```

Any session-specific scratchpad outside the repo works. Create it with `mkdir -p "$S"`. The shell
is **zsh**: use `${(P)name}`, not `${!name}`, and no bash-only constructs.

### Step 1: Environment, full suite green, Neon preflight

**File:** none (operations).

**1a. Worktree venv** (handover §5). Re-running `pip install -e` is idempotent, and it picks up
phase 1's scikit-learn pin.

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -q -e 'engine[dev]'
engine/.venv/bin/python -c "import seer_engine, pathlib, sklearn; print(pathlib.Path(seer_engine.__file__).resolve(), sklearn.__version__)"
```

The path must start with `/home/miftah/.worktrees/seer/strategy-b-ranker/`, and the scikit-learn
version must start with `1.9.`.

**1b. Full suite, 0 skipped.**

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
mkdir -p "$S"
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  engine/.venv/bin/pytest engine/tests -q -rs | tee "$S/suite-before.out"
grep -c '^SKIPPED' "$S/suite-before.out"   # must print 0
```

Every test must pass, with 0 skipped. Record the passed count as `<N6>`, the count after phase 6:
761 plus what phases 1–6 added, per the plan index's reconciled count table: **`<N6>` = 964**, and
**970** after this phase. A failure here belongs
to an earlier phase: stop and report it.

**1c. Neon preflight and fingerprint.** This is read-only and goes through the engine.

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
SEER_ENV_FILE=/home/miftah/seer/.env.local timeout 180 engine/.venv/bin/python - <<'PY' | tee "$S/fingerprint-before.txt"
from contextlib import closing
from seer_engine import db
with closing(db.connect()) as conn:
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    try:
        print("bars", *conn.execute("select max(date), count(*) from bars").fetchone())
        print("spy_end", conn.execute("select max(date) from bars where symbol = 'SPY'").fetchone()[0])
        print("universe_rows", conn.execute("select count(*) from universe").fetchone()[0])
        print("fx_end", conn.execute("select max(date) from fx_rates").fetchone()[0])
    finally:
        conn.rollback()
PY
```

Expected today: `bars 2026-10-02 1817429` and `spy_end 2026-10-02`. A newer date is allowed: the B
report stem follows `spy_end`, and Step 2 takes its fallback path. Any connection error means
**Neon unreachable**.

**1d. Starting state.**

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
git status --porcelain                                              # empty
grep -n -B2 "^STRATEGY_B_FROZEN" engine/src/seer_engine/strategies/b.py   # 2 placeholder comment lines + "= None"
grep -n "^from datetime import" engine/src/seer_engine/strategies/b.py    # must import date
ls docs/backtests/                                                  # only the 2026-10-02-strategy-a* and -a2-walkforward* files
test ! -e engine/data/models && echo "no models dir"
engine/.venv/bin/python -m seer_engine backtest_b --help > "$S/help-b.txt" && cat "$S/help-b.txt"
git diff --stat 0e91d8a -- engine/src/seer_engine/sim engine/src/seer_engine/strategies/a.py \
  engine/src/seer_engine/strategies/a2.py engine/src/seer_engine/strategies/base.py \
  engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/walkforward.py \
  engine/src/seer_engine/backtest/wf_report.py engine/src/seer_engine/backtest/metrics.py \
  engine/src/seer_engine/backtest/tuning.py engine/src/seer_engine/backtest/report.py \
  engine/src/seer_engine/backtest/market.py engine/src/seer_engine/backtest/benchmark.py \
  engine/src/seer_engine/commands/backtest.py engine/src/seer_engine/commands/backtest_wf.py \
  engine/src/seer_engine/cli.py docs/backtests web .github   # must print nothing
```

Keep `help-b.txt`: Step 8 checks the readme's command section against it. If `b.py` does not
import `date` at runtime, that is a phase 2 defect. Add `from datetime import date` as a
Bug-protocol fix (`fix(strategies): …`) before Step 5, and only on a pass.

### Step 2: A2 byte-identity check (R4)

**File:** none. Everything goes to `$S/a2`, and nothing under `docs/` is written.

`walkforward.py`, `wf_report.py` and `backtest_wf.py` are unedited (D1), and the rest of the
pipeline (`runner`, `metrics`, `tuning`, `market`, `benchmark`, `io.write_wf_report`,
`strategies.a2`) is unchanged or only gained additions. So A2's P3b report must re-render
byte-identically on the data it was made from.

**2a. Primary path, when Step 1c printed `bars 2026-10-02 1817429`.**

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
mkdir -p "$S/a2"
SEER_ENV_FILE=/home/miftah/seer/.env.local /usr/bin/time -v \
  engine/.venv/bin/python -m seer_engine backtest_wf --end 2026-10-02 --out "$S/a2" \
  > "$S/a2.out" 2> "$S/a2.log"; echo "exit=$?"
for f in 2026-10-02-strategy-a2-walkforward.md 2026-10-02-strategy-a2-walkforward-equity.csv \
         2026-10-02-strategy-a2-walkforward-equity.svg 2026-10-02-strategy-a2-walkforward-variants.svg \
         2026-10-02-strategy-a2-walkforward-grid.csv; do
  cmp "docs/backtests/$f" "$S/a2/$f" && echo "same $f"
done
grep -E "Elapsed \(wall clock\)|Maximum resident set size" "$S/a2.log"
```

The run must exit 0 and print five `same` lines. `{{A2_METHOD}}` is then "re-running `backtest_wf
--end 2026-10-02` on the unchanged Neon data (1,817,429 bar rows)". The worktree has no
`engine/.cache` and main has none either (verified), so this is a cold load, and it writes
`engine/.cache/bars-2026-10-02-1817429.pkl` (gitignored). Steps 3 and 6 then hit that cache. Record
`LOAD_COLD_S` from the log's load line.

**2b. Fallback, when the fingerprint is not `(2026-10-02, 1817429)`.** Rebuild the 2026-10-02 bar
set from a `COPY` of `bars` restricted to `date <= 2026-10-02`, guarded by an exact row count of
1,817,429, with live `universe` and `fx_rates`. Then call `backtest_wf`'s own `resolve` + `execute`
and `io.write_wf_report`. If the nightly job has applied a split since 2026-10-02, historical rows
were rescaled. The count then still matches but the prices do not, and 2c reports a data change.

Save as `$S/a2_rebuild.py`:

```python
"""Rebuild the P3b A2 walk-forward report from the 2026-10-02 bar set into a scratch dir.

usage: python a2_rebuild.py <out_dir>

Read-only: one REPEATABLE READ, READ ONLY transaction, always rolled back.
"""

from __future__ import annotations

import sys
from contextlib import closing
from datetime import date
from pathlib import Path

from seer_engine import db
from seer_engine.backtest import io
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.tuning import IS_START
from seer_engine.backtest.walkforward import FIRST_TRADE_YEAR
from seer_engine.commands import backtest_wf

A2_END = date(2026, 10, 2)
A2_ROWS = 1_817_429
COPY_SQL = (
    "COPY (SELECT symbol, date, open, high, low, close, volume FROM bars "
    "WHERE date <= DATE '2026-10-02' ORDER BY symbol, date) TO STDOUT"
)


def main() -> None:
    out = Path(sys.argv[1])
    with closing(db.connect()) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        try:
            io.BARS_COPY_SQL = COPY_SQL  # scratch-only override; read_bars_frame reads the module global
            frame = io.read_bars_frame(conn)
            intervals = io.read_intervals(conn)
            fx_rows = io.read_fx(conn)
        finally:
            conn.rollback()
    assert tuple(frame.columns) == io.BAR_COLUMNS, tuple(frame.columns)
    assert len(frame) == A2_ROWS, f"{len(frame)} bar rows, expected {A2_ROWS}"
    assert frame["date"].max().date() == A2_END, frame["date"].max()
    history = io.histories_from_frame(frame)
    market = Market(history=history, membership=Membership(intervals=intervals), fx=fx_rows)
    w = backtest_wf.resolve(market, IS_START, FIRST_TRADE_YEAR, A2_END)
    report = backtest_wf.execute(market, A2_ROWS, io.read_dividends(), w.is_start, w.first_year, w.end)
    for path in io.write_wf_report(out, report):
        print(path)


if __name__ == "__main__":
    main()
```

Before running it, check the names it relies on against `0e91d8a`:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
grep -n "^BARS_COPY_SQL\|^def read_bars_frame\|^def read_intervals\|^def read_fx\|^def histories_from_frame\|^BAR_COLUMNS" engine/src/seer_engine/backtest/io.py
grep -n "BARS_COPY_SQL" engine/src/seer_engine/backtest/io.py   # read_bars_frame must read the module global at call time
grep -n "^class Market\|^class Membership" -A6 engine/src/seer_engine/backtest/market.py
```

If `read_bars_frame` binds the SQL at import time, or `Market`/`Membership` take other field names,
adapt the **scratch script** only, never the engine. Then run it and compare:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
mkdir -p "$S/a2"
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python "$S/a2_rebuild.py" "$S/a2" 2> "$S/a2.log"; echo "exit=$?"
for f in "$S"/a2/*; do n=$(basename "$f"); cmp "docs/backtests/$n" "$f" && echo "same $n"; done
```

`{{A2_METHOD}}` is then "rebuilding from a `date <= 2026-10-02` copy of `bars` (1,817,429 rows),
with live `universe` and `fx_rates`, through `backtest_wf.resolve` + `execute`". There is no cold
load into the cache on this path. Step 3's `backtest_b` makes it, and `LOAD_COLD_S` comes from
there.

**2c. If any `cmp` differs, tell code from data.** `/home/miftah/seer` is `main` @ `0e91d8a`, and
its venv is an editable install of that tree. Running the same rebuild there separates a code
change from a data change. This is the only permitted use of main's venv, and it is read-only.

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
git -C /home/miftah/seer status --porcelain -- engine/src   # must be empty
git -C /home/miftah/seer rev-parse HEAD                     # 0e91d8a...
mkdir -p "$S/a2-main" "$S/a2-wt"
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python "$S/a2_rebuild.py" "$S/a2-wt" 2> "$S/a2-wt.log"
SEER_ENV_FILE=/home/miftah/seer/.env.local /home/miftah/seer/engine/.venv/bin/python "$S/a2_rebuild.py" "$S/a2-main" 2> "$S/a2-main.log"
for f in "$S"/a2-wt/*; do n=$(basename "$f"); cmp "$f" "$S/a2-main/$n" && echo "worktree==main $n"; done
for f in "$S"/a2-main/*; do n=$(basename "$f"); cmp "$f" "docs/backtests/$n" && echo "main==committed $n"; done
diff "$S/a2-main/2026-10-02-strategy-a2-walkforward.md" docs/backtests/2026-10-02-strategy-a2-walkforward.md | head -n 60
```

Both runs use the `copy` source, so they see identical data. Read the result this way:
- **Worktree == main, but main != committed:** the data changed, not the code. Name the table from
  the `.md` diff (a universe refresh, a split rescale or an FX revision). This is an **A2
  finding**: stop and report.
- **Worktree != main:** this phase set's code changed A2's output, which breaks invariant 3. This is
  also an **A2 finding**: stop and report.

### Step 3: Real `backtest_b` run #1

**File:** this step produces `docs/backtests/<END>-strategy-b-walkforward{.md,-equity.csv,-equity.svg}`,
and on a pass also `engine/data/models/<END>-strategy-b.pkl`.

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
SEER_ENV_FILE=/home/miftah/seer/.env.local /usr/bin/time -v \
  engine/.venv/bin/python -m seer_engine backtest_b --out docs/backtests \
  > "$S/b1.out" 2> "$S/b1.log"; echo "exit=$?"
tail -n 80 "$S/b1.log"
grep -E "Elapsed \(wall clock\)|Maximum resident set size" "$S/b1.log"
ls -l docs/backtests/ engine/data/models/ 2>&1
```

- **Exit code.** It must be 0, whether the gate passes or fails.
  - Exit 1 → **Bug protocol**, or **Neon unreachable** for a connection error.
  - Exit 2 → a precondition failed. Report it to the caller, and do not work around it with flags.
- **Files.** Exactly three new files appear, sharing the stem `<END>-strategy-b-walkforward`.
  Record `<END>`. `engine/data/models/` exists only if the gate passed, and then it holds exactly
  `<END>-strategy-b.pkl`.
- **Pristine copy:**

  ```sh
  mkdir -p "$S/b1" && cp docs/backtests/<END>-strategy-b-walkforward* "$S/b1/"
  test -e engine/data/models/<END>-strategy-b.pkl && cp engine/data/models/<END>-strategy-b.pkl "$S/b1/"
  ```
- **Machine lines:**

  ```sh
  grep -E '^(p6a-gate|gated-model|last-fold-model|frozen-model): ' docs/backtests/<END>-strategy-b-walkforward.md | tee "$S/machine1.txt"
  ```

  Expect exactly four lines: `p6a-gate: passed|failed`, `gated-model: B|B-linear`,
  `last-fold-model: {"kind": …, "digest": …, "train_end": …, "rows": …, "label_sum": …}` and
  `frozen-model: null`. Record:
  - `<GATE>` and `<GATED>`;
  - `<LAST_KIND>`, `<LAST_DIGEST>` and `<TRAIN_END>` (expected `2025-12-31`, the last fold's
    `tune_end`);
  - `<TRAIN_ROWS>` and `<LABEL_SUM>`;
  - `<LAST_YEAR>`, the year of `<END>`.
- **Verdict.** Record the sentence verbatim from the report as `<VERDICT_SENTENCE>`. Act on it only
  through Step 5's branch and the docs.
- **Artifact log (pass).** Record the sha256 that the command logged for the artifact as
  `<SHA256>`, then check it:
  `engine/.venv/bin/python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" engine/data/models/<END>-strategy-b.pkl`.
  The two values must be equal.
- **Timings.** Record from `b1.log` and `/usr/bin/time`:
  - wall time and peak RSS;
  - cache hit or miss (a hit after Step 2a, a miss after 2b);
  - the load, `prepare_b`, candidate table + labels, both `train_folds`, the probe, both
    walk-forward runs, the A2 recompute, and the diagnostics/calibration.

**Sanity read** (to catch bugs, not to tune). Check the `.md` against §6.7 and phase 5's section
list, in order:
1. The title.
2. Data: `<END>`, bar rows, symbols, candidate rows and labelled rows. Both row counts are > 0, and
   labelled ≤ candidate.
3. Method. It names the folds, candidates, the 18 features, the net-of-cost label, the purge, the
   model and its fixed hyperparameters, B-linear as information only, the picks rule (> 0.0), the
   gate, the determinism probe's result, and "one round only".
4. The per-fold training summary for B and B-linear. There are 9 folds (trade years 2018 …
   `<LAST_YEAR>`), each with tune `2015-10-19 → <last session of Y−1>`, rows, label mean, in-fold R²,
   pred mean, positive share and the top 5 features.
5. Results: B, B-linear and A2 against price-only and total-return SPY, from 2018-01-02.
6. Year by year.
7. Diagnostics for B and B-linear: P/L by exit reason and by year, the < 3-share share, cost drag,
   passed nights and the calibration table (10 deciles).
8. "Seen before", 2022-01-03 → `<END>`, labelled information only.
9. The go-live checklist.
10. Survivorship, with the learned-model caveat (handover §2.5).
11. Open positions at the end.
12. The curves: the SVG is linked inline.
13. The verdict sentence.
14. On a fail only, the owner's options (b), (c) and (d) as handover §8 names them.
15. The machine fence.

Then:
- `head -n 2 docs/backtests/<END>-strategy-b-walkforward-equity.csv` shows the header
  `date,b,b_linear,a2,spy_price,spy_tr`.
- The A2 column of the CSV, from 2018-01-02, ends at the same final equity as the `walk-forward`
  column of `$S/a2/2026-10-02-strategy-a2-walkforward-equity.csv` when `<END>` is 2026-10-02. That is
  the information curve D12 recomputes.
- Open the SVG in a browser.

A missing section, a wrong fold window, or an impossible value (negative equity, NaN, SPY as a traded
symbol, an artifact on a failed gate) → **Bug protocol**.

### Step 4: Add the frozen-model test (R8)

**File:** `engine/tests/test_strategy_b_frozen.py` (new). The test passes in either branch and fails
on any drift between code, artifact and report. It has **6 tests**, and every one runs in both
branches. None skips.

**Code:**

```python
"""Strategy B's frozen model agrees with the newest committed P6a report and its artifact.

P6a (docs/handover/2026-10-03-strategy-b-ranker.md §3 "Deployed model" and "One round only"): the
walk-forward report decides, once, whether Strategy B may be deployed. ``b_report.render_markdown``
writes four machine-readable lines into ``docs/backtests/<data end>-strategy-b-walkforward.md``:

    p6a-gate: passed | failed
    gated-model: B | B-linear                 # B-linear only by the pre-registered determinism switch
    last-fold-model: {"kind": ..., "digest": ..., "train_end": ..., "rows": ..., "label_sum": ...}
    frozen-model: null | {"report": ..., "artifact": ..., "train_end": ..., "sha256": ...}

``b_report.parse_machine_line`` reads them back. These tests read the newest committed report and
assert whichever branch it took:

- passed: STRATEGY_B_FROZEN == the report's frozen-model line; it names this report, the artifact
  engine/data/models/<data end>-strategy-b.pkl and the last fold's training cut-off; the artifact's
  sha256 is the constant's; b_model.loads(artifact) has the last-fold-model's kind and digest; and
  the comment above STRATEGY_B_FROZEN in b.py names the report;
- failed: STRATEGY_B_FROZEN is None, the report's frozen-model is null, and no
  *-strategy-b.pkl artifact is committed under engine/data/models/.

So B can never be deployed without a passing report, and the deployed model can never drift from
the evidence without a new report and artifact being committed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

import seer_engine.strategies.b as strategy_b
from seer_engine import config
from seer_engine.backtest.b_report import (
    FROZEN_KEY,
    GATE_KEY,
    GATED_KEY,
    LAST_FOLD_KEY,
    parse_machine_line,
)
from seer_engine.backtest.b_walkforward import B, B_LINEAR
from seer_engine.strategies import b_model
from seer_engine.strategies.b import FEATURE_NAMES, FrozenModel

BACKTESTS_DIR = config.REPO_ROOT / "docs" / "backtests"
MODELS_DIR = config.REPO_ROOT / "engine" / "data" / "models"
REPORT_SUFFIX = "-strategy-b-walkforward.md"
REPORT_GLOB = "*" + REPORT_SUFFIX
ARTIFACT_SUFFIX = "-strategy-b.pkl"
ARTIFACT_GLOB = "*" + ARTIFACT_SUFFIX
PASSED = "passed"
FAILED = "failed"
KIND_OF_GATED = {B: b_model.TREE, B_LINEAR: b_model.RIDGE}
LAST_FOLD_FIELDS = {"kind", "digest", "train_end", "rows", "label_sum"}
HEX64 = re.compile(r"[0-9a-f]{64}")
RERUN = "re-run `python -m seer_engine backtest_b` and commit its report, never edit either by hand"


def _latest_report() -> Path:
    reports = sorted(BACKTESTS_DIR.glob(REPORT_GLOB))
    assert reports, f"no committed P6a report matches {BACKTESTS_DIR / REPORT_GLOB}"
    return reports[-1]  # stems start with the ISO data-end date, so name order is date order


def _text(report: Path) -> str:
    return report.read_text(encoding="utf-8")


def _data_end(report: Path) -> date:
    return date.fromisoformat(report.name[: -len(REPORT_SUFFIX)])


def _repo_relative(path: Path) -> str:
    return path.relative_to(config.REPO_ROOT).as_posix()


def _artifact_relative(data_end: date) -> str:
    return _repo_relative(MODELS_DIR / f"{data_end.isoformat()}{ARTIFACT_SUFFIX}")


def _gate(text: str) -> str:
    gate = parse_machine_line(text, GATE_KEY)
    assert gate in (PASSED, FAILED), f"{GATE_KEY}: expected {PASSED!r} or {FAILED!r}, got {gate!r}"
    return gate


def _json_line(text: str, key: str) -> object:
    raw = parse_machine_line(text, key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise AssertionError(f"'{key}:' is not JSON: {raw!r}") from e


def _last_fold(report: Path, text: str) -> dict[str, object]:
    last = _json_line(text, LAST_FOLD_KEY)
    assert isinstance(last, dict), f"{report.name}: {LAST_FOLD_KEY} is not a JSON object: {last!r}"
    return last


def _frozen_dict(frozen: FrozenModel) -> dict[str, str]:
    return {
        "report": frozen.report,
        "artifact": frozen.artifact,
        "train_end": frozen.train_end.isoformat(),
        "sha256": frozen.sha256,
    }


def test_report_records_a_gate_outcome() -> None:
    report = _latest_report()
    assert _gate(_text(report)) in (PASSED, FAILED)


def test_gated_model_line_names_b_or_b_linear() -> None:
    report = _latest_report()
    gated = parse_machine_line(_text(report), GATED_KEY)
    assert gated in KIND_OF_GATED, (
        f"{report.name}: {GATED_KEY} must be {B!r} or {B_LINEAR!r} (the pre-registered switch), got {gated!r}"
    )


def test_last_fold_line_is_a_valid_model_record() -> None:
    report = _latest_report()
    text = _text(report)
    gated = parse_machine_line(text, GATED_KEY)
    last = _last_fold(report, text)
    assert set(last) == LAST_FOLD_FIELDS, (
        f"{report.name}: {LAST_FOLD_KEY} has fields {sorted(last)}, expected {sorted(LAST_FOLD_FIELDS)}"
    )
    assert last["kind"] == KIND_OF_GATED.get(gated), (
        f"{report.name}: {GATED_KEY} is {gated!r} but the last fold's model kind is {last['kind']!r}"
    )
    digest = last["digest"]
    assert isinstance(digest, str) and HEX64.fullmatch(digest), (
        f"{report.name}: {LAST_FOLD_KEY} digest {digest!r} is not a lowercase sha256 hex digest"
    )
    train_end = last["train_end"]
    assert isinstance(train_end, str), f"{report.name}: train_end {train_end!r} is not an ISO date string"
    assert date.fromisoformat(train_end) < _data_end(report), (
        f"{report.name}: the last fold trained through {train_end}, not before the data end {_data_end(report)}"
    )
    rows = last["rows"]
    assert isinstance(rows, int) and not isinstance(rows, bool) and rows > 0, (
        f"{report.name}: {LAST_FOLD_KEY} rows {rows!r} is not a positive int"
    )
    raw_sum = last["label_sum"]
    assert isinstance(raw_sum, str), (
        f"{report.name}: {LAST_FOLD_KEY} label_sum {raw_sum!r} must be a JSON string holding repr(float)"
    )
    label_sum = float(raw_sum)
    assert math.isfinite(label_sum) and repr(label_sum) == raw_sum, (
        f"{report.name}: {LAST_FOLD_KEY} label_sum {raw_sum!r} is not the repr of a finite float"
    )


def test_code_constant_equals_report_frozen_line() -> None:
    STRATEGY_B_FROZEN = strategy_b.STRATEGY_B_FROZEN  # read at call time, never a stale import copy
    report = _latest_report()
    frozen = _json_line(_text(report), FROZEN_KEY)
    if STRATEGY_B_FROZEN is None:
        assert frozen is None, f"STRATEGY_B_FROZEN is None but {report.name} {FROZEN_KEY} is {frozen}; {RERUN}"
        return
    expected = _frozen_dict(STRATEGY_B_FROZEN)
    assert isinstance(frozen, dict) and frozen == expected, (
        f"STRATEGY_B_FROZEN {expected} differs from {report.name} {FROZEN_KEY} {frozen}; {RERUN}"
    )


def test_freeze_follows_the_gate() -> None:
    STRATEGY_B_FROZEN = strategy_b.STRATEGY_B_FROZEN  # read at call time, never a stale import copy
    report = _latest_report()
    text = _text(report)
    if _gate(text) == FAILED:
        assert STRATEGY_B_FROZEN is None, (
            f"{report.name} says the P6a gate failed, so STRATEGY_B_FROZEN must stay None "
            f"(B's one round failed on this data); it is {STRATEGY_B_FROZEN!r}"
        )
        assert parse_machine_line(text, FROZEN_KEY) == "null", (
            f"{report.name}: a failed gate must record {FROZEN_KEY}: null"
        )
        return
    assert STRATEGY_B_FROZEN is not None, (
        f"{report.name} says the P6a gate passed; set STRATEGY_B_FROZEN in strategies/b.py to the "
        "artifact backtest_b wrote, then re-run backtest_b so the report records it"
    )
    last = _last_fold(report, text)
    assert STRATEGY_B_FROZEN.report == _repo_relative(report), (
        f"STRATEGY_B_FROZEN.report {STRATEGY_B_FROZEN.report!r} is not {_repo_relative(report)!r}"
    )
    assert STRATEGY_B_FROZEN.artifact == _artifact_relative(_data_end(report)), (
        f"STRATEGY_B_FROZEN.artifact {STRATEGY_B_FROZEN.artifact!r} is not "
        f"{_artifact_relative(_data_end(report))!r}"
    )
    assert isinstance(STRATEGY_B_FROZEN.train_end, date), (
        f"STRATEGY_B_FROZEN.train_end {STRATEGY_B_FROZEN.train_end!r} is not a date"
    )
    assert STRATEGY_B_FROZEN.train_end.isoformat() == last["train_end"], (
        f"STRATEGY_B_FROZEN.train_end {STRATEGY_B_FROZEN.train_end} is not the last fold's "
        f"training cut-off {last['train_end']} in {report.name}"
    )
    source = Path(strategy_b.__file__).read_text(encoding="utf-8")
    assert f"docs/backtests/{report.name}" in source, (
        f"the comment above STRATEGY_B_FROZEN in {Path(strategy_b.__file__).name} must name "
        f"docs/backtests/{report.name}"
    )


def test_artifact_follows_the_gate() -> None:
    STRATEGY_B_FROZEN = strategy_b.STRATEGY_B_FROZEN  # read at call time, never a stale import copy
    report = _latest_report()
    text = _text(report)
    artifacts = sorted(MODELS_DIR.glob(ARTIFACT_GLOB))
    if _gate(text) == FAILED:
        assert artifacts == [], (
            f"{report.name} says the P6a gate failed, so no Strategy B model may be committed; "
            f"found {[_repo_relative(p) for p in artifacts]}"
        )
        return
    assert STRATEGY_B_FROZEN is not None, f"{report.name} says the P6a gate passed but STRATEGY_B_FROZEN is None"
    path = config.REPO_ROOT / STRATEGY_B_FROZEN.artifact
    assert path.is_file(), f"the frozen artifact {STRATEGY_B_FROZEN.artifact} is not committed"
    assert artifacts and artifacts[-1] == path, (
        f"the newest artifact {[_repo_relative(p) for p in artifacts][-1:]} is not the frozen one "
        f"{STRATEGY_B_FROZEN.artifact}"
    )
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    assert actual == STRATEGY_B_FROZEN.sha256, (
        f"{STRATEGY_B_FROZEN.artifact} has sha256 {actual}, but STRATEGY_B_FROZEN.sha256 is "
        f"{STRATEGY_B_FROZEN.sha256}; never edit the artifact by hand"
    )
    model = b_model.loads(data)
    last = _last_fold(report, text)
    assert model.kind == last["kind"], (
        f"{STRATEGY_B_FROZEN.artifact} holds a {model.kind!r} model; {report.name} says {last['kind']!r}"
    )
    assert model.digest == last["digest"], (
        f"{STRATEGY_B_FROZEN.artifact} loads to digest {model.digest}, but {report.name}'s "
        f"{LAST_FOLD_KEY} digest is {last['digest']}"
    )
    assert model.n_features == len(FEATURE_NAMES), (
        f"{STRATEGY_B_FROZEN.artifact} expects {model.n_features} features, Strategy B has {len(FEATURE_NAMES)}"
    )
```

Notes for the implementer:
- A missing report is an assertion failure, not a skip, which is intended: CI treats skips as
  failures, and it must also fail on a missing report. So the test and the report land in the
  **same commit** (Step 9).
- The test reads machine lines only through `b_report.parse_machine_line` and the four keys, never
  with a regex of its own. If phase 5 renders `frozen-model` as anything other than the literal
  `null` for `None`, or `train_end` as anything other than an ISO date, that contradicts the plan
  index contract. Fix it in `b_report.py` under the Bug protocol.
- The test asserts the `last-fold-model` *field set*, not its key order. The key order is phase 5's
  rendering and stays byte-stable without this test.
- `REPORT_GLOB` ends in `-strategy-b-walkforward.md`, so it never matches an A or A2 report. The A
  and A2 frozen tests' globs (`*-strategy-a.md` and `*-strategy-a2-walkforward.md`) never match a B
  report.
- `b_model.loads` imports scikit-learn. The test runs under `engine[dev]`, which installs it locally
  and in CI.
- **Red step, run it now:**
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_strategy_b_frozen.py -q`.
  - **Fail branch:** all 6 pass already.
  - **Pass branch, before Step 5:** `test_freeze_follows_the_gate` and
    `test_artifact_follows_the_gate` fail, because the constant is still `None`. The other 4 pass.
  - **Pass branch, after Step 5 and before Step 6:** only
    `test_code_constant_equals_report_frozen_line` fails, because the run #1 report still says
    `frozen-model: null`.

**Impact:** one new test file and no source change. The suite grows by exactly **6** tests.

### Step 5: Freeze or stop (R8)

**File:** `engine/src/seer_engine/strategies/b.py`, at the `STRATEGY_B_FROZEN` assignment and the
two placeholder comment lines directly above it. Find them with
`grep -n -B2 "^STRATEGY_B_FROZEN" engine/src/seer_engine/strategies/b.py`.

**Branch FAIL (`p6a-gate: failed`):**
- Change nothing in `b.py`. `STRATEGY_B_FROZEN` stays `None`, with phase 2's comment.
- `engine/data/models/` must not exist. `test -e engine/data/models && echo BUG` must print nothing,
  because an artifact on a failed gate is a phase 6 bug.
- Go to Step 6.

**Branch PASS (`p6a-gate: passed`):** print the literal from the report and the artifact, so no
value is typed by hand:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
engine/.venv/bin/python - <<'PY' | tee "$S/frozen-literal.txt"
import hashlib, json, pathlib
from datetime import date
from seer_engine.backtest.b_report import GATE_KEY, GATED_KEY, LAST_FOLD_KEY, parse_machine_line
from seer_engine.strategies import b_model

report = sorted(pathlib.Path("docs/backtests").glob("*-strategy-b-walkforward.md"))[-1]
text = report.read_text(encoding="utf-8")
assert parse_machine_line(text, GATE_KEY) == "passed", "not a passing report"
end = report.name[: -len("-strategy-b-walkforward.md")]
artifact = pathlib.Path("engine/data/models") / f"{end}-strategy-b.pkl"
data = artifact.read_bytes()
last = json.loads(parse_machine_line(text, LAST_FOLD_KEY))
model = b_model.loads(data)
assert model.digest == last["digest"] and model.kind == last["kind"], (model.kind, model.digest, last)
t = date.fromisoformat(last["train_end"])
print(f"# gated: {parse_machine_line(text, GATED_KEY)}  rows: {last['rows']}  label_sum: {last['label_sum']}")
print("STRATEGY_B_FROZEN: FrozenModel | None = FrozenModel(")
print(f'    report="docs/backtests/{report.name}",')
print(f'    artifact="{artifact.as_posix()}",')
print(f"    train_end=date({t.year}, {t.month}, {t.day}),")
print(f'    sha256="{hashlib.sha256(data).hexdigest()}",')
print(")")
PY
```

Replace phase 2's two placeholder comment lines and the `= None` line with the block below. Fill
the bracketed comment values from Step 3, take the six code lines verbatim from
`frozen-literal.txt`, and keep every other character:

```python
# Frozen by P6a (Strategy B, ML cross-sectional ranker under anchored yearly walk-forward), run on
# Neon data through <END>. The deployed model is the gated curve's (<GATED>) last-fold model: trade
# year <LAST_YEAR>, fit only on labels resolved on or before <TRAIN_END> (<TRAIN_ROWS> rows, label sum
# <LABEL_SUM>), with the pre-registered features, label and hyperparameters. The walk-forward
# 2018-01-02..<END> traded only out-of-fold models and beat total-return SPY with PF >= 1.3 and
# max DD <= 15%. Gate verdict: PASSED.
# Report: docs/backtests/<END>-strategy-b-walkforward.md
# Artifact: engine/data/models/<END>-strategy-b.pkl (b_model.dumps; load with b_model.loads, scikit-learn 1.9.x)
# tests/test_strategy_b_frozen.py fails if code, artifact and report drift apart.
# Changing it resets the forward clock: re-run `seer_engine backtest_b` and commit its report and artifact.
STRATEGY_B_FROZEN: FrozenModel | None = FrozenModel(
    report="docs/backtests/<END>-strategy-b-walkforward.md",
    artifact="engine/data/models/<END>-strategy-b.pkl",
    train_end=date(<YYYY>, <M>, <D>),
    sha256="<SHA256>",
)
```

For example, with `<END>` = 2026-10-02, gated B and a 2025-12-31 cut-off, the code lines read:
`report="docs/backtests/2026-10-02-strategy-b-walkforward.md"`,
`artifact="engine/data/models/2026-10-02-strategy-b.pkl"`, `train_end=date(2025, 12, 31)` and
`sha256="<64 hex chars from frozen-literal.txt>"`.

Cross-check before saving: run #1's log (Step 3) holds phase 6's WARNING line
`... set STRATEGY_B_FROZEN = FrozenModel(report='docs/backtests/<END>-strategy-b-walkforward.md', artifact='engine/data/models/<END>-strategy-b.pkl', train_end=date(Y, M, D), sha256='…') ...`.
Its four values must equal `frozen-literal.txt`'s (only the quote style differs). The sha256 is
always `sha256(file bytes)`; never derive it from `b_model.dumps(b_model.loads(bytes))`, because
re-pickling an unpickled tree can change a few framing bytes (Decision D25). A mismatch is a
Bug-protocol finding in phase 6.

Verify:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
engine/.venv/bin/python -c "from seer_engine.strategies.b import STRATEGY_B_FROZEN as f; print(f)"
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  engine/.venv/bin/pytest engine/tests/test_strategy_b_frozen.py engine/tests/test_strategy_purity.py -q
```

`test_code_constant_equals_report_frozen_line` must be the only failure, and it stays failing until
Step 6. The purity test must pass, because `b.py` gained no import.

**Impact:** only what the report records as frozen. No walk-forward run reads `STRATEGY_B_FROZEN`
(phase 6 reads it only into `BReport.frozen`), so no number moves. P4 will read this constant.

### Step 6: Re-run (pass: records `frozen-model`; fail: byte-identity), fingerprint post-check

**File:** regenerates the three `docs/backtests/<END>-strategy-b-walkforward*` files, and on a pass
also the artifact.

**Pass branch.** This re-run is required: it makes the report record `frozen-model`.

**Fail branch.** This re-run is a reproducibility check on real data before anything is committed.
It changes no file, it is cheap, and it catches a non-determinism bug the synthetic tests missed.
The requirement itself (R5) belongs to phases 1, 4, 5 and 6. This step only measures it.

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
SEER_ENV_FILE=/home/miftah/seer/.env.local /usr/bin/time -v \
  engine/.venv/bin/python -m seer_engine backtest_b --out docs/backtests \
  > "$S/b2.out" 2> "$S/b2.log"; echo "exit=$?"
for f in "$S"/b1/*-strategy-b-walkforward*; do n=$(basename "$f"); cmp "$f" "docs/backtests/$n" && echo "same $n"; done
test -e "$S/b1/<END>-strategy-b.pkl" && cmp "$S/b1/<END>-strategy-b.pkl" engine/data/models/<END>-strategy-b.pkl && echo "same artifact"
diff "$S/b1/<END>-strategy-b-walkforward.md" "docs/backtests/<END>-strategy-b-walkforward.md"
grep -E '^(p6a-gate|gated-model|last-fold-model|frozen-model): ' docs/backtests/<END>-strategy-b-walkforward.md | tee "$S/machine2.txt"
```

Acceptance:
- Exit 0, a cache hit in the log, and still exactly three report files with the same stem.
- **FAIL branch:**
  - three `same` lines, an empty `diff`, and still no `engine/data/models/`;
  - `machine2.txt` == `machine1.txt`.
- **PASS branch:**
  - `-equity.csv` and `-equity.svg` print `same`, and `same artifact` prints: the artifact is
    rewritten byte-identically.
  - In the `.md`, `diff` shows only lines rendered from `BReport.frozen`: the `frozen-model:` line,
    which goes from `null` to the JSON, plus any sentence phase 5 renders from `frozen`.
  - Every number, table, fold summary, the verdict sentence, `p6a-gate:`, `gated-model:` and
    `last-fold-model:` are unchanged.
- Any other difference → **Bug protocol** (non-determinism, or `frozen` leaking into a result).

Then run the frozen test again. All 6 must pass in either branch:

```sh
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  engine/.venv/bin/pytest engine/tests/test_strategy_b_frozen.py -q
```

**Post-check (Rule 5):** re-run the Step 1c snippet into `"$S/fingerprint-after.txt"`, then run
`diff "$S/fingerprint-before.txt" "$S/fingerprint-after.txt"`. The diff must be empty. If it is
not, discard every output and restart at Step 2.

### Step 7: Timings for the readme

**File:** none. This step only measures, and nothing from it is committed.

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
SEER_ENV_FILE=/home/miftah/seer/.env.local timeout 900 engine/.venv/bin/python - <<'PY' | tee "$S/timings.txt"
import time
from contextlib import closing
from seer_engine import db
from seer_engine.backtest import io
from seer_engine.strategies.b import STRATEGY_B

t0 = time.perf_counter()
with closing(db.connect()) as conn:
    market, rows = io.load_market(conn)
t1 = time.perf_counter()
prepared = STRATEGY_B.prepare(market.history)
t2 = time.perf_counter()
print(f"bars_rows={rows} symbols={len(market.history)} load_warm_s={t1 - t0:.2f} prepare_b_s={t2 - t1:.2f} "
      f"prepared_rows={len(prepared.dates)}")
PY
grep -iE "cache|load|prepar|candidate|label|fit|train|probe|determin|walk|B-linear|A2|tune|calibrat|passed|gate|artifact|sha256|wrote" "$S/b1.log" | tail -n 120 | tee -a "$S/timings.txt"
grep -E "Elapsed \(wall clock\)|Maximum resident set size" "$S"/b1.log "$S"/b2.log "$S"/a2.log | tee -a "$S/timings.txt"
ls -l engine/.cache/ | tee -a "$S/timings.txt"
test -e engine/data/models && ls -l engine/data/models/ | tee -a "$S/timings.txt"
git status --porcelain | tee -a "$S/timings.txt"   # engine/.cache must not appear
```

Record these values, with seconds to 1 dp, MB as whole numbers, and wall clock as `m:ss`:
- `ROWS`, `SYMBOLS`, `CANDIDATE_ROWS`, `LABELLED_ROWS` and `N_FOLDS` (from the report's data
  section and fold table);
- `LOAD_COLD_S` (from `a2.log` on path 2a, else from `b1.log`), `LOAD_WARM_S` and `PREPARE_B_S`;
- `TABLE_S`: the candidate table plus the labels over `CANDIDATE_ROWS` rows;
- `FIT_TREE_S` and `FIT_RIDGE_S`: the 9 fits each, in total;
- `PROBE_S`: the determinism probe's two refits;
- `RUNS_S`: the B and B-linear walk-forward runs, with their SPY curves;
- `A2_S`: the A2 recompute (D12);
- `DIAG_S`: the diagnostics, calibration and passed nights;
- `B1_WALL`, `B2_WALL` and `PEAK_RSS_MB` (the larger of b1 and b2, KB / 1024);
- `A2_WALL`, from `a2.log` (Step 2a only, else "n/a");
- `CACHE_MB`;
- `ARTIFACT_KB` (pass only).

Phase 6's log lines decide which of these exist. Where phase 6 merges two steps into one log line,
record the merged value and word the readme bullet to match. The machine is WSL2, Python 3.11.

If `B1_WALL` is more than 60 minutes, note it for Step 8 and **Handoffs**.

### Step 8: Commit the run

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  engine/.venv/bin/pytest engine/tests -q -rs | tee "$S/suite-mid.out"
grep -c '^SKIPPED' "$S/suite-mid.out"   # 0; passed == <N6> + 6
git add docs/backtests/ engine/tests/test_strategy_b_frozen.py
git add engine/src/seer_engine/strategies/b.py engine/data/models/   # PASS branch only
git status --porcelain                                              # only those paths; no engine/.cache, no 2026-10-02-* change
git commit -F "$S/commit-run.txt"
```

`git status` must show **no** change to `docs/backtests/2026-10-02-*`, because Step 2 wrote only to
`$S/a2`.

`$S/commit-run.txt`. Fill the bracketed values, and keep exactly one of each `PASS:`/`FAIL:`
alternative, without its label:

```text
feat(backtest): P6a real walk-forward run on Neon — Strategy B <frozen|not frozen, gate failed>

One read-only run of `python -m seer_engine backtest_b` on Neon data through <END>
(<ROWS> bar rows, <SYMBOLS> symbols; <CANDIDATE_ROWS> candidate rows, <LABELLED_ROWS> labelled).
Report: docs/backtests/<END>-strategy-b-walkforward.md (+ -equity.csv, -equity.svg), generated by
the command, never edited.

P3b's anchored yearly folds (<N_FOLDS>, trade years 2018..<LAST_YEAR>); per fold, B (fixed-
hyperparameter HistGradientBoostingRegressor) and B-linear (ridge, information only) fit on the
purged net-of-cost labels resolved by tune_end; one continuous portfolio 2018-01-02..<END>.
Determinism probe on the last fold: <bit-identical|differs>, so the gated model is <GATED>.

Gate: <PASSED|FAILED>. <VERDICT_SENTENCE>

PASS: STRATEGY_B_FROZEN names the report, engine/data/models/<END>-strategy-b.pkl
PASS: (sha256 <SHA256>) and the training cut-off <TRAIN_END>; the report was re-run after freezing
PASS: and records it, and the artifact was rewritten byte-identically.
FAIL: STRATEGY_B_FROZEN stays None and no artifact is committed. B's one round has failed on this
FAIL: data; B is not reworked on it, and P4 stays blocked.

tests/test_strategy_b_frozen.py (6 tests) ties code, artifact and report together in either branch.
Run #2 reproduced every file byte-identically (PASS: except the frozen-model line(s)).
A2 check (R4): <A2_METHOD>; all five 2026-10-02-strategy-a2-walkforward* files byte-identical.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
```

### Step 9: `engine/package_readme.md`

**File:** `engine/package_readme.md`. The line numbers are as of `0e91d8a`, and phases 1–6 do not
edit this file. Apply the edits **bottom-up** (9n first, 9a last), so the earlier line numbers stay
valid.

Before writing, check every claim against the landed code:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
cat "$S/help-b.txt"
grep -n "^def \|^class \|^[A-Z_0-9]* *[:=]" engine/src/seer_engine/strategies/b_model.py engine/src/seer_engine/strategies/b.py \
  engine/src/seer_engine/backtest/{labels,b_walkforward,b_report,io}.py engine/src/seer_engine/commands/backtest_b.py
grep -n "^def mean_window\|^def stdev_return_window" engine/src/seer_engine/strategies/indicators.py
grep -n "^from\|^import" engine/src/seer_engine/strategies/{b_model,b}.py engine/src/seer_engine/backtest/{labels,b_walkforward,b_report,io}.py engine/src/seer_engine/commands/backtest_b.py
grep -n "b\b\|from .b import\|__all__" engine/src/seer_engine/strategies/__init__.py
grep -n "Error\|return 2\|raise " engine/src/seer_engine/commands/backtest_b.py
grep -n "scikit" engine/pyproject.toml
```

**Where the code differs from this text, the code wins.** Adjust the sentence, never the code. For
example, if phase 6 names its error class differently or adds an exit-2 case, describe what is
there.

Replace every `{{TOKEN}}`. Where a block has PASS and FAIL alternatives, keep exactly one, and drop
its label. Step 10 greps for leftovers.

| Token | Value |
|---|---|
| `{{TODAY}}` | the commit date |
| `{{END}}`, `{{ROWS}}`, `{{SYMBOLS}}`, `{{CANDIDATE_ROWS}}`, `{{LABELLED_ROWS}}`, `{{N_FOLDS}}`, `{{LAST_YEAR}}`, `{{TRAIN_END}}`, `{{TRAIN_ROWS}}`, `{{LABEL_SUM}}` | Steps 3 and 7 |
| `{{GATED}}` | `B` or `B-linear`, from `gated-model:` |
| `{{PROBE_RESULT}}` | `bit-identical at 1 thread and at the default, so B is gated` or `not bit-identical, so the pre-registered switch gated B-linear` |
| `{{VERDICT_SENTENCE}}` | verbatim from the report |
| `{{PASSED_OR_FAILED}}` | `PASSED` or `FAILED`, from `p6a-gate:` |
| `{{SHA256}}` | the pass artifact's sha256 |
| `{{A2_METHOD}}` | Step 2 |
| `{{NEVER_FETCHED}}` | the report's survivorship count of members with no bars at all |
| `{{LOAD_COLD_S}}`, `{{LOAD_WARM_S}}`, `{{PREPARE_B_S}}`, `{{TABLE_S}}`, `{{FIT_TREE_S}}`, `{{FIT_RIDGE_S}}`, `{{PROBE_S}}`, `{{RUNS_S}}`, `{{A2_S}}`, `{{DIAG_S}}`, `{{B1_WALL}}`, `{{B2_WALL}}`, `{{PEAK_RSS_MB}}`, `{{CACHE_MB}}`, `{{ARTIFACT_KB}}` | Step 7 |

**9n. Notes (after line 904, the end of the file).** Append:

```markdown

The P6a sections (`strategies.b_model`, `strategies.b`, the labeler, the B walk-forward and report
modules, the `backtest_b` command and the committed P6a report) were added on {{TODAY}}. Their
design, invariants and decisions are in `STRATEGY_B_RANKER_PLAN.md` and
`docs/handover/2026-10-03-strategy-b-ranker.md`.
```

**9m. Usage (after line 880, the end of `### Backtest: walk-forward (P3b)`, before line 882 `### Gotchas`).** Insert:

````markdown

### Backtest: Strategy B walk-forward (P6a)

```
cd <repo or worktree root>
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine backtest_b
```

Then read `docs/backtests/<data end>-strategy-b-walkforward.md`. Its `p6a-gate:`, `gated-model:`,
`last-fold-model:` and `frozen-model:` lines are what `test_strategy_b_frozen.py` reads:

- On a passing report, `backtest_b` also writes `engine/data/models/<data end>-strategy-b.pkl` and
  logs its sha256. `STRATEGY_B_FROZEN` must name the report, that artifact, its sha256 and the last
  fold's `train_end`. The artifact must load (`b_model.loads`) to the `last-fold-model:` digest, and
  the comment above the constant must name the report. Re-run after freezing, so the report records
  `frozen-model:`.
- On a failing report, the constant must be `None`, and no `*-strategy-b.pkl` may be committed.

A newer report with a different outcome or model fails the test until the constant and the artifact
follow it. Committing a newer report is a re-measurement on new data, not a new round.
````

**PASS branch only:** directly after that block, also insert:

````markdown

### Strategy B: P4 nightly picks

```python
from seer_engine import config, dates
from seer_engine.sim import size_picks
from seer_engine.strategies import b_model
from seer_engine.strategies.b import SPY_SYMBOL, STRATEGY_B, STRATEGY_B_FROZEN, BParams
from seer_engine.strategies.base import history_from_bars

data = (config.REPO_ROOT / STRATEGY_B_FROZEN.artifact).read_bytes()
assert b_model.sha256(data) == STRATEGY_B_FROZEN.sha256      # the committed artifact, untouched
params = BParams(b_model.loads(data))                        # scikit-learn 1.9.x (pinned)

rd = dates.run_dates()
members = universe.members_on(conn, rd.data_date)
# At least STRATEGY_B.lookback (200) bars ending at rd.data_date for every member AND for SPY:
# SPY's 3 features are read from the same mapping. SPY is never a pick.
symbols = sorted(members | {SPY_SYMBOL})
history = {s: history_from_bars(s, bars) for s, bars in last_bars_by_symbol(conn, rd.data_date, symbols).items()}
picks = STRATEGY_B.picks(history, members, rd.data_date, params)  # [] on a night with no positive prediction
sized = size_picks(result.portfolio, picks, rd.session_date)        # after settling data_date
```

This is the model the committed walk-forward's last fold trained, so a night's picks are the
backtest's picks for that date, given the same bars.
````

**9l. Performance (after line 743, the P3b whole-command sub-bullet, before line 744 `- There is no benchmark coverage for the DB writers.`).** Insert, matching the sub-bullets to Step 7's log lines:

```markdown
- Strategy B walk-forward (P6a), measured on the {{END}} data ({{ROWS}} bar rows, {{SYMBOLS}} symbols), WSL2, Python 3.11, scikit-learn 1.9:
  - Load: {{LOAD_WARM_S}} s from the {{CACHE_MB}} MB pickle cache (about {{LOAD_COLD_S}} s from Neon on a miss). `STRATEGY_B.prepare` (the 18 raw window columns for every (symbol, date) with 200 bars, plus SPY's 3): {{PREPARE_B_S}} s, once per command.
  - Candidate table and labels: {{CANDIDATE_ROWS}} candidate rows ranked per date and labelled by the vectorized bracket labeler ({{LABELLED_ROWS}} with a valid bracket and a resolved label) in {{TABLE_S}} s. It is one numpy pass per session offset over the still-open rows, not one `sim.step` per row.
  - Fits: {{N_FOLDS}} tree fits in {{FIT_TREE_S}} s and {{N_FOLDS}} ridge fits in {{FIT_RIDGE_S}} s, sequential, in fold order. The determinism probe (the last fold's tree refit at 1 thread and at the default) took {{PROBE_S}} s.
  - The B and B-linear walk-forward runs (2018-01-02 → {{END}}) and their SPY curves: {{RUNS_S}} s. The A2 information curve, recomputed through `backtest_wf`'s pipeline (D12): {{A2_S}} s. Diagnostics, calibration and passed nights: {{DIAG_S}} s.
  - Whole command: {{B1_WALL}} for the first run, {{B2_WALL}} for the re-run; peak RSS {{PEAK_RSS_MB}} MB.
```

PASS only: append the sub-bullet `  - The frozen artifact is {{ARTIFACT_KB}} KB.`

If `B1_WALL` is more than 60 minutes, append to the whole-command sub-bullet: `Above the handover's
60-minute threshold; a process pool gathered in fold order is a follow-up (it changes no number).`

**9k. Reverse Dependencies (after line 706, the P3b "P4 is blocked" bullet).** Insert exactly one of:

PASS:
```markdown
- P4 (nightly) runs Strategy B: `strategies.b.STRATEGY_B.picks(...)` with `BParams(b_model.loads(<artifact>))`, the artifact named by `STRATEGY_B_FROZEN` (sha256-checked), and SPY's last 200 bars in `history` beside the members'. Writing the frozen model's identity to `strategies.params` is P4's job. `STRATEGY_A_PARAMS` and `STRATEGY_A2_PARAMS` stay the records of P3 and P3b.
```
FAIL:
```markdown
- P4 stays blocked: the P6a gate failed, `STRATEGY_B_FROZEN` is `None`, and no model artifact is committed. Nothing may deploy Strategy A, A2 or B. B's one round has failed on this data. The owner chooses among the report's options (b), (c) and (d).
```

**9j. Internal module graph (after line 697, the `backtest.io` / `commands.backtest_wf` bullet).** Insert, adjusted to the `grep -n "^from\|^import"` output:

```markdown
- `strategies.b_model` imports numpy, scikit-learn (`HistGradientBoostingRegressor`), `threadpoolctl`, `pickle` and `hashlib`, and nothing from the engine. scikit-learn loads none of psycopg, requests or yfinance, so the module stays pure. `strategies.b` imports numpy, `sim` (`Pick`), `strategies.a` (`_bracket`, `Features`, `DESIGN_PARAMS`, `LOOKBACK`), `strategies.base` and `strategies.indicators`. It never imports `b_model`, so `import seer_engine.strategies` does not load scikit-learn, and never `universe` (psycopg), so `SPY_SYMBOL` repeats `universe.BENCHMARK` and a test asserts they are equal.
- `backtest.labels` imports numpy, `dates`, `strategies.base` and `sim` (`COST_RATE`, which a test pins). `backtest.b_walkforward` imports `dates`, `strategies.b`, `strategies.b_model`, `backtest.labels`, `runner`, `metrics`, `market`, `walkforward` (`Fold`, `folds`, `diagnostics`, `window_metrics`, `curve_window_metrics`) and `tuning` (`Verdict`). `backtest.b_report` imports `backtest.report`'s and `wf_report`'s helpers (read-only), `strategies.b`, and `backtest.b_walkforward`, `metrics`, `runner`, `benchmark` and `walkforward`. None of them imports `bars`, `db`, `http` or `config`.
- `backtest.io` also imports `b_report` and `strategies.b_model` (for `write_b_report` and `write_model_artifact`). `commands.backtest_b` imports `config`, `db`, `dates`, `universe` (for `BENCHMARK`), `backtest.io`, `b_walkforward`, `b_report`, `walkforward`, `benchmark`, `market`, `metrics`, `runner`, `commands.backtest_wf` (`resolve`, `tune_all`, `run_walk_forward`), `commands.backtest` (`never_fetched_members`), `strategies.a2` and `strategies.b`.
```

**9i. External dependencies (after line 684, the `yfinance` bullet, before line 685 `- dev: pytest>=8.`).** Insert:

```markdown
- `scikit-learn>=1.9,<1.10` (P6a): Strategy B's `HistGradientBoostingRegressor`, used only by `strategies.b_model`. The minor version is pinned, because a frozen model is a pickle of its estimator, and `b_model`'s digest reads the fitted trees' private node arrays. It brings `threadpoolctl` (used to cap the threads in the determinism probe), `joblib` and `scipy`.
```

**9h. B walk-forward API (after line 655, the end of the P3b **Survivorship** paragraph, before line 657 `## Migration 002`).** Insert:

````markdown

### backtest Strategy B walk-forward (P6a)

This adds to P3 and P3b without changing them. `walkforward.py`, `wf_report.py` and `backtest_wf.py`
are not edited, so A2's P3b report re-renders byte-identically on its own data (checked by
{{A2_METHOD}}). Like the rest of `backtest/`, every module here except `io.py` is pure, and the
purity glob covers it.

- **`backtest.labels`**:
  - `REASONS = ("expire", "tp", "sl", "gap", "time", "forced")`, with `code = index` and -1 for
    unresolved. `COST = 0.001`, which equals `float(sim.COST_RATE)` (tested).
  - `Labels(label, resolved, reason, fill, exit)`: arrays per row.
  - `label_orders(history, symbols, data_dates, limit, tp, sl, end) -> Labels` puts one bracket order
    per row, alone, under design §5 exactly as `sim.step` and the runner apply it, on NYSE sessions,
    reading bars dated ≤ `end` only:
    - The order session is `next_session(data_date)`. With no bar there, or low ≥ limit, the result
      is `expire`, label 0.0.
    - Otherwise it fills at min(open, limit), with no exit check on the fill session.
    - On each later session, in order: the day-5 time stop at the open; a gap through SL or TP at
      the open; SL intraday (first on a both-in-range bar); TP intraday. A session without a bar
      still counts toward the time stop.
    - A symbol whose bars end exits at its last close (`forced`).
    - Anything not resolved by `end` is unresolved (NaN / NaT / -1).
  - `label = exit × (1 − 0.001) ÷ (fill × (1 + 0.001)) − 1`, per share, so it does not depend on
    the share count. `resolved` is the exit session, or the expiry session when unfilled.
  - It is vectorized: session-aligned float matrices, one numpy pass per session offset over the
    still-open rows. A test proves it agrees with a one-order `run_backtest` on a seeded sample:
    the same reason, the same exit date, and the return within 1e-6.
- **`backtest.b_walkforward`**:
  - `B = "B"` and `B_LINEAR = "B-linear"` (curve names), `DECILES = 10`, `TOP_FEATURES = 5`.
  - `candidate_table(market, prepared, is_start, end) -> CandidateTable`: every candidate row from
    `prev_session(is_start)` through `prev_session(end)`, ordered by `(data_date, symbol)`. Its `X`
    equals that date's `Design` rows bit for bit. It carries the `b.bracket` prices (NaN when
    invalid) and `labels` from `label_orders(..., end=end)`.
  - `training_mask(table, fold)` is **the purge**. It keeps rows with a valid bracket whose label
    resolved on or before `fold.tune_end`, with `data_date ≥ prev_session(fold.tune_start)`. A trade
    still open at `tune_end` is excluded.
  - `train_folds(table, folds, kind) -> tuple[FoldModel, ...]`, sequential and in fold order.
    `FoldModel(fold, model, rows, label_mean, label_sum, pred_mean, r2, positive_share, importance)`:
    the in-fold values are information only.
  - `probe_determinism(table, fold) -> bool`: the fold's tree fit at 1 thread and at the default
    give equal digests.
  - `model_schedule(folds, fold_models)` gives a `ParamsSchedule` of `BParams` that switches at each
    year's first session. `walk_forward_b(market, prepared, folds, fold_models, name) -> BWalkForward`
    is one continuous portfolio from the first trade session to the data end.
  - `oos_predictions`, `calibration(pred, label) -> tuple[CalibrationRow, ...]` (10 deciles of the
    out-of-fold prediction, with mean predicted vs realized label) and
    `passed_nights(table, folds, fold_models) -> (passed, traded)`. These **explain** the result and
    never select anything.
  - `gate_p6a(wf, spy_tr, start, end, gated) -> Verdict`.
- **`backtest.b_report`**:
  - `BReport`, `report_stem(data_end)` (`<data end>-strategy-b-walkforward`), `render_markdown`,
    `equity_csv` (`date,b,b_linear,a2,spy_price,spy_tr`) and `equity_svg` (B, B-linear, A2 and both
    SPY curves). It is deterministic: two renders are byte-equal.
  - The machine lines are `p6a-gate:` (`GATE_KEY`), `gated-model:` (`GATED_KEY`),
    `last-fold-model:` (`LAST_FOLD_KEY`: kind, digest, `train_end`, rows and `label_sum`, the retrain
    recipe) and `frozen-model:` (`FROZEN_KEY`, `null` when nothing is frozen). Read them with
    `parse_machine_line(markdown, key) -> str`.
- **`backtest.io`**:
  - `write_b_report(out_dir, report) -> list[Path]` renders the three files before writing any.
  - `MODELS_DIR` (`engine/data/models`).
  - `write_model_artifact(model_dir, data_end, model) -> (path, sha256)` writes
    `b_model.dumps(model)` to `<data end>-strategy-b.pkl`.

**Folds, training and trading.**
- The folds are exactly P3b's (`walkforward.folds`): fold Y trains on 2015-10-19 → the last session
  of Y−1 and trades Y, for 2018 → the data end. No fold selects anything: each one just fits B and
  B-linear on its purged rows.
- The traded segments form **one** portfolio: 20,000,000 IDR at `prev_session(2018-01-02)`'s FX,
  with the model switching at each year's first session. Orders keep the bracket they were placed
  with across a switch.
- Each night's picks are the candidates with a predicted net return > 0.0, ranked descending, ties
  broken by symbol, each with A's design bracket. The simulator fills the free slots in order, and
  a night with no positive prediction trades nothing.

**Gate (P6a).** The gated curve passes only if its walk-forward (2018-01-02 → data end) beats
total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%, measured with P3's `metrics`
(web parity). The gated curve is B, unless the last fold's determinism probe fails. Then the
pre-registered switch gates B-linear, and the verdict sentence says so. B-linear is otherwise
information only and never promotable on this data. A2's walk-forward is on the chart and in the
tables as information.

**The report** (`docs/backtests/<data end>-strategy-b-walkforward.md`) contains, in order:

1. the title;
2. data;
3. method, which lists everything that was fixed in advance;
4. every fold's training summary for B and B-linear (rows, label mean, in-fold R², pred mean,
   positive share, top 5 features by split gain, or by |coef| × std for B-linear);
5. B, B-linear and A2 vs both SPY curves;
6. year by year;
7. the diagnostics: P/L by exit reason and by year, < 3 shares, cost drag, passed nights and the
   calibration table;
8. "seen before" (2022-01-03 →);
9. the go-live checklist;
10. survivorship, with the learned-model caveat;
11. positions open at the end;
12. the chart;
13. the gate verdict;
14. on a fail, the owner's options (b), (c) and (d) (handover §8);
15. the machine lines.

**Committed result** ({{END}} data, walk-forward 2018-01-02 → {{END}}): gate **{{PASSED_OR_FAILED}}**. Determinism probe: {{PROBE_RESULT}}. {{VERDICT_SENTENCE}}
See `docs/backtests/{{END}}-strategy-b-walkforward.md`.
PASS: `STRATEGY_B_FROZEN` names `engine/data/models/{{END}}-strategy-b.pkl` (sha256 `{{SHA256}}`): the last fold's {{GATED}} model, trained on labels resolved through {{TRAIN_END}}. P4 may start with it.
FAIL: B's one round has failed on this data. B is not reworked on it, no model is frozen, and P4 stays blocked until the owner chooses among the report's options.

**Survivorship.** The gap is the same as P3's: {{NEVER_FETCHED}} index members in the window from
2015-10-19 have no bars at all. A learned model can absorb that bias more than a rule can, because
the losers it never saw are exactly the ones it would have needed to learn to avoid. The report says
so.
````

**9g. Strategy B API (after line 493, the end of the `strategies.a2` section, before line 495 `### backtest (P3)`).** Insert, keeping exactly one of the two `STRATEGY_B_FROZEN` bullets:

````markdown
**`strategies.indicators`, P6a additions.** `mean_window(x, n)` is the mean of the last `n`
columns, summed left to right. `stdev_return_window(close, n)` is the population (ddof 0) stdev of
the last `n` one-bar returns, NaN when the window is too short. Both follow the same bit-identity
rule as the other windows: an explicit column loop, never `sum`/`mean`/`cumsum` along time.

**`strategies.b_model`** (P6a: `docs/handover/2026-10-03-strategy-b-ranker.md`)

This is the one place scikit-learn is used. It is pure: no I/O, no clock and no global randomness,
because seeds are passed as `random_state=0`.

- `TREE = "tree"` and `RIDGE = "ridge"`. `TREE_PARAMS` is the pre-registered
  `HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False, random_state=0)`.
  There is no hyperparameter search. `RIDGE_ALPHA = 1.0`.
- `BModel(kind, n_features, digest, estimator)`. Equality and hash are `(kind, n_features, digest)`.
  `digest` is the sha256 of the tree's baseline and node arrays, or of the ridge coefficients and
  intercept. `predict(X)` is bit-identical per row, whatever the batch size.
- `fit_tree(X, y, *, threads=None)` and `fit_ridge(X, y, alpha=RIDGE_ALPHA)`. The ridge is closed
  form with an unpenalized intercept, accumulated in fixed `BLOCK_ROWS` blocks, so it never depends
  on BLAS threads. `fit(kind, X, y)` dispatches between them.
- `importance(model, X)`: shares that sum to 1. Trees use split gain; ridge uses |coef| × the
  feature's std. `r2(y, pred)`.
- `dumps(model) -> bytes` (a protocol-5 pickle of `(kind, n_features, estimator)`),
  `loads(data) -> BModel` (it recomputes the digest) and `sha256(data) -> str`.

**`strategies.b`** (P6a: Strategy B, the ML cross-sectional ranker)

Strategy B ranks the same eligible set as A by a learned prediction of each order's net return, and
keeps A's fixed bracket. `a.py` and `a2.py` are not changed.

- `LOOKBACK = 200`, `SPY_SYMBOL = "SPY"` (equal to `universe.BENCHMARK`, which a test asserts), and
  `MIN_DOLLAR_VOLUME = 20_000_000.0` (A's floor, strict `>`).
- `FEATURE_NAMES`: the 15 `SYMBOL_FEATURES` (returns over 1/5/20/60/120 bars, close ÷ SMA(50) − 1,
  close ÷ SMA(200) − 1, RSI(2), RSI(14), ATR(14) ÷ close, the 20-bar stdev of returns, 20-day mean
  dollar volume, 5- ÷ 20-day mean volume, gap and range position), then the 3 `SPY_FEATURES` (SPY's
  5- and 20-bar returns and close ÷ SMA(200) − 1).
  - Each symbol feature is turned into a cross-sectional rank in [0, 1] among that date's
    candidates only (`rank01`: ties averaged, 0.5 for a single candidate). The SPY features stay
    raw.
  - Ranking dollar volume itself equals ranking its log (D6).
- **Candidates on `d`:** a member other than SPY, with a bar dated `d`, at least 200 bars through
  `d`, a 20-day mean dollar volume above $20M and all 15 raw features finite. SPY's features must
  also be defined on `d`; if they are not, there are no candidates. Bracket validity is not a
  candidate rule: it applies to picks and to training rows.
- `Design(data_date, symbols, X, close, atr)`, `BPrepared` / `prepare_b(history)` (raw window
  features once per (symbol, date)), `design_on(members, d)`, and `design_at(history, members, d)`
  (the single-window path, bit-identical to `prepare_b`).
- `BParams(model)`. Any `Predictor` with `predict(X) -> float64` fits, and `b_model.BModel` is the
  real one. `bracket(symbol, close, atr)` is `a._bracket` at the design values.
  `picks_from_design(design, params)` keeps predictions > 0.0, ordered by (−prediction, symbol).
- `FrozenModel(report, artifact, train_end, sha256)`.
- PASS: `STRATEGY_B_FROZEN`, **the frozen model**: the report `docs/backtests/{{END}}-strategy-b-walkforward.md`, whose P6a gate passed, and the artifact `engine/data/models/{{END}}-strategy-b.pkl` (sha256 `{{SHA256}}`), the last fold's {{GATED}} model, trained on labels resolved through {{TRAIN_END}} ({{TRAIN_ROWS}} rows).
  - `tests/test_strategy_b_frozen.py` fails if code, artifact and report disagree.
  - Changing it means re-running `backtest_b` and committing its report and artifact, and it resets the forward clock.
- FAIL: `STRATEGY_B_FROZEN = None`.
  - The P6a gate failed (`docs/backtests/{{END}}-strategy-b-walkforward.md`), so nothing is frozen, no artifact is committed, and B may not be deployed.
  - `tests/test_strategy_b_frozen.py` fails if a value or an artifact appears without a passing report.
- `StrategyB` implements `Strategy` with `id = "B"` and `lookback = LOOKBACK`; `STRATEGY_B =
  StrategyB()`. Its contract is `picks_prepared(prepare(H), M, d, p) == picks({s: h.upto(d)}, M, d,
  p)` for every model, and no look-ahead, SPY's bars included. B-linear is the same `STRATEGY_B`
  with a ridge `BParams`.

````

**9f. Command section (after line 219, the end of `### backtest_wf (P3b)`, before line 221 `## Exported API`).** Insert. Check every flag, default, logged step and exit-2 case against `$S/help-b.txt` and `commands/backtest_b.py`:

````markdown
### `backtest_b` (P6a)

```
SEER_ENV_FILE=/path/to/.env.local python -m seer_engine backtest_b [--dry-run] [-v] [--out DIR] [--cache-dir DIR]
    [--refresh-cache] [--is-start YYYY-MM-DD] [--first-year YYYY] [--end YYYY-MM-DD] [--dividends PATH]
    [--model-dir DIR]
```

This runs Strategy B's anchored yearly walk-forward against Neon and writes the P6a report.
**Read-only**, like `backtest_wf`: it reads `bars`, `universe` and `fx_rates`, and writes nothing to
any table, `strategies.params` included.

- **Defaults are the committed run.**
  - `--out` defaults to `<repo>/docs/backtests` and `--model-dir` to `<repo>/engine/data/models`.
  - The window flags have `backtest_wf`'s defaults (2015-10-19, 2018, the last SPY bar, and
    `engine/data/spy_dividends.csv`). They exist for synthetic tests. Passing them for a real run
    is how training on traded data starts, so don't.
- **Steps:**
  1. Load the market, from the same bar cache as `backtest`.
  2. The folds; `prepare_b` once; the candidate table with its labels.
  3. Per fold, a tree fit and a ridge fit on the purged rows, sequential, in fold order. Then the
     determinism probe on the last fold, which decides the gated curve.
  4. The B and B-linear walk-forward runs, each one continuous portfolio from 2018-01-02.
  5. A2's combined walk-forward, recomputed through `backtest_wf`'s `tune_all` + `run_walk_forward`
     as information.
  6. Both SPY curves, survivorship, passed nights, calibration, `gate_p6a`, and the three files.
  7. On a pass, the gated curve's last-fold model goes to `<model-dir>/<data end>-strategy-b.pkl`,
     and its sha256 is logged with the instruction to freeze it.
- **Output:** `<out>/<data end>-strategy-b-walkforward.md`, `-equity.csv` and `-equity.svg`, plus
  the artifact on a pass. A re-run on the same data overwrites them byte-identically. Only the
  `frozen-model:` line, and what renders from it, follows `STRATEGY_B_FROZEN`.
- **Logs:** cache hit or miss, the wall time of every step, every fold's training summary, the
  probe result, the gate verdict, and the artifact path and sha256 on a pass. Wall times appear in
  logs only, never in a file.
- **Exit codes:**
  - 0 whether the gate passes or fails, because a losing verdict is a result.
  - 1 on an error.
  - 2 on a precondition, as for `backtest_wf`.
- **Worktrees:** as for `backtest`, set `SEER_ENV_FILE` to the main checkout's `.env.local`. Never
  `source` it.
- **One round.** The committed run is B's single round on this data. Re-running it on newer data
  re-measures the same pre-registered procedure. Changing a feature, the label, a hyperparameter or
  the pick rule after seeing results is not allowed.

````

Drop `[--dry-run] [-v]` from the synopsis if `help-b.txt` does not list them. The CLI adds them
globally, so they normally appear.

**9e. Layout `docs/backtests/` line (line 82).** Replace it with:

```text
docs/backtests/             committed reports: <end>-strategy-a{.md,-equity.csv,-equity.svg} (P3); <end>-strategy-a2-walkforward{.md,-equity.csv,-equity.svg,-variants.svg,-grid.csv} (P3b); <end>-strategy-b-walkforward{.md,-equity.csv,-equity.svg} (P6a)
```

**9d. Layout `engine/` lines (lines 78–81).** After line 78 (`      backtest_wf.py        …`),
insert:

```text
      backtest_b.py         `backtest_b` command (P6a)
```

PASS only: after line 80 (`  data/spy_dividends.csv …`), also insert:

```text
  data/models/              committed frozen models: <end>-strategy-b.pkl (P6a; b_model.dumps, sha256 in STRATEGY_B_FROZEN)
```

**9c. Layout `strategies/` and `backtest/` lines (lines 57–72).** Make these replacements and
insertions. Each one targets an exact line.
- Line 57 → `      __init__.py           re-exports the public names of base, a, a2 and b (never b_model, so importing the package does not load scikit-learn)`
- Line 59 → `      indicators.py         sma / wilder_rsi / wilder_atr / mean_dollar_volume / mean / stdev_return windows, rolling()`
- After line 61 (`a2.py`), insert:
  ```text
      b_model.py            Strategy B's model (P6a): fit_tree / fit_ridge, BModel (digest identity), importance, dumps / loads
      b.py                  Strategy B (P6a): 18 features, rank01, candidates, BParams, picks > 0, FrozenModel, STRATEGY_B_FROZEN, StrategyB
  ```
- Line 62 → `    backtest/               10-year backtest (P3) and walk-forward (P3b, P6a); every module but io.py is pure`
- After line 71 (`wf_report.py`), insert:
  ```text
      labels.py             vectorized bracket labeler: net-of-cost label and resolution date per order (P6a)
      b_walkforward.py      candidate table, purge, per-fold fits, probe, B / B-linear runs, calibration, gate_p6a() (P6a)
      b_report.py           BReport, machine lines, Markdown, equity CSV, SVG (P6a)
  ```
- Line 72 → `      io.py                 Neon loader + bar cache, dividends CSV, report writers write_report() / write_wf_report() / write_b_report(), write_model_artifact() (impure)`

If `strategies/__init__.py` exports differ (Step 9's grep), describe what is there.

**9b. Key Responsibilities (after line 27, the P3b bullet).** Insert:

```markdown
- Strategy B (P6a): `strategies.b` (an ML cross-sectional ranker on 15 ranked features and 3 SPY features, keeping A's bracket and passing on nights with no positive prediction), `strategies.b_model` (fixed-hyperparameter gradient-boosted trees, plus a ridge for information), a vectorized net-of-cost bracket labeler (`backtest/labels.py`), the B walk-forward over P3b's folds with a label purge (`backtest/b_walkforward.py`), its report (`backtest/b_report.py`), and the `backtest_b` command
```

**9a. Line 4 (Last Updated).** Replace it with:

```markdown
**Last Updated**: {{TODAY}} (Strategy B P6a, phase 7 of `STRATEGY_B_RANKER_PLAN.md`: `strategies.b`, `b_model`, labeler, B walk-forward, `backtest_b` command, committed P6a report)
```

**Impact:** documentation only.

### Step 10: `docs/ROADMAP.md` P6a block, final suite, docs commit

**File:** `docs/ROADMAP.md`. Insert the block after line 43 (the P3b `(c) revisit …` sub-bullet),
and keep the blank line before line 45 `## P4 — Nightly forward paper trading`. Do not edit the P3
or P3b blocks, which are historical records, or P4, P6 or any other block. Keep exactly one branch.

B is placed before P4 because it ran ahead of P4 (handover §1). The P6 block's "Strategy B (ML
ranker), walk-forward backtest, then forward paper" bullet stays as it is: the forward-paper half
still belongs to P6.

**FAIL branch:**

```markdown

## P6a — Strategy B (ML ranker) under walk-forward · done {{TODAY}}: **Gate failed — B's one round failed on this data; P4 stays blocked** ([report](backtests/{{END}}-strategy-b-walkforward.md))
- Spec: [handover](handover/2026-10-03-strategy-b-ranker.md). Option (a) of the P3b verdict, run ahead of P4. Research-only and read-only; no trade rule changed
- Tried, all pre-registered before any B result: gradient-boosted regression trees (fixed hyperparameters, no search) on 15 cross-sectional feature ranks + 3 raw SPY features, trained per fold on the net-of-cost return of A's fixed bracket order, purged at each fold's tuning end; picks are every candidate with a predicted net return > 0, so B may sit a night out. B-linear (ridge) ran beside it as information only. P3b's folds, one continuous portfolio 2018-01-02 → {{END}}, with A2 on the same chart
- Determinism probe on the last fold: {{PROBE_RESULT}}
- **Gate:** the walk-forward curve must beat total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%
- **Verdict ({{END}} data, walk-forward 2018-01-02 → {{END}}):** {{VERDICT_SENTENCE}}
- B's one round failed on this data; P4 stays blocked. B is not reworked on this data, `STRATEGY_B_FROZEN` stays `None`, and no model is committed. The owner decides next (handover §8):
  - (b) accept SPY buy-and-hold as the honest champion for now: Seer can still paper-trade research strategies (P4 without real-money picks), and the home screen recommends no buys;
  - (c) revisit a design-§5 trade rule (for example the 5-day time stop, the 4 slots, or a longer holding horizon). That is a design change: it needs the owner's explicit decision and a new handover, and it is never done inside a strategy phase;
  - (d) Strategy C (news + LLM veto) is forward-paper only by design §4, so it cannot pass a backtest gate and does not unblock P4 under the current ROADMAP wording; changing that wording is the owner's call.
```

**PASS branch:**

```markdown

## P6a — Strategy B (ML ranker) under walk-forward · done {{TODAY}}: gate passed — P4 may start with Strategy B's frozen model ([report](backtests/{{END}}-strategy-b-walkforward.md))
- Spec: [handover](handover/2026-10-03-strategy-b-ranker.md). Option (a) of the P3b verdict, run ahead of P4. Research-only and read-only; no trade rule changed
- Tried, all pre-registered before any B result: gradient-boosted regression trees (fixed hyperparameters, no search) on 15 cross-sectional feature ranks + 3 raw SPY features, trained per fold on the net-of-cost return of A's fixed bracket order, purged at each fold's tuning end; picks are every candidate with a predicted net return > 0, so B may sit a night out. B-linear (ridge) ran beside it as information only. P3b's folds, one continuous portfolio 2018-01-02 → {{END}}, with A2 on the same chart
- Determinism probe on the last fold: {{PROBE_RESULT}}
- **Gate:** the walk-forward curve must beat total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%
- **Verdict ({{END}} data, walk-forward 2018-01-02 → {{END}}):** {{VERDICT_SENTENCE}}
- This supersedes P3b's "P4 stays blocked". P4 may start with Strategy B: `STRATEGY_B` with `BParams(b_model.loads(…))` of `engine/data/models/{{END}}-strategy-b.pkl` (sha256 `{{SHA256}}`), the last fold's {{GATED}} model trained on labels resolved through {{TRAIN_END}}, named by `STRATEGY_B_FROZEN` in `engine/src/seer_engine/strategies/b.py`
  - P4's nightly job must load SPY's last 200 bars into `history` too, because B's SPY features read them; SPY is never a pick.
  - The artifact needs scikit-learn 1.9.x, which `engine/pyproject.toml` pins. Moving to another minor version means refitting from the report's `last-fold-model` recipe, re-checking the digest, and committing a new artifact and report.
  - Strategy A v1 and A2 stay P3's and P3b's records and are not deployed.
```

Then the leftovers check, the Law check, the final suite and the docs commit:

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
grep -n "{{\|^PASS: \|^FAIL: \|^- PASS: \|^- FAIL: " engine/package_readme.md docs/ROADMAP.md && echo "LEFTOVER" || echo "docs clean"
grep -n "<END>\|<GATED>\|<LAST_YEAR>\|<TRAIN_END>\|<TRAIN_ROWS>\|<LABEL_SUM>\|<YYYY>\|<SHA256>" engine/src/seer_engine/strategies/b.py && echo "LEFTOVER" || echo "b.py clean"
git diff --stat 0e91d8a -- engine/src/seer_engine/sim engine/src/seer_engine/strategies/a.py \
  engine/src/seer_engine/strategies/a2.py engine/src/seer_engine/strategies/base.py \
  engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/walkforward.py \
  engine/src/seer_engine/backtest/wf_report.py engine/src/seer_engine/backtest/metrics.py \
  engine/src/seer_engine/backtest/tuning.py engine/src/seer_engine/backtest/report.py \
  engine/src/seer_engine/backtest/market.py engine/src/seer_engine/backtest/benchmark.py \
  engine/src/seer_engine/commands/backtest.py engine/src/seer_engine/commands/backtest_wf.py \
  engine/src/seer_engine/cli.py docs/backtests/2026-10-02-strategy-a.md \
  docs/backtests/2026-10-02-strategy-a-equity.csv docs/backtests/2026-10-02-strategy-a-equity.svg \
  docs/backtests/2026-10-02-strategy-a2-walkforward.md docs/backtests/2026-10-02-strategy-a2-walkforward-equity.csv \
  docs/backtests/2026-10-02-strategy-a2-walkforward-equity.svg docs/backtests/2026-10-02-strategy-a2-walkforward-variants.svg \
  docs/backtests/2026-10-02-strategy-a2-walkforward-grid.csv web .github   # must print nothing (handover §3 Law)
git diff --name-only --diff-filter=M 0e91d8a -- engine/tests   # must print nothing: no existing test file edited
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  engine/.venv/bin/pytest engine/tests -q -rs | tee "$S/suite-after.out"
grep -c '^SKIPPED' "$S/suite-after.out"   # must print 0
git add engine/package_readme.md docs/ROADMAP.md
git commit -F "$S/commit-docs.txt"
git log --oneline -5
git status --porcelain                    # empty (engine/.cache/ ignored)
```

The suite must pass `<N6> + 6` tests with 0 skipped, plus any Bug-protocol regression tests, which
must be named.

`$S/commit-docs.txt`:

```text
docs(engine): P6a Strategy B, b_model, labeler, B walk-forward, backtest_b command; ROADMAP P6a verdict

engine/package_readme.md: strategies.b (features, ranks, candidates, picks, FrozenModel),
strategies.b_model (tree + ridge, digest identity, dumps/loads), the indicator additions,
backtest.labels, backtest.b_walkforward (purge, per-fold fits, determinism probe, calibration,
gate_p6a), backtest.b_report, the io writers, the `backtest_b` command, scikit-learn, layout,
module graph, reverse dependencies, measured load/prepare/label/fit/run times, usage.

docs/ROADMAP.md: P6a done, gate <passed|failed>. <VERDICT_SENTENCE>
<PASS: P4 may start with STRATEGY_B_FROZEN's model. | FAIL: B's one round failed on this data; P4 stays blocked; owner's options (b), (c), (d).>

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
```

### Step 11: Push the branch and watch CI (R9)

```sh
cd /home/miftah/.worktrees/seer/strategy-b-ranker
git push -u origin feature/strategy-b-ranker
gh run list --workflow engine-ci.yml --branch feature/strategy-b-ranker --limit 3 --json databaseId,headSha,status,conclusion
```

- The run commit touches `engine/**`, so the workflow's `push` path filter triggers it. Take the
  newest run whose `headSha` equals `git rev-parse HEAD`. A foreground `sleep` may be blocked, so
  poll `gh run list` with Monitor or an until-loop until it appears.
- Then run `gh run watch <id> --exit-status`. It must end in `success`. The job that matters is
  `engine (pytest)`: it installs `engine[dev]` (and so scikit-learn 1.9.x), runs the suite, and fails
  on any `SKIPPED`.
- If no run appears for `HEAD`, trigger it with
  `gh workflow run engine-ci.yml --ref feature/strategy-b-ranker`, then list and watch as above.
- A red CI is handled by the Bug protocol if it is a code defect, or reported to the caller if it
  is an environment issue, such as CI's Postgres service or a wheel install. Never push to `main`.

## Verification

**Build:**
```sh
engine/.venv/bin/pip install -q -e 'engine[dev]' && engine/.venv/bin/python -c "from seer_engine.strategies.b import STRATEGY_B_FROZEN; print(STRATEGY_B_FROZEN)"
```

**Tests:**
```sh
docker start seer-pg && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs
```

Expect `<N6> + 6` passed (the 6 tests in `test_strategy_b_frozen.py`), and
`grep -c '^SKIPPED'` = 0. `<N6>` is the plan index's reconciled count after phase 6: 761 plus
phases 1–6's additions = **964**, so **970 passed** after this phase.

**Manual check:**
- `docs/backtests/` holds the eight untouched `2026-10-02-strategy-a*` files plus exactly three
  `<END>-strategy-b-walkforward*` files.
- `engine/data/models/` holds exactly `<END>-strategy-b.pkl` on a pass, and does not exist on a
  fail.
- The `.md` renders on GitHub with every §6.7 item and the SVG inline.
- Step 2 printed five `same` lines.
- Run #2 against run #1: on a fail, all three files are `cmp`-identical. On a pass, only the
  `frozen-model`-derived `.md` lines differ, and the artifact is identical.
- The fingerprint did not change across the phase.
- The readme and ROADMAP have no `{{` and no `PASS:`/`FAIL:` labels left.
- `gh run watch` ended in `success`.

**Exit criteria:**
- `backtest_wf --end 2026-10-02` re-rendered all five A2 files byte-identically (R4).
- A read-only real `backtest_b` run on Neon produced the committed three-file report, holding every
  §6.7 section (R7).
- **Pass:** `STRATEGY_B_FROZEN` names the report, the committed artifact, the last fold's
  `train_end` and the artifact's sha256. The comment names the report, and the report's
  `frozen-model:` equals the constant (R8).
- **Fail:** `STRATEGY_B_FROZEN` is `None`, the report says `frozen-model: null`, no artifact is
  committed, and ROADMAP P6a says B's one round failed on this data and P4 stays blocked, with
  options (b), (c) and (d) (R8).
- `test_strategy_b_frozen.py` (6 tests) is green.
- The readme documents B, the labeler, the features, the model, `backtest_b` and its measured
  performance. The full suite is green with 0 skipped. `feature/strategy-b-ranker` is pushed, and CI
  is green on its head (R9).

## Handoffs

- **Phase 2 (R3, R8):**
  - `STRATEGY_B_FROZEN: FrozenModel | None = None` sits on a single line, directly below exactly
    two placeholder comment lines, so `grep -n -B2 "^STRATEGY_B_FROZEN"` finds the block Step 5
    replaces.
  - `b.py` imports `date` at runtime (`from datetime import date`), not only under `TYPE_CHECKING`.
  - `FrozenModel`, `FEATURE_NAMES`, `STRATEGY_B_FROZEN`, `SPY_SYMBOL`, `BParams` and `STRATEGY_B`
    are importable from `seer_engine.strategies.b`.
- **Phase 1 (R5):** `b_model.loads` recomputes the digest from the estimator, and `BModel.kind`
  equals `TREE`/`RIDGE`, which are `"tree"`/`"ridge"`. Step 4's test compares `model.kind` with the
  report's `last-fold-model` `kind`.
- **Phase 4 (R4):** `B = "B"` and `B_LINEAR = "B-linear"`. The test maps them to `TREE`/`RIDGE`.
- **Phase 5 (R7):**
  - `parse_machine_line` returns the **raw** value.
  - `frozen-model:` renders exactly `null` for `None`. Otherwise it renders
    `json.dumps({"report", "artifact", "train_end": <ISO>, "sha256"})`.
  - `last-fold-model:` has exactly the keys `kind`, `digest`, `train_end` (ISO), `rows` (a JSON int)
    and `label_sum`, describing the **gated** curve's last fold.
  - Only `BReport.frozen` drives the `frozen-model` line, plus any sentence derived from it.

  Step 4's test and Step 6's diff check depend on this.
- **Phase 6 (R7, R8):**
  - `run()` writes the artifact only on a gate pass, from the gated curve's last fold, to
    `--model-dir` (default `<repo>/engine/data/models`), named `<data end>-strategy-b.pkl`, and logs
    its path and sha256.
  - `--cache-dir` defaults to `engine/.cache`, the same as `backtest_wf`, so Step 2a warms the
    cache for Step 3.
  - Every step's wall time is logged, which Step 7 reads.
- **Fact for the coordinator:** neither main nor the worktree has an `engine/.cache/` at plan time,
  so the first real command in this phase is a cold Neon load (about 25–37 s). If the fingerprint has
  moved past 2026-10-02, Step 2 uses its `date <= 2026-10-02` rebuild, and any remaining difference
  is an **A2 finding** that stops the phase.
- **Not owned here (R5):** run-twice byte-identity on real data. Step 6 measures it as a by-product
  of the pass branch's required re-run, and as a cheap pre-commit check on the fail branch. A
  mismatch is a Bug-protocol fix in the phase that owns the module.
- **Follow-up, unowned:** if `B1_WALL` is more than 60 minutes, add a process pool to the per-fold
  fits, gathered in fold order (D18). It changes no number.
- **Follow-up, owner:**
  - Merging `feature/strategy-b-ranker` to `main` belongs to the completion handler or coordinator.
  - On a fail, the owner picks (b), (c) or (d) from handover §8. That needs a new handover and is
    not part of P6a.
  - On a pass, P4 is the next major plan. It must load SPY's last 200 bars, verify the artifact's
    sha256 before `b_model.loads`, and write the frozen model's identity to `strategies.params`.
    None of that is done here.
  - The ROADMAP's v0.1.0 goal line ("Strategy A forward paper trading") and the P6 bullet are left
    as they are. Rewording them is the owner's call.

## Rollback

There are two local commits, plus any Bug-protocol fix commits.

- **Before the push:** `git reset --hard <phase-6 head>` on the branch.
- **After the push:** `git revert <docs commit> <run commit>`, newest first.

Either way, this restores `STRATEGY_B_FROZEN = None` and removes the P6a report, the artifact, the
frozen test and the readme/ROADMAP edits together. The frozen test and the report must always be
reverted together, or the test fails on a missing report.

Neon is never written, so there is nothing to undo there. `engine/.cache/` and the scratch
directory can be deleted at any time.
