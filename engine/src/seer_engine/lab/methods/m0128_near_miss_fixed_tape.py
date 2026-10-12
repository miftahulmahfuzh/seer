"""M0128 — The near misses re-measured on the fixed tape, beside plain equal-weight books of the same size.

Source: a variation of M0030 (its 2026-10-12 amendment, SAT100) that re-measures the lab's near
misses -- M0030-SAT100, M0007-N20-RAW, M0021-B70-RAW and M0020-W-NOSTOP -- with M0120's
equal-weight 20-name book as the control; docs/plans/HANDOVER_20261012-measure-then-learn.md
section 2 item 4, and the lab's insight 211 (Sera 20261012-1842), which asked the question.

Idea: every number the lab holds for these books was measured on a tape with two known flaws.
Idle cash earned nothing, and a holding was resized only once it had drifted by 1% of the whole
account. Both are now explicit rule levers -- ``resize_basis="target"`` (20% of the holding's own
target) and ``cash_yield="T13W"`` (the 13-week T-bill yield, read the session before) -- and three
presets carry them. This method re-runs each near miss's OWN allocator and params on those
presets, so nothing about what it picks changes, and runs two plain books of the same size on the
same tape beside them. That turns Sera's question into three paired differences on one tape, one
set of deposits and one fee schedule:

    twin minus gated EW20          the picks
    gated EW20 minus ungated EW20  the SPY 200-day gate
    ungated EW20 against SPY       the equal-weight shape (SPY fed the same deposits)

Why six variants and not four twins:

    * M0030-SAT100 and M0007-N20-RAW are the SAME configuration apart from the rule set: RESIDMOM
      on RAW20 (``ResidParams(N20, scaled=False)``, which M0011 defines as "M0007-N20-RAW's
      params, verbatim" and M0030 imports). One variant covers both.
    * RAW20 runs twice, with and without the cash yield: the yield's worth is one paired
      difference, and the no-cash run is the one variant here with no owner input.
    * Two controls. Every near miss is gated by SPY's 200-day average; M0120's EW20 book is not.
      With only the ungated control, the gate's 2001-2002 and 2008 exits would be booked as
      picking. The gated control isolates them.

The gated control is the only new code. ``GATED`` wraps M0120's ``CLOCK`` (book "ew", no clock)
in ``f_factor.trend_on`` with M0007's ``TREND`` -- the same function and the same ("SPY", 200)
that RESIDMOM, the blend's calm sleeve and M0020's re-entry book read -- so the gate is the near
misses' own, and the twenty names are M0120's own. A weekly-tape EW20 control was the other
candidate for this slot; it was not chosen because the weekly twin's tape difference is already
one paired difference inside this method (the weekly twin against RAW20-CASH: same picks, same
gate), while the gate's share of the near misses' edge is measured nowhere else.

The band arithmetic, stated before the run: a 20-name equal-weight slot is 5% of the account, and
20% of 5% is 1% -- the old band. For RAW20, RAW20-CASH, the weekly twin and both controls the band
lever therefore changes nothing; only the blend (3.5% and 1.5% slots) feels it.

Presets are looked up by id in ``sim.rules.PRESETS`` rather than imported by constant name, so the
file names each rule set exactly as its trial will record it. Owner inputs are computed from the
rules (``rule_owner_inputs``), so every cash variant carries "cash-yield" honestly.

Pure: every piece reads only bars dated <= d; no clock, randomness or I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import REENTRY, ReentryParams
from seer_engine.lab.methods.m0021_momentum_lowvol_blend import _blend
from seer_engine.lab.methods.m0120_calendar_clock import CLOCK, SCREEN, ClockParams, ClockPrepared
from seer_engine.sim.book import Target
from seer_engine.sim.rules import PRESETS, TradeRules, rule_owner_inputs
from seer_engine.strategies.allocator import BLEND
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

ADDED = date(2026, 10, 12)


def _preset(rules_id: str) -> TradeRules:
    """The ``PRESETS`` entry whose id is ``rules_id``: the rule set exactly as a trial records it."""
    for rules in PRESETS:
        if rules.id == rules_id:
            return rules
    raise LookupError(f"sim.rules.PRESETS has no rule set {rules_id!r}")


MONTHLY_TBAND = _preset("monthly-hold-frac-gotrade-tband")
MONTHLY_TBAND_CASH = _preset("monthly-hold-frac-gotrade-tband-cash")
WEEKLY_TBAND_CASH = _preset("weekly-hold-frac-gotrade-tband-cash")

EW20 = ClockParams("ew", "none")  # M0120-EW20-ALWAYS's params, verbatim
B70_RAW = _blend("0.7", braked=False)  # M0021-B70-RAW's params, verbatim (imported as M0029 does)
W_NOSTOP = ReentryParams(RAW20, None)  # M0020-W-NOSTOP's params, verbatim


@dataclass(frozen=True, slots=True)
class GatedParams:
    """M0120's plain equal-weight book, held only while ``trend`` says the market is up."""

    book: ClockParams = EW20
    trend: tuple[str, int] = TREND

    def __post_init__(self) -> None:
        if not isinstance(self.book, ClockParams):
            raise TypeError(f"book must be ClockParams, got {type(self.book).__name__}")
        if self.book.book != "ew" or self.book.clock != "none":
            raise ValueError(f"the gated control is the plain EW book with no calendar clock, got {self.book!r}")
        if not isinstance(self.trend, tuple) or len(self.trend) != 2:
            raise TypeError(f"trend must be a (symbol, n) tuple, got {self.trend!r}")
        symbol, n = self.trend
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"trend symbol must be a non-empty str, got {symbol!r}")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"trend n must be an int >= 1, got {n!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"trend": f"{self.trend[0]}:{self.trend[1]}"}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> GatedParams:
    if not isinstance(params, GatedParams):
        raise TypeError(f"params must be GatedParams, got {type(params).__name__}")
    return params


