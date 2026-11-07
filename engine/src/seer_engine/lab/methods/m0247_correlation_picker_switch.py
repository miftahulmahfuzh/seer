"""M0247 — Is average correlation a switch on the stock PICKER rather than on the market?

Source: a variation of M0182 (average correlation as a market clock), applied to the lab's best
recorded residual-momentum book, M0032-N20-RAW-FRAC-GT (parent chassis M0007). Pollet & Wilson
(2010) is the correlation reading; the question of whether it times a picker is the lab's own.
Idea: M0182 found that tightly-linked markets paid SPY well and loosely-linked ones paid it
little. A stock picker needs stocks that differ from each other, so the two should point
opposite ways: LOW correlation should be the picker's good market. If so, correlation is a
measurement of when picking works and applies to every stock book the lab owns.

The wrapper runs the residual-momentum allocator (``RESIDMOM``) unchanged and only decides whether
it may hold on data date d. The reading is M0182's own (``band_state``): average pairwise
correlation of daily returns among the 100 busiest point-in-time members, over 63 sessions,
compared with its own last 31 readings spanning 300 sessions. ``at or below`` the band means
"low", ``at or above`` means "high". No reading (early history, a data gap) means the book is
held, as in M0182, so a gap never turns into a bet.

Arms, all fixed before any result (``seer_engine`` books at Gotrade's real fees, fractional):

    * ``NEVER``: control. The book never steps aside and never reads correlation. It repeats the
      host's own book (M0032-N20-RAW-FRAC-GT) under a new allocator id, so the lab will record it
      as a book twin of the host. Expected, costs no look, and not a new book.
    * ``LO20``: hold only while correlation is at or below its 20th percentile (about a fifth of
      months): the picker-friendly reading.
    * ``LO33``: the dose rung, bottom third (about a third of months).
    * ``HI80``: the mirror. Hold only while correlation is at or above its 80th percentile. If the
      idea is real this must lose.
    * ``PLC20`` and ``PLC33``: placebos. Same share of months in the book as ``LO20`` and ``LO33``,
      picked by a date hash that never reads a price. They price what stepping aside costs when
      the opinion is random, which is what the lab needs to tell a dead rule from a badly dressed
      one.

The trade count stays comfortable: a 20-name monthly book that is in the market a fifth of the time
still opens and closes many positions.

Pure: reads only bars dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    N20,
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
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 7)
WINDOW = 63  # sessions of returns behind each correlation reading
_HASH = 2654435761  # Knuth's multiplicative constant: the placebo never reads a price
_SALT = 17  # fixed before any result, shifts which days the hash lands on; the first that let the contract probes see a target

Rule = Literal["none", "lo", "hi", "placebo"]
_RULES: tuple[str, ...] = ("none", "lo", "hi", "placebo")


@dataclass(frozen=True, slots=True)
class CorrPickParams:
    """``band`` is the quantile that marks the edge for lo/hi; for a placebo it is the share of
    months the book is held (the hash cut), so a placebo and its lo twin hold equal shares."""

    inner: ResidParams
    rule: Rule = "none"
    band: Decimal = Decimal("0.2")

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if not isinstance(self.rule, str) or self.rule not in _RULES:
            raise ValueError(f"rule must be one of {_RULES}, got {self.rule!r}")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise TypeError(f"band must be a finite Decimal, got {self.band!r}")
        if not Decimal("0.01") <= self.band <= Decimal("0.99"):
            raise ValueError(f"band must be in [0.01, 0.99], got {self.band}")

    def as_dict(self) -> dict[str, str]:
        return {**self.inner.as_dict(), "rule": self.rule,
                "band": format(self.band.normalize(), "f"), "window": str(WINDOW)}


def _check(params: object) -> CorrPickParams:
    if not isinstance(params, CorrPickParams):
        raise TypeError(f"params must be CorrPickParams, got {type(params).__name__}")
    return params


@dataclass(frozen=True, slots=True, eq=False)
class CorrPickPrepared:
    resid: ResidPrepared = field(repr=False)
    panel: Panel | None = field(repr=False)


def _placebo_held(data_date: date, share: Decimal) -> bool:
    """In the book on a date-hash fraction ``share`` of days, chosen without any price."""
    u = (((data_date.toordinal() + _SALT) * _HASH) % 2**32) / 2**32
    return u < float(share)


def _held(panel: Panel | None, members: AbstractSet[str], data_date: date,
          p: CorrPickParams) -> bool:
    if p.rule == "none":
        return True
    if p.rule == "placebo":
        return _placebo_held(data_date, p.band)
    state = None if panel is None else band_state(panel, members, data_date, WINDOW, p.band)
    if state is None:
        return True  # no reading: the book is held, as in M0182
    return state[1] if p.rule == "lo" else state[0]


class CorrelationPickerSwitch:
    """Residual momentum's book, held only while the correlation reading (or the placebo) says so."""

    id = "M0247"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(RESIDMOM.lookback(p.inner), CORR_LOOKBACK)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        panel = build_panel(history, "SPY") if p.rule in ("lo", "hi") else None
        if not _held(panel, members, data_date, p):
            return ()
        return RESIDMOM.targets(history, members, data_date, held, p.inner)

    def prepare(self, history: Mapping[str, History]) -> CorrPickPrepared:
        return CorrPickPrepared(RESIDMOM.prepare(history), build_panel(history, "SPY"))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CorrPickPrepared):
            raise TypeError(f"prepared must be CorrPickPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not _held(prepared.panel, members, data_date, p):
            return ()
        return RESIDMOM.targets_prepared(prepared.resid, members, data_date, held, p.inner)


SWITCH = CorrelationPickerSwitch()
BASE = ResidParams(N20, scaled=False)  # M0032-N20-RAW-FRAC-GT's configuration, verbatim


def _v(suffix: str, rule: Rule, band: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0247-{suffix}", family="M0247", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=CorrPickParams(BASE, rule, Decimal(band)),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0247",
    name="Is stock picking only worth doing when stocks move apart? Correlation as a switch on the picker",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="variation of M0182 (average correlation as a market clock); chassis "
               "M0032-N20-RAW-FRAC-GT; reading from Pollet & Wilson (2010), JFE 96(3)",
    parent_id="M0182",
    hypothesis=(
        "M0182 showed that for SPY, months when the 100 busiest index members move closely "
        "together were the good ones and months when they move independently were the poor ones. "
        "That is about the MARKET. A stock picker needs stocks that differ from one another to "
        "have anything to pick, so low correlation should be the picker's best market even though "
        "it is SPY's worst: the two should point opposite ways. If that holds, correlation is "
        "a measurement of when picking works and would apply to every stock book the lab owns. "
        "Test: the lab's best fractional real-fee residual-momentum book (top-20 raw residual "
        "momentum, SPY-200 gate, equal weights, monthly; M0032-N20-RAW-FRAC-GT) unchanged, held "
        "only while correlation (63-session, 100 busiest members, against its own last 31 "
        "readings) is at or below its 20th percentile (LO20), at or below its 33rd (LO33, dose "
        "rung), or at or above its 80th (HI80, the mirror, which must lose). Two placebos hold "
        "the same share of months as LO20 and LO33, chosen by a date hash that reads no price "
        "(PLC20, PLC33). NEVER is the always-held control with no opinion; it repeats the host's "
        "book under a new allocator id and will record as a book twin of M0032-N20-RAW-FRAC-GT, "
        "which is expected and is not a new book. Published 2010, so the dev window may show an "
        "edge the crowd has since traded away. SUCCESS: LO beats NEVER on 2009-2015 AND on a "
        "majority of folds AND HI80 loses AND LO beats its placebo. Assumption written now: with "
        "no reading the book is held. Trade count should stay over 100."
    ),
    expected_failure=(
        "Correlation and dispersion are close cousins and the lab's dispersion clock (M0118) was "
        "empty in both directions; M0182 found a correlation spike arrives after the crash, not "
        "before. The most likely result is that LO and HI both land at or below NEVER and near "
        "their placebos: sitting out most months of a book that earns +37% a year costs more than "
        "any timing opinion earns, so even a real signal is drowned by the time out of market (the "
        "lab's own measured dial, insight 462). The residual-momentum chassis also has a drawdown "
        "of about 20.6% against a 20% bar and kin that read test-failed, so even a clean win here "
        "may be refused at promotion for kin, not for merit."
    ),
    candidates=(
        _v("NEVER", "none", "0.2", "Control: the host book always held, no opinion"),
        _v("LO20", "lo", "0.2", "Hold only in the lowest-correlation fifth of readings"),
        _v("LO33", "lo", "0.3333", "Dose rung: hold in the lowest-correlation third"),
        _v("HI80", "hi", "0.8", "Mirror: hold only in the highest-correlation fifth; must lose"),
        _v("PLC20", "placebo", "0.2", "Placebo: held a fifth of days by date hash, no price read"),
        _v("PLC33", "placebo", "0.3333", "Placebo: held a third of days by date hash, no price read"),
    ),
    seen_keys=("concept:correlation-as-picker-switch",),
)
