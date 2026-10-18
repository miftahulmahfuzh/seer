"""M0227 — Companies shrinking their share count: the index members that bought back the most stock.

Source: Pontiff & Woodgate (2008), "Share Issuance and Cross-Sectional Returns", Journal of
Finance 63(2) 921-945 (https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html); Daniel &
Titman (2006) composite issuance; McLean & Pontiff (2016) on post-publication decay. Reserved by
Sera batch 20261018-2051 as an ``idea`` row; this file refines it and keeps its id.

Why it can run only now. The effect ranks on the change in shares outstanding, and until
2026-10-17 the store had no share counts at all. It now carries the count each company filed, public
from its filing date, restated across splits (``Market.shares``), from 1996 on, and per listed share
class from 2009. A twelve-month change needs a year of counts, so the book starts trading in 1997.

How. On each monthly check, for every index member with a bar dated ``data_date``: take the count
public that day (``ShareCounts.count``) and the count public 365 calendar days earlier. The old
count is carried into today's share units through every split between them
(``ShareCounts.split_factor``), so a two-for-one does not read as a doubling. The signal is the
log of new over carried-old: negative for a company that shrank its share count (buybacks), positive
for one that issued (offerings, stock-paid deals, option grants). A member is scored only when the
two figures were counted at least 180 days apart -- a company whose newest filing is still the one
from a year ago tells us nothing -- and when the ratio does not sit within 3% of a common split
ratio (2, 3, 4, 3/2 or their inverses). That guard is the pre-registered defence against a split the
store's split table missed, which would otherwise read as a 50% buyback or a 100% issue. It also
catches Alphabet's 2014 class split (the GOOG line drops from the whole company to class C alone).
A ratio outside 0.5-3.0 is skipped as well: no company buys back half its stock in a year, and the
coverage check run before this file was committed (pool sizes only, no returns) found a handful of
readings a thousand-fold off -- a filing stated in thousands where the next is in units -- that would
otherwise sit at the top of the shrink or issue list.
Two members answering the identical share count on the same day are one company listed twice
(GOOG/GOOGL before 2014-04-03); only the one with the larger 60-session trading value is kept.

Arms. ``side="shrink"`` holds the ``top`` most-negative scores (the biggest shrinkers);
``side="issue"`` the ``top`` most-positive (the biggest issuers: the opposite book the paper says
should lag); ``side="random"`` the placebo: ``top`` names from the same scored pool in a fixed hash
order of (seed, symbol), so it shares the pool and its gaps but knows nothing about the signal.
Equal slots, fully invested. ``trend=("SPY", 200)`` holds nothing while SPY closes at or below its
200-day average (``f_factor.trend_on``).

Assumptions written before any result. The dev window ends 2015-10-16, so the book trades
1997-2015, of which 1997-2008 is before and around the paper's publication. Share-count coverage is
thin early (about 57% of dev member-days carry a size, most of the gap being members with no bars),
so the pool is the members the store can both price and count. A held name whose count goes stale
is not held any more on the next check: it drops out of the pool and the book sells it.

Market-aware (``market_fields = ("shares",)``): the history-only path has no share counts, so by the
contract it targets nothing. Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's
real fees, asked monthly, on the owner's monthly top-up. Pure: reads only bars and counts public on
or before ``data_date``.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0198_size_weighted_placebo import trading_value
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorParams, trend_on

ADDED = date(2026, 10, 18)
LOOKBACK_DAYS = 365  # calendar days between the two counts compared
MIN_COUNT_GAP_DAYS = 180  # the two figures must have been counted at least this far apart
DV_N = 60  # sessions of trading value that decide which listing of one company stays
SPLIT_RATIOS = (2.0, 3.0, 4.0, 1.5, 0.5, 1.0 / 3.0, 0.25, 2.0 / 3.0)
SPLIT_TOLERANCE = 0.03  # a ratio within 3% of one of SPLIT_RATIOS is read as a missed split
RATIO_BAND = (0.5, 3.0)  # a one-year ratio outside this is read as a units error in a filing
SIDES = ("shrink", "issue", "random")


@dataclass(frozen=True, slots=True)
class IssuanceParams:
    """``top`` names held; ``side`` shrink, issue or random (the placebo); ``seed`` the placebo's
    hash seed; ``trend`` the switch, (symbol, n) or None, set by every variant."""

    top: int
    side: str = "shrink"
    seed: int = 0
    trend: tuple[str, int] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top, bool) or not isinstance(self.top, int) or not 1 <= self.top <= 200:
            raise ValueError(f"top must be an int in [1, 200], got {self.top!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative int, got {self.seed!r}")
        FactorParams(rank="momentum", top=self.top, trend=self.trend)  # validates the switch

    def as_dict(self) -> dict[str, str]:
        return {"top": str(self.top), "side": self.side, "seed": str(self.seed),
                "trend": "none" if self.trend is None else f"{self.trend[0]}:{self.trend[1]}",
                "lookback_days": str(LOOKBACK_DAYS), "min_count_gap_days": str(MIN_COUNT_GAP_DAYS),
                "split_tolerance": repr(SPLIT_TOLERANCE),
                "ratio_band": f"{RATIO_BAND[0]!r}:{RATIO_BAND[1]!r}", "dv_n": str(DV_N),
                "class_rule": "identical-share-count"}


def _check(params: object) -> IssuanceParams:
    if not isinstance(params, IssuanceParams):
        raise TypeError(f"params must be IssuanceParams, got {type(params).__name__}")
    return params


def _gate(p: IssuanceParams) -> FactorParams:
    return FactorParams(rank="momentum", top=p.top, trend=p.trend)


def draw(seed: int, symbol: str) -> int:
    """The placebo's fixed order: a hash of (seed, symbol) that knows nothing about the market."""
    key = f"M0227|{seed}|{symbol}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def looks_like_split(ratio: float) -> bool:
    """True when ``ratio`` sits within ``SPLIT_TOLERANCE`` of a common split ratio."""
    return any(abs(ratio / r - 1.0) <= SPLIT_TOLERANCE for r in SPLIT_RATIOS)


