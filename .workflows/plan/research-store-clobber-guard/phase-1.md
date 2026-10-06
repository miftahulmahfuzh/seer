# Phase 1: Content-based clobber guard on the build path

**Plan set:** `RESEARCH_STORE_CLOBBER_GUARD_PLAN.md`
**Analysis:** `20261006-143038-C4R9_code_analyzer.md`
**Satisfies:** R1 (a build refuses a wrong-window store in **any** checkout or worktree), R2 (the
existing same-checkout guard is not weakened, and the sibling paths are pinned by regression test)
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `seer_engine.commands`

---

## Goal

After this phase, `research_store`'s build path refuses to overwrite a store that declares the
*other* window, identified by the window in the target's own `manifest.json` rather than by
comparing the `--store` path against this process's `research.STORE_DIR`. The refusal therefore
fires for a store belonging to any checkout or worktree, not only the running one; it exits 2 and
writes nothing. The two existing path-comparison guards are left byte-for-byte unchanged and keep
firing first, so `test_research_test_store.py:449-452` still passes in a worktree where
`research.STORE_DIR` does not exist.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** `seer_engine.commands.research_store._declared_window_or_none(store: Path) -> research.Window | None`
(`engine/src/seer_engine/commands/research_store.py`, inserted between `_same_dir` and `run`)
**Signature changes:** none. `run(args)` keeps its signature and its exit-code vocabulary; one new
refusal returns the existing code `2`.
**New refusal message** (the only new log line; `log.error`, so it reaches stderr and `caplog`):

```
research_store: refusing to build the {dev|test} window into {store}: that directory already
holds a store declaring {the dev window | the test window YYYY-MM-DD..YYYY-MM-DD}, and a build
REPLACES the directory. A store is identified by the window its own manifest declares, not by
its path, so this holds for a store in any checkout or worktree. Point --store at the matching
directory, or remove that store first if it is genuinely disposable
```

Its distinguishing substring, which the tests match on, is `already holds a store declaring`.
The two existing messages (`refusing to act on the dev store`, `is the test store; pass
--test-window`) are untouched and remain distinct.

**Requires (from earlier phases):** none — this is the only phase.

