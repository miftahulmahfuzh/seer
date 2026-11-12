"""M0591 — Volume surprise scaled by move size, sign-agnostic, against four blind draws.

M0461 and M0467 both ranked on the SIGN of a correlation between volume change and return (at 20
and 120 days) and found it statistically indistinguishable from a coin flip in both windows: every
blind draw in both methods cleared the luck bar that the signal arm missed. This is a different
cut on the same raw ingredients (daily price and volume), not another window length on the same
statistic. For each screened member, as of the decision date: today's volume relative to its own
trailing 20-day average (the "surprise", log of the ratio, negative when volume is unusually
light, positive when unusually heavy) times the size of that day's price move (the absolute daily
return, direction discarded). The most negative product is a big move on unusually light volume —
an information vacuum or "air pocket" — the most positive is a big move that heavy volume
confirmed. Because M0461/M0467 showed this family's blind draws can themselves span several
points a year, this method registers four draws (not two) from the start, per the hypothesis as
reserved.

Frame is M0461/M0467's: point-in-time members, the F4 screen, 20 equal slots, monthly, fractional
shares at Gotrade's real fees, SPY's 200-day switch on every arm — M0461 already measured that
switch's cost on this exact chassis (about 1 point a year, worst fall cut from 64% to 24%), so it
is not re-measured here, same choice M0467 made. Names with a missing bar, non-positive price or
volume, or fewer than 21 bars of history on the decision date are not scored, in every arm alike.

Arms (six): NEG holds the 20 most negative surprise-times-move products (the air-pocket long leg),
POS the 20 most positive (the mirror, heavy-volume-confirmed moves), R1-R4 draw 20 of the same
pool by hash (seeds 591001-591004, new draws, not a repeat of M0461's or M0467's).
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)
MODES = ("neg", "pos", "blind")
WIN = 20  # trailing sessions the volume average is measured over
MARKET = "SPY"


@dataclass(frozen=True, slots=True)
class VSMParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "neg"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> VSMParams:
    if not isinstance(params, VSMParams):
        raise TypeError(f"params must be VSMParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Log(today's volume / its trailing WIN-day average) times the day's absolute return.

    Needs WIN + 1 bars ending on data_date (WIN trailing volume bars plus today's). Names with a
    missing bar, non-positive price or non-positive volume anywhere in the window are not
    scored."""
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        c = h.close[i - 1 : i + 1]
        v_trail = h.volume[i - WIN : i]
        v_today = h.volume[i]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)
                and np.all(np.isfinite(v_trail)) and np.all(v_trail > 0.0)
                and np.isfinite(v_today) and v_today > 0.0):
            continue
        trail_mean = float(np.mean(v_trail))
        if trail_mean <= 0.0:
            continue
        move = abs(float(c[1] / c[0] - 1.0))
        vol_ratio = float(v_today) / trail_mean
        out[s] = math.log(vol_ratio) * move
    return out


def choose(rows: list[FactorRow], score: dict[str, float], params: VSMParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "neg":
        key = {r.symbol: score[r.symbol] for r in pool}
    elif params.mode == "pos":
        key = {r.symbol: -score[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class VSMPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class VSMAllocator:
    """The lab's index-member book ranked on volume surprise scaled by the day's move size."""

    id = "M0591"

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

    def _run(self, prepared: VSMPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: VSMParams) -> tuple[Target, ...]:
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

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> VSMPrepared:
        return VSMPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, VSMPrepared):
            raise TypeError(f"prepared must be VSMPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


VSM = VSMAllocator()


def _v(suffix: str, params: VSMParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0591-{suffix}", family="M0591",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=VSM, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0591",
    name="Volume surprise sized by the move: rank on volume change scaled by return magnitude, "
         "not its sign",
    family="stock-volume-surprise",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "M0461 and M0467 both show that the SIGN of the volume/return relationship (positive or "
        "negative correlation, at 20 or 120 days) carries no information once measured against "
        "several blind draws of the same size. A different cut on the same raw ingredients may "
        "still have content: rank names by trading volume's surprise (today's volume relative to "
        "its own trailing 20-day average, in logs) scaled by the size of the day's price move, on "
        "the theory that a large price move on unusually light volume is a stronger signal (an "
        "information vacuum, or an air pocket) than the same move on heavy volume, regardless of "
        "which direction either one is pointing. Rank the F4-screened point-in-time index members "
        "by that product, hold 20 equal slots, monthly, fractional shares at Gotrade's real fees, "
        "behind SPY's 200-day switch (not re-measured here; M0461 already priced it on this "
        "chassis at about 1 point a year). Arms: NEG (most negative product, the air-pocket long "
        "leg), POS (most positive, the mirror: heavy volume confirming a big move), R1-R4 (four "
        "hash draws of 20 from the same pool, seeds 591001-591004). This is a magnitude-based cut, "
        "not a sign-based one, so it does not inherit M0461/M0467's two null results outright. "
        "SUCCESS: NEG beats the best of R1-R4 by more than the full R1-R4 spread, POS loses to "
        "the blind draws, with a positive 2009-2015 edge vs SPY. Predictions, written now: a "
        "single day's volume-and-move snapshot is noisier than a 20- or 120-day correlation, so "
        "the R1-R4 spread is wider than either prior method's, and NEG falls inside it rather "
        "than clearing it."
    ),
    expected_failure=(
        "The statistic is a single day's volume ratio times a single day's move, read once a "
        "month: far noisier than M0461's 20-day correlation or M0467's 120-day one, both of which "
        "already failed to clear their own blind-draw spread. Given how easily this family's "
        "signals turn out to be the same size as sampling noise, the more likely outcome is that "
        "NEG falls inside the R1-R4 spread, repeating the null result a third time under a new "
        "name. A published or well-known liquidity-vacuum effect, if real, is also likely to have "
        "faded by the dev window's end."
    ),
    candidates=(
        _v("NEG", VSMParams(N20, "neg"),
           "Most negative volume-surprise-times-move product: big move on light volume, the "
           "air-pocket long leg, behind the switch"),
        _v("POS", VSMParams(N20, "pos"),
           "Most positive product: big move confirmed by heavy volume, the reversed arm"),
        _v("R1", VSMParams(N20, "blind", 591001),
           "Control: hash draw of 20 from the same pool, seed 591001, behind the switch"),
        _v("R2", VSMParams(N20, "blind", 591002),
           "Control: hash draw of 20 from the same pool, seed 591002, behind the switch"),
        _v("R3", VSMParams(N20, "blind", 591003),
           "Control: hash draw of 20 from the same pool, seed 591003, behind the switch"),
        _v("R4", VSMParams(N20, "blind", 591004),
           "Control: hash draw of 20 from the same pool, seed 591004, behind the switch"),
    ),
    seen_keys=(
        "concept:volume-surprise-magnitude-scaled-sign-agnostic",
    ),
)
