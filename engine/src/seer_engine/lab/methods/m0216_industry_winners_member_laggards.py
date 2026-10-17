"""M0216 — Winning industries, lagging members: last month's laggards inside the strongest industries.

Source: Moskowitz & Grinblatt (1999), Do Industries Explain Momentum?, Journal of Finance 54(4);
Hameed & Mian (2015), Industries and Stock Return Reversals, JFQA 50(1-2); Li & Turkington,
Mapping Momentum (S&P 500).
Idea: two findings pull in opposite directions on the same stock. Momentum lives mostly at the
industry level -- a stock's winning streak is largely its industry's -- while over a single month
a stock *reverses* against its own industry: a name that lagged its peers last month, with no
industry-wide news behind the lag, tends to catch up. So: pick the strongest industries by their
members' 6- or 12-month return (skipping the last month), and inside them buy the members that
lagged their industry the most last month. The book rides the industry trend and buys its members
on a temporary dip, rather than buying the most-extended names as a plain momentum book does.

On data date d:

    * the pool is F4's screened members on d (price >= $5, 20-day dollar volume > $20M, enough
      history for the window), exactly the names every F4-frame book may buy;
    * each pool member's industry is its Fama-French 12 industry on d (``seer_engine.sectors``:
      SEC EDGAR's SIC for the filer trading as that ticker on d). A member with no known industry
      is not in any industry, is never ranked as one and is never bought -- ``Unknown`` is a gap in
      the data, not a line of business;
    * an industry's strength is the equal-weight mean of its pool members' ``W``-1 return
      (``inner.mom_n`` = 126 or 252 sessions, skip 21), only for an industry with at least
      ``MIN_MEMBERS`` (5) pool members on d, so one or two names cannot make an industry;
    * the ``sectors`` strongest industries each get an equal share of the 20 slots (top 3: 7, 7,
      6, the extra slot to the stronger industry; top 4: 5 each);
    * inside an industry, members are ordered by last month's return (close d over close 21
      sessions back) minus their industry's mean of the same, lowest first. The industry mean is
      one number per industry, so the order inside an industry is the raw one-month order; the
      relative form is written out because it is what the papers rank on;
    * every slot is 1/20; a slot the industry cannot fill, and every slot when no industry ranks,
      holds SPY. Cash while SPY is under its 200-day average (F4's switch), as M0203/M0208.

No band: the reversal is a one-month signal, so last month's laggard that bounced is no longer a
laggard, and holding it on would hold a stale signal. Every month the book is re-picked.

Sector cap. The book is capped by construction: no more than ceil(20/sectors) names (7 or 5) from
any one FF12 industry. ``sectors.select_capped`` is not called because the allotment is exact
per industry rather than a cap over one global ranking; the rule it encodes -- unknowns share one
bucket, an unfilled slot stays out of the book -- is kept (unknowns are simply never picked, and
an unfilled slot is SPY rather than cash, as in the F4-frame books).

``order``: ``"laggard"`` is the method; ``"hash"`` is the control the reserved idea asked for --
the same industries, the same allotment, the same switch, members ordered by
blake2b(seed | symbol | year-month) (M0187's placebo). The gap between the two is what picking
last month's laggards adds over a plain industry-rotation book.

Assumption, written before the run: the reserved idea names the FF12 labels as "latest SIC only,
not point-in-time"; ``sectors`` maps the ticker to its filer point in time and the filer to its
latest SIC, so a filer that changed trade reads as its end state for its whole history (the
module's docstring names the cases). This can only blur an industry, never leak a price.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees on the owner's
monthly deposits. Pure: no clock, randomness, files or network in this file; the vendored sector
tables are read once through ``sectors.load``; reads only bars dated at or before d.
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine import sectors
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
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

ADDED = date(2026, 10, 17)
REV_N = 21  # last month, in sessions: the reversal window
MIN_MEMBERS = 5  # pool members an industry needs on d to be ranked
ORDERS = ("laggard", "hash")


@functools.cache
def _sector_map() -> sectors.SectorMap:
    return sectors.load()


def sector_of(symbol: str, on: date) -> str | None:
    return _sector_map().sector_of(symbol, on)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class IndustryParams:
    """``inner`` is F4's screen, switch, book size and industry window (``mom_n``, ``mom_skip``).

    ``inner.rank`` never selects here; ``"momentum"`` keeps the screened universe identical to
    M0007's and M0208's for the same window.
    """

    inner: FactorParams
    sectors: int = 3
    order: str = "laggard"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("sectors", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 1 <= self.sectors <= 12:
            raise ValueError(f"sectors must be in 1..12, got {self.sectors}")
        if self.sectors > self.inner.top:
            raise ValueError(f"sectors must be <= top, got {self.sectors} > {self.inner.top}")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {ORDERS}, got {self.order!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"sectors": str(self.sectors), "order": self.order, "seed": str(self.seed),
               "market": self.market, "rev_n": str(REV_N), "min_members": str(MIN_MEMBERS),
               "taxonomy": "ff12-edgar-sic"}
        if self.order == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> IndustryParams:
    if not isinstance(params, IndustryParams):
        raise TypeError(f"params must be IndustryParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def draw(seed: int, symbol: str, data_date: date) -> int:
    """The control's score: a fixed 64-bit hash of seed, symbol and the decision's month (M0187)."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def month_return(h: History, data_date: date) -> float | None:
    """close(d) / close(d - 21 sessions) - 1 on the symbol's own bars, else None."""
    i = h.index_of(data_date)
    if i is None or i < REV_N:
        return None
    base = float(h.close[i - REV_N])
    now = float(h.close[i])
    if not (base > 0.0 and now > 0.0):
        return None
    return now / base - 1.0


