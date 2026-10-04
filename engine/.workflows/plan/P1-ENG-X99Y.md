> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 5. Source: `.workflows/plan/paper-trading-ship/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Dividends and held-symbol bars in `nightly`

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R1 — the paper step (phases 6, 7) needs ex-dividend cash for held book symbols and SPY, and bars for every symbol paper state holds, in the same units as `bars`
**Depends on:** Phase 1 (migration `003`: tables `dividends`, `book_positions`, `book_targets`; `orders` unchanged apart from `mark`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine` (`massive.py`, `dividends.py`, `splits.py`, `universe.py`, `commands/nightly.py`)

---

## Goal

After this phase every nightly run also fetches the Massive cash dividends going ex on each
missing session, keeps the USD `CD` + `SC` rows for tracked symbols (universe ∪ SPY ∪ paper-held),
sums them per (symbol, ex-date) to 6 dp and writes them to `dividends` in the same single
transaction as bars, splits, FX and the run row. An applied split rewrites stored dividends before
its execution date the same way it rewrites bars. Symbols that paper state still holds or has
pending (`orders` pending/open, `book_positions`, `book_targets` for the session or later) are
fetched every night even after they leave the index, without affecting the coverage check.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `seer_engine.dividends` (new module, `engine/src/seer_engine/dividends.py`, impure: imports psycopg):
  - `AMOUNT_QUANTUM = Decimal("0.000001")`, `CASH_TYPES = frozenset({"CD", "SC"})`, `CURRENCY = "USD"`
  - `quantize_amount(value: Decimal) -> Decimal` (half-up, 6 dp)
  - `@dataclass(frozen=True) class Dividend: symbol: str; ex_date: date; amount: Decimal` (USD per share, > 0)
  - `parse_massive(raw: Mapping[str, Any]) -> Dividend | None` (None = valid row that is not a USD cash dividend; raises KeyError/ValueError/TypeError/InvalidOperation when malformed; amount not quantized)
  - `totals(items: Iterable[Dividend]) -> list[Dividend]` (sum per (symbol, ex_date), quantize half-up 6 dp, drop zero, sorted by (symbol, ex_date))
  - `adjust_for_splits(items: Iterable[Dividend], split_items: Iterable[Split]) -> list[Dividend]` (for freshly fetched rows: each split of the same symbol with `execution_date > ex_date`, in date order, applies `quantize(amount * split_from / split_to)`; zero results dropped)
  - `upsert_dividends(conn, items: Iterable[Dividend]) -> int` (insert/update with `IS DISTINCT FROM`; returns rows inserted or changed; ValueError on a duplicate (symbol, ex_date) in the batch or a non-positive amount; does not commit)
- `massive.Client.dividends(self, d: date) -> list[Dividend]` (`massive.py`)
- `massive.MassiveSource.dividends(self, d: date) -> list[Dividend]` (protocol method)
- `universe.paper_symbols(conn, d: date) -> set[str]` (`universe.py`)
- `splits.SplitOutcome.dividend_rows: int = 0` (new trailing field with default)
- `nightly.Fetched.dividends: list[Dividend]` (new field), `nightly.Fetched.held: dict[date, set[str]]` is **not** added (held symbols are folded into `bars_by_session` and the tracked set)

**Signature changes:** none to existing public functions. `splits.apply_splits(conn, items, first_opens)` keeps its signature; when it applies a split it now also rewrites `dividends` (ex_date < execution_date) for that symbol.

**Requires (from earlier phases):**
- Phase 1: `db/migrations/003_paper.sql` creates `dividends (symbol, ex_date, amount numeric(14,6) CHECK (amount > 0), recorded_at timestamptz DEFAULT now(), PRIMARY KEY (symbol, ex_date))`, `book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd, stop_price, take_price, exit_pending)` and `book_targets (strategy_id, session_date, rank, symbol, weight, last_price, …)` exactly as in contract C1. The `pg` test fixture applies every migration, so these tables exist in every DB test.
- Phase 1: `dividends` is **not** in `demo.DEMO_TABLES` (dividends are market data like `bars`, not demo state).

**Leaves alone (owned by others):** `paper/*` (phases 1, 3, 4, 6, 8), `commands/paper*.py` (7, 8), `runs.py` (7), `backtest/*` (closed / phase 6), `.github/workflows/*` (7, 13), `web/*` (10–12), `docs/*`, `engine/package_readme.md` (13), `db/migrations/*` (1), `demo.py` (1).

