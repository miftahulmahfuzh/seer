"""M0606 — Shallow-fall stocks behind the SPY 200-day switch, against blind draws.

Source: "Maximum Drawdown, Recovery, and Momentum", Journal of Risk and Financial Management
14(11) 542 (2021), doi:10.3390/jrfm14110542; arXiv 1403.8125 (maximum drawdown as a model-free
risk measure) for the measure itself. Published 2014 / 2021, so the dev window (ends 2015) sees
the shape-of-loss rank before the crowd traded this form of it, and it sits beside the low-risk
anomaly (Ang, Hodrick, Xing & Zhang 2006), which has faded since.

**What M0108 left open.** M0108 ranked each index member on its own worst peak-to-trough fall
over 252 sessions and held the 20 mildest, *always invested*. It was rejected: the ranking picked
better companies, but the book still fell 42% because a company's own past fall says nothing
about the day every company falls at once. Every near miss in this lab that keeps a worst fall
under the bar does it with the SPY 200-day switch, and M0108 deliberately left the switch off so
the stock rank would not be confounded. The question M0606 asks is the one that was left:
**does the shallow-fall rank add anything once the switch has already taken the crash away?**
If the switch does all the work, a blind draw of the same pool behind the same switch should do
as well. That is the control this method exists to run.

Arms (all on ``monthly-hold-frac-gotrade``: fractional shares, Gotrade's real fees):

- ``SHALLOW20-GATE``: the 20 mildest-fall members, switch on. The treatment.
- ``SHALLOW20-NOGATE``: the same rank, switch off. **Control: it is M0108-DD20's book** (the
  same screen, window, size and weights; only the allocator id differs). It is registered to
  re-measure that book beside the treatment, not as a new result.
- ``DRAW20-GATE-S1`` and ``-S2``: 20 members drawn blind from the same pool (those with a
  measurable fall), re-drawn monthly from a hash of seed, symbol and month, switch on. The
  matched random control: same pool, same pace, same switch, no opinion. Two seeds, because one
  draw is a coin and the lab has measured how wide that coin is.
- ``EW20-DV-GATE``: the 20 most-traded members, switch on. The no-opinion arm for the dressing
  question: same switch, a plain big-name book, no fall rank.
- ``DEEP20-GATE``: the 20 deepest-fall members, switch on. The mirror, which must trail the
  treatment if the rank is real; it reverses the treatment, so EW20-DV-GATE and the draws price
  what acting on the signal costs beside it.

Assumptions, written before the run: the pool is F4's screen (point-in-time S&P 500 / Nasdaq-100
members, $5 price, 20M-dollar volume) restricted to names with a full 252-close window; the
switch is F4's (SPY close above its 200-day average, else all cash); bars are split- and
dividend-adjusted so an ex-dividend day is not read as a fall; reads only bars dated <= d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0108_own_drawdown_resilience import (
    N20 as N20_NOTREND,
)
from seer_engine.lab.methods.m0108_own_drawdown_resilience import (
    own_drawdown,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 13)

Side = Literal["shallow", "deep", "draw", "traded"]
_SIDES: tuple[str, ...] = ("shallow", "deep", "draw", "traded")


@dataclass(frozen=True, slots=True)
class ShallowParams:
    """``inner`` is F4's screen, size, weights and (or not) the switch; the rest is the rank."""

    inner: FactorParams
    side: Side = "shallow"
    window: int = 252
    seed: int = 0  # only read when side == "draw"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if isinstance(self.window, bool) or not isinstance(self.window, int) or self.window < 21:
            raise ValueError(f"window must be an int >= 21, got {self.window!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "window": str(self.window), "seed": str(self.seed)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> ShallowParams:
    if not isinstance(params, ShallowParams):
        raise TypeError(f"params must be ShallowParams, got {type(params).__name__}")
    return params


def _hash_key(seed: int, symbol: str, data_date: date) -> str:
    raw = f"{seed}|{symbol}|{data_date.year}-{data_date.month:02d}".encode()
    return hashlib.blake2b(raw, digest_size=8).hexdigest()


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: ShallowParams) -> list[FactorRow]:
    """The chosen rows; the pool is every screened row with a measurable fall, for every side."""
    scored: list[tuple[Any, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED:
            continue
        h = history.get(r.symbol)
        if h is None:
            continue
        x = own_drawdown(h, data_date, params.window)
        if x is None:
            continue
        if params.side == "shallow":
            key: Any = x
        elif params.side == "deep":
            key = -x
        elif params.side == "traded":
            key = -r.dollar_volume
        else:
            key = _hash_key(params.seed, r.symbol, data_date)
        scored.append((key, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def targets_from_rows(chosen: list[FactorRow], params: ShallowParams) -> tuple[Target, ...]:
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.inner), strict=True):
        if weight is None:
            continue
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass
class ShallowPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class ShallowFallAllocator:
    """F4's screen ranked (or drawn) on own worst fall; all cash when the SPY switch is off."""

    id = "M0606"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.inner), p.window)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, history, data_date, p), p)

    def prepare(self, history: Mapping[str, History]) -> ShallowPrepared:
        return ShallowPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ShallowPrepared):
            raise TypeError(f"prepared must be ShallowPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, p), p)


SHALLOW = ShallowFallAllocator()
GATED = N20  # F4's screen, 20 equal slots, SPY 200-day switch on
OPEN = replace(N20_NOTREND)  # the same with the switch off


def _v(suffix: str, params: ShallowParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0606-{suffix}", family="M0606",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=SHALLOW, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0606",
    name=("Shallow-fall stocks: rank index members by their smallest worst-peak-to-trough fall "
          "over the past year, behind the 200-day switch, against random draws"),
    family="stock-max-drawdown-rank",
    source_kind="paper",
    source_ref=("Maximum Drawdown, Recovery, and Momentum, J. Risk Financial Management 14(11) "
                "542 (2021), doi:10.3390/jrfm14110542; arXiv 1403.8125"),
    parent_id=None,
    hypothesis=(
        "M0108 held the 20 index members with the mildest own worst fall over 252 sessions, "
        "always invested, and was rejected: better companies, but the book fell 42% against a "
        "20% limit because one company's past fall says nothing about the day every company "
        "falls. This puts the SPY 200-day switch behind the same rank and asks whether the rank "
        "adds anything once the switch has taken the crash away. Each month, among F4-screened "
        "point-in-time S&P 500 / Nasdaq-100 members with a full 252-close window, hold the 20 "
        "mildest, equal weight, fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade), all cash when SPY is below its 200-day average. Arms: "
        "SHALLOW20-GATE (treatment); SHALLOW20-NOGATE (Control: M0108-DD20's book, re-measured "
        "beside the treatment, not a new result); DRAW20-GATE-S1 and -S2 (20 names drawn blind "
        "from the same pool every month, same switch, the matched random control); EW20-DV-GATE "
        "(the 20 most-traded names behind the switch, the no-opinion arm); DEEP20-GATE (the 20 "
        "deepest-fall names, the mirror). Success: SHALLOW20-GATE beats SPY TR on deposit-matched "
        "money with worst fall under 20%, PF >= 1.3, 100+ trades, beats both blind draws and "
        "EW20-DV-GATE, and the mirror trails it. Closest recorded: M0108 (same rank, no switch), "
        "M0110 (shelter works and is not enough), M0278 and M0283 (calm books trail SPY after "
        "2009). The measure is from 2014/2021 and the low-risk anomaly beside it has been traded "
        "since 2006."
    ),
    expected_failure=(
        "The switch does all the work: the blind draws behind it land within the draw noise of "
        "the treatment, so the fall rank adds nothing. Second, the rank collapses onto low "
        "volatility in large caps, and a calm book behind a switch trails SPY after 2009, the "
        "most SPY-like years, where the switch's time in cash and the fees on monthly turnover "
        "are the real cost. Third, before 2008 the mildest-fall names were financials and "
        "utilities, the groups that then fell hardest, so the rank may pick the wrong shelter "
        "in precisely the crash the switch is late to leave."
    ),
    candidates=(
        _v("SHALLOW20-GATE", ShallowParams(GATED, side="shallow"),
           "The 20 mildest-fall members behind the SPY 200-day switch: the treatment"),
        _v("SHALLOW20-NOGATE", ShallowParams(OPEN, side="shallow"),
           "Control: M0108-DD20's book (same rank, switch off), re-measured beside the treatment"),
        _v("DRAW20-GATE-S1", ShallowParams(GATED, side="draw", seed=1),
           "Control: 20 names drawn blind from the same pool, same switch, seed 1"),
        _v("DRAW20-GATE-S2", ShallowParams(GATED, side="draw", seed=2),
           "Control: 20 names drawn blind from the same pool, same switch, seed 2"),
        _v("EW20-DV-GATE", ShallowParams(GATED, side="traded"),
           "Control: the 20 most-traded members behind the switch, no fall rank in it"),
        _v("DEEP20-GATE", ShallowParams(GATED, side="deep"),
           "The 20 deepest-fall members behind the switch: the mirror, must trail the treatment"),
    ),
    seen_keys=(
        "concept:own-max-drawdown-cross-section",
        "concept:shallow-fall-rank-behind-switch",
        "doi:10.3390/jrfm14110542",
    ),
)
