"""M0217 — Index-shaped industry weights: a stock book whose slots follow the index's own industry mix.

Source: knowledge (variation of M0216). Industry weights as the market's own mix is how every
cap-weighted index is built; the question here is whether the lab's equal-slot books lost to SPY
in 2009-2015 because of *which stocks* they chose or because of *which industries* they leaned on.
Idea: M0216 showed random picks inside chosen industries did as well as clever ones, so the
industry mix may decide the result. Take the stock picking out of the mix. Split the 20 slots
across the 12 Fama-French industries in proportion to each industry's share of the screened pool's
20-day dollar volume (the store has no point-in-time market caps for the whole pool; dollar volume
is the size proxy that tracks the big names), then fill each industry by a fixed hash order (the
control, no opinion) or by a ranker (12-1 momentum, lowest volatility).

On data date d:

    * the pool is F4's screened members on d, the names every F4-frame book may buy;
    * each pool member's industry is its FF12 industry on d (``seer_engine.sectors``, as M0216).
      A member with no known industry is never bought;
    * ``weights="dollar"``: an industry's share is its pool members' summed 20-day dollar volume
      over the labelled pool's total. ``weights="equal"``: every industry with at least
      ``MIN_MEMBERS`` pool members shares equally (the equal-industry control the hypothesis
      names). Slots are split by largest remainder (ties to the industry name), then capped at the
      industry's member count; a slot that cannot be filled holds SPY;
    * inside an industry members are ordered by the variant's ``order``: ``hash`` (blake2b of seed,
      symbol and month: M0187's placebo), ``momentum`` (highest 12-1 return first) or ``lowvol``
      (lowest 60-day return stdev first);
    * every slot is 1/20; cash while SPY is under its 200-day average (F4's switch), except the
      NOSW arm, which never steps aside.

The NOSW arm is the third arm with no opinion in it: the same index-shaped hash book never
switching. The gap between HASH-DV and HASH-DV-NOSW is what the 200-day habit costs or earns; the
gap between HASH-DV and HASH-EQ is what the industry mix alone does.

Assumption, written before the run: sector labels are the filer's latest SIC (M0216's caveat),
which can only blur an industry, never leak a price. Rules are ``monthly-hold-frac-gotrade``:
fractional shares at Gotrade's real fees on the owner's monthly deposits. Pure: reads only bars
dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0216_industry_winners_member_laggards import draw, sector_of
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
MIN_MEMBERS = 3  # pool members an industry needs on d to hold slots (equal arm)
ORDERS = ("hash", "momentum", "lowvol")
WEIGHTS = ("dollar", "equal")


@dataclass(frozen=True, slots=True)
class MixParams:
    """``inner`` is F4's screen, switch (``trend``) and book size (``top``)."""

    inner: FactorParams
    weights: str = "dollar"
    order: str = "hash"
    seed: int = 1
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")
        if self.weights not in WEIGHTS:
            raise ValueError(f"weights must be one of {WEIGHTS}, got {self.weights!r}")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {ORDERS}, got {self.order!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"weights": self.weights, "order": self.order, "seed": str(self.seed),
               "market": self.market, "min_members": str(MIN_MEMBERS),
               "taxonomy": "ff12-edgar-sic"}
        if self.order == "hash":
            out["hash"] = "blake2b-8"
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> MixParams:
    if not isinstance(params, MixParams):
        raise TypeError(f"params must be MixParams, got {type(params).__name__}")
    return params


def split_slots(top: int, shares: Mapping[str, float]) -> dict[str, int]:
    """``top`` slots over industries by largest remainder; ties go to the industry name."""
    total = sum(shares.values())
    if total <= 0.0:
        return {}
    quota = {k: top * v / total for k, v in shares.items()}
    out = {k: int(q) for k, q in quota.items()}
    left = top - sum(out.values())
    for k in sorted(quota, key=lambda k: (-(quota[k] - out[k]), k))[:left]:
        out[k] += 1
    return {k: n for k, n in out.items() if n > 0}


def picks(rows: list[FactorRow], data_date: date, p: MixParams) -> list[str]:
    by_ind: dict[str, list[FactorRow]] = {}
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == p.market:
            continue
        ind = sector_of(r.symbol, data_date)
        if ind is None:
            continue
        by_ind.setdefault(ind, []).append(r)
    if p.weights == "dollar":
        shares = {i: sum(r.dollar_volume for r in rs) for i, rs in by_ind.items()}
    else:
        shares = {i: 1.0 for i, rs in by_ind.items() if len(rs) >= MIN_MEMBERS}
    out: list[str] = []
    for ind, n in sorted(split_slots(p.inner.top, shares).items()):
        members = by_ind[ind]
        if p.order == "hash":
            ranked = sorted(members, key=lambda r: (draw(p.seed, r.symbol, data_date), r.symbol))
        elif p.order == "momentum":
            ranked = sorted(members, key=lambda r: (-r.momentum, r.symbol))
        else:
            ranked = sorted(members, key=lambda r: (r.vol, r.symbol))
        out.extend(r.symbol for r in ranked[:n])
    return out