@dataclass(frozen=True, slots=True, eq=False)
class IssuancePrepared:
    history: Mapping[str, History]
    market: Any  # the Market (share counts), or None on the history-only path


def issuance(market: Any, symbol: str, data_date: date) -> float | None:
    """Log change in ``symbol``'s split-adjusted share count over the last year, or None."""
    then = data_date - timedelta(days=LOOKBACK_DAYS)
    shares = market.shares
    now_c, old_c = shares.count(symbol, data_date), shares.count(symbol, then)
    if now_c is None or old_c is None:
        return None
    if (now_c.counted - old_c.counted).days < MIN_COUNT_GAP_DAYS:
        return None
    now_n, old_n = shares.shares_on(symbol, data_date), shares.shares_on(symbol, then)
    if now_n is None or old_n is None or not (now_n > 0.0 and old_n > 0.0):
        return None
    ratio = now_n / (old_n * shares.split_factor(symbol, then, data_date))
    if not math.isfinite(ratio) or not RATIO_BAND[0] < ratio < RATIO_BAND[1] or looks_like_split(ratio):
        return None
    return math.log(ratio)


def scored_pool(prepared: IssuancePrepared, members: AbstractSet[str], data_date: date) -> dict[str, float]:
    """The issuance score of every member that can be held on ``data_date``, one listing per company."""
    mk = prepared.market
    if mk is None:
        return {}
    by_count: dict[float, tuple[float, str, float]] = {}
    for s in sorted(members):
        if s in EXCLUDED:
            continue
        h = prepared.history.get(s)
        if h is None or h.index_of(data_date) is None:
            continue
        score = issuance(mk, s, data_date)
        if score is None:
            continue
        n = mk.shares_on(s, data_date)
        dv = trading_value(h, data_date, DV_N)
        seen = by_count.get(n)
        if seen is None or (dv, s) > (seen[0], seen[1]):
            by_count[n] = (dv, s, score)
    return {s: score for _, s, score in by_count.values()}


