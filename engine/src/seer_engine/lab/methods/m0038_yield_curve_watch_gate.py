"""M0038 — Regime gate on the yield curve, not on price: stand down for two years after it inverts.

Source: general knowledge (Estrella & Mishkin 1996, "The Yield Curve as a Predictor of U.S.
Recessions", NY Fed Current Issues 2(7); Estrella & Hardouvelis 1991, JF 46(2); the NY Fed's
10-year minus 3-month recession model, published monthly since the late 1990s). Reserved as an
idea row by the lab and re-reserved by Sera 20261016-2034.

Idea, sharpened from the row as written: the row asked for a gate on the term spread **and** the
BAA credit spread. The research store holds no corporate yields, so this tests the yield-curve
half alone, on the 10-year Treasury minus the 13-week bill (the NY Fed's 10y-3m, the one with the
cleanest record) and, as a second reading, the 10-year minus the 5-year. An inverted curve is not
a crash signal: recessions start 6 to 18 months after it, and the curve has usually re-steepened
by the time stocks fall. So "out while inverted" is the wrong gate -- it sells early and buys back
right before the damage. The gate here is a **watch**: it opens on the first inverted day and
stays open for ``watch_days`` calendar days after the last one.

    * ``gate="watch"``: cash while the watch is open. A pure macro switch, no price at all.
    * ``gate="2key"``: cash only while the watch is open **and** SPY closes at or below its
      200-day average. The trend gate every book in the lab uses, armed only after the curve has
      warned. Its claim: the trend gate's false alarms (1998, 2010, 2011, 2015) came with a steep
      curve, its real saves (2000-2002, 2007-2009) came after an inversion, so arming it only on a
      warning keeps the saves and drops the whipsaws.

A spread reading on day t needs both yields dated t; a day where either is missing gives no
reading (and so cannot open the watch). Before the 10-year series starts (1993-11-02) the watch
is closed. ``prepare_market`` collects every inverted date once; ``gate_on`` only looks at those
dated on or before ``data_date`` (a bisect), so the decision reads nothing after it.

Gate off -> no targets (cash, earning nothing: the T-bill interest is not credited, which
understates the gate by roughly the bill rate for the time it sits out). Gate on -> the host's
own targets, unchanged.

Hosts (``host``), the same two M0039 used so the comparison with that gate is like for like:

    * ``"spy"``: SPY at full weight, decided every session, fractional shares at Gotrade's real
      fees (M0039's daily preset). Controls on record: SPY (the benchmark, same fees, same run)
      and M0039-SPY-200 (the SPY 200-day switch on the same daily rules).
    * ``"div"``: M0076-X-M's big-dividend-raise book (20 slots at 5%, the rest in SPY) **with its
      own SPY-200 switch removed**, so the macro gate replaces the trend gate rather than
      stacking on it. Re-picked monthly, re-scaled weekly (monthly-rank-weekly-resize-frac-
      gotrade). Controls: DIV-OPEN here (no gate at all, new) and M0039-DIV on record (the same
      book behind its SPY-200 switch on the same rules).
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0039_vix_term_structure_gate import DAILY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0070_dividend_raise_drift import NOT20
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import ANNOUNCED, R25, AnnParams
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_rotation import trend_on

ADDED = date(2026, 10, 16)

TREND_N = 200  # the 2key gate's price half: SPY's 200-day average, as every lab book uses

Host = Literal["spy", "div"]
Gate = Literal["watch", "2key"]
Short = Literal["T13W", "T5Y"]

DIV_OPEN = AnnParams(replace(R25, inner=NOT20), "ex")  # M0076-X-M's book, its SPY-200 switch removed


@dataclass(frozen=True, slots=True)
class CurveParams:
    """Cash while the ``T10Y - short`` curve inverted within ``watch_days`` (and, 2key, SPY <= SMA200)."""

    host: Host
    gate: Gate
    short: Short = "T13W"
    watch_days: int = 730  # two years: the literature's 6-18 month lead plus the bear market itself
    div: AnnParams = DIV_OPEN

    def __post_init__(self) -> None:
        if self.host not in ("spy", "div"):
            raise ValueError(f"host must be 'spy' or 'div', got {self.host!r}")
        if self.gate not in ("watch", "2key"):
            raise ValueError(f"gate must be 'watch' or '2key', got {self.gate!r}")
        if self.short not in ("T13W", "T5Y"):
            raise ValueError(f"short must be 'T13W' or 'T5Y', got {self.short!r}")
        if isinstance(self.watch_days, bool) or not isinstance(self.watch_days, int) or self.watch_days < 1:
            raise ValueError(f"watch_days must be an int >= 1, got {self.watch_days!r}")
        if not isinstance(self.div, AnnParams):
            raise TypeError(f"div must be AnnParams, got {type(self.div).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"host": self.host, "gate": self.gate, "short": self.short,
               "watch_days": str(self.watch_days)}
        for k, v in self.div.as_dict().items():
            out[f"div.{k}"] = v
        return out


def _check(params: object) -> CurveParams:
    if not isinstance(params, CurveParams):
        raise TypeError(f"params must be CurveParams, got {type(params).__name__}")
    return params


def inverted_dates(series: MarketSeries, short: str) -> tuple[date, ...]:
    """Every date on which both ``T10Y`` and ``short`` were published and T10Y < short, ascending."""
    longs = dict(series.upto("T10Y", date.max))
    return tuple(d for d, v in series.upto(short, date.max) if d in longs and longs[d] < v)


def watch_open(inverted: tuple[date, ...], data_date: date, watch_days: int) -> bool:
    """True when an inverted date lies in (data_date - watch_days, data_date]; reads none after it."""
    i = bisect_right(inverted, data_date)
    return i > 0 and data_date - inverted[i - 1] < timedelta(days=watch_days)


@dataclass(frozen=True, slots=True, eq=False)
class CurvePrepared:
    history: Mapping[str, History]
    inverted: Mapping[str, tuple[date, ...]]  # short leg -> inverted dates; empty without series
    host: Any  # the div host's prepared value; None for the spy host


class CurveGateAllocator:
    """The host's targets while the yield-curve gate is on; nothing (cash) while it is off."""

    def __init__(self, id: str, host: Host, market_fields: tuple[str, ...]) -> None:
        self.id = id
        self._host = host
        self.market_fields = market_fields

    def _p(self, params: object) -> CurveParams:
        p = _check(params)
        if p.host != self._host:
            raise ValueError(f"{self.id} gates host {self._host!r}, got params for {p.host!r}")
        return p

    def lookback(self, params: Any) -> int:
        p = self._p(params)
        own = TREND_N + 1 if p.gate == "2key" else 1
        return max(own, ANNOUNCED.lookback(p.div)) if p.host == "div" else own

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._p(params)
        return tuple(sorted({"SPY", *ANNOUNCED.symbols(p.div)})) if p.host == "div" else ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = self._p(params)
        return ANNOUNCED.holds(p.div) if p.host == "div" else ("SPY",)

    def uses_members(self, params: Any) -> bool:
        return self._p(params).host == "div"

    def _gate_on(self, prepared: CurvePrepared, data_date: date, p: CurveParams) -> bool:
        if not watch_open(prepared.inverted.get(p.short, ()), data_date, p.watch_days):
            return True
        if p.gate == "watch":
            return False
        return trend_on(prepared.history.get("SPY"), data_date, TREND_N)

    def _run(self, prepared: CurvePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: CurveParams) -> tuple[Target, ...]:
        if not prepared.inverted:  # no series: target nothing (market-aware contract)
            return ()
        if not self._gate_on(prepared, data_date, p):
            return ()
        if p.host == "div":
            return ANNOUNCED.targets_prepared(prepared.host, members, data_date, held, p.div)
        h = prepared.history.get("SPY")
        if h is None or (h.index_of(data_date) is None and "SPY" not in held):
            return ()  # a symbol with no bar dated d is never a NEW target
        t = target_from_close("SPY", last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        p = self._p(params)
        return self._run(CurvePrepared(history, {}, None), members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> CurvePrepared:
        host = ANNOUNCED.prepare(history) if self._host == "div" else None
        return CurvePrepared(history, {}, host)

    def prepare_market(self, market: Any) -> CurvePrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        inverted = {} if len(series) == 0 else {s: inverted_dates(series, s) for s in ("T13W", "T5Y")}
        host = ANNOUNCED.prepare_market(market) if self._host == "div" else None
        return CurvePrepared(market.history, inverted, host)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, CurvePrepared):
            raise TypeError(f"prepared must be CurvePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, self._p(params))


SPY_CURVE = CurveGateAllocator("M0038", "spy", ("series",))
DIV_CURVE = CurveGateAllocator("M0038-DIV", "div", ("dividends", "series"))


def _v(suffix: str, allocator: Any, params: Any, rationale: str, rules: Any) -> Candidate:
    return Candidate(id=f"M0038-{suffix}", family="M0038", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())



# --------------------------------------------------------------------------- amendment 1

#: The yardstick's lookback, pinned to the SPY-WATCH arms' own. ``CurveGateAllocator.lookback``
#: returns 1 for a ``watch`` gate on the SPY host, and ``dev.candidate_window`` opened both
#: M0038-SPY-WATCH and this arm's window on 1993-02-01 for that reason. Pinning it is the whole
#: point: a bill read off an arm that was scored on eleven extra months of 1993 is not a bill.
#: M0038-SPY-2KEY reads a 200-bar average and already starts 1993-11-15; the gap between those two
#: arms is M0038's own and is not introduced here.
ALWAYS_LOOKBACK = 1

#: Full weight, once, so the target builder below allocates no new Decimal per session.
ALWAYS_FULL = equal_weight(1)



@dataclass(frozen=True, slots=True)
class AlwaysParams:
    """No dial at all: ``hold`` is held on every session and there is no gate to open.

    A separate params type rather than a ``CurveParams`` with the watch disabled, because
    ``CurveParams`` cannot express "no watch" -- ``gate`` is ``watch`` or ``2key`` and
    ``watch_days`` is at least 1 -- and because a recorded row that said ``gate=watch`` while no
    watch ran would be a lie in the one place the lab cannot afford one.
    """

    hold: str = "SPY"

    def __post_init__(self) -> None:
        if not isinstance(self.hold, str) or not self.hold or self.hold != self.hold.upper():
            raise ValueError(f"hold must be a non-empty upper-case symbol, got {self.hold!r}")

    def as_dict(self) -> dict[str, str]:
        return {"hold": self.hold, "gate": "none"}


def _always(params: object) -> AlwaysParams:
    if not isinstance(params, AlwaysParams):
        raise TypeError(f"params must be AlwaysParams, got {type(params).__name__}")
    return params


class AlwaysAllocator:
    """M0038's SPY host with the curve watch taken out: held every session, never in cash.

    Not market-aware. The gated arms return no target without ``Market.series`` because their
    decision needs the yield curve; this arm has no decision to make, so it reads no series and
    declares no market field. Everything else -- the instrument, the weight, the rule set, the
    lookback -- is M0038's.
    """

    id = "M0038-ALWAYS"

    def lookback(self, params: Any) -> int:
        _always(params)
        return ALWAYS_LOOKBACK

    def symbols(self, params: Any) -> tuple[str, ...]:
        return (_always(params).hold,)

    def holds(self, params: Any) -> tuple[str, ...]:
        return (_always(params).hold,)

    def uses_members(self, params: Any) -> bool:
        _always(params)
        return False

    def _run(self, history: Mapping[str, History], data_date: date,
             p: AlwaysParams) -> tuple[Target, ...]:
        h = history.get(p.hold)
        if h is None or h.index_of(data_date) is None:  # no bar dated d: never a new target
            return ()
        t = target_from_close(p.hold, last_close(h, data_date), ALWAYS_FULL)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(history, data_date, _always(params))

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)  # one instrument: nothing to precompute

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, Mapping):
            raise TypeError(f"prepared must be a Mapping, got {type(prepared).__name__}")
        return self._run(prepared, data_date, _always(params))


