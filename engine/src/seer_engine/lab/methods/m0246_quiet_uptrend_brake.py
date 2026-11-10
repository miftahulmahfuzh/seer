"""M0246 — A brake that fires in the uptrend: hold SPY, and step down when a rising market goes
quiet and scattered (the busiest index members moving loosely together).

Parent: M0182, which read average correlation only to *leave* a falling market and found the
spike arrives after the crash, not before. Its table of SPY's next-month return, split by trend
and by correlation band, showed the clean ordering somewhere else: inside an uptrend (SPY above
its 200-day average) the bottom fifth of correlation was followed by +0.33% a month and the top
fifth by +2.44%; below the average the reading sorted almost nothing. Every brake this lab has
built fires in a falling market. This one fires in a rising one.

**This is a selected hypothesis, a paired measurement and not a roster candidate.** It was found
by reading a table built from data already run, so the mirror and the placebo are not optional.
The book holds SPY alone, monthly, so it trades far under design §1's 100-trade floor and no
variant can be eligible; the fold record and the 2009-2015 number decide it.

The reading is M0182's, reused unchanged (``band_state`` over the same 100 busiest members, the
same 31-reading trailing band): the trailing-band state is "low" at or below the ``band``
quantile and "high" at or above it. What is new is only where the brake sits, and the plain
200-day switch stays underneath it:

    * SPY under its 200-day average: cash, as in the control. The correlation reading is not
      consulted.
    * SPY above it and the trigger firing: ``weight_off`` of SPY.
    * SPY above it and the trigger quiet, or no reading: all in SPY (a data gap never steps down).

The variants, every threshold fixed here before any result:

    * ``LO20-UP-HALF``: trigger = bottom fifth (band 0.2), half weight.
    * ``LO20-UP-OFF``: the same to cash.
    * ``LO33-UP-HALF``: bottom third (band 0.33), half weight. The dose-response rung: more
      months, a weaker signal.
    * ``HI80-UP-HALF``: **the mirror**, step down on the *tight* uptrend months (top fifth). It
      must lose or the frame, not the signal, did the work.
    * ``PLACEBO-UP-HALF``: step down to half in a pseudo-random 20% of uptrend decision days,
      drawn from a hash of the date (no clock, no randomness). It separates "be out of a rising
      market sometimes" from "be out of the quiet ones". One draw is one draw: the lab's own error
      bar for a single blind draw is wide, so a result inside it reads as unresolved, not as a win.
    * ``SPY200``: the control, the plain 200-day switch on this window.

Known risk, written before the run: the loose-and-rising months cluster in the late 1990s and
mid-2000s, so this may be a rule about two stretches of history rather than about markets.
Pollet and Wilson (2010) is old enough that any edge has had time to be traded away.

Pure: no clock, randomness, files or network; reads only columns at or before d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0182_average_correlation_clock import (
    BENCH,
    LOOKBACK,
    MAX_WINDOW,
    SMA_GATE,
    Panel,
    band_state,
    build_panel,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 11, 10)
Rule = Literal["lo", "hi", "placebo", "spy"]
_RULES: tuple[str, ...] = ("lo", "hi", "placebo", "spy")


@dataclass(frozen=True, slots=True)
class UpBrakeParams:
    """``band`` is the quantile of the trailing readings that marks the trigger (a ``lo`` rule
    fires at or below it, a ``hi`` rule at or above it, a ``placebo`` fires on that share of
    uptrend days at random). ``weight_off`` is SPY's weight while the brake is on."""

    rule: Rule = "lo"
    window: int = 63
    band: Decimal = Decimal("0.2")
    weight_off: Decimal = Decimal("0.5")

    def __post_init__(self) -> None:
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"rule must be one of {_RULES}, got {self.rule!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int):
            raise TypeError(f"window must be an int, got {type(self.window).__name__}")
        if not 20 <= self.window <= MAX_WINDOW:
            raise ValueError(f"window must be in [20, {MAX_WINDOW}], got {self.window}")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise TypeError(f"band must be a finite Decimal, got {self.band!r}")
        if not Decimal("0.01") <= self.band <= Decimal("0.99"):
            raise ValueError(f"band must be in [0.01, 0.99], got {self.band}")
        if not isinstance(self.weight_off, Decimal) or not self.weight_off.is_finite():
            raise TypeError(f"weight_off must be a finite Decimal, got {self.weight_off!r}")
        if not Decimal(0) <= self.weight_off < Decimal(1):
            raise ValueError(f"weight_off must be in [0, 1), got {self.weight_off}")

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "window": str(self.window),
            "band": format(self.band.normalize(), "f"),
            "weight_off": format(self.weight_off.normalize(), "f"),
        }


