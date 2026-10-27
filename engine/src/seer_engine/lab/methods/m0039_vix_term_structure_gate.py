"""M0039 — Risk gate on the VIX term structure, which turns days before a 200-day average.

Source: general knowledge (the VIX futures curve and the spot VIX / VIX3M ratio as a stress
signal: Simon & Campasano 2014, "The VIX Futures Basis"; CBOE's VIX3M, 2007-; widely traded by
volatility funds from about 2012). Reserved by Sera 20261011-1815.
Idea: the 200-day average reacts only after the market has already fallen a long way. The
one-month fear index rising above the three-month one (the term structure "inverting") marks
the start of a shock rather than its middle, so a gate on it should step aside sooner and give
back less on the way down.

The gate is an overlay on a host book and reads ``Market.series`` point in time:

    * ``gate="ts"``: off on data_date d when VIX(d) / VIX3M(d) >= ``threshold``. The store's
      three-month series starts 2006-07-17; before both series carry a value dated within
      ``STALE_DAYS`` of d the gate is ON (no information is not a signal), so a ``ts`` variant
      is its host, trade for trade, until mid-2006. That is deliberate: the paired difference
      with the ungated control is then the gate's effect over 2006-2015 alone.
    * ``gate="spike"``: off when VIX(d) / mean(VIX over the last ``spike_n`` rows through d)
      >= ``threshold``. The fear index alone goes back to 1990, so this proxy for an inverted
      curve -- spot fear far above its own recent level -- covers the whole dev window, the
      summer-1998 fall the idea was written for included.

Gate off -> no targets (cash: the book earns nothing on it; the T-bill yield it would have had
is not credited, which understates the gate a little in 2006-2008 and not at all from 2009).
Gate on -> the host's own targets, unchanged.

Hosts (``host``):

    * ``"spy"``: SPY at full weight, decided every session (daily cadence, fractional shares at
      Gotrade's real fees). The paired controls are SPY itself (the benchmark, which pays the
      same fees in the same run) and the SPY-200 switch on the same daily rules (F1's
      ``TIMING``, variant SPY-200).
    * ``"div"``: M0076-X-M's big-dividend-raise book (M0070's event, 20 slots at 5%, the rest in
      SPY, behind its own SPY-200 switch), re-picked monthly and re-scaled weekly on
      monthly-rank-weekly-resize-frac-gotrade, so a weekly gate check can cut the book between
      re-picks. The engine re-enters a cut basket only at the next monthly re-pick. Paired
      control: the same host on the same rules with no VIX gate (variant DIV, M0076's own
      allocator), since the weekly re-scale also lets the host's own SPY-200 switch act weekly.

Market-aware: ``prepare_market`` carries the series (and, for ``div``, the dividend calendar).
The history-only path has no series and targets nothing, per the lab's market-aware contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import ANNOUNCED, R25, AnnParams
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TIMING, TimingParams

ADDED = date(2026, 10, 11)

# SPY decided every session in fractional shares at Gotrade's real fees. No preset of this id
# exists: it runs on dev, and `promote` would need one (a feature-wish if it wins). resize=True
# so the monthly deposits are invested (the 1% resize band keeps it from trading daily noise).
DAILY_HOLD_FRAC_GOTRADE = replace(MONTHLY_HOLD_FRAC_GOTRADE, id="daily-hold-frac-gotrade",
                                  cadence="daily")

STALE_DAYS = 7  # a series row older than this (calendar days) is no reading: gate on

Host = Literal["spy", "div"]
Gate = Literal["ts", "spike"]


@dataclass(frozen=True, slots=True)
class GateParams:
    """``host`` is the book gated; ``gate`` the signal; off when the ratio is >= ``threshold``."""

    host: Host
    gate: Gate
    threshold: float = 1.0
    spike_n: int = 63  # spike: sessions of VIX in the trailing mean (about three months)
    div: AnnParams = AnnParams(R25, "ex")  # the div host's book: M0076-X-M

    def __post_init__(self) -> None:
        if self.host not in ("spy", "div"):
            raise ValueError(f"host must be 'spy' or 'div', got {self.host!r}")
        if self.gate not in ("ts", "spike"):
            raise ValueError(f"gate must be 'ts' or 'spike', got {self.gate!r}")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, float) or not self.threshold > 0:
            raise ValueError(f"threshold must be a positive float, got {self.threshold!r}")
        if isinstance(self.spike_n, bool) or not isinstance(self.spike_n, int) or self.spike_n < 2:
            raise ValueError(f"spike_n must be an int >= 2, got {self.spike_n!r}")
        if not isinstance(self.div, AnnParams):
            raise TypeError(f"div must be AnnParams, got {type(self.div).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"host": self.host, "gate": self.gate, "threshold": repr(self.threshold),
               "spike_n": str(self.spike_n)}
        for k, v in self.div.as_dict().items():
            out[f"div.{k}"] = v
        return out


def _check(params: object) -> GateParams:
    if not isinstance(params, GateParams):
        raise TypeError(f"params must be GateParams, got {type(params).__name__}")
    return params


def _fresh(rows: tuple[tuple[date, float], ...], data_date: date) -> bool:
    return bool(rows) and (data_date - rows[-1][0]) <= timedelta(days=STALE_DAYS)


def gate_on(series: MarketSeries, data_date: date, p: GateParams) -> bool:
    """True when the book may be invested on ``data_date``; reads only rows dated <= data_date."""
    vix = series.upto("VIX", data_date, last=p.spike_n if p.gate == "spike" else 1)
    if not _fresh(vix, data_date):
        return True
    if p.gate == "ts":
        v3 = series.upto("VIX3M", data_date, last=1)
        if not _fresh(v3, data_date) or v3[-1][1] <= 0:
            return True
        return vix[-1][1] / v3[-1][1] < p.threshold
    if len(vix) < p.spike_n:
        return True
    total = 0.0
    for _, v in vix:  # left to right, so the float is the same however much history is loaded
        total += v
    mean = total / len(vix)
    return mean <= 0 or vix[-1][1] / mean < p.threshold


@dataclass(frozen=True, slots=True, eq=False)
class GatePrepared:
    history: Mapping[str, History]
    series: MarketSeries
    host: Any  # the div host's prepared value; None for the spy host


class GateAllocator:
    """The host's targets while the VIX gate is on; nothing (cash) while it is off."""

    def __init__(self, id: str, host: Host, market_fields: tuple[str, ...]) -> None:
        self.id = id
        self._host = host
        self.market_fields = market_fields

    def _p(self, params: object) -> GateParams:
        p = _check(params)
        if p.host != self._host:
            raise ValueError(f"{self.id} gates host {self._host!r}, got params for {p.host!r}")
        return p

    def lookback(self, params: Any) -> int:
        p = self._p(params)
        return ANNOUNCED.lookback(p.div) if p.host == "div" else 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._p(params)
        return ANNOUNCED.symbols(p.div) if p.host == "div" else ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = self._p(params)
        return ANNOUNCED.holds(p.div) if p.host == "div" else ("SPY",)

    def uses_members(self, params: Any) -> bool:
        return self._p(params).host == "div"

    def _run(self, prepared: GatePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: GateParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        if not gate_on(prepared.series, data_date, p):
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
        return self._run(GatePrepared(history, EMPTY_SERIES, None), members, data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> GatePrepared:
        host = ANNOUNCED.prepare(history) if self._host == "div" else None
        return GatePrepared(history, EMPTY_SERIES, host)

    def prepare_market(self, market: Any) -> GatePrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        host = ANNOUNCED.prepare_market(market) if self._host == "div" else None
        return GatePrepared(market.history, series, host)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, GatePrepared):
            raise TypeError(f"prepared must be GatePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, self._p(params))


SPY_GATE = GateAllocator("M0039", "spy", ("series",))
DIV_GATE = GateAllocator("M0039-DIV", "div", ("dividends", "series"))


def _v(suffix: str, allocator: Any, params: Any, rationale: str, rules: Any) -> Candidate:
    return Candidate(id=f"M0039-{suffix}", family="M0039", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())



# --------------------------------------------------------------------------- amendment 1

#: The yardstick's lookback, pinned to the gated SPY arms' own. ``GateAllocator.lookback``
#: returns 1 for the SPY host, and M0039-SPY-TS and M0039-SPY-SPIKE are both recorded starting
#: 1993-02-01 for that reason. Pinning it is the whole point: a bill read off an arm scored on a
#: different window is not a bill. M0039-SPY-200 reads a 200-bar average and opens 1993-11-12;
#: that gap is M0039's own and is not introduced here.
ALWAYS_LOOKBACK = 1

#: Full weight, once, so the target builder below allocates no new Decimal per session.
ALWAYS_FULL = equal_weight(1)



@dataclass(frozen=True, slots=True)
class AlwaysParams:
    """No dial at all: ``hold`` is held on every session and there is no gate to open.

    A separate params type rather than a ``GateParams`` with the gate disabled, because
    ``GateParams`` cannot express it: ``gate`` is ``ts`` or ``spike`` and ``threshold`` is a
    level, not an off switch, and a recorded row reading ``threshold=1000000000.0`` would be a
    dial abused rather than a gate removed.
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
    """M0039's SPY host with the fear gate taken out: held every session, never in cash.

    Not market-aware. The gated arms return no target without ``Market.series`` because their
    decision needs the fear index; this arm has no decision to make, so it reads no series and
    declares no market field. ``GateParams`` could not express this: ``gate`` is ``ts`` or
    ``spike`` and ``threshold`` is a level, not an off switch, and a row reading
    ``threshold=1000000000.0`` would be a dial abused rather than a gate removed.
    """

    id = "M0039-ALWAYS"

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
        "M0039's two fear gates are priced against M0039-SPY-200, which is itself a step-aside "
        "rule, so what either gate costs on its own has never been read. This arm is SPY held on "
        "every session of the same window: the zero both gates and the 200-day switch are "
        "measured from."
    ),
    hypothesis=(
        "M0389 proved on this exact chassis -- SPY at full weight, decided every session, "
        "fractional at Gotrade's real fees -- that two step-aside habits are strongly "
        "sub-additive, and that the lab's habit of quoting stacked-minus-switch as an overlay's "
        "price understates the overlay's own bill by about half: 55% for the fear spike and 40% "
        "for the term structure. M0039 is the method both of those overlays were first registered "
        "on, and it is the one that has never carried the zero. This arm is that zero: SPY at full "
        "weight on every session, M0039's own daily rule set, the same one-bar lookback its "
        "gated arms ran on, so M0039-SPY-TS, M0039-SPY-SPIKE and this arm all open on 1993-02-01 "
        "and every paired difference is the gate alone. M0039-SPY-200 opens 1993-11-12 because it "
        "reads a 200-bar average; that gap is M0039's own and is not introduced here, and the "
        "switch's own bill must therefore be read on the common era rather than whole-window. "
        "Success is three numbers the method could not produce before: the term structure's own "
        "bill, the fear spike's own bill, and the difference between each and the figure M0039's "
        "analysis quoted against the 200-day switch. It is a measuring stick and not a candidate; "
        "it cannot beat total-return SPY because it pays Gotrade's fees to hold the same thing, "
        "and it must not be promoted on any showing."
    ),
    expected_failure=(
        "The first way this fails is coverage, and it is certain rather than likely: VIX3M begins "
        "2006-07-17 in the dev store, so M0039-SPY-TS is this arm trade for trade over the "
        "window's first thirteen years and its whole-window bill is diluted by roughly half. Only "
        "the spike cell reads both bear markets. Any term-structure bill quoted off this arm "
        "without the 2006-2015 split attached is a number wearing a coat that does not fit. "
        "Second, this arm runs in a LATER run than the arms it prices. The fidelity evidence is "
        "the three-way reproduction measured on 2026-10-27 -- M0038-DIV-OPEN, M0173-EXP100 and "
        "M0336-NEVER, one configuration through three allocator ids on two dates eight days "
        "apart, identical to four decimals -- but it is evidence about a different chassis, and "
        "if this arm's numbers do not sit where SPY's own recorded total return says they should, "
        "the bill is unreadable and the analysis must say so. Third, this arm will post by far "
        "the deepest fall in the method: M0039-SPY-SPIKE already records 63.59% and this arm "
        "holds through the whole of 2000-2002 and 2008 with nothing to cut it, so it will fail "
        "the fall screen by a wide margin. That is the arm working, not failing."
    ),
    candidates=(
        Candidate(
            id="M0039-ALWAYS", family="M0039", rules=DAILY_HOLD_FRAC_GOTRADE, allocator=ALWAYS,
            params=AlwaysParams(),
            rationale=("Yardstick: SPY held on every session with no fear gate and no trend "
                       "switch, so each gate's own cost can be read off directly instead of "
                       "inferred from an arm that also steps aside."),
            added=date(2026, 10, 27), owner_inputs=(),
        ),
    ),
)


METHOD = Method(
    id="M0039",
    name="Risk gate on the VIX term structure, which turns days before a 200-day average",
    family="volatility-term-structure-gate",
    source_kind="knowledge",
    source_ref="",
    parent_id=None,
    hypothesis=(
        "The VIX term structure as a stress signal has been public since VIX futures listed (2004) "
        "and widely traded by volatility funds since about 2012, so the dev window (to 2015) sees it "
        "before most of the crowd. The 200-day trend gate reacts only after the market has fallen a "
        "long way; the one-month fear index rising above the three-month one marks the start of a "
        "shock, so a gate on it should step aside sooner. Hosts, chosen so no momentum book is "
        "involved (every momentum book moves with a book that already lost its test look): (1) SPY "
        "itself, decided every session, cash when the gate is off, fractional at Gotrade's real "
        "fees; (2) M0076-X-M's big-dividend-raise book (20 slots, rest in SPY, behind its SPY-200 "
        "switch), re-picked monthly and re-scaled weekly so the gate can cut it between re-picks. "
        "Variants: SPY-TS (off while VIX/VIX3M >= 1.00), SPY-SPIKE (off while VIX >= 1.20x its own "
        "63-session mean: a proxy for inversion that covers the whole window, mid-1998 included), "
        "SPY-200 (control: the SPY 200-day switch on the same daily rules), DIV (control: the host "
        "on the weekly-resize rules, no VIX gate), DIV-TS and DIV-SPIKE (the host behind each gate). "
        "VIX3M starts 2006-07-17; before it the TS gate is on, so TS variants equal their controls "
        "trade for trade until mid-2006 and the paired difference is the gate over 2006-2015, "
        "which includes 2008, the May 2010 flash crash and August 2011. Assumed: cash earns nothing "
        "(no T-bill credit), a series value older than 7 days is no reading (gate on), the gate reads "
        "the fear index's close on day d and trades at the next open. Success: the gated host beats "
        "its control on funded return with a shallower worst fall over 2006-2015, and a gated "
        "variant beats total-return SPY within the 20% worst fall with a positive 2009-2015 edge."
    ),
    expected_failure=(
        "Inversions are frequent, brief and mostly harmless (August 2007, May 2010, August 2011, "
        "October 2014, August 2015 all reversed within weeks), so the gate sells after the first "
        "drop and buys back after the rebound, paying Gotrade's fees both ways and missing the "
        "recovery days that follow fear spikes. Over 2006-2015 SPY's worst fall (2008) would be cut, "
        "but the 2009-2015 years, a long rally punctuated by short scares, should cost the gated SPY "
        "a point or more a year against plain SPY. SPY-TS before mid-2006 is SPY less fees, so over "
        "the full window it cannot beat SPY by much even if the gate works; its worst fall from "
        "1996-2003 (the 2000-2002 bear, about 47%) is untouched, so SPY-TS fails the 20% limit "
        "regardless. SPY-SPIKE covers that bear market, but 2001-2002 was a slow grind with few "
        "spikes, so it likely still falls well over 20%. On the dividend host the weekly cut "
        "re-enters only at the next monthly re-pick, so every false alarm costs up to a month out of "
        "the market; the host's 21.9% worst fall came in the 1998-2002 fast falls, which the TS "
        "gate cannot see, so DIV-TS likely keeps that fall and only DIV-SPIKE can address it. "
        "Cash earning nothing understates the gate slightly in 2006-2008."
    ),
    candidates=(
        _v("SPY-TS", SPY_GATE, GateParams("spy", "ts", 1.0),
           "SPY, cash while the one-month fear index is at or above the three-month one",
           DAILY_HOLD_FRAC_GOTRADE),
        _v("SPY-SPIKE", SPY_GATE, GateParams("spy", "spike", 1.2),
           "SPY, cash while the fear index is 20%+ above its own three-month average (whole window)",
           DAILY_HOLD_FRAC_GOTRADE),
        _v("SPY-200", TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
           "Control: SPY behind its 200-day average on the same daily rules", DAILY_HOLD_FRAC_GOTRADE),
        _v("DIV", ANNOUNCED, AnnParams(R25, "ex"),
           "Control: the big-dividend-raise book on the weekly-resize rules, no fear-index gate",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-TS", DIV_GATE, GateParams("div", "ts", 1.0),
           "The big-dividend-raise book behind the term-structure gate, checked weekly",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-SPIKE", DIV_GATE, GateParams("div", "spike", 1.2),
           "The big-dividend-raise book behind the fear-spike gate, checked weekly",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
    ),
    amendments=(AMEND_ALWAYS,),
    seen_keys=(
        "concept:vix-term-structure",
        "concept:volatility-term-structure-gate",
        "concept:vix-spike-gate",
        "concept:risk-gate-overlay",
    ),
)
