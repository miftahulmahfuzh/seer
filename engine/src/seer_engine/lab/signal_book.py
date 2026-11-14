"""The one chassis a panelled signal is booked on (SERA_SIGNAL_PANEL_PLAN.md phase 5, R4).

Stage two of the lab books a stock-picking idea only after its signal has cleared the panel
(``lab panel``; ``panel_verdict.published``), and only on this chassis. One chassis, because the
panel has already measured the idea as a ranking across the whole pool: what the book stage adds
is a reading of that ranking as a portfolio a person could hold at Gotrade's fees. Every degree of
freedom left in the book -- a width, a cadence, a brake, a weighting -- would be a second idea the
panel never screened and another chance to fit the dev window. ``hardgate.panel_refusal`` (D21)
refuses a signal method whose non-control arms are anything but the two built here.

**The book.** On each monthly decision date ``d`` (``MONTHLY_HOLD_FRAC_GOTRADE``: fractional
shares at Gotrade's fees; the book engine asks the allocator on decision sessions only):

1. the pool is the members that pass ``tree_rank.SCREEN`` on ``d`` -- F4's screen with no trend
   switch, the pool the panel ranks (``f_factor.factor_rows`` / ``FactorPrepared.rows_on``);
2. every pool name is scored by the signal on bars cut at ``d`` (``Signal.scores``, the cut
   the panel measured with: ``panel.signal_scorer`` returns this same method); a missing or non-finite score has no opinion and the name is
   skipped;
3. the ``WIDTH`` highest scores are the targets, ties broken by symbol, each at
   ``equal_weight(WIDTH)``. A held name is kept only while it is still among them and is sold at
   the rebalance otherwise, so the book is the signal's top twenty and nothing else;
4. the gated arm (``<method>-N20``) holds nothing on a ``d`` when SPY closes at or below its
   200-day average (``f_factor.trend_on``, the switch every F4 book uses); the other arm
   (``<method>-N20-NOGATE``) never steps aside. Both are recorded because in most of the lab's
   books the switch, not the picking, did the work (the plan's Why), and a signal is worth booking
   only if its book is worth holding without the switch's help as well.

**Why the allocator is built per signal and not looked up.** ``book_allocator(signal)`` returns a
new object whose id is ``"SB-" + signal.id``. A config digest names an allocator by its id
(``method.config_text``), so a standard arm's digest is a function of the signal id, the rule set
and the switch setting alone: two methods that book one signal produce the same digests, and the
second is refused by ``runner.preflight``'s repeat check. One signal, one book. The signal's file
is frozen by its commit, and D21 compares its sha with the one its panel was measured on, so the
id is a sufficient name. ``test_lab_methods`` still holds a method file to one allocator object per
id: ``standard_candidates`` gives both arms the same object.

**A market-aware signal.** A signal that declares ``market_fields`` gets a ``MarketAware`` book
(``prepare_market``), so ``lab run``'s coverage and series checks read it exactly as they read any
other allocator (``runner.market_fields``). Its history-only path targets nothing, the convention
``test_lab_methods`` holds every market-aware allocator to: without the market there is nothing to
rank on. A bar-only signal's history-only path builds a ``Market`` from the bars it was given and
nothing else, so the scorer always receives a ``Market`` and the P4 identity holds on both paths.

Pure: no database, clock, files or randomness.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab.signal import Signal
from seer_engine.lab.tree_rank import SCREEN
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

#: The book's width: the signal's twenty highest-scored pool names.
WIDTH = 20

#: The market switch of the gated arm, F4's: SPY's close above its 200-session average.
SWITCH: tuple[str, int] = ("SPY", 200)

#: A signal book's allocator id is this prefix and the signal id: ``SB-S0001``.
ID_PREFIX = "SB-"

#: The two standard arms' candidate-id suffixes.
GATED_SUFFIX = "N20"
NOGATE_SUFFIX = "N20-NOGATE"

#: The chassis's rule set: monthly hold, fractional shares, Gotrade's real fees.
RULES = MONTHLY_HOLD_FRAC_GOTRADE

_NO_MEMBERS = Membership(intervals=())


@dataclass(frozen=True, slots=True)
class BookParams:
    """The chassis's one setting: the gated arm's switch, or none.

    Not a width, a cadence or a weighting: those are fixed (module docstring), and a field for
    them would be a dial a method could turn without the panel ever seeing it.
    """

    trend: tuple[str, int] | None = SWITCH

    def __post_init__(self) -> None:
        if self.trend is not None and self.trend != SWITCH:
            raise ValueError(
                f"the signal chassis has two settings, the SPY 200-day switch or none; "
                f"got trend={self.trend!r}"
            )

    def as_dict(self) -> dict[str, str]:
        """Every parameter as a plain string, in a fixed key order (report and pre-registration)."""
        trend = "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}"
        return {"width": str(WIDTH), "trend": trend}


def _check(params: object) -> BookParams:
    if not isinstance(params, BookParams):
        raise TypeError(f"params must be BookParams, got {type(params).__name__}")
    return params


def _screen(p: BookParams) -> FactorParams:
    """F4's screen (``tree_rank.SCREEN``) carrying this arm's switch: the pool and the switch."""
    return replace(SCREEN, trend=p.trend)


def _bars_market(history: Mapping[str, History]) -> Market:
    """A ``Market`` holding only ``history``: what a bar-only signal is handed off the full store."""
    return Market(history=history, membership=_NO_MEMBERS, fx=())


@dataclass(frozen=True, eq=False)
class SignalPrepared:
    """F4's prepared columns for the pool, and the market the signal reads.

    ``market`` is None only on a market-aware book's history-only path, where the book targets
    nothing (module docstring).
    """

    factor: FactorPrepared
    market: Market | None


class SignalBook:
    """A panelled signal's standard book behind the ``Allocator`` protocol (module docstring)."""

    def __init__(self, signal: Signal) -> None:
        if not isinstance(signal, Signal):
            raise TypeError(f"signal must be a Signal, got {type(signal).__name__}")
        self.signal = signal
        self.id = ID_PREFIX + signal.id
        self.market_fields: tuple[str, ...] = tuple(signal.market_fields)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(_screen(p)), self.signal.lookback)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.trend is None else (p.trend[0],)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _check(params)
        screen = _screen(p)
        if not trend_on(history, data_date, screen):
            return ()
        rows = factor_rows(history, members, data_date, screen)
        return self._pick(rows, self._market_of(history), data_date)

    def prepare(self, history: Mapping[str, History]) -> SignalPrepared:
        return SignalPrepared(prepare_factor(history), self._market_of(history))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        if not isinstance(prepared, SignalPrepared):
            raise TypeError(f"prepared must be SignalPrepared, got {type(prepared).__name__}")
        p = _check(params)
        screen = _screen(p)
        if not trend_on(prepared.factor.history, data_date, screen):
            return ()
        rows = prepared.factor.rows_on(members, data_date, screen)
        return self._pick(rows, prepared.market, data_date)

    def _market_of(self, history: Mapping[str, History]) -> Market | None:
        """The market a bar-only signal reads on the history-only path: the bars, nothing else."""
        return _bars_market(history)

    def _pick(
        self, rows: Sequence[FactorRow], market: Market | None, data_date: date
    ) -> tuple[Target, ...]:
        """The ``WIDTH`` highest-scored pool rows, ties by symbol, at ``equal_weight(WIDTH)``."""
        if market is None or not rows:
            return ()
        pool = frozenset(r.symbol for r in rows)
        scores = self.signal.scores(market, pool, data_date)  # applies signal.visible's cut
        ranked: list[tuple[float, str, float]] = []
        for r in rows:
            value = scores.get(r.symbol)
            if value is None:
                continue
            x = float(value)
            if math.isfinite(x):
                ranked.append((-x, r.symbol, r.close))
        ranked.sort()
        weight = equal_weight(WIDTH)
        out: list[Target] = []
        for _, symbol, close in ranked[:WIDTH]:
            target = target_from_close(symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)


