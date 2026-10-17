"""M0222 — A market-shaped book that leans toward dividend raisers.

Source: FTSE Russell's factor-tilt method ("Multi-factor indexes: the power of tilting": cap
weight x a normal-CDF score of the factor, rescaled), MSCI's factor tilt indexes; the raise
signal is Michaely, Thaler & Womack (1995), JF 50(2), as this lab has measured it since M0070;
insight 391 (Sera 20261017-2050: the raise signal beat a random twin of the same frame by about
two points a year, while the frame -- equal slots, the SPY-200 switch, money parked in SPY --
trailed SPY after 2009). Reserved by Sera 20261018-0517 as M0222.

Why this shape. Every dividend-raise book so far held equal slots, which is a bet against the
market's shape (insight 91) on top of the picking. Here the frame is the market itself: the 50
biggest screened index companies by real point-in-time market value (``Market.market_value``,
shares outstanding as filed by that day x the close as it printed), weighted by that value.
The raise signal only *tilts* those weights, the way FTSE and MSCI build their tilt indexes, so
the book cannot drift far from SPY's shape and the tilt's effect is a clean paired difference.

The universe on data date d: index members passing F4's screen (``factor_rows``: price >= $5,
20-day dollar volume >= $20M, a year of bars) with a known market value. Two listed classes of
one company answer the same whole-company share count, so members are grouped by that count and
only the class with the larger 20-day dollar volume is kept. The ``top`` biggest are held.

The raise score. A member's latest dividend, dated by the day the market could see it
(``timing="announced"``: the declaration date when the store has one, else the ex-date), is live
for ``hold_days``. Its change r is the amount over the median of its up-to-four payments in the
400 days before, minus one (M0070's baseline). Neutral (score 0.5): no live dividend, no payer,
an unchanged payment (|r| <= 1%), a one-off special (r > 100%), or a first payment (rare among
the 50 biggest; counted neutral rather than guessed at). Every other live change is scaled by
the root-mean-square r of all such changes that day across the universe, so no change stays at
zero and a raise lands above it and a cut below: z = r / rms, clipped to +-3, score = Phi(z).
With fewer than ``min_events`` such changes the day is all neutral.

The weights. w = market value x score^power, rescaled to 1, then capped at ``ceiling`` with the
excess re-spread pro rata over the uncapped names until nothing is over (pre-registered, as M0047
warned an uncapped size book concentrates). ``power=0`` is the plain market core.

The random twin. ``order="random"`` keeps every non-neutral score of the day (their number and
their values) and hands them to as many universe names drawn by a fixed blake2b hash of seed,
symbol and quarter, the scores in a hash order of their own; everyone else is neutral. Same core,
same tilt strength and spread, names that know nothing about dividends.

``trend`` (the inner screen's SPY-200 switch) steps the whole book into cash while SPY closes
under its 200-day average. Without the market's calendar or share history (the history-only
``prepare``/``targets`` path) nothing is targeted: the market-aware allocator contract.

Rules are ``monthly-hold-frac-gotrade-tband``: fractional shares at Gotrade's real fees, monthly,
with the rebalance band measured against each holding's own target (20%) rather than 1% of the
account. A 50-name market-shaped book holds many 1-2% weights; under the account-wide band a
deposit would almost never be added to them and would sit as cash (the 50-slot M0117-C was 89%
invested on the old band, the 100-name M0123-ALL100-TB 96% on this one).

Pure: reads only bars, dividends and share counts dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import BASE_DAYS, BASE_N, NOT20, T20
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import events
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 18)
ORDERS = ("raise", "random")
_W_Q = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class TiltParams:
    """``inner`` is F4's screen and (optional) SPY-200 switch; ``top`` the core's size;
    ``ceiling`` the most one company may weigh; ``power`` the tilt strength (0: no tilt);
    ``order`` the real raise scores or the random twin's."""

    inner: FactorParams
    top: int = 50
    ceiling: Decimal = Decimal("0.10")
    power: int = 1
    order: str = "raise"
    seed: int = 1
    hold_days: int = 182
    flat_tol: float = 0.01
    special: float = 1.0
    zclip: float = 3.0
    min_events: int = 5
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("top", "power", "seed", "hold_days", "min_events"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {v!r}")
        if self.top < 2 or self.power < 0 or self.hold_days < 20 or self.min_events < 2:
            raise ValueError("top >= 2, power >= 0, hold_days >= 20 and min_events >= 2")
        if not isinstance(self.ceiling, Decimal) or not (Decimal(0) < self.ceiling <= Decimal(1)):
            raise ValueError(f"ceiling must be a Decimal in (0, 1], got {self.ceiling!r}")
        if self.ceiling * self.top < 1:
            raise ValueError("ceiling x top must reach 1, or the weights cannot sum to 1")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {ORDERS}, got {self.order!r}")
        for name in ("flat_tol", "special", "zclip"):
            v = getattr(self, name)
            if not isinstance(v, float) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{name} must be a finite float > 0, got {v!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "ceiling": str(self.ceiling), "power": str(self.power),
               "order": self.order, "seed": str(self.seed), "hold_days": str(self.hold_days),
               "flat_tol": repr(self.flat_tol), "special": repr(self.special),
               "zclip": repr(self.zclip), "min_events": str(self.min_events),
               "market": self.market, "timing": "announced", "score": "normal-cdf-rms",
               "size": "market-value-one-class", "hash": "blake2b-8-quarter"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TiltParams:
    if not isinstance(params, TiltParams):
        raise TypeError(f"params must be TiltParams, got {type(params).__name__}")
    return params


@dataclass
class TiltPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared | None = field(repr=False)
    calendar: DividendCalendar = field(repr=False)
    market: Any = field(repr=False, default=None)


def change(paid: tuple[tuple[date, Decimal], ...], data_date: date, p: TiltParams) -> float | None:
    """The latest live dividend's change against its baseline, or None when it is neutral."""
    if not paid:
        return None
    e, a = paid[-1]
    if (data_date - e).days >= p.hold_days:
        return None
    since = e - timedelta(days=BASE_DAYS)
    prior = [amt for d, amt in paid[:-1] if d > since][-BASE_N:]
    if not prior:
        return None  # a first payment (or the store's first row): neutral
    base = statistics.median(prior)
    if base <= 0:
        return None
    r = float(a / base) - 1.0
    if abs(r) <= p.flat_tol or r > p.special:
        return None
    return r


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def draw(seed: int, key: str, data_date: date) -> int:
    """The random twin's order: a fixed 64-bit hash of seed, key and the calendar quarter."""
    tag = f"{seed}|{key}|{data_date.year:04d}-Q{(data_date.month - 1) // 3 + 1}".encode()
    return int.from_bytes(hashlib.blake2b(tag, digest_size=8).digest(), "big")


def core(prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
         p: TiltParams) -> list[tuple[str, float, float]]:
    """The ``top`` biggest screened members, one class per company: (symbol, close, value)."""
    inner = p.inner
    if prepared.factor is None:
        rows = factor_rows(prepared.history, members, data_date, inner)
    else:
        rows = prepared.factor.rows_on(members, data_date, inner)
    m = prepared.market
    best: dict[float, tuple[float, str, float, float]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        shares = m.shares_on(r.symbol, data_date)
        value = m.market_value(r.symbol, data_date)
        if shares is None or value is None or not (value > 0 and math.isfinite(value)):
            continue
        row = (r.dollar_volume, r.symbol, r.close, value)
        seen = best.get(shares)
        if seen is None or (row[0], row[1]) > (seen[0], seen[1]):
            best[shares] = row
    ranked = sorted(best.values(), key=lambda t: (-t[3], t[1]))[: p.top]
    return [(s, c, v) for _, s, c, v in ranked]


def scores(prepared: TiltPrepared, names: list[str], data_date: date,
           p: TiltParams) -> dict[str, float]:
    """Each name's tilt score in (0, 1); 0.5 is neutral."""
    out = dict.fromkeys(names, 0.5)
    changes: dict[str, float] = {}
    for s in names:
        paid, _ = events(prepared.calendar, s, data_date, "announced")
        r = change(paid, data_date, p)
        if r is not None:
            changes[s] = r
    if len(changes) < p.min_events:
        return out
    rms = math.sqrt(sum(r * r for r in changes.values()) / len(changes))
    if not rms > 0:
        return out
    real = {s: phi(max(-p.zclip, min(p.zclip, r / rms))) for s, r in changes.items()}
    if p.order == "raise":
        out.update(real)
        return out
    vals = sorted(real.values(), key=lambda v: (draw(p.seed, repr(v), data_date), v))
    takers = sorted(names, key=lambda s: (draw(p.seed, s, data_date), s))[: len(vals)]
    out.update(zip(takers, vals, strict=True))
    return out


def capped(raw: dict[str, float], ceiling: float) -> dict[str, float]:
    """``raw`` rescaled to 1 with no weight over ``ceiling``; the excess goes pro rata to the rest."""
    w = dict(raw)
    fixed: dict[str, float] = {}
    while True:
        free = sum(w.values())
        budget = 1.0 - sum(fixed.values())
        over = [s for s, v in w.items() if v / free * budget > ceiling]
        if not over:
            return {**fixed, **{s: v / free * budget for s, v in w.items()}}
        for s in over:
            fixed[s] = ceiling
            del w[s]
        if not w:
            return fixed


def choose(prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
           p: TiltParams) -> tuple[Target, ...]:
    book = core(prepared, members, data_date, p)
    if len(book) < 2:
        return ()
    sc = scores(prepared, [s for s, _, _ in book], data_date, p)
    raw = {s: v * sc[s] ** p.power for s, _, v in book}
    w = capped(raw, float(p.ceiling))
    out: list[Target] = []
    for s, c, _ in sorted(book, key=lambda t: (-w[t[0]], t[0])):
        wt = Decimal(repr(w[s])).quantize(_W_Q, rounding=ROUND_FLOOR)
        if wt <= 0:
            continue
        t = target_from_close(s, c, wt)
        if t is not None:
            out.append(t)
    return tuple(out)


class RaiseTiltedCoreAllocator:
    """The 50 biggest index companies at their market value, tilted by a dividend-change score
    (or a random twin of it), capped per company; optionally behind the SPY-200 switch."""

    id = "M0222"
    market_fields = ("dividends", "shares")

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
             p: TiltParams) -> tuple[Target, ...]:
        m = prepared.market
        if m is None or len(prepared.calendar) == 0 or len(m.shares) == 0:
            return ()  # no panel: target nothing (market-aware contract)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        return choose(prepared, members, data_date, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar and no share counts, so no target."""
        return self._run(TiltPrepared(history, None, EMPTY_DIVIDENDS), members, data_date,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> TiltPrepared:
        return TiltPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> TiltPrepared:
        calendar = getattr(market, "dividends", EMPTY_DIVIDENDS)
        if not isinstance(calendar, DividendCalendar):
            raise TypeError(f"market.dividends must be a DividendCalendar, got {type(calendar).__name__}")
        return TiltPrepared(market.history, prepare_factor(market.history), calendar, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TiltPrepared):
            raise TypeError(f"prepared must be TiltPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


TILT = RaiseTiltedCoreAllocator()


def _v(suffix: str, params: TiltParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0222-{suffix}", family="M0222", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=TILT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0222",
    name=(
        "A market-shaped book that leans toward dividend raisers: every member at its market "
        "value, tilted by a dividend-raise score"
    ),
    family="stock-dividend-change-drift",
    source_kind="paper",
    source_ref=(
        "FTSE Russell factor-tilt method (cap weight x normal-CDF score, rescaled; 'Multi-factor "
        "indexes: the power of tilting'); MSCI factor tilt indexes; CEPR index-weight study via "
        "AAII (index weight negatively predicts return); Michaely, Thaler & Womack (1995), JF "
        "50(2); insight 391 (dividend-raise signal real, frame trails)"
    ),
    parent_id=None,
    hypothesis=(
        "Published 1995 (dividend-change drift); factor tilting is index practice since about "
        "2013, not an anomaly. Insight 391: the raise signal beat a random twin of its own frame "
        "by about two points a year, but the frame (equal 5% slots, the SPY-200 switch, the rest "
        "parked in SPY) trailed SPY in 2009-2015. Remove the frame. Core: the 50 biggest F4-"
        "screened index members by point-in-time market value (shares filed by that day x the "
        "close as printed), one share class per company (classes grouped by their shared share "
        "count, the more traded kept), weighted by market value, no company over 10%. Tilt: each "
        "weight x score^power, rescaled, re-capped; score = Phi(z), z = r / rms(r) clipped to "
        "+-3, where r is the latest dividend's change against the median of its up-to-four "
        "payments in the prior 400 days, dated by its declaration (else ex-date) and live 182 "
        "days; unchanged (within 1%), specials (over +100%), first payments, non-payers and "
        "names without a live dividend sit at a neutral 0.5; raises tilt up, cuts down. Variants "
        "(all monthly, fractional, Gotrade's real fees, target-relative band, owner's deposits, "
        "no SPY parking): CORE (power 0: the market-shaped yardstick), TILT1 (power 1), TILT2 "
        "(power 2), RAND1 and RAND2 (the same day's non-neutral scores handed to hash-drawn "
        "names, quarterly), TILT2-T (TILT2 behind the SPY-200 switch). Success: TILT1 or TILT2 "
        "beats total-return SPY on the owner's deposits with the worst fall under the bar, beats "
        "its RAND twin, beats CORE, and does not trail SPY in 2009-2015. Assumptions: the tband "
        "preset rather than the plain monthly one, because a 50-name book of 1-2% weights would "
        "otherwise leave most deposits in cash; first payments neutral."
    ),
    expected_failure=(
        "A tilt this gentle moves a 50-name market-value book less than a point a year from its "
        "core, and the core itself trails SPY: the top 50 is not the S&P 500 (it leaves out "
        "SPY's other ~50% and holds no names the dev store cannot price), the 10% ceiling bites "
        "on GE, Exxon, Microsoft and Apple in their peaks, and the deposits and fees on fifty "
        "names cost more than SPY's single order. The 1990s-2000s top 50 is GE, Exxon, Citi, "
        "AIG, Enron-era names: a bigger-is-better core lost hard in 2000-2002 and 2008, so CORE "
        "and the ungated tilts take a 45-55% fall, far over the bar; only TILT2-T has a chance at "
        "the bar and the switch is what made the old frame trail after 2009. Among the 50 "
        "biggest companies raises are routine (most raise 5-10% a year), so the score spreads "
        "little and the difference to the random tilt is noise. Banks raised the most before "
        "2008 and cut the most in it, so a raise tilt may lean into the 2008 crash, and the cut "
        "penalty only arrives after the fall. A published anomaly whose dev edge, if any, may "
        "have faded; withholding tax on dividends is not modelled; market value is missing for "
        "members with no bars, which the dev store mostly lacks before 2005."
    ),
    candidates=(
        _v("CORE", TiltParams(NOT20, power=0),
           "The yardstick: 50 biggest members at market value, 10% ceiling, no tilt"),
        _v("TILT1", TiltParams(NOT20, power=1),
           "Market value x dividend-change score (normal-CDF, neutral 0.5)"),
        _v("TILT2", TiltParams(NOT20, power=2),
           "Market value x score squared: the stronger tilt"),
        _v("RAND1", TiltParams(NOT20, power=1, order="random"),
           "Control: the same day's scores handed to hash-drawn names, power 1"),
        _v("RAND2", TiltParams(NOT20, power=2, order="random"),
           "Control: the same day's scores handed to hash-drawn names, power 2"),
        _v("TILT2-T", TiltParams(T20, power=2),
           "TILT2 behind the SPY-200 switch: all cash while SPY is under its 200-day average"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:market-cap-weight",
        "concept:factor-tilt",
        "concept:random-tilt-control",
    ),
)
