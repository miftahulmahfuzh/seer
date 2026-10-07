> Adopted from `SEAN_GOTRADE_TRACKER_PLAN.md` phase 4. Source: `.workflows/plan/sean-gotrade-tracker/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Engine: marks and the daily P&L series

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R2 — Sean tracks all of the owner's Gotrade activity and shows a profit-and-loss graph (this phase writes the daily series the graph draws, at real market prices)
**Depends on:** Phase 1 (migration `015_sean.sql`, fixture `web/lib/sean/fixtures/ledger.json`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/sean`

---

## Goal

After this phase the engine has a `sean marks` command that reads the owner's real orders from `sean_orders`, fetches daily closes from Yahoo for every symbol the owner has ever held (universe or not, delisted or not), stores them in `sean_marks`, and rewrites `sean_equity` with one profit/loss row per NYSE session from the first order on. A Python ledger, the twin of the web's TS ledger, computes those rows under contract B and passes the shared fixture. A dispatchable `sean.yml` workflow and a never-failing nightly step keep the series current.

All code in this plan was written and run before it was written down: the four new modules and three test files pass (23 tests, `-n auto` and `-n0`) against Postgres 16 with contract A applied as `015_sean.sql`, `ruff check` is clean, and both workflow files parse as YAML.

**Reconciled (round 1):** the sell rule in `ledger.py` and two of its unit tests were changed to
Phase 1's pro-rata oversell (plan Decisions). The reconciled `ledger.py` and `test_sean_ledger.py`
were run again from this file: 13/13 green, including the shared fixture written by Phase 1's plan.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- package `seer_engine.sean` (`engine/src/seer_engine/sean/__init__.py`)
- `seer_engine.sean.ledger` (`sean/ledger.py`): `Order`, `Holding`, `Ledger`, `PnlPoint`, `Closes` (type alias), `money`, `share_count`, `order_from_mapping`, `closes_from_mapping`, `sort_orders`, `close_on_or_before`, `build_ledger`, `pnl_series`, `pnl_at`, constants `MARKET_TZ`, `CENT`, `SHARE_QUANTUM`, `DUST`, `SIDES`
- `seer_engine.sean.marks` (`sean/marks.py`): `CloseFetch`, `yahoo_closes`, `Fetched`, `fetch_closes`, `upsert_marks`, `read_marks`
- `seer_engine.sean.equity` (`sean/equity.py`): `read_orders`, `symbol_starts`, `series`, `lock`, `replace_equity`
- command `seer_engine.commands.sean` (`commands/sean.py`): `HELP`, `add_arguments` (subparsers `dest="sean_command"`), `run`, `execute_marks(conn, *, now_utc=None, dry_run=False, fetch=marks.yahoo_closes) -> int`, `_marks`, `_HANDLERS = {"marks": _marks}`
- CLI: `python -m seer_engine [--dry-run] [-v] sean marks [--now ISO8601]`
- workflow `.github/workflows/sean.yml` (`workflow_dispatch`, optional boolean input `dry_run`, concurrency group `sean-writer`)
- step `Sean marks` at the end of `.github/workflows/nightly.yml` (`continue-on-error: true`)
- tests `engine/tests/test_sean_ledger.py`, `test_sean_marks.py`, `test_sean_command.py`

**Signature changes:** none
**Writes (DB):** `sean_marks` (upsert), `sean_equity` (full replace, inside a `LOCK TABLE sean_marks, sean_equity IN EXCLUSIVE MODE` transaction). **Reads:** `sean_orders`, `sean_marks`. Nothing outside the `sean_*` tables.
**Requires (from earlier phases):**
- Phase 1: `db/migrations/015_sean.sql` with contract A verbatim — specifically `sean_orders` columns `id, symbol, side, executed_at, price, shares, total_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd` (plus the NOT NULL `order_type, status, amount_usd` the tests insert), `sean_marks (symbol, date, close numeric(18,4), PK (symbol, date))`, `sean_equity (date PK, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd, computed_at DEFAULT now())`.
- Phase 1: `web/lib/sean/fixtures/ledger.json` in the schema under **Bindings** below. `test_sean_ledger.py::test_shared_fixture_matches_the_web_ledger` reads it and must not skip (CI fails on any SKIPPED).
**Provides (to later phases):**
- Phase 2: the workflow file name `sean.yml`, `workflow_dispatch` on `ref: main` with no required inputs (body `{"ref":"main"}` is enough, same as `dispatchRepick`).
- Phase 3: `sean_equity` holds one row per NYSE session from the first order's New York trade date through the last completed session, money in cents; empty when there are no orders. `sean_marks` has closes for every symbol Yahoo could price.
- Phase 7: `commands/sean.py` dispatch shape — add one `sub.add_parser("calibrate", ...)` block in `add_arguments` and one `"calibrate": _calibrate` entry in `_HANDLERS`; handlers take `(conn: psycopg.Connection, args: argparse.Namespace) -> int`; `run` opens and closes the connection. `equity.read_orders(conn) -> list[ledger.Order]` is reusable for reading orders, but note `Order` carries only the ledger's columns (no `amount_usd`, `order_type` or `net_profit_usd`); calibrate needs `amount_usd`, so it should run its own SELECT.
**Leaves alone (owned by others):** `db/migrations/*` and `web/**` (Phases 1, 2, 3, 5); `sim/`, `backtest/` (Phase 6); `lab/`, `commands/lab.py`, skills, docs (Phase 7); `paper/`, `commands/paper.py`, `commands/nightly.py`.

### Bindings (reconciled against Phase 1's executed plan; Phase 1 wins)

**1. Fixture, `web/lib/sean/fixtures/ledger.json` (written by Phase 1, the single source).** Keys
are the `sean_orders` / `sean_equity` column names; every number is a JSON string. `orders[]`:
`id` (int), `side`, `symbol`, `executed_at` (ISO with offset), `price`, `shares`, `amount_usd`,
`trading_fee_usd`, `regulatory_fee_usd`, `ppn_usd`, `total_usd` (no `net_profit_usd`; the ledger
never reads it). `closes`: `{ SYMBOL: [{date, close}] }`. `expected.positions[] = {symbol, shares
(9 dp), cost_usd}`, `expected.realized_usd`, `expected.fees_usd`, `expected.points[] = {date,
value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd}`. One extra top-level key,
`sessions[] = {executed_at, session}`, is ignored here. Phase 1's fixture covers an
after-midnight-WIB fill (id 3), an oversell (id 5), a sell of a stock never seen bought (id 10), a
holding with no closes (CCC), two orders at one instant replayed by id, a weekend date, a date
before any order, and a half-cent tie in realized.