**Notes for the reconciler / later phases:**
- `Dividend` lives in an impure module (`dividends.py` imports psycopg). Pure cores (`paper/book.py`, `paper/benchmark.py`, `paper/replay.py`) must not import it; phase 6's store converts rows to whatever plain mapping (e.g. `dict[str, Decimal]` per ex-date) the cores take.
- Stored dividend amounts are in the **current** units of `bars` (same as `bars`): rewritten by every applied split, and freshly fetched rows adjusted in memory for splits fetched in the same batch. Phase 6 reads `dividends` by ex-date and gets amounts consistent with the bars it reads.
- `universe.paper_symbols(conn, d)` is available for phase 6/7 to reuse.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/dividends.py` | create | value type, Massive row parsing, sums, gap split adjustment, upsert |
| `engine/src/seer_engine/massive.py` | modify | docstring (l.1), imports (l.17–20), `MassiveSource` (l.38–41), new `Client.dividends` after `splits` (after l.146) |
| `engine/src/seer_engine/splits.py` | modify | `SplitOutcome` (l.67–73) gains `dividend_rows`; new SQL after `_REWRITE` (l.141–149); `apply_splits` (l.152–203) rewrites dividends when applying |
| `engine/src/seer_engine/universe.py` | modify | new `paper_symbols` after `all_symbols` (after l.48) |
| `engine/src/seer_engine/commands/nightly.py` | modify | whole file replaced (docstring l.1–10, `HELP` l.28, imports l.22–24, `Fetched` l.41–47, `_fetch` l.137–214, `_write` l.217–255) |
| `engine/tests/test_dividends.py` | create | pure parsing/sums/adjust tests + PG upsert tests |
| `engine/tests/test_massive.py` | modify | dividends parsing/pagination/status/max-pages tests; `test_key_never_logged` (l.151–157) also calls `dividends` |
| `engine/tests/test_splits.py` | modify | dividend rewrite tests appended after l.161 |
| `engine/tests/test_universe_queries.py` | modify | `paper_symbols` test appended after l.60 |
| `engine/tests/test_nightly.py` | modify | `FakeMassive` gains `dividends`; checksums include `dividends`; call-list asserts at l.119 and l.229; new tests for dividends, held symbols and failures |

## Implementation Steps

### Step 1: New module `dividends.py`
**File:** `engine/src/seer_engine/dividends.py` (new)
**Change:** the value type, parsing of one Massive row, per-key sums, the in-memory split
adjustment for rows fetched in the same batch as a split, and the idempotent upsert.
**Code:**
```python
"""Cash dividends by ex-date: the value type, Massive row parsing, sums, and writes to ``dividends``.

Massive's /v3/reference/dividends returns one row per declared distribution. Seer keeps the USD
cash ones (dividend_type CD = regular cash, SC = special cash) and drops capital-gain
distributions (LT, ST) and other currencies. Rows for the same symbol and ex-date are summed and
quantized half-up to 6 dp, which is what the ``dividends`` table (migration 003) stores.

Units: stored amounts are per share in the same units as ``bars``. ``splits.apply_splits`` rewrites
stored rows before a split's execution date exactly when it rewrites the bars; rows fetched in the
same nightly batch as a later split are adjusted in memory by ``adjust_for_splits`` (Massive's
cash_amount is the declared, unadjusted amount, while grouped-daily bars are adjusted as of fetch
time).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import psycopg

from seer_engine.splits import Split

log = logging.getLogger(__name__)

AMOUNT_QUANTUM = Decimal("0.000001")
CASH_TYPES = frozenset({"CD", "SC"})
CURRENCY = "USD"


def quantize_amount(value: Decimal) -> Decimal:
    """``value`` rounded half-up to 6 decimals (numeric(14,6), like SQL round(x, 6) for x > 0)."""
    return value.quantize(AMOUNT_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Dividend:
    symbol: str
    ex_date: date
    amount: Decimal  # USD per share, > 0


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"cash_amount is not a number: {value!r}") from e
    if not d.is_finite() or d <= 0:
        raise ValueError(f"cash_amount must be positive: {value!r}")
    return d


def parse_massive(raw: Mapping[str, Any]) -> Dividend | None:
    """One Massive dividends row -> Dividend, or None for a valid row Seer does not credit.

    None: dividend_type not CD/SC (LT, ST capital gains, anything new) or currency not USD
    (a missing currency counts as not USD). Raises KeyError/ValueError/TypeError when a row of a
    kept type is malformed. The amount is not quantized here; ``totals`` does that after summing.
    """
    symbol = raw["ticker"]
    if not isinstance(symbol, str) or not symbol:
        raise ValueError(f"bad ticker: {symbol!r}")
    if raw.get("dividend_type") not in CASH_TYPES:
        return None
    if raw.get("currency") != CURRENCY:
        return None
    ex = raw["ex_dividend_date"]
    if not isinstance(ex, str) or not ex:
        raise ValueError(f"bad ex_dividend_date: {ex!r}")
    return Dividend(symbol=symbol, ex_date=date.fromisoformat(ex), amount=_amount(raw["cash_amount"]))


def totals(items: Iterable[Dividend]) -> list[Dividend]:
    """One Dividend per (symbol, ex_date): the exact sum, quantized half-up to 6 dp.

    Sums that quantize to zero are dropped (the table requires amount > 0). Sorted by
    (symbol, ex_date).
    """
    sums: dict[tuple[str, date], Decimal] = defaultdict(Decimal)
    for x in items:
        sums[(x.symbol, x.ex_date)] += x.amount
    out: list[Dividend] = []
    for (symbol, ex_date) in sorted(sums):
        amount = quantize_amount(sums[(symbol, ex_date)])
        if amount <= 0:
            log.warning("dividend %s %s rounds to 0 at 6 dp; dropped", symbol, ex_date.isoformat())
            continue
        out.append(Dividend(symbol, ex_date, amount))
    return out


def adjust_for_splits(items: Iterable[Dividend], split_items: Iterable[Split]) -> list[Dividend]:
    """Put freshly fetched dividends into the units of the bars fetched with them.

    For each dividend, every split of the same symbol whose execution_date is after its ex_date
    is applied in date order as ``quantize(amount * split_from / split_to)``: exactly what
    ``splits.apply_splits`` would do to the row had it been stored before the split. Splits are
    de-duplicated per (symbol, execution_date) like ``apply_splits``. Results that round to 0 are
    dropped. Order of ``items`` is kept.
    """
    by_symbol: dict[str, dict[date, Split]] = defaultdict(dict)
    for s in split_items:
        by_symbol[s.symbol].setdefault(s.execution_date, s)
    out: list[Dividend] = []
    for x in items:
        chain = by_symbol.get(x.symbol, {})
        amount = x.amount
        for execution_date in sorted(chain):
            if x.ex_date < execution_date:
                s = chain[execution_date]
                amount = quantize_amount(amount * s.split_from / s.split_to)
        if amount <= 0:
            log.warning(
                "dividend %s %s rounds to 0 after later splits; dropped", x.symbol, x.ex_date.isoformat()
            )
            continue
        out.append(x if amount == x.amount else Dividend(x.symbol, x.ex_date, amount))
    return out


_UPSERT = """
INSERT INTO dividends AS d (symbol, ex_date, amount)
SELECT t.symbol, t.ex_date, t.amount
FROM unnest(%(symbols)s::text[], %(ex_dates)s::date[], %(amounts)s::numeric[]) AS t(symbol, ex_date, amount)
ON CONFLICT (symbol, ex_date) DO UPDATE
SET amount = EXCLUDED.amount,
    recorded_at = now()
WHERE d.amount IS DISTINCT FROM EXCLUDED.amount
"""


def upsert_dividends(conn: psycopg.Connection, items: Iterable[Dividend]) -> int:
    """Insert new dividends and update changed ones; return how many rows were inserted or changed.

    Amounts are quantized to 6 dp first. Rows identical to the stored row are skipped by the
    ``IS DISTINCT FROM`` guard, so an identical re-run returns 0. Raises ValueError when the batch
    holds the same (symbol, ex_date) twice or an amount that is not positive at 6 dp.
    Does not commit.
    """
    rows = list(items)
    if not rows:
        return 0
    seen: set[tuple[str, date]] = set()
    symbols: list[str] = []
    ex_dates: list[date] = []
    amounts: list[Decimal] = []
    for x in rows:
        key = (x.symbol, x.ex_date)
        if key in seen:
            raise ValueError(f"duplicate dividend in batch: {x.symbol} {x.ex_date.isoformat()}")
        seen.add(key)
        amount = quantize_amount(x.amount)
        if amount <= 0:
            raise ValueError(f"dividend amount must be positive: {x.symbol} {x.ex_date.isoformat()} {x.amount}")
        symbols.append(x.symbol)
        ex_dates.append(x.ex_date)
        amounts.append(amount)
    with conn.cursor() as cur:
        cur.execute(_UPSERT, {"symbols": symbols, "ex_dates": ex_dates, "amounts": amounts})
        return cur.rowcount
```
**Impact:** new module only. `dividends.py` imports `splits` (for the `Split` type); `splits` does
not import `dividends` (it rewrites the table with SQL), so there is no import cycle.

### Step 2: `massive.Client.dividends` and the protocol
**File:** `engine/src/seer_engine/massive.py:1`, `:17–20`, `:38–41`, after `:146`
**Change:**

(a) Module docstring line 1 becomes:
```python
"""Massive (ex-Polygon) REST client: grouped daily bars, stock splits and cash dividends.
```
(the rest of the docstring, lines 2–7, is unchanged).

(b) Imports, lines 17–20, become:
```python
from seer_engine import bars as bars_mod
from seer_engine import http
from seer_engine.bars import Bar
from seer_engine.dividends import Dividend, parse_massive
from seer_engine.splits import Split
```

(c) `MassiveSource`, lines 38–41, becomes:
```python
class MassiveSource(Protocol):
    def grouped(self, d: date) -> dict[str, Bar]: ...

    def splits(self, d: date) -> list[Split]: ...

    def dividends(self, d: date) -> list[Dividend]: ...
