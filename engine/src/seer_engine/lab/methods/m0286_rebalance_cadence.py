"""M0286 — How often must a book be re-weighted? The same names in the market's own shape and in
the lab's equal slices, each re-set every month and once a year.

Source: variation of M0281 (the rate-trend lean, whose CORE arm is the whole-market base) and
through it M0224/M0226, which built that base; M0266 (rebalancing is worth nothing on a 50-name
equal-weight book once exposure is matched); insight 462 (the equal-weight placebo's 8-point gap
decomposed: 3.6 gate, 3.8 fees on 15 turns a year, under 0.9 pool and weighting). Reserved by
Sera 20261023-0843 as M0286.

Why this shape. The whole-market base -- every F4-screened index member with a known
point-in-time market value, one listed class per identical share count, weighted by that value,
no company over 5%, fractional shares at Gotrade's real fees on the owner's deposits -- is the
yardstick every lean the lab has tried sits on top of, and it beats deposit-matched SPY by only
0.2 points a year (+7.4% against +7.2%). The dial never turned on it is how often it is
re-weighted. Turnover is the dial the lab has already priced as expensive, and M0266 found that
the trimming itself -- buying the faller, selling the riser -- is worth nothing once the cash it
releases is held still.

But a book weighted by company size barely needs re-weighting at all, and that is arithmetic
rather than a result: a company's market value IS its share count times its price, so a
size-weighted book's weights drift exactly the way its targets drift. Only share issuance,
index entries and exits and the 5% ceiling can separate them. So this method turns the cadence
dial on TWO shapes at once and the comparison is a 2x2. ``weighting="value"`` is the market's
own shape; ``weighting="equal"`` is one equal slice per name over the identical names -- the
shape every other book in this lab holds, and the one that must be traded back to its targets
because nothing holds it there. The cadence dial should be near-inert on the first and
expensive on the second, and the size of that second number is the point.

The ladder. ``months`` is how often the weights are re-set: 1 (every month) or 12 (each
January). An anchor month is one whose number divides by ``months``. On a non-anchor decision
date the book is **not** re-computed: it is the anchor's book carried forward by each name's own
price change since the anchor, which is exactly what an untouched book's weights do. The
engine's rebalance band is measured against each holding's own target (20%), so targets that
equal the drifted weights produce no trade. Between anchors the only sells are a name that has
left the index (dropped from the targets) and a name that has drifted above the 5% ceiling
(pinned back to it) -- the two sells a buy-and-hold index book cannot avoid.

``deposit`` never re-weights by selling at all. Between anchors each name's target is the larger
of its drifted weight and the weight its shape wants, re-capped: nothing is ever sold to fund a
purchase, and the targets are handed over most under-weight first, so the month's deposit is
spent closing the widest gaps. It runs on the equal-weight side, where it has something to do,
and it is the cheapest honest way to keep an equal-slice book near equal: EQ-ANNUAL and
EQ-DEPOSIT share an anchor and differ only in whether the month's money steers.

The endpoint with no opinion in it is SPY: the owner's deposits buying total-return SPY and
nothing else, at the same Gotrade fees, with the band at zero so each month's money is invested
the day it lands. It is what all five book arms are an attempt to improve on, priced with the
fees the lab's benchmark line does not charge.

Assumption written down because it was a judgement, not a given: the reserved row asked for a
deposit-steered arm with no anchor at all, and for a quarterly rung. A book that has never been
re-weighted has path-dependent weights, and an allocator cannot read its own weights (it is
handed a set of symbols, not a book), so that rule is not computable here without replaying
every month since 1996 at every decision; the yearly anchor is the nearest computable rule. The
quarterly rung was dropped for the second shape, because a middle rung of a dial that is inert
by construction buys less than a whole second shape does.

Lookback. A non-anchor date reads the core at its anchor, so the history must reach the screen's
year back from THERE: ``shadow_lookback_for(253, depth)`` with ``depth`` the number of monthly
steps, capped at the 8 the 473-bar smoke fixture can afford. The yearly arm can need 12, which no
fixture can hold; on the dev window it never binds (the store's bars begin in 1993 and the run
begins in 1996), and where the anchor book cannot be read the arm falls back to re-weighting on
the spot, which is what a book with no anchor yet must do.

Market-aware: reads ``shares`` (company size); without it, or without the market's membership
calendar, it targets nothing. Pure: reads only bars, share counts and index membership dated
<= d.
"""

