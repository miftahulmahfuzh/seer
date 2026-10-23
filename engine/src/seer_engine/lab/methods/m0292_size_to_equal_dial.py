"""M0292 — Slide the weighting from pure size to pure equal in five rungs over the same names,
and read the narrow-month column beside 2009-2015.

Source: variation of M0286 (the re-weighting cadence 2x2, which found equal slices beat market
value by 2.8 points a year over identical names and by 4.6 points in 2009-2015), and through it
M0281/M0224/M0226, which built the whole-market base. Insight 462 (the equal-weight placebo's
8-point gap decomposed to 3.6 gate, 3.8 fees, under 0.9 pool-and-weighting), insight 91 (the
lab's long-standing reading that favouring the smaller members is a handicap), insight 492
(cash in lumps costs more than cash spread evenly), and M0266 (a point of exposure is priced by
its era, not by a constant). Reserved by Sera 20261023-1049 as M0292.

Why this shape. M0286 turned a two-position switch: weight every screened index member by its
market value, or give the same names one equal slice each. The equal side won by 2.8 points a
year and by 4.6 in 2009-2015, which is the opposite sign to what this lab has assumed for a
year. But a two-point read cannot rank a dial -- the lab has the scar (insight 500: an "8x"
slope between stores was one drifted pair, and five rungs said 1.66x) -- and M0286's own
coordinator check named two unseparated terms riding along with that 2.8: the two arms do not
hold the same amount of money in the market (91.4% against 97.1%), and the equal arms earn +13%
a year in broad months and LOSE 8-9% in narrow ones, while 2018-2026 was narrow.

So this method replaces the switch with a dial and turns it five times. Each name's weight is
its market value raised to a power ``a``, rescaled: ``a=0`` gives every name the identical
weight (pure equal), ``a=1`` gives it its market value (pure size), and 0.25, 0.5 and 0.75 are
the rungs in between. Nothing else moves. The names are identical at every rung -- the same
F4-screened members with a known point-in-time market value, one listed class per identical
share count -- so the ladder moves weighting and only weighting.

The cadence is M0286's EQ-DEPOSIT: a January anchor, never a sale to fund a buy, each month's
deposit handed to the names furthest below their target. M0286 found that is both the cheapest
shape it tested and the one that holds exposure nearly still, which is exactly what this ladder
needs: an exposure column that barely moves across the rungs means a return curve that is about
weighting rather than about time spent in cash. If exposure does move across the rungs, the
analysis prices it at this chassis's own measured rate rather than asserting a weighting result,
and says so.

The sixth arm is not a rung. ``a=1`` with the 5% ceiling lifted is the one arm that prices the
cap, because the cap binds hardest where the weights are most concentrated. The reserved row's
own expected failure names this: market value raised to a power is not a clean size tilt once
the ceiling re-spreads the excess, so part of any curvature in the return curve is the cap and
not the weighting, and without the cap priced at its hardest-binding rung the curvature cannot
be attributed. It is the habit-off half of a 2x2 whose habit-on half is PURE-SIZE, and it costs
no method id.

Recorded before the pre-registration, so the predictions below can be read against what was
already known: a book-construction probe (no backtest, no returns) measured the ceiling's bite
on six year-end dates. The 5% cap never binds at powers 0, 0.25, 0.5 or 0.75; at power 1 it
moves between 0 and 1.8% of total weight, in three of the six years sampled. The rungs do
separate -- on 2015-10-16 the ten biggest names hold 2.6%, 4.7%, 8.2%, 13.2% and 19.6% of the
book as the power rises -- so a step-function result would be a surprise rather than the
default. That probe fixed the SIZE-NOCAP prediction below and nothing else; no return, fall or
era number was looked at before this file was committed.

Assumption written down because it was a judgement, not a given: the reserved row asked for five
rungs and said nothing about a sixth arm. The ceiling is spent on, rather than a sixth rung at
``a=1.25``, because the row's own expected failure names the ceiling as the thing that would
make the five rungs unreadable, and an over-tilted rung past pure size answers a question
nobody asked.

Nothing here is a candidate and the hypothesis says so before any result: M0286's arms fall
50-58% in 2008 against a 25% bar, and a weighting dial does not touch that. Success is a
measurement.

Market-aware: reads ``shares`` (company size); without it, or without the market's membership
calendar, it targets nothing. Pure: reads only bars, share counts and index membership dated
<= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.control_draw import max_shadow_depth, shadow_lookback_for
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20
from seer_engine.lab.methods.m0222_raise_tilted_market_core import capped, core
from seer_engine.lab.methods.m0286_rebalance_cadence import anchor_session
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    FactorPrepared,
    factor_lookback,
    prepare_factor,
)

ADDED = date(2026, 10, 23)
EVERY = 1000  # past any day's member count: the base is every member with a known size
CEIL = Decimal("0.05")
NO_CEIL = Decimal("1")
_W_Q = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class PowerParams:
    """``power`` is the dial: each name's weight is its market value raised to this power, then
    rescaled and capped. 0 is one equal slice each, 1 is the market's own shape, and the rungs
    between are a continuous slide from one to the other over identical names.

    The other fields carry M0286's EQ-DEPOSIT cadence: ``months`` is how often the weights are
    re-set from scratch (12, each January), and ``deposit=True`` means nothing is ever sold to
    fund a buy -- between anchors each month's money goes to the names furthest below target.

    This is a separate class from M0286's ``CadenceParams`` on purpose. Adding a field to that
    one would move every configuration digest M0286 recorded, and recorded trials are frozen.
    """

    inner: FactorParams = NOT20
    top: int = EVERY
    ceiling: Decimal = CEIL
    power: Decimal = Decimal("1")
    months: int = 12
    deposit: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("top", "months"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {v!r}")
        if self.top < 2:
            raise ValueError(f"top must be >= 2, got {self.top}")
        if self.months not in (1, 2, 3, 4, 6, 12):
            raise ValueError(f"months must divide 12 (1, 2, 3, 4, 6, 12), got {self.months}")
        if not isinstance(self.deposit, bool):
            raise TypeError(f"deposit must be a bool, got {type(self.deposit).__name__}")
        if self.deposit and self.months == 1:
            raise ValueError("a book re-weighted every month has no month for the deposit to steer")
        if not isinstance(self.power, Decimal) or not (Decimal(0) <= self.power <= Decimal(2)):
            raise ValueError(f"power must be a Decimal in [0, 2], got {self.power!r}")
        if not isinstance(self.ceiling, Decimal) or not (Decimal(0) < self.ceiling <= Decimal(1)):
            raise ValueError(f"ceiling must be a Decimal in (0, 1], got {self.ceiling!r}")
        if self.ceiling * self.top < 1:
            raise ValueError("ceiling x top must reach 1, or the weights cannot sum to 1")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "ceiling": str(self.ceiling), "power": str(self.power),
               "months": str(self.months), "deposit": str(self.deposit),
               "size": "market-value-one-class", "market": self.market,
               "weighting": "market-value-to-the-power",
               "carry": "price-drift-since-anchor",
               "anchor": "month-number-divides-months"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PowerParams:
    if not isinstance(params, PowerParams):
        raise TypeError(f"params must be PowerParams, got {type(params).__name__}")
    return params


@dataclass
class PowerPrepared:
    """The three attributes M0222's ``core`` and M0286's ``anchor_session`` read."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    market: Any = field(repr=False, default=None)