```

(d) New method appended to `Client` after `splits` (after line 146, same indentation as `splits`):
```python
    def dividends(self, d: date) -> list[Dividend]:
        """USD cash dividends (types CD and SC) going ex on d, one per Massive row (follows next_url).

        Rows of other types (LT/ST capital gains) or currencies are dropped, rows with another
        ex-date are ignored, and a row repeated under the same Massive id is kept once. Rows are
        not summed here: ``dividends.totals`` sums them per (symbol, ex-date).
        """
        url = f"{self.base_url}/v3/reference/dividends"
        params: dict[str, Any] = {"ex_dividend_date": d.isoformat(), "limit": 1000}
        out: list[Dividend] = []
        seen_ids: set[str] = set()
        dropped = 0
        for _ in range(MAX_PAGES):
            data = self._get(url, params)
            status = data.get("status")
            if status is not None and status not in OK_STATUSES:
                detail = data.get("message") or data.get("error") or ""
                raise MassiveError(f"dividends {d.isoformat()}: status {status!r} {detail}".strip())
            for raw in data.get("results") or []:
                try:
                    dividend = parse_massive(raw)
                except (KeyError, ValueError, TypeError, InvalidOperation) as e:
                    log.warning("dividends %s: skipped malformed row %r (%s)", d.isoformat(), raw, e)
                    continue
                if dividend is None:
                    dropped += 1
                    continue
                if dividend.ex_date != d:
                    continue
                row_id = raw.get("id")
                if isinstance(row_id, str) and row_id:
                    if row_id in seen_ids:
                        log.debug("dividends %s: repeated id %s skipped", d.isoformat(), row_id)
                        continue
                    seen_ids.add(row_id)
                out.append(dividend)
            next_url = data.get("next_url")
            if not next_url:
                log.info("dividends %s: %d cash, %d other dropped", d.isoformat(), len(out), dropped)
                return out
            url, params = next_url, {}
        raise MassiveError(f"dividends {d.isoformat()}: more than {MAX_PAGES} pages")
```
`Any`, `InvalidOperation`, `MAX_PAGES`, `OK_STATUSES`, `MassiveError` and `log` are already in
the module. The key still only travels through `_get`, which logs the path without the query
string; `raw` rows never contain the key.

**Impact:** every `MassiveSource` implementation must now have `dividends`. The only one besides
`Client` is `FakeMassive` in `tests/test_nightly.py` (updated in Step 9). Real nightly runs make one
more Massive call per missing session (see Risks).

### Step 3: Applied splits rewrite earlier dividends
**File:** `engine/src/seer_engine/splits.py:67–73`, `:141–149`, `:152–203`
**Change:**

(a) `SplitOutcome` (lines 67–73) gains a trailing defaulted field:
```python
@dataclass(frozen=True)
class SplitOutcome:
    split: Split
    recorded: bool  # a new split_adjustments row was inserted by this call
    applied: bool  # stored history was rewritten by this call
    reason: str
    rows: int  # bars rows rewritten
    dividend_rows: int = 0  # dividends rows rewritten (ex_date before the execution date)
```

(b) After `_REWRITE` (line 149) add:
```python
# Dividends are stored in the same units as bars: an applied split rewrites every earlier
# ex-date for the symbol (cash per share * split_from / split_to, 6 dp). A row that would round
# to zero is removed first (dividends.amount must stay > 0).
_DROP_TINY_DIVIDENDS = """
DELETE FROM dividends
WHERE symbol = %(symbol)s AND ex_date < %(execution_date)s
  AND round(amount * %(split_from)s / %(split_to)s, 6) = 0
"""

_REWRITE_DIVIDENDS = """
UPDATE dividends SET amount = round(amount * %(split_from)s / %(split_to)s, 6)
WHERE symbol = %(symbol)s AND ex_date < %(execution_date)s
"""
```

(c) The module docstring's first paragraph (lines 3–6) becomes:
```python
"""Stock splits: decide whether stored history still needs a split, and apply it exactly once.

A split with factor f = split_to / split_from (NVDA 2024-06-10: 1 -> 10, f = 10) means every bar
before the execution date must be rewritten: prices * 1/f, volume * f, and every stored cash
dividend with an earlier ex-date * 1/f (6 dp). `split_adjustments` holds one row per
(symbol, execution_date); a split whose row already exists is never applied again, so re-runs and
replays cannot double-adjust.
"""
```

(d) `apply_splits` (lines 152–203) is replaced by:
```python
def apply_splits(
    conn: psycopg.Connection,
    items: Iterable[Split],
    first_opens: Mapping[str, Decimal],
) -> list[SplitOutcome]:
    """Record every split once and rewrite stored history for the ones that need it.

    Stored history is the symbol's bars and its cash dividends with an ex-date before the
    execution date (same units as the bars). Must run inside the caller's write transaction,
    before any bar or dividend fetched in this batch is upserted (fetched bars are adjusted as of
    fetch time and fetched dividends are adjusted by ``dividends.adjust_for_splits``; neither may
    be rewritten again). `first_opens[symbol]` is the open of the earliest fetched bar for that
    symbol in this batch.
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
                dividend_rows = 0
                if apply:
                    cur.execute(_REWRITE, params)
                    rows = cur.rowcount
                    cur.execute(_DROP_TINY_DIVIDENDS, params)
                    if cur.rowcount:
                        log.warning(
                            "split %s %s: %d earlier dividend(s) round to 0 after the split; removed",
                            symbol,
                            split.execution_date,
                            cur.rowcount,
                        )
                    cur.execute(_REWRITE_DIVIDENDS, params)
                    dividend_rows = cur.rowcount
                outcomes.append(SplitOutcome(split, True, apply, reason, rows, dividend_rows))
                log.info(
                    "split %s %s %s:%s %s (%s; %d rows, %d dividends)",
                    symbol,
                    split.execution_date,
                    split.split_from,
                    split.split_to,
                    "applied" if apply else "not applied",
                    reason,
                    rows,
                    dividend_rows,
                )
    return outcomes
```
**Impact:** `apply_splits` now touches `dividends`, which exists from migration `003` (phase 1).
Nothing else calls `apply_splits` besides `nightly._write`. Existing `test_splits` asserts on
`(recorded, applied, rows)` / `reason` only, so they stay green.

### Step 4: `universe.paper_symbols`
**File:** `engine/src/seer_engine/universe.py`, after line 48
**Change:** append:
```python
def paper_symbols(conn: psycopg.Connection, d: date) -> set[str]:
    """Symbols paper state still needs a bar for on session ``d`` (tables from migration 003).

    Bracket orders that are pending or open, every open book position (book strategies and the
    SPY benchmark holding), and book targets decided for session ``d`` or later. ``nightly`` adds
    these to the universe set so a held symbol that left the index keeps getting bars.
    """
    rows = conn.execute(
        """
        SELECT symbol FROM orders WHERE status IN ('pending', 'open')
        UNION
        SELECT symbol FROM book_positions
        UNION
        SELECT symbol FROM book_targets WHERE session_date >= %(d)s
        """,
        {"d": d},
    ).fetchall()
    return {r[0] for r in rows}
```
**Impact:** read-only; needs `book_positions`/`book_targets` (phase 1).

### Step 5: `nightly` — held symbols, dividends, one transaction
**File:** `engine/src/seer_engine/commands/nightly.py` (whole file; changes at l.1–10, l.22–24, l.28, l.41–47, l.137–214, l.217–255)
**Change:** replace the file with the version below. Behavior changes:

1. `_fetch` reads `universe.paper_symbols(conn, d)` for each missing session next to
   `symbols_for_bars` (same read block, rolled back).
2. **Coverage stays over the universe set only.** The ≥ 90% check, the empty-universe check and
   the "absent universe symbols" warning use `symbols_for_bars(d)` exactly as today. Paper-held
   symbols outside that set are stored when Massive has them; when Massive does not, nightly logs
   a separate warning and still succeeds. Why: a held symbol that is delisted, renamed or halted
   has no bar by nature, and the runners' rule (which the paper step mirrors) is to force-close a
   position whose bars ended at its mark. Failing the whole run instead would block bars and the
   paper step for every strategy, every night, with no way to recover except editing paper state.
   Folding paper symbols into the denominator would also let a handful of paper symbols change a
   statistic that is about data-vendor completeness of the index.
3. Only universe ∪ paper symbols are stored: nothing else is added to the wanted set (`ZZZZ` in
   the tests is still dropped).
4. After `splits(d)`, `client.dividends(d)` for each missing session. Dividends are kept for
   `tracked ∪ {SPY}` where `tracked` is the union over sessions of universe and paper symbols,
   summed by `dividends.totals`, then `dividends.adjust_for_splits(…, relevant splits)` so a
   dividend that went ex inside the fetched gap before a split in the same gap is stored in the
   post-split units its bars arrive in.
5. `_write` upserts dividends in the same transaction, **after** `apply_splits` (so the gap rows,
   already adjusted in memory, are not rewritten a second time) and before `finish_run`.
6. Any failure, including `client.dividends` raising, still writes nothing and marks the run failed.

**Code:**
```python
"""nightly: append the newest session(s) from Massive, apply splits, record dividends and USD/IDR, write the run.

