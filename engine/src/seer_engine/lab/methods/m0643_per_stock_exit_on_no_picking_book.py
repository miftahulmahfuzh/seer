"""M0643 — The per-stock 200-day exit on a no-picking book: a kin-clean host by construction.

Source: variation of M0107 (the per-stock 200-day trend exit, proven only on M0088's picked
raisers) and M0120 (the lab's one *measured* no-picking book, EW20-ALWAYS: the 20 largest
dollar-volume members, equal weight, no trend gate, which lost to SPY on every axis). M0121 and
M0437 proposed widening that frame to the whole F4-screened pool, and M0594 proposed an
equal-weight index yardstick; none of the three ever ran (`lab show` prints no trials for M0121
or M0437, and M0594 was dropped before running, as a duplicate of M0121). So the no-picking pool
this method needs does not exist as a recorded book yet, and the NONE candidate below is its
first actual measurement, not a citation of one.

Idea: M0620 found that every open stock-picking family in the lab -- low-volatility, short-term
reversal, profitability, 52-week-high nearness -- loses to a same-size random draw of its own
picks under real fees. The common factor each time is the picking rule, not the per-stock trend
exit (M0107), which has only ever been measured sitting on top of one such picker (M0088's
dividend raisers) and so carries that picker's kin. A book with no ranking opinion at all --
every F4-eligible member, held equal weight, re-priced monthly -- cannot be kin of a failed
picker, because it does not pick: it has no family of failed pickers to belong to. This method
puts M0107's exit on that frame instead, to separate two questions the picked books could never
answer cleanly: does the per-stock exit still cut the worst fall when there is no picking rule to
interact with, and what does it cost in return when measured against the no-picking book's own
baseline rather than against SPY?

Three candidates, one screen (`f_factor.factor_rows`, trend gate OFF, no top cut -- *every*
F4-eligible member on `data_date`, not a ranked subset):

    * NONE -- the frame itself, every eligible member held equal weight, no exit. The yardstick,
      and the first recorded measurement of this exact book.
    * STOCK200 -- NONE's exact pool, minus any member whose close is at or below the mean of its
      own last 200 closes (`m0107.above_own_trend`, the identical arithmetic M0107 and the
      market's own 200-day switch use). Dropped slots are left in cash, so exposure falls as names
      drop out one at a time rather than all at once.
    * STOCK200-SPREAD -- the same exit, but the weight a dropped name would have held is spread
      across the survivors instead (`equal_weight(len(kept))` rather than `equal_weight(n_all)`),
      so total exposure tracks what NONE would have held and only the choice of names changes.
      Paired against STOCK200, it separates de-risking (lower exposure) from name selection
      (same exposure, fewer names) exactly as M0107's own NONE/STOCK200/STOCK200-SPREAD trio did.

NONE is the no-opinion control this trio is built around: STOCK200 and STOCK200-SPREAD are both
differences from it, and the whole point of the method is that NONE itself cannot be kin of a
failed picker. No separate blind-random arm is registered -- a random draw of "similar trading
size" names has no distinct meaning here, since the pool already holds every eligible member and
a same-size random twin of the whole eligible set is the set itself.

Pure: reads only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0107_stock_trend_exit_raisers import above_own_trend
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    MAX_TOP,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
)

ADDED = date(2026, 11, 13)

#: The lab's standard F4 screen, trend gate OFF (no market opinion of any kind) and `top` unused
#: (NONE holds every eligible member, not a ranked cut; `rank` is likewise never read).
SCREEN = FactorParams(rank="momentum", top=MAX_TOP, trend=None)


@dataclass(frozen=True, slots=True)
class NoPickParams:
    """``stock_n`` is M0107's per-stock exit window; ``spread`` chooses cash or the survivors."""

    stock_n: int | None = None
    spread: bool = False

    def __post_init__(self) -> None:
        if self.stock_n is not None:
            if isinstance(self.stock_n, bool) or not isinstance(self.stock_n, int):
                raise TypeError(f"stock_n must be None or an int, got {type(self.stock_n).__name__}")
            if self.stock_n < 2:
                raise ValueError(f"stock_n must be >= 2, got {self.stock_n}")
        if not isinstance(self.spread, bool):
            raise TypeError(f"spread must be a bool, got {type(self.spread).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {
            "stock_n": "none" if self.stock_n is None else str(self.stock_n),
            "spread": str(self.spread).lower(),
        }


