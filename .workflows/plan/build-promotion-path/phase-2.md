# Phase 2: Build and load the test-window store

**Plan set:** `BUILD_PROMOTION_PATH_PLAN.md`
**Analysis:** `20261006-115723-B7K2_code_analyzer.md`
**Satisfies:** R1 — a test-window research store (2015-10-19 → latest session), built like the dev store, with the same files, manifest and checks
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine` (`research.py`, `commands/research_store.py`)

---

## Interface from Phase 1 (final, settled by the coordinator)

Phase 1 owns the window value object and the window-bearing helpers in `research.py`. Its
contract is final and this plan is written against it:

```python
# seer_engine/backtest/window.py (new leaf module; imports nothing from seer_engine.research)

WINDOW_NAMES = ("dev", "test")

@dataclass(frozen=True)
class Window:
    name: str     # one of WINDOW_NAMES
    start: date   # first session the window trades and scores
    end: date     # last session; the D9 bound

    def covers(self, d: date) -> bool: ...
    def following(self, name: str, end: date) -> "Window": ...
```

and, in `research.py`:

```python
DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)

def _overlaps_window(iv: membership.Interval, window: Window = DEV_WINDOW) -> bool
def requested_symbols(data_dir: Path | None = None, *, window: Window = DEV_WINDOW) -> tuple[str, ...]
def research_membership(data_dir: Path | None = None, *, window: Window = DEV_WINDOW) -> Membership
def unserved_by_year(members: Membership, unserved: Iterable[str], *, window: Window = DEV_WINDOW) -> tuple[tuple[int, int, int], ...]
def unserved_reason(start: date = STORE_START, end: date = DEV_END) -> str   # replaces the UNSERVED_REASON constant
```

Phase 1 names four sites it expects **this** phase to fill in, and this plan fills exactly
those: `research.py:320` (`requested_symbols` inside `build_store`, Step 3), `research.py:337`
(`unserved_reason(STORE_START, window.end)`, Step 3), `research.py:684`
(`research_membership` inside `load_store`, Step 7) and
`commands/research_store.py:261` (`unserved_by_year`, Step 15).

Two properties of that contract this phase depends on, stated so the reconciler can check them:

1. **`research.py` reads only `window.end` to bound the *data range*.** `DEV_WINDOW.start` is
   `date.min`, which is precisely the point: the window's `start` never says what the store
   *holds*. The bar range stays `STORE_START..window.end` and the FX range
   `FX_START..window.end` for **both** windows — that is the coordinator decision below.

   **But `window.start` does bound the universe and the membership tally** (reconciled
   2026-10-06; see the plan index's Decisions row "the test store's universe"). Phase 1's
   `_members_start(window)` is `max(window.start, MEMBERSHIP_START)`, so:
   - dev window: `max(date.min, MEMBERSHIP_START)` = `MEMBERSHIP_START` — byte-identical to
     today, which is what keeps the dev store's fingerprint fixed;
   - test window: `2015-10-19` — the universe is exactly the companies that are index members
     on some session of the test window, and `unserved_by_year` runs `2015..window.end.year`.

   This costs the test run nothing: `members_on(t)` for every `t >= 2015-10-19` is identical
   under either lower bound, because an interval that closed before 2015-10-19 contributes no
   member on any test-window session. What changes is only how many symbols the crawl
   downloads and what the unserved tally covers. A company that left the index in 2000 is never
   ranked, held or exited on a test-window session, so its "deep history" is history nothing
   reads. Run-up is a *date-range* property (`STORE_START`), settled by the coordinator
   decision below, not a *symbol-selection* property.
2. **`unserved_reason(STORE_START, DEV_END)` must be byte-identical to today's
   `UNSERVED_REASON`** (`"yfinance returned no bars for 1993-01-29..2015-10-16"`). It is written
   into `unserved.csv`, which is hashed into the fingerprint. One changed character changes
   `399d0d25…` and breaks cross-machine sync plus every recorded trial's provenance.
   `test_research_store.py:256` pins it.

`research.py` never names `Window(...)` directly: `_window()` builds every window with
`dataclasses.replace(DEV_WINDOW, name=…, start=…, end=…)`, so a `Window` that grows a field
needs no edit here. `test_window(end)` must agree with `DEV_WINDOW.following("test", end)`;
Step 17 asserts that so the two phases cannot drift.

### Coordinator decision: the test store carries the FULL history

**Settled, not reversible later:** the test store holds `research.STORE_START` (1993-01-29)
through the latest available session. It is **not** truncated to the test window's first
session. Rung: design §3, "built the way `research.build_store` builds the dev store".

The test *window* (`start = 2015-10-19`) bounds which sessions are traded and scored; the
*store* carries the run-up a candidate's lookback needs. This mirrors the dev store exactly:
the dev store holds 1993→2015-10-16 while `dev.candidate_window` only trades from the first
session where every symbol's lookback is covered. A test store opening at 2015-10-19 would push
a 12-1 momentum candidate's only look ~10 months late, and because a trial row is append-only
and the test window gets exactly **one** look per configuration, that wrong number would be
permanent.

Two consequences this plan carries explicitly:

- The test store's date range is a **superset** of the dev store's, so "refuse to load a test
  store where a dev store is expected" matters *more*, not less: a mis-pointed
  `SEER_RESEARCH_STORE` would otherwise hand the dev pipeline post-2015 bars and defeat D9
  silently. The refusal is raised before any data file is read (Step 8) and is tested in both
  directions (Step 17).
- The universe/membership point is unchanged by this: symbols are the **test** window's
  members, and membership intervals clamp against the **test** window's end, not `DEV_END`.

---

## Goal

After this phase, `python -m seer_engine research_store --test-window` builds
`engine/.research-test`: the same five CSV files, the same manifest shape, the same sha256 +
fingerprint verification and the same three checks as the dev store, holding the same history
from `STORE_START` (1993-01-29) **and** every session after `DEV_END` through the latest
completed NYSE session, with the universe and the membership intervals resolved against *that*
end. The window it declares (2015-10-19 → that end) says what gets scored, not what gets
stored — the run-up a candidate's lookback needs is in the files. A store now declares the window it
was built for, and `load_store` refuses to hand a test store to a caller expecting a dev store
or the reverse. The dev store at `engine/.research` keeps loading bit-identically: its manifest
gains nothing, its files are not touched, and its fingerprint is still
`399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`.

**No crawl is run by this phase.** Building the real test store is an operator action, taken
the first time something is promoted (design §3). Every test here injects fakes and touches no
network.

---

## Interface Contract

**Creates:**
- `research.TEST_STORE_DIR` (`research.py`) — `config.REPO_ROOT / "engine" / ".research-test"`
- `research.TEST_WINDOW_START` (`research.py`) — `date(2015, 10, 19)`
- `research.test_window(end: date) -> Window` (`research.py`)
- `research.latest_session(now_utc: datetime | None = None) -> date` (`research.py`)
- `research.declared_window(store_dir: Path) -> Window` (`research.py`)
- `research.WINDOW_NAME_KEY` / `research.WINDOW_START_KEY` / `research.WINDOW_END_KEY`
  (`research.py`) — `"window_name"` / `"window_start"` / `"window_end"`
- `research.OPTIONAL_MANIFEST_KEYS: frozenset[str]` (`research.py`) —
  `{"window_name", "window_start", "window_end"}`
- `research.ResearchData.window: Window` — new field, defaults to `DEV_WINDOW` (so
  `engine/tests/labkit.py:52`'s `smoke_data`, which names neither `unserved` nor `window`,
  keeps working unchanged)
- `research._window`, `research._is_dev_window`, `research._declared_window`,
  `research._manifest_json`, `research._window_label`, `research._after_window_end`
  (private, `research.py`)
- `commands/research_store.py`: `--test-window` flag, `--window-end DATE` flag,
  `_session_date`, `_store_window`, `_same_dir`
- `.gitignore` entries `engine/.research-test/`, `engine/.research-test.tmp/`,
  `engine/.research-test.old/`
- `engine/tests/test_research_test_store.py` (new file)

**Signature changes:**
- `research.build_store(…)` -> `research.build_store(…, *, window: Window = DEV_WINDOW)`
- `research.load_store(store_dir, *, data_dir=None)` -> `research.load_store(store_dir, *, data_dir=None, window: Window = DEV_WINDOW)`
- `research.refresh_fundamentals(store_dir, facts, *, data_dir=None)` -> `(…, *, data_dir=None, window: Window = DEV_WINDOW)`
- `research.check_spy_sessions(data, start=SPY_CHECK_START, end=DEV_END)` -> `(data, start=SPY_CHECK_START, end=None)` (`None` means `data.window.end`)
- `research._seal(tmp, counts, *, extra_files=())` -> `(…, *, extra_files=(), window=DEV_WINDOW)`
- `research._read_manifest(store_dir)` -> `(store_dir, window)`
- `research._read_bars(path)` / `_read_dividends(path)` / `_read_fx(path)` -> each gains `end: date`
- `research._fetch_fx_rows(fetch_rates)` -> `(fetch_rates, end)`
- `research._write_bars(tmp, symbols, fetch, sleep, batch_size)` -> `(…, end)`
- `research._fetch_batch(batch, fetch, sleep)` -> `(…, end)`
- `research._download_with_backoff(symbols, fetch, sleep)` -> `(…, end)`
- `research._in_window(history)` -> `(history, end)`
- `commands/research_store._build(store, batch_size, facts)` -> `(…, window)`
- `commands/research_store._verify(store, *, note)` -> `(store, *, note, test=False)`
- `commands/research_store._run_refresh(store, dry_run)` -> `(store, dry_run, test)`
- `commands/research_store._refresh(store, facts)` -> `(store, facts, window)`
- `commands/research_store.format_summary` — unchanged signature, gains one printed line
- `--store`'s argparse default moves from `research.STORE_DIR` to `None`, resolved in `run()`

**Deletes:** `research._after_dev_end` (`research.py:760`) — replaced by `_after_window_end`,
which emits the current message verbatim when the window end is `DEV_END`.

**Renames:** none.

**Requires (from earlier phases):** Phase 1's `Window` / `DEV_WINDOW`, and
`requested_symbols` / `research_membership` / `unserved_by_year` / `unserved_reason` accepting
`window=`. See **Assumed interface from Phase 1** above.

**Leaves alone (owned by others):** `backtest/dev.py` and `backtest/window.py` (Phase 1);
`lab/runner.py`, `commands/lab.py`, `commands/promote.py`, everything under `lab/` (Phases 3,
4); `engine/tests/test_fundamentals_coverage.py` — **not one byte**; `fundamentals/coverage.py`
and its `WINDOW_END`.

**File collision, handled:** Phase 1 also edits `engine/tests/test_research_store.py` (one
import plus an appended section; no existing test function touched). **This phase does not edit
that file at all** — every addition goes in the new `engine/tests/test_research_test_store.py`.
Where this plan quotes assertions from `test_research_store.py` it quotes the existing
functions, which phase 1 leaves intact, so the two phases cannot collide there.

**For Phase 4, the three things you asked about:**

1. **How a caller selects the test store.** Two independent choices, both explicit:
   - *the directory*: `research.TEST_STORE_DIR` (`engine/.research-test`), or whatever the
     operator passes; and
   - *the window*: `research.load_store(path, window=w)` where
     `w = research.declared_window(path)`. `declared_window` reads `manifest.json` alone (no
     data files, no verification) and answers "which window is this store for?"; `load_store`
     then verifies that the answer matches what you asked for. The idiomatic test-runner
     opening is:
     ```python
     window = research.declared_window(store_path)
     if window == research.DEV_WINDOW:
         raise store.LabError(f"{store_path} is a dev store; `lab test` needs the test store")
     data = research.load_store(store_path, window=window)   # data.window == window
     ```
     `data.window.start` is `2015-10-19` and `data.window.end` is the session the store was
     built through — read them, never hardcode them.
2. **The manifest's window identity.** Three optional keys — `window_name` (a member of
   `WINDOW_NAMES`, never `"dev"`), `window_start` and `window_end` (ISO dates) — present
   together or not at all. **Absent means the dev window** — exactly the precedent `load_store`
   already sets for a four-file manifest from before fundamentals existed
   (`research.py:643-646`). A dev build writes none of them, so the dev store's `manifest.json`
   is byte-identical and its fingerprint (which covers only the `files` map) cannot move.
   `dev_end` keeps the value `"2015-10-16"` on **both** kinds of store: it is a code-version
   pin, not the store's window, and the existing check on it is unchanged.
   `window_start` is `"2015-10-19"` and `window_end` is the session the store was built
   through; neither says where the *data* starts — that is `store_start`, `"1993-01-29"` on
   both stores, per the coordinator's decision above.
3. **The exact `load_store` refusal.** A `ValueError` whose message contains the stable
   substrings `"declares the dev window"` / `"declares the test window"` and
   `"are not interchangeable"`:
   ```
   <store>/manifest.json: this store declares the test window ending 2026-10-02, but the caller
   asked for the dev window ending 2015-10-16. A dev store and a test store are not
   interchangeable: the test store holds the same history AND every session after 2015-10-16,
   so loading one where the other is expected would run the dev pipeline on unseen data (D9).
   Point --store at the matching store directory (.research for the dev window, .research-test
   for the test window).
   ```
   The label is `"<name> window ending <end>"` rather than `start..end`, because
   `DEV_WINDOW.start` is `date.min` and printing it would be noise.
   Raised from `_read_manifest`, i.e. **before any data file is read**. Because
   `lab/runner.py` and `commands/lab.py:237` call `research.load_store(Path(args.store))` with
   no `window=`, a mis-pointed `SEER_RESEARCH_STORE` fails here, loudly, with zero changes to
   `lab.py`. Phase 4 must not weaken that: `lab run` keeps the default.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/research.py` | modify | window param on `build_store`/`load_store`/`refresh_fundamentals`; `TEST_STORE_DIR`, `TEST_WINDOW_START`, `test_window`, `latest_session`, `declared_window`; manifest window identity; D9 guards keyed on the window end; `ResearchData.window`; the two window-bearing checks |