Flow (all bars, splits, dividends, FX and the run's success land in ONE transaction):
  1. purge demo data if a demo run exists (own transaction; rolled back under --dry-run)
  2. rd = run_dates(now); start_run -> None means this session already succeeded -> exit 0, no writes
  3. missing sessions = after SPY's latest bar .. rd.data_date (at most MAX_GAP)
  4. fetch everything into memory (grouped daily + splits + cash dividends per session, latest FX);
     no DB writes. Each session's wanted set is the universe set plus the symbols paper state
     holds or has pending; coverage is checked over the universe set only
  5. one transaction: apply splits to pre-existing history (bars and dividends), upsert bars,
     upsert dividends, upsert FX, finish_run
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

from seer_engine import bars, config, dates, db, demo, dividends, fx, http, massive, runs, splits, universe
from seer_engine.bars import Bar
from seer_engine.dividends import Dividend
from seer_engine.splits import Split

log = logging.getLogger(__name__)

HELP = "Fetch the latest session's bars (Massive), splits, cash dividends and USD/IDR; write one runs row"

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
    dividends: list[Dividend]


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
        held = {d: universe.paper_symbols(conn, d) for d in missing}
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
    fetched_dividends: list[Dividend] = []
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
        # Paper-held symbols outside the universe set: stored when present, never counted in the
        # coverage above. Absent ones only warn: the paper step force-closes a position whose
        # bars ended, as the runners do.
        extra = held[d] - want
        extra_present = sorted(extra & got.keys())
        extra_absent = sorted(extra - got.keys())
        if extra_absent:
            log.warning(
                "%s: %d paper-held symbol(s) outside the universe absent from grouped daily: %s",
                d,
                len(extra_absent),
                ", ".join(extra_absent),
            )
        session_bars = [got[s] for s in sorted(set(present) | set(extra_present))]
        bars_by_session[d] = session_bars
        for b in session_bars:
            first_opens.setdefault(b.symbol, b.open)
        fetched_splits.extend(client.splits(d))
        fetched_dividends.extend(client.dividends(d))

    fx_row = fetch_fx()

    split_symbols = {s.symbol for s in fetched_splits}
    tracked = set().union(*wanted.values(), *held.values()) if missing else set()
    try:
        with_bars = splits.symbols_with_bars(conn, split_symbols - tracked)
    finally:
        conn.rollback()
    relevant = [s for s in fetched_splits if s.symbol in tracked or s.symbol in with_bars]
    if fetched_splits:
        log.info("splits: %d fetched, %d relevant", len(fetched_splits), len(relevant))

    dividend_symbols = tracked | {universe.BENCHMARK}
    cash = dividends.adjust_for_splits(
        dividends.totals(x for x in fetched_dividends if x.symbol in dividend_symbols),
        relevant,
    )
    if fetched_dividends:
        log.info("dividends: %d cash row(s) fetched, %d tracked (symbol, ex-date)", len(fetched_dividends), len(cash))

    return Fetched(
        sessions=list(missing),
        bars_by_session=bars_by_session,
        splits=relevant,
        first_opens=first_opens,
        fx_row=fx_row,
        dividends=cash,
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
        # Splits first: they rewrite pre-existing bars and dividends only. The fetched bars and
        # dividends below are already in post-split units and must not be rewritten again.
        outcomes = splits.apply_splits(conn, f.splits, f.first_opens)
        changed = 0
        for d in f.sessions:
            changed += bars.upsert_bars(conn, f.bars_by_session[d])
        dividends_changed = dividends.upsert_dividends(conn, f.dividends)
        fx_changed = fx.upsert_fx(conn, [f.fx_row])
        runs.finish_run(conn, run_id)
        total = sum(len(f.bars_by_session[d]) for d in f.sessions)
        applied = sum(1 for o in outcomes if o.applied)
        log.info(
            "%s %d bars (%d changed) over %d session(s), %d split(s) recorded (%d applied), "
            "%d dividend(s) (%d changed), fx %s=%s (%d changed), run %s success",
            "dry-run: would write" if dry_run else "wrote",
            total,
            changed,
            len(f.sessions),
            sum(1 for o in outcomes if o.recorded),
            applied,
            len(f.dividends),
            dividends_changed,
            f.fx_row[0],
            f.fx_row[1],
            fx_changed,
            run_id,
        )
    if dry_run:
        log.info("dry-run: rolled back; nothing written")
```
**Impact:** one more Massive call per missing session. `wanted` keeps its name and meaning (the
universe set), so `tests/test_nightly.py`'s `fixed_universe` monkeypatch keeps working. When no
session is missing, no dividend call is made (`test_bars_already_current_still_records_fx_and_finishes`
still sees `fake.calls == []`).

### Step 6: Tests — new `test_dividends.py`
**File:** `engine/tests/test_dividends.py` (new)
**Code:**
```python
from datetime import date
from decimal import Decimal

import pytest
from psycopg.rows import tuple_row

from seer_engine import db, dividends
from seer_engine.dividends import Dividend, adjust_for_splits, parse_massive, quantize_amount, totals
from seer_engine.splits import Split

EX = date(2026, 9, 18)


def row(ticker="SPY", amount=1.888834, kind="CD", currency="USD", ex="2026-09-18"):
    return {"ticker": ticker, "cash_amount": amount, "currency": currency, "dividend_type": kind, "ex_dividend_date": ex}


# ---- parsing (pure) ----

def test_parse_regular_and_special_cash():
    assert parse_massive(row()) == Dividend("SPY", EX, Decimal("1.888834"))
    assert parse_massive(row("AAPL", 0.5, kind="SC")) == Dividend("AAPL", EX, Decimal("0.5"))


@pytest.mark.parametrize(
    "raw",
    [
        row(kind="LT"),
        row(kind="ST"),
        row(kind=None),
        row(currency="CAD"),
        {"ticker": "SPY", "cash_amount": 1.0, "dividend_type": "CD", "ex_dividend_date": "2026-09-18"},
    ],
)
def test_parse_drops_non_cash_and_non_usd(raw):
    assert parse_massive(raw) is None


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        ({"cash_amount": 1, "currency": "USD", "dividend_type": "CD", "ex_dividend_date": "2026-09-18"}, KeyError),
        (row(ticker=""), ValueError),
        (row(ticker=7), ValueError),
        (row(amount=0), ValueError),
        (row(amount=-0.1), ValueError),
        (row(amount="abc"), ValueError),
        (row(amount=True), TypeError),
        (row(ex="18/09/2026"), ValueError),
        (row(ex=None), ValueError),
        ({"ticker": "SPY", "currency": "USD", "dividend_type": "CD", "ex_dividend_date": "2026-09-18"}, KeyError),
    ],
)
def test_parse_malformed_rows_raise(raw, error):
    with pytest.raises(error):
        parse_massive(raw)


