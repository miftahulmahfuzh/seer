"""M0419 — Low residual volatility with a rank buffer: keep a calm stock until it leaves the calmest 40.

Source: variation on M0417 (Ang, Hodrick, Xing, Zhang 2006; published 2006 and traded hard since,
so the dev window can only show an edge from before the crowd and it may fade).

M0417's ranked arm re-picked the 20 calmest names every month and made 1,276 trades against 342
for its random arm, paying Gotrade's small-order fees on every swap. Here the same key (M0417's
63-day residual volatility on SPY, the same scored pool) is kept, but a holding is sold only when
it falls out of the calmest ``exit_rank`` of the whole scored pool, not the moment it leaves the
top 20. Slots freed are filled by the next calmest names. This differs from M0424, whose buffer
lived inside a calm-third pool and used the lowest half as its exit line.

The unbuffered ranked twin and its no-switch twin already exist as M0417's IVOL and IVOL-NOSW and
a configuration runs once, so they are not re-registered; their numbers are read from M0417.
Frame: point-in-time members, F4 screen, 20 equal slots monthly, fractional shares at Gotrade's
real fees, the SPY 200-day switch on every arm but two.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.lab.methods.m0417_low_residual_volatility import (
    MARKET,
    NOSW,
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

MODES = ("ivol", "blind")


@dataclass(frozen=True, slots=True)
class BufParams:
    """``mode``: ivol = lowest residual vol first; blind = hash order. ``exit_rank``: a holding
    stays while it ranks within this many names on the same order."""

    inner: FactorParams
    mode: str = "ivol"
    seed: int = 0
    exit_rank: int = 40

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if isinstance(self.exit_rank, bool) or not isinstance(self.exit_rank, int):
            raise TypeError(f"exit_rank must be an int, got {type(self.exit_rank).__name__}")
        if self.exit_rank < self.inner.top:
            raise ValueError("exit_rank must be at least the book size")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "exit_rank": str(self.exit_rank),
               "win": str(WIN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BufParams:
    if not isinstance(params, BufParams):
        raise TypeError(f"params must be BufParams, got {type(params).__name__}")
    return params


def choose_buffered(rows: list[FactorRow], stats: dict[str, tuple[float, float]],
                    held: frozenset[str], p: BufParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in stats]
    if p.mode == "ivol":
        key = {r.symbol: stats[r.symbol][0] for r in pool}
    else:
        key = {r.symbol: float(draw(p.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    top = p.inner.top
    stay = [r for r in pool[: p.exit_rank] if r.symbol in held][:top]
    have = {r.symbol for r in stay}
    fill = [r for r in pool if r.symbol not in have]
    return stay + fill[: top - len(stay)]


def _targets(chosen: list[FactorRow], p: BufParams) -> tuple[Target, ...]:
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for r in chosen:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class BufferedIvolAllocator:
    """M0417's residual-volatility book with a sell buffer on the same ranking."""

    id = "M0419"

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
             p: BufParams) -> tuple[Target, ...]:
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
        return _targets(choose_buffered(rows, stats, held, p), p)

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


BUF = BufferedIvolAllocator()


def _v(suffix: str, params: BufParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0419-{suffix}", family="M0419",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=BUF, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0419",
    name="Low residual volatility with a rank buffer: keep a calm stock until it drops out of the calmest 40",
    family="stock-idiosyncratic-volatility",
    source_kind="variation",
    source_ref="M0417 variation: Ang, Hodrick, Xing, Zhang 2006",
    parent_id="M0417",
    hypothesis=(
        "M0417's ranked calm-stock book traded about 3.7 times as often as its random book and "
        "paid Gotrade's small-order fees on every swap. Hold the 20 lowest residual-volatility "
        "names (M0417's key and pool) but sell one only when it falls out of the lowest 40, "
        "which should cut trades by a third or more and, if the signal has any pull, let the "
        "calm stocks compound without the fee drag. Arms, all fractional at real fees, 20 equal "
        "slots, monthly: BUF40 (exit rank 40), BUF60 (a wider buffer: does more patience help), "
        "R1-BUF40 and R2-BUF40 (hash order with the same buffer, seeds 419 and 420: the chance "
        "spread, same trade count mechanics), BUF40-NOSW (no SPY switch: the always-invested "
        "arm that prices the switch's habit apart from the opinion) and R1-BUF40-NOSW (the same "
        "for chance). The unbuffered ranked twins are M0417's IVOL and IVOL-NOSW and are read "
        "from there because a configuration runs once. Published 2006, so an edge from before "
        "the crowd may have faded. SUCCESS, written now: BUF40 trades at least 30% less than "
        "M0417's IVOL, beats SPY in 2009-2015 and beats both random buffered arms by more than "
        "their spread."
    ),
    expected_failure=(
        "Calm large caps trail SPY in a rising decade whatever the pick and the buffer only "
        "saves fees (M0344 and M0413 buffers moved return by under a point; M0424's buffer cut "
        "trades 53-75% with no edge). BUF40 lags SPY in 2009-2015, the random arms match or beat "
        "it, and the family is dropped after this one buffer test as M0417's analysis advised."
    ),
    candidates=(
        _v("BUF40", BufParams(N20, "ivol", 0, 40), "20 calmest, sell only below rank 40"),
        _v("BUF60", BufParams(N20, "ivol", 0, 60), "Wider buffer: sell only below rank 60"),
        _v("R1-BUF40", BufParams(N20, "blind", 419, 40), "Hash order, seed 419, same buffer"),
        _v("R2-BUF40", BufParams(N20, "blind", 420, 40), "Hash order, seed 420, same buffer"),
        _v("BUF40-NOSW", BufParams(NOSW, "ivol", 0, 40), "BUF40 with no SPY switch"),
        _v("R1-BUF40-NOSW", BufParams(NOSW, "blind", 419, 40), "Seed 419 buffered, no switch"),
    ),
    seen_keys=(
        "concept:low-idiosyncratic-volatility-rank-buffer",
        "concept:rank-buffer-hysteresis",
    ),
)
