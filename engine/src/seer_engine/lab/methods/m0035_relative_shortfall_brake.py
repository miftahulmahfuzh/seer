"""M0035 — Step back to the market when the book has trailed it for a year.

Source: a variation of M0032, from insight 58's second recommendation (four of four test-window
looks failed, and the dev window cannot see why).
Idea: every brake in the lab reads *absolute* risk -- the book's own volatility (M0001, M0011,
M0022), the market's own trend (F4's SPY-200 gate), the basket's own drawdown (M0013), a fast
crash gate (M0012). None of them reads how the book is doing against the thing it is judged by.
The four failed test looks did not fail in a crash: they failed by trailing a SPY fed the owner's
identical deposits, steadily, across 2016-2026, and no absolute brake can see that, because
nothing about the book's own path looked alarming while it happened.

This method keeps M0032 verbatim -- M0007-N20-RAW's ranking (top-20 raw cumulative residual
momentum, F4's screen, the SPY-200 trend gate, monthly, equal weights) in fractional shares on
``monthly-hold-frac-gotrade`` -- and adds exactly one switch. At every rebalance it measures the
book's own trailing ``look_n``-session return against SPY's over the same sessions, and while the
book is behind by more than ``behind`` it moves ``park`` of the account into SPY, scaling the
stock legs by what is left. When the gap closes, the stock book comes back.

THE SHADOW BOOK, and what it is not. An allocator sees bars, members, the data date and what the
book holds; it never sees the account's equity curve, so "the book's own trailing return" has to
be rebuilt from bars. ``relative_gap`` rebuilds it: it walks the month-end sessions inside the
trailing window, asks the *unbraked* inner allocator what it would have ranked at each one, and
chains those equal-weight baskets day by day on SPY's own session calendar. Four things about
that reconstruction are worth stating plainly, because they are what could fool us:

  * It is the UNBRAKED book, deliberately. The real account's own path would make the trigger
    recursive -- once parked in SPY the gap would close mechanically within a year whatever the
    strategy did -- so the signal is "would the stock book have trailed the market", which is the
    question the brake is actually asking, and it stays a pure function of bars.
  * It uses the member set of the DATA DATE at each past month-end, because point-in-time
    membership reaches an allocator only through ``prepare_market``, which the lab reserves for
    fundamentals. Measured on this store, that proxy overlaps the true point-in-time universe by
    94-98% (Jaccard) a year back -- about 12 extra names out of 250-390 -- so it is a small,
    bounded distortion of the trigger's universe, and none at all of the book's own picks, which
    still rank the true point-in-time members.
  * It is gross: no fees, no deposits, no cash drag. It is a signal, not an accounting.
  * It needs ``resid_lookback + look_n + a month`` of bars, about 677 sessions, which is deeper
    than ``lookback()`` declares. ``lookback()`` stays at the inner allocator's requirement, the
    one the PICKS need, so that this method's dev window is identical to M0032's (both are floored
    by ``MEMBERSHIP_START`` anyway) and the two are comparable trade for trade. Where the extra
    depth is absent the brake stands down and the variant IS the control -- a hard on/off on a
    fixed bar count, never a shortened window, so the P4 identity holds either way. On the real
    dev store that depth is there from the first session, which the analysis verifies rather than
    assumes.

The trend gate stays supreme: when SPY is below its 200-day average the inner allocator targets
nothing, and the brake adds nothing either. This switch trades stock risk for market risk; it
never trades cash for market risk.

Six variants: the control plus three thresholds (5, 10, 15 points) at half the account and the
two wider thresholds at the whole account. The seventh combination, 5 points at the whole
account, is dropped rather than squeezed in -- it is the most trigger-happy switch in the set and
the least plausible thing to ask of a real account, and the method cap is six.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    ReturnGrid,
    build_grid,
    resid_lookback,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History, as_day

ADDED = date(2026, 10, 9)

PARK = "SPY"  # where the account steps aside to: a default ETF, so no owner input is needed
MONTH_SESSIONS = 23  # the most NYSE sessions a calendar month can hold


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ShortfallParams:
    """M0032's configuration (``inner``) plus the relative-shortfall switch."""

    inner: ResidParams
    look_n: int = 252  # sessions the book and SPY are compared over (12 months)
    behind: Decimal = Decimal("0.10")  # park once the book trails SPY by more than this
    park: Decimal = Decimal("0.5")  # share of the account moved to SPY while behind (0 = control)

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if isinstance(self.look_n, bool) or not isinstance(self.look_n, int) or self.look_n < 20:
            raise ValueError(f"look_n must be an int >= 20, got {self.look_n!r}")
        if not isinstance(self.behind, Decimal) or not (0 < self.behind < 1):
            raise ValueError(f"behind must be a Decimal in (0, 1), got {self.behind!r}")
        if not isinstance(self.park, Decimal) or not (0 <= self.park <= 1):
            raise ValueError(f"park must be a Decimal in [0, 1], got {self.park!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"look_n": str(self.look_n), "behind": str(self.behind), "park": str(self.park)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def shortfall_lookback(params: ShortfallParams) -> int:
    """Bars the PICKS need. The brake reads deeper; see the module docstring."""
    return resid_lookback(params.inner)


def shadow_depth(params: ShortfallParams) -> int:
    """Bars the shadow book needs before the brake switches on at all."""
    return resid_lookback(params.inner) + params.look_n + MONTH_SESSIONS + 1


# --------------------------------------------------------------------------- the shadow book


def month_end_indices(cal: np.ndarray) -> np.ndarray:
    """Indices of the last session of each calendar month in ``cal`` (ascending)."""
    months = cal.astype("datetime64[M]")
    change = np.concatenate((months[1:] != months[:-1], np.ones(1, dtype=bool)))
    return np.flatnonzero(change)


def _chain(grid: ReturnGrid, rows: np.ndarray, lo: int, hi: int) -> float:
    """The equal-weight basket's growth factor over sessions ``lo + 1 .. hi`` (1.0 when empty)."""
    if hi <= lo or rows.size == 0:
        return 1.0
    block = grid.rets[rows, lo + 1 : hi + 1]
    with np.errstate(invalid="ignore"):
        daily = np.nanmean(np.where(np.isfinite(block), block, np.nan), axis=0)
    daily = np.where(np.isfinite(daily), daily, 0.0)
    return float(np.prod(1.0 + daily))


def relative_gap(
    grid: ReturnGrid | None,
    picks_at: Callable[[date], tuple[str, ...]],
    data_date: date,
    params: ShortfallParams,
) -> float | None:
    """The shadow book's trailing return minus SPY's over the same sessions, or None.

    None means "not measurable here" -- ``data_date`` is not a session of the market symbol's
    calendar, or the store is shallower than ``shadow_depth(params)``. The caller then leaves the
    book unbraked, which is the control. Reads only columns at or before ``data_date``.
    """
    if grid is None:
        return None
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day or j + 1 < shadow_depth(params):
        return None
    market = grid.row.get(params.inner.market)
    if market is None:
        return None
    start = j - params.look_n
    ends = month_end_indices(grid.dates[: j + 1])
    prior = ends[ends <= start]
    if prior.size == 0:
        return None

    marks = [int(prior[-1]), *(int(r) for r in ends[(ends > start) & (ends < j)])]
    wealth = 1.0
    for k, mark in enumerate(marks):
        lo = max(mark, start)
        hi = min(marks[k + 1], j) if k + 1 < len(marks) else j
        picks = picks_at(grid.dates[mark].astype(object))
        rows = np.asarray([grid.row[s] for s in picks if s in grid.row], dtype=np.int64)
        # No picks is the trend gate shut (or nothing scorable): the shadow sits in cash.
        wealth *= _chain(grid, rows, lo, hi) if rows.size else 1.0

    spy = grid.rets[market, start + 1 : j + 1]
    spy_wealth = float(np.prod(1.0 + np.where(np.isfinite(spy), spy, 0.0)))
    if not (np.isfinite(wealth) and np.isfinite(spy_wealth)):
        return None
    return wealth - spy_wealth


def braked(
    inner: tuple[Target, ...],
    gap: float | None,
    history: Mapping[str, History],
    data_date: date,
    params: ShortfallParams,
) -> tuple[Target, ...]:
    """``inner``, or ``park`` of the account in SPY with the stock legs scaled by the rest."""
    if not inner or params.park <= 0 or gap is None or gap > -float(params.behind):
        return inner
    close = last_close(history.get(PARK), data_date)
    if close is None:
        return inner
    leg = target_from_close(PARK, close, params.park)
    if leg is None:  # an unusable SPY price: stay in the book rather than half-brake
        return inner
    out = [leg]
    keep = Decimal(1) - params.park
    if keep > 0:
        for target in inner:
            weight = scale_weight(target.weight, keep)
            if weight is not None:
                out.append(replace(target, weight=weight))
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


def _check(params: object) -> ShortfallParams:
    if not isinstance(params, ShortfallParams):
        raise TypeError(f"params must be ShortfallParams, got {type(params).__name__}")
    return params


class RelativeShortfallBrake:
    """M0032's book, part of it parked in SPY while the book trails SPY over the trailing year.

    Held symbols get no special treatment: the stock legs are the inner allocator's fresh top
    set, as in M0007, and the SPY leg is sized by ``park`` alone.
    """

    id = "M0035"

    def lookback(self, params: Any) -> int:
        return shortfall_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({PARK, *RESIDMOM.symbols(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (PARK,)

    def uses_members(self, params: Any) -> bool:
        return bool(RESIDMOM.uses_members(_check(params).inner))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = RESIDMOM.targets(history, members, data_date, held, p.inner)
        if not inner or p.park <= 0:
            return inner

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(t.symbol for t in RESIDMOM.targets(history, members, d, frozenset(), p.inner))

        gap = relative_gap(build_grid(history, p.inner.market), picks_at, data_date, p)
        return braked(inner, gap, history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = RESIDMOM.targets_prepared(prepared, members, data_date, held, p.inner)
        if not inner or p.park <= 0:
            return inner

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(
                t.symbol
                for t in RESIDMOM.targets_prepared(prepared, members, d, frozenset(), p.inner)
            )

        gap = relative_gap(prepared.grid(p.inner.market), picks_at, data_date, p)
        return braked(inner, gap, prepared.history, data_date, p)


BRAKE = RelativeShortfallBrake()
RAW20 = ResidParams(N20, scaled=False)  # M0007-N20-RAW / M0032's ranking, verbatim


def _v(suffix: str, behind: str, park: str, rationale: str) -> Candidate:
    params = ShortfallParams(RAW20, behind=Decimal(behind), park=Decimal(park))
    return Candidate(id=f"M0035-{suffix}", family="M0035", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BRAKE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0035",
    name="Step back to the market when the book has trailed it for a year: a relative-shortfall brake",
    family="stock-relative-shortfall-brake",
    source_kind="variation",
    source_ref="insight 58's second recommendation; M0032-N20-RAW-FRAC-GT plus a relative-drawdown switch to SPY",
    parent_id="M0032",
    hypothesis=(
        "Every brake in the lab reads absolute risk: own volatility (M0001, M0011, M0022), the "
        "market's trend (F4's SPY-200 gate), the basket's own drawdown (M0013), a fast crash gate "
        "(M0012). None reads how the book is doing against the thing it is judged by. The four "
        "failed test looks did not fail in a crash; they failed by trailing a deposit-matched SPY "
        "steadily across 2016-2026, and no absolute brake can see that, because nothing about the "
        "book's own path looked alarming while it happened. This keeps M0032's ranking and "
        "execution verbatim -- top-20 raw cumulative residual momentum, F4's screen, the SPY-200 "
        "trend gate, monthly, equal weights, fractional shares at Gotrade's real fees on "
        "monthly-hold-frac-gotrade, funded 5,000,000 IDR on the 25th of each month -- and adds "
        "exactly one switch: at each monthly rebalance, compare the book's own trailing 12-month "
        "return with SPY's over the same sessions, and while the book is behind by more than the "
        "threshold, park a fraction of the account in SPY. I expect this to COST return on the dev "
        "window, and the point of the run is to price the insurance rather than hope it is free. "
        "The useful outputs are two numbers the lab has never measured: how many points a year the "
        "switch costs, and how often and how long it fires. A brake that costs under a point a year "
        "and caps the relative shortfall is a far better promotion candidate than one more ranking "
        "tweak, because the failure it insures against is the one that has now actually happened "
        "four times out of four. CTRL (park = 0) is the in-method control: it should reproduce "
        "M0032's trade count and shape on the identical window and fee schedule, which is the only "
        "fair baseline, since a recorded trial's returns are not reproducible across store rebuilds "
        "and must be compared re-run to re-run."
    ),
    expected_failure=(
        "The switch sells low and buys the index back high, at least twice. 1996-2015 contains two "
        "long spells -- 1998-2000 and 2007-2009 -- in which an active book trailing the index was "
        "exactly the moment to keep holding the active book: momentum lags badly into the late "
        "stage of a melt-up and then earns it all back in the unwind. Being wrong twice in twenty "
        "years can easily cost more than the two points a year the switch is trying to protect, so "
        "I expect the braked variants to land 1-3 points a year below CTRL with a worst fall that "
        "is no better, and possibly worse, because the parked SPY leg takes the market's own 2008 "
        "fall at full size while the trend gate that would have held the stock book in cash is "
        "still shut. The second way it fails is quieter and worse: the trigger almost never fires "
        "on dev, because a top-20 residual-momentum book beat SPY by seven points a year over "
        "1996-2015, so a 12-month shortfall of 10 or 15 points is rare -- and then the dev window "
        "says nothing at all about the regime that actually broke the four test looks, and every "
        "variant comes back as a near-copy of CTRL."
    ),
    candidates=(
        _v("CTRL", "0.10", "0.00",
           "The control: M0032's book under this wrapper with the switch off, the baseline the braked runs are read against"),
        _v("T05-HALF", "0.05", "0.50", "Behind by more than 5 points over a year: half the account to SPY"),
        _v("T10-HALF", "0.10", "0.50", "Behind by more than 10 points: half the account to SPY"),
        _v("T15-HALF", "0.15", "0.50", "Behind by more than 15 points: half the account to SPY"),
        _v("T10-ALL", "0.10", "1.00", "Behind by more than 10 points: the whole account to SPY"),
        _v("T15-ALL", "0.15", "1.00", "Behind by more than 15 points: the whole account to SPY"),
    ),
    seen_keys=(
        "concept:relative-shortfall-brake",
        "concept:book-vs-benchmark-drawdown-switch",
        "concept:park-in-spy-while-trailing",
    ),
)