def allot(top: int, k: int) -> list[int]:
    """``top`` slots over ``k`` industries, strongest first: 20 over 3 is [7, 7, 6]."""
    q, r = divmod(top, k)
    return [q + (1 if i < r else 0) for i in range(k)]


def picks(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
          p: IndustryParams) -> list[str]:
    """The book's names, strongest industry first, best-ranked member first inside each."""
    by_ind: dict[str, list[FactorRow]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        ind = sector_of(r.symbol, data_date)
        if ind is None:
            continue
        by_ind.setdefault(ind, []).append(r)
    strength: list[tuple[float, str]] = []
    for ind, rs in by_ind.items():
        if len(rs) >= MIN_MEMBERS:
            strength.append((-sum(r.momentum for r in rs) / len(rs), ind))
    chosen = [ind for _, ind in sorted(strength)[: p.sectors]]
    out: list[str] = []
    for ind, n in zip(chosen, allot(p.inner.top, max(len(chosen), 1))):
        members = by_ind[ind]
        if p.order == "hash":
            ranked = sorted(members, key=lambda r: (draw(p.seed, r.symbol, data_date), r.symbol))
            out.extend(r.symbol for r in ranked[:n])
            continue
        rev = {r.symbol: month_return(history[r.symbol], data_date) for r in members}
        scored = [(v, s) for s, v in rev.items() if v is not None]
        if not scored:
            continue
        mean = sum(v for v, _ in scored) / len(scored)
        out.extend(s for _, s in sorted((v - mean, s) for v, s in scored)[:n])
    return out


def build(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
          p: IndustryParams) -> tuple[Target, ...]:
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks(history, rows, data_date, p):
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


# --------------------------------------------------------------------------- the allocator


@dataclass(frozen=True, slots=True, eq=False)
class IndustryPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class IndustryAllocator:
    """Last month's laggards (or hash picks) inside the strongest FF12 industries."""

    id = "M0216"

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

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        if not rows:
            return ()
        return build(history, rows, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> IndustryPrepared:
        return IndustryPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, IndustryPrepared):
            raise TypeError(f"prepared must be IndustryPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        return build(prepared.history, rows, data_date, p)


INDUSTRY = IndustryAllocator()

TREND = ("SPY", 200)
W6 = FactorParams(rank="momentum", top=20, mom_n=126, mom_skip=21, trend=TREND)
W12 = FactorParams(rank="momentum", top=20, mom_n=252, mom_skip=21, trend=TREND)


def _v(suffix: str, params: IndustryParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0216-{suffix}", family="M0216", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=INDUSTRY, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0216",
    name="Winning industries, lagging members: buy last month's laggards inside the strongest industries",
    family="stock-industry-momentum-reversal",
    source_kind="paper",
    source_ref=("Moskowitz & Grinblatt (1999) Do Industries Explain Momentum?; Hameed & Mian (2015) "
                "Industries and Stock Return Reversals, JFQA; Li & Turkington, Mapping Momentum "
                "(S&P 500)"),
    hypothesis=(
        "Momentum lives mostly at the industry level, while over one month a stock reverses "
        "against its own industry. Each month-end, among F4's screened members, label each with "
        "its Fama-French 12 industry (SEC EDGAR SIC; unknowns never picked), rank industries with "
        "at least 5 members by the equal-weight mean of their members' 6-1 or 12-1 return, give "
        "the 3 or 4 strongest an equal share of 20 slots (7/7/6 or 5 each, so a structural sector "
        "cap of 7 or 5), and inside each buy the members with the lowest last-month return "
        "relative to their industry. Equal 5% slots, re-picked monthly with no band, unfilled "
        "slots in SPY, cash under SPY's 200-day average. Variants: top-3 vs top-4 industries, "
        "6-1 vs 12-1 industry window; control HASH-T3-W6, the same industries, allotment and "
        "switch with members in a fixed hash order (a plain industry-rotation book). Moskowitz "
        "and Grinblatt published in 1999 and Hameed and Mian's reversal in 2015, so most of the "
        "dev window predates the industry-momentum crowd and all of it predates the "
        "within-industry reversal paper. Fractional shares at Gotrade's real fees "
        "(monthly-hold-frac-gotrade) on the owner's monthly top-up. Success: beats SPY TR on dev "
        "with worst fall <= 25%, PF >= 1.3, a majority of walk-forward folds, a positive lead "
        "over SPY in 2009-2015, laggard picks beat the hash control by at least 2 points a year, "
        "and the book does not move with the test-failed momentum books (residual correlation "
        "under 0.85)."
    ),
    expected_failure=(
        "Holding only 3 or 4 industries is a concentrated bet: when the leading industries turn "
        "(tech in 2000, financials and energy in 2008) the book holds 15-20 names in them and the "
        "200-day switch meets the turn late, so the worst fall may break 25%. Industry momentum is "
        "a well-published 1999 anomaly and may have faded inside the window; 2009-2015's "
        "big-company drift (insight 91) works against equal slots in mid-sized laggards. The "
        "one-month reversal is a short-horizon effect that is strongest in small, illiquid "
        "stocks and is eaten by trading costs; in large index members at monthly re-picking and "
        "Gotrade's real fees on 20 small slots it may be gone, so the laggard picks may not beat "
        "the hash control. Last month's laggard inside a hot industry is sometimes the member "
        "with real bad news, which keeps falling. The 12-1 window ranks industries as momentum "
        "does, so the rotation may move with the test-failed momentum books (hardgate D14) and "
        "be refused on kin however it scores."
    ),
    candidates=(
        _v("T3-W6", IndustryParams(W6, sectors=3),
           "Top 3 industries by 6-1 return, 7/7/6 slots, last month's laggards inside each"),
        _v("T3-W12", IndustryParams(W12, sectors=3),
           "Top 3 industries by 12-1 return, 7/7/6 slots, last month's laggards inside each"),
        _v("T4-W6", IndustryParams(W6, sectors=4),
           "Top 4 industries by 6-1 return, 5 slots each: more spread, smaller industry bet"),
        _v("T4-W12", IndustryParams(W12, sectors=4),
           "Top 4 industries by 12-1 return, 5 slots each"),
        _v("HASH-T3-W6", IndustryParams(W6, sectors=3, order="hash"),
           "Control: the same top-3 industries and allotment, members in a fixed hash order"),
    ),
    seen_keys=(
        "concept:industry-momentum",
        "concept:within-industry-reversal",
        "concept:sector-rotation-ff12",
    ),
)