class MarketSignalBook(SignalBook):
    """The book of a signal that declares ``market_fields``: ``MarketAware``, history path empty."""

    def _market_of(self, history: Mapping[str, History]) -> Market | None:
        return None

    def prepare_market(self, market: Market) -> SignalPrepared:
        return SignalPrepared(prepare_factor(market.history), market)


def book_allocator(signal: Signal) -> SignalBook:
    """``signal``'s standard book, id ``"SB-" + signal.id``; market-aware when the signal is."""
    return MarketSignalBook(signal) if signal.market_fields else SignalBook(signal)


def standard_candidates(signal: Signal, method_id: str, added: date) -> tuple[Candidate, Candidate]:
    """The two arms a signal method books, in order: behind the switch, then never stepping aside.

    Both share one allocator object. Neither rationale names the signal (a signal's name can hold
    a phrase ``control_shape.role_of`` reads as a control, which would make an arm ineligible), and
    neither reads as a control: the gated arm opens ``The idea:`` and the other is a treatment.
    ``added`` reaches ``Candidate.added`` only, which no digest reads.
    """
    book = book_allocator(signal)
    gated = Candidate(
        id=f"{method_id}-{GATED_SUFFIX}",
        family=method_id,
        rules=RULES,
        allocator=book,
        params=BookParams(trend=SWITCH),
        rationale=(
            "The idea: the signal's twenty highest-scored members of F4's pool, equal weight, "
            "rebalanced monthly at Gotrade's fees, holding nothing while SPY is at or below its "
            "200-day average. The lab's one signal chassis."
        ),
        added=added,
        owner_inputs=(),
    )
    never = Candidate(
        id=f"{method_id}-{NOGATE_SUFFIX}",
        family=method_id,
        rules=RULES,
        allocator=book,
        params=BookParams(trend=None),
        rationale=(
            "The same twenty names with the market switch removed, never stepping aside, so the "
            "signal's book is read without the timing that did most of the work in most of the "
            "lab's books."
        ),
        added=added,
        owner_inputs=(),
    )
    return gated, never
