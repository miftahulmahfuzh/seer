"""M0282 — Moving-average distance: buy the index members whose 21-day average sits furthest above
their 200-day average.

Source: Avramov, Kaplanski & Subrahmanyam (2021), "Moving Average Distance as a Predictor of
Equity Returns", Review of Financial Economics 39(2) 127-145 (SSRN working paper 2018); summary at
https://alphaarchitect.com/moving-average-distance/. Reserved by Sera batch 20261022-1954 as an
``idea`` row; this file refines it and keeps its id.

WHY. Investors anchor on a stock's own long-run price level and under-react when the price drifts
away from it. The paper measures the drift as MAD, the ratio of a stock's 21-session moving average
to its 200-session one, and reports that MAD predicts the next month's return in the cross-section:
about 9% a year value-weighted long-short alpha over 1977-2018, mostly from the long side,
surviving momentum, 52-week-high and profitability controls -- and momentum's own alpha fading once
MAD is in the regression. The working paper appeared in 2018, so the whole dev window (1996-2015)
predates the crowd; that is a reason a dev lead here can be real and also a reason it may not last.

THE DANGER, NAMED BEFORE THE RUN. A stock whose short average is far above its long one has, almost
by definition, risen over the past year and sits near its yearly high. The lab has spent three of
its four test-window looks on momentum books that failed, and the hard gate's behaviour test (D14)
calls any method kin of a failed book when its de-funded monthly returns move with that book at
0.85 or more. A top-MAD book is likely to be exactly that. So the method carries a fourth arm that
ranks on the part of MAD that 12-1 momentum and 52-week-high proximity do NOT explain: on each
decision, across the pool, MAD is regressed on the two (each winsorised at the pool's 5th and 95th
percentiles, then standardised) and the book holds the largest residuals. If that arm ties the
blind draw, MAD is momentum renamed in this data.

THE POOL, ONE PER DECISION, SHARED BY EVERY ARM. Index members (S&P 500 union Nasdaq-100, point in
time) with a bar dated ``data_date``, at least ``BARS`` (253) bars through it, and a known company
size that day (``market.market_value``: "sized" members, which is what the idea row asked for and
what keeps a member the store cannot size out of the book). One listing per company: the second
listed class of a filer (GOOGL beside GOOG, and the rest of M0047's table) is dropped, the class with
the larger market value kept. All three features are read from closes dated on or before the day:

    * MAD = mean of the last 21 closes / mean of the last 200 closes (the paper's ratio);
    * 12-1 momentum = close 21 sessions ago / close 252 sessions ago - 1;
    * 52-week-high proximity = today's close / the highest close of the last 252 sessions.
      **Assumption:** closing highs, not intraday highs (George & Hwang use the daily high; the
      difference is a few tenths of a percent and the regression is about rank, not level).

Fewer than ``MIN_NAMES`` (50) scored names and the decision holds SPY instead. Measured on the dev
store before the run (pool counts only, no returns read): 171 companies at 1996-01-31, 183 in mid
1996, 223 at the end of 1998, 263 in mid 2003, 325 in March 2009, 358 in mid 2012 and 390 in
September 2015, so the guard should never fire.

ARMS, equal 1/20 slots, a held name kept while it still ranks inside the top 40, free slots filled
from the top, fully invested, monthly:

    TOP20       the 20 highest MAD -- the paper's long side, no market switch
    BOT20       the 20 lowest MAD -- the mirror the paper says lags
    TOP20-PLC   placebo: TOP20's book size and monthly entry count drawn blind (hash order) from the
                same pool, with TOP20's band replayed six decisions back (``control_draw``'s
                matched-draw-v2 shadow) so the draw enters as many names as the banded book does.
                The no-opinion arm the mirror rule asks for: same habits, no ranking
    RESID20     the 20 largest MAD residuals after 12-1 momentum and 52-week-high proximity are
                regressed out: is anything left that momentum is not?
    TOP20-SW    TOP20 behind the SPY 200-day switch (all cash while SPY closes at or below its
                200-day average): the habit-on twin of TOP20, so the switch's cost is priced, not
                assumed

Rules ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly top-up. Market-aware (``market_fields = ("shares",)``): on the history-only path there are
no sizes and the allocator targets nothing, as every market-aware allocator must.

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date`` and
share counts filed by it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, NamedTuple

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.lab import control_draw
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0047_market_value_residual import company
from seer_engine.lab.methods.m0130_tree_ranker import _bench
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED

ADDED = date(2026, 10, 22)
SHORT = 21  # sessions in the short moving average
LONG = 200  # sessions in the long moving average
MOM_N, MOM_SKIP = 252, 21  # 12-1 momentum
HIGH_N = 252  # sessions the 52-week high is read over
BARS = MOM_N + 1  # bars through data_date every pool member needs
MIN_NAMES = 50  # smallest pool scored; fewer and the decision holds SPY
WINSOR = 5.0  # percent clipped off each tail of each control before the residual fit
TREND = ("SPY", 200)  # the switch arm's market filter
DEPTH = 6  # decisions the placebo's shadow replays TOP20's band (max affordable is 8)
SIGNALS = ("top", "bottom", "resid", "control")


@dataclass(frozen=True, slots=True)
class MadParams:
    """``top`` names held, ``keep`` the band; ``signal`` top, bottom, resid or control (the matched
    draw of the top book); ``switch`` puts the SPY 200-day filter in front; ``seed`` the draw's."""

    top: int = 20
    keep: int = 40
    signal: str = "top"
    switch: bool = False
    seed: int = 0

    def __post_init__(self) -> None:
        for name in ("top", "keep", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be a non-negative int, got {v!r}")
        if not 1 <= self.top <= 200 or self.keep < self.top:
            raise ValueError(f"need 1 <= top <= 200 and keep >= top, got {self.top}, {self.keep}")
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.signal!r}")
        if not isinstance(self.switch, bool):
            raise TypeError(f"switch must be a bool, got {type(self.switch).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "keep": str(self.keep), "signal": self.signal,
               "switch": f"{TREND[0]}:{TREND[1]}" if self.switch else "none",
               "seed": str(self.seed), "short": str(SHORT), "long": str(LONG),
               "mom": f"{MOM_N}-{MOM_SKIP}", "high_n": str(HIGH_N), "bars": str(BARS),
               "min_names": str(MIN_NAMES), "winsor": repr(WINSOR), "pool": "sized-members",
               "class_rule": "m0047-company-larger-value", "high": "close",
               "fallback": "SPY"}
        if self.signal == "control":
            out["control_rule"] = control_draw.SHADOW_RULE_ID
            out["control_of"] = "top"
            out["depth"] = str(DEPTH)
        return out