def _check(params: object) -> UpBrakeParams:
    if not isinstance(params, UpBrakeParams):
        raise TypeError(f"params must be UpBrakeParams, got {type(params).__name__}")
    return params


def coin(data_date: date, share: Decimal) -> bool:
    """True on a deterministic ``share`` of dates: a hash of the date, not a random draw."""
    h = hashlib.sha256(f"M0246:{data_date.isoformat()}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64 < float(share)


@dataclass(frozen=True, slots=True, eq=False)
class UpBrakePrepared:
    history: Mapping[str, History] = field(repr=False)
    panel: Panel | None = field(repr=False)


class QuietUptrendBrake:
    """100% SPY unless SPY is under its 200-day (cash), or it is over it and the brake is on."""

    id = "M0246"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True  # the correlation is read over point-in-time index members

    def _weight(self, history: Mapping[str, History], panel: Panel | None,
                members: AbstractSet[str], data_date: date, p: UpBrakeParams) -> Decimal:
        if not trend_on(history, data_date, SMA_GATE):
            return Decimal(0)  # the plain 200-day switch underneath, in every variant
        if p.rule == "spy":
            return Decimal(1)
        if p.rule == "placebo":
            return p.weight_off if coin(data_date, p.band) else Decimal(1)
        state = None if panel is None else band_state(panel, members, data_date, p.window, p.band)
        if state is None:
            return Decimal(1)  # no reading: a data gap never steps the book down
        fired = state[1] if p.rule == "lo" else state[0]
        return p.weight_off if fired else Decimal(1)

    def _run(self, history: Mapping[str, History], panel: Panel | None, members: AbstractSet[str],
             data_date: date, p: UpBrakeParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
            return ()
        w = self._weight(history, panel, members, data_date, p)
        if w <= 0:
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), w)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not isinstance(held, frozenset):
            raise TypeError(f"held must be a frozenset, got {type(held).__name__}")
        panel = build_panel(history, BENCH) if p.rule in ("lo", "hi") else None
        return self._run(history, panel, members, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> UpBrakePrepared:
        return UpBrakePrepared(history, build_panel(history, BENCH))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, UpBrakePrepared):
            raise TypeError(f"prepared must be UpBrakePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not isinstance(held, frozenset):
            raise TypeError(f"held must be a frozenset, got {type(held).__name__}")
        panel = prepared.panel if p.rule in ("lo", "hi") else None
        return self._run(prepared.history, panel, members, data_date, p)


BRAKE = QuietUptrendBrake()


def _v(suffix: str, params: UpBrakeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0246-{suffix}", family="M0246",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BRAKE, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0246",
    name=(
        "Step down when a rising market goes quiet and scattered: the brake that fires in the "
        "uptrend, not the downtrend"
    ),
    family="market-average-correlation",
    source_kind="variation",
    source_ref=(
        "M0182's own table of SPY's next-month return by trend and correlation band; "
        "Pollet & Wilson (2010), Average correlation and stock market returns, JFE 96(3)"
    ),
    parent_id="M0182",
    hypothesis=(
        "M0182 measured SPY's next-month return across 237 months split by trend and by how "
        "closely the 100 busiest index members moved together. Inside an uptrend (SPY above its "
        "200-day average, 170 months) the ordering was clean and large: bottom-fifth correlation "
        "+0.33% a month (61 months, about +4% a year), middle +1.10% (80), top fifth +2.44% "
        "(29, about +34% a year). Below the 200-day average the same reading barely sorted "
        "anything (-0.54% high vs -0.19% middle; the -2.83% low cell is 6 months, two of which "
        "set its average). Every brake this lab has built fires in a falling market; this one "
        "would fire in a rising one. Hold SPY at full weight while the market is rising AND "
        "correlation is not in its bottom band, step down to part SPY while the market is rising "
        "and correlation is loose, and keep the plain 200-day switch underneath (cash below the "
        "average, in every variant). Variants, fixed before the run: LO20-UP-HALF (bottom-fifth "
        "trigger to half weight); LO20-UP-OFF (the same to cash); LO33-UP-HALF (bottom third, "
        "more months and a weaker signal, the dose-response rung); HI80-UP-HALF (the MIRROR: "
        "step down on TIGHT uptrend months, which must lose or the frame did the work); "
        "PLACEBO-UP-HALF (steps down to half on a hash-chosen 20% of uptrend decision days, "
        "which separates 'be out of a rising market sometimes' from 'be out of the quiet ones'; "
        "this is ONE draw and is read as unresolved if it lands inside the lab's single-draw "
        "error bar); SPY200 (control: the plain 200-day switch, same window). THIS IS A "
        "SELECTED HYPOTHESIS: it was found by reading a table built from data already run, so "
        "the mirror and the placebo are not optional, and the fold record and the 2009-2015 "
        "number decide it. Known risk: the loose-and-rising months cluster in the late 1990s "
        "and mid-2000s, so this may be a rule about two stretches of history rather than about "
        "markets. Assumed here: the placebo rate 0.2 is the band's nominal share, not the "
        "measured firing rate of LO20, so exposure is compared after the run. Trade count will "
        "again be far under 100, so this is a paired measurement, not a roster candidate: no "
        "variant can be eligible and none is meant to be."
    ),
    expected_failure=(
        "The most likely result is that the table was a selected look. A 61/80/29-month split "
        "of one rising stretch carries little weight: the bottom-fifth cell's gap to the "
        "middle is about 0.8 points a month with a wide error bar, and the loose months sit in "
        "1996-2000 and 2004-2007, so the brake probably steps down for two bull runs and earns "
        "back less than it gives up. Half weight in a market that returns about 1% a month "
        "costs about 0.5% for every month it fires, and the whole prize is the 0.77-point gap "
        "between bottom-fifth and middle months. After 2009 SPY has had no bear market, so "
        "the 2009-2015 number will likely show the brake as a pure drag against SPY200. "
        "The mirror may beat the signal arm, which would say the frame, not correlation, "
        "mattered, and the placebo may land within a point of the signal arm, which would make "
        "it unresolved. Profit factor and DSR are meaningless on a few dozen trades and no "
        "variant should clear the luck bar. Cash earns nothing in the simulator, so every "
        "switched variant's cost is an upper bound."
    ),
    candidates=(
        _v("LO20-UP-HALF", UpBrakeParams("lo", 63, Decimal("0.2"), Decimal("0.5")),
           "Half in SPY when a rising market's correlation is in its bottom fifth"),
        _v("LO20-UP-OFF", UpBrakeParams("lo", 63, Decimal("0.2"), Decimal(0)),
           "All cash when a rising market's correlation is in its bottom fifth"),
        _v("LO33-UP-HALF", UpBrakeParams("lo", 63, Decimal("0.33"), Decimal("0.5")),
           "Half in SPY on a bottom-third trigger: more months, weaker signal"),
        _v("HI80-UP-HALF", UpBrakeParams("hi", 63, Decimal("0.8"), Decimal("0.5")),
           "Mirror: half in SPY when a rising market's correlation is in its top fifth"),
        _v("PLACEBO-UP-HALF", UpBrakeParams("placebo", 63, Decimal("0.2"), Decimal("0.5")),
           "Placebo: half in SPY on a hash-chosen fifth of rising-market decision days"),
        _v("SPY200", UpBrakeParams("spy", 63, Decimal("0.2"), Decimal(0)),
           "Control: the plain SPY 200-day switch on this window"),
    ),
    seen_keys=(
        "concept:correlation-uptrend-brake",
        "concept:loose-correlation-in-a-rising-market",
        "concept:pollet-wilson-average-correlation",
    ),
)
