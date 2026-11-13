"""M0111 — The residual-momentum book, weighted the way the market weights instead of equally.

Source: a variation of M0108 (its EW40-DV yardstick), applied to M0032's winning book.
Idea: M0108 put in an equal-weight 40 most-traded-members book only as a yardstick, and it read
5.8% a year on the owner's deposits against SPY TR's 7.2%, with a 62% fall. That was a different
question than the one asked: what does equal slots cost a book? Every stock-picking book in the
lab is equal-slotted. This isolates it on a book that wins: M0032's configuration (top-20 raw
residual momentum, F4's screen, SPY-200 gate, monthly, fractional shares, Gotrade fees) with one
dial changed -- how the invested money is split across the same 20 names.

Weights are over the *chosen* names only (the ranking is untouched), scaled so the invested
fraction equals len(chosen)/top exactly as equal weighting does, so a thin month holds the same
cash in every arm. ``dv`` is proportional to the 20-day mean dollar volume; ``dv-capped`` is the
same with no name above 15% (water-filled, so the clipped excess goes to the rest);
``sqrt-dv`` is proportional to its square root. The equal-weight twin is NOT re-run here: it is
M0032-N20-RAW-FRAC-GT (trial #129), the identical book on the identical rules, cited rather than
recorded a second time. Every piece reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    ResidPrepared,
    ResidParams,
    resid_lookback,
    residual_scores,
)
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorRow,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 13)

Mode = Literal["dv", "dv-capped", "sqrt-dv"]
_MODES: tuple[str, ...] = ("dv", "dv-capped", "sqrt-dv")


@dataclass(frozen=True, slots=True)
class ShapedParams:
    """``resid`` is M0032's whole ranking book; the rest is how the money is split."""

    resid: ResidParams
    mode: Mode = "dv"
    cap: float = 0.15  # dv-capped only: no name above this share of the invested money

    def __post_init__(self) -> None:
        if not isinstance(self.resid, ResidParams):
            raise TypeError(f"resid must be ResidParams, got {type(self.resid).__name__}")
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        if not 0.0 < self.cap <= 1.0:
            raise ValueError(f"cap must be in (0, 1], got {self.cap}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "cap": repr(self.cap)}
        for k, v in self.resid.as_dict().items():
            out[f"resid.{k}"] = v
        return out


def _check(params: object) -> ShapedParams:
    if not isinstance(params, ShapedParams):
        raise TypeError(f"params must be ShapedParams, got {type(params).__name__}")
    return params


def shares(dollar_volumes: list[float], mode: str, cap: float) -> list[float]:
    """Each name's share of the invested money; sums to 1. Water-fills the cap when asked."""
    raw = [max(x, 0.0) for x in dollar_volumes]
    if mode == "sqrt-dv":
        raw = [float(np.sqrt(x)) for x in raw]
    total = sum(raw)
    if total <= 0.0:
        return [1.0 / len(raw)] * len(raw)
    w = [x / total for x in raw]
    if mode != "dv-capped" or cap * len(w) < 1.0:
        return w  # a cap that cannot hold the whole book is ignored (cannot sum to 1)
    fixed: set[int] = set()
    for _ in range(len(w)):
        over = [i for i in range(len(w)) if i not in fixed and w[i] > cap + 1e-12]
        if not over:
            break
        fixed.update(over)
        free = [i for i in range(len(w)) if i not in fixed]
        room = 1.0 - cap * len(fixed)
        free_raw = sum(raw[i] for i in free)
        for i in fixed:
            w[i] = cap
        for i in free:
            w[i] = room * raw[i] / free_raw if free_raw > 0.0 else room / len(free)
    return w


def targets_from_scores(rows: list[FactorRow], scores: Mapping[str, float],
                        params: ShapedParams) -> tuple[Target, ...]:
    """The same top names M0032 picks, split by ``mode`` instead of equally."""
    top = params.resid.inner.top
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    chosen = sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))[:top]
    if not chosen:
        return ()
    scale = len(chosen) / top  # same cash in a thin month as the equal-weight book holds
    w = shares([r.dollar_volume for r in chosen], params.mode, params.cap)
    out: list[Target] = []
    for row, share in zip(chosen, w, strict=True):
        x = share * scale
        if not np.isfinite(x) or Decimal(repr(x)) < WEIGHT_QUANTUM:
            continue
        target = target_from_close(row.symbol, row.close, to_weight(x))
        if target is not None:
            out.append(target)
    return tuple(out)