def build(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
          p: MixParams) -> tuple[Target, ...]:
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks(rows, data_date, p):
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


@dataclass(frozen=True, slots=True, eq=False)
class MixPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class MixAllocator:
    """Slots split across FF12 industries by dollar volume (or equally), filled by one ranker."""

    id = "M0217"

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

    def prepare(self, history: Mapping[str, History]) -> MixPrepared:
        return MixPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MixPrepared):
            raise TypeError(f"prepared must be MixPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        if not rows:
            return ()
        return build(prepared.history, rows, data_date, p)


MIX = MixAllocator()

W12 = FactorParams(rank="momentum", top=20, mom_n=252, mom_skip=21, trend=("SPY", 200))
W12_NOSW = FactorParams(rank="momentum", top=20, mom_n=252, mom_skip=21, trend=None)


def _v(suffix: str, params: MixParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0217-{suffix}", family="M0217", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MIX, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0217",
    name="Index-shaped industry weights: a stock book whose slots follow the index's own industry mix",
    family="stock-sector-shape",
    source_kind="variation",
    source_ref="M0216",
    parent_id="M0216",
    hypothesis=(
        "Every equal-slot book in the lab lost to SPY in 2009-2015, and M0216 showed random picks "
        "inside chosen industries do as well as clever ones, so the industry mix itself may decide "
        "the result. Each month-end, among F4's screened members labelled with their Fama-French 12 "
        "industry, split 20 equal slots across industries in proportion to each industry's share of "
        "the pool's 20-day dollar volume (a size proxy; the store has no market caps for the whole "
        "pool) by largest remainder, and fill each industry by a fixed hash order (control, no "
        "opinion), by 12-1 momentum, or by lowest 60-day volatility. Controls: HASH-EQ, the same "
        "hash fill with equal industry shares (the equal-industry book), and HASH-DV-NOSW, the "
        "index-shaped hash book never stepping aside for SPY's 200-day average (the third arm with "
        "no opinion, to price the switch). Fractional shares at Gotrade's real fees on the owner's "
        "monthly top-up; unfillable slots in SPY. Prediction: if HASH-DV tracks SPY in 2009-2015 "
        "while HASH-EQ lags, the lag was an industry bet against big tech, not a failure of "
        "stock picking. Report each variant's industry mix vs the pool's, the 2009-2015 edge, "
        "folds, and residual correlation to the test-failed books. Dollar-volume and sector "
        "weighting is how every index is built, so there is no published edge to fade; the "
        "rankers are 12-1 momentum (Jegadeesh-Titman 1993) and low volatility (Ang et al. 2006), "
        "both heavily published and likely faded post-2015. Success for promotion: beats SPY TR on "
        "dev, worst fall <= 25%, PF >= 1.3, majority of folds, positive 2009-2015 lead, residual "
        "correlation under 0.85 to test-failed books."
    ),
    expected_failure=(
        "Dollar volume is a poor size proxy: it favours stocks with heavy trading, not heavy "
        "market value, and tilts to tech and financials in the 2000s, so the mix is not the "
        "index's mix. Twenty equal slots cannot copy a mix whose top names hold several percent "
        "each, so the book stays equal-weight in effect and the lag to SPY from big-company drift "
        "persists even with the right industry shares. Hash fill picks arbitrary names, so "
        "HASH-DV is a noisy sample of the pool and one seed may mislead. The 200-day switch costs "
        "time out of a rising decade (about 3.6 points, insight 462), and NOSW may win simply by "
        "being always invested. The momentum and low-volatility fills carry the known failures of "
        "the test-failed momentum books and may be refused on kin."
    ),
    candidates=(
        _v("HASH-DV", MixParams(W12, "dollar", "hash"),
           "Control: slots by industry dollar-volume share, members in a fixed hash order"),
        _v("MOM-DV", MixParams(W12, "dollar", "momentum"),
           "Index-shaped industry slots, highest 12-1 return inside each industry"),
        _v("LOWVOL-DV", MixParams(W12, "dollar", "lowvol"),
           "Index-shaped industry slots, lowest 60-day volatility inside each industry"),
        _v("HASH-EQ", MixParams(W12, "equal", "hash"),
           "Control: equal industry shares, hash fill (the equal-industry book)"),
        _v("MOM-EQ", MixParams(W12, "equal", "momentum"),
           "Equal industry shares, 12-1 momentum fill: isolates the weighting from the ranker"),
        _v("HASH-DV-NOSW", MixParams(W12_NOSW, "dollar", "hash"),
           "Third arm: the HASH-DV book never stepping aside for SPY's 200-day average"),
    ),
    seen_keys=(
        "concept:industry-weights-index-shaped",
        "concept:dollar-volume-industry-mix",
    ),
)
