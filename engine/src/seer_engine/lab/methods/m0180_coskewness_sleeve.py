"""M0180 — Crash-prone stocks as a small sleeve: M0179's negative-coskewness picks as a minority
beside a fixed SPY core, no market switch.

Source: variation of M0179 (its quarterly, banded coskewness book as the sleeve); Harvey &
Siddique (2000), JF 55(3); the core-plus-sleeve shape of M0030 and M0096.
Idea: M0179's no-switch 20-name book was the only version that did not trail SPY in 2009-2015
(+0.3 points a year on dev, +3.7 on the dead-company check store), but it fell 52% in 2008, and
the 200-day switch that cut the fall gave back the recent years. Shrink the bet instead of timing
it: hold SPY with most of the money and the most negative-coskewness members with the rest.

Why a new allocator and not ``BLEND``: ``BLEND`` gives each part its own share of the book but the
sleeve here must keep M0179's ``choose`` banding against what the *whole* book holds, and M0096's
shape already does exactly this: run the inner allocator, scale every target by ``1 - core``
(floored to WEIGHT_QUANTUM; a zero drops), then add SPY at ``core`` to the sleeve's own SPY park.

    * the sleeve is M0179's ``CoskewAllocator`` verbatim (156 weekly returns, quarterly re-pick on
      the last close of March / June / September / December, kept under 40%, F4's $5 / $20M
      screen), with no switch of its own;
    * ``switch=True`` (evidence only): F4's SPY-200 gate empties the *whole* book while SPY is
      under its 200-day average, as M0096's "book" switch does. A SPY core held through 2008 falls
      with SPY (about 55% on dev), so without some switch no core-plus-sleeve book can meet the
      25% bar; this variant prices what meeting it costs.

At a 70% core a 20-name sleeve's slots are 1.5%, a 40-name sleeve's 0.75%; at 60%, 2% and 1%.
Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
Reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0179_coskewness import COSKEW, CoskewParams, CoskewPrepared
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, factor_lookback, trend_on

ADDED = date(2026, 10, 17)
SW = ("SPY", 200)


@dataclass(frozen=True, slots=True)
class SleeveParams:
    """``sleeve`` is M0179's book (its ``inner`` must carry no switch); ``core`` the fixed SPY
    share; ``switch`` puts F4's SPY-200 gate on the whole book."""

    sleeve: CoskewParams
    core: Decimal
    switch: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sleeve, CoskewParams):
            raise TypeError(f"sleeve must be CoskewParams, got {type(self.sleeve).__name__}")
        if self.sleeve.inner.trend is not None:
            raise ValueError("the sleeve carries no switch of its own; use switch=True")
        if not isinstance(self.core, Decimal) or not self.core.is_finite() or not 0 < self.core < 1:
            raise ValueError(f"core must be a Decimal in (0, 1), got {self.core!r}")
        if self.core % WEIGHT_QUANTUM != 0:
            raise ValueError(f"core must be a multiple of {WEIGHT_QUANTUM}, got {self.core}")
        if not isinstance(self.switch, bool):
            raise TypeError(f"switch must be a bool, got {type(self.switch).__name__}")

    def gate(self) -> FactorParams:
        """The sleeve's screen with the switch attached when the book is switched."""
        return replace(self.sleeve.inner, trend=SW) if self.switch else self.sleeve.inner

    def as_dict(self) -> dict[str, str]:
        out = {"core": format(self.core.normalize(), "f"), "switch": str(self.switch).lower()}
        for k, v in self.sleeve.as_dict().items():
            out[f"sleeve.{k}"] = v
        return out


def _check(params: object) -> SleeveParams:
    if not isinstance(params, SleeveParams):
        raise TypeError(f"params must be SleeveParams, got {type(params).__name__}")
    return params


