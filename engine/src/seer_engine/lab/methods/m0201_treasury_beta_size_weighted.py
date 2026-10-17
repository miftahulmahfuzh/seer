"""M0201 — The bond-like book sized by company size: M0197's 20 picks weighted by real market
value under a 10% ceiling, instead of equal slots.

Source: variation of M0197 (Treasury beta; D.E. Shaw research note, caia.org/node/6853; Maio &
Santa-Clara; Driessen, Kuiper & Beilo). Reserved as an idea weighting by dollar volume; Sera
20261018-0517 sharpened it for the owner's theme "books shaped like the market": weight by real
point-in-time market value, one share class per company, a pre-registered ceiling, a dollar-volume
arm only as the bridge to M0122/M0198, and the meaningless control of the same shape.

Why. M0197's bond-like book beat its rate-rising opposite by about 5 points a year on the deposits
with no switch, but every book in that frame holds 20 equal slots, which leans toward the smaller
index members compared with SPY (insight 91), and SPY's big-company drift is the opponent from
2018. This method keeps M0197's picks byte for byte (its ``scored`` and banded quarterly
``choose``, imported unchanged) and moves money between them by company size, so the question is
whether the ranking's lead survives once the book is shaped like the market.

The sizing. At every monthly check each pick's weight is proportional to its size and the stock
weights sum to what the equal book holds (picks / 20): the dial moves money between names, never
changes how much is invested; unfilled slots stay in SPY as in M0197.

    * ``"mv"``: ``Market.market_value(symbol, data_date)``, shares outstanding as filed by that day
      times the close as it printed (``market_fields`` includes ``"shares"``). One value per
      company: when more than one listed class of one company is held (GOOG/GOOGL, FOX/FOXA,
      NWS/NWSA), each class answers the whole company's count times its own price, so the
      company is sized once (from the first held class that answers), the ceiling applies to the
      company, and its weight is split equally over its held classes.
    * ``"dv"``: mean close times volume over the last ``DV_N`` sessions (M0198's
      ``trading_value``), the old stand-in, kept as the bridge to the dollar-volume yardsticks.

A company whose size is unknown (no filed count, or a zero read) gets the median size of the
picks' companies that have one; with no known size at all they share the exposure equally. Then no name may hold
more than ``cap`` of the account (M0034's water-filling ``_apply_ceiling``: the excess goes to the
names still under it). The ceiling is 10% in every variant, written now: a ranking probe run
before this file was committed (the bond side's picks and their market values on re-pick dates,
no later returns) put up to 52% of an uncapped book in one name (MSFT, 2013-12-31) and the
effective name count at 3.5-15.

Known caveats of the size figure, written before any result: about one pick in ten has no value
(Fannie and Freddie through 2004, DTE, PCG, META in 2014) and takes the median; BRK.B's 2010-11
figure counts class A shares only, so it weighs far too little those years; companies tagging
their count per class in XBRL (Alphabet from 2014) go unknown and take the median.

Controls in the same frame: ``side="opp"`` (M0197's rate-rising side, the paired control) and
``side="placebo"``, M0202's hash order over exactly the names M0197's loadings could score that
day (M0187's ``draw``), sized the same way -- the meaningless book of the same shape.

Pure: picks, sizes and weights read only bars and filings dated <= ``data_date``. Every variant
sets ``trend`` explicitly (``FactorParams``' default is the SPY 200-day switch, M0188's slip).
Market-aware (``market_fields = ("series", "shares")``): the history-only path has no yield, so by
the contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at
Gotrade's real fees on the owner's monthly top-up.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    YieldBetaParams,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0197_treasury_yield_beta import scored as yb_scored
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target
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

ADDED = date(2026, 10, 18)
DV_N = 63  # sessions in the dollar-volume read
SIDES = ("bond", "opp", "placebo")
SIZINGS = ("mv", "dv")

#: Listed classes of one company; each answers the whole company's count times its own price.
CLASS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"GOOG", "GOOGL"}),
    frozenset({"FOX", "FOXA"}),
    frozenset({"NWS", "NWSA"}),
)


@dataclass(frozen=True, slots=True)
class SizedYieldBetaParams:
    """M0197's book (``yb``; its own ``side`` is unused, ``side`` here decides) plus the sizing.
    ``cap`` is an absolute per-name ceiling (0.10 = 10% of the account); ``seed`` the placebo's
    hash seed (0 and unused for the real rankings)."""

    yb: YieldBetaParams
    side: str = "bond"
    sizing: str = "mv"
    cap: float = 0.10
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.yb, YieldBetaParams):
            raise TypeError(f"yb must be YieldBetaParams, got {type(self.yb).__name__}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if self.sizing not in SIZINGS:
            raise ValueError(f"sizing must be one of {SIZINGS}, got {self.sizing!r}")
        if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
            raise TypeError(f"cap must be a number, got {type(self.cap).__name__}")
        if not (1.0 / self.yb.inner.top <= float(self.cap) <= 1.0):
            raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be an int >= 0, got {self.seed!r}")
        if (self.side == "placebo") != (self.seed > 0):
            raise ValueError("a placebo needs a seed >= 1, and only a placebo takes one")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "sizing": self.sizing, "cap": repr(float(self.cap)),
               "seed": str(self.seed), "dv_n": str(DV_N),
               "class_groups": ";".join(",".join(sorted(g)) for g in CLASS_GROUPS)}
        for k, v in self.yb.as_dict().items():
            if k != "side":
                out[f"yb.{k}"] = v
        return out


def _check(params: object) -> SizedYieldBetaParams:
    if not isinstance(params, SizedYieldBetaParams):
        raise TypeError(f"params must be SizedYieldBetaParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class SizedPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None
    market: Any  # the Market, for market_value; None on the history-only path


def ranked(history: Mapping[str, History], series: MarketSeries, rows: list[FactorRow],
           data_date: date, p: SizedYieldBetaParams) -> dict[str, float]:
    """Rank fractions in [0, 1), 0 first: M0197's for bond and opp, M0202's hash placebo over
    exactly the names M0197's loadings could score that day."""
    if p.side != "placebo":
        return yb_scored(history, series, rows, data_date, replace(p.yb, side=p.side))
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.yb.market)
    lv = loadings(history, series, pool, data_date, p.yb.market)
    order = sorted(lv, key=lambda s: (draw(p.seed, s, data_date), s))
    return {s: k / len(order) for k, s in enumerate(order)}


