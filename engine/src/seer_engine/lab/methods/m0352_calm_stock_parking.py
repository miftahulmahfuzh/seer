"""M0352 -- Park the switched-off book in the calmest index stocks instead of cash.

Source: variation of M0291 (and M0287, M0271 beneath it); the low-volatility anomaly (Haugen and
Heins 1975, popularised by Baker, Bradley and Wurgler 2011 and the low-vol ETFs after 2011).
Idea: M0291 found that while the shared SPY 200-day gate is out, parking in staples recovered
most of cash's 2009-2015 cost because it kept stock exposure, but staples (XLP) is not a Gotrade
default fund. The executable version holds the calmest index stocks themselves, which need no
owner input, so the arm can be eligible.

Same chassis, gate, band, fees and funding as M0291. Only the out leg differs, and it is run
beside two controls that keep the "hold 20 stocks" part and drop the "calm" part.

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
from seer_engine.lab.methods.m0291_gate_parking_place import GATE
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
)

ADDED = date(2026, 10, 24)

#: What the out leg ranks the screened index members on. ``calm`` is the treatment; ``loud`` and
#: ``traded`` are the controls: the same 20-stock out leg picked the opposite way, and picked by
#: size of trading with no opinion on volatility.
PICKS: tuple[str, ...] = ("calm", "loud", "traded")


@dataclass(frozen=True, slots=True)
class CalmParams:
    """M0291's base book plus an out leg of ``count`` stocks chosen by ``pick``.

    ``gate`` is ``None`` for the always-invested arm and ``(200,)`` otherwise. ``pick`` is None
    for cash, the incumbent every other gated book uses.
    """

    book: ScaledBandParams = ScaledBandParams()
    gate: tuple[int, ...] | None = GATE
    pick: str | None = None
    count: int = 20
    vol_n: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.book, ScaledBandParams):
            raise TypeError(f"book must be ScaledBandParams, got {type(self.book).__name__}")
        if self.gate is not None and self.gate != GATE:
            raise ValueError(f"gate must be None or {GATE}, got {self.gate!r}")
        if self.pick is not None and self.pick not in PICKS:
            raise ValueError(f"pick must be None or one of {PICKS}, got {self.pick!r}")
        if isinstance(self.count, bool) or not isinstance(self.count, int) or not 1 <= self.count <= 100:
            raise ValueError(f"count must be an int in 1..100, got {self.count!r}")
        if isinstance(self.vol_n, bool) or not isinstance(self.vol_n, int) or self.vol_n < 5:
            raise ValueError(f"vol_n must be an int >= 5, got {self.vol_n!r}")

    def factor(self) -> FactorParams:
        """The screen the out leg reads: M0291's liquidity and price floors, volatility over vol_n.

        Momentum is never ranked on, but the shared row builder wants it finite, so it is read
        over the same window and skip 0; that keeps the deepest lookback at ``vol_n + 1``.
        """
        return FactorParams(
            rank="lowvol", top=self.count, mom_n=self.vol_n, mom_skip=0, vol_n=self.vol_n,
            min_dollar_volume=self.book.min_dollar_volume, min_price=self.book.min_price,
            trend=None,
        )

    def as_dict(self) -> dict[str, str]:
        out = dict(self.book.as_dict())
        out["gate"] = "off" if self.gate is None else "SPY:" + "/".join(str(n) for n in self.gate)
        out["out_leg"] = "cash" if self.pick is None else f"{self.pick}{self.count}"
        out["vol_n"] = str(self.vol_n)
        return out


def _check(params: object) -> CalmParams:
    if not isinstance(params, CalmParams):
        raise TypeError(f"params must be CalmParams, got {type(params).__name__}")
    return params


def _rank(rows: list[FactorRow], q: CalmParams) -> list[FactorRow]:
    if q.pick == "calm":
        key = lambda r: (r.vol, r.symbol)  # noqa: E731
    elif q.pick == "loud":
        key = lambda r: (-r.vol, r.symbol)  # noqa: E731
    else:
        key = lambda r: (-r.dollar_volume, r.symbol)  # noqa: E731
    return sorted(rows, key=key)[: q.count]


def _targets(rows: list[FactorRow], q: CalmParams) -> tuple[Target, ...]:
    if q.pick is None:
        return ()
    w = equal_weight(q.count)
    out: list[Target] = []
    for row in _rank(rows, q):
        t = target_from_close(row.symbol, row.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class CalmParkedBook(GradedVoteBook):
    """M0291's gate and base book; while the gate is out, hold ``count`` index stocks, not a fund.

    A name needs ``vol_n + 1`` bars and passes the same dollar-volume and price floors as the
    base book, so the out leg is as tradeable as the in leg. Weights are 1/count each, fractional
    shares, so a short list leaves the rest of the account in cash.
    """

    id = "M0352"

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def lookback(self, params: Any) -> int:
        q = _check(params)
        return max(super(GradedVoteBook, self).lookback(q.book), max(GATE), factor_lookback(q.factor()))

    def _gate_on(self, history: Mapping[str, History], data_date: date, q: CalmParams) -> bool:
        return vote_share(history, data_date, q.gate) > 0

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        if q.gate is None or self._gate_on(history, data_date, q):
            return super(GradedVoteBook, self).targets(history, members, data_date, held, q.book)
        if q.pick is None:
            return ()
        return _targets(factor_rows(history, members, data_date, q.factor()), q)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        q = _check(params)
        if q.gate is None or self._gate_on(prepared.history, data_date, q):
            return super(GradedVoteBook, self).targets_prepared(
                prepared, members, data_date, held, q.book)
        if q.pick is None:
            return ()
        return _targets(prepared.rows_on(members, data_date, q.factor()), q)


BOOK = CalmParkedBook()


def _v(suffix: str, params: CalmParams, what: str) -> Candidate:
    c = Candidate(
        id=f"M0352-{suffix}",
        family="M0352",
        rules=BAND,
        allocator=BOOK,
        params=params,
        rationale=what,
        added=ADDED,
        owner_inputs=(),
    )
    return replace(c, owner_inputs=candidate_owner_inputs(c))


METHOD = Method(
    id="M0352",
    name="Park the switched-off book in the calmest index stocks instead of cash",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "M0291 for the chassis, the shared SPY 200-day gate and the finding that staples, "
        "which kept stock exposure, recovered the most of cash's 2009-2015 cost (4.1 of 6.7 "
        "points a year) but is not a Gotrade default fund; M0287 and M0271 for the price of "
        "cash on this chassis; insight 523 for the no-opinion third arm; low-volatility "
        "anomaly (Haugen and Heins 1975; Baker, Bradley and Wurgler 2011)"
    ),
    parent_id="M0291",
    hypothesis=(
        "M0291 held the SPY 200-day gate, the 50-name opinion-free book and the fees fixed and "
        "changed only what the book holds while the gate is out. Staples recovered 4.1 of "
        "cash's 6.7 points a year in 2009-2015 but needs a fund Gotrade does not list by "
        "default and lost 14.6% in 2008. This method tests the executable version: while the "
        "gate is out, hold the 20 calmest index stocks (lowest 60-day volatility among "
        "members passing the book's own price and dollar-volume floors), equal weight, "
        "fractional shares, Gotrade fees. No owner input, so it can be eligible. Five arms on "
        "one store: always invested (the no-opinion arm), gate with cash (incumbent), gate "
        "parking in the calmest 20 (treatment), gate parking in the 20 MOST volatile stocks "
        "(control: stocks with the calm sign flipped), and gate parking in the 20 most-traded "
        "stocks (control: stocks with no opinion on volatility). If calm beats cash but does "
        "not beat the two controls, the gain is stock exposure and not calmness. Judged by "
        "2009-2015 first, 2008 second. Published-anomaly note: low volatility was published "
        "in 1975, popularised in 2011 and packaged in ETFs, so a dev result is the pre-crowd "
        "value. The out leg is not the whole book, so the expected mechanism is exposure kept "
        "during a gate-out spell, which is the market's rising-decade drift reaching the book."
    ),
    expected_failure=(
        "Calm stocks fell nearly as hard in 2008 as the market, so the arm recovers nothing "
        "the always-invested arm does not and is just the book with less return; the loud "
        "control would then do as well or better in 2009-2015 because it has more beta in a "
        "rising decade. The gate flips about a dozen times a decade and each flip trades 20 "
        "small slots at Gotrade's per-order minimum, so the arm pays more fee than a fund "
        "would. Screened low-volatility members may be utilities and staples, which lagged "
        "the 2009-2015 leaders. A max fall over the bar and DSR under 0.90 at the lab's N are "
        "both likely."
    ),
    candidates=(
        _v("FULL", CalmParams(gate=None),
           "no gate: always invested, the no-opinion arm"),
        _v("CASH", CalmParams(),
           "the shared 200-day gate holding cash while out: the incumbent"),
        _v("CALM20", CalmParams(pick="calm"),
           "gate out: hold the 20 calmest screened index stocks by 60-day volatility, equal weight"),
        _v("LOUD20", CalmParams(pick="loud"),
           "gate out: hold the 20 most volatile screened stocks (control: calm sign flipped)"),
        _v("TRADED20", CalmParams(pick="traded"),
           "gate out: hold the 20 most-traded screened stocks (control: stocks, no volatility view)"),
    ),
    seen_keys=(
        "concept:gate-parking-place",
        "concept:out-leg-holding-instead-of-cash",
        "concept:low-volatility-stocks-as-gate-parking",
    ),
)
