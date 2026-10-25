"""M0253 -- The patient safety rule, put under a book that actually picks stocks.

Source: variation of M0245, which measured the shared SPY 200-day gate exit by exit. The switch
itself is old (Brock, Lakonishok and LeBaron 1992; Faber 2007), so no fade argument applies to
the gate; the residual-momentum book is Blitz, Huij and Martens (2011), widely published and
likely to have faded since, which is why the question is about the gate and not the ranking.
Reserved by Sera 20261025-1846.

WHY THIS METHOD EXISTS. M0245 found that nine of the gate's eleven 1994-2015 exits were false
alarms and that waiting for the 200-day average itself to turn down skipped five of them while
keeping both crash exits. But every M0245 arm held only SPY, so the result rests on four to six
selling decisions in twenty-one years and could not clear the 100-trade bar. The open question
is whether the patient rule survives a book that really trades.

THE BOOK. M0032's configuration verbatim: top-20 raw residual momentum, F4's screen, equal
weights, monthly, fractional shares at Gotrade's real fees, on the owner's monthly top-ups. Only
the gate changes: this allocator turns the inner book's own SPY-200 gate off and applies the
gate itself, with M0245's confirmation functions imported unchanged, so each paired difference
is the exit rule alone. GATE must reproduce M0032-N20-RAW-FRAC-GT.

THE SIX ARMS.
    * GATE -- the plain switch, the control; must reproduce the parent book.
    * FALL21 / FALL126 -- leave only once the 200-day average is below where it stood 21 or 126
      sessions ago.
    * CROSS -- leave only once the 50-day average is under the 200-day one (the death cross).
    * RISE21 -- the mirror, leaving only while the average still rises; must fail.
    * NOGATE -- the same book never stepping aside: the opinion removed. Without it the lab
      can say whether the patient rule beats the plain one, but not whether either gate is worth
      what its habit costs (insight 523).

Pure: reads only bars dated <= data_date; no clock, no I/O, no randomness.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, RESIDMOM, ResidParams
from seer_engine.lab.methods.m0245_gate_confirmation import (
    BENCH,
    LOOKBACK as GATE_LOOKBACK,
    SMA_GATE,
    ConfirmParams,
    confirmed,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import trend_on

ADDED = date(2026, 10, 25)

#: M0032's book with its own gate switched off; this allocator applies the gate instead.
INNER = ResidParams(replace(N20, trend=None), scaled=False)


@dataclass(frozen=True, slots=True)
class PatientParams:
    """Which exit rule sits over the book; ``gated=False`` is the never-step-aside arm."""

    confirm: ConfirmParams = ConfirmParams("none")
    gated: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.confirm, ConfirmParams):
            raise TypeError(f"confirm must be ConfirmParams, got {type(self.confirm).__name__}")
        if not isinstance(self.gated, bool):
            raise TypeError(f"gated must be a bool, got {type(self.gated).__name__}")
        if not self.gated and self.confirm != ConfirmParams("none"):
            raise ValueError("an ungated arm has no confirmation rule")

    def as_dict(self) -> dict[str, str]:
        out = {"gated": "yes" if self.gated else "no", "book": "M0032 N20 raw residual"}
        out.update({f"gate.{k}": v for k, v in self.confirm.as_dict().items()})
        return out


def _check(params: object) -> PatientParams:
    if not isinstance(params, PatientParams):
        raise TypeError(f"params must be PatientParams, got {type(params).__name__}")
    return params


def risk_on(history: Mapping[str, History], data_date: date, p: PatientParams) -> bool:
    """May the book hold stocks today? The plain gate, unless the slow market confirms nothing."""
    if not p.gated or trend_on(history, data_date, SMA_GATE):
        return True
    return not confirmed(history.get(BENCH), data_date, p.confirm)


class PatientGateStockBook:
    """M0032's residual-momentum book under the plain or the patient 200-day exit."""

    id = "M0253"

    def lookback(self, params: Any) -> int:
        _check(params)
        return max(RESIDMOM.lookback(INNER), GATE_LOOKBACK)

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return tuple(sorted({BENCH, *RESIDMOM.symbols(INNER)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not risk_on(history, data_date, _check(params)):
            return ()
        return RESIDMOM.targets(history, members, data_date, held, INNER)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not risk_on(prepared.history, data_date, _check(params)):
            return ()
        return RESIDMOM.targets_prepared(prepared, members, data_date, held, INNER)


ALLOC = PatientGateStockBook()


def _v(suffix: str, params: PatientParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0253-{suffix}", family="M0253", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0253",
    name="Put the patient safety rule under a real stock book, where it has enough trades to be judged",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref="variation of M0245 (its patient exit measured on a SPY-only book) on M0032's stock book",
    parent_id="M0245",
    hypothesis=(
        "M0245 measured the shared 200-day safety rule exit by exit and found it is insurance: "
        "nine of its eleven exits between 1994 and 2015 were false alarms costing 52 points of "
        "missed market, and only two were real crashes. Waiting for the 200-day average itself "
        "to turn down before selling skipped five of the nine false alarms, kept both crash "
        "exits (two months late each time), earned 0.9 to 1.8 points a year more on the owner's "
        "deposits and held the worst fall at 18.9% against the plain rule's 19.0%. Its mirror "
        "collapsed. But every M0245 arm held nothing but SPY, so the whole result rests on four "
        "to six selling decisions in twenty-one years and was correctly rejected as a "
        "measurement. The open question is whether the patient rule survives a book that "
        "actually picks stocks. This runs M0032's residual-momentum book (top 20, monthly, "
        "fractional shares at Gotrade's real fees, the owner's monthly top-ups) unchanged except "
        "for the gate, in six arms: GATE (the plain 200-day rule, the control, which must "
        "reproduce M0032-N20-RAW-FRAC-GT), FALL21 and FALL126 (exit only once the 200-day "
        "average is below where it stood 21 or 126 sessions ago), CROSS (the 50-over-200 death "
        "cross), RISE21 (the mirror, which must fail) and NOGATE (the same book never stepping "
        "aside, the arm with no opinion in it, so the cost of acting on the signal can be priced "
        "apart from the signal). SUCCESS: a patient arm beats GATE on the owner's deposits by at "
        "least half a point a year without a deeper worst fall than GATE's, and its 2009-2015 lag "
        "to SPY is smaller than GATE's. The likely failure: the book trades hundreds of times, so "
        "the gate's handful of flips is a small share of what happens to it and the gain washes "
        "out. The gate was published in 1992 and 2007 and the ranking in 2011, so a strong "
        "dev-window edge is likely to fade after 2015. Assumed without asking: the 200-day gate "
        "and 20 names as M0032 had them, and the comparison is read on the 1994-05 window that "
        "the 327-bar lookback imposes, so the GATE arm here is compared with M0032 only to check "
        "it reproduces, not for its level."
    ),
    expected_failure=(
        "The sample is still two crashes: a rule that sells about two months late looks good on "
        "a window whose two crashes were slow, and says nothing about a fast one like 2020. A "
        "stock book is also not SPY: in a bear market its 20 names can fall faster than the "
        "index, so selling two months late may cost far more than it did on SPY and the worst "
        "fall may come in well above GATE's. The book's own monthly rebuild already sheds losers, "
        "so the gate may matter less than M0245 suggested and all gate arms may land within "
        "noise of each other. The window has no 2009-2015 bear market, so any gate arm lags "
        "NOGATE there by construction. Fees at 15 or more turns a year could swamp a half-point "
        "difference. If the patient arms fail here, this family should be closed: the patient "
        "rule is a SPY-only curiosity."
    ),
    candidates=(
        _v("GATE", PatientParams(ConfirmParams("none")),
           "Control: M0032's book under the plain 200-day gate; must reproduce the parent"),
        _v("FALL21", PatientParams(ConfirmParams("fall", 21)),
           "Exit only once the 200-day average is below where it stood a month ago"),
        _v("FALL126", PatientParams(ConfirmParams("fall", 126)),
           "The same at half a year: the slowest rung and the fewest exits"),
        _v("CROSS", PatientParams(ConfirmParams("cross")),
           "Exit only once the 50-day average is under the 200-day one"),
        _v("RISE21", PatientParams(ConfirmParams("rise", 21)),
           "Mirror: exit only while the average still rises; must fail on both axes"),
        _v("NOGATE", PatientParams(gated=False),
           "No opinion: the same book never stepping aside, to price the gate's habit"),
    ),
    seen_keys=("concept:patient-gate-on-residual-momentum-book",),
)
