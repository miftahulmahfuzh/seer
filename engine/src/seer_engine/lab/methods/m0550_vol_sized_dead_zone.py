"""M0550 -- The volatility-sized dead zone: ignore falls that are normal for the market right now.

Source: variation on M0115 (the fixed-width dead-zone brake, itself a variation on M0109's
proportional own-drawdown brake). Idea: M0115 found that ignoring the first 10-20% of a fall cut
M0109's 2009-2015 cost from about 10 points a year to 4-6, but gave back most of the crash
protection -- the worst fall rose from 17.8% to 41-47% as the zone widened, and no version cleared
the luck bar (best DSR 0.638 against the 0.90 bar at the policy's N). Every one of M0115's zones
was a FIXED width, chosen the same way whether the market was calm or already swinging hard. A
15% dead zone is generous in a quiet year like 2005 and almost nothing in a year that is already
volatile, so a fixed zone is mis-sized twice over: too narrow to stop whipsaw in the calm years
M0115 was trying to fix, and too wide to still protect once a real crash has already lifted
volatility. This method sizes the zone off the shadow book's own trailing volatility instead of a
constant, so "normal" is read from the market itself at each date rather than guessed once in
2026.

THE BOOK, THE SHADOW AND THE DRAWDOWN READ ARE M0109'S, UNCHANGED. The 50 most-traded index
members at equal weight, the gross membership-free shadow index rebuilt from bars, the trailing
one-year high the drawdown is measured against, the weekly clock and every other constant are
imported from M0109 rather than copied, exactly as M0115 did. ``BrakeParams`` cannot gain a field
without moving every M0109 digest, so ``VolZoneParams`` subclasses it; the allocator has its own
id, ``M0550``. ``taper`` (inherited) is repurposed here as a pure on/off switch -- ``None`` is the
control (brake never fires), any other Decimal means the brake is live -- because the actual zone
and taper widths are no longer fixed numbers on the method, they are read from the market at
run time.

THE DIAL. At a data date with a shadow drawdown ``dd``:

  * The ZONE WIDTH is ``vol_mult`` trailing monthly-return standard deviations of the shadow's own
    gross returns, clipped to ``[min_start, max_start]`` so a flat run of months cannot zero the
    zone and a wild one cannot brake the account off entirely. The SD is taken over the trailing
    ``vol_n`` (default 12) month-end-to-month-end returns of the SAME shadow index M0109 already
    reads, using only month-ends at or before the data date -- never a partial, still-open month.
  * The TAPER WIDTH is ``vol_mult + slope_sds`` of the same trailing SD (with a small floor above
    the zone so the slope is never degenerate), so the account reaches ``floor`` (0, all cash)
    ``slope_sds`` further standard deviations past where the zone ends.
  * Exposure is 1 inside the zone (``dd <= start``), falls in a straight line to ``floor`` by
    ``taper``, clipped to ``[floor, 1]`` and rounded to M0109's ``STEP`` -- the same shape M0109
    and M0115 use, only the ``start``/``taper`` inputs are now a function of the date instead of a
    constant.
  * Before 13 month-ends exist (``vol_n`` + 1, so ``vol_n`` trailing monthly returns can be
    measured) the volatility is not yet knowable and the brake stands down -- full exposure --
    which is the same convention M0109's own ``shadow_drawdown`` already uses for an unwarmed
    shadow, so the two warm-up gates agree on what "not yet measurable" means.

THE ARMS. VOL2, VOL3 and VOL4 hold the taper's distance past the zone fixed at 2 standard
deviations (``slope_sds=2``) and vary only the zone itself: 2, 3 and 4 trailing monthly-return
SDs. CTRL is the same book weekly, never braked -- the no-opinion arm, and a recorded book twin of
M0109-EW-ALL-W. REPRO-20-40 is the reproduction arm: ``fixed_start``/``fixed_taper`` bypass the
volatility read entirely and pin the zone and taper at 20%/40%, M0115-START20-T40's exact
configuration, so it must reproduce that trial's curve precisely and proves the new exposure
function against a result the lab already has, at no look of its own -- it too is a book twin.

Success, pre-registered: a 2009-2015 cost against CTRL under 3 points a year with a worst fall
under 25% -- looser than M0115's implicit "half the saving" bar on the fall, because a
volatility-scaled zone is not expected to preserve ALL of M0109's crash protection, only enough of
it to be worth the calm-year cost it is meant to save. Eligibility would still need a braked book
to beat SPY TR on deposit-matched money with a worst fall under 20% and a majority of folds; the
plain book underneath already trailed SPY in M0109 and M0115, so a pass remains unlikely and the
measurement is the point.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ReturnGrid, build_grid
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    ONE,
    STEP,
    WEEKLY,
    BrakeParams,
    BrakePrepared,
    DrawdownBrake,
    book_rows,
    book_targets,
    braked,
    chosen,
    month_end_marks,
    prepared_rows,
    shadow_drawdown,
    shadow_wealth,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History, as_day

ADDED = date(2026, 11, 12)


@dataclass(frozen=True, slots=True)
class VolZoneParams(BrakeParams):
    """M0109's book and brake; the dead zone and its taper are sized from the shadow's own vol.

    ``taper`` (inherited) is the on/off switch only: ``None`` is the control, any Decimal means
    the brake is live. ``fixed_start``/``fixed_taper``, when both set, bypass the volatility read
    entirely and pin the zone/taper to constants -- used only by the reproduction arm.
    """

    vol_mult: Decimal = Decimal("2")  # zone width, in trailing monthly-return standard deviations
    slope_sds: Decimal = Decimal("2")  # further SDs past the zone before exposure reaches floor
    vol_n: int = 12  # trailing month-end-to-month-end returns the SD is measured over
    min_start: Decimal = Decimal("0.05")  # zone width floor, so a flat run cannot zero the zone
    max_start: Decimal = Decimal("0.45")  # zone width cap, so one wild month cannot brake it off
    fixed_start: Decimal | None = None  # bypass: pin the zone (reproduction arm only)
    fixed_taper: Decimal | None = None  # bypass: pin the taper (reproduction arm only)

    def __post_init__(self) -> None:
        BrakeParams.__post_init__(self)
        for name in ("vol_mult", "slope_sds", "min_start", "max_start"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite():
                raise TypeError(f"{name} must be a Decimal, got {v!r}")
        if self.vol_mult < 0:
            raise ValueError(f"vol_mult must be >= 0, got {self.vol_mult}")
        if self.slope_sds <= 0:
            raise ValueError(f"slope_sds must be > 0, got {self.slope_sds}")
        if not (Decimal("0") <= self.min_start < self.max_start < 1):
            raise ValueError(
                f"min_start/max_start must satisfy 0 <= min_start < max_start < 1, got "
                f"{self.min_start}/{self.max_start}"
            )
        if isinstance(self.vol_n, bool) or not isinstance(self.vol_n, int) or self.vol_n < 3:
            raise ValueError(f"vol_n must be an int >= 3, got {self.vol_n!r}")
        if (self.fixed_start is None) != (self.fixed_taper is None):
            raise ValueError("fixed_start and fixed_taper must both be set or both be None")
        if self.fixed_start is not None:
            for name in ("fixed_start", "fixed_taper"):
                v = getattr(self, name)
                if not isinstance(v, Decimal) or not v.is_finite():
                    raise TypeError(f"{name} must be a Decimal, got {v!r}")
            if not (Decimal("0") <= self.fixed_start < self.fixed_taper <= 1):
                raise ValueError(
                    f"fixed_start must be < fixed_taper, both in [0, 1], got "
                    f"{self.fixed_start}/{self.fixed_taper}"
                )

    def as_dict(self) -> dict[str, str]:
        out = BrakeParams.as_dict(self)
        out["vol_mult"] = str(self.vol_mult)
        out["slope_sds"] = str(self.slope_sds)
        out["vol_n"] = str(self.vol_n)
        out["min_start"] = str(self.min_start)
        out["max_start"] = str(self.max_start)
        out["fixed_start"] = "none" if self.fixed_start is None else str(self.fixed_start)
        out["fixed_taper"] = "none" if self.fixed_taper is None else str(self.fixed_taper)
        return out


def _check(params: object) -> VolZoneParams:
    if not isinstance(params, VolZoneParams):
        raise TypeError(f"params must be VolZoneParams, got {type(params).__name__}")
    return params


def _day_index(grid: ReturnGrid, data_date: date) -> int | None:
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return None
    return j


def trailing_monthly_vol(grid: ReturnGrid, wealth: np.ndarray, data_date: date,
                         vol_n: int) -> float | None:
    """Sample SD of the shadow's trailing ``vol_n`` monthly returns, using only completed months.

    None means not enough completed months yet: fewer than ``vol_n`` + 1 month-end marks have
    occurred at or before ``data_date``, so there are not ``vol_n`` monthly returns to measure.
    """
    j = _day_index(grid, data_date)
    if j is None:
        return None
    marks = month_end_marks(grid.dates)
    hi = int(np.searchsorted(marks, j, side="right"))
    if hi < vol_n + 1:
        return None
    lo = hi - (vol_n + 1)
    levels = wealth[marks[lo:hi]]
    if levels.size < 2:
        return None
    rets = levels[1:] / levels[:-1] - 1.0
    if not np.all(np.isfinite(rets)):
        return None
    return float(np.std(rets, ddof=1))


def _exposure_from(dd: float, start: float, taper: float, floor: Decimal) -> Decimal:
    if dd <= start:
        return ONE
    raw = 1.0 - (dd - start) / (taper - start)
    clipped = min(1.0, max(float(floor), raw))
    stepped = (Decimal(repr(clipped)) / STEP).quantize(ONE, rounding=ROUND_HALF_UP) * STEP
    return min(ONE, max(floor, stepped))


def vol_zone_exposure(grid: ReturnGrid | None, wealth: np.ndarray | None, data_date: date,
                      drawdown: float | None, p: VolZoneParams) -> Decimal:
    """1 inside a dead zone sized from the shadow's own trailing volatility, then a slope to cash.

    Stands down (full exposure) wherever the drawdown or the volatility is not yet measurable --
    the same convention ``shadow_drawdown`` uses for an unwarmed shadow.
    """
    if p.taper is None or drawdown is None or not np.isfinite(drawdown) or drawdown <= 0.0:
        return ONE
    if p.fixed_start is not None and p.fixed_taper is not None:
        start = float(p.fixed_start)
        taper = float(p.fixed_taper)
    else:
        if grid is None or wealth is None:
            return ONE
        sigma = trailing_monthly_vol(grid, wealth, data_date, p.vol_n)
        if sigma is None:
            return ONE
        start = min(float(p.max_start), max(float(p.min_start), float(p.vol_mult) * sigma))
        taper_raw = (float(p.vol_mult) + float(p.slope_sds)) * sigma
        taper = max(taper_raw, start + 0.01)
    return _exposure_from(drawdown, start, taper, p.floor)


class VolZoneBrake(DrawdownBrake):
    """M0109's book and shadow with a dead zone sized from the shadow's own trailing volatility."""

    id = "M0550"

    def lookback(self, params: Any) -> int:
        _check(params)
        return super().lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params))

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params))

    def uses_members(self, params: Any) -> bool:
        return super().uses_members(_check(params))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        base = book_targets(book_rows(history, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid = build_grid(history, p.market)
        if grid is None:
            return base
        universe = frozenset(history)

        def picks_at(d: date) -> tuple[str, ...]:
            return tuple(r.symbol for r in chosen(book_rows(history, universe, d, p), p))

        wealth = shadow_wealth(grid, picks_at)
        dd = shadow_drawdown(grid, wealth, data_date, p)
        return braked(base, vol_zone_exposure(grid, wealth, data_date, dd, p))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, BrakePrepared):
            raise TypeError(f"prepared must be BrakePrepared, got {type(prepared).__name__}")
        p = _check(params)
        base = book_targets(prepared_rows(prepared.factor, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid, wealth = prepared.shadow(p)
        dd = shadow_drawdown(grid, wealth, data_date, p)
        return braked(base, vol_zone_exposure(grid, wealth, data_date, dd, p))


VOL_ZONE = VolZoneBrake()


def _v(suffix: str, vol_mult: str, slope_sds: str, rationale: str) -> Candidate:
    params = VolZoneParams(taper=Decimal("1"), vol_mult=Decimal(vol_mult), slope_sds=Decimal(slope_sds))
    return Candidate(id=f"M0550-{suffix}", family="M0550", rules=WEEKLY, allocator=VOL_ZONE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


def _ctrl(suffix: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0550-{suffix}", family="M0550", rules=WEEKLY, allocator=VOL_ZONE,
                     params=VolZoneParams(taper=None), rationale=rationale, added=ADDED,
                     owner_inputs=())


def _repro(suffix: str, fixed_start: str, fixed_taper: str, rationale: str) -> Candidate:
    params = VolZoneParams(taper=Decimal("1"), fixed_start=Decimal(fixed_start),
                           fixed_taper=Decimal(fixed_taper))
    return Candidate(id=f"M0550-{suffix}", family="M0550", rules=WEEKLY, allocator=VOL_ZONE,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0550",
    name="The volatility-sized dead zone: ignore falls that are normal for the current market, brake the ones that are not",
    family="book-drawdown-brake",
    source_kind="variation",
    source_ref=(
        "M0115 (the fixed-width dead-zone brake on M0109's proportional own-drawdown brake), with "
        "the zone and taper sized from the shadow's own trailing volatility instead of fixed "
        "constants"
    ),
    parent_id="M0115",
    hypothesis=(
        "M0115 found that a dead zone -- ignore the first part of a fall, then taper hard -- cut "
        "M0109's 2009-2015 cost from about 10 points a year to 4-6, but gave back most of the "
        "crash protection: worst fall rose from 17.8% to 41-47% as the zone widened from 10% to "
        "20%, and no arm cleared the luck bar (best DSR 0.638 against 0.90). Every M0115 zone was "
        "a fixed width chosen once, whether the market was calm or already swinging hard. This "
        "method sizes the zone and its taper from the shadow book's own trailing volatility "
        "instead: the zone is `vol_mult` trailing monthly-return standard deviations of the same "
        "gross shadow index M0109 already reads (clipped to [5%, 45%] so neither a flat run nor a "
        "wild one breaks the dial), and the taper reaches cash `slope_sds` further standard "
        "deviations past the zone. A calm stretch narrows the zone and should restore the "
        "whipsaw-cutting the fixed 15-20% zones could not afford to buy, while a stretch that is "
        "already volatile widens it, which is the stretch M0115's worst falls actually came from. "
        "Everything else is M0109's, unchanged: the 50 most-traded index members at equal weight, "
        "the gross membership-free shadow, the trailing one-year high the drawdown reads against, "
        "the weekly clock, fractional shares at Gotrade's real fees on the owner's monthly "
        "deposits. Arms: VOL2, VOL3, VOL4 (a 2/3/4 trailing-SD zone, each tapering to cash 2 SDs "
        "further out), CTRL (never braked, weekly: the no-opinion arm, a recorded book twin of "
        "M0109-EW-ALL-W), and REPRO-20-40 (the zone and taper pinned at M0115's fixed 20%/40% "
        "configuration, bypassing the volatility read entirely; it must reproduce "
        "M0115-START20-T40's curve exactly and is itself a book twin). Success, pre-registered: a "
        "2009-2015 cost against CTRL under 3 points a year with a worst fall under 25% -- looser "
        "than M0115's implicit half-the-saving bar, because a volatility-scaled zone is not "
        "expected to keep ALL of M0109's crash protection, only enough to be worth what it saves "
        "in calm years. Eligibility would still need a braked book to beat SPY TR on "
        "deposit-matched money with a worst fall under 20% and a majority of folds; the plain book "
        "underneath already trailed SPY in M0109 and M0115, so a pass remains unlikely and the "
        "measurement is the point. The trailing SD is read over only 12 monthly returns by "
        "default, which is a short, noisy window by construction; the analysis checks how much the "
        "zone itself moves around rather than assuming it is stable."
    ),
    expected_failure=(
        "The volatility read may widen the zone at exactly the wrong moment: volatility tends to "
        "rise in the weeks before a crash deepens, not only during it, so a zone sized off trailing "
        "SD could widen just as the real danger increases, letting the brake ignore MORE of a "
        "crash's opening leg than a fixed 15-20% zone would have, which would make the worst fall "
        "deeper than M0115's, not shallower. The second likely failure is noise: a 12-month trailing "
        "SD of a 50-name equal-weight book's monthly returns is estimated from few points and can "
        "itself swing month to month, so the zone could widen and narrow inside a single decline, "
        "trimming and re-entering on the SD's own wobble rather than on anything about the market. "
        "The third is M0115's own finding restated: the base book is a bet against SPY's "
        "big-company shape whatever the brake does, so even a well-behaved vol-sized zone may still "
        "trail SPY TR after 2009, making the brake's cost academic regardless of how it is sized."
    ),
    candidates=(
        _v("VOL2", "2", "2",
           "Dead zone at 2 trailing monthly-return SDs, taper to cash by 4 SDs"),
        _v("VOL3", "3", "2",
           "Dead zone at 3 trailing monthly-return SDs, taper to cash by 5 SDs"),
        _v("VOL4", "4", "2",
           "Dead zone at 4 trailing monthly-return SDs, taper to cash by 6 SDs"),
        _ctrl("CTRL",
              "No-opinion arm: the same book weekly, never braked (book twin of M0109-EW-ALL-W)"),
        _repro("REPRO-20-40", "0.20", "0.40",
               "Reproduction arm: zone and taper pinned at M0115's fixed 20%/40% configuration, "
               "bypassing the volatility read; must equal M0115-START20-T40"),
    ),
    seen_keys=(
        "concept:volatility-scaled-dead-zone",
        "concept:drawdown-brake-dead-zone",
        "concept:own-drawdown-proportional-brake",
    ),
)
