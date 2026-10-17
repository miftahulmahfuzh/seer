"""M0202 — Bond-like stocks with a gentler crash guard: half the book stays invested below SPY's
200-day average instead of all of it going to cash.

Source: variation of M0197 (Treasury beta; D.E. Shaw research note, caia.org/node/6853; Maio &
Santa-Clara; Driessen, Kuiper & Beilo), reserved by Sera 20261017-1835 from the 20261017-1808
synthesis. The ranking, the screen, the band and the SPY slots are M0197's, imported unchanged;
only the switch is new.

Why. M0197's bond-like book (the 20 members whose weekly returns rise most when the 10-year yield
falls, net of the market) beat every placebo seed and its own opposite with no switch (+12.5% a
year on the deposits against +8.8% to +11.9% and +7.7%), but fell 62% in 2008. Behind the
all-or-nothing SPY 200-day switch it fell only 22%, yet trailed SPY by 3.3 points a year in
2009-2015 (the switch sold the 2010 and 2011 dips) and led the switched placebo by under a point:
the switch did the work and erased the ranking's gap. A half-size guard keeps half the bet on
through the dips the switch sold, so it should keep more of the ranking's lead (and its 2009-2015
edge) while still cutting the 2008 fall roughly in half.

The guard, one of two, always explicit (``FactorParams.trend`` is None in every variant, so F4's
default 200-day gate can never sneak in and empty the book):

    * ``"half"``: full size while SPY closes above its 200-day average; otherwise every target
      (stock slots and the SPY filler alike) at half weight, the rest in cash.
    * ``"half-fast"``: full size while SPY closes above its 200-day OR its 50-day average (M0195's
      stateless "back in on a close over the 50-day"); half size only under both.

Under half size the holdings do not change: a quarter's picks are kept, only resized, so the guard
costs a trim and a top-up, not a full round trip. A re-pick in a half-size month picks as usual
and buys at half weight. With too few SPY bars to read the guard the book is at half size.

Controls on the same frame and the same guard: ``side="neutral"`` (M0197's rate-neutral ranking,
smallest absolute loading; M0197 showed it carries no information) and ``side="placebo"``, which
orders exactly the names M0197's loadings could score by M0187's hash of (seed, symbol, month) --
the frame with no idea in it. Two placebo seeds under "half" and one under "half-fast", so the
idea's lead is read against a spread and not a single draw.

Market-aware (``market_fields = ("series",)``): the history-only path has no yield, so by the
contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``, as M0197: fractional shares,
Gotrade's real fees, the owner's monthly deposits, resized when a slot is off by 1% of the account
(halving a 5% slot always clears it).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    YieldBetaParams,
    YieldBetaPrepared,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0197_treasury_yield_beta import scored as yb_scored
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
)
from seer_engine.strategies.indicators import sma_window

ADDED = date(2026, 10, 17)
SLOW_N = 200
FAST_N = 50
HALF = Decimal("0.5")
GUARDS = ("half", "half-fast")
SIDES = ("bond", "neutral", "placebo")


@dataclass(frozen=True, slots=True)
class HalfGuardParams:
    """``yb`` is M0197's params (screen, book size, band, market; its ``side`` is ignored and its
    ``inner.trend`` must be None); ``side`` which order fills the book; ``guard`` the half-size
    rule; ``seed`` the placebo's hash seed (0 and unused for the real rankings)."""

    yb: YieldBetaParams
    side: str = "bond"
    guard: str = "half"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.yb, YieldBetaParams):
            raise TypeError(f"yb must be YieldBetaParams, got {type(self.yb).__name__}")
        if self.yb.inner.trend is not None:
            raise ValueError("yb.inner.trend must be None: the guard here replaces F4's switch")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if self.guard not in GUARDS:
            raise ValueError(f"guard must be one of {GUARDS}, got {self.guard!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if (self.side == "placebo") != (self.seed > 0):
            raise ValueError("a placebo needs a seed >= 1, and only a placebo takes one")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "guard": self.guard, "seed": str(self.seed),
               "slow_n": str(SLOW_N), "fast_n": str(FAST_N), "half": str(HALF)}
        for k, v in self.yb.as_dict().items():
            if k != "side":
                out[f"yb.{k}"] = v
        return out


