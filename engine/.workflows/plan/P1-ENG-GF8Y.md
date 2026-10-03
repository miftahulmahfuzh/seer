> Adopted from `ENGINE_DATA_PIPELINE_PLAN.md` phase 4. Source: `.workflows/plan/engine-data-pipeline/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Nightly command: Massive bars, splits, FX, runs

**Plan set:** `ENGINE_DATA_PIPELINE_PLAN.md`
**Analysis:** `20261003-121931-K7P2_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-data-pipeline.md` (§2.3, §3 "Nightly source", §6.3, §6.4, §6.5, §6.7)
**Satisfies:** R3, R4, R6. Every US trading night `python -m seer_engine nightly` appends the newest
session's bars from Massive grouped daily, keeps split history consistent, records USD/IDR, and writes
exactly one `runs` row per target session. A re-run is a no-op, a failed fetch leaves no partial bars,
and `--dry-run` writes nothing.
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/`

---

## Goal

After this phase, `python -m seer_engine nightly [--now ISO8601]` computes `RunDates` and returns
without writing anything when that `session_date` has already succeeded. Otherwise it:

- fetches every missing NYSE session up to `data_date` (at most 30) from Massive grouped daily, with
  calls spaced at least 12.5 s apart,
- fetches that day's splits and the latest USD/IDR rate,
- applies each split to stored history exactly once,
- in **one** transaction, writes the bars for universe ∪ SPY plus FX and marks the run `success`.

On any failure the run row is marked `failed` with a redacted error and nothing else is written.
`--dry-run` does every read and fetch, runs the write transaction, and rolls it back.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `seer_engine.massive` (`engine/src/seer_engine/massive.py`):
  - `BASE_URL`, `MIN_INTERVAL = 12.5`, `RETRIES = 4`, `BACKOFF = 15.0`, `MAX_PAGES = 50`, `OK_STATUSES`
  - `class MassiveError(RuntimeError)`
  - `class MassiveSource(Protocol)` with `grouped(d) -> dict[str, Bar]` and `splits(d) -> list[Split]`
  - `class Client(api_key, *, base_url, min_interval, retries, backoff, get_json, clock, sleep)` with `.grouped(d)`, `.splits(d)`, `.calls`
- `seer_engine.splits` (`engine/src/seer_engine/splits.py`):
  - `@dataclass(frozen) Split(symbol, execution_date, split_from: Decimal, split_to: Decimal)`, with `.factor` and `Split.from_massive(raw, default_date)`
  - `AMBIGUOUS_LOG_FACTOR`
  - `should_apply(prev_close, open_today, factor) -> bool`
  - `@dataclass(frozen) SplitOutcome(split, recorded, applied, reason, rows)`
  - `symbols_with_bars(conn, symbols) -> set[str]`
  - `apply_splits(conn, items, first_opens) -> list[SplitOutcome]`
- `seer_engine.commands.nightly` (`engine/src/seer_engine/commands/nightly.py`):
  - `HELP`, `add_arguments(p)` (adds `--now`), `run(args) -> int`
  - `execute(conn, *, now, client, dry_run=False, fetch_fx=None, secret=None) -> int`
  - `class NightlyError(RuntimeError)`, `@dataclass(frozen) Fetched`, `MAX_GAP = 30`, `MIN_COVERAGE = 0.90`
- Tests: `engine/tests/test_massive.py`, `engine/tests/test_splits.py`, `engine/tests/test_nightly.py`

**Signature changes:** none (all new)

