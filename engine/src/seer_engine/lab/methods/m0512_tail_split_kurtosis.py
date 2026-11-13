"""M0512 — Which tail is fat: stocks with big up days versus stocks with big down days.

Source: variation on M0510 (Amaya, Christoffersen, Jacobs & Vasquez 2015, JFE). M0510 scored
each name by one number, excess kurtosis of its last 126 daily returns, and found the mirror of
its treatment (HIGHK, the fattest-tail book) reached dev MAR 0.40 / DSR 0.919 but won only 1 of 4
walk-forward folds with the pick changing fold to fold: a selection on the dev average, not a
dev-majority edge, and the family has no promoted member yet. Excess kurtosis cannot tell a stock
whose extreme days are upside jumps (a lottery-ticket premium: Bali, Cakici & Whitelaw's MAX
effect is the same shape on the daily max) from a stock whose extreme days are downside breaks
(plausibly just "had a bad recent event" rather than a priced trait). Split the tail: score each
name's last 126 daily returns on upside-tail fatness (mean fourth power of the standardised
returns that landed above their own mean) and downside-tail fatness (the same, for returns below
the mean), separately. Same N20 host as M0510: 20-name, F4-screened, point-in-time index members,
monthly, equal fractional slots at Gotrade real fees, behind SPY's 200-day switch. A name needs
at least 20 above-mean and 20 below-mean returns in the window to be scored on both tails alike;
short of that it is unscored in every arm, same as a gap, a non-positive price or zero volatility.

Arms (six): LOW-UP (avoid the most upside-lottery-like names: lowest 20 by upside-tail fatness —
tests whether a lottery premium is priced at all), LOW-DOWN (avoid the most crash-prone names:
lowest 20 by downside-tail fatness — tests whether M0510's edge was really "avoid names that just
had a bad event"), HIGH-UP (the mirror of LOW-UP: the most lottery-like names, which a real
upside-lottery premium should make underperform), R1 and R2 (blind draws, seeds 512 and 513,
behind the switch — different seeds from M0510's 510/511 so the drawn books are not duplicates of
its already-recorded R1/R2) and R1-NOSW (always invested, no opinion, seed 512: prices the switch
and acting, same convention as M0510's R1-NOSW).
SUCCESS: at least one of LOW-UP/LOW-DOWN beats the better of R1/R2 by more than 2 points a year
funded, HIGH-UP loses to R1, and whichever arm wins keeps a positive edge in 2009-2015.
"""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
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