**2. Contract B as Phase 1 made it exact; this ledger does exactly the same:**
- **Trade date** = the America/New_York calendar date of `executed_at` (a 03:10 WIB fill is the previous US session).
- **Rounding** half away from zero (`ROUND_HALF_UP`), each output field on its own from unrounded values (`pnl_usd` can differ by a cent from `realized_usd + unrealized_usd`).
- **Sell, pro rata (plan Decisions, "Oversell"):** `sold = min(receipt shares, held)`. When `sold > 0`: `avg = cost / held`; `proceeds = total_usd` when `sold` is the whole receipt, else `total_usd * sold / receipt shares` (multiply first, then divide); `realized += proceeds - sold * avg`; `cost -= sold * avg`; `shares -= sold`. The shares sold beyond what Sean knows of, and their money, are ignored. **A sell with nothing held adds nothing to realized — only its fees count** — so a pre-Sean holding the owner sells (e.g. the June 2025 NVDA lot, if its buy receipt is never uploaded) never books its whole proceeds as invented profit.
- **Fees** `+= trading + regulatory + PPN` on every order, the clamped part included.
- **"Last order price"** = the `price` of the latest order (either side) for that symbol among the orders applied at `d`; used only when the symbol has no close dated <= `d`.
- **Closing a position:** shares `< 1e-9` after an order -> the symbol leaves the holdings (shares and cost dropped).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sean/__init__.py` | create (line 1) | package docstring |
| `engine/src/seer_engine/sean/ledger.py` | create (line 1) | pure contract-B ledger |
| `engine/src/seer_engine/sean/marks.py` | create (line 1) | per-symbol Yahoo closes, `sean_marks` I/O |
| `engine/src/seer_engine/sean/equity.py` | create (line 1) | `sean_orders` read, series, lock, `sean_equity` replace |
| `engine/src/seer_engine/commands/sean.py` | create (line 1) | `sean` command, subcommand `marks` |
| `engine/tests/test_sean_ledger.py` | create (line 1) | ledger unit tests + shared fixture |
| `engine/tests/test_sean_marks.py` | create (line 1) | Yahoo mapping, skip-on-failure, upsert |
| `engine/tests/test_sean_command.py` | create (line 1) | end-to-end on the `pg` fixture, CLI parse |
| `.github/workflows/sean.yml` | create (line 1) | dispatchable marks run |
| `.github/workflows/nightly.yml` | modify (append after line 137, the end of the `Explain` step) | one `Sean marks` step, `continue-on-error: true` |

No change to `cli.py` (commands are discovered), `pyproject.toml` (no new dependency: `zoneinfo` is stdlib, yfinance/pandas already present) or `engine-ci.yml` (it already runs all of `engine/tests` with Postgres and the full checkout, so `REPO_ROOT/web/lib/sean/fixtures/ledger.json` is present).

## Implementation Steps

### Step 0: Worktree venv
**File:** none
**Change:** the worktree has no `engine/.venv` (memory `worktree-needs-own-venv`).
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
```
**Impact:** none on the tree.

### Step 1: The package
**File:** `engine/src/seer_engine/sean/__init__.py:1` (new)
**Code:**
```python
"""Sean: the owner's real Gotrade orders, marked to market.

- ``ledger``: pure average-cost ledger (plan contract B), the twin of web/lib/sean/ledger.ts.
- ``marks``: daily closes for every symbol the owner has held (``sean_marks``).
- ``equity``: the daily profit/loss series (``sean_equity``) the Overview page draws.

The command is ``python -m seer_engine sean marks`` (commands/sean.py).
"""
```
**Impact:** none.

