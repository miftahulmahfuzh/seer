"""MNNNN — <one-line name>.

Source: <URL / citation / "variation of M00xx" / general knowledge>.
Idea: <two or three sentences: the mechanism and why it should beat SPY under design §1>.

Copy to engine/src/seer_engine/lab/methods/mNNNN_<slug>.py, replace every MNNNN, keep ONE of the
two shapes below and delete the other.

A. A stock-picking idea (it ranks index members) is a SIGNAL first: write
   seer_engine/lab/signals/sNNNN_<slug>.py from signal_template.py, commit it, run
   `lab panel SNNNN`. Only once it clears does it become a method, and the method is shape A:
   `signal="SNNNN"` and the two standard arms, nothing hand-built. `lab run` refuses anything
   else (lab/hardgate.py, D21). A foil beside them is allowed when its rationale opens "Control:".

B. Anything else -- a market switch, an ETF rotation, a brake or width or cadence measured on a
   book, a control study -- is your own allocator. Reusing an existing one (FACTOR, TIMING,
   ROTATION, SWING, VOLTARGET, BLEND) with new params needs no class at all: write only METHOD.
   If any arm chooses among index members, declare why the panel does not apply:
   `panel_exempt="chassis: <why>"`, `"control-study: <why>"` or `"market: <why>"`.

Pure: no clock, randomness, files, network, printing. Read only bars dated <= data_date.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.signal_book import standard_candidates
from seer_engine.lab.signals.sNNNN_slug import SIGNAL  # shape A: the committed, cleared signal
from seer_engine.sim.book import Target, equal_weight
# Fractional and at Gotrade's real fees by default: paper trades books in fractional shares, a 20M
# IDR book cannot fill whole-share slots at 2016+ prices (M0021), and from M0031 on `lab run`
# refuses a variant at the old flat 0.1%. Other real-fee preset: MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE.
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 13)  # today


# ---- Shape A: a panelled signal on the one chassis ---------------------------------------------
# No allocator, no params: the arms are the signal's standard book -- the twenty highest-scored
# members of F4's pool, equal weight, monthly at Gotrade's fees, one arm behind the SPY 200-day
# switch (MNNNN-N20) and one never stepping aside (MNNNN-N20-NOGATE).

METHOD = Method(
    id="MNNNN",
    name="<name>",
    family=SIGNAL.family,
    source_kind="knowledge",  # paper | blog | github | knowledge | variation
    source_ref="",            # URL / citation / parent id (required unless knowledge)
    parent_id=None,           # set for a variation
    hypothesis="<why the signal's book beats total-return SPY under design §1>",
    expected_failure="<the way it most likely fails, written before the run>",
    signal="SNNNN",
    candidates=standard_candidates(SIGNAL, "MNNNN", ADDED),
    seen_keys=("concept:<short-concept>",),
)


# ---- Shape B: your own allocator -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Params:
    top: int = 10
    lookback_n: int = 126

    def as_dict(self) -> dict[str, str]:  # every field, as plain strings
        return {"top": str(self.top), "lookback_n": str(self.lookback_n)}


class Alloc:
    """<What it targets on data_date d, in one paragraph. Held symbols: keep or drop?>"""

    id = "MNNNN"  # unique across the lab: the method id

    def lookback(self, params: Params) -> int:
        return params.lookback_n + 1  # bars through d the decision needs

    def symbols(self, params: Params) -> tuple[str, ...]:
        return ("SPY",)  # fixed instruments read (not index members)

    def holds(self, params: Params) -> tuple[str, ...]:
        return ()  # fixed instruments it may hold (ETFs); () when it holds members only

    def uses_members(self, params: Params) -> bool:
        return True  # reads index members (point-in-time S&P 500 ∪ Nasdaq-100): needs panel_exempt

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Params) -> tuple[Target, ...]:
        scored: list[tuple[float, str]] = []
        for s in sorted(members):
            h = history.get(s)
            if h is None or h.index_of(data_date) is None:  # a new target needs a bar dated d
                continue
            i = h.index_of(data_date)
            if i < params.lookback_n:
                continue
            score = float(h.close[i] / h.close[i - params.lookback_n] - 1.0)  # <your rule>
            scored.append((-score, s))
        w = equal_weight(params.top)
        out: list[Target] = []
        for _, s in sorted(scored)[: params.top]:
            t = target_from_close(s, last_close(history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)  # rank order, unique symbols, Σ weight <= 1

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # precompute here only if targets_prepared stays == targets

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


ALLOC = Alloc()


def _v(suffix: str, params: Params, rationale: str, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(id=f"MNNNN-{suffix}", family="MNNNN", rules=rules, allocator=ALLOC,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="MNNNN",
    name="<name>",
    family="<free-text family, e.g. trend-switch>",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis="<why this beats total-return SPY under design §1>",
    expected_failure="<the way it most likely fails, written before the run>",
    candidates=(
        _v("V1", Params(), "<one line>"),
    ),
    # Required here because Alloc.uses_members is True; delete it for an allocator that reads no
    # member. Begin with chassis:, control-study: or market:, then say why.
    panel_exempt="chassis: <why this member-picking book is not a new stock-picking idea>",
    seen_keys=("concept:<short-concept>",),
)
