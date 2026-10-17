"""M0187 — A placebo book: the coskewness frame filled in a fixed, meaningless order.

Source: variation of M0184 (and of the frame M0174, M0179 and M0184 share), Sera batch
20261017-1752. Not a strategy. A yardstick.

Why it exists. Three batches in a row (the low-correlation book, the coskewness book, the
beta-matched coskewness book) each carried a paired control -- the opposite end of its own
ranking -- and each control earned about as much as the idea. When both ends of a ranking beat
SPY by the same margin, the ranking is not what beat SPY: the frame did. The frame is F4's member
screen ($5 close, $20M trading value), 20 names at equal weight, re-picked on the last close of
March, June, September and December, a held name kept while its rank fraction stays under 40%,
unfilled slots in SPY, and optionally the whole book in cash under SPY's 200-day average.

This method keeps that frame byte for byte (M0179's ``choose`` path: the same eligibility, the same
band, the same SPY slots, the same switch) and replaces the score with a hash. On a re-pick date,
each eligible member's rank fraction comes from blake2b(seed | symbol | year-month): a fixed,
reproducible order that knows nothing about prices. Eligibility is M0179's exactly -- a member is
ranked only if it has a bar dated d and closes back past the three-year weekly window's first date
-- by reading which names M0179's coskewness function can score, so the placebo draws from the
same pool the coskewness books drew from, new listings excluded the same way. The hash is
re-drawn each quarter, so a held name stays with probability about 40% per re-pick, which is
roughly the turnover a noisy real signal produces under the same band (an assumption: a real
signal is stickier than chance, so the placebo trades somewhat more).

Pure: the hash is a function of its inputs, no clock and no run-time randomness. Several seeds
are run as variants so the result is a spread, not one lucky draw.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0179_coskewness import REPICK_MONTHS, CoskewPrepared, coskewness
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


@dataclass(frozen=True, slots=True)
class PlaceboParams:
    """``inner`` is F4's screen, book size and optional switch; ``seed`` picks the hash order;
    ``keep_pct`` the rank fraction (in percent) a holding must stay under."""

    inner: FactorParams
    seed: int = 1
    keep_pct: int = 40
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("seed", "keep_pct"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 0 < self.keep_pct <= 100:
            raise ValueError(f"keep_pct must be in (0, 100], got {self.keep_pct}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"seed": str(self.seed), "keep_pct": str(self.keep_pct), "market": self.market,
               "hash": "blake2b-8", "eligibility": "m0179-coskewness",
               "repick_months": ",".join(str(m) for m in REPICK_MONTHS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> PlaceboParams:
    if not isinstance(params, PlaceboParams):
        raise TypeError(f"params must be PlaceboParams, got {type(params).__name__}")
    return params


def draw(seed: int, symbol: str, data_date: date) -> int:
    """The placebo's score: a fixed 64-bit hash of seed, symbol and the re-pick's month."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: PlaceboParams) -> dict[str, float]:
    """Each eligible symbol's rank fraction in [0, 1) in hash order. Eligible means M0179 could
    score it on ``data_date`` (the coskewness value itself is discarded)."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    eligible = coskewness(history, pool, data_date, p.market, False)
    if not eligible:
        return {}
    order = sorted(eligible, key=lambda s: (draw(p.seed, s, data_date), s))
    return {s: k / len(order) for k, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: PlaceboParams) -> tuple[Target, ...]:
    """M0179's ``choose`` with the placebo's ``scored``."""
    stocks = sorted(s for s in held if s != p.market and s not in EXCLUDED)
    if not stocks or data_date.month in REPICK_MONTHS:
        frac = scored(history, rows, data_date, p)
        order = [s for _, s in sorted((v, s) for s, v in frac.items())]
        cut = p.keep_pct / 100.0
        kept = sorted((s for s in stocks if frac.get(s, 1.0) < cut), key=lambda s: (frac[s], s))
        picks = kept[: p.inner.top]
        for s in order:
            if len(picks) >= p.inner.top:
                break
            if s not in picks:
                picks.append(s)
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


class PlaceboAllocator:
    """The coskewness frame's screened members in a fixed hash order, quarterly, banded."""

    id = "M0187"

    def lookback(self, params: Any) -> int:
        # As M0179: the screen's and the switch's need only. A member without the three-year
        # window is not eligible yet and its slot holds SPY.
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
             held: frozenset[str], p: PlaceboParams) -> tuple[Target, ...]:
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


