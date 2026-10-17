"""M0198 — The placebo book weighted by company size: the same meaningless picks, sized by trading value.

Source: variation of M0187 (the placebo yardstick), reserved by Sera batch 20261017-1835. Not a
strategy. A yardstick that asks which half of the frame earns its lead.

Why it exists. Four rankings in a row (coskewness, beta-matched coskewness, steady alpha with and
without the switch) did no better than M0187: the same 20-slot quarterly frame filled in a hash
order that knows nothing about prices. So the frame earns the lead over SPY. The frame has two
parts that could do it: (1) the equal slots, which lean toward the smaller index members
compared with SPY's size weighting (insight 91), and (2) the screen, quarterly holding and keep
band. This method keeps (2) exactly and removes (1).

How. M0187's own ``choose`` picks the names, byte for byte (same hash, same eligibility, same
40% band, same quarterly re-pick months). This method then re-sizes those picks: each pick's
weight is proportional to its average daily trading value (close times volume) over the last 60
sessions ending on ``data_date``, a point-in-time size stand-in (the store has no sound market
caps; M0034 measured trading value against market value at a rank correlation of about 0.69).
The stock weights sum to what the equal book holds (picks / 20), so the dial moves money between
names and never changes how much is invested; unfilled slots go to SPY exactly as in M0187. No
name may hold more than 15% of the account: the excess is spread over the names still under the
ceiling (water-filling, M0034's ``_apply_ceiling``). Weights are recomputed at every monthly
check, so a held name drifts with its trading value; the book engine's resize band decides
whether that drift trades.

The paired control is the same allocator with ``weighting="equal"``: M0187's configuration
reached through this allocator, so the comparison sits inside one recorded batch.

Assumption (written before any result): the 60-day window was chosen over the screen's 20-day
one to make the size read steadier month to month and so trade less; trading value is a busy-ness
measure as well as a size one, so a stock in the news briefly weighs more than its size alone
would give it.

Pure: the hash is a function of its inputs and the weights read only bars dated <= ``data_date``.
Every variant sets ``trend`` explicitly (the ``FactorParams`` default is the SPY 200-day switch).

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0179_coskewness import CoskewPrepared
from seer_engine.lab.methods.m0187_placebo_hash_order import PlaceboAllocator, PlaceboParams, choose
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, factor_lookback, factor_rows, trend_on

ADDED = date(2026, 10, 17)

#: How the placebo's picks are sized. ``equal`` is M0187's; ``dv`` reads trading value.
WEIGHTINGS: tuple[str, ...] = ("equal", "dv")


@dataclass(frozen=True, slots=True)
class SizedPlaceboParams:
    """M0187's placebo (``placebo``) plus the sizing dial. ``cap`` is an absolute per-name ceiling
    (0.15 = 15% of the account); ``dv_n`` the trading-value window in sessions."""

    placebo: PlaceboParams
    weighting: str = "dv"
    cap: float | None = 0.15
    dv_n: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.placebo, PlaceboParams):
            raise TypeError(f"placebo must be PlaceboParams, got {type(self.placebo).__name__}")
        if self.weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be one of {WEIGHTINGS}, got {self.weighting!r}")
        if isinstance(self.dv_n, bool) or not isinstance(self.dv_n, int) or self.dv_n < 1:
            raise ValueError(f"dv_n must be a positive int, got {self.dv_n!r}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not (1.0 / self.placebo.inner.top <= float(self.cap) <= 1.0):
                raise ValueError(f"cap must lie in [1/top, 1], got {self.cap}")
            if self.weighting == "equal":
                raise ValueError("cap is meaningless on equal weights")

    def as_dict(self) -> dict[str, str]:
        out = {"weighting": self.weighting, "dv_n": str(self.dv_n),
               "cap": "none" if self.cap is None else repr(float(self.cap))}
        for k, v in self.placebo.as_dict().items():
            out[f"placebo.{k}"] = v
        return out


def _check(params: object) -> SizedPlaceboParams:
    if not isinstance(params, SizedPlaceboParams):
        raise TypeError(f"params must be SizedPlaceboParams, got {type(params).__name__}")
    return params


def trading_value(h: History, data_date: date, n: int) -> float:
    """Mean close times volume over the last ``n`` bars dated <= ``data_date`` (fewer if the
    history is shorter); 0.0 when there is no bar on ``data_date`` or the read is not finite."""
    i = h.index_of(data_date)
    if i is None:
        return 0.0
    lo = max(0, i + 1 - n)
    with np.errstate(invalid="ignore"):
        v = float(np.mean(h.close[lo : i + 1] * h.volume[lo : i + 1]))
    return v if np.isfinite(v) and v > 0.0 else 0.0


def sized_weights(dvs: list[float], top: int, p: SizedPlaceboParams) -> list[Decimal | None]:
    """One weight per pick, summing to len(dvs) / top: the equal book's exposure."""
    if not dvs:
        return []
    if p.weighting == "equal" or sum(dvs) <= 0.0:
        return [equal_weight(top) for _ in dvs]
    size = np.array(dvs, dtype=np.float64)
    w = size / float(size.sum()) * (len(dvs) / top)
    if p.cap is not None:
        w = _apply_ceiling(w, float(p.cap))
    return [_floor_weight(float(x)) for x in w]