### Step 2: The ledger (contract B)
**File:** `engine/src/seer_engine/sean/ledger.py:1` (new)
**Change:** a pure module (no psycopg, no network, no floats). `_Book` is the running state; `pnl_series` walks the orders once in `(executed_at, id)` order and emits a point per date, applying every order whose New York trade date is ≤ that date (trade date is monotonic in `executed_at`, so a prefix walk is exact). `close_on_or_before` uses `bisect` with `key=` (Python ≥ 3.10; the engine requires 3.11).
**Code:**
```python
"""Sean's ledger: the owner's real Gotrade orders -> holdings and profit/loss.

The Python twin of ``web/lib/sean/ledger.ts`` (plan contract B). Both must reproduce
``web/lib/sean/fixtures/ledger.json``; a change to one is a change to both.

Average-cost method, fees in the cost basis, orders applied in ``(executed_at, id)`` order:

- buy:  shares += s; cost += total_usd (trade amount plus every fee).
- sell: sold = min(s, shares held). If sold > 0: avg = cost / held; proceeds = total_usd when
  sold is the whole receipt, else total_usd * sold / s (the shares sold beyond what Sean knows
  of, and their money, are ignored); realized += proceeds - sold * avg; cost -= sold * avg;
  shares -= sold. A sell of a stock Sean never saw bought therefore changes nothing but the
  fees: booking its whole proceeds as profit would invent gains the size of the position.
  A position left under 1e-9 shares is closed (shares = cost = 0).
- fees += trading + regulatory + PPN, on every order (the clamped part included).

An order belongs to the New York calendar date of its ``executed_at`` (its trade date): a
03:10 WIB fill is the previous US session. At date ``d`` the orders with trade date <= d
are applied, and each holding is valued at its last close on or before ``d`` or, with no
close at all, at the price of its last order applied so far.

Money is kept unrounded and rounded to cents (half away from zero) only on output; shares
round to 9 decimals on output. Pure: no database, no network, no floats.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")
CENT = Decimal("0.01")
SHARE_QUANTUM = Decimal("0.000000001")
DUST = Decimal("1e-9")
SIDES = ("buy", "sell")
_ZERO = Decimal(0)
_MONEY_FIELDS = ("price", "shares", "total_usd", "trading_fee_usd", "regulatory_fee_usd", "ppn_usd")

# symbol -> ascending (session date, close)
Closes = Mapping[str, Sequence[tuple[date, Decimal]]]


def money(x: Decimal) -> Decimal:
    """``x`` rounded to cents, half away from zero (Decimal's ROUND_HALF_UP)."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def share_count(x: Decimal) -> Decimal:
    """``x`` rounded to 9 decimals, half away from zero."""
    return x.quantize(SHARE_QUANTUM, rounding=ROUND_HALF_UP)


def _dec(value: object, field: str) -> Decimal:
    """An exact Decimal from a Decimal, int or numeric string. Floats are refused."""
    if isinstance(value, (bool, float)):
        raise TypeError(f"{field}: {value!r} is not an exact number (floats are refused)")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"{field}: expected a number, got {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Order:
    """One filled Gotrade order, the columns of ``sean_orders`` the ledger reads."""

    id: int
    symbol: str
    side: str
    executed_at: datetime
    price: Decimal
    shares: Decimal
    total_usd: Decimal
    trading_fee_usd: Decimal
    regulatory_fee_usd: Decimal
    ppn_usd: Decimal

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"order {self.id}: side must be buy or sell, got {self.side!r}")
        if not self.symbol:
            raise ValueError(f"order {self.id}: empty symbol")
        if not isinstance(self.executed_at, datetime) or self.executed_at.utcoffset() is None:
            raise ValueError(f"order {self.id}: executed_at must be a timezone-aware datetime")
        for name in _MONEY_FIELDS:
            if not isinstance(getattr(self, name), Decimal):
                raise TypeError(f"order {self.id}: {name} must be a Decimal")
        if self.shares <= 0:
            raise ValueError(f"order {self.id}: shares must be positive, got {self.shares}")

    @property
    def trade_date(self) -> date:
        """The New York calendar date of the fill: the US session it belongs to."""
        return self.executed_at.astimezone(MARKET_TZ).date()

    @property
    def fees_usd(self) -> Decimal:
        return self.trading_fee_usd + self.regulatory_fee_usd + self.ppn_usd


@dataclass(frozen=True, slots=True)
class Holding:
    """An open position on output: 9-decimal shares, cost basis in cents (fees included)."""

    symbol: str
    shares: Decimal
    cost_usd: Decimal


@dataclass(frozen=True, slots=True)
class Ledger:
    """Every order applied: open holdings by symbol, cumulative realized P&L and fees."""

    holdings: tuple[Holding, ...]
    realized_usd: Decimal
    fees_usd: Decimal


@dataclass(frozen=True, slots=True)
class PnlPoint:
    """One date's marks, in cents. The fields are the ``sean_equity`` columns."""

    day: date
    value_usd: Decimal
    cost_usd: Decimal
    realized_usd: Decimal
    unrealized_usd: Decimal
    pnl_usd: Decimal
    fees_usd: Decimal


def order_from_mapping(m: Mapping[str, object]) -> Order:
    """An Order from a fixture object or a row dict keyed by ``sean_orders`` column names.

    ``executed_at`` may be an ISO 8601 string with an offset or an aware datetime; numbers
    may be strings, ints or Decimals.
    """
    at = m["executed_at"]
    if isinstance(at, str):
        at = datetime.fromisoformat(at)
    if not isinstance(at, datetime):
        raise TypeError(f"executed_at: expected an ISO string or datetime, got {at!r}")
    return Order(
        id=int(str(m["id"])),
        symbol=str(m["symbol"]),
        side=str(m["side"]),
        executed_at=at,
        price=_dec(m["price"], "price"),
        shares=_dec(m["shares"], "shares"),
        total_usd=_dec(m["total_usd"], "total_usd"),
        trading_fee_usd=_dec(m["trading_fee_usd"], "trading_fee_usd"),
        regulatory_fee_usd=_dec(m["regulatory_fee_usd"], "regulatory_fee_usd"),
        ppn_usd=_dec(m["ppn_usd"], "ppn_usd"),
    )


def closes_from_mapping(
    m: Mapping[str, Iterable[Mapping[str, object]]],
) -> dict[str, list[tuple[date, Decimal]]]:
    """``{symbol: [{"date": "YYYY-MM-DD", "close": "1.23"}, ...]}`` -> sorted Closes."""
    out: dict[str, list[tuple[date, Decimal]]] = {}
    for symbol, rows in m.items():
        out[symbol] = sorted(
            (date.fromisoformat(str(r["date"])), _dec(r["close"], "close")) for r in rows
        )
    return out


def sort_orders(orders: Iterable[Order]) -> list[Order]:
    """Orders in ledger order: ``executed_at``, then ``id``."""
    return sorted(orders, key=lambda o: (o.executed_at, o.id))


def close_on_or_before(series: Sequence[tuple[date, Decimal]], d: date) -> Decimal | None:
    """The last close dated on or before ``d`` in an ascending series, or None."""
    i = bisect.bisect_right(series, d, key=lambda row: row[0])
    return series[i - 1][1] if i else None


class _Book:
    """The running ledger. Unrounded Decimals throughout."""

    __slots__ = ("shares", "cost", "realized", "fees", "last_price")

    def __init__(self) -> None:
        self.shares: dict[str, Decimal] = {}
        self.cost: dict[str, Decimal] = {}
        self.realized = _ZERO
        self.fees = _ZERO
        self.last_price: dict[str, Decimal] = {}

    def apply(self, o: Order) -> None:
        held = self.shares.get(o.symbol, _ZERO)
        cost = self.cost.get(o.symbol, _ZERO)
        if o.side == "buy":
            held += o.shares
            cost += o.total_usd
        else:
            sold = min(o.shares, held)
            if sold > 0:
                avg = cost / held
                # Pro rata (contract B, as web/lib/sean/ledger.ts): only the shares Sean knows of,
                # and their share of the receipt's total, count. Multiply first, then divide.
                proceeds = o.total_usd if sold == o.shares else o.total_usd * sold / o.shares
                self.realized += proceeds - sold * avg
                cost -= sold * avg
                held -= sold
        if held < DUST:
            self.shares.pop(o.symbol, None)
            self.cost.pop(o.symbol, None)
        else:
            self.shares[o.symbol] = held
            self.cost[o.symbol] = cost
        self.fees += o.fees_usd
        self.last_price[o.symbol] = o.price

    def value(self, d: date, closes: Closes) -> Decimal:
        total = _ZERO
        for symbol, held in self.shares.items():
            price = close_on_or_before(closes.get(symbol, ()), d)
            if price is None:
                price = self.last_price[symbol]
            total += held * price
        return total

    def point(self, d: date, closes: Closes) -> PnlPoint:
        value = self.value(d, closes)
        cost = sum(self.cost.values(), _ZERO)
        unrealized = value - cost
        return PnlPoint(
            day=d,
            value_usd=money(value),
            cost_usd=money(cost),
            realized_usd=money(self.realized),
            unrealized_usd=money(unrealized),
            pnl_usd=money(self.realized + unrealized),
            fees_usd=money(self.fees),
        )


def build_ledger(orders: Iterable[Order]) -> Ledger:
    """Apply every order; open holdings sorted by symbol."""
    book = _Book()
    for o in sort_orders(orders):
        book.apply(o)
    holdings = tuple(
        Holding(symbol, share_count(book.shares[symbol]), money(book.cost[symbol]))
        for symbol in sorted(book.shares)
    )
    return Ledger(holdings=holdings, realized_usd=money(book.realized), fees_usd=money(book.fees))


def pnl_series(orders: Iterable[Order], days: Iterable[date], closes: Closes) -> list[PnlPoint]:
    """One PnlPoint per date in ``days`` (strictly ascending), each counting the orders whose
    trade date is on or before it."""
    wanted = list(days)
    for a, b in zip(wanted, wanted[1:]):
        if b <= a:
            raise ValueError(f"days must be strictly ascending: {a} then {b}")
    ordered = sort_orders(orders)
    book = _Book()
    out: list[PnlPoint] = []
    i = 0
    for d in wanted:
        while i < len(ordered) and ordered[i].trade_date <= d:
            book.apply(ordered[i])
            i += 1
        out.append(book.point(d, closes))
    return out


def pnl_at(orders: Iterable[Order], d: date, closes: Closes) -> PnlPoint:
    """The marks at one date."""
    return pnl_series(orders, [d], closes)[0]
```
**Impact:** none outside Sean. `PnlPoint.day` is named `day`, not `date`, so the field does not shadow the `date` type inside the dataclass; `equity.replace_equity` maps it to the `date` column.

