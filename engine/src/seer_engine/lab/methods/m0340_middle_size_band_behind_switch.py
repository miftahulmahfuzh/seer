"""M0340 — Does the middle of the company-size range beat both ends behind SPY's 200-day switch?

Source: variation of M0333 (size ranking behind SPY's 200-day switch on M0197-Y20's chassis).
The two ends of the size range carry published effects: the small-firm premium (Banz 1981, JFE
9(1); Fama & French 1992, JF 47(2)) and the big-company drift that cap-weighted SPY rides. The
middle has no famous paper of its own here, which is the point: it is the part of the range the
crowd has not been told to trade, though "mid-cap" funds have existed since the 1990s.

Idea. M0333 found that behind the cash switch, smallest-first tied a random-order book and a book
with no size opinion did as well as either end. If size carries anything on this chassis, the
untried place is the middle. Each band arm ranks the host's pool (the names its yearly yield fit
can score) by how close each company's size percentile sits to a fixed centre: 0.50 for the
middle, 0.333 for the lower middle, 0.667 for the upper middle. Twenty slots therefore fill from
the names nearest that centre outward. Everything else is M0333's chassis untouched: same pool,
20 equal slots, 40% keep band (a held name stays while it is in the first 40% of the order),
quarterly re-pick, SPY in leftover slots, all cash when SPY closes at or under its 200-day average.

Controls. M0333's random books, its two ends and its no-opinion host were recorded on an older
store (fingerprint 704a21…, run 2026-10-25), not the current one, so they cannot be cited as the
same measurement. Three fresh random books (R4-R6, hash order, new seeds 340-342) run here on the
current store, and they are the yardstick the bands are judged against. M0333's ends and host are
quoted only as older-store context. With six arms the cap, the no-opinion host is not re-run.

Names with no market value on the re-pick date rank behind every sized name in every arm.
Pure: bars dated <= ``data_date``, ``MarketSeries.upto`` for T10Y through the host's yield fit,
``Market.market_value`` as filed and priced on or before ``data_date``.
Rules are ``monthly-hold-frac-gotrade``: twenty slots of fractional shares at real fees.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0197_treasury_yield_beta import REPICK_MONTHS, YieldBetaParams, choose, loadings
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import HOST
from seer_engine.lab.methods.m0323_rank_by_size import SIZERANK, SizeRankParams
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

ADDED = date(2026, 11, 13)


@dataclass(frozen=True, slots=True)
class MidBandParams:
    """``inner`` is the host, term for term. ``centre`` is the size percentile (0 smallest, 1
    biggest) the book fills outward from: the names whose percentile is nearest it come first."""

    inner: YieldBetaParams
    centre: Decimal = Decimal("0.5")

    def __post_init__(self) -> None:
        if not isinstance(self.inner, YieldBetaParams):
            raise TypeError(f"inner must be YieldBetaParams, got {type(self.inner).__name__}")
        if not isinstance(self.centre, Decimal):
            raise TypeError(f"centre must be a Decimal, got {type(self.centre).__name__}")
        if not Decimal(0) <= self.centre <= Decimal(1):
            raise ValueError(f"centre must be in [0, 1], got {self.centre}")

    def as_dict(self) -> dict[str, str]:
        out = {"centre": str(self.centre), "rank_by": "market-value-percentile-distance",
               "unknown_size": "ranks-last"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> MidBandParams:
    if not isinstance(params, MidBandParams):
        raise TypeError(f"params must be MidBandParams, got {type(params).__name__}")
    return params


def band_frac(history: Mapping[str, History], series: MarketSeries, market: Any, rows: list[Any],
              data_date: date, p: MidBandParams) -> dict[str, float]:
    """Rank fraction over the host's own pool: 0 is the first name the book wants. Sized names are
    placed on a size percentile ((k + 0.5) / n, smallest first) and ordered by distance from the
    centre; unsized names follow by symbol."""
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
    asc = sorted(sized, key=lambda s: (sized[s], s))
    n = len(asc)
    c = float(p.centre)
    dist = {s: abs((k + 0.5) / n - c) for k, s in enumerate(asc)}
    first = sorted(asc, key=lambda s: (dist[s], s))
    order = first + sorted(s for s in lv if s not in sized)
    return {s: k / len(order) for k, s in enumerate(order)}


@dataclass(frozen=True, slots=True, eq=False)
class MidBandPrepared:
    history: Mapping[str, History]
    series: MarketSeries
    factor: FactorPrepared | None
    market: Any


class MidBandAllocator:
    """M0333's chassis with the size rank re-centred: nearest a size percentile first."""

    id = "M0340"
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

    def _run(self, prepared: MidBandPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: MidBandParams) -> tuple[Target, ...]:
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
        frac = (band_frac(prepared.history, prepared.series, prepared.market, rows, data_date, p)
                if repick else {})
        return choose(prepared.history, members, frac, data_date, held, inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no market, so no size lookup and no target."""
        return self._run(MidBandPrepared(history, EMPTY_SERIES, None, None), members, data_date,
                         held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> MidBandPrepared:
        return MidBandPrepared(history, EMPTY_SERIES, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> MidBandPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return MidBandPrepared(market.history, series, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MidBandPrepared):
            raise TypeError(f"prepared must be MidBandPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


MIDBAND = MidBandAllocator()


def _band(suffix: str, centre: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0340-{suffix}", family="M0340", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MIDBAND, params=MidBandParams(HOST, centre=Decimal(centre)),
                     rationale=rationale, added=ADDED, owner_inputs=())


def _rand(suffix: str, seed: int) -> Candidate:
    return Candidate(id=f"M0340-{suffix}", family="M0340", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZERANK, params=SizeRankParams(HOST, side="blind", seed=seed),
                     rationale=(f"Control: M0333's hash-ranked random book with a new seed {seed}, "
                                "behind the same switch, on the current store"),
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0340",
    name="Does the middle of the company-size range beat both ends behind SPY's 200-day switch?",
    family="stock-size-tilt",
    source_kind="variation",
    source_ref=("variation of M0333 (size ranking behind SPY's 200-day switch); small-firm "
                "premium Banz 1981 JFE 9(1), Fama & French 1992 JF 47(2) at one end, cap-weighted "
                "big-company drift at the other"),
    parent_id="M0333",
    hypothesis=(
        "Behind the cash switch, smallest-first and biggest-first both failed to beat a "
        "random-order book by a margin worth the name, and a book with no size opinion did as "
        "well as either (M0333). The two ends of the size range carry the published small-firm "
        "premium (1981, 1992) and the large-company drift; the middle has not been tried. Three "
        "band arms on M0333's exact chassis behind the same 200-day switch fill twenty slots "
        "outward from a fixed size percentile: MID (0.50), LOWMID (0.333), UPMID (0.667). Three "
        "fresh random books R4-R6 (M0333's hash order, new seeds 340-342) run beside them on the "
        "current store, because M0333's own random books (trials 1172-1174), its ends (1170 "
        "SMALL, 1171 BIG) and its no-opinion host (1175, the book first recorded as M0197-Y20-SW, "
        "trial 649) were measured on an older store; those are quoted as older-store context "
        "only. Pass line, written now: a band passes only if its dev funded CAGR beats the best "
        "of R4-R6 by more than the R4-R6 range in this run, it leads SPY in 2009-2015, and it "
        "clears the lab's gates. If no band does, close the size family on this chassis. "
        "Predictions: the three bands sit inside the random range or within a point of its top; "
        "MID's worst fall is similar to the random books' (the switch, not the band, sets it); "
        "no arm leads SPY in 2009-2015 (time in cash through a rising decade); UPMID is the best "
        "band in 2009-2015 because it is closest to the big names that drove that era."
    ),
    expected_failure=(
        "The likeliest failure is that no band separates from the random books: on this chassis "
        "the switch and the yearly pool decide the return, and which twenty names fill the slots "
        "barely matters, as M0333 found for both ends. Second, every arm trails SPY in 2009-2015 "
        "because the switch sat in cash during false alarms in a decade with no bear market "
        "(insights 452, 462). Third, market-value coverage is thin before 2009, so percentile "
        "bands early on are drawn over a partial pool and the 'middle' is not the market's "
        "middle. Fourth, survivorship: the dev store misses dead companies, which sit mostly in "
        "the smaller half, so LOWMID is the arm most flattered. Fifth, three random draws are a "
        "thin spread; a range of three is a weak yardstick and a pass against it is weak too. "
        "Sixth, mid-cap funds are an old product, so whatever the middle earned before 2015 may "
        "already be traded away."
    ),
    candidates=(
        _band("MID", "0.5", "Fill outward from the middle of the size range (50th percentile): "
                            "the idea"),
        _band("LOWMID", "0.333", "Fill outward from the lower middle (33rd percentile)"),
        _band("UPMID", "0.667", "Fill outward from the upper middle (67th percentile)"),
        _rand("R4", 340),
        _rand("R5", 341),
        _rand("R6", 342),
    ),
    seen_keys=(
        "concept:middle-size-band-behind-200-day-switch",
    ),
)
