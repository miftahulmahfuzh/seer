"""M0424 — Is the calm pool the edge? A random twenty from the calmest third, with a rank buffer.

Source: variation on M0417 (Ang, Hodrick, Xing, Zhang 2006; published 2006, heavily traded since,
so the dev window can only show an edge from before the crowd and it may fade).

M0417 was dev-eligible only on its random control arm. That arm drew from the whole scored pool,
not from the calm part, so it cannot say whether the calm pool or the picking inside it carried
the result. Here the pool is explicit: the lowest third of the scored index members by trailing
63-day residual volatility (M0417's key). Inside it, an optional rank buffer keeps a holding until
it falls out of the lowest half, which is meant to cut the turnover that M0417's ranked arm paid
(1,276 trades against 342 for its random arm). The draw is M0417's sticky per-symbol hash.

Everything else is M0412/M0417's frame: point-in-time members, F4 screen, 20 equal slots monthly,
fractional shares at Gotrade's real fees, the SPY 200-day switch on every arm.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from math import ceil
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.lab.methods.m0417_low_residual_volatility import (
    MARKET,
    WIN,
    IvolPrepared,
    scored_names,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 1)

MODES = ("rank", "rand", "pool")
POOL_FRAC = 1 / 3  # the calm pool: lowest third by residual volatility
KEEP_FRAC = 1 / 2  # the buffer: a holding stays while it is in the lowest half
POOL_CAP = 200  # POOL-EW holds at most the 200 calmest, so a slot never floors below 0.5%


@dataclass(frozen=True, slots=True)
class CalmPoolParams:
    """``mode``: rank = lowest residual vol first; rand = hash order; pool = whole pool, equal."""

    inner: FactorParams
    mode: str = "rank"
    seed: int = 0
    buffer: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if not isinstance(self.buffer, bool):
            raise TypeError(f"buffer must be a bool, got {type(self.buffer).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "buffer": str(self.buffer),
               "win": str(WIN), "pool": f"{POOL_FRAC:.4f}", "cap": str(POOL_CAP), "keep": f"{KEEP_FRAC:.4f}"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CalmPoolParams:
    if not isinstance(params, CalmPoolParams):
        raise TypeError(f"params must be CalmPoolParams, got {type(params).__name__}")
    return params


def choose(rows: list[FactorRow], stats: dict[str, tuple[float, float]],
           held: frozenset[str], p: CalmPoolParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in stats]
    pool.sort(key=lambda r: (stats[r.symbol][0], r.symbol))  # calmest first
    n = len(pool)
    if n == 0:
        return []
    calm = pool[: max(1, ceil(n * POOL_FRAC))]
    if p.mode == "pool":
        return calm[:POOL_CAP]
    order = (lambda r: (float(draw(p.seed, r.symbol)), r.symbol)) if p.mode == "rand" \
        else (lambda r: (stats[r.symbol][0], r.symbol))
    top = p.inner.top
    keep: list[FactorRow] = []
    if p.buffer:
        stay = pool[: max(1, ceil(n * KEEP_FRAC))]
        keep = sorted((r for r in stay if r.symbol in held), key=order)[:top]
    have = {r.symbol for r in keep}
    fill = sorted((r for r in calm if r.symbol not in have), key=order)
    return keep + fill[: top - len(keep)]


def _targets(chosen: list[FactorRow], p: CalmPoolParams) -> tuple[Target, ...]:
    if not chosen:
        return ()
    w = equal_weight(len(chosen) if p.mode == "pool" else p.inner.top)
    out: list[Target] = []
    for r in chosen:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class CalmPoolAllocator:
    """M0417's calm pool, with a random or ranked pick inside it and an optional rank buffer."""

    id = "M0424"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IvolPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, held: frozenset[str],
             p: CalmPoolParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            stats = scored_names(history, syms, data_date)
        else:
            stats = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = stats
        return _targets(choose(rows, stats, held, p), p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IvolPrepared:
        return IvolPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IvolPrepared):
            raise TypeError(f"prepared must be IvolPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, held, _check(params))


CALM = CalmPoolAllocator()


def _v(suffix: str, params: CalmPoolParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0424-{suffix}", family="M0424",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=CALM, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0424",
    name="Random twenty from the calmest third of index stocks, with a rank buffer",
    family="stock-idiosyncratic-volatility",
    source_kind="variation",
    source_ref="M0417 variation: Ang, Hodrick, Xing, Zhang 2006",
    parent_id="M0417",
    hypothesis=(
        "M0417's only dev-eligible arm was a random twenty drawn from the whole scored pool, so "
        "the pool, not the ranking, may be the edge. Pool here = the lowest third of the scored "
        "index members by trailing 63-day residual volatility on SPY. Arms, all behind SPY's "
        "200-day switch, fractional shares at Gotrade real fees, 20 equal slots, monthly: "
        "RANK-BUF (20 calmest, a holding stays until it leaves the lowest half), RANK-NOBUF "
        "(20 calmest, no buffer: M0417's IVOL in this pool), RAND-BUF-1 and RAND-BUF-2 (hash "
        "draw from the calm third, seeds 424 and 425, same buffer: the chance spread), "
        "RAND-NOBUF-1 (seed 424 without buffer: isolates what the buffer does to turnover and "
        "return) and POOL-EW (the whole calm third, capped at its 200 calmest, equal-weighted, no picking: the always-"
        "invested no-opinion arm that prices the pool apart from any pick). Published 2006 so "
        "an edge from before the crowd may have faded. SUCCESS, written now: a random-in-pool "
        "arm beats its M0417 whole-pool twin on 2009-2015 return vs SPY by more than the two "
        "seeds' spread, and the buffer cuts trades by a third or more while giving up under 1 "
        "point a year. Predictions: RAND arms land within 2 points a year of RANK arms; the "
        "buffer saves fees but trails SPY in 2009-2015 anyway; POOL-EW within 1 point of the "
        "random arms, meaning the pool carries everything."
    ),
    expected_failure=(
        "A calm third of large index members is a utilities-and-staples sleeve that trails SPY "
        "in a rising decade whatever is picked in it, so every arm lags SPY in 2009-2015 and "
        "POOL-EW reads the same as the picks. The buffer shrinks trades but keeps stale names "
        "past the point they stop being calm. Two seeds are still a thin chance spread, and "
        "the anomaly is published and likely faded. If so, the follow-up is five seeds or a "
        "size-ceilinged pool."
    ),
    candidates=(
        _v("RANK-BUF", CalmPoolParams(N20, "rank", 0, True),
           "20 calmest of the calm third; hold until out of the lowest half"),
        _v("RANK-NOBUF", CalmPoolParams(N20, "rank", 0, False),
           "20 calmest, re-ranked every month: the no-buffer twin"),
        _v("RAND-BUF-1", CalmPoolParams(N20, "rand", 424, True),
           "Random 20 from the calm third, seed 424, with buffer"),
        _v("RAND-BUF-2", CalmPoolParams(N20, "rand", 425, True),
           "Random 20 from the calm third, seed 425, with buffer: chance spread"),
        _v("RAND-NOBUF-1", CalmPoolParams(N20, "rand", 424, False),
           "Seed 424 without buffer: what the buffer changes"),
        _v("POOL-EW", CalmPoolParams(N20, "pool", 0, False),
           "Whole calm third equal-weighted: the no-opinion arm"),
    ),
    seen_keys=(
        "concept:calm-pool-random-with-buffer",
        "concept:low-idiosyncratic-volatility",
    ),
)