### Step 3: Closes
**File:** `engine/src/seer_engine/sean/marks.py:1` (new)
**Change:** one Yahoo call per symbol (the owner holds about 15) so one bad ticker cannot sink a batch; `yahoo.download` already maps `BRK.B → BRK-B` via `to_yahoo`. Any exception or an empty answer is logged and the symbol listed in `Fetched.missing`; the run continues (contract B). The upsert uses `unnest` arrays with an `IS DISTINCT FROM` guard, so an identical re-run writes 0 rows; `fetch_closes` dedupes by date so the batch never holds the same `(symbol, date)` twice (which `ON CONFLICT DO UPDATE` would refuse).
**Code:**
```python
"""Daily closes for every symbol the owner has held, stored in ``sean_marks``.

Owner symbols are not limited to the universe (FUTU) and may be delisted, so ``bars`` is not
used: each symbol is fetched from Yahoo on its own, from its first trade date to the last
completed session. A symbol that fails or comes back empty is logged and skipped; it never
aborts the run. Its earlier stored closes still stand, and with none the ledger values it at
its last order price (contract B).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import psycopg

from seer_engine import yahoo

log = logging.getLogger(__name__)

# (symbol, first date, last date inclusive) -> [(date, close), ...]
CloseFetch = Callable[[str, date, date], list[tuple[date, Decimal]]]


def yahoo_closes(
    symbol: str, start: date, end: date, *, downloader: yahoo.Downloader | None = None
) -> list[tuple[date, Decimal]]:
    """Daily closes for one canonical symbol in ``[start, end]`` (split-adjusted, 4 decimals)."""
    got = yahoo.download([symbol], start, end + timedelta(days=1), downloader=downloader)
    bars = got.get(symbol.strip().upper(), [])
    return [(b.date, b.close) for b in bars if start <= b.date <= end]


@dataclass(frozen=True)
class Fetched:
    """Closes fetched this run, and the symbols that got none."""

    closes: dict[str, list[tuple[date, Decimal]]]
    missing: tuple[str, ...]

    def rows(self) -> list[tuple[str, date, Decimal]]:
        return [(s, d, c) for s, series in sorted(self.closes.items()) for d, c in series]


def fetch_closes(
    starts: Iterable[tuple[str, date]], end: date, fetch: CloseFetch = yahoo_closes
) -> Fetched:
    """Fetch ``[start, end]`` closes for each ``(symbol, start)``. Never raises for a symbol."""
    closes: dict[str, list[tuple[date, Decimal]]] = {}
    missing: list[str] = []
    for symbol, start in starts:
        if start > end:
            continue
        try:
            got = fetch(symbol, start, end)
        except Exception as exc:  # one symbol must never abort the run (contract B)
            log.warning("sean marks: no prices for %s (%s); its stored closes or last order price stand", symbol, exc)
            missing.append(symbol)
            continue
        by_date = {d: c for d, c in got if start <= d <= end}
        if not by_date:
            log.warning("sean marks: no prices for %s; its stored closes or last order price stand", symbol)
            missing.append(symbol)
            continue
        closes[symbol] = [(d, by_date[d]) for d in sorted(by_date)]
    return Fetched(closes=closes, missing=tuple(missing))


def upsert_marks(conn: psycopg.Connection, rows: Iterable[tuple[str, date, Decimal]]) -> int:
    """Insert new closes and update changed ones; return how many rows were written.

    An identical re-run writes nothing and returns 0. Does not commit.
    """
    batch = list(rows)
    if not batch:
        return 0
    cur = conn.execute(
        """
        INSERT INTO sean_marks (symbol, date, close)
        SELECT * FROM unnest(%s::text[], %s::date[], %s::numeric[])
        ON CONFLICT (symbol, date) DO UPDATE SET close = EXCLUDED.close
        WHERE sean_marks.close IS DISTINCT FROM EXCLUDED.close
        """,
        ([r[0] for r in batch], [r[1] for r in batch], [r[2] for r in batch]),
    )
    return cur.rowcount


def read_marks(conn: psycopg.Connection) -> dict[str, list[tuple[date, Decimal]]]:
    """Every stored close: ``{symbol: [(date, close), ...]}``, dates ascending."""
    out: dict[str, list[tuple[date, Decimal]]] = {}
    for symbol, d, close in conn.execute("SELECT symbol, date, close FROM sean_marks ORDER BY symbol, date"):
        out.setdefault(symbol, []).append((d, close))
    return out
```
**Impact:** network only through `yahoo.yf_download` when no `fetch`/`downloader` is injected. Every close is refetched from the symbol's first trade date each run (a few hundred rows a symbol), so a Yahoo correction is picked up.

### Step 4: The series
**File:** `engine/src/seer_engine/sean/equity.py:1` (new)
**Change:** reads orders, computes the session series through `dates.sessions`, and replaces `sean_equity` wholesale. `lock` takes `EXCLUSIVE` on both Sean tables: it serializes the nightly step against a dispatched `sean.yml` (each would otherwise `DELETE` then `INSERT` and could collide on the `date` primary key) and blocks no reader, so the site keeps the old series until commit. A table lock, not an advisory lock, because advisory locks are database-wide and would serialize the parallel test schemas under `pytest -n auto`.
**Code:**
```python
"""Sean's daily profit/loss series: ``sean_orders`` + ``sean_marks`` -> ``sean_equity``.

The series has one row per NYSE session from the first order's trade date to the last
completed session, recomputed in full and replaced on every run (a deleted or late upload
changes history, and the whole series is a few hundred rows).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

import psycopg

from seer_engine import dates
from seer_engine.sean import ledger
from seer_engine.sean.ledger import Closes, Order, PnlPoint

_ORDER_SQL = """
SELECT id, symbol, side, executed_at, price, shares, total_usd,
       trading_fee_usd, regulatory_fee_usd, ppn_usd
  FROM sean_orders
 ORDER BY executed_at, id
"""

_INSERT_SQL = """
INSERT INTO sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def read_orders(conn: psycopg.Connection) -> list[Order]:
    """Every stored order, in ledger order."""
    return [
        Order(
            id=int(r[0]),
            symbol=r[1],
            side=r[2],
            executed_at=r[3],
            price=r[4],
            shares=r[5],
            total_usd=r[6],
            trading_fee_usd=r[7],
            regulatory_fee_usd=r[8],
            ppn_usd=r[9],
        )
        for r in conn.execute(_ORDER_SQL).fetchall()
    ]


def symbol_starts(orders: Iterable[Order]) -> list[tuple[str, date]]:
    """``(symbol, first trade date)`` for every symbol ever traded, sorted by symbol."""
    first: dict[str, date] = {}
    for o in orders:
        d = o.trade_date
        if o.symbol not in first or d < first[o.symbol]:
            first[o.symbol] = d
    return sorted(first.items())


def series(orders: Sequence[Order], end: date, closes: Closes) -> list[PnlPoint]:
    """One point per NYSE session from the first trade date through ``end``."""
    if not orders:
        return []
    first = min(o.trade_date for o in orders)
    return ledger.pnl_series(orders, dates.sessions(first, end), closes)


def lock(conn: psycopg.Connection) -> None:
    """Serialize Sean writers (the nightly step and a dispatched sean.yml may overlap).

    EXCLUSIVE blocks other writers and other ``lock`` callers but not readers, so the site
    keeps reading the previous series until this transaction commits.
    """
    conn.execute("LOCK TABLE sean_marks, sean_equity IN EXCLUSIVE MODE")


def replace_equity(conn: psycopg.Connection, points: Sequence[PnlPoint]) -> int:
    """Replace the whole series with ``points``; return how many rows were written. No commit."""
    conn.execute("DELETE FROM sean_equity")
    if points:
        with conn.cursor() as cur:
            cur.executemany(
                _INSERT_SQL,
                [
                    (p.day, p.value_usd, p.cost_usd, p.realized_usd, p.unrealized_usd, p.pnl_usd, p.fees_usd)
                    for p in points
                ],
            )
    return len(points)
```
**Impact:** none outside Sean.