def _check(params: object) -> NoPickParams:
    if not isinstance(params, NoPickParams):
        raise TypeError(f"params must be NoPickParams, got {type(params).__name__}")
    return params


class NoPickPoolAllocator:
    """Every F4-eligible member, equal weight, with M0107's per-stock 200-day exit optional."""

    id = "M0643"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        need = factor_lookback(SCREEN)
        return need if p.stock_n is None else max(need, p.stock_n)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()  # no fixed instrument; slack is cash, never parked in SPY or anything else

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = factor_rows(history, members, data_date, SCREEN)
        return run(history, rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> FactorPrepared:
        return prepare_factor(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FactorPrepared):
            raise TypeError(f"prepared must be FactorPrepared, got {type(prepared).__name__}")
        p = _check(params)
        rows = prepared.rows_on(members, data_date, SCREEN)
        return run(prepared.history, rows, data_date, p)


def run(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
        p: NoPickParams) -> tuple[Target, ...]:
    """Every eligible row, then M0107's per-stock exit (if on), then the chosen weighting."""
    n_all = len(rows)
    if n_all == 0:
        return ()
    if p.stock_n is None:
        kept = rows
    else:
        kept = [r for r in rows if above_own_trend(history.get(r.symbol), data_date, p.stock_n)]
    if not kept:
        return ()
    w = equal_weight(len(kept)) if p.spread else equal_weight(n_all)
    out: list[Target] = []
    for r in sorted(kept, key=lambda row: row.symbol):
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


NOPICK = NoPickPoolAllocator()


def _v(suffix: str, params: NoPickParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0643-{suffix}", family="M0643", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=NOPICK, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0643",
    name=(
        "The per-stock 200-day exit on a no-picking book: a kin-clean host by construction"
    ),
    family="per-stock-trend-exit",
    source_kind="variation",
    source_ref=(
        "variation of M0107 (the per-stock 200-day trend exit) and M0120 (EW20-ALWAYS, the lab's "
        "one measured no-picking book); M0121, M0437 and M0594 proposed a wider no-picking frame "
        "but never ran (M0121/M0437 are still idea rows with no trials, M0594 was dropped before "
        "running as a duplicate of M0121)"
    ),
    parent_id="M0620",
    hypothesis=(
        "M0620 found that every open stock-picking family in the lab -- low-volatility (M0417, "
        "M0419, M0468), short-term reversal (M0158, M0161, M0391, M0490, M0537, M0538, M0028), "
        "profitability (M0569) and 52-week-high nearness (M0620 itself) -- loses to a same-size "
        "random draw of its own picks under real fees. The per-stock trend exit (M0107) is proven "
        "only as a brake sitting on top of one such picker (M0088's dividend raisers), so its "
        "measured drawdown benefit carries that picker's kin and cannot be cleanly separated from "
        "it. A book with no ranking opinion at all -- every F4-eligible member, held equal weight, "
        "re-priced monthly, trend gate off -- cannot be kin of a failed picker because it does not "
        "pick, and it is kin-clean by construction. This method puts M0107's exit on exactly that "
        "frame. Three candidates on one screen (f_factor.factor_rows, trend=None, no top cut -- "
        "every eligible member, not a ranked subset): NONE holds the whole pool equal weight with "
        "no exit, the yardstick and the first actual recorded measurement of this book (M0121 and "
        "M0437 proposed it but never ran, and M0594 was dropped as a duplicate of M0121 before "
        "running either); STOCK200 drops any member whose close is at or below the mean of its own "
        "last 200 closes, freed slots left in cash; STOCK200-SPREAD applies the same exit but "
        "hands the freed weight to the survivors instead, holding total exposure at what NONE "
        "would have held so only the choice of names changes. NONE is the no-opinion control the "
        "other two are measured against: the question is whether STOCK200's worst fall improves "
        "on NONE's by something close to what M0107's own STOCK200 improved on M0107's own NONE "
        "(26.3% to 13.1%, a 13.1-point cut, at a 0.7-point funded cost), and whether that holds "
        "even with no picking rule for the exit to interact with. M0120's narrower analogue "
        "(EW20-ALWAYS: the 20 largest-dollar-volume members, equal weight, no trend gate) is the "
        "closest existing measurement of the shape of NONE's expected result: funded +5.7% a year "
        "against SPY's +7.2%, a 74.4% worst fall, DSR 0.255 -- not SPY-beating, not go-live "
        "eligible, and not expected to be. Success for this method is not NONE beating SPY (it "
        "should not, and should not be promoted if it does by accident); it is STOCK200 cutting "
        "NONE's worst fall by a double-digit number of points at a funded cost under 2 points a "
        "year, on a book that has no stock-picking kin to disqualify it."
    ),
    expected_failure=(
        "The most likely failure is that NONE's worst fall is driven by the same handful of names "
        "breaking down together in 2008 that broke M0120's EW20-ALWAYS (44.5% in 2008 alone, on a "
        "narrower 20-name version of the same idea), so the per-stock exit may simply be too slow: "
        "it only sells a name after it has already crossed under its own average, and in a fast, "
        "broad-based crash most of the pool crosses within the same few weeks, which looks like a "
        "market-wide event to a per-stock rule and gives back most of the whipsaw savings it is "
        "meant to provide. The whole pool is hundreds of names re-priced monthly at Gotrade's real "
        "fees, so STOCK200's turnover -- names leaving and rejoining one at a time, every month, "
        "across the full eligible universe rather than M0107's twenty 5% slots -- may be far larger "
        "in absolute trade count than anything the lab has priced before, and the fee drag could "
        "exceed the 0.7-point cost M0107 paid on a much smaller book. NONE itself may also simply "
        "reproduce SPY's own cap-weighted drift in miniature: if dollar-volume-and-price eligibility "
        "already tilts the pool toward large, liquid names, equal-weighting hundreds of them may "
        "behave more like a diluted SPY than like a true market-shape yardstick, in which case the "
        "exit's effect on NONE says little about its effect on a genuinely different frame. "
        "STOCK200-SPREAD may turn out to be a thinner, more concentrated version of NONE in the "
        "months the exit is most active, and could fall further than NONE in those months rather "
        "than less, since redistributing weight to survivors raises each survivor's correlation "
        "with the book's overall fate. 2009-2015 is the era that matters most and the whole pool "
        "has no picking rule to earn an edge from in the first place, so both NONE and the two "
        "exit variants may simply lag SPY throughout that era by a similar margin to M0120's "
        "EW20-ALWAYS, which would mean the per-stock exit's drawdown benefit, if any, buys no "
        "return and the frame is not worth building on further."
    ),
    candidates=(
        _v("NONE", NoPickParams(None, False),
           "The no-opinion yardstick: every F4-eligible member, equal weight, no exit -- not a "
           "repeat of any recorded book. STOCK200 and STOCK200-SPREAD are both measured against it."),
        _v("STOCK200", NoPickParams(200, False),
           "M0107's per-stock 200-day exit on the whole pool, freed slots left in cash"),
        _v("STOCK200-SPREAD", NoPickParams(200, True),
           "Same exit, freed weight handed to the survivors instead of held in cash"),
    ),
    seen_keys=(
        "concept:per-stock-trend-exit-on-kin-clean-host",
        "concept:no-picking-equal-weight-whole-pool",
        "concept:per-stock-200-day-average-exit",
    ),
)
