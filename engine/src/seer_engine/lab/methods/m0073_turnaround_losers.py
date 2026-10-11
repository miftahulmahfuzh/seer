"""M0073 — Turnaround losers: big companies that fell hardest over five years but have risen over the past year.

Source: variation of M0069 (De Bondt & Thaler 1985, long-term reversal), with the turnaround
confirmation that value-plus-momentum work (Asness, Moskowitz & Pedersen 2013, "Value and
Momentum Everywhere") says sharpens a contrarian sort.
Idea: M0069's five-year losers beat SPY only through 2000-2002 and the 2009 junk rally, and lost
70% at their worst because the book kept buying companies that were still falling (2001-2002,
2008). Waiting for the second half of the turnaround -- the stock has started rising again --
should keep the rebounds and skip the falling knives.

The frame is M0069's: F4's point-in-time members with the $5 price and 20M-dollar volume screen,
monthly, equal weights, fractional shares at Gotrade's real fees on ``monthly-hold-frac-gotrade``,
slots the screen cannot fill in SPY. The pool is the bottom ``pool`` fraction of the eligible
names by the formation return

    formation(s) = return_window(close, mom_n, 252)    (c[-253] / c[-1-mom_n] - 1)

and inside that pool the book picks ``top`` names by ``pick``:

- ``"recent"``: the highest last-12-month return, r12 = c[-1] / c[-253] - 1 (the turnaround);
- ``"confirmed"``: only names with r12 > 0 and the close above its own 200-day average, then the
  most beaten (lowest formation) first -- the losers that have turned, not the ones turning most;
- ``"knife"``: the LOWEST r12 -- the control, losers still falling, which should do worst.

r12 and the 200-day average read the member's own bars through d; a name has at least
``mom_n + 1`` of them (F4's eligibility), so both are always defined. When ``inner.trend`` is set
and SPY is below its 200-day average, the whole book is cash, as in M0069.

Assumptions, written before the run: the reserved idea said "best last-12-month return (or simply
a positive one, and price above the 200-day average)", so both readings run as separate variants
rather than one being chosen; "bottom fifth" is taken among the members eligible that day, rounded
up. Reads only bars dated <= d.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    DV_N,
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_rows,
    prepare_factor,
    trend_on,
)

ADDED = date(2026, 10, 11)

Pick = Literal["recent", "confirmed", "knife"]
_PICKS: tuple[str, ...] = ("recent", "confirmed", "knife")
R12_N = 252
SMA_N = 200


@dataclass(frozen=True, slots=True)
class TurnParams:
    """``inner`` is F4's screen, formation window, book size and trend gate; ``pool`` the loser cut."""

    inner: FactorParams
    pick: Pick = "recent"
    pool: float = 0.2
    fill: str | None = "SPY"  # unfilled slots go here; None leaves them in cash

    def __post_init__(self) -> None:
        if not isinstance(self.inner, FactorParams):
            raise TypeError(f"inner must be FactorParams, got {type(self.inner).__name__}")
        if self.inner.rank != "momentum":
            raise ValueError("inner.rank must be 'momentum' (the formation return)")
        if self.inner.mom_n < R12_N + 1:
            raise ValueError(f"inner.mom_n must be > {R12_N} so r12 is always defined")
        if not isinstance(self.pick, str) or self.pick not in _PICKS:
            raise ValueError(f"pick must be one of {_PICKS}, got {self.pick!r}")
        if not isinstance(self.pool, float) or not 0.0 < self.pool <= 1.0:
            raise ValueError(f"pool must be a float in (0, 1], got {self.pool!r}")
        if self.fill is not None and (not isinstance(self.fill, str) or not self.fill):
            raise ValueError(f"fill must be None or a non-empty str, got {self.fill!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"pick": self.pick, "pool": repr(self.pool), "fill": self.fill or ""}
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> TurnParams:
    if not isinstance(params, TurnParams):
        raise TypeError(f"params must be TurnParams, got {type(params).__name__}")
    return params


def _recent(h: History, data_date: date) -> tuple[float, bool] | None:
    """(r12, close > own 200-day average) from bars dated <= d; None when undefined."""
    i = h.index_of(data_date)
    if i is None or i < max(R12_N, SMA_N - 1):
        return None
    c = h.close
    r12 = float(c[i] / c[i - R12_N] - 1.0)
    above = bool(c[i] > float(np.mean(c[i + 1 - SMA_N : i + 1])))
    if not math.isfinite(r12):
        return None
    return r12, above


def choose(rows: list[FactorRow], history: Mapping[str, History], data_date: date,
           params: TurnParams) -> list[FactorRow]:
    ranked = sorted((r for r in rows if r.symbol not in EXCLUDED),
                    key=lambda r: (r.momentum, r.symbol))
    pool = ranked[: math.ceil(len(ranked) * params.pool)]
    scored: list[tuple[float, str, FactorRow]] = []
    for r in pool:
        h = history.get(r.symbol)
        rec = _recent(h, data_date) if h is not None else None
        if rec is None:
            continue
        r12, above = rec
        if params.pick == "recent":
            scored.append((-r12, r.symbol, r))
        elif params.pick == "knife":
            scored.append((r12, r.symbol, r))
        elif r12 > 0.0 and above:  # confirmed: turned, most beaten first
            scored.append((r.momentum, r.symbol, r))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in scored[: params.inner.top]]


