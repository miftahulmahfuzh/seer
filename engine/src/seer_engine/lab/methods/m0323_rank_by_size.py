"""M0323 — Does ranking directly by company size beat using size only as an after-the-fact filter?

Source: variation of M0318 (a size pool filter, dropping one end of the market-value sort from
M0197-Y20's pool before the host's own yield-sensitivity rank). Small-firm size premium: Banz 1981
(JFE 9(1)) and Fama & French 1992 (JF 47(2)), published long before the dev window ends, so a
strong dev reading is expected to be the faded kind (the crowd traded it from the 1980s).

Idea. M0318's mirror arm dropped the biggest 60% and kept the smaller and unknown-size names. It
earned far more than every other arm on the regular prices, but on the survivorship-check store its
margin over the best blind draw shrank to 1.6 points a year (13.8% against 12.2%), inside the
7.5-point spread measured among chance-only draws. That is a filter's side effect: the final rank
was still the host's interest-rate-sensitivity key. Here size is the rank. The chassis is M0318's
exactly (same screened pool, the same yearly yield fit deciding who is in the pool, 20 equal slots,
40% keep band, quarterly re-rank, no switch, SPY in any slot left over), only the key changes.

Arms (six, the lab's cap). SMALL ranks the pool smallest company first, BIG biggest first (the
mirror; it prices what the direction is worth, since both pay the same costs), HOST is M0318's
allocator with nothing dropped, i.e. M0197-Y20 untouched: the no-opinion book that prices what
the habit of this chassis costs and earns, so a size arm's edge is read against it and not only
against SPY. R1-R3 rank by a fixed per-symbol hash over the same known-size pool: three random
20-name books on the same chassis, the spread that says how much of a 20-name book's return is
which 20 names happened to be held.

A company with no market value on the re-pick date cannot be ranked by size. It goes behind every
known-size name (never picked while a sized name is free), identically in all four ranked arms.
Market-value coverage is 62-75% of dev member-days in 2009-2015 and lower before, so early years
rank over a thinner pool; the analysis reads that before crediting any era difference to size.

Pure: bars dated <= ``data_date``, ``MarketSeries.upto`` for T10Y, ``Market.market_value`` as filed
and priced on or before ``data_date``. Market-aware (``market_fields = ("series", "shares")``).
Rules are ``monthly-hold-frac-gotrade``: twenty slots of fractional shares at real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0197_treasury_yield_beta import REPICK_MONTHS, YieldBetaParams, choose, loadings
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import NOSW, draw
from seer_engine.lab.methods.m0318_size_filter_dose import SIZEFILTER, SizeFilterParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 24)

SIDES = ("small", "big", "blind")


@dataclass(frozen=True, slots=True)
class SizeRankParams:
    """``inner`` is the host, term for term. ``side``: smallest market value first (``"small"``),
    biggest first (``"big"``) or a fixed per-symbol hash order (``"blind"``, keyed by ``seed``).
    Names with no usable market value rank behind every sized name."""

    inner: YieldBetaParams
    side: str = "small"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, YieldBetaParams):
            raise TypeError(f"inner must be YieldBetaParams, got {type(self.inner).__name__}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "seed": str(self.seed), "rank_by": "market-value",
               "unknown_size": "ranks-last"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SizeRankParams:
    if not isinstance(params, SizeRankParams):
        raise TypeError(f"params must be SizeRankParams, got {type(params).__name__}")
    return params


def size_frac(history: Mapping[str, History], series: MarketSeries, market: Any, rows: list[Any],
              data_date: date, p: SizeRankParams) -> dict[str, float]:
    """Rank fraction over the host's own pool (the names the yield fit can score): 0 is the first
    name the book wants. Sized names first in the arm's order, unsized behind them by symbol."""
    inner = p.inner
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != inner.market)
    lv = loadings(history, series, pool, data_date, inner.market)
    if not lv:
        return {}
    sized: dict[str, float] = {}
    for s in lv:
        v = market.market_value(s, data_date)
        if v is not None and np.isfinite(v) and v > 0.0:
            sized[s] = float(v)
    if p.side == "small":
        first = sorted(sized, key=lambda s: (sized[s], s))
    elif p.side == "big":
        first = sorted(sized, key=lambda s: (-sized[s], s))
    else:
        first = sorted(sized, key=lambda s: (draw(p.seed, s), s))
    order = first + sorted(s for s in lv if s not in sized)
    return {s: k / len(order) for k, s in enumerate(order)}


@dataclass(frozen=True, slots=True, eq=False)
class SizeRankPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None
    market: Any


