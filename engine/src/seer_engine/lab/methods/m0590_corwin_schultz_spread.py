"""M0590 — Hold the index members with the widest (or narrowest) estimated bid-ask spread.

Source: Corwin & Schultz (2012, JF 67(2)), "A Simple Way to Estimate Bid-Ask Spreads from Daily
High and Low Prices." Their estimator uses only two consecutive days' high/low prices -- no
volume, no quote data -- to back out an implied percentage spread, and later work finds
wider-implied-spread stocks earn a return premium distinct from both Amihud illiquidity (a
volume-scaled price-impact measure) and the daily high-low RANGE already in the lab.

Mechanism, and why it is not a repeat of what the lab already ran. M0348 (dev-eligible, family
stock-price-range-competition) ranks on the mean daily high-low range itself -- a proxy for how
far a stock swings, i.e. its ordinary volatility -- and M0350 found that range adds nothing over
plain close-to-close volatility once matched for it (every ratio arm landed inside its own
volatility-matched control). The Corwin-Schultz estimator does not read range as a swing size; it
reads the RATIO of two days' combined range to each day's own range separately. A stock whose
price travels far intraday but closes near the extreme (high transaction cost, wide quoted
spread) scores high; a stock whose two-day combined range is no wider than either day alone on
its own (the days overlap, no new extreme) scores low, whatever its absolute volatility is. The
two could be highly correlated (both read the same high/low bars) or nearly orthogonal (CS factors
out the volatility level that range measures directly) -- the lab does not know yet, which is the
first thing this run checks. The hypothesized mechanism is also different from M0058's Amihud
illiquidity premium (ILLIQ, rejected: a small-company bet that fell 26% and lost 3 of 4 walk-
forward folds) and from M0497's share-turnover ranking (test-failed in the wrong direction): CS
estimates the SPREAD LEVEL implied by price action alone, where Amihud scales dollar volume by
price impact and turnover scales volume by shares outstanding. All three could still collapse to
the same underlying small/illiquid-company tilt, which is exactly what the size-matched control
below is built to catch.

Estimator. For a trailing window of WIN=21 overlapping two-day pairs (22 bars), each pair t gives
beta_t = ln(H_t/L_t)^2 + ln(H_{t+1}/L_{t+1})^2 (the two days' own ranges, squared log high-low),
gamma_t = ln(max(H_t,H_{t+1}) / min(L_t,L_{t+1}))^2 (the two-day combined range, squared log), and
alpha_t = (sqrt(2*beta_t) - sqrt(beta_t)) / k - sqrt(gamma_t / k) with k = 3 - 2*sqrt(2). The
implied spread is S_t = 2*(exp(alpha_t) - 1) / (1 + exp(alpha_t)), floored at zero per pair (a
negative S_t is the known noise/measurement case the original paper flags, not a usable estimate)
before averaging the 21 pairs into one trailing score per name per month. Names with any
non-finite or zero/crossed high-low bar in the window are not scored, identically in every arm.

Frame: the lab's usual book (M0091/M0348's), point-in-time members, F4's screen, 20 equal slots,
monthly, fractional shares at Gotrade's real fees (``monthly-hold-frac-gotrade``), SPY's 200-day
switch. Company size (point-in-time market value, ``Market.market_value``) is read only for the
size-matched control; market-aware (``market_fields = ("shares",)``), so, by the lab's contract for
market-aware allocators, every arm targets nothing on the history-only path and all five arms run
on the same store and the same code path.

Arms (five of the lab's cap of six): WIDE holds the 20 widest estimated spread (the idea: a
liquidity-risk premium), NARROW the 20 narrowest (the mirror, same costs, opposite opinion),
SM-WIDE a size-matched blind-draw control for WIDE (the pool cut into five market-value quintiles,
drawing as many hash-picked names from each quintile as WIDE holds, so it carries WIDE's size
profile and none of its spread opinion -- this is the check for "is the premium just smallness in
a new coat"), R1 (plain hash order on the same scored pool, behind the switch: the chance-only
yardstick) and R1-NOSW (R1's order, no switch: the always-invested no-opinion arm that prices the
switch's habit apart from any ranking, so WIDE vs NARROW can be split into signal and dressing).
A sixth arm, SM-NARROW, is left for a follow-up if WIDE does not already fail outright: six
arms is the registration cap and SM-WIDE is the more informative single size check, since WIDE
(the premium's predicted winning side) is the arm a promotion would be about.
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

ADDED = date(2026, 11, 12)

MODES = ("wide", "narrow", "sm-wide", "blind")
WIN = 21  # overlapping two-day pairs in the trailing spread estimate (22 bars)
BUCKETS = 5  # market-value quintiles for the size-matched control
MARKET = "SPY"
K = 3.0 - 2.0 * np.sqrt(2.0)  # Corwin & Schultz's constant, 3 - 2*sqrt(2)

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class SpreadParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking
    key. ``seed`` keys the hash draw (``blind`` and ``sm-wide``)."""

    inner: FactorParams
    mode: str = "wide"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "buckets": str(BUCKETS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> SpreadParams:
    if not isinstance(params, SpreadParams):
        raise TypeError(f"params must be SpreadParams, got {type(params).__name__}")
    return params


def corwin_schultz(hi: np.ndarray, lo: np.ndarray) -> float:
    """Mean Corwin-Schultz implied spread over the WIN overlapping two-day pairs in ``hi``/``lo``
    (length WIN + 1, chronological). Each pair's estimate is floored at zero before averaging."""
    beta = np.log(hi[:-1] / lo[:-1]) ** 2 + np.log(hi[1:] / lo[1:]) ** 2
    hmax = np.maximum(hi[:-1], hi[1:])
    lmin = np.minimum(lo[:-1], lo[1:])
    gamma = np.log(hmax / lmin) ** 2
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / K - np.sqrt(gamma / K)
    s = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    return float(np.mean(np.maximum(s, 0.0)))


def scored_names(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Mean estimated Corwin-Schultz spread per scorable name over the last WIN + 1 bars."""
    spread: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        hi = h.high[i - WIN : i + 1]
        lo = h.low[i - WIN : i + 1]
        if not (np.all(np.isfinite(hi)) and np.all(np.isfinite(lo))):
            continue
        if not (np.all(lo > 0.0) and np.all(hi >= lo)):
            continue
        value = corwin_schultz(hi, lo)
        if np.isfinite(value):
            spread[s] = value
    return spread


def choose(rows: list[FactorRow], spread: dict[str, float], size: dict[str, float],
           params: SpreadParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in spread]
    top = params.inner.top
    if params.mode == "blind":
        pool.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        return pool[:top]
    if params.mode in ("wide", "narrow"):
        sign = -1.0 if params.mode == "wide" else 1.0
        ranked = sorted(pool, key=lambda r: (sign * spread[r.symbol], r.symbol))
        return ranked[:top]
    # sm-wide: size-matched random control for WIDE -- same count per market-value quintile as
    # WIDE holds, hash-drawn within the quintile, so the spread opinion is removed and the size
    # profile kept. A name with no known market value cannot be bucketed and is excluded from the
    # control's own pool; it still counts toward WIDE's picks if WIDE happened to hold it, but
    # then cannot be matched and is dropped from that quintile's need.
    ranked = sorted(pool, key=lambda r: (-spread[r.symbol], r.symbol))
    treat = ranked[:top]
    sized_pool = [r for r in pool if r.symbol in size]
    if not sized_pool:
        return []
    by_size = sorted(sized_pool, key=lambda r: (size[r.symbol], r.symbol))
    n = len(by_size)
    bucket = {r.symbol: min(BUCKETS - 1, i * BUCKETS // n) for i, r in enumerate(by_size)}
    need: dict[int, int] = {}
    for r in treat:
        b = bucket.get(r.symbol)
        if b is None:
            continue
        need[b] = need.get(b, 0) + 1
    out: list[FactorRow] = []
    for b in sorted(need):
        cand = [r for r in sized_pool if bucket[r.symbol] == b]
        cand.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
        out.extend(cand[: need[b]])
    return out


@dataclass
class SpreadPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    market: Any = field(default=None, repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class CorwinSchultzAllocator:
    """The lab's index-member book ranked on the trailing Corwin-Schultz estimated bid-ask
    spread. Market-aware: every arm targets nothing without a share-count-bearing store, so WIDE,
    NARROW and the plain blind draw run on the same store and code path as the size-matched
    control, even though only the control reads ``market.market_value``."""

    id = "M0590"
    market_fields = ("shares",)

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

    def _run(self, prepared: SpreadPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SpreadParams) -> tuple[Target, ...]:
        if prepared.market is None:  # the lab's market-aware contract: no panel, no targets
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        spread = prepared.cache.get(data_date)
        if spread is None:
            spread = scored_names(prepared.history, syms, data_date)
            prepared.cache[data_date] = spread
        size: dict[str, float] = {}
        for s in syms:
            v = prepared.market.market_value(s, data_date)
            if v is not None and np.isfinite(v) and v > 0.0:
                size[s] = float(v)
        return targets_from_rows(choose(rows, spread, size, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no market, so no arm targets anything (the contract)."""
        return self._run(SpreadPrepared(history, prepare_factor(history), None), members,
                         data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SpreadPrepared:
        return SpreadPrepared(history, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> SpreadPrepared:
        sized = len(market.shares) > 0
        return SpreadPrepared(market.history, prepare_factor(market.history),
                              market if sized else None)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SpreadPrepared):
            raise TypeError(f"prepared must be SpreadPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CORWINSCHULTZ = CorwinSchultzAllocator()


def _v(suffix: str, params: SpreadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0590-{suffix}", family="M0590", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CORWINSCHULTZ, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0590",
    name="Corwin-Schultz high-low spread: hold the stocks with the widest estimated bid-ask spread",
    family="stock-corwin-schultz-spread",
    source_kind="paper",
    source_ref=("Corwin & Schultz (2012, JF 67(2)), 'A Simple Way to Estimate Bid-Ask Spreads "
                "from Daily High and Low Prices'"),
    parent_id=None,
    hypothesis=(
        "Corwin & Schultz (2012) back out an implied percentage bid-ask spread from two "
        "consecutive days' high/low prices alone -- no volume, no quote data -- and later work "
        "finds wider-implied-spread stocks earn a liquidity-risk premium. This is a different "
        "mechanism from two things already in the lab: M0348 (dev-eligible) ranks on the mean "
        "daily high-low RANGE, a swing-size proxy, and its sibling M0350 found range adds nothing "
        "over plain close-to-close volatility once matched for it; Corwin-Schultz instead reads "
        "the ratio of a two-day combined range to each day's own range, which factors out the "
        "volatility level range measures directly. It is also different from M0058's Amihud "
        "illiquidity (volume-scaled price impact, rejected: a small-company bet, -26% worst fall, "
        "lost 3 of 4 walk-forward folds) and from M0497's share-turnover ranking (volume scaled "
        "by shares outstanding, test-failed in the direction opposite the published anomaly). "
        "Every month the book scores each F4-screened index member on the mean trailing "
        "Corwin-Schultz spread over 21 overlapping two-day pairs (22 bars) and holds the 20 "
        "widest equal weight, monthly, fractional shares at Gotrade's real fees, behind SPY's "
        "200-day switch. Arms: WIDE (the idea), NARROW (the mirror, same costs), SM-WIDE "
        "(size-matched blind-draw control: same count per market-value quintile as WIDE holds, "
        "hash-drawn within the quintile, so WIDE's size profile is kept and its spread opinion "
        "removed -- the direct test of whether this is a liquidity premium or smallness again), "
        "R1 (plain hash order on the same scored pool, behind the switch) and R1-NOSW (R1's "
        "order, no switch: the always-invested no-opinion arm that prices the switch's habit). "
        "Predictions, written now: WIDE beats NARROW on funded CAGR (both pay the same costs); "
        "WIDE's edge over SM-WIDE is under 2 points a year, i.e. the premium is mostly size "
        "wearing a new estimator (consistent with M0058's finding); WIDE trails SPY in "
        "2009-2015, the highest-coverage era; R1-NOSW falls over 40%, so the switch and not the "
        "ranking carries the fall. Published 2012 and cited widely since in the market- "
        "microstructure literature, so a strong dev-only result is treated as the pre-crowd kind "
        "at best and a size proxy at worst, not a surviving edge."
    ),
    expected_failure=(
        "The likeliest failure, by the lab's own prior: WIDE's edge collapses into SM-WIDE's "
        "(the premium is smallness/illiquidity in disguise, the same conclusion M0058 reached "
        "with a volume-based measure), and WIDE trails SPY in 2009-2015 and most walk-forward "
        "folds the way M0058 did (lost 3 of 4). A second failure mode is emptiness rather than "
        "decay: the Corwin-Schultz estimator can be dominated by measurement noise on back-"
        "adjusted dev-era prices (stale bars, gaps, thin two-day windows), in which case WIDE and "
        "NARROW both land close to R1's chance spread and the hypothesis is unfalsifiable from "
        "this run rather than falsified. Negative two-day estimates are floored at zero per pair "
        "before averaging (the paper's own convention for a known noise case), which can still "
        "compress genuine cross-sectional variation among liquid large caps toward zero and make "
        "the narrow end close to a random draw. Names with no market value cannot be matched by "
        "SM-WIDE and are dropped from its own pool only, not from WIDE's; coverage of market "
        "value is 62-75% of dev member-days in 2009-2015 and lower earlier, so the size match is "
        "thinner in early years."
    ),
    candidates=(
        _v("WIDE", SpreadParams(N20, "wide"),
           "The 20 widest trailing Corwin-Schultz estimated spread, behind the SPY switch: the idea"),
        _v("NARROW", SpreadParams(N20, "narrow"),
           "The 20 narrowest estimated spread, behind the switch: the mirror"),
        _v("SM-WIDE", SpreadParams(N20, "sm-wide", 590),
           "Size-matched random control for WIDE: same count per market-value quintile, hash-drawn"),
        _v("R1", SpreadParams(N20, "blind", 591),
           "Control: hash-ranked scored pool, seed 591, behind the switch"),
        _v("R1-NOSW", SpreadParams(NOSW, "blind", 591),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
    ),
    seen_keys=(
        "concept:corwin-schultz-high-low-spread",
        "concept:estimated-bid-ask-spread-from-high-low",
    ),
)