ADDED = date(2026, 11, 13)
MODES = ("low_up", "high_up", "low_down", "blind")
NEED = 127  # closes needed: 126 returns
MIN_SIDE = 20  # above- or below-mean returns needed to score that tail
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class TimeParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "low_up"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "need": str(NEED)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TimeParams:
    if not isinstance(params, TimeParams):
        raise TypeError(f"params must be TimeParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float, float]]:
    """(upside-tail fatness, downside-tail fatness, daily volatility) of the last 126 returns.

    Each tail score is the mean fourth power of the standardised returns on that side of the
    mean. Unscored on a gap, a non-positive price, zero volatility, or fewer than MIN_SIDE
    returns on either side of the mean."""
    out: dict[str, tuple[float, float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < NEED - 1:
            continue
        c = h.close[i - NEED + 1 : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        sd = float(np.std(r))
        if sd <= 0.0:
            continue
        z = (r - float(np.mean(r))) / sd
        up = z[z > 0.0]
        down = z[z < 0.0]
        if len(up) < MIN_SIDE or len(down) < MIN_SIDE:
            continue
        out[s] = (float(np.mean(up**4)), float(np.mean(down**4)), float(np.std(r, ddof=1)))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float, float]], params: TimeParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    n = params.inner.top
    if params.mode == "low_up":
        key = {r.symbol: (score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "high_up":
        key = {r.symbol: (-score[r.symbol][0], 0.0) for r in pool}
    elif params.mode == "low_down":
        key = {r.symbol: (score[r.symbol][1], 0.0) for r in pool}
    else:
        key = {r.symbol: (float(draw(params.seed, r.symbol)), 0.0) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[:n]


@dataclass
class TimePrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float, float]]] = field(default_factory=dict, repr=False)


class TailSplitAllocator:
    """The lab's index-member book ranked on one side of each stock's return-tail fatness."""

    id = "M0512"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), NEED)

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

    def _run(self, prepared: TimePrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: TimeParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> TimePrepared:
        return TimePrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TimePrepared):
            raise TypeError(f"prepared must be TimePrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


TAILSPLIT = TailSplitAllocator()


def _v(suffix: str, params: TimeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0512-{suffix}", family="M0512",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=TAILSPLIT, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0512",
    name="Which tail is fat: stocks with big up days versus stocks with big down days",
    family="stock-realized-kurtosis",
    source_kind="variation",
    source_ref="M0510 (Amaya, Christoffersen, Jacobs & Vasquez 2015, Does realized skewness and kurtosis predict the cross-section of equity returns?, JFE)",
    parent_id="M0510",
    hypothesis=(
        "M0510 scored each name on one number, excess kurtosis of its last 126 daily returns, and "
        "found its fattest-tail mirror (HIGHK) reached dev MAR 0.40 / DSR 0.919 but won only 1 of "
        "4 walk-forward folds with the pick changing fold to fold: a selection on the dev average, "
        "not a dev-majority edge. Excess kurtosis cannot tell a stock whose extreme days are "
        "upside jumps (a lottery-ticket premium, the same shape as Bali/Cakici/Whitelaw's MAX "
        "effect) from one whose extreme days are downside breaks (plausibly just 'had a bad recent "
        "event'). Split the tail: score the last 126 daily returns on upside-tail fatness (mean "
        "fourth power of standardised returns above their own mean) and downside-tail fatness "
        "(the same, below the mean), separately, in the same N20 frame (F4-screened, point-in-time "
        "index members, 20 equal fractional monthly slots at Gotrade real fees, behind SPY's "
        "200-day switch). A name needs at least 20 returns on each side of the mean to be scored "
        "on either tail; short of that it is unscored in every arm. Arms: LOW-UP (avoid the most "
        "lottery-like names), LOW-DOWN (avoid the most crash-prone names), HIGH-UP (the mirror of "
        "LOW-UP), R1 and R2 (blind draws, seeds 512/513, behind the switch) and R1-NOSW (always "
        "invested, no opinion, seed 512). SUCCESS: at least one of LOW-UP/LOW-DOWN beats the "
        "better of R1/R2 by more than 2 points a year funded, HIGH-UP loses to R1, and the winning "
        "arm keeps a positive edge in 2009-2015. Prediction, written now: if M0510's edge survives "
        "at all it travels with LOW-UP, because a priced lottery premium is the more established "
        "literature result than 'avoid names with recent bad news'; LOW-DOWN is expected to land "
        "within noise of the draws."
    ),
    expected_failure=(
        "A tail score over half a year, even split by sign, is still dominated by one or two "
        "earnings days, so LOW-UP and LOW-DOWN both reduce to 'avoid names with a recent event' "
        "under a different name, and both land within the draws' spread in 2009-2015 as M0510's "
        "own arms and the lab's other lottery and skewness books did. A strong dev result on "
        "either split arm would be expected to fade out of sample, same as M0510's."
    ),
    candidates=(
        _v("LOW-UP", TimeParams(N20, "low_up"), "Lowest 126-session upside-tail fatness: avoid lottery-like names, behind the switch"),
        _v("LOW-DOWN", TimeParams(N20, "low_down"), "Lowest 126-session downside-tail fatness: avoid crash-prone names, behind the switch"),
        _v("HIGH-UP", TimeParams(N20, "high_up"), "Highest upside-tail fatness: the mirror of LOW-UP"),
        _v("R1", TimeParams(N20, "blind", 512), "Control: hash draw of 20, seed 512, behind the switch"),
        _v("R2", TimeParams(N20, "blind", 513), "Control: hash draw of 20, seed 513, measures draw noise"),
        _v("R1-NOSW", TimeParams(NOSW, "blind", 512), "Always invested, no opinion: prices acting on either split"),
    ),
    seen_keys=(
        "concept:realized-kurtosis",
        "concept:tail-split-kurtosis",
    ),
)