**Leaves alone (owned by nobody in this set; must not be edited):**
`engine/src/seer_engine/research.py` · `engine/src/seer_engine/config.py` ·
`engine/src/seer_engine/commands/lab.py` · `engine/src/seer_engine/lab/runner.py` ·
`engine/src/seer_engine/commands/backtest_dev.py` · `engine/tests/test_research_store.py` ·
`engine/tests/test_fundamentals_coverage.py` · `.gitignore` · `.claude/skills/**` ·
the real `engine/.research` and `engine/.research-test` on disk (create neither, write neither).
Inside `research_store.py`, lines `:219-232` (both `_same_dir` guards) stay byte-for-byte.
Inside `test_research_test_store.py`, every existing function is appended after, never edited —
`:449-452` in particular must pass unedited.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/research_store.py` | modify | docstring `:27-31`; new helper after `_same_dir` (`:172`); new build-path guard between `:239` and `:241` |
| `engine/tests/test_research_test_store.py` | modify (append only) | 9 new test functions (11 collected items) after the current last line `:513` |
| `engine/package_readme.md` | modify | the one sentence at `:2372` |

## Measured facts this plan rests on

Every one of these was run in this worktree, with
`PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python`, before the plan was written.

| Fact | Measured result |
|---|---|
| `research.STORE_DIR` in this worktree | `.../research-store-clobber-guard/engine/.research`, **exists: False** |
| `research.TEST_STORE_DIR` in this worktree | `.../engine/.research-test`, **exists: False** |
| `declared_window(<missing dir>)` / `<empty dir>` / `<dir with "{not json">` | `ValueError` in all three |
| `declared_window(<dev store>)` | `research.DEV_WINDOW` |
| **The defect, forward:** `research_store --test-window --store <dev store under tmp_path>` | build **proceeds**, manifest replaced |
| **The defect, reverse:** `research_store --store <test store under tmp_path>` | build **proceeds**, `window_end` gone from the manifest |
| `--verify --test-window --store <dev store>` | 2 (already content-based) |
| `--refresh-fundamentals --test-window --store <dev store>` and `--refresh-fundamentals --store <test store>` | 2 each, **no database touched** (`_store_window` runs before `_read_facts`) |
| `--coverage --store <test store>` | 2, stdout empty (`load_store` → `_read_manifest` refuses before any data file) |
| `lab --db <tmp> test M0001-A --store <dev store>` with `runner.resolve_candidate` / `runner.preflight_test` stubbed | 2, `lab.store.test_looks(conn) == 0` |
| `caplog.text` after `cli.main([...])` | contains the `log.error` message without `caplog.at_level` |
| `--dry-run` before or after the subcommand | both accepted by the parser |
| build into a missing dir / empty dir / dir with an unparseable manifest, `--test-window` | 1 each (built; the fake-data checks fail), manifest sealed with `window_end` |
| dev rebuild over an existing dev store (`patched_build(..., end=research.DEV_END)`) | 1, 9 manifest keys, **identical fingerprint** |

> **A fake-data build exits 1, not 0.** `research.run_checks` fails on the synthetic market, exactly
> as `test_command_builds_a_test_store:492` already documents. Every "the build proceeded" assertion
> below therefore asserts `== 1` plus a sealed manifest, never `== 0`.

> **`patched_build`'s `end` must match the window being built.** Its `fx_for(end)` fake *asserts* the
> requested FX range. A CLI **dev** build under the default `end=TEST_END` fails inside the FX fetch
> and returns 1 having written nothing — which would make a "the rebuild proceeded" test pass for the
> wrong reason. Every dev-build test below passes `end=research.DEV_END`. This was measured: the first
> draft of the dev-rebuild test passed vacuously until the `end` was fixed.

## Implementation Steps

### Step 1: Say how the build refuses, in the module docstring

**File:** `engine/src/seer_engine/commands/research_store.py:27-31`
**Change:** Replace the five lines of the two-stores paragraph. The current text claims the command
"refuses to build one window into the other's directory" without saying what identifies the
directory; after this phase the answer is "the manifest, not the path", and that is the whole point
of the change.

**Code:** the paragraph as it stands today, for an unambiguous match —

```python
``--test-window`` builds through the latest completed NYSE session and records that date in the
manifest (``window_start`` / ``window_end``); ``--window-end`` pins it instead, so an
interrupted build can be resumed to the same end rather than silently moving. The two stores
are **not** interchangeable: ``research.load_store`` refuses a store whose declared window is
not the one the caller asked for, this command refuses to build one window into the other's
directory, and ``--verify`` / ``--refresh-fundamentals`` refuse a store whose declared window
disagrees with ``--test-window``.
```

— replaced by:

```python
``--test-window`` builds through the latest completed NYSE session and records that date in the
manifest (``window_start`` / ``window_end``); ``--window-end`` pins it instead, so an
interrupted build can be resumed to the same end rather than silently moving. The two stores
are **not** interchangeable: ``research.load_store`` refuses a store whose declared window is
not the one the caller asked for, and ``--verify`` / ``--refresh-fundamentals`` refuse a store
whose declared window disagrees with ``--test-window``. A **build** is refused twice over. By
name: ``--store`` naming this checkout's own ``engine/.research`` under ``--test-window``, or
its ``engine/.research-test`` without it, is refused on the path alone. By content: the build
reads the target's own ``manifest.json`` (``research.declared_window``) and refuses, exit 2,
when the store already in that directory declares the other window. The content check is on the
store's manifest and never on the path, so it refuses a wrong-window store belonging to **any**
checkout or worktree, not only the running one. When the target holds no store, or one whose
manifest will not parse, the window cannot be told and the build proceeds -- the first build of
all is exactly that case.
```

**Impact:** documentation only; no behaviour. It is in the same edit as the code so the two cannot
drift.

### Step 2: The helper — "which window does this directory's store declare, if it can be told?"

**File:** `engine/src/seer_engine/commands/research_store.py:168-175` (insert between `_same_dir`
and `run`)
**Change:** Add one module-level function. `_same_dir` above it and `def run` below it are not
touched; the new function goes in the two blank lines between them.

**Code:** the region after the edit, from `_same_dir` through `def run`'s first line, so the
insertion point is unambiguous —

```python
def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:  # pragma: no cover - an unresolvable path is simply not the same one
        return a == b


