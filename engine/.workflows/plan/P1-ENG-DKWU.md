> Adopted from `STRATEGY_B_RANKER_PLAN.md` phase 3. Source: `.workflows/plan/strategy-b-ranker/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Vectorized bracket labeler

**Plan set:** `STRATEGY_B_RANKER_PLAN.md`
**Analysis:** `20261003-180843-B6R1_code_analyzer.md`
**Satisfies:** R1 (label paths, net of 0.1%/side, sim parity, no read past resolution), R6 (purity) — B's training target is the exact net return `sim` would book for that one order
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

`seer_engine.backtest.labels.label_orders` labels any number of (symbol, data_date, bracket) rows
in one vectorized call, with exactly the outcome `sim.step` plus the runner's forced close would give
that one order traded alone: same exit reason, same exit session (or expiry session), same fill and
exit prices, and the net-of-cost return per dollar. A new test file proves every label path by hand
and proves parity against `run_backtest` on a seeded synthetic market. Nothing else in the tree
changes.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates** (all in `engine/src/seer_engine/backtest/labels.py`, new):
- `REASONS: tuple[str, ...] = ("expire", "tp", "sl", "gap", "time", "forced")` — code = index; -1 = unresolved
- `COST = 0.001` (tested `== float(sim.COST_RATE)`)
- `@dataclass(frozen=True, eq=False) class Labels: label, resolved, reason, fill, exit` — exactly the contract's
  dtypes; **every array is returned read-only** (`flags.writeable == False`)
- `def label_orders(history: Mapping[str, History], symbols: Sequence[str], data_dates: np.ndarray, limit: np.ndarray, tp: np.ndarray, sl: np.ndarray, end: date) -> Labels`
- private: `_EXPIRE.._FORCED`, `_UNRESOLVED`, `_readonly`, `_prices`, `_symbol_index`, `_layout`
- the module imports `TIME_STOP_DAYS` from `seer_engine.sim.model` (read-only use; `labels.TIME_STOP_DAYS` is therefore an attribute, asserted == 5 in a test)

**Input preconditions (binding on phase 4, the only caller):**
- `data_dates`: `datetime64[D]`, 1-D, no NaT (else TypeError / ValueError).
- `limit`, `tp`, `sl`: float64 1-D of the same length, all finite and `0 < sl < limit < tp` on
  **every** row, else ValueError. So phase 4 must call `label_orders` on the valid-bracket subset only
  and scatter the result back into its full-table arrays (NaN / NaT / -1 elsewhere), exactly as the
  index's `CandidateTable.labels` comment already says.
- `symbols`: a `Sequence[str]` (tuple or list) of the same length, non-empty strs. A symbol missing from
  `history` has no bars (its orders expire). `history` values must be `History`.
- `end`: a `date`, not a `datetime`.

**Semantics pinned beyond the index text:**
- "The symbol's last bar" = its last bar dated `<= end` (any date, as `Market.last_bar_date`); the
  forced-close price is the close of its last bar on an NYSE session `<= end` (the runner's mark). When
  the market's data ends at `end` (phase 4's case) this is exactly the runner. When `end` is earlier than
  the data end, a symbol whose bars pause across `end` is force-closed at `end`'s point in time —
  deliberate: no bar after `end` is ever read.
- `days_held` on entering session `S1 + t` is `t` (every session adds 1, bar or not), so the time stop is
  "first bar at offset `t >= TIME_STOP_DAYS`".
- Runtime measured on a 1.34M-row / 663-symbol / 2,955-session synthetic market: **0.40 s** (one call).
  Memory: three `(symbols x sessions)` float64 matrices, about 47 MB at that scale.

**Requires (from earlier phases):** none.
**Leaves alone (owned by others):** `seer_engine/sim/*`, `backtest/runner.py`, `backtest/market.py`
and every other existing `backtest/` module, `strategies/*` (phases 1 and 2), `backtest/b_walkforward.py`
(phase 4), every existing test file (incl. `tests/test_backtest_runner.py`, `tests/stratkit.py`,
`tests/simkit.py`, `tests/test_strategy_purity.py`, which are imported, never edited).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/labels.py` | create (new file, line 1) | the labeler: `REASONS`, `COST`, `Labels`, `label_orders` |
| `engine/tests/test_backtest_labels.py` | create (new file, line 1) | 30 tests: constants, every label path, shape/validation, sim parity, vectorized == row-by-row, mutation after resolution |

No other file is touched. `tests/test_strategy_purity.py` globs `backtest/*.py`, so its three
existing tests cover the new module with no edit.

## Implementation Steps

### Step 0: Worktree venv (if this is the first session in the tree)
**File:** none
**Change:** from `/home/miftah/.worktrees/seer/strategy-b-ranker`:
`python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` (idempotent; re-run
after phase 1 lands). Never use `/home/miftah/seer/engine/.venv`. Then `docker start seer-pg`.
**Impact:** none on the tree.

### Step 1: Create the labeler
**File:** `engine/src/seer_engine/backtest/labels.py:1` (new)
**Change:** the complete module below. Algorithm:
1. Validate; build `sess = dates.sessions(min(data_dates), end)` as `datetime64[D]`.
2. `S1` index per row = `searchsorted(sess, data_date, "right")` — exactly `next_session(data_date)`
   whenever it is `<= end`; `== len(sess)` means S1 > end (unresolved). No per-row calendar call.
3. `_layout`: per distinct symbol (sorted), scatter its bars dated in `[sess[0], end]` onto session
   columns of dense `open/high/low` matrices (NaN = no bar); `gone_from[k]` = index of the first session
   after its last bar `<= end`; `last_close[k]` = close of its last session bar `<= end`.
4. S1 pass over all rows: `low < limit` (strict, NaN false) fills at `min(open, limit)`, else expire
   (label 0.0, resolved S1).
5. `t = 1, 2, ...`: one numpy pass over the still-open rows at column `S1 + t`: time (`t >= 5`) / gap /
   tp-at-open / sl / tp, first hit wins in that order; then still-open rows with `col >= gone_from`
   are forced at `last_close`. Rows whose column runs past `end` drop out unresolved. Stops when none is
   left.
6. `label = exit * (1 - COST) / (fill * (1 + COST)) - 1` for every traded resolved row.

Purity: no `logging`/`time`/`random`/`.random`/`.now`/`open()`; imports only `numpy`,
`seer_engine.dates`, `seer_engine.sim.model`, `seer_engine.strategies.base` (all already imported by
`runner.py`, so no new module reaches the purity subprocess check).

**Code:**
```python
"""Vectorized bracket-order labels: Strategy B's training target (P6a, handover §3 "Label").

``label_orders`` answers, for many candidate rows at once, "what would ONE bracket order placed
for this row have returned, net of cost, had it traded alone?" It follows design §5 exactly as
``sim.step`` and ``backtest.runner.run_backtest`` apply it, on NYSE sessions:

- the order session is ``S1 = next_session(data_date)``; the order fills only on S1, only when
  S1 has a bar with ``low < limit`` (strict), at ``min(open, limit)``; otherwise it expires;
- a filled order is not checked for exits on S1; ``days_held`` is 1 on S1 and grows by one on
  every later session, with or without a bar;
- on each later session with a bar, in order: ``days_held >= TIME_STOP_DAYS`` exits at the
  open ("time"); ``open <= sl`` at the open ("gap"); ``open >= tp`` at the open ("tp");
  ``low <= sl`` at sl ("sl"); ``high > tp`` at tp ("tp");
- after a session's checks, an order still open whose symbol's last bar is before that
  session is force-closed at the last close (the runner's ``close_unpriced``: sim reason
  "time" with ``forced=True``; here "forced"), resolved on that session.

Only bars dated ``<= end`` are read, and "the symbol's last bar" means its last bar dated
``<= end``: the labels are what a run whose data ends at ``end`` would see. An order not
resolved by ``end`` is unresolved (label NaN, resolved NaT, reason -1).

The label is ``exit * (1 - COST) / (fill * (1 + COST)) - 1``: the net return per dollar of the
one order, 0.1% per side. An expired order's label is 0.0. Labels are training targets, not
money, so this is float arithmetic on the float bars; the brackets are ``float()`` of the
4-dp Decimal prices ``sim`` would get, so every comparison agrees with the Decimal one.

Vectorized: the bars of the symbols present are laid out as session-aligned dense float
matrices (NaN = no bar), then one numpy pass per session offset after S1 runs over the rows
still open, until none is left or the sessions run out.

Pure: no database, clock, randomness, logging or files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from seer_engine import dates
from seer_engine.sim.model import TIME_STOP_DAYS
from seer_engine.strategies.base import History

REASONS: tuple[str, ...] = ("expire", "tp", "sl", "gap", "time", "forced")
COST = 0.001

_EXPIRE = 0
_TP = 1
_SL = 2
_GAP = 3
_TIME = 4
_FORCED = 5
_UNRESOLVED = -1


@dataclass(frozen=True, eq=False)
class Labels:
    """One entry per input row, in input order. Every array is read-only.

    - ``label``: float64, ``exit * (1 - COST) / (fill * (1 + COST)) - 1``; 0.0 for "expire";
      NaN when unresolved.
    - ``resolved``: datetime64[D], the exit session (for "expire": the order session S1);
      NaT when unresolved.
    - ``reason``: int8 index into ``REASONS``; -1 when unresolved.
    - ``fill``: float64 fill price; NaN when the order never filled (expired, or S1 > end).
    - ``exit``: float64 exit price; NaN when not filled or unresolved.
    """

    label: np.ndarray
    resolved: np.ndarray
    reason: np.ndarray
    fill: np.ndarray
    exit: np.ndarray


def _readonly(arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    return arr


def _prices(name: str, x: object, n: int) -> np.ndarray:
    if not isinstance(x, np.ndarray) or x.dtype != np.float64:
        raise TypeError(f"{name} must be a float64 numpy array")
    if x.shape != (n,):
        raise ValueError(f"{name} has shape {x.shape}, expected ({n},)")
    if not bool(np.all(np.isfinite(x))):
        raise ValueError(f"{name} must be finite on every row")
    return x


def _symbol_index(symbols: Sequence[str], n: int) -> tuple[list[str], np.ndarray]:
    """(sorted distinct symbols, int64 index of each row's symbol into that list)."""
    if isinstance(symbols, (str, bytes)) or not isinstance(symbols, Sequence):
        raise TypeError("symbols must be a sequence of str")
    if len(symbols) != n:
        raise ValueError(f"symbols has {len(symbols)} entries, data_dates has {n}")
    names = sorted(set(symbols))
    for s in names:
        if not isinstance(s, str) or not s:
            raise TypeError(f"every symbol must be a non-empty str, got {s!r}")
    code = {s: i for i, s in enumerate(names)}
    return names, np.fromiter((code[s] for s in symbols), dtype=np.int64, count=n)


def _layout(
    history: Mapping[str, History], names: list[str], sess: np.ndarray, end64: np.datetime64
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Session-aligned bars of ``names`` over ``sess`` (all dated <= end).

    Returns (open, high, low) as (symbols, sessions) float64 matrices with NaN where the
    symbol has no bar, ``gone_from`` (int64: the index of the first session after the symbol's
    last bar dated <= end; 0 when it has none) and ``last_close`` (float64: the close of its
    last bar on a session in ``sess``; NaN when none).
    """
    k, m = len(names), sess.shape[0]
    o = np.full((k, m), np.nan)
    hi = np.full((k, m), np.nan)
    lo = np.full((k, m), np.nan)
    c = np.full((k, m), np.nan)
    gone_from = np.zeros(k, dtype=np.int64)
    for i, s in enumerate(names):
        h = history.get(s)
        if h is None:
            continue
        if not isinstance(h, History):
            raise TypeError(f"history[{s!r}] must be a History, got {type(h).__name__}")
        stop = int(np.searchsorted(h.dates, end64, side="right"))
        if stop == 0:
            continue
        gone_from[i] = int(np.searchsorted(sess, h.dates[stop - 1], side="right"))
        start = int(np.searchsorted(h.dates, sess[0], side="left"))
        if start >= stop:
            continue
        d = h.dates[start:stop]
        pos = np.searchsorted(sess, d, side="left")
        on = (pos < m) & (sess[np.minimum(pos, m - 1)] == d)
        cols = pos[on]
        o[i, cols] = h.open[start:stop][on]
        hi[i, cols] = h.high[start:stop][on]
        lo[i, cols] = h.low[start:stop][on]
        c[i, cols] = h.close[start:stop][on]
    has = ~np.isnan(c)
    any_bar = has.any(axis=1)
    last_col = np.where(any_bar, m - 1 - np.argmax(has[:, ::-1], axis=1), 0)
    last_close = np.where(any_bar, c[np.arange(k), last_col], np.nan)
    return o, hi, lo, gone_from, last_close


def label_orders(
    history: Mapping[str, History],
    symbols: Sequence[str],
    data_dates: np.ndarray,
    limit: np.ndarray,
    tp: np.ndarray,
    sl: np.ndarray,
    end: date,
) -> Labels:
    """Label one bracket order per row, each simulated alone (see the module docstring).

    Row i is the order ``(symbols[i], limit[i], tp[i], sl[i])`` placed after the close of
    ``data_dates[i]`` for the next NYSE session. ``data_dates`` is datetime64[D] without NaT;
    ``limit``, ``tp`` and ``sl`` are finite float64 with ``0 < sl < limit < tp`` on every row
    (``float()`` of a valid 4-dp bracket). A symbol missing from ``history`` has no bars, so
    its orders expire. Raises TypeError / ValueError on malformed input.
    """
    if not isinstance(history, Mapping):
        raise TypeError(f"history must be a Mapping, got {type(history).__name__}")
    if isinstance(end, datetime) or not isinstance(end, date):
        raise TypeError(f"end must be a date, got {type(end).__name__}")
    if not isinstance(data_dates, np.ndarray) or data_dates.dtype != np.dtype("datetime64[D]"):
        raise TypeError("data_dates must be a datetime64[D] numpy array")
    if data_dates.ndim != 1:
        raise ValueError("data_dates must be 1-D")
    n = int(data_dates.shape[0])
    if bool(np.any(np.isnat(data_dates))):
        raise ValueError("data_dates must not hold NaT")
    lim = _prices("limit", limit, n)
    take = _prices("tp", tp, n)
    stop = _prices("sl", sl, n)
    if not bool(np.all((stop > 0.0) & (stop < lim) & (lim < take))):
        raise ValueError("every row needs 0 < sl < limit < tp")
    names, sym = _symbol_index(symbols, n)

    label = np.full(n, np.nan)
    resolved = np.full(n, np.datetime64("NaT"), dtype="datetime64[D]")
    reason = np.full(n, _UNRESOLVED, dtype=np.int8)
    fill = np.full(n, np.nan)
    exit_ = np.full(n, np.nan)

    end64 = np.datetime64(end, "D")
    sess = (
        np.array(dates.sessions(data_dates.min().item(), end), dtype="datetime64[D]")
        if n
        else np.array([], dtype="datetime64[D]")
    )
    m = int(sess.shape[0])
    if n and m:
        o, hi, lo, gone_from, last_close = _layout(history, names, sess, end64)

        # S1 = next_session(data_date): the first session in sess after data_date; none -> S1 > end.
        j1 = np.searchsorted(sess, data_dates, side="right")
        rows = np.flatnonzero(j1 < m)
        k1, c1 = sym[rows], j1[rows]
        filled = lo[k1, c1] < lim[rows]  # strict; NaN (no bar on S1) compares False
        gone = rows[~filled]
        reason[gone] = _EXPIRE
        label[gone] = 0.0
        resolved[gone] = sess[j1[gone]]
        act = rows[filled]
        open1 = o[sym[act], j1[act]]
        fill[act] = np.where(open1 < lim[act], open1, lim[act])

        t = 1  # session offset after S1; days_held on entering session S1 + t is t
        while act.size:
            col = j1[act] + t
            inside = col < m
            act, col = act[inside], col[inside]
            if not act.size:
                break
            k = sym[act]
            bo, bh, bl = o[k, col], hi[k, col], lo[k, col]
            bar = ~np.isnan(bo)
            s_, t_ = stop[act], take[act]
            price = np.full(act.size, np.nan)
            why = np.full(act.size, _UNRESOLVED, dtype=np.int8)
            for hit, at, code in (
                (bar & (t >= TIME_STOP_DAYS), bo, _TIME),
                (bar & (bo <= s_), bo, _GAP),
                (bar & (bo >= t_), bo, _TP),
                (bar & (bl <= s_), s_, _SL),
                (bar & (bh > t_), t_, _TP),
            ):
                now = hit & (why == _UNRESOLVED)
                price[now] = at[now]
                why[now] = code
            forced = (why == _UNRESOLVED) & (col >= gone_from[k])
            price[forced] = last_close[k][forced]
            why[forced] = _FORCED
            done = why != _UNRESOLVED
            out = act[done]
            reason[out] = why[done]
            exit_[out] = price[done]
            resolved[out] = sess[col[done]]
            act = act[~done]
            t += 1

        traded = reason > _EXPIRE
        label[traded] = exit_[traded] * (1.0 - COST) / (fill[traded] * (1.0 + COST)) - 1.0

    return Labels(
        label=_readonly(label),
        resolved=_readonly(resolved),
        reason=_readonly(reason),
        fill=_readonly(fill),
        exit=_readonly(exit_),
    )
```
**Impact:** additive; nothing imports it yet (phase 4 will).

### Step 2: Create the tests
**File:** `engine/tests/test_backtest_labels.py:1` (new)
**Change:** the complete file below. It imports `mutate_from` from `tests/stratkit.py` and
`_module_name`, `_pure_sources` from `tests/test_strategy_purity.py` (both read-only; `tests/` is on
`sys.path` as for `simkit`). The parity test defines its own `OnePick` fake strategy rather than
reusing `FixedPicks`, so it does not import `test_backtest_runner` (which would re-execute that
module's scenario constants at import).

Tests (30):
- constants (2): `test_cost_and_reasons_match_the_simulator`, `test_the_purity_glob_covers_the_labeler`
- no fill (3): no bar on S1; `low == limit` (strict); symbol without history
- fills (3): at the limit; at the open when `open < limit`; no exit check on the fill session
- exits (12): TP intraday (with the hand number 0.0978021978…); `high == tp` no exit / `low == sl` exits;
  SL intraday (hand number −0.1017982); both in range → SL; gap through SL; open == SL is a gap; gap through
  TP; day-5 time stop at the open of S6; time stop beats gap/TP on the same bar; a missing bar mid-hold
  still counts; time stop delayed by a missing bar on S6; forced close after the last bar
- edge (4): a halt that resumes is not forced; still open at `end` → unresolved; S1 > end → unresolved;
  bars after `end` never read (forced at the last bar `<= end`)
- shape/validation (3): row independence and input order, dtypes, read-only arrays; empty input;
  malformed input (8 raises)
- parity (3): `test_sim_parity_on_a_seeded_market` (40 symbols × the 2024-01-02..2024-06-28 sessions,
  scattered missing bars, a quarter delisted early, a few late starters, random gaps; ≥ 3,000 compared
  rows; per row one `run_backtest(market, OnePick(d, pick), None, S1, S1+13 sessions, prepared=())`;
  asserts no sizing rejection, same reason with `forced` ⇔ sim `time` + `forced=True`, same
  resolved/expiry date, `fill`/`exit` equal to `float()` of the sim's Decimal prices, label within
  1e-12 of the price formula and within **1e-6 of `pnl_usd / buy_cost`** (the sim's own cash), rows the
  run window does not resolve are unresolved or resolved later, and **all six reasons occur**);
  `test_vectorized_equals_one_row_at_a_time`; `test_changing_bars_after_resolution_leaves_the_label_unchanged`
  (mutates every symbol's bar values from 2024-04-01 on; every row resolved before it is bit-identical,
  > 1,000 such rows; later rows do change)

Prices in the synthetic market are integer ten-thousandths / 1e4, so `Market.bar`'s
`to_decimal(float)` is exact and float comparisons equal the Decimal ones. The test uses
`np.random.default_rng(seed)` (allowed in tests; the module never draws randomness).

**Code:**
```python
"""The vectorized bracket labeler (handover §6.1 "Labels", plan phase 3, requirement R1).

Two halves:

- hand-built bars for every label path, each checked against numbers worked out from design §5
  (``sim.step`` + the runner's forced close) and netted at 0.1% per side;
- sim parity: on a seeded synthetic market, every row's label agrees with ``run_backtest``
  trading that one order alone through a one-pick fake strategy.

Sessions used by the hand-built cases (March 2025, no holidays): data_date 03-03, then
S1 = 03-04, S2 = 03-05, S3 = 03-06, S4 = 03-07, S5 = 03-10, S6 = 03-11, S7 = 03-12,
S8 = 03-13, S9 = 03-14. The bracket is limit 10, tp 11, sl 9 unless a case says otherwise.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from stratkit import mutate_from

from seer_engine import dates
from seer_engine.backtest import labels as labels_mod
from seer_engine.backtest.labels import COST, REASONS, Labels, label_orders
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import run_backtest
from seer_engine.prices import to_decimal
from seer_engine.sim import COST_RATE, Pick, buy_cost
from seer_engine.strategies.base import History

D0 = date(2025, 3, 3)  # data_date
S = [date(2025, 3, d) for d in (4, 5, 6, 7, 10, 11, 12, 13, 14)]  # S[0] = S1 ... S[8] = S9
END = S[-1]

FLAT = (10.5, 10.8, 10.2, 10.5)  # a bar that neither fills (low > 10) nor exits a 10/11/9 bracket
HOLD = (10.2, 10.8, 9.5, 10.5)  # inside the bracket once filled: low > 9, high < 11


def net(fill: float, exit_: float) -> float:
    return exit_ * (1 - 0.001) / (fill * (1 + 0.001)) - 1


def history(symbol: str, bars: Mapping[date, tuple[float, float, float, float]]) -> History:
    days = sorted(bars)
    rows = [bars[d] for d in days]
    return History(
        symbol,
        np.array(days, dtype="datetime64[D]"),
        np.array([r[0] for r in rows], dtype=np.float64),
        np.array([r[1] for r in rows], dtype=np.float64),
        np.array([r[2] for r in rows], dtype=np.float64),
        np.array([r[3] for r in rows], dtype=np.float64),
        np.full(len(rows), 1_000_000.0),
    )


def one(
    bars: Mapping[date, tuple[float, float, float, float]],
    *,
    limit: float = 10.0,
    tp: float = 11.0,
    sl: float = 9.0,
    data_date: date = D0,
    end: date = END,
) -> tuple[str, date | None, float, float, float]:
    """(reason name or "unresolved", resolved date, label, fill, exit) of one order on symbol X."""
    out = label_orders(
        {"X": history("X", bars)},
        ["X"],
        np.array([data_date], dtype="datetime64[D]"),
        np.array([limit]),
        np.array([tp]),
        np.array([sl]),
        end,
    )
    code = int(out.reason[0])
    when = None if np.isnat(out.resolved[0]) else out.resolved[0].item()
    name = "unresolved" if code < 0 else REASONS[code]
    return name, when, float(out.label[0]), float(out.fill[0]), float(out.exit[0])


def filled_on_s1(**later: tuple[float, float, float, float]) -> dict[date, tuple[float, float, float, float]]:
    """D0 flat, S1 fills at the limit 10 (open 10.2, low 9.8, no exit check), then HOLD bars on
    every later session unless ``later`` names it: keys "s2".."s9" set a bar, value None drops it."""
    bars: dict[date, tuple[float, float, float, float]] = {D0: FLAT, S[0]: (10.2, 10.6, 9.8, 10.3)}
    for i in range(1, 9):
        bars[S[i]] = HOLD
    for key, value in later.items():
        d = S[int(key[1:]) - 1]
        if value is None:
            del bars[d]
        else:
            bars[d] = value
    return bars


# --------------------------------------------------------------------------- constants


def test_cost_and_reasons_match_the_simulator():
    assert COST == float(COST_RATE)
    assert REASONS == ("expire", "tp", "sl", "gap", "time", "forced")


def test_the_purity_glob_covers_the_labeler():
    from test_strategy_purity import _module_name, _pure_sources

    assert "seer_engine.backtest.labels" in {_module_name(p) for p in _pure_sources()}
    assert labels_mod.TIME_STOP_DAYS == 5


# --------------------------------------------------------------------------- no fill


def test_no_bar_on_the_order_session_expires():
    name, when, lab, fill, ex = one({D0: FLAT, S[1]: (9.0, 9.5, 8.0, 9.2)})
    assert (name, when, lab) == ("expire", S[0], 0.0)
    assert math.isnan(fill) and math.isnan(ex)


def test_low_at_the_limit_does_not_fill():
    name, when, lab, fill, _ = one({D0: FLAT, S[0]: (10.5, 10.8, 10.0, 10.4)})  # low == limit: strict
    assert (name, when, lab) == ("expire", S[0], 0.0)
    assert math.isnan(fill)


def test_a_symbol_without_history_expires():
    out = label_orders(
        {},
        ["GONE"],
        np.array([D0], dtype="datetime64[D]"),
        np.array([10.0]),
        np.array([11.0]),
        np.array([9.0]),
        END,
    )
    assert REASONS[int(out.reason[0])] == "expire"
    assert out.resolved[0].item() == S[0]
    assert out.label[0] == 0.0


# --------------------------------------------------------------------------- fills


def test_fill_at_the_limit_when_the_open_is_above_it():
    name, when, lab, fill, ex = one(filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2)))
    assert fill == 10.0
    assert (name, when, ex) == ("tp", S[1], 11.0)
    assert lab == net(10.0, 11.0)


def test_fill_at_the_open_when_the_open_is_below_the_limit():
    bars = filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2))
    bars[S[0]] = (9.9, 10.2, 9.6, 10.0)
    name, when, lab, fill, ex = one(bars)
    assert fill == 9.9
    assert (name, when, ex) == ("tp", S[1], 11.0)
    assert lab == net(9.9, 11.0)


def test_no_exit_check_on_the_fill_session():
    bars = filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2))
    bars[S[0]] = (10.2, 12.0, 8.5, 10.0)  # crosses both tp and sl on S1: ignored
    name, when, _, fill, ex = one(bars)
    assert fill == 10.0
    assert (name, when, ex) == ("tp", S[1], 11.0)


# --------------------------------------------------------------------------- exits


def test_take_profit_intraday():
    name, when, lab, _, ex = one(filled_on_s1(s3=(10.5, 11.3, 10.1, 11.0)))
    assert (name, when, ex) == ("tp", S[2], 11.0)
    assert lab == pytest.approx(0.0978021978021978, abs=1e-15)


def test_high_equal_to_tp_does_not_exit_but_low_equal_to_sl_does():
    hold = one(filled_on_s1(s2=(10.5, 11.0, 10.1, 10.9), s3=(10.5, 10.9, 9.0, 9.5)))
    assert hold[:2] == ("sl", S[2])  # high == tp on S2 is no exit (strict >); low == sl on S3 is
    assert hold[4] == 9.0


def test_stop_loss_intraday():
    name, when, lab, _, ex = one(filled_on_s1(s2=(10.0, 10.4, 8.8, 9.1)))
    assert (name, when, ex) == ("sl", S[1], 9.0)
    assert lab == pytest.approx(9.0 * 0.999 / (10.0 * 1.001) - 1, abs=1e-15)
    assert lab == pytest.approx(-0.1017982, abs=1e-7)


def test_both_in_range_takes_the_stop_first():
    name, when, _, _, ex = one(filled_on_s1(s2=(10.0, 11.5, 8.8, 10.0)))
    assert (name, when, ex) == ("sl", S[1], 9.0)


def test_gap_through_the_stop_exits_at_the_open():
    name, when, lab, _, ex = one(filled_on_s1(s2=(8.5, 8.9, 8.2, 8.6)))
    assert (name, when, ex) == ("gap", S[1], 8.5)
    assert lab == net(10.0, 8.5)


def test_open_at_the_stop_is_a_gap():
    name, when, _, _, ex = one(filled_on_s1(s2=(9.0, 9.4, 8.9, 9.2)))
    assert (name, when, ex) == ("gap", S[1], 9.0)


def test_gap_through_the_target_exits_at_the_open():
    name, when, lab, _, ex = one(filled_on_s1(s2=(11.3, 11.6, 11.1, 11.4)))
    assert (name, when, ex) == ("tp", S[1], 11.3)
    assert lab == net(10.0, 11.3)


def test_time_stop_on_day_five_exits_at_the_open_of_s6():
    name, when, lab, _, ex = one(filled_on_s1())
    assert (name, when, ex) == ("time", S[5], 10.2)
    assert lab == net(10.0, 10.2)


def test_time_stop_beats_a_gap_and_a_target_on_the_same_bar():
    name, when, _, _, ex = one(filled_on_s1(s6=(8.0, 12.0, 7.5, 8.5)))
    assert (name, when, ex) == ("time", S[5], 8.0)


def test_a_missing_bar_still_counts_toward_the_time_stop():
    name, when, _, _, ex = one(filled_on_s1(s3=None))  # no bar on S3: days_held still grows
    assert (name, when, ex) == ("time", S[5], 10.2)


def test_time_stop_is_delayed_by_a_missing_bar_on_s6():
    name, when, _, _, ex = one(filled_on_s1(s6=None, s7=(10.3, 10.8, 9.5, 10.5)))
    assert (name, when, ex) == ("time", S[6], 10.3)


def test_forced_close_after_the_last_bar():
    bars = filled_on_s1()
    for i in range(3, 9):  # last bar on S3 (03-06)
        del bars[S[i]]
    bars[S[2]] = (10.2, 10.8, 9.5, 10.4)
    name, when, lab, _, ex = one(bars)
    assert (name, when, ex) == ("forced", S[3], 10.4)  # the session after the last bar, at its close
    assert lab == net(10.0, 10.4)


def test_a_halt_that_resumes_is_not_a_forced_close():
    bars = filled_on_s1(s3=None, s4=None, s5=None)  # bars resume on S6
    name, when, _, _, ex = one(bars)
    assert (name, when, ex) == ("time", S[5], 10.2)


def test_still_open_at_the_end_is_unresolved():
    name, when, lab, fill, ex = one(filled_on_s1(), end=S[3])
    assert (name, when) == ("unresolved", None)
    assert fill == 10.0
    assert math.isnan(lab) and math.isnan(ex)


def test_order_session_after_the_end_is_unresolved():
    name, when, lab, fill, _ = one(filled_on_s1(), data_date=S[3], end=S[3])
    assert (name, when) == ("unresolved", None)
    assert math.isnan(lab) and math.isnan(fill)


def test_bars_after_the_end_are_never_read():
    bars = filled_on_s1()
    for i in range(3, 9):
        del bars[S[i]]
    bars[S[7]] = (20.0, 21.0, 19.0, 20.0)  # a later bar exists, but after end
    name, when, _, _, ex = one(bars, end=S[6])
    assert (name, when, ex) == ("forced", S[3], 10.5)  # the last bar <= end is S3 (HOLD close 10.5)
    assert one(bars, end=S[2])[:2] == ("unresolved", None)


# --------------------------------------------------------------------------- shape and validation


def test_rows_are_independent_and_keep_input_order():
    bars_x = filled_on_s1(s2=(10.4, 11.5, 10.1, 11.2))
    bars_y = filled_on_s1(s2=(10.0, 10.4, 8.8, 9.1))
    h = {"X": history("X", bars_x), "Y": history("Y", bars_y)}
    out = label_orders(
        h,
        ["Y", "X", "Y"],
        np.array([D0, D0, S[3]], dtype="datetime64[D]"),
        np.array([10.0, 10.0, 9.4]),  # row 3: S1 = S5, a HOLD bar whose low 9.5 >= 9.4
        np.array([11.0, 11.0, 11.0]),
        np.array([9.0, 9.0, 8.0]),
        END,
    )
    assert [REASONS[int(r)] for r in out.reason] == ["sl", "tp", "expire"]
    assert out.resolved.tolist() == [S[1], S[1], S[4]]
    assert out.reason.dtype == np.int8 and out.resolved.dtype == np.dtype("datetime64[D]")
    for arr in (out.label, out.resolved, out.reason, out.fill, out.exit):
        assert arr.shape == (3,) and not arr.flags.writeable


def test_empty_input_gives_empty_labels():
    out = label_orders(
        {}, [], np.array([], dtype="datetime64[D]"), np.array([]), np.array([]), np.array([]), END
    )
    assert isinstance(out, Labels)
    assert [a.shape for a in (out.label, out.resolved, out.reason, out.fill, out.exit)] == [(0,)] * 5


def test_malformed_input_is_rejected():
    h = {"X": history("X", filled_on_s1())}
    d = np.array([D0], dtype="datetime64[D]")
    good = (np.array([10.0]), np.array([11.0]), np.array([9.0]))
    with pytest.raises(TypeError):
        label_orders(h, ["X"], d, *good, END.isoformat())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        label_orders(h, ["X"], np.array(["2025-03-03"], dtype="datetime64[s]"), *good, END)
    with pytest.raises(ValueError):
        label_orders(h, ["X", "X"], d, *good, END)
    with pytest.raises(ValueError):
        label_orders(h, ["X"], np.array(["NaT"], dtype="datetime64[D]"), *good, END)
    with pytest.raises(TypeError):
        label_orders(h, ["X"], d, np.array([10], dtype=np.int64), good[1], good[2], END)
    with pytest.raises(ValueError):
        label_orders(h, ["X"], d, np.array([np.nan]), good[1], good[2], END)
    with pytest.raises(ValueError):
        label_orders(h, ["X"], d, np.array([10.0]), np.array([11.0]), np.array([10.0]), END)  # sl == limit
    with pytest.raises(ValueError):
        label_orders(h, ["X"], d, np.array([10.0]), np.array([10.0]), np.array([9.0]), END)  # tp == limit


# --------------------------------------------------------------------------- sim parity

PARITY_SEED = 20261003
PARITY_DAYS = dates.sessions(date(2024, 1, 2), date(2024, 6, 28))
PARITY_SYMBOLS = tuple(f"S{i:02d}" for i in range(40))
RUN_SESSIONS = 14  # each sim run covers S1 and the next 13 sessions; later resolutions are skipped


def _ticks(x: np.ndarray) -> np.ndarray:
    """Prices as exact 4-dp floats (integer ten-thousandths / 1e4: the float's repr is the 4-dp value)."""
    return np.maximum(np.round(x * 10_000.0), 10_000.0) / 10_000.0


def _parity_market(seed: int = PARITY_SEED) -> Market:
    rng = np.random.default_rng(seed)
    n = len(PARITY_DAYS)
    hist: dict[str, History] = {}
    for i, s in enumerate(PARITY_SYMBOLS):
        gap = np.where(rng.random(n) < 0.06, rng.normal(0.0, 0.06, n), 0.0)
        body = rng.normal(0.0, 0.025, n)
        close = np.empty(n)
        open_ = np.empty(n)
        prev = rng.uniform(20.0, 80.0)
        for t in range(n):
            open_[t] = prev * (1.0 + gap[t])
            close[t] = open_[t] * (1.0 + body[t])
            prev = close[t]
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.012, n)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.012, n)))
        keep = rng.random(n) > 0.05  # scattered missing bars
        if i % 4 == 0:  # a quarter of the symbols stop trading before the data end
            keep[int(rng.integers(n // 3, n - 5)):] = False
        if i % 7 == 3:  # a few start late
            keep[: int(rng.integers(5, 30))] = False
        days = np.array(PARITY_DAYS, dtype="datetime64[D]")[keep]
        o, h, lo, c = _ticks(open_[keep]), _ticks(high[keep]), _ticks(low[keep]), _ticks(close[keep])
        h = np.maximum(h, np.maximum(o, c))
        lo = np.minimum(lo, np.minimum(o, c))
        hist[s] = History(s, days, o, h, lo, c, np.full(days.shape[0], 1_000_000.0))
    return Market(history=hist, membership=Membership(()), fx=((date(2023, 12, 1), Decimal("16000")),))


def _parity_rows(market: Market, seed: int = PARITY_SEED) -> list[tuple[str, date, Pick]]:
    """One row per (symbol, bar date) except the data end: a 4-dp bracket off that close."""
    rng = np.random.default_rng(seed + 1)
    rows: list[tuple[str, date, Pick]] = []
    for s in PARITY_SYMBOLS:
        h = market.history[s]
        for d, c in zip(h.dates.tolist(), h.close.tolist()):
            if d >= PARITY_DAYS[-1]:
                continue
            atr = c * float(rng.uniform(0.01, 0.06))
            last = to_decimal(c)
            lim = to_decimal(c - 0.5 * atr)
            rows.append((s, d, Pick(s, last, lim, to_decimal(float(lim) + atr), to_decimal(float(lim) - 1.5 * atr))))
    return rows


class OnePick:
    """A fake ``Strategy`` that places one pick for one data_date and nothing else."""

    id = "ONE"
    lookback = 1

    def __init__(self, data_date: date, pick: Pick):
        self.data_date = data_date
        self.pick = pick

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
              params: Any) -> list[Pick]:
        return [self.pick] if data_date == self.data_date else []

    def prepare(self, history: Mapping[str, History]) -> Any:
        return ()

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                       params: Any) -> list[Pick]:
        return [self.pick] if data_date == self.data_date else []


def _label_rows(market: Market, rows: list[tuple[str, date, Pick]]) -> Labels:
    return label_orders(
        market.history,
        [s for s, _, _ in rows],
        np.array([d for _, d, _ in rows], dtype="datetime64[D]"),
        np.array([float(p.limit_price) for _, _, p in rows]),
        np.array([float(p.tp_price) for _, _, p in rows]),
        np.array([float(p.sl_price) for _, _, p in rows]),
        PARITY_DAYS[-1],
    )


def test_sim_parity_on_a_seeded_market():
    market = _parity_market()
    rows = _parity_rows(market)
    assert len(rows) >= 3000
    out = _label_rows(market, rows)
    data_end = PARITY_DAYS[-1]
    seen: set[str] = set()
    compared = 0
    for i, (s, d, p) in enumerate(rows):
        s1 = dates.next_session(d)
        stop = PARITY_DAYS[min(PARITY_DAYS.index(s1) + RUN_SESSIONS - 1, len(PARITY_DAYS) - 1)]
        run = run_backtest(market, OnePick(d, p), None, s1, stop, prepared=())
        assert run.rejections == ()
        code = int(out.reason[i])
        terminal = [e for e in run.events if e.kind in ("expire", "exit")]
        if not terminal:
            # still open after the run window: the labeler resolves it later or never
            assert code == -1 or out.resolved[i].item() > stop, (s, d)
            if stop == data_end:
                assert code == -1, (s, d)
            continue
        compared += 1
        (event,) = terminal
        if event.kind == "expire":
            assert (REASONS[code], out.resolved[i].item(), float(out.label[i])) == ("expire", s1, 0.0), (s, d)
            assert math.isnan(out.fill[i]), (s, d)
            seen.add("expire")
            continue
        order = event.order
        want = "forced" if event.forced else order.exit_reason
        if event.forced:
            assert order.exit_reason == "time", (s, d)
        assert REASONS[code] == want, (s, d, REASONS[code], want)
        assert out.resolved[i].item() == order.exit_date, (s, d)
        assert float(out.fill[i]) == float(order.fill_price), (s, d)
        assert float(out.exit[i]) == float(order.exit_price), (s, d)
        by_price = float(order.exit_price) * (1 - COST) / (float(order.fill_price) * (1 + COST)) - 1
        by_cash = float(order.pnl_usd / buy_cost(order.fill_price, order.shares))
        assert abs(float(out.label[i]) - by_price) <= 1e-12, (s, d)
        assert abs(float(out.label[i]) - by_cash) <= 1e-6, (s, d)
        seen.add(want)
    assert compared >= 3000
    assert seen == set(REASONS)  # the sample exercises every path


def test_vectorized_equals_one_row_at_a_time():
    market = _parity_market()
    rows = _parity_rows(market)[::37]
    together = _label_rows(market, rows)
    for i, row in enumerate(rows):
        alone = _label_rows(market, [row])
        assert alone.reason[0] == together.reason[i]
        assert alone.resolved[0] == together.resolved[i] or (np.isnat(alone.resolved[0]) and np.isnat(together.resolved[i]))
        for name in ("label", "fill", "exit"):
            a, b = getattr(alone, name)[0], getattr(together, name)[i]
            assert a == b or (math.isnan(a) and math.isnan(b)), (row[0], row[1], name)


def test_changing_bars_after_resolution_leaves_the_label_unchanged():
    market = _parity_market()
    rows = _parity_rows(market)
    before = _label_rows(market, rows)
    cut = date(2024, 4, 1)
    mutated = Market(
        history={s: mutate_from(h, cut, lambda x: x * 1.7 + 3.0) for s, h in market.history.items()},
        membership=market.membership,
        fx=market.fx,
    )
    after = _label_rows(mutated, rows)
    early = ~np.isnat(before.resolved) & (before.resolved < np.datetime64(cut, "D"))
    assert int(early.sum()) > 1000
    assert np.array_equal(before.reason[early], after.reason[early])
    assert np.array_equal(before.resolved[early], after.resolved[early])
    for name in ("label", "fill", "exit"):
        b, a = getattr(before, name)[early], getattr(after, name)[early]
        assert np.array_equal(b, a, equal_nan=True), name
    late = ~early & (before.reason >= 0)
    assert not np.array_equal(before.label[late], after.label[late], equal_nan=True)  # the cut does bite later
```
**Impact:** +30 tests. Measured on a scratch copy of the tree (numpy 2.4.6): the file runs in about
1.7 s, the parity test about 0.9 s.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.backtest.labels as m; print(m.REASONS, m.COST)"`
**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_backtest_labels.py engine/tests/test_strategy_purity.py -q` → 33 passed
- `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
  → **791 passed, 0 skipped** on this phase alone (761 baseline + 30). In the reconciled set the total
  is 761 + this phase's 30 + the other phases' additions.
- `git diff --stat 0e91d8a -- engine/src/seer_engine/sim engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/market.py engine/src/seer_engine/strategies engine/tests/test_*.py ':!engine/tests/test_backtest_labels.py'` → empty.

**Manual check:** none needed; optionally time one call on a ~1.3M-row synthetic input (expect well
under 1 s; measured 0.40 s).
**Exit criteria:** `labels.py` and `test_backtest_labels.py` exist exactly as above; the suite is green
with 0 skipped and 30 more tests than before; the purity glob lists `seer_engine.backtest.labels`; no
out-of-scope file differs from `0e91d8a`.

## Handoffs

- **Phase 4 (R1 purge, R4):** call `label_orders` only on rows with a valid bracket (it raises
  ValueError otherwise) and scatter into the full `CandidateTable` arrays. Pass `symbols` as a tuple/list
  of str (one per row, ~1.3M: the call costs ~0.4 s). `Labels` arrays are read-only: copy before writing.
  `training_mask` reads `labels.resolved` (NaT for unresolved, so `resolved <= tune_end` is False there).
- **Phase 4 purge test (R1 third clause):** mutate bar **values** after `tune_end(Y)`, not add/delete
  bars. A forced-close label depends on the *absence* of bars through `end` (the runner's own rule), so
  appending a bar after `tune_end` for a symbol whose bars had stopped can legitimately change a
  forced label resolved before `tune_end`. Mutation of values provably leaves it unchanged (tested here).
- **Phase 4:** pass `end` equal to the market's data end (resolve's default) for labels to equal the
  runner bit-for-bit on forced closes; an earlier `end` is point-in-time at `end` (documented above).
- **Phase 5/7 (docs, R7/R9):** the readme's labeler paragraph can quote the semantics block of the module
  docstring and the 0.40 s / 1.34M-row timing.

## Rollback

Delete `engine/src/seer_engine/backtest/labels.py` and `engine/tests/test_backtest_labels.py` (or
revert this phase's commit). Nothing else references them until phase 4.
