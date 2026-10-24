"""M0344 — Residual book with a holding buffer: keep a name until it falls out of the top 40.

Parent: M0043 (its RES-PLAIN arm, the plain residual top-20), itself M0007-N20-RAW's ranking in
M0036's frame. The plain book re-ranks every month and sells a name the moment it slips from 20th
to 21st, paying Gotrade's small-order fee on both legs. A rank buffer (hysteresis on rank, the
turnover-saving device of index construction, e.g. FTSE/Russell reconstitution bands) buys a name
only when it is in the top ``top`` and sells a held name only when it falls below ``exit_rank``.

On data date d: eligible rows are F4's screen under the SPY-200 gate, ranked on M0007-N20-RAW's raw
cumulative market-model residual (the same ``residual_scores``). Held names whose rank is within
``exit_rank`` are kept; the free slots, up to ``top``, are filled from the top of the ranking by
rank. ``exit_rank == top`` keeps nobody for being close, so it IS the plain book through the same
allocator and fees: the arm with no opinion in it, which prices what the buffer adds. Every piece
reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    ResidPrepared,
    build_grid,
    residual_scores,
)
from seer_engine.lab.methods.m0036_frog_in_the_pan import (
    FipParams,
    FrogInThePanAllocator,
    targets_from_rows,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, FactorRow, factor_rows, trend_on

ADDED = date(2026, 10, 24)


@dataclass(frozen=True, slots=True)
class BufferParams:
    """``inner`` is F4's screen, trend gate and book size; ``exit_rank`` is the rank a held name may fall to."""

    inner: FactorParams
    exit_rank: int = 40
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.exit_rank, bool) or not isinstance(self.exit_rank, int):
            raise TypeError(f"exit_rank must be an int, got {type(self.exit_rank).__name__}")
        if self.exit_rank < self.inner.top:
            raise ValueError(f"exit_rank must be >= inner.top, got {self.exit_rank} < {self.inner.top}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def fip(self) -> FipParams:
        """M0036's parameters for the same screen and residual key (lookback, universe, weights)."""
        return FipParams(self.inner, base="residual", pool=self.inner.top, market=self.market)

    def as_dict(self) -> dict[str, str]:
        out = {"exit_rank": str(self.exit_rank), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BufferParams:
    if not isinstance(params, BufferParams):
        raise TypeError(f"params must be BufferParams, got {type(params).__name__}")
    return params


def choose_buffered(
    rows: list[FactorRow], score: Mapping[str, float], held: frozenset[str], params: BufferParams
) -> list[FactorRow]:
    """Held names still within ``exit_rank`` stay; the top-ranked others fill up to ``inner.top``."""
    ranked = sorted((r for r in rows if r.symbol in score and r.symbol not in EXCLUDED),
                    key=lambda r: (-score[r.symbol], r.symbol))
    top = params.inner.top
    keep = {r.symbol for r in ranked[: params.exit_rank] if r.symbol in held}
    kept = [r for r in ranked if r.symbol in keep][:top]
    kept_syms = {r.symbol for r in kept}
    fill = [r for r in ranked if r.symbol not in kept_syms][: top - len(kept)]
    chosen = kept + fill
    return sorted(chosen, key=lambda r: (-score[r.symbol], r.symbol))


class BufferedResidualAllocator(FrogInThePanAllocator):
    """M0043's plain residual book, with held names kept while they stay inside ``exit_rank``."""

    id = "M0344"

    def lookback(self, params: Any) -> int:
        return super().lookback(_check(params).fip())

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params).fip())

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _book(self, history: Mapping[str, History], rows: list[FactorRow], grid: Any,
              data_date: date, held: frozenset[str], p: BufferParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        fp = p.fip()
        score = residual_scores(grid, [r.symbol for r in rows], data_date, fp.resid())
        return targets_from_rows(choose_buffered(rows, score, held, p), fp)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._book(history, rows, build_grid(history, p.market), data_date, held, p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._book(prepared.history, rows, prepared.grid(p.market), data_date, held, p)


BUFFERED = BufferedResidualAllocator()


def _v(suffix: str, params: BufferParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0344-{suffix}", family="M0344", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUFFERED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0344",
    name="Residual book with a holding buffer: keep a name until it falls out of the top 40, not the top 20",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="lab parent M0043 (RES-PLAIN); rank-band hysteresis as used in index reconstitution",
    parent_id="M0043",
    hypothesis=(
        "M0043 showed the plain residual top-20 (13.6% a year money-weighted, 1607 trades) beat every "
        "continuity sort, and that sorting only added churn. The remaining cost in the plain book is "
        "trading: monthly re-ranking sells a name the moment it slips from 20th to 21st and pays "
        "Gotrade's small-order fees on both legs. A rank buffer buys a new name only when it enters "
        "the top 20 and sells a held name only when it leaves the top 40 (or the trend gate turns "
        "off). Arms: buffer 20 (the plain control, no opinion), 30 and 40, so the lab can price the "
        "habit. Frame unchanged: F4's screen, SPY-200 trend gate, equal weights, monthly, fractional "
        "shares at Gotrade's real fees on the monthly-hold-frac-gotrade preset, funded 5,000,000 IDR "
        "on the 25th. Rank bands are standard in index construction and have no publication-decay "
        "story of their own, but the residual key they sit on dates from 2011. Expect fewer trades "
        "and about the same pick quality, and a worst fall still near 20%, since this changes cost, "
        "not exposure. Rank hysteresis has not been tried on a stock book; the lab only holds switch "
        "hysteresis (M0148)."
    ),
    expected_failure=(
        "The buffer keeps fading winners longer, and their lag costs as much as the saved fees: "
        "buffer 40 lands within a point of the plain book on return with only slightly fewer "
        "trades, because monthly top-20 turnover is dominated by names leaving the top 40 anyway. "
        "The worst fall stays over 20% since exposure is unchanged, so the method is rejected on "
        "the fall as the plain residual book is."
    ),
    candidates=(
        _v("BUF20", BufferParams(N20, exit_rank=20),
           "No opinion: exit at rank 20, the plain residual top-20 through this allocator, same fees"),
        _v("BUF30", BufferParams(N20, exit_rank=30),
           "Hold a name until it falls below rank 30"),
        _v("BUF40", BufferParams(N20, exit_rank=40),
           "Hold a name until it falls below rank 40"),
    ),
    seen_keys=(
        "concept:rank-buffer-hysteresis",
        "concept:residual-momentum-holding-buffer",
    ),
)
