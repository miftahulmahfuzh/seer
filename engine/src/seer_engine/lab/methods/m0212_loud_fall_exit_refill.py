"""M0212 — The loud-fall exit with an instant refill: sell a momentum holding that drops on heavy
trading and buy the next-ranked name the same week.

Source: a variation of M0204 (the weekly loud-fall exit on the residual-momentum book), which sold a
faller and left the slot in cash until the next monthly re-pick. M0204's NONE arm beat its LOUD arm
by 2.3 points a year on the owner's deposits; part of that is three weeks of cash per exit. This
method keeps M0204's clock, signal and host book unchanged and changes one thing: a freed slot is
refilled at the same check, so the book stays at twenty names.

**THE REFILL RULE.** At each check date, in order, every current holding that fires the exit (M0204's
bottom-tenth rule, loud or any) is sold. Its slot is refilled with the highest-ranked name, by the
anchor's own residual-momentum score, that is (a) not held now, (b) not sold earlier this month and
(c) not itself in the pool's bottom tenth at this check. Each refill takes the sold slot's weight.
A refilled name can fire at a later check and be replaced in turn. Nothing is remembered: the
allocator replays every check date since the anchor from bars alone, like its parent.

Arms (fixed before any result): LOUD-FILL (main), ANY-FILL (no volume condition), LOUD-CASH (the
parent's rule, cash until the re-pick) and NONE (no exit, the clean control). LOUD-CASH against
NONE prices the exit; LOUD-FILL against LOUD-CASH prices the cash. Every arm is on the parent's
weekly fractional preset at Gotrade's real fees. Every piece reads only bars dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import residual_scores
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0158_standardised_residual_reversal import zrev_scores
from seer_engine.lab.methods.m0161_quiet_fall_reversal import Z10, volume_ratios
from seer_engine.lab.methods.m0204_loud_fall_exit import (
    DECILE,
    LoudExitParams,
    LoudFallExitAllocator,
    _close_at,
    anchor_and_checks,
    fired,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorRow, factor_weights, trend_on

ADDED = date(2026, 10, 25)


@dataclass(frozen=True, slots=True)
class RefillParams(LoudExitParams):
    """M0204's params plus ``refill``: whether a freed slot is refilled at the same check."""

    refill: bool = True

    def as_dict(self) -> dict[str, str]:
        return {**super().as_dict(), "refill": str(self.refill)}


def _check(params: object) -> RefillParams:
    if not isinstance(params, RefillParams):
        raise TypeError(f"params must be RefillParams, got {type(params).__name__}")
    return params


class LoudFallRefillAllocator(LoudFallExitAllocator):
    """M0204's weekly rebuild, with each sold slot handed to the next-ranked name."""

    id = "M0212"

    def lookback(self, params: Any) -> int:
        return super().lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params))

    def _decide(self, history: Mapping[str, History], rows_at, grid, vols, data_date: date,
                p: RefillParams) -> tuple[Target, ...]:
        p = _check(p)
        anchor, checks = anchor_and_checks(data_date)
        if grid is None or not trend_on(history, anchor, p.host.inner):
            return ()
        rows = rows_at(anchor, p.host.inner)
        if not rows:
            return ()
        anchor_scores = residual_scores(grid, [r.symbol for r in rows], anchor, p.host)
        ranked: list[FactorRow] = sorted(
            (r for r in rows if r.symbol in anchor_scores and r.symbol not in EXCLUDED),
            key=lambda r: (-anchor_scores[r.symbol], r.symbol))
        top = p.host.inner.top
        chosen = ranked[:top]
        if not chosen:
            return ()
        weights = factor_weights(chosen, p.host.inner)
        slots: dict[str, tuple[FactorRow, Any]] = {
            r.symbol: (r, w) for r, w in zip(chosen, weights, strict=True)}
        reserve = ranked[top:]
        sold: set[str] = set()
        if p.exit != "none" and vols is not None:
            for w in checks:
                pool = [r.symbol for r in rows_at(w, p.signal.inner)]
                if not pool:
                    continue
                scores = zrev_scores(grid, pool, w, p.signal)
                if not scores:
                    continue
                ratios = {} if p.exit == "any" else volume_ratios(grid, vols, pool, w, p.signal)
                out = fired(scores, ratios, frozenset(slots), p.exit)
                if not out:
                    continue
                cut = float(np.quantile(np.fromiter(scores.values(), dtype=np.float64), DECILE))
                for sym in sorted(out):
                    row, weight = slots.pop(sym)
                    sold.add(sym)
                    if not p.refill:
                        continue
                    for cand in reserve:
                        s = cand.symbol
                        if (s in slots or s in sold or s not in scores or scores[s] <= cut
                                or _close_at(history.get(s), data_date) is None):
                            continue
                        slots[s] = (cand, weight)
                        break
        targets: list[Target] = []
        for sym, (row, weight) in slots.items():
            if weight is None:
                continue
            close = _close_at(history.get(sym), data_date)
            if close is None:
                continue
            target = target_from_close(sym, close, weight)
            if target is not None:
                targets.append(target)
        return tuple(targets)


