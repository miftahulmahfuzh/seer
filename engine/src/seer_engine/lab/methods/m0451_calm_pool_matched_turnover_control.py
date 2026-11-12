"""M0451 — Calm-stock buffer: a random control redrawn at the ranked book's trade count.

Source: variation on M0419 (itself a variation on M0417; Ang, Hodrick, Xing, Zhang 2006).

M0419 buffered the calm-stock book (hold until a name leaves the calmest 40) and ran two random
"chance spread" twins with the same buffer mechanics, hoping they would churn at a comparable
pace. They did not: M0419-R1-BUF40 and R2-BUF40 traded 210 and 219 times against the ranked
BUF40's 692, about 0.3x. The reason is the random twins' hash order has no date in its key
(``m0293_calm_filter_on_a_host.draw``), so a name's rank under that hash never changes month to
month; the buffer then almost never fires, and a held name is dropped only when it leaves the
scored pool outright. A random control that trades four times less often than the book it is
meant to price is not a clean read: lower turnover alone, not the absence of a ranking opinion,
could explain part of its edge.

This method drops the rank-buffer mechanic entirely and controls the trade count directly. Each
month a fresh hash order is drawn over the scored pool (``m0187_placebo_hash_order.draw``, which
keys on the year and month, so the order reshuffles every month instead of staying sticky). The
``rotate_k`` lowest-hash-ranked names *currently held* are forced out, and the ``rotate_k``
lowest-hash-ranked names *not held* are drawn in to replace them (new entries fill the slots
emptied by forced exits and by any held name that has left the scored pool outright). Trade count
then scales almost linearly with ``rotate_k`` x months, with no indirect buffer-rank algebra to
second-guess: ``rotate_k=1`` should land near the 20-name book's lower turnover range,
``rotate_k=3`` well above M0419-BUF40's 692 trades, bracketing the match from both sides.

Pool and screen are M0417's: point-in-time members, the F4 screen, 20 equal slots, monthly,
fractional shares at Gotrade's real fees, SPY's 200-day switch on every arm but one. The ranked
twin is not re-registered; M0419-BUF40 (692 trades, +7.5%/yr funded) is read from there because a
configuration runs once.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
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
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    factor_lookback,
    factor_rows,
    trend_on,
)

ADDED = date(2026, 11, 12)


@dataclass(frozen=True, slots=True)
class RotParams:
    """``inner`` is the host's screen, switch and book size. ``rotate_k`` names are forced out
    (and replaced) every month, ranked by that month's fresh hash draw; ``seed`` is the draw's
    only source of randomness."""

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
               "mechanism": "forced-monthly-rotation-redrawn-hash"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> RotParams:
    if not isinstance(params, RotParams):
        raise TypeError(f"params must be RotParams, got {type(params).__name__}")
    return params


def choose_rotated(rows, stats: dict[str, tuple[float, float]], held: frozenset[str],
                    data_date: date, p: RotParams):
    """This month's book: force out the ``rotate_k`` lowest-hash held names (plus any held name
    no longer in ``stats``), fill with the lowest-hash names not already kept."""
    pool = sorted(s for s in stats if s not in EXCLUDED)
    held_elig = sorted(s for s in held if s in stats and s not in EXCLUDED)
    held_ranked = sorted(held_elig, key=lambda s: (draw_redraw(p.seed, s, data_date), s))
    n_drop = min(p.rotate_k, len(held_ranked))
    kept = set(held_ranked[n_drop:])
    need = max(p.inner.top - len(kept), 0)
    candidates = sorted((s for s in pool if s not in kept),
                        key=lambda s: (draw_redraw(p.seed, s, data_date), s))
    chosen = sorted(kept) + candidates[:need]
    row_by_sym = {r.symbol: r for r in rows}
    return [row_by_sym[s] for s in chosen if s in row_by_sym]


def _targets(chosen, p: RotParams) -> tuple[Target, ...]:
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for r in chosen:
        t = target_from_close(r.symbol, r.close, w)
        if t is not None:
            out.append(t)
    return tuple(out)


class ForcedRotationAllocator:
    """A random control that churns at a chosen, directly-set pace: every month it forces exactly
    ``rotate_k`` of its current holdings out (lowest fresh hash rank that month) and draws
    ``rotate_k`` replacements (also lowest fresh hash rank), from M0417's scored pool."""

    id = "M0451"

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
             p: RotParams) -> tuple[Target, ...]:
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
        return _targets(choose_rotated(rows, stats, held, data_date, p), p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IvolPrepared:
        from seer_engine.strategies.f_factor import prepare_factor
        return IvolPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IvolPrepared):
            raise TypeError(f"prepared must be IvolPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, held, _check(params))


ROT = ForcedRotationAllocator()


def _v(suffix: str, params: RotParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0451-{suffix}", family="M0451",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ROT, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0451",
    name="Calm-stock buffer: random control redrawn at the ranked book's trade count",
    family="stock-idiosyncratic-volatility",
    source_kind="variation",
    source_ref="M0419 variation: a turnover-matched random control, Ang Hodrick Xing Zhang 2006",
    parent_id="M0419",
    hypothesis=(
        "M0419's random buffered twins traded 0.3x as often as the ranked calm book (210-219 "
        "trades against 692) because their hash order carried no date, so the buffer almost "
        "never fired. Here the hash order is redrawn every month and a fixed count of holdings, "
        "rotate_k, is forced out and replaced each month regardless of any ranking, from "
        "M0417's own scored pool. Trade count then scales directly with rotate_k, not with a "
        "buffer-rank guess. Arms, all fractional at real fees, 20 equal slots, monthly, behind "
        "SPY's 200-day switch except one: ROT1 (rotate_k=1, seed 4511), ROT2-S1 (rotate_k=2, "
        "seed 4511), ROT2-S2 (rotate_k=2, seed 4522: the chance spread at the rung expected to "
        "land nearest M0419-BUF40's 692 trades), ROT3 (rotate_k=3, seed 4511), and "
        "ROT2-S1-NOSW (rotate_k=2, seed 4511, no switch: prices the switch's habit apart from "
        "any opinion, there being none here). SUCCESS, written now: whichever rotate_k lands "
        "within 15% of 692 trades scores within 2 points a year of M0419-BUF40's +7.5%, meaning "
        "the earlier random twins' apparent edge was mostly their lower turnover, not an absent "
        "ranking opinion; if instead the matched-turnover control clearly trails M0419-BUF40, "
        "the calmest-40 ranking itself was adding something the under-traded controls hid."
    ),
    expected_failure=(
        "No rotate_k lands exactly on 692 trades (three discrete rungs bracketing a continuous "
        "target rarely hit it on the nose), so the read is an interpolation, not an exact match, "
        "and must be reported as such. A second failure mode: forced monthly rotation at a fixed "
        "hash order may itself behave unlike a buffer-driven book in ways beyond trade count "
        "(e.g. holding-period distribution), so even a matched trade count may not fully settle "
        "whether turnover alone explains M0419's random-control edge. If either happens, the "
        "honest reading uses whichever rung's trade count brackets 692 most closely and says so "
        "plainly, and a follow-up would need a continuous (probabilistic) rotation rate instead "
        "of discrete rotate_k rungs."
    ),
    candidates=(
        _v("ROT1", RotParams(N20, 4511, 1),
           "Force out and replace 1 holding a month, seed 4511, behind the switch"),
        _v("ROT2-S1", RotParams(N20, 4511, 2),
           "Force out and replace 2 holdings a month, seed 4511, behind the switch"),
        _v("ROT2-S2", RotParams(N20, 4522, 2),
           "Control: same rotate_k=2, seed 4522 (chance spread), behind the switch"),
        _v("ROT3", RotParams(N20, 4511, 3),
           "Force out and replace 3 holdings a month, seed 4511, behind the switch"),
        _v("ROT2-S1-NOSW", RotParams(NOSW, 4511, 2),
           "ROT2-S1 with no SPY switch: the always-invested twin"),
    ),
    seen_keys=(
        "concept:low-idiosyncratic-volatility-rank-buffer",
        "concept:turnover-matched-random-control",
        "concept:forced-monthly-rotation-redrawn-hash",
    ),
)
