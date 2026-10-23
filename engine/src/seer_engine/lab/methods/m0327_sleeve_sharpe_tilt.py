"""M0327 — Time the sleeves by their own recent record: tilt a momentum sleeve and a calm-stock sleeve.

Source: Favero, Melone & Tamoni, "Factor models with drifting prices" / anomaly timing (a factor's
past cumulative risk-adjusted return predicts its next return; published 2020s, so expect the
edge to be thin by now). The sleeves are the lab's own: M0007-N20-RAW's residual-momentum top 20
and F5-LV60-N20-TREND's calm 20, the two halves of M0021/M0029.
Idea: M0029 holds them at a fixed 70/30. Instead of a switch that steps out of the market (the
timing family the lab has rejected over and over), keep the book fully in the same two sleeves and
only move the *split* between 25% and 75% each month, toward whichever sleeve had the better
trailing 12-month Sharpe ratio. Each sleeve's "own record" is shadow-built from its own rule: at
each of the last 12 month-ends, its picks are re-derived from bars dated <= that day and the
equal-weight next-month return of the picks is taken (cash when the SPY filter had the sleeve out).

Disclosed approximation: the shadow picks are drawn from the index members of the decision day,
not of the past month-end (the allocator is handed no older membership). That is survivor-flavoured
and lifts both sleeves' shadow record alike; the tilt reads the *difference*, and the mirror arm
(REV) and the fixed split (FIX) run through the identical machinery, so a bias that moves both
sleeves together does not move the comparison.

Arms (one look, one method): TILT (toward the stronger), REV (toward the weaker, the mirror),
FIX (50/50, opinion removed, same sleeves, same filter), SPY (always invested in SPY: prices the
habit of holding a stock book at all). Every arm trades fractional shares at Gotrade's real fees.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import (
    BLEND,
    BlendParams,
    BlendPart,
    LazyPrepared,
    last_close,
    target_from_close,
)
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FACTOR, FactorParams

ADDED = date(2026, 10, 23)

CALM20 = FactorParams(rank="lowvol", top=20)  # F5-LV60-N20-TREND's book, verbatim
SPY = "SPY"
MONTHS = 12  # months of shadow record each sleeve is judged on
MODES = ("tilt", "rev", "fix", "spy")


@dataclass(frozen=True, slots=True)
class TiltParams:
    mode: str = "tilt"
    strength: float = 0.25  # share moved per point of annualised Sharpe gap
    lo: float = 0.25  # momentum sleeve's floor share
    hi: float = 0.75  # and its cap

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        for name in ("strength", "lo", "hi"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, float):
                raise TypeError(f"{name} must be a float, got {type(v).__name__}")
        if not 0.0 < self.lo <= 0.5 <= self.hi < 1.0:
            raise ValueError(f"need 0 < lo <= 0.5 <= hi < 1, got {self.lo}, {self.hi}")

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "strength": repr(self.strength), "lo": repr(self.lo),
                "hi": repr(self.hi)}


def _check(params: object) -> TiltParams:
    if not isinstance(params, TiltParams):
        raise TypeError(f"params must be TiltParams, got {type(params).__name__}")
    return params


class Prepared:
    """The blend's lazy per-sleeve preparation plus the shadow-return cache.

    The cache key carries the member set, because a shadow pick depends on it: a hit is then exactly
    the value a fresh call would give, so a call's result never depends on which dates ran before.
    """

    __slots__ = ("cache", "lazy")

    def __init__(self, history: Mapping[str, History]) -> None:
        self.lazy = LazyPrepared(history)
        self.cache: dict[tuple[Any, ...], float] = {}


def month_ends(spy: History | None, data_date: date, n: int) -> list[date]:
    """The last ``n`` completed month-end sessions on or before d, oldest first (SPY's calendar)."""
    if spy is None:
        return []
    dts = spy.dates[spy.dates <= np.datetime64(data_date)]
    if dts.shape[0] == 0:
        return []
    months = dts.astype("datetime64[M]")
    last_of_month = np.append(months[1:] != months[:-1], True)
    ends = dts[last_of_month]
    # The final month is complete only if d is its last session in the history (a month-end on d).
    if ends.shape[0] and ends[-1] != dts[-1]:
        ends = ends[:-1]
    out = [e.astype("datetime64[D]").astype(date) for e in ends[-n:]]
    return out


def _shadow_return(prep: Prepared, history: Mapping[str, History], sleeve: Any, sp: Any,
                   members: AbstractSet[str], e0: date, e1: date) -> float:
    key = (sleeve.id, e0, e1, frozenset(members))
    got = prep.cache.get(key)
    if got is not None:
        return got
    tg = sleeve.targets_prepared(prep.lazy.of(sleeve), members, e0, frozenset(), sp)
    ret = 0.0
    for t in tg:
        h = history.get(t.symbol)
        c0, c1 = last_close(h, e0), last_close(h, e1)
        if c0 is None or c1 is None or c0 <= 0.0:
            continue
        ret += float(t.weight) * (c1 / c0 - 1.0)
    prep.cache[key] = ret
    return ret


def _sharpe(rets: list[float]) -> float:
    a = np.asarray(rets, dtype=np.float64)
    sd = float(a.std(ddof=1)) if a.shape[0] > 1 else 0.0
    if sd < 1e-9:
        return 0.0
    return float(a.mean()) / sd * math.sqrt(12.0)


def momentum_share(prep: Prepared, history: Mapping[str, History], members: AbstractSet[str],
                   data_date: date, p: TiltParams) -> float:
    """The momentum sleeve's share of equity: 0.5 unless the mode tilts, then clipped and on a 5% grid."""
    if p.mode == "fix":
        return 0.5
    ends = month_ends(history.get(SPY), data_date, MONTHS + 1)
    if len(ends) < MONTHS + 1:
        return 0.5  # not enough record to judge: neutral, identical across the tilting arms
    mom, calm = [], []
    for e0, e1 in zip(ends[:-1], ends[1:], strict=True):
        mom.append(_shadow_return(prep, history, RESIDMOM, RAW20, members, e0, e1))
        calm.append(_shadow_return(prep, history, FACTOR, CALM20, members, e0, e1))
    gap = _sharpe(mom) - _sharpe(calm)
    sign = 1.0 if p.mode == "tilt" else -1.0
    w = min(p.hi, max(p.lo, 0.5 + sign * p.strength * gap))
    return round(w * 20.0) / 20.0


class SleeveTiltAllocator:
    """Fully in two sleeves (momentum, calm), the split set monthly from their trailing Sharpe gap."""

    id = "M0327"

    def _blend(self, w: float) -> BlendParams:
        mom = Decimal(str(round(w, 2)))
        return BlendParams((BlendPart(RESIDMOM, RAW20, mom), BlendPart(FACTOR, CALM20, Decimal(1) - mom)))

    def lookback(self, params: Any) -> int:
        _check(params)
        # The sleeves' own, identical on every arm so all four start on the same session. The 13
        # month-ends of shadow record are not required: until they exist the split is a neutral
        # 50/50 on every tilting arm, which keeps the arms comparable from the first month.
        return max(RESIDMOM.lookback(RAW20), FACTOR.lookback(CALM20))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        if p.mode == "spy":
            return (SPY,)
        return BLEND.symbols(self._blend(0.5))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        if p.mode == "spy":
            return (SPY,)
        return BLEND.holds(self._blend(0.5))

    def uses_members(self, params: Any) -> bool:
        return _check(params).mode != "spy"

    def _spy(self, history: Mapping[str, History], data_date: date, held: frozenset[str]) -> tuple[Target, ...]:
        h = history.get(SPY)
        if h is None or (h.index_of(data_date) is None and SPY not in held):
            return ()
        t = target_from_close(SPY, last_close(h, data_date), to_weight(1.0))
        return (t,) if t is not None else ()

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets_prepared(self.prepare(history), members, data_date, held, params)

    def prepare(self, history: Mapping[str, History]) -> Prepared:
        return Prepared(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Prepared):
            raise TypeError(f"prepared must be Prepared, got {type(prepared).__name__}")
        p = _check(params)
        history = prepared.lazy.history
        if p.mode == "spy":
            return self._spy(history, data_date, held)
        w = momentum_share(prepared, history, members, data_date, p)
        return BLEND.targets_prepared(prepared.lazy, members, data_date, held, self._blend(w))


ALLOC = SleeveTiltAllocator()


def _v(suffix: str, params: TiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0327-{suffix}", family="M0327", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0327",
    name="Time the sleeves by their own recent risk-adjusted record: weights shift between a "
         "momentum sleeve and a calm-stock sleeve",
    family="stock-factor-timing",
    source_kind="paper",
    source_ref="Favero, Melone & Tamoni, factor/anomaly timing from past cumulative risk-adjusted "
               "returns; sleeves from M0021/M0029 (residual-momentum top 20 + calm 20)",
    parent_id="M0029",
    hypothesis=(
        "M0029 holds a fixed 70/30 split of residual momentum and calm stocks. A factor's own "
        "trailing 12-month Sharpe ratio is said to predict its next month, so moving the split "
        "between 25% and 75% toward the sleeve with the better record (TILT) should beat the "
        "fixed 50/50 (FIX) by a point or two a year and cut the worst fall slightly, without "
        "ever stepping out of the stocks. REV (tilt to the weaker) is the mirror: if the signal "
        "is real REV must lose to FIX; if REV also beats FIX the gain is the sleeve mix, not the "
        "timing. SPY (always invested in the fund) prices the habit of holding a stock book: the "
        "yardstick for whether either sleeve mix earns its fees. Published in the 2020s, a "
        "widely read idea in a window ending 2015: any dev edge is expected to be thin, and "
        "2009-2015, a narrow cap-weighted bull market with no bear, is the first filter."
    ),
    expected_failure=(
        "Sleeve Sharpe ratios over 12 months are noise: the gap flips sign most months, so TILT "
        "churns between mixes and pays fees on the swap for nothing, landing within a point of "
        "FIX with REV equally close. Both mixes then trail SPY in 2009-2015 as the calm sleeve "
        "lags a rising market and the SPY filter's cash months cost the momentum sleeve."
    ),
    candidates=(
        _v("TILT", TiltParams("tilt"), "Tilt toward the sleeve with the better trailing 12-month Sharpe"),
        _v("REV", TiltParams("rev"), "Mirror: tilt toward the weaker sleeve"),
        _v("FIX", TiltParams("fix"), "Fixed 50/50, same sleeves and filter: opinion removed"),
        _v("SPY", TiltParams("spy"), "Always invested in SPY: prices holding a stock book at all"),
    ),
    seen_keys=(
        "concept:factor-timing-sleeve-tilt",
        "concept:trailing-sharpe-factor-timing",
    ),
)
