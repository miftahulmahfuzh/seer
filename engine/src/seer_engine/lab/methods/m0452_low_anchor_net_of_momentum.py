"""M0452 — Far above the yearly low, with the momentum part taken out.

Source: a variation on M0448 (Bhootra and Hur 2013, published 2013; the dev window ends 2015, so
it holds almost none of the years after the crowd found it and any edge is likely to have faded).

M0448's low-anchor book beat plain 12-1 momentum by 2.5 points a year on dev, but the two top-20
lists shared about 61% of their names, and the momentum control moves with a book that already
failed the test window. This method asks the cleaner question: among names with *the same* 12-1
return, does being far above the 252-bar low still pick winners?

The ranking is a residual on 12-1 momentum, done by bucketing rather than regression so that it
is easy to audit: the screened pool is sorted on 12-1 return (close 21 bars ago over close 252
bars ago) and cut into five equal-count buckets; inside each bucket the names are ranked on close
over the lowest close of the last 252 bars (today included), and each bucket sends its best four.
The book is 20 equal fractional slots at Gotrade's real fees, monthly, like M0448, whose screen,
host (N20), score function and book builder are reused unchanged. A bucket holds equal weight in
the book, so the book's momentum equals the pool's: whatever it earns is not momentum.

Arms (six, the lab's cap):
  RESID        the treatment: best four per momentum bucket, behind SPY's 200-day switch.
  RESID-NEAR   the reversed rung: the four names *closest* to the low per bucket, same switch.
  RESID-NOSW / RESID-NEAR-NOSW   the same two with no switch, always invested.
  R1 / R1-NOSW   hash draw of 20 from the same pool, with and without the switch. R1-NOSW is the
               always-invested arm with no opinion in it: it prices what acting on the sort and
               on the switch each cost (the 2x2 of opinion on/off by habit on/off).
M0448's FAR and MOM arms are the comparison for "is this just momentum", read from its record.
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
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.lab.methods.m0448_far_above_the_yearly_low import (
    NOSW,
    WIN,
    LowAnchorAllocator,
    LowPrepared,
    scored_names,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    trend_on,
)

ADDED = date(2026, 11, 3)
MODES = ("resid", "resid-near", "blind")
BUCKETS = 5
MARKET = "SPY"


@dataclass(frozen=True, slots=True)
class ResidParams:
    """``inner`` is the host's screen, switch and book size; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "resid"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.inner.top % BUCKETS:
            raise ValueError(f"top must divide into {BUCKETS} buckets, got {self.inner.top}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN),
               "buckets": str(BUCKETS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> ResidParams:
    if not isinstance(params, ResidParams):
        raise TypeError(f"params must be ResidParams, got {type(params).__name__}")
    return params


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: ResidParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "blind":
        pool.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        return pool[: params.inner.top]
    pool.sort(key=lambda r: (score[r.symbol][1], r.symbol))  # low 12-1 return first
    n = len(pool)
    per = params.inner.top // BUCKETS
    sign = -1.0 if params.mode == "resid" else 1.0  # resid: farthest above the low first
    out: list[FactorRow] = []
    for b in range(BUCKETS):
        bucket = pool[b * n // BUCKETS : (b + 1) * n // BUCKETS]
        bucket.sort(key=lambda r: (sign * score[r.symbol][0], r.symbol))
        out.extend(bucket[:per])
    return out


class ResidualLowAnchorAllocator(LowAnchorAllocator):
    """M0448's pipeline with the momentum-bucketed ranking in place of its modes."""

    id = "M0452"

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

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LowPrepared):
            raise TypeError(f"prepared must be LowPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))

    def _run(self, prepared: LowPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: Any) -> tuple[Target, ...]:
        p = _check(p)
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            scores = scored_names(history, syms, data_date)
        else:
            scores = prepared.cache.get(data_date) or scored_names(history, syms, data_date)
            prepared.cache[data_date] = scores
        return targets_from_rows(choose(rows, scores, p), p)  # type: ignore[arg-type]


RESIDLOW = ResidualLowAnchorAllocator()


def _v(suffix: str, params: ResidParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0452-{suffix}", family="M0452",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=RESIDLOW, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0452",
    name="Far above the yearly low, with the momentum part taken out",
    family="stock-52week-low-anchor",
    source_kind="variation",
    source_ref="M0448 (Bhootra & Hur 2013 low-anchor); Sera 20261103-2059",
    parent_id="M0448",
    hypothesis=(
        "M0448's low-anchor book beat plain 12-1 momentum by 2.5 points a year on dev, but the "
        "two top-20 lists shared about 61% of names and the momentum control moves with a book "
        "that already failed the test window. Rank members by distance above the 252-day low "
        "among names with the same 12-1 return: the screened pool is cut into five equal-count "
        "buckets on 12-1 return, each bucket sends its four names farthest above their low, 20 "
        "equal fractional slots, monthly, at Gotrade's real fees, behind SPY's 200-day switch. "
        "Arms: RESID (treatment); RESID-NEAR (reversed: closest to the low per bucket); the "
        "no-switch twins of both; R1 and R1-NOSW (blind hash draw, with and without the "
        "switch). R1-NOSW is the always-invested arm with no opinion in it, so the lab can price "
        "the habit of acting, as the third arm beside the reversed pair. SUCCESS: RESID beats "
        "R1 by more than 1 point a year, RESID-NEAR loses to R1, RESID has a positive "
        "2009-2015 edge vs SPY and beats SPY in a majority of walk-forward folds. Predictions, "
        "written now: with momentum held flat the edge shrinks to under 2 points a year over "
        "the blind draw and is not positive in 2009-2015."
    ),
    expected_failure=(
        "The low-anchor ratio is mostly a restatement of trailing return, so inside a bucket of "
        "similar 12-1 returns it sorts on little but the shape of the last year (late runners "
        "versus early ones), which may be noise. Equal-count buckets also make the book "
        "momentum-neutral, so it forgoes the momentum premium that carried M0448 and may simply "
        "equal the blind draw. Published 2013, so any dev edge is likely to fade out of sample, "
        "and every price-trend book so far lagged SPY after 2009."
    ),
    candidates=(
        _v("RESID", ResidParams(N20, "resid"),
           "Four farthest-above-low names per 12-1 bucket, behind the switch"),
        _v("RESID-NEAR", ResidParams(N20, "resid-near"),
           "Reversed rung: four closest-to-low names per bucket, behind the switch"),
        _v("RESID-NOSW", ResidParams(NOSW, "resid"),
           "Always-invested twin of RESID: prices the switch's habit"),
        _v("RESID-NEAR-NOSW", ResidParams(NOSW, "resid-near"),
           "Always-invested twin of the reversed rung"),
        _v("R1", ResidParams(N20, "blind", 452),
           "Blind hash draw of 20, seed 452, behind the switch: the switch with no sort"),
        _v("R1-NOSW", ResidParams(NOSW, "blind", 452),
           "Always invested, no opinion: prices acting on the sort and on the switch"),
    ),
    seen_keys=(
        "concept:52-week-low-anchor-net-of-momentum",
    ),
)
