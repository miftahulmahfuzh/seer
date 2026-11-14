"""M0579 — A softer market brake on the most-turned-over book: trim under the 200-day, never all cash.

Source: variation of M0497 (family stock-share-turnover); reserved by Sera batch 20261114-0909.

Why it exists. M0497 recorded the same twenty picks twice: behind the SPY 200-day switch
(``M0497-HIGH-SW``, trial 2058) and never stepping aside (``M0497-HIGH-ALWAYS``, trial 2067). The
switch is all or nothing, and the two ends bracket a question the lab has not asked of this book:
the always-invested end earned slightly more and fell 67% from a peak, the switched end fell 26%.
Is there a setting in between that keeps the always-invested return and still takes most of the
fall away, or is the trade a straight line between the two ends (or worse than the line)?

The wrapper changes nothing about which stocks are held. Every arm asks M0497's allocator for
``TurnoverParams("high", trend=None)`` -- F4's screen, the twenty most turned-over members, equal
slots -- and only scales the weights:

* ``KEEP25``, ``KEEP50``, ``KEEP75``: full size while SPY closes above its 200-day average;
  otherwise every slot at 25% / 50% / 75% of its weight, the rest in cash. The picks are kept and
  re-ranked as usual in a trimmed month, so the brake costs a trim and a top-up instead of twenty
  round trips. With too few SPY bars to read the average the book is at the trimmed size.
* ``FLAT85``: Control: the same picks at a constant 85% of full weight, every month, reading no
  market at all. It is the no-opinion arm: KEEP50 is expected to sit about 83% invested on
  average (the midpoint of HIGH-SW's recorded 0.695 exposure and HIGH-ALWAYS's 0.971), and 85% of
  HIGH-ALWAYS's 0.971 is 0.825. If KEEP50 does not beat FLAT85 on return for the fall it takes,
  timing the trim is worth nothing beyond simply holding less.

The 0% and 100% rungs are not re-run. They are recorded books on the current dev store with the
same rules, allocator and params -- ``M0497-HIGH-SW`` (trial 2058) and ``M0497-HIGH-ALWAYS``
(trial 2067) -- and are cited as the ladder's two ends.

Assumptions written before any result. The reserved idea also named "a slower or smoothed trend
read"; that is a different dial (when the brake fires, not how hard) and is left out so the ladder
has one dial. M0497 is test-failed, so no arm here can ever be promoted (hardgate K): the result
is knowledge about the brake, not a candidate. Under monthly-hold-frac-gotrade a held slot is
resized once it is off by 1% of the account; the smallest step here (KEEP75: a 5% slot to 3.75%)
is a 1.25% gap, so every rung's trim is expected to trade, and the recorded exposure is the check
that it did (a partial-weight step closes no round trip, so trades and profit factor say little).

Market-aware through M0497's allocator (``market_fields = ("shares",)``). Pure: reads only bars
and share counts dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0497_share_turnover import TURNOVER, TurnoverParams, TurnoverPrepared
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 11, 14)
MODES = ("brake", "flat")
PICKS = TurnoverParams("high", trend=None)  # M0497-HIGH-ALWAYS's book: the host's picks, ungated
SWITCH = TurnoverParams("high")             # M0497-HIGH-SW's params: the same SPY 200-day read


@dataclass(frozen=True, slots=True)
class SoftBrakeParams:
    """``mode`` brake (trim only while SPY is at or under its 200-day) or flat (trim always, the
    no-opinion control); ``keep_pct`` the share of each slot's weight kept when trimmed."""

    mode: str
    keep_pct: int

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.keep_pct, bool) or not isinstance(self.keep_pct, int) or not 1 <= self.keep_pct <= 99:
            raise ValueError(f"keep_pct must be an int in [1, 99], got {self.keep_pct!r}")

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "keep_pct": str(self.keep_pct), "host": "M0497-high",
                "trend": f"{SWITCH.trend[0]}:{SWITCH.trend[1]}" if self.mode == "brake" else "none"}


def _check(params: object) -> SoftBrakeParams:
    if not isinstance(params, SoftBrakeParams):
        raise TypeError(f"params must be SoftBrakeParams, got {type(params).__name__}")
    return params


def _trim(targets: tuple[Target, ...], keep_pct: int) -> tuple[Target, ...]:
    """Every target at ``keep_pct`` percent of its weight, the rest left in cash."""
    scale = Decimal(keep_pct) / Decimal(100)
    out: list[Target] = []
    for t in targets:
        w = (t.weight * scale).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        if w > 0:
            out.append(replace(t, weight=w))
    return tuple(out)


def _soften(history: Mapping[str, History], d: date, targets: tuple[Target, ...],
            p: SoftBrakeParams) -> tuple[Target, ...]:
    if p.mode == "brake" and trend_on(history, d, SWITCH.inner):
        return targets
    return _trim(targets, p.keep_pct)