### Step 5: The command
**File:** `engine/src/seer_engine/commands/sean.py:1` (new)
**Change:** discovered by `cli.discover()`; subcommands dispatch through `_HANDLERS` like `commands/lab.py:272-275,1560`. `execute_marks`: (1) read orders in a short transaction; (2) none → lock, clear `sean_equity` (an owner who deleted every order must not keep a stale graph), no network, exit 0; (3) otherwise fetch closes outside any transaction; (4) in one locked transaction: upsert closes, **re-read orders** (an upload may have landed during the fetch), compute the series from every stored close, replace `sean_equity`. `--dry-run` rolls both transactions back (the write transaction still upserts and reads its own closes, so the logged figures are real). Exit code is 0 even when symbols had no prices; any unexpected exception becomes exit 1 through `cli.main`.
**Code:**
```python
"""`sean`: the owner's real Gotrade trades (the Sean section of the site).

    sean marks [--now ISO8601]   fetch daily closes for every symbol the owner has held
                                 (sean_marks) and rewrite the daily profit/loss series
                                 (sean_equity) from the first order to the last completed
                                 NYSE session

No orders yet: clears any stale series, fetches nothing, exit 0. A symbol Yahoo cannot price
(delisted, not listed there) is logged and valued at its stored closes or its last order
price; it never fails the run. Exit 0 on success, 1 on any other error.

Each subcommand is one ``sub.add_parser`` call in ``add_arguments`` and one ``_HANDLERS``
entry taking ``(conn, args)``.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

import psycopg

from seer_engine import dates, db
from seer_engine.sean import equity, marks

log = logging.getLogger(__name__)

HELP = "Sean, the owner's real Gotrade trades: mark holdings to market, write the daily P&L"


def _parse_now(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--now must be ISO 8601 (e.g. 2026-10-02T23:00:00Z): {value!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="sean_command", metavar="<sean command>", required=True)

    s = sub.add_parser(
        "marks",
        help="fetch closes for the owner's symbols and rewrite the daily P&L series",
        description=(
            "Fetch daily closes from Yahoo for every symbol in sean_orders, from its first trade "
            "date to the last completed NYSE session, upsert them into sean_marks, and replace "
            "sean_equity with one row per session from the first order on."
        ),
    )
    s.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        metavar="ISO8601",
        help="pretend the current time is this (UTC if no offset); for tests and replays",
    )


def run(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        return _HANDLERS[args.sean_command](conn, args)
    finally:
        conn.close()


def execute_marks(
    conn: psycopg.Connection,
    *,
    now_utc: datetime | None = None,
    dry_run: bool = False,
    fetch: marks.CloseFetch = marks.yahoo_closes,
) -> int:
    """Fetch closes, store them, rewrite the series. Prices are fetched outside any write
    transaction; the write re-reads the orders under the lock, so an upload that lands while
    prices download is counted (valued at its order price if it brought a new symbol)."""
    now = now_utc or datetime.now(timezone.utc)
    end = dates.last_completed_session(now)

    with db.transaction(conn, dry_run):
        orders = equity.read_orders(conn)

    if not orders:
        with db.transaction(conn, dry_run):
            equity.lock(conn)
            equity.replace_equity(conn, [])
        log.info("sean marks: no orders yet; nothing to mark")
        return 0

    fetched = marks.fetch_closes(equity.symbol_starts(orders), end, fetch)

    with db.transaction(conn, dry_run):
        equity.lock(conn)
        changed = marks.upsert_marks(conn, fetched.rows())
        orders = equity.read_orders(conn)
        points = equity.series(orders, end, marks.read_marks(conn))
        written = equity.replace_equity(conn, points)

    last = points[-1] if points else None
    log.info(
        "sean marks: %d symbols priced, %d without prices%s; %d closes written; %d sessions through %s%s%s",
        len(fetched.closes),
        len(fetched.missing),
        f" ({', '.join(fetched.missing)})" if fetched.missing else "",
        changed,
        written,
        end.isoformat(),
        f"; profit/loss ${last.pnl_usd}" if last else "",
        " (dry-run: rolled back)" if dry_run else "",
    )
    return 0


def _marks(conn: psycopg.Connection, args: argparse.Namespace) -> int:
    return execute_marks(conn, now_utc=args.now, dry_run=bool(args.dry_run))


_HANDLERS = {
    "marks": _marks,
}
```
**Impact:** `python -m seer_engine --help` lists `sean`. `test_cli.py` is unaffected (it asserts only `migrate` and a fake module).