| `engine/src/seer_engine/commands/research_store.py` | modify | `--test-window` and `--window-end`; store-directory resolution and the two clobber guards; window-aware verify/refresh; the window line in `format_summary` |
| `.gitignore` | modify | `engine/.research-test/`, `engine/.research-test.tmp/`, `engine/.research-test.old/` |
| `engine/pyproject.toml` | modify | `[tool.ruff] extend-exclude` gains `".research-test"` |
| `engine/tests/test_research_test_store.py` | create | the whole phase's tests; no network, no database |

Line references below are against the tree as it stands at `2d03fd1`. Phase 1 edits
`research.py:63-200` and will shift later numbers; anchor on the function name, not the number.

---

## Implementation Steps

### Step 1: `research.py` — imports, window constants and the window constructors

**File:** `engine/src/seer_engine/research.py:33-60` (imports), `:63-110` (constants)
**Change:** import phase 1's window type, add the test-store constants and the manifest's
optional window keys, and add the three window constructors. `_window` is the only place a
`Window` is constructed, and it uses `dataclasses.replace` so a `Window` with fields beyond
`start`/`end` works unchanged.

Replace the `from dataclasses import dataclass` line and the `from datetime import …` line:

**Code (imports):**
```python
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from seer_engine import config, dates, fx, membership, yahoo
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.io import (
    BAR_COLUMNS,
    LoadError,
    facts_from_frame,
    histories_from_frame,
    merge_intervals,
)
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.backtest.window import WINDOW_NAMES, Window
from seer_engine.fundamentals import FACT_COLUMNS, Fact, FundamentalPanel as Panel
from seer_engine.prices import to_decimal
```

(`DEV_WINDOW` itself is defined in `research.py` by phase 1, beside `DEV_END`:
`DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)`. Only `Window` and
`WINDOW_NAMES` are imported.)

**Code (constants — insert after `STORE_DIR` at `:67`):**
```python
STORE_DIR = config.REPO_ROOT / "engine" / ".research"  # gitignored; the dev window
TEST_STORE_DIR = config.REPO_ROOT / "engine" / ".research-test"  # gitignored; the P7b test window
TEST_WINDOW_START = date(2015, 10, 19)  # the first NYSE session after DEV_END (design §3)
"""The first session the test window TRADES. Not where the test store's data starts.

Both stores hold bars from :data:`STORE_START` (1993-01-29): a candidate evaluated from
2015-10-19 still needs ``lookback`` bars before that date, and a test store opening at its own
window start would push a 12-1 momentum candidate's only look ~10 months late. A test-window
trial is append-only and there is exactly one look per configuration, so that error would be
permanent. The window's ``start`` bounds scoring; ``STORE_START`` bounds the files.
"""
```

**Code (manifest keys — replace `MANIFEST_KEYS` at `:107`):**
```python
MANIFEST_KEYS: frozenset[str] = frozenset({"dev_end", "store_start", "files", "fingerprint", *_COUNT_KEYS})
"""The keys every manifest carries, whatever window the store was built for.

``dev_end`` is a **code-version pin**, not the store's window: it records the ``DEV_END`` the
building code was compiled against, so a store built before ``DEV_END`` moved (it never has)
is refused. A test store carries the same ``"2015-10-16"``. The store's own window lives in
:data:`OPTIONAL_MANIFEST_KEYS`.
"""

WINDOW_NAME_KEY = "window_name"
WINDOW_START_KEY = "window_start"
WINDOW_END_KEY = "window_end"
OPTIONAL_MANIFEST_KEYS: frozenset[str] = frozenset(
    {WINDOW_NAME_KEY, WINDOW_START_KEY, WINDOW_END_KEY}
)
"""The window a non-dev store declares: a name and two ISO dates, all three or none.

They describe what the store is **scored** on, never what it holds: ``store_start`` is
``"1993-01-29"`` on a test store too.

**Absent means the dev window.** That is not a convenience, it is the only shape that keeps the
dev store on disk loadable: ``engine/.research`` was sealed with exactly ``MANIFEST_KEYS`` and
its fingerprint ``399d0d25…`` is the identity the ``sync-research-store`` skill keys on and
every recorded lab trial was measured against. Requiring a window key would reject it before
any reader ran -- exactly the precedent ``OPTIONAL_DATA_FILES`` already sets for a four-file
manifest from before fundamentals existed.

A dev build therefore writes none of them (see :func:`_seal`). The fingerprint is unaffected
either way: :func:`fingerprint_of` hashes the ``files`` map alone, never the manifest's other
keys.
"""
```

**Code (window constructors — insert immediately after the `Check` dataclass, before the
`# ---- symbols and membership ----` banner at `:149`):**
```python
# ---- windows -------------------------------------------------------------------------------


def _window(name: str, start: date, end: date) -> Window:
    """A research window.

    Built with ``dataclasses.replace`` from ``DEV_WINDOW`` rather than by calling ``Window``:
    this module then never names phase 1's constructor, so a ``Window`` that grows a field
    stays buildable here without an edit.
    """
    if name not in WINDOW_NAMES:
        raise ValueError(f"window name must be one of {WINDOW_NAMES}, got {name!r}")
    return replace(DEV_WINDOW, name=name, start=start, end=end)


def _is_dev_window(window: Window) -> bool:
    return (window.name, window.start, window.end) == (
        DEV_WINDOW.name,
        DEV_WINDOW.start,
        DEV_WINDOW.end,
    )


def _window_label(window: Window) -> str:
    """``"dev window ending 2015-10-16"`` / ``"test window ending 2026-10-02"``.

    The end, not ``start..end``: ``DEV_WINDOW.start`` is ``date.min`` and printing it is noise.
    The name alone separates the two windows; the end separates two test stores built on
    different days.
    """
    return f"{window.name} window ending {window.end.isoformat()}"


def test_window(end: date) -> Window:
    """The P7b test window: :data:`TEST_WINDOW_START` (2015-10-19) through ``end``.

    ``end`` is the last session **scored**, and design §3 fixes it as "data end" -- the latest
    session available when the store is built (see :func:`latest_session`), recorded in the
    manifest. It is deliberately **not** a constant: a hardcoded end goes stale and would
    silently change what a recorded test trial meant. The store still holds bars from
    ``STORE_START``; see :data:`TEST_WINDOW_START`.

    Equivalent to ``DEV_WINDOW.following("test", end)`` and asserted equal to it in
    ``test_research_test_store.py``, so the two phases cannot drift. Spelled out here because
    this module owns the validation and the ``TEST_WINDOW_START`` constant.

    ``ValueError`` when ``end`` is not after ``DEV_END`` (that is the dev window's territory,
    and a "test" store ending inside it would be a dev store wearing the wrong label) or is not
    an NYSE session (the window's end must be a session a bar can exist for).
    """
    if isinstance(end, datetime) or not isinstance(end, date):
        raise TypeError(f"end must be a date, got {type(end).__name__}")
    if end <= DEV_END:
        raise ValueError(
            f"the test window must end after DEV_END {DEV_END.isoformat()}, got {end.isoformat()}"
        )
    if not dates.is_session(end):
        raise ValueError(f"the test window must end on an NYSE session, and {end.isoformat()} is not one")
    return _window("test", TEST_WINDOW_START, end)


def latest_session(now_utc: datetime | None = None) -> date:
    """The latest NYSE session whose close has settled -- "data end" at build time.

    Thin, injectable wrapper over ``dates.last_completed_session`` so a caller (and a test) can
    fix the clock. It is the default end of a ``--test-window`` build.
    """
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    return dates.last_completed_session(now)
```

**Impact:** `research.Window` and `research.DEV_WINDOW` become part of this module's surface
(the command and phase 4 import them from here, not from `backtest.window`). Nothing existing
changes behaviour. `_window` is the single adapter if phase 1's `Window` differs.

---

### Step 2: `research.py` — `ResearchData` carries its window

**File:** `engine/src/seer_engine/research.py:127-139`
**Change:** add a `window` field so every consumer of a loaded store can read the window it was
built for instead of recomputing or hardcoding it. It defaults to `DEV_WINDOW`, so every
existing construction site and every test that builds one by hand keeps working.

**Code:**
```python
@dataclass(frozen=True)
class ResearchData:
    """A loaded, verified research store."""

    market: Market  # history from bars.csv, membership clipped to ``window``, fx from fx.csv
    dividends: dict[str, dict[date, Decimal]]  # symbol -> ex_date -> amount (ascending)
    spy_dividends: tuple[Dividend, ...]  # SPY's, as benchmark.Dividend, ascending
    fingerprint: str
    manifest: Mapping[str, Any]
    unserved: tuple[str, ...] = ()  # requested members with no bars, sorted
    window: Window = DEV_WINDOW  # the window this store declares; its ``end`` is the D9 bound
```

**Impact:** `dataclasses.replace(data, …)` in `test_research_store.py:490` still works (it
names only `dividends`). Phase 4 reads `data.window` rather than hardcoding `2015-10-19`.

---

### Step 3: `research.py` — `build_store` takes the window

**File:** `engine/src/seer_engine/research.py:290-366`
**Change:** a keyword-only `window` defaulting to `DEV_WINDOW`, threaded into the universe, the
FX range, the bar range, the unserved reason and the seal. Every existing caller compiles with
no argument change.