def resize(history: Mapping[str, History], equal: tuple[Target, ...], data_date: date,
           p: SizedPlaceboParams) -> tuple[Target, ...]:
    """M0187's equal-slot targets with the stock slots re-sized and the remainder in SPY."""
    market = p.placebo.market
    picks = [t.symbol for t in equal if t.symbol != market]
    if p.weighting == "equal":
        return equal
    dvs = [trading_value(history[s], data_date, p.dv_n) for s in picks]
    out: list[Target] = []
    for s, w in zip(picks, sized_weights(dvs, p.placebo.inner.top, p), strict=True):
        if w is None:
            continue
        t = target_from_close(s, last_close(history[s], data_date), w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
    mh = history.get(market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class SizedPlaceboAllocator(PlaceboAllocator):
    """M0187's picks, sized by trading value under a per-name ceiling."""

    id = "M0198"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(factor_lookback(p.placebo.inner), p.dv_n)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params).placebo)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params).placebo)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _sized(self, prepared: CoskewPrepared, members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: SizedPlaceboParams) -> tuple[Target, ...]:
        q = p.placebo
        if not trend_on(prepared.history, data_date, q.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, q.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, q.inner)
        equal = choose(prepared.history, members, rows, data_date, held, q)
        return resize(prepared.history, equal, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._sized(CoskewPrepared(history, None), members, data_date, held, _check(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoskewPrepared):
            raise TypeError(f"prepared must be CoskewPrepared, got {type(prepared).__name__}")
        return self._sized(prepared, members, data_date, held, _check(params))


SIZED = SizedPlaceboAllocator()

SW = ("SPY", 200)


def _screen(top: int, trend: tuple[str, int] | None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _sized(seed: int, trend: tuple[str, int] | None = None) -> SizedPlaceboParams:
    return SizedPlaceboParams(PlaceboParams(_screen(20, trend), seed=seed))


def _v(suffix: str, params: SizedPlaceboParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0198-{suffix}", family="M0198", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SIZED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0198",
    name="The meaningless-order book weighted by company size: does the frame's lead over SPY survive without equal slots?",
    family="placebo-hash-order",
    source_kind="variation",
    source_ref="variation of M0187 (the placebo yardstick); reserved by Sera batch 20261017-1835",
    parent_id="M0187",
    hypothesis=(
        "Four rankings in a row did no better than the same 20-slot quarterly frame filled in a "
        "meaningless hash order (M0187), so the frame earns the lead over SPY. Which part: the "
        "equal slots (a lean toward smaller members, insight 91) or the screen and quarterly "
        "holding? Keep M0187's picks exactly (its own choose: hash, eligibility, 40% band, "
        "quarterly re-picks, unfilled slots in SPY) and size each pick by its 60-session average "
        "trading value, a point-in-time size stand-in, capped at 15% a name with the excess spread "
        "over the rest; the stock weights sum to what the equal book holds. Seeds 1-3 with no "
        "switch (trend explicitly None), seed 1 behind the SPY 200-day switch, and seed 1 at "
        "equal weight under this allocator as the paired control. Fractional shares at Gotrade's "
        "real fees on the owner's 5M IDR monthly top-up. Expected: the size-weighted seeds fall "
        "back toward SPY (funded about +7.5-9% a year against the equal book's +8.8-11.9% and "
        "SPY's +7.2%), with a lower beta gap to SPY, because the frame's lead was mostly the "
        "equal-weight lean of 1996-2008. If so every ranking in this frame must be judged against "
        "an equal-weight yardstick, not SPY. If the sized seeds keep most of the lead, the screen "
        "and holding are doing something worth naming. Not a published anomaly; evidence only, "
        "never to be promoted. Each variant's beta to SPY is reported in the analysis."
    ),
    expected_failure=(
        "Three ways this reads badly. (1) With a 15% ceiling and 20 names drawn from the screened "
        "members, a handful of giants can take half the book, so a seed's result may hinge on "
        "whether its hash happened to pick a Microsoft or a GE: the seed spread could widen until "
        "it says nothing. (2) Trading value is busy-ness as well as size; in 1999-2000 the busiest "
        "names were the bubble stocks, so the sized book may lean into the tech crash and fall "
        "harder than the equal one, the opposite of the size story. (3) Re-sizing monthly to a "
        "drifting trading value adds trades the equal book does not pay, so part of any shortfall "
        "may be Gotrade's fees on small resize orders rather than the shape. Expect the unswitched "
        "seeds to fall about 50% in 2008 like M0187's, and every seed to trail SPY in 2009-2015."
    ),
    candidates=(
        _v("EQ1", SizedPlaceboParams(PlaceboParams(_screen(20, None), seed=1), weighting="equal", cap=None),
           "Paired control: M0187's seed-1 book at equal weight, no switch, through this allocator"),
        _v("DV1", _sized(1),
           "Seed 1 picks sized by 60-session trading value, 15% cap, no switch"),
        _v("DV2", _sized(2),
           "Seed 2 picks sized by 60-session trading value, 15% cap, no switch"),
        _v("DV3", _sized(3),
           "Seed 3 picks sized by 60-session trading value, 15% cap, no switch"),
        _v("DV1-SW", _sized(1, SW),
           "Seed 1 sized by trading value, 15% cap, behind the SPY 200-day switch"),
    ),
    seen_keys=(
        "concept:size-weighted-placebo",
        "concept:equal-weight-lean-test",
    ),
)