**Requires (from Phase 1, used exactly as written in the plan index's shared contract):**
- `config.require(name) -> str` and `config.ConfigError`
- `db.connect()` and `db.transaction(conn, dry_run)`: a context manager that commits on clean
  exit and rolls back when `dry_run` is true or on an exception, which it re-raises
- `http.get_json(url, params=None, *, retries, backoff, timeout)`, which retries 429/5xx itself
  with backoff, raises on final failure, and returns parsed JSON. Also `http.redact(text)`, which
  masks `apiKey=…` anywhere in a string. Phase 4 also scrubs the literal key itself, as a second guard.
- `dates.run_dates(now_utc) -> RunDates(data_date, session_date)`, `dates.sessions(start, end)`
  (inclusive, ascending), `dates.next_session(d)`
- `runs.start_run(conn, rd) -> int|None`: None when that session already succeeded. It reuses a
  `failed` row for the same `session_date` (same id).
- `runs.finish_run(conn, run_id)` and `runs.fail_run(conn, run_id, error)`. Like `start_run`,
  **none of the three commits**; the caller wraps them in `db.transaction`.
- `bars.Bar` (fields `symbol, date, open, high, low, close, volume`; Decimal prices, int volume)
- `bars.make_bar(symbol, d, o, h, l, c, v)`, which accepts floats, rounds prices to 4 dp and makes volume an int
- `bars.upsert_bars(conn, bars) -> int` and `bars.latest_bar_date(conn, symbol) -> date|None`
- `fx.fetch_latest() -> (date, Decimal)` and `fx.upsert_fx(conn, rows) -> int`
- `universe.BENCHMARK == "SPY"` and `universe.symbols_for_bars(conn, d, grace_days=30) -> set[str]` (includes SPY)
- `demo.purge_demo_if_needed(conn, dry_run) -> bool`, which runs in its own transaction
- Table `split_adjustments(symbol text, execution_date date, split_from numeric, split_to numeric,
  applied boolean, recorded_at timestamptz DEFAULT now(), PRIMARY KEY (symbol, execution_date))`
- The partial unique index `runs(session_date) WHERE NOT is_demo`
- CLI discovery of `commands/nightly.py` (invariant 7); `args.dry_run` is set by `cli.py`
- `engine/tests/conftest.py` fixture **`pg`**: a `psycopg.Connection` (autocommit off) on a fresh
  schema with every `db/migrations/*.sql` applied, skipped when `PG_TEST_URL` is unset

**Leaves alone (owned by others):**
- Every Phase 1 file (`config/db/http/dates/demo/universe/bars/fx/runs.py`, `cli.py`, `conftest.py`, `002_engine.sql`)
- `membership.py`, `commands/universe.py` and `engine/data/*` (Phase 2)
- `yahoo.py` and `commands/backfill.py` (Phase 3)
- `.github/`, `web/` and `docs/` (Phase 5)

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/splits.py` | create (line 1) | `Split` model, `should_apply` heuristic, `apply_splits` DB writer (records once, rewrites history once) |
| `engine/src/seer_engine/massive.py` | create (line 1) | rate-limited Massive client: grouped daily and splits (with pagination) |
| `engine/src/seer_engine/commands/nightly.py` | create (line 1) | the `nightly` command: the run lifecycle, fetch-then-write, the dry-run path |
| `engine/tests/test_splits.py` | create (line 1) | heuristic unit tests and DB tests for applying once, already-adjusted, rounding and chains |
| `engine/tests/test_massive.py` | create (line 1) | throttling, parsing, empty/failed responses, pagination, key never logged |
| `engine/tests/test_nightly.py` | create (line 1) | end-to-end against `pg` with a fake Massive and a fixed `--now` |

## Design decisions made in this phase

1. **Every split in the gap is applied before any fetched bar is upserted.** This deliberately
   refines the brief's per-D ordering. Massive `adjusted=true` adjusts **as of fetch time**. In a
   multi-session gap, then, the fetched bar for D1 already reflects a split executed on D2 > D1. If
   splits were applied per D after D1's bars had been upserted, D1 would be divided twice. So the
   whole gap's splits rewrite only the history that existed before this run, and then all fetched
   bars are upserted. A single-session night behaves exactly like the brief's flow.
2. **A deterministic guard comes before the heuristic.** A symbol whose latest stored bar is on or
   after the split's `execution_date` was fetched after the split, by a backfill, so it is already
   adjusted and `applied=false`. Otherwise the stored history predates the split by construction.
   The brief's `should_apply` heuristic then acts as a safety net, and it is only consulted when it
   is reliable: `|ln f| ≥ ln 1.25`. For tiny factors (stock dividends like 21:20), ordinary overnight
   gaps swamp the signal, so the split is applied because the history predates it. This is the
   "tiny factor ambiguity" case.
3. **Chained splits in one gap.** For the k-th split of a symbol inside one batch, the reference
   open is `first_fetched_open × Π(factor of later splits in the batch)`. That undoes the later
   adjustments already baked into the fetched open, so each split is judged on its own factor.
4. **Which splits are recorded.** Only those for symbols in the night's wanted set (universe ∪ SPY)
   or that already have stored bars. Recording the ~dozens of unrelated market splits per day
   would be noise.
5. **Universe empty means failure.** If `symbols_for_bars(D) == {SPY}`, the night fails with
   "run `universe refresh` first" rather than silently storing SPY only.
6. **Massive `status` values `OK` and `DELAYED` are both accepted.** The free tier may label
   recent aggregates `DELAYED`. Anything else is a `MassiveError`, and so are empty `results`
   ("not published yet").
7. **DB reads happen outside any write transaction and are closed with `conn.rollback()`.** That
   way no implicit transaction stays open across the up-to-12.5-minute fetch loop, and nothing
   relies on `db.transaction` nesting semantics.
8. **Dry-run calls `runs.start_run` twice.** The first call is in a rolled-back transaction, to
   learn whether the session already succeeded. The second is inside the rolled-back write
   transaction, so `finish_run` exercises a real row. Neither commits. The `runs_id_seq` sequence
   still advances, which is not table contents, so checksums are unaffected.

## Implementation Steps

### Step 1: Split model, heuristic and DB application
**File:** `engine/src/seer_engine/splits.py:1` (new)
**Change:** Create the module.
**Code:**
```python
"""Stock splits: decide whether stored history still needs a split, and apply it exactly once.

A split with factor f = split_to / split_from (NVDA 2024-06-10: 1 -> 10, f = 10) means every bar
before the execution date must be rewritten: prices * 1/f, volume * f. `split_adjustments` holds
one row per (symbol, execution_date); a split whose row already exists is never applied again, so
re-runs and replays cannot double-adjust.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from psycopg.rows import tuple_row

log = logging.getLogger(__name__)

# Below this |ln f| (f within 0.8x..1.25x) normal overnight gaps can exceed the split itself,
# so the price heuristic is not trusted; history that predates the split is adjusted by construction.
AMBIGUOUS_LOG_FACTOR = math.log(1.25)


def _positive_decimal(value: Any, name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"{name} is not a number: {value!r}") from e
    if not d.is_finite() or d <= 0:
        raise ValueError(f"{name} must be positive: {value!r}")
    return d


@dataclass(frozen=True)
class Split:
    symbol: str
    execution_date: date
    split_from: Decimal
    split_to: Decimal

    @property
    def factor(self) -> Decimal:
        """Shares after / shares before: 10 for a 10-for-1, 1/32 for a 1-for-32 reverse split."""
        return self.split_to / self.split_from

    @classmethod
    def from_massive(cls, raw: Mapping[str, Any], default_date: date) -> "Split":
        """Build from a Massive /v3/reference/splits result row. Raises KeyError/ValueError if malformed."""
        symbol = raw["ticker"]
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"bad ticker: {symbol!r}")
        ex = raw.get("execution_date")
        execution_date = date.fromisoformat(ex) if ex else default_date
        return cls(
            symbol=symbol,
            execution_date=execution_date,
            split_from=_positive_decimal(raw["split_from"], "split_from"),
            split_to=_positive_decimal(raw["split_to"], "split_to"),
        )


@dataclass(frozen=True)
class SplitOutcome:
    split: Split
    recorded: bool  # a new split_adjustments row was inserted by this call
    applied: bool  # stored history was rewritten by this call
    reason: str
    rows: int  # bars rows rewritten


def should_apply(prev_close: Decimal | float, open_today: Decimal | float, factor: Decimal | float) -> bool:
    """True when stored history still looks unadjusted for a split of `factor`.

    prev_close is the latest stored close before the split; open_today is the first post-split
    (adjusted) open. If history is unadjusted, prev_close / (open_today * f) is near 1; if it is
    already adjusted, prev_close / open_today is near 1. Apply when the first is closer:
    |ln(prev/(open*f))| < |ln(prev/open)|.

    Factors within AMBIGUOUS_LOG_FACTOR of 1 always return True (callers only ask when the stored
    history predates the split); a factor of exactly 1 returns False.
    """
    p, o, f = float(prev_close), float(open_today), float(factor)
    if p <= 0 or o <= 0 or f <= 0:
        raise ValueError(f"should_apply needs positive inputs, got prev={p} open={o} factor={f}")
    log_f = math.log(f)
    if log_f == 0.0:
        return False
    if abs(log_f) < AMBIGUOUS_LOG_FACTOR:
        return True
    x = math.log(p / o)
    return abs(x - log_f) < abs(x)


def symbols_with_bars(conn: psycopg.Connection, symbols: Iterable[str]) -> set[str]:
    """The subset of `symbols` that has at least one row in bars."""
    wanted = sorted(set(symbols))
    if not wanted:
        return set()
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(
            "SELECT s FROM unnest(%s::text[]) AS s "
            "WHERE EXISTS (SELECT 1 FROM bars b WHERE b.symbol = s)",
            (wanted,),
        )
        return {row[0] for row in cur.fetchall()}


def _decide(cur: psycopg.Cursor, split: Split, ref_open: Decimal | None) -> tuple[bool, str]:
    factor = split.factor
    if factor == 1:
        return False, "factor is 1"
    cur.execute(
        "SELECT date, close FROM bars WHERE symbol = %s ORDER BY date DESC LIMIT 1",
        (split.symbol,),
    )
    row = cur.fetchone()
    if row is None:
        return False, "no stored bars"
    last_date, last_close = row
    if last_date >= split.execution_date:
        return False, f"stored history reaches {last_date.isoformat()}; already post-split"
    if ref_open is None or ref_open <= 0 or last_close <= 0:
        return True, "no reference open; stored history predates the split"
    if should_apply(last_close, ref_open, factor):
        return True, f"prev close {last_close} vs open {ref_open} fits factor {factor}"
    return False, f"prev close {last_close} vs open {ref_open} already consistent"


_INSERT = """
INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied)
VALUES (%(symbol)s, %(execution_date)s, %(split_from)s, %(split_to)s, %(applied)s)
ON CONFLICT (symbol, execution_date) DO NOTHING
RETURNING symbol
"""

_REWRITE = """
UPDATE bars SET
  open   = round(open  * %(split_from)s / %(split_to)s, 4),
  high   = round(high  * %(split_from)s / %(split_to)s, 4),
  low    = round(low   * %(split_from)s / %(split_to)s, 4),
  close  = round(close * %(split_from)s / %(split_to)s, 4),
  volume = round(volume * %(split_to)s / %(split_from)s)::bigint