def _check(params: object) -> MadParams:
    if not isinstance(params, MadParams):
        raise TypeError(f"params must be MadParams, got {type(params).__name__}")
    return params


class Features(NamedTuple):
    mad: float
    mom: float
    high: float


def features(h: History, data_date: date) -> Features | None:
    """MAD, 12-1 momentum and 52-week-high proximity from closes dated on or before the day."""
    i = h.index_of(data_date)
    if i is None or i + 1 < BARS:
        return None
    c = h.close[i + 1 - BARS : i + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        long_ma = float(np.mean(c[-LONG:]))
        mad = float(np.mean(c[-SHORT:])) / long_ma
        mom = float(c[-1 - MOM_SKIP] / c[-1 - MOM_N]) - 1.0
        high = float(c[-1] / np.max(c[-HIGH_N:]))
    if not (long_ma > 0.0 and np.isfinite(mad) and np.isfinite(mom) and np.isfinite(high)):
        return None
    return Features(mad, mom, high)


@dataclass(frozen=True, slots=True, eq=False)
class MadPrepared:
    history: Mapping[str, History]
    market: Market | None


def pool_on(prepared: MadPrepared, members: AbstractSet[str],
            data_date: date) -> dict[str, Features]:
    """Every sized member's features on ``data_date``, one listing per company."""
    market = prepared.market
    if market is None or len(market.shares) == 0:
        return {}
    best: dict[str, tuple[float, str, Features]] = {}
    for s in sorted(members):
        if s in EXCLUDED or s == "SPY":
            continue
        h = prepared.history.get(s)
        if h is None:
            continue
        f = features(h, data_date)
        if f is None:
            continue
        mv = market.market_value(s, data_date)
        if mv is None or not mv > 0.0:
            continue
        c = company(s)
        seen = best.get(c)
        if seen is None or (mv, s) > (seen[0], seen[1]):
            best[c] = (float(mv), s, f)
    out = {s: f for _, s, f in best.values()}
    return out if len(out) >= MIN_NAMES else {}


def _z(x: np.ndarray) -> np.ndarray | None:
    lo, hi = np.percentile(x, [WINSOR, 100.0 - WINSOR])
    x = np.clip(x, lo, hi)
    sd = float(x.std())
    return (x - float(x.mean())) / sd if sd > 0.0 else None


def residual_mad(pool: Mapping[str, Features]) -> dict[str, float]:
    """MAD less what 12-1 momentum and 52-week-high proximity explain, across ``pool``."""
    names = sorted(pool)
    if len(names) < MIN_NAMES:
        return {}
    y = np.asarray([pool[s].mad for s in names], dtype=np.float64)
    zm = _z(np.asarray([pool[s].mom for s in names], dtype=np.float64))
    zh = _z(np.asarray([pool[s].high for s in names], dtype=np.float64))
    if zm is None or zh is None:
        return {}
    design = np.column_stack([np.ones_like(zm), zm, zh])
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    if not np.all(np.isfinite(resid)):
        return {}
    return {s: float(v) for s, v in zip(names, resid.tolist(), strict=True)}


def scores(pool: Mapping[str, Features], signal: str) -> dict[str, float]:
    """Higher is better."""
    if signal == "resid":
        return residual_mad(pool)
    if signal == "bottom":
        return {s: -f.mad for s, f in pool.items()}
    return {s: f.mad for s, f in pool.items()}


def banded(sc: Mapping[str, float], held: AbstractSet[str], top: int, keep: int) -> list[str]:
    """Held names ranked inside ``keep`` stay; the rest of ``top`` is filled from the top."""
    order = sorted(sc, key=lambda s: (-sc[s], s))
    rank = {s: i for i, s in enumerate(order)}
    picks = sorted((s for s in held if rank.get(s, keep) < keep), key=lambda s: rank[s])[:top]
    for s in order:
        if len(picks) >= top:
            break
        if s not in picks:
            picks.append(s)
    return picks


def _switch_on(history: Mapping[str, History], data_date: date) -> bool:
    h = history.get(TREND[0])
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < TREND[1]:
        return False
    return bool(h.close[i] > float(np.mean(h.close[i + 1 - TREND[1] : i + 1])))


class MadAllocator:
    """The ``top`` sized members by moving-average distance (or its mirror, its momentum-free
    residual, or a matched blind draw of the top book), banded, equal slots, fully invested; SPY
    when the pool is too small to score."""

    id = "M0282"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return control_draw.shadow_lookback_for(BARS, DEPTH) if p.signal == "control" else BARS

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _names(self, prepared: MadPrepared, members: AbstractSet[str], data_date: date,
               held: frozenset[str], p: MadParams) -> Sequence[str]:
        if p.signal == "control":
            def replay(d: date, shadow: AbstractSet[str]) -> tuple[list[str], list[str]]:
                pool = pool_on(prepared, members, d)
                if not pool:
                    return [], []
                return sorted(pool), banded(scores(pool, "top"), shadow, p.top, p.keep)

            return control_draw.shadow_book(replay, data_date, held, tag="M0282", seed=p.seed,
                                            depth=DEPTH)
        pool = pool_on(prepared, members, data_date)
        if not pool:
            return []
        return banded(scores(pool, p.signal), held, p.top, p.keep)

    def _run(self, prepared: MadPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: MadParams) -> tuple[Target, ...]:
        if prepared.market is None or len(prepared.market.shares) == 0:
            return ()  # no company sizes: no pool to read, and by contract no target
        if p.switch and not _switch_on(prepared.history, data_date):
            return ()
        names = self._names(prepared, members, data_date, held, p)
        if not names:
            return _bench(prepared.history, data_date)
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in names:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no target."""
        return self._run(MadPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> MadPrepared:
        return MadPrepared(history, None)

    def prepare_market(self, market: Any) -> MadPrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return MadPrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MadPrepared):
            raise TypeError(f"prepared must be MadPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


MAD = MadAllocator()


def _v(suffix: str, params: MadParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0282-{suffix}", family="M0282", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MAD, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0282",
    name=("Moving-average distance: buy index members whose 21-day average sits furthest above "
          "their 200-day average"),
    family="stock-moving-average-distance",
    source_kind="paper",
    source_ref=(
        "Avramov, Kaplanski & Subrahmanyam (2021), Moving Average Distance as a Predictor of "
        "Equity Returns, Review of Financial Economics 39(2):127-145 (SSRN 2018); "
        "https://alphaarchitect.com/moving-average-distance/"
    ),
    parent_id=None,
    hypothesis=(
        "Anchoring: investors under-react when a stock drifts away from its own long-run price "
        "level, so the ratio of its 21-session to its 200-session moving average (MAD) predicts "
        "next month's return across stocks. The paper (SSRN 2018, so the whole 1996-2015 dev "
        "window predates the crowd) reports about 9% a year long-short alpha over 1977-2018, "
        "strongest on the long side, surviving momentum and 52-week-high controls. Test: each "
        "month, among sized index members with 253 bars (one listing per company; fewer than 50 "
        "and the month holds SPY), rank by MAD and hold 20 in equal slots, a held name kept while "
        "inside the top 40, fully invested, no switch, fractional shares at Gotrade's real fees "
        "on the owner's monthly top-up. Arms: TOP20; BOT20 (the mirror); TOP20-PLC (TOP20's size "
        "and entry count drawn blind from the same pool, its band replayed six months back: the "
        "no-opinion arm that prices the habit); RESID20 (MAD with 12-1 momentum and 52-week-high "
        "proximity regressed out each month); TOP20-SW (TOP20 behind the SPY 200-day switch, the "
        "habit-on twin). Predictions written before any result: TOP20 beats BOT20 and the placebo "
        "by 2 or more points a year over 1996-2015; RESID20 beats the placebo by at least 1 point "
        "a year, or MAD is momentum renamed; TOP20 leads SPY in 2009-2015."
    ),
    expected_failure=(
        "In order of likelihood. (1) It is momentum in a new coat: a top-MAD stock has risen over "
        "the year and sits near its high, so TOP20's de-funded monthly returns move with the "
        "test-failed momentum books at 0.85 or more, the hard gate calls it their kin, and it "
        "cannot be promoted however good its dev numbers -- while RESID20, the arm that would "
        "escape that, ties the placebo because what MAD adds beyond momentum is small and noisy. "
        "(2) The momentum crashes: TOP20 holds 1999-2000 technology into the 2000-2002 fall and "
        "the high-beta laggards' rebound of 2009 hurts it, so its worst fall without a switch "
        "breaks the 25% bar, and TOP20-SW passes the fall test only by paying the switch's "
        "cash drag in a rising 2009-2015. (3) 2009-2015 is the first filter and every equal-slot "
        "book in this lab has trailed SPY there; a book of recent winners among index members "
        "is no exception, and the paper's value-weighted alpha came disproportionately from "
        "smaller stocks than these. (4) The mirror BOT20 may beat TOP20 in 2009 alone by enough "
        "to blur the twenty-year contrast. Any of these is a rejection, not a reason to tune the "
        "21 and 200 windows afterwards."
    ),
    candidates=(
        _v("TOP20", MadParams(signal="top"),
           "The 20 sized members whose 21-day average sits furthest above their 200-day average, "
           "held while inside the top 40, monthly, no switch"),
        _v("BOT20", MadParams(signal="bottom"),
           "Mirror: the 20 sized members whose 21-day average sits furthest below their 200-day "
           "average"),
        _v("TOP20-PLC", MadParams(signal="control", seed=1),
           "Placebo: TOP20's book size and monthly entries drawn blind in a hash order from the "
           "same pool, TOP20's band replayed six decisions back"),
        _v("RESID20", MadParams(signal="resid"),
           "The 20 largest distances left after 12-1 momentum and 52-week-high proximity are "
           "regressed out each month"),
        _v("TOP20-SW", MadParams(signal="top", switch=True),
           "TOP20 behind the SPY 200-day switch: all cash while SPY closes at or below its "
           "200-day average"),
    ),
    seen_keys=(
        "concept:moving-average-distance",
        "concept:price-anchoring",
        "concept:momentum-orthogonalised-trend",
    ),
)