ALWAYS = AlwaysAllocator()

AMEND_ALWAYS = Amendment(
    added=date(2026, 10, 27),
    why=(
        "M0038's SPY arms are priced against SPY itself and against M0039-SPY-200, both of them "
        "arms that step aside; nothing in this method's run holds SPY on every session, so what "
        "the curve watch COSTS has never been read off directly. This arm is that zero."
    ),
    hypothesis=(
        "M0389 measured that the lab under-charges a step-aside habit by about half when it "
        "prices the habit against another habit rather than against never stepping aside: on one "
        "chassis the switch alone billed 2.90 points a year, the fear-spike brake 5.04 and the "
        "term-structure brake 2.10, while the stacked pairs billed 5.66 and 3.75 rather than the "
        "7.95 and 5.00 that adding them gives. The fix is an arm with no opinion in it, and M0038 "
        "has one for its dividend host (M0038-DIV-OPEN) and none for its SPY host. This arm is "
        "SPY at full weight on every session of the same window, on M0038's own daily rule set at "
        "Gotrade's real fees, at the same one-bar lookback M0038-SPY-WATCH ran on, so the two "
        "open on the same session (1993-02-01) and the difference between them is the watch and "
        "nothing else. It is a measuring stick, not a candidate: SPY minus Gotrade's fees cannot "
        "beat total-return SPY by construction, and it must not be promoted on any showing. "
        "Success is a readable number -- the watch's own bill, in de-funded annual return against "
        "this arm -- plus the difference between that number and the one M0038's analysis quoted "
        "against M0039-SPY-200, which is the size of the error the lab has been making on this "
        "method. Assumed: cash earns nothing in the gated arms, the store is the same dev store "
        "M0038 ran on, and the comparison is de-funded, because trials.curve_json is the funded "
        "curve and annualizing it directly reports deposits as return."
    ),
    expected_failure=(
        "This arm is run in a LATER run than the arms it prices, which is the one structural "
        "weakness of any retrofit and must be reported with the number. The evidence that it is "
        "survivable was measured on 2026-10-27: M0038-DIV-OPEN (run 2026-10-16), M0173-EXP100 "
        "and M0336-NEVER (both run 2026-10-24) are the same configuration through three allocator "
        "ids and reproduce each other exactly -- 576 trades, 4.2962 turnover, 0.9746 exposure, "
        "57.65% worst fall. If this arm's own re-run on a later store disagrees with that kind of "
        "fidelity, the bill is not readable and the analysis must say so rather than quote it. "
        "The second way this fails is that M0038-SPY-WATCH made two trades in twenty-two years "
        "and sat out 24.5% of its sessions, so its bill is two events wearing a twenty-two-year "
        "coat whatever the yardstick says; a one-number answer here would be false precision, and "
        "the era split is the only honest reading. Third, this arm will post the deepest fall in "
        "the method by a wide margin -- it holds SPY through 2000-2002 and 2008 where SPY-WATCH's "
        "recorded worst fall is 18.88% -- and nothing about that makes the watch worth its price. "
        "No arm of this amendment is expected to be eligible, and the one that is most likely to "
        "clear a bar is the one that is a buy-and-hold index book and not a strategy."
    ),
    candidates=(
        Candidate(
            id="M0038-ALWAYS", family="M0038", rules=DAILY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no curve watch at all, so what "
                       "standing down for two years after an inversion costs can be read off "
                       "directly instead of inferred from another arm that also steps aside."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)


METHOD = Method(
    id="M0038",
    name="Regime gate on the yield curve, not on price: stand down for two years after it inverts",
    family="macro-regime-gate",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "The inverted yield curve as a recession signal was published by Estrella & Hardouvelis "
        "(1991) and Estrella & Mishkin (1996) and has been on the NY Fed's site monthly since the "
        "late 1990s, so it was public through the whole dev window: any edge is not from being "
        "early to it, but from the fact that a bond-market signal cannot be traded away by stock "
        "traders. Sharpened from the idea row: no credit-spread series exists in the store, so this "
        "tests the term-spread half alone, on 10-year minus 13-week bill (the NY Fed's 10y-3m) and, "
        "as a second reading, 10-year minus 5-year. Every lab book uses a SPY 200-day trend gate, "
        "which reads the price it protects and whipsaws in corrections that never become bear "
        "markets. The curve inverts 6-18 months before a recession and has usually re-steepened by "
        "the time stocks fall, so the gate is a WATCH: open from the first inverted day until 730 "
        "calendar days after the last one (two years: the literature's lead plus the bear market; "
        "an assumption, not fitted). WATCH variants sit in cash while it is open (macro only, no "
        "price). 2KEY variants sit in cash only while the watch is open AND SPY closes at or below "
        "its 200-day average: the trend gate armed only after the curve has warned. Claim: the "
        "trend gate's false alarms (1998, 2010, 2011, 2015) came with a steep curve and its real "
        "saves (2000-2002, 2007-2009) came after an inversion, so 2KEY keeps the saves and drops "
        "the whipsaws. Hosts as M0039 (not momentum: every momentum book moves with one that "
        "already lost its test look): (1) SPY, decided every session; (2) M0076-X-M's "
        "big-dividend-raise book (20 slots at 5%, rest in SPY) with its own SPY-200 switch "
        "removed, re-picked monthly, re-scaled weekly. All variants fractional at Gotrade's real "
        "fees on the owner's monthly deposits. Variants: SPY-WATCH, SPY-2KEY, DIV-OPEN (control, "
        "no gate), DIV-WATCH, DIV-2KEY, DIV-2KEY-5Y (2KEY on 10y-5y). Controls on record: "
        "M0039-SPY-200 (SPY 200-day switch, same daily rules) and M0039-DIV (the book behind its "
        "SPY-200 switch, same weekly rules). Assumed: cash earns nothing; a spread reading needs "
        "both yields dated the same day; before 1993-11-02 the watch is closed. Success: the 2KEY "
        "gate beats the plain 200-day switch on the same host in funded return without a deeper "
        "worst fall, its 2009-2015 cost is under a point a year against the ungated host, and a "
        "DIV variant beats total-return SPY within the 25% worst-fall limit."
    ),
    expected_failure=(
        "Two inversions in twenty years is two data points: the dev window holds only 2000 and "
        "2006-07 on 10y-3m, so whatever the result, the luck check sees a gate that fired twice "
        "and the evidence is thin by construction. WATCH sells SPY in August 2000 and September "
        "2006 and misses the last 15-20% of the 2006-07 rally and the first months of the 2009 "
        "rebound (the watch stays open until May 2009), so SPY-WATCH may save 2008 and still lose "
        "on return; it trades a handful of times, so it fails the 100-trade bar regardless. 2KEY "
        "outside a watch is buy-and-hold, so it keeps the 1998 fall (about 19% on SPY) and the "
        "2011 fall; inside a watch it is the 200-day switch, which whipsawed in 2000-2002 and "
        "2008. So 2KEY may equal the 200-day switch through both bears and beat it only by the "
        "fees and lost days of 2010-2015 whipsaws: a real but small gain, perhaps a point a year "
        "in 2009-2015 and nothing before. 10y-5y inverts in late 1994, mid-1998 and 2000 but "
        "barely in 2006, so the 5Y watch is open during 1998 (helping) and closed through 2008 "
        "(no protection at all), likely worse than 10y-3m. The dividend book's own worst fall "
        "(about 22-25%) came in 1998-2002; without its own switch DIV-OPEN may fall 35-50% "
        "in 2008, and if the watch fails to cut it in time DIV-WATCH and DIV-2KEY inherit that. "
        "No variant is likely to clear the 0.90 luck bar."
    ),
    candidates=(
        _v("SPY-WATCH", SPY_CURVE, CurveParams("spy", "watch"),
           "SPY, cash for two years after the 10-year/13-week curve last inverted",
           DAILY_HOLD_FRAC_GOTRADE),
        _v("SPY-2KEY", SPY_CURVE, CurveParams("spy", "2key"),
           "SPY, cash only when that watch is open and SPY is at or below its 200-day average",
           DAILY_HOLD_FRAC_GOTRADE),
        _v("DIV-OPEN", ANNOUNCED, DIV_OPEN,
           "Control: the big-dividend-raise book with no gate at all, weekly-resize rules",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-WATCH", DIV_CURVE, CurveParams("div", "watch"),
           "The big-dividend-raise book, cash for two years after the curve last inverted",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-2KEY", DIV_CURVE, CurveParams("div", "2key"),
           "The big-dividend-raise book behind the 200-day switch, armed only after an inversion",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-2KEY-5Y", DIV_CURVE, CurveParams("div", "2key", short="T5Y"),
           "As DIV-2KEY, with the watch read on the 10-year minus 5-year curve",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
    ),
    amendments=(AMEND_ALWAYS,),
    seen_keys=(
        "concept:yield-curve-gate",
        "concept:term-spread",
        "concept:macro-regime-gate",
        "concept:two-key-trend-gate",
        "concept:risk-gate-overlay",
    ),
)