def _declared_window_or_none(store: Path) -> research.Window | None:
    """The window the store at ``store`` declares, or ``None`` when that cannot be told.

    ``research.declared_window`` reads the target's own ``manifest.json`` and nothing else, so the
    answer is a property of the **store**, not of the path: it is the same for a store in this
    checkout and for one in a worktree five directories away. That is what makes the build guard
    in :func:`run` checkout-independent where ``_same_dir`` is not.

    ``None`` means *undecidable*, never *wrong*. A missing directory, an empty one and an
    unparseable ``manifest.json`` all raise ``ValueError`` from ``declared_window`` (an unreadable
    one can raise ``OSError``), and a build into any of those destroys no store -- the very first
    build is exactly the missing-directory case -- so the caller falls through instead of refusing.
    A half-written manifest cannot occur in a published store: ``build_store`` writes ``<store>.tmp``
    and ``research._swap_in`` publishes it with ``os.replace``.

    Deliberately not in ``research.py``: that module already exports ``declared_window``, which is
    the whole mechanism. This is the command's own "cannot tell" convention wrapped around it.
    """
    try:
        return research.declared_window(store)
    except (OSError, ValueError):
        return None


def run(args: argparse.Namespace) -> int:
```

**Impact:** no behaviour on its own; nothing calls it until step 3. Adds no import (`research` and
`Path` are already imported at `:67` and `:69`) and names neither `seer_engine.db` nor `psycopg`,
so `test_no_neon_and_no_database_url_needed` stays green.

### Step 3: The guard, on the build path only

**File:** `engine/src/seer_engine/commands/research_store.py:239-241`
**Change:** Insert the content check **after** the read-only and refresh dispatch (`:234-239`) and
**before** `window = research.DEV_WINDOW` (`:241`). That position is both *after* the two
`_same_dir` guards and *on the build path only*: `--coverage`, `--verify` and
`--refresh-fundamentals` have already returned by then, and they are already content-guarded by
`_store_window` (R2, pinned by the tests in step 5).

The guard runs before the `--dry-run` branch at `:258`, so a dry run is refused too. That is
deliberate and costs nothing: a dry run is a rehearsal of a build that would clobber, and the two
existing `_same_dir` guards already refuse it for the same reason.

**Code:** the region after the edit, from the refresh dispatch through the first lines of the build
branch, so the insertion point is unambiguous —

```python
    if coverage_mode:
        return _coverage(store)
    if args.verify:
        return _verify(store, note="", test=test)
    if refresh:
        return _run_refresh(store, bool(getattr(args, "dry_run", False)), test)

    # Past this point the command BUILDS, and a build replaces the whole directory
    # (``research._swap_in``). The two guards above compare PATHS, so they can only ever fire
    # inside this checkout -- ``research.STORE_DIR`` is derived from the running module's own
    # location. This one compares CONTENT: it asks the target which window the store sitting in it
    # declares, which is true of a store in any checkout or worktree. When the window cannot be
    # told there is no store there to destroy, so the build proceeds; that is the first build of
    # all, and it is why this check is additive to the two above rather than a replacement.
    declared = _declared_window_or_none(store)
    if declared is not None and (declared != research.DEV_WINDOW) != test:
        have = (
            "the dev window"
            if declared == research.DEV_WINDOW
            else f"the test window {declared.start.isoformat()}..{declared.end.isoformat()}"
        )
        log.error(
            "research_store: refusing to build the %s window into %s: that directory already "
            "holds a store declaring %s, and a build REPLACES the directory. A store is "
            "identified by the window its own manifest declares, not by its path, so this holds "
            "for a store in any checkout or worktree. Point --store at the matching directory, "
            "or remove that store first if it is genuinely disposable",
            "test" if test else "dev",
            store,
            have,
        )
        return 2

    window = research.DEV_WINDOW
    if test:
        try:
            window = research.test_window(
                window_end if window_end is not None else research.latest_session()
            )
        except (TypeError, ValueError) as exc:
            log.error("research_store: %s", exc)
            return 2
        log.info(
            "research_store: building the test window %s..%s into %s",
            window.start.isoformat(),
            window.end.isoformat(),
            store,
        )
