"""M0080 — Buy the recovered cutters: big companies six months after a dividend cut, once their price is back above its 200-day average.

Source: variation of M0077 (the dividend-cut alarm). Michaely, Thaler & Womack (1995), "Price
reactions to dividend initiations and omissions: overreaction or drift?", Journal of Finance
50(2) (NBER w4778, 1994) report the drift after an omission runs about a year; Bernard & Thomas
(1989) and the long-term reversal literature (De Bondt & Thaler 1985) say a punished name later
rebounds once the bad news is fully in the price.
Idea: M0077 benched a cutter for six months and it cost the news-day book about a point a year in
2009-2015, because the big members that cut in 2008-09 (banks, industrials) recovered strongly
afterwards. This is the mirror image: hold the cutters once the six-month drift the papers report
is over and the market has started to agree that the worst is behind them (price back above its
own 200-day average). It ranks on a board's decision plus the stock's own trend, not on past
returns against other stocks, so its picks should not move with the failed momentum books.

The frame is M0070's -- point-in-time S&P 500 / Nasdaq-100 members, F4's $5 price and $20M daily
dollar-volume screen, optionally the SPY 200-day trend switch, monthly, fractional shares at
Gotrade's real fees on ``monthly-hold-frac-gotrade``, the empty slots parked in SPY. The event is
M0077's alarm, reused verbatim (``alarms``/``payments``): a *cut* (a payment at most 75% of the
median of the up-to-four previous ones in the prior 400 days) or an *omission* (a regular payer
silent for 1.5 of its usual gaps after its last ex-date), each firing on the day it was knowable,
on the declaration day for ``timing="announce"`` (the ex-date where the store has none) and on the
ex-date for ``timing="ex"`` (the paired control).

A member qualifies on data date d when the *latest* alarm a <= d of the stock satisfies
``min_age`` <= d - a < ``max_age`` calendar days (so a second cut inside the waiting period resets
the clock), it passes F4's screen, and -- when ``sma_n`` > 0 -- its close on d is strictly above
the mean of its last ``sma_n`` closes through d. Qualifying names are ranked held first (a name
keeps its slot while it still qualifies), then the newest alarm, then the symbol; the
``inner.top`` first are held at equal weight 1/top and the weight the empty slots leave goes to
SPY. Behind the trend switch (``inner.trend`` set) the book is all cash while SPY is below its
200-day average.

Without the market's calendar (the history-only ``prepare``/``targets`` path, or an empty
calendar) nothing is targeted, which is the market-aware allocator contract.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0077_dividend_cut_overlay import alarms, payments
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 11)

Timing = Literal["announce", "ex"]
_TIMINGS: tuple[str, ...] = ("announce", "ex")


@dataclass(frozen=True, slots=True)
class RecoveryParams:
    """``inner`` is F4's screen, trend switch and book size; the rest defines the event and the filter."""

    inner: FactorParams
    timing: Timing = "announce"
    cut_ratio: Decimal = Decimal("0.75")
    omit_mult: Decimal = Decimal("1.5")
    min_age: int = 182
    max_age: int = 548
    sma_n: int = 200
    park: bool = True
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.timing, str) or self.timing not in _TIMINGS:
            raise ValueError(f"timing must be one of {_TIMINGS}, got {self.timing!r}")
        if not isinstance(self.cut_ratio, Decimal) or not self.cut_ratio.is_finite() or not 0 < self.cut_ratio < 1:
            raise ValueError(f"cut_ratio must be a Decimal in (0, 1), got {self.cut_ratio!r}")
        if not isinstance(self.omit_mult, Decimal) or not self.omit_mult.is_finite() or self.omit_mult <= 1:
            raise ValueError(f"omit_mult must be a Decimal > 1, got {self.omit_mult!r}")
        for name in ("min_age", "max_age", "sma_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be an int >= 0, got {v!r}")
        if self.max_age <= self.min_age:
            raise ValueError("max_age must be above min_age")
        if self.sma_n == 1:
            raise ValueError("sma_n must be 0 (off) or >= 2")
        if not isinstance(self.park, bool):
            raise TypeError(f"park must be a bool, got {type(self.park).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "timing": self.timing,
            "cut_ratio": str(self.cut_ratio),
            "omit_mult": str(self.omit_mult),
            "min_age": str(self.min_age),
            "max_age": str(self.max_age),
            "sma_n": str(self.sma_n),
            "park": str(self.park).lower(),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> RecoveryParams:
    if not isinstance(params, RecoveryParams):
        raise TypeError(f"params must be RecoveryParams, got {type(params).__name__}")
    return params


def above_sma(h: History | None, data_date: date, n: int) -> bool:
    """True when ``n`` is 0, else close on ``data_date`` > mean of the last ``n`` closes through it (strict)."""
    if n == 0:
        return True
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    window = h.close[i + 1 - n : i + 1]
    return bool(float(window[-1]) > float(window.mean()))


@dataclass
class RecoveryPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)
    _alarms: dict[tuple[str, str, Decimal, Decimal], list[date]] = field(default_factory=dict, repr=False)

    def latest_alarm(self, symbol: str, data_date: date, p: RecoveryParams) -> date | None:
        """The newest alarm day <= ``data_date`` for ``symbol``, or None."""
        key = (symbol, p.timing, p.cut_ratio, p.omit_mult)
        fired = self._alarms.get(key)
        if fired is None:
            fired = alarms(payments(self.calendar, symbol, p.timing), p.cut_ratio, p.omit_mult)
            self._alarms[key] = fired
        j = bisect_right(fired, data_date)
        return fired[j - 1] if j > 0 else None


