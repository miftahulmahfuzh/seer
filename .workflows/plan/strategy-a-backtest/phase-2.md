# Phase 2: SPY buy-and-hold benchmark + vendored dividends

**Plan set:** `STRATEGY_A_BACKTEST_PLAN.md`
**Analysis:** `20261003-144506-Q8N4_code_analyzer.md`
**Satisfies:** R3 — SPY buy-and-hold curves (price-only and total-return), same 0.1% costs and whole-share rule
**Depends on:** Phase 1 (creates `engine/src/seer_engine/backtest/__init__.py` and `engine/tests/test_strategy_purity.py`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/backtest` (`seer_engine.backtest.benchmark`)

---

## Goal

After this phase the engine can build both SPY benchmark curves for any window: buy whole shares
at the first session's open after the 0.1% cost, hold, mark every close, and (total-return only)
credit each dividend on its ex-date and reinvest it at that close. SPY's real dividend history
since 2015 is vendored as `engine/data/spy_dividends.csv`, with a provenance entry, and a pure
parser for it exists. Nothing reads the file from disk yet (phase 5's `io.read_dividends` will).

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** (all in `engine/src/seer_engine/backtest/benchmark.py`)
- `DIVIDENDS_HEADER = "ex_date,amount_usd"`, `PRICE_CURVE = "spy_price"`, `TOTAL_RETURN_CURVE = "spy_tr"`
- `@dataclass(frozen=True, slots=True) class Dividend: ex_date: date; amount: Decimal`
- `def parse_dividends(text: str) -> tuple[Dividend, ...]` — header must be exactly `ex_date,amount_usd`;
  blank lines ignored; amount finite and > 0 (kept at full precision, not quantized); ex_dates
  strictly ascending; `ValueError` naming the line number otherwise.
- `@dataclass(frozen=True) class BenchmarkCurve: name: str; snapshots: tuple[Snapshot, ...]; shares: int; cash: Decimal; dividends_usd: Decimal`
- `def buy_and_hold(spy: Mapping[date, Bar], start: date, end: date, initial_cash: Decimal, *, dividends: Sequence[Dividend] = (), name: str) -> BenchmarkCurve`
- `def spy_curves(spy: Mapping[date, Bar], start: date, end: date, initial_cash: Decimal, dividends: Sequence[Dividend]) -> tuple[BenchmarkCurve, BenchmarkCurve]` — `(spy_price, spy_tr)`
- Data file `engine/data/spy_dividends.csv` (`ex_date,amount_usd`, ascending; 47 rows 2015-03-20 → 2026-09-18 when probed on 2026-10-03)

**Exact semantics consumers rely on (phases 4, 5):**
- `snapshots[0] == Snapshot(prev_session(start), cash0, cash0)` with `cash0 = q(initial_cash)`; then
  exactly one snapshot per NYSE session `start..end` inclusive, dated that session. So
  `len(snapshots) == len(dates.sessions(start, end)) + 1`, same shape as `RunResult.snapshots`.
- Snapshot `equity_usd = q(cash + shares × close)` (same formula as `sim.lifecycle._snapshot_equity`),
  `cash_usd = cash` (4 dp).
- Initial buy: `shares = floor(cash0 / (open × 1.001))`, `cash = cash0 − sim.buy_cost(open, shares)`.
- Dividend credited iff `start < ex_date <= end`; `cash += q(shares × amount)`, then
  `floor(cash / (close × 1.001))` more shares bought at that close with `sim.buy_cost`.
- Never sells. `shares`/`cash` are the holding after `end`. `dividends_usd` = sum of the credited
  `q(shares × amount)` (Decimal `0.0000` for price-only).
- Raises `ValueError` when: a session in `start..end` has no key in `spy`; a bar's `.date` differs
  from its key; `start` or `end` is not an NYSE session; `end < start`; `q(initial_cash) <= 0`;
  dividends not strictly ascending; a dividend with `start < ex_date <= end` is not an NYSE session.
  `TypeError` when `initial_cash` is not a `Decimal` or a value in `spy` is not a `prices.Bar`.
- `spy` is read only for session dates in the window; extra keys (earlier/later SPY bars) are fine,
  so phase 3's `Market.spy()` (every SPY bar) can be passed straight in.

**Requires (from earlier phases):**
- `engine/src/seer_engine/backtest/__init__.py` exists (phase 1, docstring only, no imports).
- `engine/tests/test_strategy_purity.py` (phase 1) globs `backtest/*.py` except `io.py`; `benchmark.py`
  is written to pass it: imports only `collections.abc`, `dataclasses`, `datetime`, `decimal`,
  `seer_engine.dates`, `seer_engine.prices`, `seer_engine.sim`; no `open/print/input`, no
  `.now/.today/...`, no `logging/time/random`. Importing `seer_engine.dates` loads
  `pandas_market_calendars` but none of `psycopg`, `requests`, `yfinance`, `seer_engine.bars`
  (measured on 2026-10-03).
- Consumes unchanged: `seer_engine.sim.{COST_RATE, Snapshot, buy_cost, q}`, `seer_engine.prices.Bar`,
  `seer_engine.dates.{sessions, prev_session}`; test helpers `simkit.{D, P, bar}`.

**Leaves alone (owned by others):** `backtest/__init__.py`, `strategies/*`, `test_strategy_purity.py`,
`stratkit.py` (phase 1); `backtest/market.py`, `backtest/runner.py` (phase 3 — `Market.spy()` produces
the `spy` mapping); `backtest/metrics.py` (`curve_metrics(BenchmarkCurve)`), `report.py` (phase 4);
`backtest/io.py` (`read_dividends(path)` = `parse_dividends(path.read_text())`, phase 5);
`engine/package_readme.md`, `docs/ROADMAP.md` (phase 6); `seer_engine/sim/*` (never).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/benchmark.py` | create | `Dividend`, `parse_dividends`, `BenchmarkCurve`, `buy_and_hold`, `spy_curves` (whole file, 197 lines) |
| `engine/data/spy_dividends.csv` | create | fetched once from yfinance (Step 2); never hand-written |
| `engine/data/SOURCES.md` | modify | lines 1–4: retitle intro to cover both uses; append a `spy_dividends.csv` section after line 84 (end of file) |
| `engine/tests/test_benchmark.py` | create | 32 tests: hand-computed curves, cost/whole-share edges, dividend window edges, errors, parser, vendored file |

## Implementation Steps

### Step 0: Worktree venv (only if absent)
**File:** `engine/.venv` (not committed)
**Change:** The worktree had no `engine/.venv` on 2026-10-03. Phase 1 normally creates it; if this
phase's session runs in a tree where it is still missing, create it. Never use
`/home/miftah/seer/engine/.venv` (it is an editable install of main's tree).
**Code:**
```sh
cd /home/miftah/.worktrees/seer/strategy-a-backtest
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'
engine/.venv/bin/python -c "import seer_engine, yfinance; print(seer_engine.__file__)"
# must print .../worktrees/seer/strategy-a-backtest/engine/src/seer_engine/__init__.py
```
**Impact:** none on the tree.

### Step 1: The benchmark module
**File:** `engine/src/seer_engine/backtest/benchmark.py:1` (new)
**Change:** whole file below. Verified on 2026-10-03 against the worktree's `sim`, `prices` and
`dates` (32/32 tests pass; AST purity scan clean).
**Code:**
```python
"""SPY buy-and-hold benchmark curves (handover §3 "Benchmark details", "SPY dividends").

Pure: no database, no files, no clock. ``io.read_dividends`` (phase 5) reads
``engine/data/spy_dividends.csv`` and hands its text to :func:`parse_dividends`.

Rules, identical for both curves:

- The curve starts with ``Snapshot(prev_session(start), cash0, cash0)``, so total return
  ``last / first - 1`` is measured from the starting cash, exactly like the strategy's run.
- At the **open** of ``start`` buy ``floor(cash0 / (open × 1.001))`` whole shares; cash pays
  ``sim.buy_cost(open, shares)``; the remainder sits idle.
- Every session from ``start`` to ``end`` is marked at its close:
  ``equity = q(cash + shares × close)``. Nothing is ever sold (the end is marked, not
  liquidated, as the strategy's open positions are).
- Total return only (``spy_tr``): a dividend with ``start < ex_date <= end`` is credited on
  its ex-date session (the holder at the previous close is paid): ``cash += q(shares ×
  amount)``, then ``floor(cash / (close × 1.001))`` more shares are bought at that close
  with ``sim.buy_cost``. A dividend on ``start`` itself is not credited (bought at the open,
  not a holder at the previous close). Price-only (``spy_price``) ignores dividends.
- Every NYSE session in the window must have a SPY bar; a missing one raises ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from seer_engine.dates import prev_session, sessions
from seer_engine.prices import Bar
from seer_engine.sim import COST_RATE, Snapshot, buy_cost, q

DIVIDENDS_HEADER = "ex_date,amount_usd"
PRICE_CURVE = "spy_price"
TOTAL_RETURN_CURVE = "spy_tr"


@dataclass(frozen=True, slots=True)
class Dividend:
    """One cash dividend: ``amount`` USD per share, paid to holders at the close before ``ex_date``."""

    ex_date: date
    amount: Decimal


@dataclass(frozen=True)
class BenchmarkCurve:
    """A buy-and-hold equity curve.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``; then one per session
    ``start..end``. ``shares`` and ``cash`` are the holding after ``end``; ``dividends_usd`` is
    the total cash dividends credited (0 for the price-only curve).
    """

    name: str
    snapshots: tuple[Snapshot, ...]
    shares: int
    cash: Decimal
    dividends_usd: Decimal


def parse_dividends(text: str) -> tuple[Dividend, ...]:
    """Parse ``ex_date,amount_usd`` CSV text into dividends.

    The first non-empty line must be the header exactly. Blank lines are ignored. Each row
    needs an ISO date and a finite decimal amount > 0; dates must be strictly ascending (so
    unique). Any violation raises ``ValueError`` naming the 1-based line number.
    """
    lines = text.splitlines()
    rows: list[Dividend] = []
    header_seen = False
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if not header_seen:
            if line != DIVIDENDS_HEADER:
                raise ValueError(f"line {number}: expected header {DIVIDENDS_HEADER!r}, got {line!r}")
            header_seen = True
            continue
        fields = line.split(",")
        if len(fields) != 2:
            raise ValueError(f"line {number}: expected 2 fields, got {len(fields)}: {line!r}")
        try:
            ex_date = date.fromisoformat(fields[0].strip())
        except ValueError as exc:
            raise ValueError(f"line {number}: bad ex_date {fields[0]!r}") from exc
        try:
            amount = Decimal(fields[1].strip())
        except InvalidOperation as exc:
            raise ValueError(f"line {number}: bad amount_usd {fields[1]!r}") from exc
        if not amount.is_finite() or amount <= 0:
            raise ValueError(f"line {number}: amount_usd must be > 0, got {fields[1]!r}")
        if rows and ex_date <= rows[-1].ex_date:
            raise ValueError(f"line {number}: ex_date {ex_date} is not after {rows[-1].ex_date}")
        rows.append(Dividend(ex_date=ex_date, amount=amount))
    if not header_seen:
        raise ValueError(f"no header: expected {DIVIDENDS_HEADER!r}")
    return tuple(rows)


def _whole_shares(cash: Decimal, price: Decimal) -> int:
    """The most whole shares ``cash`` buys at ``price`` after the 0.1% cost."""
    n = int(cash // (price * (1 + COST_RATE)))
    # q() rounds half-up; never let the rounded cost exceed the cash.
    while n > 0 and buy_cost(price, n) > cash:
        n -= 1
    return n


def _bar(spy: Mapping[date, Bar], d: date) -> Bar:
    bar = spy.get(d)
    if bar is None:
        raise ValueError(f"no SPY bar on session {d}")
    if not isinstance(bar, Bar):
        raise TypeError(f"SPY bar on {d} must be a Bar, got {type(bar).__name__}")
    if bar.date != d:
        raise ValueError(f"SPY bar keyed {d} is dated {bar.date}")
    return bar


def buy_and_hold(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    *,
    dividends: Sequence[Dividend] = (),
    name: str,
) -> BenchmarkCurve:
    """Buy SPY at ``start``'s open, hold, mark every close through ``end``.

    ``dividends`` empty gives the price-only curve; SPY's dividends give the total-return
    curve. Raises ``ValueError`` when ``start``/``end`` are not sessions, ``end < start``,
    ``initial_cash <= 0``, a dividend list is not strictly ascending, a dividend inside
    ``(start, end]`` is not dated on a session, or a session has no SPY bar.
    """
    if not isinstance(initial_cash, Decimal):
        raise TypeError(f"initial_cash must be a Decimal, got {type(initial_cash).__name__}")
    cash0 = q(initial_cash)
    if cash0 <= 0:
        raise ValueError(f"initial_cash must be > 0, got {initial_cash}")
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    window = sessions(start, end)
    if not window or window[0] != start:
        raise ValueError(f"start {start} is not an NYSE session")
    if window[-1] != end:
        raise ValueError(f"end {end} is not an NYSE session")
    for prev, cur in zip(dividends, dividends[1:]):
        if cur.ex_date <= prev.ex_date:
            raise ValueError(f"dividends not strictly ascending at {cur.ex_date}")
    in_window = set(window)
    paid: dict[date, Decimal] = {}
    for div in dividends:
        if start < div.ex_date <= end:
            if div.ex_date not in in_window:
                raise ValueError(f"dividend ex_date {div.ex_date} is not an NYSE session")
            paid[div.ex_date] = div.amount

    snaps: list[Snapshot] = [Snapshot(date=prev_session(start), cash_usd=cash0, equity_usd=cash0)]
    first = _bar(spy, start)
    shares = _whole_shares(cash0, first.open)
    cash = cash0 - buy_cost(first.open, shares)
    credited = Decimal("0.0000")
    for d in window:
        bar = _bar(spy, d)
        amount = paid.get(d)
        if amount is not None:
            income = q(shares * amount)
            cash += income
            credited += income
            more = _whole_shares(cash, bar.close)
            cash -= buy_cost(bar.close, more)
            shares += more
        snaps.append(Snapshot(date=d, cash_usd=cash, equity_usd=q(cash + shares * bar.close)))
    return BenchmarkCurve(
        name=name,
        snapshots=tuple(snaps),
        shares=shares,
        cash=cash,
        dividends_usd=credited,
    )


def spy_curves(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    dividends: Sequence[Dividend],
) -> tuple[BenchmarkCurve, BenchmarkCurve]:
    """``(spy_price, spy_tr)``: the price-only and total-return SPY curves over one window."""
    price = buy_and_hold(spy, start, end, initial_cash, name=PRICE_CURVE)
    total = buy_and_hold(spy, start, end, initial_cash, dividends=dividends, name=TOTAL_RETURN_CURVE)
    return price, total
```
**Impact:** new module only. `_whole_shares`'s `while` guard never runs for 4-dp cash (a half-up
quantize of `x <= cash` cannot exceed `cash` when `cash` is on the 4-dp grid); it is a belt-and-braces
check kept because `initial_cash` is quantized here, not trusted.

### Step 2: Fetch and vendor SPY dividends (once)
**File:** `engine/data/spy_dividends.csv` (new)
**Change:** run the script below **once**, from the worktree root, with the worktree venv. It needs
network access to Yahoo. It writes `ex_date,amount_usd` rows, ascending, from 2015-01-01, the amount
as the shortest repr of yfinance's float (no quantize; e.g. `0.931`, `1.889`). The script is not
committed; it is reproduced in `SOURCES.md` (Step 3).

**If Yahoo is unreachable, rate-limits, returns nothing, or the script exits non-zero: STOP and report
to the coordinator. Never write, edit, complete or "fix" a row by hand, and never copy numbers from
memory or another site.** The vendored-file test (Step 4) fails without the file, so the phase cannot
be marked done without a real fetch. Retrying the same script later is fine.

**Code:**
```sh
cd /home/miftah/.worktrees/seer/strategy-a-backtest
engine/.venv/bin/python - engine/data/spy_dividends.csv <<'EOF'
import sys
from datetime import date
from decimal import Decimal
import yfinance as yf

START = date(2015, 1, 1)
out_path = sys.argv[1]
s = yf.Ticker("SPY").dividends
if s is None or len(s) == 0:
    sys.exit("yfinance returned no SPY dividends; stop and report")
rows = []
for ts, amount in s.items():
    d = ts.date()
    if d < START:
        continue
    a = Decimal(repr(float(amount)))
    if not a.is_finite() or a <= 0:
        sys.exit(f"bad amount {amount!r} on {d}; stop and report")
    rows.append((d, a))
rows.sort()
if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
    sys.exit("duplicate ex_date; stop and report")
with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write("ex_date,amount_usd\n")
    for d, a in rows:
        f.write(f"{d.isoformat()},{format(a, 'f')}\n")
print(f"{len(rows)} rows {rows[0][0]} .. {rows[-1][0]}")
EOF
sha256sum engine/data/spy_dividends.csv
wc -l engine/data/spy_dividends.csv
head -3 engine/data/spy_dividends.csv; tail -2 engine/data/spy_dividends.csv
```
Probe run on 2026-10-03 (yfinance 1.7.0, into a scratch dir, not the tree): `47 rows 2015-03-20 ..
2026-09-18`, first rows `2015-03-20,0.931`, `2015-06-19,1.03`, last `2026-09-18,1.889`, sha256
`3251a8525bfcb6e1e3fe7b74db88326122826c808be5a6005eba767fbb5b598a`. The implementing session's own
fetch is what gets committed; if its row count, range or hash differs (Yahoo revising a value, a new
ex-date after 2026-10-03), record the actual values in `SOURCES.md` — do not force them to match the probe.

Sanity before committing (all must hold; else stop and report): 4 rows per year 2015–2025, ≥ 2 in
2026, every ex_date an NYSE session (SPY ex-dates are the third Friday of Mar/Jun/Sep/Dec or the
session before), every amount between 0.5 and 3. Step 4's last test checks exactly this.

**Impact:** new data file; read by nothing yet (phase 5 wires `io.read_dividends`).

### Step 3: Provenance entry
**File:** `engine/data/SOURCES.md:1-4` and append after `:84` (end of file)
**Change (a):** replace lines 1–4 (the title and intro claim the directory serves membership only):
```markdown
# Vendored data sources

Vendored inputs for `seer_engine.membership` / `python -m seer_engine universe refresh`, and the
SPY dividend history for the backtest benchmark (`seer_engine.backtest`).
Owner of this directory: the engine. Read by nothing else.
```
**Change (b):** append at the end of the file (fill the four `<...>` values from Step 2's actual
output; they are measured, not chosen):
````markdown

## spy_dividends.csv: SPY cash dividends (backtest benchmark)

| | |
|---|---|
| Upstream | Yahoo Finance via yfinance `Ticker("SPY").dividends` (per-share cash distributions by ex-date) |
| Fetched | <YYYY-MM-DD of the fetch>, yfinance <version> |
| Range | ex-dates 2015-01-01 onward; <N> rows, <first ex_date> .. <last ex_date> |
| License | Yahoo Finance data, personal/research use; not redistributed beyond this repo |
| sha256 | `<sha256sum output>` |

`ex_date,amount_usd`, ascending, one row per ex-date. `amount_usd` is USD per share as yfinance
reports it (shortest float repr, not rounded). SPY has had no split since 2015, so no adjustment
applies. Read by `seer_engine.backtest.io.read_dividends` -> `benchmark.parse_dividends`, which
rejects a bad header, a non-positive amount or a non-ascending date. Used only for the
total-return SPY curve (`spy_tr`), which the P3 gate compares against; `bars` are not
dividend-adjusted, so the price-only curve understates SPY by roughly 1.3-1.8 %/yr.
`tests/test_benchmark.py::test_vendored_spy_dividends_parse_and_cover_2015_2026` checks 4 rows a
year 2015-2025, every ex-date an NYSE session, every amount in (0.5, 3).

Never edit rows by hand. To refresh (for a later backtest end date), re-run the fetch with the
engine venv and update the table above:

```sh
engine/.venv/bin/python - engine/data/spy_dividends.csv <<'EOF'
import sys
from datetime import date
from decimal import Decimal
import yfinance as yf

START = date(2015, 1, 1)
out_path = sys.argv[1]
s = yf.Ticker("SPY").dividends
if s is None or len(s) == 0:
    sys.exit("yfinance returned no SPY dividends; stop and report")
rows = []
for ts, amount in s.items():
    d = ts.date()
    if d < START:
        continue
    a = Decimal(repr(float(amount)))
    if not a.is_finite() or a <= 0:
        sys.exit(f"bad amount {amount!r} on {d}; stop and report")
    rows.append((d, a))
rows.sort()
if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
    sys.exit("duplicate ex_date; stop and report")
with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write("ex_date,amount_usd\n")
    for d, a in rows:
        f.write(f"{d.isoformat()},{format(a, 'f')}\n")
print(f"{len(rows)} rows {rows[0][0]} .. {rows[-1][0]}")
EOF
```
````
**Impact:** docs only.

### Step 4: Tests
**File:** `engine/tests/test_benchmark.py:1` (new)
**Change:** whole file below. All numbers are hand-computed in the module docstring and in comments;
they were checked by running this exact file (32 passed). The vendored-file test reads
`engine/data/spy_dividends.csv` unconditionally (no skip: CI fails on any `SKIPPED`).
**Code:**
```python
"""SPY buy-and-hold benchmark (handover §6 item 5) and the vendored dividend file.

Window used throughout: the week 2026-03-02 (Mon) .. 2026-03-06 (Fri), all NYSE sessions;
prev_session(2026-03-02) = 2026-02-27. Starting cash 1000.0000 USD.

Hand computation (open 100 on 03-02; closes 101, 102, 98, 99, 100.5):
  buy: floor(1000 / (100 × 1.001)) = floor(9.99) = 9 shares, cost q(900.9) = 900.9000,
       cash 99.1000 idle.
  price-only equity = 99.1 + 9 × close: 1008.1, 1017.1, 981.1, 990.1, 1003.6
  total return, dividend 2.50 ex 03-04 (close 98):
       cash 99.1 + q(9 × 2.5) = 121.6; floor(121.6 / 98.098) = 1 more share,
       cost q(98.098) = 98.0980, cash 23.5020, 10 shares.
       equity: 1008.1, 1017.1, 23.502 + 980 = 1003.502, 1013.502, 1028.502
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import seer_engine
from seer_engine.backtest.benchmark import (
    DIVIDENDS_HEADER,
    BenchmarkCurve,
    Dividend,
    buy_and_hold,
    parse_dividends,
    spy_curves,
)
from seer_engine.dates import is_session
from seer_engine.sim import Snapshot
from simkit import D, P, bar

CASH = P("1000")
START = D("2026-03-02")
END = D("2026-03-06")
DIV_CSV = Path(seer_engine.__file__).resolve().parents[2] / "data" / "spy_dividends.csv"

# (date, open, close); high/low do not matter to the benchmark.
_WEEK = [
    ("2026-03-02", "100", "101"),
    ("2026-03-03", "101", "102"),
    ("2026-03-04", "100", "98"),
    ("2026-03-05", "98", "99"),
    ("2026-03-06", "99", "100.5"),
]


def spy_bars(rows=_WEEK) -> dict[date, object]:
    out = {}
    for d, o, c in rows:
        hi = max(Decimal(o), Decimal(c)) + 1
        lo = min(Decimal(o), Decimal(c)) - 1
        b = bar("SPY", d, o, hi, lo, c, 50_000_000)
        out[b.date] = b
    return out


def equities(curve: BenchmarkCurve) -> list[Decimal]:
    return [s.equity_usd for s in curve.snapshots]


def div(d: str, amount: str) -> Dividend:
    return Dividend(D(d), Decimal(amount))


# ----------------------------------------------------------------------------- price-only


def test_price_only_whole_shares_cost_and_idle_cash():
    c = buy_and_hold(spy_bars(), START, END, CASH, name="spy_price")
    assert c.name == "spy_price"
    assert c.shares == 9
    assert c.cash == P("99.1")
    assert c.dividends_usd == P("0")
    assert c.snapshots[0] == Snapshot(D("2026-02-27"), CASH, CASH)
    assert [s.date for s in c.snapshots[1:]] == [D(d) for d, _, _ in _WEEK]
    assert all(s.cash_usd == P("99.1") for s in c.snapshots[1:])
    assert equities(c) == [P(x) for x in ("1000", "1008.1", "1017.1", "981.1", "990.1", "1003.6")]


def test_price_only_curve_ignores_dividends():
    price, _ = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-04", "2.5")])
    assert price.name == "spy_price"
    assert price.dividends_usd == P("0")
    assert equities(price)[-1] == P("1003.6")


def test_buy_uses_open_not_close_and_cost_can_drop_a_share():
    # 1001 / 100.1 = 10.0 exactly -> 10 shares cost q(1001.0) = 1001.0000, cash 0.
    c = buy_and_hold(spy_bars(), START, END, P("1001"), name="x")
    assert (c.shares, c.cash) == (10, P("0"))
    # 1000.9999 is a hair short of 10 shares with cost -> 9 shares.
    c = buy_and_hold(spy_bars(), START, END, P("1000.9999"), name="x")
    assert (c.shares, c.cash) == (9, P("100.0999"))


def test_cash_below_one_share_holds_cash_only():
    c = buy_and_hold(spy_bars(), START, END, P("100"), name="x")
    assert c.shares == 0
    assert equities(c) == [P("100")] * 6


def test_single_session_window():
    c = buy_and_hold(spy_bars(), START, START, CASH, name="x")
    assert equities(c) == [P("1000"), P("1008.1")]


# ----------------------------------------------------------------------------- total return


def test_total_return_reinvests_dividend_at_ex_date_close():
    price, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-04", "2.5")])
    assert tr.name == "spy_tr"
    assert tr.dividends_usd == P("22.5")
    assert tr.shares == 10
    assert tr.cash == P("23.502")
    assert equities(tr) == [P(x) for x in ("1000", "1008.1", "1017.1", "1003.502", "1013.502", "1028.502")]
    assert [s.cash_usd for s in tr.snapshots] == [P(x) for x in ("1000", "99.1", "99.1", "23.502", "23.502", "23.502")]
    assert equities(tr)[-1] > equities(price)[-1]


def test_dividend_amount_is_quantized_and_cash_remainder_kept():
    # 998 -> 9 shares (cost 900.9000), cash 97.1000. Dividend 0.123456 on 03-04:
    # q(9 x 0.123456 = 1.111104) = 1.1111 -> cash 98.2111; floor(98.2111 / 98.098) = 1 share,
    # cost 98.0980 -> cash 0.1131, 10 shares; equity at 03-06 = 0.1131 + 1005 = 1005.1131.
    tr = buy_and_hold(spy_bars(), START, END, P("998"), dividends=[div("2026-03-04", "0.123456")], name="spy_tr")
    assert tr.dividends_usd == P("1.1111")
    assert (tr.shares, tr.cash) == (10, P("0.1131"))
    assert equities(tr)[-1] == P("1005.1131")


def test_dividend_too_small_for_a_share_stays_idle_cash():
    # 900.9: floor(900.9 / 100.1) = 9 exactly (cost 900.9000), cash 0.
    # Dividend 1.00 on 03-04: cash q(9 x 1) = 9.0000 < 98.098 -> no share bought, cash 9.
    # equity at 03-06 = 9 + 9 x 100.5 = 913.5.
    tr = buy_and_hold(spy_bars(), START, END, P("900.9"), dividends=[div("2026-03-04", "1")], name="spy_tr")
    assert (tr.shares, tr.cash, tr.dividends_usd) == (9, P("9"), P("9"))
    assert equities(tr)[-1] == P("913.5")


def test_dividend_on_start_session_not_credited():
    _, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-02", "2.5")])
    assert tr.dividends_usd == P("0")
    assert equities(tr)[-1] == P("1003.6")


def test_dividends_outside_window_not_credited():
    divs = [div("2026-02-27", "2.5"), div("2026-03-09", "2.5")]
    _, tr = spy_curves(spy_bars(), START, END, CASH, divs)
    assert tr.dividends_usd == P("0")
    assert equities(tr)[-1] == P("1003.6")


def test_dividend_on_end_session_is_credited():
    _, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-06", "2.5")])
    # cash 99.1 + 22.5 = 121.6; floor(121.6 / (100.5 × 1.001 = 100.6005)) = 1; cost 100.6005
    # cash 20.9995, 10 shares, equity 20.9995 + 1005 = 1025.9995
    assert tr.dividends_usd == P("22.5")
    assert (tr.shares, tr.cash) == (10, P("20.9995"))
    assert equities(tr)[-1] == P("1025.9995")


# ----------------------------------------------------------------------------- errors


def test_missing_spy_bar_raises():
    bars = spy_bars()
    del bars[D("2026-03-04")]
    with pytest.raises(ValueError, match="no SPY bar on session 2026-03-04"):
        buy_and_hold(bars, START, END, CASH, name="x")


def test_missing_first_bar_raises():
    bars = spy_bars()
    del bars[START]
    with pytest.raises(ValueError, match="no SPY bar"):
        buy_and_hold(bars, START, END, CASH, name="x")


def test_misdated_bar_raises():
    bars = spy_bars()
    bars[D("2026-03-04")] = bars[D("2026-03-05")]
    with pytest.raises(ValueError, match="dated"):
        buy_and_hold(bars, START, END, CASH, name="x")


@pytest.mark.parametrize(
    ("start", "end"),
    [("2026-03-01", "2026-03-06"), ("2026-03-02", "2026-03-07"), ("2026-03-06", "2026-03-02")],
)
def test_window_must_be_sessions_in_order(start, end):
    with pytest.raises(ValueError):
        buy_and_hold(spy_bars(), D(start), D(end), CASH, name="x")


def test_cash_must_be_positive_decimal():
    with pytest.raises(ValueError):
        buy_and_hold(spy_bars(), START, END, P("0"), name="x")
    with pytest.raises(TypeError):
        buy_and_hold(spy_bars(), START, END, 1000.0, name="x")  # type: ignore[arg-type]


def test_unsorted_or_non_session_dividends_raise():
    with pytest.raises(ValueError, match="ascending"):
        buy_and_hold(spy_bars(), START, END, CASH, dividends=[div("2026-03-05", "1"), div("2026-03-04", "1")], name="x")
    with pytest.raises(ValueError, match="not an NYSE session"):
        buy_and_hold(spy_bars(), START, D("2026-03-09"), CASH, dividends=[div("2026-03-07", "1")], name="x")


def test_deterministic():
    divs = [div("2026-03-04", "2.5")]
    assert spy_curves(spy_bars(), START, END, CASH, divs) == spy_curves(spy_bars(), START, END, CASH, divs)


# ----------------------------------------------------------------------------- parse_dividends


def test_parse_dividends_ok():
    text = f"{DIVIDENDS_HEADER}\n2015-03-20,1.1931\n\n2015-06-19,1.03\n"
    assert parse_dividends(text) == (div("2015-03-20", "1.1931"), div("2015-06-19", "1.03"))
    assert parse_dividends(text)[1].amount == Decimal("1.03")


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("", "no header"),
        ("date,amount\n2015-03-20,1\n", "expected header"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20\n", "2 fields"),
        (f"{DIVIDENDS_HEADER}\n2015-13-20,1\n", "bad ex_date"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,abc\n", "bad amount_usd"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,0\n", "> 0"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,-1\n", "> 0"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,NaN\n", "> 0"),
        (f"{DIVIDENDS_HEADER}\n2015-06-19,1\n2015-03-20,1\n", "not after"),
        (f"{DIVIDENDS_HEADER}\n2015-03-20,1\n2015-03-20,1\n", "not after"),
    ],
)
def test_parse_dividends_rejects(text, match):
    with pytest.raises(ValueError, match=match):
        parse_dividends(text)


# ----------------------------------------------------------------------------- vendored file


def test_vendored_spy_dividends_parse_and_cover_2015_2026():
    divs = parse_dividends(DIV_CSV.read_text(encoding="utf-8"))
    by_year: dict[int, int] = {}
    for dv in divs:
        by_year[dv.ex_date.year] = by_year.get(dv.ex_date.year, 0) + 1
        assert is_session(dv.ex_date), dv
        assert Decimal("0.5") < dv.amount < Decimal("3"), dv
    assert divs[0].ex_date.year == 2015
    assert all(by_year.get(y) == 4 for y in range(2015, 2026)), by_year
    assert by_year.get(2026, 0) >= 2, by_year
```
**Impact:** +32 tests: **480 passed** on phase 1 alone (448 + 32), **503 passed** if phase 3 landed first (471 + 32). Both measured by the reconciler on scratch copies (the fetch reproduced the probe: 47 rows, same sha256).

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/strategy-a-backtest && engine/.venv/bin/python -c "import seer_engine.backtest.benchmark as b; print(b.spy_curves)"`
**Tests:**
```sh
docker start seer-pg
cd /home/miftah/.worktrees/seer/strategy-a-backtest
engine/.venv/bin/pytest engine/tests/test_benchmark.py engine/tests/test_strategy_purity.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
**Manual check:** `git diff --stat` shows exactly the four files in **Files**; `spy_dividends.csv`
ends with a newline, has LF endings, and its sha256 matches `SOURCES.md`.
**Exit criteria:** handover §6 item 5 holds: `test_benchmark.py` passes (price-only and total-return
curves on synthetic bars with a dividend; whole-share buy at the first open after the 0.1% cost; idle
cash remainder; dividend reinvested at the ex-date close with cost; dividend on the start session not
credited; missing SPY bar raises; the vendored CSV parses and covers 2015–2026);
`test_strategy_purity.py` passes with `benchmark.py` in its glob; the full suite is green with 0 skipped (480, or 503 with phase 3).

## Handoffs

- **Phase 5 (R5/R6):** `io.read_dividends(path=DIVIDENDS_CSV)` should be
  `parse_dividends(path.read_text(encoding="utf-8"))`; the command passes the result to `spy_curves`
  for each window with that window's `initial_cash` (the same `initial_cash_usd(INITIAL_IDR, usd_idr)`
  the strategy run used — phase 3's `RunResult.initial_cash`), so strategy and SPY start from equal cash.
- **Phase 4 (R5):** `curve_metrics(c)` can feed `c.snapshots` exactly as it feeds `RunResult.snapshots`
  (same leading `prev_session(start)` snapshot); a benchmark has no trades, so `pnls=()`.
  Report the `dividends_usd` and final `shares`/`cash` if wanted.
- **Phase 3 (R2):** `Market.spy()` must return `dict[date, Bar]` keyed by the bar's own date with Decimal
  4-dp prices; `buy_and_hold` type-checks `prices.Bar` and the key/date match.
- **Phase 6 (R6):** document `benchmark.py` and the dividend file in `engine/package_readme.md`.
- If the real run's end date is after the last vendored ex-date plus a quarter (a later re-run), the file
  must be refreshed first (SOURCES.md "To refresh"); this phase does not add an automatic check for that.

## Rollback

`git revert` this phase's commit: it only adds `benchmark.py`, `spy_dividends.csv`, `test_benchmark.py`
and edits `SOURCES.md`. Nothing else imports `benchmark.py` until phases 4/5 land; revert those first if
they have.
