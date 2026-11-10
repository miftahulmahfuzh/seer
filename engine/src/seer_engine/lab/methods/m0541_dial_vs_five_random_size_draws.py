"""M0541 — Does the correlation dial beat its own noise? The dial against five independent
random-size books, behind the 200-day switch.

Source: a variation of M0511 (the correlation concentration dial). M0511 ran the dial against ONE
sticky random-size draw (salt 17), ungated. One draw is not a control: the lab's own draws span
several points a year, so a 2-point lead over one draw is unreadable. Here the dial and its mirror
sit beside the fixed-20 control and five draws with distinct salts, all on the gated chassis
(the SPY 200-day switch, the only chassis that has ever beaten SPY after 2009).

The allocator is M0511's, wrapped: it carries a salt so the draw is a parameter that digests, and
it reuses M0511's reading, sizes and residual-momentum books unchanged. Non-draw arms repeat
M0511-DIAL-GATE and M0511-FIX20-GATE under a new allocator id, so they record as book twins of
those; expected, costs no look, and is not a new book. The mirror behind the switch is new.

Pure: reads only bars dated at or before d.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM
from seer_engine.lab.methods.m0511_correlation_concentration_dial import (
    DIAL,
    DialParams,
    DialPrepared,
    _books,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 10)
_HASH = 2654435761  # Knuth's multiplicative constant: a draw never reads a price
_BLOCK_DAYS = 91  # same quarter-long blocks as M0511's placebo
SALTS = (101, 102, 103, 104, 105)  # fixed before any result; M0511's draw used 17


@dataclass(frozen=True, slots=True)
class SaltedDialParams:
    """M0511's params plus the salt of the draw (0 for the non-draw arms, which ignore it)."""

    dial: DialParams
    salt: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.dial, DialParams):
            raise TypeError("dial must be DialParams")
        if self.dial.rule == "placebo" and self.salt not in SALTS:
            raise ValueError(f"a draw needs one of the pre-registered salts {SALTS}")

    def as_dict(self) -> dict[str, str]:
        return {**self.dial.as_dict(), "salt": str(self.salt)}


def _check(params: object) -> SaltedDialParams:
    if not isinstance(params, SaltedDialParams):
        raise TypeError(f"params must be SaltedDialParams, got {type(params).__name__}")
    return params


