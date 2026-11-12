"""M0445 — Smoothest of a wide winners pool: rank the top 200 by 12-1 return on smoothness alone.

Source: variation of M0443 (Da, Gurun, Warachka 2014, "Frog in the Pan"). M0443 trimmed the top 80
12-1 winners to the smoother half, then re-ranked that half by return — so 20 of its 40 survivors
were names that would have made a plain top-20 momentum book anyway (M0443's own analysis). Here
the pool is widened to the top 200 by 12-1 return and smoothness becomes the ranking itself, not a
trim: hold the 20 lowest-information-discreteness names in that pool directly, without a second
sort by return. If smoothness carries information beyond "was already a top-20 momentum name", a
much wider pool should surface it; if it carries none, SMOOTH should sit inside the hash draws'
spread exactly as M0402 (consistency) and M0438 (jump size) found.

Information discreteness is M0443's: ID = sign(12-1 return) x (share of down days minus share of
up days) over the formation window (231 daily returns, 252 to 21 trading days back). Low ID is
continuous (smooth); high ID is a few jumps.

``WideFrogAlloc`` reuses FACTOR's screen, point-in-time index pool and SPY 200-day switch, 20
equal slots, monthly. ``mode`` picks the rule: "smooth" the 20 lowest-ID names among the top
``WINNERS`` (200) by 12-1 return; "jump" the 20 highest-ID names in the same pool (the mirror);
"mom" plain 12-1 top 20 (the no-opinion control — this is the identical book M0443-MOM already
recorded, since WINNERS does not affect that branch; declared, not re-counted); an int seed is a
hash draw of 20 from the same top-200 pool (the error bar; new seeds, since M0443's draws came
from the unrestricted screen, not this 200-name pool). Pure; reads only bars dated <= data_date.
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
from seer_engine.lab.methods.m0443_frog_in_the_pan_momentum import discreteness
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

ADDED = date(2026, 11, 12)

SWITCH = ("SPY", 200)
TOP = 20
WINNERS = 200
LOOK = 252
SKIP = 21
MODES = ("mom", "smooth", "jump")


@dataclass(frozen=True, slots=True)
class Params:
    """``mode`` is "mom", "smooth" or "jump"; ``seed`` (an int) replaces it with a hash draw."""

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


def choose(rows: Sequence[FactorRow], history: Mapping[str, History], data_date: date,
           p: Params) -> list[FactorRow]:
    by_mom = sorted(rows, key=lambda r: (-r.momentum, r.symbol))
    if p.mode == "mom" and p.seed is None:
        return by_mom[:TOP]
    pool = by_mom[:WINNERS]
    if p.seed is not None:
        seed = p.seed
        return sorted(pool, key=lambda r: (float(draw(seed, r.symbol)), r.symbol))[:TOP]
    scored: list[tuple[float, FactorRow]] = []
    for r in pool:
        h = history.get(r.symbol)
        v = discreteness(h, data_date) if h is not None else None
        if v is not None:
            scored.append((v, r))
    if not scored:
        return []
    ordered = sorted(scored, key=lambda t: (t[0], t[1].symbol))
    picked = ordered[:TOP] if p.mode == "smooth" else ordered[len(ordered) - TOP:]
    return sorted((r for _, r in picked), key=lambda r: (-r.momentum, r.symbol))


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


class WideFrogAlloc:
    """FACTOR's screen and switch, with the pick ordered by smoothness over a wide winners pool."""

    id = "M0445"

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


WIDEFROG = WideFrogAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0445-{suffix}", family="M0445", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=WIDEFROG, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0445",
    name="Smoothest of a wide winners pool: rank the top 200 by 12-1 return on smoothness alone",
    family="stock-information-discreteness",
    source_kind="variation",
    source_ref="M0443",
    parent_id="M0443",
    hypothesis=(
        "M0443 trimmed the top 80 12-1 winners to the smoother half, then re-ranked that half by "
        "return: 20 of its 40 survivors duplicated a plain top-20 momentum book (M0443's own "
        "analysis). Here the pool widens to the top 200 by 12-1 return and smoothness (information "
        "discreteness: sign of the 12-1 return times the share of down days minus the share of up "
        "days over the formation window) becomes the ranking itself, holding the 20 lowest-ID "
        "names directly, with no second sort by return. Arms, all behind SPY's 200-day switch, "
        "20 equal slots, monthly, fractional shares at Gotrade's real fees, the F4-screened "
        "point-in-time index pool: SMOOTH (20 lowest-ID of the top 200 by 12-1 return), JUMP (20 "
        "highest-ID of the same 200, the mirror), MOM (plain 12-1 top 20, the no-opinion control — "
        "Control: M0443-MOM's book, never re-run here) and DRAW-1..3 (twenty names from the same "
        "200-name pool in sticky hash order, seeds 4451-4453, the error bar; new seeds because "
        "M0443's draws came from the unrestricted screen, not this 200-name pool). SUCCESS, "
        "written now: SMOOTH beats MOM and the best DRAW on 2009-2015 return vs SPY and clears the "
        "20% fall bar and DSR 0.95, while JUMP does worse than MOM. Prediction: a wider pool gives "
        "smoothness room to pick names a plain momentum book would not, so SMOOTH and MOM diverge "
        "by more than M0443's CONT and MOM did."),
    expected_failure=(
        "Widening the pool does not rescue the signal: SMOOTH, JUMP and MOM sit inside the draws' "
        "spread, exactly as M0402 (consistency) and M0438 (jump size) found when they tried their "
        "own wider or narrower pools. The switch and the large-index frame carry whatever return "
        "there is, every arm lags SPY in 2009-2015 through time in cash and fees, and a 2014 "
        "paper's edge faded before the dev window's end. Three draws are a thin error bar. If so, "
        "the information-discreteness family (M0402, M0438, M0443, M0445) is exhausted: journal "
        "that and do not queue a fourth pool-size variation."),
    candidates=(
        _v("SMOOTH", Params(mode="smooth"), "20 lowest-ID of the top 200 by 12-1 return"),
        _v("JUMP", Params(mode="jump"), "20 highest-ID of the top 200 by 12-1 return, the mirror"),
        _v("MOM", Params(mode="mom"),
           "Control: M0443-MOM's book (plain 12-1 top 20), no smoothness opinion"),
        _v("DRAW-1", Params(seed=4451), "hash draw of 20 from the 200-name pool, seed 4451"),
        _v("DRAW-2", Params(seed=4452), "hash draw of 20 from the 200-name pool, seed 4452"),
        _v("DRAW-3", Params(seed=4453), "hash draw of 20 from the 200-name pool, seed 4453"),
    ),
    seen_keys=("concept:information-discreteness-smooth-path-momentum",),
)
