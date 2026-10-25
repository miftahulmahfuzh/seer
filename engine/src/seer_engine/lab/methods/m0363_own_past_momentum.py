"""M0363 — Each stock against its own past: hold every index member whose own 12-month return beats zero.

Source: Moskowitz, Ooi & Pedersen (2012), Time series momentum, JFE (SSRN 1788355).
Idea: every lab momentum book ranks stocks against peers and takes the top 20. Time-series
momentum asks of each name only whether its own trailing return is positive, with no ranking, so
the number of holdings floats with how many names pass and the slots nobody fills sit in SPY.
That should de-risk itself when few names pass and be a less crowded signal than the relative
rank. This method tests it against two controls on the same frame: the relative-rank top 20, and
a random pick with the same count each month, so the signal, the rank and the frame can be told
apart.

The frame, shared by every variant (F4's screen, as in M0063): a member is eligible with a close
of at least $5 and 20-day mean trading value above $20M. Twenty slots at 5% each, re-picked on the
monthly rules, the weight the empty slots leave goes to SPY. A name's *own return* is F4's 12-1
momentum column (close 21 sessions ago over close 252 sessions ago, minus one): the last month is
skipped as in every other momentum book, so this differs from the paper's plain 12 months only by
that skip.

Modes (``Params.mode``), each reading bars dated <= d only:

    abs0     eligible and own 12-1 return > 0. More than ``top`` pass: held names keep their
             slot while they still pass, the rest by a blake2b hash of (seed, symbol, month), an
             order that knows nothing about prices, so the book is never a ranking in disguise.
    abs_spy  the same with the bar "own return > SPY's own return over the same window".
    rank     the control: the ``top`` eligible names by 12-1 return, passing or not (F4's rank).
    random   the control: as many names as pass the abs0 test this month (at most ``top``),
             drawn by the hash from all eligible names, a fresh draw each month.

``inner.trend`` set puts the whole book in cash while SPY is under its 200-day average, as in the
trend-switched books; every other variant has no switch, so the picking and the frame are
measured alone.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
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

ADDED = date(2026, 10, 25)

MODES = ("abs0", "abs_spy", "rank", "random")


@dataclass(frozen=True, slots=True)
class Params:
    """``inner`` is F4's screen, book size and optional switch; ``mode`` is the pick rule."""

    inner: FactorParams
    mode: str = "abs0"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "market": self.market}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> Params:
    if not isinstance(params, Params):
        raise TypeError(f"params must be Params, got {type(params).__name__}")
    return params


def market_return(history: Mapping[str, History], data_date: date, p: Params) -> float | None:
    """SPY's return over F4's momentum window on ``data_date`` (same two bars as ``return_window``)."""
    h = history.get(p.market)
    if h is None:
        return None
    i = h.index_of(data_date)
    n, skip = p.inner.mom_n, p.inner.mom_skip
    if i is None or i < n or h.close[i - n] <= 0:
        return None
    return float(h.close[i - skip] / h.close[i - n] - 1.0)


class OwnPastAllocator:
    """Names whose own return passes the bar, held while they pass, the rest of the book in SPY."""

    id = "M0363"

    def lookback(self, params: Any) -> int:
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

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow], data_date: date,
                 held: frozenset[str], p: Params) -> tuple[Target, ...]:
        rows = [r for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market]
        top = p.inner.top
        passing = [r for r in rows if r.momentum > 0.0]
        if p.mode == "abs_spy":
            bar = market_return(history, data_date, p)
            passing = [] if bar is None else [r for r in rows if r.momentum > bar]
        if p.mode == "rank":
            picks = [r.symbol for r in sorted(rows, key=lambda r: (-r.momentum, r.symbol))[:top]]
        elif p.mode == "random":
            k = min(top, sum(1 for r in rows if r.momentum > 0.0))
            picks = sorted((r.symbol for r in rows),
                           key=lambda s: (draw(p.seed, s, data_date), s))[:k]
        else:
            names = {r.symbol for r in passing}
            keep = sorted(s for s in held if s in names)[:top]
            rest = sorted((s for s in names if s not in keep),
                          key=lambda s: (draw(p.seed, s, data_date), s))
            picks = (keep + rest)[:top]
        w = equal_weight(top)
        out: list[Target] = []
        for s in picks:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        mh = history.get(p.market)
        spare = Decimal(1) - w * len(out)
        if spare > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(p.market, last_close(mh, data_date), spare)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> tuple[Mapping[str, History], FactorPrepared]:
        return history, prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        history, factor = prepared
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor.rows_on(members, data_date, p.inner)
        return self._targets(history, rows, data_date, held, p)


