"""M0280 — A quality tilt on the market itself: the big companies, leaning toward healthy accounts.

Source: Piotroski (2000), JAR 38 (supplement), as M0276 built it; FTSE Russell / MSCI factor-tilt
indexes (cap weight x a score, rescaled), as M0222 built the frame. Reserved by Sera 20261024-1522
as an ``idea`` row with parent M0276; this file refines it and keeps its id.

Why this shape. M0276 found the health score sorts large companies a little, but its frame (the
cheapest third, twenty equal slots) cost more than the score earned, and the check-only book led
SPY on the dev store and trailed it once dead companies were restored. The expensive part was
leaving SPY's big-company shape, so keep the shape. The frame is M0222's: the 50 biggest F4-screened
index members by point-in-time market value, one share class per company, weighted by that value,
no company over 10% (M0047's warning on uncapped size books). The health score then only *tilts*
the weights. A name is never dropped, so the book cannot move far from SPY's shape and the tilt's
effect is a clean paired difference to the plain core.

The score. M0276's own ``health()``: the fraction of up to eight Piotroski tests passed on two
comparable annual reports as filed by the day, at least six tests known. Tilt factor
``f = 0.5 + score`` (0.5 to 1.5; a name with no readable score sits at a neutral 1.0), weight
``market value x f^power``, rescaled, re-capped at the ceiling with the excess spread pro rata
(M0222's ``capped``). The score moves once a year per company, so the tilt adds almost no
turnover beyond the core's own.

Until the filing panel scores at least ``MIN_SCORED`` of the day's core names (2010-spring on
the dev store) every arm is the plain core, so 1996-2009 is the core's own curve in every arm and
the arms differ only from 2010. As in M0276 the whole-window row therefore carries the core's
2008 fall and a thin fold record: the method is evidence, and the 2010-2015 slice is the judgement.

Arms (all monthly, fractional, Gotrade's real fees, the target-relative band, owner's deposits):
CORE (power 0, the yardstick and the opinion-free arm), HEALTH1 and HEALTH2 (power 1 and 2),
REVERSE1 (the mirror, f = 1.5 - score), RAND1 (the day's real scores handed to hash-drawn core
names, redrawn yearly, so same spread and same churn but no knowledge of health).

Pure: reads only bars, filings and share counts dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

import hashlib
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
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20
from seer_engine.lab.methods.m0222_raise_tilted_market_core import (
    TiltParams,
    TiltPrepared,
    capped,
    core,
)
from seer_engine.lab.methods.m0276_cheap_financial_health import health
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, factor_lookback, prepare_factor

ADDED = date(2026, 10, 24)
MODES = ("health", "reverse", "random")
MIN_SCORED = 20  # of the core's names; fewer scored and the day is the plain core
_W_Q = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class QualityParams:
    """``inner`` is F4's screen; ``top`` the core's size; ``ceiling`` the most one company may
    weigh; ``power`` the tilt strength (0: plain core); ``mode`` which order the scores take."""

    inner: FactorParams
    top: int = 50
    ceiling: Decimal = Decimal("0.10")
    power: int = 1
    mode: str = "health"
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("top", "power", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {v!r}")
        if self.top < 2 or self.power < 0:
            raise ValueError("top >= 2 and power >= 0")
        if not isinstance(self.ceiling, Decimal) or not (Decimal(0) < self.ceiling <= Decimal(1)):
            raise ValueError(f"ceiling must be a Decimal in (0, 1], got {self.ceiling!r}")
        if self.ceiling * self.top < 1:
            raise ValueError("ceiling x top must reach 1, or the weights cannot sum to 1")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"top": str(self.top), "ceiling": str(self.ceiling), "power": str(self.power),
               "mode": self.mode, "seed": str(self.seed), "factor": "0.5+score",
               "min_scored": str(MIN_SCORED), "size": "market-value-one-class",
               "score": "piotroski-8-of-m0276", "redraw": "yearly"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> QualityParams:
    if not isinstance(params, QualityParams):
        raise TypeError(f"params must be QualityParams, got {type(params).__name__}")
    return params


def _draw(seed: int, key: str, data_date: date) -> int:
    tag = f"{seed}|{key}|{data_date.year:04d}".encode()
    return int.from_bytes(hashlib.blake2b(tag, digest_size=8).digest(), "big")


def scores(prepared: TiltPrepared, names: list[str], data_date: date,
           p: QualityParams) -> dict[str, float]:
    """Each name's tilt factor; 1.0 is neutral. Reads filings visible on ``data_date`` only."""
    out = dict.fromkeys(names, 1.0)
    m = prepared.market
    real: dict[str, float] = {}
    for s in names:
        sf = m.fundamentals.get(s)
        hs = None if sf is None else health(sf, data_date)
        if hs is not None:
            real[s] = hs[0]
    if len(real) < MIN_SCORED:
        return out
    if p.mode == "health":
        out.update({s: 0.5 + v for s, v in real.items()})
    elif p.mode == "reverse":
        out.update({s: 1.5 - v for s, v in real.items()})
    else:
        vals = sorted(real.values(), key=lambda v: (_draw(p.seed, repr(v), data_date), v))
        takers = sorted(names, key=lambda s: (_draw(p.seed, s, data_date), s))[: len(vals)]
        out.update({s: 0.5 + v for s, v in zip(takers, vals, strict=True)})
    return out


def choose(prepared: TiltPrepared, members: AbstractSet[str], data_date: date,
           p: QualityParams) -> tuple[Target, ...]:
    book = core(prepared, members, data_date,
                TiltParams(p.inner, top=p.top, ceiling=p.ceiling, power=0))
    if len(book) < 2:
        return ()
    f = scores(prepared, [s for s, _, _ in book], data_date, p)
    raw = {s: v * f[s] ** p.power for s, _, v in book}
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


