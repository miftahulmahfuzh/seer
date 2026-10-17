"""M0186 — Coskewness the way the market is shaped: only the busiest companies, picks sized toward the bigger ones.

Parent: M0179, which ranked every F4-screened index member on standardized coskewness with SPY
(Harvey & Siddique 2000, eq. 11, 156 weekly returns) and held the 20 or 40 most negative in equal
slots, quarterly, banded. Its dev lead was real on the twenty-year average (N40-SW +10.5% a year on
the owner's deposits against SPY's +7.2%) but was earned before 2009: the eligible 40-name book
trailed SPY by 5.6% a year in 2009-2015, its 20-name books paid only in months when the average
stock beat the index, and the walk-forward picked the positive-coskewness control before every
fold (2 of 4). That is the signature of an equal-weight basket of index members tilting small
against SPY's big-company drift (insight 91), and it says nothing yet about whether the premium
exists among the companies that drive SPY.

This method keeps M0179's score untouched (``m0179_coskewness.scored``, the same window, the same
standardization, the same quarterly re-pick and 40% keep band) and changes two things:

  * WHO MAY BE RANKED. On a re-pick date the F4-screened rows are cut to the ``pool`` with the
    highest 20-day mean close x volume (F4's own ``dollar_volume``; ties by symbol), as M0172 and
    M0178 did. The store has no sound market caps, so trading value stands in for size. The rank
    fraction and the keep band are measured inside that pool. When fewer than ``pool`` members
    pass the screen (the 1990s, when the store prices about half the index) the pool is all of
    them.
  * HOW THE PICKS ARE SIZED. ``weighting="sqrt"`` gives each pick a weight proportional to the
    square root of its 20-day trading value, with no name above ``cap`` (10%) and the excess spread
    over the rest (M0034's water-filling ceiling), total ``len(picks) / top`` exactly as the equal
    book, so the dial moves money between names and never changes how much is invested.
    ``weighting="equal"`` is M0179's 1/top slots, the equal-weight rung. The weights are re-read
    every month from the trailing 20 sessions; under the "equity" resize band (1% of the account)
    a month's drift mostly does not trade.

Assumptions, written before the run: trading value on back-adjusted closes reads a heavy dividend
payer's 1990s value a little low, a small cross-sectional tilt (M0172's note); a held name that
leaves the pool between re-picks keeps its slot until the next re-pick, as in M0179; and the
square root is the half-way house M0125 measured, chosen because full trading-value weights put a
third of a 20-name book in three names. None of the dials were chosen from post-2015 results: the
owner's 2018-2026 run of M0179 is known to this session, and the pool sizes (150, 200), the book
sizes (20, 40), the cap and the switch all come from the idea row and the parent's dev record.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
Pure; reads only bars dated <= ``data_date``.
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
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0179_coskewness import (
    REPICK_MONTHS,
    CoskewParams,
    CoskewPrepared,
    scored,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    DV_N,
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 17)
WEIGHTINGS = ("sqrt", "equal")


@dataclass(frozen=True, slots=True)
class BusyCoskewParams:
    """``ranking`` is M0179's score, book size, band and switch; ``pool`` the most-traded screened
    names it may rank; ``weighting`` how picks are sized; ``cap`` the sqrt book's per-name ceiling."""

    ranking: CoskewParams
    pool: int = 150
    weighting: str = "sqrt"
    cap: float = 0.10

    def __post_init__(self) -> None:
        if not isinstance(self.ranking, CoskewParams):
            raise TypeError(f"ranking must be CoskewParams, got {type(self.ranking).__name__}")
        if isinstance(self.pool, bool) or not isinstance(self.pool, int):
            raise TypeError(f"pool must be an int, got {type(self.pool).__name__}")
        if self.pool < self.ranking.inner.top:
            raise ValueError(f"pool must be >= top, got pool={self.pool} top={self.ranking.inner.top}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if isinstance(self.cap, bool) or not isinstance(self.cap, float):
            raise TypeError(f"cap must be a float, got {type(self.cap).__name__}")
        if not 1.0 / self.ranking.inner.top <= self.cap <= 1.0:
            raise ValueError(f"cap must be in [1/top, 1], got {self.cap}")

    @property
    def inner(self) -> FactorParams:
        return self.ranking.inner

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool), "weighting": self.weighting, "cap": repr(self.cap)}
        for key, v in self.ranking.as_dict().items():
            out[f"ranking.{key}"] = v
        return out