REFILL = LoudFallRefillAllocator()


def _v(suffix: str, exit_: str, refill: bool, rationale: str) -> Candidate:
    return Candidate(id=f"M0212-{suffix}", family="M0212", rules=WEEKLY_HOLD_FRAC_GOTRADE,
                     allocator=REFILL, params=RefillParams(RAW20, Z10, exit_, refill),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0212",
    name=("The loud-fall exit with an instant refill: sell a momentum holding that drops on heavy "
          "trading and buy the next-ranked name the same week"),
    family="stock-single-name-brake",
    source_kind="variation",
    parent_id="M0204",
    source_ref=("M0204 (weekly loud-fall exit, cash until re-pick) and M0155 (single-name brake: "
                "width, not exits, was its answer); signal from M0161; Conrad, Hameed & Niden 1994, "
                "J. Finance 49(4); Da, Liu & Schaumburg 2014, Management Science 60(3)"),
    hypothesis=(
        "M0204's weekly loud-fall exit cost 2.3 points a year against the plain book (10.9% vs "
        "13.2% on the deposits) but caught dying companies on the survivorship-check store, where "
        "the gap shrank to 0.8 points. Part of the cost is three weeks in cash per exit. Refill each "
        "sold slot at once with the highest-ranked residual-momentum name (ranked at the month's "
        "anchor) that is not held, not sold earlier in the month and not itself in the pool's "
        "bottom tenth at that check, so the book stays at twenty names fully invested. Published "
        "1994-2014 (volume-conditioned reversal), so likely faded by the dev window's end. Arms: "
        "LOUD-FILL (main), ANY-FILL (no volume condition), LOUD-CASH (M0204's rule, the "
        "cash-until-re-pick control that prices the cash) and NONE (no exit). Predicted: LOUD-FILL "
        "recovers about half of the 2.3-point gap, landing within one point a year of NONE, with a "
        "worst fall at or below NONE's. Success: LOUD-FILL within half a point a year of NONE on "
        "dev and ahead of it on the check store, with a shallower worst fall on both. If it still "
        "trails, close single-stock exits on the momentum book; width stays the answer. Promotion "
        "unavailable (M0007 line is test-failed kin). Assumptions: refill ranks come from the "
        "anchor's scores, not re-scored weekly; the refill takes the sold slot's weight."
    ),
    expected_failure=(
        "The refill buys the next-ranked momentum name, which is as exposed to a news fall as the "
        "one sold, so the exit churns without reducing risk and pays extra fees on $30-200 slots: "
        "LOUD-FILL trails NONE by 1-3 points a year, like M0204's cash arm. Replacing a faller "
        "with a lower-ranked name also dilutes the momentum edge. In V-shaped recoveries the exit "
        "sells bottoms and the refill buys a name that fell just as hard but not hard enough to be "
        "in the bottom tenth. The momentum book already lagged SPY in 2009-2015 and an exit cannot "
        "add return there. If LOUD-FILL ~ LOUD-CASH, the cash was not the cost and the signal is."
    ),
    candidates=(
        _v("LOUD-FILL", "loud", True,
           "Bottom-tenth fall on heavy volume: sell, refill the same check with the next-ranked name"),
        _v("ANY-FILL", "any", True,
           "Same refill with no volume condition: does the volume split add anything?"),
        _v("LOUD-CASH", "loud", False,
           "M0204's rule: sell, hold cash until the re-pick. Prices the cash drag against LOUD-FILL"),
        _v("NONE", "none", False,
           "The plain monthly picks on this weekly clock with no exit: the clean control"),
    ),
    seen_keys=(
        "concept:loud-fall-exit-instant-refill",
        "concept:loud-fall-exit",
        "concept:volume-conditioned-exit",
    ),
)
