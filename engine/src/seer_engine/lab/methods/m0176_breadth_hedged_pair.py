"""M0176 — A breadth-hedged pair: the slowest reactors beside the biggest companies.

Source: variation of M0169 (Hou & Moskowitz 2005, price delay) and M0171, with insight 91's
market-shape point (an equal-slot book of index members bets against SPY's big-company drift).
Idea: every slow-reactor version earned +7 to +11 points a year in broad months, when the average
member beats the index, and lost about 7 a year in narrow months, when a few giants carry SPY. That
breadth bet, not the brake, is what kept it from a positive 2009-2015 lead. A second half that is
paid exactly when the first is not -- the 20 most traded members, sized by trading value -- should
cancel the breadth bet and leave the delay premium, if there is one.

The big half. On every monthly decision date d, F4's screen ($5, $20M 20-day dollar volume, a
year of bars), cut to the ``top`` members with the largest 20-day mean dollar volume, each sized in
proportion to that dollar volume and capped at ``cap`` of the half (``capped_shares`` from M0092,
the excess re-spread). Re-picked every month: the biggest names change slowly, so the monthly
re-pick mostly resizes. Dollar volume is a proxy for size, not market value (the lab's market-cap
figure is broken, see M0122); no verdict may call this half cap-weighted. Behind F4's SPY 200-day
switch, the same switch M0169-D20-SW uses, so in the blend both halves step out together.

The slow half is M0169-D20-SW's params verbatim (December delay ranking, keep band 40, member
exits parked in SPY, behind the switch), run through the lab's BLEND so each half holds its own
share of the account and neither sees the other's holdings.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
Reads only bars dated <= ``data_date``.
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
from seer_engine.lab.methods.m0092_jump_trading_value_weight import capped_shares
from seer_engine.lab.methods.m0169_price_delay import DELAY, SW, DelayParams
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import BLEND, BlendParams, BlendPart, target_from_close
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

ADDED = date(2026, 10, 17)


@dataclass(frozen=True, slots=True)
class BigParams:
    """``inner`` is F4's screen, name count and switch; ``weight`` "dv" sizes by dollar volume,
    "equal" gives every name the same slot; ``cap`` is the most one name may hold (dv only)."""

    inner: FactorParams
    weight: str = "dv"
    cap: Decimal = Decimal("0.10")

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.weight not in ("dv", "equal"):
            raise ValueError(f"weight must be 'dv' or 'equal', got {self.weight!r}")
        if not isinstance(self.cap, Decimal) or not self.cap.is_finite() or not (
            Decimal(1) / self.inner.top <= self.cap <= Decimal(1)
        ):
            raise ValueError(f"cap must be a Decimal in [1/top, 1], got {self.cap!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"weight": self.weight, "cap": str(self.cap)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> BigParams:
    if not isinstance(params, BigParams):
        raise TypeError(f"params must be BigParams, got {type(params).__name__}")
    return params


def biggest(rows: list[FactorRow], p: BigParams) -> tuple[Target, ...]:
    """The ``top`` rows by dollar volume, sized by it (capped) or equally, in rank order."""
    chosen = sorted((r for r in rows if r.symbol not in EXCLUDED and r.symbol != "SPY"),
                    key=lambda r: (-r.dollar_volume, r.symbol))[: p.inner.top]
    if not chosen:
        return ()
    if p.weight == "equal":
        weights: list[Decimal | None] = [equal_weight(p.inner.top)] * len(chosen)
    else:
        budget = float(len(chosen)) / p.inner.top  # a short list leaves the rest in cash, as equal does
        shares = capped_shares([r.dollar_volume for r in chosen], budget, float(p.cap))
        # a share that floors to zero drops its name (to_weight refuses it)
        weights = [to_weight(x) if x >= float(WEIGHT_QUANTUM) else None for x in shares]
    out: list[Target] = []
    for r, w in zip(chosen, weights, strict=True):
        if w is None:
            continue
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class BigAllocator:
    """The most traded screened members, sized by trading value, behind the SPY switch."""

    id = "M0176"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return () if p.inner.trend is None else (p.inner.trend[0],)

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
        return biggest(factor_rows(history, members, data_date, p.inner), p)

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        return biggest(prepared.rows_on(members, data_date, p.inner), p)


BIG = BigAllocator()

# M0169-D20-SW's params, verbatim: the rank is unused (only F4's screen), the switch is SPY 200
SLOW_P = DelayParams(FactorParams(rank="momentum", top=20, trend=SW), keep=40)
BIG_DV = BigParams(FactorParams(rank="momentum", top=20, trend=SW))
BIG_EQ = BigParams(FactorParams(rank="momentum", top=20, trend=SW), weight="equal")


def _pair(slow: str, big: BigParams) -> BlendParams:
    s = Decimal(slow)
    return BlendParams((BlendPart(DELAY, SLOW_P, s), BlendPart(BIG, big, Decimal(1) - s)))


def _v(suffix: str, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0176-{suffix}", family="M0176", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0176",
    name=(
        "A breadth-hedged pair: the slowest reactors beside the biggest companies, so one half "
        "pays when small names lead and the other when giants lead"
    ),
    family="stock-breadth-hedged-blend",
    source_kind="variation",
    source_ref=(
        "M0169 (Hou & Moskowitz 2005, price delay, RFS 18(3)) and M0171; insight 91 (equal slots "
        "bet against SPY's big-company drift); M0122 (trading value as the lab's size proxy)"
    ),
    parent_id="M0171",
    hypothesis=(
        "Every slow-reactor version (M0169, M0171) earned +7 to +11 points a year in broad months, "
        "when the average member beats the index, and lost about 7 a year in narrow months, when a "
        "few giants carry SPY; that breadth bet, not the brake, is what kept it from a positive "
        "2009-2015 lead. Pair M0169-D20-SW verbatim (the 20 slowest reactors, December re-pick, "
        "keep band 40, behind the SPY 200-day switch) with a big half: the 20 screened members "
        "with the largest 20-day dollar volume, sized by it and capped at 10% of the half, "
        "re-picked monthly behind the same switch, so one half pays in narrow months and the "
        "other in broad ones. Price delay was published in 2005, mid dev window; the big half is "
        "no published anomaly, only the market's own shape. Fractional shares at Gotrade's real "
        "fees on the owner's deposits, monthly. Variants: P50 (half and half, the idea), P30 (30% "
        "slow, 70% big), P50-EQ (half and half, big half in equal slots, to see whether the "
        "size-weighting matters), BIG (control: the big half alone). Success: P50 beats total-"
        "return SPY with worst fall <= 25%, PF >= 1.3, reads 'pays in both' on the breadth check, "
        "a positive 2009-2015 lead and a majority of walk-forward folds, and beats BIG."
    ),
    expected_failure=(
        "The big half is close to SPY itself, and behind the same switch it is close to the lab's "
        "plain SPY-switch book, which already trails SPY by whipsawing in 2010-2011; so the blend "
        "is that switch book plus half the slow-reactor tilt, and inherits half its narrow-month "
        "losses without a full share of its broad-month gains. The 2008 fall stays near the "
        "parent's 33% in the slow half and the big half adds its own, so the blend falls 25-30%. "
        "Trading value leans to whatever is in turmoil (the busiest names in 2000 and 2008 were "
        "the ones crashing), so the dollar-volume half may fall harder than SPY in exactly the "
        "crashes the switch is late for. The slow half's dead-company flattery (dev store) is "
        "halved, not removed."
    ),
    candidates=(
        _v("P50", BLEND, _pair("0.5", BIG_DV),
           "Half in M0169-D20-SW's slow reactors, half in the 20 most traded sized by trading value"),
        _v("P30", BLEND, _pair("0.3", BIG_DV),
           "30% slow reactors, 70% in the 20 most traded sized by trading value"),
        _v("P50-EQ", BLEND, _pair("0.5", BIG_EQ),
           "Half and half, the big half in equal slots instead of trading-value sizes"),
        _v("BIG", BIG, BIG_DV,
           "Control: the 20 most traded members sized by trading value, behind the switch, alone"),
    ),
    seen_keys=(
        "concept:breadth-hedged-blend",
        "concept:price-delay-plus-big-names",
        "concept:most-traded-dv-weighted",
    ),
)
