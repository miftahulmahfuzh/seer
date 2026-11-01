"""M0443 — Frog in the pan: momentum winners whose gain came as many small up days.

Source: Da, Gurun and Warachka 2014 (Review of Financial Studies), "Frog in the Pan: Continuous
Information and Momentum". Published 2014, so the dev window (ends 2015) sits right at the
crowd's arrival and 2009-2015 is the first filter. The paper says investors under-react to
information that arrives in many small steps, so winners with a smooth path keep drifting while
winners that gained in a few jumps reverse.

Information discreteness here is the paper's: ID = sign(12-1 return) x (share of down days minus
share of up days) over the formation window (the 231 daily returns from 252 to 21 trading days
back, the same window as the 12-1 return). Low ID is continuous. This counts days by sign, not
size, which is what separates it from M0438 (jump return) and M0402 (return consistency).

``FrogAlloc`` is FACTOR's screen, point-in-time index pool, SPY 200-day switch and 20 equal
slots, monthly. ``mode`` picks the pick rule: "mom" plain 12-1 top 20 (the control); "cont" the
top ``WINNERS`` by 12-1 return, keep the half with the lowest ID, then the 20 best by return;
"disc" the same with the highest-ID half (the paper's reversal side, the mirror); an int is a
seeded draw of 20 from the very pool momentum ranks (M0293's sticky hash). Pure; reads only bars
dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FACTOR,
    FactorParams,
    FactorRow,
    factor_rows,
    factor_weights,
    trend_on,
)

ADDED = date(2026, 11, 1)

SWITCH = ("SPY", 200)
TOP = 20
WINNERS = 80
LOOK = 252
SKIP = 21
MODES = ("mom", "cont", "disc")


@dataclass(frozen=True, slots=True)
class Params:
    """``mode`` is "mom", "cont" or "disc"; ``seed`` (an int) replaces it with a hash draw."""

    mode: str = "mom"
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.seed is None and self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise TypeError(f"seed must be an int or None, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "seed": str(self.seed), "winners": str(WINNERS),
                "pool": "f4-screened-members"}

    def picker(self) -> FactorParams:
        return FactorParams(rank="momentum", top=TOP, mom_n=LOOK, mom_skip=SKIP, trend=SWITCH)


def discreteness(h: History, data_date: date) -> float | None:
    """sign(12-1 return) x (share of down days - share of up days) over the formation window.

    None when the history is too short or has a gap-free window of fewer than 2 returns."""
    i = h.index_of(data_date)
    if i is None or i - LOOK < 0:
        return None
    window = h.close[i - LOOK : i - SKIP + 1]
    if window.shape[0] < 3 or not bool(np.all(window > 0)):
        return None
    rets = window[1:] / window[:-1] - 1.0
    total = float(window[-1] / window[0] - 1.0)
    up = float(np.mean(rets > 0))
    down = float(np.mean(rets < 0))
    sign = 1.0 if total > 0 else (-1.0 if total < 0 else 0.0)
    return sign * (down - up)


def choose(rows: Sequence[FactorRow], history: Mapping[str, History], data_date: date,
           p: Params) -> list[FactorRow]:
    if p.seed is not None:
        seed = p.seed
        return sorted(rows, key=lambda r: (float(draw(seed, r.symbol)), r.symbol))[:TOP]
    by_mom = sorted(rows, key=lambda r: (-r.momentum, r.symbol))
    if p.mode == "mom":
        return by_mom[:TOP]
    scored: list[tuple[float, FactorRow]] = []
    for r in by_mom[:WINNERS]:
        h = history.get(r.symbol)
        v = discreteness(h, data_date) if h is not None else None
        if v is not None:
            scored.append((v, r))
    if not scored:
        return []
    half = len(scored) // 2
    ordered = sorted(scored, key=lambda t: (t[0], t[1].symbol))
    picked = ordered[:half] if p.mode == "cont" else ordered[len(scored) - half:]
    return sorted((r for _, r in picked), key=lambda r: (-r.momentum, r.symbol))[:TOP]


def _targets(rows: Sequence[FactorRow], history: Mapping[str, History], data_date: date,
             params: Params) -> tuple[Target, ...]:
    chosen = choose(rows, history, data_date, params)
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, params.picker()), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class FrogAlloc:
    """FACTOR's screen and switch, with the pick ordered by the information-discreteness rule."""

    id = "M0443"

    def lookback(self, params: Params) -> int:
        return FACTOR.lookback(params.picker())

    def symbols(self, params: Params) -> tuple[str, ...]:
        return FACTOR.symbols(params.picker())

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(history, data_date, p):
            return ()
        return _targets(factor_rows(history, members, data_date, p), history, data_date, params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return FACTOR.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(prepared.history, data_date, p):
            return ()
        return _targets(prepared.rows_on(members, data_date, p), prepared.history, data_date, params)


FROG = FrogAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0443-{suffix}", family="M0443", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FROG, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0443",
    name="Smooth-path momentum: winners whose gain came from many small up days (frog in the pan)",
    family="stock-information-discreteness",
    source_kind="paper",
    source_ref="Da, Gurun, Warachka 2014, Frog in the Pan: Continuous Information and Momentum (RFS)",
    hypothesis=(
        "Among 12-1 momentum winners, those whose gain arrived as many small up days keep drifting "
        "(investors under-react to slow news), while winners that gained in a few jumps reverse. "
        "Information discreteness = sign of the 12-1 return times (share of down days minus share "
        "of up days) over the formation window; low is continuous. Published 2014, so the dev "
        "window ends just as the crowd arrived and 2009-2015 is the first filter. Arms, all behind "
        "SPY's 200-day switch, 20 equal slots, monthly, fractional shares at Gotrade's real fees, "
        "the F4-screened point-in-time index pool: CONT (the 80 best 12-1 returns, keep the half "
        "with the lowest ID, hold the 20 best by return), DISC (the same with the highest-ID "
        "half, the mirror), MOM (plain 12-1 top 20, the habit-without-opinion control: same book, "
        "switch and fees, no smoothness opinion) and DRAW-1..3 (twenty names from the pool in "
        "sticky hash order, seeds 443-445, the error bar). Counts days by sign, not size, so it "
        "is distinct from the jump-return (M0438) and return-consistency (M0402) rejections. "
        "SUCCESS, written now: CONT beats MOM and the best DRAW on 2009-2015 return vs SPY and "
        "clears the 20% fall bar and DSR 0.90, while DISC does worse than MOM. Predictions: CONT "
        "and MOM differ by under 2 points a year because the filter keeps 40 of 80 names that "
        "already rank high; DISC is not meaningfully worse than CONT."),
    expected_failure=(
        "The smoothness filter does no better than a random half of the winners: CONT, DISC and "
        "MOM sit within the draws' spread, as M0402 and M0438 found for steadiness and jumps. The "
        "switch and the large-index frame carry whatever return there is, every arm lags SPY in "
        "2009-2015 through time in cash and fees, and a 2014 paper's edge faded before the dev "
        "window's end. Three draws are a thin error bar. If so, queue the smooth-path rank as a "
        "weight, not a filter, or drop the family."),
    candidates=(
        _v("CONT", Params(mode="cont"), "top 80 by 12-1, lowest-ID half, best 20 by return"),
        _v("DISC", Params(mode="disc"), "top 80 by 12-1, highest-ID half, best 20 by return"),
        _v("MOM", Params(mode="mom"), "plain 12-1 top 20, no smoothness opinion"),
        _v("DRAW-1", Params(seed=443), "hash draw of 20 from the pool, seed 443"),
        _v("DRAW-2", Params(seed=444), "hash draw of 20 from the pool, seed 444"),
        _v("DRAW-3", Params(seed=445), "hash draw of 20 from the pool, seed 445"),
    ),
    seen_keys=("concept:information-discreteness-smooth-path-momentum",),
)
