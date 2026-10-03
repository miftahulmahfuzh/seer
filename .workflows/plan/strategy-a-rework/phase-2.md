# Phase 2: Runner params schedule, `metrics_through`, `select` fallback

**Plan set:** `STRATEGY_A_REWORK_PLAN.md`
**Analysis:** `20261003-160830-R4W9_code_analyzer.md`
**Satisfies:** R3 (schedule switching by year; brackets survive the switch; the prefix property that lets each fold's selection see only its tuning window; the fallback hook), R8 (the v1 path is provably unchanged: plain-params `run_backtest` and `select(rows)` behave exactly as on `e14de0c`)
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase, `run_backtest` accepts a `ParamsSchedule` as `params` and trades session S with
`params.at(S)`, keyed by the traded session rather than by `data_date`. Every other `params` value
takes the `e14de0c` path unchanged. `metrics.metrics_through(r, end)` returns a long run's metrics cut
at a session, and tests prove it equals the metrics of a run that stops at that session, forced
closes included. `tuning.select` takes a keyword-only `fallback=` (default `DESIGN_PARAMS`).
Phase 3 (walk-forward) needs all three.

All code below was prototyped against a scratch copy of the worktree. The three touched test files
went from 54 to 67 tests, all passing, and the purity test passed.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.backtest.runner.ParamsSchedule` (`backtest/runner.py`, inserted before `run_backtest`):
  `@dataclass(frozen=True)` with one field, `segments: tuple[tuple[date, Any], ...]`, and one method,
  `at(session: date) -> Any`.
  - `__post_init__` accepts any non-str iterable of 2-item sequences and stores them as a tuple of
    2-tuples, so `ParamsSchedule([[d, p]]) == ParamsSchedule(((d, p),))`.
  - **TypeError** when: `segments` is a str or is not iterable; an item is not a pair; a first
    session is not a `date`, or is a `datetime`; or a segment's params is itself a `ParamsSchedule`.
  - **ValueError** when: there are no segments; a first session is not an NYSE session; or first
    sessions are not strictly ascending.
  - `at(s)` returns the params of the last segment whose first session is `<= s`. It does not require
    `s` to be a session. ValueError when `s < segments[0][0]`; TypeError when `s` is not a `date` or is
    a `datetime`.
- `seer_engine.backtest.metrics.metrics_through(r: RunResult, end: date) -> Metrics` (`backtest/metrics.py`,
  inserted after `run_metrics`).
  - TypeError when `r` is not a `RunResult`, or `end` is not a `date` or is a `datetime`.
  - ValueError when `end` is not a session, or `not r.start <= end <= r.end`.
  - Keeps the snapshots dated `<= end` and the events with `session_date <= end`. Closed orders are
    those events' `exit` orders, in event order.
  - It is computed as `run_metrics(replace(r, end=end, snapshots=..., events=..., closed=...))`, so it
    takes `run_metrics`' exact code path. `open_at_end` is not recomputed. `run_metrics` never reads
    it, and the replaced `RunResult` is never returned.
- Test helpers in `tests/test_backtest_runner.py`, importable by later phases' tests:
  - `ParamPicks(tables)`, a fake strategy whose picks are `tables[params][data_date]`. It records
    `seen: list[(data_date, params)]`.
  - `TABLE_B` and `SWITCH = date(2025, 3, 7)`.
  - `smoke_market(cut: date | None = None) -> (Market, start, end)`: the existing Strategy A smoke
    market, with UPC's bars optionally truncated after `cut`.

**Signature changes:**
- `tuning.select(rows: Sequence[GridRow]) -> Selection` becomes
  `tuning.select(rows: Sequence[GridRow], *, fallback: Any = DESIGN_PARAMS) -> Selection`.
  The rule, tie-breaks and reason strings are unchanged. When nothing qualifies, it returns
  `Selection(params=fallback, qualified=False, reason=<same words as today>)`.
- `run_backtest(market, strategy, params, start, end, *, prepared=None, initial_idr=INITIAL_IDR)`: the
  **signature is unchanged**. Its behaviour changes only when `isinstance(params, ParamsSchedule)`:
  - ValueError if `start < params.segments[0][0]`. This check runs after the existing start/end checks
    and before any FX lookup.
  - Picks for session S use `params.at(S)`.
  - `RunResult.params` is the schedule object.

**Requires (from earlier phases):** nothing. Phase 2 is independent of phase 1.

**Provides to later phases:**
- Phase 3 calls:
  - `run_backtest(..., ParamsSchedule(((f.trade_start, sel.params) for each fold)), ...)`;
  - `metrics_through(run, f.tune_end)`;
  - `tuning.select(rows, fallback=...)`.
- `metrics_through` cuts a run but does not re-validate it. It assumes `r` came from `run_backtest`,
  as its docstring says.
- **Existing test helpers stay importable and unchanged.** Phase 3's tests do
  `from test_backtest_runner import START, run_scenario`, and this phase's own metrics tests import
  `START`, `END`, `TABLE`, `FixedPicks` and `scenario_market`. Step 4 only replaces the import block
  and appends after line 374; it never edits `pick`, `FixedPicks`, `BARS`, `INTERVALS`, `FX`,
  `TABLE`, `scenario_market`, `run_scenario`, `START`/`END` or `_smoke_bars`. The hand-checked
  scenario numbers phase 3 relies on (`test_diagnostics_of_the_runner_scenario`,
  `test_window_metrics_slice_hand_checked`) therefore stay valid.

**Leaves alone (owned by others):**
- `strategies/*`, including `a2.py` (phase 1).
- `backtest/walkforward.py` (phase 3), `backtest/wf_report.py` (phase 4), `backtest/io.py` and
  `commands/*` (phase 5).
- `backtest/report.py`, `sim/*`, docs (phase 6, and the Law).
- The type annotations `GridRow.params: AParams` and `Selection.params: AParams` in `tuning.py` stay
  as they are. They have no runtime effect. See Handoffs.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/runner.py` | modify | import `bisect_right` (line 23); new `ParamsSchedule` between `_session` (ends line 77) and `run_backtest` (line 80); `run_backtest` docstring paragraph (line 97), schedule check after line 103, per-session params in the loop (lines 114–119) |
| `engine/src/seer_engine/backtest/metrics.py` | modify | import `datetime` (line 21) and `seer_engine.dates` (line 24); new `metrics_through` between `run_metrics` (ends line 153) and `curve_metrics` (line 156) |
| `engine/src/seer_engine/backtest/tuning.py` | modify | import `Any` (after line 13); `select` signature, docstring and fallback (lines 77–87) |
| `engine/tests/test_backtest_runner.py` | modify | imports (lines 20–30); new tests and helpers appended after line 374 |
| `engine/tests/test_backtest_metrics.py` | modify | imports (lines 6–32); new tests appended after line 296 |
| `engine/tests/test_backtest_tuning.py` | modify | new test before `test_select_is_deterministic` (line 127); **the existing structural guard at lines 175–181 must be updated** because it asserts `select`'s parameter list is exactly `["rows"]` |

## Implementation Steps

### Step 0: Worktree venv (only if absent)
**File:** none. Run from `/home/miftah/.worktrees/seer/strategy-a-rework`.
**Change:** create the worktree's own venv. Never use `/home/miftah/seer/engine/.venv`, which tests main's tree.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/strategy-a-rework
test -x engine/.venv/bin/python || { python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'; }
engine/.venv/bin/python -c "import seer_engine, sys; print(seer_engine.__file__)"   # must print a path under the worktree
docker start seer-pg
```
**Impact:** none on the tree.

### Step 1: `ParamsSchedule` and the schedule branch in `run_backtest`
**File:** `engine/src/seer_engine/backtest/runner.py`

**1a. Import** (line 23, above `from collections import Counter`):
```python
from bisect import bisect_right
from collections import Counter
```

**1b. New class**, inserted between `_session` (ends line 77) and `def run_backtest(` (line 80):
```python
@dataclass(frozen=True)
class ParamsSchedule:
    """Strategy params that change by traded session (P3b walk-forward, Decision D1/D6).

    ``segments[i] = (first_session_i, params_i)``: ``params_i`` is used for every traded session
    from ``first_session_i`` up to the session before ``first_session_{i+1}`` (the last segment
    runs to the end of the window). First sessions are NYSE sessions, strictly ascending, and
    there is at least one segment. A list or other sequence is accepted and stored as a tuple
    of 2-tuples. A segment's params may not itself be a ``ParamsSchedule``.
    """

    segments: tuple[tuple[date, Any], ...]

    def __post_init__(self) -> None:
        raw = self.segments
        if isinstance(raw, (str, bytes)) or not hasattr(raw, "__iter__"):
            raise TypeError(f"segments must be a sequence of (date, params), got {type(raw).__name__}")
        segments: list[tuple[date, Any]] = []
        for i, seg in enumerate(raw):
            if isinstance(seg, (str, bytes)) or not hasattr(seg, "__len__") or len(seg) != 2:
                raise TypeError(f"segments[{i}] must be a (first_session, params) pair")
            first, params = seg[0], seg[1]
            _session(f"segments[{i}] first session", first)
            if isinstance(params, ParamsSchedule):
                raise TypeError(f"segments[{i}] params must not be a ParamsSchedule")
            if segments and first <= segments[-1][0]:
                raise ValueError(
                    f"segments[{i}] first session {first} is not after segments[{i - 1}] ({segments[-1][0]})"
                )
            segments.append((first, params))
        if not segments:
            raise ValueError("a ParamsSchedule needs at least one segment")
        object.__setattr__(self, "segments", tuple(segments))

    def at(self, session: date) -> Any:
        """The params of the last segment whose first session is ``<= session``.

        ``session`` must be a ``date`` (not a ``datetime``); ValueError when it is before the
        first segment's first session.
        """
        if isinstance(session, datetime) or not isinstance(session, date):
            raise TypeError(f"session must be a date, got {type(session).__name__}")
        i = bisect_right([first for first, _ in self.segments], session)
        if i == 0:
            raise ValueError(f"session {session} is before the schedule's first session {self.segments[0][0]}")
        return self.segments[i - 1][1]
```

**1c. Full replacement of `run_backtest`** (lines 80–155):
```python
def run_backtest(
    market: Market,
    strategy: Strategy,
    params: Any,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
) -> RunResult:
    """Run ``strategy`` with ``params`` on a fresh portfolio over every session in ``[start, end]``.

    ``start`` and ``end`` must be NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, market.usd_idr_on(start))``. With ``prepared`` (the value of
    ``strategy.prepare(market.history)``), picks come from ``strategy.picks_prepared``;
    without it, from ``strategy.picks`` on every history cut at ``data_date``. The strategy
    contract makes both give the same result.

    ``params`` may be a ``ParamsSchedule``: then ``start`` must not be before its first
    segment, and the picks for session S use ``params.at(S)``, keyed by the session being
    traded, not by ``data_date``. Orders keep the bracket they were placed with; the simulator
    never rewrites one. ``RunResult.params`` is the schedule itself. Any other ``params`` value
    is handed to the strategy unchanged for every session.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    schedule = params if isinstance(params, ParamsSchedule) else None
    if schedule is not None and start < schedule.segments[0][0]:
        raise ValueError(f"start {start} is before the schedule's first session {schedule.segments[0][0]}")
    usd_idr = market.usd_idr_on(start)
    cash0 = initial_cash_usd(initial_idr, usd_idr)

    pf = new_portfolio(cash0)
    data_date = dates.prev_session(start)
    snapshots: list[Snapshot] = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()

    for session in dates.sessions(start, end):
        members = market.membership.members_on(data_date)
        session_params = params if schedule is None else schedule.at(session)
        if prepared is None:
            history = {s: h.upto(data_date) for s, h in market.history.items()}
            picks = strategy.picks(history, members, data_date, session_params)
        else:
            picks = strategy.picks_prepared(prepared, members, data_date, session_params)

        sized = size_picks(pf, picks, session)
        for r in sized.rejected:
            rejections[r.reason] += 1
        pf = sized.portfolio

        result = step(pf, session, market.bars_on(session, pf.held_symbols()))
        pf = result.portfolio
        events.extend(result.events)
        snapshots.append(result.snapshot)

        gone = []
        for o in pf.open_orders():
            last = market.last_bar_date(o.symbol)
            if last is None or last < session:
                gone.append(o.symbol)
        if gone:
            pf, forced = close_unpriced(pf, gone)
            events.extend(forced)
            snapshots[-1] = Snapshot(session, pf.cash, pf.equity)

        data_date = session

    return RunResult(
        strategy_id=strategy.id,
        params=params,
        start=start,
        end=end,
        usd_idr=usd_idr,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        events=tuple(events),
        closed=tuple(e.order for e in events if e.kind == "exit"),
        open_at_end=pf.open_orders(),
        rejections=tuple(sorted(rejections.items())),
    )
```
**Impact:**
- With non-schedule params, `session_params is params` on every session, so the v1 path is
  unchanged in behaviour (R8, invariant 3).
- `RunResult.params` is still the object that was passed in.
- The module stays pure: `bisect` is not on the purity test's forbidden list.

### Step 2: `metrics_through`
**File:** `engine/src/seer_engine/backtest/metrics.py`

**2a. Imports** (lines 18–26 become):
```python
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.runner import RunResult
from seer_engine.sim import Order
```

**2b. New function**, inserted after `run_metrics` (ends line 153) and before `curve_metrics` (line 156):
```python
def metrics_through(r: RunResult, end: date) -> Metrics:
    """``run_metrics`` of ``r`` cut at the session ``end``.

    Keeps the snapshots dated ``<= end`` and the orders whose exit event has
    ``session_date <= end``, in event order. A forced close (``close_unpriced``) is dated the
    session it happens on, so one on the session after ``end`` is left out, as it would be
    in a run that stops at ``end``. ``end`` must be an NYSE session with
    ``r.start <= end <= r.end``.

    Prefix property: the runner's loop never reads ``end`` except to bound its sessions, so
    this equals ``run_metrics(run_backtest(<same market, strategy, params, start, prepared>,
    end=end))``.
    """
    if not isinstance(r, RunResult):
        raise TypeError(f"r must be a RunResult, got {type(r).__name__}")
    if isinstance(end, datetime) or not isinstance(end, date):
        raise TypeError(f"end must be a date, got {type(end).__name__}")
    if not dates.is_session(end):
        raise ValueError(f"end {end} is not an NYSE session")
    if not r.start <= end <= r.end:
        raise ValueError(f"end {end} is outside the run's window [{r.start}, {r.end}]")
    snapshots = tuple(s for s in r.snapshots if s.date <= end)
    events = tuple(e for e in r.events if e.session_date <= end)
    closed = tuple(e.order for e in events if e.kind == "exit")
    return run_metrics(replace(r, end=end, snapshots=snapshots, events=events, closed=closed))
```
**Impact:**
- This is purely additive. `run_metrics` is not edited.
- `seer_engine.dates` is pure. It is already imported by the pure `runner.py`, so the purity test
  still passes.
- Why the cut is exact:
  - Snapshot 0 is dated `prev_session(start)` and is always kept.
  - Each session has exactly one snapshot, and a forced close replaces that session's snapshot rather
    than adding one.
  - A `close_unpriced` exit event carries `session_date = portfolio.last_session` (`sim/lifecycle.py:208–249`),
    which is the session it was forced on.

### Step 3: `select(..., fallback=)`
**File:** `engine/src/seer_engine/backtest/tuning.py`

**3a. Import** (after line 13 `from decimal import Decimal`):
```python
from typing import Any
```

**3b. Full replacement of `select`** (lines 77–109):
```python
def select(rows: Sequence[GridRow], *, fallback: Any = DESIGN_PARAMS) -> Selection:
    """The qualifying row with the highest in-sample total return.

    Ties go to the lower max drawdown, then to the earlier grid index. When no row qualifies,
    ``fallback`` (by default ``DESIGN_PARAMS``) is kept with ``qualified=False``; the reason
    string is the same whatever the fallback is. ``fallback`` is returned as given, never
    copied or checked.
    """
    n = len(rows)
    candidates = [(i, row) for i, row in enumerate(rows) if qualifies(row.metrics)]
    if not candidates:
        return Selection(
            params=fallback,
            qualified=False,
            reason=(
                f"No in-sample grid run had max drawdown ≤ 15% and profit factor ≥ 1.3 (0 of {n}), "
                "so the design values are kept."
            ),
        )
    best_i, best = min(
        candidates,
        key=lambda c: (-c[1].metrics.total_return, c[1].metrics.max_drawdown, c[0]),
    )
    tied = 0
    for _, row in candidates:
        if row.metrics.total_return == best.metrics.total_return:
            tied += 1
    reason = (
        f"Grid run #{best_i + 1} has the highest in-sample total return "
        f"({fmt_signed_pct(best.metrics.total_return)}, max drawdown {fmt_pct(best.metrics.max_drawdown)}) "
        f"among the {len(candidates)} of {n} runs with max drawdown ≤ 15% and profit factor ≥ 1.3"
    )
    if tied > 1:
        reason += f"; {tied} runs tied on return, broken by the lower max drawdown, then grid order"
    return Selection(params=best.params, qualified=True, reason=reason + ".")
```
**Impact:**
- `commands/backtest.py` calls `select(rows)` and gets exactly what it got before. The v1 report
  re-renders byte-identically (R8).
- The reason string still says "the design values are kept" for any fallback. That holds for the
  walk-forward's fallbacks too: `A2_DESIGN_PARAMS` and `A2Params(variant=v)` both carry the design
  values (Decision D7).

### Step 4: Runner tests
**File:** `engine/tests/test_backtest_runner.py`

**4a. Imports** (lines 20–30 become):
```python
from collections.abc import Mapping, Set as AbstractSet
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from simkit import D, P, bar

from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import (
    INITIAL_IDR,
    ParamsSchedule,
    RunResult,
    YearGap,
    run_backtest,
    survivorship,
)
```
(Lines 31–34 are unchanged: `from seer_engine.prices import Bar`, `from seer_engine.sim import Pick, Snapshot`,
`from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A`, `from seer_engine.strategies.base import History, history_from_bars`.)

**4b. Append** after the last line (374, end of `test_strategy_a_smoke_prepared_equals_plain`):
```python


# --------------------------------------------------------------------------- params schedule (P3b)


class ParamPicks(FixedPicks):
    """``FixedPicks`` whose table is chosen by ``params``: ``tables[params][data_date]``.

    Records ``(data_date, params)`` for every call, so a test can see which params the runner
    handed over for which session.
    """

    id = "PARAM"

    def __init__(self, tables: Mapping[str, Mapping[date, tuple[Pick, ...]]]):
        super().__init__({})
        self.tables = {k: dict(v) for k, v in tables.items()}
        self.seen: list[tuple[date, Any]] = []

    def _for(self, members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        self.seen.append((data_date, params))
        return [p for p in self.tables[params].get(data_date, ()) if p.symbol in members]

    def picks(self, history: Mapping[str, History], members: AbstractSet[str],
              data_date: date, params: Any) -> list[Pick]:
        return self._for(members, data_date, params)

    def picks_prepared(self, prepared: Any, members: AbstractSet[str],
                       data_date: date, params: Any) -> list[Pick]:
        return self._for(members, data_date, params)


# "b" differs from TABLE only for data_date 03-06 (session 03-07): DDD at limit 5.1, which the
# 03-07 bar (o 5.1, l 5.05) fills at min(5.1, 5.1) = 5.1. Under TABLE's limit 5 it expires.
TABLE_B = {**TABLE, D("2025-03-06"): (pick("DDD", "5.1", "6", "4"),)}
SWITCH = D("2025-03-07")  # first traded session of segment "b"; its data_date is 03-06


def test_params_schedule_validates_its_segments():
    s = ParamsSchedule(((START, "a"), (SWITCH, "b")))
    assert s.segments == ((START, "a"), (SWITCH, "b"))
    assert ParamsSchedule([[START, "a"], [SWITCH, "b"]]) == s  # sequences are stored as tuples
    with pytest.raises(ValueError):
        ParamsSchedule(())  # empty
    with pytest.raises(ValueError):
        ParamsSchedule(((SWITCH, "b"), (START, "a")))  # descending
    with pytest.raises(ValueError):
        ParamsSchedule(((START, "a"), (START, "b")))  # not strictly ascending
    with pytest.raises(ValueError):
        ParamsSchedule(((D("2025-03-08"), "a"),))  # a Saturday
    with pytest.raises(ValueError):
        ParamsSchedule(((START, "a"), (D("2025-03-09"), "b")))  # a Sunday, second segment
    with pytest.raises(TypeError):
        ParamsSchedule(((datetime(2025, 3, 4), "a"),))
    with pytest.raises(TypeError):
        ParamsSchedule(((START,),))  # not a pair
    with pytest.raises(TypeError):
        ParamsSchedule("ab")
    with pytest.raises(TypeError):
        ParamsSchedule(((START, s),))  # no nesting


def test_params_schedule_at_takes_the_last_segment_started_on_or_before():
    s = ParamsSchedule(((START, "a"), (SWITCH, "b"), (D("2025-03-12"), "c")))
    assert s.at(START) == "a"
    assert s.at(D("2025-03-06")) == "a"
    assert s.at(SWITCH) == "b"
    assert s.at(D("2025-03-08")) == "b"  # any date is looked up, sessions or not
    assert s.at(D("2025-03-11")) == "b"
    assert s.at(D("2025-03-12")) == "c"
    assert s.at(D("2030-01-02")) == "c"
    with pytest.raises(ValueError):
        s.at(D("2025-03-03"))  # before the first segment
    with pytest.raises(TypeError):
        s.at(datetime(2025, 3, 7))


def test_schedule_run_rejects_a_start_before_the_first_segment():
    sched = ParamsSchedule(((D("2025-03-05"), "a"),))
    with pytest.raises(ValueError):
        run_backtest(scenario_market(), ParamPicks({"a": TABLE}), sched, START, END)
    # Starting on or after the first segment is fine.
    r = run_backtest(scenario_market(), ParamPicks({"a": TABLE}), sched, D("2025-03-05"), END)
    assert r.params is sched


@pytest.mark.parametrize("prepared", [False, True])
def test_schedule_params_are_keyed_by_the_traded_session_not_data_date(prepared):
    market = scenario_market()
    strategy = ParamPicks({"a": TABLE, "b": TABLE_B})
    sched = ParamsSchedule(((START, "a"), (SWITCH, "b")))
    prep = strategy.prepare(market.history) if prepared else None
    r = run_backtest(market, strategy, sched, START, END, prepared=prep)

    sessions = dates.sessions(START, END)
    assert strategy.seen == [
        (dates.prev_session(s), "a" if s < SWITCH else "b") for s in sessions
    ]
    # Session 03-07 is traded with "b" although its data_date (03-06) is before the switch.
    assert (D("2025-03-06"), "b") in strategy.seen
    on_switch = [(e.kind, e.order.symbol, e.order.limit_price) for e in r.events if e.session_date == SWITCH]
    assert on_switch == [("fill", "DDD", P("5.1"))]
    assert r.params is sched

    # The same run with plain "a" lets DDD expire on 03-07: the switch is what changed it.
    plain = run_backtest(scenario_market(), ParamPicks({"a": TABLE, "b": TABLE_B}), "a", START, END)
    assert [(e.kind, e.order.symbol) for e in plain.events if e.session_date == SWITCH] == [("expire", "DDD")]


def test_an_order_open_across_the_switch_keeps_its_bracket():
    # CCC is placed under "a" (data_date 03-05, session 03-06) with tp 55 / sl 45 and is still
    # open on the switch session 03-07. Under "b" nothing re-brackets it: it exits at its own
    # sl 45 on 03-10, exactly as in the plain "a" run.
    sched = ParamsSchedule(((START, "a"), (SWITCH, "b")))
    r = run_backtest(scenario_market(), ParamPicks({"a": TABLE, "b": TABLE_B}), sched, START, END)
    plain = run_backtest(scenario_market(), ParamPicks({"a": TABLE, "b": TABLE_B}), "a", START, END)
    ccc = [o for o in r.closed if o.symbol == "CCC"]
    assert len(ccc) == 1
    c = ccc[0]
    assert c.session_date < SWITCH < c.exit_date
    assert (c.limit_price, c.tp_price, c.sl_price) == (P("50"), P("55"), P("45"))
    assert (c.exit_date, c.exit_price, c.exit_reason) == (D("2025-03-10"), P("45"), "sl")
    assert c == [o for o in plain.closed if o.symbol == "CCC"][0]


def test_one_segment_schedule_equals_the_plain_run_but_for_params():
    sched = ParamsSchedule(((START, None),))
    for prepared in (False, True):
        market = scenario_market()
        strategy = FixedPicks(TABLE)
        prep = strategy.prepare(market.history) if prepared else None
        with_sched = run_backtest(market, strategy, sched, START, END, prepared=prep)
        plain = run_backtest(market, FixedPicks(TABLE), None, START, END, prepared=prep)
        assert with_sched.params is sched
        assert replace(with_sched, params=None) == plain


def test_one_segment_schedule_equals_the_plain_run_on_the_strategy_a_smoke_market():
    market, start, end = smoke_market()
    prepared = STRATEGY_A.prepare(market.history)
    sched = ParamsSchedule(((start, DESIGN_PARAMS),))
    with_sched = run_backtest(market, STRATEGY_A, sched, start, end, prepared=prepared)
    plain = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared)
    assert any(e.kind == "exit" for e in plain.events)
    assert replace(with_sched, params=DESIGN_PARAMS) == plain


def smoke_market(cut: date | None = None) -> tuple[Market, date, date]:
    """The Strategy A smoke market of ``test_strategy_a_smoke_prepared_equals_plain``; with
    ``cut``, UPC's bars stop at ``cut`` (it is "delisted" after it)."""
    sessions = dates.sessions(D("2024-01-02"), D("2025-03-31"))
    history = {}
    for s, phase in (("UPA", 0), ("UPB", 7), ("UPC", 13)):
        bars = _smoke_bars(s, sessions, phase)
        if s == "UPC" and cut is not None:
            bars = [b for b in bars if b.date <= cut]
        history[s] = history_from_bars(s, bars)
    market = Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2023-12-29"), Decimal("16000")),),
    )
    return market, sessions[200], sessions[-1]
```
**Impact:** 8 new test items. `test_schedule_params_are_keyed_by_the_traded_session_not_data_date`
is parametrized ×2, so this is 7 functions. Existing tests are untouched.

### Step 5: `metrics_through` tests
**File:** `engine/tests/test_backtest_metrics.py`

**5a. Imports** (lines 4–32 become; everything else at the top of the file is unchanged):
```python
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from test_backtest_runner import (
    END,
    START,
    TABLE,
    TABLE_B,
    FixedPicks,
    ParamPicks,
    scenario_market,
    smoke_market,
)

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import (
    DASH,
    INFINITY,
    MINUS,
    Metrics,
    avg_days_held,
    cagr_between,
    checklist,
    curve_metrics,
    exit_reason_counts,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    metrics_through,
    run_metrics,
    strategy_metrics,
    to_fixed,
)
from seer_engine.backtest.runner import ParamsSchedule, RunResult, run_backtest
from seer_engine.sim import Event, Order, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
```
- `tests/` is on `sys.path` under pytest's default `prepend` import mode. That is how
  `from simkit import ...` already works locally and in CI, where it runs as `pytest engine/tests`.
- None of the imported names starts with `test_`, so no test is collected twice.

**5b. Append** after the last line (296, end of `test_curve_metrics_has_no_trades`):
```python


# --------------------------------------------------------------------------- metrics_through (P3b)
#
# The prefix property: cutting a long run's metrics at e1 equals the metrics of a run that
# stops at e1. Walk-forward tuning relies on it (one run per combination, sliced per fold).


def test_metrics_through_the_scenario_equals_a_run_that_stops_there():
    market = scenario_market()
    full = run_backtest(market, FixedPicks(TABLE), None, START, END)
    forced = [e.session_date for e in full.events if e.forced]
    assert forced == [D("2025-03-06")]  # BBB, the session after its last bar
    for e1 in dates.sessions(START, END):
        short = run_backtest(market, FixedPicks(TABLE), None, START, e1)
        assert metrics_through(full, e1) == run_metrics(short), e1
    # The forced close falls on the session right after 03-05 (left out) and on 03-06 itself.
    assert metrics_through(full, D("2025-03-05")).trades == 1  # AAA only
    assert metrics_through(full, D("2025-03-06")).trades == 2  # AAA, then BBB forced
    assert metrics_through(full, D("2025-03-06")).exit_reasons == (("tp", 1), ("sl", 0), ("time", 1), ("gap", 0))
    assert metrics_through(full, END) == run_metrics(full)


def test_metrics_through_a_schedule_run_equals_a_run_that_stops_there():
    market = scenario_market()
    sched = ParamsSchedule(((START, "a"), (D("2025-03-07"), "b")))
    tables = {"a": TABLE, "b": TABLE_B}
    full = run_backtest(market, ParamPicks(tables), sched, START, END)
    for e1 in dates.sessions(START, END):
        short = run_backtest(market, ParamPicks(tables), sched, START, e1)
        assert metrics_through(full, e1) == run_metrics(short), e1


def test_metrics_through_the_strategy_a_smoke_market_with_a_forced_close():
    # UPC's bars stop on 2025-01-24, the day its limit fills (see the smoke trades): from
    # 2025-01-27 on it is gone, so the runner force-closes it on 2025-01-27.
    market, start, end = smoke_market(cut=D("2025-01-24"))
    prepared = STRATEGY_A.prepare(market.history)
    full = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=prepared)
    forced = [(e.session_date, e.order.symbol) for e in full.events if e.forced]
    assert forced == [(D("2025-01-27"), "UPC")]
    assert len(full.closed) > 3
    cuts = [
        start,
        D("2024-11-14"),  # an ordinary tp exit day
        D("2025-01-24"),  # the forced close is on the next session: left out
        D("2025-01-27"),  # the forced close is on this session: kept
        D("2025-02-13"),
        end,
    ]
    for e1 in cuts:
        short = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, e1, prepared=prepared)
        assert metrics_through(full, e1) == run_metrics(short), e1
    before = metrics_through(full, D("2025-01-24"))
    at = metrics_through(full, D("2025-01-27"))
    assert at.trades == before.trades + 1
    assert dict(at.exit_reasons)["time"] == dict(before.exit_reasons)["time"] + 1


def test_metrics_through_rejects_an_end_outside_the_run_or_not_a_session():
    full = run_backtest(scenario_market(), FixedPicks(TABLE), None, START, END)
    with pytest.raises(ValueError):
        metrics_through(full, dates.prev_session(START))  # the snapshot-0 date is not in the window
    with pytest.raises(ValueError):
        metrics_through(full, dates.next_session(END))
    with pytest.raises(ValueError):
        metrics_through(full, D("2025-03-08"))  # a Saturday inside the window
    with pytest.raises(TypeError):
        metrics_through(full, datetime(2025, 3, 6))
    with pytest.raises(TypeError):
        metrics_through(run_metrics(full), END)
```
**Facts the smoke test relies on.** These were checked against the uncut smoke run, where
`start = 2024-10-17` and `end = 2025-03-31`. That run has 16 tp exits and no open positions at the
end.
- UPC fills on 2025-01-24 and would exit tp on 2025-01-27.
- With UPC cut at 2025-01-24, the runner force-closes it on 2025-01-27. That is the single forced
  event.

**Impact:** 4 new tests. `D` in this file is already `date.fromisoformat` (line 34).

### Step 6: `select` fallback tests and the structural guard
**File:** `engine/tests/test_backtest_tuning.py`

**6a. New test**, inserted immediately before `def test_select_is_deterministic():` (line 127):
```python
def test_select_fallback_is_used_only_when_nothing_qualifies():
    nothing = rows_with(M(0.5, dd=0.2), M(0.4, pf=1.0))
    sentinel = object()
    s = select(nothing, fallback=sentinel)
    assert s.params is sentinel
    assert s.qualified is False
    assert s.reason == select(nothing).reason  # same words whatever the fallback
    assert select([], fallback=sentinel).params is sentinel
    # With a qualifying row the fallback is ignored: same Selection as without it.
    some = rows_with(M(0.5, dd=0.2), M(0.1), M(0.2))
    assert select(some, fallback=sentinel) == select(some)
    assert select(some, fallback=sentinel).params == grid()[2]
    # The default is DESIGN_PARAMS, exactly as before.
    assert select(nothing) == select(nothing, fallback=DESIGN_PARAMS)
    assert select(nothing).params is DESIGN_PARAMS


```

**6b. Update the existing structural guard** (lines 175–181). It asserts that `select`'s parameters
are exactly `["rows"]`, which a new `fallback` parameter necessarily breaks. The guard's intent is
"selection takes no out-of-sample window". That intent is kept: the only parameter added is a
keyword-only fallback object, not a data window. Full replacement:
```python
def test_gate_and_select_see_only_their_own_window():
    # Structural guard for invariant 6: neither takes the other window's data. select's only
    # extra parameter is the keyword-only fallback params object (P3b), never a metrics window.
    import inspect

    params = inspect.signature(select).parameters
    assert list(params) == ["rows", "fallback"]
    assert params["fallback"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["fallback"].default is DESIGN_PARAMS
    assert list(inspect.signature(gate).parameters) == ["oos", "spy_tr_oos"]
```
**Impact:**
- One new test.
- One existing test is edited. This is the only existing assertion this phase changes, and it is
  unavoidable: the old assertion encodes the old signature. Every other existing runner, tuning and
  metrics test is untouched.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/strategy-a-rework && engine/.venv/bin/python -c "from seer_engine.backtest.runner import ParamsSchedule; from seer_engine.backtest.metrics import metrics_through; from seer_engine.backtest.tuning import select"`

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/strategy-a-rework
docker start seer-pg
engine/.venv/bin/pytest engine/tests/test_backtest_runner.py engine/tests/test_backtest_metrics.py engine/tests/test_backtest_tuning.py engine/tests/test_strategy_purity.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs
```
**Expected counts:**
- The three touched files go from **54 to 67** collected tests: runner +8, metrics +4, tuning +1.
- The full suite on this phase alone goes from **598 to 611 passed, 0 skipped**.
- Phase 1 adds 62 tests. If phase 1 landed first, this phase takes the suite from **660 to 673**.
  After both, the total is **673** whichever order they land in.
- No other phase edits `test_backtest_tuning.py`; the guard update in 6b is this phase's alone.

**Manual check:** none needed. Optionally, `git diff e14de0c -- engine/src/seer_engine/backtest/runner.py`
should show the v1 path's only differences as:
- the `schedule = ...` lines;
- `session_params` replacing `params` in the two strategy calls, where it is the same object
  whenever `params` is not a schedule.

**Exit criteria:**
- `ParamsSchedule`, `metrics_through` and `select(..., fallback=)` exist as specified.
- The suite is green with 0 skipped.
- The purity test passes over the edited modules.
- No file outside the six listed is modified.

## Handoffs

- **Phase 3 (walk-forward), for R3:**
  - It builds `ParamsSchedule(tuple((f.trade_start, s.params) for f, s in zip(folds, selections)))`.
    `trade_start` must be an NYSE session (it is: the first session of the year), and the first
    segment must start at or before the run's `start`.
  - It slices tuning runs with `metrics_through(run, f.tune_end)`, where `tune_end` must lie in
    `[run.start, run.end]` and be a session.
  - It calls `tuning.select(rows, fallback=A2_DESIGN_PARAMS)` or `fallback=A2Params(variant=v)`. The
    fallback reason reads "...so the design values are kept.", which is accurate for both (D7).
  - It may reuse `ParamPicks`, `TABLE_B` and `smoke_market` from `tests/test_backtest_runner.py`
    through `from test_backtest_runner import ...`.
- **Optional, any later phase (not done here, being annotation-only scope creep):**
  `tuning.GridRow.params` and `tuning.Selection.params` are annotated `AParams`. Phase 3 will store
  `A2Params` there. Python does not check this at runtime and no type checker runs in CI, so nothing
  breaks. Widening the annotations to `Any` is a cosmetic follow-up.
- **Phase 6 (docs, R8):** `engine/package_readme.md`'s `backtest` section should document:
  - `ParamsSchedule` and the schedule branch (keyed by the traded session; brackets kept);
  - `metrics_through` and the prefix property;
  - `select(..., fallback=)`.
- **Phase 6, for the R8 v1 byte-identity check:** this phase guarantees the code path. The check
  itself (Decision D9) is phase 6's.

## Rollback

Run `git revert <phase-2 commit>`. Every change is additive:
- a new class;
- a new function;
- a new keyword-only argument with the old default;
- new tests;
- one guard assertion widened.

Nothing else in the tree calls the new API until phase 3. If phase 3 has landed, revert it first.