def test_quantize_amount_is_half_up_6dp():
    assert quantize_amount(Decimal("0.1234565")) == Decimal("0.123457")
    assert quantize_amount(Decimal("0.1234564999")) == Decimal("0.123456")
    assert quantize_amount(Decimal("2")) == Decimal("2.000000")


# ---- sums (pure) ----

def test_totals_sum_per_symbol_and_ex_date_sorted():
    out = totals(
        [
            Dividend("SPY", EX, Decimal("1.888834")),
            Dividend("AAPL", EX, Decimal("0.26")),
            Dividend("AAPL", EX, Decimal("0.0100005")),  # SC on the same ex-date: summed, then rounded
            Dividend("AAPL", date(2026, 9, 19), Decimal("0.1")),
        ]
    )
    assert out == [
        Dividend("AAPL", EX, Decimal("0.270001")),
        Dividend("AAPL", date(2026, 9, 19), Decimal("0.100000")),
        Dividend("SPY", EX, Decimal("1.888834")),
    ]


def test_totals_drop_amounts_that_round_to_zero():
    assert totals([Dividend("TINY", EX, Decimal("0.0000004"))]) == []
    assert totals([]) == []


# ---- split adjustment of fetched rows (pure) ----

NVDA_DIV = Dividend("NVDA", EX, Decimal("1.000000"))


def test_split_after_ex_date_scales_the_amount():
    out = adjust_for_splits([NVDA_DIV], [Split("NVDA", date(2026, 9, 21), Decimal(1), Decimal(10))])
    assert out == [Dividend("NVDA", EX, Decimal("0.100000"))]


def test_split_on_or_before_ex_date_and_other_symbols_leave_it():
    items = [NVDA_DIV, Dividend("AAPL", EX, Decimal("0.26"))]
    out = adjust_for_splits(
        items,
        [
            Split("NVDA", EX, Decimal(1), Decimal(10)),  # same day: the dividend is already post-split
            Split("NVDA", date(2026, 9, 17), Decimal(1), Decimal(4)),
            Split("MSFT", date(2026, 9, 21), Decimal(1), Decimal(2)),
        ],
    )
    assert out == items
    assert out[0] is NVDA_DIV


def test_chained_and_reverse_splits_round_each_step_like_sql():
    out = adjust_for_splits(
        [Dividend("ABC", EX, Decimal("1.000001"))],
        [
            Split("ABC", date(2026, 9, 22), Decimal(2), Decimal(3)),  # 3-for-2, applied second
            Split("ABC", date(2026, 9, 21), Decimal(5), Decimal(1)),  # reverse 1-for-5, applied first -> 5.000005
        ],
    )
    # in date order: 5.000005 -> 5.000005 * 2 / 3 = 3.33333666.. -> 3.333337
    assert out == [Dividend("ABC", EX, Decimal("3.333337"))]


def test_duplicate_split_rows_count_once():
    s = Split("NVDA", date(2026, 9, 21), Decimal(1), Decimal(10))
    assert adjust_for_splits([NVDA_DIV], [s, s]) == [Dividend("NVDA", EX, Decimal("0.100000"))]


def test_adjusted_amount_rounding_to_zero_is_dropped():
    tiny = Dividend("TINY", EX, Decimal("0.000001"))
    assert adjust_for_splits([tiny], [Split("TINY", date(2026, 9, 21), Decimal(1), Decimal(10))]) == []


# ---- writes (needs PG_TEST_URL) ----

def stored(conn):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT symbol, ex_date, amount FROM dividends ORDER BY symbol, ex_date")
        rows = cur.fetchall()
    conn.rollback()
    return rows


def upsert(conn, items):
    with db.transaction(conn, False):
        return dividends.upsert_dividends(conn, items)


def test_upsert_inserts_then_is_idempotent_then_updates_changed(pg):
    items = [Dividend("SPY", EX, Decimal("1.888834")), Dividend("AAPL", EX, Decimal("0.26"))]
    assert upsert(pg, items) == 2
    assert stored(pg) == [("AAPL", EX, Decimal("0.260000")), ("SPY", EX, Decimal("1.888834"))]
    assert upsert(pg, items) == 0
    assert upsert(pg, [Dividend("AAPL", EX, Decimal("0.27")), Dividend("SPY", EX, Decimal("1.888834"))]) == 1
    assert stored(pg) == [("AAPL", EX, Decimal("0.270000")), ("SPY", EX, Decimal("1.888834"))]


def test_upsert_empty_batch_writes_nothing(pg):
    assert upsert(pg, []) == 0
    assert stored(pg) == []


def test_upsert_rejects_duplicates_and_non_positive_amounts(pg):
    with pytest.raises(ValueError, match="duplicate"):
        upsert(pg, [Dividend("SPY", EX, Decimal("1")), Dividend("SPY", EX, Decimal("2"))])
    with pytest.raises(ValueError, match="positive"):
        upsert(pg, [Dividend("SPY", EX, Decimal("0.0000001"))])
    assert stored(pg) == []
```
**Impact:** new tests only. Check the chained-split arithmetic while implementing:
`1.000001 * 5 / 1 = 5.000005`; `5.000005 * 2 / 3 = 3.333336666…` → half-up 6 dp = `3.333337`.

### Step 7: Tests — `test_massive.py`
**File:** `engine/tests/test_massive.py:151–157` (modify) and appended after line 162
**Change:**

(a) Replace `test_key_never_logged` (lines 151–157):
```python
def test_key_never_logged(caplog):
    caplog.set_level(logging.DEBUG)
    c, _ = make_client(FakeHttp([GROUPED_OK, {"status": "OK", "results": []}, {"status": "OK", "results": []}]))
    c.grouped(D)
    c.splits(D)
    c.dividends(D)
    assert KEY not in caplog.text
    assert "massive GET" in caplog.text
```

(b) Append after line 162:
```python
D_EX = date(2026, 9, 18)


def div_row(ticker, amount, kind="CD", currency="USD", ex="2026-09-18", **extra):
    return {
        "ticker": ticker,
        "cash_amount": amount,
        "currency": currency,
        "dividend_type": kind,
        "ex_dividend_date": ex,
        **extra,
    }


