"""M0138 -- Ask the fall model a yearly question: M0132's fall-sizing head on a 252-session horizon.

Source: variation of M0132 (Moreira & Muir 2017, volatility-managed portfolios, published 2017).

WHY. M0131 measured that stretching a ranker's label from one month to a year was worth several
points a year with every other field fixed, and that the ladder 21 -> 63 -> 252 sessions was
monotone. M0132 (rejected) was written on a 63-session fall horizon on the reasoning that a fall is
a path and a month of a path is mostly noise. M0131 says that reasoning was right and not carried
far enough. This method changes that one field and nothing else: the fall model, the three
un-normalised market columns, the whole-slot exposure ladder read off the model's own in-sample
prediction distribution, the fixed tape at Gotrade's real fees. Reused verbatim from M0132.

THE CALENDAR MOVES WITH THE HORIZON. ``model_ready`` needs 35 labelled month-ends whose label has
been fully read, so a 252-session label pushes the first model refit from 1999-12-31 (63 sessions)
to about the end of 2003. Every arm here, controls included, holds SPY until then. Compare the
arms with each other on the 252 calendar; the recorded 63-session arm (M0132-FALL20, trial 399) is
a cited reference on a different calendar, not a paired difference.

THE ARMS (all four are the only settings this idea tries):

    FALL252         the fall model sizes the twenty-name book, base tree, 252-session label
    FALL252-NOSIZE  the same model with the ladder ignored: always a full book, calmest names (ordering only)
    GATE252         CONTROL: the same twenty most-traded names, sized only by the SPY 200-day switch
    ON252           CONTROL: the same twenty names always invested, no opinion at all

Pure: reads only data dated <= data_date, via the M0132 and tree-rank machinery.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0132_fall_sized_book import (
    BASE,
    FALL_BOOK as _M0132_FALL_BOOK,
    ControlParams,
    FallBook,
    FallBookParams,
    SizedVolumeBook,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND

ADDED = date(2026, 11, 13)
YEAR = 252  # the one field that changes: the window the forward fall is measured over

FALL252 = replace(BASE, horizon=YEAR)
FALL252_NOSIZE = replace(FALL252, size=False)


class SizedVolumeBook138(SizedVolumeBook):
    """M0132's model-free control, under this method's own allocator id."""

    id = "M0138-DV"


FALL_BOOK = FallBook(_M0132_FALL_BOOK.inner, "M0138")
SIZED_DV = SizedVolumeBook138()


def _v(suffix: str, allocator, params, rationale: str) -> Candidate:
    return Candidate(id=f"M0138-{suffix}", family="M0138", rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0138",
    name="Ask the fall model a yearly question: the learned fall-sizing head on a 252-session horizon",
    family="model-sized-exposure",
    source_kind="variation",
    source_ref="M0132 (Moreira & Muir 2017); M0131's 21/63/252-session label ladder",
    parent_id="M0132",
    hypothesis=(
        "M0131 measured that stretching the ranker's label from 21 to 252 sessions is worth several "
        "points a year with every other field fixed, monotone at 21, 63 and 252. The learned "
        "fall-sizing head (M0132, rejected) used a 63-session horizon on the reasoning that a fall "
        "is a path and a month of it is mostly noise; M0131 says that reasoning was right and not "
        "carried far enough. This method keeps M0132's fall model exactly as pre-registered -- the "
        "same raw downside level label, never rank-normalised, the same three un-normalised "
        "market-level columns, the same whole-slot exposure ladder read off the model's own "
        "in-sample prediction distribution, the same tape at Gotrade's real fees with idle cash "
        "earning nothing -- and changes one field: the fall horizon becomes 252 sessions (the "
        "published idea dates from 2017, so it may have faded). The calendar moves with it: the "
        "first refit lands about the end of 2003 instead of 1999, so every arm holds SPY until "
        "then; the controls carry the same horizon so the pre-model era cancels. FOUR ARMS, "
        "fixed now: FALL252 (sized); FALL252-NOSIZE (the ladder ignored, always a full book of "
        "the calmest names: the ordering-only arm, so the ladder's value is separable from the "
        "model's name choice); GATE252 (Control: the SPY 200-day switch alone on the same twenty "
        "most-traded names, the standing yardstick); ON252 (Control: the same names, always "
        "invested, no opinion at all -- the dressing arm, so what the opinion is worth can be "
        "priced against what acting on it costs). The 63-session arm is CITED, not re-run: "
        "M0132-FALL20, trial 399, on a different calendar, so it is context and not a paired "
        "difference. WHAT COUNTS AS AN IMPROVEMENT, fixed now: FALL252 beats GATE252 on BOTH "
        "funded return and worst fall over the model era, and is not behind it in 2009-2015. "
        "The switch has helped every lab variant it was tried on; a learned brake that cannot beat "
        "one free moving average is not worth carrying. WHAT COUNTS AS A METHOD: a variant clears "
        "every design section 1 bar at DSR >= 0.90 at the lab's N. No arm is promoted in this run."
    ),
    expected_failure=(
        "The ladder is most likely still a slow volatility target in new clothes: a year-long "
        "forward-fall label is even more a volatility-regime label than a quarter-long one, and the "
        "market-level columns (distance below the one-year high, 60-day volatility) are what a "
        "volatility target reads, so cuts will arrive after the fall has begun. Second, the first "
        "model starts around 2003, so the model era is shorter and contains 2008 as nearly its only "
        "bear year; the SPY switch caught 2008 and has been a drag since 2009, so GATE252 may win "
        "the whole era on one year and lose 2009-2015. Third, a year-long label makes neighbouring "
        "month-ends overlap by eleven twelfths, so the effective sample is a twelfth of the rows "
        "and the learner may fit noise. Fourth, with idle cash earning nothing every cut is a pure "
        "drag on return. Fifth, a dev result for a widely published idea from 2017 may fade out of "
        "sample. If FALL252 matches FALL252-NOSIZE, the ladder did nothing and the names carried it."
    ),
    candidates=(
        _v("FALL252", FALL_BOOK, FallBookParams(FALL252),
           "The fall model, 252-session horizon, sizes the twenty-name book (M0132's FALL20 with one field changed)"),
        _v("FALL252-NOSIZE", FALL_BOOK, FallBookParams(FALL252_NOSIZE),
           "The same fall model with the exposure ladder ignored: always a full book of the calmest names"),
        _v("GATE252", SIZED_DV, ControlParams(gate=True, horizon=YEAR),
           "Control: the twenty most-traded names sized only by the SPY 200-day switch, on the 252-session calendar"),
        _v("ON252", SIZED_DV, ControlParams(horizon=YEAR),
           "Control: the twenty most-traded names always invested, no opinion, on the 252-session calendar"),
    ),
    seen_keys=(
        "concept:forward-drawdown-label",
        "concept:model-sized-exposure",
        "concept:learned-risk-control",
        "concept:market-level-exposure-ladder",
        "concept:walk-forward-annual-refit",
        "concept:fall-horizon-252",
    ),
)
