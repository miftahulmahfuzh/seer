"""M0593 — Audit: the lab's undated random-stock controls, and a redraw of M0424's calm-pool one.

Source: variation on M0424 (itself a variation on M0417; Ang, Hodrick, Xing, Zhang 2006), using
M0451's forced-rotation mechanism (variation on M0419).

A lab-wide audit (recorded in this method's analysis, not here) found that every method importing
``m0293_calm_filter_on_a_host.draw`` -- a 64-bit hash of (seed, symbol) with no date in the key, so
a name's rank under it never changes month to month -- shares one shape of result: the method's
only dev-eligible arm is the random control itself, trading far less often than the ranked arm it
is meant to price. M0419 was the first case found and M0451 already redrew its control at a forced
monthly pace, settling that question for M0417/M0419's whole-pool book. M0424 asked a related
question (is the calm pool itself the edge, not the picking in it) and inherited the same control:
M0424-RAND-BUF-2 (478 trades, MAR 0.44) is the method's only dev-eligible arm, while the two ranked
arms it was meant to price -- M0424-RANK-BUF (a holding stays until it leaves the lowest half of
the calm third, 325 trades) and M0424-RANK-NOBUF (re-ranked every month, 1,276 trades) -- both
failed DSR. RAND-BUF-2's pace (478 trades) sits between the two, matching neither, so its apparent
edge is still unpriced against either ranked book's real turnover.

This method drops M0424's rank buffer entirely and controls the trade count directly, the way
M0451 did for M0419: each month a fresh hash order is drawn over the calm third
(``m0187_placebo_hash_order.draw``, keyed on year and month so the order reshuffles instead of
staying sticky), and ``rotate_k`` of the currently-held calm-third names are forced out (lowest
fresh hash rank) and replaced by the ``rotate_k`` lowest fresh-hash-ranked calm names not already
held. Held names that have left the calm third outright are dropped regardless of ``rotate_k``.
Trade count then scales with ``rotate_k`` x months: M0451 measured rotate_k=1 at 357 trades,
rotate_k=2 at 509-510, rotate_k=3 at 656 on the whole scored pool; the calm third restricts the
pool but not the book size, so the same rungs should land close. rotate_k=1 brackets
M0424-RANK-BUF's 325 trades from above; rotate_k=7 (extrapolated, ~207 + 150 x 7 = 1,257) brackets
M0424-RANK-NOBUF's 1,276 trades from below; rotate_k=2 repeats RAND-BUF-2's own 478-trade pace at
a second, dated hash order instead of a frozen one.

Pool and screen are M0424's: point-in-time members, F4 screen, the calmest third by trailing
63-day residual volatility on SPY, 20 equal slots, monthly, fractional shares at Gotrade's real
fees, SPY's 200-day switch on every arm but one. M0424's own candidates are not re-registered;
M0424-RANK-BUF (325 trades), M0424-RANK-NOBUF (1,276 trades) and M0424-RAND-BUF-2 (478 trades,
+MAR 0.44, the only dev-eligible arm) are read from there because a configuration runs once.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0187_placebo_hash_order import draw as draw_redraw
from seer_engine.lab.methods.m0417_low_residual_volatility import (
    MARKET,
    NOSW,
    WIN,
    IvolPrepared,
    scored_names,
)
from seer_engine.lab.methods.m0424_calm_pool_random_with_buffer import POOL_FRAC
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)


@dataclass(frozen=True, slots=True)
class CalmRotParams:
    """``inner`` is the host's screen, switch and book size. ``rotate_k`` calm-third names are
    forced out (and replaced, also from the calm third) every month, ranked by that month's fresh
    hash draw; ``seed`` is the draw's only source of randomness."""

    inner: FactorParams
    seed: int = 0
    rotate_k: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if isinstance(self.rotate_k, bool) or not isinstance(self.rotate_k, int):
            raise TypeError(f"rotate_k must be an int, got {type(self.rotate_k).__name__}")
        if self.rotate_k < 1:
            raise ValueError(f"rotate_k must be >= 1, got {self.rotate_k}")
        if self.rotate_k > self.inner.top:
            raise ValueError("rotate_k must be <= the book size")

    def as_dict(self) -> dict[str, str]:
        out = {"seed": str(self.seed), "rotate_k": str(self.rotate_k), "win": str(WIN),
               "pool": f"{POOL_FRAC:.4f}", "mechanism": "forced-monthly-rotation-redrawn-hash-calm-pool"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CalmRotParams:
    if not isinstance(params, CalmRotParams):
        raise TypeError(f"params must be CalmRotParams, got {type(params).__name__}")
    return params


def choose_rotated_calm(rows, stats: dict[str, tuple[float, float]], held: frozenset[str],
                         data_date: date, p: CalmRotParams):
    """This month's book: the calmest third by residual vol, then force out the ``rotate_k``
    lowest-hash held calm names (plus any held name no longer in the calm third), fill with the
    lowest-hash calm names not already kept."""
    pool_rows = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in stats]
    pool_rows.sort(key=lambda r: (stats[r.symbol][0], r.symbol))  # calmest first
    n = len(pool_rows)
    if n == 0:
        return []
    calm = pool_rows[: max(1, ceil(n * POOL_FRAC))]
    calm_syms = {r.symbol for r in calm}
    held_elig = sorted(s for s in held if s in calm_syms)
    held_ranked = sorted(held_elig, key=lambda s: (draw_redraw(p.seed, s, data_date), s))
    n_drop = min(p.rotate_k, len(held_ranked))
    kept = set(held_ranked[n_drop:])
    need = max(p.inner.top - len(kept), 0)
    candidates = sorted((s for s in calm_syms if s not in kept),
                        key=lambda s: (draw_redraw(p.seed, s, data_date), s))
    chosen_syms = sorted(kept) + candidates[:need]
    row_by_sym = {r.symbol: r for r in calm}
    return [row_by_sym[s] for s in chosen_syms if s in row_by_sym]