WHERE symbol = %(symbol)s AND date < %(execution_date)s
"""


def apply_splits(
    conn: psycopg.Connection,
    items: Iterable[Split],
    first_opens: Mapping[str, Decimal],
) -> list[SplitOutcome]:
    """Record every split once and rewrite stored history for the ones that need it.

    Must run inside the caller's write transaction, before any bar fetched in this batch is
    upserted (fetched bars are adjusted as of fetch time and must not be rewritten).
    `first_opens[symbol]` is the open of the earliest fetched bar for that symbol in this batch.
    """
    by_symbol: dict[str, dict[date, Split]] = defaultdict(dict)
    for s in items:
        by_symbol[s.symbol].setdefault(s.execution_date, s)

    outcomes: list[SplitOutcome] = []
    with conn.cursor(row_factory=tuple_row) as cur:
        for symbol in sorted(by_symbol):
            chain = [by_symbol[symbol][d] for d in sorted(by_symbol[symbol])]
            for k, split in enumerate(chain):
                later = math.prod((s.factor for s in chain[k + 1 :]), start=Decimal(1))
                first_open = first_opens.get(symbol)
                ref_open = first_open * later if first_open is not None else None
                apply, reason = _decide(cur, split, ref_open)
                params = {
                    "symbol": split.symbol,
                    "execution_date": split.execution_date,
                    "split_from": split.split_from,
                    "split_to": split.split_to,
                    "applied": apply,
                }
                cur.execute(_INSERT, params)
                if cur.fetchone() is None:
                    outcomes.append(SplitOutcome(split, False, False, "already recorded", 0))
                    log.info("split %s %s already recorded; skipped", symbol, split.execution_date)
                    continue
                rows = 0
                if apply:
                    cur.execute(_REWRITE, params)
                    rows = cur.rowcount
                outcomes.append(SplitOutcome(split, True, apply, reason, rows))
                log.info(
                    "split %s %s %s:%s %s (%s; %d rows)",
                    symbol,
                    split.execution_date,
                    split.split_from,
                    split.split_to,
                    "applied" if apply else "not applied",
                    reason,
                    rows,
                )
    return outcomes
```
**Impact:** New module. It writes `split_adjustments` and `bars`, and is only called from inside a
`db.transaction`.

### Step 2: Massive client
**File:** `engine/src/seer_engine/massive.py:1` (new)
**Change:** Create the module.
**Code:**
```python
"""Massive (ex-Polygon) REST client: grouped daily bars and stock splits.

Free tier allows 5 calls/min, so calls are spaced >= MIN_INTERVAL seconds apart (measured from the
end of the previous call). Retries on 429/5xx are delegated to http.get_json with a backoff that is
itself >= MIN_INTERVAL. The API key only ever travels as the `apiKey` query parameter handed to
http.get_json; it is never put in a log line or an exception message built here.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from decimal import InvalidOperation
from typing import Any, Protocol

from seer_engine import bars as bars_mod
from seer_engine import http
from seer_engine.bars import Bar
from seer_engine.splits import Split

log = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"
MIN_INTERVAL = 12.5
RETRIES = 4
BACKOFF = 15.0
MAX_PAGES = 50
OK_STATUSES = frozenset({"OK", "DELAYED"})

GetJson = Callable[..., Any]


class MassiveError(RuntimeError):
    """Massive answered, but not with usable data (not published yet, not authorized, malformed)."""


class MassiveSource(Protocol):
    def grouped(self, d: date) -> dict[str, Bar]: ...

    def splits(self, d: date) -> list[Split]: ...


class Client:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        min_interval: float = MIN_INTERVAL,
        retries: int = RETRIES,
        backoff: float = BACKOFF,
        get_json: GetJson | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Massive API key is empty")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self.retries = retries
        self.backoff = backoff
        self._get_json: GetJson = get_json if get_json is not None else http.get_json
        self._clock = clock
        self._sleep = sleep
        self._last_call: float | None = None
        self.calls = 0

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._last_call is not None:
            wait = self._last_call + self.min_interval - self._clock()
            if wait > 0:
                log.debug("massive: waiting %.1fs for the rate limit", wait)
                self._sleep(wait)
        # The path without its query string and the non-secret params only; never the key.
        log.info("massive GET %s %s", url.split("?", 1)[0], params)
        self.calls += 1
        try:
            data = self._get_json(
                url,
                {**params, "apiKey": self._api_key},
                retries=self.retries,
                backoff=self.backoff,
            )
        finally:
            self._last_call = self._clock()
        if not isinstance(data, dict):
            raise MassiveError(f"unexpected response type from {url.split('?', 1)[0]}: {type(data).__name__}")
        return data

    def grouped(self, d: date) -> dict[str, Bar]:
        """Split-adjusted OHLCV for every US ticker on session d, keyed by Massive's (dot-form) ticker."""
        url = f"{self.base_url}/v2/aggs/grouped/locale/us/market/stocks/{d.isoformat()}"
        data = self._get(url, {"adjusted": "true"})
        status = data.get("status")
        if status not in OK_STATUSES:
            detail = data.get("message") or data.get("error") or ""
            raise MassiveError(f"grouped daily {d.isoformat()}: status {status!r} {detail}".strip())
        if data.get("adjusted") is False:
            raise MassiveError(f"grouped daily {d.isoformat()}: response is not split-adjusted")
        results = data.get("results") or []
        if not results:
            raise MassiveError(f"grouped daily {d.isoformat()}: no results (not published yet?)")
        out: dict[str, Bar] = {}
        skipped = 0
        for r in results:
            symbol = r.get("T")
            values = [r.get(k) for k in ("o", "h", "l", "c", "v")]
            if not isinstance(symbol, str) or not symbol or any(v is None for v in values):
                skipped += 1
                continue
            try:
                out[symbol] = bars_mod.make_bar(symbol, d, *values)
            except (ArithmeticError, ValueError, TypeError):
                skipped += 1
        if skipped:
            log.debug("grouped daily %s: skipped %d malformed rows", d.isoformat(), skipped)
        log.info("grouped daily %s: %d tickers", d.isoformat(), len(out))
        return out

    def splits(self, d: date) -> list[Split]:
        """Splits executing on d (follows next_url pagination)."""
        url = f"{self.base_url}/v3/reference/splits"
        params: dict[str, Any] = {"execution_date": d.isoformat(), "limit": 1000}
        out: list[Split] = []
        for _ in range(MAX_PAGES):
            data = self._get(url, params)
            status = data.get("status")
            if status is not None and status not in OK_STATUSES:
                detail = data.get("message") or data.get("error") or ""
                raise MassiveError(f"splits {d.isoformat()}: status {status!r} {detail}".strip())
            for raw in data.get("results") or []:
                try:
                    split = Split.from_massive(raw, d)
                except (KeyError, ValueError, TypeError, InvalidOperation) as e:
                    log.warning("splits %s: skipped malformed row %r (%s)", d.isoformat(), raw, e)
                    continue
                if split.execution_date == d:
                    out.append(split)
            next_url = data.get("next_url")
            if not next_url:
                log.info("splits %s: %d", d.isoformat(), len(out))
                return out
            url, params = next_url, {}
        raise MassiveError(f"splits {d.isoformat()}: more than {MAX_PAGES} pages")
```
**Impact:** New module. It has no import-time side effects. `http.get_json` is bound at construction.

### Step 3: The `nightly` command
**File:** `engine/src/seer_engine/commands/nightly.py:1` (new)
**Change:** Create the module. `cli.py` discovers it (invariant 7). No edit to `cli.py`.
**Code:**
```python
"""nightly: append the newest session(s) from Massive, apply splits, record USD/IDR, write the run.

Flow (all bars, splits, FX and the run's success land in ONE transaction):
  1. purge demo data if a demo run exists (own transaction; rolled back under --dry-run)
  2. rd = run_dates(now); start_run -> None means this session already succeeded -> exit 0, no writes
  3. missing sessions = after SPY's latest bar .. rd.data_date (at most MAX_GAP)
  4. fetch everything into memory (grouped daily + splits per session, latest FX); no DB writes
  5. one transaction: apply splits to pre-existing history, upsert bars, upsert FX, finish_run
  6. any exception after start_run: rollback, fail_run(error) in its own transaction, exit 1
"""
from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

import psycopg

from seer_engine import bars, config, dates, db, demo, fx, http, massive, runs, splits, universe
from seer_engine.bars import Bar
from seer_engine.splits import Split

log = logging.getLogger(__name__)

HELP = "Fetch the latest session's bars (Massive), splits and USD/IDR; write one runs row"

MAX_GAP = 30
MIN_COVERAGE = 0.90
MAX_ERROR_LEN = 2000

FxFetcher = Callable[[], tuple[date, Decimal]]


class NightlyError(RuntimeError):
    """A precondition or data-quality check failed; the run is marked failed."""


@dataclass(frozen=True)
class Fetched:
    sessions: list[date]
    bars_by_session: dict[date, list[Bar]]
    splits: list[Split]
    first_opens: dict[str, Decimal]
    fx_row: tuple[date, Decimal]


