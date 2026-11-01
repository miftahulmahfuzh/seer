"""M0431 — Volatility-scaled SPY at a higher target, beside a plain 200-day switch.

Source: variation of M0423 (Moreira & Muir 2017). M0423 aimed at a 15% volatility and sat at
about three quarters invested, which is time in cash in a rising decade. Here the target is high
enough that the book is rarely below 100% (no leverage, cap 1.0), and every arm that holds less
has a fixed-weight twin of the same average exposure, so the question is whether *timing* beats
just *holding less*. Pure; reads only SPY closes dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0423_volatility_managed_spy import Params as VolParams
from seer_engine.lab.methods.m0423_volatility_managed_spy import exposure as vol_exposure
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 1)


@dataclass(frozen=True, slots=True)
class Params:
    """``mode`` var (M0423's variance rule), sma (all in SPY above its 200-day average, else
    all cash) or flat (``flat`` percent always, no opinion). ``target_pct`` is the annualized
    volatility aimed at, in percent; ``n`` the trailing window (21 days; 200 for sma)."""

    mode: str = "var"
    n: int = 21
    target_pct: int = 25
    flat: int = 0

    def as_dict(self) -> dict[str, str]:
        return {"mode": self.mode, "n": str(self.n), "target_pct": str(self.target_pct),
                "flat_pct": str(self.flat)}


def exposure(history: Mapping[str, History], data_date: date, p: Params) -> Decimal:
    if p.mode == "sma":
        h = history.get("SPY")
        i = None if h is None else h.index_of(data_date)
        if h is None or i is None or i < p.n:
            return Decimal(0)
        c = np.asarray(h.close[i - p.n + 1 : i + 1], dtype=float)
        return Decimal(1) if c[-1] > c.mean() else Decimal(0)
    return vol_exposure(history, data_date, VolParams(mode=p.mode, n=p.n,
                                                       target_pct=p.target_pct, flat=p.flat))


class HighTargetAlloc:
    """SPY alone, weighted by the exposure rule above; empty (all cash) when the weight is 0."""

    id = "M0431"

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


ALLOC = HighTargetAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0431-{suffix}", family="M0431",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=ALLOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0431",
    name="Volatility-scaled SPY at a higher target, with a 200-day switch comparison",
    family="volatility-managed-exposure",
    source_kind="variation",
    source_ref="M0423 (Moreira & Muir 2017, Volatility-Managed Portfolios)",
    parent_id="M0423",
    hypothesis=(
        "M0423 scaled SPY down when recent swings were large and lost to SPY at a 15% target "
        "(about what a fixed share in SPY earns). Raise the target so the book is rarely below "
        "100% (cap 1.0, no leverage), monthly, 5% steps, fractional shares at Gotrade fees. "
        "Published 2017, so the dev window predates the crowd; 2009-2015 is the first filter. "
        "Average monthly exposure on the first trading day of each month, 1996-2015-10-16, read "
        "from SPY closes before the run and no returns: 25% target 0.895, 35% target 0.934, "
        "200-day switch in-market 0.735. Arms: VAR25 and VAR35 (variance rule, 21 days), SMA200 "
        "(all SPY above its 200-day average, else cash), and the no-opinion twins FLAT90 "
        "(equal exposure to VAR25), FLAT73 (equal exposure to SMA200) and FLAT100 (the zero of "
        "the dial; VAR35's twin is between FLAT90 and FLAT100). The signal is real only if VAR25 "
        "beats FLAT90 and SMA200 beats FLAT73; it beats SPY only if it beats FLAT100, since "
        "holding less is a bet against a rising market."
    ),
    expected_failure=(
        "Every managed arm loses to FLAT100 (plain SPY) in 2009-2015, a bull decade with no bear "
        "market, and so loses to SPY: dodging the rare spikes pays less than the cash time "
        "costs, and the variance rule re-sizes most months at Gotrade's minimum fee. The higher "
        "target shrinks the gap to SPY toward zero without crossing it, which would make the "
        "rule an expensive way to hold SPY. SMA200 repeats M0084: false alarms cost more than the "
        "two crashes saved. Volatility timing is widely published, so a dev edge would likely fade."
    ),
    candidates=(
        _v("VAR25", Params(mode="var", n=21, target_pct=25), "variance rule at 25% target"),
        _v("VAR35", Params(mode="var", n=21, target_pct=35), "variance rule at 35% target"),
        _v("SMA200", Params(mode="sma", n=200), "plain 200-day switch, all in or all cash"),
        _v("FLAT90", Params(mode="flat", flat=90), "dressing: equal average exposure to VAR25"),
        _v("FLAT73", Params(mode="flat", flat=73), "dressing: equal average exposure to SMA200"),
        _v("FLAT100", Params(mode="flat", flat=100), "dressing: always fully invested"),
    ),
    seen_keys=("concept:volatility-managed-spy", "concept:high-target-vol-scaling",
               "concept:spy-200d-switch-vs-flat-exposure"),
)