**Code:**
```python
def build_store(
    store_dir: Path,
    *,
    downloader: yahoo.Downloader | None = None,
    fetch_fx: FetchFx | None = None,
    sleep: Sleep = time.sleep,
    batch_size: int = DEFAULT_BATCH_SIZE,
    data_dir: Path | None = None,
    facts: Sequence[Fact] | None = None,
    window: Window = DEV_WINDOW,
) -> dict[str, Any]:
    """Build the research store at ``store_dir``; return its manifest.

    ``downloader`` defaults to ``yahoo.yf_download_actions`` and ``fetch_fx`` to
    ``fx.fetch_range`` (both injectable for tests); ``data_dir`` is the membership CSV
    directory (default ``membership.DATA_DIR``). Raises ResearchStoreError when the build
    cannot finish (rate limited out, a download error, an unserved ETF, no or conflicting FX);
    then nothing is written and a previous store at ``store_dir`` is left untouched.

    ``window`` is the window the store is built for and declares; it defaults to ``DEV_WINDOW``,
    so every caller that predates it builds exactly the store it built before -- same symbols,
    same date range, same ``unserved.csv`` text, same nine manifest keys, same fingerprint.
    Pass ``test_window(latest_session())`` to build the P7b test store.

    **The data range follows ``window.end`` alone.** It is always ``STORE_START..window.end``
    for bars and ``FX_START..window.end`` for FX, on either window. A test store therefore
    carries the *same* deep history as the dev store plus everything after it -- a candidate
    evaluated from 2015-10-19 still needs ``lookback`` bars before that date, and the test
    window grants exactly one look per configuration, so a store that started at its own window
    start would make that one look permanently wrong.

    **The universe follows the window at both ends.** ``requested_symbols(data_dir,
    window=window)`` is every member whose interval overlaps
    ``[max(window.start, MEMBERSHIP_START), window.end]`` -- ``[MEMBERSHIP_START, DEV_END]`` on
    the dev window, unchanged, and ``[2015-10-19, window.end]`` on the test window. Every
    company that joined the index after October 2015 is in; every company that left it before
    2015-10-19 is out, because no test-window session ever ranks, holds or exits one, so its
    bars would be rows nothing reads. ``members_on(t)`` for every ``t`` in the test window is
    the same set either way; only the size of the crawl differs. A membership interval that
    closes in 2018 also stays closed instead of being read as open.

    ``facts`` is the SEC point-in-time panel, as a plain sequence of ``fundamentals.Fact`` --
    never a database connection, because this module imports nothing from ``seer_engine.db``
    (see the module docstring's "Never Neon"). ``commands/research_store.py`` reads them behind
    ``--with-fundamentals`` and passes them in. ``None`` -- the default, and every caller that
    predates fundamentals -- writes no ``fundamentals.csv`` at all, so the store is
    byte-identical to the one this function built before the field existed. Facts are **not**
    filtered by ``window``: ``FundamentalPanel`` selects point-in-time on ``filed <= t`` at read
    time, so a later filing in the file is invisible on an earlier session, and filtering here
    would rewrite ``fundamentals.csv`` and move the dev store's fingerprint for no gain.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError(f"batch_size must be an int >= 1, got {batch_size!r}")
    if window.end < STORE_START:
        raise ValueError(
            f"the window ends {window.end.isoformat()}, before STORE_START {STORE_START.isoformat()}; "
            "there is nothing to build"
        )
    store_dir = Path(store_dir)
    fetch = downloader if downloader is not None else yahoo.yf_download_actions
    fetch_rates = fetch_fx if fetch_fx is not None else fx.fetch_range
    symbols = requested_symbols(data_dir, window=window)

    store_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = store_dir.with_name(store_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        fx_rows = _fetch_fx_rows(fetch_rates, window.end)
        _write_text(tmp / FX_FILE, FX_HEADER, [f"{d.isoformat()},{v}" for d, v in fx_rows])
        served, unserved, bar_rows, dividend_lines = _write_bars(
            tmp, symbols, fetch, sleep, batch_size, window.end
        )
        lost_etfs = [s for s in RESEARCH_ETFS if s in set(unserved)]
        if lost_etfs:
            raise ResearchStoreError(
                f"yfinance served no bars for ETF(s) {', '.join(lost_etfs)}; every family needs them"
            )
        _write_text(tmp / DIVIDENDS_FILE, DIVIDENDS_HEADER, dividend_lines)
        # STORE_START, not window.start: this names the range the DOWNLOAD covered, and both
        # windows download from 1993. unserved_reason(STORE_START, DEV_END) is byte-identical
        # to the old UNSERVED_REASON constant, so the dev store's unserved.csv -- and therefore
        # its fingerprint -- does not move.
        reason = unserved_reason(STORE_START, window.end)
        _write_text(tmp / UNSERVED_FILE, UNSERVED_HEADER, [f"{s},{reason}" for s in unserved])
        extra_files: tuple[str, ...] = ()
        if facts is not None:
            _write_text(tmp / FUNDAMENTALS_FILE, FUNDAMENTALS_HEADER, fundamentals_lines(facts))
            extra_files = (FUNDAMENTALS_FILE,)
        counts = {
            "bar_rows": bar_rows,
            "dividend_rows": len(dividend_lines),
            "fx_rows": len(fx_rows),
            "symbols_requested": len(symbols),
            "symbols_served": len(served),
        }
        manifest = _seal(tmp, counts, extra_files=extra_files, window=window)
        _swap_in(tmp, store_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    log.info(
        "research: store %s built for the %s: %d of %d symbols served, %d bar rows, %d dividends, "
        "%d fx rows, fingerprint %s",
        store_dir,
        _window_label(window),
        counts["symbols_served"],
        counts["symbols_requested"],
        counts["bar_rows"],
        counts["dividend_rows"],
        counts["fx_rows"],
        manifest["fingerprint"],
    )
    return manifest
```

**Impact:** a dev build is byte-for-byte what it was. A test build requests 1285 symbols
instead of 1061 (measured against the vendored CSVs: 1265 members + 20 non-member ETFs).

---

### Step 4: `research.py` — the download half takes an end date

**File:** `engine/src/seer_engine/research.py:368-485`
**Change:** `_fetch_fx_rows`, `_write_bars`, `_fetch_batch`, `_download_with_backoff` and
`_in_window` each take the window's end instead of closing over `DEV_END`. All are private.

**Code:**
```python
def _fetch_fx_rows(fetch_rates: FetchFx, end: date) -> list[tuple[date, Decimal]]:
    try:
        raw = list(fetch_rates(FX_START, end))
    except Exception as exc:  # noqa: BLE001 - any FX failure aborts the build
        raise ResearchStoreError(f"USD/IDR fetch failed: {exc!r}") from exc
    items: dict[date, Decimal] = {}
    for d, rate in raw:
        if not FX_START <= d <= end:
            continue
        value = to_decimal(rate)
        if value <= 0:
            raise ResearchStoreError(f"USD/IDR on {d.isoformat()} is not positive: {value}")
        if d in items and items[d] != value:
            raise ResearchStoreError(f"conflicting USD/IDR rates for {d.isoformat()}")
        items[d] = value
    if not items:
        raise ResearchStoreError(f"Frankfurter returned no USD/IDR rows for {FX_START}..{end}")
    log.info("research: %d USD/IDR rows %s..%s", len(items), min(items), max(items))
    return sorted(items.items())


def _write_bars(
    tmp: Path,
    symbols: Sequence[str],
    fetch: yahoo.Downloader,
    sleep: Sleep,
    batch_size: int,
    end: date,
) -> tuple[list[str], list[str], int, list[str]]:
    """Stream bars.csv batch by batch; return (served, unserved, bar rows, dividend lines)."""
    served: list[str] = []
    unserved: list[str] = []
    dividend_lines: list[str] = []
    bar_rows = 0
    batches = [list(symbols[i : i + batch_size]) for i in range(0, len(symbols), batch_size)]
    log.info(
        "research: %d symbols in %d batches, %s..%s",
        len(symbols),
        len(batches),
        STORE_START,
        end,
    )
    with (tmp / BARS_FILE).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(BARS_HEADER + "\n")
        for number, batch in enumerate(batches, start=1):
            if number > 1:
                sleep(BATCH_PAUSE_S)
            got = _fetch_batch(batch, fetch, sleep, end)
            batch_rows = 0
            for symbol in batch:
                history = got[symbol]
                if not history.bars:
                    unserved.append(symbol)
                    continue
                served.append(symbol)
                for b in history.bars:
                    fh.write(
                        f"{b.symbol},{b.date.isoformat()},{b.open},{b.high},{b.low},{b.close},{b.volume}\n"
                    )
                batch_rows += len(history.bars)
                dividend_lines.extend(
                    f"{symbol},{d.isoformat()},{_amount_text(a)}" for d, a in history.dividends
                )
            bar_rows += batch_rows
            log.info(
                "research: batch %d/%d: %d served, %d unserved, %d bar rows",
                number,
                len(batches),
                sum(1 for s in batch if got[s].bars),
                sum(1 for s in batch if not got[s].bars),
                batch_rows,
            )
    return served, unserved, bar_rows, dividend_lines


def _fetch_batch(
    batch: Sequence[str], fetch: yahoo.Downloader, sleep: Sleep, end: date
) -> dict[str, yahoo.TickerHistory]:
    """One batch, clipped to [STORE_START, end]; empties get one individual retry."""
    got = _download_with_backoff(batch, fetch, sleep, end)
    out = {s: _in_window(got.get(s, yahoo.EMPTY_HISTORY), end) for s in batch}
    if len(batch) > 1:  # a one-symbol batch already was the individual attempt
        for symbol in batch:
            if out[symbol].bars:
                continue
            sleep(BATCH_PAUSE_S)
            again = _download_with_backoff([symbol], fetch, sleep, end)
            out[symbol] = _in_window(again.get(symbol, yahoo.EMPTY_HISTORY), end)
    return out


def _download_with_backoff(
    symbols: Sequence[str], fetch: yahoo.Downloader, sleep: Sleep, end: date
) -> dict[str, yahoo.TickerHistory]:
    end_exclusive = end + timedelta(days=1)
    waits: tuple[float | None, ...] = (*RATE_LIMIT_BACKOFF_S, None)
    for wait in waits:
        try:
            return yahoo.download_actions(symbols, STORE_START, end_exclusive, downloader=fetch)
        except yahoo.RateLimited as exc:
            if wait is None:
                raise ResearchStoreError(
                    f"yfinance rate limited after {len(RATE_LIMIT_BACKOFF_S)} retries: {exc}"
                ) from exc
            log.warning("research: rate limited; sleeping %.0f s", wait)
            sleep(wait)
        except Exception as exc:  # noqa: BLE001 - a download error aborts the build (no partial store)
            raise ResearchStoreError(
                f"yfinance download of {len(symbols)} symbol(s) failed: {exc!r}"
            ) from exc
    raise AssertionError("unreachable")  # pragma: no cover


def _in_window(history: yahoo.TickerHistory, end: date) -> yahoo.TickerHistory:
    """Drop anything outside [STORE_START, end] (defensive: the request already ends at
    ``end`` + 1 day, but no row outside the store's declared window may ever reach it)."""
    return yahoo.TickerHistory(
        bars=tuple(b for b in history.bars if STORE_START <= b.date <= end),
        dividends=tuple((d, a) for d, a in history.dividends if STORE_START <= d <= end),
    )
```

**Impact:** `test_research_store.py`'s `FakeYahoo` records `(tickers, start, end_exclusive)` and
the existing assertion `(start, end) == (STORE_START, DEV_END + timedelta(days=1))` still holds
for a dev build.

---

### Step 5: `research.py` — `_seal` writes the window identity, and only for a non-dev store

**File:** `engine/src/seer_engine/research.py:500-519`
**Change:** `_seal` gains `window` and appends the three window keys **only** when the window
is not the dev window. (`_is_dev_window` and `_window_label` were defined in Step 1.)

**Code:**
```python
def _seal(
    tmp: Path,
    counts: Mapping[str, int],
    *,
    extra_files: Sequence[str] = (),
    window: Window = DEV_WINDOW,
) -> dict[str, Any]:
    """The manifest for the store under ``tmp``, written and returned.

    ``extra_files`` are the ``OPTIONAL_DATA_FILES`` this build actually wrote; they join
    ``files`` (and therefore the fingerprint) and nothing else. ``_COUNT_KEYS`` deliberately
    gains nothing: ``MANIFEST_KEYS`` is asserted as a whole set by
    ``engine/tests/test_research_store.py``, which no phase of this plan set owns.

    ``window`` is written as the three ``OPTIONAL_MANIFEST_KEYS`` **only when it is not the dev
    window**. A dev build therefore seals exactly the nine ``MANIFEST_KEYS`` it always has, so
    ``engine/.research``'s manifest stays byte-identical and the test above stays green. The
    fingerprint is unaffected either way -- ``fingerprint_of`` hashes the ``files`` map alone --
    but the manifest's bytes are not, and they are what that test reads.

    ``store_start`` is ``STORE_START`` for both windows: it is where the DATA starts, and the
    test store holds the same deep history the dev store does. Only ``window_start`` says where
    scoring begins.
    """
    files = {name: file_sha256(tmp / name) for name in (*DATA_FILES, *extra_files)}
    manifest: dict[str, Any] = {
        "dev_end": DEV_END.isoformat(),
        "store_start": STORE_START.isoformat(),
        **{key: int(counts[key]) for key in _COUNT_KEYS},
        "files": files,
        "fingerprint": fingerprint_of(files),
    }
    if not _is_dev_window(window):
        manifest[WINDOW_NAME_KEY] = window.name
        manifest[WINDOW_START_KEY] = window.start.isoformat()
        manifest[WINDOW_END_KEY] = window.end.isoformat()
    with (tmp / MANIFEST_FILE).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest
```

**Impact:** `json.dumps(sort_keys=True)` puts `window_end`/`window_name`/`window_start` last; a
dev manifest is unchanged down to the byte.

---

### Step 6: `research.py` — `refresh_fundamentals` preserves the store's window

**File:** `engine/src/seer_engine/research.py:534-630`
**Change:** a `window` parameter, passed to both `load_store` (so a mismatched store is refused
before anything is written) and `_seal` (so the refreshed store declares the same window it
declared before).

