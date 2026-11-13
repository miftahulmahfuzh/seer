"""M0545 — fast out, slow back in: SPY's switch leaves under its 150-day average and returns
only above its 250-day average.

Source: variation of M0434, whose analysis proposed exactly this pair, "run once with an
always-invested arm, and then stop". M0434 found no single length beat SPY after 2009 (150 least
bad, 250 worst) while 200 won the full window. Here the two lengths work together: the exit is
the quick one (SPY closes under its 150-day average) and the way back in is the slow one (SPY
closes above its 250-day average). The state comes from ``held``: SPY held means we are in and
only the 150 test can take us out; SPY not held means we are out and only the 250 test can bring
us back. Frame is M0434's: SPY only at full weight, monthly check, fractional shares at Gotrade's
real fees on the owner's deposits, one 253-bar lookback. Reads only bars dated <= ``data_date``.
Pure.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0404_spy200_rebound_reentry import BENCH, LOOKBACK
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 11, 13)


@dataclass(frozen=True, slots=True)
class PairParams:
    """``exit_n`` leaves while held, ``entry_n`` returns while flat; (0, 0) means always invested."""

    exit_n: int = 150
    entry_n: int = 250

    def __post_init__(self) -> None:
        for name, v in (("exit_n", self.exit_n), ("entry_n", self.entry_n)):
            if isinstance(v, bool) or not isinstance(v, int):
                raise TypeError(f"{name} must be an int, got {type(v).__name__}")
            if v != 0 and not 20 <= v <= LOOKBACK:
                raise ValueError(f"{name} must be 0 or in [20, {LOOKBACK}], got {v}")
        if (self.exit_n == 0) != (self.entry_n == 0):
            raise ValueError("exit_n and entry_n are both 0 (no switch) or both set")

    def as_dict(self) -> dict[str, str]:
        return {"exit_n": str(self.exit_n), "entry_n": str(self.entry_n)}


def _check(params: object) -> PairParams:
    if not isinstance(params, PairParams):
        raise TypeError(f"params must be PairParams, got {type(params).__name__}")
    return params


class PairTrendSwitch:
    """100% SPY: stay while above the exit average, come back only above the entry average."""

    id = "M0545"

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

    def _run(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
             p: PairParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        if p.exit_n:
            n = p.exit_n if BENCH in held else p.entry_n
            if not trend_on(history, data_date, FactorParams(rank="momentum", trend=(BENCH, n))):
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


SWITCH = PairTrendSwitch()


def _v(suffix: str, params: PairParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0545-{suffix}", family="M0545",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=SWITCH, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0545",
    name="Fast out, slow back in: SPY switch leaving at 150 days and returning at 250",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0434, whose analysis proposed the 150-out, 250-in pair",
    parent_id="M0434",
    hypothesis=(
        "M0434 found no single length beat SPY after 2009 (150 days least bad, 250 worst) while "
        "200 won the full window. Test two lengths in one switch: exit when SPY closes under its "
        "150-day average, re-enter only when it closes above its 250-day average, monthly, SPY "
        "only, fractional, Gotrade fees, owner deposits, one 253-bar lookback. Arms fixed before "
        "the run: PAIR150-250 (treatment, the only new book); SMA200 (Control: the plain 200-day "
        "switch, repeats M0434-SMA200's book, itself a twin of M0430-SPY200's, a book twin by "
        "design); ALWAYS (Control: SPY every session, the no-opinion arm; repeats "
        "M0430-ALWAYS's book, never stepping aside). The always arm prices what acting costs, so "
        "the pair's habit can be told from its opinion. The moving-average switch is old (banded "
        "1992, Faber 2007) so expect fade. Judged first on 2009-2015. SUCCESS: the pair beats "
        "SMA200 in 2009-2015 AND on the 20-year funded return with a worst fall no deeper, a "
        "majority of walk-forward folds, DSR >= 0.90 at the N in force. Readable even if it "
        "fails: a pair that sits between 150 and 250 within noise closes the switch's length "
        "and hysteresis as dials, as M0434 said it would."
    ),
    expected_failure=(
        "The slow re-entry misses recoveries as M0404 and M0430 did, and the pair sits between "
        "the neighbours within noise. A monthly check means few decisions, so trade counts stay "
        "in the tens and profit factor and the luck bar mean little. 2009-2015 had no bear "
        "market, so exits there are only false alarms. Published anomalies fade: the dev window "
        "ends in 2015 and shows only the pre-crowd edge. No interest on cash is modelled, which "
        "flatters SPY's cash time."
    ),
    candidates=(
        _v("PAIR150-250", PairParams(150, 250),
           "Treatment: exit under the 150-day average, re-enter only above the 250-day average"),
        _v("SMA200", PairParams(200, 200),
           "Control: the plain 200-day switch, monthly; M0434-SMA200's book"),
        _v("ALWAYS", PairParams(0, 0),
           "Control: M0430-ALWAYS's book, SPY held every session, never in cash"),
    ),
    seen_keys=(
        "concept:spy-sma-150-250-hysteresis-pair",
    ),
)
