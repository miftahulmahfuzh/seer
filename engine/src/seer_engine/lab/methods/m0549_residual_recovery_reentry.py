"""M0549 — residual momentum with a faster way back in after a sell-off.

Source: variation of M0017 (near-high filter on M0007's residual book); the re-entry triggers
come from M0404 (rebound off the trough) and M0113 (positive last quarter), both measured on
SPY alone and never on a stock book.
Idea: M0017's near-high filter cut the worst fall about 3 points but cost 3-5 points a year,
because it pruned picks and sat out the 2009-2011 recovery. This keeps the unfiltered pick set
(M0032-N20-RAW's top-20 raw residual momentum) and moves only one dial: how quickly the SPY
200-day switch lets the book back in. The exit is fixed in every switching arm (SPY close
strictly under its 200-day average, ``trend_on`` unchanged). Out of the market, an arm returns
on the plain 200-day test OR on its own faster trigger, read from ``held`` (nothing held means
out). Checked monthly, on the monthly rebalance date, as the parent does.

Every arm is the same fractional book at Gotrade's real fees (``monthly-hold-frac-gotrade``)
on the owner's deposits. Reads only bars dated <= ``data_date``. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    ResidParams,
    ResidPrepared,
    build_grid,
    resid_lookback,
    residual_scores,
    targets_from_scores,
)
from seer_engine.lab.methods.m0404_spy200_rebound_reentry import LOOKBACK as TROUGH_LOOKBACK
from seer_engine.lab.methods.m0404_spy200_rebound_reentry import trough_close
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 13)
BENCH = "SPY"
QUARTER = 63

Entry = Literal["sma200", "rebound", "pos63", "always"]
_ENTRIES: tuple[str, ...] = ("sma200", "rebound", "pos63", "always")


@dataclass(frozen=True, slots=True)
class ReentryParams:
    """``inner`` is F4's screen, book size and (for switching arms) the 200-day gate."""

    inner: FactorParams
    entry: Entry = "sma200"
    rebound: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if isinstance(self.rebound, bool) or not isinstance(self.rebound, (int, float)):
            raise TypeError(f"rebound must be a number, got {type(self.rebound).__name__}")
        if self.entry == "rebound":
            if not 0.0 < self.rebound <= 0.5:
                raise ValueError(f"rebound must be in (0, 0.5], got {self.rebound}")
        elif self.rebound != 0.0:
            raise ValueError(f"rebound must be 0 for entry={self.entry!r}")
        if self.entry == "always" and self.inner.trend is not None:
            raise ValueError("the always arm carries no trend gate")
        if self.entry != "always" and self.inner.trend != (BENCH, 200):
            raise ValueError("switching arms need the SPY 200-day gate")

    def resid(self) -> ResidParams:
        return ResidParams(self.inner, scaled=False, market=BENCH)

    def as_dict(self) -> dict[str, str]:
        out = {"entry": self.entry, "rebound": repr(self.rebound)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ReentryParams:
    if not isinstance(params, ReentryParams):
        raise TypeError(f"params must be ReentryParams, got {type(params).__name__}")
    return params


def fast_entry(h: History | None, data_date: date, p: ReentryParams) -> bool:
    """The arm's own way back in. Reads only bars dated <= ``data_date``."""
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    close = h.close
    if p.entry == "pos63":
        return i >= QUARTER and bool(close[i] > close[i - QUARTER])
    if p.entry == "rebound":
        t = trough_close(h, i)
        return t is not None and t > 0 and bool(close[i] >= t * (1.0 + p.rebound))
    return False


class RecoveryReentryAllocator:
    """Residual momentum's top set, behind SPY's 200-day exit and a variant's way back in."""

    id = "M0549"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), resid_lookback(p.resid()), TROUGH_LOOKBACK,
                   QUARTER + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _on(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
            p: ReentryParams) -> bool:
        if p.entry == "always":
            return True
        if held or p.entry == "sma200":
            return trend_on(history, data_date, p.inner)
        return trend_on(history, data_date, p.inner) or fast_entry(
            history.get(BENCH), data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not self._on(history, data_date, held, p):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        grid = build_grid(history, BENCH)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        return targets_from_scores(rows, scores, p.resid())

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not self._on(prepared.history, data_date, held, p):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        grid = prepared.grid(BENCH)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid())
        return targets_from_scores(rows, scores, p.resid())