**Code:**
```python
def refresh_fundamentals(
    store_dir: Path,
    facts: Sequence[Fact],
    *,
    data_dir: Path | None = None,
    window: Window = DEV_WINDOW,
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

    ``window`` must be the window the store declares; pass ``declared_window(store_dir)``.
    ``load_store`` below refuses a mismatch, so a dev refresh can never be aimed at the test
    store or the reverse, and ``_seal`` re-declares the same window the store had -- refreshing
    a store never changes which window it is for.

    ``facts`` is a plain sequence of ``fundamentals.Fact``, exactly as ``build_store`` takes it
    -- never a database connection, because this module imports nothing from ``seer_engine.db``
    (see the module docstring's "Never Neon"). ``commands/research_store.py`` reads them behind
    ``--refresh-fundamentals`` and passes them in. An empty sequence is legal and writes a
    header-only ``fundamentals.csv`` (an explicitly empty panel); ``None`` is not, because
    "refresh with nothing" is ambiguous -- keep the panel, or clear it? -- and the caller must
    say which.

    The source store is verified with ``load_store`` first: every sha256, the fingerprint, the
    five ``_COUNT_KEYS`` counts and the window's date guards. A store that fails any of them is
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
        data = load_store(store_dir, data_dir=data_dir, window=window)
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
        manifest = _seal(tmp, counts, extra_files=(FUNDAMENTALS_FILE,), window=window)
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

**Impact:** every existing `refresh_fundamentals` call (the command, the four refresh tests)
keeps the dev default and behaves identically.

---

### Step 7: `research.py` — `load_store` takes the window and verifies the declaration

**File:** `engine/src/seer_engine/research.py:633-710`
**Change:** a `window` parameter, passed to `_read_manifest` (which refuses a mismatch), to the
three D9 date guards and to `research_membership`; the result carries it.

**Code:**
```python
def load_store(
    store_dir: Path, *, data_dir: Path | None = None, window: Window = DEV_WINDOW
) -> ResearchData:
    """Load and verify the store at ``store_dir`` (no network, no database).

    ``window`` is the window the **caller** expects. It defaults to ``DEV_WINDOW``, so every
    dev path -- ``lab run``, ``backtest_dev``, this module's own refresh -- gets the dev
    guarantee without passing anything, and a mis-pointed ``SEER_RESEARCH_STORE`` aimed at the
    test store fails loudly here instead of silently running the dev pipeline on test data.
    A test-window caller must ask for it explicitly; ``declared_window(store_dir)`` reads what
    a store is for, and passing that back in is the normal opening.

    ValueError when: the manifest is missing or malformed, or was built for another DEV_END or
    STORE_START; **the store declares a different window than the caller asked for**; a file's
    sha256 or the fingerprint does not match the manifest; any bar, dividend or FX row is dated
    after ``window.end`` (D9, data level); the counts disagree.
    """
    store_dir = Path(store_dir)
    manifest = _read_manifest(store_dir, window)
    files: dict[str, str] = manifest["files"]
    # The manifest's OWN keys, not DATA_FILES: a store built before fundamentals existed lists
    # four files and must hash exactly those four, so its fingerprint is bit-identical to the
    # one origin/main computes for the same directory.
    for name in sorted(files):
        actual = file_sha256(store_dir / name)
        if actual != files[name]:
            raise ValueError(
                f"{name}: sha256 {actual} does not match the manifest ({files[name]}); the store "
                "was modified after it was built; rebuild it with `python -m seer_engine research_store`"
            )
    fingerprint = fingerprint_of(files)
    if fingerprint != manifest["fingerprint"]:
        raise ValueError(
            f"fingerprint {fingerprint} does not match the manifest ({manifest['fingerprint']})"
        )
    frame = _read_bars(store_dir / BARS_FILE, window.end)
    dividends = _read_dividends(store_dir / DIVIDENDS_FILE, window.end)
    fx_rows = _read_fx(store_dir / FX_FILE, window.end)
    unserved = _read_unserved(store_dir / UNSERVED_FILE)
    fundamentals = (
        _read_fundamentals(store_dir / FUNDAMENTALS_FILE)
        if FUNDAMENTALS_FILE in files
        else EMPTY_FUNDAMENTALS
    )
    served = int(frame["symbol"].nunique()) if len(frame) else 0
    actual_counts = {
        "bar_rows": int(len(frame)),
        "dividend_rows": sum(len(v) for v in dividends.values()),
        "fx_rows": len(fx_rows),
        "symbols_requested": served + len(unserved),
        "symbols_served": served,
    }
    for key in _COUNT_KEYS:
        if manifest[key] != actual_counts[key]:
            raise ValueError(f"{key}: the manifest says {manifest[key]}, the files hold {actual_counts[key]}")
    try:
        history = histories_from_frame(frame)
    except LoadError as exc:
        raise ValueError(f"{BARS_FILE}: {exc}") from exc
    market = Market(
        history=history,
        membership=research_membership(data_dir, window=window),
        fx=fx_rows,
        fundamentals=fundamentals,
    )
    spy_dividends = tuple(
        Dividend(ex_date=d, amount=a) for d, a in sorted(dividends.get("SPY", {}).items())
    )
    log.info(
        "research: loaded %s for the %s: %d symbols with bars, %d bar rows, %d dividends, "
        "%d fx rows, %d unserved, fingerprint %s",
        store_dir,
        _window_label(window),
        len(history),
        actual_counts["bar_rows"],
        actual_counts["dividend_rows"],
        actual_counts["fx_rows"],
        len(unserved),
        fingerprint,
    )
    return ResearchData(
        market=market,
        dividends=dividends,
        spy_dividends=spy_dividends,
        fingerprint=fingerprint,
        manifest=manifest,
        unserved=unserved,
        window=window,
    )
```

**Impact:** `Market.membership` for a test store is clamped against the test window's end, so a
company that left the index in 2018 stops being a member in 2018 instead of reading as one
through 2026. That is the bug the analysis called out at `research.py:166`.

---

### Step 8: `research.py` — the manifest readers and the refusal

**File:** `engine/src/seer_engine/research.py:712-765`
**Change:** split the JSON read out of `_read_manifest` so `declared_window` can reuse it; add
`_declared_window` and the public `declared_window`; widen the key-set check to the
both-or-neither optional pair; add the window refusal; replace `_after_dev_end`.

**Code:**
```python
def _manifest_json(store_dir: Path) -> tuple[Path, dict[str, Any]]:
    """``manifest.json``'s parsed object and its path; ValueError when missing or not an object."""
    path = store_dir / MANIFEST_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(
            f"{store_dir}: no research store ({MANIFEST_FILE} missing); build it with "
            "`python -m seer_engine research_store`"
        ) from exc
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"{path}: expected a JSON object, got {type(manifest).__name__}")
    return path, manifest


def _declared_window(path: Path, manifest: Mapping[str, Any]) -> Window:
    """The window ``manifest`` declares. **No window keys means the dev window.**

    That default is the compatibility hinge: ``engine/.research`` was sealed with nine keys and
    must keep loading untouched, exactly as a four-file manifest from before fundamentals
    existed keeps loading (see :data:`OPTIONAL_DATA_FILES`).
    """
    if WINDOW_END_KEY not in manifest:
        return DEV_WINDOW
    name = manifest.get(WINDOW_NAME_KEY)
    raw_start = manifest.get(WINDOW_START_KEY)
    raw_end = manifest[WINDOW_END_KEY]
    if name not in WINDOW_NAMES or name == DEV_WINDOW.name:
        raise ValueError(
            f"{path}: {WINDOW_NAME_KEY!r} must be one of {tuple(n for n in WINDOW_NAMES if n != DEV_WINDOW.name)}, "
            f"got {name!r}; the dev window is declared by leaving these keys out, never by name"
        )
    try:
        start = date.fromisoformat(raw_start)
        end = date.fromisoformat(raw_end)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{path}: {WINDOW_START_KEY!r} and {WINDOW_END_KEY!r} must be ISO dates, got "
            f"{raw_start!r} and {raw_end!r}"
        ) from exc
    if start <= DEV_END or end < start:
        raise ValueError(
            f"{path}: declares the window {start.isoformat()}..{end.isoformat()}; a store that "
            f"declares a window must start after DEV_END {DEV_END.isoformat()} (a window ending "
            "inside the dev window is the dev window, and is declared by leaving the keys out) "
            "and must not end before it starts"
        )
    return _window(name, start, end)


def declared_window(store_dir: Path) -> Window:
    """The window the store at ``store_dir`` is for, from its manifest alone.

    Reads no data file and verifies nothing: it answers "which window is this store for?" so a
    caller can pass the matching ``window`` to :func:`load_store`, which does the verifying.
    A store with no window keys declares ``DEV_WINDOW``.

    This is not a way around the refusal in :func:`load_store`. It reports what the store says
    about itself; a caller that wants the dev window still passes ``DEV_WINDOW`` and is still
    refused a test store. ``lab run`` and ``backtest_dev`` never call this.

    ValueError when the store or its manifest is missing, unparseable, or declares a window
    that is not a window.
    """
    path, manifest = _manifest_json(Path(store_dir))
    return _declared_window(path, manifest)


