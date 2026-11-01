"""M0339 — Let the curve watch's cash earn the Treasury bill rate.

Source: general knowledge, a variation on M0336 (whose analysis queued exactly this: "whether the
watch's cash could earn something"). Reserved as an idea row by Sera 20261101-1335. The inverted
curve signal (Estrella & Mishkin 1996) and the idea that idle cash earns the bill rate are both
public through the whole dev window.

M0336 found the old two-year clock the best close rule and its one real cost is the time spent in
cash earning nothing. This method changes only that: the same book, the same watch (M0336's
``SteepAllocator`` in its ``fixed`` and ``never`` modes, unchanged), but on a rule set whose idle
cash is credited the 13-week bill yield (``cash_yield="T13W"``, point in time from the store's
market series). Nothing else moves, so the 2x2 is clean: habit (watch on or off) times cash
(paid or not).

Variants:

    * ``NEVER``: never steps aside, cash earns nothing. The control with no opinion in it.
    * ``NEVER-CASH``: never steps aside, the little idle cash it has is paid. Prices the
      interest on an almost fully invested book, so it isolates how much of any gain is the
      watch's cash and how much is just paying the residual.
    * ``FIXED730``: M0336's clock, cash earns nothing. The parent's best arm, re-measured here.
    * ``FIXED730-CASH``: the clock, cash paid. The treatment.

Cash yield raises the owner input "cash-yield" (nobody has verified Gotrade pays interest), so
paper refuses it: this is a lab measurement of what the watch costs when its waiting money is
credited, not a promotable configuration.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0336_yield_curve_watch_ends_on_steepening import STEEP, WatchParams
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE

ADDED = date(2026, 11, 1)

# The parent's rule set with idle cash credited the 13-week bill yield. One lever from the preset
# M0336 ran on; the only thing that differs between each arm and its -CASH twin.
RESIZE_GOTRADE_CASH = replace(
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
    id="monthly-rank-weekly-resize-frac-gotrade-cash",
    cash_yield="T13W",
)


def _v(suffix: str, params: WatchParams, rules, rationale: str) -> Candidate:
    return Candidate(id=f"M0339-{suffix}", family="M0339", rules=rules, allocator=STEEP,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0339",
    name="Let the curve watch's cash earn the Treasury bill rate",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="M0336",
    parent_id="M0336",
    hypothesis=(
        "M0336 showed that ending the watch early gives up the saves, so the old two-year clock "
        "stays the best rule, and its one real cost is the time spent in cash earning nothing. "
        "Pay the watch's cash the 13-week Treasury bill rate (series T13W, point in time) while the "
        "watch is open, on the same big-dividend-raise book (M0076-X-M's picks, own SPY-200 switch "
        "removed, monthly re-pick, weekly resize) at fractional Gotrade fees. Registered as a 2x2 "
        "so the habit and the cash are separated: NEVER and NEVER-CASH (never steps aside; the "
        "no-opinion controls, the second prices the interest on the residual cash alone), FIXED730 "
        "and FIXED730-CASH (M0336's clock, cash unpaid then paid; the treatment). The watch logic "
        "is M0336's allocator unchanged; only the rule set differs by cash_yield. Both the "
        "inverted-curve signal (1996) and bill interest are public and old, so no edge is claimed "
        "from being early. Assumed: Gotrade paying interest on idle dollars is unverified, so "
        "this is a measurement and not a promotable book; the bill yield is credited on the prior "
        "close's cash at each open. Success: a smaller 2009-2015 shortfall against SPY for "
        "FIXED730-CASH than FIXED730, with the 2000-02 and 2008 saves intact."
    ),
    expected_failure=(
        "Bill rates were near zero from 2009 to 2015, exactly where the cost of sitting in cash "
        "falls, so the interest is small there and the 2009-2015 shortfall barely moves. The "
        "interest is worth most in 2000-02 and 2006-07, where the watch already wins. The result "
        "is a small uplift of FIXED730-CASH over FIXED730 spread across the whole window, no "
        "change in the fold record (about 3 of 4, as the parent), and no arm clearing the 0.90 "
        "luck bar by a wider margin than FIXED730 did."
    ),
    candidates=(
        _v("NEVER", WatchParams("never"), MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
           "Control: never steps aside, cash earns nothing"),
        _v("NEVER-CASH", WatchParams("never"), RESIZE_GOTRADE_CASH,
           "Control: never steps aside, residual cash paid the bill rate"),
        _v("FIXED730", WatchParams("fixed"), MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
           "Parent's clock, cash earns nothing"),
        _v("FIXED730-CASH", WatchParams("fixed"), RESIZE_GOTRADE_CASH,
           "Treatment: the clock with the watch's cash paid the bill rate"),
    ),
    seen_keys=(
        "concept:yield-curve-watch-cash-yield",
        "concept:cash-yield-credit",
        "concept:yield-curve-gate",
        "concept:macro-regime-gate",
    ),
)