def _parse_now(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--now must be ISO 8601 (e.g. 2026-10-02T23:00:00Z): {value!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        metavar="ISO8601",
        help="pretend the current time is this (UTC if no offset); for tests and replays",
    )


def run(args: argparse.Namespace) -> int:
    try:
        api_key = config.require("MASSIVE_API_KEY")
    except config.ConfigError as e:
        log.error("%s", e)
        return 2  # same code cli.main gives any ConfigError (phase 1): a setup problem, not a failed run
    now = getattr(args, "now", None) or datetime.now(timezone.utc)
    conn = db.connect()
    try:
        return execute(
            conn,
            now=now,
            client=massive.Client(api_key),
            dry_run=bool(args.dry_run),
            secret=api_key,
        )
    finally:
        conn.close()


def _error_text(e: BaseException, secret: str | None) -> str:
    text = http.redact(f"{type(e).__name__}: {e}")
    if secret:
        text = text.replace(secret, "***")
    return text[:MAX_ERROR_LEN]


def execute(
    conn: psycopg.Connection,
    *,
    now: datetime,
    client: massive.MassiveSource,
    dry_run: bool = False,
    fetch_fx: FxFetcher | None = None,
    secret: str | None = None,
) -> int:
    """Run one nightly pass against `conn`. Returns the process exit code (0 ok / no-op, 1 failed)."""
    fetch_fx = fetch_fx if fetch_fx is not None else fx.fetch_latest
    demo.purge_demo_if_needed(conn, dry_run)

    rd = dates.run_dates(now)
    log.info("now %s -> data_date %s, session_date %s", now.isoformat(), rd.data_date, rd.session_date)

    with db.transaction(conn, dry_run):
        run_id = runs.start_run(conn, rd)
    if run_id is None:
        log.info("session %s already succeeded; nothing to do", rd.session_date)
        return 0
    if dry_run:
        log.info("dry-run: would start a run for session %s", rd.session_date)

    try:
        fetched = _fetch(conn, client, rd, fetch_fx)
        _write(conn, rd, fetched, run_id, dry_run)
    except Exception as e:  # noqa: BLE001 - every failure must become a failed run
        message = _error_text(e, secret)
        conn.rollback()
        log.error("nightly failed for session %s: %s", rd.session_date, message)
        if dry_run:
            log.info("dry-run: would mark the run failed")
            return 1
        with db.transaction(conn, False):
            runs.fail_run(conn, run_id, message)
        return 1
    return 0


def _fetch(
    conn: psycopg.Connection,
    client: massive.MassiveSource,
    rd: dates.RunDates,
    fetch_fx: FxFetcher,
) -> Fetched:
    """All reads and network fetches. Writes nothing; leaves no transaction open."""
    try:
        last = bars.latest_bar_date(conn, universe.BENCHMARK)
        if last is None:
            raise NightlyError(f"no {universe.BENCHMARK} bars stored; run `backfill` first")
        missing = dates.sessions(dates.next_session(last), rd.data_date) if last < rd.data_date else []
        if len(missing) > MAX_GAP:
            raise NightlyError(
                f"gap of {len(missing)} sessions ({missing[0]}..{missing[-1]}) exceeds {MAX_GAP}; "
                f"run `backfill --start {missing[0]}` first"
            )
        wanted = {d: set(universe.symbols_for_bars(conn, d)) for d in missing}
    finally:
        conn.rollback()

    for d in missing:
        if wanted[d] <= {universe.BENCHMARK}:
            raise NightlyError(f"universe is empty for {d}; run `universe refresh` first")

    if missing:
        log.info("fetching %d session(s): %s..%s", len(missing), missing[0], missing[-1])
    else:
        log.info("bars already reach %s; no sessions to fetch", rd.data_date)

    bars_by_session: dict[date, list[Bar]] = {}
    first_opens: dict[str, Decimal] = {}
    fetched_splits: list[Split] = []
    for d in missing:
        got = client.grouped(d)
        want = wanted[d]
        if universe.BENCHMARK not in got:
            raise NightlyError(f"{universe.BENCHMARK} missing from grouped daily for {d}")
        present = sorted(want & got.keys())
        absent = sorted(want - got.keys())
        coverage = len(present) / len(want)
        if coverage < MIN_COVERAGE:
            raise NightlyError(
                f"grouped daily for {d} covers {len(present)}/{len(want)} universe symbols "
                f"({coverage:.1%}) < {MIN_COVERAGE:.0%}"
            )
        if absent:
            log.warning(
                "%s: %d universe symbol(s) absent from grouped daily (renamed, delisted or halted?): %s",
                d,
                len(absent),
                ", ".join(absent),
            )
        session_bars = [got[s] for s in present]
        bars_by_session[d] = session_bars
        for b in session_bars:
            first_opens.setdefault(b.symbol, b.open)
        fetched_splits.extend(client.splits(d))

    fx_row = fetch_fx()

    split_symbols = {s.symbol for s in fetched_splits}
    tracked = set().union(*wanted.values()) if wanted else set()
    try:
        with_bars = splits.symbols_with_bars(conn, split_symbols - tracked)
    finally:
        conn.rollback()
    relevant = [s for s in fetched_splits if s.symbol in tracked or s.symbol in with_bars]
    if fetched_splits:
        log.info("splits: %d fetched, %d relevant", len(fetched_splits), len(relevant))

    return Fetched(
        sessions=list(missing),
        bars_by_session=bars_by_session,
        splits=relevant,
        first_opens=first_opens,
        fx_row=fx_row,
    )


def _write(
    conn: psycopg.Connection,
    rd: dates.RunDates,
    f: Fetched,
    run_id: int,
    dry_run: bool,
) -> None:
    """The single data transaction. Under dry-run it runs fully and is rolled back."""
    with db.transaction(conn, dry_run):
        if dry_run:
            # The run row from the dry start was rolled back; recreate it inside this
            # (also rolled back) transaction so finish_run exercises a real row.
            dry_id = runs.start_run(conn, rd)
            if dry_id is not None:
                run_id = dry_id
        outcomes = splits.apply_splits(conn, f.splits, f.first_opens)
        changed = 0
        for d in f.sessions:
            changed += bars.upsert_bars(conn, f.bars_by_session[d])
        fx_changed = fx.upsert_fx(conn, [f.fx_row])
        runs.finish_run(conn, run_id)
        total = sum(len(f.bars_by_session[d]) for d in f.sessions)
        applied = sum(1 for o in outcomes if o.applied)
        log.info(
            "%s %d bars (%d changed) over %d session(s), %d split(s) recorded (%d applied), "
            "fx %s=%s (%d changed), run %s success",
            "dry-run: would write" if dry_run else "wrote",
            total,
            changed,
            len(f.sessions),
            sum(1 for o in outcomes if o.recorded),
            applied,
            f.fx_row[0],
            f.fx_row[1],
            fx_changed,
            run_id,
        )
    if dry_run:
        log.info("dry-run: rolled back; nothing written")
```
**Impact:** New command, which `python -m seer_engine --help` lists. It is the only writer of
nightly bars, and the only caller of `runs.start_run`/`finish_run`/`fail_run`.

### Step 4: Massive client tests
**File:** `engine/tests/test_massive.py:1` (new)
**Code:**
```python
import logging
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import massive
from seer_engine.massive import Client, MassiveError

KEY = "sekret-key-123"
D = date(2026, 10, 1)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, params=None, **kwargs):
        self.requests.append((url, dict(params or {}), kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


GROUPED_OK = {
    "status": "OK",
    "adjusted": True,
    "resultsCount": 3,
    "results": [
        {"T": "SPY", "o": 764.36, "h": 765.65, "l": 758.7901, "c": 763.99, "v": 47708058.813089,
         "vw": 762.1, "t": 1790798400000, "n": 512345},
        {"T": "BRK.B", "o": 480.1, "h": 482.0, "l": 478.5, "c": 481.25, "v": 3100200.0},
        {"T": "BAD", "o": 1.0},
    ],
}


def make_client(http_, clock=None):
    clock = clock or FakeClock()
    return Client(KEY, get_json=http_, clock=clock.now, sleep=clock.sleep), clock


def test_grouped_parses_bars_and_keeps_dot_tickers():
    http_ = FakeHttp([GROUPED_OK])
    c, _ = make_client(http_)
    out = c.grouped(D)
    assert set(out) == {"SPY", "BRK.B"}
    spy = out["SPY"]
    assert spy.date == D
    assert spy.open == Decimal("764.36")
    assert spy.low == Decimal("758.7901")
    assert spy.close == Decimal("763.99")
    assert isinstance(spy.volume, int)
    assert abs(spy.volume - 47708058) <= 1


def test_grouped_request_shape_and_retry_settings():
    http_ = FakeHttp([GROUPED_OK])
    c, _ = make_client(http_)
    c.grouped(D)
    url, params, kwargs = http_.requests[0]
    assert url == "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/2026-10-01"
    assert params == {"adjusted": "true", "apiKey": KEY}
    assert kwargs == {"retries": massive.RETRIES, "backoff": massive.BACKOFF}
    assert massive.BACKOFF >= massive.MIN_INTERVAL


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "OK", "adjusted": True, "resultsCount": 0},
        {"status": "OK", "adjusted": True, "resultsCount": 0, "results": []},
        {"status": "NOT_AUTHORIZED", "message": "plan doesn't include this data timeframe"},
        {"status": "OK", "adjusted": False, "results": GROUPED_OK["results"]},
    ],
)
def test_grouped_unusable_responses_raise(payload):
    c, _ = make_client(FakeHttp([payload]))
    with pytest.raises(MassiveError):
        c.grouped(D)


