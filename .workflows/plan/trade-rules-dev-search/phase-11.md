# Phase 11: The candidate registry (54 entries, append-only test)

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R5 — the candidate registry is committed before the dev run: ≤ 60 entries, append-only, each with a family, rules, fixed params, a rationale and an owner-verification flag
**Depends on:** Phase 5, 6, 7, 8, 9 (and transitively 1, 2, 3)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

`seer_engine.backtest.registry.REGISTRY` holds the 54 pre-registered candidates of the plan
index's **Registry** table, in that order, each a frozen `dev.Candidate` with fixed params, its
`TradeRules` preset, a one-line rationale, its `added` date and its declared owner inputs (the
`needs-owner-verification` flag: non-empty = flagged). `candidate_digest` fingerprints every
entry, and `tests/test_registry.py` pins `(id, digest)` for all 54 so the tuple can only grow
by appending. Every candidate is proven runnable by a short `dev.run_candidate` smoke window on
a synthetic market. The phase ends with the registry **committed**, before any real dev run.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates (all in `engine/src/seer_engine/backtest/registry.py`):**
- `SECTOR_ETFS: tuple[str, ...]` = `("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")` (same value as `research.SECTOR_ETFS`; defined here because `seer_engine.research` is impure and may not be imported by a pure module)
- `FIRST_APPEND: date` — the `added` date of entries 1–54 (the phase-11 commit date)
- `REGISTRY: tuple[Candidate, ...]` — 54 entries, plan-index order
- `candidate_text(c: Candidate) -> str` — the canonical text the digest hashes (public so reports and tests can show it)
- `candidate_digest(c: Candidate) -> str` — `hashlib.sha256(candidate_text(c).encode("utf-8")).hexdigest()`
- `engine/tests/test_registry.py` with the `PINS` literal

**Signature changes:** none

**Interface note (the digest, plan index contract and D-F):** `candidate_text` walks dataclass
fields recursively (`compare=True` fields only, in declaration order), renders allocator and
strategy objects as `<id>`, and covers the **full** `TradeRules` value (every field), not just
its id. It does not hash `params.as_dict()` (that is the report's rendering, which flattens types
to strings). The digest therefore changes if a preset's values change, if any param changes, or if
an id/family changes; it does **not** change for `rationale`, `added` or `owner_inputs`
(`owner_inputs` is derived and separately tested; rationale wording is not a trial parameter).

**Row 54 (plan index D-B):** `F9-SPY200D50-SWING50` is registered under **`SWING_T20`**, exactly
as the index's Registry table says. Its TIMING core part returns `Target(SPY, w)` with
`limit=None`; phase 1's book engine buys an unheld limit-less target under entry `"limit"`
exactly like `open_limit` (limit = last close + 2%), so the row runs as registered. F7's own
entries carry their limits.

**Requires (from earlier phases), exactly these names:**
- Phase 1 `seer_engine.sim.rules`: `DESIGN_V0`, `V0_BOOK`, `MONTHLY_HOLD`, `MONTHLY_HOLD_TBILL`, `WEEKLY_HOLD`, `DAILY_SWITCH`, `DAILY_SWITCH_TBILL`, `SWING_T10`, `SWING_T20`, `SWING_T20_OPEN`, `PRESETS`, `LEVERAGED_ETFS`; `TradeRules` is a frozen dataclass whose fields are `id, engine, cadence, entry, max_positions, time_stop, resize, fractional, dividends, idle_symbol, cost_rate` in that order.
- Phase 2 `seer_engine.strategies.allocator`: `Allocator` (runtime-checkable protocol), `BLEND`, `BlendParams(parts)`, `BlendPart(allocator, params, share)`, `VOLTARGET`, `VolTargetParams(inner, inner_params, signal, target_vol, n)`; every allocator has `.id`, `.symbols(params)`, `.holds(params)`.
- Phase 5 `seer_engine.strategies.f_index`: `TIMING`, `TimingParams(hold, signal, rule, n)`, `CALENDAR`, `CalendarParams(hold, days_before, days_after, trend)`; `TimingParams(rule="always", n=1)` is valid.
- Phase 6 `seer_engine.strategies.f_rotation`: `ROTATION`, `RotationParams(universe, lookback, top, absolute, fallback, trend)`.
- Phase 7 `seer_engine.strategies.f_factor`: `FACTOR`, `FactorParams(rank, top, mom_n, mom_skip, vol_n, pool, sizing, min_dollar_volume, min_price, trend)` with `trend` defaulting to `("SPY", 200)`.
- Phase 8 `seer_engine.strategies.f_swing`: `SWING`, `SwingParams(slots, rsi_n, rsi_max, sma_n, entry, limit_atr, stop_atr, take_atr, exit_sma, exit_rsi, min_dollar_volume, market_trend)`.
- Phase 9 `seer_engine.backtest.dev`: `Candidate(id, family, rules, allocator, params, rationale, added, owner_inputs)` (frozen dataclass, keyword-constructible), `candidate_owner_inputs`, `candidate_window`, `run_candidate(market, dividends, spy_dividends, c, *, prepared=None) -> (RunResult | BookResult, DevRow)`, `DevRow.candidate/.start/.end`, `MAX_CANDIDATES`, `DEV_END`.
- Phase 3 `seer_engine.backtest.book_runner.BookResult` (has `.snapshots`, each with `.date`).