def build(chosen: list[FactorRow], history: Mapping[str, History], data_date: date,
          params: TurnParams) -> tuple[Target, ...]:
    w = equal_weight(params.inner.top)
    out: list[Target] = []
    for row in chosen:
        t = target_from_close(row.symbol, row.close, w)
        if t is not None:
            out.append(t)
    empty = params.inner.top - len(out)
    if params.fill is not None and empty > 0:
        rest = w * empty
        h = history.get(params.fill)
        if rest >= WEIGHT_QUANTUM and h is not None and h.index_of(data_date) is not None:
            t = target_from_close(params.fill, last_close(h, data_date), to_weight(rest))
            if t is not None:
                out.append(t)
    return tuple(out)


@dataclass
class TurnPrepared:
    history: Mapping[str, History] = field(repr=False)
    factor: FactorPrepared = field(repr=False)


class TurnaroundLosersAllocator:
    """M0069's five-year-loser pool, picked on how the last year went.

    Held symbols get no special treatment: a name that leaves the chosen set is signal-exited.
    """

    id = "M0073"

    def lookback(self, params: Any) -> int:
        # As M0069: the fixed instruments' need only. A member without mom_n + 1 bars is not
        # eligible yet and its slot holds SPY.
        p = _check(params)
        return max(DV_N, p.inner.vol_n + 1, p.inner.trend[1] if p.inner.trend is not None else 0)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        out = {p.inner.trend[0]} if p.inner.trend is not None else set()
        if p.fill is not None:
            out.add(p.fill)
        return tuple(sorted(out))

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return (p.fill,) if p.fill is not None else ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, p.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.inner)
        return build(choose(rows, history, data_date, p), history, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> TurnPrepared:
        return TurnPrepared(history, prepare_factor(history))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, TurnPrepared):
            raise TypeError(f"prepared must be TurnPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, p.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.inner)
        return build(choose(rows, prepared.history, data_date, p), prepared.history, data_date, p)


TURN = TurnaroundLosersAllocator()

F60 = FactorParams(rank="momentum", top=20, mom_n=1260, mom_skip=252, trend=None)  # months -60..-13
F36 = replace(F60, mom_n=756)  # months -36..-13
F60_T = replace(F60, trend=("SPY", 200))


def _v(suffix: str, params: TurnParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0073-{suffix}", family="M0073", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=TURN, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0073",
    name="Turnaround losers: big companies that fell hardest over five years but have risen over the past year",
    family="stock-long-term-reversal",
    source_kind="variation",
    source_ref=(
        "Variation of M0069 (De Bondt & Thaler 1985, Journal of Finance 40(3)); the value-plus-"
        "momentum confirmation from Asness, Moskowitz & Pedersen (2013), Value and Momentum "
        "Everywhere, Journal of Finance 68(3)"
    ),
    parent_id="M0069",
    hypothesis=(
        "Long-term reversal was published in 1985 and value-plus-momentum in 2013, so the dev "
        "window 1996-2015 sits after the first and before the second became crowded. M0069 showed "
        "that buying five-year losers pays only through crashes and rebounds, and that most of its "
        "70% fall came from buying companies still falling (2001-2002, 2008). Require the second "
        "half of a turnaround before buying. Each month, among point-in-time S&P 500 / Nasdaq-100 "
        "members on F4's $5 / 20M-dollar screen, take the bottom fifth by the months -60..-13 "
        "return and hold 20 of them equal weight, fractional at Gotrade's real fees on "
        "monthly-hold-frac-gotrade, empty slots in SPY. Variants: R12-N20 (the 20 with the best "
        "last-12-month return), UP-N20 (only names up over the last 12 months and above their own "
        "200-day average, most beaten first; few qualify in a bear market, so it drifts into SPY), "
        "R12-L36 (the 36-month formation), R12-N20-T (R12-N20 in cash while SPY is under its 200-day "
        "average) and KNIFE-N20 (the control: the 20 with the WORST last 12 months, still falling, "
        "which should do worst). Success: a turnaround variant beats SPY TR on dev with a worst "
        "fall at or under 20%, beats KNIFE-N20 and M0069's L60-N20, and keeps an edge in 2009-2015 "
        "beyond the single year 2009."
    ),
    expected_failure=(
        "The 12-month filter turns the book into momentum among cheap names, so its month-to-month "
        "result may move with the failed momentum books (the gate's behaviour kin) and it inherits "
        "momentum's crash: in spring 2009 the turnaround names were the defensive ones, and the "
        "junk rally that made M0069's average came off a bottom with negative trailing returns, so "
        "that rebound is lost. In 2001-2002 many old-economy losers were already rising, so the "
        "filter keeps that episode; in 2008 the losers that had risen in 2007 fell with everything "
        "else, so the worst fall is still likely well over 20% without the switch. Equal weight "
        "among beaten names bets against SPY's big-company drift, so 2010-2015 likely trails SPY. "
        "Survivorship still flatters losers that lived. UP-N20 may simply hold SPY much of the "
        "time and tie it."
    ),
    candidates=(
        _v("R12-N20", TurnParams(F60, pick="recent"),
           "Bottom fifth by five-year return, the 20 with the best last 12 months, SPY in empty slots"),
        _v("UP-N20", TurnParams(F60, pick="confirmed"),
           "Bottom fifth, only names up on the year and above their 200-day average, most beaten first"),
        _v("R12-L36", TurnParams(F36, pick="recent"),
           "Bottom fifth by three-year return, the 20 with the best last 12 months"),
        _v("R12-N20-T", TurnParams(F60_T, pick="recent"),
           "R12-N20 while SPY is above its 200-day average, cash below"),
        _v("KNIFE-N20", TurnParams(F60, pick="knife"),
           "Control: bottom fifth, the 20 with the WORST last 12 months (still falling)"),
    ),
    seen_keys=(
        "concept:long-term-reversal-turnaround",
        "concept:value-plus-momentum-confirmation",
        "doi:10.1111/jofi.12021",
    ),
)
