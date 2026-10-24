"""M0291 -- Stop tuning the gate and change what the book holds while it is out.

Source: variation of M0287 (and M0271, M0270, M0266 beneath it); general knowledge for the
flight-to-quality premise (Treasuries and gold as the usual crash parking places).
Idea: every gated book in this lab holds cash while the SPY 200-day gate is out. Seven methods
moved WHEN the gate is read and none moved WHAT is held. This runs the one gate, unchanged,
over the same opinion-free 50-name chassis and swaps only the parking place.

EVIDENCE ONLY. TLT, IEF, GLD and XLP are not in ``DEFAULT_ETFS``, so every arm that parks in
one carries an ``etf:<symbol>`` owner input and can never be eligible. The result is a number
to put in front of the owner, not a lab candidate.

Pure: reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate, candidate_owner_inputs
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0266_exposure_matched_rebalance import ScaledBandParams
from seer_engine.lab.methods.m0287_graded_trend_vote import BAND, GradedVoteBook, vote_share
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorPrepared

ADDED = date(2026, 10, 24)

#: Every parking place any arm may use. All arms DECLARE all of them (``symbols``), so every arm
#: loads the same instruments and starts scoring on the same session: the window is set by the
#: youngest fund (GLD), and an arm may not buy a longer window by leaving a fund out. ``holds``
#: is what differs per arm.
PARKING_SYMBOLS: tuple[str, ...] = ("GLD", "IEF", "TLT", "XLP")

#: The single gate every arm reads: the lab's shared SPY 200-day line, exactly M0287's K1 rung.
GATE: tuple[int, ...] = (200,)


@dataclass(frozen=True, slots=True)
class ParkParams:
    """M0287's base book plus the parking place.

    ``gate`` is ``None`` for the no-opinion arm (always invested) and ``(200,)`` otherwise.
    ``park`` is the tuple of funds the book holds, equal-weighted, while the gate is out; empty
    means cash, the incumbent every other gated book in the lab uses.
    """

    book: ScaledBandParams = ScaledBandParams()
    gate: tuple[int, ...] | None = GATE
    park: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.book, ScaledBandParams):
            raise TypeError(f"book must be ScaledBandParams, got {type(self.book).__name__}")
        if self.gate is not None and self.gate != GATE:
            raise ValueError(f"gate must be None or {GATE}, got {self.gate!r}")
        if not isinstance(self.park, tuple) or not set(self.park) <= set(PARKING_SYMBOLS):
            raise ValueError(f"park must be a tuple drawn from {PARKING_SYMBOLS}, got {self.park!r}")
        if len(set(self.park)) != len(self.park):
            raise ValueError(f"park must be distinct, got {self.park!r}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.book.as_dict())
        out["gate"] = "off" if self.gate is None else "SPY:" + "/".join(str(n) for n in self.gate)
        out["park"] = "+".join(self.park) if self.park else "cash"
        return out


def _check(params: object) -> ParkParams:
    if not isinstance(params, ParkParams):
        raise TypeError(f"params must be ParkParams, got {type(params).__name__}")
    return params


class ParkedGateBook(GradedVoteBook):
    """M0287's book, gate and rounding, with the out leg holding ``park`` instead of nothing.

    While the gate is on, this computes exactly what M0287's K1 arm computes (it delegates to the
    parent with the vote's own ``VoteParams``-free path: the base book at scale 1). While it is
    off, each parking fund with a bar on ``data_date`` gets an equal slot; a fund without one is
    skipped, so the rest of the account sits in cash, as the rotation allocator's fallback does.
    """

    id = "M0291"

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY", *PARKING_SYMBOLS)

    def holds(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted(_check(params).park))

    def uses_members(self, params: Any) -> bool:
        return True

    def lookback(self, params: Any) -> int:
        return max(super(GradedVoteBook, self).lookback(_check(params).book), max(GATE))

    def _gate_on(self, history: Mapping[str, History], data_date: date, q: ParkParams) -> bool:
        return vote_share(history, data_date, q.gate) > 0

    def _parked(self, history: Mapping[str, History], data_date: date,
                q: ParkParams) -> tuple[Target, ...]:
        if not q.park:
            return ()
        weight = equal_weight(len(q.park))
        out: list[Target] = []
        for symbol in q.park:
            close = last_close(history.get(symbol), data_date)
            if close is None:
                continue
            target = target_from_close(symbol, close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        if q.gate is None or self._gate_on(history, data_date, q):
            return super(GradedVoteBook, self).targets(history, members, data_date, held, q.book)
        return self._parked(history, data_date, q)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        q = _check(params)
        if q.gate is None or self._gate_on(prepared.history, data_date, q):
            return super(GradedVoteBook, self).targets_prepared(
                prepared, members, data_date, held, q.book)
        return self._parked(prepared.history, data_date, q)


BOOK = ParkedGateBook()


def _v(suffix: str, params: ParkParams, what: str) -> Candidate:
    c = Candidate(
        id=f"M0291-{suffix}",
        family="M0291",
        rules=BAND,
        allocator=BOOK,
        params=params,
        rationale=what,
        added=ADDED,
        owner_inputs=(),
    )
    return replace(c, owner_inputs=candidate_owner_inputs(c))


METHOD = Method(
    id="M0291",
    name="What should the book hold while the safety switch is out? Treasuries, gold, staples or cash",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "M0287, M0271, M0270 and M0266 for the opinion-free 50-name chassis, the shared SPY "
        "200-day gate and the measured price of cash on it; M0245, M0258, M0260, M0261, M0262 "
        "and M0271 for the seven ways the gate's timing has already been moved; insight 523 for "
        "the no-opinion third arm; H-P7A-F2 for the earlier, ungated-stock bond-fallback seed"
    ),
    parent_id="M0287",
    hypothesis=(
        "Seven methods this month moved WHEN the shared SPY 200-day gate is read, and each "
        "answer was a fraction of a point either side of the gate's own value. The one thing "
        "nobody changed is what the book holds while the gate is out: cash, in every gated book "
        "in the lab. M0287 and M0271 priced that cash on this exact chassis and found the "
        "gate's whole-window value positive and its 2009-2015 value strongly negative, with the "
        "cost of cash explaining most but not all of the later shortfall. This method keeps the "
        "gate, the 50-name opinion-free book, the band, the fees and the funding identical and "
        "changes only the out leg, in six arms on one store: always invested (no opinion), gate "
        "with cash (the incumbent), and the gate parking the whole account, equal to one slot, "
        "in intermediate Treasuries (IEF), long Treasuries (TLT), gold (GLD) or consumer staples "
        "(XLP). The always-invested arm is the insight-523 third arm and what makes the cost of "
        "the habit recoverable instead of cancelling. EVIDENCE ONLY, STATED UP FRONT: TLT, IEF, "
        "GLD and XLP are not Gotrade defaults, so every parked arm carries an owner input and "
        "can never be eligible, whatever it earns; the output is a number for the owner's "
        "decision, which the lab does not currently have. Every parked arm is judged by the "
        "2009-2015 era first, not the whole-window average (insights 89, 91, 93), and by the "
        "2008 episode second. Window assumption: all arms declare all four funds so they share "
        "one start, set by the youngest, gold (2004-11 plus the 275-session lookback), which "
        "puts the 2000-2002 bear outside this measurement; I assume that is better than letting "
        "arms score different years. SHY, BIL and XLU were left out to stay within six arms "
        "(SHY and BIL are cash-like and add no new question; XLU is the staples question again). "
        "Published-anomaly note: trend-plus-bonds tactical allocation was popularised by Faber "
        "(2007) and was widely traded afterwards, so a dev result from before 2015 is the "
        "pre-crowd value."
    ),
    expected_failure=(
        "Treasuries and equities were negatively correlated in 2000-2002 and 2008 and "
        "positively correlated in parts of 2009-2015, so the arm that rescues 2008 may do "
        "nothing in the era the money lives in; the honest answer would then be that no single "
        "parking place works in both. Gold's 2011-2015 collapse makes it the arm most likely to "
        "look good whole window and worst in the era that matters. Staples keep most of the "
        "equity beta and so may rescue little in a crash. Because the gate flips about a dozen "
        "times a decade, every arm pays extra orders at Gotrade's per-order minimum, so a "
        "parked arm's gain over cash is net of that extra churn. Dev window is shorter than "
        "M0287's, so figures are not comparable with M0287's recorded trials; compare only "
        "inside this method."
    ),
    candidates=(
        _v("FULL", ParkParams(gate=None),
           "no gate: always invested, the no-opinion arm"),
        _v("CASH", ParkParams(),
           "the shared 200-day gate holding cash while out: the incumbent every gated book uses"),
        _v("IEF", ParkParams(park=("IEF",)),
           "gate out: the whole book in intermediate Treasuries (evidence only, non-default ETF)"),
        _v("TLT", ParkParams(park=("TLT",)),
           "gate out: the whole book in long Treasuries (evidence only, non-default ETF)"),
        _v("GLD", ParkParams(park=("GLD",)),
           "gate out: the whole book in gold (evidence only, non-default ETF)"),
        _v("XLP", ParkParams(park=("XLP",)),
           "gate out: the whole book in consumer staples (evidence only, non-default ETF)"),
    ),
    seen_keys=(
        "concept:gate-parking-place",
        "concept:trend-gate-treasury-or-gold-fallback",
        "concept:out-leg-holding-instead-of-cash",
    ),
)