from __future__ import annotations

import calendar
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
from seer_engine.lab.methods.m0127_slot_relative_resize_band import T00
from seer_engine.lab.methods.m0222_raise_tilted_market_core import capped, core
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
MODES = ("book", "spy")
WEIGHTINGS = ("value", "equal")
EVERY = 1000  # past any day's member count: the base is every member with a known size
CEIL = Decimal("0.05")
_W_Q = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class CadenceParams:
    """``months`` is how often the weights are re-set (1 or 12 here); ``weighting`` is what they
    are re-set TO -- each company's market value, or one equal slice each; ``deposit`` lets the
    month's money steer toward them between re-sets instead of nothing happening; ``mode="spy"``
    is the endpoint arm that holds total-return SPY and nothing else."""

    inner: FactorParams = NOT20
    top: int = EVERY
    ceiling: Decimal = CEIL
    months: int = 1
    deposit: bool = False
    weighting: str = "value"
    mode: str = "book"
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
        if not isinstance(self.ceiling, Decimal) or not (Decimal(0) < self.ceiling <= Decimal(1)):
            raise ValueError(f"ceiling must be a Decimal in (0, 1], got {self.ceiling!r}")
        if self.ceiling * self.top < 1:
            raise ValueError("ceiling x top must reach 1, or the weights cannot sum to 1")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "ceiling": str(self.ceiling), "months": str(self.months),
               "deposit": str(self.deposit), "weighting": self.weighting,
               "mode": self.mode, "market": self.market,
               "size": "market-value-one-class", "carry": "price-drift-since-anchor",
               "anchor": "month-number-divides-months"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CadenceParams:
    if not isinstance(params, CadenceParams):
        raise TypeError(f"params must be CadenceParams, got {type(params).__name__}")
    return params


@dataclass
class CadencePrepared:
    """The three attributes M0222's ``core`` reads: bars, the screen's rolling rows, the market."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    market: Any = field(repr=False, default=None)


def anchor_month(data_date: date, months: int) -> tuple[int, int]:
    """The (year, month) of the latest re-weight on or before ``data_date``.

    A month is an anchor when its number divides ``months``: quarterly re-sets are decided on the
    last session of March, June, September and December (opening April, July, October, January),
    the yearly one on the last session of December.
    """
    m = data_date.month - (data_date.month % months)
    return (data_date.year - 1, 12) if m == 0 else (data_date.year, m)


def anchor_session(prepared: CadencePrepared, data_date: date, p: CadenceParams) -> date | None:
    """The session the anchor's weights were set on, or None when it is not before ``data_date``."""
    if p.months == 1:
        return None
    year, month = anchor_month(data_date, p.months)
    if (year, month) == (data_date.year, data_date.month):
        return None  # this decision IS the anchor: re-weight from scratch
    end = date(year, month, calendar.monthrange(year, month)[1])
    h = prepared.history.get(p.market)
    if h is None:
        return None
    a = h.upto(end).last_date()
    return a if a is not None and a < data_date else None


def target_weights(prepared: CadencePrepared, members: AbstractSet[str], data_date: date,
                   p: CadenceParams) -> dict[str, tuple[float, float]]:
    """symbol -> (close on or before ``data_date``, the weight this shape wants it at).

    Market value under the 5% ceiling, or one equal slice each over the same names.
    """
    book = core(prepared, members, data_date, p)  # type: ignore[arg-type]
    if len(book) < 2:
        return {}
    raw = {s: (1.0 if p.weighting == "equal" else v) for s, _, v in book}
    w = capped(raw, float(p.ceiling))
    return {s: (c, w[s]) for s, c, _ in book}