class CoskewSleeveAllocator:
    """A fixed SPY core plus M0179's coskewness book on the rest of the money."""

    id = "M0180"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).gate())

    def symbols(self, params: Any) -> tuple[str, ...]:
        return COSKEW.symbols(_check(params).sleeve)

    def holds(self, params: Any) -> tuple[str, ...]:
        return COSKEW.holds(_check(params).sleeve)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CoskewPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SleeveParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.gate()):
            return ()
        sleeve = COSKEW.targets_prepared(prepared, members, data_date, held, p.sleeve)
        market = p.sleeve.market
        share = Decimal(1) - p.core
        order: list[str] = []
        first: dict[str, Target] = {}
        total: dict[str, Decimal] = {}
        for t in sleeve:
            w = scale_weight(t.weight, share)
            if w is None:
                continue
            order.append(t.symbol)
            first[t.symbol] = t
            total[t.symbol] = w
        mh = prepared.history.get(market)
        if mh is not None and mh.index_of(data_date) is not None:
            if market in first:
                total[market] = to_weight(total[market] + p.core)
            else:
                t = target_from_close(market, last_close(mh, data_date), p.core)
                if t is not None:
                    order.append(market)
                    first[market] = t
                    total[market] = t.weight
        return tuple(replace(first[s], weight=total[s]) for s in order)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(CoskewPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CoskewPrepared:
        return COSKEW.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoskewPrepared):
            raise TypeError(f"prepared must be CoskewPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SLEEVE = CoskewSleeveAllocator()


def _book(top: int, positive: bool = False) -> CoskewParams:
    # As M0179: F4's screen only (its rank is unused), kept under 40%, no switch inside the sleeve.
    return CoskewParams(FactorParams(rank="momentum", top=top, trend=None), positive=positive)


def _v(suffix: str, params: SleeveParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0180-{suffix}", family="M0180", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SLEEVE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0180",
    name=(
        "Crash-prone stocks as a small sleeve: the negative-coskewness picks as a minority beside "
        "a SPY core, no market switch"
    ),
    family="stock-coskewness",
    source_kind="variation",
    source_ref=(
        "variation of M0179 (its quarterly banded coskewness book as the sleeve); Harvey & "
        "Siddique (2000), JF 55(3); core-plus-sleeve shape of M0030 and M0096"
    ),
    parent_id="M0179",
    hypothesis=(
        "Published 2000. M0179's no-switch 20-name negative-coskewness book was the only version "
        "that did not trail SPY in 2009-2015 (+0.3 points a year on dev), but it fell 52% in 2008, "
        "and the 200-day switch that cut the fall cost the recent years. Shrink the bet instead "
        "of timing it: a fixed SPY core and M0179's book verbatim on the rest (156 weekly "
        "returns, standardized coskewness, quarterly re-pick, kept under 40%, F4's screen), no "
        "switch, fractional shares at Gotrade's real fees on the owner's deposits. Variants, all "
        "chosen from dev-window reasoning only: C70-N20 (the idea: 70% SPY, 20 names at 1.5%); "
        "C60-N20 (60% SPY, a bigger sleeve at 2%); C70-N40 (70% SPY, 40 names at 0.75%, a "
        "broader and less noisy sleeve); C70-P20 (paired control: 70% SPY, the 20 most POSITIVE "
        "names); C70-N20-SW and C70-P20-SW (evidence: the same pair with the SPY-200 switch on "
        "the whole book, because a SPY core held through 2008 falls about as far as SPY, near "
        "55%, so no unswitched core book can meet 25%). Assumption written now: the idea row's "
        "'worst fall <= 25%' is unreachable without a switch, so the unswitched variants are "
        "judged on the lab's dev screen and on whether the sleeve adds to SPY; the switched pair "
        "answers the 25% question. Success: C70-N20 beats SPY TR on the deposits, beats C70-P20, "
        "keeps a positive 2009-2015 edge, and wins a majority of walk-forward folds."
    ),
    expected_failure=(
        "The core dilutes the edge toward SPY: a 30% sleeve keeps about 30% of M0179-N20's lead "
        "(roughly 0.9 points a year), its +0.3 point 2009-2015 edge shrinks to about +0.1, inside "
        "the noise, and the DSR falls under 0.90 because the swings stay SPY-sized while the "
        "edge shrinks. The worst fall lands near SPY's 55% and fails the 50% dev screen; the "
        "switched pair meets 25% but trails SPY after 2009, as every SPY-200 book in the lab has. "
        "The fold selection again prefers the positive control in some folds, because the gap "
        "between the two sides is a high-beta regime, not a steady premium. A widely published "
        "anomaly: any dev edge is likely to fade after 2015."
    ),
    candidates=(
        _v("C70-N20", SleeveParams(_book(20), Decimal("0.7")),
           "70% SPY core + 30% in the 20 most negative-coskewness members, no switch"),
        _v("C60-N20", SleeveParams(_book(20), Decimal("0.6")),
           "60% SPY core + 40% in the 20 most negative-coskewness members, no switch"),
        _v("C70-N40", SleeveParams(_book(40), Decimal("0.7")),
           "70% SPY core + 30% in the 40 most negative-coskewness members, no switch"),
        _v("C70-P20", SleeveParams(_book(20, positive=True), Decimal("0.7")),
           "Control: 70% SPY core + 30% in the 20 most positive-coskewness members, no switch"),
        _v("C70-N20-SW", SleeveParams(_book(20), Decimal("0.7"), switch=True),
           "70% SPY + 30% negative-coskewness sleeve, the SPY-200 switch on the whole book"),
        _v("C70-P20-SW", SleeveParams(_book(20, positive=True), Decimal("0.7"), switch=True),
           "Control for the switched book: 70% SPY + 30% positive-coskewness, whole-book switch"),
    ),
    seen_keys=(
        "concept:coskewness-sleeve",
        "concept:spy-core-coskewness-satellite",
    ),
)