def test_grouped_accepts_delayed_status():
    c, _ = make_client(FakeHttp([{**GROUPED_OK, "status": "DELAYED"}]))
    assert "SPY" in c.grouped(D)


def test_calls_are_spaced_by_min_interval():
    clock = FakeClock()
    c, _ = make_client(FakeHttp([GROUPED_OK, GROUPED_OK, GROUPED_OK]), clock)
    c.grouped(D)
    c.grouped(D)
    clock.t += 20.0
    c.grouped(D)
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]
    assert c.calls == 3


def test_http_error_propagates_and_still_counts_for_spacing():
    clock = FakeClock()
    c, _ = make_client(FakeHttp([RuntimeError("HTTP 503"), GROUPED_OK]), clock)
    with pytest.raises(RuntimeError):
        c.grouped(D)
    c.grouped(D)
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]


def test_splits_parses_and_follows_next_url():
    page1 = {
        "status": "OK",
        "results": [{"ticker": "NVDA", "execution_date": "2024-06-10", "split_from": 1, "split_to": 10}],
        "next_url": "https://api.massive.com/v3/reference/splits?cursor=abc",
    }
    page2 = {
        "status": "OK",
        "results": [
            {"ticker": "XYZ", "execution_date": "2024-06-10", "split_from": 32, "split_to": 1},
            {"ticker": "BROKEN", "execution_date": "2024-06-10", "split_from": 0, "split_to": 1},
            {"ticker": "OTHER", "execution_date": "2024-06-11", "split_from": 1, "split_to": 2},
        ],
    }
    http_ = FakeHttp([page1, page2])
    c, clock = make_client(http_)
    out = c.splits(date(2024, 6, 10))
    assert [(s.symbol, s.split_from, s.split_to) for s in out] == [
        ("NVDA", Decimal("1"), Decimal("10")),
        ("XYZ", Decimal("32"), Decimal("1")),
    ]
    assert out[0].factor == Decimal(10)
    assert http_.requests[0][1] == {"execution_date": "2024-06-10", "limit": 1000, "apiKey": KEY}
    assert http_.requests[1][0] == "https://api.massive.com/v3/reference/splits?cursor=abc"
    assert http_.requests[1][1] == {"apiKey": KEY}
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]


def test_key_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    c, _ = make_client(FakeHttp([GROUPED_OK, {"status": "OK", "results": []}]))
    c.grouped(D)
    c.splits(D)
    assert KEY not in caplog.text
    assert "massive GET" in caplog.text


def test_empty_key_rejected():
    with pytest.raises(ValueError):
        Client("")
```

### Step 5: Split tests
**File:** `engine/tests/test_splits.py:1` (new)
**Code:**
```python
from datetime import date
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, db, splits
from seer_engine.splits import Split, should_apply


# ---- heuristic (pure) ----

def test_forward_split_unadjusted_history_applies():
    assert should_apply(Decimal("1200.00"), Decimal("121.00"), Decimal(10)) is True


def test_reverse_split_unadjusted_history_applies():
    assert should_apply(Decimal("0.50"), Decimal("16.20"), Decimal(1) / Decimal(32)) is True


def test_forward_split_already_adjusted_history_not_applied():
    assert should_apply(Decimal("120.00"), Decimal("121.00"), Decimal(10)) is False


def test_reverse_split_already_adjusted_history_not_applied():
    assert should_apply(Decimal("16.00"), Decimal("16.20"), Decimal(1) / Decimal(32)) is False


def test_large_overnight_gap_still_resolves_to_nearest_explanation():
    # 2:1 split plus a -20% gap: unadjusted 100 -> 40 open. ln(100/80)=0.22 < ln(100/40)=0.92
    assert should_apply(100, 40, 2) is True


def test_tiny_factor_is_ambiguous_and_applies_by_construction():
    # 21:20 stock dividend: a 5% factor is inside normal overnight noise -> always apply
    assert should_apply(Decimal("100"), Decimal("95.3"), Decimal(21) / Decimal(20)) is True
    assert should_apply(Decimal("100"), Decimal("104.0"), Decimal(21) / Decimal(20)) is True


def test_factor_one_never_applies():
    assert should_apply(100, 100, 1) is False


@pytest.mark.parametrize("args", [(0, 1, 2), (1, 0, 2), (1, 1, 0), (-1, 1, 2)])
def test_non_positive_inputs_raise(args):
    with pytest.raises(ValueError):
        should_apply(*args)


def test_split_from_massive():
    s = Split.from_massive({"ticker": "NVDA", "execution_date": "2024-06-10", "split_from": 1, "split_to": 10}, date(2000, 1, 1))
    assert s == Split("NVDA", date(2024, 6, 10), Decimal("1"), Decimal("10"))
    assert s.factor == Decimal(10)
    with pytest.raises(ValueError):
        Split.from_massive({"ticker": "X", "split_from": 0, "split_to": 1}, date(2024, 1, 2))
    with pytest.raises(KeyError):
        Split.from_massive({"split_from": 1, "split_to": 2}, date(2024, 1, 2))


# ---- DB application (needs PG_TEST_URL) ----

D0 = date(2026, 9, 30)
D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)


def seed(conn, rows):
    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(*r) for r in rows])


def bar(conn, symbol, d):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT open, high, low, close, volume FROM bars WHERE symbol=%s AND date=%s", (symbol, d))
        row = cur.fetchone()
    conn.rollback()
    return row


def recorded(conn):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT symbol, execution_date, split_from, split_to, applied FROM split_adjustments ORDER BY 1, 2")
        rows = cur.fetchall()
    conn.rollback()
    return rows


def apply(conn, items, first_opens):
    with db.transaction(conn, False):
        return splits.apply_splits(conn, items, first_opens)


NVDA_SPLIT = Split("NVDA", D2, Decimal(1), Decimal(10))


def test_split_applies_once_across_two_calls(pg):
    seed(pg, [("NVDA", D0, 1190, 1210, 1180, 1200, 1_000_000), ("NVDA", D1, 1200, 1220, 1190, 1210, 2_000_000)])
    first = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.recorded, o.applied, o.rows) for o in first] == [(True, True, 2)]
    assert bar(pg, "NVDA", D1) == (Decimal("120.0000"), Decimal("122.0000"), Decimal("119.0000"), Decimal("121.0000"), 20_000_000)
    second = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.recorded, o.applied, o.reason) for o in second] == [(False, False, "already recorded")]
    assert bar(pg, "NVDA", D1)[3] == Decimal("121.0000")
    assert recorded(pg) == [("NVDA", D2, Decimal(1), Decimal(10), True)]


