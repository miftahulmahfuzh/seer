"""M0605 — 60-day winners with a market-wide core, to cure the deeper fall on dead companies.

Source: variation on M0562. M0562's 60-session winners book (W60-B100: 20 equal monthly slots of
F4-screened point-in-time index members, 100% keep band, fractional shares at Gotrade real fees, SPY
200-day switch) led SPY in 2009-2015 on dev but its worst fall deepened on the survivorship-check
store (the dev store plus EODHD prices for dead companies) past the 25% bar, and its luck score fell
below 0.90. Two dials could shorten that fall without touching the signal: hold part of the account
in SPY (a market-wide core that dead companies cannot hurt), or spread the picks over 30 names.

The core shares the book's own switch: when SPY is under its 200-day average the whole account,
core included, steps aside, so the core adds no new opinion and the arms differ from M0562 only by
the dial. The picks keep the same scoring and keep band; each pick's weight is scaled by
(1 - core), the rest sits in SPY, one extra order a month at Gotrade's fee.

Arms (five): CORE25 and CORE50 (winners, 25% and 50% SPY), N30 (30 winners slots, no core), and two
blind coin-flip draws at the 50% core (seeds 6051, 6052, 100% band, 60-session pool) so the core's
effect is read against a same-shape control. The unmodified 20-slot winners book is M0562-W60-B100
and is read against, not repeated. No arm mirrors another, so no third arm is owed; the blind arms
are the control. Success needs a funded edge over SPY in 2009-2015, a worst fall under 25% on dev,
and luck at N above 0.90; the check-store fall is read afterwards with `lab survivorship`.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0509_keep_band_ladder import LADDER, MARKET, TimeParams
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 13)
N30 = replace(N20, top=30)


@dataclass(frozen=True, slots=True)
class CoreParams:
    """``book`` is M0509's ranked book; ``core_pct`` of the account goes to SPY instead."""

    book: TimeParams
    core_pct: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.book, TimeParams):
            raise TypeError(f"book must be TimeParams, got {type(self.book).__name__}")
        if isinstance(self.core_pct, bool) or not isinstance(self.core_pct, int):
            raise TypeError(f"core_pct must be an int, got {type(self.core_pct).__name__}")
        if not 0 <= self.core_pct < 100:
            raise ValueError(f"core_pct must be in [0, 100), got {self.core_pct}")

    def as_dict(self) -> dict[str, str]:
        out = {"core_pct": str(self.core_pct)}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> CoreParams:
    if not isinstance(params, CoreParams):
        raise TypeError(f"params must be CoreParams, got {type(params).__name__}")
    return params


def with_core(picks: tuple[Target, ...], history: Mapping[str, History], data_date: date,
              core_pct: int) -> tuple[Target, ...]:
    """Scale each pick by (1 - core) and add SPY at the core weight; nothing when no picks."""
    if core_pct == 0 or not picks:
        return picks
    keep = Decimal(100 - core_pct) / Decimal(100)
    out: list[Target] = []
    for t in picks:
        w = (t.weight * keep).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
        if w > 0:
            out.append(replace(t, weight=w))
    h = history.get(MARKET)
    i = None if h is None else h.index_of(data_date)
    if h is None or i is None:
        return tuple(out)
    core = target_from_close(MARKET, float(h.close[i]), Decimal(core_pct) / Decimal(100))
    if core is not None:
        out.append(core)
    return tuple(out)


class CoreAllocator:
    """M0509's winners/blind book, with part of the account held in SPY."""

    id = "M0605"

    def lookback(self, params: Any) -> int:
        return LADDER.lookback(_check(params).book)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return LADDER.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return LADDER.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return LADDER.uses_members(_check(params).book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        return with_core(LADDER.targets(history, members, data_date, held, p.book),
                         history, data_date, p.core_pct)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return LADDER.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        return with_core(
            LADDER.targets_prepared(prepared, members, data_date, held, p.book),
            prepared.history, data_date, p.core_pct)


CORE = CoreAllocator()


def _v(suffix: str, params: CoreParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0605-{suffix}", family="M0605",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=CORE, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0605",
    name="60-day winners with a market-wide core",
    family="stock-momentum-short-window",
    source_kind="variation",
    source_ref="M0562-W60-B100: the 60-session winners book whose worst fall deepens past 25% on "
               "the dead-company check store",
    parent_id="M0562",
    hypothesis=(
        "M0562's 60-session winners book (20 slots, 100% keep band, F4-screened point-in-time "
        "index members, fractional shares, Gotrade real fees, SPY 200-day switch) was +14.9% a "
        "year funded and +5.4 points over SPY in 2009-2015, but its worst fall goes from 23.9% on "
        "dev to 25.9% on the check store, past the 25% bar, and its luck score falls to 0.864. "
        "Test whether a market-wide core (25% or 50% of the account in SPY, under the same "
        "switch) or 30 slots instead of 20 keeps the lead while shrinking the fall. Arms: CORE25, "
        "CORE50, N30, and two blind draws at the 50% core (seeds 6051, 6052). M0562-W60-B100 is "
        "the recorded unmodified book and is not repeated. Prediction written now: the core pulls "
        "the fall down roughly in proportion but gives up at least as much return, so luck at N "
        "does not improve; N30 changes little. Momentum at this horizon was published in 1993 "
        "and the lab's post-2009 record on this family is weak, so a fade is the default."
    ),
    expected_failure=(
        "The core dilutes the lead and the fall together, leaving a book that is mostly SPY and "
        "no more luck-proof than before; or the blind draws at the same core land within 2 "
        "points of the winners, so the core, not the picking, explains the result; or the "
        "winners still inherit the kin block that stopped their siblings."
    ),
    candidates=(
        _v("W60-CORE25", CoreParams(TimeParams(N20, "win", 0, 100, 60), 25),
           "60-session winners, 100% band, 25% of the account in SPY"),
        _v("W60-CORE50", CoreParams(TimeParams(N20, "win", 0, 100, 60), 50),
           "60-session winners, 100% band, 50% of the account in SPY"),
        _v("W60-N30", CoreParams(TimeParams(N30, "win", 0, 100, 60), 0),
           "60-session winners, 100% band, 30 slots, no core"),
        _v("W60-RAND-CORE50-A", CoreParams(TimeParams(N20, "blind", 6051, 100, 60), 50),
           "Control: hash draw of 20, seed 6051, 100% band, 60-session pool, 50% SPY core, "
           "matched to W60-CORE50"),
        _v("W60-RAND-CORE50-B", CoreParams(TimeParams(N20, "blind", 6052, 100, 60), 50),
           "Control: hash draw of 20, seed 6052, 100% band, 60-session pool, 50% SPY core, "
           "second seed"),
    ),
    seen_keys=(
        "concept:market-core-on-short-window-winners",
    ),
)