def company(symbol: str) -> str:
    """The key one company's listed classes share (the group's first symbol), else the symbol."""
    group = next((g for g in CLASS_GROUPS if symbol in g), None)
    return symbol if group is None else min(group)


def sizes(prepared: SizedPrepared, picks: list[str], data_date: date,
          p: SizedYieldBetaParams) -> dict[str, float]:
    """One size per company among the picks (0.0 = unknown): market value, read from the first
    held class that answers (every class answers the whole company), or summed trading value."""
    out: dict[str, float] = {}
    for s in picks:
        k = company(s)
        if p.sizing == "dv":
            out[k] = out.get(k, 0.0) + trading_value(prepared.history[s], data_date, DV_N)
            continue
        if out.get(k, 0.0) > 0.0:
            continue
        v = prepared.market.market_value(s, data_date)
        out[k] = float(v) if v is not None and np.isfinite(v) and v > 0.0 else 0.0
    return out


def sized_weights(raw: list[float], exposure: float, cap: float) -> list[Decimal | None]:
    """One weight per company, summing to ``exposure`` (the equal book's), unknown sizes at the
    median known size, then the ceiling. No known size: equal shares of ``exposure``."""
    if not raw:
        return []
    known = [x for x in raw if x > 0.0]
    med = float(np.median(known)) if known else 1.0
    size = np.array([x if x > 0.0 else med for x in raw], dtype=np.float64)
    w = _apply_ceiling(size / float(size.sum()) * exposure, cap)
    return [_floor_weight(float(x)) for x in w]