def _read_manifest(store_dir: Path, window: Window = DEV_WINDOW) -> dict[str, Any]:
    path, manifest = _manifest_json(store_dir)
    keys = set(manifest)
    if keys != MANIFEST_KEYS and keys != MANIFEST_KEYS | OPTIONAL_MANIFEST_KEYS:
        raise ValueError(
            f"{path}: expected keys {sorted(MANIFEST_KEYS)}, optionally also "
            f"{sorted(OPTIONAL_MANIFEST_KEYS)} (all three or none), got {sorted(keys)}"
        )
    if manifest["dev_end"] != DEV_END.isoformat():
        raise ValueError(
            f"{path}: the store was built for dev_end {manifest['dev_end']!r}; this code expects "
            f"{DEV_END.isoformat()}; rebuild it"
        )
    if manifest["store_start"] != STORE_START.isoformat():
        raise ValueError(
            f"{path}: the store was built for store_start {manifest['store_start']!r}; this code "
            f"expects {STORE_START.isoformat()}; rebuild it"
        )
    declared = _declared_window(path, manifest)
    if (declared.name, declared.start, declared.end) != (window.name, window.start, window.end):
        raise ValueError(
            f"{path}: this store declares the {_window_label(declared)}, but the caller asked "
            f"for the {_window_label(window)}. A dev store and a test store are not "
            "interchangeable: the test store holds the same history AND every session after "
            f"{DEV_END.isoformat()}, so loading one where the other is expected would run the "
            "dev pipeline on unseen data (D9). Point --store at the matching store directory "
            f"({STORE_DIR.name} for the dev window, {TEST_STORE_DIR.name} for the test window)."
        )
    files = manifest["files"]
    # The four DATA_FILES are required; the OPTIONAL_DATA_FILES may be there and nothing else
    # may. This is what keeps a store built before fundamentals existed loadable -- widening
    # DATA_FILES instead would reject every such store with a ValueError before any reader ran.
    if (
        not isinstance(files, dict)
        or not set(DATA_FILES) <= set(files) <= set(DATA_FILES) | set(OPTIONAL_DATA_FILES)
        or not all(isinstance(v, str) for v in files.values())
    ):
        raise ValueError(
            f"{path}: 'files' must map {list(DATA_FILES)} (optionally also "
            f"{list(OPTIONAL_DATA_FILES)}) to sha256 hex strings"
        )
    if not isinstance(manifest["fingerprint"], str):
        raise ValueError(f"{path}: 'fingerprint' must be a string")
    for key in _COUNT_KEYS:
        value = manifest[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{path}: {key!r} must be a non-negative int, got {value!r}")
    return manifest


def _after_window_end(name: str, what: str, d: date, end: date) -> ValueError:
    """The D9 data-level refusal. The dev message is reproduced verbatim.

    ``test_research_store.py:412`` matches ``"after DEV_END 2015-10-16"``; that test is shipped
    code this phase must leave green and must not edit, so the dev branch keeps the exact
    string it has today.
    """
    if end == DEV_END:
        return ValueError(
            f"{name}: {what} dated {d.isoformat()} is after DEV_END {DEV_END.isoformat()}; the "
            "research store must never hold a test-window row (D9)"
        )
    return ValueError(
        f"{name}: {what} dated {d.isoformat()} is after the store's window end "
        f"{end.isoformat()}; a store must never hold a row after the window it declares (D9)"
    )
```

**Impact:** the three existing manifest tests (`dev_end`, bad fingerprint, tampered file) pass
unchanged. `test_load_store_rejects_a_store_built_for_another_dev_end` is unaffected because
`dev_end` keeps its meaning on both kinds of store.

---

### Step 9: `research.py` — the three data-level D9 guards take the end

**File:** `engine/src/seer_engine/research.py:767-801` (`_read_bars`), `:833-850`
(`_read_dividends`), `:852-864` (`_read_fx`)
**Change:** each takes the end date and calls `_after_window_end`. The lower bound stays
`STORE_START`.

**Code:**
```python
def _read_bars(path: Path, end: date = DEV_END) -> pd.DataFrame:
    with path.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n")
    if header != BARS_HEADER:
        raise ValueError(f"{path.name}: expected header {BARS_HEADER!r}, got {header!r}")
    frame = pd.read_csv(
        path,
        sep=",",
        header=0,
        dtype={
            "symbol": str,
            "date": str,
            "open": np.float64,
            "high": np.float64,
            "low": np.float64,
            "close": np.float64,
            "volume": np.int64,
        },
        na_filter=False,
        float_precision="round_trip",
        engine="c",
    )
    if tuple(frame.columns) != BAR_COLUMNS:
        raise ValueError(f"{path.name}: columns {list(frame.columns)}, expected {list(BAR_COLUMNS)}")
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    if len(frame):
        latest = frame["date"].max().date()
        if latest > end:
            symbol = str(frame.loc[frame["date"].idxmax(), "symbol"])
            raise _after_window_end(path.name, f"a {symbol} bar", latest, end)
        earliest = frame["date"].min().date()
        if earliest < STORE_START:
            raise ValueError(f"{path.name}: a bar dated {earliest} is before STORE_START {STORE_START}")
    return frame


def _read_dividends(path: Path, end: date = DEV_END) -> dict[str, dict[date, Decimal]]:
    out: dict[str, dict[date, Decimal]] = {}
    for number, line in _data_lines(path, DIVIDENDS_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError(f"{where}: expected 3 fields, got {len(fields)}")
        symbol, raw_date, raw_amount = fields
        ex_date = _parse_date(raw_date, where)
        if ex_date > end:
            raise _after_window_end(where, f"a {symbol} dividend", ex_date, end)
        amount = _parse_positive(raw_amount, where)
        per_symbol = out.setdefault(symbol, {})
        if ex_date in per_symbol:
            raise ValueError(f"{where}: duplicate {symbol} dividend on {ex_date}")
        per_symbol[ex_date] = amount
    return {symbol: dict(sorted(rows.items())) for symbol, rows in sorted(out.items())}


def _read_fx(path: Path, end: date = DEV_END) -> tuple[tuple[date, Decimal], ...]:
    rows: list[tuple[date, Decimal]] = []
    for number, line in _data_lines(path, FX_HEADER):
        where = f"{path.name}:{number}"
        fields = line.split(",")
        if len(fields) != 2:
            raise ValueError(f"{where}: expected 2 fields, got {len(fields)}")
        d = _parse_date(fields[0], where)
        if d > end:
            raise _after_window_end(where, "a USD/IDR rate", d, end)
        rows.append((d, to_decimal(_parse_positive(fields[1], where))))
    return tuple(rows)
```

**Impact:** the `end: date = DEV_END` defaults keep these three callable with one argument,
which keeps any direct test call compiling. `load_store` always passes `window.end`.

---

### Step 10: `research.py` — the two window-bearing checks

**File:** `engine/src/seer_engine/research.py:879-909`
**Change:** `check_spy_sessions` defaults its end to the loaded store's window end;
`check_spy_dividends` clamps the comparison's upper bound to the last vendored ex-date as well
as the window end. `check_dividend_scale` and `run_checks` are unchanged.

**Code:**
```python
def check_spy_sessions(
    data: ResearchData, start: date = SPY_CHECK_START, end: date | None = None
) -> Check:
    """SPY has a bar on every NYSE session in [start, end].

    ``end`` defaults to the store's own window end, so a dev store is still checked to
    2015-10-16 and a test store is checked to the session it was built through.
    """
    if end is None:
        end = data.window.end
    sess = dates.sessions(start, end)
    h = data.market.history.get("SPY")
    if h is None:
        return Check("spy-sessions", False, "no SPY bars in the store")
    have = set(h.dates.tolist())
    missing = [d for d in sess if d not in have]
    detail = f"{len(sess)} NYSE sessions {start.isoformat()}..{end.isoformat()}, {len(missing)} without a SPY bar"
    if missing:
        detail += " (first: " + ", ".join(d.isoformat() for d in missing[:5]) + ")"
    return Check("spy-sessions", not missing, detail)


def check_spy_dividends(data: ResearchData, vendored: Sequence[Dividend]) -> Check:
    """The store's SPY dividends equal the vendored file on the overlap of the two.

    The overlap is [first vendored ex_date, min(window end, last vendored ex_date)] --
    2015-03-20..2015-10-16 for the dev store, where the vendored file (which runs to
    2026-09-18) is the longer of the two. For a test store built past the vendored file's last
    row the clamp is what stops a store dividend the file simply does not have yet from
    reading as a mismatch. It cannot weaken the dev check: there, the window end is the
    earlier bound and nothing changes.
    """
    if not vendored:
        return Check("spy-dividends", False, "the vendored SPY dividend file is empty")
    lo = vendored[0].ex_date
    hi = min(data.window.end, vendored[-1].ex_date)
    ours = [(d.ex_date, d.amount) for d in data.spy_dividends if lo <= d.ex_date <= hi]
    theirs = [(d.ex_date, d.amount) for d in vendored if lo <= d.ex_date <= hi]
    ok = bool(theirs) and ours == theirs
    detail = (
        f"{lo.isoformat()}..{hi.isoformat()}: store "
        + ", ".join(f"{d.isoformat()}={a}" for d, a in ours)
        + " | vendored "
        + ", ".join(f"{d.isoformat()}={a}" for d, a in theirs)
    )
    return Check("spy-dividends", ok, detail)
```

**Impact:** verified against the four existing assertions in
`test_research_store.py::test_check_spy_dividends` — all four verdicts are unchanged. Only the
`detail` string's upper bound moves (1999-01-05 instead of 2015-10-16 in that fixture), and no
test reads it. `test_check_spy_sessions`'s pinned detail
`"5721 NYSE sessions 1993-02-01..2015-10-16, 5718 without a SPY bar"` is reproduced exactly,
because the fixture store's `window` is `DEV_WINDOW`.

---

### Step 11: `commands/research_store.py` — the docstring and `HELP`

**File:** `engine/src/seer_engine/commands/research_store.py:1-59`
**Change:** document the two new flags and the refusals.

**Code (replace lines 1-38, the module docstring, and `HELP` at `:56`):**
```python
"""research_store — build (or verify) the local research store (handover D5).

Downloads split-adjusted daily bars and cash dividends from yfinance for the L9 ETF set and
every S&P 500 / Nasdaq-100 member since 1996, and USD/IDR from Frankfurter, into a gitignored
store directory. Then it loads the store back, runs the three verifications (SPY on every NYSE
session; SPY dividends equal the vendored file on the overlap; AAPL 2012 dividend scale) and
prints counts, the window, the fingerprint and the unserved members per year.

Never touches Neon and needs no DATABASE_URL.

    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]
                                        [--coverage] [--with-fundamentals]
                                        [--refresh-fundamentals]
                                        [--test-window [--window-end YYYY-MM-DD]]

Two windows, two stores:

- the **dev window** (1993-01-29..2015-10-16) in ``engine/.research`` -- the default, what
  ``lab run`` and ``backtest_dev`` read, and the store whose fingerprint every recorded lab
  trial was measured against;
- the **test window** (2015-10-19..data end) in ``engine/.research-test``, behind
  ``--test-window`` -- built the first time something is promoted and never before (design §3),
  read only by ``lab test``.

``--test-window`` builds through the latest completed NYSE session and records that date in the
manifest (``window_start`` / ``window_end``); ``--window-end`` pins it instead, so an
interrupted build can be resumed to the same end rather than silently moving. The two stores
are **not** interchangeable: ``research.load_store`` refuses a store whose declared window is
not the one the caller asked for, this command refuses to build one window into the other's
directory, and ``--verify`` / ``--refresh-fundamentals`` refuse a store whose declared window
disagrees with ``--test-window``.

``--verify`` loads an existing store only (no network). ``--coverage`` also loads an existing
store only and measures what its fundamental panel can rank across the dev window
(``fundamentals.coverage``): a per-year table and one fraction, printed whatever the number is.
It needs no network and no database, and it wins when both it and ``--verify`` are given. It
exits 0 when the fraction is at or above ``coverage.MIN_DEV_COVERAGE`` and 1 when it is below --
the same convention ``--verify`` uses for a failed check. It is a dev-window measure and is
refused with ``--test-window``. ``--with-fundamentals`` additionally reads the SEC
point-in-time fact panel from the database (``DATABASE_URL_UNPOOLED``, the one place in this
command that needs it) and writes it as the store's optional fifth file, so ``lab run`` sees a
non-empty ``Market.fundamentals``; without the flag the store carries no fundamentals and the
lab ranks on bars alone, silently. The global ``--dry-run`` builds into a temporary directory
and discards it. Exit codes: 0 ok; 1 build failed, a check failed or coverage is below the
floor; 2 the store is missing or invalid, or the flags refuse.

``--refresh-fundamentals`` rewrites **only** ``fundamentals.csv`` in an existing store and
needs no network: ``bars.csv``, ``dividends.csv``, ``fx.csv`` and ``unserved.csv`` are carried
over byte for byte, so the price history every recorded lab trial was run against survives
untouched while the panel moves. It reads the facts the same way ``--with-fundamentals`` does
(``DATABASE_URL_UNPOOLED`` -- point ``SEER_ENV_FILE`` at the train env file, and give it an
ABSOLUTE path: a relative one is resolved against the cwd and falling through to the ambient
environment means Neon) and refuses with exit 2 if the store is missing or fails verification.
The store's fingerprint changes -- a new ``fundamentals.csv`` is new content -- but not one bar
does, and the window it declares does not move. Under ``--dry-run`` it refreshes a copy in a
temporary directory and discards it. Not combinable with ``--verify`` or ``--coverage``.
"""
```

```python
HELP = (
    "Build the local research store (yfinance bars + dividends, Frankfurter USD/IDR): the dev "
    "window by default, the test window with --test-window; never Neon."
)
```

**Impact:** documentation only.

---

### Step 12: `commands/research_store.py` — the flags

**File:** `engine/src/seer_engine/commands/research_store.py:41-114`
**Change:** import `dates`, add `_session_date`, change `--store`'s default to `None` and add
the two flags.

**Code (imports — replace lines 41-54):**
```python
from __future__ import annotations

import argparse
import logging
import shutil
import tempfile
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.backtest import io as bt_io
from seer_engine.fundamentals import Fact, coverage

log = logging.getLogger(__name__)
```

**Code (`_session_date`, after `_positive_int` at `:69`):**
```python
def _session_date(text: str) -> date:
    try:
        value = date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an ISO date (YYYY-MM-DD): {text!r}") from exc
    if not dates.is_session(value):
        raise argparse.ArgumentTypeError(f"{text} is not an NYSE session")
    return value
```

**Code (`add_arguments` — replace the whole function at `:72-114`):**
```python
def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--store",
        type=Path,
        default=None,
        help=(
            f"store directory (default {research.STORE_DIR} without --test-window, "
            f"{research.TEST_STORE_DIR} with it)"
        ),
    )
    p.add_argument(
        "--batch-size",
        type=_positive_int,
        default=research.DEFAULT_BATCH_SIZE,
        help=f"symbols per yfinance call (default {research.DEFAULT_BATCH_SIZE})",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="load and check an existing store only (no network)",
    )
    p.add_argument(
        "--coverage",
        action="store_true",
        help=(
            "load an existing store and measure what its fundamental panel can rank over the "
            "dev window (no network, no database); exit 1 when it is below the lab's floor"
        ),
    )
    p.add_argument(
        "--with-fundamentals",
        action="store_true",
        help=(
            "also write fundamentals.csv from fundamental_facts (needs DATABASE_URL_UNPOOLED); "
            "without it the store carries no panel and the lab ranks on bars alone"
        ),
    )
    p.add_argument(
        "--refresh-fundamentals",
        action="store_true",
        help=(
            "rewrite only fundamentals.csv in an existing store, keeping every bar byte for "
            "byte (needs DATABASE_URL_UNPOOLED); the fingerprint changes, the price history "
            "does not; not combinable with --verify"
        ),
    )
    p.add_argument(
        "--test-window",
        action="store_true",
        help=(
            f"act on the P7b test store ({research.TEST_STORE_DIR}): the window "
            f"{research.TEST_WINDOW_START.isoformat()}..data end, not the dev window. Build it "
            "only when something is being promoted (design §3)"
        ),
    )
    p.add_argument(
        "--window-end",
        type=_session_date,
        default=None,
        help=(
            "end the test window on this NYSE session instead of the latest completed one; "
            "only with --test-window, and only for a build (use it to resume an interrupted "
            "build to the same end)"
        ),
    )
```

**Impact:** `--store`'s default moves into `run()`. No test asserts the argparse default
(checked: the eight `--store` call sites in `tests/` all pass an explicit path).

---

### Step 13: `commands/research_store.py` — `run()` and the clobber guards

**File:** `engine/src/seer_engine/commands/research_store.py:117-145`
**Change:** resolve the store directory from `--test-window`, refuse the two cross-window
mistakes, refuse `--coverage --test-window` and the two `--window-end` misuses, build the
window, and pass it down.

**Code:**
```python
def _same_dir(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:  # pragma: no cover - an unresolvable path is simply not the same one
        return a == b


def run(args: argparse.Namespace) -> int:
    test = bool(getattr(args, "test_window", False))
    refresh = bool(getattr(args, "refresh_fundamentals", False))
    coverage_mode = bool(getattr(args, "coverage", False))
    read_only = coverage_mode or bool(args.verify)
    window_end = getattr(args, "window_end", None)

    if refresh and read_only:
        log.error(
            "research_store: --refresh-fundamentals cannot be combined with --verify or "
            "--coverage; those two only read a store, --refresh-fundamentals rewrites its "
            "fundamentals.csv"
        )
        return 2
    if coverage_mode and test:
        log.error(
            "research_store: --coverage measures the fundamental panel over the DEV window "
            "(fundamentals.coverage.WINDOW_END) and has no meaning for a test store; run it "
            "against %s",
            research.STORE_DIR,
        )
        return 2
    if window_end is not None and not test:
        log.error(
            "research_store: --window-end applies only to --test-window; the dev window ends "
            "at %s and never moves (D9)",
            research.DEV_END.isoformat(),
        )
        return 2
    if window_end is not None and (read_only or refresh):
        log.error(
            "research_store: --window-end sets the window a BUILD writes; --verify, --coverage "
            "and --refresh-fundamentals read the window the store already declares"
        )
        return 2

    store = Path(args.store) if args.store is not None else (
        research.TEST_STORE_DIR if test else research.STORE_DIR
    )
    # The dev store's fingerprint is the identity the sync-research-store skill keys on and
    # every recorded lab trial was measured against. Writing the test window into it would be
    # unrecoverable, so refuse it even when the operator names the directory explicitly.
    if test and _same_dir(store, research.STORE_DIR):
        log.error(
            "research_store: refusing to act on the dev store %s with --test-window; the test "
            "store is %s",
            research.STORE_DIR,
            research.TEST_STORE_DIR,
        )
        return 2
    if not test and _same_dir(store, research.TEST_STORE_DIR):
        log.error(
            "research_store: %s is the test store; pass --test-window to act on it",
            research.TEST_STORE_DIR,
        )
        return 2

    if coverage_mode:
        return _coverage(store)
    if args.verify:
        return _verify(store, note="", test=test)
    if refresh:
        return _run_refresh(store, bool(getattr(args, "dry_run", False)), test)

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

    facts = _read_facts() if getattr(args, "with_fundamentals", False) else None
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size), facts, window)
            if code != 0:
                return code
            return _verify(
                target, note=" (dry run: built in a temporary directory and discarded)", test=test
            )
    code = _build(store, int(args.batch_size), facts, window)
    if code != 0:
        return code
    return _verify(store, note="", test=test)
