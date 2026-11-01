"""M0480 — Staying power: hold the stocks that have stayed in the top fifth of 12-1 momentum longest.

Source: Grinblatt and Moskowitz (2004), "Predicting stock price movements from past returns: the
role of consistency and tax-loss selling" (JFE). Published 22 years ago, so a dev edge is likely
already traded away. M0402 read the same paper as steadiness of daily moves and found it barely
better than a random pick; this reads it as rank persistence: how many month-ends in a row a
stock has stayed in the top fifth of the 12-1 momentum ranking.

The frame is M0480's: F4 screen, 20 equal slots, monthly, fractional shares at Gotrade's real
fees, SPY 200-day switch on every arm but one. The pool is the names in the top fifth today.
The key is the streak: month-ends are taken as every 21st SPY bar back from data_date, up to 9;
the streak counts back until the first one at which the name was outside the top fifth of the
eligible names then (ranked on the same members as today: point-in-time membership for past
dates is not read, a small known blur). Ties break on momentum, then symbol.

Arms (six): MOM plain top-20 momentum (control), VET the 20 longest streaks, NEW the 20 shortest
(the reversed arm), R1 and R2 hash draws of 20 from the same pool, VET-NOSW is VET with no switch.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

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
STEP = 21  # SPY bars per month-end
MAXK = 9  # month-ends read back

MODES = ("mom", "new", "vet", "blind")
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class StayParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "mom"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "step": str(STEP), "maxk": str(MAXK)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> StayParams:
    if not isinstance(params, StayParams):
        raise TypeError(f"params must be StayParams, got {type(params).__name__}")
    return params


def month_ends(history: Mapping[str, History], data_date: date) -> list[date]:
    """data_date and every 21st SPY bar before it, newest first, up to MAXK + 1 dates."""
    h = history.get(MARKET)
    if h is None:
        return []
    i = h.index_of(data_date)
    if i is None:
        return []
    out = []
    for k in range(MAXK + 1):
        j = i - k * STEP
        if j < 0:
            break
        out.append(h.dates[j].astype("datetime64[D]").item())
    return out


def top_fifth(rows: list[FactorRow]) -> frozenset[str]:
    ok = sorted((r for r in rows if r.symbol not in EXCLUDED), key=lambda r: (-r.momentum, r.symbol))
    return frozenset(r.symbol for r in ok[: -(-len(ok) // 5)])


def streaks(dates: list[date], tops: dict[date, frozenset[str]]) -> dict[str, int]:
    """Consecutive month-ends, newest first, a name has sat in the top fifth (0 when not today)."""
    out: dict[str, int] = {}
    for s in tops[dates[0]]:
        n = 0
        for d in dates:
            if s in tops[d]:
                n += 1
            else:
                break
        out[s] = n
    return out


def choose(rows: list[FactorRow], streak: dict[str, int], params: StayParams) -> list[FactorRow]:
    ranked = sorted((r for r in rows if r.symbol not in EXCLUDED), key=lambda r: (-r.momentum, r.symbol))
    if params.mode == "mom":
        return ranked[: params.inner.top]
    pool = [r for r in ranked if r.symbol in streak]
    if params.mode == "vet":
        key = {r.symbol: -streak[r.symbol] for r in pool}
    elif params.mode == "new":
        key = {r.symbol: streak[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], -r.momentum, r.symbol))
    return pool[: params.inner.top]


@dataclass
class StayPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, frozenset[str]] = field(default_factory=dict, repr=False)


class StayAllocator:
    """The lab's index-member book ranked on how long a name has stayed in the top momentum fifth."""

    id = "M0480"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner) + STEP * MAXK + 5

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

    def _run(self, prepared: StayPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: StayParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            def rows_at(d: date) -> list[FactorRow]:
                return factor_rows(history, members, d, p.inner)
        else:
            def rows_at(d: date) -> list[FactorRow]:
                return prepared.factor.rows_on(members, d, p.inner)
        rows = rows_at(data_date)
        streak: dict[str, int] = {}
        if p.mode != "mom":
            dates = month_ends(history, data_date)
            tops: dict[date, frozenset[str]] = {}
            for d in dates:
                if d == data_date:
                    tops[d] = top_fifth(rows)
                elif prepared is not None and d in prepared.cache:
                    tops[d] = prepared.cache[d]
                else:
                    tops[d] = top_fifth(rows_at(d))
            if dates:
                streak = streaks(dates, tops)
        return targets_from_rows(choose(rows, streak, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> StayPrepared:
        return StayPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, StayPrepared):
            raise TypeError(f"prepared must be StayPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


STAY = StayAllocator()


def _v(suffix: str, params: StayParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0480-{suffix}", family="M0480",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=STAY, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0480",
    name="Staying power: hold the stocks that have stayed in the top fifth of 12-1 momentum for the most months in a row",
    family="stock-rank-persistence",
    source_kind="paper",
    source_ref="Grinblatt and Moskowitz (2004), consistency of past returns, JFE, rank-persistence reading",
    parent_id=None,
    hypothesis=(
        "Grinblatt and Moskowitz (2004), published 2004: consistent past winners keep winning. "
        "Among F4-screened point-in-time index members, take the names in today's top fifth of "
        "12-1 momentum and rank them by how many consecutive month-ends (every 21st SPY bar, up "
        "to 9) they have stayed in the top fifth. Hold 20 equal slots, monthly, fractional "
        "shares at Gotrade's real fees, behind SPY's 200-day switch. Arms: MOM (plain top-20 "
        "momentum, control), VET (longest streaks), NEW (shortest streaks, the reversed arm), "
        "R1 and R2 (hash draws of 20 from the same top-fifth pool, the blind pair), VET-NOSW "
        "(VET with no switch, prices the switch's habit). SUCCESS: VET beats the better of MOM, "
        "R1 and R2 by more than the blind pair's spread plus 2 points a year, NEW loses to VET, "
        "and VET has a positive 2009-2015 edge vs SPY. Predictions, written now: VET and MOM "
        "differ by under 2 points a year in return; NEW and the blind draws are within 2 points "
        "of each other; all trail SPY in 2009-2015; VET-NOSW falls over 35%."
    ),
    expected_failure=(
        "Veterans simply are the plain 12-1 book and trade less, so any lead is trading pace and "
        "not signal; the blind draws from the same pool match VET. The pool is wide (a fifth of "
        "~300 names) so the filter has reach, but the switch does the work (M0412, M0425). "
        "Published 22 years ago, so a dev edge is likely to fade; 2009-2015 trails SPY. Past "
        "ranks use today's members, a small blur."
    ),
    candidates=(
        _v("MOM", StayParams(N20, "mom"),
           "Control: plain top-20 12-1 momentum, behind the switch"),
        _v("VET", StayParams(N20, "vet"),
           "20 names with the longest run of month-ends in the top fifth"),
        _v("NEW", StayParams(N20, "new"),
           "20 names with the shortest run: the reversed arm"),
        _v("R1", StayParams(N20, "blind", 480),
           "Control: hash draw of 20 from today's top fifth, seed 480, behind the switch"),
        _v("R2", StayParams(N20, "blind", 481),
           "Control: hash draw of 20 from today's top fifth, seed 481, behind the switch"),
        _v("VET-NOSW", StayParams(NOSW, "vet"),
           "No-switch twin of VET: always invested, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:rank-persistence",
    ),
)
