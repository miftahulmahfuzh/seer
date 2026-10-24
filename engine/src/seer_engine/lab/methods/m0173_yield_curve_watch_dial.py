"""M0173 — The yield-curve warning as a dial, not a switch: hold part of the book while the watch is open.

Source: general knowledge, a variation on M0167 and M0038 (Estrella & Mishkin 1996, NY Fed Current
Issues 2(7); published in 1991 and on the NY Fed's site since the late 1990s, so a public signal
through the whole dev window). Reserved as an idea row by Sera 20261024-1522.

M0038's watch opens on the first day the 10-year yield sits under the 13-week bill and stays open
730 calendar days after the last such day. It was all or nothing: cash while open. That makes the
result hang on two events (2000 and 2006-07) and on being fully out for the 2009 rebound. Here the
same watch, the same big-dividend-raise book (M0076-X-M with its own SPY-200 switch removed, as in
M0038's DIV hosts), but while the watch is open the book is held at ``exposure`` of its normal
size and the rest sits in cash. Same picks, same resize rhythm, same fractional Gotrade fees;
only the size changes, so the exposure is the one thing that differs between the arms.

Variants, four rungs of one dial:

    * ``EXP100``: exposure 1, never steps aside. The control with no opinion in it: it prices what
      acting on the warning costs, which the two reversed-pair arms alone cannot (see ``lab dressing``).
    * ``EXP50``, ``EXP33``: the dial.
    * ``EXP00``: exposure 0, the full switch (M0038-DIV-WATCH's rule on this allocator).

The watch is read exactly as M0038 reads it (``inverted_dates``, ``watch_open``): a reading needs
both yields dated the same day, and before the 10-year series starts the watch is closed. Cash
earns nothing, as in M0038.
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
from seer_engine.lab.methods.m0038_yield_curve_watch_gate import (
    DIV_CURVE,
    DIV_OPEN,
    CurvePrepared,
    watch_open,
)
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import ANNOUNCED, AnnParams
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 24)


@dataclass(frozen=True, slots=True)
class DialParams:
    """The dividend book at ``exposure`` of its size while the ``T10Y - T13W`` watch is open."""

    exposure: Decimal
    watch_days: int = 730  # M0038's two years, kept so the watch is the same one
    div: AnnParams = DIV_OPEN

    def __post_init__(self) -> None:
        if not isinstance(self.exposure, Decimal) or not (0 <= self.exposure <= 1):
            raise ValueError(f"exposure must be a Decimal in [0, 1], got {self.exposure!r}")
        if isinstance(self.watch_days, bool) or not isinstance(self.watch_days, int) or self.watch_days < 1:
            raise ValueError(f"watch_days must be an int >= 1, got {self.watch_days!r}")
        if not isinstance(self.div, AnnParams):
            raise TypeError(f"div must be AnnParams, got {type(self.div).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"exposure": str(self.exposure), "watch_days": str(self.watch_days)}
        for k, v in self.div.as_dict().items():
            out[f"div.{k}"] = v
        return out


def _check(params: object) -> DialParams:
    if not isinstance(params, DialParams):
        raise TypeError(f"params must be DialParams, got {type(params).__name__}")
    return params


def scaled(targets: tuple[Target, ...], exposure: Decimal) -> tuple[Target, ...]:
    """Every target at ``exposure`` of its weight, the rest left in cash."""
    if exposure == 1:
        return targets
    out = []
    for t in targets:
        w = (t.weight * exposure).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        if w > 0:
            out.append(replace(t, weight=w))
    return tuple(out)


class DialAllocator:
    """M0038's dividend host with the watch resizing the book instead of emptying it."""

    id = "M0173"
    market_fields = ("dividends", "series")

    def lookback(self, params: Any) -> int:
        return ANNOUNCED.lookback(_check(params).div)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({"SPY", *ANNOUNCED.symbols(_check(params).div)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return ANNOUNCED.holds(_check(params).div)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CurvePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: DialParams) -> tuple[Target, ...]:
        if not prepared.inverted:  # no series: target nothing (market-aware contract)
            return ()
        open_ = watch_open(prepared.inverted.get("T13W", ()), data_date, p.watch_days)
        if open_ and p.exposure == 0:
            return ()
        book = ANNOUNCED.targets_prepared(prepared.host, members, data_date, held, p.div)
        return scaled(book, p.exposure) if open_ else book

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        return self._run(CurvePrepared(history, {}, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CurvePrepared:
        return DIV_CURVE.prepare(history)

    def prepare_market(self, market: Any) -> CurvePrepared:
        return DIV_CURVE.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CurvePrepared):
            raise TypeError(f"prepared must be CurvePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


DIAL = DialAllocator()


def _v(suffix: str, exposure: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0173-{suffix}", family="M0173",
                     rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE, allocator=DIAL,
                     params=DialParams(Decimal(exposure)), rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0173",
    name="The yield-curve warning as a dial, not a switch: hold half the book in cash while the watch is open",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="M0167",
    parent_id="M0167",
    hypothesis=(
        "M0038 and M0167 showed the curve watch is all or nothing: two right calls in 1996-2015, "
        "but every timing variant re-sorts the same two events and the walk-forward folds split 2 "
        "to 2, because 2009-2011 always punishes a gate that was fully in cash for the 2009 "
        "rebound. The inverted-curve signal was published in 1991 and 1996 and public through the "
        "whole dev window, so any edge is not from being early to it. Hold the big-dividend-raise "
        "book (M0076-X-M's picks, its own SPY-200 switch removed, re-picked monthly and re-scaled "
        "weekly) at 50% (and a 33% rung) of its size while the 10-year/13-week watch (M0038's: open "
        "from the first inverted day to 730 days after the last) is open, instead of 0%. It gives "
        "up part of the bear-market save in exchange for part of the rebound, so the fold record "
        "should depend less on getting a handful of dates exactly right. Variants: EXP100 (never "
        "steps aside: the control with no opinion in it, which prices what acting on the warning "
        "costs), EXP50, EXP33, EXP00 (the full switch, M0038-DIV-WATCH's rule on this allocator). "
        "All fractional at Gotrade's real fees on the owner's monthly deposits. Assumed: cash earns "
        "nothing; a reading needs both yields dated the same day; before 1993-11-02 the watch is "
        "closed; 730 days kept from M0038, not fitted. Success: a majority of folds won by the "
        "variant picked, a positive 2009-2015 lead on the money-weighted measure, a worst fall "
        "within the limit."
    ),
    expected_failure=(
        "Half exposure through 2000-2002 and 2008 lets the dividend book's 50% falls through at "
        "half size, about 25%, while the 2009 gain is only half recovered, so the dial trails both "
        "ends: it does not beat EXP00 where the save was real and does not beat EXP100 where the "
        "rebound was. With only two warnings in twenty years the dial interpolates between two "
        "curves that already split the folds, so a 2 of 4 fold record is the likely outcome and "
        "no rung is likely to clear the 0.90 luck bar at this N."
    ),
    candidates=(
        _v("EXP100", "1", "Control: the dividend book never stepping aside for the curve watch"),
        _v("EXP50", "0.5", "The dividend book at half size while the curve watch is open"),
        _v("EXP33", "0.333333", "The dividend book at a third of its size while the curve watch is open"),
        _v("EXP00", "0", "The full switch: the dividend book in cash while the curve watch is open"),
    ),
    seen_keys=(
        "concept:yield-curve-half-exposure-dial",
        "concept:yield-curve-gate",
        "concept:macro-regime-gate",
    ),
)
