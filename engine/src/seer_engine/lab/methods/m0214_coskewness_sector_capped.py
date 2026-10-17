"""M0214 — Coskewness with the sector bet taken out: the crash-prone picks, no more than a few from
any one industry.

Source: variation of M0179 (Harvey & Siddique 2000, coskewness), Sera batch 20261017-2050.
Idea: the live coskewness book came out 12 of 20 in oil and gas on 2026-10-17. Coskewness is
measured against the market's squared moves over three years, so a whole industry that fell
together in the last crash week shares a score, and a 20-name book ranked on it can quietly become
one sector. If the dev lead over SPY was that sector bet, capping each Fama-French 12 industry
(``seer_engine.sectors``) should take the lead away; if it was a stock-level premium, it should
survive the cap.

Two ways to take the sector out:

* **cap** -- M0179's ranking and band unchanged, then ``sectors.select_capped`` walks the ranked
  list (held names still under the keep band first, then the rest best first) and skips a name
  whose FF12 industry already holds ``cap`` names. The cap is never relaxed to fill slots; a slot
  it leaves empty holds SPY like every other empty slot in this frame. Held names over the cap
  are sold on a re-pick. Between re-picks the book only loses names, so the cap holds.
* **within** -- sector-neutral: each scoreable member's coskewness is turned into a z-score
  against the other scoreable members of its own FF12 industry that day (mean and population
  standard deviation), and the book ranks on that, so a name is picked for being crash-prone
  *for its industry*. Industries with fewer than ``MIN_SECTOR`` scoreable names are left out of
  the ranking (a z-score over three names is noise), an assumption. The capped fill then spreads
  the slots across industries.

Sector labels are EDGAR's latest SIC per filer, mapped to FF12, read for (symbol, re-pick date);
not point-in-time for a company that changed trade (the module's docstring lists the cases), and
every unknown shares one capped bucket. The map is vendored data loaded once and cached; it reads
no prices and so cannot leak the future.

The control is M0187's hash order (blake2b of seed, symbol, year-month) over the same eligible
pool, capped the same way, so "capped coskewness vs capped random" is the comparison the cap
leaves standing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real
fees, asked monthly.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Any

import numpy as np

from seer_engine import sectors
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0179_coskewness import REPICK_MONTHS, CoskewPrepared, coskewness
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
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

ADDED = date(2026, 10, 17)
MIN_SECTOR = 5  # scoreable names an industry needs before its members get a within-sector z-score
SCORES = ("cosk", "within", "hash")


@lru_cache(maxsize=1)
def sector_map() -> sectors.SectorMap:
    """The vendored FF12 map, loaded once per process."""
    return sectors.load()


def sector_of(symbol: str, on: date) -> str | None:
    return sector_map().sector_of(symbol, on)


@dataclass(frozen=True, slots=True)
class CappedParams:
    """``inner`` is F4's screen, book size and optional switch; ``cap`` the most names one FF12
    industry may hold; ``score`` is ``cosk`` (M0179's rank), ``within`` (z-score inside the
    industry) or ``hash`` (M0187's placebo order, ``seed``); ``keep_pct`` the keep band."""

    inner: FactorParams
    cap: int
    score: str = "cosk"
    seed: int = 1
    keep_pct: int = 40
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("cap", "seed", "keep_pct"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 1 <= self.cap <= self.inner.top:
            raise ValueError(f"cap must be in [1, top], got {self.cap}")
        if self.score not in SCORES:
            raise ValueError(f"score must be one of {SCORES}, got {self.score!r}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"cap": str(self.cap), "score": self.score, "seed": str(self.seed),
               "keep_pct": str(self.keep_pct), "market": self.market,
               "sectors": "ff12-edgar-latest-sic-unknown-shared", "min_sector": str(MIN_SECTOR),
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CappedParams:
    if not isinstance(params, CappedParams):
        raise TypeError(f"params must be CappedParams, got {type(params).__name__}")
    return params


def within_sector(cs: Mapping[str, float], on: date) -> dict[str, float]:
    """Each symbol's coskewness as a z-score inside its FF12 industry (unknowns as one bucket);
    industries with fewer than ``MIN_SECTOR`` names, or no spread, are left out."""
    groups: dict[str, list[str]] = {}
    for s in cs:
        groups.setdefault(sector_of(s, on) or sectors.UNKNOWN, []).append(s)
    out: dict[str, float] = {}
    for names in groups.values():
        if len(names) < MIN_SECTOR:
            continue
        v = np.array([cs[s] for s in names])
        sd = float(v.std())
        if not sd > 0.0:
            continue
        mu = float(v.mean())
        for s, x in zip(names, v):
            out[s] = (float(x) - mu) / sd
    return out


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: CappedParams) -> dict[str, float]:
    """Each rankable symbol's rank fraction in [0, 1): 0 is the first name the book wants."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    cs = coskewness(history, pool, data_date, p.market, False)
    if not cs:
        return {}
    if p.score == "hash":
        key = {s: float(draw(p.seed, s, data_date)) for s in cs}
    elif p.score == "within":
        key = within_sector(cs, data_date)
    else:
        key = cs
    order = sorted(key, key=lambda s: (key[s], s))
    return {s: k / len(order) for k, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: CappedParams) -> tuple[Target, ...]:
    """M0179's ``choose`` with the sector cap applied to the re-pick's ranked list."""
    stocks = sorted(s for s in held if s != p.market and s not in EXCLUDED)
    if not stocks or data_date.month in REPICK_MONTHS:
        frac = scored(history, rows, data_date, p)
        order = [s for _, s in sorted((v, s) for s, v in frac.items())]
        cut = p.keep_pct / 100.0
        kept = sorted((s for s in stocks if frac.get(s, 1.0) < cut), key=lambda s: (frac[s], s))
        picks = sectors.select_capped(kept + order, data_date, p.inner.top, p.cap, sector_of)
    else:  # between re-picks: keep every holding that is still a member with a bar today
        picks = [s for s in stocks if s in members][: p.inner.top]
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        h = history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        t = target_from_close(s, last_close(h, data_date), w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


class CappedCoskewAllocator:
    """M0179's quarterly banded frame, ranked by coskewness (or within-industry coskewness, or a
    hash control), with at most ``cap`` names from any one FF12 industry."""

    id = "M0214"

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {p.market}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_check(params).market,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: CoskewPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CappedParams) -> tuple[Target, ...]:
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        return choose(prepared.history, members, rows, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(CoskewPrepared(history, None), members, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CoskewPrepared:
        return CoskewPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CoskewPrepared):
            raise TypeError(f"prepared must be CoskewPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


CAPPED = CappedCoskewAllocator()

SW = ("SPY", 200)


def _screen(top: int) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=SW)  # the rank is unused: only the screen


def _v(suffix: str, params: CappedParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0214-{suffix}", family="M0214", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPPED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0214",
    name=(
        "Coskewness ranked within each industry: the crash-prone picks with the energy bet "
        "taken out"
    ),
    family="stock-coskewness",
    source_kind="variation",
    source_ref="variation of M0179 (Harvey & Siddique 2000); FF12 sectors from SEC EDGAR",
    parent_id="M0179",
    hypothesis=(
        "The live coskewness book came out 12 of 20 in oil and gas on 2026-10-17. Coskewness "
        "(Harvey & Siddique, published 2000) is a co-movement with the market's big weeks, so "
        "whole industries share a score and the book can become one sector. Test whether "
        "coskewness's dev lead over SPY was a hidden sector bet. Same frame as M0179 (F4's "
        "$5/$20M screen, three years of weekly returns, quarterly re-pick, 40% keep band, empty "
        "slots in SPY, SPY 200-day switch, fractional shares at Gotrade's real fees on the "
        "owner's deposits), with Fama-French 12 sectors from SEC EDGAR (latest SIC, not point in "
        "time; unknowns share one capped bucket) and the cap never relaxed (a slot it leaves "
        "empty holds SPY). Variants: C3-20 and C4-20 (the 20 most negative, at most 3 or 4 per "
        "industry), W2-20 (sector-neutral: z-score of coskewness inside its own industry, "
        "industries under 5 scoreable names left out, at most 2 per industry so the slots spread "
        "across industries), C6-40 (the 40-name rung that was M0179's eligible variant, at most 6 "
        "per industry, the same 15% share as 3 of 20), and the controls H3-20 and H6-40 (M0187's "
        "fixed hash order over the same eligible pool, capped the same way). Success: a capped "
        "coskewness variant beats total-return SPY with worst fall <= 25%, PF >= 1.3, DSR >= 0.90, "
        "a majority of walk-forward folds and a positive 2009-2015 edge, and beats its capped "
        "hash control clearly. The sector mix of the uncapped book is measured outside the run."
    ),
    expected_failure=(
        "M0179's control (the most positive coskewness) and M0187's hash placebo earned about as "
        "much as the idea, so the frame, not the ranking, did most of the beating, and the cap "
        "cannot change that: the capped books land within a point a year of their hash controls. "
        "Taking out the sector bet removes the energy and financials runs that carried the "
        "uncapped book, so the capped books lose some of M0179's lead and still trail SPY in "
        "2009-2015 (M0179 was -4 to -6 points a year there); the within-industry z-score is "
        "noisier still. The coskewness family already sits at 2 of 4 folds, and an equal-weight "
        "book of index members leans small against SPY's big-company drift."
    ),
    candidates=(
        _v("C3-20", CappedParams(_screen(20), cap=3),
           "The 20 most negative-coskewness members, at most 3 per FF12 industry, behind the switch"),
        _v("C4-20", CappedParams(_screen(20), cap=4),
           "The same book with at most 4 per industry"),
        _v("W2-20", CappedParams(_screen(20), cap=2, score="within"),
           "Sector-neutral: coskewness z-scored inside its own industry, at most 2 per industry"),
        _v("C6-40", CappedParams(_screen(40), cap=6),
           "The 40-name rung (M0179's eligible variant) with at most 6 per industry"),
        _v("H3-20", CappedParams(_screen(20), cap=3, score="hash"),
           "Control: the same eligible pool in a fixed hash order, at most 3 per industry"),
        _v("H6-40", CappedParams(_screen(40), cap=6, score="hash"),
           "Control: the 40-name hash-order book, at most 6 per industry"),
    ),
    seen_keys=(
        "concept:coskewness",
        "concept:sector-cap",
        "concept:sector-neutral-rank",
    ),
)