def target_weights(prepared: PowerPrepared, members: AbstractSet[str], data_date: date,
                   p: PowerParams) -> dict[str, tuple[float, float]]:
    """symbol -> (close on or before ``data_date``, the weight this rung wants it at).

    Market value raised to ``power``, rescaled to 1, then capped. ``power=0`` makes every raw
    weight exactly 1.0, which is one equal slice each; ``power=1`` leaves the value alone.
    """
    book = core(prepared, members, data_date, p)  # type: ignore[arg-type]
    if len(book) < 2:
        return {}
    a = float(p.power)
    raw = {s: (1.0 if a == 0.0 else v**a) for s, _, v in book}
    w = capped(raw, float(p.ceiling))
    return {s: (c, w[s]) for s, c, _ in book}


def carried(prepared: PowerPrepared, members: AbstractSet[str], data_date: date, anchor: date,
            p: PowerParams) -> dict[str, tuple[float, float]]:
    """The anchor's book carried to ``data_date`` by each name's own price change.

    A name that has left the index since the anchor is dropped, as is one with no readable
    price. Weights are left un-normalised: the caller re-caps them, which rescales to 1 exactly
    as the real book's weights rescale.
    """
    m = prepared.market
    was = target_weights(prepared, m.membership.members_on(anchor), anchor, p)
    out: dict[str, tuple[float, float]] = {}
    for s, (c0, w0) in was.items():
        if s not in members:
            continue
        c = last_close(prepared.history.get(s), data_date)
        if c is None or not (c > 0.0) or not (c0 > 0.0):
            continue
        out[s] = (c, w0 * c / c0)
    return out


def _emit(weights: dict[str, float], closes: dict[str, float],
          order: dict[str, float]) -> tuple[Target, ...]:
    out: list[Target] = []
    for s in sorted(weights, key=lambda k: (-order[k], k)):
        wt = Decimal(repr(weights[s])).quantize(_W_Q, rounding=ROUND_FLOOR)
        if wt <= 0:
            continue
        t = target_from_close(s, closes[s], wt)
        if t is not None:
            out.append(t)
    return tuple(out)


