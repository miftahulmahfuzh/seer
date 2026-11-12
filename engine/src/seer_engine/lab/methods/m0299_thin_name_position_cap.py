"""M0299 — Cap the thinnest names instead of refusing them: liveness protection without the tilt.

Source: variation of M0288, chassis M0032/M0007-N20-RAW (Blitz, Huij & Martens 2011, Residual
momentum, J. Empirical Finance 18(3), 506-521).

Idea: M0288 bought 3.5 points a year of survivorship honesty for 5.4 points a year of dev return,
and its own breadth report says exactly where the 5.4 went -- the floor herds the book into the
largest, most-traded names (narrow-month lead climbs 5.6 to 11.4 percent across the five rungs
while broad-month lead falls 6.4 to minus 4.7, both monotone, with names held and exposure barely
moving). So the whole price is a size tilt, and a tilt is a design choice bought more cheaply than
by refusing names outright. Instead of excluding the least-traded fifth of the pool, this lets
every eligible name be picked but caps what a bottom-quintile pick may be WORTH: it costs only
``cap_frac`` of a full slot's budget instead of a whole one, and the slot money freed by capping
it is spent further down the ranked list -- never parked in cash or SPY, which M0279 already
measured at 2 to 6 points a year of its own cost.

The cut itself (bottom 20 percent of the day's own eligible pool by 20-day mean dollar volume) is
fixed at M0288's own cross-sectional quintile boundary (``m0288_liveness_volume_floor.apply_floor``,
reused verbatim so the boundary is identical) -- M0288 already swept the CUT five ways; this
experiment holds that finding constant and sweeps the other half of the design, what a pick past
the cut is worth. Rungs: ``CAP100`` (1.0, no cap -- the reference arm, which must reproduce
M0032-N20-RAW-FRAC-GT bit for bit), ``CAP075``, ``CAP050``, ``CAP025`` and ``CAP000`` (0.0, which
degenerates to M0288-DV20's book exactly: a thin pick costs nothing, so the ranked walk below
skips it for free and the chosen set is exactly the top 20 of the untouched 80%, tying this
ladder to M0288's at one end and making this a genuine extension rather than a fresh guess).

Mechanism, concretely: rank every scorable row (same screen, same scores, ``scaled=False`` so a
symbol's own residual score never depends on who else is in the pool -- the same choice M0288
made, which is what lets both ladders meet exactly at their shared ends) by score descending.
Walk the ranked list spending a slot budget of ``top`` (20) full slots: a name outside the bottom
quintile costs one full slot and is held at the base equal weight; a name inside it costs
``cap_frac`` of a slot and is held at ``cap_frac`` of the base weight. The walk keeps going past
the usual top-20 cutoff whenever a capped pick only spent part of a slot, so the book can hold
more than 20 names and still invests the same total weight it always has. ``cap_frac=0`` spends
zero budget on a thin name (so it is skipped and never held, and the walk is equivalent to
filtering the pool first); ``cap_frac=1`` makes every name cost one slot regardless of its volume,
which is exactly M0032's book with no opinion in it.

Pure: reads only F4's own feature columns (computed through ``data_date``) and the residual
scores built on bars through the same date; nothing dated after ``data_date`` is touched.
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
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
    RESIDMOM,
    FACTOR_SYMBOLS,
    ResidParams,
    ResidPrepared,
    build_grid,
    residual_scores,
    resid_lookback,
)
from seer_engine.lab.methods.m0288_liveness_volume_floor import apply_floor
from seer_engine.sim.book import Target, equal_weight, to_weight, WEIGHT_QUANTUM
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorRow, factor_rows, trend_on

ADDED = date(2026, 11, 12)
QUINTILE_PCT = 20  # bottom fifth of the day's own eligible pool by 20-day mean dollar volume


@dataclass(frozen=True, slots=True)
class CapParams:
    """``inner`` is M0032's configuration verbatim; ``cap_frac`` is the only dial.

    The quintile cut is M0288's own (``QUINTILE_PCT``, fixed): M0288 already swept the cut five
    ways, so this holds it constant and sweeps what a pick past it is worth instead.
    """

    inner: ResidParams
    cap_frac: Decimal = Decimal(1)  # a thin pick's weight = cap_frac of a full slot; 0 excludes it

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not isinstance(self.cap_frac, Decimal) or not self.cap_frac.is_finite():
            raise TypeError(f"cap_frac must be a finite Decimal, got {self.cap_frac!r}")
        if not (0 <= self.cap_frac <= 1):
            raise ValueError(f"cap_frac must be in [0, 1], got {self.cap_frac}")

    def as_dict(self) -> dict[str, str]:
        out = {"cap_frac": str(self.cap_frac)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def thin_symbols(rows: list[FactorRow]) -> frozenset[str]:
    """Symbols in the bottom ``QUINTILE_PCT`` percent of ``rows`` by 20-day mean dollar volume.

    Reuses M0288's own cross-sectional, rank-based cut (ties by symbol ascending) so the boundary
    a pick is capped against here is identical to the one M0288 would have refused it at.
    """
    if not rows:
        return frozenset()
    kept = {r.symbol for r in apply_floor(rows, QUINTILE_PCT)}
    return frozenset(r.symbol for r in rows if r.symbol not in kept)


def _weighted_targets(rows: list[FactorRow], scores: Mapping[str, float], inner: ResidParams,
                       cap_frac: Decimal, thin: frozenset[str]) -> tuple[Target, ...]:
    """Walk the ranked list spending a ``top``-slot budget; a thin pick costs ``cap_frac`` of one.

    Weight is always ``base_weight * slots spent``, so a pick that only spends a fraction of a
    slot is held at that same fraction of the base weight -- there is no separate redistribution
    step; the freed budget is simply still available for the next name down the ranked list.
    """
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    ranked = sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))
    top = inner.inner.top
    base = equal_weight(top)
    budget_target = Decimal(top)
    budget = Decimal(0)
    out: list[Target] = []
    for row in ranked:
        if budget >= budget_target:
            break
        cost = cap_frac if row.symbol in thin else Decimal(1)
        if cost == 0:
            continue  # a thin pick worth nothing spends nothing and is never held
        remaining = budget_target - budget
        filled = cost if cost <= remaining else remaining
        weight = base * filled
        budget += filled
        if weight < WEIGHT_QUANTUM:
            continue
        target = target_from_close(row.symbol, row.close, to_weight(weight))
        if target is not None:
            out.append(target)
    return tuple(out)


def _check(params: object) -> CapParams:
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    return params


class PositionCapAllocator:
    """M0032's residual-momentum book with a position-size cap on its thinnest picks.

    A pick's own dollar-volume rank decides what it is WORTH, not whether it exists: a bottom-
    quintile name still competes for a slot on its score, but a full slot of money only goes to
    it at ``cap_frac=1``. Held symbols get no special treatment -- the targets are the new
    weighted set, so a name that falls out of it, or whose weight floors to nothing, is
    signal-exited by the book engine, exactly as in M0007 and M0288.
    """

    id = "M0299"

    def lookback(self, params: Any) -> int:
        return resid_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params).inner
        return tuple(sorted({p.market, *FACTOR_SYMBOLS(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = p.inner
        if not trend_on(history, data_date, inner.inner):
            return ()
        rows = factor_rows(history, members, data_date, inner.inner)
        if not rows:
            return ()
        thin = thin_symbols(rows)
        grid = build_grid(history, inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return _weighted_targets(rows, scores, inner, p.cap_frac, thin)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = p.inner
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, inner.inner)
        if not rows:
            return ()
        thin = thin_symbols(rows)
        grid = prepared.grid(inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return _weighted_targets(rows, scores, inner, p.cap_frac, thin)


CAP = PositionCapAllocator()

#: M0032-N20-RAW-FRAC-GT's configuration, which every rung shares but for ``cap_frac``.
BASE = ResidParams(N20, scaled=False)


def _v(suffix: str, cap_frac: Decimal, rationale: str) -> Candidate:
    return Candidate(id=f"M0299-{suffix}", family="M0299", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAP, params=CapParams(BASE, cap_frac), rationale=rationale,
                     added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0299",
    name=(
        "Cap the thinnest names instead of refusing them: liveness protection without the "
        "big-company tilt"
    ),
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref=(
        "variation of M0288 (its cross-sectional dollar-volume floor and the breadth report that "
        "attributed its cost to a size tilt rather than the names it removed), carried onto "
        "M0032's chassis -- M0007-N20-RAW in fractional shares at Gotrade's real fees on the "
        "owner's deposits (Blitz, Huij & Martens 2011, Residual momentum, J. Empirical Finance "
        "18(3), 506-521)"
    ),
    parent_id="M0288",
    hypothesis=(
        "M0288 bought 3.5 points a year of survivorship honesty for 5.4 points a year of dev "
        "return, and the breadth report says exactly where the 5.4 went: the floor herds the "
        "book into the largest, most-traded names. Lead in narrow months climbs 5.6 to 11.4 "
        "percent across the five rungs while lead in broad months falls 6.4 to minus 4.7 -- five "
        "steps, both directions, monotone, with no fee or cash-drag component (names held stayed "
        "at 20.0 and exposure moved only 69.4 to 68.6 percent). So the whole price is a size "
        "tilt, and a tilt is a design choice that can be bought more cheaply than by refusing "
        "names outright. Instead of excluding the least-traded part of the pool, let every "
        "eligible name be picked but cap what the thinnest ones may be worth: a pick in the "
        "bottom quintile by 20-day mean dollar volume costs only cap_frac of a full slot's "
        "budget, and the slot money freed by capping it is spent on the next-ranked name down "
        "the list rather than parked in cash or SPY -- M0279 measured parking at 2 to 6 points a "
        "year and M0288's design deliberately avoided it, so this one must too. Rungs on the "
        "cap: 1.0 (no cap, the reference arm that must reproduce M0032-N20-RAW-FRAC-GT bit for "
        "bit), 0.75, 0.5, 0.25 and 0.0 (which degenerates exactly to M0288-DV20's book -- a thin "
        "pick costing nothing is skipped for free, so the ranked walk ends up choosing the top "
        "20 of the untouched 80% precisely as M0288's pre-selection filter does -- tying the two "
        "ladders together at one end and making this a genuine extension rather than a fresh "
        "guess). Chassis unchanged: M0007-N20-RAW, F4's screen, the SPY-200 monthly switch, "
        "fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade, the owner's "
        "monthly deposits. Success for the idea: a cap that keeps at least half of M0288's "
        "honesty swing (the dev-minus-check-store gap M0288 measured, read with lab survivorship) "
        "while giving up under 1.5 points a year of dev return against CAP100, with the "
        "narrow-versus-broad lead spread clearly flatter than the floor ladder's at a matching "
        "amount of honesty bought. Success for the gate, separately, and unrelated to the idea: "
        "an arm with a worst fall under the screen's bar that beats total-return SPY with DSR >= "
        "0.90."
    ),
    expected_failure=(
        "Four ways this can fail, in the order I think they bite. First, a partial-weight book "
        "can record few or no new trades at some rungs while still moving exposure and holding "
        "more than 20 names at once -- another lab method with a partial-weight dial recorded "
        "exactly this shape (zero new trades with exposure still moving), so trade counts and "
        "profit factor may read strangely here too and exposure, not trades, is the meter to "
        "watch. Second, spending "
        "freed slot money further down the ranked list is itself a size tilt in a different "
        "direction: the 21st-, 22nd-, ... ranked names it reaches for are, on average, LOWER "
        "momentum than the top 20, so even a cap that buys back all of M0288's honesty gap may "
        "still cost dev return for a reason that has nothing to do with company size -- diluting "
        "the book's conviction. Third, and the central risk to the whole idea: a cap is only "
        "cheaper than a floor if the size tilt and the liveness signal are separable, but a "
        "thinly-traded name that still clears F4's own $20M screen may BE the liveness signal "
        "(dying companies trade thin before they die), in which case capping its weight half-buys "
        "both the honesty and the tilt together and the ladder's two effects move in lockstep "
        "rather than trading off -- the measurement that tells them apart is whether the "
        "narrow-versus-broad spread flattens faster or slower than the honesty gap closes, rung "
        "by rung. Fourth, like M0288 this cannot produce a candidate regardless of what it shows: "
        "the chassis kin (M0021, M0022, M0029) already failed the test window, so the hard gate "
        "refuses promotion whatever the result."
    ),
    candidates=(
        _v("CAP100", Decimal(1),
           "Control: repeats M0032-N20-RAW-FRAC-GT's book exactly (M0288-DV00), no opinion about "
           "a thin pick's weight -- the reference rung"),
        _v("CAP075", Decimal("0.75"), "A bottom-quintile pick is worth three quarters of a slot"),
        _v("CAP050", Decimal("0.5"), "A bottom-quintile pick is worth half a slot"),
        _v("CAP025", Decimal("0.25"), "A bottom-quintile pick is worth a quarter slot"),
        _v("CAP000", Decimal(0),
           "Control: repeats M0288-DV20's book exactly (a bottom-quintile pick is worth nothing, "
           "so it is skipped and the walk fills on the untouched 80% precisely as M0288's own "
           "pre-selection filter does) -- ties this ladder to M0288's at one end"),
    ),
    seen_keys=("concept:thin-name-position-cap",),
)
