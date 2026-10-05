> Adopted from `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md` phase 4. Source: `.workflows/plan/fundamental-panel-coverage/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Refresh the store's panel without re-downloading bars

**Plan set:** `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md`
**Analysis:** `20261005-133648-2XUM_code_analyzer.md`
**Satisfies:** R4 — the capability half of "honest reporting": phase 5 cannot measure the
refreshed panel's coverage until there is a way to put a new panel into the store without
destroying the bars the 64 recorded trials were run against.
**Depends on:** Phase 1 **(added by the reconciler — see `## Shared-file sequencing`)**
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine` (research)

---

## Runtime preamble — run this before every command in this phase

Reconciled set-wide (see the index's `## Decisions`, row C2). The worktree has **no venv of its
own**, and `/home/miftah/seer/engine/.venv` is an *editable* install whose
`__editable__.seer_engine-0.1.0.pth` contains the literal `/home/miftah/seer/engine/src` — the
**main checkout**. `engine/pyproject.toml`'s `[tool.pytest.ini_options]` sets only
`testpaths = ["tests"]` and **no `pythonpath`**, so pytest resolves `seer_engine` through that
same editable install. Without the block below, every command in this phase — `pytest`
included — silently exercises `main`'s code and reads `main`'s `engine/data/`.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/fundamental-panel-coverage
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src          # searched before anything `site` adds
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

**Reuse main's venv; do not build one in the worktree.** `PYTHONPATH` wins over the `.pth`
(measured), carries `cik.DATA_DIR` (`Path(cik.__file__).parents[2] / "data"`) to the worktree
with it, and applies uniformly to `pytest` and to `python -m seer_engine`. A second venv would
mean a second dependency resolution, and invariant 1 pins this set to the `2dad9ff` baseline of
2216 passed / 332 skipped measured in *this* interpreter.
`engine/scripts/build_ticker_cik.py:40` does its own
`sys.path.insert(0, Path(__file__).resolve().parents[1] / "src")`, so the generator
self-resolves when invoked by its worktree path — that rescues the generator and nothing else.

This phase touches no database, no network and no store on disk: every test builds its own store
in `tmp_path` and `_read_facts` is monkeypatched. It still needs the preamble, because without it
`pytest` and `python -m seer_engine research_store --help` run **main**'s `seer_engine`, which
has neither this phase's flag nor phase 1's.

---

## Goal

After this phase `seer_engine.research` has a second write path into a store:
`refresh_fundamentals(store_dir, facts)`, which verifies the store at `store_dir` with
`load_store`, carries `bars.csv`, `dividends.csv`, `fx.csv` and `unserved.csv` over **byte for
byte**, writes a new `fundamentals.csv` from the facts it is handed, re-seals the manifest and
swaps the directory in atomically. `python -m seer_engine research_store
--refresh-fundamentals` reaches it. Before this phase the only path into a store was
`build_store`, which always downloads every symbol's bars from yfinance first — so picking up a
new panel meant replacing all 2,490,793 bar rows with whatever yfinance answers today.

This phase writes the capability only. **Phase 5** runs it against the real
`engine/.research/`. Every test here builds its own store in `tmp_path`.

## Interface Contract

**Creates:**
- `research.refresh_fundamentals` (`engine/src/seer_engine/research.py`, new, inserted between
  `_swap_in` and the `# ---- load ----` banner)
- `commands.research_store._run_refresh` (`engine/src/seer_engine/commands/research_store.py`)
- `commands.research_store._refresh` (`engine/src/seer_engine/commands/research_store.py`)
- CLI flag `--refresh-fundamentals` on `research_store` (`args.refresh_fundamentals`)
- `import shutil` in `engine/src/seer_engine/commands/research_store.py`

**Deletes:** none
**Renames:** none
**Signature changes:**
- `engine/tests/test_research_store.py::build(...)` gains a defaulted keyword `facts=None`,
  forwarded to `research.build_store(facts=...)`. Purely additive: `build_store`'s own default
  is already `facts=None`, so every existing caller of the helper is unchanged in behaviour.
- No signature in `engine/src/` changes.

**Requires (from earlier phases):** **Phase 1**, and only for one file. Phase 1 must already
have landed in `engine/src/seer_engine/commands/research_store.py`:

