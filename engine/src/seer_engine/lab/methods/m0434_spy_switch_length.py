"""M0434 — is 200 days a lucky number? SPY's plain switch at 150, 200 and 250 days.

Source: variation of M0430, whose analysis named the switch's own length as the unmeasured dial.
Idea: every re-entry tweak on SPY's 200-day switch (M0404, M0422, M0430) matched the plain rule
at best, so the exit length is what is left. M0343 swept the length on a momentum stock book and
found it barely matters there; nobody has swept it on the SPY-only switch, where the book is one
holding and the length is the whole strategy.

Frame, deliberately M0404/M0430's: SPY only at full weight, monthly check, fractional shares at
Gotrade's real fees on the owner's deposits, and the same 253-bar lookback in every arm so the
arms are scored on the same sessions. The exit and the way back in are both the plain test
"SPY close strictly above its n-day average"; only n changes. ALWAYS holds SPY every session.
Reads only bars dated <= ``data_date``. Pure.
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

ADDED = date(2026, 11, 10)


@dataclass(frozen=True, slots=True)
class LengthParams:
    """``n`` is the average's length in sessions; 0 means no switch (always invested)."""

    n: int = 200

    def __post_init__(self) -> None:
        if isinstance(self.n, bool) or not isinstance(self.n, int):
            raise TypeError(f"n must be an int, got {type(self.n).__name__}")
        if self.n != 0 and not 20 <= self.n <= LOOKBACK:
            raise ValueError(f"n must be 0 or in [20, {LOOKBACK}], got {self.n}")

    def as_dict(self) -> dict[str, str]:
        return {"n": str(self.n)}


def _check(params: object) -> LengthParams:
    if not isinstance(params, LengthParams):
        raise TypeError(f"params must be LengthParams, got {type(params).__name__}")
    return params


class LengthTrendSwitch:
    """100% SPY while its close is above its n-day average, else cash."""

    id = "M0434"

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

    def _run(self, history: Mapping[str, History], data_date: date,
             p: LengthParams) -> tuple[Target, ...]:
        h = history.get(BENCH)
        if h is None or h.index_of(data_date) is None:
            return ()
        if p.n and not trend_on(history, data_date,
                                FactorParams(rank="momentum", trend=(BENCH, p.n))):
            return ()
        t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, _check(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, _check(params))


SWITCH = LengthTrendSwitch()


def _v(suffix: str, params: LengthParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0434-{suffix}", family="M0434", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0434",
    name="Is 200 days a lucky number? SPY's switch at 150 and 250 days",
    family="market-trend-switch",
    source_kind="variation",
    source_ref="variation of M0430, whose analysis named the switch's own length",
    parent_id="M0430",
    hypothesis=(
        "The SPY-versus-moving-average switch is old (banded 1992, Faber 2007) so expect fade. "
        "Every re-entry tweak (M0404, M0422, M0430) matched the plain 200-day rule at best; the "
        "length of the average is the unmeasured dial on the SPY-only book (M0343 swept it on a "
        "momentum stock book only, and found length barely mattered there). Arms fixed before "
        "the run, monthly, SPY only, fractional, Gotrade fees, owner deposits, one 253-bar "
        "lookback so every arm is scored on the same sessions: SMA200 (control, the plain switch; "
        "its book repeats M0430-SPY200's, a book twin by design), SMA150, SMA250 and ALWAYS (SPY "
        "every session, the no-opinion arm; repeats M0430-ALWAYS). Judged first on 2009-2015. "
        "SUCCESS: a neighbour beats SMA200 in 2009-2015 AND on the 20-year funded return with a "
        "worst fall no deeper, a majority of walk-forward folds, DSR >= 0.90. Readable even if "
        "it fails: if 150 and 250 both land within noise of 200, 200 is a plateau, not a peak, "
        "and the switch's length is closed as a dial."
    ),
    expected_failure=(
        "200 is the best of three only by luck of the dev years and its neighbours sit within "
        "noise; a monthly check makes 150 and 250 trade on nearly the same months, so the three "
        "curves may differ by a handful of trades. Trade counts stay in the tens, so profit "
        "factor and the luck bar mean little. 2009-2015 had no bear market, so a faster or "
        "slower exit is only paid for or saved by false alarms there. Published anomalies fade: "
        "the dev window ends in 2015 and shows only the pre-crowd edge. No interest on cash is "
        "modelled, which flatters SPY's cash time."
    ),
    candidates=(
        _v("SMA150", LengthParams(150), "Faster switch: 150-day average, exits and re-enters sooner"),
        _v("SMA200", LengthParams(200), "Control: the plain 200-day switch, monthly"),
        _v("SMA250", LengthParams(250), "Slower switch: 250-day average, fewer exits"),
        _v("ALWAYS", LengthParams(0), "No-opinion arm: SPY held every session, never in cash"),
    ),
    seen_keys=(
        "concept:spy-only-switch-length-sweep",
        "concept:spy-sma-150-250-neighbours",
    ),
)
