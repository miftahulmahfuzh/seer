"""M0448 — Far above the yearly low: index members that have run furthest from their 52-week low.

Source: Bhootra and Hur (2013), "The timing of 52-week high price and momentum" and the wider
52-week anchoring literature (George and Hwang 2004 for the high; Bhootra and Hur for a separate
role of the low). Published 2004-2013, so the dev window (to 2015) holds almost none of the years
after the crowd found it, and any edge is likely to have faded since.

The lab has tested the 52-week HIGH (M0015, M0232) but never the LOW anchor. The key here is the
latest close divided by the lowest close of the last 252 bars (today's bar included). Closes are
used, not the daily low column, because the closes are the series the lab back-adjusts and
trusts everywhere else; a one-bar bad low print cannot then set the anchor.

The frame is M0438's, whose allocator machinery is reused: point-in-time members, the F4 screen,
20 equal slots, monthly, fractional shares at Gotrade's real fees, SPY's 200-day switch on four
arms. The pool is every screened member. Names with fewer than 253 bars, a missing bar on the
decision day or a non-positive price in the window are not scored, in every arm alike.

Arms (six, the lab's cap): FAR holds the 20 highest close-over-low ratios (the treatment); NEAR
the 20 lowest (the reversed rung); MOM the 20 highest 12-1 returns (close 21 bars ago over close
252 bars ago), the control that says whether the low anchor is only momentum renamed; R1 a hash
draw of 20 from the same pool, behind the switch; FAR-NOSW and R1-NOSW the same two with no switch.
R1-NOSW is the always-invested arm with no opinion in it, so the lab can price what the switch and
the sort each add (the dressing question). The rank overlap of FAR and MOM is read after the run
by a report-only script, not by an arm.
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

ADDED = date(2026, 11, 1)
MODES = ("far", "near", "mom", "blind")
WIN = 252  # bars in the low window (and the momentum formation window)
SKIP = 21  # bars skipped at the recent end of the 12-1 momentum control
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class LowParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "far"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "skip": str(SKIP)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LowParams:
    if not isinstance(params, LowParams):
        raise TypeError(f"params must be LowParams, got {type(params).__name__}")
    return params


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, tuple[float, float]]:
    """(close / lowest close of the last WIN bars, 12-1 return) per name on data_date.

    Needs WIN + 1 closes ending on data_date; names with a missing bar or a non-positive price
    in that span are not scored."""
    out: dict[str, tuple[float, float]] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        c = h.close[i - WIN : i + 1]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)):
            continue
        low = float(c[1:].min())  # lowest of the last WIN closes, today's included
        out[s] = (float(c[-1]) / low, float(c[-1 - SKIP] / c[0] - 1.0))
    return out


def choose(rows: list[FactorRow], score: dict[str, tuple[float, float]], params: LowParams
           ) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in score]
    if params.mode == "far":
        key = {r.symbol: -score[r.symbol][0] for r in pool}
    elif params.mode == "near":
        key = {r.symbol: score[r.symbol][0] for r in pool}
    elif params.mode == "mom":
        key = {r.symbol: -score[r.symbol][1] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class LowPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, tuple[float, float]]] = field(default_factory=dict, repr=False)


class LowAnchorAllocator:
    """The lab's index-member book ranked on distance above the 52-week low."""

    id = "M0448"

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

    def _run(self, prepared: LowPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: LowParams) -> tuple[Target, ...]:
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

    def prepare(self, history: Mapping[str, History]) -> LowPrepared:
        return LowPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LowPrepared):
            raise TypeError(f"prepared must be LowPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


LOWANCHOR = LowAnchorAllocator()


def _v(suffix: str, params: LowParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0448-{suffix}", family="M0448",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=LOWANCHOR, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0448",
    name="Far above the yearly low: stocks that have run furthest from their 52-week low",
    family="stock-52week-low-anchor",
    source_kind="paper",
    source_ref="Bhootra & Hur 2013 (52-week-low anchoring); Sera 2026-11-01 web search on daily-price anomalies",
    parent_id=None,
    hypothesis=(
        "Investors anchor on a stock's 52-week low as well as its high, and stocks trading far "
        "above their yearly low keep outperforming those hugging it, partly apart from 12-1 "
        "momentum (Bhootra and Hur 2013; the high-side anchor is George and Hwang 2004). Rank the "
        "F4-screened point-in-time index members by latest close over the lowest close of the "
        "last 252 bars, hold the top 20 monthly in equal fractional slots at Gotrade's real "
        "fees, behind SPY's 200-day switch. Arms: FAR (the treatment), NEAR (the reversed rung: "
        "closest to the low), MOM (plain 12-1 momentum, the control that says whether the low "
        "anchor adds anything), R1 (hash draw of 20 from the same pool, the blind control), "
        "FAR-NOSW and R1-NOSW (no switch; R1-NOSW is always invested with no opinion, the third "
        "arm that prices the switch and acting). SUCCESS: FAR beats R1 by more than 2 points a "
        "year, NEAR loses to R1, FAR beats MOM, with a positive 2009-2015 edge vs SPY. "
        "Predictions, written now: FAR and MOM land within 2 points a year of each other (the "
        "ratio mostly restates trailing return), neither beats SPY in 2009-2015, NEAR trails R1, "
        "and the always-invested arms fall past 35% in 2008-09."
    ),
    expected_failure=(
        "Price over its 252-day low is mostly a restatement of trailing return, so FAR may be "
        "plain momentum under another name: the MOM control and a post-run rank-overlap read are "
        "there to say so. Large index members that doubled off the 2009 low dominate the early "
        "years, which are the lowest-coverage ones. Published 2004-2013, so any dev edge is "
        "likely to fade out of sample, and every 12-1 style book so far lagged SPY after 2009."
    ),
    candidates=(
        _v("FAR", LowParams(N20, "far"),
           "Highest close over 252-bar low among screened members, behind the switch"),
        _v("NEAR", LowParams(N20, "near"),
           "Lowest close over 252-bar low: the reversed rung"),
        _v("MOM", LowParams(N20, "mom"),
           "Control: plain 12-1 momentum on the same pool, behind the switch"),
        _v("R1", LowParams(N20, "blind", 448),
           "Control: hash draw of 20 from the same pool, seed 448, behind the switch"),
        _v("FAR-NOSW", LowParams(NOSW, "far"),
           "No-switch twin of FAR: always invested, prices the switch's habit"),
        _v("R1-NOSW", LowParams(NOSW, "blind", 448),
           "Always invested, no opinion: blind draw with no switch, prices acting on either"),
    ),
    seen_keys=(
        "concept:52-week-low-anchor-distance-above-low",
    ),
)