def carried(prepared: CadencePrepared, members: AbstractSet[str], data_date: date, anchor: date,
            p: CadenceParams) -> dict[str, tuple[float, float]]:
    """The anchor's book carried to ``data_date`` by each name's own price change.

    A name that has left the index since the anchor is dropped (the one sell a held index book
    cannot avoid); a name with no readable price is dropped too. Weights are left un-normalised:
    the caller re-caps them, which rescales to 1 exactly as the real book's weights rescale.
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


def choose(prepared: CadencePrepared, members: AbstractSet[str], data_date: date,
           p: CadenceParams) -> tuple[Target, ...]:
    """The book this cadence wants held after the next open."""
    anchor = anchor_session(prepared, data_date, p)
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


class RebalanceCadenceAllocator:
    """The whole-market base re-weighted every ``months`` months, optionally with the month's
    deposit steering in between; or the SPY endpoint. No market panel: no targets."""

    id = "M0286"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        inner = factor_lookback(p.inner)
        if p.mode == "spy" or p.months == 1:
            return inner
        return shadow_lookback_for(inner, min(p.months, max_shadow_depth(inner)))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.mode == "spy" else ()

    def uses_members(self, params: Any) -> bool:
        return _check(params).mode == "book"

    def _spy(self, prepared: CadencePrepared, data_date: date,
             p: CadenceParams) -> tuple[Target, ...]:
        c = last_close(prepared.history.get(p.market), data_date)
        if c is None:
            return ()
        t = target_from_close(p.market, c, Decimal(1))
        return () if t is None else (t,)

    def _run(self, prepared: CadencePrepared, members: AbstractSet[str], data_date: date,
             p: CadenceParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(m.shares) == 0:
            return ()  # no panel: target nothing (market-aware contract), SPY arm included
        if p.mode == "spy":
            return self._spy(prepared, data_date, p)
        return choose(prepared, members, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts and no membership calendar, so no book.

        The SPY arm reads neither, but a market-aware allocator must target nothing without its
        panel (the lab's allocator contract), so it waits for the panel like every other arm.
        """
        return self._run(CadencePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CadencePrepared:
        return CadencePrepared(history, prepare_factor(history))

    def prepare_market(self, market: Any) -> CadencePrepared:
        return CadencePrepared(market.history, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CadencePrepared):
            raise TypeError(f"prepared must be CadencePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CADENCE = RebalanceCadenceAllocator()


def _v(suffix: str, params: CadenceParams, rationale: str, rules: Any = None) -> Candidate:
    return Candidate(id=f"M0286-{suffix}", family="M0286",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND if rules is None else rules,
                     allocator=CADENCE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0286",
    name=(
        "How often must a book be re-weighted? The market's own shape and the lab's equal "
        "slices, each re-set every month and once a year"
    ),
    family="portfolio-rebalancing",
    source_kind="variation",
    source_ref=(
        "M0281's CORE arm and M0224/M0226, which built the whole-market base; M0266 (with "
        "exposure held still, trimming winners to feed laggards is worth nothing on a 50-name "
        "equal-weight book); M0127 (the rebalance band measured against the holding); insight "
        "462 (fees on 15 turns a year were 3.8 of the equal-weight placebo's 8-point gap); "
        "insight 492 (cash in lumps costs more than cash spread evenly)"
    ),
    parent_id="M0281",
    hypothesis=(
        "The whole-market base -- every F4-screened index member with a known point-in-time "
        "market value, one listed class per identical share count, no company over 5%, "
        "monthly, fractional, Gotrade's real fees, the band measured against each holding's own "
        "target -- beats deposit-matched SPY by 0.2 points a year (+7.4% vs +7.2%). The dial "
        "never turned on it is how often it is re-weighted, and M0266 found that with exposure "
        "held still the trimming itself is worth nothing. A size-weighted book, though, barely "
        "needs re-weighting by arithmetic: market value is share count times price, so its "
        "weights drift the way its targets drift, and only issuance, index changes and the "
        "ceiling separate them. So the dial is turned on two shapes at once, a 2x2 of shape and "
        "cadence over identical names, with one field between each pair. MONTHLY and ANNUAL "
        "weight by market value and re-set every month or each January; EQ-MONTHLY and "
        "EQ-ANNUAL give the same names one equal slice each on the same two cadences; "
        "EQ-DEPOSIT shares EQ-ANNUAL's January anchor but never sells to fund a buy, spending "
        "each month's deposit on the names furthest below an equal slice; SPY is the endpoint "
        "with no opinion in it, the same deposits buying total-return SPY at the same fees with "
        "the band at zero. On a non-anchor month a book is its anchor's weights carried forward "
        "by each name's own price change, so nothing trades but an index exit and a name over "
        "the 5% ceiling. MONTHLY should reproduce M0281-CORE's +7.4%, a built-in check that the "
        "carry code leaves the base alone. Predictions, written before any result: ANNUAL lands "
        "within about 0.3 points a year of MONTHLY, because the shape rebalances itself; "
        "EQ-ANNUAL beats EQ-MONTHLY by a point or more, because the equal shape does not; and "
        "EQ-DEPOSIT beats EQ-ANNUAL, because the deposit buys the laggards for free. Nothing "
        "here is a candidate: the base falls about 50% in 2008, twice the 25% bar, and no "
        "cadence touches that. Success is a measurement -- what the lab's habitual equal-slice "
        "shape pays to be held in place, on a book where the market's own shape pays nothing."
    ),
    expected_failure=(
        "Three ways this answers nothing. (1) The 20% target band on a book of several hundred "
        "sub-1% weights may already suppress nearly every drift trade, in which case all four "
        "book arms land on top of each other and the finding is about the band, not the "
        "cadence; turnover, order count and average exposure must be quoted beside return "
        "either way. (2) The equal arms slice a 20-million-rupiah account about 240 ways, so a "
        "slot starts near six dollars and a 20%-of-target drift trade is a one-dollar order. "
        "Gotrade's per-order minimum then swallows it, or the engine refuses it as too small, "
        "and the equal cadence gap becomes a measurement of a small account's order economics "
        "rather than of rebalancing. That is still a real answer for the owner, but the verdict "
        "must say which it is. (3) A slower cadence leaves the month's deposit in cash for up to "
        "eleven months, and cash in lumps costs more per point of absent exposure than cash "
        "spread evenly (insight 492), so an annual arm may lose on exposure what it saves on "
        "fees; EQ-DEPOSIT exists precisely to separate those two. Beyond that: the base's small "
        "lead over SPY is the missing dead companies and the coverage hole, not fees, so no "
        "cadence closes it; rebalancing buys the faller and the dev store prices no delisted "
        "names, so the often-re-weighted arms are structurally flattered here and the check "
        "store should move them down relative to the annual ones; and the carry rule is price "
        "drift only -- dividends are credited to cash and redeployed by the band like any other "
        "money -- so a carried weight is a few tenths of a percent off a truly untouched "
        "book's, far inside the 20% band but not zero."
    ),
    candidates=(
        _v("MONTHLY", CadenceParams(),
           "The recorded base: every member with a known size at market value, 5% ceiling, "
           "re-weighted every month"),
        _v("ANNUAL", CadenceParams(months=12),
           "The same market-value base re-weighted each January only"),
        _v("EQ-MONTHLY", CadenceParams(weighting="equal"),
           "The same names in equal slices, re-weighted every month: the lab's usual shape"),
        _v("EQ-ANNUAL", CadenceParams(months=12, weighting="equal"),
           "The same equal slices re-weighted each January only"),
        _v("EQ-DEPOSIT", CadenceParams(months=12, weighting="equal", deposit=True),
           "Equal slices that are never sold to fund a buy: each month's deposit goes to the "
           "names furthest below a slice, with a January re-weight as the backstop"),
        _v("SPY", CadenceParams(mode="spy"),
           "The endpoint with no opinion in it: the deposits buying total-return SPY at the "
           "same fees, invested the month they land", T00),
    ),
    seen_keys=(
        "concept:rebalance-cadence",
        "concept:whole-market-core",
        "concept:market-cap-weight",
        "concept:deposit-steered-rebalance",
        "concept:equal-weight-vs-cap-weight",
        "concept:buy-and-hold-index-book",
        "concept:turnover-cost",
    ),
)
