"""M0116 — Slow to sell, fast to buy back: an asymmetric fall brake.

Source: variation on M0109 (the proportional own-drawdown brake; Black & Perold 1992 CPPI,
Grossman & Zhou 1993 reduced to a dial). Idea: M0109's brake cut the worst fall from about 50%
to 17% and paid for it in the recoveries, because exposure comes back on the same dial that
governs the exit, so money returns only as the shadow book climbs toward its own one-year high.
This method keeps the exit exactly as M0109 had it and gives the re-entry its own, faster dial.

THE BOOK, THE SHADOW AND THE EXIT ARE M0109'S, UNCHANGED. The 50 most-traded index members at
equal weight, the gross membership-free shadow index rebuilt from bars, the trailing one-year
high, the weekly clock, the 20% straight-line taper to cash and every other constant are imported
from M0109 rather than copied. ``BrakeParams`` cannot gain a field without moving M0109's
digests, so ``AsymParams`` subclasses it and carries the recovery dial; the allocator has its
own id, ``M0116``.

THE RECOVERY DIAL. ``taper(dd)`` is M0109's exposure at the shadow's drawdown ``dd``. Walk the
shadow's calendar session by session with a latch:

  * the latch SETS when the shadow closes above its own highest close of the previous ``rec_n``
    sessions while ``taper`` is still below 1 (a rally has outrun the last ``rec_n`` sessions);
  * while set, exposure is 1 (REC variants) or ``max(taper, 0.5)`` (the HALF variant, which
    reaches full only when the shadow is back at its year-high, where ``taper`` is 1 anyway);
  * the latch CLEARS when ``taper`` is 1 again (nothing left to override), or when the shadow
    closes below its lowest close of the previous ``rec_n`` sessions (the rally failed).
    The clearing rule reads the same window as the setting rule on purpose, so the fast re-entry
    adds one dial (``rec_n``) and no other.
  * unlatched, exposure is ``taper(dd)`` exactly: the exit is untouched.

The latch is a pure function of the shadow's bars up to the session, so a history cut at any
date gives the same exposure as the whole history. The brake stands down before ``WARM`` sessions
exactly as in M0109.

THE ARMS (all weekly, fractional shares, Gotrade real fees; M0109's preset). REC63, REC42 and
REC21 are the dose ladder on ``rec_n``; HALF42 is the half-step version at 42. CTRL is M0109's
symmetric 20% taper (``rec_n`` unset) reproduced under this wrapper: a declared control, and a
book twin of M0109-TAPER-20-W when the store is the one that trial ran on. The never-braked book
is M0109-EW-ALL-W's (trial 354) and is cited, not re-run. If any REC arm shares CTRL's curve the
latch never fired, and the analysis says so.
Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import ReturnGrid, build_grid
from seer_engine.lab.methods.m0109_book_drawdown_brake import (
    ONE,
    WARM,
    WEEKLY,
    BrakeParams,
    BrakePrepared,
    DrawdownBrake,
    book_rows,
    book_targets,
    braked,
    chosen,
    exposure,
    prepared_rows,
    shadow_wealth,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import prepare_factor

ADDED = date(2026, 11, 13)
HALF = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class AsymParams(BrakeParams):
    """M0109's book and 20% taper plus the fast re-entry window (None = M0109's symmetric dial)."""

    rec_n: int | None = None  # sessions of the recovery / failed-rally window
    half_step: bool = False  # latched exposure is max(taper, 0.5) instead of 1

    def __post_init__(self) -> None:
        BrakeParams.__post_init__(self)
        if self.rec_n is not None and (
            isinstance(self.rec_n, bool) or not isinstance(self.rec_n, int)
            or not 2 <= self.rec_n < WARM
        ):
            raise ValueError(f"rec_n must be None or an int in 2..{WARM - 1}, got {self.rec_n!r}")
        if not isinstance(self.half_step, bool):
            raise TypeError(f"half_step must be a bool, got {self.half_step!r}")

    def as_dict(self) -> dict[str, str]:
        out = BrakeParams.as_dict(self)
        out["rec_n"] = "none" if self.rec_n is None else str(self.rec_n)
        out["half_step"] = str(self.half_step)
        return out


def _check(params: object) -> AsymParams:
    if not isinstance(params, AsymParams):
        raise TypeError(f"params must be AsymParams, got {type(params).__name__}")
    return params


def exposure_series(wealth: np.ndarray, p: AsymParams) -> list[Decimal]:
    """The brake's exposure at every session of ``wealth`` (causal: entry j reads wealth[:j+1])."""
    n = len(wealth)
    out = [ONE] * n
    latch = False
    for j in range(n):
        if j + 1 < WARM:
            continue
        peak = float(np.max(wealth[max(0, j - p.peak_n + 1) : j + 1]))
        here = float(wealth[j])
        if not (np.isfinite(peak) and np.isfinite(here)) or peak <= 0.0:
            continue
        taper = exposure(1.0 - here / peak, p)
        if p.rec_n is None:
            out[j] = taper
            continue
        if taper >= ONE:
            latch = False
        else:
            prior = wealth[j - p.rec_n : j]
            if latch and here < float(np.min(prior)):
                latch = False
            elif not latch and here > float(np.max(prior)):
                latch = True
        if latch and taper < ONE:
            out[j] = max(taper, HALF) if p.half_step else ONE
        else:
            out[j] = taper
    return out