class QualityTiltedCoreAllocator:
    """The 50 biggest index companies at their market value, tilted by a financial-health score
    (or its mirror, or a random twin), capped per company. History-only path: no targets."""

    id = "M0280"
    market_fields = ("fundamentals", "shares")

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        _check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> TiltPrepared:
        return TiltPrepared(history, prepare_factor(history), EMPTY_DIVIDENDS)

    def prepare_market(self, market: Any) -> TiltPrepared:
        return TiltPrepared(market.history, prepare_factor(market.history), EMPTY_DIVIDENDS, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TiltPrepared):
            raise TypeError(f"prepared must be TiltPrepared, got {type(prepared).__name__}")
        p = _check(params)
        m = prepared.market
        if m is None or len(getattr(m, "shares", ())) == 0 or len(getattr(m, "fundamentals", ())) == 0:
            return ()  # no panel: target nothing (market-aware contract)
        return choose(prepared, members, data_date, p)


QUALITY = QualityTiltedCoreAllocator()


def _v(suffix: str, params: QualityParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0280-{suffix}", family="M0280", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=QUALITY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0280",
    name=(
        "A quality tilt on the market itself: hold the big companies, but lean toward those whose "
        "accounts are improving"
    ),
    family="stock-quality-tilt-core",
    source_kind="variation",
    source_ref=(
        "Piotroski (2000), JAR 38 (supplement) 1-41, via M0276's score; FTSE Russell and MSCI "
        "factor-tilt index method via M0222's frame; M0047's weight ceiling"
    ),
    parent_id="M0276",
    hypothesis=(
        "Published 2000 and widely used in quality indexes since: crowded, so any edge here has "
        "had two decades to fade. M0276 found healthy big companies beat sick ones by 2.9 points "
        "a year in 2010-2015 but its cheap-third, twenty-slot frame cost more than the score "
        "earned, and its check-only book led SPY by 1.2 on the dev store and lost 1.3 once dead "
        "companies came back. The expensive part was leaving SPY's big-company shape. Frame: M0222's "
        "core, the 50 biggest F4-screened index members by point-in-time market value, one class "
        "per company, weighted by that value, no company over 10%. Tilt: each weight x f^power, "
        "f = 0.5 + M0276's health score (fraction of up to eight tests passed, at least six known), "
        "so 0.5 to 1.5, a name with no readable score neutral at 1.0, never dropped; the score "
        "moves once a year so turnover stays the core's own. Until the panel scores 20 of the core "
        "names every arm is the plain core, so the arms differ only from 2010 and the whole-window "
        "row is not promotable by construction; the judgement is the 2010-04 to 2015-10 slice, "
        "de-funded, against SPY total return, and the same slice on the survivorship-check store. "
        "Arms (monthly, fractional, Gotrade fees, target-relative band, deposits): CORE (power 0, "
        "the opinion-free yardstick), HEALTH1, HEALTH2, REVERSE1 (f = 1.5 - score), RAND1 (the day's "
        "real scores handed to hash-drawn core names, redrawn yearly). Predictions, fixed now: (1) "
        "HEALTH1 beats REVERSE1 by at least 1 point a year in the slice; (2) HEALTH1 beats RAND1 "
        "and CORE by at least 0.5; (3) HEALTH1 lands within 1 point of SPY, ahead or behind; (4) "
        "HEALTH2 widens (1) without a deeper worst fall. Success is (1), (2) and HEALTH1 not "
        "trailing SPY, on the dev store and on the survivorship-check store. Assumptions: the "
        "tband preset, as M0222 chose for a 50-name book; unscorable names neutral."
    ),
    expected_failure=(
        "Most likely the tilt is too gentle to read: a 0.5-1.5 factor on a 50-name book moves the "
        "weights by tens of percent of themselves, a few tenths of a point a year, inside the "
        "noise of 66 months, so HEALTH1, CORE and RAND1 are indistinguishable. Second, the core "
        "itself trails SPY (M0222: top-50 +6.3% a year vs SPY +7.2%): it omits SPY's other half, "
        "and fees on fifty names exceed one order, so the arms all lag SPY by about a point and "
        "'within a point' is a stretch. Third, the health score is coarse and annual, and big "
        "companies are analysed to death, so healthy and sick large companies priced alike and "
        "HEALTH1 does not beat REVERSE1. Fourth, from 2009 the dev store prices 74% of members and "
        "the check store restores dead companies, so a thin lead on dev may flip. The whole-window "
        "row carries the core's 45-55% 2008 fall and fails the fall screen whatever the tilt does."
    ),
    candidates=(
        _v("CORE", QualityParams(NOT20, power=0),
           "The yardstick: 50 biggest members at market value, 10% ceiling, no tilt"),
        _v("HEALTH1", QualityParams(NOT20, power=1),
           "Market value x (0.5 + health score): the idea"),
        _v("HEALTH2", QualityParams(NOT20, power=2),
           "Market value x (0.5 + health score) squared: the stronger tilt"),
        _v("REVERSE1", QualityParams(NOT20, power=1, mode="reverse"),
           "The mirror: market value x (1.5 - health score), leaning toward the sick"),
        _v("RAND1", QualityParams(NOT20, power=1, mode="random"),
           "Control: the day's real scores handed to hash-drawn core names, redrawn yearly"),
    ),
    seen_keys=(
        "concept:piotroski-f-score",
        "concept:financial-health-score-in-cheap-third",
        "concept:factor-tilt",
        "concept:random-tilt-control",
        "concept:market-cap-weight",
    ),
)
