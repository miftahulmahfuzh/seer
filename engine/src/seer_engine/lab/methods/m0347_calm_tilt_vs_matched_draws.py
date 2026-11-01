"""M0347 — Is the calm-stocks smoothness purchasable, or just what any book of calm names gets?

Parent: M0342 (expected idiosyncratic skewness). Its LOW arm fell 16.9% at worst while random
picks from the same pool behind the same switch fell 24-25% for the same money. The forecast was
mostly residual volatility in disguise, so the real question is the plain one: does ranking to
the calmest stocks buy that smoother ride, and does it pay anything *beyond* simply being
somewhere in the calm part of the market?

Low-volatility investing was published long before the dev window ends (Haugen & Heins 1975,
Ang-Hodrick-Xing-Zhang 2006 on idiosyncratic volatility, Frazzini & Pedersen 2014), so a dev
edge is the pre-crowd kind; Lipper-style "low vol" funds were everywhere by 2011.

Frame: M0091's book. Point-in-time index members, the usual price and dollar-volume screen,
20 equal slots, monthly, fractional shares at Gotrade's real fees, SPY 200-day switch on every
arm but the two marked NOSW. Only the choice of names differs.

The calm score is residual volatility: the standard deviation of a name's daily return after
removing beta times SPY's return, over the last 63 bars ending at the data date (beta fitted on
the same window). Names lacking 64 clean bars are not scored, identically in every arm.

Six arms, the lab's cap:
CALM holds the 20 lowest residual volatilities. CALM-NOSW is the same order never stepping
aside (always invested, opinion on the names but none on the market). MATCH1 and MATCH2 hash-draw
20 names out of the 40 calmest (a pool matched on calmness: its average volatility sits within a
few percent of the CALM book's), behind the switch, two seeds for the chance spread. MATCH1-NOSW is
MATCH1's order with no switch, so the switch's habit is priced apart from the ranking: CALM vs
MATCH is the ranking, CALM-NOSW vs MATCH1-NOSW is the ranking without the switch, and each
against its NOSW twin is the switch. WIDE hash-draws 20 from the whole scored pool behind the
switch (M0342's R1 equivalent), the anchor that says how much of the ride is calmness at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20
from seer_engine.lab.methods.m0091_lottery_avoidance import targets_from_rows
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

MODES = ("calm", "matched", "wide")
WIN = 63  # returns in the volatility window
MARKET = "SPY"
POOL = 40  # the calm pool the matched draws come from (twice the book)

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class CalmParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``mode`` picks the names."""

    inner: FactorParams
    mode: str = "calm"
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "seed": str(self.seed), "win": str(WIN), "pool": str(POOL)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> CalmParams:
    if not isinstance(params, CalmParams):
        raise TypeError(f"params must be CalmParams, got {type(params).__name__}")
    return params


def residual_vol(history: Mapping[str, History], symbols: list[str], data_date: date
                 ) -> dict[str, float]:
    """Std of the market-model residual over the WIN returns ending at ``data_date``."""
    spy = history.get(MARKET)
    if spy is None:
        return {}
    out: dict[str, float] = {}
    for s in symbols:
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < WIN:
            continue
        d = h.dates[i - WIN : i + 1]
        k = np.searchsorted(spy.dates, d)
        if k.max(initial=0) >= len(spy.dates) or not np.array_equal(spy.dates[k], d):
            continue
        c = h.close[i - WIN : i + 1]
        sc = spy.close[k]
        if not (np.all(np.isfinite(c)) and np.all(c > 0.0)
                and np.all(np.isfinite(sc)) and np.all(sc > 0.0)):
            continue
        r = c[1:] / c[:-1] - 1.0
        m = sc[1:] / sc[:-1] - 1.0
        vm = float(np.var(m))
        if not vm > 0.0:
            continue
        beta = float(np.mean((r - r.mean()) * (m - m.mean())) / vm)
        e = r - beta * m
        sd = float(np.std(e))
        if sd > 0.0:
            out[s] = sd
    return out


def choose(rows: list[FactorRow], vol: dict[str, float], params: CalmParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in vol]
    top = params.inner.top
    if params.mode == "calm":
        pool.sort(key=lambda r: (vol[r.symbol], r.symbol))
        return pool[:top]
    if params.mode == "matched":
        pool.sort(key=lambda r: (vol[r.symbol], r.symbol))
        pool = pool[:POOL]
    pool.sort(key=lambda r: (float(draw(params.seed, r.symbol)), r.symbol))
    return pool[:top]


