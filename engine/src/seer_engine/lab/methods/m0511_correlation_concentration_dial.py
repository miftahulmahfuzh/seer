"""M0511 — Correlation as a concentration dial, never a switch: always invested, fewer names
when stocks move apart.

Source: a variation of M0247 (average correlation as a switch on the residual-momentum picker).
Pollet & Wilson (2010) is the correlation reading; the dial is the lab's own.
Idea: M0247 found low correlation beat high correlation as a picker switch, but every on/off arm
lost heavily to the always-held book because time in cash cost more than the signal earned. Here
nothing ever steps aside. The residual-momentum book (raw, top names, equal weight, monthly,
Gotrade fees, fractional) is held every month and the correlation reading only changes how many
names it holds: few when stocks move apart (more to pick from), many when they move together.

The reading is M0182's own (``band_state``): average pairwise correlation of daily returns among
the 100 busiest point-in-time members over 63 sessions, against its own last 31 readings. The
lowest third is "at or below the 33rd percentile", the highest third "at or above the 67th".
No reading (early history, a data gap) means the middle size, 20, so a gap never turns into a bet.

Arms, all fixed before any result. Four are gate-off (no cash months at all, the idea as
stated); two repeat the dial and its fixed control behind the host's SPY 200-day switch, so the
2x2 of "dial on/off" x "gate on/off" is priced and the cost of the habit is readable:

    * ``FIX20``: control. 20 names always, no gate, no reading.
    * ``DIAL``: 10 names in the low third, 30 in the high third, 20 otherwise.
    * ``MIRROR``: 30 in the low third, 10 in the high third. If the idea is real this must lose.
    * ``PLC``: placebo with the dial's own mix. 10, 20 or 30 names chosen by a date hash that never
      reads a price, one third of time each, held for 91 calendar days at a time so it flips about as
      slowly as the 63-session reading does. This is the "sticky" placebo; its turnover is
      compared with the dial's after the run.
    * ``DIAL-GATE`` and ``FIX20-GATE``: the same two behind the SPY 200-day switch. ``FIX20-GATE``
      repeats M0032-N20-RAW-FRAC-GT's book under a new allocator id, so the lab records it as a
      book twin of that host. Expected, costs no look, and is not a new book.

Pure: reads only bars dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N10,
    N20,
    N30,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
)
from seer_engine.lab.methods.m0182_average_correlation_clock import (
    LOOKBACK as CORR_LOOKBACK,
)
from seer_engine.lab.methods.m0182_average_correlation_clock import (
    Panel,
    band_state,
    build_panel,
)
from decimal import Decimal

from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 9)
WINDOW = 63  # sessions of returns behind each correlation reading
_THIRD = Decimal("0.3333")
_TWO_THIRDS = Decimal("0.6667")
_HASH = 2654435761  # Knuth's multiplicative constant: the placebo never reads a price
_SALT = 17  # fixed before any result
_BLOCK_DAYS = 91  # placebo holds one size for a quarter, as slow as the reading

Rule = Literal["fixed", "dial", "mirror", "placebo"]
_RULES: tuple[str, ...] = ("fixed", "dial", "mirror", "placebo")


@dataclass(frozen=True, slots=True)
class DialParams:
    """``few``, ``mid`` and ``many`` are the same residual-momentum book at 10, 20 and 30 names."""

    few: ResidParams
    mid: ResidParams
    many: ResidParams
    rule: Rule = "fixed"

    def __post_init__(self) -> None:
        for name in ("few", "mid", "many"):
            if not isinstance(getattr(self, name), ResidParams):
                raise TypeError(f"{name} must be ResidParams")
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"rule must be one of {_RULES}, got {self.rule!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"rule": self.rule, "window": str(WINDOW)}
        for name in ("few", "mid", "many"):
            for k, v in getattr(self, name).as_dict().items():
                out[f"{name}.{k}"] = v
        return out


def _check(params: object) -> DialParams:
    if not isinstance(params, DialParams):
        raise TypeError(f"params must be DialParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class DialPrepared:
    resid: ResidPrepared = field(repr=False)
    panel: Panel | None = field(repr=False)


def _placebo_size(data_date: date) -> int:
    """0, 1 or 2 for few, mid, many: a date-hash thirds draw, fixed for a quarter at a time."""
    u = ((((data_date.toordinal() // _BLOCK_DAYS) + _SALT) * _HASH) % 2**32) / 2**32
    return 0 if u < 1 / 3 else (1 if u < 2 / 3 else 2)


def _size(panel: Panel | None, members: AbstractSet[str], data_date: date, p: DialParams) -> int:
    """0 few, 1 mid, 2 many."""
    if p.rule == "fixed":
        return 1
    if p.rule == "placebo":
        return _placebo_size(data_date)
    if panel is None:
        return 1
    low = band_state(panel, members, data_date, WINDOW, _THIRD)
    high = band_state(panel, members, data_date, WINDOW, _TWO_THIRDS)
    if low is None or high is None:
        return 1
    if low[1]:  # at or below the 33rd percentile: stocks moving apart
        return 0 if p.rule == "dial" else 2
    if high[0]:  # at or above the 67th: stocks moving together
        return 2 if p.rule == "dial" else 0
    return 1


def _inner(p: DialParams, size: int) -> ResidParams:
    return (p.few, p.mid, p.many)[size]


class CorrelationConcentrationDial:
    """Residual momentum's book, always held, sized by the correlation reading (or the placebo)."""

    id = "M0511"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(max(RESIDMOM.lookback(x) for x in (p.few, p.mid, p.many)), CORR_LOOKBACK)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).mid)

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).mid)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        panel = build_panel(history, "SPY") if p.rule in ("dial", "mirror") else None
        inner = _inner(p, _size(panel, members, data_date, p))
        return RESIDMOM.targets(history, members, data_date, held, inner)

    def prepare(self, history: Mapping[str, History]) -> DialPrepared:
        return DialPrepared(RESIDMOM.prepare(history), build_panel(history, "SPY"))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, DialPrepared):
            raise TypeError(f"prepared must be DialPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = _inner(p, _size(prepared.panel, members, data_date, p))
        return RESIDMOM.targets_prepared(prepared.resid, members, data_date, held, inner)


DIAL = CorrelationConcentrationDial()


def _books(trend: bool) -> tuple[ResidParams, ResidParams, ResidParams]:
    def one(base: Any) -> ResidParams:
        return ResidParams(base if trend else replace(base, trend=None), scaled=False)
    return one(N10), one(N20), one(N30)


def _v(suffix: str, rule: Rule, trend: bool, rationale: str) -> Candidate:
    few, mid, many = _books(trend)
    return Candidate(id=f"M0511-{suffix}", family="M0511", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=DIAL, params=DialParams(few, mid, many, rule),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0511",
    name="Correlation as a concentration dial, never a switch: always invested, fewer names when stocks move apart",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="variation of M0247 (correlation as a picker switch); chassis "
               "M0032-N20-RAW-FRAC-GT with the SPY trend gate removed; reading from "
               "Pollet & Wilson (2010), JFE 96(3)",
    parent_id="M0247",
    hypothesis=(
        "M0247 found low correlation beat high correlation and a blind placebo by a small margin as "
        "a picker switch, but every on/off arm lost heavily to the always-held book because time "
        "in cash cost more than the signal earned. So keep the residual-momentum book always "
        "invested (no cash months) and let the correlation reading change only how concentrated it "
        "is: 10 names when correlation is in its lowest third (more to pick from), 30 names when it "
        "is in its highest third, 20 otherwise (and 20 when no reading exists). Correlation: 63 "
        "sessions, 100 busiest point-in-time members, against its own last 31 readings; terciles "
        "at the 33rd and 67th percentile. Published 2010, so the dev window may show an edge the "
        "crowd has since traded away. Arms: DIAL (the three-way dial), MIRROR (30 names when low, "
        "10 when high), FIX20 (control: 20 names always), PLC (placebo: 10, 20 or 30 names by a "
        "date hash that reads no price, a third of time each, one size held for 91 days, to sit near "
        "the dial's own turnover; the sticky placebo, its trade count and turnover are read after "
        "the run), plus DIAL-GATE and FIX20-GATE, the dial and its control behind the SPY "
        "200-day switch, so the 2x2 of dial x gate prices the habit. FIX20-GATE repeats M0032-N20-"
        "RAW-FRAC-GT's book under a new allocator id and will record as its book twin; that is "
        "expected and not a new book. All fractional at Gotrade's real fees. Assumption written "
        "now: the idea says no cash months, so the four main arms drop the trend gate. SUCCESS: "
        "DIAL beats FIX20 on 2009-2015 AND on a majority of folds AND MIRROR loses AND DIAL beats "
        "PLC."
    ),
    expected_failure=(
        "Concentration changes risk more than return, so the dial moves the fall, not the growth "
        "rate. With no gate the book will be at or above the host's ~20.6% worst fall and over the "
        "20% bar whatever the dial does, so it may fail on the fall alone. A wide book under high "
        "correlation is also the wrong direction for a momentum book in a crash, when names fall "
        "together. Ten names against thirty is also a coin-flip-sized difference in return (the "
        "lab's own draws span 7.5 pts a year), so a small dial lead is unreadable against the "
        "placebo."
    ),
    candidates=(
        _v("FIX20", "fixed", False, "Control: 20 names always, no gate, no reading"),
        _v("DIAL", "dial", False, "10 names when correlation is low, 30 when high, 20 between"),
        _v("MIRROR", "mirror", False, "Mirror: 30 names when correlation is low, 10 when high"),
        _v("PLC", "placebo", False, "Placebo: 10/20/30 by date hash, a quarter at a time"),
        _v("DIAL-GATE", "dial", True, "The dial behind the SPY 200-day switch"),
        _v("FIX20-GATE", "fixed", True, "Control behind the switch: host book, new allocator id"),
    ),
    seen_keys=("concept:correlation-as-concentration-dial",),
)