```

**Impact:** `test_command_builds_the_store` and `test_command_dry_run_keeps_nothing` pass
`--store <tmp>` with no `--test-window`, so `test` is `False`, `window` is `DEV_WINDOW`, and
the monkeypatched `functools.partial(research.build_store, …)` receives `window=DEV_WINDOW` as
one more keyword — no clash with the bound ones. `fake_fx`'s assertion
`(start, end) == (FX_START, DEV_END)` still holds.

---

### Step 14: `commands/research_store.py` — window-aware build, verify and refresh

**File:** `engine/src/seer_engine/commands/research_store.py:159-218`
**Change:** `_build` takes the window; a shared `_store_window` resolves and cross-checks a
store's declared window; `_verify` and `_run_refresh` use it. `_coverage` is **unchanged**: it
calls `research.load_store(store)` with the dev default, so pointing it at a test store is
refused by `load_store` with the "not interchangeable" message.

**Code:**
```python
def _build(store: Path, batch_size: int, facts: Sequence[Fact] | None, window) -> int:
    try:
        research.build_store(store, batch_size=batch_size, facts=facts, window=window)
    except research.ResearchStoreError as exc:
        log.error("research_store: build failed, nothing written: %s", exc)
        return 1
    return 0


def _store_window(store: Path, test: bool):
    """``(window, 0)`` when ``store``'s declared window matches ``test``; ``(None, 2)`` logged.

    The one place a read-only or refresh mode learns which window it is working with. It reads
    the manifest and nothing else; ``research.load_store`` still verifies the declaration
    against what it is handed, so this cannot become a way past that refusal.
    """
    try:
        window = research.declared_window(store)
    except ValueError as exc:
        log.error("research_store: %s", exc)
        return None, 2
    is_test = window != research.DEV_WINDOW
    if is_test != test:
        have = (
            f"the test window {window.start.isoformat()}..{window.end.isoformat()}"
            if is_test
            else "the dev window"
        )
        want = "a test store (--test-window)" if test else "a dev store"
        log.error(
            "research_store: %s declares %s, but this invocation is for %s; a dev store and a "
            "test store are not interchangeable",
            store,
            have,
            want,
        )
        return None, 2
    return window, 0


def _run_refresh(store: Path, dry_run: bool, test: bool) -> int:
    """``--refresh-fundamentals``: rewrite fundamentals.csv in place, keeping every bar.

    The facts are read **before** the store is opened, so a database failure refuses while the
    store is still untouched. A dry run copies the whole store into a temporary directory,
    refreshes the copy and discards it: the real store is never opened for writing, which is
    what ``--dry-run`` promises everywhere else in this CLI. The refreshed store keeps the
    window it declared.
    """
    if not store.is_dir():
        log.error(
            "research_store: %s is not a directory; --refresh-fundamentals needs an existing "
            "store to refresh",
            store,
        )
        return 2
    window, code = _store_window(store, test)
    if window is None:
        return code
    facts = _read_facts()
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            shutil.copytree(store, target)
            code = _refresh(target, facts, window)
            if code != 0:
                return code
            return _verify(
                target,
                note=" (dry run: refreshed a copy in a temporary directory and discarded it)",
                test=test,
            )
    code = _refresh(store, facts, window)
    if code != 0:
        return code
    return _verify(store, note="", test=test)


def _refresh(store: Path, facts: Sequence[Fact], window) -> int:
    try:
        research.refresh_fundamentals(store, facts, window=window)
    except research.ResearchStoreError as exc:
        log.error("research_store: refresh refused, nothing written: %s", exc)
        return 2
    return 0


def _verify(store: Path, *, note: str, test: bool = False) -> int:
    window, code = _store_window(store, test)
    if window is None:
        return code
    try:
        data = research.load_store(store, window=window)
    except ValueError as exc:
        log.error("research_store: %s", exc)
        return 2
    checks = research.run_checks(data, bt_io.read_dividends())
    print(format_summary(store, data, checks, note=note))
    return 0 if all(c.ok for c in checks) else 1
```

**Impact:** `test_command_verify_missing_store_exits_2` still gets exit 2 with empty stdout —
`_store_window` now produces it, via `declared_window`'s "no research store" `ValueError`,
before anything is printed.

---

### Step 15: `commands/research_store.py` — `format_summary` prints the window

**File:** `engine/src/seer_engine/commands/research_store.py:244-265`
**Change:** one added line, and `unserved_by_year` gets the store's window so a test store's
table runs to the test window's last year.

**Code:**
```python
def format_summary(
    store: Path,
    data: research.ResearchData,
    checks: Sequence[research.Check],
    *,
    note: str = "",
) -> str:
    m = data.manifest
    w = data.window
    # The window says what is SCORED; store_start says what is HELD. They differ on a test
    # store (data from 1993, scoring from 2015-10-19), and printing both stops anyone reading
    # the test store as if it began at its window start.
    scored_from = "each candidate's first tradable session" if w.start == date.min else w.start.isoformat()
    lines = [
        f"research store {store}{note}",
        f"  window: {w.name}, scored from {scored_from}, data through {w.end.isoformat()}",
        f"  dev_end: {m['dev_end']}  store_start: {m['store_start']}",
        f"  fingerprint: {data.fingerprint}",
        f"  symbols: {m['symbols_served']} served of {m['symbols_requested']} requested, "
        f"{len(data.unserved)} unserved",
        f"  rows: {m['bar_rows']:,} bars, {m['dividend_rows']:,} dividends, {m['fx_rows']:,} fx",
        "  unserved members by year (unserved of members):",
    ]
    for year, members, unserved in research.unserved_by_year(
        data.market.membership, data.unserved, window=data.window
    ):
        lines.append(f"    {year}: {unserved} of {members}")
    for check in checks:
        lines.append(f"  check {check.name}: {'ok' if check.ok else 'FAIL'}: {check.detail}")
    return "\n".join(lines)
```

`format_summary` needs `from datetime import date` — Step 12 already adds it for
`_session_date`.

**Impact:** `test_command_verify_prints_fingerprint_and_checks` asserts four substrings with
`in out`; adding a line cannot break any of them.

---

### Step 16: `.gitignore` and the ruff exclude

**File:** `.gitignore:21-24`
**Change:** the test store and its two swap siblings. `research._swap_in` creates
`<store>.tmp` and `<store>.old` next to the store, so all three names must be ignored.

**Code (replace the block that currently lists the three `.research` entries):**
```
# P7a research store (seer_engine.research; rebuilt by `python -m seer_engine research_store`)
engine/.research/
engine/.research.tmp/
engine/.research.old/