def choose(prepared: PowerPrepared, members: AbstractSet[str], data_date: date,
           p: PowerParams) -> tuple[Target, ...]:
    """The book this rung wants held after the next open.

    On the January anchor the weights are set from scratch. In between, the book is the anchor's
    weights carried by price, and each name's target is the larger of that drifted weight and
    the weight its rung wants, re-capped: nothing is sold to fund a purchase, and the targets
    are handed over most under-weight first, so the month's deposit closes the widest gaps.
    """
    anchor = anchor_session(prepared, data_date, p)  # type: ignore[arg-type]
    held = carried(prepared, members, data_date, anchor, p) if anchor is not None else {}
    if len(held) < 2:  # an anchor that cannot be read yet: set the weights here instead
        now = target_weights(prepared, members, data_date, p)
        if len(now) < 2:
            return ()
        w = {s: wt for s, (_, wt) in now.items()}
        return _emit(w, {s: c for s, (c, _) in now.items()}, w)
    closes = {s: c for s, (c, _) in held.items()}
    drift = {s: wt for s, (_, wt) in held.items()}
    if not p.deposit:
        w = capped(drift, float(p.ceiling))
        return _emit(w, closes, w)
    now = target_weights(prepared, members, data_date, p)
    raw = dict(drift)
    for s, (c, wt) in now.items():
        raw[s] = max(raw.get(s, 0.0), wt)
        closes[s] = c
    w = capped(raw, float(p.ceiling))
    gap = {s: w[s] - drift.get(s, 0.0) for s in w}
    return _emit(w, closes, gap)