def test_already_adjusted_history_recorded_not_applied(pg):
    seed(pg, [("NVDA", D1, 120, 122, 119, 121, 20_000_000)])
    out = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121.5")})
    assert [(o.recorded, o.applied) for o in out] == [(True, False)]
    assert bar(pg, "NVDA", D1)[3] == Decimal("121.0000")
    assert recorded(pg)[0][4] is False


def test_stored_bar_on_execution_date_means_already_adjusted(pg):
    # e.g. a backfill fetched after the split: unadjusted-looking numbers are not trusted over dates
    seed(pg, [("NVDA", D1, 1200, 1200, 1200, 1200, 1), ("NVDA", D2, 121, 121, 121, 121, 1)])
    out = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert out[0].applied is False
    assert bar(pg, "NVDA", D1)[3] == Decimal("1200.0000")


def test_symbol_without_bars_recorded_not_applied(pg):
    out = apply(pg, [Split("NEW", D2, Decimal(1), Decimal(2))], {"NEW": Decimal("50")})
    assert [(o.recorded, o.applied, o.reason) for o in out] == [(True, False, "no stored bars")]
    assert recorded(pg) == [("NEW", D2, Decimal(1), Decimal(2), False)]


def test_reverse_split_and_rounding(pg):
    seed(pg, [("XYZ", D1, Decimal("0.5"), Decimal("0.51"), Decimal("0.49"), Decimal("0.5"), 3_200_001)])
    out = apply(pg, [Split("XYZ", D2, Decimal(32), Decimal(1))], {"XYZ": Decimal("16.2")})
    assert out[0].applied is True
    o, h, l, c, v = bar(pg, "XYZ", D1)
    assert (o, h, l, c) == (Decimal("16.0000"), Decimal("16.3200"), Decimal("15.6800"), Decimal("16.0000"))
    assert v == 100_000  # 3_200_001 / 32 = 100000.03 -> 100000


def test_three_for_two_rounds_to_4dp(pg):
    seed(pg, [("ABC", D1, 100, 100, 100, 100, 1001)])
    apply(pg, [Split("ABC", D2, Decimal(2), Decimal(3))], {"ABC": Decimal("66.5")})
    o, _, _, c, v = bar(pg, "ABC", D1)
    assert (o, c) == (Decimal("66.6667"), Decimal("66.6667"))
    assert v == 1502  # 1501.5 rounds half away from zero


def test_chained_splits_in_one_batch_each_apply(pg):
    seed(pg, [("CH", D0, 100, 100, 100, 100, 1000)])
    s1 = Split("CH", D1, Decimal(1), Decimal(2))
    s2 = Split("CH", D2, Decimal(1), Decimal(2))
    out = apply(pg, [s2, s1], {"CH": Decimal("25")})  # fetched open already reflects both
    assert [(o.split.execution_date, o.applied) for o in out] == [(D1, True), (D2, True)]
    o, _, _, c, v = bar(pg, "CH", D0)
    assert c == Decimal("25.0000")
    assert v == 4000


def test_symbols_with_bars(pg):
    seed(pg, [("AAA", D1, 1, 1, 1, 1, 1)])
    assert splits.symbols_with_bars(pg, ["AAA", "BBB"]) == {"AAA"}
    assert splits.symbols_with_bars(pg, []) == set()
    pg.rollback()
```

### Step 6: Nightly end-to-end tests
**File:** `engine/tests/test_nightly.py:1` (new)
**Code:**
```python
import argparse
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, db, universe
from seer_engine.commands import nightly
from seer_engine.massive import MassiveError
from seer_engine.splits import Split

UTC = timezone.utc
FRI_NIGHT = datetime(2026, 10, 2, 23, 0, tzinfo=UTC)
D0 = date(2026, 9, 29)
D_WED = date(2026, 9, 30)
D_THU = date(2026, 10, 1)
D_FRI = date(2026, 10, 2)
MON_AFTER = date(2026, 10, 5)

UNIVERSE = ["SPY", "AAPL", "MSFT", "NVDA", "BRK.B", "AMZN", "GOOGL", "META", "TSLA", "AVGO"]
FX = (D_FRI, Decimal("17950.0000"))


def fx_ok():
    return FX


class FakeMassive:
    """grouped_data: {date: {symbol: (o, h, l, c, v)}}; splits_data: {date: [Split]}."""

    def __init__(self, grouped_data=None, splits_data=None, fail=None):
        self.grouped_data = grouped_data or {}
        self.splits_data = splits_data or {}
        self.fail = fail
        self.calls = []

    def grouped(self, d):
        self.calls.append(("grouped", d))
        if self.fail is not None:
            raise self.fail
        rows = self.grouped_data.get(d)
        if not rows:
            raise MassiveError(f"grouped daily {d}: no results (not published yet?)")
        return {s: bars.make_bar(s, d, *v) for s, v in rows.items()}

    def splits(self, d):
        self.calls.append(("splits", d))
        return list(self.splits_data.get(d, []))


def day(symbols=UNIVERSE, price=100.0, extra=()):
    rows = {s: (price, price + 1, price - 1, price + 0.5, 1_000_000.4) for s in symbols}
    rows["ZZZZ"] = (5.0, 5.0, 5.0, 5.0, 10.0)  # non-universe ticker: must not be stored
    for s, v in extra:
        rows[s] = v
    return rows


@pytest.fixture
def fixed_universe(monkeypatch):
    members = set(UNIVERSE)
    monkeypatch.setattr(universe, "symbols_for_bars", lambda conn, d, grace_days=30: set(members))
    return members


def seed(conn, *days, symbols=UNIVERSE):
    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(s, d, 99, 101, 98, 100, 1000) for d in days for s in symbols])


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.rollback()
    return rows


def real_runs(conn):
    return q(conn, "SELECT id, status, data_date, session_date, error FROM runs WHERE NOT is_demo ORDER BY id")


def bars_on(conn, d):
    return q(conn, "SELECT symbol FROM bars WHERE date = %s ORDER BY symbol", (d,))


CHECKSUM_TABLES = {
    "bars": "x.symbol, x.date",
    "fx_rates": "x.date",
    "runs": "x.id",
    "split_adjustments": "x.symbol, x.execution_date",
}


def checksums(conn):
    out = {}
    for table, order in CHECKSUM_TABLES.items():
        out[table] = q(
            conn,
            f"SELECT count(*), coalesce(md5(string_agg(x::text, '|' ORDER BY {order})), '') FROM {table} x",
        )[0]
    return out


def go(conn, client, now=FRI_NIGHT, dry_run=False):
    return nightly.execute(conn, now=now, client=client, dry_run=dry_run, fetch_fx=fx_ok, secret="sekret")


def test_friday_run_writes_bars_fx_and_success_run(pg, fixed_universe):
    seed(pg, D_THU)
    fake = FakeMassive({D_FRI: day()})
    assert go(pg, fake) == 0
    [(run_id, status, data_date, session_date, error)] = real_runs(pg)
    assert (status, data_date, session_date, error) == ("success", D_FRI, MON_AFTER, None)
    assert sorted(r[0] for r in bars_on(pg, D_FRI)) == sorted(UNIVERSE)  # ZZZZ not stored
    assert q(pg, "SELECT date, usd_idr FROM fx_rates") == [FX]
    assert fake.calls == [("grouped", D_FRI), ("splits", D_FRI)]


def test_same_now_twice_leaves_identical_tables(pg, fixed_universe):
    seed(pg, D_THU)
    assert go(pg, FakeMassive({D_FRI: day()})) == 0
    before = checksums(pg)
    second = FakeMassive({D_FRI: day(price=200.0)})
    assert go(pg, second) == 0
    assert checksums(pg) == before
    assert second.calls == []