def test_dividends_keep_usd_cash_rows_and_follow_next_url():
    page1 = {
        "status": "OK",
        "results": [
            div_row("SPY", 1.888834, id="E1"),
            div_row("XYZ", 0.5, kind="LT", id="E2"),
            div_row("ABC", 0.3, currency="CAD", id="E3"),
            div_row("SPY", 1.888834, id="E1"),  # same Massive id again: kept once
        ],
        "next_url": "https://api.massive.com/v3/reference/dividends?cursor=abc",
    }
    page2 = {
        "status": "OK",
        "results": [
            div_row("AAPL", 0.26, id="E4"),
            div_row("AAPL", 0.01, kind="SC", id="E5"),
            {"ticker": "BROKEN", "dividend_type": "CD", "currency": "USD", "ex_dividend_date": "2026-09-18"},
            div_row("LATER", 0.1, ex="2026-09-19", id="E6"),
        ],
    }
    http_ = FakeHttp([page1, page2])
    c, clock = make_client(http_)
    out = c.dividends(D_EX)
    assert [(x.symbol, x.ex_date, x.amount) for x in out] == [
        ("SPY", D_EX, Decimal("1.888834")),
        ("AAPL", D_EX, Decimal("0.26")),
        ("AAPL", D_EX, Decimal("0.01")),
    ]
    assert http_.requests[0][0] == "https://api.massive.com/v3/reference/dividends"
    assert http_.requests[0][1] == {"ex_dividend_date": "2026-09-18", "limit": 1000, "apiKey": KEY}
    assert http_.requests[0][2] == {"retries": massive.RETRIES, "backoff": massive.BACKOFF}
    assert http_.requests[1][0] == "https://api.massive.com/v3/reference/dividends?cursor=abc"
    assert http_.requests[1][1] == {"apiKey": KEY}
    assert clock.sleeps == [pytest.approx(massive.MIN_INTERVAL)]


def test_dividends_without_results_is_empty():
    c, _ = make_client(FakeHttp([{"status": "OK"}]))
    assert c.dividends(D_EX) == []


def test_dividends_bad_status_raises():
    c, _ = make_client(FakeHttp([{"status": "NOT_AUTHORIZED", "message": "plan does not include dividends"}]))
    with pytest.raises(MassiveError, match="dividends 2026-09-18"):
        c.dividends(D_EX)


def test_dividends_page_limit(monkeypatch):
    monkeypatch.setattr(massive, "MAX_PAGES", 2)
    page = {"status": "OK", "results": [], "next_url": "https://api.massive.com/v3/reference/dividends?cursor=x"}
    http_ = FakeHttp([page, page])
    c, _ = make_client(http_)
    with pytest.raises(MassiveError, match="more than 2 pages"):
        c.dividends(D_EX)
    assert len(http_.requests) == 2
```
**Impact:** test-only.

### Step 8: Tests — `test_splits.py` and `test_universe_queries.py`
**File:** `engine/tests/test_splits.py`, appended after line 161
**Code:**
```python
# ---- dividends move with the bars (migration 003 table) ----

def seed_dividends(conn, rows):
    with db.transaction(conn, False):
        conn.execute(
            "INSERT INTO dividends (symbol, ex_date, amount) SELECT * FROM unnest(%s::text[], %s::date[], %s::numeric[])",
            ([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]),
        )


def stored_dividends(conn):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT symbol, ex_date, amount FROM dividends ORDER BY symbol, ex_date")
        rows = cur.fetchall()
    conn.rollback()
    return rows


def test_applied_split_rewrites_earlier_dividends_once(pg):
    seed(pg, [("NVDA", D0, 1190, 1210, 1180, 1200, 1_000_000), ("NVDA", D1, 1200, 1220, 1190, 1210, 2_000_000)])
    seed_dividends(pg, [("NVDA", D0, Decimal("1.000000")), ("NVDA", D2, Decimal("0.100000")), ("AAPL", D0, Decimal("0.260000"))])
    first = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.applied, o.rows, o.dividend_rows) for o in first] == [(True, 2, 1)]
    assert stored_dividends(pg) == [
        ("AAPL", D0, Decimal("0.260000")),
        ("NVDA", D0, Decimal("0.100000")),
        ("NVDA", D2, Decimal("0.100000")),  # ex on the execution date: already post-split
    ]
    second = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.recorded, o.dividend_rows) for o in second] == [(False, 0)]
    assert stored_dividends(pg)[1] == ("NVDA", D0, Decimal("0.100000"))


def test_split_not_applied_leaves_dividends(pg):
    seed(pg, [("NVDA", D1, 120, 122, 119, 121, 20_000_000)])
    seed_dividends(pg, [("NVDA", D0, Decimal("0.100000"))])
    out = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121.5")})
    assert [(o.applied, o.dividend_rows) for o in out] == [(False, 0)]
    assert stored_dividends(pg) == [("NVDA", D0, Decimal("0.100000"))]


def test_dividend_rewrite_rounds_to_6dp_and_reverse_splits_scale_up(pg):
    seed(pg, [("ABC", D1, 100, 100, 100, 100, 1001), ("XYZ", D1, Decimal("0.5"), Decimal("0.5"), Decimal("0.5"), Decimal("0.5"), 3200)])
    seed_dividends(pg, [("ABC", D0, Decimal("1.000001")), ("XYZ", D0, Decimal("0.010000"))])
    apply(pg, [Split("ABC", D2, Decimal(2), Decimal(3)), Split("XYZ", D2, Decimal(32), Decimal(1))], {"ABC": Decimal("66.5"), "XYZ": Decimal("16.2")})
    assert stored_dividends(pg) == [
        ("ABC", D0, Decimal("0.666667")),  # 1.000001 * 2 / 3 = 0.66666733..
        ("XYZ", D0, Decimal("0.320000")),  # reverse 32:1
    ]


def test_dividend_that_rounds_to_zero_is_removed(pg):
    seed(pg, [("NVDA", D1, 1200, 1200, 1200, 1200, 1)])
    seed_dividends(pg, [("NVDA", D0, Decimal("0.000001")), ("NVDA", D1, Decimal("1.000000"))])
    out = apply(pg, [NVDA_SPLIT], {"NVDA": Decimal("121")})
    assert [(o.applied, o.dividend_rows) for o in out] == [(True, 1)]
    assert stored_dividends(pg) == [("NVDA", D1, Decimal("0.100000"))]
```

**File:** `engine/tests/test_universe_queries.py`, appended after line 60; imports at line 7
**Change:** line 7 becomes
```python
from seer_engine.universe import BENCHMARK, all_symbols, members_on, paper_symbols, symbols_for_bars
```
and append:
```python
def _paper_state(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO strategies (id, name, sub, icon) VALUES ('T1', 'T1', '', 'sigma') ON CONFLICT (id) DO NOTHING"
        )
        cur.executemany(
            "INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, "
            "tp_price, sl_price, shares, status) VALUES ('T1', %s, %s, %s, %s, 10, 10, 11, 9, 1, %s)",
            [
                (date(2026, 9, 28), 1, "PEND", "Pending Co", "pending"),
                (date(2026, 9, 21), 2, "OPEN", "Open Co", "open"),
                (date(2026, 9, 14), 3, "DONE", "Closed Co", "closed"),
                (date(2026, 9, 14), 4, "EXP", "Expired Co", "expired"),
            ],
        )
        cur.execute(
            "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held, "
            "cost_usd, income_usd) VALUES ('T1', 'HELD', 3, 50, '2026-09-01', 48, 20, 0.5, 0)"
        )
        cur.executemany(
            "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price) "
            "VALUES ('T1', %s, %s, %s, 0.5, 20)",
            [
                (date(2026, 9, 1), 1, "PAST"),
                (date(2026, 10, 2), 1, "TODAY"),
                (date(2026, 10, 5), 1, "NEXT"),
            ],
        )


