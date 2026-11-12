"""M0563 — Industry momentum, value-weighted: hold every member of the winning industries, sized
by their real market value.

Source: Moskowitz & Grinblatt (1999), Do Industries Explain Momentum?, Journal of Finance 54(4).
Idea: the paper's own test is a value-weighted long-short across FF-style industry portfolios
formed on trailing industry return. M0216 already asked whether WHICH member inside a winning
industry matters (its own last-month laggard vs a fixed hash order) and found it did not, losing
to SPY either way in 2009-2015. M0217 already asked whether a dollar-volume-shaped industry MIX
tracks the market's own shape. Neither tried the paper's actual construction: no per-industry slot
cap, no member selection at all -- hold every pool member the winning industries contain, in
proportion to its own market value, the way the index itself is built. Since 2026-10-17 the store
carries point-in-time market value (``Market.market_value``), which M0216/M0217 (both written
before or without it) do not use. This method is that missing construction, not a restatement of
either prior one.

On data date d:

    * the pool is F4's screened members on d (price >= $5, 20-day dollar volume > $20M, enough
      history for the window), the same universe M0216/M0217/M0221 read;
    * each pool member's industry is its Fama-French 12 industry on d
      (``seer_engine.lab.methods.m0216_industry_winners_member_laggards.sector_of``: SEC EDGAR's
      SIC for the filer trading as that ticker on d, M0216's exact mapping). An unknown industry
      is never ranked and never bought;
    * an industry's strength is the equal-weight mean of its pool members' ``inner.mom_n``/
      ``inner.mom_skip`` return (6-1 or 12-1 sessions), only for an industry with at least
      ``MIN_MEMBERS`` (5) pool members on d -- M0216's exact rule, so the industry ranking is
      directly comparable;
    * the ``p.sectors`` strongest industries (``pick="momentum"``) each get an equal 1/sectors
      share of the account. ``pick="hash"`` is the control: the same count of industries, chosen
      by a fixed monthly hash that knows nothing about momentum (M0187's placebo, keyed on the
      industry name and the decision month so the drawn set can rotate the way the real one does);
    * inside a chosen industry, EVERY pool member with a known market value
      (``m0221_cap_weighted_top_n.sized_pool``, one share class per company, the dedupe M0221
      already wrote) is held in proportion to its own market value within that industry's share.
      No per-industry member cap, unlike M0216's fixed 7/7/6 or 5-each slots: the paper's winning
      industry is the whole industry, not a sample of it;
    * no name above ``p.cap`` (10%) of the WHOLE account -- applied once, across every held name in
      every chosen industry together, M0034/M0221's water-filling -- the excess spread over the
      names still under it. This can move money between industries when one industry's biggest
      name is also the account's biggest holding; it is the simplest rule that prevents one company
      from deciding the result, and it is pre-registered here rather than discovered after a run;
    * the money an industry cannot place (no sizeable members, or every one over a cap elsewhere)
      and the money no chosen industry claims when sectors cannot be filled, holds SPY. Cash while
      SPY is under its 200-day average (F4's switch), as every F4-frame book in this lab, except
      the NOSW arm, the third arm with no opinion on the switch.

Why this is not a repeat of a recorded book. M0216's HASH-T3-W6 control already measured "does
picking inside a winning industry matter" with a CAPPED slot count (7/7/6) and EQUAL weight; it
lost to SPY in 2009-2015 same as the laggard arm. This method's real arms hold an uncapped,
VALUE-weighted member set, which is a different number of names, different weights and therefore a
different curve from any recorded M0216 or M0217 trial; the hash control here draws INDUSTRIES
(M0217's axis) rather than MEMBERS (M0216's axis), on this value-weighted construction, which
M0217's own HASH-EQ/HASH-DV controls (dollar-volume or equal industry shares, capped equal-weight
slots inside) do not either. ``lab run`` checks every arm's finished curve against the record
regardless of this reasoning; if any arm still matches a recorded curve, that is the system working
and the arm must be re-declared truthfully rather than renamed.

Assumption, written before any result (M0216's and M0221's, restated together): sector labels are
the filer's latest SIC, which can blur an industry but never leak a price; about 38-43% of pool
member-days have no known market value in 2009-2015 (62-75% coverage per the skill's data note),
mostly the names that later died, so "every member" is every member the store can price, and an
edge that depends on the uncovered half is a question for ``lab survivorship``, not this run.
Members with no known value are excluded from the book but do not block their industry from being
ranked or chosen (the industry STRENGTH calculation uses the full F4-screened pool, exactly
M0216's rule, so the ranking signal is unaffected by which members the store can size).

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by
the contract it targets nothing (M0221's exact pattern). Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees, asked monthly. Pure: no clock, randomness, files or
network in this file; ``sectors`` tables are read once through its own cache; reads only bars and
share counts dated at or before d.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0216_industry_winners_member_laggards import sector_of
from seer_engine.lab.methods.m0221_cap_weighted_top_n import DV_N as TRADE_VALUE_N
from seer_engine.lab.methods.m0221_cap_weighted_top_n import sized_pool
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 11, 12)
MIN_MEMBERS = 5  # pool members an industry needs on d to be ranked (M0216's rule)
PICKS = ("momentum", "hash")


def draw_industry(seed: int, industry: str, data_date: date) -> int:
    """The control's score: a fixed 64-bit hash of seed, industry and the decision's month.

    Keyed on the industry NAME, not a symbol (M0216's ``draw`` keys on symbols; this chooses which
    industries are in the book at all, not which members inside one, so it needs its own
    namespace). A month term lets the drawn set rotate the way the real arm's chosen industries
    do, rather than fixing one blind set for the whole window.
    """
    key = f"M0563|{seed}|{industry}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class CapIndustryParams:
    """``inner`` is F4's screen, switch and industry-momentum window (``mom_n``, ``mom_skip``).

    ``inner.top`` is not read by this allocator (there is no per-industry slot cap and no overall
    holding count: every sizeable member of a chosen industry is held), so it is fixed at 500 by
    every variant below and carries no meaning beyond ``FactorParams``'s own bookkeeping.
    """

    inner: FactorParams
    sectors: int = 3
    pick: str = "momentum"
    cap: float | None = 0.10
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.sectors, bool) or not isinstance(self.sectors, int):
            raise TypeError(f"sectors must be an int, got {type(self.sectors).__name__}")
        if not 1 <= self.sectors <= 12:
            raise ValueError(f"sectors must be in 1..12, got {self.sectors}")
        if self.pick not in PICKS:
            raise ValueError(f"pick must be one of {PICKS}, got {self.pick!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, (int, float)):
                raise TypeError(f"cap must be a number or None, got {type(self.cap).__name__}")
            if not 0.0 < float(self.cap) <= 1.0:
                raise ValueError(f"cap must lie in (0, 1], got {self.cap}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"sectors": str(self.sectors), "pick": self.pick, "seed": str(self.seed),
               "cap": "none" if self.cap is None else repr(float(self.cap)),
               "market": self.market, "min_members": str(MIN_MEMBERS),
               "taxonomy": "ff12-edgar-sic", "trade_value_n": str(TRADE_VALUE_N)}
        if self.pick == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CapIndustryParams:
    if not isinstance(params, CapIndustryParams):
        raise TypeError(f"params must be CapIndustryParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def _weighted_picks(prepared: "CapIndustryPrepared", rows: list[FactorRow], data_date: date,
                     p: CapIndustryParams) -> dict[str, float]:
    """Every sizeable member of the chosen industries, weighted by its own market value within
    its industry's equal share of the account. Pre-ceiling; the cap is applied by the caller."""
    by_ind: dict[str, list[FactorRow]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        ind = sector_of(r.symbol, data_date)
        if ind is None:
            continue
        by_ind.setdefault(ind, []).append(r)
    eligible = [ind for ind, rs in by_ind.items() if len(rs) >= MIN_MEMBERS]
    if not eligible:
        return {}
    if p.pick == "momentum":
        strength = [(-sum(r.momentum for r in by_ind[ind]) / len(by_ind[ind]), ind) for ind in eligible]
        chosen = [ind for _, ind in sorted(strength)[: p.sectors]]
    else:
        chosen = sorted(eligible, key=lambda ind: (draw_industry(p.seed, ind, data_date), ind))[: p.sectors]
    if not chosen:
        return {}
    out: dict[str, float] = {}
    share = 1.0 / len(chosen)
    for ind in chosen:
        members_ind = {r.symbol for r in by_ind[ind]}
        pool = sized_pool(prepared, members_ind, data_date)
        if not pool:
            continue
        total = sum(pool.values())
        for s, v in pool.items():
            out[s] = share * v / total
    return out


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class CapIndustryPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    market: Any = field(default=None, repr=False)  # the Market (share counts), or None


class CapIndustryAllocator:
    """Every sizeable member of the strongest (or a blind draw of) FF12 industries, value-weighted.

    No share counts (history-only path): no size and no targets, as ``CapTopAllocator``."""

    id = "M0563"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), TRADE_VALUE_N)

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

    def _run(self, prepared: CapIndustryPrepared, members: AbstractSet[str], data_date: date,
              p: CapIndustryParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        raw = _weighted_picks(prepared, rows, data_date, p)
        out: list[Target] = []
        invested = Decimal(0)
        if raw:
            symbols = sorted(raw)
            w = np.array([raw[s] for s in symbols], dtype=np.float64)
            if p.cap is not None:
                w = _apply_ceiling(w, float(p.cap))
            for s, wt in zip(symbols, w):
                fw = _floor_weight(float(wt))
                if fw is None:
                    continue
                t = target_from_close(s, last_close(prepared.history[s], data_date), fw)
                if t is not None:
                    out.append(t)
                    invested += fw
        rest = Decimal(1) - invested
        mh = prepared.history.get(p.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(p.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no size and no target."""
        _check(params)
        return ()

    def prepare(self, history: Mapping[str, History]) -> CapIndustryPrepared:
        return CapIndustryPrepared(history, prepare_factor(history), None)

    def prepare_market(self, market: Any) -> CapIndustryPrepared:
        if not hasattr(market, "market_value") or len(market.shares) == 0:
            return CapIndustryPrepared(market.history, prepare_factor(market.history), None)
        return CapIndustryPrepared(market.history, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CapIndustryPrepared):
            raise TypeError(f"prepared must be CapIndustryPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


CAPIND = CapIndustryAllocator()

SW = ("SPY", 200)
W6 = FactorParams(rank="momentum", top=500, mom_n=126, mom_skip=21, trend=SW)
W12 = FactorParams(rank="momentum", top=500, mom_n=252, mom_skip=21, trend=SW)
W6_NOSW = FactorParams(rank="momentum", top=500, mom_n=126, mom_skip=21, trend=None)


def _v(suffix: str, params: CapIndustryParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0563-{suffix}", family="M0563", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPIND, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0563",
    name="Industry momentum, value-weighted: hold every member of the winning industries, sized by market value",
    family="stock-industry-momentum",
    source_kind="paper",
    source_ref="Moskowitz & Grinblatt (1999) Do Industries Explain Momentum?, Journal of Finance 54(4)",
    parent_id=None,
    hypothesis=(
        "Industry momentum lives in the industry, not in picking its members (M0216 already showed "
        "picking does not matter). The paper's own test value-weights whole industry portfolios, "
        "which neither M0216 (equal 7/7/6 or 5-slot caps) nor M0217 (dollar-volume industry mix, "
        "still capped equal-weight slots inside) measured. Each month-end, among F4's screened "
        "members labelled with their Fama-French 12 industry, rank industries with at least 5 "
        "members by the equal-weight mean of their 6-1 or 12-1 return, give the 3 or 4 strongest an "
        "equal share of the account, and inside each hold EVERY member the store can size, weighted "
        "by its own market value, no name above 10% of the whole account. Unfillable money and "
        "unchosen industries hold SPY; cash under SPY's 200-day average. Variants: top-3 vs top-4 "
        "industries, 6-1 vs 12-1 window; RANDOM-T3-W6, the control -- the same count of industries "
        "drawn by a fixed monthly hash that knows nothing about momentum, same value-weighted "
        "construction, which prices the momentum signal apart from simply holding more of the "
        "market through fewer, bigger industry bets; CAP-T3-W6-NOSW, the third arm with no opinion "
        "on the switch, the CAP-T3-W6 book never stepping aside, which prices the 200-day habit on "
        "this exact book shape rather than borrowing M0217's number from a different one. Moskowitz "
        "and Grinblatt published in 1999, so most of the dev window predates the industry-momentum "
        "crowd. Success: beats SPY TR on dev with worst fall <= 25%, PF >= 1.3, a majority of "
        "walk-forward folds, a positive lead over SPY in 2009-2015, and CAP-T3-W6 beats "
        "RANDOM-T3-W6 by at least 2 points a year (the momentum signal must earn its keep over "
        "simply concentrating in fewer, larger industry bets)."
    ),
    expected_failure=(
        "Holding only 3 or 4 industries, even value-weighted, is a concentrated bet: when the "
        "leading industries turn (tech in 2000, financials and energy in 2008) the book is "
        "effectively a handful of giant names and the 200-day switch meets the turn late, so the "
        "worst fall may break 25%. Industry momentum is a well-published 1999 anomaly and 2009-2015 "
        "is the lab's first filter (insight 91's big-company drift); M0216 and M0217's equal-slot "
        "versions of this same family both lost to SPY there, and value-weighting may simply "
        "concentrate the same losing bet into fewer, larger positions rather than fix it. About "
        "38-43% of pool member-days in 2009-2015 have no known market value, mostly the companies "
        "that later died, so the value-weighted book may lean on survivors in a way the equal-slot "
        "versions did not, and `lab survivorship` must separate a real industry effect from a "
        "coverage artefact before any promotion is considered. RANDOM-T3-W6 may beat CAP-T3-W6 "
        "outright: M0216 already found picking does not matter for WHICH member, and the same may "
        "be true for WHICH industry once the book is value-weighted and fully invested either way, "
        "in which case the result is simply fewer, bigger industry bets with no edge from momentum "
        "at all. A momentum-ranked industry rotation is kin of the test-failed momentum books "
        "(hardgate D14) however this method's family is named, and may be refused on kin whatever "
        "it scores on dev."
    ),
    candidates=(
        _v("CAP-T3-W6", CapIndustryParams(W6, sectors=3, pick="momentum"),
           "Top 3 FF12 industries by 6-1 mean member return, hold every sizeable member "
           "value-weighted inside, 10% per-name ceiling across the whole account"),
        _v("CAP-T3-W12", CapIndustryParams(W12, sectors=3, pick="momentum"),
           "Same construction, 12-1 industry window"),
        _v("CAP-T4-W6", CapIndustryParams(W6, sectors=4, pick="momentum"),
           "Top 4 industries, 6-1 window: more spread, smaller industry bet"),
        _v("RANDOM-T3-W6", CapIndustryParams(W6, sectors=3, pick="hash"),
           "Control: 3 industries drawn by a fixed monthly hash, independent of momentum; same "
           "value-weighted construction -- the no-opinion arm for which industries to hold"),
        _v("CAP-T3-W6-NOSW", CapIndustryParams(W6_NOSW, sectors=3, pick="momentum"),
           "Third arm: the CAP-T3-W6 book never stepping aside for SPY's 200-day average -- the "
           "no-opinion arm for when to step aside"),
    ),
    seen_keys=(
        "concept:industry-momentum-value-weighted",
        "concept:industry-momentum",
        "concept:ff12-industry-rotation",
    ),
)