```

**Impact:** R1 closed. A `--test-window` build over a dev store and a dev build over a test store
now exit 2 and write nothing, wherever the store lives. Exactly four target shapes still fall
through — missing, empty, unparseable manifest, same-window store — and step 5 pins all four. The
`(declared != research.DEV_WINDOW)` spelling is the same predicate `_store_window:307` uses, so
"which window is this" has one definition in this module, not two.

### Step 4: The README sentence

**File:** `engine/package_readme.md:2372`
**Change:** Replace the single bullet line. It is one physical line in the file; the text below is
that whole line, before and after.

**Code:** the line as it stands today —

```markdown
- **A dev store and a test store are never interchangeable** (build-promotion-path phase 2). They live in different directories (`engine/.research` vs `engine/.research-test`) and a store declares which it is in its manifest, so `load_store` refuses the wrong one *before* reading any data file, and `research_store` refuses to build or verify one window against the other's directory even when `--store` names it explicitly. Do not "fix" a mismatch by pointing `--store` or `SEER_RESEARCH_STORE` somewhere else: the test store holds the same history **and** every session after `DEV_END`, so running the dev pipeline on it would spend unseen data silently.
```

— replaced by:

```markdown
- **A dev store and a test store are never interchangeable** (build-promotion-path phase 2; the build guard is content-based since research-store-clobber-guard). They live in different directories (`engine/.research` vs `engine/.research-test`) and a store declares which it is in its manifest, so `load_store` refuses the wrong one *before* reading any data file, and `research_store` refuses to build or verify one window against the other's directory even when `--store` names it explicitly — the **build** check reads the target's own `manifest.json` (`research.declared_window`), not the `--store` path, so it refuses a wrong-window store in **any** checkout or worktree and not merely this one, and falls through only when the directory holds no readable store at all. Do not "fix" a mismatch by pointing `--store` or `SEER_RESEARCH_STORE` somewhere else: the test store holds the same history **and** every session after `DEV_END`, so running the dev pipeline on it would spend unseen data silently.
```

**Impact:** documentation only.

### Step 5: The tests

**File:** `engine/tests/test_research_test_store.py` — **append** after the current last line
(`:513`, the closing `assert` of `test_command_window_end_pins_the_build`). Nothing above line 513
is edited: the header imports stay `from seer_engine import cli, config, research`, and the two
`lab` imports the last test needs are function-local for exactly that reason.

Every test reuses the file's existing helpers — `build`, `read`, `patched_build`, the `members_dir`
fixture and the `TEST_END` constant. `tmp_path` is outside the running checkout, which is precisely
what makes these the cross-checkout cases: `_same_dir(tmp_path/..., research.STORE_DIR)` is `False`,
so the two path guards cannot fire and only the new content guard can refuse. Two of the tests
assert that explicitly.

Every refusal test also installs `patched_build`, so that a regression which let the build run would
hit the injected fakes and flip the assertion, rather than reaching yfinance from the test suite.

**Change:** append these 9 functions (11 collected items).

**Code:**

```python
# ---- command: the cross-checkout clobber guard (build path) --------------------------------------


def test_command_build_refuses_a_cross_checkout_dev_store(
    tmp_path, members_dir, monkeypatch, caplog
):
    """R1 forward: --test-window over a dev store that belongs to ANOTHER checkout.

    ``tmp_path`` is outside the running checkout, so ``_same_dir(store, research.STORE_DIR)`` is
    False and the path guard at research_store.py:219 cannot fire. Only the content guard can
    refuse here, and before this phase the build proceeded and replaced the manifest (measured).
    """
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "other-checkout" / "engine" / ".research"
    store.parent.mkdir(parents=True)
    build(store, members_dir)
    before = read(store, research.MANIFEST_FILE)
    assert store.resolve() != research.STORE_DIR.resolve()  # the path guard cannot fire

    code = cli.main(["research_store", "--test-window", "--store", str(store)])

    assert code == 2
    assert "already holds a store declaring" in caplog.text
    assert str(store) in caplog.text
    assert "the dev window" in caplog.text
    assert read(store, research.MANIFEST_FILE) == before  # not one byte written
    assert set(json.loads(before)) == research.MANIFEST_KEYS
    assert not (store.parent / ".research.tmp").exists()
    assert not (store.parent / ".research.old").exists()
    # A dry run is a rehearsal of the same destructive build and is refused the same way.
    assert cli.main(["--dry-run", "research_store", "--test-window", "--store", str(store)]) == 2
    assert read(store, research.MANIFEST_FILE) == before


