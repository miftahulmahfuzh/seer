"""M0356 — The daily-return score with weights learned before the dev window and frozen.

Source: variation of M0353, which tested the *idea* of the Cakici, Fieberg, Neszveda, Bianchi
and Zaremba paper (January 2026, SSRN 6005614) with a fixed, hand-chosen blend and could not
test the paper's actual claim. The paper's estimator is an elastic net on the previous month's
21 daily returns, entered twice -- in calendar order and sorted by size -- refit yearly against
next month's return. M0353 replaced that with a guessed 50/50 blend of a decay-weighted sum and
the mean of the five largest days, and the result tied a pseudo-random pick (+7.5% a year on the
owner's deposits against +7.1% for the random arm and +7.2% for SPY, DSR 0.862). Its own verdict
named the honest next step: learn the weights where learning them is allowed, and freeze them.

**How the weights were learned, and why this is out of sample.** The lab's allocator contract
gives every method a bounded lookback, so a model refit inside the window cannot run. The lab's
scored dev window, for any method that reads index members, opens at ``MEMBERSHIP_START`` =
1996-01-02 (``backtest/dev.py``): that is the first row of the point-in-time membership file and
no earlier session is ever scored. The dev store's bars, however, start 1993-01-29. That gap --
1993-01-29 to 1995-12-29, three years of prices that the dev window never scores -- is the only
place in this lab where a model may be fitted without peeking. ``COEF`` below was fitted there,
offline, once, and written in as constants. Nothing dated 1996-01-02 or later entered the fit.

The fit, in full, so it can be repeated:

- Universe: the 487 symbols the membership file lists as S&P 500 or Nasdaq-100 members on
  1996-01-02. There is no point-in-time membership before that date, so this one snapshot --
  taken two sessions after the training data ends -- stands in for it. It decides *which names*
  are trained on, never any return; a company in the index on 1996-01-02 was a large cap through
  1993-1995, so the look-ahead this buys is small and is written down here rather than hidden.
- Screen: close >= $5 on the observation day. F4's 20-million-dollar volume bar was deliberately
  **not** applied to the fit. It is a nominal number that was never adjusted for inflation or for
  the growth of market turnover: in 1994 it admits about 50 names a month, in 2010 several
  hundred. Matching the nominal screen would have matched the wrong economic universe and left
  1,812 training rows; dropping it leaves 5,298 across about 160 names a month.
- Observations: the last session of each month, 1993-03-31 through 1995-11-30, non-overlapping.
  33 monthly cross-sections. Inputs are the same 42 numbers M0353 scores on (``_features``,
  imported below so the two can never drift): the 21 daily returns through the observation day
  clipped to +/-50%, in calendar order, then the same 21 sorted ascending. Target is the return
  to the next month-end less that month's cross-section mean.
- Estimator: scikit-learn ``ElasticNet`` on features standardised by their pooled training
  standard deviation, at ``l1_ratio=0.5`` and ``alpha=1e-4``; the fitted coefficients are divided
  back by those standard deviations so ``COEF`` applies to raw clipped returns. The intercept is
  dropped: the book ranks within one day's cross-section, and a constant cannot change a ranking.

**The fit found nothing, and that is pre-registered here before any dev number exists.** Choosing
the penalty honestly -- five-fold cross-validation grouped by month, so a fold never splits one
cross-section -- selects the empty model: at the cross-validated optimum
(``l1_ratio=0.1, alpha=0.0464``) all 42 coefficients are zero and the cross-validated R-squared is
+0.00003, which is the R-squared of predicting the mean. Every other pipeline tried inside the
training window agrees: raw or cross-sectionally standardised inputs, raw-demeaned or
rank-transformed targets, penalties from 3e-4 to 3e-2, the cross-validated R-squared never leaves
the band -0.0086 to +0.0006, and every positive value sits at a penalty strong enough to have
shrunk the model to nothing. On 1993-1995 large caps these 42 features carry no learnable
cross-sectional signal at all.

``COEF`` is therefore the **forced** fit, not the honest one: the least-shrunk setting on the
grid that was examined, run anyway so the question gets a curve instead of an argument. Its own
grouped cross-validated R-squared inside the training window is **-0.0063** -- worse than
predicting the mean. 40 of its 42 coefficients are non-zero. One block of it is recognisable:
the three most recent days carry the three largest negative chronological weights (-0.140,
-0.169, -0.215, oldest to newest), which is short-term reversal, learned rather than assumed, in
the published direction. The sorted block oscillates hard (+1.73, -2.04, ..., +0.94, -1.51)
between adjacent order statistics that differ by almost nothing, which is what fitting noise
looks like. So this method asks one question and expects one answer: a score whose weights were
genuinely learned out of sample, and which cross-validation says is empty, should tie a coin.
If it does, the family closes.

Frame is M0353's, unchanged, so the two are comparable arm for arm: F4's point-in-time members
with the $5 and 20-million-dollar screen, 20 names equally weighted, the SPY 200-day trend
switch, monthly, fractional shares at Gotrade's real fees. Bars are split- and
dividend-adjusted. Reads only bars dated <= d.

**The arms are the full three-by-three-halves grid M0353 was missing.** ``lab dressing`` scored
M0353 unpriced because its no-switch arm still carried an opinion, so the cost of the habit could
not be separated from the worth of the signal. Here every ranking runs with the switch on and
with it off: the book, its mirror, and a pseudo-random pick, six arms, no method id spent on the
second half. The random arm uses M0353's hash formula verbatim, so its two arms also re-measure
that method's draw-noise yardstick on a second allocator id.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows

# _features and its two constants are imported, not copied: COEF's meaning is tied to the exact
# 42 numbers it was fitted on, and a second copy of a four-line formula is a way for the frozen
# weights and the features they weight to drift apart without anything going red.
from seer_engine.lab.methods.m0353_daily_return_profile import CLIP, W, _features
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

ADDED = date(2026, 10, 26)

# Fitted 1993-01-29 .. 1995-12-29, frozen 2026-10-26. The first 21 weight the daily returns in
# calendar order, oldest first; the last 21 weight the same returns sorted ascending. Applied to
# returns already clipped to +/- CLIP. See the module docstring for the whole recipe.
COEF: tuple[float, ...] = (
    -0.05787321, -0.04726552, -0.00000000, +0.00883249, +0.08583864, -0.04445772,
    -0.12397588, +0.08254864, +0.01591780, +0.07043045, -0.14911362, +0.00358158,
    +0.13980040, +0.12670811, -0.01745413, +0.07009695, +0.04558331, -0.08105793,
    -0.14042487, -0.16880886, -0.21503780, -0.08890888, -0.13108611, +0.06631286,
    -0.00000000, +0.03306523, +1.73463108, -2.03934451, -0.01735727, +0.68193678,
    +0.30565631, -0.60543101, -0.23884286, +0.93860420, -1.50929363, +0.43409882,
    -0.11260635, -0.38817712, +0.31519721, +0.28686014, -0.12529191, +0.02824917,
)
_W = np.asarray(COEF, dtype=float)

Score = Literal["dri", "random"]
Side = Literal["high", "low"]
_SCORES: tuple[str, ...] = ("dri", "random")
_SIDES: tuple[str, ...] = ("high", "low")


@dataclass(frozen=True, slots=True)
class FrozenParams:
    """``inner`` is F4's screen, trend gate and book size; ``score`` and ``side`` pick the ranking."""

    inner: FactorParams
    score: Score = "dri"
    side: Side = "high"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.score not in _SCORES:
            raise ValueError(f"score must be one of {_SCORES}, got {self.score!r}")
        if self.side not in _SIDES:
            raise ValueError(f"side must be one of {_SIDES}, got {self.side!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"score": self.score, "side": self.side}
        for key, v in self.inner.as_dict().items():
            out[f"inner.{key}"] = v
        return out


def _check(params: object) -> FrozenParams:
    if not isinstance(params, FrozenParams):
        raise TypeError(f"params must be FrozenParams, got {type(params).__name__}")
    return params


def frozen_lookback(params: FrozenParams) -> int:
    return max(factor_lookback(params.inner), W + 1)


def _score(h: History, data_date: date, score: str) -> float | None:
    """The frozen predicted excess return, or the pseudo-random yardstick; None when unusable."""
    i = h.index_of(data_date)
    if i is None or i < W:
        return None
    x = _features(h.close[i - W : i + 1])
    if x is None:
        return None
    if score == "dri":
        return float(np.dot(_W, x))
    import hashlib  # noqa: PLC0415 -- M0353's formula verbatim, so the two draws coincide

    digest = hashlib.sha256(f"{h.symbol}|{data_date.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2.0**64


@dataclass
class FrozenPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


def choose(rows: list[FactorRow], prepared: FrozenPrepared, data_date: date,
           p: FrozenParams) -> list[FactorRow]:
    kept: list[tuple[FactorRow, float]] = []
    for r in rows:
        h = prepared.history.get(r.symbol)
        if r.symbol in EXCLUDED or h is None:
            continue
        s = _score(h, data_date, p.score)
        if s is not None:
            kept.append((r, s))
    if not kept:
        return []
    sign = -1.0 if p.side == "high" else 1.0
    order = sorted(range(len(kept)), key=lambda k: (sign * kept[k][1], kept[k][0].symbol))
    return [kept[k][0] for k in order[: p.inner.top]]


class FrozenAllocator:
    """F4's book ranked on a score whose weights were fitted on 1993-1995 and frozen.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0356"

    def lookback(self, params: Any) -> int:
        return frozen_lookback(_check(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.inner.trend[0],) if p.inner.trend is not None else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def prepare(self, history: Mapping[str, History]) -> FrozenPrepared:
        return FrozenPrepared(history, prepare_factor(history))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        prepared = FrozenPrepared(history, prepare_factor(history))
        return targets_from_rows(choose(rows, prepared, data_date, p), p)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, FrozenPrepared):
            raise TypeError(f"prepared must be FrozenPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return targets_from_rows(choose(rows, prepared, data_date, p), p)


FROZEN = FrozenAllocator()


def _v(suffix: str, params: FrozenParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0356-{suffix}", family="M0356", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=FROZEN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0356",
    name=("Daily-return score with weights learned before 1996 and frozen: the paper's own "
          "estimator, fitted where the lab allows it and never refitted"),
    family="stock-daily-return-profile",
    source_kind="variation",
    source_ref="M0353 (its verdict named this as the honest next step)",
    parent_id="M0353",
    hypothesis=(
        "M0353 tested the idea of the Cakici-Fieberg-Neszveda-Bianchi-Zaremba daily-return "
        "framework with a hand-chosen 50/50 blend and tied a pseudo-random pick (+7.5% a year on "
        "the owner's deposits against +7.1% random and +7.2% SPY, DSR 0.862, fell 32%). It never "
        "touched the paper's real claim, which is that an elastic net learns how to weigh the 21 "
        "daily returns, in calendar order and sorted by size, against next month's return. This "
        "method supplies that. The dev window for a member-reading method opens at "
        "MEMBERSHIP_START = 1996-01-02, while the dev store's bars begin 1993-01-29, so the "
        "elastic net was fitted offline on 1993-03-31 .. 1995-11-30 only -- 33 non-overlapping "
        "monthly cross-sections, 5,298 rows, about 160 names a month, index members as of "
        "1996-01-02 priced at $5 or more, target the next month's return less the cross-section "
        "mean -- and its 42 coefficients are frozen into the file as constants. Nothing dated "
        "1996-01-02 or later entered the fit. "
        "Pre-registered before any dev number: the honest fit is EMPTY. Five-fold "
        "cross-validation grouped by month selects l1_ratio 0.1 and alpha 0.0464, at which all 42 "
        "coefficients are zero and the cross-validated R-squared is +0.00003; across raw and "
        "cross-sectionally standardised inputs, raw and rank-transformed targets, and penalties "
        "from 3e-4 to 3e-2, the cross-validated R-squared never leaves -0.0086 to +0.0006. COEF "
        "is therefore the forced, least-shrunk fit on the grid (l1_ratio 0.5, alpha 1e-4, 40 of "
        "42 coefficients non-zero, grouped cross-validated R-squared -0.0063), run so the "
        "question gets a curve rather than an argument. Its one recognisable feature is that the "
        "three most recent days carry the three largest negative chronological weights, which is "
        "short-term reversal in the published direction, learned rather than assumed. "
        "The book holds the 20 HIGHEST predicted excess returns among F4-screened point-in-time "
        "index members at 5% each, behind the SPY 200-day switch, monthly, fractional shares at "
        "Gotrade's real fees -- M0353's chassis unchanged, so the two methods compare arm for "
        "arm. Six arms are the full grid M0353 lacked: three rankings (the book, its mirror, a "
        "pseudo-random pick on M0353's own hash) times the switch on and off, so the worth of the "
        "signal and the cost of the habit are separable, which lab dressing could not do for the "
        "parent. To count, the book must beat SPY TR on dev within the 20% limit, clear the luck "
        "bar, beat both random arms by more than the lab's measured draw noise, trail its mirror, "
        "and be positive in 2009-2015."
    ),
    expected_failure=(
        "The fit says there is nothing to learn, so the most likely outcome is that the book "
        "lands within draw noise of its own random arms, exactly as the parent's fixed blend did, "
        "and the family closes. Three years and 33 monthly cross-sections of large caps are far "
        "too little to estimate 42 weights: the sorted block of COEF swings between +1.73 and "
        "-2.03 on adjacent order statistics that differ by almost nothing, which is fitted noise, "
        "and a score dominated by it should rank close to randomly twenty years later. The part "
        "that is not noise is short-term reversal, which this lab has already seen tie SPY at "
        "best (M0028 at +7.5% on deposits and a 27% fall; M0353's plain reversal arm was its "
        "worst at +3.2%), so even the signal that did survive the fit points at a known "
        "disappointment. The 1993-1995 training universe is also survivorship-flavoured -- it is "
        "the names that were index members on 1996-01-02 -- so any weight the fit put on "
        "surviving-company behaviour is borrowed, not earned. Expect the switch, not the score, "
        "to explain most of the difference between the gate-on and gate-off halves, a worst fall "
        "above 20% on the gated arms and near 60% on the ungated ones as in the parent, and the "
        "luck bar to be missed at N in the mid-200s."
    ),
    candidates=(
        _v("DRI-HI-N20-T", FrozenParams(N20, "dri", "high"),
           "Highest frozen predicted return, behind the switch: the book"),
        _v("DRI-LO-N20-T", FrozenParams(N20, "dri", "low"),
           "Lowest frozen predicted return, behind the switch: the mirror, expected to trail"),
        _v("RAND-N20-T", FrozenParams(N20, "random", "low"),
           "M0353's pseudo-random 20 behind the switch: the draw-noise yardstick"),
        _v("DRI-HI-N20", FrozenParams(N20_NOTREND, "dri", "high"),
           "The book always invested: with the mirror and random twins, prices the switch"),
        _v("DRI-LO-N20", FrozenParams(N20_NOTREND, "dri", "low"),
           "The mirror always invested: completes the signal-by-habit square"),
        _v("RAND-N20", FrozenParams(N20_NOTREND, "random", "low"),
           "The pseudo-random 20 always invested: the opinion-free arm that prices the habit"),
    ),
    seen_keys=(
        "concept:daily-return-profile",
        "concept:frozen-learned-weights",
        "concept:pre-window-model-fit",
    ),
)
