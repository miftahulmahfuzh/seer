"""M0417 — Hold the index members with the lowest residual volatility (the part SPY does not explain).

Source: Ang, Hodrick, Xing and Zhang (2006), "The Cross-Section of Volatility and Expected
Returns", Journal of Finance. Published 2006, and the low-volatility family has been traded hard
since, so the dev window (to 2015) can only show an edge from before the crowd, and the risk is
that it fades; named here, not discovered later.

The frame is M0412's: point-in-time members, the F4 screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, the SPY 200-day switch on every arm but two. The key is the standard
deviation of the market-model residual over the last 63 daily returns ending on data_date
(residual = stock return - beta * SPY return, beta fitted on the same window). Names with a missing
bar, a bar date SPY lacks, or a non-positive price are not scored, identically in every arm. This
differs from the lab's calm-tilt and market-beta families, which rank on raw volatility or on beta.

Arms (six, the lab's cap): IVOL holds the 20 lowest residual volatility, TVOL the 20 lowest raw
volatility (the mechanism control: is the residual step doing anything), R1 and R2 hash-rank the
pool behind the switch, IVOL-NOSW is IVOL's order with no switch (the always-invested arm that
prices the switch's habit apart from the opinion), R1-NOSW the same for chance.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
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

ADDED = date(2026, 11, 1)

MODES = ("ivol", "tvol", "blind")
WIN = 63  # daily returns in the volatility window
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class IvolParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "ivol"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> IvolParams:
    if not isinstance(params, IvolParams):
        raise TypeError(f"params must be IvolParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float]]:
    """(residual std, raw std) of daily returns per scorable name over the last WIN returns.

    Residual = return - beta * SPY return, beta = cov/var on the same window. Raw std is the plain
    standard deviation of the stock's returns. Names whose last WIN+1 bar dates SPY does not also
    have, or with a non-finite or non-positive close, are not scored."""
    spy = history.get(MARKET)
    if spy is None:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        d = h.dates[i - WIN : i + 1]
        k = np.searchsorted(spy.dates, d)
        if k.max(initial=0) >= len(spy.dates) or not np.array_equal(spy.dates[k], d):
            continue
        c = h.close[i - WIN : i + 1]
        mc = spy.close[k]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)
                and np.all(np.isfinite(mc)) and np.all(mc > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        m = mc[1:] / mc[:-1] - 1.0
        vm = float(np.var(m))
        if not vm > 0.0:
            continue
        beta = float(np.mean((r - r.mean()) * (m - m.mean())) / vm)
        e = r - beta * m
        out[s] = (float(np.std(e)), float(np.std(r)))
    return out


def choose(rows: list[FactorRow], stats: dict[str, tuple[float, float]], params: IvolParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in stats]
    if params.mode == "ivol":
        key = {r.symbol: stats[r.symbol][0] for r in pool}
    elif params.mode == "tvol":
        key = {r.symbol: stats[r.symbol][1] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class IvolPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class IvolAllocator:
    """The lab's index-member book ranked on trailing residual (or raw) volatility, lowest first."""

    id = "M0417"

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
             members: AbstractSet[str], data_date: date, p: IvolParams) -> tuple[Target, ...]:
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
        return targets_from_rows(choose(rows, stats, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IvolPrepared:
        return IvolPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IvolPrepared):
            raise TypeError(f"prepared must be IvolPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


IVOL = IvolAllocator()


def _v(suffix: str, params: IvolParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0417-{suffix}", family="M0417",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=IVOL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0417",
    name="Low idiosyncratic volatility: hold the stocks whose daily moves are least explained by SPY noise",
    family="stock-idiosyncratic-volatility",
    source_kind="paper",
    source_ref="Ang, Hodrick, Xing, Zhang 2006, The Cross-Section of Volatility and Expected Returns",
    parent_id=None,
    hypothesis=(
        "Rank index members by the standard deviation of their trailing 63-day residual returns "
        "after a regression on SPY (market-model residual volatility), hold the 20 lowest, "
        "monthly, fractional shares at Gotrade real fees (-frac-gotrade preset). Published 2006, "
        "so the dev window to 2015 can only show an edge from before the crowd traded it, and "
        "the lab's calm and market-beta books, which rank on raw volatility or beta, are the "
        "near neighbours. Arms: IVOL (20 lowest residual volatility behind SPY's 200-day "
        "switch), TVOL (20 lowest raw volatility, the mechanism control: does removing the "
        "market part change anything), R1 and R2 (hash order, same pool, same switch), "
        "IVOL-NOSW (IVOL's order with no switch: the always-invested arm that prices the "
        "switch's habit apart from the signal) and R1-NOSW (chance, no switch). SUCCESS: IVOL "
        "beats the better of R1 and R2 by more than their spread plus 2 points a year, with a "
        "positive 2009-2015 edge versus SPY. Predictions, written now: IVOL and TVOL land within "
        "2 points a year of each other; both beat the random pair on worst fall but not on "
        "return; both trail SPY in 2009-2015 because low-risk books sit out a rising decade."
    ),
    expected_failure=(
        "Low residual volatility in large index members is mostly a utilities-and-staples "
        "tilt, so the book is a defensive sleeve that trails SPY in a bull market (insight 91 "
        "territory) and looks the same as TVOL. The edge, if any, is the lower fall, which "
        "the switch already supplies, so IVOL-NOSW and the switched arm differ by the switch "
        "alone. Two hash draws are a thin chance spread. A published anomaly, likely faded "
        "after 2006. If so, a follow-up pairs it with a size floor or tests the high-residual "
        "(lottery) side as a reversed arm."
    ),
    candidates=(
        _v("IVOL", IvolParams(N20, "ivol"),
           "The 20 lowest 63-day residual volatility on SPY, behind the SPY switch"),
        _v("TVOL", IvolParams(N20, "tvol"),
           "Mechanism control: the 20 lowest raw 63-day volatility, behind the switch"),
        _v("R1", IvolParams(N20, "blind", 417),
           "Control: hash-ranked scored pool, seed 417, behind the switch"),
        _v("R2", IvolParams(N20, "blind", 418),
           "Control: hash-ranked scored pool, seed 418, behind the switch"),
        _v("IVOL-NOSW", IvolParams(NOSW, "ivol"),
           "No-switch twin of IVOL: always invested, prices the switch's habit"),
        _v("R1-NOSW", IvolParams(NOSW, "blind", 417),
           "No-opinion always-invested arm: R1's order with no switch"),
    ),
    seen_keys=(
        "concept:low-idiosyncratic-volatility",
        "doi:10.1111/j.1540-6261.2006.00836.x",
    ),
)