def _check(params: object) -> HalfGuardParams:
    if not isinstance(params, HalfGuardParams):
        raise TypeError(f"params must be HalfGuardParams, got {type(params).__name__}")
    return params


def _sma(h: History, i: int, n: int) -> float | None:
    if i + 1 < n:
        return None
    return float(sma_window(h.close[i + 1 - n : i + 1].reshape(1, n), n)[0])


def full_size(history: Mapping[str, History], data_date: date, p: HalfGuardParams) -> bool:
    """True when the guard allows the full book on ``data_date``; False (half size) otherwise,
    including when SPY has no bar dated d or too few bars for the 200-day average."""
    h = history.get(p.yb.market)
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    close = float(h.close[i])
    slow = _sma(h, i, SLOW_N)
    if slow is None:
        return False
    if close > slow:
        return True
    if p.guard == "half":
        return False
    fast = _sma(h, i, FAST_N)
    return fast is not None and close > fast


def ranked(history: Mapping[str, History], series: MarketSeries, rows: list[FactorRow],
           data_date: date, p: HalfGuardParams) -> dict[str, float]:
    """Rank fractions in [0, 1), 0 first: M0197's for bond and neutral, the hash for the placebo
    over exactly the names M0197's loadings could score that day."""
    if p.side != "placebo":
        return yb_scored(history, series, rows, data_date, replace(p.yb, side=p.side))
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.yb.market)
    lv = loadings(history, series, pool, data_date, p.yb.market)
    order = sorted(lv, key=lambda s: (draw(p.seed, s, data_date), s))
    return {s: k / len(order) for k, s in enumerate(order)}


def halved(targets: tuple[Target, ...]) -> tuple[Target, ...]:
    """Every target at half its weight, the rest left in cash."""
    out = []
    for t in targets:
        w = (t.weight * HALF).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        if w > 0:
            out.append(replace(t, weight=w))
    return tuple(out)


