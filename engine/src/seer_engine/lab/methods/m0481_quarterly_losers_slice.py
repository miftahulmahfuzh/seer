"""M0481 — A fixed 20% slice of five-year losers beside SPY, re-picked only every quarter.

Source: variation on M0450 (rejected: one-month losers slice trailed SPY) and M0165 (its always-held
five-year slice, S20-ALWAYS, led SPY by 0.3 points a year but failed the fall and luck bars). The
five-year reversal idea was published in 1985 (De Bondt & Thaler), so dev likely overstates it.

Why a new allocator: the sim has no quarterly cadence and adding one touches the web mirrors. The
allocator instead *freezes the picks*: on every monthly session it ranks as of the first bar of the
current quarter (``every=3``) and holds those names at today's prices, equal slots; a pick that has
left the index or screen since goes to SPY. The monthly resize band still trims drift, but the names
change four times a year, not twelve. ``every=1`` is the monthly twin (the M0165-S20-ALWAYS shape in
this allocator's id, so it records as a book twin of that trial: expected, costs no look).

Arms (four): Q-LOSERS (the idea), M-LOSERS (monthly twin, to price the cadence), Q-WINNERS (control:
same shape on five-year winners), SPY-ONLY (share 0: no opinion; its digest is new under this id and
should record as a book twin of the earlier always-SPY trial, M0251-HOLD).
SUCCESS: Q-LOSERS beats SPY TR on deposits, beats Q-WINNERS, beats M-LOSERS after fees, and leads in
2009-2015.
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
from seer_engine.lab.methods.m0069_long_term_reversal import F60, LtrParams, choose, LTR
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import LazyPrepared, last_close, scale_weight, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import prepare_factor

ADDED = date(2026, 11, 8)
CORE = "SPY"


@dataclass(frozen=True, slots=True)
class QuarterParams:
    ltr: LtrParams
    share: Decimal = Decimal("0.2")
    every: int = 3  # months between re-picks: 1 or 3

    def __post_init__(self) -> None:
        if not isinstance(self.ltr, LtrParams):
            raise TypeError("ltr must be LtrParams")
        if self.every not in (1, 3):
            raise ValueError("every must be 1 or 3")
        if not Decimal(0) <= self.share < Decimal(1):
            raise ValueError("share must be in [0, 1)")

    def as_dict(self) -> dict[str, str]:
        out = {"share": str(self.share), "every": str(self.every)}
        for k, v in self.ltr.as_dict().items():
            out[f"ltr.{k}"] = v
        return out


def _check(params: object) -> QuarterParams:
    if not isinstance(params, QuarterParams):
        raise TypeError(f"params must be QuarterParams, got {type(params).__name__}")
    return params


def pick_date(spy: History, data_date: date, every: int) -> date:
    """The first SPY bar of the current ``every``-month block, never after ``data_date``."""
    if every == 1:
        return data_date
    m0 = ((data_date.month - 1) // every) * every + 1
    start = np.datetime64(date(data_date.year, m0, 1), "D")
    i = int(np.searchsorted(spy.dates, start, side="left"))
    if i >= len(spy) or spy.dates[i] > np.datetime64(data_date, "D"):
        return data_date
    return spy.dates[i].astype(date)


class QuarterlyLosersAllocator:
    id = "M0481"

    def lookback(self, params: Any) -> int:
        return LTR.lookback(_check(params).ltr)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (CORE,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (CORE,)

    def uses_members(self, params: Any) -> bool:
        return _check(params).share > 0

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets_prepared(self.prepare(history), members, data_date, held, params)

    def prepare(self, history: Mapping[str, History]) -> LazyPrepared:
        return _Prep(history, prepare_factor(history))  # type: ignore[return-value]

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        hist = prepared.history
        spy = hist.get(CORE)
        if spy is None or spy.index_of(data_date) is None:
            return ()
        share = p.share
        px: dict[str, Target] = {}
        core = target_from_close(CORE, last_close(spy, data_date), to_weight(Decimal(1) - share))
        slots = p.ltr.inner.top
        if share > 0:
            snap = pick_date(spy, data_date, p.every)
            chosen = {r.symbol for r in choose(prepared.factor.rows_on(members, snap, p.ltr.inner), p.ltr)}
            now = {r.symbol: r for r in prepared.factor.rows_on(members, data_date, p.ltr.inner)}
            w = equal_weight(slots)
            for s in sorted(chosen):
                r = now.get(s)
                t = target_from_close(s, r.close, w) if r is not None else None
                if t is not None:
                    px[s] = t
            empty = slots - len(px)
            rest = w * empty
            core_w = (core.weight if core is not None else Decimal(0))
            targets = []
            for s, t in px.items():
                v = scale_weight(t.weight, share)
                if v is not None:
                    targets.append(_with(t, v))
            if core is not None:
                extra = scale_weight(to_weight(rest), share) if rest >= WEIGHT_QUANTUM else None
                total = core_w + (extra or Decimal(0))
                targets.insert(0, _with(core, to_weight(total)))
            return tuple(targets)
        return (core,) if core is not None else ()


from dataclasses import dataclass as _dc, field as _field, replace as _replace


def _with(t: Target, w: Decimal) -> Target:
    return _replace(t, weight=w)


@_dc
class _Prep:
    history: Mapping[str, History] = _field(repr=False)
    factor: Any = _field(repr=False)


ALLOC = QuarterlyLosersAllocator()


def _v(suffix: str, params: QuarterParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0481-{suffix}", family="M0481", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=ALLOC, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


LOSERS = LtrParams(F60, side="losers")
WINNERS = LtrParams(F60, side="winners")

METHOD = Method(
    id="M0481",
    name="A fixed slice of five-year losers beside SPY, re-picked only every quarter",
    family="stock-core-satellite",
    source_kind="variation",
    source_ref="Variation of M0450 and M0165 (De Bondt & Thaler 1985, Journal of Finance 40(3), long-term reversal)",
    parent_id="M0450",
    hypothesis=(
        "Long-term reversal was published in 1985, so dev is well after the crowd. M0450's monthly "
        "one-month-losers slice trailed SPY (5.7% a year against 7.2%) and its winners control "
        "(6.3%); M0165's always-held five-year slice (S20-ALWAYS) earned 7.5% a year against SPY's "
        "7.2% on deposits. Both pay Gotrade's fees on monthly resizing. A five-year signal moves "
        "slowly, so freezing the picks for a quarter should cut trading by about two thirds while "
        "keeping the signal. The book holds 80% SPY and a 20% slice of the 20 five-year losers "
        "(months -60..-13), fractional at real fees on monthly-hold-frac-gotrade, picks frozen at "
        "each quarter's first session. Arms: Q-LOSERS (the idea); M-LOSERS (monthly re-pick, prices "
        "the cadence; a book twin of M0165-S20-ALWAYS, expected); Q-WINNERS (control, five-year "
        "winners); SPY-ONLY (no opinion; a book twin of the earlier always-SPY trial, expected). "
        "Success: Q-LOSERS beats SPY TR on deposits, beats Q-WINNERS and M-LOSERS, and leads SPY in "
        "2009-2015."
    ),
    expected_failure=(
        "The lead is too thin to clear the luck bar (DSR 0.90 at the lab's N); M0165 already "
        "showed the slice earns only about 0.3 points over SPY and the fall stays near SPY's 55%. "
        "Quarterly freezing will probably look the same as monthly because the signal barely moves; "
        "the survivorship-free missing losers that died flatter the slice on dev."
    ),
    candidates=(
        _v("Q-LOSERS", QuarterParams(LOSERS, Decimal("0.2"), 3), "20% five-year losers, picks frozen each quarter"),
        _v("M-LOSERS", QuarterParams(LOSERS, Decimal("0.2"), 1), "Monthly re-pick twin of the same slice"),
        _v("Q-WINNERS", QuarterParams(WINNERS, Decimal("0.2"), 3), "Control: five-year winners, same shape"),
        _v("SPY-ONLY", QuarterParams(LOSERS, Decimal("0"), 3), "No opinion: SPY alone, same rules and fees"),
    ),
    seen_keys=("concept:quarterly-resize-five-year-losers-slice", "concept:core-satellite-spy-losers"),
)