def test_command_build_refuses_a_cross_checkout_test_store(
    tmp_path, members_dir, monkeypatch, caplog
):
    """R1 reverse: a dev build aimed at another checkout's test store. Lower stake, same defect.

    ``end=research.DEV_END`` because a dev build asks Frankfurter for FX through DEV_END and
    ``patched_build``'s fake asserts the range; with the default end a regression would fail inside
    the FX fetch and this test would pass for the wrong reason.
    """
    patched_build(monkeypatch, members_dir, end=research.DEV_END)
    store = tmp_path / "other-checkout" / "engine" / ".research-test"
    store.parent.mkdir(parents=True)
    build(store, members_dir, window=research.test_window(TEST_END))
    before = read(store, research.MANIFEST_FILE)
    assert store.resolve() != research.TEST_STORE_DIR.resolve()  # the path guard cannot fire

    code = cli.main(["research_store", "--store", str(store)])

    assert code == 2
    assert "already holds a store declaring" in caplog.text
    assert str(store) in caplog.text
    assert f"the test window 2015-10-19..{TEST_END.isoformat()}" in caplog.text
    assert read(store, research.MANIFEST_FILE) == before
    assert json.loads(before)["window_end"] == TEST_END.isoformat()
    assert not (store.parent / ".research-test.tmp").exists()


@pytest.mark.parametrize("shape", ["missing", "empty", "unparseable"])
def test_command_build_proceeds_when_the_window_cannot_be_told(
    tmp_path, members_dir, monkeypatch, capsys, shape
):
    """The three undecidable shapes fall through. ``missing`` is the first build of all, and it is
    also ``research.STORE_DIR`` in every worktree, which is why the guard may never refuse it."""
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "target"
    if shape in ("empty", "unparseable"):
        store.mkdir()
    if shape == "unparseable":
        (store / research.MANIFEST_FILE).write_text("{not json", encoding="utf-8")

    code = cli.main(["research_store", "--test-window", "--store", str(store)])

    capsys.readouterr()
    assert code == 1  # built fine; the real-data checks fail on fake data
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    assert manifest["window_end"] == TEST_END.isoformat()
    assert manifest["window_name"] == "test"


def test_command_build_allows_a_same_window_dev_rebuild(
    tmp_path, members_dir, monkeypatch, capsys
):
    """A rebuild over a store of the SAME window is legitimate and must not be refused:
    ``--with-fundamentals`` over an existing dev store is the documented routine."""
    patched_build(monkeypatch, members_dir, end=research.DEV_END)
    store = tmp_path / "dev"
    first = build(store, members_dir)

    code = cli.main(["research_store", "--store", str(store)])

    out = capsys.readouterr().out
    assert code == 1
    second = json.loads(read(store, research.MANIFEST_FILE))
    assert set(second) == research.MANIFEST_KEYS  # still nine keys, still no window key
    assert second["fingerprint"] == first["fingerprint"]  # it really rebuilt the same store
    assert "store_start: 1993-01-29" in out


def test_command_build_allows_a_same_window_test_rebuild(
    tmp_path, members_dir, monkeypatch, capsys
):
    patched_build(monkeypatch, members_dir)
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))

    code = cli.main(["research_store", "--test-window", "--store", str(store)])

    capsys.readouterr()
    assert code == 1
    assert json.loads(read(store, research.MANIFEST_FILE))["window_end"] == TEST_END.isoformat()


# ---- R2: the sibling paths were never checkout-local, and these pin it -----------------------------


def test_command_verify_refuses_a_cross_checkout_dev_store(tmp_path, members_dir, capsys):
    """The direction ``test_command_verify_refuses_a_cross_window_store`` does not cover: a DEV
    store under --test-window. Content-based through ``_store_window``, with no edit to it."""
    store = tmp_path / "dev"
    build(store, members_dir)
    assert cli.main(["research_store", "--verify", "--test-window", "--store", str(store)]) == 2
    assert capsys.readouterr().out == ""


