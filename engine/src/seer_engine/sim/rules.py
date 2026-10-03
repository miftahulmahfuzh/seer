"""Trade rules as a value (P7a, handover D2).

Design §5's trade shape used to be module constants (``SLOTS``, ``TIME_STOP_DAYS``,
``COST_RATE``) and hard-wired code paths. ``TradeRules`` carries every execution lever as one
frozen value:

- ``DESIGN_V0`` is §5 exactly. It is the only rule set with ``engine="bracket_v0"``, and it is
  executed by the unchanged ``sim.size_picks`` + ``sim.step`` path (``backtest.runner``), so the
  closed A, A2 and B records stay byte-identical by construction.
- Every other rule set has ``engine="book"`` and is executed by ``sim.book.step_book``.
  ``V0_BOOK`` is §5 replayed by the book engine; it exists only for the parity test.

Selection levers (slot count, sizing, universe, exposure switch, vol targeting) are not here:
they are functions of history and live in the allocators (``strategies.allocator``).

Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from seer_engine import dates

Engine = Literal["bracket_v0", "book"]
Cadence = Literal["daily", "weekly", "monthly"]
Entry = Literal["limit", "open_limit", "open"]

OPEN_LIMIT_BAND = Decimal("0.02")
RESIZE_BAND = Decimal("0.01")
SHARE_QUANTUM = Decimal("0.0001")
DEFAULT_ETFS: frozenset[str] = frozenset({"SPY", "QQQ"})
LEVERAGED_ETFS: frozenset[str] = frozenset({"SSO", "QLD", "UPRO", "TQQQ"})

_ENGINES: tuple[str, ...] = ("bracket_v0", "book")
_CADENCES: tuple[str, ...] = ("daily", "weekly", "monthly")
_ENTRIES: tuple[str, ...] = ("limit", "open_limit", "open")
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DEFAULT_COST = Decimal("0.001")
_MAX_COST = Decimal("0.05")
_V0_ID = "design-v0"


def _bool(name: str, x: object) -> bool:
    if not isinstance(x, bool):
        raise TypeError(f"{name} must be a bool, got {type(x).__name__}")
    return x


def _opt_count(name: str, x: object) -> int | None:
    if x is None:
        return None
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int or None, got {type(x).__name__}")
    if x < 1:
        raise ValueError(f"{name} must be >= 1, got {x}")
    return x


@dataclass(frozen=True, slots=True)
class TradeRules:
    """Every execution lever of a rule set. See the module docstring and the plan index."""

    id: str
    engine: Engine
    cadence: Cadence = "daily"
    entry: Entry = "limit"
    max_positions: int | None = None
    time_stop: int | None = None
    resize: bool = False
    fractional: bool = False
    dividends: bool = True
    idle_symbol: str | None = None
    cost_rate: Decimal = _DEFAULT_COST

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError(f"id must be a str, got {type(self.id).__name__}")
        if not _ID_RE.match(self.id):
            raise ValueError(f"id must be kebab-case ^[a-z0-9]+(-[a-z0-9]+)*$, got {self.id!r}")
        for name, allowed in (("engine", _ENGINES), ("cadence", _CADENCES), ("entry", _ENTRIES)):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a str, got {type(value).__name__}")
            if value not in allowed:
                raise ValueError(f"unknown {name} {value!r}; expected one of {allowed}")
        _opt_count("max_positions", self.max_positions)
        _opt_count("time_stop", self.time_stop)
        _bool("resize", self.resize)
        _bool("fractional", self.fractional)
        _bool("dividends", self.dividends)
        if self.idle_symbol is not None:
            if not isinstance(self.idle_symbol, str):
                raise TypeError(f"idle_symbol must be a str or None, got {type(self.idle_symbol).__name__}")
            if not self.idle_symbol:
                raise ValueError("idle_symbol must be non-empty")
        if not isinstance(self.cost_rate, Decimal):
            raise TypeError(f"cost_rate must be a Decimal, got {type(self.cost_rate).__name__}")
        if not self.cost_rate.is_finite() or not (0 <= self.cost_rate < _MAX_COST):
            raise ValueError(f"cost_rate must be in [0, {_MAX_COST}), got {self.cost_rate}")
        is_v0 = _lever_values(self) == _V0_LEVERS
        if self.engine == "bracket_v0" and not is_v0:
            raise ValueError("engine 'bracket_v0' is reserved for DESIGN_V0 (the unchanged §5 simulator)")
        if self.id == _V0_ID and self.engine != "bracket_v0":
            raise ValueError(f"id {_V0_ID!r} is reserved for DESIGN_V0 (engine 'bracket_v0')")


def _lever_values(r: TradeRules) -> tuple[object, ...]:
    """Every field of ``r`` (``id`` and ``engine`` included), in field order."""
    return tuple(getattr(r, f.name) for f in fields(r))


_V0_LEVERS: tuple[object, ...] = (
    _V0_ID,
    "bracket_v0",
    "daily",
    "limit",
    4,
    5,
    False,
    False,
    False,
    None,
    _DEFAULT_COST,
)

DESIGN_V0 = TradeRules(
    id=_V0_ID,
    engine="bracket_v0",
    cadence="daily",
    entry="limit",
    max_positions=4,
    time_stop=5,
    resize=False,
    fractional=False,
    dividends=False,
    idle_symbol=None,
    cost_rate=Decimal("0.001"),
)
V0_BOOK = replace(DESIGN_V0, id="v0-book", engine="book")

MONTHLY_HOLD = TradeRules(id="monthly-hold", engine="book", cadence="monthly", entry="open_limit", resize=True)
MONTHLY_HOLD_TBILL = replace(MONTHLY_HOLD, id="monthly-hold-tbill", idle_symbol="BIL")
WEEKLY_HOLD = TradeRules(id="weekly-hold", engine="book", cadence="weekly", entry="open_limit", resize=True)
DAILY_SWITCH = TradeRules(id="daily-switch", engine="book", cadence="daily", entry="open_limit", resize=False)
DAILY_SWITCH_TBILL = replace(DAILY_SWITCH, id="daily-switch-tbill", idle_symbol="BIL")
SWING_T10 = TradeRules(id="swing-t10", engine="book", cadence="daily", entry="limit", time_stop=10)
SWING_T20 = replace(SWING_T10, id="swing-t20", time_stop=20)
SWING_T20_OPEN = replace(SWING_T20, id="swing-t20-open", entry="open_limit")

PRESETS: tuple[TradeRules, ...] = (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    WEEKLY_HOLD,
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
)


def _rules(x: object) -> TradeRules:
    if not isinstance(x, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(x).__name__}")
    return x


def is_decision_session(rules: TradeRules, session: date) -> bool:
    """True when ``session`` is one on which ``rules`` acts on the strategy's targets.

    daily: every session; weekly: the first NYSE session of its ISO (year, week); monthly: the
    first NYSE session of its calendar (year, month). ValueError when ``session`` is not an
    NYSE session.
    """
    _rules(rules)
    if isinstance(session, datetime) or not isinstance(session, date):
        raise TypeError(f"session must be a date, got {type(session).__name__}")
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if rules.cadence == "daily":
        return True
    prev = dates.prev_session(session)
    if rules.cadence == "weekly":
        return session.isocalendar()[:2] != prev.isocalendar()[:2]
    return (session.year, session.month) != (prev.year, prev.month)


def rule_owner_inputs(rules: TradeRules) -> tuple[str, ...]:
    """The Gotrade features ``rules`` needs that the owner has not verified, sorted and unique.

    ``market-on-open`` (entry "open"), ``fractional``, ``etf:<symbol>`` (an idle instrument
    outside ``DEFAULT_ETFS``) and ``fee`` (a cost rate other than 0.1% per side). Empty means
    executable under the conservative owner-input defaults.
    """
    _rules(rules)
    out: set[str] = set()
    if rules.entry == "open":
        out.add("market-on-open")
    if rules.fractional:
        out.add("fractional")
    if rules.idle_symbol is not None and rules.idle_symbol not in DEFAULT_ETFS:
        out.add(f"etf:{rules.idle_symbol}")
    if rules.cost_rate != _DEFAULT_COST:
        out.add("fee")
    return tuple(sorted(out))


def _pct(x: Decimal) -> str:
    """``x`` as a plain percentage string: Decimal('0.001') -> '0.1%'."""
    return f"{format((x * 100).normalize(), 'f')}%"


def describe_rules(rules: TradeRules) -> tuple[str, ...]:
    """One fixed plain-English line per field of ``rules``, in field order.

    Used by the dev report and the pre-registration file. Deterministic (golden-tested).
    """
    _rules(rules)
    lines: list[str] = [f"Rule set: {rules.id}."]
    if rules.engine == "bracket_v0":
        lines.append("Engine: the design §5 bracket simulator, unchanged.")
    else:
        lines.append(
            "Engine: the target-weight book; a position the strategy stops wanting is sold at the "
            "next open, and stops and take-profits are fixed at entry."
        )
    if rules.cadence == "daily":
        lines.append("Decisions: every session, from the previous session's close.")
    elif rules.cadence == "weekly":
        lines.append("Decisions: the first session of each ISO week, from the previous session's close.")
    else:
        lines.append("Decisions: the first session of each calendar month, from the previous session's close.")
    if rules.entry == "limit" and rules.engine == "bracket_v0":
        lines.append(
            "Entry: a buy limit at the strategy's limit price for the next session; it fills only "
            "when the low trades below the limit, at the lower of the open and the limit."
        )
    elif rules.entry == "limit":
        lines.append(
            "Entry: a buy limit at the strategy's limit price for the next session; it fills only "
            "when the low trades below the limit, at the lower of the open and the limit. A new "
            f"position the strategy gives no limit price is bought at a limit of the last close + "
            f"{_pct(OPEN_LIMIT_BAND)} instead, filled the same way."
        )
    elif rules.entry == "open_limit":
        lines.append(
            f"Entry: a buy limit at the last close + {_pct(OPEN_LIMIT_BAND)} for the next session; it "
            "fills only when the low trades below the limit, at the lower of the open and the limit."
        )
    else:
        lines.append("Entry: a market order at the next open (needs owner verification: market-on-open).")
    if rules.max_positions is None:
        lines.append("Positions: as many as the strategy targets.")
    else:
        lines.append(f"Positions: at most {rules.max_positions} at a time (the idle instrument not counted).")
    if rules.time_stop is None:
        lines.append("Time stop: none.")
    else:
        lines.append(f"Time stop: sell at the next open once a position has been held {rules.time_stop} sessions.")
    if rules.resize:
        lines.append(
            f"Rebalance: on decision sessions, a held position is traded back to its target weight "
            f"at the open when it is off by at least {_pct(RESIZE_BAND)} of equity."
        )
    else:
        lines.append("Rebalance: none; a held position keeps its shares until it exits.")
    if rules.fractional:
        lines.append(f"Shares: fractional, rounded down to {SHARE_QUANTUM} share (needs owner verification).")
    else:
        lines.append("Shares: whole shares only.")
    if rules.dividends:
        lines.append("Dividends: cash dividends are credited on the ex-date.")
    else:
        lines.append("Dividends: not credited.")
    if rules.idle_symbol is None:
        lines.append("Idle cash: held as cash, earning nothing.")
    else:
        lines.append(f"Idle cash: the unallocated weight is held in {rules.idle_symbol} on decision sessions.")
    lines.append(f"Costs: {_pct(rules.cost_rate)} per side.")
    return tuple(lines)
