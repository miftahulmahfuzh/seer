# Phase 4: Public API, scenario, determinism, benchmark, docs

**Plan set:** `ENGINE_FILL_SIMULATOR_PLAN.md`
**Analysis:** `20261003-134417-F7S2_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-fill-simulator.md` (§6.2 determinism, §6.3 scenario, §6.5 readme, §7 performance)
**Satisfies:** R4. P3 and P4 get one documented import surface (`seer_engine.sim`). A ≥10-session hand-checked scenario, a determinism test and a benchmark prove it.
**Depends on:** Phase 2 (`sim/sizing.py`), Phase 3 (`sim/split_adjust.py`), and through them Phase 1
**Difficulty:** NORMAL
**Package:** `seer_engine.sim` (`engine/src/seer_engine/sim/`), `engine/tests/`, docs

---

## Goal

After this phase, `seer_engine.sim` exports the whole simulator: the model and lifecycle from
phase 1, plus `size_picks` and its types (phase 2) and `apply_split` (phase 3). One test file
runs a 12-session, 4-slot scenario on real consecutive NYSE sessions around Thanksgiving 2025.
It asserts every placement, rejection, event, snapshot and closed-trade `pnl_usd` as exact
Decimals, each worked by hand in a comment. The same file checks that the scenario is
deterministic and benchmarks 2,950 sessions × 4 slots. `engine/package_readme.md` documents the
API, the rules, event ordering, a P3 backtest loop, a P4 nightly sequence and the measured
benchmark. `docs/ROADMAP.md` marks P2 done.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `engine/tests/test_sim_scenario.py` (new): 11 tests. `run_scenario(reverse_bar_order=False) -> Run` is a module-level helper, not an export.
- Re-exports in `seer_engine.sim` (`sim/__init__.py`): `Pick`, `RejectReason`, `Rejection`, `SizingResult`, `size_picks` (from `sim.sizing`) and `apply_split` (from `sim.split_adjust`), all added to `__all__`.

**Signature changes:** none. This phase only re-exports.

**Requires (from earlier phases), quoted as the plans for phases 1–3 define them:**
- Phase 1, `sim/__init__.py` exactly as phase 1 Step 5 writes it: it imports `close_unpriced` and `step` from `lifecycle`, plus `COST_RATE, SLOTS, TIME_STOP_DAYS, Event, EventKind, ExitReason, Order, OrderStatus, Portfolio, Snapshot, StepResult, buy_cost, initial_cash_usd, new_portfolio, q, sell_proceeds` from `model`, with a sorted `__all__`. This phase replaces the whole file with a superset.
- Phase 1, `step` semantics:
  - events are `exits + fills + expiries`, and each group is in slot order;
  - a fill sets `days_held = 1`;
  - an exit at the open keeps `days_held`, and an intraday exit adds 1;
  - an expire event carries `status="expired"` and no fill or exit fields;
  - `Event.cash_usd` is `-buy_cost` on a fill, `+proceeds` on an exit and `None` on an expire;
  - `Snapshot(date, cash_usd, equity_usd)`, with `portfolio.equity == snapshot.equity_usd`;
  - `marks` holds exactly the open symbols, sorted.
- Phase 1, `simkit.D(str) -> date` and `simkit.P(str) -> Decimal` (quantized). `from simkit import …` works because `engine/tests` has no `__init__.py`.
- Phase 1, `seer_engine.prices.Bar(symbol, date, open, high, low, close, volume)`.
- Phase 2, `Pick(symbol, last_price, limit_price, tp_price, sl_price)`, which validates `sl < limit < tp`.
- Phase 2, `size_picks(portfolio, picks, session_date) -> SizingResult(portfolio, placed, rejected)`:
  - `placed` and `rejected` come back in pick order;
  - `held` is checked before `no_slot`, which is checked before `lt_one_share`;
  - the lowest free slot goes first;
  - `budget = min(q(equity / 4), cash − Σ buy_cost(limit, shares) of pending orders, including this night's earlier placements)`;
  - `session_date` must be an NYSE session after `last_session`.
- Phase 3, `apply_split(portfolio, symbol, factor, session_date) -> (Portfolio, tuple[Event, ...])`. It emits `split`, `expire`, or a forced `exit` that floors to 0 shares, in slot order.

**Leaves alone (owned by others):** `sim/model.py`, `sim/lifecycle.py`, `prices.py`, `bars.py`, `tests/simkit.py`, `test_sim_lifecycle.py`, `test_sim_purity.py` (Phase 1); `sim/sizing.py`, `test_sim_sizing.py` (Phase 2); `sim/split_adjust.py`, `test_sim_split.py` (Phase 3). The one sanctioned exception, from the index: if the scenario exposes a real bug in `model`/`lifecycle`/`sizing`/`split_adjust`, the minimal fix lands here and is recorded in the commit message. Changing a rule is never a bug fix.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/__init__.py` | modify (whole file, phase-1 version) | add sizing and split exports to the imports and `__all__` |
| `engine/tests/test_sim_scenario.py` | create | hand-checked 12-session scenario, determinism, cash reconciliation, benchmark |
| `engine/package_readme.md` | modify (lines 4, 25–51, 147–159, 203/205, 234–239, 268–273, 297–311) | Last Updated, layout, `prices` + `sim` API sections, module graph, Performance, P3/P4 usage |
| `docs/ROADMAP.md` | modify (line 21) | P2 heading gets a status line |

## Scenario design (what the test proves)

The scenario covers sessions 2025-11-20 → 2025-12-08, 12 consecutive NYSE sessions. Thursday
2025-11-27 is Thanksgiving, and Friday 2025-11-28 is a half day. Starting capital is
20,000,000 IDR / 16,250 = **1230.7692** USD.

| Outcome | Where |
|---|---|
| fill at limit (low < limit, open ≥ limit) | CCC, AAA (S1), EEE (S2), FFF (S3), JJJ (S7), LLL (S9) |
| fill at the **open** (open < limit) | BBB (S1), GGG (S4), HHH (S6), KKK (S7) |
| **expire**: low == limit (touch is not a fill) | DDD (S1), III (S6) |
| **sl**, same bar as TP → SL first | BBB (S2) |
| **sl**, touch (low == SL) | HHH (S10) |
| **tp** intraday (high > TP) | AAA (S3), GGG (S8, day 5), JJJ (S11, day 5) |
| **gap** (open ≤ SL) | FFF (S5) |
| **gap-tp** (open ≥ TP, reason `tp`) | EEE (S5) |
| **time** at the day-6 open, across the holiday, onto a half day, beating a TP-range bar | CCC (S6) |
| **time** at the day-6 open | KKK (S12) |
| no TP check on the fill session (high > TP on the fill day) | LLL (S9) |
| **ineligible** `lt_one_share` | XXX (night 0) |
| `no_slot` | YYY (night 0) |
| `held` (no adding) | AAA (night 1) |
| **cash cap** binds (19 shares, where equity / 4 alone would give 20) | III (night 5) |
| slot reuse after an exit or expiry | slot 3 (BBB → FFF → HHH), slot 2 (AAA → GGG → LLL), slot 4 (DDD → EEE → III → KKK), slot 1 (CCC → JJJ) |
| zero picks | nights 4, 7, 9, 10, 11 |
| 4-dp rounding in costs | HHH buy 315.69538 → 315.6954, KKK buy 314.12381 → 314.1238, KKK sell 316.57311 → 316.5731, EEE sell 297.69201 → 297.6920 |
| a position still open at the end | LLL (cash reconciliation includes its cost) |

Totals: Σ closed `pnl_usd` = **84.6604**. Final cash = **985.0996**, final equity =
**1340.5996**. Cash change = −245.6696 = 84.6604 − 330.3300 (LLL's buy cost).

I computed every number twice: once with an independent reference model of the Decisions, and
once by running this exact test file against a throwaway stub of the phase 1–3 contract in the
planner's scratch area, where all 11 tests passed. The stub has no authority. If the real
modules disagree, check the disagreement against the Decisions table before touching either
side.

**Event order.** Phase 1 fixes it: all exits (any reason) in slot order, then all fills in slot
order, then all expiries in slot order. `EXPECTED_EVENTS` is written in exactly that order. (In
this scenario, the exits on one session also happen to be in stage order, so nothing depends on
how exits of different reasons interleave.)

## Implementation Steps

### Step 1: Export sizing and split from the package
**File:** `engine/src/seer_engine/sim/__init__.py:1` (replace the whole phase-1 file)
**Change:** keep every phase-1 name, add the phase 2 and phase 3 names, and keep `__all__` isort-style sorted (constants, then types, then functions, each alphabetical), as phase 1 writes it.
The docstring gains the call order. No logic. Phase 1's AST purity scan covers this file (no
`print`, `time`, `logging`).
**Code:**
```python
"""Seer fill simulator: pure, deterministic order lifecycle and portfolio accounting.

One code path for the backtest (P3) and nightly paper trading (P4). No database, no
network, no clock: importing this package must never load psycopg, requests or yfinance
(enforced by tests/test_sim_purity.py).

Per session S: ``apply_split`` (only if a split executes on S) -> ``step(S)`` -> persist
events and snapshot -> ``size_picks(..., next session)``. See engine/package_readme.md.
"""