def _check(params: object) -> BusyCoskewParams:
    if not isinstance(params, BusyCoskewParams):
        raise TypeError(f"params must be BusyCoskewParams, got {type(params).__name__}")
    return params


def busiest(rows: list[FactorRow], pool: int) -> list[FactorRow]:
    """The ``pool`` rows with the highest 20-day mean trading value (ties by symbol)."""
    return sorted(rows, key=lambda r: (-r.dollar_volume, r.symbol))[:pool]


def trading_value(h: History, data_date: date) -> float | None:
    """Mean close x volume over the DV_N sessions through ``data_date`` (None when unreadable)."""
    i = h.index_of(data_date)
    if i is None or i + 1 < DV_N:
        return None
    v = float(np.mean(h.close[i + 1 - DV_N: i + 1] * h.volume[i + 1 - DV_N: i + 1]))
    return v if np.isfinite(v) and v > 0.0 else None


def pick_weights(dvs: list[float], p: BusyCoskewParams) -> list[Decimal | None]:
    """One weight per pick, Σ = len(dvs) / top: the equal book's exposure under either dial."""
    if not dvs:
        return []
    top = p.inner.top
    if p.weighting == "equal":
        eq = equal_weight(top)
        return [eq for _ in dvs]
    raw = np.sqrt(np.array(dvs, dtype=np.float64))
    w = _apply_ceiling(raw / float(raw.sum()) * (len(dvs) / top), p.cap)
    return [_floor_weight(float(x)) for x in w]


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: BusyCoskewParams) -> tuple[Target, ...]:
    r = p.ranking
    stocks = sorted(s for s in held if s != r.market and s not in EXCLUDED)
    if not stocks or data_date.month in REPICK_MONTHS:
        frac = scored(history, busiest(rows, p.pool), data_date, r)
        order = [s for _, s in sorted((v, s) for s, v in frac.items())]
        cut = r.keep_pct / 100.0
        kept = sorted((s for s in stocks if frac.get(s, 1.0) < cut), key=lambda s: (frac[s], s))
        picks = kept[: r.inner.top]
        for s in order:
            if len(picks) >= r.inner.top:
                break
            if s not in picks:
                picks.append(s)
    else:  # between re-picks: keep every holding that is still a member with a bar today
        picks = [s for s in stocks if s in members][: r.inner.top]
    live: list[tuple[str, Decimal, float]] = []
    for s in picks:
        h = history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        dv = trading_value(h, data_date)
        if dv is None:
            continue
        live.append((s, last_close(h, data_date), dv))
    out: list[Target] = []
    for (s, close, _), w in zip(live, pick_weights([dv for _, _, dv in live], p)):
        if w is None:
            continue
        t = target_from_close(s, close, w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
    mh = history.get(r.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(r.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class BusyCoskewAllocator:
    """M0179's coskewness book, ranked among the most-traded members, sized toward the bigger ones."""

    id = "M0186"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.ranking.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).ranking.market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CoskewPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: BusyCoskewParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(CoskewPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CoskewPrepared:
        return CoskewPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoskewPrepared):
            raise TypeError(f"prepared must be CoskewPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


BUSY_COSKEW = BusyCoskewAllocator()

SW = ("SPY", 200)


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _p(top: int, pool: int, weighting: str = "sqrt", *, switch: bool = False,
       positive: bool = False) -> BusyCoskewParams:
    ranking = CoskewParams(_screen(top, SW if switch else None), positive=positive)
    return BusyCoskewParams(ranking, pool=pool, weighting=weighting)


def _v(suffix: str, params: BusyCoskewParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0186-{suffix}", family="M0186", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUSY_COSKEW, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0186",
    name=("Coskewness the way the market is shaped: only the busiest companies, picks sized "
          "toward the bigger ones"),
    family="stock-coskewness",
    source_kind="variation",
    source_ref=(
        "Harvey & Siddique (2000), Conditional Skewness in Asset Pricing Tests, JF 55(3); "
        "variation of M0179 (pool cut as M0172, square-root sizing and ceiling as M0125/M0034)"
    ),
    parent_id="M0179",
    hypothesis=(
        "M0179's lead came mostly from before 2009, much of it 2000-2002 when unloved and smaller "
        "index members rebounded while the giants crashed; it trailed SPY in 2009-2015 when the "
        "giants led, and its 20-name books paid only in broad months. Ask whether the coskewness "
        "premium survives among the companies that drive SPY. Keep M0179's score exactly "
        "(standardized coskewness with SPY over 156 weekly log returns, HS 2000 eq. 11; published "
        "2000, so the dev window is mostly post-publication), its quarterly re-pick and 40% keep "
        "band, but rank only the 150 (or 200) F4-screened members with the highest 20-day trading "
        "value, and size the picks by the square root of trading value with no name above 10% "
        "(total invested the same as the equal book; unfilled slots in SPY). Fractional shares at "
        "Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's monthly top-up. Variants: "
        "N20-B150-SQ (the idea: 20 most negative of the 150 busiest, sqrt-sized, no switch), "
        "N20-B150-SQ-SW (the same behind the SPY 200-day switch), N40-B150-SQ-SW (a 40-name rung, "
        "switch, mirroring M0179-N40-SW), N40-B200-SQ (40 of the 200 busiest, no switch), "
        "N20-B150-EQ (equal-weight rung, no switch), and P20-B150-SQ, the paired control: the 20 "
        "most positive-coskewness names of the same pool, same sizing, no switch, kept in the "
        "walk-forward pool so the fold selection can pick against the idea. Report M0179-N20 and "
        "M0179-N40-SW beside the results and each variant's beta to SPY. Success: a negative "
        "variant beats SPY TR with worst fall <= 25%, PF >= 1.3, the control trails it, a "
        "positive 2009-2015 edge on both the dev and the survivorship-check stores, and a "
        "majority of walk-forward folds. Design is from the dev window only: no variant, pool or "
        "cap was chosen for post-2015 results."
    ),
    expected_failure=(
        "Like the spike filter on the busiest names (M0172) and the busiest low-correlation book "
        "(M0178), narrowing to the most-traded members shrinks the spread, because a pricing "
        "premium for crash risk lives in the less-watched companies where few arbitrageurs "
        "work. The 150 busiest are also the crowd's favourites of each era (1999-2000 tech, "
        "2007-2008 banks and energy), and the most negative-coskewness of them are exactly those, "
        "so the no-switch books fall 45-55% in 2008 and break the 25% limit; the switch cuts the "
        "fall but gives back the 2009-2011 rebound, as in M0179. Square-root sizing moves the "
        "book toward SPY's shape, so the gap to SPY in 2009-2015 narrows, but the twenty-year "
        "lead narrows with it and may vanish. Coskewness from three years of weekly returns is "
        "dominated by the last crash, so the control and the idea swap places by regime and the "
        "folds stay near 2 of 4."
    ),
    candidates=(
        _v("N20-B150-SQ", _p(20, 150),
           "The 20 most negative-coskewness of the 150 busiest members, square-root sized, no switch"),
        _v("N20-B150-SQ-SW", _p(20, 150, switch=True),
           "The same book behind the SPY 200-day switch"),
        _v("N40-B150-SQ-SW", _p(40, 150, switch=True),
           "A 40-name rung of the busiest-pool book, square-root sized, behind the switch"),
        _v("N40-B200-SQ", _p(40, 200),
           "40 of the 200 busiest members, square-root sized, no switch"),
        _v("N20-B150-EQ", _p(20, 150, "equal"),
           "The 20 most negative of the 150 busiest in equal slots: the weighting's own control"),
        _v("P20-B150-SQ", _p(20, 150, positive=True),
           "Control: the 20 most positive-coskewness of the same pool, same sizing, no switch"),
    ),
    seen_keys=(
        "concept:coskewness-busiest-pool",
        "concept:coskewness-sqrt-trading-value-weight",
    ),
)
