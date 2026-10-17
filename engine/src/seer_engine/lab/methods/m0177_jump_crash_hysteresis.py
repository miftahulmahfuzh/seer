"""M0177 — The filtered news-day book that leaves on a crash and comes back on the recovery.

Source: variation of M0075 (M0092-SQRT-CAP10's filtered earnings-day picks, Brandt, Kishore,
Santa-Clara & Venkatachalam 2008, SSRN 909563, behind a weekly crash latch), queued by Sera's
synthesis 20261017-1607 as the one repair M0075's analysis left open.
Idea: M0075-SQRT-DD8's exit (SPY 8% under its 126-session high) saved the August 1998 crash, but
its re-entry was a calendar: out until the next monthly check. Through the V-shaped falls of 2000
and 2007 that lockout sold after the drop, sat in cash through the bounce and bought back near the
top, and the worst fall deepened to 33%. So keep the exit and swap the calendar for a price: come
back at the next weekly check once SPY has recovered to within ``reentry`` of its high. The gap
between the exit level and the re-entry level is the hysteresis that stops a single noisy day from
flipping the book in and out.

Mechanics. Rules ``monthly-rank-weekly-resize-frac-gotrade``. On the month's rank session (data
date = the anchor, the session before the month's first session) the basket is M0092's, chosen
exactly as M0092 chooses it, monthly SPY-200 switch included: a month the switch reads off stays in
cash whatever the gate says. On every weekly resize session the runner keeps that basket and reads
only the allocator's total weight: the full basket while the gate is in, nothing (cash) while it
is out. The gate is a two-level switch on SPY's closes, read without carried state by scanning back
from ``data_date`` to the most recent session that was an *event*:

    * an **exit day**: SPY's close at or more than ``dd_limit`` below the highest close of the
      ``dd_n`` sessions through that day (M0075's DD leg);
    * a **re-entry day**: SPY's close within ``reentry`` of that same high **and** above its
      ``sma_n``-session simple average.

The gate is out when the most recent event is an exit day, in when it is a re-entry day, and in
when no event lies in the last ``scan`` sessions (SPY sitting between the two levels for 200 sessions
has never happened in the store; the safe default is the book M0092 would hold). This is exactly
the forward state machine "trip -> out; out and re-entry -> in" started ``scan`` sessions back, so
it needs no memory between calls. A session SPY has no bar for, or one with too little history,
is an exit day (the safe side). Assumptions written before the run: the gate reads every session,
not only the weekly data dates, so a trip on a Tuesday counts at Friday's decision unless SPY has
already recovered into the re-entry band by Friday; a re-entry mid-month buys back the anchor's
basket at fresh prices (as M0075 and M0020 do), not a re-pick. Reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0020_stop_with_weekly_reentry import _refreshed, anchor_date
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZPrepared
from seer_engine.lab.methods.m0075_jump_crash_latch import EQUAL, SQRT
from seer_engine.lab.methods.m0092_jump_trading_value_weight import SIZED, SizeParams
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 17)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class GateParams:
    """``inner`` is M0092's picks, sizes and monthly switch; the rest is the two-level weekly gate."""

    inner: SizeParams
    dd_limit: Decimal = Decimal("0.08")
    reentry: Decimal = Decimal("0.04")
    dd_n: int = 126
    sma_n: int = 200
    scan: int = 200
    market: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.inner, SizeParams):
            raise TypeError(f"inner must be SizeParams, got {type(self.inner).__name__}")
        for name in ("dd_limit", "reentry"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not 0 < v < 1:
                raise ValueError(f"{name} must be a Decimal in (0, 1), got {v!r}")
        if not self.reentry < self.dd_limit:
            raise ValueError(f"reentry must sit inside dd_limit, got {self.reentry} >= {self.dd_limit}")
        for name in ("dd_n", "sma_n", "scan"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 2:
                raise ValueError(f"{name} must be an int >= 2, got {v!r}")
        if not isinstance(self.market, str) or not self.market:
            raise ValueError(f"market must be a non-empty symbol, got {self.market!r}")

    def as_dict(self) -> dict[str, str]:
        out = {
            "dd_limit": str(self.dd_limit),
            "reentry": str(self.reentry),
            "dd_n": str(self.dd_n),
            "sma_n": str(self.sma_n),
            "scan": str(self.scan),
            "market": self.market,
        }
        for k, v in self.inner.as_dict().items():
            out[f"inner.{k}"] = v
        return out


def _check(params: object) -> GateParams:
    if not isinstance(params, GateParams):
        raise TypeError(f"params must be GateParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the gate


def event(h: History, j: int, p: GateParams) -> str | None:
    """``"exit"``, ``"reentry"`` or None for SPY's bar j (see the module docstring); reads bars <= j."""
    if j + 1 < max(p.dd_n, p.sma_n):
        return "exit"
    close = float(h.close[j])
    high = float(h.close[j + 1 - p.dd_n : j + 1].max())
    if not close > high * (1.0 - float(p.dd_limit)):
        return "exit"
    sma = float(h.close[j + 1 - p.sma_n : j + 1].mean())
    if close >= high * (1.0 - float(p.reentry)) and close > sma:
        return "reentry"
    return None


def gate_in(history: Mapping[str, History], data_date: date, p: GateParams) -> bool:
    """True when the most recent event through ``data_date`` is a re-entry day, or none is in reach."""
    h = history.get(p.market)
    if h is None:
        return False
    hi = h.index_of(data_date)
    if hi is None:
        return False
    for j in range(hi, max(hi - p.scan, -1), -1):
        e = event(h, j, p)
        if e is not None:
            return e == "reentry"
    return True


# --------------------------------------------------------------------------- the allocator


class HysteresisJumpAllocator:
    """M0092's monthly basket while the two-level gate is in, cash while it is out."""

    id = "M0177"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(SIZED.lookback(p.inner), p.scan + max(p.dd_n, p.sma_n)) + 25  # anchor ~23 back

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        return tuple(sorted({p.market, *SIZED.symbols(p.inner)}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return SIZED.holds(_check(params).inner)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        if not gate_in(history, data_date, p):
            return ()
        anchor = anchor_date(data_date)
        cut = {s: h.upto(anchor) for s, h in history.items()}
        basket = SIZED.targets(cut, members, anchor, held, p.inner)
        return _refreshed(basket, history, data_date, None)

    def prepare(self, history: Mapping[str, History]) -> ZPrepared:
        return SIZED.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not gate_in(prepared.history, data_date, p):
            return ()
        anchor = anchor_date(data_date)
        basket = SIZED.targets_prepared(prepared, members, anchor, held, p.inner)
        return _refreshed(basket, prepared.history, data_date, None)


GATED = HysteresisJumpAllocator()


def _v(suffix: str, params: GateParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0177-{suffix}", family="M0177", rules=MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
                     allocator=GATED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0177",
    name="Exit on the crash, come back on the recovery: the filtered news-day book leaving when "
         "SPY is 8% under its high and returning once it is back within 4%",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0075 (M0092-SQRT-CAP10's picks, Brandt, Kishore, Santa-Clara & "
               "Venkatachalam 2008, SSRN 909563, behind M0012's DD8 crash leg) with the monthly "
               "lockout replaced by a price re-entry with hysteresis; queued by Sera 20261017-1607",
    parent_id="M0075",
    hypothesis=(
        "Published 2008 (the earnings-day drift), so the dev window can only show the drift from "
        "before and just after it was widely known; 2009-2015 is judged first. M0075-SQRT-DD8 "
        "showed an exit when SPY closes 8% under its 126-session high saves the August 1998 crash "
        "(1998 -3% -> +15% without deposits), but its calendar lockout (back only at the next "
        "monthly check) sold low and rebought high through the 2000 and 2007 V-shaped recoveries: "
        "worst fall 33% (Jul 2007-Jul 2009), luck score 0.862 at N=112, +10.6% a year vs SPY's "
        "+7.2% on the owner's deposits, against the no-latch control's +12.0%, 25.1% and 0.895. "
        "Keep M0092-SQRT-CAP10's monthly picks, sizes and monthly SPY-200 switch and the DD8 exit "
        "exactly, on monthly-rank-weekly-resize-frac-gotrade, but re-enter on price: the gate goes "
        "back in at the next weekly check once SPY closes within the re-entry band of its "
        "126-session high and above its 200-day average, with no wait for the month's end. "
        "Variants: SQRT-DD8-R4 (exit 8%, back within 4%), SQRT-DD8-R2 (back within 2%: later, "
        "surer), SQRT-DD12-R4 (exit only at 12%: trips on 1998, 2001-2002 and 2008, not on the "
        "10% pullbacks of 2007, 2010 and 2011) and EQ-DD8-R4 (the R4 gate on M0072-Z2-RAWRANK's "
        "equal 5% slots, the second host). I expect SQRT-DD8-R4 or SQRT-DD12-R4 to be best: keep "
        "most of 1998's saving, buy back within weeks after a V-shaped fall instead of a month, "
        "worst fall near 20-22% funded, about +11.5% a year. Success: beats total-return SPY on "
        "the owner's deposits, worst fall (funded) within the bar, DSR >= 0.90, positive against "
        "SPY in 2009-2015 and in a majority of walk-forward folds."
    ),
    expected_failure=(
        "A price-based re-entry still buys back after the bounce: by the time SPY is back within "
        "4% of its high it has recovered most of the drop, so each round trip still sells low and "
        "buys higher, and it only narrows the whipsaw M0075 paid. The 2007-2008 top was a series "
        "of 8-10% falls and quick recoveries to within 4%, which is precisely the pattern that "
        "trips DD8-R4 repeatedly; R2 waits longer and may miss more of each rebound. DD12 may "
        "trip too late in August 1998 (SPY was 12% down only near the end of the month) to save "
        "much. Each exit and re-entry pays Gotrade's charges on 20 small slots. The luck score "
        "will likely stay under 0.90 because the control itself read 0.895 at N=112 and N has "
        "grown since. And the survivorship-check store already drops this family to 1 of 4 "
        "folds, which no switch can repair. A published 2008 anomaly, so any dev edge may have "
        "faded after 2016."
    ),
    candidates=(
        _v("SQRT-DD8-R4", GateParams(SQRT, Decimal("0.08"), Decimal("0.04")),
           "M0092-SQRT-CAP10 out when SPY is 8% under its 6-month high, back once within 4%"),
        _v("SQRT-DD8-R2", GateParams(SQRT, Decimal("0.08"), Decimal("0.02")),
           "The same exit, back only once SPY is within 2% of its high"),
        _v("SQRT-DD12-R4", GateParams(SQRT, Decimal("0.12"), Decimal("0.04")),
           "A deeper exit that sees only real crashes: out at 12% under the high, back within 4%"),
        _v("EQ-DD8-R4", GateParams(EQUAL, Decimal("0.08"), Decimal("0.04")),
           "The DD8-R4 gate on M0072-Z2-RAWRANK's equal 5% slots: the second host"),
    ),
    seen_keys=(
        "concept:event-drift-crash-hysteresis",
        "concept:fast-exit-price-reentry",
        "concept:drawdown-band-switch",
    ),
)