@dataclass
class CalmPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    cache: dict[date, dict[str, float]] = field(default_factory=dict, repr=False)


class CalmTiltAllocator:
    """The lab's index-member book choosing among names by residual volatility or by chance."""

    id = "M0347"

    def lookback(self, params: Any) -> int:
        return max(factor_lookback(_check(params).inner), WIN + 1)

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

    def _run(self, prepared: CalmPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: CalmParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        syms = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED)
        if prepared is None:
            vol = residual_vol(history, syms, data_date)
        else:
            vol = prepared.cache.get(data_date)
            if vol is None:
                vol = residual_vol(history, syms, data_date)
                prepared.cache[data_date] = vol
        return targets_from_rows(choose(rows, vol, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> CalmPrepared:
        return CalmPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CalmPrepared):
            raise TypeError(f"prepared must be CalmPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


CALMTILT = CalmTiltAllocator()


def _v(suffix: str, params: CalmParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0347-{suffix}", family="M0347",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=CALMTILT, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0347",
    name="Calm-stocks tilt priced against random picks of equal calmness",
    family="stock-calm-tilt",
    source_kind="variation",
    source_ref=("Ang, Hodrick, Xing & Zhang (2006), The cross-section of volatility and expected "
                "returns, Journal of Finance 61(1); Frazzini & Pedersen (2014), Betting against "
                "beta, JFE 111(1)"),
    parent_id="M0342",
    hypothesis=(
        "M0342's lowest-forecast book fell 16.9% against 24-25% for random picks behind the same "
        "switch, while earning the same money. Test whether that smoother ride is purchasable: "
        "hold the 20 lowest residual-volatility index members (daily return less beta times SPY's, "
        "63 bars) behind the SPY 200-day switch, against random books drawn from the 40 calmest "
        "names (a pool matched on calmness), against a random draw from the whole scored pool, and "
        "against the always-invested no-switch versions. Low-volatility effects were published "
        "2006-2014, so a dev edge is the pre-crowd kind. Predictions, written now: CALM's worst "
        "fall is under 20% and at least 4 points shallower than WIDE's; CALM beats MATCH1 and "
        "MATCH2 by less than the gap between those two plus 1.5 points a year of funded CAGR (the "
        "calm region, not the ranking inside it, carries the ride); CALM trails SPY in 2009-2015; "
        "CALM-NOSW falls over 30%, so the switch not the calmness carries most of the protection. "
        "If CALM does not beat the volatility-matched random order on fall and return, the skew "
        "family is closed."
    ),
    expected_failure=(
        "Calmness is a sector tilt (utilities, staples, health care) and a bet against the "
        "market's growth run, so CALM trails SPY by several points a year in 2009-2015 as the "
        "lab's other calm books did (M0091, M0293). Inside the calm pool the ranking adds nothing "
        "over chance, so MATCH matches CALM and the calm region alone explains the shallower fall. "
        "The switch's time in cash, not the stocks, is most of the protection, so CALM-NOSW falls "
        "as deep as an index. Fees on 20 small slots at 12 turns a year eat a low-return book. "
        "The 40-name pool is a judgment call, and two seeds are a thin chance spread."
    ),
    candidates=(
        _v("CALM", CalmParams(N20, "calm"),
           "The 20 lowest residual volatilities behind the SPY switch: the idea"),
        _v("CALM-NOSW", CalmParams(NOSW, "calm"),
           "Calm order, no switch: always invested, prices the switch's habit against CALM"),
        _v("MATCH1", CalmParams(N20, "matched", 347),
           "Control: hash draw of 20 from the 40 calmest, seed 347, behind the switch"),
        _v("MATCH2", CalmParams(N20, "matched", 348),
           "Control: same matched pool, seed 348, the chance spread"),
        _v("MATCH1-NOSW", CalmParams(NOSW, "matched", 347),
           "No-opinion always-invested arm: MATCH1's order, no switch"),
        _v("WIDE", CalmParams(N20, "wide", 347),
           "Anchor: hash draw of 20 from the whole scored pool behind the switch"),
    ),
    seen_keys=(
        "concept:calm-tilt-vs-matched-draws",
        "concept:residual-volatility-ranking",
    ),
)
