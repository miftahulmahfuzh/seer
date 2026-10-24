"""M0055 — Buy the dip inside the winners: last year's strongest stocks, entered after a bad month.

Source: variation of M0028 (the short-term bounce book); Jegadeesh & Titman (1993), Returns to
buying winners and selling losers, J. Finance 48(1); Jegadeesh (1990), J. Finance 45(3).
Idea: classic 12-1 momentum skips the latest month because recent winners and losers partly
reverse. M0028 tried the reversal on its own and got about SPY's return. Here the pool is the 60
screened names with the best plain 12-1 momentum, and inside it the book holds the ``pick`` whose
last month was worst against the market, so the entry is a pullback in a stock the market has
liked for a year rather than a faller that was already weak.

On data date d, behind F4's screen and SPY-200 gate:

    * the ``pool`` names with the highest plain 12-1 total momentum (not residual) are kept;
    * each is scored by its last-month return, raw or net of beta times SPY (M0028's
      ``reversal_scores``, calm and uptrend filters off);
    * ``side="dip"`` holds the ``pick`` most negative scores, ``side="strength"`` the most
      positive (the mirror); equal weight, held a month.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.lab.methods.m0028_short_term_reversal import RevParams, reversal_scores
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    rank_rows,
    trend_on,
)

ADDED = date(2026, 10, 24)

Side = Literal["dip", "strength"]


@dataclass(frozen=True, slots=True)
class PullParams:
    """``inner`` is F4's screen, gate, book size (``top`` = names held) and weighting."""

    inner: FactorParams
    pool: int = 60  # strongest 12-1 names the month's move is read inside
    signal: Literal["residual", "raw"] = "residual"
    side: Side = "dip"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.pool, bool) or not isinstance(self.pool, int) or self.pool < self.inner.top:
            raise ValueError(f"pool must be an int >= inner.top, got {self.pool!r}")
        if self.side not in ("dip", "strength"):
            raise ValueError(f"side must be dip or strength, got {self.side!r}")

    @property
    def rev(self) -> RevParams:
        return RevParams(self.inner, signal=self.signal, calm_frac=Decimal("1"), sma_n=None)

    def as_dict(self) -> dict[str, str]:
        out = {"pool": str(self.pool), "signal": self.signal, "side": self.side}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PullParams:
    if not isinstance(params, PullParams):
        raise TypeError(f"params must be PullParams, got {type(params).__name__}")
    return params


class MomentumPullbackAllocator:
    """The month's worst (or best) ``top`` names inside the strongest-12-1 pool, held a month."""

    id = "M0055"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.rev.beta_n + p.rev.rev_n + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.rev.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, rows: list[FactorRow], grid: ReturnGrid | None, data_date: date,
                 p: PullParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        screened = [r for r in rows if r.symbol not in EXCLUDED]
        pool = rank_rows(screened, FactorParams(rank="momentum", top=p.pool, trend=p.inner.trend))
        scores = reversal_scores(grid, [r.symbol for r in pool], data_date, p.rev)
        scorable = [r for r in pool if r.symbol in scores]
        sign = 1.0 if p.side == "dip" else -1.0
        chosen = sorted(scorable, key=lambda r: (sign * scores[r.symbol], r.symbol))[: p.inner.top]
        out: list[Target] = []
        for row, weight in zip(chosen, factor_weights(chosen, p.inner), strict=True):
            if weight is None:
                continue
            target = target_from_close(row.symbol, row.close, weight)
            if target is not None:
                out.append(target)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(rows, build_grid(history, p.rev.market), data_date, p)

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
        return self._targets(rows, prepared.grid(p.rev.market), data_date, p)


PULLBACK = MomentumPullbackAllocator()


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0055-{suffix}", family="M0055", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0055",
    name="Buy the dip inside the winners: last year's strongest stocks, entered after a bad month",
    family="stock-short-term-reversal",
    source_kind="variation",
    source_ref=(
        "Variation of M0028; Jegadeesh & Titman (1993), J. Finance 48(1); Jegadeesh (1990), "
        "J. Finance 45(3)"
    ),
    parent_id="M0028",
    hypothesis=(
        "The bounce book (M0028) showed a one-month fall is worth little as a stand-alone signal "
        "(about SPY's return, a 27% worst fall), but classic 12-1 momentum skips the latest month "
        "precisely because recent losers bounce. Among the 60 names with the best plain 12-1 "
        "total momentum (not residual, so the family is not the test-failed residual one), hold "
        "the 20 with the worst last-month return relative to the market, equal weight, behind the "
        "SPY-200 gate, fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade with "
        "the monthly top-up. Reversal in a pool the market has liked for a year was published as "
        "separate anomalies (1990, 1993) and has faded since; the dev window ends in 2015 and can "
        "show only the pre-crowd edge. Arms: DIP-RESID (the idea); DIP-RAW (does removing the "
        "market's move matter?); DIP-POOL40 (a gentler pool: 40 names, does the pool size "
        "matter?); MIRROR-RESID (the 20 with the BEST last month in the same pool, which would "
        "reverse the idea if the dip is the signal); the no-opinion control is the plain top-20 12-1 "
        "momentum book behind the same gate, which the lab already holds as M0332-M12-1 (same "
        "configuration, so the lab refuses to run it twice; it is read from that recorded trial, "
        "not re-run, and prices the habit so the dip and the mirror can be read against it). "
        "Success: DIP-RESID beats M0332-M12-1 on worst fall at similar return, beats MIRROR-RESID on return, beats SPY in 2009-2015, "
        "and wins a majority of walk-forward folds. If DIP-RESID and MIRROR-RESID land within the "
        "gap that the plain momentum control explains, the month's move carries no information and the verdict is "
        "that the pool, not the dip, does the work."
    ),
    expected_failure=(
        "The pullback pushes the book down into the weaker momentum names, so it is a milder "
        "momentum book with more turnover, and the 2009 junk rally hits it as it hit the parent. "
        "At Gotrade's real fees a monthly 20-name turnover costs several tenths of a percent a "
        "side on small slots and eats the reversal premium. MIRROR-RESID may do as well as "
        "DIP-RESID, which would mean the pool is the whole story. Because both reversal and "
        "momentum are widely published, a dev edge from before 2009 is likely to fade."
    ),
    candidates=(
        _v("DIP-RESID", PULLBACK, PullParams(N20),
           "Idea: 20 worst last-month residual returns inside the 60 strongest 12-1 names"),
        _v("DIP-RAW", PULLBACK, PullParams(N20, signal="raw"),
           "Same pool, ranked on the plain last-month return: does removing the market matter?"),
        _v("DIP-POOL40", PULLBACK, PullParams(N20, pool=40),
           "Pool of 40 instead of 60: a stronger-momentum pool, a milder dip"),
        _v("MIRROR-RESID", PULLBACK, PullParams(N20, side="strength"),
           "Mirror control: the 20 BEST last-month residual returns inside the same pool"),
    ),
    seen_keys=(
        "concept:momentum-pullback",
        "concept:dip-inside-winners",
        "concept:short-term-reversal",
    ),
)
