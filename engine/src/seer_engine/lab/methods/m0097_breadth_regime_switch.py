"""M0097 — Own the typical stock only when it is keeping up: equal-weight members when they lead SPY.

Source: Hussman (Jan 2025) on cap- vs equal-weight persistence; Blitz (2025), "Implications of
Increased Index Concentration for Active Investors"; RSP/SPY relative-strength rotation lore.
Reserved by Sera 20261011-1838 from the 20261011-1815 synthesis: every equal-slot book in the lab
loses ground whenever a few giants lead the market, and wins when the typical member keeps up.
Idea: time the bet itself, not the picks. Hold an equal-weight basket of big index members while
that basket's trailing total return beats SPY's; hold SPY while the giants lead.

On data_date d:

    * the **reading set** is the ``universe`` point-in-time members (S&P 500 ∪ Nasdaq-100, SPY
      excluded) with the highest median dollar volume (close x volume) over the last ``dv_n``
      bars, among those with a bar dated d and ``lookback_n`` bars of history behind it;
    * **lead** = mean over the reading set of close_i(d) / close_i(d - lookback_n bars) - 1,
      minus SPY's same-length return. Bars are split- and dividend-adjusted, so both are total
      returns;
    * **mode**: basket when lead > 0, SPY otherwise. With ``band`` > 0 the switch has a dead
      zone read from what the book holds: holding SPY, it moves to the basket only when
      lead > +band; holding the basket, it moves to SPY only when lead < -band; holding nothing
      (the first decision), the plain sign decides. ``always=True`` is the control: the basket
      every month, whatever the lead says;
    * **basket targets**: ``slots`` equal weights. ``slots == universe`` holds the whole reading
      set; ``slots < universe`` holds an evenly spaced sample of it by dollar-volume rank
      (ranks 1, 1+k, 1+2k, ... with k = universe // slots), so the sample spans the giants to
      the hundredth name instead of being the giants alone.

Why a 20-name sample and not the whole hundred (an assumption, written before the run): the book
simulator tops up a held name only when it is at least 1% of equity below its target
(``sim.rules.RESIZE_BAND``). In a 100-slot book every slot is 1% of equity, so a monthly
deposit is never added to a held name, and it is invested only through the few names that enter
the basket each month: cash would pile up and the test would measure idle deposits, not the
switch. Twenty 5% slots is the lab's standard book, so the sample carries the same deposit
drag as every book it is compared with. The full hundred is run once (T100-L6) so the drag is
measured rather than assumed. A switch to SPY sells everything and a switch back buys every
slot at full weight, which re-invests idle cash; the always-basket control has no such reset,
so a switch variant beating the control by a small margin may be that reset, not timing.

Known bias, written before the run: the reading set is d's members, so its trailing return
leans toward stocks that joined the index after rising (survivorship inside the lookback).
That tilts the lead toward the basket, i.e. toward the always-basket control.

Fractional shares at Gotrade's real fees, monthly (``monthly-hold-frac-gotrade``). Pure: reads
only bars dated <= d; ``held`` is used only to read the current mode for the band.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 11)
BENCH = "SPY"


@dataclass(frozen=True, slots=True)
class SwitchParams:
    lookback_n: int = 126  # bars in the lead's trailing return (about six months)
    universe: int = 100  # members in the reading set, by median dollar volume
    slots: int = 20  # basket names held (an evenly spaced sample of the reading set)
    band: float = 0.0  # hysteresis dead zone on the lead, in return units (0.01 = one point)
    dv_n: int = 60  # bars in the median dollar volume
    always: bool = False  # control: the basket every month, no switch

    def __post_init__(self) -> None:
        for name in ("lookback_n", "universe", "slots", "dv_n"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if self.slots > self.universe:
            raise ValueError(f"slots ({self.slots}) must be <= universe ({self.universe})")
        if isinstance(self.band, bool) or not isinstance(self.band, float) or not self.band >= 0.0:
            raise ValueError(f"band must be a float >= 0, got {self.band!r}")
        if not isinstance(self.always, bool):
            raise TypeError(f"always must be a bool, got {type(self.always).__name__}")

    def as_dict(self) -> dict[str, str]:
        return {"lookback_n": str(self.lookback_n), "universe": str(self.universe),
                "slots": str(self.slots), "band": repr(self.band), "dv_n": str(self.dv_n),
                "always": str(self.always)}


def _check(params: object) -> SwitchParams:
    if not isinstance(params, SwitchParams):
        raise TypeError(f"params must be SwitchParams, got {type(params).__name__}")
    return params


def _trailing(h: History, i: int, n: int) -> float | None:
    a, b = float(h.close[i - n]), float(h.close[i])
    if not (np.isfinite(a) and np.isfinite(b) and a > 0.0 and b > 0.0):
        return None
    return b / a - 1.0


def reading_set(history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                p: SwitchParams) -> list[tuple[str, float]]:
    """(symbol, trailing return) for the ``universe`` most-traded members, most-traded first."""
    need = max(p.lookback_n, p.dv_n)
    scored: list[tuple[float, str, float]] = []
    for s in sorted(members):
        if s == BENCH:
            continue
        h = history.get(s)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i < need:
            continue
        c = h.close[i - p.dv_n + 1 : i + 1]
        v = h.volume[i - p.dv_n + 1 : i + 1]
        dv = c * v
        if not np.all(np.isfinite(dv)):
            continue
        med = float(np.median(dv))
        r = _trailing(h, i, p.lookback_n)
        if r is None or not med > 0.0:
            continue
        scored.append((-med, s, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [(s, r) for _, s, r in scored[: p.universe]]


def lead(history: Mapping[str, History], rows: list[tuple[str, float]], data_date: date,
         p: SwitchParams) -> float | None:
    """The reading set's equal-weight trailing return minus SPY's; None with no reading.

    The dev store prices well over ``universe`` members on every dev session, so a short set
    only happens on small fixtures; it is read as it is rather than refused.
    """
    h = history.get(BENCH)
    if h is None or not rows:
        return None
    i = h.index_of(data_date)
    if i is None or i < p.lookback_n:
        return None
    spy = _trailing(h, i, p.lookback_n)
    if spy is None:
        return None
    total = 0.0
    for _, r in rows:  # left to right: the same float however much history is loaded
        total += r
    return total / len(rows) - spy


def basket_mode(x: float, held: frozenset[str], p: SwitchParams) -> bool:
    """True for the basket. The band reads the current mode from what the book holds."""
    in_spy = BENCH in held
    in_basket = any(s != BENCH for s in held)
    if p.band > 0.0 and in_spy and not in_basket:
        return x > p.band
    if p.band > 0.0 and in_basket and not in_spy:
        return x >= -p.band
    return x > 0.0


class BreadthSwitchAllocator:
    """Equal-weight big members while they lead SPY over the lookback; SPY otherwise.

    Held symbols get no special treatment: a basket name that leaves the sample is sold, and a
    switch sells the whole side being left.
    """

    id = "M0097"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(p.lookback_n, p.dv_n) + 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return (BENCH,)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        rows = reading_set(history, members, data_date, p)
        x = lead(history, rows, data_date, p)
        if x is None:
            return ()  # no full reading: stand aside rather than guess
        if not (p.always or basket_mode(x, held, p)):
            t = target_from_close(BENCH, last_close(history.get(BENCH), data_date), equal_weight(1))
            return () if t is None else (t,)
        step = p.universe // p.slots
        chosen = [s for s, _ in rows[::step][: p.slots]]
        w = equal_weight(p.slots)
        out: list[Target] = []
        for s in chosen:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


SWITCH = BreadthSwitchAllocator()


def _v(suffix: str, params: SwitchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0097-{suffix}", family="M0097", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0097",
    name="Own the typical stock only when it is keeping up: equal-weight index members when they lead SPY, SPY when the giants lead",
    family="breadth-regime-switch",
    source_kind="blog",
    source_ref=(
        "Hussman, Jan 2025 (cap- vs equal-weight persistence); Blitz (2025), Implications of "
        "Increased Index Concentration for Active Investors; RSP/SPY relative-strength rotation lore"
    ),
    parent_id=None,
    hypothesis=(
        "Sera's 20261011-1815 synthesis: every equal-slot book in the lab loses ground whenever a few "
        "giant companies lead the market and wins when the typical member keeps up, so time the bet "
        "itself instead of the picks. Equal- vs cap-weight relative strength is old lore (RSP listed "
        "2003); the concentration papers are 2024-2025, after the dev window, so dev sees the idea "
        "before any crowd traded it, but also before the 2016-2024 giant-led era it is meant for. "
        "Book: each month read the lead -- the equal-weight trailing total return of the 100 most-"
        "traded point-in-time S&P 500 / Nasdaq-100 members (60-day median dollar volume) minus SPY's "
        "over the same bars. Lead above zero: hold the basket, equal weights; else 100% SPY. Monthly, "
        "fractional shares at Gotrade's real fees (monthly-hold-frac-gotrade), funded on the owner's "
        "monthly top-up. The basket is an evenly spaced 20-name sample of the 100 by dollar-volume "
        "rank (5% slots), because the simulator only tops up a held name that is 1% of equity below "
        "target, so a 100-slot book would leave the monthly deposits in cash; T100-L6 holds all 100 "
        "to measure that drag. Variants: S20-L6 (the book), S20-L3 and S20-L12 (3 and 12 months), "
        "S20-L6-B1 (a one-point dead zone against whipsaw), S20-ALWAYS (control: the basket every "
        "month, no switch), T100-L6. SPY always is the benchmark itself. Success: a switch variant "
        "beats SPY TR with a worst fall under 20%, beats the always-basket control, is positive in "
        "2009-2015, and wins a majority of walk-forward folds."
    ),
    expected_failure=(
        "Relative strength between equal and cap weight is weakly persistent at monthly horizons, so "
        "the switch whipsaws: it moves into SPY after the basket has already lagged and back after it "
        "has already caught up, paying Gotrade's fees on 20 names each way for nothing. On dev "
        "(1996-2015) the equal-weight basket beat SPY in most years after 2000, so the switch may just "
        "track the always-basket control with extra cost and a few badly timed SPY months. Neither "
        "side of the switch has any crash protection: SPY fell about 55% in 2007-2009 and the basket "
        "will have fallen as much or more, so every variant very likely fails the 20% worst-fall "
        "limit; the idea can at best show a return edge that a later method would put behind a risk "
        "switch. The reading set is today's members, a small survivorship lean toward the basket."
    ),
    candidates=(
        _v("S20-L6", SwitchParams(lookback_n=126),
           "20-name sample of the 100 most-traded members while they lead SPY over 6 months; else SPY"),
        _v("S20-L3", SwitchParams(lookback_n=63),
           "The same switch read over 3 months: faster, more whipsaw"),
        _v("S20-L12", SwitchParams(lookback_n=252),
           "The same switch read over 12 months: slower, fewer trades"),
        _v("S20-L6-B1", SwitchParams(lookback_n=126, band=0.01),
           "The 6-month switch with a one-point dead zone, so a small lead does not flip the book"),
        _v("S20-ALWAYS", SwitchParams(lookback_n=126, always=True),
           "Control: the 20-name sample every month, no switch"),
        _v("T100-L6", SwitchParams(lookback_n=126, slots=100),
           "The 6-month switch holding all 100 names: measures the deposit drag of 1% slots"),
    ),
    seen_keys=(
        "concept:breadth-regime-switch",
        "concept:equal-weight-vs-cap-weight-relative-strength",
        "concept:rsp-spy-rotation",
    ),
)
