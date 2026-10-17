"""M0171 — The slowest-to-react companies with a gentle brake: the book scaled by its own volatility.

Source: variation of M0169 (Hou & Moskowitz 2005, price delay), with M0001's own-volatility
overlay (Barroso & Santa-Clara 2015) in place of the SPY 200-day switch.
Idea: M0169's twenty most delayed index members led SPY by 7.3 points a year in 2009-2015 with no
switch, but fell 64% through 2008. Behind the 200-day switch the fall shrank to 33% and the
2009-2015 lead to +0.6, because the switch stepped out in the 2010 and 2011 scares and missed the
rebounds. An on-off switch is all or nothing; a volatility dial trims the book in proportion to how
hard it is swinging, so a short scare costs a slice of exposure instead of the whole rebound, while
a long, violent fall like 2008 still drives the book mostly to cash.

Mechanics. The inner book is M0169's allocator verbatim (same December delay ranking, keep band,
member exits into SPY, no switch). On each monthly decision the inner targets, SPY filler included,
form a basket at their weights; its annualized volatility over the last ``n`` daily returns of
each holding through ``data_date`` is M0001's ``basket_scale``. Every stock weight is multiplied by
min(1, target_vol / vol). With ``rest="cash"`` the SPY filler is scaled too and the freed weight is
cash; with ``rest="spy"`` only the stocks are scaled and SPY takes up everything they give back
(the dial then moves money between the slow reactors and the market, never out of it). No
leverage: a calm book is never scaled above its full weight.

Why monthly, not weekly: the parent's frame is ``monthly-hold-frac-gotrade``, and keeping the tape
fixed means the brake is the only change. The cost is that the dial is re-read only once a month,
which is the expected failure below; the 20-day variant shortens the window instead of the cadence.

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
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import basket_scale
from seer_engine.lab.methods.m0169_price_delay import DELAY, DelayParams, DelayPrepared
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 10, 17)


@dataclass(frozen=True, slots=True)
class DelayVolParams:
    """``inner`` is M0169's params (no switch); ``target_vol`` the annual volatility the book is
    held to; ``n`` the daily returns in the estimate; ``rest`` where the trimmed weight goes."""

    inner: DelayParams
    target_vol: Decimal = Decimal("0.12")
    n: int = 60
    rest: str = "cash"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, DelayParams):
            raise TypeError(f"inner must be DelayParams, got {type(self.inner).__name__}")
        if self.inner.inner.trend is not None:
            raise ValueError("the dial replaces the 200-day switch: inner must have no trend")
        if not isinstance(self.target_vol, Decimal) or not self.target_vol.is_finite() or self.target_vol <= 0:
            raise ValueError(f"target_vol must be a positive Decimal, got {self.target_vol!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 2:
            raise ValueError(f"n must be an int >= 2, got {self.n!r}")
        if self.rest not in ("cash", "spy"):
            raise ValueError(f"rest must be 'cash' or 'spy', got {self.rest!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"target_vol": str(self.target_vol), "n": str(self.n), "rest": self.rest}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> DelayVolParams:
    if not isinstance(params, DelayVolParams):
        raise TypeError(f"params must be DelayVolParams, got {type(params).__name__}")
    return params


def dialed(history: Mapping[str, History], inner: tuple[Target, ...], data_date: date,
           p: DelayVolParams) -> tuple[Target, ...]:
    """The inner targets with the stock weights (and, for cash, SPY's) scaled by the dial."""
    scale = basket_scale(history, inner, data_date, p.n, p.target_vol)
    if scale is None:
        return inner
    market = p.inner.market
    out: list[Target] = []
    given = Decimal(0)
    spy = Decimal(0)
    for t in inner:
        if t.symbol == market and p.rest == "spy":
            spy += t.weight
            continue
        w = scale_weight(t.weight, scale)
        if t.symbol != market:
            given += t.weight - (w or Decimal(0))
        if w is not None:
            out.append(replace(t, weight=w))
    if p.rest == "spy":
        total = spy + given
        mh = history.get(market)
        if total > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(market, last_close(mh, data_date), total)
            if t is not None:
                out.append(t)
    return tuple(out)


class DelayVolAllocator:
    """M0169's delay book, held to a volatility target by its own recent swings."""

    id = "M0171"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DELAY.lookback(p.inner), p.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return DELAY.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return DELAY.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return DELAY.uses_members(_check(params).inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = DELAY.targets(history, members, data_date, held, p.inner)
        return dialed(history, inner, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> DelayPrepared:
        return DELAY.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DelayPrepared):
            raise TypeError(f"prepared must be DelayPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = DELAY.targets_prepared(prepared, members, data_date, held, p.inner)
        return dialed(prepared.history, inner, data_date, p)


DELAYVOL = DelayVolAllocator()


def _book(top: int, keep: int, least: bool = False) -> DelayParams:
    # the rank is unused: only F4's screen; no trend, the dial is the brake
    return DelayParams(FactorParams(rank="momentum", top=top, trend=None), keep=keep, least=least)


def _v(suffix: str, params: DelayVolParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0171-{suffix}", family="M0171", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DELAYVOL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


TV12 = Decimal("0.12")
TV16 = Decimal("0.16")

METHOD = Method(
    id="M0171",
    name=(
        "The slowest-to-react companies with a gentle brake: scale the book toward SPY as its own "
        "swings grow, instead of the on-off 200-day switch"
    ),
    family="stock-price-delay",
    source_kind="variation",
    source_ref=(
        "M0169 (Hou & Moskowitz 2005, price delay) + M0001's own-volatility overlay "
        "(Barroso & Santa-Clara 2015, Momentum has its moments, JFE 116(1))"
    ),
    parent_id="M0169",
    hypothesis=(
        "M0169's twenty slowest reactors led SPY by 7.3 points a year in 2009-2015 with no switch "
        "(5.6 on the survivorship-check prices) but fell 64% in 2008; behind the 200-day switch "
        "the fall shrank to 33% and the 2009-2015 lead to +0.6 (-1.8 on the check prices), "
        "because the switch whipsawed out in 2010 and 2011. Keep M0169's December delay ranking, "
        "keep band and member exits exactly, drop the switch, and each month scale every stock "
        "weight by min(1, target / the book's own annualized volatility over the last 60 daily "
        "returns) (M0001's overlay; the price-delay paper is 2005 and the volatility-scaling "
        "paper 2015, so neither was crowded for most of the dev window). Variants: D20-TV12 (the "
        "idea: 12% target, trimmed weight in cash), D20-TV16 (a looser 16% target), D20-TV12-N20 "
        "(a 20-day window, quicker to react), D20-TV12-SPY (trimmed weight parked in SPY "
        "instead of cash), D40-TV12 (a 40-name rung kept inside the top 80), L20-TV12 (control: "
        "the 20 fastest reactors under the same dial). Fractional shares at Gotrade's real fees "
        "on the owner's deposits, monthly. Success: D20-TV12 beats total-return SPY with worst "
        "fall <= 25%, PF >= 1.3, a positive 2009-2015 lead, a majority of walk-forward folds, "
        "and L20-TV12 trails it."
    ),
    expected_failure=(
        "A volatility dial reacts too late to a 2008-style fall: read once a month on 60 days of "
        "history, it was still near full weight in September 2008 and the book still falls more "
        "than 25%. A 12% target on a book that normally swings 18-20% also holds it two-thirds "
        "invested in calm years, which costs the 2009-2015 lead it was meant to keep. Parking "
        "the trimmed weight in SPY keeps the lead but brings back SPY's own 2008 fall, so that "
        "variant should fall about as far as SPY did (over 50%). The slowest reactors are the "
        "smaller, quieter index members, so the book still leans against SPY's big-company "
        "drift after 2009 (insight 91), and the dev store's missing dead companies flatter it."
    ),
    candidates=(
        _v("D20-TV12", DelayVolParams(_book(20, 40), TV12),
           "The 20 most delayed, kept inside the top 40, held to 12% own volatility over 60 days; the rest cash"),
        _v("D20-TV16", DelayVolParams(_book(20, 40), TV16),
           "The same book held to a looser 16% target"),
        _v("D20-TV12-N20", DelayVolParams(_book(20, 40), TV12, n=20),
           "The same 12% target read on 20 days of returns: quicker to cut, quicker to come back"),
        _v("D20-TV12-SPY", DelayVolParams(_book(20, 40), TV12, rest="spy"),
           "The same 12% dial, but the trimmed weight is parked in SPY instead of cash"),
        _v("D40-TV12", DelayVolParams(_book(40, 80), TV12),
           "A 40-name rung, kept inside the top 80, held to 12% own volatility; the rest cash"),
        _v("L20-TV12", DelayVolParams(_book(20, 40, least=True), TV12),
           "Control: the 20 least delayed (the quickest to react) under the same 12% dial"),
    ),
    seen_keys=(
        "concept:price-delay-own-vol",
        "concept:price-delay",
        "concept:own-vol-dial-vs-trend-switch",
    ),
)