def _targets(chosen, p: CalmRotParams) -> tuple[Target, ...]:
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for r in chosen:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class CalmForcedRotationAllocator:
    """A random control, inside M0424's calm third, that churns at a chosen, directly-set pace:
    every month it forces exactly ``rotate_k`` of its current holdings out (lowest fresh hash rank
    that month) and draws ``rotate_k`` replacements (also lowest fresh hash rank), from the calm
    third of M0417's scored pool."""

    id = "M0593"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IvolPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, held: frozenset[str],
             p: CalmRotParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            stats = scored_names(history, syms, data_date)
        else:
            stats = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = stats
        return _targets(choose_rotated_calm(rows, stats, held, data_date, p), p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IvolPrepared:
        return IvolPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IvolPrepared):
            raise TypeError(f"prepared must be IvolPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, held, _check(params))


ROT = CalmForcedRotationAllocator()


def _v(suffix: str, params: CalmRotParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0593-{suffix}", family="M0593",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ROT, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0593",
    name="Audit the lab's undated random-stock controls; redraw M0424's calm-pool one",
    family="method-lab-practice",
    source_kind="variation",
    source_ref="variation on M0424 (Ang, Hodrick, Xing, Zhang 2006), using M0451's redraw method",
    parent_id="M0424",
    hypothesis=(
        "A lab-wide audit (this method's analysis) found every method using "
        "m0293_calm_filter_on_a_host.draw -- a hash with no date, so the picked set barely moves "
        "month to month -- clears the dev screen only on that frozen control, never on the ranked "
        "arm it is meant to price. M0424 is one of these: M0424-RAND-BUF-2 (478 trades, the hash "
        "draw with a rank buffer, same buffer mechanic as M0419's) is the method's only "
        "dev-eligible arm, while M0424-RANK-BUF (325 trades) and M0424-RANK-NOBUF (1,276 trades) "
        "both failed DSR. RAND-BUF-2's pace matches neither ranked book, so whether its edge "
        "survives at either one's real turnover is still unmeasured. Here the buffer is replaced "
        "by forced monthly rotation at a fixed count, redrawn from a dated hash so the order "
        "reshuffles instead of staying sticky. Arms, all fractional at real fees, 20 equal slots "
        "from the calm third, monthly, behind SPY's 200-day switch except one: ROT1 (rotate_k=1, "
        "seed 5931, brackets RANK-BUF's 325 trades from above), ROT2-S1 and ROT2-S2 (rotate_k=2, "
        "seeds 5931 and 5932, repeating RAND-BUF-2's own 478-trade pace at a dated hash, with a "
        "chance spread), ROT7 (rotate_k=7, seed 5931, extrapolated to bracket RANK-NOBUF's 1,276 "
        "trades from below), and ROT2-S1-NOSW (rotate_k=2, seed 5931, no switch: prices the "
        "switch's habit apart from any opinion, there being none here). SUCCESS, written now: a "
        "rung landing within 15% of 478 trades scores within 2 points a year of M0424-RAND-BUF-2's "
        "return, meaning the frozen control's edge was not a turnover artifact and the calm pool "
        "itself may carry something; if instead every rung at a comparable or higher trade count "
        "trails SPY in 2009-2015 (where RAND-BUF-2 itself already does, per M0424's own hypothesis "
        "prediction), the control's apparent DSR clearance was mostly its low, frozen turnover, "
        "not the calm pool or any opinion."
    ),
    expected_failure=(
        "rotate_k is a discrete rung bracketing a continuous trade-count target, so no rung lands "
        "exactly on 478, 325 or 1,276 trades, and the read is an interpolation that must be "
        "reported as such. A calm third of large index members is the same utilities-and-staples "
        "sleeve M0424 already flagged as likely to trail SPY in 2009-2015 whatever is picked in "
        "it, so a forced-rotation rung may simply repeat that result without settling whether "
        "turnover or the pool explains RAND-BUF-2's dev-screen clearance. If so, the honest "
        "reading says which rung brackets which recorded trade count most closely and reports the "
        "2009-2015 read for every rung regardless of DSR, since the DSR screen is exactly what "
        "this method doubts."
    ),
    candidates=(
        _v("ROT1", CalmRotParams(N20, 5931, 1),
           "Force out and replace 1 calm-third holding a month, seed 5931, behind the switch"),
        _v("ROT2-S1", CalmRotParams(N20, 5931, 2),
           "Force out and replace 2 calm-third holdings a month, seed 5931, behind the switch"),
        _v("ROT2-S2", CalmRotParams(N20, 5932, 2),
           "Control: same rotate_k=2, seed 5932 (chance spread), behind the switch"),
        _v("ROT7", CalmRotParams(N20, 5931, 7),
           "Force out and replace 7 calm-third holdings a month, seed 5931, behind the switch"),
        _v("ROT2-S1-NOSW", CalmRotParams(NOSW, 5931, 2),
           "ROT2-S1 with no SPY switch: the always-invested twin"),
    ),
    seen_keys=(
        "concept:undated-hash-random-control-audit",
        "concept:turnover-matched-random-control",
        "concept:forced-monthly-rotation-redrawn-hash-calm-pool",
    ),
)