def choose(prepared: RecoveryPrepared, rows: list[FactorRow], data_date: date,
           held: frozenset[str], p: RecoveryParams) -> tuple[Target, ...]:
    history = prepared.history
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        a = prepared.latest_alarm(r.symbol, data_date, p)
        if a is None or not p.min_age <= (data_date - a).days < p.max_age:
            continue
        if not above_sma(history.get(r.symbol), data_date, p.sma_n):
            continue
        live.append((0 if r.symbol in held else 1, -a.toordinal(), r.symbol, r))
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for _, _, _, r in live[: p.inner.top]:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    if p.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(p.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(p.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class CutRecoveryAllocator:
    """Members 6-18 months past a dividend cut or omission whose price is back above its 200-day average; rest SPY."""

    id = "M0080"
    market_fields = ("dividends",)  # reads Market.dividends, never Market.fundamentals

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.sma_n)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: RecoveryPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: RecoveryParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no calendar: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
        return self._run(RecoveryPrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RecoveryPrepared:
        return RecoveryPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> RecoveryPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return RecoveryPrepared(market.history, prepare_factor(market.history), calendar)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RecoveryPrepared):
            raise TypeError(f"prepared must be RecoveryPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


RECOVERY = CutRecoveryAllocator()

T20 = replace(N20, rank="lowvol")  # F4's screen and SPY-200 switch; the rank field is unused here
NOT20 = replace(N20_NOTREND, rank="lowvol")


def _v(suffix: str, params: RecoveryParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0080-{suffix}", family="M0080", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RECOVERY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0080",
    name="Buy the recovered cutters: big companies six months after a dividend cut, once their price is back above its 200-day average",
    family="stock-dividend-cut-recovery",
    source_kind="variation",
    source_ref="M0077; Michaely, Thaler & Womack (1995), JF 50(2), https://www.nber.org/papers/w4778",
    parent_id="M0077",
    hypothesis=(
        "The omission drift was published in 1994-1995, and the 'buy the punished name once it "
        "turns' idea is older still (De Bondt & Thaler 1985), so the dev window is after the crowd "
        "could know both; this is a variation built from a lab result, not a published rule. "
        "M0077's cut alarm cost the news-day book about a point a year in 2009-2015 because the "
        "big members that cut in 2008-09 later recovered strongly. Test the mirror image: index "
        "members whose latest dividend cut or omission alarm (M0077's alarm reused verbatim: a "
        "payment at most 75% of the median of the up-to-four previous ones, or a regular payer "
        "silent for 1.5 usual gaps) fired 182 to 547 days ago, so the papers' six-month drift is "
        "over and no newer cut has come, and whose close is now above its own 200-day average, so "
        "the market has started to agree the worst is behind them. Inside F4's liquidity and "
        "membership screen, hold up to 20 such names at 5% each (held names keep their slot while "
        "they still qualify, then the newest alarm), park the rest in SPY, behind the SPY 200-day "
        "switch, re-picked monthly, fractional at Gotrade's real fees on monthly-hold-frac-gotrade. "
        "Variants: ANN-S200-T (alarm on the declaration day), EX-S200-T (the paired control: the "
        "same rule timed on the ex-date), ANN-ALL-T (no 200-day filter: every cutter in the "
        "window, which isolates whether waiting for the price to turn adds anything) and ANN-S200 "
        "(no SPY switch, always invested: the picking alone). Success: a variant beats "
        "total-return SPY on dev within the 20% worst fall with a positive edge over SPY in "
        "2009-2015, ANN-S200-T beats ANN-ALL-T, and the walk-forward folds are won in a majority. "
        "Assumed, not tested: newest alarm first when more than 20 qualify, because the drift and "
        "reversal papers both put the strongest rebound early; the six-to-eighteen-month window "
        "was set from the papers' horizons before any run."
    ),
    expected_failure=(
        "About 30 cuts a year among big members leaves the book mostly in SPY outside 2009-2011, "
        "so its result may be one episode (the 2009-2010 bank and industrial recovery) and the "
        "walk-forward folds will be thin: the folds that miss that episode will look like SPY "
        "less fees. Cutters are cheap, cyclical, often financial names, so the book is a value "
        "and small-ish tilt that trailed SPY's big-company growth from 2011; equal slots of "
        "mostly mid-size members bet against the market's shape (insight 91). A name above its "
        "200-day average a year after a cut is partly a momentum pick, so it may move with the "
        "failed momentum books and read as their kin. Behind the SPY switch the fast falls of "
        "1998 and 2011 still land before it turns. The announcement timing changes an alarm by "
        "about 19 days against a 182-day wait, so ANN and EX should be within noise of each "
        "other (under half a point a year). The omission alarm can fire on a data gap or a "
        "switch to half-yearly payments; such a name is not a cutter and only adds noise."
    ),
    candidates=(
        _v("ANN-S200-T", RecoveryParams(T20),
           "Cutters 6-18 months on, price above its 200-day average, up to 20 at 5%, rest SPY, behind the SPY-200 switch"),
        _v("EX-S200-T", RecoveryParams(T20, timing="ex"),
           "Control: the same rule with the cut alarm timed on the ex-date"),
        _v("ANN-ALL-T", RecoveryParams(T20, sma_n=0),
           "Every cutter 6-18 months on, no 200-day filter: is waiting for the turn worth anything?"),
        _v("ANN-S200", RecoveryParams(NOT20),
           "No SPY switch: the recovered-cutter picks on top of SPY, always invested"),
    ),
    seen_keys=(
        "concept:dividend-cut-recovery",
        "concept:dividend-omission-reversal",
        "concept:dividend-announcement-timing",
    ),
)
