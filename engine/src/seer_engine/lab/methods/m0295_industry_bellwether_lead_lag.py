"""M0295 — The industry's biggest name leads: do its smaller peers follow next month?

Source: Hou (2007), Industry Information Diffusion and the Lead-Lag Effect in Stock Returns,
Review of Financial Studies 20(4); Lo & MacKinlay (1990), When Are Contrarian Profits Due to
Stock Market Overreaction?, RFS 3(2).
Idea: news reaches the biggest, most-watched company in an industry first and reaches its
smaller peers with a lag. So last month's return of an industry's **largest** member should
predict this month's return of its **other** members. The signal is therefore another company's
return, never the stock's own past return — which is what keeps this from being momentum under a
new name, the failure that killed M0282 and the trap insight 555 warns about.

This is not M0216. There the signal was the industry's own average 6-1 or 12-1 return and the
pick was a laggard inside it. Here the signal is one designated company's last-month return, the
pick inside an industry carries no opinion at all, and the control randomises the **industries**
rather than the members — the question M0216 left open when its random-member control matched
its clever one.

On data date d:

    * the pool is F4's screened members on d (close >= $5, 20-day mean dollar volume > $20M, at
      least 253 bars through d), exactly the names every F4-frame book may buy;
    * each pool member's industry is its Fama-French 12 industry on d (``seer_engine.sectors``:
      SEC EDGAR's SIC for the filer trading as that ticker on d). A member with no known industry
      is never ranked and never bought — ``Unknown`` is a gap in the data, not a line of business;
    * an industry is **eligible** on d when it has at least ``MIN_MEMBERS`` (5) pool members and
      its leader has a computable last-month return;
    * the industry's **leader** is its member with the largest 20-day mean dollar volume
      (``leader="largest"``) or the smallest (``leader="smallest"``, the SMALL arm). The lab's
      market-cap figure is broken (it multiplies an unadjusted share count by a split-adjusted
      close), so dollar volume stands in for size — and dollar volume is the better proxy for
      "most watched" anyway, which is the mechanism Hou describes;
    * the leader is the signal, never a holding: it is removed from its own industry's followers;
    * industries are ordered by their leader's last-month return (close d over close 21 sessions
      back), highest first for ``side="follow"``, lowest first for ``side="fade"``, and by
      blake2b(seed | industry | year-month) for ``side="matched"``. The first ``industries`` (3)
      are chosen;
    * the 20 slots are split equally over the chosen industries, strongest first (7, 7, 6), so no
      industry ever holds more than 7 of 20 — a structural sector cap;
    * **inside** a chosen industry the followers are ordered by blake2b(seed | symbol |
      year-month) (M0187's placebo order) in every arm. The within-industry choice carries no
      opinion in any variant, so the only thing that separates FOLLOW, FADE and MATCHED is how
      the three industries were chosen. M0216 already measured that a clever within-industry
      pick adds nothing, so spending this method's variants there would re-buy a known answer;
    * every slot is 1/20; a slot the chosen industries cannot fill holds SPY, as in the F4-frame
      books. Cash while SPY is under its 200-day average, except in the no-gate arms.

Why these six arms. FOLLOW-T3 is the idea. FADE-T3 is its mirror: if the lead-lag is real the
ladder runs one way, and if the two arms are indistinguishable there is no signal. A mirror pair
alone cannot price what *acting* costs, because both arms pay the switch's time in cash equally
and it cancels — so FOLLOW-T3-NOGATE and MATCHED-T3-NOGATE complete the 2x2 the skill's dressing
rule asks for, and `lab dressing M0295` can price the habit. MATCHED-T3 is the control that
matters: three industries drawn blind, the same slot split, the same switch, the same
opinion-free member order. It isolates the bellwether signal from the shape of a three-industry
rotation book, which M0216 priced at roughly nothing after 2009. SMALL-T3 is the mechanism
probe: rank industries by their **least** traded member instead. If SMALL does as well as FOLLOW,
nothing is leading anything and the whole lead is one-month industry drift.

No band: a one-month signal re-read every month-end. Every month the book is re-picked.

Assumption, written before the run: EDGAR's SIC is the filer's latest, not point in time, so a
filer that changed trade reads as its end state for its whole history (``sectors`` names the
cases). This can only blur an industry, never leak a price.

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

ADDED = date(2026, 10, 23)
REV_N = 21  # last month, in sessions: the leader's signal window
MIN_MEMBERS = 5  # pool members an industry needs on d to be eligible
SIDES = ("follow", "fade", "matched")
LEADERS = ("largest", "smallest")


@functools.cache
def _sector_map() -> sectors.SectorMap:
    return sectors.load()


def sector_of(symbol: str, on: date) -> str | None:
    return _sector_map().sector_of(symbol, on)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class LeadLagParams:
    """``inner`` is F4's screen, switch and book size; ``inner.rank`` never selects here.

    ``inner.trend`` is the SPY 200-day switch, or None for the always-invested arms.
    """

    inner: FactorParams
    industries: int = 3
    side: str = "follow"
    leader: str = "largest"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        for name in ("industries", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 1 <= self.industries <= 12:
            raise ValueError(f"industries must be in 1..12, got {self.industries}")
        if self.industries > self.inner.top:
            raise ValueError(f"industries must be <= top, got {self.industries} > {self.inner.top}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")
        if self.leader not in LEADERS:
            raise ValueError(f"leader must be one of {LEADERS}, got {self.leader!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"industries": str(self.industries), "side": self.side, "leader": self.leader,
               "seed": str(self.seed), "market": self.market, "rev_n": str(REV_N),
               "min_members": str(MIN_MEMBERS), "taxonomy": "ff12-edgar-sic",
               "member_order": "blake2b-8", "leader_held": "no"}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> LeadLagParams:
    if not isinstance(params, LeadLagParams):
        raise TypeError(f"params must be LeadLagParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def draw(seed: int, key: str, data_date: date) -> int:
    """A fixed 64-bit hash of seed, a key and the decision's month (M0187's placebo draw)."""
    raw = f"{seed}|{key}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big")


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
    """``top`` slots over ``k`` industries, first first: 20 over 3 is [7, 7, 6]."""
    q, r = divmod(top, k)
    return [q + (1 if i < r else 0) for i in range(k)]


def leader_of(rows: list[FactorRow], how: str) -> FactorRow:
    """The industry's signal company: its most (or least) traded member by 20-day dollar volume."""
    sign = -1.0 if how == "largest" else 1.0
    return min(rows, key=lambda r: (sign * r.dollar_volume, r.symbol))