REENTRY = RecoveryReentryAllocator()

GATED = FactorParams(rank="momentum", top=20, trend=(BENCH, 200))
UNGATED = FactorParams(rank="momentum", top=20, trend=None)


def _v(suffix: str, params: ReentryParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0549-{suffix}", family="M0549", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=REENTRY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0549",
    name="Residual momentum with a recovery re-entry rule after sell-offs",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="variation of M0017; triggers from M0404 (rebound off trough) and M0113 (positive quarter)",
    parent_id="M0017",
    hypothesis=(
        "M0017's near-high filter cut the worst fall about 3 points but cost 3-5 points a year, "
        "likely by sitting out post-sell-off recoveries. Test whether the residual book can "
        "reduce its fall without pruning picks: keep the unfiltered pick set (top-20 raw "
        "residual momentum, F4 screen, equal weights, monthly, fractional shares at Gotrade's "
        "real fees, owner deposits) and vary only how quickly the SPY-200 exit lets it back in. "
        "The 200-day switch dates from 1992/2007 and residual momentum from Blitz et al. 2011, so "
        "the crowd had both by 2015 and dev may flatter them. Arms: SPY200 (Control: "
        "M0032-N20-RAW-FRAC-GT's book, the plain switch, expected to record as its twin), "
        "REB10 and REB15 (back in once SPY is 10% / 15% above the lowest close of the current "
        "below-200-day episode, or over its 200-day), POS63 (back in once SPY's close is above "
        "its close 63 sessions ago, M0113's best trigger on SPY alone), and ALWAYS (Control: the "
        "same book never stepping aside, no opinion, so what the switch's habit costs can be "
        "separated from what its opinion earns). SUCCESS: a fast arm beats SPY200 on funded "
        "return in 2009-2015 without a worst fall deeper than SPY200's, and beats ALWAYS on fall. "
        "KILL: every fast arm has a deeper fall than SPY200 or none adds return. Assumption: "
        "'out' means nothing held at the monthly check; the trough follows M0404's definition."
    ),
    expected_failure=(
        "M0404 found a rebound trigger on SPY alone grew the worst fall from 18.9% to 26.5%, "
        "and M0113 found price-above-a-line triggers re-enter mid-crash. A stock book is a "
        "higher-beta version of the same bet, so fast re-entry buys 2001, 2002 and late-2008 "
        "rallies and deepens the fall with no 2009 gain to pay for it. 2009-2015 had no bear "
        "market, so a fast arm can look good there for the wrong reason. The switch has few "
        "episodes (a handful in 20 years), so arms may record near-identical curves and the "
        "differences be luck-sized; the luck bar is close to meaningless at that count. Arms "
        "that never fire before the 200-day test would repeat the control's curve (a treatment "
        "that never acted)."
    ),
    candidates=(
        _v("SPY200", ReentryParams(GATED, "sma200"),
           "Control: M0032-N20-RAW-FRAC-GT's book, the plain symmetric 200-day switch"),
        _v("REB10", ReentryParams(GATED, "rebound", 0.10),
           "Out under the 200-day, back in 10% above the episode's lowest SPY close"),
        _v("REB15", ReentryParams(GATED, "rebound", 0.15),
           "As REB10 with a 15% rebound required: more proof of a bottom, later entry"),
        _v("POS63", ReentryParams(GATED, "pos63"),
           "Out under the 200-day, back in once SPY closes above its close 63 sessions ago"),
        _v("ALWAYS", ReentryParams(UNGATED, "always"),
           "Control: the same residual book never stepping aside, no gate, no opinion"),
    ),
    seen_keys=(
        "concept:residual-momentum-recovery-reentry",
        "concept:stock-book-fast-reentry-after-sma200-exit",
    ),
)