- the `--coverage` flag in `add_arguments`, inserted after the `--verify` block;
- the `_coverage(store)` handler, inserted after `_verify`;
- `from seer_engine.fundamentals import Fact, coverage` on the import line;
- and above all the **rewritten `run()`** (phase 1's step 3d), which is the body this phase's
  Step 3 quotes and extends. Step 3's code block below is phase 1's body with three statements
  added; if the file does not already match phase 1's version, **stop** — phase 1 has not landed
  and this phase's `run()` would delete its branch.

Nothing in `engine/src/seer_engine/research.py` depends on phase 1, and none of this phase's
tests import `fundamentals.coverage`.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/fundamentals/**` — phase 1. In particular this phase does **not**
  import, call or anticipate `fundamentals.coverage`.
- `engine/src/seer_engine/commands/research_store.py`'s `--verify`, `--with-fundamentals`,
  `_build`, `_verify`, `_read_facts`, `format_summary`, `add_arguments`'s first four
  `p.add_argument` calls — untouched beyond the three lines named in **Step 3**. Phase 1 adds
  `--coverage` to this same file; see **Shared-file sequencing** below.
- `engine/src/seer_engine/cik.py`, `engine/scripts/`, `engine/data/` — phase 2.
- `engine/src/seer_engine/commands/fundamentals.py` — phase 3.
- `docs/**`, `engine/package_readme.md`, `m0005_fundamental_factors.py` — phase 5.
- `engine/.research/` **on disk** — phase 5 runs the refresh against it.

**Reused unchanged (read-only dependencies of this phase):** `build_store`'s download path,
`load_store`, `_read_manifest`, `_seal`, `_swap_in`, `_write_text`, `file_sha256`,
`fingerprint_of`, `fundamentals_lines`, `_read_fundamentals`, `DATA_FILES`,
`OPTIONAL_DATA_FILES`, `FUNDAMENTALS_FILE`, `FUNDAMENTALS_HEADER`, `MANIFEST_KEYS`,
`_COUNT_KEYS`, `ResearchStoreError`. **None of them is modified.** `MANIFEST_KEYS` keeps exactly
its current members and `engine/tests/test_research_store.py:233`
(`assert set(manifest) == research.MANIFEST_KEYS`) keeps passing unedited.

### Shared-file sequencing — RESOLVED by the reconciler

Phase 1 and phase 4 both edit `engine/src/seer_engine/commands/research_store.py`, and both edit
`run()` and `add_arguments()`. They were planned as the same wave, so neither could quote the
other's output. **They are now serialised: phase 1 lands first, and this phase is in its
`Depends on`.** A correct serialisation beats a false concurrency, and phase 1 is the right first
mover because it rewrites `run()` *wholesale* (its step 3d) while this phase appends one branch
— the reverse order would make phase 1's whole-function rewrite silently delete this phase's
branch.

The branch order is settled too, and it differs by one swap from what this plan originally
asserted: **guards → `--coverage` → `--verify` → `--refresh-fundamentals` → build.**
`--coverage` is tested *before* `--verify` because phase 1's Interface Contract and its step-3d
code block both state that `--coverage` wins when both read-only flags are given; the relative
order of two read-only modes is observable only in that case, and phase 1's code block is the
higher rung. Both remain ahead of `--refresh-fundamentals`, which is the one writing mode here.

Neither phase converts `--verify` into a mutually-exclusive argparse group (a group would make
the two diffs collide, and it is explicitly forbidden to both). Instead this phase adds one
explicit guard covering **both** read-only flags.

My edits, against the file **as phase 1 leaves it**:

| Where | My edit |
|---|---|
| module docstring (phase 1's rewritten lines 12–21) | add `[--refresh-fundamentals]` to the usage block and one paragraph after phase 1's `--coverage` paragraph — Step 6 quotes the merged result in full |
| imports, after `import logging` | add `import shutil` |
| `add_arguments`, **appended after** the existing `--with-fundamentals` block | one new `p.add_argument("--refresh-fundamentals", ...)`. Phase 1's `--coverage` sits *before* `--with-fundamentals`, so the two insertions do not touch |
| `run` | phase 1's body with three statements inserted: the guard, and the `if refresh:` branch after `--verify`. Step 3 quotes the whole post-change function |
| after `_build`, **before** `_verify` | two new functions `_run_refresh` and `_refresh`. Phase 1's `_coverage` sits after `_verify`, so the two insertions do not touch |

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/research.py` | modify | new `# ---- refresh ----` section with `refresh_fundamentals`, inserted after `_swap_in` (ends `:528`) and before the `# ---- load ----` banner (`:531`) |
| `engine/src/seer_engine/commands/research_store.py` | modify | `import shutil` (after `:27`); `--refresh-fundamentals` in `add_arguments` (after `:79`); three statements in `run` (`:82`–`:97`); `_run_refresh` + `_refresh` after `_build` (after `:115`); module docstring (`:12`–`:21`) |
| `engine/tests/test_research_store.py` | modify | `from seer_engine.fundamentals import Fact` (after `:21`); `facts=None` on the `build` helper (`:120`–`:128`); a new `# ---- refresh ----` section appended after `:553` with nine tests |

## Implementation Steps

### Step 1: The refresh itself

**File:** `engine/src/seer_engine/research.py:529` — insert between `_swap_in`'s last line
(`:528`, `shutil.rmtree(old, ignore_errors=True)`) and the `# ---- load ----` banner (`:531`).

**Change:** a new top-level section and one public function. No existing line in this file is
edited, no import is added (`shutil`, `Sequence`, `Any`, `Path` are all already imported at
`:36`, `:38`, `:43`, `:42`).

**Code:**

```python
# ---- refresh -------------------------------------------------------------------------------


def refresh_fundamentals(
    store_dir: Path,
    facts: Sequence[Fact],
    *,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """Rewrite an existing store's ``fundamentals.csv`` from ``facts``; return the new manifest.

    This is ``build_store``'s panel half without its download half. ``bars.csv``,
    ``dividends.csv``, ``fx.csv`` and ``unserved.csv`` are carried over **byte for byte** from
    the store already at ``store_dir``; only ``fundamentals.csv`` is written anew, the manifest
    is re-sealed and the directory is swapped in with the same ``.tmp`` / ``.old`` /
    ``os.replace`` discipline ``build_store`` uses -- so on any failure nothing is written and
    the store on disk is left exactly as it was.

    Why this exists rather than ``build_store(facts=new_facts)``: ``build_store`` always fetches
    FX and downloads every symbol's bars from yfinance before it writes anything, and yfinance
    answers differently day to day. A rebuild would therefore replace every bar row and break
    comparability with the lab trials already recorded against this store's fingerprint.
    Copying -- not rebuilding -- is what keeps one comparable price history while the panel
    moves underneath it.

    The fingerprint **does** change, and that is correct: ``fundamentals.csv`` changed and
    ``fingerprint_of`` hashes the whole file map. What does not change is a single bar.

    ``facts`` is a plain sequence of ``fundamentals.Fact``, exactly as ``build_store`` takes it
    -- never a database connection, because this module imports nothing from ``seer_engine.db``
    (see the module docstring's "Never Neon"). ``commands/research_store.py`` reads them behind
    ``--refresh-fundamentals`` and passes them in. An empty sequence is legal and writes a
    header-only ``fundamentals.csv`` (an explicitly empty panel); ``None`` is not, because
    "refresh with nothing" is ambiguous -- keep the panel, or clear it? -- and the caller must
    say which.

    The source store is verified with ``load_store`` first: every sha256, the fingerprint, the
    five ``_COUNT_KEYS`` counts and the D9 date guards. A store that fails any of them is
    refused with ``ResearchStoreError`` and nothing is written. Refusing to refresh a store that
    cannot be verified is the point of doing it this way round: a silently half-valid store is
    exactly the failure this plan set exists to end. A store with **no** ``fundamentals.csv`` at
    all -- one built before the optional fifth file existed -- is a legal source: it loads with
    an empty panel, and the refresh legitimately adds the file to it.

    The five ``_COUNT_KEYS`` values are carried over from the verified manifest rather than
    recomputed, and the two are the same number by construction: ``load_store`` has just
    compared every one of them against the files this call then copies byte for byte, so
    recomputing could only restate a check that has already passed. They are never re-derived
    from a download -- there is no download.
    """
    store_dir = Path(store_dir)
    if facts is None:
        raise ValueError(
            "refresh_fundamentals needs a sequence of fundamentals.Fact; pass () to write an "
            "empty panel"
        )
    try:
        data = load_store(store_dir, data_dir=data_dir)
    except ValueError as exc:
        raise ResearchStoreError(
            f"{store_dir}: refusing to refresh a store that does not verify: {exc}"
        ) from exc
    # Keep the manifest, drop the Market: the real store holds 2.49M bar rows and nothing below
    # needs them -- only the recorded counts and the per-file digests.
    before = dict(data.manifest)
    del data
    counts = {key: int(before[key]) for key in _COUNT_KEYS}

    tmp = store_dir.with_name(store_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        for name in DATA_FILES:
            shutil.copyfile(store_dir / name, tmp / name)
            copied = file_sha256(tmp / name)
            if copied != before["files"][name]:
                raise ResearchStoreError(
                    f"{name}: the carried-over copy hashes {copied}, the verified store hashes "
                    f"{before['files'][name]}; the copy is not byte-identical, nothing written"
                )
        _write_text(tmp / FUNDAMENTALS_FILE, FUNDAMENTALS_HEADER, fundamentals_lines(facts))
        manifest = _seal(tmp, counts, extra_files=(FUNDAMENTALS_FILE,))
        _swap_in(tmp, store_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "research: store %s panel refreshed: %d facts written, %d bar rows carried over "
        "unchanged, fingerprint %s -> %s",
        store_dir,
        len(facts),
        counts["bar_rows"],
        before["fingerprint"],
        manifest["fingerprint"],
    )
    return manifest
```

**Impact:**

- A second writer of `store_dir` exists. It shares `build_store`'s `.tmp` and `.old` sibling
  paths, both already in `.gitignore` (`engine/.research.tmp/`, `engine/.research.old/`;
  asserted by `test_store_dirs_are_gitignored`), so nothing new leaks into git.
- `.tmp` is a sibling of `store_dir`, so `os.replace` stays within one filesystem exactly as it
  does for a build.
- The refusal is `ResearchStoreError`, not the `ValueError` `load_store` raises. That matches
  `build_store`'s contract ("the build could not finish; nothing was written and any previous
  store is intact") and lets `commands/research_store.py` catch one exception type for both
  write paths. `load_store` itself is unchanged and still raises `ValueError` to its own
  callers.
- Cost on the real store: `load_store` reads 2.49M bar rows and builds a `Market` (tens of
  seconds, a few hundred MB), then the copy hashes ~150 MB twice (once to verify the copy, once
  inside `_seal`). That is the price of verifying rather than assuming, and it is paid once per
  refresh.
- `_seal`'s docstring still says `test_research_store.py` is a file "which no phase of this plan
  set owns". That sentence is now stale — see **Handoffs**. It is deliberately not edited here,
  because `_seal` is reused unchanged.

### Step 2: The CLI flag — `add_arguments`

**File:** `engine/src/seer_engine/commands/research_store.py:79` — append a fifth
`p.add_argument` block immediately after the existing `--with-fundamentals` block, before
`add_arguments`'s closing blank lines.

**Change:** one new flag. The four existing `p.add_argument` calls are untouched.

**Code:**

```python
    p.add_argument(
        "--refresh-fundamentals",
        action="store_true",
        help=(
            "rewrite only fundamentals.csv in an existing store, keeping every bar byte for "
            "byte (needs DATABASE_URL_UNPOOLED); the fingerprint changes, the price history "
            "does not; not combinable with --verify"
        ),
    )
```

**Impact:** `args.refresh_fundamentals` exists on the namespace. No other flag's behaviour
changes; a run without the flag is byte-for-byte the command it is today.

### Step 3: The CLI flag — `run`

**File:** `engine/src/seer_engine/commands/research_store.py:82`–`:97` (`run`)

**Change:** three inserted statements. **Phase 1's `--coverage` branch, its dispatch order and
every line below it are kept verbatim**; nothing existing is deleted or reordered.

**The function as phase 1 leaves it** — confirm the file matches this before editing, because
if it does not, phase 1 has not landed:

```python
def run(args: argparse.Namespace) -> int:
    store = Path(args.store)
    if getattr(args, "coverage", False):
        return _coverage(store)
    if args.verify:
        return _verify(store, note="")
    facts = _read_facts() if getattr(args, "with_fundamentals", False) else None
    ...
```

**Code (the whole function, post-change — this is the body both phases agree on):**

```python
def run(args: argparse.Namespace) -> int:
    store = Path(args.store)
    refresh = bool(getattr(args, "refresh_fundamentals", False))
    read_only = bool(getattr(args, "coverage", False)) or bool(args.verify)
    if refresh and read_only:
        log.error(
            "research_store: --refresh-fundamentals cannot be combined with --verify or "
            "--coverage; those two only read a store, --refresh-fundamentals rewrites its "
            "fundamentals.csv"
        )
        return 2
    if getattr(args, "coverage", False):
        return _coverage(store)
    if args.verify:
        return _verify(store, note="")
    if refresh:
        return _run_refresh(store, bool(getattr(args, "dry_run", False)))
    facts = _read_facts() if getattr(args, "with_fundamentals", False) else None
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size), facts)
            if code != 0:
                return code
            return _verify(target, note=" (dry run: built in a temporary directory and discarded)")
    code = _build(store, int(args.batch_size), facts)
    if code != 0:
        return code
    return _verify(store, note="")
```

**Impact:** `--refresh-fundamentals` short-circuits before the build path, so the build's
`--batch-size` and `--with-fundamentals` never apply to it (the refresh always reads the facts —
reading them is the whole point of the mode). Either read-only flag combined with
`--refresh-fundamentals` exits 2 with a message rather than silently doing the read-only thing;
`--verify` *with* `--coverage` is untouched and still resolves to `--coverage`, which is phase
1's rule. See **Shared-file sequencing**.

### Step 4: The CLI flag — `_run_refresh` and `_refresh`

**File:** `engine/src/seer_engine/commands/research_store.py:115` — insert both functions
immediately after `_build` and before `_verify`.

**Change:** two new private helpers, shaped exactly like `_build`.

**Code:**

```python
def _run_refresh(store: Path, dry_run: bool) -> int:
    """``--refresh-fundamentals``: rewrite fundamentals.csv in place, keeping every bar.

    The facts are read **before** the store is opened, so a database failure refuses while the
    store is still untouched. A dry run copies the whole store into a temporary directory,
    refreshes the copy and discards it: the real store is never opened for writing, which is
    what ``--dry-run`` promises everywhere else in this CLI.
    """
    if not store.is_dir():
        log.error(
            "research_store: %s is not a directory; --refresh-fundamentals needs an existing "
            "store to refresh",
            store,
        )
        return 2
    facts = _read_facts()
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            shutil.copytree(store, target)
            code = _refresh(target, facts)
            if code != 0:
                return code
            return _verify(
                target,
                note=" (dry run: refreshed a copy in a temporary directory and discarded it)",
            )
    code = _refresh(store, facts)
    if code != 0:
        return code
    return _verify(store, note="")


def _refresh(store: Path, facts: Sequence[Fact]) -> int:
    try:
        research.refresh_fundamentals(store, facts)
    except research.ResearchStoreError as exc:
        log.error("research_store: refresh refused, nothing written: %s", exc)
        return 2
    return 0
```

**Impact:** exit code **2** for a refused refresh, matching the module docstring's "2 the store
is missing or invalid" — a refusal is always *about* the store being missing or not verifying.
Exit **1** stays reserved for "the store is fine but a check failed", which `_verify` returns
unchanged. `Sequence` and `Fact` are already imported at `:29` and `:33`.

### Step 5: `import shutil`

**File:** `engine/src/seer_engine/commands/research_store.py:27` — insert after `import logging`
so the stdlib block stays alphabetical.

**Code:**

```python
import argparse
import logging
import shutil
import tempfile
```

**Impact:** `shutil.copytree` in `_run_refresh`. `test_no_neon_and_no_database_url_needed`
AST-scans this module's imports for `seer_engine.db` and `psycopg` only, so `shutil` is fine.

### Step 6: The module docstring

**File:** `engine/src/seer_engine/commands/research_store.py`, the docstring block **phase 1
left behind** (its step 3b replaced the original lines 12–21).

**Change:** the usage block gains this phase's flag, and one paragraph is appended after phase
1's. **Phase 1's text is quoted verbatim below and must not be re-worded** — the only edits are
the second usage line and the final paragraph.

**Code (the merged block, replacing phase 1's):**

```
    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]
                                        [--coverage] [--with-fundamentals]
                                        [--refresh-fundamentals]

``--verify`` loads an existing store only (no network). ``--coverage`` also loads an existing
store only and measures what its fundamental panel can rank across the dev window
(``fundamentals.coverage``): a per-year table and one fraction, printed whatever the number is.
It needs no network and no database, and it wins when both it and ``--verify`` are given. It
exits 0 when the fraction is at or above ``coverage.MIN_DEV_COVERAGE`` and 1 when it is below --
the same convention ``--verify`` uses for a failed check. ``--with-fundamentals`` additionally
reads the SEC point-in-time fact panel from the database (``DATABASE_URL_UNPOOLED``, the one
place in this command that needs it) and writes it as the store's optional fifth file, so
``lab run`` sees a non-empty ``Market.fundamentals``; without the flag the store carries no
fundamentals and the lab ranks on bars alone, silently. The global ``--dry-run`` builds into a
temporary directory and discards it. Exit codes: 0 ok; 1 build failed, a check failed or
coverage is below the floor; 2 the store is missing or invalid.

``--refresh-fundamentals`` rewrites **only** ``fundamentals.csv`` in an existing store and
needs no network: ``bars.csv``, ``dividends.csv``, ``fx.csv`` and ``unserved.csv`` are carried
over byte for byte, so the price history every recorded lab trial was run against survives
untouched while the panel moves. It reads the facts the same way ``--with-fundamentals`` does
(``DATABASE_URL_UNPOOLED`` -- point ``SEER_ENV_FILE`` at the train env file, and give it an
ABSOLUTE path: a relative one is resolved against the cwd and falling through to the ambient
environment means Neon) and refuses with exit 2 if the store is missing or fails verification.
The store's fingerprint changes -- a new ``fundamentals.csv`` is new content -- but not one bar
does. Under ``--dry-run`` it refreshes a copy in a temporary directory and discards it. Not
combinable with ``--verify`` or ``--coverage``.
```

**Impact:** documentation only. The usage block now names all five flags and the two paragraphs
sit side by side in the order the dispatch tests them.

### Step 7: Test support — the `Fact` import and the `build` helper

**File:** `engine/tests/test_research_store.py:21` and `:120`–`:128`

**Change:** one import, and one defaulted keyword on the module's local `build` helper so a test
can build a store that already has a panel. No existing assertion is edited.

**Code (the import block, lines 19–21 post-change):**

```python
from seer_engine import cli, config, db, research, yahoo
from seer_engine.backtest.benchmark import Dividend
from seer_engine.commands import research_store as research_cmd
from seer_engine.fundamentals import Fact
```

**Code (the `build` helper, replacing lines 120–128):**

```python
def build(store, members_dir, *, fake=None, fetch_fx=fake_fx, sleeps=None, batch_size=40, facts=None):
    return research.build_store(
        store,
        downloader=fake if fake is not None else FakeYahoo(default_data()),
        fetch_fx=fetch_fx,
        sleep=sleeps if sleeps is not None else Sleeps(),
        batch_size=batch_size,
        data_dir=members_dir,
        facts=facts,
    )
```

**Impact:** additive. `build_store`'s own default for `facts` is already `None`, so every
existing call of this helper produces the identical four-file store it does today — including
`test_build_is_deterministic_across_runs_and_batch_sizes`, which compares manifests across
calls.

### Step 8: The refresh's tests

**File:** `engine/tests/test_research_store.py:554` — append a new section at the end of the
file, after `test_command_dry_run_keeps_nothing`.

**Change:** nine tests and two fixtures-by-constant. They build their own stores in `tmp_path`
and touch no network and no database: `_read_facts` is monkeypatched where the command path
needs it.

**Code:**

```python
# ---- refresh (fundamentals only) -----------------------------------------------------------

# Two tiny panels. Facts are plain values -- never a database row -- exactly as build_store and
# refresh_fundamentals take them. filed <= DEV_END so nothing here is test-window data.


def fact(symbol, tag, *, val, filed, accn, period_end=date(2015, 6, 30)):
    return Fact(
        symbol=symbol,
        taxonomy="us-gaap",
        tag=tag,
        unit="USD",
        period_start=None,
        period_end=period_end,
        val=val,
        accn=accn,
        form="10-Q",
        fy=2015,
        fp="Q2",
        filed=filed,
    )


FACTS_A = (fact("AAA", "Assets", val=1000.0, filed=date(2015, 8, 1), accn="0000-a1"),)
FACTS_B = (
    fact("AAA", "Assets", val=1000.0, filed=date(2015, 8, 1), accn="0000-a1"),
    fact("AAA", "Liabilities", val=400.0, filed=date(2015, 8, 1), accn="0000-a1"),
    fact("BBB", "Assets", val=2000.0, filed=date(2015, 8, 2), accn="0000-b1"),
)


def test_refresh_fundamentals_keeps_every_bar_and_swaps_the_panel(tmp_path, members_dir):
    """The whole point of phase 4, in one test.

    Facts A in, facts B over the top: the four carried files are byte-identical, the panel is
    not, the fingerprint moved, every _COUNT_KEYS value stayed, and load_store accepts the
    result.
    """
    store = tmp_path / "store"
    before = build(store, members_dir, facts=FACTS_A)
    before_bytes = {n: (store / n).read_bytes() for n in research.DATA_FILES}
    before_panel = (store / research.FUNDAMENTALS_FILE).read_bytes()

    after = research.refresh_fundamentals(store, FACTS_B, data_dir=members_dir)

    # the bars, dividends, fx and unserved rows survived byte for byte
    assert {n: (store / n).read_bytes() for n in research.DATA_FILES} == before_bytes
    assert {n: after["files"][n] for n in research.DATA_FILES} == {
        n: before["files"][n] for n in research.DATA_FILES
    }
    # the panel did not
    assert (store / research.FUNDAMENTALS_FILE).read_bytes() != before_panel
    assert (
        after["files"][research.FUNDAMENTALS_FILE]
        != before["files"][research.FUNDAMENTALS_FILE]
    )
    # the fingerprint changed, and that is correct
    assert after["fingerprint"] != before["fingerprint"]
    assert after["fingerprint"] == research.fingerprint_of(after["files"])
    # the counts did not, and neither did the window constants or the manifest's shape
    assert {k: after[k] for k in research._COUNT_KEYS} == {k: before[k] for k in research._COUNT_KEYS}
    assert after["dev_end"] == before["dev_end"] == "2015-10-16"
    assert after["store_start"] == before["store_start"] == "1993-01-29"
    assert set(after) == research.MANIFEST_KEYS
    assert after == json.loads(read(store, research.MANIFEST_FILE))

    data = research.load_store(store, data_dir=members_dir)
    assert data.fingerprint == after["fingerprint"]
    assert data.market.fundamentals.names() == ("AAA", "BBB")
    assert tuple(data.market.history) == SERVED  # the bars loaded back, unchanged
    assert not (tmp_path / "store.tmp").exists()
    assert not (tmp_path / "store.old").exists()


def test_refresh_fundamentals_adds_the_fifth_file_to_a_four_file_store(tmp_path, members_dir):
    """A store built before fundamentals existed is a legal source; the refresh adds the file."""
    store = tmp_path / "store"
    before = build(store, members_dir)  # facts=None: four files, no panel
    assert not (store / research.FUNDAMENTALS_FILE).exists()
    assert sorted(before["files"]) == sorted(research.DATA_FILES)
    before_bytes = {n: (store / n).read_bytes() for n in research.DATA_FILES}

    after = research.refresh_fundamentals(store, FACTS_A, data_dir=members_dir)

    assert {n: (store / n).read_bytes() for n in research.DATA_FILES} == before_bytes
    assert sorted(after["files"]) == sorted([*research.DATA_FILES, research.FUNDAMENTALS_FILE])
    assert after["fingerprint"] != before["fingerprint"]
    assert {k: after[k] for k in research._COUNT_KEYS} == {k: before[k] for k in research._COUNT_KEYS}
    data = research.load_store(store, data_dir=members_dir)
    assert data.market.fundamentals.names() == ("AAA",)


def test_refresh_fundamentals_is_deterministic_and_reversible(tmp_path, members_dir):
    """A -> B -> A gives back the ORIGINAL manifest, digest for digest.

    The strongest statement available that no byte of the price history moved: equality of the
    whole manifest covers every per-file sha256, every count and the fingerprint.
    """
    store = tmp_path / "store"
    original = build(store, members_dir, facts=FACTS_A)
    research.refresh_fundamentals(store, FACTS_B, data_dir=members_dir)
    back = research.refresh_fundamentals(store, FACTS_A, data_dir=members_dir)
    assert back == original
    assert read(store, research.FUNDAMENTALS_FILE) == (
        "\n".join([research.FUNDAMENTALS_HEADER, *research.fundamentals_lines(FACTS_A)]) + "\n"
    )


def test_refresh_fundamentals_writes_an_explicitly_empty_panel(tmp_path, members_dir):
    """`()` is legal and means "a panel with no facts"; None is not and says so."""
    store = tmp_path / "store"
    build(store, members_dir, facts=FACTS_A)
    research.refresh_fundamentals(store, (), data_dir=members_dir)
    assert read(store, research.FUNDAMENTALS_FILE) == research.FUNDAMENTALS_HEADER + "\n"
    assert research.load_store(store, data_dir=members_dir).market.fundamentals.names() == ()
    with pytest.raises(ValueError, match="pass [(][)] to write an empty panel"):
        research.refresh_fundamentals(store, None, data_dir=members_dir)


def test_refresh_fundamentals_refuses_a_missing_store(tmp_path):
    with pytest.raises(research.ResearchStoreError, match="no research store"):
        research.refresh_fundamentals(tmp_path / "nope", FACTS_A)
    assert not (tmp_path / "nope").exists()
    assert not (tmp_path / "nope.tmp").exists()


@pytest.mark.parametrize("name", research.DATA_FILES)
def test_refresh_fundamentals_refuses_a_tampered_store_and_writes_nothing(
    tmp_path, members_dir, name
):
    """A bad sha256 refuses; every file of the store, the old panel included, is left as it was."""
    store = tmp_path / "store"
    build(store, members_dir, facts=FACTS_A)
    with (store / name).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("X\n")
    kept = (*research.DATA_FILES, research.FUNDAMENTALS_FILE, research.MANIFEST_FILE)
    before = {n: (store / n).read_bytes() for n in kept}
    with pytest.raises(research.ResearchStoreError, match="does not verify"):
        research.refresh_fundamentals(store, FACTS_B, data_dir=members_dir)
    assert {n: (store / n).read_bytes() for n in kept} == before
    assert not (tmp_path / "store.tmp").exists()
    assert not (tmp_path / "store.old").exists()


def test_refresh_fundamentals_refuses_a_count_mismatch(tmp_path, members_dir):
    """Hashes can be made to agree; the counts cannot. Both gates refuse before any write."""
    store = tmp_path / "store"
    build(store, members_dir, facts=FACTS_A)
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["bar_rows"] = manifest["bar_rows"] + 1
    (store / research.MANIFEST_FILE).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    before = {n: (store / n).read_bytes() for n in (*research.DATA_FILES, research.FUNDAMENTALS_FILE)}
    with pytest.raises(research.ResearchStoreError, match="bar_rows"):
        research.refresh_fundamentals(store, FACTS_B, data_dir=members_dir)
    assert {n: (store / n).read_bytes() for n in before} == before
    assert not (tmp_path / "store.tmp").exists()


def test_command_refresh_fundamentals_rewrites_the_panel_and_never_downloads(
    tmp_path, members_dir, monkeypatch, capsys
):
    store = tmp_path / "store"
    before = build(store, members_dir, facts=FACTS_A)
    before_bytes = {n: (store / n).read_bytes() for n in research.DATA_FILES}
    monkeypatch.setattr(research_cmd, "_read_facts", lambda: FACTS_B)
    monkeypatch.setattr(
        research,
        "build_store",
        lambda *a, **k: pytest.fail("--refresh-fundamentals must never download bars"),
    )
    monkeypatch.setattr(
        research,
        "refresh_fundamentals",
        functools.partial(research.refresh_fundamentals, data_dir=members_dir),
    )
    code = cli.main(["research_store", "--refresh-fundamentals", "--store", str(store)])
    out = capsys.readouterr().out
    assert code == 1  # refreshed fine; the real-data checks fail on fake data, as for --verify
    after = json.loads(read(store, research.MANIFEST_FILE))
    assert {n: (store / n).read_bytes() for n in research.DATA_FILES} == before_bytes
    assert after["fingerprint"] != before["fingerprint"]
    assert f"fingerprint: {after['fingerprint']}" in out
    assert "rows: 71 bars, 2 dividends, 2 fx" in out  # the counts are the carried-over ones


def test_command_refresh_fundamentals_rejects_read_only_flags_and_a_missing_store(tmp_path, capsys):
    """Both read-only modes refuse to be combined with the one writing mode (phase 1 + phase 4)."""
    for flag in ("--verify", "--coverage"):
        assert cli.main(
            ["research_store", flag, "--refresh-fundamentals", "--store", str(tmp_path / "s")]
        ) == 2
    missing = cli.main(["research_store", "--refresh-fundamentals", "--store", str(tmp_path / "s")])
    assert missing == 2
    assert capsys.readouterr().out == ""


def test_command_refresh_dry_run_leaves_the_store_untouched(
    tmp_path, members_dir, monkeypatch, capsys
):
    store = tmp_path / "store"
    build(store, members_dir, facts=FACTS_A)
    kept = (*research.DATA_FILES, research.FUNDAMENTALS_FILE, research.MANIFEST_FILE)
    before = {n: (store / n).read_bytes() for n in kept}
    monkeypatch.setattr(research_cmd, "_read_facts", lambda: FACTS_B)
    monkeypatch.setattr(
        research,
        "refresh_fundamentals",
        functools.partial(research.refresh_fundamentals, data_dir=members_dir),
    )
    cli.main(["--dry-run", "research_store", "--refresh-fundamentals", "--store", str(store)])
    out = capsys.readouterr().out
    assert "dry run: refreshed a copy in a temporary directory and discarded it" in out
    assert {n: (store / n).read_bytes() for n in kept} == before
    assert not (tmp_path / "store.tmp").exists()
```

**Impact:** **+13 collected tests** — ten new test functions, one of which is parametrized over
the four `DATA_FILES`, so 9 + 4 = 13. (The original draft said "+9 functions / +12 collected";
both were miscounts and are corrected here.) `functools`, `json`, `pytest`, `date`, `cli`,
`research_cmd` and the `members_dir` fixture are all already imported or defined in this file;
only `Fact` is new.

Two notes on the command tests:

- `monkeypatch.setattr(research, "refresh_fundamentals", functools.partial(...))` works because
  `commands/research_store.py` calls `research.refresh_fundamentals(...)` through the module
  object, exactly as `test_command_builds_the_store` patches `research.build_store`. The partial
  injects the tiny `members_dir` so `load_store` does not read the real vendored CSVs.
- `_verify` afterwards calls `research.load_store(store)` with **no** `data_dir`, i.e. the real
  `membership.DATA_DIR`. That is already what `test_command_verify_prints_fingerprint_and_checks`
  does today and it needs no network — `compute_universe` reads vendored CSVs.

## Verification

Run the **Runtime preamble** first.

**Build:** `"$SEER_PY" -c "import seer_engine.research, seer_engine.commands.research_store"`

**Tests:**

```bash
cd "$SEER_WT"
"$SEER_PY" -m pytest engine/tests/test_research_store.py engine/tests/test_market_fundamentals.py -q
"$SEER_PY" -m pytest engine/tests -q
```

**The test delta, not an absolute.** This phase adds **+13** collected tests and changes no
existing one. It runs after phase 1 (+27), so off the `2dad9ff` baseline of 2216 the number on
screen will be **2256 passed, 332 skipped** if phases 1 and 4 are the only two merged, and more
once phase 2 (+5) lands. Report `+13` and "no existing test changed its result"; the binding
rule is invariant 1, which is about the direction, not the absolute.

**Manual check (no store on disk required):**

```bash
"$SEER_PY" -m seer_engine research_store --help | grep -A3 refresh-fundamentals
"$SEER_PY" -m seer_engine research_store --help | grep -A2 -- --coverage   # phase 1's, still there
```

Both flags appear with their help text. Do **not** run `--refresh-fundamentals` against
`engine/.research/` in this phase — phase 5 owns that run.

**Exit criteria:**

1. `research.refresh_fundamentals(store, facts)` exists, is the only new public symbol, and
   `build_store`, `load_store`, `_seal`, `MANIFEST_KEYS`, `_COUNT_KEYS`, `DATA_FILES`,
   `OPTIONAL_DATA_FILES`, `fingerprint_of`, `fundamentals_lines` and `_read_fundamentals` are
   byte-unchanged (`git diff` on `research.py` shows one added block and nothing else).
2. `test_refresh_fundamentals_keeps_every_bar_and_swaps_the_panel` passes: facts A in, facts B
   over the top, and `bars.csv` / `dividends.csv` / `fx.csv` / `unserved.csv` byte-identical,
   `fundamentals.csv` changed, the fingerprint changed, all five `_COUNT_KEYS` unchanged, and
   `load_store` accepting the result.
3. `test_refresh_fundamentals_refuses_a_missing_store`,
   `test_refresh_fundamentals_refuses_a_tampered_store_and_writes_nothing` (×4) and
   `test_refresh_fundamentals_refuses_a_count_mismatch` pass: a refusal leaves every byte of the
   store as it was and leaves no `.tmp` or `.old` behind.
4. `python -m seer_engine research_store --refresh-fundamentals` reaches it, `--verify` with it
   exits 2, and `--dry-run` with it writes nothing to the named store.
5. `"$SEER_PY" -m pytest engine/tests -q` reports **+13** against whatever this phase inherited
   and no new failure; `git status` shows exactly three modified files and nothing untracked.
6. Phase 1's `--coverage` flag, its `_coverage` handler and its branch in `run()` are all still
   present and unmodified — `git diff` on `commands/research_store.py` must show no deletion
   inside them.

## Handoffs

- **`_seal`'s stale docstring** (`research.py:506`) says `MANIFEST_KEYS` "is asserted as a whole
  set by `engine/tests/test_research_store.py`, which no phase of this plan set owns." The first
  clause is still true and still load-bearing; the second is now wrong — phase 4 owns that test
  file, additively. Deliberately **not** edited here, because this phase reuses `_seal` without
  touching it and a one-word docstring edit would put a diff hunk into a function three phases
  depend on reading unchanged. Left for a later doc pass.
- **Running the refresh against the real store** — phase 5. This phase ships the capability and
  tests it on stores it builds in `tmp_path`; `engine/.research/` is not opened. The command
  phase 5 will run is:
  `SEER_ENV_FILE=/home/miftah/seer/.env.local-train "$SEER_PY" -m seer_engine research_store --refresh-fundamentals --store /home/miftah/seer/engine/.research`
  — **absolute** `SEER_ENV_FILE` (index `## Decisions`, row C3) and an explicit `--store`,
  because the store lives only in the main checkout. It needs phase 3's re-ingested facts to be
  in that database first.
- **Coverage measurement of the refreshed panel** — phases 1 and 5 (R3, R4's reporting half).
  Nothing here imports `fundamentals.coverage`; the refresh neither measures nor refuses on
  coverage, by design. A `--coverage` run against the refreshed store is phase 5's step.
- **Recording the new fingerprint and re-pushing the store** — phase 5. The refresh changes the
  fingerprint by construction, so `/sync-research-store push` must follow it and the new content
  hash must be written down alongside the old `e597367b…`.
- **A `--refresh-fundamentals` paragraph in `docs/runbooks/data-pipeline.md`** — phase 5 owns
  `docs/**`. The flag is documented in this phase only inside the command's own module
  docstring.
- **Not done, and not this set's business:** `refresh_fundamentals` could in principle refresh
  any single optional file rather than `fundamentals.csv` specifically. There is exactly one
  optional file today, so generalising it would be speculation; it stays named for what it does.

## Rollback

This phase is one commit on `feature/fundamental-panel-coverage` touching three files and
nothing else: `git revert <sha>`. It has **no** side effect outside git — no store on disk is
written, no database row is read or written, no network call is made, and no method id is spent.
`engine/.research/` is byte-identical before and after this phase, so no
`/sync-research-store pull` is needed to undo it.

Reverting removes `research.refresh_fundamentals` and the `--refresh-fundamentals` flag; phase 5
then has no way to pick up a new panel without a full rebuild, and must either not run (the
plan's preference) or accept that a rebuild replaces every bar and breaks comparability with the
64 recorded trials. That dependency is the reason phase 5 lists phase 4 in its `Depends on`.
