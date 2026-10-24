"""M0351 — Dearest-third buyback shrinkers behind the SPY 200-day safety switch, with the twin.

Variation of M0345. Reserved by Sera batch 20261024-1959 as an ``idea`` row; this file refines it
and keeps its id.

Why. M0345 found the 20 biggest share-shrinkers in the dearest third lead a matched blind draw by
4.8-6.5 points a year in 2009-2015, but the book fell 48% at the worst and missed the luck bar.
The lab's one cheap defence against a fall is the SPY 200-day switch (``f_factor.trend_on``, read
through M0287's ``vote_share`` so the gate is literally the function every gated book calls).
This file wraps M0345's allocator in that switch and registers the same book never switching
beside it, so the price of acting on the switch is measured and not guessed (insight 523).

Arms are a 2x2 on two books: the shrinkers and M0345's matched blind draw, each switched
(SW) and always invested (AI). The AI shrinkers are M0345's own book, kept here so the pair
shares one run; the matched draws say whether the switch helps a book with no stock opinion in
the same way. The wrapper adds only the gate: while it is on, it delegates to M0345's allocator
untouched, and while it is off it holds nothing (cash).

Market-aware (``market_fields = ("shares",)``). Pure: reads bars and counts dated on or before
``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0287_graded_trend_vote import vote_share
from seer_engine.lab.methods.m0345_dear_band_matched_draw import DEAR_BAND, DearParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 24)

GATE = (200,)


@dataclass(frozen=True, slots=True)
class SwitchedParams:
    """M0345's book plus the switch: ``gate`` is ``(200,)`` (SPY 200-day) or ``None`` (always in)."""

    book: DearParams
    gate: tuple[int, ...] | None = GATE

    def __post_init__(self) -> None:
        if not isinstance(self.book, DearParams):
            raise TypeError(f"book must be DearParams, got {type(self.book).__name__}")
        if self.gate is not None and self.gate != GATE:
            raise ValueError(f"gate must be None or {GATE}, got {self.gate!r}")

    def as_dict(self) -> dict[str, str]:
        out = dict(self.book.as_dict())
        out["gate"] = "off" if self.gate is None else "SPY:" + "/".join(str(n) for n in self.gate)
        return out


def _check(params: object) -> SwitchedParams:
    if not isinstance(params, SwitchedParams):
        raise TypeError(f"params must be SwitchedParams, got {type(params).__name__}")
    return params


class SwitchedDearBand:
    """M0345's allocator while SPY closes above its 200-day average; cash otherwise."""

    id = "M0351"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return max(DEAR_BAND.lookback(_check(params).book), max(GATE))

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _on(self, history: Mapping[str, History], data_date: date, q: SwitchedParams) -> bool:
        return vote_share(history, data_date, q.gate) > 0

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        if not self._on(history, data_date, q):
            return ()
        return DEAR_BAND.targets(history, members, data_date, held, q.book)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return DEAR_BAND.prepare(history)

    def prepare_market(self, market: Any) -> Any:
        return DEAR_BAND.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        q = _check(params)
        if not self._on(prepared.history, data_date, q):
            return ()
        return DEAR_BAND.targets_prepared(prepared, members, data_date, held, q.book)


SWITCHED = SwitchedDearBand()


def _v(suffix: str, params: SwitchedParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0351-{suffix}", family="M0351", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCHED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0351",
    name="Dearest-third buyback shrinkers behind a market safety switch, with the always-invested twin",
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0345 (dearest-third shrinkers vs matched draw); SPY 200-day gate via "
        "M0287 vote_share / f_factor.trend_on; M0291 for the gated-twin pattern; insight 523 for "
        "the no-opinion arm; Pontiff & Woodgate (2008) JF 63(2) 921-945"
    ),
    parent_id="M0345",
    hypothesis=(
        "M0345's 20 biggest share-shrinkers in the dearest third led a matched blind draw by "
        "4.8-6.5 points a year in 2009-2015 on both stores but fell 48% at the worst and missed "
        "the luck bar. Wrap the same allocator in the lab's SPY 200-day safety switch (all in "
        "while SPY closes above its 200-day average, cash otherwise) and register the same book "
        "never switching, so the switch's cost is priced. 2x2 on two books, all "
        "MONTHLY_HOLD_FRAC_GOTRADE: shrinkers switched (SW-S) and always in (AI-S); matched draw "
        "seeds 1 and 2 switched (SW-MD1/2) and always in (AI-MD1/2). The matched draws carry no "
        "stock opinion, so AI-vs-SW on them prices the switch for a book with no signal, and "
        "AI-vs-SW on the shrinkers prices it for the signal. Published-anomaly note: buybacks "
        "(2008) are widely known and may have faded. Judge 2009-2015 and the dead-company store "
        "first. Predictions written before any result: (a) SW-S cuts the worst fall below AI-S's "
        "by 15+ points, capping 2008; (b) SW-S gives up time in a rising 2009-2015, so its "
        "CAGR trails AI-S there; (c) SW-S still leads the median switched matched draw by 3+ "
        "points a year in 2009-2015 on both stores; (d) the switch's cost on the shrinkers is "
        "about the same as on the draws, so the signal and the switch are separable. Close-out "
        "rule: if SW-S fails the fall bar or its 2009-2015 lead over the switched draws is under "
        "3 points on either store, the dear-band buyback idea is closed behind a switch; if it "
        "is dev-eligible it goes to the hard gate, and nothing here is itself a buy signal."
    ),
    expected_failure=(
        "Four ways. (1) The luck bar: N is above 200, and a 20-name book from a 30-80 name third "
        "is noisy, so DSR stays under 0.90 even if the fall is capped. (2) The switch costs more "
        "than it saves in 2009-2015, a decade without a bear market, so SW-S trails AI-S and "
        "SPY there (M0332 and M0334 saw the hard switch trail SPY by about 2 points). (3) The "
        "switched draws gain as much as the switched shrinkers, so the lead over blind draws "
        "was the switch and not the buyback signal. (4) Buybacks have faded: a strong pre-2009 "
        "edge that is gone in 2009-2015. A tweak after the result is a new method."
    ),
    candidates=(
        _v("SW-S", SwitchedParams(DearParams(20, "shrink")),
           "Shrinkers behind the SPY 200-day switch"),
        _v("AI-S", SwitchedParams(DearParams(20, "shrink"), gate=None),
           "Shrinkers never switching: the no-opinion-on-timing twin"),
        _v("SW-MD1", SwitchedParams(DearParams(20, "matched", seed=1)),
           "Matched blind draw (seed 1) behind the switch"),
        _v("SW-MD2", SwitchedParams(DearParams(20, "matched", seed=2)),
           "Matched blind draw (seed 2) behind the switch"),
        _v("AI-MD1", SwitchedParams(DearParams(20, "matched", seed=1), gate=None),
           "Matched blind draw (seed 1), always invested"),
        _v("AI-MD2", SwitchedParams(DearParams(20, "matched", seed=2), gate=None),
           "Matched blind draw (seed 2), always invested"),
    ),
    seen_keys=(
        "concept:dear-band-buybacks-behind-safety-switch",
    ),
)
