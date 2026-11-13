"""M0561 — Index admission decay: newly admitted members against the whole liquid universe.

Source: Vijh & Wang (2022) and Greenwood & Sammon (2023), the "index inclusion effect has faded and
admitted firms go on to disappoint" literature; the lab's own M0117 (rejected) and M0558 (rejected).
Both anomalies are decades old by the dev window's end, so a dev edge is likely a pre-crowd one.

M0558 compared admissions with a control matched on recent return (the best 126-day winners), and
the two tied. That can only rule out price continuation. It cannot see a decay that rides on top of
the momentum that got a name admitted, because the control was momentum-matched on purpose. This
method takes the matched control away: each admission arm is run beside a control that holds the
same count of names, on exactly the same days, drawn from the whole liquid current-member universe
with no ranking at all (a deterministic hash-ordered draw, so it has no opinion and no look-ahead).
The gap admit minus universe is the admission's forward return against the average liquid member.

Everything else is M0558's: the union-of-indices spells (M0117's merge_spells), the epoch guard, the
liquidity and continuity screen (``addition_pool``), a 10% slot, the rest in SPY. Fractional shares
at Gotrade's real fees. Long-only Gotrade cannot short the decay, so a negative gap is evidence and
never promotable on its own; only a positive, durable one could ever be traded.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0558_index_addition_drift import (
    IDLE,
    AdditionParams,
    AdditionPrepared,
    IndexAdditionAllocator,
    _liquid_close,
    addition_pool,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 13)
ARMS = ("admit", "universe")


@dataclass(frozen=True, slots=True)
class DecayParams:
    """Admission window, slot, and whether this arm holds the admissions or the unmatched draw."""

    window_months: int = 6
    slot: float = 0.10
    arm: str = "admit"

    def __post_init__(self) -> None:
        if not isinstance(self.window_months, int) or isinstance(self.window_months, bool) or self.window_months < 1:
            raise ValueError(f"window_months must be an int >= 1, got {self.window_months!r}")
        if not (0.0 < float(self.slot) <= 1.0):
            raise ValueError(f"slot must be in (0, 1], got {self.slot!r}")
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")

    def addition(self) -> AdditionParams:
        return AdditionParams(window_months=self.window_months, slot=self.slot)

    def as_dict(self) -> dict[str, str]:
        return {"window_months": str(self.window_months), "slot": f"{self.slot:.4f}", "arm": self.arm}


def _check(params: object) -> DecayParams:
    if not isinstance(params, DecayParams):
        raise TypeError(f"params must be DecayParams, got {type(params).__name__}")
    return params


def universe_draw(
    history: Mapping[str, History], members: AbstractSet[str], data_date: date, p: AdditionParams, n: int
) -> list[tuple[str, float]]:
    """``n`` liquid current members in a date-seeded hash order: no ranking, no look-ahead."""
    live: list[tuple[str, str, float]] = []
    for symbol in sorted(members):
        if symbol == IDLE:
            continue
        h = history.get(symbol)
        i = h.index_of(data_date) if h is not None else None
        if h is None or i is None:
            continue
        close = _liquid_close(h, i, p)
        if close is None:
            continue
        key = hashlib.md5(f"{symbol}|{data_date.isoformat()}".encode()).hexdigest()
        live.append((key, symbol, close))
    live.sort()
    return [(s, c) for _, s, c in live[:n]]


class IndexAdmissionDecayAllocator(IndexAdditionAllocator):
    """M0558's admission pool, or an equally many unmatched liquid members, the rest in SPY."""

    id = "M0561"
    market_fields = ()

    def lookback(self, params: Any) -> int:
        return super().lookback(_check(params).addition())

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (IDLE,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(  # type: ignore[override]
        self, prepared: AdditionPrepared, members: AbstractSet[str], data_date: date, p: Any
    ) -> tuple[Target, ...]:
        d = _check(p)
        if prepared.spells is None:
            return ()
        a = d.addition()
        picks = addition_pool(prepared, members, data_date, a)[: a.slots]
        if d.arm == "admit":
            chosen = [(s, c) for _, s, c in picks]
        else:
            chosen = universe_draw(prepared.history, members, data_date, a, len(picks))
        slot = Decimal(f"{d.slot:.4f}")
        out: list[Target] = []
        for symbol, close in chosen:
            t = target_from_close(symbol, close, slot)
            if t is not None:
                out.append(t)
        rest = Decimal(1) - slot * len(out)
        if rest > 0:
            h = prepared.history.get(IDLE)
            i = h.index_of(data_date) if h is not None else None
            if i is not None:
                t = target_from_close(IDLE, float(h.close[i]), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history, members, data_date, held, params):  # type: ignore[no-untyped-def]
        return self._run(AdditionPrepared(dict(history)), members, data_date, params)

    def targets_prepared(self, prepared, members, data_date, held, params):  # type: ignore[no-untyped-def]
        if not isinstance(prepared, AdditionPrepared):
            raise TypeError(f"prepared must be AdditionPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, params)


DECAY = IndexAdmissionDecayAllocator()


def _v(suffix: str, params: DecayParams, rationale: str) -> Candidate:
    return Candidate(
        id=f"M0561-{suffix}",
        family="M0561",
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=DECAY,
        params=params,
        rationale=rationale,
        added=ADDED,
        owner_inputs=(),
    )


METHOD = Method(
    id="M0561",
    name="Index admission decay: newly admitted names vs the whole liquid universe",
    family="stock-index-addition-drift",
    source_kind="variation",
    source_ref=(
        "Vijh & Wang (2022) and Greenwood & Sammon (2023) on admitted firms underperforming after "
        "inclusion; parent M0558 (rejected: admissions tied a momentum-matched control)"
    ),
    parent_id="M0558",
    hypothesis=(
        "M0558 tied A6 to a control matched on recent return, which rules out price continuation but "
        "cannot see a decay riding on top of momentum (the control was momentum-matched on purpose). "
        "M0561 removes the matching: arms D3, D6, D12 hold the newly admitted S&P 500 / Nasdaq-100 "
        "names (M0558's pool, screen and epoch guard, up to 10 names at 10% each, the rest in SPY, "
        "windows of 3, 6 and 12 months); arms U3, U6, U12 are their Controls: the same count of names "
        "on exactly the same days, drawn from all liquid current members in a date-seeded hash order "
        "with no ranking (M0558 pool and screen, so U6 is not M0558-W6's book: it ranks on nothing). "
        "The gap D minus U is the admission's forward return against the average liquid member. "
        "Decay predicts D < U in the later, best-covered years (2009-2015). Published 2022-2023, the "
        "decay itself is recent, so the dev window sees mostly the older era in which admissions "
        "earned a pop; a positive D-U gap early and a fade by 2009-2015 is the expected shape. "
        "Success for a tradable result: D beats total-return SPY and U on dev with a worst fall under "
        "the bar and a positive 2009-2015 edge. A negative D-U gap is evidence only (Gotrade is "
        "long-only) and settles whether M0117's near-zero exclusion result (0.2 pt/yr, rejected) was "
        "underpowered or a true null. SPY is the always-invested no-opinion arm. Fractional shares "
        "at Gotrade's real fees on the owner's monthly deposits; lab survivorship is mandatory."
    ),
    expected_failure=(
        "Thin pool: a 6-month window averages about 4 live names and is empty about a third of "
        "months, so both D and U sit mostly in SPY and the gap is a small difference of small "
        "differences, below what DSR at the lab's N will call real. D and U are likely to share a "
        "curve in the 1-month-thin months and may be close to one curve overall; if so the dial "
        "never moved. The 12-month window is the best-powered arm. Admission drift is a published "
        "anomaly, so any edge is likely pre-2009 and gone in 2009-2015."
    ),
    candidates=(
        _v("D3", DecayParams(window_months=3), "admissions in the last 3 months, 10% each, rest SPY"),
        _v(
            "U3",
            DecayParams(window_months=3, arm="universe"),
            "Control: as many names as D3, drawn unranked from all liquid members, same days",
        ),
        _v("D6", DecayParams(window_months=6), "admissions in the last 6 months, 10% each, rest SPY"),
        _v(
            "U6",
            DecayParams(window_months=6, arm="universe"),
            "Control: as many names as D6, drawn unranked from all liquid members, same days",
        ),
        _v("D12", DecayParams(window_months=12), "admissions in the last 12 months, 10% each, rest SPY"),
        _v(
            "U12",
            DecayParams(window_months=12, arm="universe"),
            "Control: as many names as D12, drawn unranked from all liquid members, same days",
        ),
    ),
    seen_keys=(
        "concept:index-admission-decay",
        "concept:index-addition-drift",
        "concept:index-addition-effect",
    ),
)