def test_paper_symbols_open_orders_positions_and_current_targets(pg):
    _paper_state(pg)
    assert paper_symbols(pg, date(2026, 10, 2)) == {"PEND", "OPEN", "HELD", "TODAY", "NEXT"}
    assert paper_symbols(pg, date(2026, 10, 5)) == {"PEND", "OPEN", "HELD", "NEXT"}
    pg.rollback()


def test_paper_symbols_empty_without_paper_state(pg):
    assert paper_symbols(pg, date(2026, 10, 2)) == set()
    pg.rollback()
```
**Impact:** test-only. Uses a private strategy id `T1` so it does not depend on phase 1's roster ids.

### Step 9: Tests — `test_nightly.py`
**File:** `engine/tests/test_nightly.py`
**Change:**

(a) Imports, lines 9–12, become:
```python
from seer_engine import bars, db, dividends, universe
from seer_engine.commands import nightly
from seer_engine.dividends import Dividend
from seer_engine.massive import MassiveError
from seer_engine.splits import Split
```

(b) `FakeMassive` (lines 30–50) becomes:
```python
class FakeMassive:
    """grouped_data: {date: {symbol: (o, h, l, c, v)}}; splits_data: {date: [Split]};
    dividends_data: {date: [Dividend]} (one per Massive row, not summed); dividends_fail raises
    from dividends() only."""

    def __init__(self, grouped_data=None, splits_data=None, fail=None, dividends_data=None, dividends_fail=None):
        self.grouped_data = grouped_data or {}
        self.splits_data = splits_data or {}
        self.dividends_data = dividends_data or {}
        self.fail = fail
        self.dividends_fail = dividends_fail
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

    def dividends(self, d):
        self.calls.append(("dividends", d))
        if self.dividends_fail is not None:
            raise self.dividends_fail
        return list(self.dividends_data.get(d, []))
```

(c) `CHECKSUM_TABLES` (lines 89–94) gains `dividends`:
```python
CHECKSUM_TABLES = {
    "bars": "x.symbol, x.date",
    "dividends": "x.symbol, x.ex_date",
    "fx_rates": "x.date",
    "runs": "x.id",
    "split_adjustments": "x.symbol, x.execution_date",
}
```

(d) Line 119 becomes
```python
    assert fake.calls == [("grouped", D_FRI), ("splits", D_FRI), ("dividends", D_FRI)]
```

(e) `test_dry_run_writes_nothing` (lines 222–229) becomes:
```python
def test_dry_run_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    before = checksums(pg)
    fake = FakeMassive(
        {D_FRI: day()},
        {D_FRI: [Split("NVDA", D_FRI, Decimal(1), Decimal(10))]},
        dividends_data={D_FRI: [Dividend("SPY", D_FRI, Decimal("1.888834"))]},
    )
    assert go(pg, fake, dry_run=True) == 0
    assert checksums(pg) == before
    assert real_runs(pg) == []
    assert fake.calls == [("grouped", D_FRI), ("splits", D_FRI), ("dividends", D_FRI)]
