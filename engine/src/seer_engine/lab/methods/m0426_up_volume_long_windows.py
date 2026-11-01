"""M0426 — Up-volume accumulation on long windows: the second look M0425's one lead asked for.

Source: variation of M0425 (on-balance volume, Granville 1963; Lee & Swaminathan 2000). Reserved by
Sera batch sera-20261101-1604 as an ``idea`` row; this file refines it and keeps its id.

WHY NOT A RE-RUN. M0425-UP120-SW has already been measured: re-running that configuration would be
a repeat of one draw, not a second look. So the pair here is the 126-day window (half a year, the
120-day signal's neighbour) and the 250-day window (a full year). If M0425's 120-day lead was a
signal, its neighbour and its longer sibling should agree with it; if it was one lucky draw out of
six, they will not. The parameter space was not tuned on any result of this method.

THE SIGNAL is M0425's, unchanged: the share of the last ``window`` sessions' dollar volume (close x
volume) traded on up-close days. The allocator's maths is imported from M0425, so the two methods
cannot drift apart; only the windows, the arms and the placebo seeds differ.

ARMS, equal 1/20 slots, fractional shares, Gotrade's real fees, monthly (``MONTHLY_HOLD_FRAC_GOTRADE``),
held names kept inside the top 40:

    UP126-SW    top 20 by 126-day up-volume share, behind the SPY 200-day switch
    UP250-SW    the same on a 250-day window
    DN126-SW    the mirror (lowest share): if it matches UP126-SW the signal reads liquidity, not direction
    PLC126-SW   blind draw of UP126-SW's size and entry count (no opinion; prices the switch and habit)
    PLC250-SW   the same blind draw for the 250-day book
    UP126       UP126-SW with no switch (the 2x2: prices what the switch earns and costs)

ASSUMPTIONS made without asking. (1) The placebo is the "no opinion, always invested behind the same
switch" arm the idea row asked for. (2) No matched-return control this time: M0425 showed volume share
and price strength were already indistinguishable at 60 days, and the arm budget goes to the placebo
at both windows. (3) Same pool and fallbacks as M0425 (index members with 253 bars, fewer than 50
scored holds SPY).

Pure: no clock, randomness, files or network; reads only bars dated on or before ``data_date``.
"""

from __future__ import annotations

from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0425_up_volume_accumulation import UpVolAllocator, UpVolParams
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE

ADDED = date(2026, 11, 1)


class LongUpVolAllocator(UpVolAllocator):
    """M0425's allocator under this method's id, so its candidates are its own."""

    id = "M0426"


LONGUPVOL = LongUpVolAllocator()


def _v(suffix: str, params: UpVolParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0426-{suffix}", family="M0426",
                     rules=MONTHLY_HOLD_FRAC_GOTRADE, allocator=LONGUPVOL, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0426",
    name="Up-volume accumulation on 126 and 250 day windows",
    family="stock-volume-accumulation",
    source_kind="variation",
    source_ref="M0425",
    parent_id="M0425",
    hypothesis=(
        "M0425's 120-day window earned 11.2% a year and paid in narrow and broad markets but missed "
        "the luck bar (0.886 vs 0.90) and lost the 2009-2014 folds, while its 60-day twin and mirror "
        "pointed the wrong way. Up-volume accumulation is an old, public indicator (Granville 1963), "
        "so expect a small edge at best. Test: the 120-day lead cannot be re-run as the same "
        "configuration, so measure its neighbour (126 days) and a year (250 days): each month, among "
        "index members with 253 bars, rank by the share of dollar volume traded on up-close days, hold "
        "20 in equal slots with a held name kept inside the top 40, fractional shares at Gotrade's "
        "real fees, behind the SPY 200-day switch. Arms: UP126-SW; UP250-SW; DN126-SW (mirror); "
        "PLC126-SW and PLC250-SW (blind draws of each book's size and entry count: no opinion, same "
        "switch and habit); UP126 (no switch: the 2x2). Predictions written before any result: UP126-SW "
        "and UP250-SW each beat their blind draw by 1.5 or more points a year, DN126-SW lags UP126-SW "
        "by 1.5 or more, and UP126-SW leads SPY in 2009-2015. Abandon if it trails SPY in 2009-2015."
    ),
    expected_failure=(
        "(1) M0425's 120-day lead was one lucky draw out of six: the 126 and 250 windows land within "
        "a point of their blind draws. (2) The switch plus the monthly habit does the work: the "
        "placebos match the signal arms and UP126 without the switch falls far behind. (3) The mirror "
        "DN126-SW does as well as the signal, because the quantity measured is liquidity, not "
        "direction. (4) Long-window up-volume share is a restatement of 12-month price strength, so "
        "the book is momentum kin of the failed momentum books and trails SPY in 2009-2015. Any of "
        "these is a rejection, not a reason to tune the window."
    ),
    candidates=(
        _v("UP126-SW", UpVolParams(window=126, signal="up", switch=True),
           "Top 20 by 126-day up-day dollar-volume share, behind the SPY 200-day switch"),
        _v("UP250-SW", UpVolParams(window=250, signal="up", switch=True),
           "The same on a 250-day window"),
        _v("DN126-SW", UpVolParams(window=126, signal="down", switch=True),
           "Mirror: the 20 with the lowest 126-day up-day share"),
        _v("PLC126-SW", UpVolParams(window=126, signal="control", switch=True, seed=2),
           "Placebo: UP126-SW's book size and entries drawn blind, behind the same switch"),
        _v("PLC250-SW", UpVolParams(window=250, signal="control", switch=True, seed=3),
           "Placebo: UP250-SW's book size and entries drawn blind, behind the same switch"),
        _v("UP126", UpVolParams(window=126, signal="up", switch=False),
           "UP126-SW without the switch: prices what the switch costs and earns"),
    ),
    seen_keys=("concept:up-volume-accumulation-long-window",),
)