def test_command_refresh_fundamentals_refuses_a_cross_checkout_store(tmp_path, members_dir):
    """Both directions, and no database is reached: ``_run_refresh`` calls ``_store_window``
    before ``_read_facts``, so the refusal happens with no DATABASE_URL in the environment."""
    dev = tmp_path / "dev"
    build(dev, members_dir)
    assert (
        cli.main(["research_store", "--refresh-fundamentals", "--test-window", "--store", str(dev)])
        == 2
    )
    test = tmp_path / "test"
    build(test, members_dir, window=research.test_window(TEST_END))
    assert cli.main(["research_store", "--refresh-fundamentals", "--store", str(test)]) == 2
    assert read(dev, research.MANIFEST_FILE)  # both stores still there, unread and unwritten
    assert json.loads(read(test, research.MANIFEST_FILE))["window_end"] == TEST_END.isoformat()


def test_command_coverage_refuses_a_cross_checkout_test_store(tmp_path, members_dir, capsys):
    """--coverage has no ``_store_window`` call, but ``load_store`` defaults to DEV_WINDOW and
    ``_read_manifest`` compares the declaration before opening a single data file."""
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    assert cli.main(["research_store", "--coverage", "--store", str(store)]) == 2
    assert capsys.readouterr().out == ""  # the number is never printed for a refused store


def test_command_lab_test_refuses_a_cross_checkout_dev_store(tmp_path, members_dir, monkeypatch):
    """``lab test --store`` was already content-guarded at commands/lab.py:484. Pinned, not edited.

    ``resolve_candidate`` and ``preflight_test`` are stubbed because they run before the store is
    read and would otherwise refuse first, for an unrelated reason; the window check is then the
    first thing that actually runs. The two imports are function-local so this file's import block
    stays byte-for-byte as it was. ``runner.run_test``'s second, independent refusal is already
    pinned by ``test_lab_test_window.py:215-221`` and is not duplicated here.
    """
    from seer_engine.lab import runner
    from seer_engine.lab import store as lab_store

    store = tmp_path / "dev"
    build(store, members_dir)
    monkeypatch.setattr(runner, "resolve_candidate", lambda cid: (None, tmp_path / "m.py", None))
    monkeypatch.setattr(runner, "preflight_test", lambda conn, method, path, candidate: None)
    db = tmp_path / "lab.sqlite"

    code = cli.main(["lab", "--db", str(db), "test", "M0001-A", "--store", str(store)])

    assert code == 2
    conn = lab_store.connect(db)
    try:
        assert lab_store.test_looks(conn) == 0  # the one counted look was not spent
    finally:
        conn.close()
```

**Impact:** +11 collected tests. None of them builds, reads or writes a real store: every store
lives under `tmp_path`, every build goes through `build` / `patched_build` with the injected
yfinance and Frankfurter fakes, and the lab database is a fresh file under `tmp_path`.
`engine/.research` and `engine/.research-test` are never named except through
`research.STORE_DIR.resolve()` / `research.TEST_STORE_DIR.resolve()` in two inequality assertions,
which touch the filesystem not at all beyond a path resolve.

## Verification

**Build:** there is no compile step; import is the check.

```bash
cd /home/miftah/.worktrees/seer/research-store-clobber-guard
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -c \
  "import seer_engine.commands.research_store as m; print(m._declared_window_or_none.__name__)"
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m ruff check engine/src engine/tests
```

(If `ruff` is not on that interpreter, skip it — CI lints `E9,F` only and this change introduces no
new name.)

**Tests:**

```bash
cd /home/miftah/.worktrees/seer/research-store-clobber-guard

# the phase's own file first
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  engine/tests/test_research_test_store.py -q

# the invariant that forces the check to be additive, on its own, by name
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  engine/tests/test_research_test_store.py -q \
  -k test_command_refuses_the_test_window_on_the_dev_store

# the two files this phase must not break and must not edit
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  engine/tests/test_research_store.py engine/tests/test_fundamentals_coverage.py \
  engine/tests/test_lab_test_window.py -q