**Leaves alone (owned by others):** every other module. In particular `sim/rules.py` (1),
`strategies/allocator.py` (2), `backtest/book_runner.py` (3), `seer_engine/research.py` (4),
`strategies/f_*.py` (5–8), `backtest/dev.py` (9), `backtest/dev_report.py` (10),
`commands/backtest_dev.py` and `backtest/io.py` (12), docs (13). No `__init__.py` export is added.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/registry.py` | create (line 1) | `SECTOR_ETFS`, `FIRST_APPEND`, `REGISTRY` (54 entries), `candidate_text`, `candidate_digest` |
| `engine/tests/test_registry.py` | create (line 1) | identity, append-only pins, owner inputs, pairing, family checks, 54 smoke runs |

## Implementation Steps

### Step 1: Write the registry module
**File:** `engine/src/seer_engine/backtest/registry.py:1` (new)
**Change:** the whole module below. `FIRST_APPEND` is the date on which the phase-11 commit is
made: if you implement on a day other than 2026-10-03, change that one literal to today's date
(it is then written once and never edited again). Rationales are the index table's text,
verbatim.
**Code:**
```python
"""The P7a candidate registry (handover D6, plan phase 11).

Pure. ``REGISTRY`` is every strategy the P7a dev run tries, fixed BEFORE the run: a family, a
``TradeRules`` preset, fixed parameters, a one-line rationale, the date it was appended and the
owner inputs it depends on (``owner_inputs`` non-empty = needs-owner-verification; such a
candidate cannot become a finalist, D8).

The rules of this file (handover D6):

- **Append only.** Never edit, reorder or remove an entry. ``tests/test_registry.py`` pins
  ``(id, candidate_digest)`` for every entry; changing a pinned candidate fails that test.
- **Size cap.** ``len(REGISTRY) <= dev.MAX_CANDIDATES`` (60).
- **An append** adds the new ``Candidate`` at the end with its own ``added`` date, adds its pin
  line at the end of ``PINS`` in the test, and is committed (this file and the pin together)
  **before** the dev run that includes it. ``backtest_dev`` refuses a dirty registry.

``candidate_text`` is the canonical text of a candidate's trial-defining parts (id, family,
every ``TradeRules`` field, the allocator id, every parameter, recursively);
``candidate_digest`` is its sha256.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.sim.rules import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    WEEKLY_HOLD,
    TradeRules,
)
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.allocator import (
    BLEND,
    VOLTARGET,
    Allocator,
    BlendParams,
    BlendPart,
    VolTargetParams,
)
from seer_engine.strategies.base import Strategy
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import CALENDAR, TIMING, CalendarParams, TimingParams
from seer_engine.strategies.f_rotation import ROTATION, RotationParams
from seer_engine.strategies.f_swing import SWING, SwingParams

# The nine original Select Sector SPDRs (1998). Same value as seer_engine.research.SECTOR_ETFS,
# which a pure module may not import.
SECTOR_ETFS: tuple[str, ...] = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")

# The date of the commit that registered entries 1-54 (D6 timestamp). Never edited afterwards.
FIRST_APPEND = date(2026, 10, 3)

_SECTOR_FLAGS: tuple[str, ...] = tuple(f"etf:{s}" for s in SECTOR_ETFS)


def _c(
    id: str,
    family: str,
    rules: TradeRules,
    allocator: Allocator | Strategy,
    params: Any,
    rationale: str,
    owner_inputs: tuple[str, ...] = (),
    added: date = FIRST_APPEND,
) -> Candidate:
    return Candidate(
        id=id,
        family=family,
        rules=rules,
        allocator=allocator,
        params=params,
        rationale=rationale,
        added=added,
        owner_inputs=owner_inputs,
    )


REGISTRY: tuple[Candidate, ...] = (
    # ---- 2026-10-03: the first registry (plan index "Registry", rows 1-54) ----------------
    _c("REF-SPY-HOLD", "REF", MONTHLY_HOLD,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="always", n=1),
       "Sanity reference: SPY held with dividends should track SPY TR minus whole-share cash drag"),
    _c("REF-A-V0", "REF", DESIGN_V0,
       STRATEGY_A, DESIGN_PARAMS,
       "A's idea under the closed §5 rules on fresh data: is A's failure specific to 2015–2026?"),
    _c("F1-SPY-SMA200-D", "F1", DAILY_SWITCH,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
       "The classic drawdown cutter, checked nightly"),
    _c("F1-SPY-SMA200-M", "F1", MONTHLY_HOLD,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
       "Same signal, monthly: fewer whipsaws"),
    _c("F1-SPY-SMA100-D", "F1", DAILY_SWITCH,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=100),
       "A faster filter cuts crashes sooner"),
    _c("F1-SPY-SMA50-D", "F1", DAILY_SWITCH,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=50),
       "Fastest filter; more trades, more whipsaw"),
    _c("F1-SPY-10MSMA-M", "F1", MONTHLY_HOLD,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="month_sma", n=10),
       "Faber's 10-month rule"),
    _c("F1-SPY-ABS12-M", "F1", MONTHLY_HOLD,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="abs_mom", n=252),
       "12-month absolute momentum (vs 0, T-bills unavailable by default)"),
    _c("F1-SPY-SMA200-D-TBILL", "F1", DAILY_SWITCH_TBILL,
       TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
       "Idle cash in T-bills (BIL from 2007)",
       owner_inputs=("etf:BIL",)),
    _c("F1-QQQ-SMA200-D", "F1", DAILY_SWITCH,
       TIMING, TimingParams(hold="QQQ", signal="QQQ", rule="sma", n=200),
       "Tech-led index adds return in bull eras"),
    _c("F1-QQQ-SMA200-M", "F1", MONTHLY_HOLD,
       TIMING, TimingParams(hold="QQQ", signal="QQQ", rule="sma", n=200),
       "Monthly variant"),
    _c("F1-QQQ-SMA100-D", "F1", DAILY_SWITCH,
       TIMING, TimingParams(hold="QQQ", signal="QQQ", rule="sma", n=100),
       "QQQ's faster crashes need a faster filter"),
    _c("F1-QQQ-SPYSIG-D", "F1", DAILY_SWITCH,
       TIMING, TimingParams(hold="QQQ", signal="SPY", rule="sma", n=200),
       "Hold QQQ, time on the broader market"),
    _c("F1-QQQ-10MSMA-M", "F1", MONTHLY_HOLD,
       TIMING, TimingParams(hold="QQQ", signal="QQQ", rule="month_sma", n=10),
       "10-month rule on QQQ"),
    _c("F1-SPY-VT12-W", "F1", WEEKLY_HOLD,
       VOLTARGET, VolTargetParams(
           inner=TIMING,
           inner_params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
           signal="SPY", target_vol=Decimal("0.12"), n=20),
       "Trend filter plus 12% vol targeting"),
    _c("F1-QQQ-VT15-W", "F1", WEEKLY_HOLD,
       VOLTARGET, VolTargetParams(
           inner=TIMING,
           inner_params=TimingParams(hold="QQQ", signal="QQQ", rule="sma", n=200),
           signal="QQQ", target_vol=Decimal("0.15"), n=20),
       "QQQ with 15% vol targeting"),
    _c("F10-SSO-SMA200-D", "F10", DAILY_SWITCH,
       TIMING, TimingParams(hold="SSO", signal="SPY", rule="sma", n=200),
       "2× S&P only above trend (owner: leverage)",
       owner_inputs=("etf:SSO", "leverage")),
    _c("F10-QLD-SMA200-D", "F10", DAILY_SWITCH,
       TIMING, TimingParams(hold="QLD", signal="QQQ", rule="sma", n=200),
       "2× Nasdaq only above trend (owner: leverage)",
       owner_inputs=("etf:QLD", "leverage")),
    _c("F10-SSO-10MSMA-M", "F10", MONTHLY_HOLD,
       TIMING, TimingParams(hold="SSO", signal="SPY", rule="month_sma", n=10),
       "Leveraged 10-month rule",
       owner_inputs=("etf:SSO", "leverage")),
    _c("F11-SPY-TOM", "F11", DAILY_SWITCH,
       CALENDAR, CalendarParams(hold="SPY", days_before=1, days_after=3, trend=None),
       "Turn-of-month effect: low exposure, low DD"),
    _c("F11-SPY-TOM-TREND", "F11", DAILY_SWITCH,
       CALENDAR, CalendarParams(hold="SPY", days_before=1, days_after=3, trend=("SPY", 200)),
       "Turn of month, only above trend"),
    _c("F11-QQQ-TOM-TREND", "F11", DAILY_SWITCH,
       CALENDAR, CalendarParams(hold="QQQ", days_before=1, days_after=3, trend=("QQQ", 200)),
       "Turn of month on QQQ above trend"),
    _c("F2-SPYQQQ-12M", "F2", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=("QQQ", "SPY"), lookback=252, top=1,
                                absolute=True, fallback=None, trend=None),
       "Dual momentum with default ETFs only"),
    _c("F2-SPYQQQ-6M", "F2", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=("QQQ", "SPY"), lookback=126, top=1,
                                absolute=True, fallback=None, trend=None),
       "Faster lookback"),
    _c("F2-SPYQQQ-3M", "F2", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=("QQQ", "SPY"), lookback=63, top=1,
                                absolute=True, fallback=None, trend=None),
       "Fastest lookback"),
    _c("F2-SPYQQQ-12M-IEF", "F2", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=("QQQ", "SPY"), lookback=252, top=1,
                                absolute=True, fallback="IEF", trend=None),
       "Bonds instead of cash when risk-off (owner: IEF)",
       owner_inputs=("etf:IEF",)),
    _c("F2-GEM-SPYEFA-IEF", "F2", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=("EFA", "SPY"), lookback=252, top=1,
                                absolute=True, fallback="IEF", trend=None),
       "Classic GEM: US vs international, else bonds (owner: EFA, IEF)",
       owner_inputs=("etf:EFA", "etf:IEF")),
    _c("F3-SEC-TOP3-6M", "F3", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=SECTOR_ETFS, lookback=126, top=3,
                                absolute=True, fallback=None, trend=None),
       "Sector leadership with an absolute filter (owner: sector ETFs)",
       owner_inputs=_SECTOR_FLAGS),
    _c("F3-SEC-TOP3-12M", "F3", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=SECTOR_ETFS, lookback=252, top=3,
                                absolute=True, fallback=None, trend=None),
       "12-month lookback",
       owner_inputs=_SECTOR_FLAGS),
    _c("F3-SEC-TOP2-3M", "F3", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=SECTOR_ETFS, lookback=63, top=2,
                                absolute=True, fallback=None, trend=None),
       "Short lookback, concentrated",
       owner_inputs=_SECTOR_FLAGS),
    _c("F3-SEC-TOP3-6M-TREND", "F3", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=SECTOR_ETFS, lookback=126, top=3,
                                absolute=True, fallback=None, trend=("SPY", 200)),
       "Plus a market trend filter",
       owner_inputs=_SECTOR_FLAGS),
    _c("F3-SEC-TOP3-6M-IEF", "F3", MONTHLY_HOLD,
       ROTATION, RotationParams(universe=SECTOR_ETFS, lookback=126, top=3,
                                absolute=True, fallback="IEF", trend=None),
       "Unused slots in bonds",
       owner_inputs=("etf:IEF",) + _SECTOR_FLAGS),
    _c("F4-MOM12-N10", "F4", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=10, trend=None),
       "Plain 12-1 momentum, no filter"),
    _c("F4-MOM12-N10-TREND", "F4", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=10),
       "Momentum with a SPY 200-day filter"),
    _c("F4-MOM12-N20-TREND", "F4", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=20),
       "More names, lower DD"),
    _c("F4-MOM12-N5-TREND", "F4", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=5),
       "Concentrated"),
    _c("F4-MOM6-N10-TREND", "F4", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=10, mom_n=126),
       "6-1 momentum"),
    _c("F4-MOM12-N10-TREND-IVOL", "F4", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=10, sizing="inverse_vol"),
       "Vol-scaled sizing (L3)"),
    _c("F4-MOM12-N10-TREND-W", "F4", WEEKLY_HOLD,
       FACTOR, FactorParams(rank="momentum", top=10),
       "Weekly re-ranking"),
    _c("F5-LV60-N20", "F5", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="lowvol", top=20, trend=None),
       "Least-volatile large caps"),
    _c("F5-LV60-N20-TREND", "F5", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="lowvol", top=20),
       "Plus the trend filter"),
    _c("F5-LV252-N20-TREND", "F5", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="lowvol", top=20, vol_n=252),
       "Year-long volatility"),
    _c("F6-ML-P50-N10-TREND", "F6", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="mom_lowvol", top=10, pool=50),
       "Momentum among calmer names"),
    _c("F6-ML-P50-N20-TREND", "F6", MONTHLY_HOLD,
       FACTOR, FactorParams(rank="mom_lowvol", top=20, pool=50),
       "Broader"),
    _c("F6-ML-P50-N10-VT12", "F6", WEEKLY_HOLD,
       VOLTARGET, VolTargetParams(
           inner=FACTOR,
           inner_params=FactorParams(rank="mom_lowvol", top=10, pool=50),
           signal="SPY", target_vol=Decimal("0.12"), n=20),
       "Plus vol targeting"),
    _c("F7-RSI2-T20-DIP", "F7", SWING_T20,
       SWING, SwingParams(),
       "A's idea, longer horizon, no TP, signal exit"),
    _c("F7-RSI2-T10-DIP", "F7", SWING_T10,
       SWING, SwingParams(),
       "Shorter horizon"),
    _c("F7-RSI2-T20-CLOSE", "F7", SWING_T20,
       SWING, SwingParams(entry="close"),
       "Limit at the close: less adverse selection"),
    _c("F7-RSI2-T20-OPEN", "F7", SWING_T20_OPEN,
       SWING, SwingParams(),
       "Enter at the open (marketable limit)"),
    _c("F7-RSI2-T20-N8", "F7", SWING_T20,
       SWING, SwingParams(slots=8),
       "More, smaller positions"),
    _c("F7-RSI2-T20-TREND", "F7", SWING_T20,
       SWING, SwingParams(market_trend=("SPY", 200)),
       "No new entries in a down market"),
    _c("F7-RSI2-T20-NOSTOP", "F7", SWING_T20,
       SWING, SwingParams(stop_atr=None),
       "No stop: exits by signal or time only"),
    _c("F9-SPY200M70-MOM30", "F9", MONTHLY_HOLD,
       BLEND, BlendParams(parts=(
           BlendPart(allocator=TIMING,
                     params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
                     share=Decimal("0.7")),
           BlendPart(allocator=FACTOR,
                     params=FactorParams(rank="momentum", top=10),
                     share=Decimal("0.3")),
       )),
       "Timed SPY core, momentum satellite"),
    _c("F9-SPY200D50-SWING50", "F9", SWING_T20,
       BLEND, BlendParams(parts=(
           BlendPart(allocator=TIMING,
                     params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
                     share=Decimal("0.5")),
           BlendPart(allocator=SWING,
                     params=SwingParams(),
                     share=Decimal("0.5")),
       )),
       "Timed SPY core, swing satellite in the idle half"),
)


def _canon(value: Any) -> str:
    """One value as deterministic text. Order of the checks matters (bool before int,
    allocator/strategy objects before dataclasses)."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return "(" + ",".join(_canon(v) for v in value) + ")"
    if isinstance(value, (Allocator, Strategy)):
        return f"<{value.id}>"
    if is_dataclass(value) and not isinstance(value, type):
        inner = ",".join(
            f"{f.name}={_canon(getattr(value, f.name))}" for f in fields(value) if f.compare
        )
        return f"{type(value).__name__}({inner})"
    raise TypeError(f"no canonical text for a {type(value).__name__}: {value!r}")


