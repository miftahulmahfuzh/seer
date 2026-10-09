"""M0057 — Short-term momentum: last month's winners among the most heavily traded stocks keep going.

Source: Medhat & Schmeling (2022), Short-term Momentum, Review of Financial Studies 35(3).
Idea: the one-month reversal everyone knows is an average of two opposite effects. Among stocks
with low share turnover last month's return reverses (liquidity provision), but among stocks with
high turnover it continues: heavy trading marks a stock the market is repricing on news, and the
repricing is not finished in a month. The store has no share counts before 2009, so turnover is
proxied by abnormal volume -- a stock's own recent volume against its own past year.

On data date d, inside F4's liquidity and membership screen and behind its SPY-200 trend gate:

    * the screened names above their own ``sma_n``-day average are kept (M0028's screen with no
      calm filter);
    * abnormal volume = mean daily share volume over the last ``av_short`` sessions through d,
      divided by the mean over the ``av_long`` sessions before that (volume is split-adjusted in
      the store, so a split does not fake a surge);
    * ``side="high"`` keeps the top ``av_frac`` of the kept names by abnormal volume, ``"low"``
      the bottom ``av_frac`` (the control the paper says reverses), ``"all"`` skips the sort;
    * the ``top`` names with the highest plain return over the last ``rev_n`` sessions are held,
      equal weight, for a month.

Every piece reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N30, ResidPrepared, ReturnGrid, build_grid
from seer_engine.lab.methods.m0028_short_term_reversal import (
    RevParams,
    reversal_scores,
    rev_lookback,
    screen,
    targets_from_scores,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, FactorRow, factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 9)

Side = Literal["high", "low", "all"]
_SIDES: tuple[str, ...] = ("high", "low", "all")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class StmParams:
    """``inner`` is F4's screen, trend gate, book size and weighting; the rest picks the winners."""

    inner: FactorParams
    side: Side = "high"
    av_frac: Decimal = Decimal("0.2")  # share of the kept names in the abnormal-volume bucket
    av_short: int = 21  # sessions in the recent-volume window
    av_long: int = 252  # sessions before it, the stock's own normal volume
    rev_n: int = 21  # sessions in the formation window (one month)
    sma_n: int | None = 200  # keep names above their own sma_n-day average (None = off)
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if not isinstance(self.side, str) or self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if not isinstance(self.av_frac, Decimal):
            raise TypeError(f"av_frac must be a Decimal, got {type(self.av_frac).__name__}")
        if not self.av_frac.is_finite() or not 0 < self.av_frac <= 1:
            raise ValueError(f"av_frac must be in (0, 1], got {self.av_frac}")
        for name in ("av_short", "av_long", "rev_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 5:
                raise ValueError(f"{name} must be an int >= 5, got {v!r}")
        if self.sma_n is not None and (isinstance(self.sma_n, bool) or not isinstance(self.sma_n, int)
                                       or self.sma_n < 2):
            raise ValueError(f"sma_n must be None or an int >= 2, got {self.sma_n!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def rev(self) -> RevParams:
        """M0028's params for the shared pieces: no calm filter, plain return, same SMA."""
        return RevParams(self.inner, signal="raw", rev_n=self.rev_n, calm_frac=Decimal("1"),
                         sma_n=self.sma_n, market=self.market)

    def as_dict(self) -> dict[str, str]:
        out = {
            "side": self.side,
            "av_frac": str(self.av_frac),
            "av_short": str(self.av_short),
            "av_long": str(self.av_long),
            "rev_n": str(self.rev_n),
            "sma_n": "none" if self.sma_n is None else str(self.sma_n),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> StmParams:
    if not isinstance(params, StmParams):
        raise TypeError(f"params must be StmParams, got {type(params).__name__}")
    return params


def stm_lookback(params: StmParams) -> int:
    return max(rev_lookback(params.rev()), params.av_short + params.av_long + 1)


# --------------------------------------------------------------------------- the signal


def abnormal_volume(h: History, data_date: date, params: StmParams) -> float | None:
    """Recent mean share volume over the stock's own prior-year mean, through ``data_date``."""
    i = h.index_of(data_date)
    if i is None or i + 1 < params.av_short + params.av_long:
        return None
    recent = h.volume[i + 1 - params.av_short : i + 1]
    base = h.volume[i + 1 - params.av_short - params.av_long : i + 1 - params.av_short]
    if not (np.all(np.isfinite(recent)) and np.all(np.isfinite(base))):
        return None
    b = float(base.mean())
    if b <= 0.0:
        return None
    return float(recent.mean()) / b


def volume_bucket(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
                  params: StmParams) -> list[FactorRow]:
    """The ``side`` bucket of ``rows`` by abnormal volume (symbol order kept)."""
    if params.side == "all":
        return rows
    av: dict[str, float] = {}
    for r in rows:
        h = history.get(r.symbol)
        v = None if h is None else abnormal_volume(h, data_date, params)
        if v is not None:
            av[r.symbol] = v
    if not av:
        return []
    cut = math.ceil(float(params.av_frac) * len(av))
    sign = -1.0 if params.side == "high" else 1.0
    keep = {s for _, s in sorted((sign * v, s) for s, v in av.items())[:cut]}
    return [r for r in rows if r.symbol in keep]


# --------------------------------------------------------------------------- the allocator


class ShortTermMomentumAllocator:
    """Last month's biggest winners within an abnormal-volume bucket, held for a month.

    Held symbols get no special treatment: the targets are exactly the new set.
    """

    id = "M0057"

    def lookback(self, params: Any) -> int:
        return stm_lookback(_check(params))

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
                 grid: ReturnGrid | None, data_date: date, params: StmParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        rev = params.rev()
        kept = volume_bucket(history, screen(history, rows, data_date, rev), data_date, params)
        if not kept:
            return ()
        scores = reversal_scores(grid, [r.symbol for r in kept], data_date, rev)
        # targets_from_scores takes the most negative first: negate to take the biggest winners
        return targets_from_scores(kept, {s: -v for s, v in scores.items()}, rev)

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


STM = ShortTermMomentumAllocator()


def _v(suffix: str, params: StmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0057-{suffix}", family="M0057", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STM, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0057",
    name="Short-term momentum: last month's winners among the most heavily traded stocks keep going",
    family="stock-short-term-momentum",
    source_kind="paper",
    source_ref="Medhat & Schmeling (2022), Short-term Momentum, Review of Financial Studies 35(3)",
    parent_id=None,
    hypothesis=(
        "Medhat and Schmeling find that last month's return reverses among low-turnover stocks "
        "but continues among high-turnover stocks: the reversal everyone knows hides a "
        "continuation in the stocks the market is actively trading on news. The store has no "
        "share counts before 2009, so turnover is proxied by abnormal volume: the stock's mean "
        "daily share volume over the last 21 sessions divided by its own mean over the 252 before "
        "(volume in the store is split-adjusted). Inside F4's liquidity and membership screen, "
        "behind the SPY-200 trend gate (an assumption carried over from the family the lab "
        "already runs, so the result is comparable with M0028), among names above their own "
        "200-day average, HIGH-N20 takes the top fifth by abnormal volume and holds the 20 with "
        "the highest one-month return, equal weight, monthly, in fractional shares at Gotrade's "
        "real fees (monthly-hold-frac-gotrade). HIGH-N30 holds 30. LOW-N20 is the control: the "
        "same ranking in the bottom fifth by abnormal volume, which the paper says should reverse "
        "and lose. ALL-N20 skips the volume sort (plain one-month winners) to show whether the "
        "volume conditioning adds anything. Success: HIGH beats total-return SPY on dev with a "
        "worst fall under 20%, LOW is clearly worse than HIGH, ALL sits between them, and the "
        "edge survives a majority of walk-forward folds at real fees."
    ),
    expected_failure=(
        "This is a near-100%-a-month churn book, so Gotrade's fees on 15-35 USD slots take "
        "several tenths of a percent each side and may eat a premium the paper measured in "
        "all-CRSP stocks, mostly small ones. Large caps may show little continuation: the paper's "
        "effect is strongest in the top turnover decile of the whole market, and a fifth of ~300 "
        "uptrending index names is a blunter cut. Abnormal volume is a weaker proxy than "
        "turnover: a volume spike after a crash is also a high-volume month, so the high bucket "
        "may buy one-month winners that are only bouncing. The shocks of 1998, 2000-02 and 2008 "
        "hit last month's hot stocks hardest, so the worst fall may pass 20%. If the control "
        "is no worse than HIGH, the paper's split did not carry over to this universe."
    ),
    candidates=(
        _v("HIGH-N20", StmParams(N20),
           "20 biggest one-month winners in the top fifth by abnormal volume, above SMA200"),
        _v("HIGH-N30", StmParams(N30),
           "Same bucket, 30 names: does a broader book keep the edge with less single-name risk?"),
        _v("LOW-N20", StmParams(N20, side="low"),
           "Control: the bottom fifth by abnormal volume, which the paper says reverses"),
        _v("ALL-N20", StmParams(N20, side="all"),
           "No volume sort: plain one-month winners, to price what the conditioning adds"),
    ),
    seen_keys=(
        "concept:short-term-momentum",
        "concept:turnover-conditioned-reversal",
        "concept:abnormal-volume-momentum",
        "doi:10.1093/rfs/hhab055",
    ),
)