class IssuanceAllocator:
    """The ``top`` members with the biggest twelve-month fall (or rise, or a size-blind hash draw)
    in split-adjusted shares outstanding, equal slots, fully invested; nothing while the switch,
    if any, is off. No share counts (history-only path): no targets."""

    id = "M0227"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(DV_N, 0 if p.trend is None else p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return ("SPY",) if p.trend is None else tuple(sorted({"SPY", p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: IssuancePrepared, members: AbstractSet[str], data_date: date,
             p: IssuanceParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        pool = scored_pool(prepared, members, data_date)
        if not pool:
            return ()
        if p.side == "shrink":
            order = sorted(pool, key=lambda s: (pool[s], s))
        elif p.side == "issue":
            order = sorted(pool, key=lambda s: (-pool[s], s))
        else:
            order = sorted(pool, key=lambda s: (draw(p.seed, s), s))
        w = equal_weight(p.top)
        out: list[Target] = []
        for s in order[: p.top]:
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no signal and no target."""
        return self._run(IssuancePrepared(history, None), members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> IssuancePrepared:
        return IssuancePrepared(history, None)

    def prepare_market(self, market: Any) -> IssuancePrepared:
        if not hasattr(market, "shares") or len(market.shares) == 0:
            return IssuancePrepared(market.history, None)
        return IssuancePrepared(market.history, market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IssuancePrepared):
            raise TypeError(f"prepared must be IssuancePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, _check(params))


ISSUANCE = IssuanceAllocator()

SW = ("SPY", 200)


def _v(suffix: str, params: IssuanceParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0227-{suffix}", family="M0227", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ISSUANCE, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0227",
    name=(
        "Companies shrinking their share count: buy the index members that bought back the most "
        "stock over the past year"
    ),
    family="stock-net-share-issuance",
    source_kind="paper",
    source_ref=(
        "Pontiff & Woodgate (2008) JF 63(2) 921-945, "
        "https://ideas.repec.org/a/bla/jfinan/v63y2008i2p921-945.html; Daniel & Titman (2006) "
        "composite issuance; McLean & Pontiff (2016) decay"
    ),
    parent_id=None,
    hypothesis=(
        "Firms that reduce their shares outstanding (buybacks) beat firms that issue shares, a "
        "published effect (Pontiff and Woodgate 2008; Daniel and Titman 2006) the lab can test only "
        "now that the store carries point-in-time share counts from SEC filings (from 1996, per "
        "listed class from 2009). Each month, for every index member with a bar that day, compare "
        "the share count public today with the one public 365 days ago, carried across splits, and "
        "score the log change; skip a member whose two figures were counted under 180 days apart or "
        "whose ratio sits within 3% of a common split ratio (a missed split) or outside 0.5-3.0 (a units "
        "error in a filing), and keep one listing "
        "per company. Book: the 20 biggest shrinkers, equal slots, monthly, fractional shares at "
        "Gotrade's real fees on the owner's monthly top-up (monthly-hold-frac-gotrade). Arms: S20 "
        "(no switch), S20-SW (behind the SPY 200-day switch), S40 (the 40 biggest shrinkers, broader "
        "and closer to the market), I20 (the 20 biggest issuers, the opposite book) and R20 (20 "
        "names from the same scored pool in a fixed hash order: the placebo of the same size). "
        "Window: 1997-2015 (a year of counts first). Predictions written before any result: S20 "
        "beats I20 by 2 or more points a year and beats R20; S20 beats total-return SPY over "
        "1997-2015 by a point or two, mostly from 2000-2008 when issuers (the dot-com offerings) "
        "collapsed; in 2009-2015 the gap over SPY shrinks to about zero. S20-SW cuts the 2008 fall "
        "under the 20% limit but gives back return to whipsaws. Published 2008, so the dev window "
        "straddles publication: expect the edge after 2008 to be smaller."
    ),
    expected_failure=(
        "Four ways, in order of likelihood. (1) The buyback tilt is a disguised big-mature-company "
        "tilt that tracks SPY with an equal-weight drag, so S20 lands near R20 and both lag SPY "
        "after 2009 -- the lab's usual 2009-2015 shortfall -- and the issuer book is the only one "
        "that differs (it lags). (2) Data, not markets: share-count gaps sit on the firms the store "
        "cannot see (the dead ones, which were disproportionately heavy issuers), so I20 looks "
        "better than it was and the shrink-minus-issue spread is understated; a split the guard "
        "does not catch (a 5-for-4, say) puts a false issuer or shrinker in the book now and then. "
        "(3) The 2008 fall: shrinkers in 2007-2008 included the banks that bought back stock right "
        "before collapsing, so without the switch the worst fall is near SPY's and breaks the 20% "
        "limit. (4) Decay: the anomaly was public from 2006-2008 and buybacks became the default way "
        "for US companies to return cash, so the signal is crowded by 2010 and the 2009-2015 era "
        "shows nothing. Any of these is a rejection; none is a reason to tune the 365-day window "
        "or the guards afterwards."
    ),
    candidates=(
        _v("S20", IssuanceParams(20, trend=None),
           "The 20 members with the biggest one-year fall in split-adjusted shares, no switch"),
        _v("S20-SW", IssuanceParams(20, trend=SW),
           "The same 20 biggest shrinkers behind the SPY 200-day switch"),
        _v("S40", IssuanceParams(40, trend=None),
           "Broader: the 40 biggest shrinkers, no switch"),
        _v("I20", IssuanceParams(20, side="issue", trend=None),
           "Opposite: the 20 biggest issuers of new shares, no switch"),
        _v("R20", IssuanceParams(20, side="random", seed=1, trend=None),
           "Placebo: 20 names from the same scored pool in a fixed hash order, no switch"),
    ),
    seen_keys=(
        "concept:net-share-issuance",
        "concept:buyback-shrinkers",
    ),
)
