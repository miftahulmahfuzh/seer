"""M0210 — Paper gains beyond the price rise: the overhang that twelve-month return cannot explain.

Source: variation of M0208 (Grinblatt & Han, 2005, *Prospect theory, mental accounting, and
momentum*, Journal of Financial Economics 78(2), 311-339).

Why this exists. M0208 built the paper's **capital-gains overhang** -- how far a stock trades above
the turnover-weighted average price its holders paid -- and held the twenty largest. It came out
dev-eligible and was then refused by the hard gate on kin (hardgate D14): with the market's share
taken out, its monthly return moved with the test-failed momentum book M0002-REL-85 at 0.90
residual correlation. That is exactly what Grinblatt and Han predict in reverse. They argue the
overhang *subsumes* momentum; in this store the two are so close that the overhang book simply is
the momentum book. M0208's analysis ended by naming the one question momentum cannot answer:
**among stocks whose twelve-month return is the same, does a bigger overhang still win?**

This method asks that question. On each decision date, across the screened members that have an
overhang, the overhang is regressed on twelve-month-minus-one-month return and on its square, and
the book ranks on what is left over -- the residual. By construction the residual is uncorrelated
with 12-1 return in the cross-section (and with its square), so a stock gets in by having paper
gains that its own price rise does **not** account for: a quiet, heavily-traded name whose holders
bought in recently and high, rather than a name that has simply run.

Measured before the run on the dev store (the pool and the fit the method will see): the
overhang-scored pool is 0 names in January 1996 (three years of weekly history is not there yet),
then 80 to 395 names at every quarter-end from April 1996 to the window's close, and the
cross-sectional correlation between overhang and 12-1 return runs +0.19 to +0.82 with a middle
near +0.63. So the linear part of momentum explains roughly 40% of the overhang's cross-sectional
variance and about 60% survives the regression. There is something left to rank on; whether it
pays is what the run answers.

The overhang itself is M0208's, imported rather than re-implemented so the two methods rank on
literally the same number: weeks are five-session blocks ending at the data date, a name needs 156
to 260 clean weeks, the reference price is the paper's turnover-survival weighted average of past
weekly closes, overhang = 1 - reference/price, and turnover is proxied as 2% a week times the
week's volume over the name's own average weekly volume (the store has no share counts). That
proxy's limits are M0208's and are inherited whole.

The fit, written down before the run:

    * the cross-section is the screened names that have both an overhang and a finite 12-1 return
      on the date, sorted by symbol (so the arrays are built in one fixed order);
    * fewer than ``MIN_NAMES`` (50) of them and nothing is scored: the book holds SPY that month.
      The measured pool never falls below 80 after March 1996, so this guard fires only in the
      window's first quarter;
    * 12-1 return is winsorised at the cross-section's 5th and 95th percentiles and then
      standardised to mean 0, standard deviation 1. **Assumption:** raw 12-1 returns reach several
      hundred percent in 1999 and -90% in 2001, and squaring those makes the quadratic term a
      single-stock dummy. Winsorising and standardising keeps the fit about the body of the
      cross-section instead of its two tails. It is a monotone rescaling, so "the part momentum
      explains" still means the same thing;
    * least squares of overhang on (1, z, z^2) -- or (1, z) when ``degree`` is 1 -- and the score
      is the residual. Higher is better.

``signal``: ``"resid"`` holds the largest residuals; ``"low"`` the most negative (the contrast --
stocks whose overhang is *smaller* than their price rise implies, which should trail if the
disposition effect is real); ``"hash"`` is M0187's same-frame placebo, the identical pool, band,
slots, fill and switch in a fixed blake2b order.

The frame is M0208's exactly, so the comparison is about the signal and nothing else: F4's screen
and SPY 200-day switch, M0203's band (a held name stays while it ranks inside ``keep``), free slots
filled from the top, unfilled slots in SPY, equal 1/top slots, fractional shares at Gotrade's real
fees (``monthly-hold-frac-gotrade``) on the owner's monthly deposits.

Assumption, written before the run: no plain-momentum variant is registered, for M0203's and
M0208's reason -- the hard gate's behaviour test reads every dev variant, and one momentum arm
would tie the whole method to the test-failed momentum books. Momentum is compared in the analysis
against the lab's recorded real-fee momentum books instead.

Pure: no clock, randomness, files or network; reads only columns dated at or before ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0208_capital_gains_overhang import (
    MIN_WEEKS,
    RATE,
    TAU_MAX,
    WEEK,
    WEEKS,
    WeekGrid,
    build_week_grid,
    choose,
    draw,
    overhangs,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
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

ADDED = date(2026, 10, 19)
MIN_NAMES = 50  # smallest cross-section the regression is trusted on; measured pool is 80-395
WINSOR = 5.0  # percent clipped off each tail of 12-1 return before the fit
SIGNALS = ("resid", "low", "hash")
DEGREES = (1, 2)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ResidualOverhangParams:
    """``inner`` is F4's screen, switch and book size; the rest is the fit, the signal and the band.

    ``inner.rank`` never selects here; ``"momentum"`` keeps the screened universe identical to
    M0208's, M0203's and M0007's, name for name -- and it is also where the 12-1 return the
    regression removes is read from, so the method's own ranking and the thing it controls for
    come from one computation.
    """

    inner: FactorParams
    keep: int = 40
    signal: str = "resid"
    degree: int = 2
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("keep", "degree", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.keep < self.inner.top:
            raise ValueError(f"keep must be >= top, got {self.keep} < {self.inner.top}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if self.degree not in DEGREES:
            raise ValueError(f"degree must be one of {DEGREES}, got {self.degree}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"keep": str(self.keep), "signal": self.signal, "degree": str(self.degree),
               "seed": str(self.seed), "market": self.market, "week": str(WEEK),
               "weeks": str(WEEKS), "min_weeks": str(MIN_WEEKS), "rate": repr(RATE),
               "tau_max": repr(TAU_MAX), "min_names": str(MIN_NAMES), "winsor": repr(WINSOR)}
        if self.signal == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ResidualOverhangParams:
    if not isinstance(params, ResidualOverhangParams):
        raise TypeError(f"params must be ResidualOverhangParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def residual_overhangs(grid: WeekGrid, rows: list[FactorRow], data_date: date,
                       market: str, degree: int) -> dict[str, float]:
    """The part of each name's overhang that its 12-1 return does not explain, on ``data_date``.

    The cross-section is built in symbol order, so the arrays -- and therefore the least-squares
    solution and every residual -- are the same however the caller reached this date.
    """
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != market)
    g = overhangs(grid, pool, data_date)
    if not g:
        return {}
    mom = {r.symbol: r.momentum for r in rows}
    names = [s for s in pool if s in g and np.isfinite(mom.get(s, np.nan))]
    if len(names) < MIN_NAMES:
        return {}
    y = np.asarray([g[s] for s in names], dtype=np.float64)
    m = np.asarray([mom[s] for s in names], dtype=np.float64)
    lo, hi = np.percentile(m, [WINSOR, 100.0 - WINSOR])
    m = np.clip(m, lo, hi)
    sd = float(m.std())
    if not sd > 0.0:
        return {}
    z = (m - float(m.mean())) / sd
    cols = [np.ones_like(z), z] + ([z * z] if degree == 2 else [])
    design = np.column_stack(cols)
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    if not np.all(np.isfinite(resid)):
        return {}
    return {s: float(v) for s, v in zip(names, resid.tolist(), strict=True)}


def scored(grid: WeekGrid, rows: list[FactorRow], data_date: date,
           p: ResidualOverhangParams) -> dict[str, float]:
    """Higher is better. The contrast flips the order; the placebo keeps the pool, not the order."""
    e = residual_overhangs(grid, rows, data_date, p.market, p.degree)
    if p.signal == "resid":
        return e
    if p.signal == "low":
        return {s: -v for s, v in e.items()}
    return {s: -float(draw(p.seed, s, data_date)) for s in e}


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class ResidualPrepared:
    """F4's rolling columns plus one weekly grid per market symbol, built on first use."""

    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    grids: dict[str, WeekGrid | None] = field(default_factory=dict, repr=False)

    def grid(self, market: str) -> WeekGrid | None:
        if market not in self.grids:
            self.grids[market] = build_week_grid(self.history, market)
        return self.grids[market]


