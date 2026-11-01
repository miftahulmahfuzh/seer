"""M0433 — Plain momentum with a sell buffer, read against five random draws from the same pool.

Source: variation of M0413 (Jegadeesh and Titman 1993, published long ago, so the dev window is
after the crowd and 2009-2015 is the first filter). M0413 priced a top-40 sell buffer on plain
12-1 momentum and moved return by under a point either way; M0424 then showed the same random
rule can fall 19.6% or 35.0% depending only on the seed. One plain-momentum run cannot say
whether a result is the rule or the draw. Here the error bar is explicit: five seeded draws
(seeds 433-437) of twenty names from the very pool momentum ranks (F4-screened index members),
each with the same buffer (a held name stays while it sits inside the first 40 of the draw
order), so the plain-momentum book is judged against how far a no-opinion book wanders.

``BufferedDrawAlloc`` is M0413's allocator with one extra dial: ``seed`` of None ranks by 12-1
return, an int ranks by M0293's sticky per-symbol hash. The SPY 200-day switch, the screen and
the equal 20 slots are FACTOR's own for every arm. Pure; reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FACTOR,
    FactorParams,
    FactorRow,
    factor_rows,
    factor_weights,
    trend_on,
)

ADDED = date(2026, 11, 1)

SWITCH = ("SPY", 200)
TOP = 20
EXIT_RANK = 40


@dataclass(frozen=True, slots=True)
class Params:
    """``seed`` None = rank by 12-1 momentum; an int = rank by the sticky hash of that seed."""

    seed: int | None = None
    exit_rank: int = EXIT_RANK

    def __post_init__(self) -> None:
        if self.exit_rank < TOP:
            raise ValueError(f"exit_rank must be >= {TOP}, got {self.exit_rank}")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise TypeError(f"seed must be an int or None, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {"seed": str(self.seed), "exit_rank": str(self.exit_rank), "pool": "f4-screened-members"}

    def picker(self) -> FactorParams:
        return FactorParams(rank="momentum", top=TOP, mom_n=252, mom_skip=21, trend=SWITCH)


def choose(rows: Sequence[FactorRow], held: frozenset[str], p: Params) -> list[FactorRow]:
    """Held names still inside the first ``exit_rank`` of the order stay (best first, at most
    TOP); the first others in that order fill the rest."""
    if p.seed is None:
        order = lambda r: (-r.momentum, r.symbol)  # noqa: E731
    else:
        seed = p.seed
        order = lambda r: (float(draw(seed, r.symbol)), r.symbol)  # noqa: E731
    ranked = sorted(rows, key=order)
    kept = [r for r in ranked[: p.exit_rank] if r.symbol in held][:TOP]
    have = {r.symbol for r in kept}
    fill = [r for r in ranked if r.symbol not in have][: TOP - len(kept)]
    return sorted(kept + fill, key=order)


def _targets(rows: Sequence[FactorRow], held: frozenset[str], params: Params) -> tuple[Target, ...]:
    chosen = choose(rows, held, params)
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.picker()), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class BufferedDrawAlloc:
    """FACTOR's screen and switch, with a buffered pick ordered by momentum or by a seeded draw."""

    id = "M0433"

    def lookback(self, params: Params) -> int:
        return FACTOR.lookback(params.picker())

    def symbols(self, params: Params) -> tuple[str, ...]:
        return FACTOR.symbols(params.picker())

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(history, data_date, p):
            return ()
        return _targets(factor_rows(history, members, data_date, p), held, params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return FACTOR.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(prepared.history, data_date, p):
            return ()
        return _targets(prepared.rows_on(members, data_date, p), held, params)


DRAWN = BufferedDrawAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0433-{suffix}", family="M0433", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DRAWN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0433",
    name="Plain momentum with a sell buffer, against five random draws from the same pool",
    family="stock-momentum",
    source_kind="variation",
    source_ref="M0413",
    parent_id="M0413",
    hypothesis=(
        "M0413 found a top-40 sell buffer on plain 12-1 momentum cuts trades but moves return by "
        "under a point; M0424 found one random rule's worst fall ranges 19.6% to 35.0% on the seed "
        "alone. Arms, all behind SPY's 200-day switch, 20 equal slots, monthly, fractional shares "
        "at Gotrade's real fees, the same F4-screened point-in-time index pool: MOM-B40 (the top "
        "20 by 12-1 return, a held name stays while in the top 40) and DRAW-B40-1..5 (twenty "
        "names from the same pool in sticky hash order, seeds 433-437, the same buffer on the hash "
        "order). The five draws are the error bar: the spread of no-opinion books under the same "
        "frame. The unbuffered momentum control is M0413-B20, recorded at the same fees, and "
        "M0413-B40 is the buffered twin on M0413's own allocator; they are compared, not re-run. "
        "SUCCESS, written now: MOM-B40's 2009-2015 return vs SPY beats the best of the five draws "
        "AND its worst fall is no deeper than the median draw's. Predictions: MOM-B40 beats the "
        "draws' median on full-window return (momentum has a real signal) but not in 2009-2015; "
        "the five draws' worst falls spread by more than 8 points; MOM-B40 stays above the 20% "
        "fall bar. Momentum was published in 1993, so a strong dev edge may predate the crowd."),
    expected_failure=(
        "The draws land as wide as the gap between momentum and SPY, so one momentum run says "
        "nothing the seed spread cannot explain, and MOM-B40 sits inside the draws on return and "
        "fall. The frame (the switch, large index members) carries the result, and every arm lags "
        "SPY in 2009-2015 through time in cash. Five draws is still a thin error bar. If so, the "
        "follow-up is ten draws on the cheap arm or a draw-free benchmark such as the equal-weight "
        "index."),
    candidates=(
        _v("MOM-B40", Params(seed=None), "plain 12-1 top 20, hold until out of the top 40"),
        _v("DRAW-B40-1", Params(seed=433), "hash draw of 20 from the pool, seed 433, buffer 40"),
        _v("DRAW-B40-2", Params(seed=434), "hash draw of 20 from the pool, seed 434, buffer 40"),
        _v("DRAW-B40-3", Params(seed=435), "hash draw of 20 from the pool, seed 435, buffer 40"),
        _v("DRAW-B40-4", Params(seed=436), "hash draw of 20 from the pool, seed 436, buffer 40"),
        _v("DRAW-B40-5", Params(seed=437), "hash draw of 20 from the pool, seed 437, buffer 40"),
    ),
    seen_keys=("concept:momentum-buffer-five-draw-error-bar",),
)
