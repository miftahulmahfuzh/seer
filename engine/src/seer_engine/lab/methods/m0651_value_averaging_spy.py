"""M0651 — Value averaging on SPY: put in more after a fall and less after a rise, judged on the
money it ends with.

Source: Edleson (1991), *Value Averaging*; Hayley (2014), "Dynamic Strategy Bias of IRR and
Modified IRR: the Case of Value Averaging", https://openaccess.city.ac.uk/id/eprint/6298/.
Idea: a deposit rule, not a stock picker. The book holds SPY and a cash reserve only. Each month
the money invested in SPY is steered toward a target path that grows by the owner's top-up plus an
assumed growth rate: when SPY has fallen behind the path the rule buys more than the top-up out of
the reserve, when SPY has run ahead of it the rule buys less or nothing and the reserve grows.
Nothing is ever sold (the owner's "buy and hold" habit; Edleson's selling version would add tax
and fee questions the idea row did not ask).

THE MECHANISM is two new book-engine levers (``sim.rules.TradeRules``), in the line of M0519's
and M0555's account-reading levers. Value averaging is a rule about DOLLARS, and an allocator
answers with a weight of an account it is never shown (``held`` is symbols, not money; a shadow
account replayed inside the allocator was tried first and breaks the lookback contract, since
the path depends on every month since the start). So the path lives in
``backtest.book_runner.run_book``, which holds the real account: ``value_path_growth`` keeps a
path that opens at the starting capital, takes every deposit, and compounds at that rate a year
once per month-start rank session; on each rank session the allocator's weights are scaled by
``path / equity``, never above 1. ``value_path_reserve_cap`` floors that scale at one minus
itself. With ``resize_trims=False`` and the band shut (M0532's add-only monthly rules) the book
buys up to that share and never sells. The allocator carries no opinion at all: SPY at a
constant share, 100% on the value-averaging arms.

THE CASH SHARES WERE MEASURED BEFORE ANY RETURN WAS READ, on SPY's closes and the deposit calendar
alone (a throwaway script replaying the rule in a shadow account over the dev store's SPY bars:
two units to start, one on every 25th, fills at the month-end close, no fees, dividends credited
at a flat 1.9% a year; no backtest run, no return printed). Session-averaged share of that shadow
account sitting in the reserve, 1993-02-17 to 2015-10-16:

    assumed growth    whole window    before 2009    2009-2015    months that bought (of 273)
    2% a year         17.8%           20.5%          11.4%         65
    6% a year          9.5%           12.7%           2.0%        132
    2%, reserve
      capped at 20%   14.8%           16.3%          11.4%        130

(For the record, the other rates replayed and not registered: 0% 21.6%, 4% 13.4%, 8% 6.2%, 10%
5.1%, 12% 4.2%. At 8% and above the reserve is empty for all of 2009-2015, so those rungs would
have been straight-in SPY in the years the lab reads first.) A book that is always told to hold
100% still averages 0.4% in cash, because a top-up waits from the 25th to the month's first
session. The constant-share twins below were solved on the same replay, so each one's
session-averaged cash equals its value-averaging arm's to four decimals: 82.5%, 90.9% and 85.5%
in SPY.

SIX ARMS, fractional shares, Gotrade's real fees, the owner's funding plan:
  * G02 (the idea, strong dose): ``value_path_growth=0.02``, the path grows 2% a year. SPY
    outruns it most years, so the reserve builds in rises and is spent in falls.
  * G06 (the idea, mild dose): the path grows 6% a year, close to SPY's own price drift, so the
    rule buys in about half the months.
  * G02-CAP20: G02, but the reserve may never be more than 20% of the account; the excess is
    invested whatever the path says. Prices the unbounded build-up of the late 1990s.
  * CONST-825, CONST-909, CONST-855 (the no-opinion twins): SPY at a constant 82.5%, 90.9% and
    85.5% of the account, traded back every month. Each holds its value-averaging arm's average
    cash with the timing removed, so arm minus twin is what the TIMING of the reserve earned and
    twin minus straight-in SPY is what the idle cash cost.

The straight-in control (the same deposits put into SPY the day they arrive) is NOT re-run: it is
M0555-IMMEDIATE, trial 2034, the same window (1993-02-17 to 2015-10-16) on the same store
(fingerprint 640fc25e5c7b), and it is cited by that trial. The lab's own benchmark line (the same
deposits in total-return SPY) is recorded on every arm besides.

Pure. The allocator reads only SPY's close on data_date; the path reads only the account and the
deposits credited on or before the rank session (``backtest.book_runner``).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0532_deposit_deployment_timing import ADD_MONTHLY
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND00, TradeRules
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History

ADDED = date(2026, 11, 14)

LOOKBACK = 12  # M0555's, so the dev window opens on the same session as the cited straight-in control


@dataclass(frozen=True, slots=True)
class Params:
    """``share``: the constant share of the account wanted in SPY. 1 on the value-averaging arms,
    whose path (a TradeRules lever) scales it month by month; below 1 on the constant twins."""

    share: Decimal = Decimal(1)

    def as_dict(self) -> dict[str, str]:
        return {"share": str(self.share)}


class SpyShare:
    """SPY, always wanted at ``params.share`` of the account. The value-averaging arms' whole
    subject is their TradeRules path (``value_path_growth``, ``value_path_reserve_cap``), never
    this function, so nothing but the path can explain a gap between an arm and straight-in SPY."""

    id = "M0651"

    def lookback(self, params: Any) -> int:
        _check(params)
        return LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        t = target_from_close("SPY", last_close(history.get("SPY"), data_date), to_weight(p.share))
        return () if t is None else (t,)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


def _check(params: object) -> Params:
    if not isinstance(params, Params):
        raise TypeError(f"params must be Params, got {type(params).__name__}")
    return params


ALLOC = SpyShare()
FULL = Params()

# Value averaging buys and never sells: M0532's add-only monthly rules (band shut, trims off) plus
# the path. A constant share has to be traded back both ways, so the twins run on the band-shut tape.
G02: TradeRules = replace(
    ADD_MONTHLY, id="monthly-hold-frac-gotrade-add-only-vpath02", value_path_growth=Decimal("0.02")
)
G06: TradeRules = replace(
    ADD_MONTHLY, id="monthly-hold-frac-gotrade-add-only-vpath06", value_path_growth=Decimal("0.06")
)
G02_CAP20: TradeRules = replace(
    G02, id="monthly-hold-frac-gotrade-add-only-vpath02-cap20", value_path_reserve_cap=Decimal("0.20")
)
CONST_RULES: TradeRules = MONTHLY_HOLD_FRAC_GOTRADE_TBAND00


def _v(suffix: str, rules: TradeRules, params: Params, rationale: str) -> Candidate:
    return Candidate(id=f"M0651-{suffix}", family="M0651", rules=rules, allocator=ALLOC, params=params,
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0651",
    name=(
        "Value averaging on SPY: put in more after a fall and less after a rise, judged on the "
        "money it ends with"
    ),
    family="deposit-value-averaging",
    source_kind="paper",
    source_ref=(
        "Edleson (1991), Value Averaging; Hayley (2014), Dynamic Strategy Bias of IRR and Modified "
        "IRR: the Case of Value Averaging, https://openaccess.city.ac.uk/id/eprint/6298/"
    ),
    parent_id=None,
    hypothesis=(
        "A deposit rule, not a stock picker: the book holds SPY and a cash reserve only (fixed "
        "instruments, no index member is read). Each month the money in SPY is steered toward a "
        "target path that grows by the owner's top-up plus an assumed growth rate: after a fall "
        "the rule buys more than the top-up out of the reserve, after a rise it buys less or "
        "nothing and the reserve grows. Nothing is ever sold. Fractional shares, Gotrade's real "
        "fees, the owner's funding plan. Published 1991 and long known; Hayley (2014) showed it "
        "raises the money-weighted return by construction (more money goes in after poor returns) "
        "while lowering expected final wealth because cash waits. So the verdict is read on the "
        "money each arm ends with and on its worst fall, against a twin holding the same average "
        "cash at a constant share, never on the money-weighted return alone. The path is kept by "
        "the book engine on the real account (two new TradeRules levers, value_path_growth and "
        "value_path_reserve_cap): it opens at the starting capital, takes every deposit, compounds "
        "once a month, and each month the book is told to hold path / account in SPY, never above "
        "100%. Six arms. G02 and G06: the path grows 2% and 6% a "
        "year. G02-CAP20: G02 with the reserve never above 20% of the account. CONST-825, "
        "CONST-909, CONST-855: the no-opinion twins, SPY at a constant 82.5%, 90.9% and 85.5%, "
        "each solved before any return was read so its session-averaged cash equals its arm's "
        "(17.8%, 9.5% and 14.8% in a shadow replay on SPY's closes and the deposit calendar "
        "alone, 1993-02-17 to 2015-10-16; the shadow fills at the close, pays no fees and credits "
        "dividends at a flat 1.9% a year, so the real arms' cash is read back from their recorded "
        "exposure and any miss is stated). The straight-in control is cited, not re-run: M0555-IMMEDIATE, trial 2034, "
        "the same deposits put into SPY the day they arrive, same window, same store. Closest "
        "recorded: M0555 (deposits timed on SPY's own average, rejected) and M0532 (invest the "
        "deposit the day it arrives). SUCCESS: an arm ends with more money than its constant twin "
        "on the dev store, on the survivorship store and in 2009-2015, with a shallower worst "
        "fall than M0555-IMMEDIATE. PREDICTIONS, written before any return was read. (1) Every "
        "arm ends with less money than M0555-IMMEDIATE and fails 'beats SPY', because 9-18% of "
        "the account sat in cash through two decades in which SPY rose. (2) Each value-averaging "
        "arm beats its constant twin by under half a point a year: the reserve is spent near the "
        "2002 and 2009 lows, which is real, but it was built through 1995-1999, the best years "
        "to be invested. (3) The 2009-2015 read is confounded and must be read with the cash "
        "beside it: in those years G02 holds 11.4% cash where its twin holds 17.5%, and G06 2.0% "
        "where its twin holds 9.1%, so an arm beating its twin there is partly just being more "
        "invested in a rising market. (4) The value-averaging arms fall less than M0555-IMMEDIATE "
        "in 2008 on the book without its deposits, by roughly their cash share going in."
    ),
    expected_failure=(
        "The reserve's idle cash costs more than the dip-buying earns: each arm lands within "
        "noise of its constant twin (a few tenths of a point a year either way) and all six land "
        "below straight-in SPY, the same result the lab recorded for dip-timed deposits (M0555) "
        "and for cash left waiting (M0119, M0532). Or an arm beats its twin only because its cash "
        "is unevenly spread across eras: heavy before 2009 and light after, so it was simply more "
        "invested in the 2009-2015 rise, which is an accident of when the window ends, not timing "
        "skill. Or the cap never binds differently enough and G02-CAP20 reads as G02. Or the "
        "calibration's shadow differs from the real account (dividends, fees, open-versus-close "
        "fills) far enough that the realized cash share misses the calibrated one by more than a "
        "point, in which "
        "case the twins are no longer matched and arm-minus-twin has to be corrected for the gap "
        "before it means anything. Whatever the money-weighted return says, it is expected to "
        "flatter value averaging, exactly as Hayley warned."
    ),
    candidates=(
        _v("G02", G02, FULL,
           "THE IDEA, strong dose: steer SPY money toward a path growing 2% a year plus the top-ups, buying only"),
        _v("G06", G06, FULL,
           "THE IDEA, mild dose: the same with the path growing 6% a year"),
        _v("G02-CAP20", G02_CAP20, FULL,
           "G02 with the reserve never above 20% of the account"),
        _v("CONST-825", CONST_RULES, Params(share=Decimal("0.825")),
           "Control: no-opinion twin of G02, SPY at a constant 82.5%, the same average cash with the timing removed"),
        _v("CONST-909", CONST_RULES, Params(share=Decimal("0.909")),
           "Control: no-opinion twin of G06, SPY at a constant 90.9%"),
        _v("CONST-855", CONST_RULES, Params(share=Decimal("0.855")),
           "Control: no-opinion twin of G02-CAP20, SPY at a constant 85.5%"),
    ),
    seen_keys=(
        "concept:value-averaging",
        "concept:deposit-value-path-reserve",
    ),
)