def exposure_on(grid: ReturnGrid | None, series: list[Decimal] | None, data_date: date) -> Decimal:
    """The exposure at ``data_date`` (1 when it is not a session of the shadow's calendar)."""
    if grid is None or series is None:
        return ONE
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return ONE
    return series[j]


@dataclass
class AsymPrepared(BrakePrepared):
    """M0109's prepared state plus one exposure series per distinct brake setting."""

    series_cache: dict[tuple[Any, ...], list[Decimal]] = field(default_factory=dict, repr=False)


class AsymmetricBrake(DrawdownBrake):
    """M0109's book and shadow with a fast re-entry latch on top of the same taper."""

    id = "M0116"

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
        return braked(base, exposure_on(grid, exposure_series(wealth, p), data_date))

    def prepare(self, history: Mapping[str, History]) -> AsymPrepared:
        return AsymPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, AsymPrepared):
            raise TypeError(f"prepared must be AsymPrepared, got {type(prepared).__name__}")
        p = _check(params)
        base = book_targets(prepared_rows(prepared.factor, members, data_date, p), p)
        if not base or p.taper is None:
            return base
        grid, wealth = prepared.shadow(p)
        if grid is None or wealth is None:
            return base
        key = (p.market, p.top, p.min_dollar_volume, p.min_price, p.taper, p.floor, p.peak_n,
               p.rec_n, p.half_step)
        series = prepared.series_cache.get(key)
        if series is None:
            series = exposure_series(wealth, p)
            prepared.series_cache[key] = series
        return braked(base, exposure_on(grid, series, data_date))


ASYM = AsymmetricBrake()