def _gate(p: GatedParams) -> FactorParams:
    """M0120's screen with only its trend gate switched on: ``trend_on`` reads nothing else."""
    return replace(SCREEN, trend=p.trend)


class GatedEqualWeightAllocator:
    """M0120's EW book on data date d when ``trend_on`` holds on d, all cash otherwise.

    The gate is evaluated exactly as RESIDMOM evaluates it (close on d strictly above its n-day
    simple average, False when the gate symbol has no bar dated d or fewer than n bars), and the
    book is M0120's own code path, so the only difference from M0120-EW20-ALWAYS is the gate.
    """

    id = "M0128"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(CLOCK.lookback(p.book), p.trend[1])

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({*CLOCK.symbols(p.book), p.trend[0]}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return CLOCK.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return CLOCK.uses_members(_check(params).book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not trend_on(history, data_date, _gate(p)):
            return ()
        return CLOCK.targets(history, members, data_date, held, p.book)

    def prepare(self, history: Mapping[str, History]) -> ClockPrepared:
        return CLOCK.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ClockPrepared):
            raise TypeError(f"prepared must be ClockPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.history, data_date, _gate(p)):
            return ()
        return CLOCK.targets_prepared(prepared, members, data_date, held, p.book)


GATED = GatedEqualWeightAllocator()


def _v(suffix: str, rules: TradeRules, allocator: Any, params: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0128-{suffix}", family="M0128", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(rules))


METHOD = Method(
    id="M0128",
    name="The near misses re-measured on the fixed tape, beside plain equal-weight books of the same size",
    family="near-miss-fixed-tape",
    source_kind="variation",
    source_ref=(
        "M0030-SAT100, M0007-N20-RAW, M0021-B70-RAW, M0020-W-NOSTOP; controls from "
        "M0120-EW20-ALWAYS; docs/plans/HANDOVER_20261012-measure-then-learn.md section 2 item 4; "
        "insight 211"
    ),
    parent_id="M0030",
    hypothesis=(
        "A re-measurement, not a discovery. Every near miss here was measured on a tape that paid "
        "nothing on idle cash and resized a holding only when it drifted by 1% of the whole "
        "account. Both are fixed now as explicit levers: the band is 20% of the holding's own "
        "target, and idle cash earns the 13-week T-bill yield read the session before. All six "
        "variants run in fractional shares at Gotrade's real fee schedule, funded on the owner's "
        "plan (the opening book plus 5,000,000 IDR on the 25th of every month) against a SPY fed "
        "the identical deposits on the identical days, and every comparison below is that "
        "money-weighted pair. "
        "THE BAND ARITHMETIC, stated before the run: a 20-name equal-weight slot is 5% of the "
        "account and 20% of 5% is exactly 1%, the old band. So for RAW20-CASH, RAW20, "
        "W-NOSTOP-CASH and both controls the band fix changes nothing by construction, and RAW20 "
        "is expected to reproduce M0032-N20-RAW-FRAC-GT -- the same picks at Gotrade's fees on the "
        "old band: money-weighted 13.7% a year against 7.2% for deposit-matched SPY, a 20.6% worst "
        "fall, gains 1.98 times losses, 1,607 trades -- to within what a different starting "
        "capital can move. A material gap there is a finding about the simulator before it is "
        "anything about the method. The band bites only on the blend, whose momentum slots are "
        "3.5% of the account (band 0.7%) and calm slots 1.5% (band 0.3%): B70-CASH should trade "
        "visibly more often per name than any 20-name book here and pay for it in small-trim fees. "
        "THE CASH YIELD is where the tape moves. The gated books sit out roughly 30% of the months "
        "(M0030-SAT100 was 69% invested), and those months earn 3-5% a year before 2008 and almost "
        "nothing after it. Expected: RAW20-CASH leads RAW20 by 0.5 to 1.5 points a year of "
        "money-weighted return, almost all of it before 2008, with a worst fall within half a "
        "point of RAW20's. EW20-CASH, invested about 96% of the time, gains under 0.3 points and "
        "stays about 1.5 points a year behind deposit-matched SPY with a worst fall near 74% "
        "(M0120-EW20-ALWAYS: 5.7% against 7.2%). EW20-GATED-CASH should land near the gated "
        "most-liquid book the lab already measured (M0058-LIQ20-T: 8.1% against 7.2%, a 17.6% "
        "worst fall) plus its share of the cash interest. "
        "PICKING OR SHAPE, and the rule this method will be read by, fixed now: on this one tape, "
        "a near miss's PICKING is its money-weighted lead over deposit-matched SPY minus the gated "
        "control's lead; the GATE is the gated control's lead minus the ungated control's; the "
        "SHAPE is the ungated control's lead (negative means holding equal amounts cost money "
        "against the market). The picks are credited with an edge only if a twin beats the gated "
        "control by more than 1 point a year; otherwise the honest reading is that the near miss "
        "won on the gate and the shape. Expected: RAW20-CASH beats the gated control by 4 to 6 "
        "points a year, so the residual-momentum near misses were winning on their picks and not "
        "on their shape; the shape costs about 1.5 points a year; the gate is worth 2 to 3 points "
        "a year over the whole window, almost all of it in 2001-2002 and 2008. W-NOSTOP-CASH lands "
        "within half a point of RAW20-CASH, because with the band unchanged at 20 names the weekly "
        "re-issue still has almost nothing to do -- so insight 211's point that weekly against "
        "monthly measured nothing should hold for 20-name books even on the fixed tape. B70-CASH "
        "lands between RAW20-CASH and the gated control, its calm sleeve diluting the picks. "
        "WHAT THIS METHOD CANNOT DO is be promoted. Its line runs through M0029 and M0021, both "
        "test-failed, so the hard gate refuses it on kin whatever it scores; and every cash-yield "
        "variant carries the owner input cash-yield (Gotrade paying interest on idle dollars is "
        "not verified), which keeps it ineligible. Only RAW20 can be eligible, and it is expected "
        "to miss the 20% drawdown bar by about the 0.6 points M0032-N20-RAW-FRAC-GT did. It is a "
        "measurement, registered as a method so that it is held to this prediction; it adds one "
        "idea to the lab's count."
    ),
    expected_failure=(
        "The likeliest disappointment is that this confirms rather than changes anything: for "
        "five of the six variants the band fix is arithmetically a no-op and the cash yield is "
        "worth about a point, so the near misses land where they were, a fraction of a point "
        "either side of the 20% drawdown bar, and the method's real contribution is the control "
        "pair. Specific failures written now. (1) The picking edge may live in 1996-2002, where "
        "the dev store prices the fewest of the companies that later died: the survivorship check "
        "of 2026-10-10 took 1 to 1.4 points a year off the momentum books and pushed "
        "M0007-N20-RAW's worst fall from 19.6% to 23.5%. The picking reading must be quoted beside "
        "the check's, and if a twin's lead over the gated control falls under 1 point a year on "
        "the survivorship-check store, the answer becomes 'not clearly picking'. (2) The gated "
        "control holds the 20 most-traded members, which are the biggest companies; the near "
        "misses pick from the whole liquid pool. Part of what this method calls picking may be a "
        "tilt toward smaller members, and this method cannot separate the two. (3) The cash lever "
        "is new. If RAW20-CASH beats RAW20 by more than 2 points a year, that is a reason to audit "
        "the accrual before it is a result. (4) If W-NOSTOP-CASH differs from RAW20-CASH by more "
        "than a point, the cause is the weekly re-issue of the monthly basket at fresh prices, "
        "not the band, and must be reported that way. (5) Deposits soften every worst fall here "
        "alike; none of them may be lined up against an unfunded parent's. (6) The picking edge "
        "may be a pre-2009 edge only: if the twins trail the gated control over 2009-2015 the "
        "verdict says so first, because that is the era most like today."
    ),
    candidates=(
        _v("RAW20-CASH", MONTHLY_TBAND_CASH, RESIDMOM, RAW20,
           "The residual-momentum top 20 of M0030-SAT100 and M0007-N20-RAW, on the fixed tape with cash interest"),
        _v("RAW20", MONTHLY_TBAND, RESIDMOM, RAW20,
           "The same book with the band fix only: no cash interest and no owner input, the one variant that can be eligible"),
        _v("B70-CASH", MONTHLY_TBAND_CASH, BLEND, B70_RAW,
           "M0021-B70-RAW's 70/30 residual-momentum and calm-stock blend, on the fixed tape with cash interest"),
        _v("W-NOSTOP-CASH", WEEKLY_TBAND_CASH, REENTRY, W_NOSTOP,
           "M0020-W-NOSTOP's monthly basket re-issued weekly, on the weekly fixed tape with cash interest"),
        _v("EW20-CASH", MONTHLY_TBAND_CASH, CLOCK, EW20,
           "Control: M0120's 20 most-traded members, equal weight, no gate, on the fixed tape with cash interest"),
        _v("EW20-GATED-CASH", MONTHLY_TBAND_CASH, GATED, GatedParams(),
           "Control: the same 20-name book behind the SPY 200-day gate every near miss here reads"),
    ),
    seen_keys=(
        "concept:near-miss-fixed-tape-remeasure",
        "concept:picking-versus-equal-weight-shape",
    ),
)
