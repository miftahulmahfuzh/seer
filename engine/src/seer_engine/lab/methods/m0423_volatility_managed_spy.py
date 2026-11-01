"""M0423 — Volatility-managed SPY: scale exposure by the inverse of last month's realized variance.

Source: Moreira & Muir (2017), "Volatility-Managed Portfolios", Journal of Finance.
Idea: volatility is persistent but the market's reward for bearing it is not proportional, so
holding less when recent variance is high and more when it is low improves risk-adjusted return.
The book is one instrument, SPY, with the rest in cash, so a decision is one order a month and
Gotrade's minimum fee barely bites. Exposure is never above 100%: no leverage (owner inputs).

Every arm reads only SPY closes dated <= data_date and sizes in 5% steps, so the book does not
re-size every month for nothing. Pure.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 1)

STEP = Decimal("0.05")
TRADING_DAYS = 252


@dataclass(frozen=True, slots=True)
class Params:
    """``mode``: ``var`` weight = min(1, target_vol^2 / realized variance); ``vol`` weight =
    min(1, target_vol / realized volatility); ``rev`` the mirror, 1.6 minus the ``var`` weight
    capped at 1 (more exposure when variance is high); ``flat`` always ``flat`` percent invested,
    no opinion. ``n`` is the trailing daily-return window, ``target_pct`` the annualized
    volatility the rule aims at, in percent."""

    mode: str = "var"
    n: int = 21
    target_pct: int = 15
    flat: int = 0

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "n": str(self.n), "target_pct": str(self.target_pct),
                "flat_pct": str(self.flat)}


def exposure(history: Mapping[str, History], data_date: date, p: Params) -> Decimal:
    """Invested fraction on data_date, floored to STEP; 0 when SPY has too few bars."""
    if p.mode == "flat":
        return Decimal(p.flat) / 100
    h = history.get("SPY")
    i = None if h is None else h.index_of(data_date)
    if h is None or i is None or i < p.n:
        return Decimal(0)
    c = np.asarray(h.close[i - p.n : i + 1], dtype=float)
    r = c[1:] / c[:-1] - 1.0
    var = float(np.var(r, ddof=1)) * TRADING_DAYS
    if not math.isfinite(var) or var <= 0.0:
        return Decimal(0)
    tv = p.target_pct / 100.0
    if p.mode == "vol":
        w = min(1.0, tv / math.sqrt(var))
    else:
        w = min(1.0, tv * tv / var)
        if p.mode == "rev":
            w = min(1.0, 1.6 - w)
    return (Decimal(repr(w)) / STEP).to_integral_value(rounding="ROUND_DOWN") * STEP


class VolManagedAlloc:
    """SPY alone, weighted by the exposure rule above; empty (all cash) when the weight is 0."""

    id = "M0423"

    def lookback(self, params: Params) -> int:
        return params.n + 1

    def symbols(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)

    def uses_members(self, params: Params) -> bool:
        return False

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        w = exposure(history, data_date, params)
        if w <= 0:
            return ()
        t = target_from_close("SPY", last_close(history.get("SPY"), data_date), w)
        return () if t is None else (t,)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = VolManagedAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0423-{suffix}", family="M0423",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALLOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0423",
    name="Volatility-managed SPY: scale exposure by inverse of last month's realized variance",
    family="volatility-managed-exposure",
    source_kind="paper",
    source_ref="Moreira & Muir 2017, Volatility-Managed Portfolios, J. Finance",
    parent_id=None,
    hypothesis=(
        "Hold SPY at weight min(1, c / realized variance of the prior 21 trading days), the rest "
        "in cash, re-sized monthly in 5% steps; c is a 15% annualized volatility target squared "
        "(0.0225), no leverage. Published 2017, so the dev window ends before the crowd traded it; "
        "2009-2015 (a bull decade where cash time costs most) is the first filter. One order a "
        "month in one instrument, fractional shares at Gotrade fees. Arms: VAR21 (the paper's "
        "rule), VAR63 (slower window), VOL21 (volatility not variance, same 15% target), FLAT80 "
        "(always 80% invested, no opinion: 80% is the average monthly exposure VAR21 and VAR63 "
        "would have held on SPY 1996-2015, 0.796 and 0.784, read from SPY closes before the run "
        "and no return), FLAT100 (always fully invested, the zero of the dial: what SPY costs "
        "with no opinion and no cash), and REV21 (the mirror: 1.6 minus the VAR21 weight, capped "
        "at 1, more exposure when variance is high). The signal is real only if VAR21 beats FLAT80 "
        "and REV21; whether it beats SPY depends on FLAT100 against FLAT80: holding less is itself "
        "a bet against a rising market."
    ),
    expected_failure=(
        "It fails 'beats SPY' like M0001 and M0003 did (own-volatility scaling fixed the fall but "
        "cut return to 6-7.6% against SPY about 7.9%) and like the 12% volatility target on SPY in "
        "P7a (5.3% a year, 20.2% worst fall): in a rising decade, average exposure under 100% is "
        "time in cash, and the variance spikes of 2008 and 2020 are rare enough that dodging them "
        "pays less than being out of the market pays in every calm year. FLAT80 probably matches "
        "VAR21 on return and the managed arms win only on worst fall. With a 15% target the rule "
        "is out for about a fifth of the time on average. The arms that react to variance may "
        "also churn: a 5% step on a 21-day window re-sizes most months and pays the Gotrade "
        "minimum each time."
    ),
    candidates=(
        _v("VAR21", Params(mode="var", n=21, target_pct=15), "paper rule: 21-day variance"),
        _v("VAR63", Params(mode="var", n=63, target_pct=15), "slower window: 63-day variance"),
        _v("VOL21", Params(mode="vol", n=21, target_pct=15), "volatility scaling, not variance"),
        _v("FLAT80", Params(mode="flat", flat=80), "dressing: always 80% invested, equal average exposure"),
        _v("FLAT100", Params(mode="flat", flat=100), "dressing: always fully invested, no opinion"),
        _v("REV21", Params(mode="rev", n=21, target_pct=15), "mirror: more exposure when variance is high"),
    ),
    seen_keys=("concept:volatility-managed-spy", "concept:variance-scaled-exposure"),
)