class SoftBrakeAllocator:
    """M0497's twenty most turned-over members, always held; each slot trimmed to ``keep_pct``
    percent of its weight while SPY closes at or below its 200-day average (brake), or in every
    month (flat). The picks are the host's and are never changed here."""

    id = "M0579"
    market_fields = TURNOVER.market_fields

    def lookback(self, params: Any) -> int:
        _check(params)
        return TURNOVER.lookback(SWITCH)  # the switch's 200 bars on every arm, flat included

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return TURNOVER.symbols(SWITCH)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so the host targets nothing (the contract)."""
        p = _check(params)
        return _soften(history, data_date, TURNOVER.targets(history, members, data_date, held, PICKS), p)

    def prepare(self, history: Mapping[str, History]) -> TurnoverPrepared:
        return TURNOVER.prepare(history)

    def prepare_market(self, market: Any) -> TurnoverPrepared:
        return TURNOVER.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        picks = TURNOVER.targets_prepared(prepared, members, data_date, held, PICKS)
        return _soften(prepared.history, data_date, picks, p)


SOFTBRAKE = SoftBrakeAllocator()


def _v(suffix: str, params: SoftBrakeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0579-{suffix}", family="M0579", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SOFTBRAKE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0579",
    name="A softer brake on the share-turnover winner: partial exposure cut instead of all-cash",
    family="stock-share-turnover",
    source_kind="variation",
    source_ref="M0497 (HIGH-SW trial 2058 and HIGH-ALWAYS trial 2067 are the ladder's two ends)",
    parent_id="M0497",
    hypothesis=(
        "Written before any result. M0497 recorded the twenty most turned-over big index members "
        "twice on the current dev store: behind the all-or-nothing SPY 200-day switch "
        "(M0497-HIGH-SW, trial 2058: 0.695 exposure, worst fall 26.1%, 2008 about flat) and never "
        "stepping aside (M0497-HIGH-ALWAYS, trial 2067: 0.971 exposure, worst fall 67.4%, 2008 "
        "-51%). Those two recorded trials are cited as the 0% and 100% rungs and are not re-run. "
        "This method fills in the ladder between them on the same picks: while SPY closes at or "
        "under its 200-day average every slot is cut to 25%, 50% or 75% of its weight, never to "
        "cash. The hypothesis is that the trade is not a straight line: a partial cut keeps "
        "nearly all of the always-invested return (because it stays in for the rebounds the full "
        "switch misses) while removing more than its proportional share of the fall, so KEEP50 "
        "earns at least the average of the two ends with a worst fall clearly under their "
        "midpoint (about 47%), and beats FLAT85 -- the same picks held at a constant 85% with no "
        "market opinion, matched to KEEP50's expected average exposure of about 0.83 -- on "
        "return and on fall. M0497 is test-failed, so nothing here can be promoted; the result "
        "is knowledge about the brake. Closest recorded neighbours: M0287 (grading a trend gate "
        "cost return and bought no safety) and M0202 (a half-size guard on a bond-like book)."
    ),
    expected_failure=(
        "The ladder is a straight line or bows the wrong way, as M0287's graded gate and M0283's "
        "SPY blend did: each rung's return and fall sit on or behind the line between HIGH-SW and "
        "HIGH-ALWAYS, because a book that is still half invested through 2008 takes about half of "
        "a 67% fall (well past the 25% screen) while the return it keeps is no better than "
        "proportional. Then the all-or-nothing switch is the best brake on this book and every "
        "softer rung fails the fall limit. The trims may also cost more in Gotrade fees than "
        "they save, since each flip trades all twenty slots twice. And KEEP50 may not beat "
        "FLAT85, which would say the timing adds nothing beyond holding less."
    ),
    candidates=(
        _v("KEEP25", SoftBrakeParams("brake", 25),
           "M0497-HIGH-ALWAYS's picks, each slot cut to 25% of its weight while SPY is at or under its 200-day"),
        _v("KEEP50", SoftBrakeParams("brake", 50),
           "M0497-HIGH-ALWAYS's picks, each slot cut to 50% of its weight while SPY is at or under its 200-day"),
        _v("KEEP75", SoftBrakeParams("brake", 75),
           "M0497-HIGH-ALWAYS's picks, each slot cut to 75% of its weight while SPY is at or under its 200-day"),
        _v("FLAT85", SoftBrakeParams("flat", 85),
           "Control: M0497-HIGH-ALWAYS's picks at a constant 85% of full weight, reading no market, "
           "matched to KEEP50's expected average exposure"),
    ),
    panel_exempt="chassis: a softer market brake on M0497-HIGH's picks",
    seen_keys=(
        "concept:partial-exposure-brake-on-share-turnover-book",
        "concept:soft-200-day-brake-dose-ladder",
    ),
)
