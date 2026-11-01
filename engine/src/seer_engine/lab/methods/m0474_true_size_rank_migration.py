"""M0474 — Hold the index members whose true company size rank has climbed the most in a year.

Source: variation of M0466. M0466 ranked on the 60-day mean of close times volume, a proxy that
mixes size with news bursts; its analysis asked for filing-based size. The store has had point-in-time
company size (shares outstanding as filed times the close as printed) since 2026-10-17, so this
redoes the same climb-versus-slide test with real size. The underlying attention and index-demand
ideas date from the 1980s-2000s, so a crowd had time to trade them: a dev edge is more likely
fading than fresh, and 2009-2015 is the first filter.

Frame as M0466: point-in-time members, the F4 screen, 20 equal slots, monthly, fractional shares
at Gotrade's real fees, SPY 200-day switch on every arm but two. Each month the screened members
(one share class per company, so Google's two lines are one) with a known size today AND 365
calendar days earlier are ranked by size on both dates, each as a percentile (0 = smallest) within
that same set; the key is today's percentile minus last year's. RISE holds the tenth with the
largest climb, FALL the tenth with the largest drop (each capped at 20 slots, at least one name).
A name with no size on either date is left out of the ranking (coverage is 62-75% in 2009-2015).

Arms (six, the lab's cap): RISE, FALL (mirror), R1 and R2 (hash order on the whole scored set
behind the same switch), R1-NOSW (always-invested no-opinion arm pricing the switch) and
RISE-NOSW (the 2x2 pair).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
from seer_engine.lab.methods.m0047_market_value_residual import one_per_company
from seer_engine.lab.methods.m0293_calm_filter_on_a_host import draw
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
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

ADDED = date(2026, 11, 1)

MODES = ("rise", "fall", "blind")
LAG_DAYS = 365  # calendar days back for the earlier size rank
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class MigParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` is the ranking."""

    inner: FactorParams
    mode: str = "rise"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "size": "market_value",
               "lag_days": str(LAG_DAYS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> MigParams:
    if not isinstance(params, MigParams):
        raise TypeError(f"params must be MigParams, got {type(params).__name__}")
    return params


def _pct(vals: dict[str, float]) -> dict[str, float]:
    """Percentile within the set, 0 = smallest; ties share the mean-free lower-rank rule."""
    n = len(vals)
    order = sorted(vals, key=lambda s: (vals[s], s))
    return {s: i / (n - 1) for i, s in enumerate(order)} if n > 1 else {s: 0.5 for s in order}


def rank_change(market: Market, symbols: list[str], data_date: date) -> dict[str, float]:
    """Today's size percentile minus the one a year earlier, both within the same names.

    One share class per company first, then only names with a company size on both dates.
    """
    then_date = data_date - timedelta(days=LAG_DAYS)
    now: dict[str, float] = {}
    then: dict[str, float] = {}
    for s in one_per_company(symbols, len(symbols)):
        a = market.market_value(s, data_date)
        b = market.market_value(s, then_date)
        if a is None or b is None or not (a > 0.0 and b > 0.0):
            continue
        now[s] = float(a)
        then[s] = float(b)
    if len(now) < 5:
        return {}
    pn, pt = _pct(now), _pct(then)
    return {s: pn[s] - pt[s] for s in now}


def choose(rows: list[FactorRow], change: dict[str, float], params: MigParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in change]
    if not pool:
        return []
    mode = params.mode
    if mode == "rise":
        key = {r.symbol: -change[r.symbol] for r in pool}
        n = max(1, -(-len(pool) // 10))
    elif mode == "fall":
        key = {r.symbol: change[r.symbol] for r in pool}
        n = max(1, -(-len(pool) // 10))
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
        n = params.inner.top
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: min(n, params.inner.top)]


@dataclass
class MigPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    market: Market | None = field(default=None, repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class RankMigrationAllocator:
    """The lab's index-member book ranked on the 12-month change in a name's true size rank."""

    id = "M0474"
    market_fields = ("shares",)

    def lookback(self, params: Any) -> int:
        return factor_lookback(_check(params).inner)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        fixed = {MARKET}
        if p.inner.trend is not None:
            fixed.add(p.inner.trend[0])
        return tuple(sorted(fixed))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _run(self, prepared: MigPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: MigParams) -> tuple[Target, ...]:
        if prepared is None or prepared.market is None or len(prepared.market.shares) == 0:
            return ()  # no company size: target nothing
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        change = prepared.cache.get(data_date)
        if change is None:
            change = rank_change(prepared.market, syms, data_date)
            prepared.cache[data_date] = change
        return targets_from_rows(choose(rows, change, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no share counts, so no targets."""
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> MigPrepared:
        return MigPrepared(history, prepare_factor(history))

    def prepare_market(self, market: Any) -> MigPrepared:
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        return MigPrepared(market.history, prepare_factor(market.history), market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MigPrepared):
            raise TypeError(f"prepared must be MigPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


MIGRATE = RankMigrationAllocator()


def _v(suffix: str, params: MigParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0474-{suffix}", family="M0474",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=MIGRATE, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0474",
    name="Climbing the size ranks, measured with real company size: the tenth that rose most over 12 months, against the tenth that fell most",
    family="stock-size-rank-migration",
    source_kind="variation",
    source_ref="variation of M0466 with filing-based company size (shares times price) in place of dollar volume; Sera 20261101-1949",
    parent_id="M0466",
    hypothesis=(
        "M0466 ranked members on a dollar-volume proxy and a blind draw behind the same switch did "
        "as well as the climbers. Dollar volume mixes size with news bursts, so the test was "
        "muddy. Here the size is real: shares outstanding as filed times the close as printed, "
        "point in time, one share class per company. Each month the screened members with a size on "
        "both dates are ranked today and 365 days earlier, each as a percentile within that set; "
        "RISE holds the tenth with the largest climb, FALL the tenth with the largest fall, up to "
        "20 equal slots, monthly, fractional shares at Gotrade's real fees, behind SPY's 200-day "
        "switch. Arms: RISE, FALL (mirror), R1 and R2 (hash order on the scored set behind the "
        "same switch), R1-NOSW (always invested, no opinion: prices the switch's habit), RISE-NOSW "
        "(the 2x2 pair). SPY is the benchmark column. Predictions, written now: RISE beats FALL on "
        "funded CAGR; RISE beats the better of R1 and R2 by less than their spread plus 2 points a "
        "year; RISE trails SPY in 2009-2015; RISE-NOSW falls over 40%. A pass needs RISE to clear "
        "the lab's gate AND beat both blind draws outside their spread; otherwise the verdict is "
        "that volume noise was not the problem. Attention and index-demand ideas date from the "
        "1980s-2000s, so any dev edge is likely crowded and faded."
    ),
    expected_failure=(
        "The same as the parent: a name climbing the size ranks has already risen in price, so RISE "
        "is a 12-month momentum book in disguise and the lab's momentum kin say it fades behind the "
        "switch; a blind draw of the same pool does as well. Real size removes the volume noise but "
        "not the momentum. Only ~62-75% of members have a size in 2009-2015, so the ranked set is "
        "the better-covered and larger companies, and the switch's time in cash in a rising decade, "
        "not the ranking, decides the result against SPY."
    ),
    candidates=(
        _v("RISE", MigParams(N20, "rise"),
           "Tenth with the largest 12-month climb in size-rank percentile, behind the switch: the idea"),
        _v("FALL", MigParams(N20, "fall"),
           "Tenth with the largest 12-month fall in size-rank percentile, behind the switch: the mirror"),
        _v("R1", MigParams(N20, "blind", 466),
           "Control: hash-ranked scored set, seed 466, behind the switch"),
        _v("R2", MigParams(N20, "blind", 467),
           "Control: hash-ranked scored set, seed 467, behind the switch"),
        _v("R1-NOSW", MigParams(NOSW, "blind", 466),
           "No-opinion always-invested arm: R1's order with no switch, prices the switch's habit"),
        _v("RISE-NOSW", MigParams(NOSW, "rise"),
           "The idea with no switch: the 2x2 pair beside RISE and R1-NOSW"),
    ),
    seen_keys=(
        "concept:market-value-rank-migration",
        "concept:size-rank-migration",
    ),
)