def picks(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
          p: LeadLagParams) -> list[str]:
    """The book's names, chosen industry first, in the opinion-free member order inside each."""
    by_ind: dict[str, list[FactorRow]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        ind = sector_of(r.symbol, data_date)
        if ind is None:
            continue
        by_ind.setdefault(ind, []).append(r)

    followers: dict[str, list[FactorRow]] = {}
    ranked: list[tuple[float, int, str]] = []
    for ind, members in by_ind.items():
        if len(members) < MIN_MEMBERS:
            continue
        lead = leader_of(members, p.leader)
        signal = month_return(history[lead.symbol], data_date)
        if signal is None:
            continue
        followers[ind] = [r for r in members if r.symbol != lead.symbol]
        if p.side == "follow":
            ranked.append((-signal, 0, ind))
        elif p.side == "fade":
            ranked.append((signal, 0, ind))
        else:
            ranked.append((0.0, draw(p.seed, ind, data_date), ind))
    chosen = [ind for _, _, ind in sorted(ranked)[: p.industries]]

    out: list[str] = []
    for ind, n in zip(chosen, allot(p.inner.top, max(len(chosen), 1))):
        order = sorted(followers[ind], key=lambda r: (draw(p.seed, r.symbol, data_date), r.symbol))
        out.extend(r.symbol for r in order[:n])
    return out


def build(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
          p: LeadLagParams) -> tuple[Target, ...]:
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
class LeadLagPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class LeadLagAllocator:
    """Followers of the industries whose biggest name moved most last month."""

    id = "M0295"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), REV_N + 1)

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

    def prepare(self, history: Mapping[str, History]) -> LeadLagPrepared:
        return LeadLagPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, LeadLagPrepared):
            raise TypeError(f"prepared must be LeadLagPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        return build(prepared.history, rows, data_date, p)


LEADLAG = LeadLagAllocator()

TREND = ("SPY", 200)
GATED = FactorParams(rank="momentum", top=20, mom_n=252, mom_skip=21, trend=TREND)
OPEN = FactorParams(rank="momentum", top=20, mom_n=252, mom_skip=21, trend=None)


def _v(suffix: str, params: LeadLagParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0295-{suffix}", family="M0295", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=LEADLAG, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0295",
    name="The industry's biggest name leads: do its smaller peers follow next month?",
    family="stock-industry-lead-lag",
    source_kind="paper",
    source_ref=("Hou (2007) Industry Information Diffusion and the Lead-Lag Effect in Stock "
                "Returns, RFS 20(4); Lo & MacKinlay (1990) When Are Contrarian Profits Due to "
                "Stock Market Overreaction?, RFS 3(2)"),
    parent_id=None,
    hypothesis=(
        "News reaches an industry's biggest, most-watched company first and its smaller peers "
        "with a lag, so last month's return of the largest member should predict this month's "
        "return of the others. The stock's own past return is never read, so the book cannot be "
        "momentum renamed. Each month-end, among F4's screened members, label each with its "
        "Fama-French 12 industry (SEC EDGAR SIC; unknowns never picked), call an industry's "
        "most-traded member by 20-day dollar volume its leader (the lab's market-cap figure is "
        "broken, dollar volume is not), keep industries with at least 5 pool members, rank them "
        "by their leader's last-month return, give the 3 strongest an equal share of 20 slots "
        "(7/7/6, a structural sector cap), and buy the other members of those industries in a "
        "fixed hash order — the within-industry choice carries no opinion in any arm, because "
        "M0216 already measured that a clever one adds nothing. Equal 5% slots, re-picked "
        "monthly with no band, unfilled slots in SPY, cash under SPY's 200-day average. Arms: "
        "FOLLOW-T3 (the idea), FADE-T3 (its mirror, the weakest leaders' industries), MATCHED-T3 "
        "(the control that matters: three industries drawn blind, the same split, switch and "
        "member order, so the bellwether signal is separated from the shape of a three-industry "
        "rotation book), FOLLOW-T3-NOGATE and MATCHED-T3-NOGATE (the 2x2 that prices the "
        "switch's habit, so the mirror pair does not join the 22 that cannot be priced), and "
        "SMALL-T3 (rank industries by their least-traded member instead: if it does as well, "
        "nothing is leading anything). Success: FOLLOW-T3 beats MATCHED-T3 by more than the "
        "lab's measured blind-draw noise of about 1.5 points a year, the ladder runs the right "
        "way against FADE-T3, and the lead survives on the survivorship-check store. Hou "
        "published in 2007, so most of the dev window predates the crowd, and the fade warning "
        "applies. Fractional shares at Gotrade's real fees on the owner's monthly deposits."
    ),
    expected_failure=(
        "The leader's last-month return is just its industry's last-month return, the followers "
        "are just that industry's members, and the whole lead is the three-industry rotation bet "
        "M0216 already priced at roughly nothing — its rotation book lost to SPY by 5.7 points a "
        "year in 2009-2015 and lost 3 of 4 walk-forward folds. If that is what happens here, "
        "FOLLOW-T3 and MATCHED-T3 will land inside the 1.5-point blind-draw noise band, SMALL-T3 "
        "will do about as well as FOLLOW-T3, and the mirror FADE-T3 will not be clearly worse. "
        "The second likely failure is the era: three concentrated industries re-picked monthly "
        "in equal slots is the book shape insight 91 warns about, so even a real lead before "
        "2009 should vanish against SPY's big-company drift afterwards. The third is cost: 20 "
        "slots re-picked every month on a hash order churns hard, and Gotrade's fees on a $35 "
        "slot are several times the old flat assumption."
    ),
    candidates=(
        _v("FOLLOW-T3", LeadLagParams(inner=GATED, industries=3, side="follow", leader="largest"),
           "the idea: followers of the three industries whose biggest name rose most last month"),
        _v("FADE-T3", LeadLagParams(inner=GATED, industries=3, side="fade", leader="largest"),
           "the mirror: followers of the three industries whose biggest name fell most"),
        _v("MATCHED-T3", LeadLagParams(inner=GATED, industries=3, side="matched", leader="largest"),
           "the control: three industries drawn blind, same split, switch and member order"),
        _v("FOLLOW-T3-NOGATE", LeadLagParams(inner=OPEN, industries=3, side="follow", leader="largest"),
           "the idea always invested: the habit removed, so the switch can be priced"),
        _v("MATCHED-T3-NOGATE", LeadLagParams(inner=OPEN, industries=3, side="matched", leader="largest"),
           "the control always invested: completes the 2x2 over signal and switch"),
        _v("SMALL-T3", LeadLagParams(inner=GATED, industries=3, side="follow", leader="smallest"),
           "the mechanism probe: rank industries by their least-traded member instead"),
    ),
    seen_keys=("concept:industry-lead-lag", "concept:bellwether-leader",
               "concept:blind-industry-draw-control"),
)
