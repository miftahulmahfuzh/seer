"""M0139 — How many names should the book hold, asked on a tape that actually invests the deposits.

Source: a variation of M0128 (the near misses on the fixed tape), asking M0123's finding back at
the one decision it invalidates. Reserved by Sera 20261014-1242.

**The confound, in one paragraph.** Under ``resize_basis="equity"`` -- the basis every recorded
trial in this lab used before 2026-10-12 -- the book engine tops a held name back up only once it
is off target by ``RESIZE_BAND``, 1% **of the whole account**. The band does not scale with the
slot, so it bites harder the more names a book holds: at 20 names a 5% slot must drift 20% of
itself, at 50 names a 2% slot must drift 50% of itself, and at 100 names a 1% slot can never drift
far enough at all. M0123 measured the consequence on an ungated 100-name basket: the same names on
the same dates with the same 859 trades were 51% invested on the equity basis and 96% on the
target basis, worth 3.1 points a year of funded return. The owner's monthly deposit reaches a
wide book almost only through turnover, and the wider the book the less of it lands.

**Why that makes a roster decision unsafe.** The lab's name-count evidence is M0007's own sweep --
N10, N20, N30, all on ``monthly-hold``, all on the equity basis -- which read MAR 0.51, 0.64, 0.63
and exposure 0.68, 0.66, 0.63. Fewer names looked better, and the paper roster carries twenty
names on the back of it. But exposure fell as names rose, so part of what that sweep called
"concentration pays" was the measuring tape draining the wider books into cash. The owner mirrors
the roster with real money, so "how many names" is a live decision and deserves a pre-registered
prediction rather than a free report.

**What this method does.** One engine, one screen, one gate, one fee schedule, one funding plan,
and exactly two things vary:

    * **how many names the book holds** -- 35, 50 or 70;
    * **where the rebalance band is measured** -- ``monthly-hold-frac-gotrade-tband``
      (``resize_basis="target"``, 20% of the holding's own target) against
      ``monthly-hold-frac-gotrade`` (the old 1%-of-equity basis).

Three name counts on two bases is a 3x2 grid. Read down a column it is the name-count sweep on a
tape that invests; read across a row it is the confound itself, priced at each width.

**The twenty-name rung is already in the record, and is deliberately not re-run.** The 20-name
arm of this sweep exists twice: M0032-N20-RAW-FRAC-GT on the equity basis (trial 129) and
M0128-RAW20 on the target basis (trial 388). They are bit-identical -- both +55492.3% return,
20.6% worst fall, 1.98 gains-to-losses, 1,607 trades, exposure 0.694043390520648 -- which is
exactly what the arithmetic predicts, because 20% of a 5% slot *is* 1% of equity. So the two
controls the idea row asked for are already measured, their no-op is confirmed to the last digit,
and ``lab run`` would refuse their digests anyway (``has_trial``). Re-registering them would spend
two of six arms reproducing a known identity. They are quoted as the sweep's 20-name rung instead,
and the three freed arms go to the equity-basis twins, which is where the confound actually lives.
Written down as an assumption, before the run: the N=20 rung of every table below is trial 388 and
not a variant of this method.

**The picks are M0007-N20-RAW's, verbatim, with only ``top`` moved.** ``ResidParams(inner=
FactorParams(rank="momentum", top=K, trend=("SPY", 200)), scaled=False)`` -- rank the liquid
point-in-time members on cumulative market-model residual return over 12-1 months, take the best
K, equal money in each, all cash while SPY is below its 200-day average. ``scaled=False`` is
M0011's RAW20 setting: the raw cumulative residual, no division by its own standard deviation, no
volatility brake anywhere. Nothing in the picking changes across the six arms; only ``top`` and
the preset do.

**A measured bound on the screen, taken before the run and not after it.** ``factor_weights``
weights every chosen name ``1/top``, not ``1/len(chosen)``, so a book asking for K names but
finding only k is k/K invested by construction. Counting the rows M0007's screen admits on every
month-end of the dev window: 64-97 names in 1996, 102-124 in 1997, and 129 or more every year
after. So the 50- and 35-name arms are always fillable, and only the 70-name arm is structurally
short, in 1996 alone, by at most six names in its worst month. Any exposure gap wider than that,
or outside 1996, is the band and not the screen. The same count puts the gate's cash at 2001,
2002 and 2008 (zero months on, in all three), which is why every arm here sits near 69% invested
rather than near 96%: the SPY 200-day gate, not the band, is the larger cash position, and the
band moves what is left.

Fractional shares at Gotrade's real fee schedule, monthly, funded on the owner's plan. No cash
yield on any arm: that lever raises the unverified owner input "Gotrade pays interest on idle
dollars" and is what keeps every M0128 cash arm ineligible, and this method would rather its arms
be judgeable. Pure: every piece reads only bars dated <= d, ``held`` is never read, and the two
presets are looked up by id in ``sim.rules.PRESETS`` so the file names each rule set exactly as
its trial will record it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.sim.rules import PRESETS, TradeRules, rule_owner_inputs
from seer_engine.strategies.f_factor import FactorParams

ADDED = date(2026, 10, 14)


def _preset(rules_id: str) -> TradeRules:
    """The ``PRESETS`` entry whose id is ``rules_id``: the rule set exactly as a trial records it."""
    for rules in PRESETS:
        if rules.id == rules_id:
            return rules
    raise LookupError(f"sim.rules.PRESETS has no rule set {rules_id!r}")


#: The fixed tape: the band is 20% of the holding's own target, so a deposit reaches a held name.
TBAND = _preset("monthly-hold-frac-gotrade-tband")
#: The old tape: the band is 1% of the whole account, so it binds harder the wider the book.
EBAND = _preset("monthly-hold-frac-gotrade")

#: Name counts. 20 is the record's rung (trials 129 and 388, identical); 35, 50 and 70 are new.
WIDTHS: tuple[int, ...] = (35, 50, 70)


def _picks(top: int):
    """M0007-N20-RAW's params with only ``top`` moved: same screen, same gate, same ranking."""
    return replace(RAW20, inner=FactorParams(rank="momentum", top=top, trend=TREND))