# P7b test-window research store (`python -m seer_engine research_store --test-window`);
# built on first promotion, never before (docs/plans/2026-10-04-method-lab-design.md §3)
engine/.research-test/
engine/.research-test.tmp/
engine/.research-test.old/
```

**File:** `engine/pyproject.toml:37`
**Change:** keep ruff out of a multi-gigabyte data directory.

**Code:**
```toml
extend-exclude = [".cache", ".research", ".research-test"]
```

**Impact:** `test_store_dirs_are_gitignored` checks three specific entries are *present* in the
file; it does not assert the list is exhaustive, so it passes unchanged.

---

### Step 17: `engine/tests/test_research_test_store.py` — the phase's tests

**File:** `engine/tests/test_research_test_store.py` (new)
**Change:** a self-contained suite. It deliberately does **not** import from
`test_research_store.py` (`engine/tests/` has no `__init__.py` and no cross-test imports exist
in the tree) and does not edit it: the 110 shipped research/lab tests must stay byte-identical.
The fixtures are the same tiny shapes, trimmed to what this phase needs.

`TEST_END = date(2016, 1, 4)` is chosen because it is a real NYSE session (verified), it is
after `DEV_END`, and it is the date the membership fixture's third snapshot lands on — so the
same fixture exercises a joiner (`NEW`) and a leaver (`BBB`) at the test window's edge.

**Code:**
```python
"""Tests for the P7b test-window research store: building it, declaring its window, and the
refusal that keeps a dev store and a test store from being used for each other.

No test touches the network or a database. yfinance is an injected fake, Frankfurter is a fake,
sleeps are recorded, and membership comes from a tiny CSV fixture. Nothing here builds the real
test store: that is an operator action, taken the first time a method is promoted.

Deliberately separate from ``test_research_store.py``, which is shipped code this phase leaves
byte-identical -- in particular its ``set(manifest) == research.MANIFEST_KEYS`` assertion, which
is what forces this phase's window identity to be additive and absent on a dev build.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from seer_engine import cli, config, research, yahoo

COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]

D1 = date(1999, 1, 4)
D2 = date(1999, 1, 5)
D3 = date(2015, 10, 16)  # == DEV_END
POST = date(2015, 10, 19)  # == TEST_WINDOW_START, the first session after DEV_END
TEST_END = date(2016, 1, 4)  # an NYSE session, and the membership fixture's third snapshot


# ---- fakes ---------------------------------------------------------------------------------


def bar_rows(*days, base=10.0):
    return [(d, base, base + 1, base - 1, base + 0.5, 1000 + i) for i, d in enumerate(days)]


def ticker_frame(rows, divs):
    index = pd.DatetimeIndex([pd.Timestamp(r[0]) for r in rows], name="Date")
    data = [
        [o, h, l, c, round(c * 0.9, 6), v, float(divs.get(d, 0.0)), 0.0]
        for (d, o, h, l, c, v) in rows
    ]
    return pd.DataFrame(data, index=index, columns=pd.Index(COLS, name="Price"), dtype=float)


def multi_frame(by_ticker):
    frames = {t: ticker_frame(rows, divs) for t, (rows, divs) in by_ticker.items()}
    return pd.concat(
        list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
    )


def default_data():
    """yahoo ticker -> (rows, dividends). GONE and NEW are absent; DDD only after DEV_END."""
    data = {etf: (bar_rows(D1, D2, D3, TEST_END, base=50.0), {}) for etf in research.RESEARCH_ETFS}
    data["SPY"] = (bar_rows(D1, D2, D3, POST, TEST_END, base=100.0), {D2: 0.25, POST: 0.5})
    data["AAA"] = (bar_rows(D1, D2, D3), {D2: 2.65 / 28})
    data["BBB"] = (bar_rows(D1, D3, base=20.0), {})
    data["BRK-B"] = (bar_rows(D2, D3, base=70.123456), {})
    data["CCC"] = (bar_rows(D3, POST), {})
    data["DDD"] = (bar_rows(POST), {POST: 1.0})
    return data


class FakeYahoo:
    """Injected downloader. Ignores the date range on purpose (the store must clip)."""

    def __init__(self, data):
        self.data = data
        self.calls: list[tuple[list[str], date, date]] = []

    def __call__(self, tickers, start, end_exclusive):
        self.calls.append((list(tickers), start, end_exclusive))
        return multi_frame({t: self.data.get(t, ([], {})) for t in tickers})


def fx_for(end: date):
    """A Frankfurter fake that asserts the build asked for FX_START..``end``."""

    def fetch(start, got_end):
        assert (start, got_end) == (research.FX_START, end)
        return [(D1, Decimal("8002")), (D2, 8010.5), (POST, Decimal("13600")), (TEST_END, 13700)]

    return fetch


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


@pytest.fixture
def members_dir(tmp_path):
    d = tmp_path / "members"
    d.mkdir()
    (d / "sp500_history.csv").write_text(
        "date,tickers\n"
        '1996-01-02,"AAA,BBB,GONE"\n'
        '2000-01-03,"AAA,BBB,BRK.B,CCC"\n'
        '2016-01-04,"AAA,CCC,NEW"\n',
        encoding="utf-8",
    )
    (d / "ndx_history.csv").write_text('date,tickers\n2007-02-01,"AAA,DDD"\n', encoding="utf-8")
    (d / "membership_overrides.csv").write_text("date,index_id,action,ticker,note\n", encoding="utf-8")
    (d / "ticker_aliases.csv").write_text("old,new,effective_date,note\n", encoding="utf-8")
    return d


def build(store, members_dir, *, window=None):
    w = research.DEV_WINDOW if window is None else window
    return research.build_store(
        store,
        downloader=FakeYahoo(default_data()),
        fetch_fx=fx_for(w.end),
        sleep=Sleeps(),
        batch_size=40,
        data_dir=members_dir,
        window=w,
    )


def read(store, name):
    return (store / name).read_text(encoding="utf-8")


def reseal(store):
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    files = {n: research.file_sha256(store / n) for n in research.DATA_FILES}
    manifest["files"] = files
    manifest["fingerprint"] = research.fingerprint_of(files)
    (store / research.MANIFEST_FILE).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


# ---- the window ------------------------------------------------------------------------------


def test_test_window_constants_and_constructor():
    assert research.TEST_WINDOW_START == date(2015, 10, 19)
    assert research.TEST_STORE_DIR == config.REPO_ROOT / "engine" / ".research-test"
    assert research.TEST_STORE_DIR != research.STORE_DIR
    w = research.test_window(TEST_END)
    assert (w.name, w.start, w.end) == ("test", research.TEST_WINDOW_START, TEST_END)
    assert w != research.DEV_WINDOW
    assert research.DEV_WINDOW.name == "dev" and research.DEV_WINDOW.end == research.DEV_END
    # Phase 1 owns Window.following; this asserts the two spellings have not drifted.
    assert w == research.DEV_WINDOW.following("test", TEST_END)
    # The window bounds scoring, the store bounds data: the test store still starts at 1993.
    assert research.STORE_START < research.TEST_WINDOW_START
    with pytest.raises(ValueError, match="must end after DEV_END"):
        research.test_window(research.DEV_END)
    with pytest.raises(ValueError, match="must end after DEV_END"):
        research.test_window(date(2015, 1, 2))
    with pytest.raises(ValueError, match="NYSE session"):
        research.test_window(date(2016, 1, 3))  # a Sunday
    with pytest.raises(TypeError):
        research.test_window(datetime(2016, 1, 4, tzinfo=timezone.utc))


def test_latest_session_is_the_last_settled_nyse_session():
    assert research.latest_session(datetime(2016, 1, 5, 23, 0, tzinfo=timezone.utc)) == date(2016, 1, 5)
    # Before the close + settle on the 5th, the latest settled session is the 4th.
    assert research.latest_session(datetime(2016, 1, 5, 12, 0, tzinfo=timezone.utc)) == date(2016, 1, 4)


def test_test_store_dirs_are_gitignored():
    lines = (config.REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("engine/.research-test/", "engine/.research-test.tmp/", "engine/.research-test.old/"):
        assert entry in lines


def test_manifest_keys_stay_nine_and_the_window_is_optional():
    """The dev store on disk carries exactly these nine keys. Widening the required set would
    refuse it before any reader ran, and its fingerprint 399d0d25... is the sync identity."""
    assert research.MANIFEST_KEYS == frozenset(
        {
            "dev_end",
            "store_start",
            "files",
            "fingerprint",
            "bar_rows",
            "dividend_rows",
            "fx_rows",
            "symbols_requested",
            "symbols_served",
        }
    )
    assert research.OPTIONAL_MANIFEST_KEYS == frozenset(
        {"window_name", "window_start", "window_end"}
    )
    assert not research.MANIFEST_KEYS & research.OPTIONAL_MANIFEST_KEYS


# ---- build -----------------------------------------------------------------------------------


def test_a_dev_build_declares_no_window(tmp_path, members_dir):
    manifest = build(tmp_path / "dev", members_dir)
    assert set(manifest) == research.MANIFEST_KEYS
    assert not research.OPTIONAL_MANIFEST_KEYS & set(manifest)
    assert manifest["dev_end"] == "2015-10-16"


def test_a_test_build_declares_its_window(tmp_path, members_dir):
    store = tmp_path / "test"
    manifest = build(store, members_dir, window=research.test_window(TEST_END))
    assert set(manifest) == research.MANIFEST_KEYS | research.OPTIONAL_MANIFEST_KEYS
    assert manifest["window_name"] == "test"
    assert manifest["window_start"] == "2015-10-19"
    assert manifest["window_end"] == TEST_END.isoformat()
    assert manifest["dev_end"] == "2015-10-16"  # still the code-version pin, not the window
    # The data still starts in 1993: window_start bounds scoring, store_start bounds the files.
    assert manifest["store_start"] == "1993-01-29"
    assert manifest["fingerprint"] == research.fingerprint_of(manifest["files"])
    assert manifest == json.loads(read(store, research.MANIFEST_FILE))


def test_a_test_build_requests_the_test_windows_members(tmp_path, members_dir):
    """The universe is the test window's members at BOTH ends (reconciled; index Decisions)."""
    dev = research.requested_symbols(members_dir)
    test = research.requested_symbols(members_dir, window=research.test_window(TEST_END))
    assert "NEW" not in dev  # joined 2016-01-04, after DEV_END
    assert "NEW" in test  # the far end moves: a post-2015 joiner is a test-window member
    assert "GONE" in dev  # a 1996-2000 member is a dev-window member
    assert "GONE" not in test  # ... and is a member on no test-window session, so nothing reads it
    assert "AAA" in dev and "AAA" in test  # a member across both windows is in both universes
    assert set(research.RESEARCH_ETFS) <= set(test)  # the ETFs are unconditional


def test_a_test_store_clamps_membership_against_its_own_end(tmp_path, members_dir):
    dev = research.research_membership(members_dir)
    test = research.research_membership(members_dir, window=research.test_window(TEST_END))
    # BBB leaves the index on 2016-01-04. For the dev window that end is beyond the window and
    # becomes None (a member on every dev session). For the test window it must stay a real end,
    # or a company that left would read as a member for the rest of the test window.
    assert ("BBB", date(1996, 1, 2), None) in dev.intervals
    assert ("BBB", date(1996, 1, 2), TEST_END) in test.intervals
    assert "NEW" not in dev.symbols()
    assert "NEW" in test.symbols()
    assert all(end is None or end <= TEST_END for _, _, end in test.intervals)


def test_a_test_store_is_a_superset_of_the_dev_stores_date_range(tmp_path, members_dir):
    """The coordinator's decision: the test store carries the FULL history from STORE_START.

    If it began at the test window's start, a candidate needing ~252 sessions of run-up would
    have its single, permanent, append-only look open ~10 months late.

    The comparison is **per symbol**, not over the whole file: the test universe is the test
    window's members (index Decisions), so GONE -- a 1996-2000 member -- is in the dev store
    and deliberately not in the test one. For every symbol the two universes share, the test
    store holds every dev row and more.
    """
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    build(test, members_dir, window=research.test_window(TEST_END))
    dev_bars = set(read(dev, research.BARS_FILE).splitlines()[1:])
    test_bars = set(read(test, research.BARS_FILE).splitlines()[1:])
    shared = {s for s in research.requested_symbols(members_dir)} & {
        s for s in research.requested_symbols(members_dir, window=research.test_window(TEST_END))
    }
    dev_shared = {line for line in dev_bars if line.split(",", 1)[0] in shared}
    assert dev_shared and dev_shared < test_bars  # every shared dev row, plus the post-DEV_END ones
    assert {line for line in test_bars if line.split(",", 1)[0] == "GONE"} == set()
    assert "SPY,1999-01-04," in read(test, research.BARS_FILE)  # the run-up is there
    assert "AAA,1999-01-05,0.094643" in read(test, research.DIVIDENDS_FILE)
    assert read(test, research.FX_FILE).startswith("date,usd_idr\n1999-01-04,")


def test_a_test_build_holds_the_post_dev_end_rows(tmp_path, members_dir):
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    build(test, members_dir, window=research.test_window(TEST_END))
    assert "2015-10-19" not in read(dev, research.BARS_FILE)
    assert "SPY,2015-10-19," in read(test, research.BARS_FILE)
    assert f"SPY,{TEST_END.isoformat()}," in read(test, research.BARS_FILE)
    assert "SPY,2015-10-19,0.5" in read(test, research.DIVIDENDS_FILE)
    assert f"{TEST_END.isoformat()},13700" in read(test, research.FX_FILE)
    # DDD has only a post-DEV_END bar: unserved for the dev window, served for the test window.
    assert "DDD," in read(dev, research.UNSERVED_FILE)
    assert "DDD," not in read(test, research.UNSERVED_FILE)


def test_a_test_build_requests_bars_through_its_window_end(tmp_path, members_dir):
    fake = FakeYahoo(default_data())
    research.build_store(
        tmp_path / "test",
        downloader=fake,
        fetch_fx=fx_for(TEST_END),
        sleep=Sleeps(),
        data_dir=members_dir,
        window=research.test_window(TEST_END),
    )
    assert fake.calls
    for _tickers, start, end_exclusive in fake.calls:
        assert start == research.STORE_START
        assert end_exclusive == TEST_END + pd.Timedelta(days=1).to_pytimedelta()


# ---- load: the refusal -------------------------------------------------------------------------


def test_load_store_round_trips_a_test_store(tmp_path, members_dir):
    store = tmp_path / "test"
    window = research.test_window(TEST_END)
    manifest = build(store, members_dir, window=window)
    data = research.load_store(store, data_dir=members_dir, window=window)
    assert data.window == window
    assert data.fingerprint == manifest["fingerprint"]
    assert data.market.bar("SPY", POST) is not None
    assert data.market.membership.members_on(date(2016, 1, 5)) == frozenset({"AAA", "CCC"})
    assert any(d.ex_date == POST for d in data.spy_dividends)


def test_load_store_refuses_a_test_store_where_a_dev_store_is_expected(tmp_path, members_dir):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    with pytest.raises(ValueError, match="not interchangeable"):
        research.load_store(store, data_dir=members_dir)  # the dev default
    with pytest.raises(ValueError, match="declares the test window"):
        research.load_store(store, data_dir=members_dir, window=research.DEV_WINDOW)


def test_load_store_refuses_a_dev_store_where_a_test_store_is_expected(tmp_path, members_dir):
    store = tmp_path / "dev"
    build(store, members_dir)
    with pytest.raises(ValueError, match="declares the dev window"):
        research.load_store(store, data_dir=members_dir, window=research.test_window(TEST_END))


def test_load_store_refuses_a_test_store_for_the_wrong_end(tmp_path, members_dir):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    with pytest.raises(ValueError, match="not interchangeable"):
        research.load_store(store, data_dir=members_dir, window=research.test_window(date(2016, 1, 5)))