```

(f) New helpers and tests, inserted after `test_bars_already_current_still_records_fx_and_finishes`
(after line 297, before `# ---- CLI surface ----`):
```python
# ---- dividends and paper-held symbols ----

def stored_dividends(conn):
    return q(conn, "SELECT symbol, ex_date, amount FROM dividends ORDER BY symbol, ex_date")


def hold(conn, symbol, *, strategy="T1", target_session=None):
    """Paper state holding `symbol`: a book position, or a book target for `target_session`."""
    with db.transaction(conn, False):
        conn.execute(
            "INSERT INTO strategies (id, name, sub, icon) VALUES (%s, %s, '', 'sigma') ON CONFLICT (id) DO NOTHING",
            (strategy, strategy),
        )
        if target_session is None:
            conn.execute(
                "INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, "
                "days_held, cost_usd, income_usd) VALUES (%s, %s, 10, 50, %s, 50, 1, 0, 0)",
                (strategy, symbol, D_THU),
            )
        else:
            conn.execute(
                "INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price) "
                "VALUES (%s, %s, 1, %s, 1, 50)",
                (strategy, target_session, symbol),
            )


GONE_BAR = ("GONE", (50.0, 51.0, 49.0, 50.5, 1000.0))


def test_dividends_for_tracked_symbols_are_summed_and_written_with_the_bars(pg, fixed_universe):
    seed(pg, D_THU)
    fake = FakeMassive(
        {D_FRI: day()},
        dividends_data={
            D_FRI: [
                Dividend("SPY", D_FRI, Decimal("1.888834")),
                Dividend("AAPL", D_FRI, Decimal("0.26")),
                Dividend("AAPL", D_FRI, Decimal("0.01")),  # an SC row on the same ex-date
                Dividend("ZZZZ", D_FRI, Decimal("0.5")),  # not tracked: dropped
            ]
        },
    )
    assert go(pg, fake) == 0
    assert stored_dividends(pg) == [("AAPL", D_FRI, Decimal("0.270000")), ("SPY", D_FRI, Decimal("1.888834"))]
    assert real_runs(pg)[0][1] == "success"
    before = checksums(pg)
    assert go(pg, fake) == 0  # same session again: no-op
    assert checksums(pg) == before


def test_dividends_fetched_for_every_session_of_a_gap(pg, fixed_universe):
    seed(pg, D0)
    fake = FakeMassive(
        {D_WED: day(), D_THU: day(), D_FRI: day()},
        dividends_data={D_THU: [Dividend("MSFT", D_THU, Decimal("0.83"))]},
    )
    assert go(pg, fake) == 0
    assert [c for c in fake.calls if c[0] == "dividends"] == [("dividends", D_WED), ("dividends", D_THU), ("dividends", D_FRI)]
    assert stored_dividends(pg) == [("MSFT", D_THU, Decimal("0.830000"))]


def test_dividend_inside_gap_before_a_split_is_stored_in_post_split_units(pg, fixed_universe):
    others = [s for s in UNIVERSE if s != "NVDA"]
    seed(pg, D0, symbols=others)
    with db.transaction(pg, False):
        bars.upsert_bars(pg, [bars.make_bar("NVDA", D0, 1200, 1200, 1200, 1200, 1000)])
        dividends.upsert_dividends(pg, [Dividend("NVDA", D0, Decimal("1.000000"))])
    nvda = ("NVDA", (120.0, 121.0, 119.0, 120.5, 10_000.0))
    fake = FakeMassive(
        {D_WED: day(extra=[nvda]), D_THU: day(extra=[nvda]), D_FRI: day(extra=[nvda])},
        {D_THU: [Split("NVDA", D_THU, Decimal(1), Decimal(10))]},
        dividends_data={D_WED: [Dividend("NVDA", D_WED, Decimal("1.0"))]},
    )
    assert go(pg, fake) == 0
    assert stored_dividends(pg) == [
        ("NVDA", D0, Decimal("0.100000")),  # stored before: rewritten by apply_splits
        ("NVDA", D_WED, Decimal("0.100000")),  # fetched in the gap: adjusted in memory, not twice
    ]


def test_paper_held_symbol_outside_universe_gets_bars_and_dividends(pg, fixed_universe):
    seed(pg, D_THU)
    hold(pg, "GONE")
    hold(pg, "SOON", target_session=D_FRI)  # decided for the session being fetched
    hold(pg, "PAST", target_session=D_THU)  # an executed decision: not needed any more
    fake = FakeMassive(
        {D_FRI: day(extra=[GONE_BAR, ("SOON", (20.0, 21.0, 19.0, 20.5, 500.0)), ("PAST", (9.0, 9.0, 9.0, 9.0, 1.0))])},
        dividends_data={D_FRI: [Dividend("GONE", D_FRI, Decimal("0.4")), Dividend("PAST", D_FRI, Decimal("0.1"))]},
    )
    assert go(pg, fake) == 0
    stored = {r[0] for r in bars_on(pg, D_FRI)}
    assert stored == set(UNIVERSE) | {"GONE", "SOON"}  # not PAST, not ZZZZ
    assert stored_dividends(pg) == [("GONE", D_FRI, Decimal("0.400000"))]


def test_absent_paper_symbol_warns_and_does_not_count_toward_coverage(pg, fixed_universe, caplog):
    seed(pg, D_THU)
    for s in ("GONE1", "GONE2", "GONE3"):
        hold(pg, s)
    rows = day([s for s in UNIVERSE if s != "AVGO"])  # universe 9/10 = 90%; 3 held symbols all absent
    caplog.set_level(logging.WARNING)
    assert go(pg, FakeMassive({D_FRI: rows})) == 0
    assert "paper-held symbol(s) outside the universe absent" in caplog.text
    assert "GONE1, GONE2, GONE3" in caplog.text
    assert real_runs(pg)[0][1] == "success"


def test_dividends_failure_marks_run_failed_and_writes_nothing(pg, fixed_universe):
    seed(pg, D_THU)
    hold(pg, "GONE")
    before = checksums(pg)
    fake = FakeMassive({D_FRI: day(extra=[GONE_BAR])}, dividends_fail=MassiveError("dividends 2026-10-02: status 'ERROR'"))
    assert go(pg, fake) == 1
    [(_, status, _, _, error)] = real_runs(pg)
    assert status == "failed" and "dividends" in error
    assert bars_on(pg, D_FRI) == []
    assert stored_dividends(pg) == []
    assert q(pg, "SELECT count(*) FROM fx_rates") == [(0,)]
    after = checksums(pg)
    assert {k: v for k, v in after.items() if k != "runs"} == {k: v for k, v in before.items() if k != "runs"}


def test_fx_failure_after_dividends_fetched_writes_no_dividends(pg, fixed_universe):
    seed(pg, D_THU)

    def fx_down():
        raise RuntimeError("frankfurter down")

    fake = FakeMassive({D_FRI: day()}, dividends_data={D_FRI: [Dividend("SPY", D_FRI, Decimal("1.888834"))]})
    assert nightly.execute(pg, now=FRI_NIGHT, client=fake, fetch_fx=fx_down) == 1
    assert real_runs(pg)[0][1] == "failed"
    assert stored_dividends(pg) == []
    assert bars_on(pg, D_FRI) == []
```
**Impact:** test-only. `test_gap_of_three_sessions_fetched_in_order` (line 171) already filters
on `grouped` and needs no change; `test_same_now_twice…` and `test_labor_day…` compare call lists
before/after and stay valid; `test_bars_already_current…` still sees `fake.calls == []`.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.commands.nightly, seer_engine.dividends, seer_engine.massive"`
**Tests:** `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` — all pass, **0 skipped**. Focused: `… pytest engine/tests/test_dividends.py engine/tests/test_massive.py engine/tests/test_splits.py engine/tests/test_universe_queries.py engine/tests/test_nightly.py -q`. Web untouched (`cd web && npx vitest run` unchanged).
**Manual check (optional, read-only, costs 1 Massive call):** with `SEER_ENV_FILE=/home/miftah/seer/.env.local`,
`engine/.venv/bin/python -c "from datetime import date; from seer_engine import config, massive, dividends; c = massive.Client(config.require('MASSIVE_API_KEY')); t = dividends.totals(c.dividends(date(2026, 9, 18))); print(len(t), [x for x in t if x.symbol == 'SPY'])"` — expect ~500 totals and `SPY 2026-09-18 1.888834`. Never print the key. A `nightly --dry-run` against Neon is phase 13's job.
**Exit criteria:** fake-client tests cover dividends parsing (CD+SC kept, LT/ST/non-USD dropped, malformed skipped, id de-dup) and `next_url` pagination; `test_dividends` covers sums, 6-dp half-up rounding, gap split adjustment and idempotent upsert; `test_splits` shows an applied split rewrites earlier dividends once and a non-applied one does not; `test_nightly` shows dividends written in the run's transaction, a paper-held symbol outside the universe still fetched (and its dividends kept), an absent held symbol only warning, and a dividends or FX failure writing nothing.

## Handoffs

- **Phase 6 (paper store):** read dividends with `SELECT symbol, amount FROM dividends WHERE ex_date = %s` (or a range for the replay window); amounts are already in current bar units. Do not import `seer_engine.dividends` from pure modules. `universe.paper_symbols` may be reused.
- **Phase 7 (paper command / workflow):** the nightly job now makes 3 Massive calls per missing session at 12.5 s spacing (a full 30-session gap ≈ 19 min of rate-limit waits plus FX). `nightly.yml` has `timeout-minutes: 30` for the whole job. Reconciled: phase 13 raises it to 45 (plan index Decisions, "Nightly time budget"); phase 7 does not touch it, and neither does this phase. Normal nights (1 session) add ~12.5 s.
- **Phase 7 (R1, store/command semantics):** a dividend whose ex-date equals a split's execution date is stored as fetched (not rewritten), i.e. assumed already in post-split units. If the paper step applies the split before crediting the dividend on that session (C3 order: split → step_book with dividends), the units agree.
- **Phase 13 (docs, R7):** document in `engine/package_readme.md` (`nightly`, new `dividends` section) and `docs/runbooks/data-pipeline.md` / the paper runbook: the dividends source (`/v3/reference/dividends`, CD+SC, USD), the split rewrite, the paper-held symbols in the wanted set and the coverage rule. Not done here (docs are phase 13's).
- **Not done anywhere (out of scope, noted):** backfilling historical dividends into `dividends` (the paper clock starts after this lands, and the benchmark only credits ex-dates after the start); `backfill` stays bars-only.

## Risks

- **Massive `cash_amount` units.** The in-memory gap adjustment assumes `cash_amount` is the declared, unadjusted amount (Polygon semantics; observed for historical rows). If Massive ever returns split-adjusted amounts, a dividend that went ex inside a multi-session gap *before* a split in the same gap would be divided twice. That case needs a gap plus a split plus an ex-date in it on a tracked symbol; normal one-session nights are unaffected.
- **Extra Massive call per session** can fail the whole night (dividends are needed for correctness, so a failure is a failed run, like splits). Retry behavior is the existing `http.get_json` retry.
- **Rows the type filter drops.** A missing `currency` is treated as non-USD and dropped (logged in the count only). Verified 2026-09-18 rows all carried `currency`.

## Rollback

`git revert` this phase's commit: `dividends.py`, the `Client.dividends` method, the split dividend
rewrite, `paper_symbols` and the nightly changes go away together; tests revert with them. Data:
rows already written to `dividends` on Neon are harmless to older code (nothing else reads them
before phase 6); `TRUNCATE dividends` removes them if wanted. Bars fetched for paper-held symbols
are ordinary bars and stay valid.