def _v(suffix: str, rec_n: int | None, half: bool, rationale: str) -> Candidate:
    params = AsymParams(taper=Decimal("0.20"), rec_n=rec_n, half_step=half)
    return Candidate(id=f"M0116-{suffix}", family="M0116", rules=WEEKLY, allocator=ASYM,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0116",
    name="Slow to sell, fast to buy back: an asymmetric fall brake",
    family="book-drawdown-brake",
    source_kind="variation",
    source_ref="M0109 (the proportional own-drawdown brake), with a separate faster re-entry reading",
    parent_id="M0109",
    hypothesis=(
        "M0109's cost is almost entirely re-entry, not exit. Its 20% taper's worst stretch ran from "
        "October 2007 to a trough in June 2010 -- sixteen months after the unbraked book had "
        "bottomed in February 2009 -- because exposure is restored on the same dial that governs "
        "the exit, so the money only comes back as the book climbs toward its own one-year high, "
        "which takes months of a rally. Being late to sell costs little: by the time a book is 10% "
        "down the first half of the fall is already paid. Being late to buy costs a great deal and "
        "costs it on every dip that bounces. The trim here is M0109's straight-line 20% taper, "
        "unchanged, but exposure is restored on a separate, faster reading: the shadow book "
        "closing above its own highest close of the last rec_n sessions (63, 42 or 21) sets a "
        "latch that returns exposure to full, and the latch clears when the shadow closes below "
        "its lowest close of the last rec_n sessions or is back at its year-high. HALF42 restores "
        "only to half exposure on the latch and to full at the year-high. Arms: REC63, REC42, "
        "REC21, HALF42, and CTRL (M0109's symmetric 20% taper reproduced under this wrapper, "
        "declared as a control: a recorded trial's returns are not reproducible across store "
        "rebuilds, so the reproduction is the fair baseline and doubles as a check that the new "
        "exposure function equals M0109's when the latch is off; it should be a book twin of "
        "M0109-TAPER-20-W, trial 355). The never-braked book is M0109-EW-ALL-W, trial 354, cited "
        "and not re-run: it prices the whole habit (what braking costs against never braking) "
        "and CTRL prices the symmetric brake, so the split M0109 could not make is CTRL minus "
        "REC (what the slow re-entry cost) against EW-ALL-W minus CTRL (what the brake cost). "
        "Weekly clock, fractional shares, Gotrade real fees, as M0109. Assumptions recorded before "
        "any result: the clearing rule reads the same window as the setting rule so the re-entry "
        "adds one dial and no more; the exit is untouched while the latch is off; the half-step "
        "is run at 42 only. Success is a measurement: how much of M0109's roughly 10 points a "
        "year given up in 2009-2015 comes back, and how much of the worst-fall saving is kept. "
        "Eligibility would need beating SPY TR with a worst fall under 20% and a majority of "
        "folds; M0109's base book already trailed SPY, so that is unlikely and not the point."
    ),
    expected_failure=(
        "A fast re-entry reading is a momentum signal in disguise and will buy back into the false "
        "rallies of 2001 and late 2008, giving back the saving that justified the brake: the worst "
        "fall comes out well above M0109's 17%, most likely in the 25-35% range at REC21 and less "
        "at REC63. The shadow's rebounds in 2008-2009 were violent and a 21-session new high "
        "arrives within weeks of a trough, so the shorter windows may be bought into the next leg "
        "down. A second failure is that the latch never fires in the fast-recovery years it was "
        "built for because the shadow is still below its one-year high but also below its own "
        "63-session high for months; then REC63 shares CTRL's curve and the dose ladder is one "
        "rung. Published-anomaly caveat: CPPI-style brakes are textbook since the 1990s and the "
        "dev window cannot show an edge from after the crowd traded it; the 2009-2015 era, with "
        "no real bear, is where a faster re-entry should help and so is the first filter."
    ),
    candidates=(
        _v("REC63", 63, False,
           "Re-enter at full exposure once the shadow closes above its highest close of 63 sessions"),
        _v("REC42", 42, False,
           "Same, 42-session window (about two months)"),
        _v("REC21", 21, False,
           "Same, 21-session window (about one month): the fastest re-entry"),
        _v("HALF42", 42, True,
           "Half-step: the 42-session signal restores to half exposure, full only at the year-high"),
        _v("CTRL", None, False,
           "Control: M0109-TAPER-20-W's book (symmetric 20% taper) reproduced under this wrapper"),
    ),
    seen_keys=(
        "concept:asymmetric-brake-fast-reentry",
        "concept:own-drawdown-proportional-brake",
    ),
)
