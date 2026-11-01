"""M0413 — Keep monthly plain momentum, but sell a held name only when it falls out of the top 40.

Source: variation of M0354. M0354 re-ranked plain 12-1 top-20 momentum quarterly and lost 2 to 2.5
points a year to the monthly book: a stale list costs more than the trades it saves. This keeps the
monthly look and cuts trades a different way. A held name stays while it ranks inside the top
``exit_rank`` by 12-1 return; only free slots are filled, from the top of the ranking. M0344 priced
the same buffer on residual momentum (0.3 points a year, deeper fall) and M0163 on yearly dividend
yield (1.7 points); plain 12-1 has never had it. Jegadeesh and Titman published 12-1 in 1993, so the
dev window is after the crowd and 2009-2015 is the first filter.

``BUFFERED`` wraps ``FACTOR``: the SPY 200-day switch, the screen and the 12-1 score are FACTOR's
own, and only the choice of names changes. ``exit_rank`` equal to ``TOP`` keeps nothing the top 20
would not have picked, so it reproduces the plain monthly book through this allocator: the control
and the fidelity check in one. The switch-off twins are the always-invested dressing arms. Pure;
reads only bars dated <= d.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    FACTOR,
    FactorParams,
    FactorRow,
    factor_rows,
    factor_weights,
    trend_on,
)

ADDED = date(2026, 11, 1)

SWITCH = ("SPY", 200)
TOP = 20


@dataclass(frozen=True, slots=True)
class Params:
    """``exit_rank`` is the rank a held name may fall to before it is sold (TOP = no buffer)."""

    exit_rank: int = 40
    switch: bool = True

    def __post_init__(self) -> None:
        if self.exit_rank < TOP:
            raise ValueError(f"exit_rank must be >= {TOP}, got {self.exit_rank}")

    def as_dict(self) -> dict[str, str]:
        return {"exit_rank": str(self.exit_rank), "switch": str(self.switch)}

    def picker(self) -> FactorParams:
        return FactorParams(rank="momentum", top=TOP, mom_n=252, mom_skip=21,
                            trend=SWITCH if self.switch else None)


def choose_buffered(rows: Sequence[FactorRow], held: frozenset[str], exit_rank: int) -> list[FactorRow]:
    """Held names still ranked within ``exit_rank`` stay (best first, at most TOP); the best
    others fill the rest."""
    ranked = sorted(rows, key=lambda r: (-r.momentum, r.symbol))
    kept = [r for r in ranked[:exit_rank] if r.symbol in held][:TOP]
    kept_syms = {r.symbol for r in kept}
    fill = [r for r in ranked if r.symbol not in kept_syms][: TOP - len(kept)]
    return sorted(kept + fill, key=lambda r: (-r.momentum, r.symbol))


def _targets(rows: Sequence[FactorRow], held: frozenset[str], params: Params) -> tuple[Target, ...]:
    chosen = choose_buffered(rows, held, params.exit_rank)
    p = params.picker()
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, p), strict=True):
        if weight is None:
            continue
        t = target_from_close(row.symbol, row.close, weight)
        if t is not None:
            out.append(t)
    return tuple(out)


class BufferedMomentumAlloc:
    """FACTOR's 12-1 top-20, with held names kept while they stay inside ``exit_rank``."""

    id = "M0413"

    def lookback(self, params: Params) -> int:
        return FACTOR.lookback(params.picker())

    def symbols(self, params: Params) -> tuple[str, ...]:
        return FACTOR.symbols(params.picker())

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Params) -> bool:
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(history, data_date, p):
            return ()
        return _targets(factor_rows(history, members, data_date, p), held, params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return FACTOR.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        p = params.picker()
        if not trend_on(prepared.history, data_date, p):
            return ()
        return _targets(prepared.rows_on(members, data_date, p), held, params)


BUFFERED = BufferedMomentumAlloc()


def _v(suffix: str, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0413-{suffix}", family="M0413", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BUFFERED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0413",
    name="Keep winners until they fall out of the top 40: monthly plain momentum with a sell buffer",
    family="stock-momentum",
    source_kind="variation",
    source_ref="M0354",
    parent_id="M0354",
    hypothesis=(
        "M0354 re-picked less often and lost 2 to 2.5 points a year, so a stale list costs more "
        "than it saves. Keep the monthly re-pick, but sell a held name only when it drops out of "
        "the top 40 by 12-1 return, buying replacements from the top 20 only to fill empty slots. "
        "This cuts trades without leaving the list stale: strong names stay, weak ones still go "
        "every month. Same picker as M0354-M1 (12-1, top 20, equal weight, F4's screen, SPY 200-day "
        "switch read monthly), fractional shares at Gotrade's real fees. Arms: B40 (treatment), B30 "
        "(a narrower band), B20 (exit rank 20: no buffer, the control and a reproduction of "
        "M0354-M1), and the switch-off twins B40-NOSW and B20-NOSW as the always-invested arms, so "
        "an effect of the buffer is told apart from an effect of the switch. Questions: do trades "
        "and fees fall, does the return beat the unbuffered book, does it hold in 2009-2015? "
        "Momentum was published in 1993, so a strong dev edge may be pre-publication and fade; the "
        "buffer idea has been priced on residual momentum (M0344, +0.3 a year) and dividend yield "
        "(M0163, +1.7 a year) but never on plain 12-1."),
    expected_failure=(
        "The buffer holds fading names through momentum crashes like M0163's yearly version and "
        "deepens the fall: the worst fall rises above B20's (M0354-M1 was 23.3%, already over the "
        "20% bar) and the saved fees do not pay for it. Second: the saving is small because the "
        "switch's in-and-out trades and the monthly resize happen in every arm, as in M0344 (+0.3 "
        "a year). Third: B40 and B20 hold nearly the same names and the gap is inside the noise of "
        "20-name books. Every arm still lags SPY in 2009-2015 through time in cash."),
    candidates=(
        _v("B40", Params(exit_rank=40), "treatment: sell only below rank 40, switch on"),
        _v("B30", Params(exit_rank=30), "narrower band: sell only below rank 30, switch on"),
        _v("B20", Params(exit_rank=20), "control: no buffer, switch on; reproduces M0354-M1"),
        _v("B40-NOSW", Params(exit_rank=40, switch=False), "treatment, switch off, always invested"),
        _v("B20-NOSW", Params(exit_rank=20, switch=False),
           "control, switch off, always invested; reproduces M0354-M1-NOSW"),
    ),
    seen_keys=("concept:rank-buffer-hysteresis", "concept:momentum-sell-buffer"),
)