PLACEBO = PlaceboAllocator()


def _screen(top: int, trend: tuple[str, int] | None = None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: PlaceboParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0187-{suffix}", family="M0187", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=PLACEBO, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


SW = ("SPY", 200)

METHOD = Method(
    id="M0187",
    name="A placebo book: the same 20-name quarterly frame filled in a fixed meaningless order",
    family="placebo-hash-order",
    source_kind="variation",
    source_ref="variation of M0184 (the frame of M0174, M0179, M0184); Sera batch 20261017-1752",
    parent_id="M0184",
    hypothesis=(
        "The last three batches (low correlation, coskewness, beta-matched coskewness) each had a "
        "paired control that earned as much as the idea, which says the frame -- F4-screened "
        "index members, 20 at equal weight, quarterly re-picks, a 40% keep band, unfilled slots "
        "in SPY -- delivers the lead over SPY on its own. Fill exactly that frame (M0179's "
        "eligibility and choose path) in the order of a fixed hash of seed, symbol and re-pick "
        "month: pure, no run-time randomness, no price information. Three seeds, each with and "
        "without the SPY 200-day switch, fractional shares at Gotrade's real fees on the owner's "
        "monthly top-up. Expected: every seed beats total-return SPY over 1996-2015 by about as "
        "much as the coskewness and correlation books (M0179-N20, M0184-T20 and their controls), "
        "and trails SPY in 2009-2015. If so the lab gets a standing yardstick: a ranking must beat "
        "the placebo's spread of seeds, not SPY alone, and a method whose dev lead sits inside "
        "that spread is the frame, not an edge. Not a published anomaly; the frame's lead is the "
        "equal-weight, smaller-company lean of 1996-2008 (insight 91). Never to be promoted: it "
        "is evidence, and a placebo that clears the gate is a finding about the gate."
    ),
    expected_failure=(
        "The 'failure' that matters is the placebo landing well below the coskewness and "
        "correlation books: then those rankings did carry something and the paired controls were "
        "a second, different signal rather than noise. A smaller risk: the seeds spread so widely "
        "(a 20-name random book over twenty years) that the yardstick is too wide to reject "
        "anything, which would say 20 names is too few to tell signal from luck at all. The "
        "placebo turns over more than a sticky real signal (a hash re-drawn each quarter keeps "
        "about 40% of holdings), so it pays somewhat more in fees and may trail the frame's real "
        "books by that cost alone. Expect a worst fall near 50% without the switch, like M0179-N20."
    ),
    candidates=(
        _v("H1", PlaceboParams(_screen(20), seed=1),
           "Hash order, seed 1, 20 names, no switch"),
        _v("H2", PlaceboParams(_screen(20), seed=2),
           "Hash order, seed 2, 20 names, no switch"),
        _v("H3", PlaceboParams(_screen(20), seed=3),
           "Hash order, seed 3, 20 names, no switch"),
        _v("H1-SW", PlaceboParams(_screen(20, SW), seed=1),
           "Hash order, seed 1, behind the SPY 200-day switch"),
        _v("H2-SW", PlaceboParams(_screen(20, SW), seed=2),
           "Hash order, seed 2, behind the SPY 200-day switch"),
        _v("H3-SW", PlaceboParams(_screen(20, SW), seed=3),
           "Hash order, seed 3, behind the SPY 200-day switch"),
    ),
    seen_keys=(
        "concept:placebo-frame",
        "concept:hash-order-yardstick",
    ),
)