class SizeRankAllocator:
    """M0197's book chassis with company size as the rank key instead of yield loading."""

    id = "M0323"
    market_fields = ("series", "shares")

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        inner = _check(params).inner
        fixed = {inner.market}
        if inner.inner.trend is not None:
            fixed.add(inner.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).inner.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: SizeRankPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizeRankParams) -> tuple[Target, ...]:
        inner = p.inner
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner.inner)
        stocks = [s for s in held if s != inner.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = (size_frac(prepared.history, prepared.series, prepared.market, rows, data_date, p)
                if repick else {})
        return choose(prepared.history, members, frac, data_date, held, inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no market, so no size lookup and no target."""
        return self._run(SizeRankPrepared(history, EMPTY_SERIES, None, None), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SizeRankPrepared:
        return SizeRankPrepared(history, EMPTY_SERIES, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> SizeRankPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return SizeRankPrepared(market.history, series, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SizeRankPrepared):
            raise TypeError(f"prepared must be SizeRankPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SIZERANK = SizeRankAllocator()


def _v(suffix: str, side: str, seed: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0323-{suffix}", family="M0323", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZERANK, params=SizeRankParams(NOSW, side=side, seed=seed),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0323",
    name=("Does ranking directly by company size (favouring smaller companies) beat using size "
          "only as an after-the-fact filter?"),
    family="stock-size-tilt",
    source_kind="variation",
    source_ref=("variation of M0318 (size pool filter on M0197-Y20's book); small-firm size "
                "premium, Banz 1981 JFE 9(1), Fama & French 1992 JF 47(2)"),
    parent_id="M0318",
    hypothesis=(
        "M0318's reversed mirror arm, which dropped the biggest 60% of a bond-like book's pool and "
        "kept the smaller and unknown-size names, earned far more than every other arm tested on "
        "the regular prices, but its edge over the best random-drop control shrank to 1.6 points a "
        "year on the survivorship-checked prices (13.8% against 12.2%), inside the 7.5-point "
        "spread among chance-only draws. That was a filter's side effect: the final rank was still "
        "the host's yield-sensitivity key. This method ranks the same screened pool DIRECTLY by "
        "market value on the same 20-name, equal-weight, no-switch chassis. The small-firm "
        "premium was published in 1981 and 1992 and has been traded since, so any dev edge is "
        "expected to be the pre-crowd kind. Six arms: SMALL (smallest first, the idea), BIG "
        "(biggest first, the mirror: same costs and chassis, opposite opinion, so the pair proves "
        "whether the signal is real), HOST (M0318's allocator with nothing dropped, i.e. the "
        "untouched M0197-Y20 book: the no-opinion arm that prices the chassis itself, so a size "
        "arm is read against it and not only against SPY), and three hash-ranked books R1-R3 over "
        "the same known-size pool (the spread of what any 20 names do on this chassis). "
        "Predictions, written now: SMALL beats SPY on dev funded CAGR but falls outside the "
        "R1-R3 spread by less than the 7.5-point chance spread; SMALL's worst fall exceeds 50% "
        "(small names plus no switch), BIG's is under SMALL's; SMALL does not lead SPY in "
        "2009-2015 on the survivorship-check store. Names with no market value rank last in every "
        "ranked arm."
    ),
    expected_failure=(
        "The likeliest failure is that SMALL's edge sits inside the R1-R3 random spread, so the "
        "size signal is indistinguishable from which 20 names were held, as M0318's mirror was on "
        "the survivorship-check store. Second, a max drawdown over 50% for a 20-name book with no "
        "switch (M0318's mirror arm fell 66%) fails the hard gate on its own. Third, the small end "
        "of the dev store is the part most helped by missing dead companies: the edge may shrink "
        "or flip on the survivorship store and in 2009-2015, where coverage is best. Fourth, "
        "market-value coverage is 62-75% in 2009-2015 and lower earlier, so the ranked pool "
        "thins in early years. Fifth, the premium is published and widely traded, so a strong "
        "dev result likely fades from 2018. Three hash draws are a thin spread; claims leaning on "
        "its exact width are written as weak."
    ),
    candidates=(
        _v("SMALL", "small", 0, "Rank the pool smallest market value first: the idea, direct size "
                                "tilt on M0318's chassis"),
        _v("BIG", "big", 0, "Rank biggest market value first: the mirror, same costs and "
                            "chassis, opposite opinion"),
        Candidate(id="M0323-HOST", family="M0323", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                  allocator=SIZEFILTER, params=SizeFilterParams(NOSW),
                  rationale="No-opinion control: M0318's allocator with nothing dropped, the "
                            "untouched yield-ranked book, prices the chassis",
                  added=ADDED, owner_inputs=()),
        _v("R1", "blind", 323, "Control: hash-ranked pool, seed 1, a random 20 on the same chassis"),
        _v("R2", "blind", 324, "Control: hash-ranked pool, seed 2"),
        _v("R3", "blind", 325, "Control: hash-ranked pool, seed 3"),
    ),
    seen_keys=(
        "concept:rank-by-company-size-direct-small-tilt",
        "concept:size-rank-vs-size-filter-same-chassis",
    ),
)