@dataclass(frozen=True, slots=True, eq=False)
class ShapedPrepared:
    inner: ResidPrepared = field(repr=False)


class ResidualShapedAllocator:
    """M0032's ranking, weighted by dollar volume instead of equally. Gate and screen unchanged."""

    id = "M0111"

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).resid)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).resid)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets_prepared(self.prepare(history), members, data_date, held, params)

    def prepare(self, history: Mapping[str, History]) -> ShapedPrepared:
        return ShapedPrepared(ResidPrepared(history, prepare_factor(history)))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ShapedPrepared):
            raise TypeError(f"prepared must be ShapedPrepared, got {type(prepared).__name__}")
        p = _check(params)
        rp = prepared.inner
        if not trend_on(rp.history, data_date, p.resid.inner):
            return ()
        rows = rp.factor.rows_on(members, data_date, p.resid.inner)
        if not rows:
            return ()
        grid = rp.grid(p.resid.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, p.resid)
        return targets_from_scores(rows, scores, p)


SHAPED = ResidualShapedAllocator()

M0032_BOOK = ResidParams(N20, scaled=False)  # M0032-N20-RAW-FRAC-GT's ranking, verbatim


def _v(suffix: str, params: ShapedParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0111-{suffix}", family="M0111", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SHAPED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0111",
    name="The lab's best book, weighted the way the market weights: does equal slots cost it the point and a half M0108 measured?",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="M0108's EW40-DV yardstick, applied to M0032's residual-momentum book",
    parent_id="M0108",
    hypothesis=(
        "M0108's EW40-DV yardstick (equal money across the 40 most-traded index members) earned "
        "5.8% a year on the owner's deposits against SPY TR's 7.2% and fell 62%, so equal "
        "weighting big names cost about 1.4 points a year and doubled the crash damage over "
        "1996-2015. Every stock-picking book here is equal-slotted and carries that handicap. "
        "This measures it on a book that wins: M0032's configuration verbatim (top-20 raw "
        "residual momentum, F4's screen, SPY-200 gate, monthly, fractional shares, Gotrade fees) "
        "with one change, how the invested money is split over the same chosen names. Arms: "
        "DV-WEIGHT (proportional to 20-day mean dollar volume), DV-CAPPED (the same, no name "
        "above 15%), SQRT-DV (proportional to its square root, a half-step between equal and "
        "market-shaped). The equal-weight twin is not re-run: it is M0032-N20-RAW-FRAC-GT, "
        "trial #129 (+13.7% a year funded vs SPY TR +7.2%, worst fall 20.6%, 1607 trades), the "
        "identical ranking on the identical rules, and a recorded trial is the measurement; "
        "assumption: the store has not moved since (lab run's own store check refuses if it "
        "has). Residual momentum was published in 2011 (Blitz, Huij, Martens); dollar-volume "
        "weighting is not a published anomaly, so there is no fade to price. Success: a weighted "
        "arm beats #129 on deposit-matched money, or reaches a worst fall under 20% without "
        "giving up more than the 0.6 points the book needs to shed; either way the set sizes the "
        "equal-weighting handicap inside a winning book."
    ),
    expected_failure=(
        "Dollar volume is trading activity, not market value, and the most-traded names are often "
        "the most contested, so the tilt may add volatile giants and deepen the fall. The book's "
        "edge also comes partly from smaller index members (insight 91); market-shaping it trades "
        "return away for a steadier ride and lands in the one-for-one trap every risk filter in "
        "the lab has fallen into. A momentum book that concentrates in a few mega-caps also "
        "becomes kin of a plain large-cap tilt, and 2009-2015 (SPY led by a few giants) is where "
        "that would show."
    ),
    candidates=(
        _v("DV-WEIGHT", ShapedParams(M0032_BOOK, mode="dv"),
           "Same top-20 as M0032, money split in proportion to 20-day dollar volume"),
        _v("DV-CAPPED", ShapedParams(M0032_BOOK, mode="dv-capped", cap=0.15),
           "Dollar-volume weights with no name above 15%, so one giant cannot become the book"),
        _v("SQRT-DV", ShapedParams(M0032_BOOK, mode="sqrt-dv"),
           "Square root of dollar volume: halfway between equal slots and market-shaped"),
    ),
    seen_keys=("concept:residual-momentum-dollar-volume-weighted",),
)