def resize(prepared: SizedPrepared, equal: tuple[Target, ...], data_date: date,
           p: SizedYieldBetaParams) -> tuple[Target, ...]:
    """M0197's equal-slot targets with the stock slots re-sized by company, the ceiling applied
    to each company, a company's weight split equally over its held classes, the rest in SPY."""
    market = p.yb.market
    picks = [t.symbol for t in equal if t.symbol != market]
    size = sizes(prepared, picks, data_date, p)
    keys = list(size)
    cw = sized_weights([size[k] for k in keys], len(picks) / p.yb.inner.top, float(p.cap))
    weight = dict(zip(keys, cw, strict=True))
    out: list[Target] = []
    for s in picks:
        w = weight[company(s)]
        if w is None:
            continue
        n = sum(1 for x in picks if company(x) == company(s))
        if n > 1:
            w = _floor_weight(float(w) / n)
            if w is None:
                continue
        t = target_from_close(s, last_close(prepared.history[s], data_date), w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
    mh = prepared.history.get(market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class SizedYieldBetaAllocator:
    """M0197's screened, banded, quarterly book (bond-like, its opposite or a hash placebo), the
    picks sized by company size under a ceiling; slots left over in SPY. No yield: no targets."""

    id = "M0201"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).yb.inner), DV_N)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.yb.market}
        if p.yb.inner.trend is not None:
            fixed.add(p.yb.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).yb.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizedYieldBetaParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        inner = p.yb.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = ranked(prepared.history, prepared.series, rows, data_date, p) if repick else {}
        equal = choose(prepared.history, members, frac, data_date, held, p.yb)
        return resize(prepared, equal, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no yield and no share counts, so no target."""
        return self._run(SizedPrepared(history, EMPTY_SERIES, None, None), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SizedPrepared:
        return SizedPrepared(history, EMPTY_SERIES, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> SizedPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return SizedPrepared(market.history, series, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizedPrepared):
            raise TypeError(f"prepared must be SizedPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SIZEDYB = SizedYieldBetaAllocator()

SW = ("SPY", 200)


def _p(side: str, sizing: str = "mv", trend: tuple[str, int] | None = None,
       seed: int = 0) -> SizedYieldBetaParams:
    # trend has no default here: FactorParams' own default is the SPY 200-day switch, and every
    # variant must say which it means (M0188's slip). The rank is unused: only the screen.
    yb = YieldBetaParams(FactorParams(rank="momentum", top=20, trend=trend))
    return SizedYieldBetaParams(yb, side=side, sizing=sizing, cap=0.10, seed=seed)


def _v(suffix: str, params: SizedYieldBetaParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0201-{suffix}", family="M0201", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZEDYB, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0201",
    name=(
        "The bond-like book sized by company size: the 20 stocks that rise most when yields fall, "
        "weighted by market value under a 10% ceiling instead of equal slots"
    ),
    family="stock-treasury-beta",
    source_kind="variation",
    source_ref=(
        "variation of M0197 (Treasury beta; D.E. Shaw research note, caia.org/node/6853); "
        "reserved by Sera 20261018-0517 for the theme 'books shaped like the market'"
    ),
    parent_id="M0197",
    hypothesis=(
        "M0197's bond-like book (the 20 screened members whose weekly returns rise most when the "
        "10-year yield falls, net of the market; quarterly re-picks, a 40% keep band, empty slots "
        "in SPY) beat its rate-rising opposite by about 5 points a year on the deposits without "
        "the switch (+12.5% vs +7.7%, SPY +7.2%, placebo M0187 +8.8% to +11.9%), but every book "
        "in that frame holds equal slots, a lean toward the smaller index members (insight 91), "
        "and SPY's big-company drift is the opponent. The rate-beta papers are from the 2010s, so "
        "the whole dev window is before publication. Keep M0197's picks exactly and weight each "
        "by its real point-in-time market value (shares as filed by that day times the close as "
        "it printed; held classes of one company are one company, sized once and capped "
        "together; an unknown size takes the median), capped at 10% of the account per company "
        "with the excess spread over the rest, stock "
        "weights summing to what the equal book holds, re-sized at every monthly check. "
        "Variants: Y20-MV10 (bond side, no switch), Y20-MV10-SW (behind the SPY 200-day switch), "
        "OPP-MV10 (the opposite side sized the same way, the paired control), Y20-DV10 (bond side "
        "sized by 63-day dollar volume instead, the bridge to M0122 and M0198), and PLC1-MV10, "
        "PLC2-MV10 (M0202's hash placebo over the same scoreable names, sized the same way: the "
        "meaningless book of the same shape). Fractional shares at Gotrade's real fees on the "
        "owner's monthly top-up. Reported beside the equal-weight M0197 rows, M0187 and M0198, "
        "with each variant's beta to SPY, on both the dev and the survivorship-check stores. "
        "Judged first on 2009-2015 against SPY, then the 2013 rate jump. Success: Y20-MV10 keeps "
        "a clear gap (2+ points a year on the deposits) over both OPP-MV10 and the sized "
        "placebo seeds, and does not trail SPY in 2009-2015."
    ),
    expected_failure=(
        "Sized by market value, the bond side becomes a book of its few biggest names at the 10% "
        "ceiling (the probe put the effective name count at 3.5-15; MSFT took 52% uncapped on "
        "2013-12-31, AAPL 36% on 2012-12-31), and the rest are utilities and REITs too small to "
        "matter, so it behaves like a handful of large defensives plus SPY. The equal-weight "
        "lean was part of M0197's lead (insight 91 and M0198's question), so the sized bond book "
        "loses 1-3 points a year against its equal twin and the gap to its opposite shrinks to "
        "the 1996-2008 falling-rate era; in 2009-2015 it trails SPY's tech-led rally, and the "
        "sized placebo seeds land within a point of it. Without the switch it falls about 45-55% "
        "in 2008 like every book in this frame; with the switch the worst fall drops near 20% "
        "but the switch sells the 2010 and 2011 dips. Re-sizing monthly to a drifting value adds "
        "small resize trades at Gotrade's minimums. DSR at N about 142 will not reach 0.90 unless "
        "the lead over the sized placebo is several points. The dollar-volume arm leans into the "
        "busiest names (1999-2000 tech) and differs from the market-value arm by more than the "
        "ranking does. From 2016 yields stopped falling and rose sharply in 2022, the regime a "
        "bond-like book suffers in, which dev cannot show; and the missing dead companies "
        "flattered M0197 by about half its lead, likely the same here."
    ),
    candidates=(
        _v("Y20-MV10", _p("bond"),
           "The bond-like 20, weighted by market value under a 10% ceiling, no switch"),
        _v("Y20-MV10-SW", _p("bond", trend=SW),
           "The size-weighted bond-like book behind the SPY 200-day switch"),
        _v("OPP-MV10", _p("opp"),
           "Control: the rate-rising 20, weighted by market value under a 10% ceiling, no switch"),
        _v("Y20-DV10", _p("bond", sizing="dv"),
           "The bond-like 20 weighted by 63-day dollar volume under a 10% ceiling, no switch"),
        _v("PLC1-MV10", _p("placebo", seed=1),
           "Placebo: the same scoreable names in a hash order (seed 1), sized by market value"),
        _v("PLC2-MV10", _p("placebo", seed=2),
           "Placebo: hash order seed 2, sized by market value"),
    ),
    seen_keys=(
        "concept:treasury-beta-size-weighted",
        "concept:market-value-weighting",
    ),
)