### Step 6: Ledger tests
**File:** `engine/tests/test_sean_ledger.py:1` (new)
**Change:** unit cases for every contract-B rule in **Bindings** §2, then the shared fixture. The figures were computed by hand and confirmed by running: MU bought 0.25 for $30.13 (avg 120.52), 0.1 sold for $12.87 → realized 12.87 − 12.052 = 0.818 → `0.82`.
**Code:**
```python
"""Sean's ledger (plan contract B): unit cases, then the fixture shared with the web ledger."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from seer_engine import config
from seer_engine.sean import ledger
from seer_engine.sean.ledger import Order

FIXTURE = config.REPO_ROOT / "web" / "lib" / "sean" / "fixtures" / "ledger.json"
_POINT_FIELDS = ("value_usd", "cost_usd", "realized_usd", "unrealized_usd", "pnl_usd", "fees_usd")


def order(
    id: int,
    symbol: str,
    side: str,
    at: str,
    price: str,
    shares: str,
    total: str,
    fees: tuple[str, str, str] = ("0.10", "0.02", "0.01"),
) -> Order:
    return Order(
        id=id,
        symbol=symbol,
        side=side,
        executed_at=datetime.fromisoformat(at),
        price=Decimal(price),
        shares=Decimal(shares),
        total_usd=Decimal(total),
        trading_fee_usd=Decimal(fees[0]),
        regulatory_fee_usd=Decimal(fees[1]),
        ppn_usd=Decimal(fees[2]),
    )


def test_buy_puts_fees_in_the_cost_basis():
    led = ledger.build_ledger([order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13")])
    assert led.holdings == (ledger.Holding("MU", Decimal("0.250000000"), Decimal("30.13")),)
    assert led.realized_usd == Decimal("0.00")
    assert led.fees_usd == Decimal("0.13")


def test_sell_realizes_against_the_average_cost_with_fees():
    led = ledger.build_ledger([
        order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13"),
        order(2, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "12.87"),
    ])
    # avg = 30.13 / 0.25 = 120.52; basis sold = 12.052; realized = 12.87 - 12.052 = 0.818
    assert led.realized_usd == Decimal("0.82")
    assert led.holdings == (ledger.Holding("MU", Decimal("0.150000000"), Decimal("18.08")),)
    assert led.fees_usd == Decimal("0.26")


def test_a_sell_of_more_than_held_counts_only_the_held_shares_and_their_money():
    led = ledger.build_ledger([
        order(1, "AAA", "buy", "2026-06-16T21:40:00+07:00", "10.00", "1", "10.13"),
        order(2, "AAA", "sell", "2026-06-17T21:40:00+07:00", "6.00", "2", "11.87"),
    ])
    assert led.holdings == ()
    # 1 of the 2 shares sold was known: proceeds 11.87 * 1 / 2 = 5.935; realized 5.935 - 10.13
    # = -4.195, half away from zero -> -4.20
    assert led.realized_usd == Decimal("-4.20")
    assert led.fees_usd == Decimal("0.26")


def test_a_sell_with_nothing_held_adds_only_its_fees():
    led = ledger.build_ledger([order(1, "AAA", "sell", "2026-06-17T21:40:00+07:00", "6.00", "1", "5.87")])
    assert led.holdings == ()
    assert led.realized_usd == Decimal("0.00")
    assert led.fees_usd == Decimal("0.13")


def test_selling_everything_then_buying_again_starts_a_fresh_basis():
    led = ledger.build_ledger([
        order(1, "AAA", "buy", "2026-06-16T21:40:00+07:00", "10.00", "1", "10.13"),
        order(2, "AAA", "sell", "2026-06-17T21:40:00+07:00", "11.00", "1", "10.87"),
        order(3, "AAA", "buy", "2026-06-18T21:40:00+07:00", "12.00", "2", "24.13"),
    ])
    assert led.holdings == (ledger.Holding("AAA", Decimal("2.000000000"), Decimal("24.13")),)
    assert led.realized_usd == Decimal("0.74")


def test_orders_apply_by_time_then_id_whatever_order_they_arrive_in():
    a = order(2, "AAA", "sell", "2026-06-17T21:40:00+07:00", "11.00", "1", "10.87")
    b = order(1, "AAA", "buy", "2026-06-17T21:40:00+07:00", "10.00", "1", "10.13")
    c = order(3, "AAA", "buy", "2026-06-16T21:40:00+07:00", "9.00", "1", "9.13")
    assert [o.id for o in ledger.sort_orders([a, b, c])] == [3, 1, 2]
    assert ledger.build_ledger([a, b, c]) == ledger.build_ledger([c, b, a])


def test_trade_date_is_the_new_york_date():
    late = order(1, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "12.87")
    assert late.trade_date == date(2026, 6, 17)
    evening = order(2, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13")
    assert evening.trade_date == date(2026, 6, 16)


def test_value_uses_the_last_close_on_or_before_the_date_else_the_last_order_price():
    orders = [
        order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "1", "120.13"),
        order(2, "XYZ", "buy", "2026-06-16T22:00:00+07:00", "10.00", "2", "20.13"),
    ]
    closes = {"MU": [(date(2026, 6, 16), Decimal("121")), (date(2026, 6, 18), Decimal("125"))]}
    p = ledger.pnl_at(orders, date(2026, 6, 17), closes)
    assert p.value_usd == Decimal("141.00")  # MU at the 16th's close, XYZ at its order price
    assert p.cost_usd == Decimal("140.26")
    assert p.unrealized_usd == Decimal("0.74")
    assert p.pnl_usd == Decimal("0.74")
    assert p.fees_usd == Decimal("0.26")


def test_series_counts_only_orders_traded_on_or_before_each_date():
    orders = [
        order(1, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.13"),
        order(2, "XYZ", "buy", "2026-06-17T22:00:00+07:00", "10.00", "2", "20.13"),
        order(3, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "12.87"),
    ]
    closes = {"MU": [(date(2026, 6, 16), Decimal("121")), (date(2026, 6, 17), Decimal("125"))]}
    p16, p17 = ledger.pnl_series(orders, [date(2026, 6, 16), date(2026, 6, 17)], closes)
    assert (p16.value_usd, p16.cost_usd, p16.pnl_usd, p16.fees_usd) == (
        Decimal("30.25"), Decimal("30.13"), Decimal("0.12"), Decimal("0.13"),
    )
    assert (p17.value_usd, p17.cost_usd, p17.realized_usd, p17.unrealized_usd, p17.pnl_usd, p17.fees_usd) == (
        Decimal("38.75"), Decimal("38.21"), Decimal("0.82"), Decimal("0.54"), Decimal("1.36"), Decimal("0.39"),
    )


def test_series_refuses_unsorted_dates():
    with pytest.raises(ValueError):
        ledger.pnl_series([], [date(2026, 6, 17), date(2026, 6, 16)], {})


def test_money_rounds_half_away_from_zero():
    assert ledger.money(Decimal("0.005")) == Decimal("0.01")
    assert ledger.money(Decimal("-0.005")) == Decimal("-0.01")
    assert ledger.money(Decimal("0.0049")) == Decimal("0.00")


def test_order_refuses_floats_bad_sides_and_naive_times():
    with pytest.raises(TypeError):
        ledger.order_from_mapping({
            "id": 1, "symbol": "MU", "side": "buy", "executed_at": "2026-06-16T21:40:00+07:00",
            "price": 120.0, "shares": "1", "total_usd": "120.13",
            "trading_fee_usd": "0.10", "regulatory_fee_usd": "0.02", "ppn_usd": "0.01",
        })
    with pytest.raises(ValueError):
        order(1, "MU", "hold", "2026-06-16T21:40:00+07:00", "1", "1", "1")
    with pytest.raises(ValueError):
        order(1, "MU", "buy", "2026-06-16T21:40:00", "1", "1", "1")


def test_shared_fixture_matches_the_web_ledger():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"), parse_float=Decimal)
    orders = [ledger.order_from_mapping(m) for m in data["orders"]]
    closes = ledger.closes_from_mapping(data["closes"])
    expected = data["expected"]

    led = ledger.build_ledger(orders)
    assert [(h.symbol, h.shares, h.cost_usd) for h in led.holdings] == [
        (p["symbol"], Decimal(str(p["shares"])), Decimal(str(p["cost_usd"]))) for p in expected["positions"]
    ]
    assert led.realized_usd == Decimal(str(expected["realized_usd"]))
    assert led.fees_usd == Decimal(str(expected["fees_usd"]))

    assert expected["points"], "the fixture must check at least one date"
    for want in expected["points"]:
        got = ledger.pnl_at(orders, date.fromisoformat(want["date"]), closes)
        for field in _POINT_FIELDS:
            assert getattr(got, field) == Decimal(str(want[field])), (want["date"], field)
```
**Impact:** `test_shared_fixture_matches_the_web_ledger` fails (not skips) if Phase 1's fixture is missing or shaped differently — intended: the two ledgers must agree.