def test_massive_failure_marks_run_failed_and_writes_no_bars_then_rerun_reuses_row(pg, fixed_universe):
    seed(pg, D_THU)
    assert go(pg, FakeMassive(fail=RuntimeError("boom apiKey=sekret"))) == 1
    [(run_id, status, _, session_date, error)] = real_runs(pg)
    assert status == "failed" and session_date == MON_AFTER
    assert "boom" in error and "sekret" not in error
    assert bars_on(pg, D_FRI) == []
    assert q(pg, "SELECT count(*) FROM fx_rates") == [(0,)]

    assert go(pg, FakeMassive({D_FRI: day()})) == 0
    [(run_id2, status2, _, _, _)] = real_runs(pg)
    assert (run_id2, status2) == (run_id, "success")
    assert len(bars_on(pg, D_FRI)) == len(UNIVERSE)


def test_empty_grouped_marks_run_failed(pg, fixed_universe):
    seed(pg, D_THU)
    assert go(pg, FakeMassive({})) == 1
    assert real_runs(pg)[0][1] == "failed"
    assert "no results" in real_runs(pg)[0][4]
    assert bars_on(pg, D_FRI) == []


def test_fx_failure_marks_run_failed_and_writes_no_bars(pg, fixed_universe):
    seed(pg, D_THU)

    def fx_down():
        raise RuntimeError("frankfurter down")

    rc = nightly.execute(pg, now=FRI_NIGHT, client=FakeMassive({D_FRI: day()}), fetch_fx=fx_down)
    assert rc == 1
    assert real_runs(pg)[0][1] == "failed"
    assert bars_on(pg, D_FRI) == []


def test_gap_of_three_sessions_fetched_in_order(pg, fixed_universe):
    seed(pg, D0)
    fake = FakeMassive({D_WED: day(), D_THU: day(), D_FRI: day()})
    assert go(pg, fake) == 0
    assert [c for c in fake.calls if c[0] == "grouped"] == [("grouped", D_WED), ("grouped", D_THU), ("grouped", D_FRI)]
    for d in (D_WED, D_THU, D_FRI):
        assert len(bars_on(pg, d)) == len(UNIVERSE)


def test_gap_over_thirty_sessions_fails_without_fetching(pg, fixed_universe):
    seed(pg, date(2026, 8, 3))
    fake = FakeMassive({D_FRI: day()})
    assert go(pg, fake) == 1
    assert "gap" in real_runs(pg)[0][4]
    assert fake.calls == []


def test_no_spy_bars_fails(pg, fixed_universe):
    assert go(pg, FakeMassive({D_FRI: day()})) == 1
    assert "backfill" in real_runs(pg)[0][4]


def test_spy_missing_from_grouped_fails(pg, fixed_universe):
    seed(pg, D_THU)
    rows = day()
    del rows["SPY"]
    assert go(pg, FakeMassive({D_FRI: rows})) == 1
    assert "SPY missing" in real_runs(pg)[0][4]
    assert bars_on(pg, D_FRI) == []


def test_coverage_below_90_percent_fails(pg, fixed_universe):
    seed(pg, D_THU)
    rows = day([s for s in UNIVERSE if s not in ("TSLA", "AVGO")])  # 8/10
    assert go(pg, FakeMassive({D_FRI: rows})) == 1
    assert "covers 8/10" in real_runs(pg)[0][4]
    assert bars_on(pg, D_FRI) == []


def test_one_absent_symbol_is_a_warning_not_a_failure(pg, fixed_universe, caplog):
    seed(pg, D_THU)
    rows = day([s for s in UNIVERSE if s != "AVGO"])  # 9/10 = 90%
    caplog.set_level(logging.WARNING)
    assert go(pg, FakeMassive({D_FRI: rows})) == 0
    assert "AVGO" in caplog.text
    assert len(bars_on(pg, D_FRI)) == len(UNIVERSE) - 1


def test_empty_universe_fails(pg, monkeypatch):
    monkeypatch.setattr(universe, "symbols_for_bars", lambda conn, d, grace_days=30: {"SPY"})
    seed(pg, D_THU, symbols=["SPY"])
    assert go(pg, FakeMassive({D_FRI: day()})) == 1
    assert "universe refresh" in real_runs(pg)[0][4]


def test_dry_run_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    before = checksums(pg)
    fake = FakeMassive({D_FRI: day()}, {D_FRI: [Split("NVDA", D_FRI, Decimal(1), Decimal(10))]})
    assert go(pg, fake, dry_run=True) == 0
    assert checksums(pg) == before
    assert real_runs(pg) == []
    assert fake.calls == [("grouped", D_FRI), ("splits", D_FRI)]


def test_dry_run_failure_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    before = checksums(pg)
    assert go(pg, FakeMassive(fail=RuntimeError("boom")), dry_run=True) == 1
    assert checksums(pg) == before


def test_split_applied_to_history_once(pg, fixed_universe):
    seed(pg, D_THU, symbols=[s for s in UNIVERSE if s != "NVDA"])
    with db.transaction(pg, False):
        bars.upsert_bars(pg, [bars.make_bar("NVDA", D_THU, 1190, 1210, 1180, 1200, 1_000_000)])
    split = Split("NVDA", D_FRI, Decimal(1), Decimal(10))
    fake = FakeMassive({D_FRI: day(extra=[("NVDA", (121.0, 123.0, 119.0, 122.0, 9_000_000.0))])}, {D_FRI: [split]})
    assert go(pg, fake) == 0
    assert q(pg, "SELECT close, volume FROM bars WHERE symbol='NVDA' AND date=%s", (D_THU,)) == [(Decimal("120.0000"), 10_000_000)]
    assert q(pg, "SELECT close FROM bars WHERE symbol='NVDA' AND date=%s", (D_FRI,)) == [(Decimal("122.0000"),)]
    assert q(pg, "SELECT symbol, applied FROM split_adjustments") == [("NVDA", True)]
    before = checksums(pg)
    assert go(pg, fake) == 0  # same session again: no-op, split not re-applied
    assert checksums(pg) == before


def test_split_inside_multi_session_gap_does_not_touch_fetched_bars(pg, fixed_universe):
    others = [s for s in UNIVERSE if s != "NVDA"]
    seed(pg, D0, symbols=others)
    with db.transaction(pg, False):
        bars.upsert_bars(pg, [bars.make_bar("NVDA", D0, 1200, 1200, 1200, 1200, 1000)])
    # Massive adjusted=true is adjusted as of fetch time: Wed's NVDA bar is already post-split.
    nvda = ("NVDA", (120.0, 121.0, 119.0, 120.5, 10_000.0))
    fake = FakeMassive(
        {D_WED: day(extra=[nvda]), D_THU: day(extra=[nvda]), D_FRI: day(extra=[nvda])},
        {D_THU: [Split("NVDA", D_THU, Decimal(1), Decimal(10))]},
    )
    assert go(pg, fake) == 0
    assert q(pg, "SELECT close FROM bars WHERE symbol='NVDA' AND date=%s", (D0,)) == [(Decimal("120.0000"),)]
    assert q(pg, "SELECT close FROM bars WHERE symbol='NVDA' AND date=%s", (D_WED,)) == [(Decimal("120.5000"),)]


def test_untracked_split_is_ignored(pg, fixed_universe):
    seed(pg, D_THU)
    fake = FakeMassive({D_FRI: day()}, {D_FRI: [Split("ZZZZ", D_FRI, Decimal(1), Decimal(2))]})
    assert go(pg, fake) == 0
    assert q(pg, "SELECT count(*) FROM split_adjustments") == [(0,)]


def test_labor_day_monday_run_is_a_noop_after_friday(pg, fixed_universe):
    fri = date(2026, 9, 4)
    seed(pg, date(2026, 9, 3))
    fake = FakeMassive({fri: day()})
    assert go(pg, fake, now=datetime(2026, 9, 4, 23, 0, tzinfo=UTC)) == 0
    [(_, status, data_date, session_date, _)] = real_runs(pg)
    assert (status, data_date, session_date) == ("success", fri, date(2026, 9, 8))
    before = checksums(pg)
    calls = list(fake.calls)
    assert go(pg, fake, now=datetime(2026, 9, 7, 23, 0, tzinfo=UTC)) == 0
    assert checksums(pg) == before
    assert fake.calls == calls