class ResidualOverhangAllocator:
    """The ``top`` largest momentum-free capital-gains overhangs among screened members, banded."""

    id = "M0210"

    def lookback(self, params: Any) -> int:
        # The screen's and the switch's need, as M0208: a name short of weekly history is simply
        # not scored, and its slot holds SPY.
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: WeekGrid | None, data_date: date, held: frozenset[str],
                 p: ResidualOverhangParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        sc = scored(grid, rows, data_date, p)
        return choose(history, rows, sc, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_week_grid(history, p.market), data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ResidualPrepared:
        return ResidualPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidualPrepared):
            raise TypeError(f"prepared must be ResidualPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, held, p)


RESIDUAL = ResidualOverhangAllocator()

TREND = ("SPY", 200)
N20 = FactorParams(rank="momentum", top=20, trend=TREND)
N40 = FactorParams(rank="momentum", top=40, trend=TREND)


def _v(suffix: str, params: ResidualOverhangParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0210-{suffix}", family="M0210", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=RESIDUAL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0210",
    name=("Paper gains beyond the price rise: rank on the part of the capital-gains overhang that "
          "twelve-month return does not explain"),
    family="stock-capital-gains-overhang-residual",
    source_kind="variation",
    source_ref="M0208",
    parent_id="M0208",
    hypothesis=(
        "Grinblatt and Han (2005) say the capital-gains overhang subsumes momentum; M0208 built "
        "the overhang book and found it moves with the test-failed momentum book at 0.90 residual "
        "correlation, so in this store the two are the same bet. Test the part momentum cannot "
        "see. On each decision date, across the screened members that have an overhang, regress "
        "the overhang on 12-1 month return and on its square (the return winsorised at the "
        "cross-section's 5th and 95th percentiles, then standardised; at least 50 names or "
        "nothing is scored) and rank on the residual, so a stock gets in by having paper gains "
        "its own price rise does not account for. Hold the top 20 in equal 5% slots, monthly, in "
        "M0208's frame exactly: F4's screen, the SPY 200-day switch, a held name kept while it "
        "ranks inside the top 40, unfilled slots in SPY, fractional shares at Gotrade's real fees "
        "on the owner's monthly top-up. Measured before the run: the scored pool is 80 to 395 "
        "names from April 1996 on and the overhang's cross-sectional correlation with 12-1 return "
        "is about +0.63, so roughly 60% of the overhang's spread survives the regression. Arms: "
        "RESID-N40 (40 names, band 80), RESID-LIN-N20 (linear fit only, no square) and "
        "RESID-LOW-N20 (the most negative residuals, which should trail). Control: HASH-N20, the "
        "same pool, band, slots, fill and switch in a fixed hash order. Success: beats the "
        "placebo by at least 2 points a year, residual correlation with the momentum books under "
        "0.85 so the hard gate's behaviour test lets it through, a positive lead over SPY in "
        "2009-2015, beats SPY TR on dev with worst fall <= 25% and PF >= 1.3, and a majority of "
        "walk-forward folds. If it fails, the disposition-effect family is closed in this data."
    ),
    expected_failure=(
        "The regression removes the part of the overhang that momentum explains, and that part "
        "may be the part that pays: the overhang's power in this store could be nothing but a "
        "slower, smoother reading of the price rise, in which case the residual book earns little "
        "and may not beat the placebo at all. Residuals are also where measurement error "
        "concentrates -- the turnover proxy gives every name the same average turnover, so a "
        "stock whose reference price is wrong for a data reason, not a behavioural one, lands "
        "high in the residual ranking; the book may end up holding the names whose cost basis the "
        "proxy mis-estimates. A stock with a big overhang and a flat twelve-month return has "
        "usually risen over two to five years and gone quiet lately, which is the long-term "
        "winner the long-term-reversal work says reverses, so the book may lean into names that "
        "mean-revert. Even if the behaviour test clears 0.85, the method still has to beat SPY in "
        "2009-2015, where every equal-slot book in this lab has lost to SPY's big-company drift "
        "(insight 91), and a published anomaly fades (insight on M0050): Grinblatt and Han was a "
        "2001 working paper, so only the window's first half predates the crowd. Finally the "
        "residual is a small number -- the overhang's spread is wide but its momentum-free part "
        "is narrow -- so the top 20 may be separated from the next 20 by noise, which would show "
        "up as high turnover and a result close to the placebo's."
    ),
    candidates=(
        _v("RESID-N20", ResidualOverhangParams(N20, keep=40),
           "20 largest momentum-free overhangs, held while inside the top 40, behind the SPY "
           "200-day switch"),
        _v("RESID-N40", ResidualOverhangParams(N40, keep=80),
           "Same signal, 40 names, band 80: width, as M0208 ran it"),
        _v("RESID-LIN-N20", ResidualOverhangParams(N20, keep=40, degree=1),
           "Linear fit only: does the squared return term change what is left over?"),
        _v("RESID-LOW-N20", ResidualOverhangParams(N20, keep=40, signal="low"),
           "Contrast: the most negative residuals in the same frame; these should trail"),
        _v("HASH-N20", ResidualOverhangParams(N20, keep=40, signal="hash"),
           "Placebo: the same pool, band, slots and switch in a fixed hash order"),
    ),
    seen_keys=(
        "concept:momentum-free-capital-gains-overhang",
        "concept:cross-sectional-residual-ranking",
        "concept:disposition-effect-orthogonalised",
    ),
)