class HalfGuardAllocator:
    """M0197's screened, banded, quarterly book (bond-like, rate-neutral or a hash placebo),
    always invested, at half size while SPY is under its guard. No yield: no targets."""

    id = "M0202"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).yb.inner), SLOW_N + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_check(params).yb.market,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).yb.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: HalfGuardParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        inner = p.yb.inner
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = ranked(prepared.history, prepared.series, rows, data_date, p) if repick else {}
        out = choose(prepared.history, members, frac, data_date, held, p.yb)
        return out if full_size(prepared.history, data_date, p) else halved(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield, so no ranking and no target."""
        return self._run(YieldBetaPrepared(history, EMPTY_SERIES, None), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> YieldBetaPrepared:
        return YieldBetaPrepared(history, EMPTY_SERIES, prepare_factor(history))

    def prepare_market(self, market: Any) -> YieldBetaPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return YieldBetaPrepared(market.history, series, prepare_factor(market.history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, YieldBetaPrepared):
            raise TypeError(f"prepared must be YieldBetaPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


HALFGUARD = HalfGuardAllocator()


def _p(side: str, guard: str, seed: int = 0) -> HalfGuardParams:
    # trend=None, always: FactorParams' default is the SPY 200-day switch (M0188's slip), and here
    # the guard replaces it. The rank is unused: only the screen.
    yb = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=None))
    return HalfGuardParams(yb, side=side, guard=guard, seed=seed)


def _v(suffix: str, params: HalfGuardParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0202-{suffix}", family="M0202", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=HALFGUARD, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0202",
    name=(
        "Bond-like stocks with a gentler crash guard: half the book stays invested below SPY's "
        "200-day average instead of all of it going to cash"
    ),
    family="stock-treasury-beta",
    source_kind="variation",
    source_ref="M0197 synthesis (Sera 20261017-1808); Treasury beta, caia.org/node/6853",
    parent_id="M0197",
    hypothesis=(
        "M0197's bond-like picks (the 20 screened members whose weekly returns rise most when the "
        "10-year Treasury yield falls, net of the market, re-picked quarterly with a 40% keep "
        "band, empty slots in SPY) beat every placebo seed and their own opposite without a "
        "switch (+12.5% a year on the deposits vs +8.8% to +11.9%, SPY +7.2%) but fell 62% in "
        "2008; behind the all-or-nothing SPY 200-day switch they fell 22% but trailed SPY by 3.3 "
        "points a year in 2009-2015 and led the switched placebo by under a point. The rate-beta "
        "papers are from the 2010s, so the dev window is before publication and any edge may have "
        "faded since. A gentler guard keeps half the bet on: full size while SPY closes above its "
        "200-day average, every target at half weight (rest cash) below it (HALF); and HALF-FAST, "
        "full size again as soon as SPY closes above its 50-day average. Holdings are kept and "
        "only resized when the guard flips. Controls under the same guard and frame: N20-HALF "
        "(rate-neutral, smallest absolute loading) and a hash-order placebo over the same "
        "scoreable names (two seeds under HALF, one under HALF-FAST). Fractional shares at "
        "Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's monthly top-up. "
        "Success, written now: Y20-HALF or Y20-HALF-FAST beats total-return SPY on dev with a "
        "worst fall under the screen's 50% bar, a positive lead over SPY in 2009-2015, and beats "
        "its own same-guard placebo seeds by at least 2 points a year on the deposits."
    ),
    expected_failure=(
        "Halving exposure halves the switch's protection without restoring the ranking's edge: "
        "the 2008 fall of the bond-like book was led by the financials the 2007-08 fit put on the "
        "bond side (Fannie, Freddie, regional banks), and half of a 62% fall compounded through "
        "a year below the 200-day is still about 35-40%, past design section 1's 25% even if it "
        "clears the screen's 50%. In 2009-2015 the half-size book recovers only half as fast in "
        "the 2009 rebound and the 2010-11 dips, so it lands between Y20 (+7.0 points vs SPY) and "
        "Y20-SW (-3.3), likely near zero, and the placebo under the same guard rises with it, "
        "leaving the gap to the placebo near M0197's one point rather than two. HALF-FAST adds "
        "whipsaw trades at real fees around the 50-day. DSR at N about 130 needs a lead well "
        "above the placebo's; the survivorship check halved M0197's lead and is likely to do the "
        "same here. And from 2016 yields stopped falling and rose sharply in 2022, the regime a "
        "bond-like book suffers in, which dev cannot show."
    ),
    candidates=(
        _v("Y20-HALF", _p("bond", "half"),
           "The 20 members that rise most when the 10-year yield falls, half size below SPY's "
           "200-day average"),
        _v("Y20-HALF-FAST", _p("bond", "half-fast"),
           "The bond-like book, half size only while SPY is under both its 200-day and 50-day "
           "averages"),
        _v("N20-HALF", _p("neutral", "half"),
           "Contrast: the 20 members least moved by yield changes, same half-size guard"),
        _v("PLC1-HALF", _p("placebo", "half", seed=1),
           "Placebo: the same scoreable names in a fixed hash order (seed 1), same guard"),
        _v("PLC2-HALF", _p("placebo", "half", seed=2),
           "Placebo: hash order seed 2, same guard"),
        _v("PLC1-HALF-FAST", _p("placebo", "half-fast", seed=1),
           "Placebo: hash order seed 1 under the fast guard"),
    ),
    seen_keys=(
        "concept:treasury-beta",
        "concept:half-size-trend-guard",
    ),
)