def test_bars_already_current_still_records_fx_and_finishes(pg, fixed_universe):
    seed(pg, D_FRI)  # e.g. a backfill already reached data_date
    fake = FakeMassive({})
    assert go(pg, fake) == 0
    assert fake.calls == []
    assert real_runs(pg)[0][1] == "success"
    assert q(pg, "SELECT date FROM fx_rates") == [(D_FRI,)]


# ---- CLI surface ----

def test_parse_now_accepts_z_and_naive_as_utc():
    assert nightly._parse_now("2026-10-02T23:00:00Z") == FRI_NIGHT
    assert nightly._parse_now("2026-10-02T23:00:00") == FRI_NIGHT
    assert nightly._parse_now("2026-10-03T06:00:00+07:00") == FRI_NIGHT
    with pytest.raises(argparse.ArgumentTypeError):
        nightly._parse_now("friday")


def test_add_arguments_and_run_wiring(monkeypatch):
    p = argparse.ArgumentParser()
    nightly.add_arguments(p)
    args = p.parse_args(["--now", "2026-10-02T23:00:00Z"])
    args.dry_run = True

    class DummyConn:
        closed = False

        def close(self):
            self.closed = True

    conn = DummyConn()
    seen = {}

    def fake_execute(c, **kw):
        seen.update(kw, conn=c)
        return 0

    monkeypatch.setattr(nightly.config, "require", lambda name: "sekret")
    monkeypatch.setattr(nightly.db, "connect", lambda: conn)
    monkeypatch.setattr(nightly, "execute", fake_execute)
    assert nightly.run(args) == 0
    assert seen["conn"] is conn and conn.closed
    assert seen["now"] == FRI_NIGHT and seen["dry_run"] is True and seen["secret"] == "sekret"


def test_run_without_key_exits_2(monkeypatch):
    def missing(name):
        raise nightly.config.ConfigError(f"{name} is not set")

    monkeypatch.setattr(nightly.config, "require", missing)
    args = argparse.Namespace(now=None, dry_run=False)
    assert nightly.run(args) == 2
```

## Verification

**Build:** `cd engine && .venv/bin/python -c "import seer_engine.massive, seer_engine.splits, seer_engine.commands.nightly"`
and `engine/.venv/bin/python -m seer_engine --help`, which must list `nightly`.
**Tests:**
- Pure tests: `engine/.venv/bin/pytest engine/tests/test_massive.py engine/tests/test_splits.py engine/tests/test_nightly.py -q`. Without `PG_TEST_URL` the DB tests skip.
- DB tests, using phase 1's test database (`docker start seer-pg`, see phase 1 Verification): `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs`. That runs the full suite, which must stay green (invariant 1).

**Manual check:** none against Neon in this phase (migration 002 is not on Neon until phase 5).
The live dry run (`python -m seer_engine --dry-run -v nightly`, real Massive + Neon, writes
nothing, no API key in the output) is executed by **phase 5 Step 13** after the live backfill.

**Exit criteria:**
- `nightly` is discovered by the CLI, and every test in the three new files passes against `PG_TEST_URL`.
- The checksum test proves a same-`now` re-run leaves `bars`, `fx_rates`, `runs` and `split_adjustments` identical.
- The failure tests prove a `failed` run with an error and zero bars for D.
- The dry-run test proves zero table changes and no `runs` row.

## Assumptions (about Phase 1, which is planned in parallel)

1. The fixture `pg` yields a `psycopg.Connection` on a fresh, migrated schema. If Phase 1 names
   it differently, or yields a URL, the reconciler renames the fixture parameter in
   `test_splits.py` and `test_nightly.py`.
2. `runs.start_run`, `finish_run`, `fail_run`, `bars.upsert_bars` and `fx.upsert_fx` do not
   commit. Transaction control belongs to `db.transaction`.
3. `db.transaction(conn, dry_run)` re-raises the exception after rolling back, and is safe to use
   when no transaction is open.
4. `runs.start_run` reuses a `failed` row for the same `session_date` (same id). It also clears
   `error` and sets `status='running'`, or `finish_run` clears `error`. The tests assert only on
   status and id after a reuse. **Reconciled:** phase 1's `start_run` is one
   `INSERT … ON CONFLICT (session_date) WHERE NOT is_demo DO UPDATE … WHERE runs.status <> 'success'`,
   so it reuses both a `failed` row and a stale `running` row (same id), clears `error` and
   `finished_at`, and refreshes `data_date`.

All nine assumptions were checked against phase 1's plan by the reconciler and hold as written
(`db.transaction` re-raises after rollback; `http.get_json(url, params, *, retries, backoff,
timeout)` retries 429/5xx and redacts `apiKey=` in every error URL; `make_bar` accepts floats via
their shortest repr; `split_from`/`split_to` are `numeric`; the fixture is named `pg`).
5. `http.redact` accepts any string and masks `apiKey=<value>` inside it.
6. `http.get_json` retries HTTP 429/5xx with backoff when called with `retries`/`backoff`, and
   raises after the last attempt.
7. `bars.make_bar` accepts Python floats (Massive JSON) and ints.
8. `split_adjustments.split_from` and `split_to` are `numeric`. Integer would truncate 3-for-2
   splits.
9. Phase 1's `db.connect()` may set any `row_factory`. Every cursor in this phase passes
   `row_factory=tuple_row` explicitly, so the code works with either.

## Handoffs

- **Phase 1** (R4, reconciled, no action left): `runs.start_run` already reuses a stale `running`
  row for the same `session_date` (its `DO UPDATE` fires for any status other than `success`), so
  a process killed mid-fetch (an Actions timeout or a SIGKILL) is recovered by the next run.
- **Phase 5** (R3): the `nightly.yml` job timeout must allow for the rate limit. A normal night
  makes 2 Massive calls (about 13 s). A 30-session catch-up makes 60 calls, about 12.5 min plus
  retries, so set `timeout-minutes: 30`. The job passes `MASSIVE_API_KEY` and
  `DATABASE_URL_UNPOOLED` as secrets. `workflow_dispatch` with `dry_run` maps to the global
  `--dry-run` flag, which comes **before** the command: `python -m seer_engine --dry-run nightly`.
  The 01:00 UTC retry slot is safe to run unconditionally, because it is a no-op when 23:00
  succeeded. Exit codes: 0 = success or already-succeeded no-op; 1 = run marked `failed` (or a
  dry-run failure); 2 = `MASSIVE_API_KEY`/`DATABASE_URL_UNPOOLED` missing (no run row written).
- **Phase 5** (R3): the runbook should document the recovery paths. A gap over 30 sessions
  means `backfill --start <first missing>`, and an empty universe means `universe refresh`. Both
  appear verbatim in the failed run's `error`.
- **Phase 3** (R1/R4): this phase's split guard treats a stored bar dated on or after a split's
  execution date as "already adjusted". That holds as long as `backfill` writes yfinance's
  split-adjusted-as-of-fetch prices. If Phase 3 ever writes unadjusted prices, this guard is wrong.

## Risks

- Massive's `adjusted=true` is assumed to mean "adjusted as of fetch time". Design decision 1
  depends on that. If it meant "as of that date", a split inside a multi-session gap would leave
  the in-gap bars before the execution date unadjusted. That only matters for catch-ups of more
  than one session that span a split.
- The DB connection sits open but idle during the fetch loop. That is 13 s on a normal night, and
  up to about 13 min on a 30-session catch-up. Neon's proxy could drop an idle connection on the
  long path. If that happens, the remedy is to reconnect before `_write`. That is not done
  pre-emptively.
- A ticker renamed in Massive but not yet aliased in the universe (Phase 2) shows up as an
  "absent" warning. More than 10 % absent fails the night by design.

## Rollback

Delete the six new files (`git revert` of the phase commit). Nothing else references them until
Phase 5 adds the workflow. Data written by a live `nightly` run is reversed by the plan index's
rollback (`DELETE FROM runs WHERE NOT is_demo; TRUNCATE bars, fx_rates, split_adjustments …`).