OWNPAST = OwnPastAllocator()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0363-{suffix}", family="M0363", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=OWNPAST, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0363",
    name="Each stock against its own past: hold every index member whose own 12-month return beats zero, no ranking against peers",
    family="stock-time-series-momentum",
    source_kind="paper",
    source_ref="Moskowitz, Ooi & Pedersen (2012), Time series momentum, Journal of Financial "
               "Economics, SSRN 1788355",
    parent_id=None,
    hypothesis=(
        "Published 2012, so the dev window (to 2015) shows the edge only from before and just "
        "after it was widely known; 2009-2015 is judged first. Every lab momentum book ranks "
        "stocks against peers and takes the top 20. Time-series momentum asks of each name only "
        "whether its own 12-1 return is above zero, with no ranking, so the number of holdings "
        "floats with how many names pass and the unfilled slots sit in SPY: up to 20 names at 5% "
        "each inside F4's liquidity and membership screen, monthly, fractional shares at "
        "Gotrade's real fees (monthly-hold-frac-gotrade) on the owner's top-up. When more than 20 "
        "pass, held names keep their slot and the rest are drawn by a price-blind hash, so the "
        "book never ranks. Variants: ABS0 (own return > 0, no switch), ABS-SPY (own return > "
        "SPY's over the same window), ABS0-SW (ABS0 behind the SPY-200 switch, all cash while "
        "it is off), RANK20 (control: the top 20 by 12-1 return, same frame, no switch), "
        "RANDOM20 and RANDOM20-S2 (controls: as many names as pass ABS0 that month, drawn by "
        "hash from all eligible names, two seeds). Success: ABS0 beats total-return SPY on dev "
        "with a worst fall under 20%, beats SPY in 2009-2015, and beats both RANDOM20 seeds "
        "(so the absolute test, not the frame, earned it). The honest prior is that it mostly "
        "reproduces the plain momentum book and adds nothing."
    ),
    expected_failure=(
        "A name above zero over 12 months is most names in a rising market: ABS0 will hold 20 "
        "names almost always, so it degenerates into a hash-picked equal-weight book of index "
        "members, which lost to SPY on every dev era after 2009 (the pool and the even slices, "
        "plus fees on monthly turns). Without the switch the 2000-02 and 2008 falls are taken in "
        "full, so the worst fall should break 20%, as M0332's no-switch momentum book did. "
        "ABS-SPY will collapse toward RANK20 because few names beat SPY. RANDOM20 pays more "
        "turnover than ABS0 (a fresh draw each month), so a gap in ABS0's favour may be fees "
        "and not signal. If RANDOM20 matches ABS0 the signal is nothing."
    ),
    candidates=(
        _v("ABS0", Params(N20_NOTREND),
           "Own 12-1 return > 0, up to 20 at 5%, the rest in SPY, no switch, hash fills past 20"),
        _v("ABS-SPY", Params(N20_NOTREND, mode="abs_spy"),
           "Own 12-1 return above SPY's over the same window: a harder bar, fewer names"),
        _v("ABS0-SW", Params(N20),
           "ABS0 behind the SPY-200 switch: all cash while SPY is under its average"),
        _v("RANK20", Params(N20_NOTREND, mode="rank"),
           "Control: top 20 by 12-1 return, the relative rank, same frame, no switch"),
        _v("RANDOM20", Params(N20_NOTREND, mode="random"),
           "Control: as many names as pass ABS0, drawn price-blind from all eligible (seed 1)"),
        _v("RANDOM20-S2", Params(N20_NOTREND, mode="random", seed=2),
           "Control: same count, a second hash seed, so the placebo is a spread"),
    ),
    seen_keys=(
        "concept:time-series-momentum-per-stock",
        "concept:absolute-momentum-per-stock",
        "ssrn:1788355",
    ),
)
