"""M0036 — Frog in the pan: prefer momentum earned in a drizzle over momentum earned in jumps.

Source: Da, Gurun & Warachka (2014), "Frog in the Pan: Continuous Information and Momentum",
Review of Financial Studies 27(7), 2171-2218 (SSRN 1777988).
Idea: the lab has ranked stocks on the LEVEL of past return eleven different ways and has never
once asked HOW that return was earned. The paper's claim is that a limited-attention investor
under-reacts to information that arrives as a long drizzle of small daily moves and over-reacts
to the same cumulative move delivered in a few jumps, so momentum earned smoothly continues
while momentum earned in jumps reverses. The measure needs nothing the store lacks: information
discreteness is

    ID = sign(formation return) x (share of down days - share of up days)

over the formation window, from daily returns alone. Low ID is continuous information; high ID
is discrete. The paper reports six-month momentum profits falling monotonically from 8.86% a
year for the most continuous information to 2.91% for the most discrete, at the same cumulative
formation return.

This method keeps M0032's frame verbatim -- F4's liquidity and membership screen, the SPY-200
trend gate, top-20, monthly, equal weights, fractional shares at Gotrade's real fees on
``monthly-hold-frac-gotrade`` -- and changes only how the twenty names are chosen. On data date d:

    * the base score is either F4's 12-1 total momentum (``base="momentum"``) or M0007-N20-RAW's
      raw cumulative market-model residual (``base="residual"``, the lab's best ranking key);
    * the ``pool`` highest base scores are the winners, as F4's ``mom_lowvol`` does its first cut;
    * ``mode="continuous"`` then holds the ``top`` most continuous of that pool,
      ``mode="discrete"`` holds the ``top`` most discrete -- the paper's mirror, the control that
      makes the other two mean something -- and ``mode="blend"`` skips the pool and ranks the whole
      eligible set on the sum of its base rank and its continuity rank.

Information discreteness is measured over the same window the momentum is: the ``fip_n`` sessions
ending ``skip`` sessions before d, on the market symbol's own calendar, with a day counted only
when the stock has back-to-back bars (the ``ReturnGrid`` M0007 already builds). A name needs 80%
of the window before it is scored. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    ResidParams,
    ResidPrepared,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 9)
MIN_FRAC = 0.8  # a formation window needs this share of usable daily returns before a name is scored

Mode = Literal["continuous", "discrete", "blend"]
Base = Literal["momentum", "residual"]
_MODES: tuple[str, ...] = ("continuous", "discrete", "blend")
_BASES: tuple[str, ...] = ("momentum", "residual")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class FipParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest is the ranking.

    ``inner.rank`` never selects here (this allocator does the choosing); it still fixes the
    eligibility screen and the lookback, so keeping it at ``"momentum"`` makes the candidate
    universe identical to F4-MOM12-N<top>-TREND's and M0007's, name for name.

    ``base="residual"`` builds M0007-N20-RAW's parameters from ``inner`` (18-month market model,
    12-month cumulative residual, one month skipped, unscaled), so the residual variants rank on
    exactly the key the lab's best dev book ranks on.
    """

    inner: FactorParams
    mode: Mode = "continuous"
    base: Base = "momentum"
    pool: int = 40  # the base-score winners the continuity sort runs inside ("blend" ignores it)
    fip_n: int = 252  # sessions the formation window spans (12 months)
    skip: int = 21  # sessions skipped before d (the "-1" of 12-1)
    market: str = "SPY"  # the calendar the daily returns are laid on

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name, allowed in (("mode", _MODES), ("base", _BASES)):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a str, got {type(value).__name__}")
            if value not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, got {value!r}")
        for name in ("pool", "fip_n", "skip"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if self.pool < self.inner.top:
            raise ValueError(f"pool must be >= inner.top, got pool={self.pool} top={self.inner.top}")
        if self.fip_n < 20:
            raise ValueError(f"fip_n must be >= 20, got {self.fip_n}")
        if self.skip < 0:
            raise ValueError(f"skip must be >= 0, got {self.skip}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def resid(self) -> ResidParams:
        """M0007-N20-RAW's ranking parameters on this method's screen (``base='residual'`` only)."""
        return ResidParams(self.inner, scaled=False, market=self.market)

    def as_dict(self) -> dict[str, str]:
        out = {
            "mode": self.mode,
            "base": self.base,
            "pool": str(self.pool),
            "fip_n": str(self.fip_n),
            "skip": str(self.skip),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> FipParams:
    if not isinstance(params, FipParams):
        raise TypeError(f"params must be FipParams, got {type(params).__name__}")
    return params


def fip_lookback(params: FipParams) -> int:
    """Bars through d the decision needs: the screen's, the formation window's, the residual's."""
    need = max(factor_lookback(params.inner), params.skip + params.fip_n + 2)
    if params.base == "residual":
        need = max(need, resid_lookback(params.resid()))
    return need


# --------------------------------------------------------------------------- continuity


def continuity_scores(
    grid: ReturnGrid, symbols: list[str], data_date: date, params: FipParams
) -> dict[str, float]:
    """Each symbol's continuity (minus information discreteness) on ``data_date``.

    Higher is more continuous: the formation return was earned as a drizzle of small daily moves
    rather than in a few jumps. Absent = the name has too little of the window to be scored.
    Reads only calendar columns at or before ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return {}
    end = j - params.skip
    f0 = end - params.fip_n + 1
    if end < 0 or f0 < 0:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)

    r = grid.rets[idx, f0 : end + 1]
    ok = np.isfinite(r)
    m = ok.sum(axis=1)
    enough = m >= max(3, math.ceil(MIN_FRAC * params.fip_n))

    rz = np.where(ok, r, 0.0)  # a missing day contributes no move and is not counted up or down
    pret = np.prod(1.0 + rz, axis=1) - 1.0
    up = (ok & (r > 0.0)).sum(axis=1)
    down = (ok & (r < 0.0)).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        discreteness = np.sign(pret) * (down - up) / np.where(m > 0, m, 1)
    score = -discreteness

    live = enough & np.isfinite(pret) & np.isfinite(score)
    return {names[k]: float(score[k]) for k in (int(v) for v in np.flatnonzero(live))}


def _base_scores(
    grid: ReturnGrid, rows: list[FactorRow], data_date: date, params: FipParams
) -> dict[str, float]:
    if params.base == "momentum":
        return {r.symbol: r.momentum for r in rows}
    return residual_scores(grid, [r.symbol for r in rows], data_date, params.resid())


def choose(
    rows: list[FactorRow],
    base: Mapping[str, float],
    cont: Mapping[str, float],
    params: FipParams,
) -> list[FactorRow]:
    """The ``inner.top`` rows this method holds, in the order it ranked them."""
    scorable = [r for r in rows if r.symbol in base and r.symbol in cont and r.symbol not in EXCLUDED]
    if not scorable:
        return []
    if params.mode == "blend":
        by_base = {r.symbol: i for i, r in enumerate(
            sorted(scorable, key=lambda r: (base[r.symbol], r.symbol)))}
        by_cont = {r.symbol: i for i, r in enumerate(
            sorted(scorable, key=lambda r: (cont[r.symbol], r.symbol)))}
        ranked = sorted(
            scorable, key=lambda r: (-(by_base[r.symbol] + by_cont[r.symbol]), r.symbol))
        return ranked[: params.inner.top]
    winners = sorted(scorable, key=lambda r: (-base[r.symbol], r.symbol))[: params.pool]
    sign = -1.0 if params.mode == "continuous" else 1.0
    return sorted(winners, key=lambda r: (sign * cont[r.symbol], r.symbol))[: params.inner.top]


def targets_from_rows(chosen: list[FactorRow], params: FipParams) -> tuple[Target, ...]:
    """F4's weighting and pricing applied to the chosen rows, in rank order."""
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


class FrogInThePanAllocator:
    """F4's book, with the winners sorted by how smoothly their momentum was earned.

    Held symbols get no special treatment: the targets are exactly the new top set, so a name
    that falls out of it is signal-exited by the book engine, as in F4 and M0007.
    """

    id = "M0036"

    def lookback(self, params: Any) -> int:
        return fip_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: ReturnGrid | None, data_date: date, params: FipParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        cont = continuity_scores(grid, [r.symbol for r in rows], data_date, params)
        if not cont:
            return ()
        base = _base_scores(grid, rows, data_date, params)
        return targets_from_rows(choose(rows, base, cont, params), params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, p)


FROG = FrogInThePanAllocator()


def _v(suffix: str, params: FipParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0036-{suffix}", family="M0036", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FROG, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0036",
    name="Frog in the pan: prefer momentum earned in a drizzle over momentum earned in jumps",
    family="stock-momentum-attention",
    source_kind="paper",
    source_ref=(
        "Da, Gurun & Warachka (2014), Frog in the Pan: Continuous Information and Momentum, "
        "Review of Financial Studies 27(7), 2171-2218 (SSRN 1777988)"
    ),
    parent_id=None,
    hypothesis=(
        "Da, Gurun and Warachka's frog-in-the-pan result says investors under-react to "
        "information that arrives as a long drizzle of small daily moves and over-react to the "
        "same cumulative move delivered in a few jumps, so momentum earned smoothly continues "
        "while momentum earned in jumps reverses. The measure needs nothing the store lacks: "
        "information discreteness is sign(formation return) times (share of down days minus share "
        "of up days) over the formation window, computed from daily returns alone. In the paper, "
        "six-month momentum profits fall monotonically from 8.86% a year for the most continuous "
        "information to 2.91% for the most discrete at the same cumulative formation return, and "
        "the finding carries a replicated status. The lab has now ranked on the LEVEL of past "
        "return eleven different ways and has never once asked HOW that return was earned, which "
        "makes this the cheapest genuinely new signal available on the data already on disk. "
        "This method keeps M0032's frame -- F4's liquidity and membership screen, the SPY-200 "
        "trend gate, top-20, monthly, equal weights, fractional shares at Gotrade's real fees on "
        "monthly-hold-frac-gotrade, funded 5,000,000 IDR on the 25th of each month -- and changes "
        "only how the twenty names are chosen out of the winners. CONT takes the forty highest "
        "12-1 momentum names and holds the twenty most continuous of them; DISC is the paper's "
        "mirror and holds the twenty most discrete, which the hypothesis says must be the worst "
        "of the set and is the control that makes the others mean anything; BLEND ranks the whole "
        "eligible set on momentum rank plus continuity rank together. RM-CONT and RM-DISC are the "
        "same pair with the pool drawn on M0007-N20-RAW's raw residual momentum instead of total "
        "momentum, which is the lab's best dev ranking key, so the two engines are tested for "
        "whether continuity adds anything on top of the best thing already known. I expect "
        "continuity to show up first in the gains-to-losses ratio and the worst fall rather than "
        "in the return, because its mechanism is fewer reversals among the picks. A smaller worst "
        "fall at the same return is the result that would matter most here, since the worst fall "
        "is the only go-live condition the real-fee residual book fails."
    ),
    expected_failure=(
        "Halving the candidate pool before taking twenty names forces the book down into stocks "
        "ranked 20-40 on momentum, and the momentum given up is worth more than the continuity "
        "bought: CONT lands below the plain book on return without buying back enough of the "
        "worst fall to pay for it. The second way it fails is that the mirror does not separate: "
        "DISC comes in at or above CONT, which would say the lab's universe -- 539 large, liquid, "
        "index-member names with a 20M USD dollar-volume floor -- has had the attention-limited "
        "under-reaction arbitraged out of it, since the paper's effect is strongest in small, "
        "thinly covered stocks and this universe holds none of them. The third is simple "
        "redundancy on the residual side: continuity is partly a volatility measure in disguise "
        "(a name that moves in a drizzle has a low daily spread), so RM-CONT may just re-derive "
        "the low-volatility tilt M0021 already bought, adding a trial and no information."
    ),
    candidates=(
        _v("CONT", FipParams(N20, mode="continuous", base="momentum"),
           "Top-40 by 12-1 momentum, then the 20 most continuous: the paper's winner-continuous book"),
        _v("DISC", FipParams(N20, mode="discrete", base="momentum"),
           "The mirror: the same 40 winners, then the 20 most discrete -- the control, expected worst"),
        _v("BLEND", FipParams(N20, mode="blend", base="momentum"),
           "No pool: rank the whole eligible set on momentum rank plus continuity rank together"),
        _v("RM-CONT", FipParams(N20, mode="continuous", base="residual"),
           "Top-40 by raw residual momentum (M0007-N20-RAW's key), then the 20 most continuous"),
        _v("RM-DISC", FipParams(N20, mode="discrete", base="residual"),
           "The residual mirror: the same 40 residual winners, then the 20 most discrete"),
    ),
    seen_keys=(
        "concept:frog-in-the-pan",
        "concept:information-discreteness",
        "concept:momentum-path-continuity",
        "doi:10.1093/rfs/hhu003",
    ),
)
