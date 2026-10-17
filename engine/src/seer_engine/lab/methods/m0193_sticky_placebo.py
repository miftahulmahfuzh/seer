"""M0193 — A sticky placebo: the coskewness frame in a fixed hash order that is never re-drawn.

Source: variation of M0187 (the placebo yardstick), Sera batch 20261017-1808. Not a strategy. A
second yardstick.

Why it exists. M0187 filled the frame M0174, M0179 and M0184 share (F4's member screen, 20 names
at equal weight, quarterly re-picks, a 40% keep band, unfilled slots in SPY, optionally the SPY
200-day switch) in the order of a hash of seed, symbol **and re-pick month**. It matched the
coskewness books (+10.3% to +11.0% a year funded behind the switch) while trading about 60% more
than they did, because a hash re-drawn every quarter keeps only about 40% of the book. One frame
book still sits two points above it: the low-correlation book (M0174-C20-SW, +13.3% a year, about
250 trades against the placebo's 813-833). Its lead may be the ranking, or only that a sticky
signal trades less and so pays Gotrade less.

This method separates the two. The hash is of seed and symbol only, so every symbol keeps one
place in the order for the whole window. A holding then leaves only when it drops out of the
index, fails the screen, or new eligible members with lower hashes push it past the 40% band:
turnover close to a sticky real signal, still no price information. Everything else is M0187's
frame byte for byte: the same ``PlaceboParams``, M0179's eligibility (a member it could score), the
same band, SPY slots and switch, reached through M0187's allocator with only the draw replaced.

A side effect worth naming: a fixed order is a fixed *set* of companies, so a seed can be lucky
or unlucky in which twenty names it happens to hold for years. Three seeds at 20 names make that
spread visible; the 40-name rung shows how much of it averages away.

Pure: the hash is a function of its inputs, no clock and no run-time randomness. Every variant sets
``trend`` explicitly (the ``FactorParams`` default is the SPY 200-day switch).

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, asked monthly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0179_coskewness import REPICK_MONTHS, CoskewPrepared, coskewness
from seer_engine.lab.methods.m0187_placebo_hash_order import PlaceboAllocator, PlaceboParams, _check
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_rows,
    trend_on,
)

ADDED = date(2026, 10, 17)


def draw(seed: int, symbol: str) -> int:
    """The sticky placebo's score: a fixed 64-bit hash of seed and symbol, the same every date."""
    return int.from_bytes(hashlib.blake2b(f"{seed}|{symbol}".encode(), digest_size=8).digest(), "big")


def scored(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
           p: PlaceboParams) -> dict[str, float]:
    """M0187's ``scored`` with the month taken out of the hash."""
    pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != p.market)
    eligible = coskewness(history, pool, data_date, p.market, False)
    if not eligible:
        return {}
    order = sorted(eligible, key=lambda s: (draw(p.seed, s), s))
    return {s: k / len(order) for k, s in enumerate(order)}


def choose(history: Mapping[str, History], members: AbstractSet[str], rows: list[FactorRow],
           data_date: date, held: frozenset[str], p: PlaceboParams) -> tuple[Target, ...]:
    """M0187's ``choose`` with the sticky ``scored``."""
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


class StickyPlaceboAllocator(PlaceboAllocator):
    """M0187's frame and pool in one fixed hash order for the whole window."""

    id = "M0193"

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


STICKY = StickyPlaceboAllocator()

SW = ("SPY", 200)


def _screen(top: int, trend: tuple[str, int] | None) -> FactorParams:
    return FactorParams(rank="momentum", top=top, trend=trend)  # the rank is unused: only the screen


def _v(suffix: str, params: PlaceboParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0193-{suffix}", family="M0193", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=STICKY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0193",
    name="A sticky placebo: the same frame in a fixed random order that is not re-drawn each quarter, 20 and 40 names",
    family="placebo-hash-order",
    source_kind="variation",
    source_ref="variation of M0187 (the placebo yardstick of the M0174/M0179/M0184 frame); Sera batch 20261017-1808",
    parent_id="M0187",
    hypothesis=(
        "The quarterly re-drawn placebo (M0187) traded about 60% more than the coskewness books "
        "and still matched them; the low-correlation book (M0174-C20-SW, +13.3% a year funded, "
        "about 250 trades) sits two points above the placebo's +10.3 to +11.0%. Hash seed and "
        "symbol only (no month), so a holding stays while its fixed place keeps it in the 40% "
        "band, giving turnover close to a sticky real signal (expected 150-350 trades at 20 "
        "names). Seeds 1-3 at 20 names behind the SPY 200-day switch, one 40-name rung behind the "
        "switch, and seed 1 at 20 names with trend explicitly None as the no-switch rung; "
        "fractional shares at Gotrade's real fees on the owner's 5M IDR monthly top-up. If the "
        "sticky placebo rises to about +12-13% funded, the low-correlation book's lead is low "
        "turnover, not correlation, and the frame's yardstick moves up; if it stays near +10.5%, "
        "low correlation carries something the frame does not. Each variant's beta to SPY is "
        "recorded beside it. Not a published anomaly; the frame's lead is the equal-weight, "
        "smaller-company lean of 1996-2008 (insight 91). Never to be promoted: it is evidence."
    ),
    expected_failure=(
        "A fixed order is a fixed set of about twenty companies held for years, so the three "
        "seeds may spread far wider than M0187's (one seed lands on a few big winners, another "
        "on a few that languish): the yardstick then becomes too wide to say anything about a "
        "two-point gap, and only the 40-name rung reads cleanly. Turnover may also not fall as "
        "much as hoped, because index membership changes and the screen still churn the book. "
        "Expect every switched seed to trail SPY in 2009-2015 like M0187, and the unswitched rung "
        "to fall about 50% in 2008."
    ),
    candidates=(
        _v("S1-SW", PlaceboParams(_screen(20, SW), seed=1),
           "Fixed hash order, seed 1, 20 names, behind the SPY 200-day switch"),
        _v("S2-SW", PlaceboParams(_screen(20, SW), seed=2),
           "Fixed hash order, seed 2, 20 names, behind the SPY 200-day switch"),
        _v("S3-SW", PlaceboParams(_screen(20, SW), seed=3),
           "Fixed hash order, seed 3, 20 names, behind the SPY 200-day switch"),
        _v("S1-40-SW", PlaceboParams(_screen(40, SW), seed=1),
           "Fixed hash order, seed 1, 40 names, behind the SPY 200-day switch"),
        _v("S1", PlaceboParams(_screen(20, None), seed=1),
           "Fixed hash order, seed 1, 20 names, no switch (trend explicitly None)"),
    ),
    seen_keys=(
        "concept:sticky-placebo-frame",
        "concept:placebo-turnover-control",
    ),
)