def _v(suffix: str, rules: TradeRules, top: int, rationale: str) -> Candidate:
    return Candidate(id=f"M0139-{suffix}", family="M0139", rules=rules, allocator=RESIDMOM,
                     params=_picks(top), rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(rules))


METHOD = Method(
    id="M0139",
    name="How many names should the book hold, asked on a tape that actually invests the deposits",
    family="stock-residual-momentum",
    source_kind="variation",
    source_ref=(
        "M0128 (the near misses on the fixed tape) for the preset and the band arithmetic; "
        "M0123 (the 1%-of-equity band left a 100-name book 51% invested) for the finding this "
        "re-opens; M0007's own N10/N20/N30 sweep for the conclusion under test; trials 129 and "
        "388 for the 20-name rung"
    ),
    parent_id="M0128",
    hypothesis=(
        "A measurement, pre-registered so that it is held to a prediction. The lab's name-count "
        "evidence -- M0007's N10/N20/N30 sweep, MAR 0.51/0.64/0.63 at exposure 0.68/0.66/0.63 -- "
        "was taken on a tape where the rebalance band is 1% of the WHOLE account rather than a "
        "share of the slot. That band does not scale with the slot, so it binds harder the more "
        "names a book holds, and the owner's monthly deposit then reaches a wide book almost only "
        "through turnover. M0123 priced that at 51% invested against 96% on an ungated 100-name "
        "basket, worth 3.1 points a year. So the sweep the twenty-name roster rests on compared a "
        "fully invested narrow book against progressively cash-heavier wide ones, and its "
        "conclusion is partly a reading of the tape. This method asks the question again with the "
        "tape fixed: M0007-N20-RAW's picks verbatim (raw cumulative market-model residual over "
        "12-1 months, equal money, all cash while SPY is under its 200-day average), at 35, 50 "
        "and 70 names, each run twice -- once on monthly-hold-frac-gotrade-tband, where the band "
        "is 20% of the holding's own target, and once on monthly-hold-frac-gotrade, the old "
        "1%-of-equity basis. Fractional shares, Gotrade's real fees, the owner's plan (10,000,000 "
        "IDR opening and 5,000,000 IDR on the 25th of every month), against a SPY fed the "
        "identical deposits on the identical days. No cash yield on any arm, so no arm carries an "
        "owner input. "
        "THE TWENTY-NAME RUNG IS NOT RE-RUN, and that is an assumption stated before the run. It "
        "is already recorded twice -- M0032-N20-RAW-FRAC-GT on the equity basis and M0128-RAW20 "
        "on the target basis -- and the two are identical to the last digit (exposure "
        "0.694043390520648 both, 20.6% worst fall, 1,607 trades), because 20% of a 5% slot is "
        "exactly 1% of equity. The no-op the arithmetic predicts is therefore already confirmed, "
        "lab run would refuse those digests, and the three arms that would have reproduced them "
        "go to the equity-basis twins instead, where the confound actually lives. "
        "WHAT IS PREDICTED, in numbers, before any result. (1) THE CONFOUND GROWS WITH WIDTH. "
        "Equity-basis exposure should fall monotonically with name count while target-basis "
        "exposure stays flat near the 0.694 that the gate alone permits: the gap should be "
        "roughly nil at 20 names, small at 35 (the band is 35% of a slot), clear at 50 (50% of a "
        "slot) and widest at 70 (70% of a slot) -- 2 to 10 points of exposure at 70, less than "
        "M0123's 45 because this book turns over about 8.9 times a year against that basket's "
        "much slower churn, and turnover is the other way a deposit reaches a holding. (2) THE "
        "SWEEP, read on the fixed tape. The honest prior is that concentration still pays "
        "something, because a residual-momentum edge genuinely decays down the ranking, but far "
        "less than the old sweep said: on the target basis the funded return should fall by less "
        "from 20 to 70 names than the equity-basis column does, and the worst fall should improve "
        "with width, because 70 equal slots cannot be hurt by one name the way 20 can. 20 names "
        "is 13.7% a year funded at a 20.6% worst fall; the 70-name target-basis arm is predicted "
        "between 11% and 13.5% a year at a worst fall of 16% to 19%. (3) MAR, which is return "
        "over worst fall, is where width could actually win: if the fall improves faster than the "
        "return decays, a 35- or 50-name book out-MARs the 20-name one, and the roster's width is "
        "wrong. That is the one outcome of this method that would change what the owner holds. "
        "(4) DEPOSIT-MATCHED SPY earns 7.2% a year over this window, and every arm here is "
        "expected to beat it, as every residual-momentum book in this lab has on dev. "
        "PROMOTION IS NOT AVAILABLE and that is accepted up front: this line runs through M0007 "
        "and M0128, and M0007 is test-failed, so the hard gate refuses it on kin whatever it "
        "scores. The value is the measurement and the roster decision it informs, not a candidate."
    ),
    expected_failure=(
        "The likeliest disappointment is that the fixed tape barely moves anything, because this "
        "book is not M0123's basket: it turns over about 8.9 times a year and the SPY 200-day "
        "gate liquidates it outright in 2001, 2002 and 2008, so deposits already reach it through "
        "churn and the band has little left to do. If equity-basis and target-basis exposure "
        "differ by under a point at 70 names, the verdict must say plainly that the confound is "
        "real but small in THIS family, that M0123's 45-point gap was a property of a slow basket "
        "rather than of wide books in general, and that the roster's twenty names were not chosen "
        "on a broken measurement after all. Specific failures written now. (1) THE SCREEN, not "
        "the band, could short the 70-name arm: it admits 64-97 names in 1996, so that arm is "
        "structurally under-filled in its first year by up to six names. Any exposure gap inside "
        "1996 must be charged to the screen, and only gaps outside it to the band. (2) THE GATE "
        "DOMINATES THE CASH. Every arm sits near 69% invested because the gate is off for three "
        "whole years; a band difference of a point or two is a small share of a large cash "
        "position, and must never be reported as though the book were otherwise fully invested. "
        "(3) WIDTH COSTS FEES. Gotrade's schedule bites hardest on small orders, and a 70-name "
        "book at 20,000,000 IDR opening capital has slots near 18 USD in its early years, where "
        "the fee is a far larger share of the order than on a 5% slot. Some of any return decay "
        "with width will be fees rather than signal decay, and the trade counts and turnover must "
        "be quoted so the two can be told apart. (4) SURVIVORSHIP. The dev store prices no "
        "delisted names, and a wider book owns more of the shortlist, so it is more exposed to "
        "the missing failures exactly as M0123's all-shortlist basket was -- which lost its whole "
        "edge on the check store. The widest arm must be survivorship-checked the same day and "
        "the result quoted beside the dev column, and if the width advantage shrinks there the "
        "verdict says the width advantage was partly the missing dead companies. (5) THE "
        "PRE-2009 TRAP. Every twenty-year edge this lab has found was earned before 2009. If "
        "width only helps before 2009 and not over 2009-2015, the roster recommendation must say "
        "so first, because those are the years most like today. (6) DEPOSITS SOFTEN EVERY WORST "
        "FALL HERE ALIKE; none of these numbers may be lined up against an unfunded parent's, and "
        "the 20-name rung quoted from trial 388 is funded on the identical plan, which is the "
        "only reason it is comparable at all."
    ),
    candidates=(
        _v("N35-TBAND", TBAND, 35,
           "35 names on the fixed tape: the band is 20% of each 2.86% slot, so deposits reach held names"),
        _v("N50-TBAND", TBAND, 50,
           "50 names on the fixed tape: the sweep's middle rung, invested on the same terms as the 20-name book"),
        _v("N70-TBAND", TBAND, 70,
           "70 names on the fixed tape: the widest rung, and the one the old band drained hardest"),
        _v("N35-EBAND", EBAND, 35,
           "The same 35 names on the old 1%-of-equity band: the confound at its mildest, 35% of a slot"),
        _v("N50-EBAND", EBAND, 50,
           "The same 50 names on the old band, where 1% of equity is half of the slot"),
        _v("N70-EBAND", EBAND, 70,
           "The same 70 names on the old band, where 1% of equity is 70% of the slot: the widest gap"),
    ),
    seen_keys=(
        "concept:residual-momentum-name-count",
        "concept:resize-band-basis-by-book-width",
    ),
)
