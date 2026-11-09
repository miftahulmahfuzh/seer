"""M0330 — The fallen after the storm, back in sooner: the members furthest below their 200-day
average, bought only while the market's fear gauge (VIX) is calm against its own 3-month level.

Variation of M0285 (a variation of M0282; moving-average distance, Avramov, Kaplanski &
Subrahmanyam, working paper 2018; long-term reversal after De Bondt & Thaler 1985). Reserved by
Sera batch 20261109-0854 as an ``idea`` row; this file refines it and keeps its id.

WHY. M0285 put M0282's fallen-stocks book behind SPY's 200-day switch: the switch cut the worst
fall roughly in half but is slow, so it re-enters after the rebound has begun, and the lab's note on
it named this method as the next thing to try. This asks whether a faster, fear-based switch keeps
the bounce. VIX is a daily series from 1993, so it covers the whole dev window (VIX3M starts only in
2006, so the term-structure version cannot be tested on 1996-2006 and is left out on purpose).

REUSE, NAMED. The picking logic is M0282's, imported unchanged (``MadParams``, ``MadAllocator``):
the same pool, band (hold 20, keep while inside 40), equal slots, monthly, fractional shares at
Gotrade's real fees. The fear test is M0039's ``gate_on(..., gate="spike")``, imported unchanged:
invested while VIX divided by its mean over the last 63 sessions is below the threshold, cash
otherwise, and invested (fails open) when VIX is stale or short of history.

ARMS (threshold 1.00 is the literal "VIX above its own 3-month level"; 1.15 is a real spike, added
because 1.00 flips often and whipsaw is the stated expected failure, so the arm that avoids it must
exist before the result).
    BOT20-VIX100       the 20 lowest MAD behind the 1.00 fear switch: the treatment
    BOT20-VIX100-PLC   placebo: a blind hash-order draw with TOP20's book size and entry count,
                       behind the same switch -- the no-opinion arm
    BOT20-VIX115       the same book behind the 1.15 switch
    BOT20-VIX115-PLC   its placebo
    BOT20              no switch: the habit-off twin. It repeats M0285-BOT20's book under a new
                       allocator id, so ``lab twins`` will record it as a twin of that trial; it is
                       not a new book and costs no look.
The 200-day-switched book is M0285-BOT20-SW and its blind draw M0285-BOT20-SW-PLC; compare against
them, they are not re-run here.

Pure: no clock, randomness, files or network; reads only bars and VIX rows dated on or before
``data_date`` and share counts filed by it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import AbstractSet, Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0039_vix_term_structure_gate import GateParams, gate_on
from seer_engine.lab.methods.m0282_moving_average_distance import (
    MadAllocator,
    MadParams,
    MadPrepared,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 9)


@dataclass(frozen=True, slots=True)
class FearParams:
    """``book`` is M0282's pick (never with its own 200-day switch); ``threshold`` the VIX ratio at
    or above which the book goes to cash, ``None`` for no switch."""

    book: MadParams
    threshold: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.book, MadParams) or self.book.switch:
            raise ValueError("book must be MadParams without the 200-day switch")
        t = self.threshold
        if t is not None and (isinstance(t, bool) or not isinstance(t, float) or not t > 0):
            raise ValueError(f"threshold must be a positive float or None, got {t!r}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.book.as_dict())
        out["fear_switch"] = "none" if self.threshold is None else f"vix-spike:63:{self.threshold!r}"
        return out


def _fear(params: object) -> FearParams:
    if not isinstance(params, FearParams):
        raise TypeError(f"params must be FearParams, got {type(params).__name__}")
    return params


class FearFallenAllocator(MadAllocator):
    """M0282's picks, gated by the VIX spike test instead of SPY's 200-day average."""

    id = "M0330"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        return super().lookback(_fear(params).book)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_fear(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_fear(params).book)

    def uses_members(self, params: Any) -> bool:
        return super().uses_members(_fear(params).book)

    def targets(self, history: Any, members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Any, ...]:
        """The history-only path has neither share counts nor VIX: no target."""
        _fear(params)
        return ()

    def _gated(self, prepared: MadPrepared, members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: FearParams) -> tuple[Any, ...]:
        market = prepared.market
        if market is None:
            return ()
        if p.threshold is not None and not gate_on(
                market.series, data_date, GateParams("spy", "spike", p.threshold)):
            return ()
        return self._run(prepared, members, data_date, held, p.book)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Any, ...]:
        if not isinstance(prepared, MadPrepared):
            raise TypeError(f"prepared must be MadPrepared, got {type(prepared).__name__}")
        return self._gated(prepared, members, data_date, held, _fear(params))

    def prepare_market(self, market: Any) -> MadPrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return MadPrepared(market.history, market)


FEAR = FearFallenAllocator()


def _v(suffix: str, params: FearParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0330-{suffix}", family="M0330", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FEAR, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


_BOT = MadParams(signal="bottom")
_PLC = MadParams(signal="control", seed=1)

METHOD = Method(
    id="M0330",
    name=("The fallen after the storm, back in sooner: beaten-down members bought behind a "
          "market-fear switch"),
    family="stock-moving-average-distance",
    source_kind="variation",
    source_ref="Variation of M0285; long-term reversal after De Bondt & Thaler (1985).",
    parent_id="M0285",
    hypothesis=(
        "M0285 put the 20 sized members furthest below their 200-day average behind SPY's "
        "200-day switch. The switch cut the worst fall a great deal but re-entered after the "
        "rebound began, and its picks beat a switched blind draw by only a little overall, though "
        "by more in 2009-2015 (figures to be read from the lab record, not from this text). Test "
        "the same pool, band (top 40), equal slots, fractional shares at Gotrade's real fees on "
        "the owner's monthly top-up behind a faster fear switch: cash while VIX is at or above "
        "1.00x (literal) or 1.15x (a real spike) its own 63-session mean. Arms: BOT20-VIX100 and "
        "BOT20-VIX115; each with a matched blind draw behind the same switch as its no-opinion "
        "arm (BOT20-VIX100-PLC, BOT20-VIX115-PLC); and BOT20 with no switch, the habit-off twin "
        "(a book twin of M0285-BOT20 by construction). Prediction written before any result: "
        "the VIX switch beats the 200-day switch's worst fall or its return, not neither, and "
        "the picks beat their switched draw by 2+ points a year in 2009-2015. Published "
        "anomaly (reversal 1985): a dev lead is likely an old edge."
    ),
    expected_failure=(
        "In order of likelihood. (1) A faster switch whipsaws: at 1.00x VIX is above its own "
        "3-month mean often, so the book spends long stretches in cash and pays fees on each "
        "flip; M0422, M0430 and M0519 found fear-index timing on a stock book matched or lost to "
        "the plain rule. (2) The 2000-2002 and 2008 falls arrive before fear signals fire: VIX "
        "drifts up slowly in a grinding bear market so it never clears its own mean by much, and "
        "the book keeps holding the fallen. (3) The picks tie their switched draw, so the "
        "whatever edge exists is the switch's. (4) 1.15x fixes the whipsaw but misses the fall. "
        "Any of these is a rejection, not a reason to tune the threshold afterwards. Read the "
        "survivorship-check store before believing any lead."
    ),
    candidates=(
        _v("BOT20-VIX100", FearParams(_BOT, 1.0),
           "The 20 fallen members, all cash while VIX is at or above its 63-session mean"),
        _v("BOT20-VIX100-PLC", FearParams(_PLC, 1.0),
           "Placebo behind the same switch: top-book size and entries drawn blind from the pool"),
        _v("BOT20-VIX115", FearParams(_BOT, 1.15),
           "The same book, all cash only while VIX is at least 15% above its 63-session mean"),
        _v("BOT20-VIX115-PLC", FearParams(_PLC, 1.15),
           "Placebo behind the 1.15x switch"),
        _v("BOT20", FearParams(_BOT, None),
           "No switch: the habit-off twin (M0285-BOT20's book under this id)"),
    ),
    seen_keys=(
        "concept:fallen-behind-vix-spike-switch",
        "concept:long-term-reversal-vix-switch",
    ),
)