def test_load_store_refuses_a_row_after_the_test_windows_end(tmp_path, members_dir):
    store = tmp_path / "test"
    window = research.test_window(TEST_END)
    build(store, members_dir, window=window)
    text = read(store, research.FX_FILE)
    assert text.count(f"{TEST_END.isoformat()},") == 1
    (store / research.FX_FILE).write_text(
        text.replace(f"{TEST_END.isoformat()},", "2016-01-05,"), encoding="utf-8", newline="\n"
    )
    reseal(store)  # hashes match again: only the window's date guard can catch it
    with pytest.raises(ValueError, match="after the store's window end 2016-01-04"):
        research.load_store(store, data_dir=members_dir, window=window)


def test_declared_window_reads_the_manifest_alone(tmp_path, members_dir):
    dev, test = tmp_path / "dev", tmp_path / "test"
    build(dev, members_dir)
    build(test, members_dir, window=research.test_window(TEST_END))
    assert research.declared_window(dev) == research.DEV_WINDOW
    assert research.declared_window(test) == research.test_window(TEST_END)
    with pytest.raises(ValueError, match="no research store"):
        research.declared_window(tmp_path / "nope")


@pytest.mark.parametrize("key", ["window_name", "window_start", "window_end"])
def test_a_manifest_with_a_partial_window_declaration_is_refused(tmp_path, members_dir, key):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    del manifest[key]
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="all three or none"):
        research.load_store(store, data_dir=members_dir, window=research.test_window(TEST_END))


def test_a_manifest_may_not_declare_the_dev_window_by_name(tmp_path, members_dir):
    """The dev window is declared by ABSENCE. Allowing a second spelling would let the live dev
    store and a hand-edited one disagree about what they are."""
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["window_name"] = "dev"
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="never by name"):
        research.declared_window(store)


def test_a_declared_window_inside_the_dev_window_is_refused(tmp_path, members_dir):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    manifest["window_start"] = "2010-01-04"
    (store / research.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="must start after DEV_END"):
        research.declared_window(store)


# ---- checks -----------------------------------------------------------------------------------


def test_checks_use_the_stores_own_window(tmp_path, members_dir):
    store = tmp_path / "test"
    window = research.test_window(TEST_END)
    build(store, members_dir, window=window)
    data = research.load_store(store, data_dir=members_dir, window=window)
    sessions = research.check_spy_sessions(data)
    assert f"..{TEST_END.isoformat()}" in sessions.detail  # not ..2015-10-16
    assert research.check_spy_sessions(data, start=D1, end=D2).ok


# ---- command ------------------------------------------------------------------------------------


def test_command_refuses_the_test_window_on_the_dev_store(caplog):
    assert cli.main(["research_store", "--test-window", "--store", str(research.STORE_DIR)]) == 2
    assert cli.main(["research_store", "--store", str(research.TEST_STORE_DIR), "--verify"]) == 2


def test_command_refuses_coverage_and_window_end_misuse(tmp_path):
    assert cli.main(["research_store", "--coverage", "--test-window", "--store", str(tmp_path / "s")]) == 2
    assert cli.main(["research_store", "--window-end", "2016-01-04", "--store", str(tmp_path / "s")]) == 2
    assert (
        cli.main(
            [
                "research_store",
                "--test-window",
                "--verify",
                "--window-end",
                "2016-01-04",
                "--store",
                str(tmp_path / "s"),
            ]
        )
        == 2
    )


def test_command_verify_refuses_a_cross_window_store(tmp_path, members_dir, capsys):
    store = tmp_path / "test"
    build(store, members_dir, window=research.test_window(TEST_END))
    assert cli.main(["research_store", "--verify", "--store", str(store)]) == 2
    assert capsys.readouterr().out == ""


def test_command_builds_a_test_store(tmp_path, members_dir, monkeypatch, capsys):
    import functools

    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store,
            downloader=FakeYahoo(default_data()),
            fetch_fx=fx_for(TEST_END),
            sleep=Sleeps(),
            data_dir=members_dir,
        ),
    )
    monkeypatch.setattr(research, "latest_session", lambda now_utc=None: TEST_END)
    store = tmp_path / "test"
    code = cli.main(["research_store", "--test-window", "--store", str(store)])
    out = capsys.readouterr().out
    assert code == 1  # built fine; the real-data checks fail on fake data
    manifest = json.loads(read(store, research.MANIFEST_FILE))
    assert manifest["window_end"] == TEST_END.isoformat()
    assert f"window: test, scored from 2015-10-19, data through {TEST_END.isoformat()}" in out
    assert "store_start: 1993-01-29" in out  # the data range is NOT the window
    assert f"fingerprint: {manifest['fingerprint']}" in out


def test_command_window_end_pins_the_build(tmp_path, members_dir, monkeypatch):
    import functools

    monkeypatch.setattr(
        research,
        "build_store",
        functools.partial(
            research.build_store,
            downloader=FakeYahoo(default_data()),
            fetch_fx=fx_for(TEST_END),
            sleep=Sleeps(),
            data_dir=members_dir,
        ),
    )
    monkeypatch.setattr(research, "latest_session", lambda now_utc=None: date(2016, 1, 5))
    store = tmp_path / "test"
    cli.main(
        ["research_store", "--test-window", "--window-end", TEST_END.isoformat(), "--store", str(store)]
    )
    assert json.loads(read(store, research.MANIFEST_FILE))["window_end"] == TEST_END.isoformat()
```

**Note on two of these tests.** `test_a_test_build_requests_bars_through_its_window_end` uses
`pd.Timedelta(days=1).to_pytimedelta()` only to avoid a second `datetime` import name; plain
`timedelta(days=1)` is equivalent and preferable if the implementer adds the import.
`test_command_refuses_the_test_window_on_the_dev_store` names the real `research.STORE_DIR` but
never builds or reads it — `run()` refuses on the path comparison before any I/O.

**Impact:** about 25 new tests, none of which touch the network, a database or the real stores.

---

## Verification

**Build:** `cd engine && python -c "import seer_engine.research, seer_engine.commands.research_store"`
and `ruff check src tests`

**Tests:**
```bash
cd engine
pytest -q tests/test_research_test_store.py
pytest -q tests/test_research_store.py tests/test_fundamentals_coverage.py   # must be untouched and green
pytest -q                                                                     # the whole suite
git diff --stat -- tests/test_research_store.py tests/test_fundamentals_coverage.py  # must be empty
```

**Manual check — the dev store must still load, bit-identically:**
```bash
cd /home/miftah/seer
python -m seer_engine research_store --verify            # exit 0; fingerprint 399d0d25...
git -C . status --porcelain engine/.research             # gitignored: no output
python - <<'PY'
import json, pathlib
m = json.loads(pathlib.Path("engine/.research/manifest.json").read_text())
assert sorted(m) == ['bar_rows','dev_end','dividend_rows','files','fingerprint','fx_rows','store_start','symbols_requested','symbols_served'], sorted(m)
assert m["fingerprint"] == "399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8"
print("dev store manifest unchanged")
PY
python3 .claude/skills/sync-research-store/sync_store.py status   # still reports the same fingerprint
```

**Manual check — the refusals, without building anything:**
```bash
cd /home/miftah/seer
python -m seer_engine research_store --test-window --store engine/.research   # exit 2, refuses
python -m seer_engine research_store --coverage --test-window                 # exit 2, refuses
python -m seer_engine lab run M0007 --store engine/.research-test             # exit 2 once the
#   test store exists: "declares the test window ... are not interchangeable"
```

**Exit criteria:**
1. `python -m seer_engine research_store --test-window` builds `engine/.research-test` with the
   same five files, the same manifest shape plus `window_start`/`window_end`, and passes the
   same sha256 + fingerprint verification and the same three checks. (Not run in this phase —
   it is an operator action.)
2. `research.load_store` refuses a test store where a dev store is expected and a dev store
   where a test store is expected, before reading any data file, with a message naming both
   windows. Both directions are tested.
2b. For every symbol the dev and test universes share, the test store's bar/dividend/FX rows
   are a **strict superset** of the dev store's — it starts at `STORE_START` (1993-01-29), not
   at the test window's start — and its `store_start` manifest key reads `"1993-01-29"` while
   `window_start` reads `"2015-10-19"`.
3. A test store's membership intervals are clamped against the test window's end: a company
   that leaves the index in 2016 has a real end date, not `None`.
4. A test store's universe is the test window's members at **both** ends: every company that
   joined the index after October 2015 is in it, and every company that left before 2015-10-19
   is not. `requested_symbols(window=test)` ⊄ `requested_symbols()` and vice versa; neither is
   a superset of the other, and that is the correct answer, not a regression.
5. The dev store at `engine/.research` loads with `--verify` exiting 0, its manifest has exactly
   nine keys, and its fingerprint is still
   `399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`.
6. `pytest -q` is green in `engine/`, and `tests/test_research_store.py` and
   `tests/test_fundamentals_coverage.py` show an empty `git diff`.
7. `engine/.research-test` and its two swap siblings are gitignored; `git status` stays clean
   after a build.

---

## Handoffs

- **Phase 1** owns `backtest/window.py`, `DEV_WINDOW`, the four generalised helpers and
  `unserved_reason(start, end)`. This phase fills exactly the four call sites phase 1 named and
  adds nothing to them. The one property phase 1 must hold for this phase to be safe:
  `unserved_reason(STORE_START, DEV_END)` is byte-identical to the retired `UNSERVED_REASON`
  constant, because that text is hashed into the dev store's fingerprint `399d0d25…`.
- **Phase 1 also edits `engine/tests/test_research_store.py`** (an import plus an appended
  section). This phase touches no existing test file; its additions are a new module. If the
  reconciler finds both phases adding a `Window`-shaped fixture there, the duplicate belongs to
  phase 1 and this phase's new file should keep its own self-contained fakes.
- **Phase 4** owns `lab test`, the test-window runner, and the `lab` CLI. It consumes
  `research.declared_window` + `research.load_store(path, window=…)` and `data.window`; it must
  **not** change `commands/lab.py:237`'s `research.load_store(Path(args.store))`, whose dev
  default is what makes a mis-pointed `SEER_RESEARCH_STORE` fail loudly on `lab run`. Phase 4
  also owns whether `lab test` gets its own `--store` default of `research.TEST_STORE_DIR`.
  **Three names phase 4 must spell exactly as this phase defines them** (reconciled
  2026-10-06): the build flag is `--test-window`, never `--test`; `load_store`'s `window=` takes
  a `Window` value, never the string `"test"`; and the loaded store's window is
  `ResearchData.window`, a `Window`. Phase 4's plan has been edited to match.
- **`fundamentals/coverage.WINDOW_END` is left alone.** `--coverage` is a dev-window measure
  and this phase refuses to combine it with `--test-window` rather than inventing a test-window
  coverage metric. If `lab test` ever needs a coverage floor on the test window, that is a new
  decision for a later phase, not a drive-by here.
- **Fundamentals are not filtered by the window, deliberately.** `bt_io.read_facts()` returns
  every fact with no date bound, and `build_store` writes them all. That is safe —
  `FundamentalPanel` selects point-in-time on `filed <= t`, so a 2020 filing is invisible on a
  2012 session — and filtering here would rewrite `fundamentals.csv` and move the dev store's
  fingerprint, which is the one thing this phase may not do. Recorded so nobody reads the
  absence of a filter as an oversight.
- **The `sync-research-store` skill is untouched.** It is hard-wired to `engine/.research` and
  reads only `files` + `fingerprint`, so it keeps working unchanged and simply does not know
  about the test store. Teaching it to carry `engine/.research-test` is a separate, optional
  piece of work — worth doing only once a real test store exists on one machine and is wanted
  on another, which this plan set does not reach.
- **`docs/runbooks/data-pipeline.md`** describes the store build and will be one paragraph
  stale. Left to the plan set's documentation pass, not added here.

---

## Rollback

This phase is one commit on `feature/build-promotion-path`; `git revert` it.

Nothing it changes is load-bearing for anything that exists today: every new parameter is
keyword-only and defaults to the dev window, so reverting restores the exact previous
behaviour of `build_store`, `load_store`, `refresh_fundamentals` and the `research_store`
command. No data on disk is rewritten — `engine/.research` is never opened for writing by any
code path this phase adds, and the two clobber guards exist to keep it that way.

If a test store was built before the revert, delete it: `rm -rf engine/.research-test
engine/.research-test.tmp engine/.research-test.old`. It is gitignored, so nothing else has to
be unwound. No lab trial, no `lab/lab.sqlite` row and no test-window look is created by this
phase, so there is no lab state to roll back.