# the whole suite
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

**Expected counts.** Baseline on this base was **2469 passed, 360 skipped**. This phase adds 11
collected tests and removes none, so the suite must end at **2480 passed, 360 skipped, 0 failed**.
The 360 skips are PG-gated and pre-existing; `PG_TEST_URL` is not set and must not be.

**Manual check:**

```bash
cd /home/miftah/.worktrees/seer/research-store-clobber-guard
git diff --stat   # exactly 3 files; no .research*, no .gitignore, no research.py, no lab.py
git diff engine/src/seer_engine/commands/research_store.py | grep -c '^-'   # only the 7 docstring lines
test -e engine/.research && echo FAIL || echo "no store created, good"
test -e engine/.research-test && echo FAIL || echo "no test store created, good"
```

On the **main** checkout (read-only, do not run any build there):

```bash
cd /home/miftah/seer
python - <<'PY'
import hashlib, pathlib
p = pathlib.Path("engine/.research/manifest.json")
print(p.exists(), hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "")
PY
sqlite3 lab/lab.sqlite "SELECT window, count(*) FROM trials GROUP BY window;"   # dev 85, no test row
```

The manifest must be byte-identical to before the phase (it is never opened by this work), and
`engine/.research-test` must still be absent.

**Exit criteria:**

1. `research_store --test-window --store <dir under tmp_path holding a dev store>` exits 2, logs
   `already holds a store declaring ... the dev window`, and leaves the manifest byte-identical.
2. `research_store --store <dir under tmp_path holding a test store>` exits 2 the same way, naming
   the test window and its dates.
3. A build into a missing directory, an empty one, or one with an unparseable `manifest.json` still
   proceeds; so does a rebuild over a store of the same window, with the dev rebuild's fingerprint
   unchanged and its manifest still exactly the nine `MANIFEST_KEYS`.
4. `engine/tests/test_research_test_store.py:449-452` passes **unedited** in this worktree, where
   `research.STORE_DIR` does not exist.
5. The four sibling-path regression tests pass against sibling code that was not edited
   (`git diff --stat` shows neither `commands/lab.py` nor `lab/runner.py`).
6. `pytest engine/tests -q` reads **2480 passed, 360 skipped**.
7. `engine/.research/manifest.json` on the main checkout is byte-identical, `engine/.research-test`
   is still absent, and `lab/lab.sqlite` still reads 85 dev trials and 0 test trials.

## Handoffs

Found while planning, deliberately **not** done here:

- **`lab run --store` and `backtest_dev --store` have no window guard of their own** — they rely on
  `load_store`'s DEV_WINDOW default, which refuses a test store before reading a data file. That is
  correct and sufficient (a read destroys nothing), and both are on the "must not touch" list. No
  requirement in this set asks for more. Noted so the absence is a decision, not an oversight.
- **`config.REPO_ROOT`'s module-relative derivation** stays as it is. It is the *cause* of the
  checkout-locality and is relied on by `lab.py` and `backtest_dev.py` for their defaults; this
  phase stops *using* it as the definition of "a dev store" without changing what it is. Any future
  change there is its own plan set and serves no requirement here.
- **No blanket refusal of an out-of-checkout `--store`** (index Decisions, fork 2). Sera's child
  sessions export `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` from their own worktrees;
  refusing cross-checkout paths outright would break that and would refuse a harmless cross-checkout
  `--verify`. If that trade is ever revisited it is a new requirement, not a widening of R1.
- **`research.declared_window` gains no new behaviour.** The "cannot tell" convention lives in the
  command, in `_declared_window_or_none`. If a second command ever needs it, promote the helper then
  — not now, on one caller.

## Rollback

One commit, three files, nothing migrated and nothing published.

```bash
cd /home/miftah/.worktrees/seer/research-store-clobber-guard
git checkout -- engine/src/seer_engine/commands/research_store.py \
                engine/tests/test_research_test_store.py \
                engine/package_readme.md
```

After a merge to `main`, `git revert` the merge commit. The change is additive refusal logic plus
tests: reverting restores today's behaviour exactly. There is no data rollback and none is needed —
the phase writes no research store, spends no test-window look, and makes no lab-database write, so
nothing outside these three files ever changed.
