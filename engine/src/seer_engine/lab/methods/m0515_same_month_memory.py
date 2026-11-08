"""M0515 — Same-month memory: index members ranked on their average return in the coming calendar
month over the previous several years.

Source: Keloharju, Linnainmaa & Nyberg (2016), "Return seasonalities", Journal of Finance 71(4)
(NBER w20815); Heston & Sadka (2008) is the one-year ancestor. Published 2016 (working paper 2014),
so the dev window (ends 2015) predates the crowd. M0024 tested only the one-year lag because an
allocator's ``lookback`` also sets when the window opens, so the memory is read through
``prepare_market`` from the whole market instead (5 years here, not the paper's 10-20: a name needs
MIN_OBS past same-month returns, so the early 1996-1998 months are cash in every arm alike).

Score on data date d (the last session before month T): the mean of the same-calendar-month
returns of T-12, T-24, ... up to K years back, from the stock's own bars (a month's return is
last close over the prior month's last close, only when consecutive; ``m0024.month_table``). A
name needs at least MIN_OBS of those months, else it is unscored in every arm alike. Frame is the
N20 host: F4 screen, 20 equal monthly slots, fractional shares at Gotrade real fees, SPY 200-day
switch.

Arms (six): SAME5 (treatment: highest 5-year same-month mean), SAME3 (dose: 3 years),
REV5 (mirror: lowest 5-year mean), R1 and R2 (blind draws, seeds 515, 516, switch on) and
R1-NOSW (always invested, no opinion, no switch: prices the switch and acting; it repeats a book
the lab already ran as a twin of the M0505-style blind draw host, which is expected).
SUCCESS: SAME5 beats the better of R1/R2 by more than 2 points a year funded, REV5 loses to R1,
SAME5 is at least as good as SAME3, positive 2009-2015 edge vs SPY.
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
from seer_engine.lab.methods.m0024_same_month_seasonality import month_table, target_month
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

ADDED = date(2026, 11, 8)
MODES = ("same", "reverse", "blind")
MEMORY_BARS = 1320  # recorded in params only: the memory is 5 years, read via prepare_market
MIN_OBS = 3
MARKET = "SPY"

NOSW = replace(N20, trend=None)


@dataclass(frozen=True, slots=True)
class MemParams:
    """``inner`` is the host's screen, switch, book size and weighting; ``years`` how many past
    same-month returns are averaged; ``mode`` the ranking."""

    inner: FactorParams
    mode: str = "same"
    years: int = 5
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        for name in ("years", "seed"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
        if not 1 <= self.years <= 5:
            raise ValueError(f"years must be 1..5 (the lookback holds 5), got {self.years}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "years": str(self.years), "seed": str(self.seed),
               "min_obs": str(MIN_OBS), "bars": str(MEMORY_BARS)}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> MemParams:
    if not isinstance(params, MemParams):
        raise TypeError(f"params must be MemParams, got {type(params).__name__}")
    return params


def same_month_mean(table: Mapping[int, float], month: int, years: int) -> float | None:
    """Mean return of the same calendar month over the previous ``years`` years, or None when the
    stock has fewer than MIN_OBS of them."""
    vals = [table[month - 12 * k] for k in range(1, years + 1) if month - 12 * k in table]
    if len(vals) < MIN_OBS:
        return None
    return float(np.mean(vals))


def choose(rows: list[FactorRow], means: Mapping[str, float], params: MemParams) -> list[FactorRow]:
    pool = [r for r in rows if r.symbol not in EXCLUDED and r.symbol in means]
    if params.mode == "same":
        key = {r.symbol: -means[r.symbol] for r in pool}
    elif params.mode == "reverse":
        key = {r.symbol: means[r.symbol] for r in pool}
    else:
        key = {r.symbol: float(draw(params.seed, r.symbol)) for r in pool}
    pool.sort(key=lambda r: (key[r.symbol], r.symbol))
    return pool[: params.inner.top]


@dataclass
class MemPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)
    tables: dict[str, dict[int, float]] = field(default_factory=dict, repr=False)

    def table(self, symbol: str) -> dict[int, float]:
        if symbol not in self.tables:
            self.tables[symbol] = month_table(self.history[symbol])
        return self.tables[symbol]


class SameMonthMemoryAllocator:
    """The lab's index-member book ranked on its multi-year same-calendar-month average."""

    id = "M0515"

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

    def _run(self, prepared: MemPrepared | None, history: Mapping[str, History],
             members: AbstractSet[str], data_date: date, p: MemParams) -> tuple[Target, ...]:
        if not trend_on(history, data_date, p.inner):
            return ()
        if prepared is None:
            rows = factor_rows(history, members, data_date, p.inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, p.inner)
        month = target_month(data_date)
        means: dict[str, float] = {}
        for r in rows:
            if r.symbol in EXCLUDED:
                continue
            if prepared is None:
                h = history.get(r.symbol)
                tab = month_table(h) if h is not None else {}
            else:
                tab = prepared.table(r.symbol)
            m = same_month_mean(tab, month, p.years)
            if m is not None:
                means[r.symbol] = m
        return targets_from_rows(choose(rows, means, p), p)  # type: ignore[arg-type]

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(None, history, members, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> MemPrepared:
        return MemPrepared(history, prepare_factor(history))

    def prepare_market(self, market: Any) -> MemPrepared:
        """The multi-year memory is read from the whole market's bars, not the lookback-cut slice.

        An allocator's ``lookback`` also sets when the window opens (M0024 hit this), so the memory
        cannot ride on it. Only months ending well before ``data_date`` (T-12 and earlier) are
        read, so the full history adds no look-ahead; a name with fewer than MIN_OBS such months
        is unscored in every arm alike. The history-only ``prepare`` path, which the contract
        drives on a two-year fixture, therefore targets nothing."""
        return MemPrepared(market.history, prepare_factor(market.history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, MemPrepared):
            raise TypeError(f"prepared must be MemPrepared, got {type(prepared).__name__}")
        return self._run(prepared, prepared.history, members, data_date, _check(params))


MEMORY = SameMonthMemoryAllocator()


def _v(suffix: str, params: MemParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0515-{suffix}", family="M0515",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=MEMORY, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0515",
    name="Stocks that did well in this same calendar month in past years",
    family="stock-calendar-month-seasonality",
    source_kind="paper",
    source_ref="Keloharju, Linnainmaa & Nyberg (2016), Return seasonalities, Journal of Finance 71(4), NBER w20815",
    parent_id=None,
    hypothesis=(
        "Published 2016 (working paper 2014, so the dev window ends before the crowd): a stock's "
        "return in a calendar month tends to repeat in the same month in later years, and the "
        "average over many past years is a cleaner signal than the single last year M0024 tested "
        "(M0024's one-year book lost 2 of 4 walk-forward folds and held high-volatility names). "
        "Here the memory is capped at 5 years because the lab's lookback also sets the window "
        "start; the paper's 10-20 years is not expressible. Score = mean of the same-month "
        "returns of the previous 5 years (at least 3 present). Hold the 20 highest F4-screened "
        "point-in-time index members each month in equal fractional slots at Gotrade real fees "
        "behind SPY's 200-day switch. Arms: SAME5, SAME3 (dose), REV5 (mirror), R1 and R2 (blind "
        "draws, seeds 515, 516, switch on) and R1-NOSW (always invested, no opinion, no switch: "
        "prices the switch and acting; it is a book twin of an earlier blind always-invested host "
        "and is named as such, not counted as new). SUCCESS: SAME5 beats the better of R1/R2 by "
        "more than 2 points a year funded, REV5 loses to R1, SAME5 at least matches SAME3, and a "
        "positive 2009-2015 edge vs SPY. Prediction written now: the picks are last year's "
        "high-volatility names again, correlated with the momentum books, and the edge over blind "
        "draws is under 2 points."
    ),
    expected_failure=(
        "Monthly returns are mostly noise, so five same-month observations rank almost at random "
        "plus a volatility tilt; SAME5 equals the blind draws within draw noise and trails SPY in "
        "2009-2015, as M0024 and the calendar-anomaly books did. A published anomaly fades."
    ),
    candidates=(
        _v("SAME5", MemParams(N20, "same", 5), "Highest mean same-month return over 5 years, behind the switch"),
        _v("SAME3", MemParams(N20, "same", 3), "Dose: same, 3 years of memory"),
        _v("REV5", MemParams(N20, "reverse", 5), "Mirror: lowest 5-year same-month mean"),
        _v("R1", MemParams(N20, "blind", 5, 515), "Control: hash draw of 20, seed 515, behind the switch"),
        _v("R2", MemParams(N20, "blind", 5, 516), "Control: hash draw of 20, seed 516, measures draw noise"),
        _v("R1-NOSW", MemParams(NOSW, "blind", 5, 515), "Always invested, no opinion: prices acting"),
    ),
    seen_keys=(
        "concept:multi-year-same-month-average",
    ),
)
