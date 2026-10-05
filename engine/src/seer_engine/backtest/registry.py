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
    is_pinned_default,
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
FIRST_APPEND = date(2026, 10, 4)

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
    # ---- 2026-10-04: the first registry (plan index "Registry", rows 1-54) ----------------
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
        # A TradeRules lever added after this registry was pinned drops out while it is at its
        # no-op value (sim.rules.LEVERS_SINCE_PINS), so every pinned digest below, and every
        # closed lab trial's config_digest, stays exactly what it was.
        pinned = isinstance(value, TradeRules)
        inner = ",".join(
            f"{f.name}={_canon(getattr(value, f.name))}"
            for f in fields(value)
            if f.compare and not (pinned and is_pinned_default(f.name, getattr(value, f.name)))
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