def draw_size(data_date: date, salt: int) -> int:
    """0, 1 or 2 for few, mid, many: a date-hash thirds draw, fixed for a quarter at a time."""
    u = ((((data_date.toordinal() // _BLOCK_DAYS) + salt) * _HASH) % 2**32) / 2**32
    return 0 if u < 1 / 3 else (1 if u < 2 / 3 else 2)


class SaltedCorrelationDial:
    """M0511's dial, with the placebo's salt a parameter."""

    id = "M0541"

    def lookback(self, params: Any) -> int:
        return DIAL.lookback(_check(params).dial)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return DIAL.symbols(_check(params).dial)

    def holds(self, params: Any) -> tuple[str, ...]:
        return DIAL.holds(_check(params).dial)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if p.dial.rule == "placebo":
            inner = (p.dial.few, p.dial.mid, p.dial.many)[draw_size(data_date, p.salt)]
            return RESIDMOM.targets(history, members, data_date, held, inner)
        return DIAL.targets(history, members, data_date, held, p.dial)

    def prepare(self, history: Mapping[str, History]) -> DialPrepared:
        return DIAL.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if p.dial.rule == "placebo":
            if not isinstance(prepared, DialPrepared):
                raise TypeError(f"prepared must be DialPrepared, got {type(prepared).__name__}")
            inner = (p.dial.few, p.dial.mid, p.dial.many)[draw_size(data_date, p.salt)]
            return RESIDMOM.targets_prepared(prepared.resid, members, data_date, held, inner)
        return DIAL.targets_prepared(prepared, members, data_date, held, p.dial)


SALTED = SaltedCorrelationDial()


def _v(suffix: str, rule: str, salt: int, rationale: str) -> Candidate:
    few, mid, many = _books(True)  # every arm sits behind the SPY 200-day switch
    return Candidate(id=f"M0541-{suffix}", family="M0541", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SALTED, params=SaltedDialParams(DialParams(few, mid, many, rule), salt),
                     rationale=rationale, added=ADDED, owner_inputs=())


def _draw(i: int) -> Candidate:
    return _v(f"DRAW-S{i + 1}", "placebo", SALTS[i],
              f"Independent sticky random-size draw {i + 1} of 5 (salt {SALTS[i]}), same 10/20/30 mix")


AMEND_1 = Amendment(
    added=ADDED,
    why=("The last two of five draws, pre-registered in the same commit as the first three and "
         "before either batch runs: six arms is the per-run cap, and five draws are the point."),
    hypothesis=("Same question as the original block: the dial must rank first of the six "
                "(itself plus five draws) on 2009-2015 and on the fold record. Draws 4 and 5 are "
                "run and reported whatever draws 1-3 show; nothing is dropped."),
    expected_failure=("The draws' spread, about 5 points a year behind the switch, swallows the "
                      "dial's 2-point lead, so the dial ranks 2nd to 4th of six."),
    candidates=(_draw(3), _draw(4)),
)

METHOD = Method(
    id="M0541",
    name="Does the correlation dial beat its own noise? The dial against five independent random-size books, behind the 200-day switch",
    family="stock-portfolio-construction",
    source_kind="variation",
    source_ref="variation of M0511 (correlation as a concentration dial); chassis M0511-DIAL-GATE "
               "and M0511-FIX20-GATE; reading from Pollet & Wilson (2010), JFE 96(3)",
    parent_id="M0511",
    hypothesis=(
        "M0511's dial (10 names when correlation is in its lowest third, 30 when highest, 20 "
        "between) led its fixed-20 control by about 2 points a year in 2009-2015, with and "
        "without the 200-day switch, but only 0.3 over the whole window, and was compared with "
        "ONE random draw. One draw is not a control. Run the dial (DIAL-GATE), its mirror "
        "(MIRROR-GATE: 30 names when low, 10 when high) and the fixed 20 (FIX20-GATE), and FIVE "
        "independent sticky random-size draws (DRAW-S1..S5, salts 101-105, same 10/20/30 mix, 91-day "
        "blocks, no price read), all behind the SPY 200-day switch, all fractional at Gotrade's "
        "real fees. The reading of the correlation is published (2010), so the dev window may show "
        "an edge since traded away. DIAL-GATE and FIX20-GATE repeat M0511-DIAL-GATE and "
        "M0511-FIX20-GATE under a new allocator id and will record as their book twins; that is "
        "expected, costs no look and is not a new book (FIX20-GATE is in turn M0032-N20-RAW-FRAC-GT's "
        "book). Blocks: six arms here (FIX20-GATE, DIAL-GATE, MIRROR-GATE, DRAW-S1..S3) and "
        "DRAW-S4, S5 in an amendment, pre-registered in this same commit. SUCCESS, fixed now: DIAL-GATE "
        "ranks first of six (itself and five draws) on 2009-2015 funded return AND beats the "
        "fixed 20 on a majority of folds AND MIRROR-GATE loses to it. Otherwise the lead is "
        "inside the draws' own spread and is reported as noise."
    ),
    expected_failure=(
        "The lead sits inside the draws' spread, about 5 points a year behind the switch (the "
        "lab's own draws span 7.5 points ungated). The dial ranks 2nd to 4th of six on 2009-2015. "
        "Concentration also moves the fall more than the growth, so the dial may not change the "
        "worst fall either."
    ),
    candidates=(
        _v("FIX20-GATE", "fixed", 0, "Control: 20 names always behind the switch"),
        _v("DIAL-GATE", "dial", 0, "10 names when correlation is low, 30 when high, 20 between"),
        _v("MIRROR-GATE", "mirror", 0, "Mirror: 30 names when low, 10 when high"),
        _draw(0),
        _draw(1),
        _draw(2),
    ),
    amendments=(AMEND_1,),
    seen_keys=("concept:dial-vs-five-random-size-draws",),
)
