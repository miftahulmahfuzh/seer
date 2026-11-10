"""M0534 — M0530's leverage-effect rank, picked evenly across volatility thirds.

Variation of M0530. M0530 ranked index members by corr(daily return, next-day change in Parkinson
range volatility) and held the 20 most negative. Its treatment missed the luck bar, its mirror won,
and the analysis suspected the score was a high-volatility proxy: a stock whose range swells on a
down day is usually a stock whose range is wide anyway.

This method takes the volatility level out of the pick. Each month the scored members are split
into thirds by their own mean Parkinson volatility over the same 252 bars, and the book takes the
best-ranked names from each third in turn (7, 7, 6 for a 20-name book), so it holds the same
volatility mix as the pool whichever side it ranks on. The store has no industry codes, so the
"industry-neutral" wording of the idea row is replaced by volatility neutrality, the confound the
parent actually named.

The control draw is shaped like the treatment: the same thirds, the same keep band, and a hash
whose salt changes once a quarter, so it turns over at roughly the treatment's pace instead of
M0530-RAND-T's monthly re-draw (3.8 times the trades). Two seeds, so the yardstick has a width of
two rather than one. Reads only bars dated <= d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0353_daily_return_profile import ProfilePrepared
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 10)

Side = Literal["negative", "positive"]
_SIDES: tuple[str, ...] = ("negative", "positive")
W = 252
MIN_BARS = 200
KEEP_BAND = 10
CLIP = 0.5
BINS = 3
_PARK = 1.0 / (2.0 * np.sqrt(np.log(2.0)))


@dataclass(frozen=True, slots=True)
class VnParams:
    """``inner`` is F4's screen, trend gate and book size; ``side`` picks the most negative or most
    positive return/volatility correlation; ``draw`` > 0 swaps the score for a quarterly hash draw
    seeded by that number."""

    inner: FactorParams
    side: Side = "negative"
    draw: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")
        if self.draw < 0:
            raise ValueError(f"draw must be >= 0, got {self.draw}")

    def as_dict(self) -> dict[str, str]:
        out = {"side": self.side, "draw": str(self.draw)}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> VnParams:
    if not isinstance(params, VnParams):
        raise TypeError(f"params must be VnParams, got {type(params).__name__}")
    return params


def _score(h: History, data_date: date, p: VnParams) -> tuple[float, float] | None:
    """(ranking score, mean Parkinson volatility) over the last ``W`` bars, or None."""
    i = h.index_of(data_date)
    if i is None or i < W + 1:
        return None
    c = h.close[i - W : i + 1]
    hi = h.high[i - W : i + 1]
    lo = h.low[i - W : i + 1]
    if not (np.all(np.isfinite(c)) and np.all(c > 0.0) and np.all(np.isfinite(hi))
            and np.all(np.isfinite(lo)) and np.all(lo > 0.0) and np.all(hi >= lo)):
        return None
    pv = np.log(hi / lo) * _PARK
    level = float(np.mean(pv))
    if p.draw:
        q = (data_date.month - 1) // 3
        salt = f"{h.symbol}|{p.draw}|{data_date.year}Q{q}"
        digest = hashlib.sha256(salt.encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2.0**64, level
    r = np.clip(np.log(c[1:] / c[:-1]), -CLIP, CLIP)  # r[k] is the return on bar k+1
    dv = pv[2:] - pv[1:-1]  # change from bar k+1 to bar k+2
    r = r[:-1]
    if len(r) < MIN_BARS or float(np.std(r)) == 0.0 or float(np.std(dv)) == 0.0:
        return None
    return float(np.corrcoef(r, dv)[0, 1]), level


def _interleave(kept: list[tuple[FactorRow, float, float]], p: VnParams) -> list[FactorRow]:
    """Rank within each volatility third, then deal the thirds out in turn, so any prefix of the
    result holds the thirds as evenly as its length allows."""
    by_level = sorted(kept, key=lambda t: (t[2], t[0].symbol))
    n = len(by_level)
    sign = 1.0 if p.side == "negative" else -1.0
    bins: list[list[FactorRow]] = []
    for b in range(BINS):
        part = by_level[b * n // BINS : (b + 1) * n // BINS]
        part.sort(key=lambda t: (sign * t[1], t[0].symbol))
        bins.append([t[0] for t in part])
    out: list[FactorRow] = []
    for k in range(max((len(b) for b in bins), default=0)):
        for b in bins:
            if k < len(b):
                out.append(b[k])
    return out


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           held: frozenset[str], p: VnParams) -> list[FactorRow]:
    kept: list[tuple[FactorRow, float, float]] = []
    for r in rows:
        h = history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None:
            continue
        s = _score(h, data_date, p)
        if s is not None and np.isfinite(s[0]) and np.isfinite(s[1]):
            kept.append((r, s[0], s[1]))
    ranked = _interleave(kept, p)
    top = p.inner.top
    keep = [r for r in ranked[: top + KEEP_BAND] if r.symbol in held][:top]
    have = {r.symbol for r in keep}
    for r in ranked:
        if len(keep) >= top:
            break
        if r.symbol not in have:
            keep.append(r)
            have.add(r.symbol)
    return keep


class VolNeutralLeverageAllocator:
    """M0530's score ranked within volatility thirds and dealt out evenly."""

    id = "M0534"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), W + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> ProfilePrepared:
        return ProfilePrepared(history, prepare_factor(history))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return targets_from_rows(choose(rows, history, data_date, held, p), p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ProfilePrepared):
            raise TypeError(f"prepared must be ProfilePrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared.history, data_date, held, p), p)


VNLEV = VolNeutralLeverageAllocator()


def _v(suffix: str, params: VnParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0534-{suffix}", family="M0534", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=VNLEV, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0534",
    name="Leverage effect within an industry-neutral rank: does the return-volatility link beat luck once high-volatility names are removed?",
    family="stock-leverage-effect",
    source_kind="variation",
    parent_id="M0530",
    source_ref="Variation of M0530 (Doshi et al. 2026, The leverage effect in the cross-section)",
    hypothesis=(
        "M0530's score may be a high-volatility proxy. Same score (252-session correlation of "
        "daily log return with the next-day change in Parkinson range volatility), but each month "
        "the scored F4-screened point-in-time members are split into thirds by their own mean "
        "Parkinson volatility and the 20-name book is dealt evenly from the thirds (7/7/6), so "
        "the volatility mix is the pool's whatever the side. Behind SPY's 200-day switch, monthly, "
        "keep band top 30, fractional shares at Gotrade's real fees on the owner's top-up "
        "(MONTHLY_HOLD_FRAC_GOTRADE). Assumption written now: the store has no industry codes, so "
        "the idea row's 'industry-neutral' is replaced by volatility neutrality, the confound "
        "M0530's analysis named. Arms: NEG-T-VN (treatment); POS-T-VN (mirror: must trail); "
        "NEG-VN (always invested, no switch: the no-opinion arm that prices the habit); "
        "DRAW1-T-VN and DRAW2-T-VN (Control: hash draws on the same thirds, band and switch, "
        "salt changed quarterly so turnover sits near the treatment's ~4 a year rather than "
        "M0530-RAND-T's monthly re-draw; two seeds, so a width of two, still not a full error "
        "bar against the lab's 7.5-point draw spread). Published 2026, after the dev window; "
        "judge 2009-2015 first. To count, NEG-T-VN must beat SPY TR within the 20% screen, beat "
        "both draws, beat its mirror, and be positive in 2009-2015. Parent numbers to beat: "
        "M0530-NEG-T +9.2% a year funded vs SPY +7.2%, DSR 0.840, 1 of 4 folds."
    ),
    expected_failure=(
        "Taking volatility out leaves nothing: the treatment lands between the two draws, the "
        "mirror again does as well or better, and the switch carries all the safety. Neutralising "
        "also drags the book toward low-volatility names that lagged in the late 1990s, so the "
        "whole-window lead over SPY shrinks below M0530-NEG-T's, and 2009-2015 still trails SPY."
    ),
    candidates=(
        _v("NEG-T-VN", VnParams(N20, "negative"),
           "Most negative return/volatility-change correlation, dealt evenly from volatility thirds, behind the switch: the treatment"),
        _v("POS-T-VN", VnParams(N20, "positive"),
           "Mirror, most positive, same thirds: must trail if the statistic carries information beyond volatility"),
        _v("NEG-VN", VnParams(N20_NOTREND, "negative"),
           "Always invested, no switch: the no-opinion arm that prices the switch and its churn"),
        _v("DRAW1-T-VN", VnParams(N20, "negative", 1),
           "Control: quarterly hash draw, seed 1, same thirds, band and switch"),
        _v("DRAW2-T-VN", VnParams(N20, "negative", 2),
           "Control: quarterly hash draw, seed 2, same thirds, band and switch"),
    ),
    seen_keys=(
        "concept:leverage-effect-volatility-neutral",
        "concept:rank-within-volatility-terciles",
    ),
)
