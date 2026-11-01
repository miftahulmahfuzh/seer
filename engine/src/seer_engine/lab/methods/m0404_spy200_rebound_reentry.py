"""M0404 — SPY's 200-day switch with a fast way back in after a crash bottom.

Source: variation of M0211 (breadth versions of the switch), by way of M0113 (the buy-back
trigger) which holds the same frame.
Idea: every breadth reading of when to LEAVE lost to SPY's own 200-day switch on worst fall, so
the exit is not the missing piece. The switch's known cost is the slow return after a V-shaped
bottom (it sat out 2009). M0113 already ran price-above-an-average and positive-return
triggers for the way back in, and found every price-above-a-line trigger re-entered mid-crash.
The one trigger it never priced is a REBOUND OF A FIXED SIZE OFF THE TROUGH: come back only
once SPY has climbed x% off the lowest close of the current below-200-day episode. That asks
for proof of a bottom rather than proof of a bounce, which is a different thing from
"above the 50-day".

Frame, deliberately M0113's: SPY only at full weight, monthly check, fractional shares at
Gotrade's real fees on the owner's deposits, the same 253-bar lookback, so the paired
difference against the SPY200 control is the buy-back trigger alone. The exit is fixed in
every switching arm (SPY close strictly under its 200-day average, ``trend_on`` unchanged);
the asymmetry runs through ``held``. The trough is read from closes only: the lowest close
since the last session SPY closed above its own 200-day average, looking back at most
LOOKBACK sessions. Reads only bars dated <= ``data_date``. Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0084_trend_switch_price import FABER_MONTHS
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 11, 1)
BENCH = "SPY"
SMA_N = 200
#: M0084 / M0113's constant, so every arm is scored on the same sessions.
LOOKBACK = max(SMA_N, 23 * (FABER_MONTHS + 1))
EXIT_GATE = FactorParams(rank="momentum", trend=(BENCH, SMA_N))

Entry = Literal["sma200", "sma50", "rebound", "always"]
_ENTRIES: tuple[str, ...] = ("sma200", "sma50", "rebound", "always")


@dataclass(frozen=True, slots=True)
class ReboundParams:
    """How SPY is bought back. ``rebound`` is the fraction off the trough (rebound arm only)."""

    entry: Entry = "sma200"
    rebound: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.entry, str) or self.entry not in _ENTRIES:
            raise ValueError(f"entry must be one of {_ENTRIES}, got {self.entry!r}")
        if isinstance(self.rebound, bool) or not isinstance(self.rebound, (int, float)):
            raise TypeError(f"rebound must be a number, got {type(self.rebound).__name__}")
        if self.entry == "rebound":
            if not 0.0 < self.rebound <= 0.5:
                raise ValueError(f"rebound must be in (0, 0.5], got {self.rebound}")
        elif self.rebound != 0.0:
            raise ValueError(f"rebound must be 0 for entry={self.entry!r}, got {self.rebound}")

    def as_dict(self) -> dict[str, str]:
        return {"entry": self.entry, "rebound": str(self.rebound)}


def _check(params: object) -> ReboundParams:
    if not isinstance(params, ReboundParams):
        raise TypeError(f"params must be ReboundParams, got {type(params).__name__}")
    return params


def trough_close(h: History, i: int) -> float | None:
    """Lowest close of the current below-200-day episode ending at bar ``i``.

    Walks back from ``i`` until a bar closes above its own 200-day average (the episode's
    start) or the lookback runs out. None when there is not enough history to place a 200-day
    average at ``i``.
    """
    close = h.close
    if i + 1 < SMA_N:
        return None
    lo = max(SMA_N - 1, i - (LOOKBACK - 1))
    trough = float(close[i])
    for j in range(i, lo - 1, -1):
        if close[j] > float(np.mean(close[j + 1 - SMA_N : j + 1])):
            break
        trough = min(trough, float(close[j]))
    return trough


def entry_on(h: History | None, data_date: date, p: ReboundParams) -> bool:
    """True when the buy-back trigger fires on ``data_date``. Reads only bars dated <= it."""
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    close = h.close
    if p.entry == "sma50":
        return i + 1 >= 50 and bool(close[i] > float(np.mean(close[i + 1 - 50 : i + 1])))
    t = trough_close(h, i)
    if t is None or t <= 0:
        return False
    return bool(close[i] >= t * (1.0 + p.rebound))


class ReboundTrendSwitch:
    """100% SPY, fixed 200-day exit, a variant's own way back in. Nothing else is held."""

    id = "M0404"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _on(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
            p: ReboundParams) -> bool:
        if p.entry == "always":
            return True
        if BENCH in held or p.entry == "sma200":
            return trend_on(history, data_date, EXIT_GATE)
        # Out of the market: back in on the plain 200-day test OR on the arm's fast trigger.
        return (trend_on(history, data_date, EXIT_GATE)
                or entry_on(history.get(BENCH), data_date, p))

    def _run(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
             p: ReboundParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        if not self._on(history, data_date, held, p):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


SWITCH = ReboundTrendSwitch()


def _v(suffix: str, params: ReboundParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0404-{suffix}", family="M0404", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0404",
    name="SPY's 200-day switch with a fast way back in after a crash bottom",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0211 (breadth versions of the switch) via M0113 (the buy-back)",
    parent_id="M0211",
    hypothesis=(
        "The 200-day switch is old (published 1992 banded, 2007 Faber), so no new anomaly and no "
        "fade argument. Every breadth reading of when to leave (M0205, M0211) lost to SPY's own "
        "200-day switch on worst fall, so the exit is the good half and stays fixed. The costly "
        "half is the return after a V-shaped bottom: it sat out 2009. M0113 priced buy-backs that "
        "fire on price above a line (50-day, 20-day, 20-day high) and found they re-enter "
        "mid-crash; it never priced a rebound of fixed size off the trough of the current "
        "below-200-day episode, which asks for proof of a bottom instead of proof of a bounce. "
        "Arms fixed before the run, monthly, SPY only, fractional, Gotrade fees, owner deposits, "
        "M0113's 253-bar lookback so the window matches: SPY200 (plain switch, control), SMA50 "
        "(back in above the 50-day or over the 200-day; close to M0113-SMA50, kept as the "
        "known price-above-a-line arm), REB10 and REB15 (back in once SPY closes 10% / 15% "
        "above the lowest close since it last closed above its 200-day average), and ALWAYS "
        "(SPY held every session, the no-opinion arm, so what the habit of switching costs can be "
        "separated from what the opinion earns). SUCCESS: a rebound arm beats SPY200 in 2009-2015 "
        "without a deeper worst fall than SPY200's. Assumption: the trough is read from closes "
        "since the last close above the 200-day average, capped at 253 sessions back."
    ),
    expected_failure=(
        "Fast re-entry buys the 2000-2002 and 2008 bear-market rallies (a 10% bounce off a low is "
        "routine inside a bear market: 2001, 2002 and late 2008 all had several) and gives back "
        "the switch's whole benefit, a deeper worst fall than SPY200 with no 2009 gain to pay for "
        "it. REB15 is more protected but may re-enter barely before the control. Trade counts stay "
        "in the tens over 22 years, so profit factor and the luck bar are close to meaningless; "
        "the funded return, worst fall and the 2009-2015 split are the readable numbers. "
        "2009-2015 contained no bear market, so a rebound rule can look good there for the "
        "wrong reason. No interest on cash is modelled, which flatters SPY and penalises every "
        "switching arm."
    ),
    candidates=(
        _v("SPY200", ReboundParams("sma200"),
           "Control: the plain symmetric 200-day switch, monthly"),
        _v("SMA50", ReboundParams("sma50"),
           "Fast arm: out under the 200-day, back in above the 50-day OR over the 200-day (M0113 priced the 50-day alone)"),
        _v("REB10", ReboundParams("rebound", 0.10),
           "Out under the 200-day, back in 10% above the episode's lowest close"),
        _v("REB15", ReboundParams("rebound", 0.15),
           "As REB10 with a larger rebound required: more proof of a bottom, later entry"),
        _v("ALWAYS", ReboundParams("always"),
           "No-opinion arm: SPY held every session, never in cash"),
    ),
    seen_keys=(
        "concept:spy200-rebound-off-trough-reentry",
        "concept:fast-reentry-after-sma200-exit",
        "concept:asymmetric-trend-switch-reentry",
    ),
)