def candidate_text(c: Candidate) -> str:
    """The canonical text of everything that defines ``c`` as a trial (not its rationale,
    ``added`` date or derived owner inputs), one ``key=value`` line each, LF-terminated."""
    lines = (
        f"id={c.id}",
        f"family={c.family}",
        f"rules={_canon(c.rules)}",
        f"allocator=<{c.allocator.id}>",
        f"params={_canon(c.params)}",
    )
    return "\n".join(lines) + "\n"


def candidate_digest(c: Candidate) -> str:
    """sha256 (hex) of ``candidate_text(c)`` in UTF-8: the value ``tests/test_registry.py`` pins."""
    return hashlib.sha256(candidate_text(c).encode("utf-8")).hexdigest()
```
**Impact:** new pure module, covered by `test_strategy_purity.py`'s `backtest/*.py` glob
(`hashlib` is not a forbidden import; no clock, I/O or print). Nothing imports it yet (phase 12
will).

### Step 2: Write the test file (with an unpinned `PINS` block)
**File:** `engine/tests/test_registry.py:1` (new)
**Change:** the whole file below. The `PINS` block is written with `"UNPINNED"` digests; Step 3
replaces it with the real digests. Until then `test_pins_are_real_digests`,
`test_registry_is_append_only_against_the_pins` and `test_every_entry_is_pinned` fail — that is
intended, so an unpinned file can never be committed green.
**Code:**
```python
"""The P7a candidate registry (handover D6, §7.5; plan phase 11).

- Identity: unique, well-formed ids, at most ``MAX_CANDIDATES`` entries, the first 54 exactly the
  plan index's Registry table in order.
- Append only: ``PINS`` holds ``(id, candidate_digest)`` for every entry. Editing, reordering or
  removing a registered candidate changes a pinned digest and fails here. An append adds its pin
  line at the END of ``PINS`` in the same commit as the registry entry, before its dev run.
- Owner inputs: the declared ``owner_inputs`` equal ``dev.candidate_owner_inputs``, and the
  flagged set is exactly the planned one.
- Pairing: presets only (never ``V0_BOOK``), ``DESIGN_V0`` only with a bracket ``Strategy``, a
  ``"limit"`` entry only for families that price their entries, families match allocators.
- Smoke: every candidate runs a short window through ``dev.run_candidate`` on a synthetic market
  holding every fixed symbol the registry reads plus a few member stocks.

Re-pin (after an append only):
    engine/.venv/bin/python -c "from seer_engine.backtest.registry import REGISTRY, candidate_digest; [print(f'    ({c.id!r}, {candidate_digest(c)!r}),') for c in REGISTRY]"
and paste the NEW lines at the end of PINS. Existing lines are never changed.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.book_runner import BookResult
from seer_engine.backtest.dev import (
    DEV_END,
    MAX_CANDIDATES,
    candidate_owner_inputs,
    candidate_window,
    run_candidate,
)
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.registry import (
    FIRST_APPEND,
    REGISTRY,
    SECTOR_ETFS,
    candidate_digest,
    candidate_text,
)
from seer_engine.backtest.runner import RunResult
from seer_engine.sim.rules import (
    DESIGN_V0,
    LEVERAGED_ETFS,
    PRESETS,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    V0_BOOK,
)
from seer_engine.strategies.allocator import BLEND, VOLTARGET, Allocator
from seer_engine.strategies.base import History, Strategy
from seer_engine.strategies.f_index import TimingParams

ID_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
FAMILIES = frozenset({"REF", *(f"F{i}" for i in range(1, 12))})
SWING_PRESETS = (SWING_T10, SWING_T20, SWING_T20_OPEN)
# Leaf allocator ids allowed under rules.entry == "limit": F7 and PICKS price their entries; F1's
# limit-less targets are bought by the engine's open_limit fallback (plan index D-B, row 54's core).
PRICED_ENTRY_LEAVES = frozenset({"F1", "F7", "PICKS"})
# The leaf allocator id each catalogue family must use (F9 is a BLEND, REF is free).
FAMILY_LEAF = {
    "F1": "F1", "F10": "F1", "F11": "F11",
    "F2": "ROT", "F3": "ROT",
    "F4": "FAC", "F5": "FAC", "F6": "FAC",
    "F7": "F7",
}
FACTOR_RANK = {"F4": "momentum", "F5": "lowvol", "F6": "mom_lowvol"}

# The plan index's Registry table, rows 1-54, in order (id, family).
PLAN_ROWS: tuple[tuple[str, str], ...] = (
    ("REF-SPY-HOLD", "REF"),
    ("REF-A-V0", "REF"),
    ("F1-SPY-SMA200-D", "F1"),
    ("F1-SPY-SMA200-M", "F1"),
    ("F1-SPY-SMA100-D", "F1"),
    ("F1-SPY-SMA50-D", "F1"),
    ("F1-SPY-10MSMA-M", "F1"),
    ("F1-SPY-ABS12-M", "F1"),
    ("F1-SPY-SMA200-D-TBILL", "F1"),
    ("F1-QQQ-SMA200-D", "F1"),
    ("F1-QQQ-SMA200-M", "F1"),
    ("F1-QQQ-SMA100-D", "F1"),
    ("F1-QQQ-SPYSIG-D", "F1"),
    ("F1-QQQ-10MSMA-M", "F1"),
    ("F1-SPY-VT12-W", "F1"),
    ("F1-QQQ-VT15-W", "F1"),
    ("F10-SSO-SMA200-D", "F10"),
    ("F10-QLD-SMA200-D", "F10"),
    ("F10-SSO-10MSMA-M", "F10"),
    ("F11-SPY-TOM", "F11"),
    ("F11-SPY-TOM-TREND", "F11"),
    ("F11-QQQ-TOM-TREND", "F11"),
    ("F2-SPYQQQ-12M", "F2"),
    ("F2-SPYQQQ-6M", "F2"),
    ("F2-SPYQQQ-3M", "F2"),
    ("F2-SPYQQQ-12M-IEF", "F2"),
    ("F2-GEM-SPYEFA-IEF", "F2"),
    ("F3-SEC-TOP3-6M", "F3"),
    ("F3-SEC-TOP3-12M", "F3"),
    ("F3-SEC-TOP2-3M", "F3"),
    ("F3-SEC-TOP3-6M-TREND", "F3"),
    ("F3-SEC-TOP3-6M-IEF", "F3"),
    ("F4-MOM12-N10", "F4"),
    ("F4-MOM12-N10-TREND", "F4"),
    ("F4-MOM12-N20-TREND", "F4"),
    ("F4-MOM12-N5-TREND", "F4"),
    ("F4-MOM6-N10-TREND", "F4"),
    ("F4-MOM12-N10-TREND-IVOL", "F4"),
    ("F4-MOM12-N10-TREND-W", "F4"),
    ("F5-LV60-N20", "F5"),
    ("F5-LV60-N20-TREND", "F5"),
    ("F5-LV252-N20-TREND", "F5"),
    ("F6-ML-P50-N10-TREND", "F6"),
    ("F6-ML-P50-N20-TREND", "F6"),
    ("F6-ML-P50-N10-VT12", "F6"),
    ("F7-RSI2-T20-DIP", "F7"),
    ("F7-RSI2-T10-DIP", "F7"),
    ("F7-RSI2-T20-CLOSE", "F7"),
    ("F7-RSI2-T20-OPEN", "F7"),
    ("F7-RSI2-T20-N8", "F7"),
    ("F7-RSI2-T20-TREND", "F7"),
    ("F7-RSI2-T20-NOSTOP", "F7"),
    ("F9-SPY200M70-MOM30", "F9"),
    ("F9-SPY200D50-SWING50", "F9"),
)

_SECTOR_FLAGS = tuple(f"etf:{s}" for s in SECTOR_ETFS)
# Every candidate that needs owner verification, and exactly what it needs (handover "Owner inputs").
FLAGGED: dict[str, tuple[str, ...]] = {
    "F1-SPY-SMA200-D-TBILL": ("etf:BIL",),
    "F10-SSO-SMA200-D": ("etf:SSO", "leverage"),
    "F10-QLD-SMA200-D": ("etf:QLD", "leverage"),
    "F10-SSO-10MSMA-M": ("etf:SSO", "leverage"),
    "F2-SPYQQQ-12M-IEF": ("etf:IEF",),
    "F2-GEM-SPYEFA-IEF": ("etf:EFA", "etf:IEF"),
    "F3-SEC-TOP3-6M": _SECTOR_FLAGS,
    "F3-SEC-TOP3-12M": _SECTOR_FLAGS,
    "F3-SEC-TOP2-3M": _SECTOR_FLAGS,
    "F3-SEC-TOP3-6M-TREND": _SECTOR_FLAGS,
    "F3-SEC-TOP3-6M-IEF": ("etf:IEF",) + _SECTOR_FLAGS,
}

# (id, candidate_digest) for every registered candidate, in registry order. APPEND ONLY.
PINS: tuple[tuple[str, str], ...] = (
    ("REF-SPY-HOLD", "UNPINNED"),
    ("REF-A-V0", "UNPINNED"),
    ("F1-SPY-SMA200-D", "UNPINNED"),
    ("F1-SPY-SMA200-M", "UNPINNED"),
    ("F1-SPY-SMA100-D", "UNPINNED"),
    ("F1-SPY-SMA50-D", "UNPINNED"),
    ("F1-SPY-10MSMA-M", "UNPINNED"),
    ("F1-SPY-ABS12-M", "UNPINNED"),
    ("F1-SPY-SMA200-D-TBILL", "UNPINNED"),
    ("F1-QQQ-SMA200-D", "UNPINNED"),
    ("F1-QQQ-SMA200-M", "UNPINNED"),
    ("F1-QQQ-SMA100-D", "UNPINNED"),
    ("F1-QQQ-SPYSIG-D", "UNPINNED"),
    ("F1-QQQ-10MSMA-M", "UNPINNED"),
    ("F1-SPY-VT12-W", "UNPINNED"),
    ("F1-QQQ-VT15-W", "UNPINNED"),
    ("F10-SSO-SMA200-D", "UNPINNED"),
    ("F10-QLD-SMA200-D", "UNPINNED"),
    ("F10-SSO-10MSMA-M", "UNPINNED"),
    ("F11-SPY-TOM", "UNPINNED"),
    ("F11-SPY-TOM-TREND", "UNPINNED"),
    ("F11-QQQ-TOM-TREND", "UNPINNED"),
    ("F2-SPYQQQ-12M", "UNPINNED"),
    ("F2-SPYQQQ-6M", "UNPINNED"),
    ("F2-SPYQQQ-3M", "UNPINNED"),
    ("F2-SPYQQQ-12M-IEF", "UNPINNED"),
    ("F2-GEM-SPYEFA-IEF", "UNPINNED"),
    ("F3-SEC-TOP3-6M", "UNPINNED"),
    ("F3-SEC-TOP3-12M", "UNPINNED"),
    ("F3-SEC-TOP2-3M", "UNPINNED"),
    ("F3-SEC-TOP3-6M-TREND", "UNPINNED"),
    ("F3-SEC-TOP3-6M-IEF", "UNPINNED"),
    ("F4-MOM12-N10", "UNPINNED"),
    ("F4-MOM12-N10-TREND", "UNPINNED"),
    ("F4-MOM12-N20-TREND", "UNPINNED"),
    ("F4-MOM12-N5-TREND", "UNPINNED"),
    ("F4-MOM6-N10-TREND", "UNPINNED"),
    ("F4-MOM12-N10-TREND-IVOL", "UNPINNED"),
    ("F4-MOM12-N10-TREND-W", "UNPINNED"),
    ("F5-LV60-N20", "UNPINNED"),
    ("F5-LV60-N20-TREND", "UNPINNED"),
    ("F5-LV252-N20-TREND", "UNPINNED"),
    ("F6-ML-P50-N10-TREND", "UNPINNED"),
    ("F6-ML-P50-N20-TREND", "UNPINNED"),
    ("F6-ML-P50-N10-VT12", "UNPINNED"),
    ("F7-RSI2-T20-DIP", "UNPINNED"),
    ("F7-RSI2-T10-DIP", "UNPINNED"),
    ("F7-RSI2-T20-CLOSE", "UNPINNED"),
    ("F7-RSI2-T20-OPEN", "UNPINNED"),
    ("F7-RSI2-T20-N8", "UNPINNED"),
    ("F7-RSI2-T20-TREND", "UNPINNED"),
    ("F7-RSI2-T20-NOSTOP", "UNPINNED"),
    ("F9-SPY200M70-MOM30", "UNPINNED"),
    ("F9-SPY200D50-SWING50", "UNPINNED"),
)


def _by_id(cid: str):
    return next(c for c in REGISTRY if c.id == cid)


def _leaves(allocator: Any, params: Any) -> list[tuple[Any, Any]]:
    """The (allocator, params) leaves under BLEND and VOLTARGET overlays, in part order."""
    if allocator is BLEND:
        out: list[tuple[Any, Any]] = []
        for part in params.parts:
            out += _leaves(part.allocator, part.params)
        return out
    if allocator is VOLTARGET:
        return _leaves(params.inner, params.inner_params)
    return [(allocator, params)]


# ---- identity -------------------------------------------------------------------------------


def test_ids_are_unique_and_well_formed():
    ids = [c.id for c in REGISTRY]
    assert len(ids) == len(set(ids))
    assert all(ID_RE.match(i) for i in ids), [i for i in ids if not ID_RE.match(i)]


def test_registry_size_is_within_the_cap():
    assert MAX_CANDIDATES == 60
    assert 54 <= len(REGISTRY) <= MAX_CANDIDATES


def test_first_54_are_the_plan_index_table_in_order():
    assert tuple((c.id, c.family) for c in REGISTRY[:54]) == PLAN_ROWS


def test_families_are_catalogue_labels_and_prefix_the_id():
    for c in REGISTRY:
        assert c.family in FAMILIES, c.id
        assert c.id.startswith(c.family + "-"), c.id


def test_rationales_are_one_non_empty_line():
    for c in REGISTRY:
        assert isinstance(c.rationale, str) and c.rationale.strip() == c.rationale, c.id
        assert c.rationale and "\n" not in c.rationale, c.id


def test_added_dates_are_append_ordered():
    assert all(c.added == FIRST_APPEND for c in REGISTRY[:54])
    assert FIRST_APPEND >= date(2026, 10, 3)  # never before the handover that defines it
    added = [c.added for c in REGISTRY]
    assert added == sorted(added)
    assert added[-1] <= date.today()


# ---- append only ----------------------------------------------------------------------------


def test_pins_are_real_digests():
    assert len({i for i, _ in PINS}) == len(PINS)
    bad = [i for i, d in PINS if not HEX64_RE.match(d)]
    assert bad == [], f"unpinned: {bad} (run the re-pin command in this file's docstring)"


def test_registry_is_append_only_against_the_pins():
    assert len(REGISTRY) >= len(PINS), "a pinned candidate was removed"
    current = tuple((c.id, candidate_digest(c)) for c in REGISTRY[: len(PINS)])
    changed = [p[0] for p, c in zip(PINS, current) if p != c]
    assert changed == [], f"pinned candidates changed or moved: {changed}"


def test_every_entry_is_pinned():
    assert len(PINS) == len(REGISTRY), "an appended candidate has no pin line yet"


def test_candidate_text_format():
    text = candidate_text(REGISTRY[0])
    assert text.startswith("id=REF-SPY-HOLD\nfamily=REF\nrules=TradeRules(id='monthly-hold',engine='book',")
    assert text.endswith(
        "\nallocator=<F1>\nparams=TimingParams(hold='SPY',signal='SPY',rule='always',n=1)\n"
    )
    assert "cost_rate=0.001" in text
    assert candidate_text(_by_id("REF-A-V0")).splitlines()[3] == "allocator=<A>"
    blend = candidate_text(_by_id("F9-SPY200M70-MOM30"))
    assert "params=BlendParams(parts=(BlendPart(allocator=<F1>," in blend
    assert "share=0.7)" in blend and "share=0.3)" in blend


def test_digest_covers_the_trial_and_ignores_the_prose():
    c = _by_id("F1-SPY-SMA200-D")
    d = candidate_digest(c)
    assert HEX64_RE.match(d)
    assert candidate_digest(replace(c)) == d
    assert candidate_digest(replace(c, rationale="different words")) == d
    assert candidate_digest(replace(c, added=date(2030, 1, 1))) == d
    assert candidate_digest(replace(c, params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=201))) != d
    assert candidate_digest(replace(c, rules=_by_id("F1-SPY-SMA200-M").rules)) != d
    assert candidate_digest(replace(c, id="F1-SPY-SMA200-X")) != d
    assert len({candidate_digest(x) for x in REGISTRY}) == len(REGISTRY)


# ---- owner inputs ---------------------------------------------------------------------------


def test_declared_owner_inputs_match_the_computed_ones():
    wrong = [(c.id, c.owner_inputs, candidate_owner_inputs(c))
             for c in REGISTRY if c.owner_inputs != candidate_owner_inputs(c)]
    assert wrong == []


def test_flagged_candidates_are_exactly_the_planned_ones():
    flagged = {c.id: c.owner_inputs for c in REGISTRY[:54] if c.owner_inputs}
    assert flagged == FLAGGED
    assert sum(1 for c in REGISTRY[:54] if not c.owner_inputs) == 43


# ---- rules / allocator pairing -------------------------------------------------------------


def test_rules_are_registry_presets_never_v0_book():
    for c in REGISTRY:
        assert any(c.rules is p for p in PRESETS), c.id
        assert c.rules is not V0_BOOK, c.id


def test_design_v0_only_with_a_bracket_strategy():
    for c in REGISTRY:
        is_strategy = isinstance(c.allocator, Strategy) and not isinstance(c.allocator, Allocator)
        assert (c.rules is DESIGN_V0) == is_strategy, c.id
        if c.rules is not DESIGN_V0:
            assert c.rules.engine == "book" and isinstance(c.allocator, Allocator), c.id


def test_limit_entry_only_for_families_that_price_their_entries():
    for c in REGISTRY:
        if c.rules is DESIGN_V0 or c.rules.entry != "limit":
            continue
        ids = {a.id for a, _ in _leaves(c.allocator, c.params)}
        assert ids <= PRICED_ENTRY_LEAVES, (c.id, ids)


def test_swing_rules_go_with_the_swing_family():
    for c in REGISTRY:
        if c.rules is DESIGN_V0:
            continue
        ids = {a.id for a, _ in _leaves(c.allocator, c.params)}
        if c.family == "F7":
            assert any(c.rules is r for r in SWING_PRESETS), c.id
            assert c.rules.time_stop is not None and c.rules.idle_symbol is None, c.id
        if any(c.rules is r for r in SWING_PRESETS):
            assert "F7" in ids, c.id


def test_family_matches_its_allocators():
    for c in REGISTRY:
        if c.family == "REF":
            continue
        if c.family == "F9":
            assert c.allocator is BLEND and len(c.params.parts) >= 2, c.id
            continue
        leaves = _leaves(c.allocator, c.params)
        assert {a.id for a, _ in leaves} == {FAMILY_LEAF[c.family]}, c.id
        for a, p in leaves:
            held = set(a.holds(p))
            if c.family in FACTOR_RANK:
                assert p.rank == FACTOR_RANK[c.family], c.id
            if c.family == "F1":
                assert not held & LEVERAGED_ETFS, c.id
            if c.family == "F10":
                assert held & LEVERAGED_ETFS, c.id
            if c.family == "F2":
                assert set(p.universe) <= {"EFA", "QQQ", "SPY"}, c.id
            if c.family == "F3":
                assert p.universe == SECTOR_ETFS, c.id


def test_sector_etfs():
    assert SECTOR_ETFS == tuple(sorted(SECTOR_ETFS))
    assert SECTOR_ETFS == ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


# ---- smoke: every candidate runs on a synthetic market --------------------------------------

SMOKE_FIRST = date(2013, 12, 2)  # 473 NYSE sessions through DEV_END: lookbacks up to ~400 fit
FIXED_SYMBOLS: tuple[str, ...] = tuple(sorted(
    {"BIL", "EFA", "IEF", "QLD", "QQQ", "SPY", "SSO", *SECTOR_ETFS}
))
MEMBER_STOCKS: tuple[str, ...] = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH")
SPY_EX_DATE = date(2015, 6, 19)
SMOKE_DIVIDENDS: dict[str, dict[date, Decimal]] = {
    "SPY": {SPY_EX_DATE: Decimal("1.0300")},
    "AAA": {date(2015, 3, 13): Decimal("0.2500")},
}
SMOKE_SPY_DIVIDENDS: tuple[Dividend, ...] = (Dividend(SPY_EX_DATE, Decimal("1.0300")),)


def _smoke_history(symbol: str, k: int, days: list[date]) -> History:
    """A deterministic, positive, 2-dp price path: drift + a slow wave + a down day in three
    (RSI(2) dips) + a market-wide ~25% dip around session 380 (trend filters switch off)."""
    n = len(days)
    t = np.arange(n, dtype=np.float64)
    base = 40.0 + 7.0 * k
    drift = 0.0009 - 0.0004 * (k % 4)
    wave = 1.0 + 0.07 * np.sin(2.0 * np.pi * t / (60.0 + 11.0 * k) + k)
    zig = np.where(t % 3 == 0, 0.985, 1.006)
    shock = 1.0 - 0.25 * np.exp(-(((t - 380.0) / 25.0) ** 2))
    close = np.round(base * (1.0 + drift * t) * wave * zig * shock, 2)
    open_ = np.round(np.concatenate((close[:1], close[:-1])), 2)
    high = np.round(np.maximum(open_, close) * 1.01, 2)
    low = np.round(np.minimum(open_, close) * 0.99, 2)
    volume = np.full(n, 2_000_000.0, dtype=np.float64)
    return History(symbol, np.array(days, dtype="datetime64[D]"), open_, high, low, close, volume)


@pytest.fixture(scope="module")
def smoke_market() -> Market:
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    symbols = FIXED_SYMBOLS + MEMBER_STOCKS
    history = {s: _smoke_history(s, k, days) for k, s in enumerate(symbols)}
    membership = Membership(intervals=tuple((s, days[0], None) for s in MEMBER_STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def test_smoke_market_covers_every_fixed_symbol(smoke_market):
    for c in REGISTRY:
        if c.rules is DESIGN_V0:
            continue
        needed = set(c.allocator.symbols(c.params)) | set(c.allocator.holds(c.params))
        if c.rules.idle_symbol is not None:
            needed.add(c.rules.idle_symbol)
        assert needed <= set(FIXED_SYMBOLS), (c.id, sorted(needed - set(FIXED_SYMBOLS)))
        assert needed <= set(smoke_market.history), c.id


@pytest.mark.parametrize("c", REGISTRY, ids=[c.id for c in REGISTRY])
def test_every_candidate_runs_a_smoke_window(smoke_market, c):
    result, row = run_candidate(smoke_market, SMOKE_DIVIDENDS, SMOKE_SPY_DIVIDENDS, c)
    start, end = candidate_window(smoke_market, c)
    window = dates.sessions(start, end)
    assert row.candidate == c
    assert (row.start, row.end) == (start, end)
    assert end == DEV_END
    assert len(window) >= 20, f"{c.id}: smoke window only {len(window)} sessions; lookback too long for the synthetic market"
    assert len(result.snapshots) == len(window) + 1
    assert result.snapshots[-1].date == DEV_END
    if c.rules is DESIGN_V0:
        assert isinstance(result, RunResult)
    else:
        assert isinstance(result, BookResult)
```
**Impact:** 21 test functions; `test_every_candidate_runs_a_smoke_window` expands to 54 cases, so
the module collects **74 tests** (20 + 54).

### Step 3: Pin the digests
**File:** `engine/tests/test_registry.py` — the `PINS = (...)` block (≈ line 165 of the file as
written in Step 2).
**Change:** from the worktree root, generate the literal and replace the whole `PINS` assignment
(every `"UNPINNED"` row) with the output, verbatim:
```bash
cd /home/miftah/.worktrees/seer/trade-rules-dev-search/engine && .venv/bin/python - <<'EOF'
from seer_engine.backtest.registry import REGISTRY, candidate_digest
print("PINS: tuple[tuple[str, str], ...] = (")
for c in REGISTRY:
    print(f"    ({c.id!r}, {candidate_digest(c)!r}),")
print(")")
EOF
```
Check the output has 54 lines between the parentheses, in the same id order as the `"UNPINNED"`
block (`test_first_54_are_the_plan_index_table_in_order` and the pin tests enforce both). Paste
it, then run the module's tests. Do **not** re-run this generator later to "fix" a failing pin:
a failing pin means a registered candidate (or a preset/param value under it) changed, which
D6 forbids — revert that change instead.
**Code:** (the generator above is the code; its output is the pasted `PINS` literal)
**Impact:** the three pin tests pass. From now on, any change in phases 1, 2, 5–9's preset or
params dataclass **fields** (names, order, defaults that registered candidates use) fails these
pins — intended.

### Step 4: Run the suite, then commit the registry
**Change:** run Verification. Then commit exactly these two files (and the phase log, if the
workflow keeps one) in one commit, message e.g.
`feat(engine): P7a candidate registry, 54 entries, pinned (phase 11)`.
If `FIRST_APPEND` is not the commit's date, fix the literal, re-run Step 3 (the digest does not
include `added`, so the pins do not change; re-run only to confirm) and the suite before
committing. The registry commit must exist before phase 12's real `--only` smoke run and phase
13's dev run.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search/engine && .venv/bin/python -c "import seer_engine.backtest.registry as r; print(len(r.REGISTRY))"` prints `54`.
**Tests:**
- `docker start seer-pg`
- `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/pytest engine/tests/test_registry.py -q` → **74 passed**
- `engine/.venv/bin/pytest engine/tests/test_strategy_purity.py -q` (covers `backtest/registry.py` via the glob)
- full suite: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` → previous phase's count + 74, **0 skipped**
- frozen set: `git diff --stat 2546a92 -- <frozen paths from the index>` prints nothing.
**Manual check:** `grep -c UNPINNED engine/tests/test_registry.py` prints `0`. Read the 11 flagged
entries in the `FLAGGED` dict against the handover "Owner inputs" table. Log the smoke test's
wall time (expected a few seconds; if > 60 s note it for phase 12's D13 estimate).
**Exit criteria:** `REGISTRY` has 54 pinned entries matching the index table exactly (row 54
under `SWING_T20`), every one runs on the synthetic market, the suite is green with 0 skipped, and the
commit containing `registry.py` + `test_registry.py` is on the branch before any real dev run.

## Handoffs

- **Phase 12 (R6, plan index D-I):** phase 12's test asserts `registry.SECTOR_ETFS ==
  research.SECTOR_ETFS` and that every fixed symbol the registry reads or holds (the union of
  `allocator.symbols/holds(params)` and `rules.idle_symbol`) is in `research.RESEARCH_ETFS`. Phase 11
  cannot import `seer_engine.research` (impure, and phase 4 is not in its `depends_on`).
- **Phase 9 / 12 (R5/R6), prepare cache key — settled, plan index D-D:** the two `BLEND` rows (53,
  54) and three `VOLTARGET` rows (15, 16, 45) share the singletons `BLEND` and `VOLTARGET`, whose
  `prepare(history)` is a param-independent `LazyPrepared` (inner prepares keyed by object
  identity, computed on first use). One prepared value per `allocator.id` is therefore correct, and
  phase 12 runs the registry through `dev.run_registry`.
- **Phase 13 (R6):** the readme/ROADMAP should note that every swing preset applies the
  `time_stop` to **every** position, including row 54's SPY core: it is sold every 20 sessions
  and re-bought on the next decision (through the D-B open_limit fallback), which adds closed
  trades (and costs) to F9-…-SWING50. That is the registered behaviour; it must be reported, not
  tuned.
- **Phase 10 (R7):** `candidate_text` is a ready, deterministic "exact specification" of a
  finalist for the pre-registration file if phase 10 wants it (optional; `params.as_dict()` remains
  the contracted rendering).

## Rollback

`git revert` the phase-11 commit: it adds only `backtest/registry.py` and `tests/test_registry.py`,
and nothing else imports `registry` until phase 12. If phase 12 has landed, revert it first. Never
"roll back" by editing a registered entry in place (D6).