from seer_engine.sim.lifecycle import close_unpriced, step
from seer_engine.sim.model import (
    COST_RATE,
    SLOTS,
    TIME_STOP_DAYS,
    Event,
    EventKind,
    ExitReason,
    Order,
    OrderStatus,
    Portfolio,
    Snapshot,
    StepResult,
    buy_cost,
    initial_cash_usd,
    new_portfolio,
    q,
    sell_proceeds,
)
from seer_engine.sim.sizing import Pick, RejectReason, Rejection, SizingResult, size_picks
from seer_engine.sim.split_adjust import apply_split

__all__ = [
    "COST_RATE",
    "SLOTS",
    "TIME_STOP_DAYS",
    "Event",
    "EventKind",
    "ExitReason",
    "Order",
    "OrderStatus",
    "Pick",
    "Portfolio",
    "RejectReason",
    "Rejection",
    "SizingResult",
    "Snapshot",
    "StepResult",
    "apply_split",
    "buy_cost",
    "close_unpriced",
    "initial_cash_usd",
    "new_portfolio",
    "q",
    "sell_proceeds",
    "size_picks",
    "step",
]
```
**Impact:** `import seer_engine.sim` now also loads `sizing` and `split_adjust`. Phase 1's
`test_sim_purity.py` subprocess check therefore covers them, with no change to that test. If the
reconciler gives phase 1's `__init__` a different name list, keep its names and add these six.
**Check:** `engine/.venv/bin/python -c "import seer_engine.sim as s; k = lambda n: (0 if n.isupper() else 1 if n[0].isupper() else 2, n); assert sorted(s.__all__, key=k) == s.__all__ and len(set(s.__all__)) == 24; [getattr(s, n) for n in s.__all__]; print('ok')"`. `__all__` is isort-style sorted (ruff RUF022: constants, then types, then functions), like phase 1's, so a plain `sorted()` check would fail.

### Step 2: The scenario, determinism and benchmark test
**File:** `engine/tests/test_sim_scenario.py` (new)
**Change:** the full file below. Every expected number is worked in the comments. `run_scenario`
is P4's nightly loop: `size_picks` for session i (made the night before), then `step(i)`. Bars
are built with `prices.Bar` directly from `simkit.P` values. Only symbols with a live order get a
bar, which is also all `step` reads.
**Code:**
```python
"""The hand-checked multi-session scenario, determinism and the benchmark (handover §6.2, §6.3, §7).

Every number below is worked out by hand in the comments, from the plan's Decisions:

- ``buy_cost(p, sh) = q(p * sh * 1.001)`` and ``sell_proceeds(p, sh) = q(p * sh * 0.999)``,
  where ``q`` rounds half-up to 4 dp.
- ``pnl_usd = sell_proceeds(exit) - buy_cost(fill)``.
- Sizing: ``budget = min(q(equity / 4), cash - sum of buy_cost(limit, shares) of pending orders)``,
  ``shares = floor(budget / (limit * 1.001))``, lowest free slot first, picks in the given order.
- Session order: time stop at the open, gap at the open (SL then TP), intraday SL then TP,
  fills, expiries, mark to close. The fill session is day 1. An intraday exit on day k records
  ``days_held = k``; an exit at the open of day k records ``k - 1``.
- Equity = cash + sum(shares * last close), quantized.

The scenario runs over 12 real consecutive NYSE sessions around Thanksgiving 2025
(Thursday 2025-11-27 is a holiday, Friday 2025-11-28 is a half day).
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from simkit import D, P

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim import (
    Event,
    Order,
    Pick,
    Portfolio,
    Rejection,
    Snapshot,
    buy_cost,
    initial_cash_usd,
    new_portfolio,
    size_picks,
    step,
)

INITIAL_IDR = Decimal("20000000")
USD_IDR = Decimal("16250")
# 20,000,000 / 16,250 = 1230.769230... -> 1230.7692
INITIAL_CASH = Decimal("1230.7692")

S1, S2, S3, S4, S5, S6 = (
    D("2025-11-20"),
    D("2025-11-21"),
    D("2025-11-24"),
    D("2025-11-25"),
    D("2025-11-26"),
    D("2025-11-28"),  # after the Thanksgiving holiday; a half day
)
S7, S8, S9, S10, S11, S12 = (
    D("2025-12-01"),
    D("2025-12-02"),
    D("2025-12-03"),
    D("2025-12-04"),
    D("2025-12-05"),
    D("2025-12-08"),
)
SESSIONS = (S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12)


def _pick(symbol: str, last: str, limit: str, tp: str, sl: str) -> Pick:
    return Pick(
        symbol=symbol,
        last_price=P(last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
    )


# PICKS[i] is sized on the night before SESSIONS[i], for SESSIONS[i].
PICKS: tuple[tuple[Pick, ...], ...] = (
    # Night before S1. equity 1230.7692, q(equity / 4) = 307.6923.
    (
        # CCC: avail 1230.7692; 307.6923 / 25.025 = 12.29 -> 12 shares, slot 1.
        #      pending cost buy_cost(25.00, 12) = 300.3000.
        _pick("CCC", "25.40", "25.00", "30.00", "22.00"),
        # AAA: avail 1230.7692 - 300.3000 = 930.4692; 307.6923 / 10.01 = 30.74 -> 30, slot 2.
        #      pending cost 10.00 * 30 * 1.001 = 300.3000.
        _pick("AAA", "10.25", "10.00", "10.80", "9.50"),
        # BBB: avail 630.1692; 307.6923 / 20.02 = 15.37 -> 15, slot 3.
        #      pending cost 20.00 * 15 * 1.001 = 300.3000.
        _pick("BBB", "20.30", "20.00", "21.00", "18.80"),
        # XXX: 307.6923 / 400.40 = 0.77 -> 0 shares -> rejected lt_one_share (ineligible).
        _pick("XXX", "405.00", "400.00", "440.00", "380.00"),
        # DDD: avail 329.8692; 307.6923 / 50.05 = 6.15 -> 6, slot 4.
        _pick("DDD", "50.60", "50.00", "55.00", "47.00"),
        # YYY: all 4 slots taken -> rejected no_slot.
        _pick("YYY", "5.10", "5.00", "5.50", "4.70"),
    ),
    # Night before S2. equity 1246.9767, q(1246.9767 / 4) = q(311.744175) = 311.7442. Free: slot 4.
    (
        # AAA is held (open since S1) -> rejected held (no adding to a holding).
        _pick("AAA", "10.50", "10.40", "11.20", "9.90"),
        # EEE: avail = cash 337.3767; 311.7442 / 40.04 = 7.79 -> 7, slot 4.
        _pick("EEE", "40.50", "40.00", "42.00", "37.00"),
    ),
    # Night before S3. equity 1246.2147, q(311.553675) = 311.5537. Free: slot 3 (BBB stopped out).
    (
        # FFF: avail 338.8147; 311.5537 / 15.015 = 20.75 -> 20, slot 3 (slot reuse after an exit).
        _pick("FFF", "15.20", "15.00", "16.50", "14.00"),
    ),
    # Night before S4. equity 1268.9907, q(317.247675) = 317.2477. Free: slot 2 (AAA took profit).
    (
        # GGG: avail 362.1907; 317.2477 / 30.03 = 10.56 -> 10, slot 2.
        _pick("GGG", "30.40", "30.00", "33.00", "28.00"),
    ),
    # Night before S5: every slot is taken; zero picks is valid.
    (),
    # Night before S6. equity 1288.1087, q(322.027175) = 322.0272. Free: slots 3 and 4.
    (
        # HHH: avail 637.3087; 322.0272 / 12.3123 = 26.15 -> 26, slot 3.
        #      pending cost q(12.30 * 26 * 1.001) = q(320.1198) = 320.1198.
        _pick("HHH", "12.45", "12.30", "13.30", "11.30"),
        # III: avail 637.3087 - 320.1198 = 317.1889 < 322.0272, so the CASH CAP binds.
        #      317.1889 / 16.016 = 19.80 -> 19 (equity / 4 alone would give 20.11 -> 20), slot 4.
        _pick("III", "16.20", "16.00", "17.60", "14.80"),
    ),
    # Night before S7. equity 1291.9761, q(322.994025) = 322.9940. Free: slots 1 (CCC) and 4 (III).
    (
        # JJJ: avail 658.4761; 322.9940 / 8.008 = 40.33 -> 40, slot 1.
        #      pending cost 8.00 * 40 * 1.001 = 320.3200.
        _pick("JJJ", "8.10", "8.00", "8.80", "7.40"),
        # KKK: avail 658.4761 - 320.3200 = 338.1561; 322.9940 / 45.045 = 7.17 -> 7, slot 4.
        _pick("KKK", "45.50", "45.00", "50.00", "42.00"),
    ),
    # Night before S8: every slot is taken.
    (),
    # Night before S9. equity 1329.5023, q(332.375575) = 332.3756. Free: slot 2 (GGG took profit).
    (
        # LLL: avail 353.7023; 332.3756 / 22.022 = 15.09 -> 15, slot 2.
        _pick("LLL", "22.30", "22.00", "24.00", "20.50"),
    ),
    # Nights before S10, S11, S12: zero picks (slots 3 and 1 stay free on purpose).
    (),
    (),
    (),
)

# BARS[i] is SESSIONS[i]'s bars: (symbol, open, high, low, close). Only symbols with a live order.
BARS: tuple[tuple[tuple[str, str, str, str, str], ...], ...] = (
    # S1 2025-11-20
    (
        ("CCC", "25.10", "25.50", "24.80", "25.30"),  # low 24.80 < 25.00, open >= limit: fill at 25.00
        ("AAA", "10.20", "10.30", "9.90", "10.10"),  # low 9.90 < 10.00: fill at 10.00
        ("BBB", "19.50", "20.40", "19.30", "20.20"),  # open 19.50 < 20.00: fill at the OPEN 19.50
        ("DDD", "51.00", "52.00", "50.00", "51.50"),  # low == limit (touch, not below): expires
    ),
    # S2 2025-11-21
    (
        ("CCC", "25.30", "26.00", "25.00", "25.80"),
        ("AAA", "10.10", "10.60", "9.90", "10.50"),
        ("BBB", "20.00", "21.20", "18.80", "19.00"),  # high > TP 21 AND low <= SL 18.80: SL first
        ("EEE", "40.20", "40.50", "39.60", "40.40"),  # fill at 40.00
    ),
    # S3 2025-11-24
    (
        ("CCC", "25.80", "26.50", "25.50", "26.20"),
        ("AAA", "10.50", "10.85", "10.40", "10.70"),  # high 10.85 > TP 10.80: TP intraday
        ("EEE", "40.40", "41.50", "40.10", "41.20"),
        ("FFF", "15.10", "15.30", "14.90", "15.20"),  # fill at 15.00
    ),
    # S4 2025-11-25
    (
        ("CCC", "26.20", "27.00", "26.00", "26.80"),
        ("GGG", "29.80", "30.50", "29.70", "30.30"),  # open 29.80 < 30.00: fill at the open
        ("FFF", "15.20", "15.60", "14.50", "14.60"),
        ("EEE", "41.20", "41.90", "40.80", "41.70"),
    ),
    # S5 2025-11-26
    (
        ("CCC", "26.80", "28.00", "26.50", "27.90"),
        ("GGG", "30.30", "31.80", "30.20", "31.60"),
        ("FFF", "13.80", "14.20", "13.50", "14.00"),  # open 13.80 <= SL 14.00: gap exit at the open
        ("EEE", "42.57", "43.00", "42.10", "42.80"),  # open 42.57 >= TP 42.00: tp exit at the open
    ),
    # S6 2025-11-28 (half day after the holiday)
    (
        ("CCC", "28.10", "30.50", "27.60", "30.20"),  # day 6: time stop at the open, before TP
        ("GGG", "31.60", "32.00", "31.00", "31.50"),
        ("HHH", "12.13", "12.40", "11.95", "12.25"),  # open 12.13 < 12.30: fill at the open
        ("III", "16.20", "16.50", "16.00", "16.40"),  # low == limit: expires
    ),
    # S7 2025-12-01
    (
        ("GGG", "31.50", "32.50", "31.20", "32.40"),
        ("HHH", "12.25", "12.60", "12.00", "12.50"),
        ("JJJ", "8.05", "8.20", "7.90", "8.15"),  # fill at 8.00
        ("KKK", "44.83", "45.60", "44.50", "45.40"),  # open 44.83 < 45.00: fill at the open
    ),
    # S8 2025-12-02
    (
        ("GGG", "32.40", "33.40", "32.20", "33.10"),  # high 33.40 > TP 33.00: TP on day 5
        ("HHH", "12.50", "12.70", "12.20", "12.30"),
        ("JJJ", "8.15", "8.40", "8.05", "8.35"),
        ("KKK", "45.40", "46.20", "45.00", "46.00"),
    ),
    # S9 2025-12-03
    (
        ("HHH", "12.30", "12.40", "11.80", "11.90"),
        ("JJJ", "8.35", "8.60", "8.20", "8.55"),
        ("KKK", "46.00", "46.80", "45.70", "46.50"),
        ("LLL", "22.10", "24.50", "21.80", "22.20"),  # fill at 22.00; high > TP not checked today
    ),
    # S10 2025-12-04
    (
        ("HHH", "11.90", "12.00", "11.30", "11.40"),  # low == SL 11.30 (touch): SL
        ("JJJ", "8.55", "8.75", "8.40", "8.70"),
        ("KKK", "46.50", "47.20", "45.90", "46.10"),
        ("LLL", "22.20", "22.90", "22.00", "22.80"),
    ),
    # S11 2025-12-05
    (
        ("JJJ", "8.70", "8.95", "8.60", "8.90"),  # high 8.95 > TP 8.80: TP on day 5
        ("KKK", "46.10", "46.60", "45.20", "45.60"),
        ("LLL", "22.80", "23.50", "22.60", "23.30"),
    ),
    # S12 2025-12-08
    (
        ("KKK", "45.27", "45.90", "44.70", "45.50"),  # day 6: time stop at the open 45.27
        ("LLL", "23.30", "23.80", "23.00", "23.70"),
    ),
)


@dataclass(frozen=True)
class Run:
    placed: tuple[tuple[Order, ...], ...]
    rejected: tuple[tuple[Rejection, ...], ...]
    events: tuple[tuple[Event, ...], ...]
    snapshots: tuple[Snapshot, ...]
    live: tuple[tuple[Order, ...], ...]
    final: Portfolio


def run_scenario(reverse_bar_order: bool = False) -> Run:
    """P4's nightly loop, 12 times: size the night's picks, then step the session."""
    pf = new_portfolio(initial_cash_usd(INITIAL_IDR, USD_IDR))
    placed, rejected, events, snapshots, live = [], [], [], [], []
    for i, session in enumerate(SESSIONS):
        sized = size_picks(pf, PICKS[i], session)
        placed.append(sized.placed)
        rejected.append(sized.rejected)
        rows = tuple(reversed(BARS[i])) if reverse_bar_order else BARS[i]
        bars = {
            sym: Bar(sym, session, P(o), P(h), P(lo), P(c), 1_000_000)
            for sym, o, h, lo, c in rows
        }
        result = step(sized.portfolio, session, bars)
        pf = result.portfolio
        events.append(result.events)
        snapshots.append(result.snapshot)
        live.append(pf.orders)
    return Run(
        tuple(placed), tuple(rejected), tuple(events), tuple(snapshots), tuple(live), pf
    )


def _order(session: date, slot: int, pick: Pick, shares: int) -> Order:
    return Order(
        session_date=session,
        slot=slot,
        symbol=pick.symbol,
        last_price=pick.last_price,
        limit_price=pick.limit_price,
        tp_price=pick.tp_price,
        sl_price=pick.sl_price,
        shares=shares,
    )


def _ev(e: Event) -> tuple:
    """The parts of an event the Decisions pin down exactly, ``days_held`` included: a fill
    is day 1, an expired order has 0, and an exit records the count the Decisions give."""
    o = e.order
    return (
        e.session_date,
        e.kind,
        o.slot,
        o.symbol,
        o.status,
        o.shares,
        o.fill_date,
        o.fill_price,
        o.exit_date,
        o.exit_price,
        o.exit_reason,
        o.days_held,
        o.pnl_usd,
        e.cash_usd,
        e.forced,
    )


def _fill(d, slot, sym, sh, price, cost):
    return (d, "fill", slot, sym, "open", sh, d, P(price), None, None, None, 1, None,
            Decimal(cost), False)


def _expire(d, slot, sym, sh):
    return (d, "expire", slot, sym, "expired", sh, None, None, None, None, None, 0, None,
            None, False)


def _exit(d, slot, sym, sh, fill_d, fill, price, reason, held, pnl, proceeds):
    return (d, "exit", slot, sym, "closed", sh, fill_d, P(fill), d, P(price), reason, held,
            Decimal(pnl), Decimal(proceeds), False)


# Per session, in phase 1's event order: all exits (any reason) by slot, then all fills by
# slot, then all expiries by slot.
EXPECTED_EVENTS: tuple[tuple[tuple, ...], ...] = (
    # S1
    (
        # buy_cost(25.00, 12): 25.00 * 12 = 300.00 * 1.001 = 300.3000
        _fill(S1, 1, "CCC", 12, "25.00", "-300.3000"),
        # 10.00 * 30 = 300.00 * 1.001 = 300.3000
        _fill(S1, 2, "AAA", 30, "10.00", "-300.3000"),
        # 19.50 * 15 = 292.50 * 1.001 = 292.7925
        _fill(S1, 3, "BBB", 15, "19.50", "-292.7925"),
        _expire(S1, 4, "DDD", 6),
    ),
    # S2
    (
        # BBB day 2, SL intraday at 18.80: 18.80 * 15 = 282.00 * 0.999 = 281.7180
        #   pnl = 281.7180 - 292.7925 = -11.0745; days_held = 2
        _exit(S2, 3, "BBB", 15, S1, "19.50", "18.80", "sl", 2, "-11.0745", "281.7180"),
        # 40.00 * 7 = 280.00 * 1.001 = 280.2800
        _fill(S2, 4, "EEE", 7, "40.00", "-280.2800"),
    ),
    # S3
    (
        # AAA day 3, TP intraday at 10.80: 10.80 * 30 = 324.00 * 0.999 = 323.6760
        #   pnl = 323.6760 - 300.3000 = 23.3760; days_held = 3
        _exit(S3, 2, "AAA", 30, S1, "10.00", "10.80", "tp", 3, "23.3760", "323.6760"),
        # 15.00 * 20 = 300.00 * 1.001 = 300.3000
        _fill(S3, 3, "FFF", 20, "15.00", "-300.3000"),
    ),
    # S4
    (
        # 29.80 * 10 = 298.00 * 1.001 = 298.2980
        _fill(S4, 2, "GGG", 10, "29.80", "-298.2980"),
    ),
    # S5
    (
        # FFF day 3, gap at the open 13.80: 13.80 * 20 = 276.00 * 0.999 = 275.7240
        #   pnl = 275.7240 - 300.3000 = -24.5760; exit at the open of day 3 -> days_held 2
        _exit(S5, 3, "FFF", 20, S3, "15.00", "13.80", "gap", 2, "-24.5760", "275.7240"),
        # EEE day 4, gap through TP at the open 42.57: 42.57 * 7 = 297.99 * 0.999 = 297.69201
        #   -> 297.6920; pnl = 297.6920 - 280.2800 = 17.4120; at the open of day 4 -> 3
        _exit(S5, 4, "EEE", 7, S2, "40.00", "42.57", "tp", 3, "17.4120", "297.6920"),
    ),
    # S6
    (
        # CCC day 6 (across the holiday): time stop at the open 28.10, although high > TP.
        #   28.10 * 12 = 337.20 * 0.999 = 336.8628; pnl = 336.8628 - 300.3000 = 36.5628;
        #   days_held 5
        _exit(S6, 1, "CCC", 12, S1, "25.00", "28.10", "time", 5, "36.5628", "336.8628"),
        # 12.13 * 26 = 315.38 * 1.001 = 315.69538 -> 315.6954
        _fill(S6, 3, "HHH", 26, "12.13", "-315.6954"),
        _expire(S6, 4, "III", 19),
    ),
    # S7
    (
        # 8.00 * 40 = 320.00 * 1.001 = 320.3200
        _fill(S7, 1, "JJJ", 40, "8.00", "-320.3200"),
        # 44.83 * 7 = 313.81 * 1.001 = 314.12381 -> 314.1238
        _fill(S7, 4, "KKK", 7, "44.83", "-314.1238"),
    ),
    # S8
    (
        # GGG day 5, TP intraday at 33.00: 33.00 * 10 = 330.00 * 0.999 = 329.6700
        #   pnl = 329.6700 - 298.2980 = 31.3720; days_held 5
        _exit(S8, 2, "GGG", 10, S4, "29.80", "33.00", "tp", 5, "31.3720", "329.6700"),
    ),
    # S9
    (
        # 22.00 * 15 = 330.00 * 1.001 = 330.3300
        _fill(S9, 2, "LLL", 15, "22.00", "-330.3300"),
    ),
    # S10
    (
        # HHH day 5, SL touched at 11.30: 11.30 * 26 = 293.80 * 0.999 = 293.5062
        #   pnl = 293.5062 - 315.6954 = -22.1892; days_held 5
        _exit(S10, 3, "HHH", 26, S6, "12.13", "11.30", "sl", 5, "-22.1892", "293.5062"),
    ),
    # S11
    (
        # JJJ day 5, TP intraday at 8.80: 8.80 * 40 = 352.00 * 0.999 = 351.6480
        #   pnl = 351.6480 - 320.3200 = 31.3280; days_held 5
        _exit(S11, 1, "JJJ", 40, S7, "8.00", "8.80", "tp", 5, "31.3280", "351.6480"),
    ),
    # S12
    (
        # KKK day 6: time stop at the open 45.27: 45.27 * 7 = 316.89 * 0.999 = 316.57311
        #   -> 316.5731; pnl = 316.5731 - 314.1238 = 2.4493; days_held 5
        _exit(S12, 4, "KKK", 7, S7, "44.83", "45.27", "time", 5, "2.4493", "316.5731"),
    ),
)

# Snapshot after each session: cash, and equity = cash + sum(shares * close).
EXPECTED_SNAPSHOTS = (
    # S1: cash 1230.7692 - 300.3000 - 300.3000 - 292.7925 = 337.3767
    #     equity 337.3767 + 12*25.30 (303.60) + 30*10.10 (303.00) + 15*20.20 (303.00) = 1246.9767
    Snapshot(S1, Decimal("337.3767"), Decimal("1246.9767")),
    # S2: cash 337.3767 + 281.7180 - 280.2800 = 338.8147
    #     equity 338.8147 + 12*25.80 (309.60) + 30*10.50 (315.00) + 7*40.40 (282.80) = 1246.2147
    Snapshot(S2, Decimal("338.8147"), Decimal("1246.2147")),
    # S3: cash 338.8147 + 323.6760 - 300.3000 = 362.1907
    #     equity 362.1907 + 12*26.20 (314.40) + 20*15.20 (304.00) + 7*41.20 (288.40) = 1268.9907
    Snapshot(S3, Decimal("362.1907"), Decimal("1268.9907")),
    # S4: cash 362.1907 - 298.2980 = 63.8927
    #     equity 63.8927 + 12*26.80 (321.60) + 10*30.30 (303.00) + 20*14.60 (292.00)
    #            + 7*41.70 (291.90) = 1272.3927
    Snapshot(S4, Decimal("63.8927"), Decimal("1272.3927")),
    # S5: cash 63.8927 + 275.7240 + 297.6920 = 637.3087
    #     equity 637.3087 + 12*27.90 (334.80) + 10*31.60 (316.00) = 1288.1087
    Snapshot(S5, Decimal("637.3087"), Decimal("1288.1087")),
    # S6: cash 637.3087 + 336.8628 - 315.6954 = 658.4761
    #     equity 658.4761 + 10*31.50 (315.00) + 26*12.25 (318.50) = 1291.9761
    Snapshot(S6, Decimal("658.4761"), Decimal("1291.9761")),
    # S7: cash 658.4761 - 320.3200 - 314.1238 = 24.0323
    #     equity 24.0323 + 40*8.15 (326.00) + 10*32.40 (324.00) + 26*12.50 (325.00)
    #            + 7*45.40 (317.80) = 1316.8323
    Snapshot(S7, Decimal("24.0323"), Decimal("1316.8323")),
    # S8: cash 24.0323 + 329.6700 = 353.7023
    #     equity 353.7023 + 40*8.35 (334.00) + 26*12.30 (319.80) + 7*46.00 (322.00) = 1329.5023
    Snapshot(S8, Decimal("353.7023"), Decimal("1329.5023")),
    # S9: cash 353.7023 - 330.3300 = 23.3723
    #     equity 23.3723 + 40*8.55 (342.00) + 15*22.20 (333.00) + 26*11.90 (309.40)
    #            + 7*46.50 (325.50) = 1333.2723
    Snapshot(S9, Decimal("23.3723"), Decimal("1333.2723")),
    # S10: cash 23.3723 + 293.5062 = 316.8785
    #      equity 316.8785 + 40*8.70 (348.00) + 15*22.80 (342.00) + 7*46.10 (322.70) = 1329.5785
    Snapshot(S10, Decimal("316.8785"), Decimal("1329.5785")),
    # S11: cash 316.8785 + 351.6480 = 668.5265
    #      equity 668.5265 + 15*23.30 (349.50) + 7*45.60 (319.20) = 1337.2265
    Snapshot(S11, Decimal("668.5265"), Decimal("1337.2265")),
    # S12: cash 668.5265 + 316.5731 = 985.0996
    #      equity 985.0996 + 15*23.70 (355.50) = 1340.5996
    Snapshot(S12, Decimal("985.0996"), Decimal("1340.5996")),
)

# Live orders after each step: (slot, symbol, status, days_held). The fill session is day 1.
EXPECTED_LIVE = (
    ((1, "CCC", "open", 1), (2, "AAA", "open", 1), (3, "BBB", "open", 1)),
    ((1, "CCC", "open", 2), (2, "AAA", "open", 2), (4, "EEE", "open", 1)),
    ((1, "CCC", "open", 3), (3, "FFF", "open", 1), (4, "EEE", "open", 2)),
    ((1, "CCC", "open", 4), (2, "GGG", "open", 1), (3, "FFF", "open", 2), (4, "EEE", "open", 3)),
    ((1, "CCC", "open", 5), (2, "GGG", "open", 2)),
    ((2, "GGG", "open", 3), (3, "HHH", "open", 1)),
    ((1, "JJJ", "open", 1), (2, "GGG", "open", 4), (3, "HHH", "open", 2), (4, "KKK", "open", 1)),
    ((1, "JJJ", "open", 2), (3, "HHH", "open", 3), (4, "KKK", "open", 2)),
    ((1, "JJJ", "open", 3), (2, "LLL", "open", 1), (3, "HHH", "open", 4), (4, "KKK", "open", 3)),
    ((1, "JJJ", "open", 4), (2, "LLL", "open", 2), (4, "KKK", "open", 4)),
    ((2, "LLL", "open", 3), (4, "KKK", "open", 5)),
    ((2, "LLL", "open", 4),),
)

# Closed trades: symbol -> pnl_usd (from EXPECTED_EVENTS). Sum = 84.6604.
EXPECTED_PNL = {
    "BBB": Decimal("-11.0745"),
    "AAA": Decimal("23.3760"),
    "FFF": Decimal("-24.5760"),
    "EEE": Decimal("17.4120"),
    "CCC": Decimal("36.5628"),
    "GGG": Decimal("31.3720"),
    "HHH": Decimal("-22.1892"),
    "JJJ": Decimal("31.3280"),
    "KKK": Decimal("2.4493"),
}


def test_scenario_runs_on_consecutive_nyse_sessions():
    assert len(SESSIONS) >= 10
    assert SESSIONS == tuple(dates.sessions(S1, S12))
    assert D("2025-11-27") not in SESSIONS  # Thanksgiving: no session, no day counted


def test_scenario_initial_cash():
    assert initial_cash_usd(INITIAL_IDR, USD_IDR) == INITIAL_CASH


def test_scenario_sizing_each_night():
    run = run_scenario()
    p = PICKS
    assert run.placed == (
        (
            _order(S1, 1, p[0][0], 12),
            _order(S1, 2, p[0][1], 30),
            _order(S1, 3, p[0][2], 15),
            _order(S1, 4, p[0][4], 6),
        ),
        (_order(S2, 4, p[1][1], 7),),
        (_order(S3, 3, p[2][0], 20),),
        (_order(S4, 2, p[3][0], 10),),
        (),
        (_order(S6, 3, p[5][0], 26), _order(S6, 4, p[5][1], 19)),  # III capped by cash
        (_order(S7, 1, p[6][0], 40), _order(S7, 4, p[6][1], 7)),
        (),
        (_order(S9, 2, p[8][0], 15),),
        (),
        (),
        (),
    )
    assert run.rejected == (
        (Rejection("XXX", "lt_one_share"), Rejection("YYY", "no_slot")),
        (Rejection("AAA", "held"),),
        (), (), (), (), (), (), (), (), (), (),
    )


def test_scenario_events_each_session():
    run = run_scenario()
    assert len(run.events) == len(EXPECTED_EVENTS)
    for session, got, want in zip(SESSIONS, run.events, EXPECTED_EVENTS):
        assert tuple(_ev(e) for e in got) == want, session


def test_scenario_every_snapshot():
    assert run_scenario().snapshots == EXPECTED_SNAPSHOTS


def test_scenario_live_orders_and_days_held():
    run = run_scenario()
    got = tuple(
        tuple((o.slot, o.symbol, o.status, o.days_held) for o in live) for live in run.live
    )
    assert got == EXPECTED_LIVE


def test_scenario_every_closed_trade_pnl():
    run = run_scenario()
    exits = [e for session in run.events for e in session if e.kind == "exit"]
    assert {e.order.symbol: e.order.pnl_usd for e in exits} == EXPECTED_PNL
    assert len(exits) == len(EXPECTED_PNL)
    assert sum(EXPECTED_PNL.values()) == Decimal("84.6604")
    # Handover §3 formula, unrounded: (exit - fill) * sh - 0.001 * (exit + fill) * sh.
    # The simulator's rounded pnl matches it to within 0.0001.
    for e in exits:
        o = e.order
        formula = (o.exit_price - o.fill_price) * o.shares - Decimal("0.001") * (
            o.exit_price + o.fill_price
        ) * o.shares
        assert abs(o.pnl_usd - formula) <= Decimal("0.0001"), o.symbol


def test_scenario_cash_reconciles_with_events_and_pnl():
    run = run_scenario()
    previous = INITIAL_CASH
    for snap, events in zip(run.snapshots, run.events):
        moved = sum((e.cash_usd for e in events if e.cash_usd is not None), Decimal("0"))
        assert snap.cash_usd - previous == moved, snap.date
        previous = snap.cash_usd
    # Closed P/L reconciles with the cash change once the open position's cost is put back:
    # 985.0996 - 1230.7692 = -245.6696 = 84.6604 - buy_cost(22.00, 15) (330.3300).
    open_cost = sum(
        (buy_cost(o.fill_price, o.shares) for o in run.final.orders if o.status == "open"),
        Decimal("0"),
    )
    assert open_cost == Decimal("330.3300")
    assert run.final.cash - INITIAL_CASH == sum(EXPECTED_PNL.values()) - open_cost
    assert run.final.cash - INITIAL_CASH == Decimal("-245.6696")


def test_scenario_final_portfolio():
    final = run_scenario().final
    assert final.cash == Decimal("985.0996")
    assert final.equity == Decimal("1340.5996")
    assert final.last_session == S12
    assert final.marks == (("LLL", Decimal("23.7000")),)
    assert final.orders == (
        Order(
            session_date=S9,
            slot=2,
            symbol="LLL",
            last_price=P("22.30"),
            limit_price=P("22.00"),
            tp_price=P("24.00"),
            sl_price=P("20.50"),
            shares=15,
            status="open",
            fill_date=S9,
            fill_price=P("22.00"),
            days_held=4,
        ),
    )


def test_scenario_is_deterministic():
    first = run_scenario()
    second = run_scenario()
    assert first == second
    assert repr(first) == repr(second)  # also the exact Decimal spellings
    # The insertion order of the bars mapping must not leak into any output.
    assert repr(run_scenario(reverse_bar_order=True)) == repr(first)


# ---------------------------------------------------------------------------------------
# Benchmark (handover §7): 2,950 sessions x 4 slots on synthetic bars, Decimal throughout.
# ---------------------------------------------------------------------------------------

BENCH_SESSIONS = 2950
BENCH_BOUND_S = 20.0
_LIMIT, _TP, _SL, _LAST = P("99.50"), P("106.00"), P("96.00"), P("100.00")
# (open, high, low, close) shapes against limit 99.50 / TP 106 / SL 96.
_SHAPES = {
    "quiet": (P("100.00"), P("101.00"), P("99.00"), P("100.00")),  # fills a pending order
    "nofill": (P("100.00"), P("101.00"), P("99.60"), P("100.50")),  # low >= limit: expires
    "tp": (P("100.00"), P("107.00"), P("99.00"), P("105.00")),  # high > TP
    "sl": (P("100.00"), P("101.00"), P("95.50"), P("97.00")),  # low <= SL
    "gap": (P("95.00"), P("96.50"), P("94.00"), P("95.50")),  # open <= SL
}
# Each placed order gets the next plan in this cycle; "time" means quiet until the day-6 open.
_PLANS = ("tp", "sl", "time", "expire", "gap", "tp", "sl", "time")
_TRIGGER_DAY = {"tp": 3, "sl": 2, "gap": 4}


def _bench_shape(order: Order, plan: str) -> str:
    if order.status == "pending":
        return "nofill" if plan == "expire" else "quiet"
    return plan if _TRIGGER_DAY.get(plan) == order.days_held + 1 else "quiet"


def test_benchmark_2950_sessions_x_4_slots():
    sessions = dates.sessions(D("2015-01-02"), D("2026-10-02"))[:BENCH_SESSIONS]
    assert len(sessions) == BENCH_SESSIONS
    pf = new_portfolio(Decimal("100000"))
    plan_of: dict[str, str] = {}
    placed_count = 0
    kinds: Counter[tuple[str, str | None]] = Counter()
    snapshots = 0
    started = time.perf_counter()
    for i, session in enumerate(sessions):
        picks = [
            Pick(
                symbol=f"S{i}_{j}",
                last_price=_LAST,
                limit_price=_LIMIT,
                tp_price=_TP,
                sl_price=_SL,
            )
            for j in range(4)
        ]
        sized = size_picks(pf, picks, session)
        for order in sized.placed:
            plan_of[order.symbol] = _PLANS[placed_count % len(_PLANS)]
            placed_count += 1
        bars = {}
        for order in sized.portfolio.orders:
            o, h, lo, c = _SHAPES[_bench_shape(order, plan_of[order.symbol])]
            bars[order.symbol] = Bar(order.symbol, session, o, h, lo, c, 1_000_000)
        result = step(sized.portfolio, session, bars)
        pf = result.portfolio
        snapshots += 1
        for e in result.events:
            kinds[(e.kind, e.order.exit_reason)] += 1
    elapsed = time.perf_counter() - started
    print(f"\nbenchmark: {BENCH_SESSIONS} sessions x 4 slots in {elapsed:.3f} s; {dict(kinds)}")
    assert snapshots == BENCH_SESSIONS
    for key in (("fill", None), ("expire", None), ("exit", "tp"), ("exit", "sl"),
                ("exit", "gap"), ("exit", "time")):
        assert kinds[key] > 0, key
    assert pf.equity > 0
    assert elapsed < BENCH_BOUND_S
```
**Impact:** adds 11 tests and no DB use. The benchmark prints its timing (`pytest -s`), which
Step 3's Performance section quotes. The bound is 20 s (index Decision). Phase 1 measured about
0.18 s, and the stub ran in about 0.11 s.

### Step 3: `engine/package_readme.md`
Four edits, top to bottom. Line numbers refer to the file as it is today; no earlier phase edits it.

**3a. Line 4, Last Updated.** Replace
```
**Last Updated**: 2026-10-03 (P1-ENG-VP1R, phase 1 of `ENGINE_DATA_PIPELINE_PLAN.md`)
```
with
```
**Last Updated**: 2026-10-03 (fill simulator P2, phase 4 of `ENGINE_FILL_SIMULATOR_PLAN.md`: `prices`, `sim`)
```
In the Overview's **Key Responsibilities** list, which ends at line 23, append one bullet after
line 23:
```
- The pure fill simulator (`sim/`): order lifecycle, whole-share sizing, cash/equity and split recompute, shared by the backtest (P3) and nightly paper trading (P4)
```

**3b. Layout (lines 41 and 44).** Replace line 41
```
    bars.py                 Bar value type, rounding, upsert_bars()
```
with
```
    prices.py               pure Bar value type, PRICE_QUANTUM, to_decimal (no DB import)
    bars.py                 re-exports prices; to_volume, make_bar, upsert_bars()
```
and after line 44 (`    runs.py                 start_run / finish_run / fail_run`) insert
```
    sim/                    fill simulator: pure, deterministic, Decimal-only (P2)
      __init__.py           public surface; import everything from seer_engine.sim
      model.py              constants, money helpers, Order, Portfolio, Event, Snapshot, StepResult
      lifecycle.py          step(), close_unpriced()
      sizing.py             Pick, Rejection, SizingResult, size_picks()
      split_adjust.py       apply_split()
```

**3c. Exported API.** Before `### bars` (line 147), insert a `### prices` section. In `### bars`,
replace the three bullets at lines 151–153 (`PRICE_QUANTUM`, `Bar`, `to_decimal`) with the
single bullet below. Then, after the `### demo` section ends (line 203) and before
`## Migration 002` (line 205), insert the `### sim` section.

`### prices` (insert before line 147):
```markdown
### prices

Pure value types for prices, with no database import, so the simulator can use `Bar` without loading `psycopg`. `bars` re-exports all three names, so `from seer_engine.bars import Bar, PRICE_QUANTUM, to_decimal` keeps working.

- `PRICE_QUANTUM = Decimal("0.0001")`
- `@dataclass(frozen, slots) Bar(symbol, date, open, high, low, close: Decimal, volume: int)`
- `to_decimal(x) -> Decimal`: rounds half-up to 4 dp. Floats go through `repr`, so `0.1` becomes `0.1000`. Raises on bool and non-finite values.
```

Replacement for `bars` lines 151–153:
```markdown
- `PRICE_QUANTUM`, `Bar`, `to_decimal`: defined in `prices` and re-exported here unchanged.
```

`### sim` (insert between line 203 and line 205):
````markdown
### sim (fill simulator, P2)

Pure and deterministic: no database, no network, no clock, no randomness, no logging. It imports only `seer_engine.dates` and `seer_engine.prices`, never `bars`, and `tests/test_sim_purity.py` checks in a subprocess that `psycopg`, `requests` and `yfinance` stay out of `sys.modules`. Every value is a frozen dataclass, and every function returns new values. All money and prices are `Decimal`, quantized to 4 dp half-up (`q`). Shares are `int`. A float or any other non-`Decimal` price raises `TypeError`. Import everything from `seer_engine.sim`.

**Rules** (design §5 + handover §3, all tested on synthetic bars):

| Topic | Rule |
|---|---|
| Fill | session `low < limit` (strict; a touch does not fill). Fill at the **open** if `open < limit`, else at the limit. Fill session = day 1 |
| Unfilled | the pending order expires at the end of its session; the slot is free for that night's picks |
| Session order | (1) time stop at the open, (2) gap at the open (`open <= SL` → `gap`, then `open >= TP` → `tp`), (3) intraday `low <= SL` → `sl` at SL, then `high > TP` → `tp` at TP (SL first), (4) fills, (5) expiries, (6) mark to close. A position filled today is not checked against TP/SL today |
| Time stop | `days_held >= 5` and a bar → exit at that bar's open, reason `time`, before any gap/TP/SL check |
| `days_held` | fill session = 1; +1 for every later session survived, bar or not. Intraday exit on day k records k; an exit at the open of day k (time, gap, gap-TP) records k − 1, so a time exit records 5 |
| Costs | `buy_cost = q(price × shares × 1.001)`, `sell_proceeds = q(price × shares × 0.999)`. Fill: `cash -= buy_cost`; exit: `cash += sell_proceeds` |
| `pnl_usd` | `sell_proceeds − buy_cost`, so Σ `pnl_usd` reconciles with cash exactly. Within 0.0001 of handover §3's `(exit − fill) × sh − 0.001 × (exit + fill) × sh` |
| Equity | `q(cash + Σ shares × last known close)` at each session's close. Pending orders reserve nothing in equity |
| Sizing | picks in rank order; each placed pick takes the lowest free slot. `budget = min(q(equity / 4), cash − Σ buy_cost(limit, shares) of pending orders)`, with `equity` the last snapshot. `shares = floor(budget / (limit × 1.001))`. Rejections: `held` (symbol has a live order, or a duplicate pick), then `no_slot`, then `lt_one_share`. A rejection never uses a slot. 0 picks is valid |
| Missing bar | an open position without a bar: no event, the day still counts, marked at the last close. A due time stop waits for the next bar's open. A pending order without a bar expires |
| Holidays | the caller steps NYSE sessions only (`dates.sessions`). `step` raises on a non-session |
| Splits | `apply_split` rewrites live orders in post-split units (see below) |

**Constants and helpers** (`sim.model`):
- `SLOTS = 4`, `TIME_STOP_DAYS = 5`, `COST_RATE = Decimal("0.001")`
- `OrderStatus = Literal["pending", "open", "closed", "expired"]`, `ExitReason = Literal["tp", "sl", "time", "gap"]`, `EventKind = Literal["fill", "expire", "exit", "split"]`
- `q(x) -> Decimal`: quantize to `PRICE_QUANTUM`, half-up.
- `buy_cost(price, shares)`, `sell_proceeds(price, shares) -> Decimal`: as in the table.
- `initial_cash_usd(idr, usd_idr) -> Decimal`: `q(idr / usd_idr)`, with `usd_idr` the IDR price of 1 USD on the start date.

**Values:**
- `Order(session_date, slot, symbol, last_price, limit_price, tp_price, sl_price, shares, status="pending", fill_date=None, fill_price=None, days_held=0, exit_date=None, exit_price=None, exit_reason=None, pnl_usd=None)`: mirrors the `orders` columns except `strategy_id`, `company`, `explanation`, `id` and `created_at`. It validates itself: `slot` is 1–4, `shares >= 1`, `sl < tp`, the fill fields exactly when `open`/`closed`, and the exit fields exactly when `closed`.
- `Portfolio(cash, equity, orders=(), marks=(), last_session=None)`: one strategy's state between sessions.
  - `orders` holds **live** orders only (pending + open), sorted by slot, at most one per slot and one per symbol.
  - `marks` is `(symbol, last close)` for exactly the open symbols, sorted.
  - `equity` is the last snapshot's (or the initial cash).
  - Methods: `open_orders()`, `pending_orders()`, `free_slots()` (ascending), `held_symbols()` (all live, sorted), `mark(symbol)`.
- `new_portfolio(cash_usd) -> Portfolio`: `cash = equity = q(cash_usd)`.
- `Event(session_date, kind, order, forced=False, cash_usd=None)`:
  - `order` is the order state after the event. A terminal order (closed or expired) leaves the portfolio and appears only here, which is where P4 writes it.
  - `cash_usd` is the cash moved: `-buy_cost` on a fill, `+proceeds` on an exit, cash in lieu on a split, and `None` on an expire.
  - `forced=True` marks an exit made without a bar (`close_unpriced`, or a split that floors an open position to 0 shares).
- `Snapshot(date, cash_usd, equity_usd)`: one `equity_snapshots` row.
- `StepResult(portfolio, events, snapshot)`.

**Functions:**
- `step(portfolio, session_date, bars: Mapping[str, Bar]) -> StepResult` (`sim.lifecycle`): advances through one session.
  - `bars` holds split-adjusted bars keyed by symbol. Only bars for symbols with a live order are read and validated; the rest are ignored. A symbol absent from `bars` has no bar this session.
  - **Event order:** all exits in slot order, then all fills in slot order, then all expiries in slot order.
  - Raises `ValueError` when `session_date` is not an NYSE session, is not after `last_session`, or differs from a pending order's `session_date`, or when a bar has the wrong symbol or date. Raises `TypeError` on a non-`Bar` or a non-`Decimal` price.
- `close_unpriced(portfolio, symbols) -> (Portfolio, events)` (`sim.lifecycle`): force-closes open positions that will never get another bar (delisted, halted for good). Each exits at its mark, reason `time`, `exit_date = last_session`, with `forced=True`. It recomputes `equity`, so persist the snapshot after it. The caller decides that no bar will come; a pure step cannot know.
- `Pick(symbol, last_price, limit_price, tp_price, sl_price)` (`sim.sizing`): one ranked pick before sizing. It requires `sl < limit < tp`.
- `size_picks(portfolio, picks, session_date) -> SizingResult(portfolio, placed, rejected)` (`sim.sizing`): sizes the picks for the next session.
  - `placed: tuple[Order, ...]` and `rejected: tuple[Rejection(symbol, reason), ...]` are in pick order. `RejectReason = Literal["no_slot", "held", "lt_one_share"]`.
  - Cash does not change; a pending order pays at its fill.
  - Raises `ValueError` when `session_date` is not a session after `last_session`, or when a pending order for another session is still in the portfolio (step that session first).
- `apply_split(portfolio, symbol, factor, session_date) -> (Portfolio, events)` (`sim.split_adjust`):
  - `factor = split_to / split_from`, the same number as `splits.Split.factor`. 10 is a 10-for-1; `Decimal(1) / 32` is a 1-for-32 reverse split.
  - Call it once per split, after session S−1's `step` and before stepping the execution session S, with `session_date = S`.
  - Prices become `q(p / factor)`, and `shares = floor(shares × factor)`. The open position's fractional remainder is paid as cash in lieu at the adjusted mark, with no cost and outside `pnl_usd`; the amount is on the `split` event's `cash_usd`.
  - A pending order that floors to 0 shares emits `expire`. An open position that floors to 0 is paid out in lieu, emitting a forced `exit` (reason `time`, `pnl_usd = in lieu − buy_cost`).
  - Events are in slot order. `equity` stays at the last snapshot until the next `step` (unlike `close_unpriced`, which recomputes it). The caller applies each split exactly once (`split_adjustments` guarantees this).
  - Raises `ValueError` when a rescaled price or mark rounds to 0 at 4 dp, or SL rounds up to TP, and leaves the input untouched. Real listed stocks never get there.
  - P3 does not need it: backfilled history is already adjusted backwards.

**Determinism:** the same inputs give `==` and `repr`-identical events and snapshots. The insertion order of `bars` does not matter. `tests/test_sim_scenario.py` checks this, and also holds the 12-session hand-checked scenario.
````

**3d. Internal module graph (after line 239).** Append to the `### Internal module graph` list:
```
- `prices` imports only the standard library; `bars` imports `prices` and re-exports it.
- `sim.model` imports `prices`. `sim.lifecycle` and `sim.split_adjust` import `dates`, `prices` and `sim.model`. `sim.sizing` imports `dates` and `sim.model`. Nothing in `sim` imports `bars`, `db` or `http`.
```

**3e. Performance (lines 268–273).** Replace the last bullet, `- There is no benchmark coverage.`, with:
```
- Simulator: `tests/test_sim_scenario.py::test_benchmark_2950_sessions_x_4_slots` runs 2,950 NYSE sessions (2015-01-02 onward) × 4 slots with `size_picks` + `step` every session on synthetic bars, using `Decimal` throughout. Measured: **__MEASURED__ s** on WSL2, Python 3.11 (bound in the test: 20 s). A 10-year backtest is therefore dominated by loading bars and computing signals, not by the simulator. Floats are not needed.
- There is no benchmark coverage for the DB writers.
```
`__MEASURED__` is a placeholder. The implementer runs
`engine/.venv/bin/pytest engine/tests/test_sim_scenario.py -k benchmark -s -q`, reads the
`benchmark: … in X.XXX s` line, and writes the number with 2 decimals. Do not commit the
placeholder.

**3f. Usage (after line 311, the end of the `### Typical write command` code block).** Insert:
````markdown
### Simulator: P3 backtest loop

History is already split-adjusted backwards, so the backtest never calls `apply_split`.

```python
from decimal import Decimal
from seer_engine import dates
from seer_engine.sim import (
    Snapshot, close_unpriced, initial_cash_usd, new_portfolio, size_picks, step,
)

pf = new_portfolio(initial_cash_usd(Decimal("20000000"), usd_idr_on(start)))
events, snapshots = [], []
for session in dates.sessions(start, end):
    picks = strategy.picks(data_date=dates.prev_session(session))  # ranked Picks, made after that close
    pf = size_picks(pf, picks, session).portfolio
    result = step(pf, session, bars_on(session, pf.held_symbols()))  # {symbol: Bar}; missing = no bar
    pf = result.portfolio
    events += result.events
    snapshots.append(result.snapshot)
    gone = delisted_after(session, pf.open_orders())  # P3 knows from data when a symbol's bars end
    if gone:
        pf, forced = close_unpriced(pf, gone)
        events += forced
        snapshots[-1] = Snapshot(session, pf.cash, pf.equity)
```

### Simulator: P4 nightly

One strategy, one night: `rd = dates.run_dates()`. The session to settle is `rd.data_date`, and the picks are for `rd.session_date`.

```python
pf = load_portfolio(conn, strategy_id)
# Portfolio(cash, equity) from the last equity_snapshots row; orders = rows with status
# pending/open, sorted by slot; marks = last close per open symbol; last_session = last snapshot date.
# The marks must be in the same (pre-split) units as the orders: take them from closes as they were
# before splits.apply rescaled history, or apply_split would rescale an already-adjusted mark.
for split in splits_executing_on(conn, rd.data_date):        # recorded by splits.apply this run
    pf, split_events = apply_split(pf, split.symbol, split.factor, rd.data_date)
    persist_events(conn, strategy_id, split_events)            # UPDATE orders prices/shares; cash in lieu
result = step(pf, rd.data_date, bars_on(conn, rd.data_date, pf.held_symbols()))
persist_events(conn, strategy_id, result.events)              # fill/exit/expire -> UPDATE orders
persist_snapshot(conn, strategy_id, result.snapshot)          # equity_snapshots (strategy_id, date)
sized = size_picks(result.portfolio, ranked_picks, rd.session_date)
insert_orders(conn, strategy_id, sized.placed)                # status 'pending', slot 1..4
```

`Event.order` maps 1:1 onto `orders` columns. Its row key is `(strategy_id, order.session_date, order.symbol)`. Everything runs inside one `db.transaction`, so a failed night leaves nothing half-written.
````

### Step 4: ROADMAP status line
**File:** `docs/ROADMAP.md:21`
**Change:** replace
```
## P2 — Fill simulator (critical path)
```
with
```
## P2 — Fill simulator (critical path) · done 2026-10-03 on synthetic bars (`engine/src/seer_engine/sim/`, API in [engine/package_readme.md](../engine/package_readme.md)); P3/P4 wire it in
```
The bullets under it (lines 22–25) stay unchanged.

## Verification

**Setup (worktree, index Invariant 1):** phase 1 Step 0 creates the venv. If it is missing, run
`cd /home/miftah/.worktrees/seer/engine-fill-simulator && python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`
(`python3` is pyenv's 3.11.0). Never run the tests with `/home/miftah/seer/engine/.venv`: it is an
editable install of `/home/miftah/seer` and tests main's tree, not this worktree.
**Build:** the Step 1 **Check** command prints `ok`.
**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_sim_scenario.py -q -s` (11 passed; note the benchmark line)
- `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` → all passed, **0 skipped**. That is the baseline 216, plus phases 1–3, plus 11.
- `grep -n "__MEASURED__" engine/package_readme.md` → no output.

**Manual check:** read the rendered `### sim` section once. Every name in `seer_engine.sim.__all__` appears in it.
**Exit criteria:** `seer_engine.sim` exports the sizing and split names. The scenario test passes with exact Decimals on 12 consecutive NYSE sessions, including the holiday, and twice-run plus reversed-bar-order outputs are `repr`-identical. The benchmark passes under 20 s, and its measured time is in the readme. The readme documents the API, rules, event order and the P3/P4 loops. ROADMAP P2 carries its status line. The full suite is green with 0 skipped.

**If a scenario assertion fails:** recompute that line by hand from the Decisions table first.
The expected values match an independent reference model. A mismatch is either a bug in
phases 1–3, which may be fixed minimally here and named in the commit message, or a typo in the
bars or picks of this file. It is never a reason to edit the expected numbers until they match.

## Handoffs

- **Reconciled:** this phase replaces phase 1's whole `sim/__init__.py`. Step 1 quotes phase 1's 18 names exactly and adds six (24 in all).
- **Reconciled:** the readme's rejection precedence (`held` → `no_slot` → `lt_one_share`, a duplicate pick counted as `held`), phase 3's floor-to-0 open-position behaviour (forced `exit`, reason `time`), the 4-dp `ValueError`, and `close_unpriced` recomputing `equity` all match the reconciled phases 1-3 and the index Decisions.
- **Verified at reconciliation:** this test file, run against the phase 1-3 code blocks in a scratch copy of the engine, passed 11 of 11. Every hand-worked number in the scenario matches the real `step` and `size_picks`.
- **P3 (roadmap):** the backtest runner, the SPY curve, `bars_on` and `delisted_after` are sketches in the readme, not code.
- **P4 (roadmap):** `load_portfolio`, `persist_events`, `persist_snapshot`, `insert_orders` and wiring `apply_split` into `nightly` are sketches in the readme, not code.
- **Not done here (out of scope):** the readme's `## Notes` paragraph, which still describes the data-pipeline phases, and its "Commands (phase 1)" heading are stale wording owned by no phase in this set. Leave them for the next readme refresh.

## Rollback

`git revert <phase-4 sha>`. That restores phase 1's `sim/__init__.py` and removes
`test_sim_scenario.py` and the readme and ROADMAP edits. The sizing and split modules stay
importable as `seer_engine.sim.sizing` / `seer_engine.sim.split_adjust`. Nothing touches the
database.