### Step 7: Marks tests
**File:** `engine/tests/test_sean_marks.py:1` (new)
**Code:**
```python
"""Sean's closes: Yahoo per symbol, failures skipped, idempotent upsert."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from seer_engine.sean import marks


def test_yahoo_closes_maps_the_symbol_and_drops_bars_after_the_end():
    calls = []

    def downloader(tickers, start, end_exclusive):
        calls.append((tickers, start, end_exclusive))
        idx = pd.DatetimeIndex(["2026-06-16", "2026-06-17", "2026-06-18"])
        return pd.DataFrame(
            {"Open": [1.0, 1.0, 1.0], "High": [2.0, 2.0, 2.0], "Low": [0.5, 0.5, 0.5],
             "Close": [1.5, 1.25, 1.75], "Volume": [10, 10, 10]},
            index=idx,
        )

    got = marks.yahoo_closes("BRK.B", date(2026, 6, 16), date(2026, 6, 17), downloader=downloader)
    assert calls == [(["BRK-B"], date(2026, 6, 16), date(2026, 6, 18))]
    assert got == [(date(2026, 6, 16), Decimal("1.5000")), (date(2026, 6, 17), Decimal("1.2500"))]


def test_a_failing_or_empty_symbol_is_skipped_not_fatal():
    def fetch(symbol, start, end):
        if symbol == "GONE":
            raise RuntimeError("delisted")
        if symbol == "EMPTY":
            return []
        return [(date(2026, 6, 15), Decimal("9")), (date(2026, 6, 16), Decimal("10")),
                (date(2026, 6, 23), Decimal("99"))]

    got = marks.fetch_closes(
        [("EMPTY", date(2026, 6, 16)), ("GONE", date(2026, 6, 16)), ("MU", date(2026, 6, 16))],
        date(2026, 6, 22),
        fetch,
    )
    assert got.closes == {"MU": [(date(2026, 6, 16), Decimal("10"))]}
    assert got.missing == ("EMPTY", "GONE")
    assert got.rows() == [("MU", date(2026, 6, 16), Decimal("10"))]


def test_a_symbol_first_traded_after_the_end_is_not_fetched():
    def fetch(symbol, start, end):
        raise AssertionError("must not fetch")

    got = marks.fetch_closes([("MU", date(2026, 6, 23))], date(2026, 6, 22), fetch)
    assert got.closes == {} and got.missing == ()


def test_upsert_is_idempotent_and_updates_changed_closes(pg):
    rows = [("MU", date(2026, 6, 16), Decimal("121")), ("MU", date(2026, 6, 17), Decimal("125"))]
    assert marks.upsert_marks(pg, rows) == 2
    assert marks.upsert_marks(pg, rows) == 0
    assert marks.upsert_marks(pg, [("MU", date(2026, 6, 17), Decimal("126"))]) == 1
    assert marks.upsert_marks(pg, []) == 0
    pg.commit()
    assert marks.read_marks(pg) == {
        "MU": [(date(2026, 6, 16), Decimal("121.0000")), (date(2026, 6, 17), Decimal("126.0000"))]
    }
```
**Impact:** `test_upsert_is_idempotent_and_updates_changed_closes` needs `PG_TEST_URL` (the `pg` fixture applies every migration, including Phase 1's `015_sean.sql`).

### Step 8: Command tests
**File:** `engine/tests/test_sean_command.py:1` (new)
**Change:** `NOW = 2026-06-23T00:00Z` → last completed session Monday 2026-06-22; sessions 16, 17, 18, 22 June (Juneteenth, Friday 19 June, is closed — asserted against `dates.sessions` as well as literally). XYZ's fetch raises, so XYZ is valued at its $10.00 order price. The 2026-06-18 03:10 WIB sell is the 17th's session.
**Code:**
```python
"""`sean marks`: closes in, daily P&L series out, against a real Postgres."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from seer_engine import cli, dates
from seer_engine.commands import sean as sean_cmd

NOW = datetime(2026, 6, 23, 0, 0, tzinfo=timezone.utc)  # last completed session: Mon 2026-06-22
MU_CLOSES = {
    date(2026, 6, 16): Decimal("121"),
    date(2026, 6, 17): Decimal("125"),
    date(2026, 6, 18): Decimal("128"),
    date(2026, 6, 22): Decimal("130"),
}


def add_order(conn, symbol, side, at, price, shares, amount, total):
    conn.execute(
        """
        INSERT INTO sean_orders (side, order_type, status, symbol, executed_at, price, shares,
                                 amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd)
        VALUES (%s, %s, 'Filled', %s, %s, %s, %s, %s, 0.10, 0.02, 0.01, %s)
        """,
        (side, "Market Buy" if side == "buy" else "Market Sell", symbol, datetime.fromisoformat(at),
         Decimal(price), Decimal(shares), Decimal(amount), Decimal(total)),
    )
    conn.commit()


def seed(conn):
    add_order(conn, "MU", "buy", "2026-06-16T21:40:00+07:00", "120.00", "0.25", "30.00", "30.13")
    add_order(conn, "XYZ", "buy", "2026-06-17T22:00:00+07:00", "10.00", "2", "20.00", "20.13")
    add_order(conn, "MU", "sell", "2026-06-18T03:10:00+07:00", "130.00", "0.1", "13.00", "12.87")


class FakeYahoo:
    def __init__(self):
        self.calls = []

    def __call__(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        if symbol == "XYZ":
            raise RuntimeError("delisted")
        return [(d, c) for d, c in sorted(MU_CLOSES.items()) if start <= d <= end]


def equity_rows(conn):
    return conn.execute(
        "SELECT date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd "
        "FROM sean_equity ORDER BY date"
    ).fetchall()


def test_no_orders_is_a_no_op_that_clears_a_stale_series(pg):
    pg.execute(
        "INSERT INTO sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd) "
        "VALUES ('2026-06-16', 1, 1, 0, 0, 0, 0)"
    )
    pg.commit()

    def fetch(symbol, start, end):
        raise AssertionError("no orders: nothing to fetch")

    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=fetch) == 0
    assert equity_rows(pg) == []


def test_marks_and_series(pg):
    seed(pg)
    fake = FakeYahoo()
    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=fake) == 0

    assert fake.calls == [("MU", date(2026, 6, 16), date(2026, 6, 22)), ("XYZ", date(2026, 6, 17), date(2026, 6, 22))]
    assert pg.execute("SELECT count(*) FROM sean_marks WHERE symbol = 'MU'").fetchone()[0] == 4
    assert pg.execute("SELECT count(*) FROM sean_marks WHERE symbol = 'XYZ'").fetchone()[0] == 0

    rows = equity_rows(pg)
    assert [r[0] for r in rows] == dates.sessions(date(2026, 6, 16), date(2026, 6, 22))
    assert [r[0] for r in rows] == [date(2026, 6, 16), date(2026, 6, 17), date(2026, 6, 18), date(2026, 6, 22)]
    D = Decimal
    assert rows[0][1:] == (D("30.25"), D("30.13"), D("0.00"), D("0.12"), D("0.12"), D("0.13"))
    # the 03:10 WIB sell is the 17th's session; XYZ has no close, so its order price stands
    assert rows[1][1:] == (D("38.75"), D("38.21"), D("0.82"), D("0.54"), D("1.36"), D("0.39"))
    assert rows[2][1:] == (D("39.20"), D("38.21"), D("0.82"), D("0.99"), D("1.81"), D("0.39"))
    assert rows[3][1:] == (D("39.50"), D("38.21"), D("0.82"), D("1.29"), D("2.11"), D("0.39"))


def test_a_rerun_replaces_the_series_and_keeps_stored_closes_when_yahoo_fails(pg):
    seed(pg)
    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=FakeYahoo()) == 0
    before = equity_rows(pg)

    def down(symbol, start, end):
        raise RuntimeError("yahoo is down")

    assert sean_cmd.execute_marks(pg, now_utc=NOW, fetch=down) == 0
    assert equity_rows(pg) == before


def test_dry_run_writes_nothing(pg):
    seed(pg)
    assert sean_cmd.execute_marks(pg, now_utc=NOW, dry_run=True, fetch=FakeYahoo()) == 0
    assert equity_rows(pg) == []
    assert pg.execute("SELECT count(*) FROM sean_marks").fetchone()[0] == 0


def test_cli_parses_the_marks_subcommand():
    args = cli.build_parser().parse_args(["sean", "marks", "--now", "2026-06-23T00:00:00Z"])
    assert args.sean_command == "marks"
    assert args.now == NOW
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["sean"])


def test_cli_end_to_end_on_an_empty_database(pg_schema, pg, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", pg_schema.url)
    assert cli.main(["sean", "marks", "--now", "2026-06-23T00:00:00Z"]) == 0
    assert cli.main(["--dry-run", "sean", "marks", "--now", "2026-06-23T00:00:00Z"]) == 0
    assert equity_rows(pg) == []
```
**Impact:** `test_cli_end_to_end_on_an_empty_database` points `DATABASE_URL_UNPOOLED` at the test schema (same pattern as `test_explain.py:293`); with no orders the command makes no network call.

### Step 9: The dispatchable workflow
**File:** `.github/workflows/sean.yml:1` (new)
**Change:** shaped like `repick.yml` (checkout, Python 3.11, install, migrate, run). Own concurrency group `sean-writer`: in `seer-db-writer` a pending Sean run would cancel a pending nightly retry, because GitHub keeps only one pending run per group. Two Sean runs collapsing into the latest is harmless (the run is idempotent). If a brand-new migration is applied by this run's `Migrate` at the same moment as the nightly's, one of the two fails on `schema_migrations` and is simply re-run; this is the same exposure `repick.yml` has and needs a new migration landing during a nightly window.
**Code:**
```yaml
name: Sean

# Marks the owner's real Gotrade holdings to market and rewrites Sean's daily profit/loss series
# (sean_marks, sean_equity). The site dispatches this right after a batch of order screenshots is
# uploaded, so the graph catches up at once; the nightly run does the same step every night, so a
# missed dispatch only delays the graph.
#
# Its own concurrency group, not seer-db-writer: Sean writes only Sean's tables, and a pending
# Sean run queued in seer-db-writer would cancel a pending nightly retry (GitHub keeps one pending
# run per group). An overlap with the nightly Sean step is serialized by a table lock in the engine.
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Fetch and compute everything, then roll back (writes nothing)'
        type: boolean
        default: false

permissions:
  contents: read

concurrency:
  group: sean-writer
  cancel-in-progress: false

jobs:
  marks:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      DATABASE_URL_UNPOOLED: ${{ secrets.DATABASE_URL_UNPOOLED }}
      DRY_RUN: ${{ inputs.dry_run == true }}
      PYTHONUNBUFFERED: '1'
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: engine/pyproject.toml

      - name: Install engine
        run: python -m pip install -e engine

      - name: Migrate
        run: |
          flags=()
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" migrate

      - name: Sean marks
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" sean marks
```
**Impact:** Phase 2's dispatch (`POST .../actions/workflows/sean.yml/dispatches` with `{"ref":"main"}`) starts working once this file is on `main`. The workflow uses only `DATABASE_URL_UNPOOLED`, already a repository secret.

### Step 10: The nightly step
**File:** `.github/workflows/nightly.yml:137` (append after the last line, `python -m seer_engine "${flags[@]}" explain`)
**Change:** one step at the very end, after Paper, Paper check and Explain, so it can never delay or fail anything the paper night does. No `PAPER_PAUSED` guard (Sean does not depend on paper). Same condition as Explain so a red Paper check does not stop it; not run after a failed Nightly or Paper (the job is already red then and the next dispatch or night catches up). Inherits `DATABASE_URL_UNPOOLED` and `DRY_RUN` from the job `env`.
**Code** (appended verbatim, including the leading blank line):
```yaml

      # Sean (the owner's real Gotrade trades): fetch closes for every symbol the owner has held
      # and rewrite the daily profit/loss series. Independent of paper trading, so it runs while
      # paper is paused too. Never fails the night: a Yahoo outage or a crash only leaves Sean's
      # graph a day behind. Runs after a red Paper check, like Explain.
      - name: Sean marks
        if: ${{ success() || steps.paper_check.outcome == 'failure' }}
        continue-on-error: true
        timeout-minutes: 10
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" sean marks
```
**Impact:** the nightly job gains up to about a minute (15 Yahoo calls). `continue-on-error: true` + `timeout-minutes: 10` mean Sean can never turn the paper night red. The job's existing `timeout-minutes: 45` has room.

## Verification

**Build/lint:** `cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/engine && .venv/bin/ruff check .`
**Tests (Sean only, fast):**
```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/engine
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  .venv/bin/pytest -q -rs tests/test_sean_ledger.py tests/test_sean_marks.py tests/test_sean_command.py tests/test_cli.py tests/test_migrate.py
```
**Tests (full, the phase gate):** `cd engine && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres .venv/bin/pytest -q -rs` — green, and no `SKIPPED` line (CI treats one as failure).
**YAML:** `python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/sean.yml', '.github/workflows/nightly.yml')]"` from the worktree root.
**Manual check:** `cd engine && .venv/bin/python -m seer_engine --dry-run -v sean marks` against the real Neon (reads `.env.local`): with `015_sean.sql` applied and no orders yet it logs `sean marks: no orders yet; nothing to mark` and exits 0. After Phase 2 lands and orders are uploaded, the same dry-run logs the symbols priced, those without prices (e.g. a delisted ticker) and the latest profit/loss, and writes nothing.
**Exit criteria:** ruff clean; full pytest green with the three new files passing and nothing skipped; `python -m seer_engine sean marks` against an empty `sean_orders` exits 0 without a network call; `nightly.yml` ends with a `Sean marks` step that has `continue-on-error: true`; `sean.yml` exists with `workflow_dispatch`.

## Handoffs

- **Phase 1 (fixture):** reconciled — Phase 1's fixture already has this phase's schema, and this ledger now follows Phase 1's pro-rata oversell (**Bindings** §2). The fixture is the single source: change the math there (and in `ledger.ts`) and this test follows.
- **Phase 3 (Overview):** reconciled — its fallback series uses the same New York trade date (`orderSession`).
- **Phase 2 (dispatch):** target `sean.yml`, body `{"ref":"main"}`; a 404 before this phase lands is the "missing workflow = ignored" case the index already names.
- **Phase 7 (calibrate):** append to `commands/sean.py` as described under **Provides**; also extend the module docstring's command list. No other change to the dispatch is needed.
- **Unowned (future work, not in any phase):** stock splits. Yahoo closes are split-adjusted; receipts are not. After a split, every pre-split holding is valued at `old shares × adjusted close` and looks like a loss of the split ratio until the owner's post-split shares are known. Neither the receipts nor contract B carry split data; a fix would apply `splits` (the engine has `splits.py` for universe symbols) to Sean's share counts. Not planned here.
- **Unowned:** cash dividends the owner received are not in the P&L (receipts don't show them; out of scope per the index: "no Gotrade cash balance").

## Rollback

Revert this phase's commit: it only adds files and one trailing step in `nightly.yml`. The `sean_marks` / `sean_equity` rows it wrote are harmless to leave (only Sean's Overview reads `sean_equity`, and it falls back to order prices when the table is empty); to clear them, `TRUNCATE sean_marks, sean_equity`.
