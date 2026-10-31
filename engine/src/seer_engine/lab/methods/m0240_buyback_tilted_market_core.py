"""M0240 — A market-shaped book that leans toward companies shrinking their share count.

Source: variation of M0230 (its buyback signal, read the same way) and of M0222 (its tilt shape);
Pontiff & Woodgate (2008), "Share Issuance and Cross-Sectional Returns", Journal of Finance 63(2)
921-945; FTSE Russell / MSCI factor-tilt indexes (cap weight x a normal-CDF score, rescaled).
Reserved by Sera batch 20261031-1503 as an ``idea`` row; this file refines it and keeps its id.

Why this shape. M0230 showed the buyback signal survives dilution linearly, but its twenty names
were still an equal-slot book of twenty and it fell with SPY in 2008. Here the frame is the market:
the ``top`` biggest screened index companies by real point-in-time market value, one share class
per company, weighted by that value (M0222's ``core``, reused verbatim). The buyback signal only
*tilts* the weights, the way index providers tilt: each weight x score^power, rescaled, capped at
10% per company with the excess re-spread pro rata (M0222's ``capped``).

The score. M0227's ``issuance`` (log change in the split-adjusted share count over a year, ``None``
when unreadable) for every core name. z = -x / rms(x) over the names that day that have a reading,
clipped to +-3, score = Phi(z): a shrinker lands above 0.5, an issuer below. Names with no reading
sit at a neutral 0.5; with fewer than ``min_scored`` readings the whole day is neutral.

The random twin. ``order="random"`` keeps the day's score *values* and hands them to as many core
names drawn by a blake2b hash of seed, symbol and calendar quarter (M0222's ``draw``) -- the
re-drawing placebo, deliberately not the sticky hash M0230 inherited from M0227, which traded 41
times in nineteen years and so measured a different habit.

Assumptions written before any run: ``top`` is 100 (the idea says "every screened index member";
100 keeps ceiling x top at 10 and gives the tilt a real choice, where M0222's 50 let the ceiling
bite); the tband preset for the reason M0222 gives (a 100-name book of ~1% weights under an account-
wide band would leave deposits in cash). ``switch`` (T20) steps the whole book into cash while SPY
closes under its 200-day average.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts and
targets nothing. Pure: reads only bars and share counts dated <= ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20, T20
from seer_engine.lab.methods.m0222_raise_tilted_market_core import (
    TiltParams,
    TiltPrepared,
    capped,
    core,
    draw,
    phi,
)
from seer_engine.lab.methods.m0227_net_share_shrinkers import issuance
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_lookback, prepare_factor, trend_on

ADDED = date(2026, 10, 31)
ORDERS = ("shrink", "random")
_W_Q = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class BuybackTiltParams:
    """``base`` is M0222's market core (its own ``power``/``order`` are unused: keep power 0);
    ``power`` the tilt strength (0: none); ``order`` the real buyback scores or the random twin's."""

    base: TiltParams
    power: int = 1
    order: str = "shrink"
    seed: int = 1
    zclip: float = 3.0
    min_scored: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.base, TiltParams):
            raise TypeError(f"base must be TiltParams, got {type(self.base).__name__}")
        if self.base.power != 0:
            raise ValueError("base.power must be 0: the tilt lives on this class")
        for name in ("power", "seed", "min_scored"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {v!r}")
        if self.power < 0 or self.min_scored < 2:
            raise ValueError("power >= 0 and min_scored >= 2")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {ORDERS}, got {self.order!r}")
        if not isinstance(self.zclip, float) or not math.isfinite(self.zclip) or self.zclip <= 0:
            raise ValueError(f"zclip must be a finite float > 0, got {self.zclip!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"power": str(self.power), "order": self.order, "seed": str(self.seed),
               "zclip": repr(self.zclip), "min_scored": str(self.min_scored),
               "signal": "log-share-count-change-365d", "score": "normal-cdf-rms-negated",
               "hash": "blake2b-8-quarter"}
        for k, v in self.base.as_dict().items():
            out[f"base.{k}"] = v
        return out


def _check(params: object) -> BuybackTiltParams:
    if not isinstance(params, BuybackTiltParams):
        raise TypeError(f"params must be BuybackTiltParams, got {type(params).__name__}")
    return params


def scores(prepared: TiltPrepared, names: list[str], data_date: date,
           p: BuybackTiltParams) -> dict[str, float]:
    """Each name's tilt score in (0, 1); 0.5 is neutral."""
    out = dict.fromkeys(names, 0.5)
    xs: dict[str, float] = {}
    for s in names:
        x = issuance(prepared.market, s, data_date)
        if x is not None and math.isfinite(x):
            xs[s] = x
    if len(xs) < p.min_scored:
        return out
    rms = math.sqrt(sum(x * x for x in xs.values()) / len(xs))
    if not rms > 0:
        return out
    real = {s: phi(max(-p.zclip, min(p.zclip, -x / rms))) for s, x in xs.items()}
    if p.order == "shrink":
        out.update(real)
        return out
    vals = sorted(real.values(), key=lambda v: (draw(p.seed, repr(v), data_date), v))
    takers = sorted(names, key=lambda s: (draw(p.seed, s, data_date), s))[: len(vals)]
    out.update(zip(takers, vals, strict=True))
    return out


def choose(prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
           p: BuybackTiltParams) -> tuple[Target, ...]:
    book = core(prepared, members, data_date, p.base)
    if len(book) < 2:
        return ()
    sc = scores(prepared, [s for s, _, _ in book], data_date, p)
    raw = {s: v * sc[s] ** p.power for s, _, v in book}
    w = capped(raw, float(p.base.ceiling))
    out: list[Target] = []
    for s, c, _ in sorted(book, key=lambda t: (-w[t[0]], t[0])):
        wt = Decimal(repr(w[s])).quantize(_W_Q, rounding=ROUND_FLOOR)
        if wt <= 0:
            continue
        t = target_from_close(s, c, wt)
        if t is not None:
            out.append(t)
    return tuple(out)


class BuybackTiltedCoreAllocator:
    """The ``top`` biggest index companies at market value, tilted by a share-count-shrink score
    (or a re-drawing random twin of it), capped per company; optionally behind the SPY-200 switch."""

    id = "M0240"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).base.inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        b = _check(params).base
        fixed = {b.market}
        if b.inner.trend is not None:
            fixed.add(b.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
             p: BuybackTiltParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(m.shares) == 0:
            return ()  # no share counts: target nothing (market-aware contract)
        if not trend_on(prepared.history, data_date, p.base.inner):
            return ()
        return choose(prepared, members, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no target."""
        return self._run(TiltPrepared(history, None, EMPTY_DIVIDENDS), members, data_date,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> TiltPrepared:
        return TiltPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> TiltPrepared:
        return TiltPrepared(market.history, prepare_factor(market.history), EMPTY_DIVIDENDS, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TiltPrepared):
            raise TypeError(f"prepared must be TiltPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


TILT = BuybackTiltedCoreAllocator()
BASE = TiltParams(NOT20, top=100, power=0)
BASE_T = TiltParams(T20, top=100, power=0)


def _v(suffix: str, params: BuybackTiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0240-{suffix}", family="M0240", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=TILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0240",
    name=(
        "A market-shaped book that leans toward buyback companies: every big index member at its "
        "market value, tilted by a share-count-shrink score"
    ),
    family="stock-net-share-issuance",
    source_kind="variation",
    source_ref=(
        "variation of M0230 (buyback signal) and M0222 (tilt shape); Pontiff & Woodgate (2008) JF "
        "63(2) 921-945, https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; FTSE Russell "
        "and MSCI factor-tilt indexes"
    ),
    parent_id="M0230",
    hypothesis=(
        "Published 2008, so the dev window's best-covered years are post-publication and the edge "
        "may have faded. M0230 showed the buyback signal survives dilution linearly (leads of +1.4, "
        "+2.5 and +3.8 points a year at 30%, 50% and 70% sleeves, monotone with the dead "
        "companies put back) but kept a twenty-name equal-slot sleeve beside SPY, so the 2008 fall "
        "stayed near 55%. Apply the signal as index providers apply a factor tilt instead: hold the "
        "100 biggest screened index members (F4's screen, one share class per company) by real "
        "point-in-time market value, multiply each weight by a score built from its one-year "
        "split-adjusted share-count change (score = Phi(-x / rms(x)) clipped to +-3, neutral 0.5 "
        "for unreadable names), rescale, cap any one company at 10%. Monthly, fractional, Gotrade's "
        "real fees, target-relative band, owner's deposits. Arms: CORE (power 0: the market-shaped "
        "yardstick), TILT1 (power 1), TILT2 (power 2), RAND1 and RAND2 (the same day's score values "
        "handed to hash-drawn names re-drawn every quarter: the re-drawing placebo, not M0230's "
        "sticky one), TILT2-T (TILT2 behind the SPY-200 switch, evidence only; TILT2 is its "
        "always-invested, no-opinion-on-timing twin, so the cost of the habit is priced inside this "
        "registration). Predictions written before any result: the fall drops only to about SPY's "
        "own 55% from the sleeve's 59%, so the 20% bar is still missed by every ungated arm; TILT2 "
        "beats RAND2 and CORE by a few tenths to a point a year; the 2009-2015 edge over CORE is "
        "positive. Success: TILT beats total-return SPY on the deposits, beats its RAND twin and "
        "CORE, and does not trail SPY in 2009-2015. Assumptions: top = 100, not 50, and the tband "
        "preset, as M0222 reasoned."
    ),
    expected_failure=(
        "The honest reading from M0221, M0222 and M0225 is that a market-shaped core in this "
        "store trails SPY by 1.6 to 2 points a year in 2009-2015 before any tilt, because the "
        "store cannot price several of that decade's biggest winners, so the tilt would have to "
        "earn 2 points just to break even; M0222's dividend tilt earned a few tenths. A tilt this "
        "gentle moves a 100-name book by under a point. Among very large companies share counts "
        "move little (a few percent a year) so the score spreads thinly, and the big shrinkers "
        "are partly the post-2008 banks and tech names that were also the winners, so the lean may "
        "be a size or momentum lean in disguise. If the core trails and the tilt cannot lift it "
        "the finding is that the ruler is bent, which is worth recording once. The 2008 fall "
        "stays 50%+ in every ungated arm; TILT2-T may reach the bar only by sitting out 2009-11."
    ),
    candidates=(
        _v("CORE", BuybackTiltParams(BASE, power=0),
           "The yardstick: 100 biggest members at market value, 10% ceiling, no tilt"),
        _v("TILT1", BuybackTiltParams(BASE, power=1),
           "Market value x buyback score, a gentle tilt"),
        _v("TILT2", BuybackTiltParams(BASE, power=2),
           "Market value x buyback score squared: the strong tilt"),
        _v("RAND1", BuybackTiltParams(BASE, power=1, order="random"),
           "Control: the same day's scores to hash-drawn names re-drawn quarterly, power 1"),
        _v("RAND2", BuybackTiltParams(BASE, power=2, order="random"),
           "Control: the same day's scores to hash-drawn names re-drawn quarterly, power 2"),
        _v("TILT2-T", BuybackTiltParams(BASE_T, power=2),
           "TILT2 behind the SPY-200 switch: evidence only"),
    ),
    seen_keys=(
        "concept:net-share-issuance",
        "concept:buyback-shrinkers",
        "concept:market-cap-weight",
        "concept:factor-tilt",
        "concept:random-tilt-control",
    ),
)
