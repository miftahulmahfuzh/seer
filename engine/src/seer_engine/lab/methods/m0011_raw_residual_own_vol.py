"""M0011 — Raw residual momentum under an own-volatility target.

Source: variation of M0007 (Blitz, Huij & Martens 2011, residual momentum) with M0001's overlay
(Barroso & Santa-Clara 2015, own-volatility scaling).
Idea: M0007-N20-RAW is the lab's best dev book by MAR (0.77: CAGR +15.0%, max DD 19.6%) and fails
only the 15% drawdown limit. M0001's own-volatility overlay took the total-return momentum book
from a 22.2% to a 12.9% max DD at about 0.8 CAGR points per DD point. Applied to the residual book,
which starts with more return per unit of fall, the same exchange rate should land inside 15%
while still beating SPY TR.

The allocator takes M0007's targets unchanged (raw cumulative residual, F4's screen, SPY-200 trend
gate, equal weights) and scales every weight by min(1, target_vol / the target basket's own
annualized volatility over the last ``n`` daily returns through d), exactly as M0001 does
(``basket_scale``). Freed weight is cash. No leverage.
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
from seer_engine.lab.methods.m0001_momentum_own_vol_scaling import _scaled, basket_scale
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    N30,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 6)


@dataclass(frozen=True, slots=True)
class ResidVolParams:
    inner: ResidParams
    target_vol: Decimal = Decimal("0.14")
    n: int = 63

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not isinstance(self.target_vol, Decimal) or not self.target_vol > 0:
            raise ValueError(f"target_vol must be a positive Decimal, got {self.target_vol!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 5:
            raise ValueError(f"n must be an int >= 5, got {self.n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"target_vol": str(self.target_vol), "n": str(self.n)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ResidVolParams:
    if not isinstance(params, ResidVolParams):
        raise TypeError(f"params must be ResidVolParams, got {type(params).__name__}")
    return params


class ResidOwnVolAllocator:
    """M0007's residual-momentum targets scaled by target_vol / the basket's own realized vol."""

    id = "M0011"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(RESIDMOM.lookback(p.inner), p.n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        return RESIDMOM.uses_members(_check(params).inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = RESIDMOM.targets(history, members, data_date, held, p.inner)
        return _scaled(inner, basket_scale(history, inner, data_date, p.n, p.target_vol))

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = RESIDMOM.targets_prepared(prepared, members, data_date, held, p.inner)
        return _scaled(inner, basket_scale(prepared.history, inner, data_date, p.n, p.target_vol))


RESIDVOL = ResidOwnVolAllocator()
RAW20 = ResidParams(N20, scaled=False)  # M0007-N20-RAW's params, verbatim
RAW30 = ResidParams(N30, scaled=False)


def _v(suffix: str, params: ResidVolParams, rationale: str, rules=MONTHLY_HOLD) -> Candidate:
    return Candidate(id=f"M0011-{suffix}", family="M0011", rules=rules, allocator=RESIDVOL,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0011",
    name="Raw residual momentum under an own-volatility target (M0007-N20-RAW + M0001 overlay)",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="M0007 (M0007-N20-RAW) + M0001 own-vol overlay; Blitz, Huij & Martens (2011); "
               "Barroso & Santa-Clara (2015)",
    parent_id="M0007",
    hypothesis=(
        "M0007-N20-RAW is the lab's best dev book by MAR (0.77): CAGR +15.0%, max DD 19.6%, PF 2.16, "
        "1596 trades, DSR 0.914 at N=85, failing only max DD. M0001's own-vol overlay moved the "
        "total-return momentum book from 22.2% to 12.9% DD at about 0.8 CAGR points per DD point. "
        "On the residual book, scaling 19.6% down to about 13-14% should cost roughly 4-5 CAGR "
        "points, landing near +10-11% CAGR against SPY TR's +7.9% with max DD inside 15%, PF well "
        "above 1.3 and trades well above 100. TV14 on the top-20 is the variant expected to pass; "
        "TV12 should pass DD with less margin on return, TV16 should beat SPY comfortably but sit "
        "near the DD limit."
    ),
    expected_failure=(
        "The binding drawdown is the fast Aug-1998 shock, which hit a calm book: the 63-day vol "
        "estimate was low going in, so the scale sat near its usual level and the fall is cut only "
        "in proportion to average exposure, not more. If the residual book's own vol is only "
        "~18-20% (lower than total momentum's), the overlay de-risks less than it did for M0001: "
        "TV14 keeps ~0.75 exposure and lands at 15-16% DD, while TV12 passes DD but its CAGR drops "
        "to ~9%, still above SPY but with DSR below 0.95 because the lab's N keeps rising."
    ),
    candidates=(
        _v("RAW20-TV12", ResidVolParams(RAW20, Decimal("0.12"), 63),
           "Top-20 raw residual book scaled to 12% own vol (M0001-TV12's target)"),
        _v("RAW20-TV14", ResidVolParams(RAW20, Decimal("0.14"), 63),
           "Same at 14%: the arithmetic's centre, expected ~14% DD at ~10-11% CAGR"),
        _v("RAW20-TV16", ResidVolParams(RAW20, Decimal("0.16"), 63),
           "Same at 16%: more return, drawdown expected right at the limit"),
        _v("RAW30-TV14", ResidVolParams(RAW30, Decimal("0.14"), 63),
           "Top-30 raw residual at 14%: more names, lower single-name noise in the vol estimate"),
        _v("RAW20-TV14-N21", ResidVolParams(RAW20, Decimal("0.14"), 21),
           "Top-20 at 14% on a one-month vol window: reacts faster to a shock like Aug 1998"),
    ),
    seen_keys=(
        "concept:residual-momentum-own-vol",
    ),
)