class SizeToEqualDialAllocator:
    """The whole-market base weighted by market value raised to a power, from one equal slice
    each (0) to the market's own shape (1), on a January anchor the month's deposit steers."""

    id = "M0292"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = factor_lookback(p.inner)
        if p.months == 1:
            return inner
        return shadow_lookback_for(inner, min(p.months, max_shadow_depth(inner)))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def _run(self, prepared: PowerPrepared, members: AbstractSet[str], data_date: date,
             p: PowerParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(m.shares) == 0:
            return ()  # no panel: target nothing (the market-aware allocator contract)
        return choose(prepared, members, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts and no membership calendar, so no book."""
        return self._run(PowerPrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> PowerPrepared:
        return PowerPrepared(history, prepare_factor(history))

    def prepare_market(self, market: Any) -> PowerPrepared:
        return PowerPrepared(market.history, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, PowerPrepared):
            raise TypeError(f"prepared must be PowerPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


DIAL = SizeToEqualDialAllocator()


def _v(suffix: str, params: PowerParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0292-{suffix}", family="M0292",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND, allocator=DIAL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0292",
    name=(
        "Slide the weighting from pure size to pure equal in five rungs over the same names, "
        "and read the narrow-month column beside 2009-2015"
    ),
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0286 (the re-weighting cadence 2x2: equal slices beat market value by 2.8 points a "
        "year over identical names, 4.6 in 2009-2015, and the equal arms lose 8-9% a year in "
        "narrow months); M0281/M0224/M0226, which built the whole-market base; M0222 (the "
        "market-value core and the per-company ceiling); M0266 (the price of a point of "
        "exposure is an era, not a constant); insight 91 (the lab's old reading that favouring "
        "the smaller members is a handicap); insight 462 (the equal-weight placebo's 8-point "
        "gap decomposed to 3.6 gate, 3.8 fees, under 0.9 pool and weighting); insight 500 (a "
        "two-point slope read is wrong: turn the dial five times)"
    ),
    parent_id="M0286",
    hypothesis=(
        "M0286 measured, on identical names at Gotrade's real fees on the owner's deposits, "
        "that equal slices beat market-value weights by 2.8 points a year over 1996-2015 and by "
        "4.6 points in 2009-2015, and that the lead survives the survivorship-check store. That "
        "contradicts the lab's year-old assumption and goes further than insight 462, which "
        "priced the weighting itself at under 0.9 points once the gate and the fees were taken "
        "out. But a two-point read cannot rank a dial, and M0286's own check named two terms "
        "riding along with the 2.8: a 5.7-point exposure gap between the two shapes, and a "
        "breadth split in which the equal arms earn +13% a year in broad months and lose 8-9% "
        "in narrow ones -- and 2018-2026 was narrow. So the switch becomes a dial, turned five "
        "times over identical names with one field moving: each name's weight is its market "
        "value raised to a power, rescaled and capped at 5%. EQUAL (power 0) gives every name "
        "the same weight; P25, P50 and P75 are the rungs; SIZE (power 1) is the market's own "
        "shape. All five run M0286's EQ-DEPOSIT cadence -- a January anchor, never a sale to "
        "fund a buy, the month's deposit handed to the names furthest below target -- because "
        "M0286 found that is the cheapest shape and the one that holds exposure nearly still "
        "across shapes, so the ladder moves weighting and not time in cash. EQUAL should "
        "reproduce M0286-EQ-DEPOSIT, a built-in check that the power code leaves the equal end "
        "alone. The sixth arm, SIZE-NOCAP, is not a rung: it is power 1 with the 5% ceiling "
        "lifted, the one arm that prices the cap at the rung where it binds hardest, so any "
        "curvature in the return curve can be attributed to the weighting rather than to the "
        "cap re-spreading the excess. Predictions, written before any result: the funded return "
        "curve is monotone and rises toward EQUAL; the narrow-month annualised spread is "
        "monotone the other way and crosses zero between P50 and P75; the worst fall rises "
        "monotonically toward EQUAL; exposure is flat to within a point across the five rungs; "
        "and SIZE-NOCAP lands within about half a point a year of SIZE, because the dev "
        "window's biggest member rarely reaches 5% of the index. Nothing here is a candidate: "
        "every rung should fall roughly 50-58% in 2008, twice the bar, and a weighting dial "
        "does not touch that. Success is a measurement -- whether the dial is a curve with an "
        "interior best rung, or a step function between the two ends M0286 already has."
    ),
    expected_failure=(
        "The rungs may not separate. Market value is distributed so unevenly across index "
        "members that raising it to 0.25 may already be most of the way to equal weighting, in "
        "which case EQUAL, P25 and P50 land on top of each other, the dial is a step function "
        "near the size end, and five rungs bought what two already said. The cap is the second "
        "trap and the reason SIZE-NOCAP is registered: market value raised to a power is not a "
        "clean size tilt once the 5% ceiling re-spreads the excess, and the ceiling binds "
        "hardest at power 1, so part of any curvature belongs to the cap; if SIZE and SIZE-NOCAP "
        "differ by more than the gap between two neighbouring rungs, the ladder is measuring "
        "the cap and the verdict must say so. Third, the narrow-and-broad split is computed on "
        "the dev window's own months, 2009-2015 contained no bear market and few genuinely "
        "narrow stretches, and the column may rest on too few months to rank six arms by -- a "
        "monotone-looking narrow-month curve could be noise with a slope. Fourth, the dev store "
        "cannot price about 40% of member-days and the missing names skew small, so every rung "
        "nearer the equal end is flattered here; the survivorship-check store must be read for "
        "ALL six arms, not only the ends, and if the ladder's slope flattens there then the "
        "slope was partly the coverage hole. Fifth, the deposit cadence spends each month's "
        "money on the names furthest below target, which is a size-dependent habit in itself: "
        "at the size end the under-weight names are the big ones and at the equal end they are "
        "the small ones, so the cadence is not perfectly neutral across the dial, and an "
        "exposure column that moves across rungs is the symptom. Finally the whole exercise is "
        "about a book that falls 50-58% in 2008 and can never be a candidate, so a monotone "
        "answer changes what the lab believes about weighting and still promotes nothing."
    ),
    candidates=(
        _v("EQUAL", PowerParams(power=Decimal("0")),
           "Power 0: every screened member gets the identical weight -- the lab's usual shape, "
           "and a reproduction check against M0286-EQ-DEPOSIT"),
        _v("P25", PowerParams(power=Decimal("0.25")),
           "Power 0.25: a quarter of the way from equal slices toward the market's own shape"),
        _v("P50", PowerParams(power=Decimal("0.5")),
           "Power 0.5: the square root of market value, the halfway rung"),
        _v("P75", PowerParams(power=Decimal("0.75")),
           "Power 0.75: three quarters of the way toward the market's own shape"),
        _v("SIZE", PowerParams(power=Decimal("1")),
           "Power 1: each name at its market value, capped at 5% -- the market's own shape"),
        _v("SIZE-NOCAP", PowerParams(power=Decimal("1"), ceiling=NO_CEIL),
           "The same market-value shape with the 5% ceiling lifted: the one arm that prices the "
           "cap, at the rung where it binds hardest"),
    ),
    seen_keys=(
        "concept:market-cap-weight",
        "concept:equal-weight-vs-cap-weight",
        "concept:size-weighting-power-dial",
        "concept:whole-market-core",
        "concept:weight-ceiling",
        "concept:deposit-steered-rebalance",
        "concept:dose-response-ladder",
    ),
)
