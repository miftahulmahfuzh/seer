"""M0068 — The leader of a broken pair, held a month: does running ahead of a close partner
predict anything?

Source: variation of M0064 (parent). Gatev, Goetzmann & Rouwenhorst (2006), Pairs trading:
performance of a relative-value arbitrage rule, Rev. Financial Studies 19(3),
doi:10.1093/rfs/hhj020.
Idea: M0064 found that the laggard of a broken pair earns less than the market at Gotrade's real
fees, because pairs mostly close by the leader falling back rather than the laggard catching up.
This method tests the other side: does running ahead of a close partner carry information at all,
or is a leader just a short-term winner that will fall back like everything else in the failed
momentum family? Each month (not weekly, to cut fees and the switch's whipsaw), among F4's
screened point-in-time members, pairs are formed on the 252 sessions before the current half-year
Gatev trading period, and the stock that has run 2 or more formation sigmas ahead of its partner
is held equal-weight, rest in SPY, monthly 200-day gate.

Reuses M0064's chassis unmodified: the same ``PairsParams``, the same pair-formation and gap
state machine, the same ``build_targets`` (it only places whatever symbols a leg list names, so
it does not care whether the legs are leaders or laggards). The only new logic is which side of
each open pair is picked: M0064's ``open_legs`` returns the lagging leg; ``open_legs_leader``
below returns the leading one instead, from the same per-pair state.

A monthly (not weekly) rules preset is used throughout, both for the reasons in the hypothesis
and because ``monthly-hold-frac-gotrade`` already exists as a standard preset — unlike M0064's
weekly book, this one needs no ad-hoc rules preset to be promotable.

Reads only grid columns dated <= data_date.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    N20_NOTREND,
    ResidPrepared,
    ReturnGrid,
    build_grid,
)
from seer_engine.lab.methods.m0064_pairs_laggard import PairsParams, build_targets, pairs_lookback
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import EXCLUDED, factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 26)


def _check(params: object) -> PairsParams:
    if not isinstance(params, PairsParams):
        raise TypeError(f"params must be PairsParams, got {type(params).__name__}")
    return params


def _period_start(d: date) -> date:
    return date(d.year, 1 if d.month <= 6 else 7, 1)


def open_legs_leader(grid: ReturnGrid, symbols: list[str], data_date: date,
                     params: PairsParams) -> list[tuple[float, str]]:
    """``(gap in sigmas, leader)`` for every pair open at the ``data_date`` close, widest first.

    Same pair-formation and gap state machine as M0064's ``open_legs``; only the final pick
    differs — the leg that ran ahead instead of the one that fell behind. Reads only grid columns
    dated <= ``data_date``.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return []
    s0 = int(np.searchsorted(grid.dates, as_day(_period_start(data_date)), side="left"))
    f0 = s0 - params.form_n
    if f0 < 0 or s0 > j:
        return []
    names = [s for s in symbols if s in grid.row and s not in EXCLUDED]
    if len(names) < 2:
        return []
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)
    form = grid.rets[idx, f0:s0]
    full = np.all(np.isfinite(form), axis=1)
    if int(full.sum()) < 2:
        return []
    names = [n for n, ok in zip(names, full, strict=True) if ok]
    idx = idx[full]
    paths = np.cumprod(1.0 + form[full], axis=1)  # (n, form_n), each name's index over formation

    sq = (paths * paths).sum(axis=1)
    dist = sq[:, None] + sq[None, :] - 2.0 * (paths @ paths.T)
    np.fill_diagonal(dist, np.inf)
    nearest = np.argmin(dist, axis=1)
    seen: set[tuple[int, int]] = set()
    cands: list[tuple[float, int, int]] = []
    for a in range(len(names)):
        b = int(nearest[a])
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        cands.append((float(dist[key[0], key[1]]), key[0], key[1]))
    cands.sort(key=lambda t: (t[0], names[t[1]], names[t[2]]))
    chosen = cands[: params.pairs]
    if not chosen:
        return []
    ia = np.asarray([c[1] for c in chosen], dtype=np.int64)
    ib = np.asarray([c[2] for c in chosen], dtype=np.int64)
    sigma = np.std(paths[ia] - paths[ib], axis=1)

    trade = np.nan_to_num(grid.rets[idx, s0 : j + 1], nan=0.0)  # a missing day carries the price
    run = np.cumprod(1.0 + trade, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        gap = (run[ia] - run[ib]) / sigma[:, None]  # > 0: b lags, a leads; < 0: a lags, b leads
    gap = np.where(np.isfinite(gap), gap, 0.0)

    entry = float(params.entry)
    stop = math.inf if params.stop is None else float(params.stop)
    max_age = params.max_age
    npairs = len(chosen)
    side = np.zeros(npairs)  # +1 or -1 while open, 0 when flat
    locked = np.zeros(npairs)  # side a stopped or timed-out pair was shut on, 0 when free
    age = np.zeros(npairs, dtype=np.int64)
    for t in range(gap.shape[1]):
        g = gap[:, t]
        for k in range(npairs):
            if side[k] != 0.0:
                age[k] += 1
                if side[k] * g[k] <= 0.0:
                    side[k] = 0.0
                elif abs(g[k]) >= stop or (max_age is not None and age[k] >= max_age):
                    locked[k] = side[k]
                    side[k] = 0.0
            elif locked[k] != 0.0:
                if locked[k] * g[k] <= 0.0:
                    locked[k] = 0.0
            if side[k] == 0.0 and locked[k] == 0.0 and abs(g[k]) >= entry:
                side[k] = 1.0 if g[k] > 0.0 else -1.0
                age[k] = 0

    best: dict[str, float] = {}
    last = gap[:, -1]
    for k in range(npairs):
        if side[k] == 0.0:
            continue
        lead = names[int(ia[k])] if side[k] > 0 else names[int(ib[k])]
        best[lead] = max(best.get(lead, 0.0), abs(float(last[k])))
    return sorted(((v, s) for s, v in best.items()), key=lambda t: (-t[0], t[1]))


# --------------------------------------------------------------------------- the allocator


class PairsLeaderAllocator:
    """The leg of every open pair that ran ahead, the rest in SPY (or cash), behind F4's gate."""

    id = "M0068"

    def lookback(self, params: Any) -> int:
        return pairs_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.market,) if p.park == "spy" else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, history: Mapping[str, History], rows, grid: ReturnGrid | None,
                 data_date: date, params: PairsParams) -> tuple[Any, ...]:
        if grid is None:
            return ()
        legs = open_legs_leader(grid, [r.symbol for r in rows], data_date, params)
        return build_targets(rows, legs, history, data_date, params)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Any, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return self._targets(history, rows, build_grid(history, p.market), data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return ResidPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Any, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return self._targets(prepared.history, rows, prepared.grid(p.market), data_date, p)


LEADER = PairsLeaderAllocator()


def _v(suffix: str, params: PairsParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0068-{suffix}", family="M0068", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LEADER, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0068",
    name="The leader of a broken pair, held a month: does running ahead of a close partner predict anything?",
    family="stock-pairs-relative-value",
    source_kind="variation",
    source_ref="M0064",
    parent_id="M0064",
    hypothesis=(
        "M0064 found that the laggard of a broken pair earns less than the market at Gotrade's "
        "real fees, because pairs mostly close by the leader falling back. Test the other side "
        "to learn whether lag versus a close partner carries information at all: each month (not "
        "weekly, to cut fees and the switch's whipsaw), among F4's screened members, form Gatev "
        "pairs on the prior 252 sessions and hold the stock that has run 2 or more formation "
        "sigmas ahead of its partner, equal weight, rest in SPY, monthly 200-day gate, fractional "
        "shares on monthly-hold-frac-gotrade. Expected failure: the leader is simply a short-term "
        "winner, so the book moves with the failed momentum books and is refused as their kin by "
        "behaviour (check the residual correlation before spending variants); or, if pairs really "
        "close by the leader falling, it loses outright, which would confirm M0064's reading and "
        "close the family."
    ),
    expected_failure=(
        "The leader is simply a short-term winner, so the book moves with the failed momentum "
        "books and is refused as their kin by behaviour (check the residual correlation before "
        "spending variants); or, if pairs really close by the leader falling, it loses outright, "
        "which would confirm M0064's reading and close the family. Either way the book holds a "
        "handful of names at a time with the rest in SPY, so even a real effect may be diluted "
        "to near nothing once Gotrade's fees and the monthly SPY resize are paid."
    ),
    candidates=(
        _v("P20", PairsParams(N20, pairs=20),
           "Gatev's 20 closest pairs, open at 2 sigmas, 4-sigma stop, 40-session limit, "
           "leader held, rest in SPY, monthly"),
        _v("P50", PairsParams(N20, pairs=50),
           "50 closest pairs: more legs open, more of the book in the leaders"),
        _v("P50-CASH", PairsParams(N20, pairs=50, park="cash"),
           "P50 with the rest in cash: the leaders alone, measured against SPY"),
        _v("P50-K15", PairsParams(N20, pairs=50, entry=Decimal("1.5")),
           "P50 opening at 1.5 sigmas: more, smaller divergences"),
        _v("P50-NOGATE", PairsParams(N20_NOTREND, pairs=50),
           "P50 with no SPY 200-day gate: what the gate is worth"),
    ),
    seen_keys=(
        "concept:pairs-trading",
        "concept:distance-method-pairs",
        "concept:relative-value-arbitrage",
        "concept:pairs-leader-momentum",
        "doi:10.1093/rfs/hhj020",
    ),
)
