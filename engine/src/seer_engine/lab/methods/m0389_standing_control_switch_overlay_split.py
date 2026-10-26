"""M0389 — The never-step-aside arm as a standing control, and the complete 2x2 that splits
the switch's bill from the overlay's.

Source: variation of M0381 (the nine-day fear overlay on the 200-day switch). Reserved by Sera
20261026-1320.

THE PROBLEM THIS METHOD EXISTS TO FIX. Every timing method the lab has run puts an overlay on
top of the 200-day switch and prices it against the switch alone. That pairing answers "is the
overlay worth anything *given* the switch", and the lab has repeatedly quoted the answer as
though it were "what does the overlay cost". M0381 made the gap visible: once it registered an
always-invested arm, the same de-funded 2009-2015 window read holding the market every session
far above the plain switch, and the switch turned out to have been charging a large bill before
any overlay existed. The attribution the lab has been making -- overlay bill = switch arm minus
overlay arm -- is a *marginal* cost, not the overlay's own, and it is only equal to the
overlay's own cost if the two habits are additive.

Nothing in the lab's record tests that additivity, because the fourth cell has never been run.
For the two volatility overlays the lab has measured, three of the four cells exist and the
fourth does not:

    overlay alone, no switch   M0039-SPY-TS, M0039-SPY-SPIKE   (recorded)
    switch alone               M0039-SPY-200, M0381-SWITCH     (recorded)
    always invested            M0381-ALWAYS                    (recorded)
    switch AND overlay         -- never run for the spike rule; M0381-TS for the term structure,
                                  but on a different allocator, in a different run, at a
                                  different funding

and recorded returns from different runs are not safely comparable anyway (the lab has seen a
recorded +660% re-run at +545%). So the decomposition has to be measured inside one run, on one
allocator, at one funding, or it is arithmetic across incomparable numbers.

WHAT THIS RUNS. One allocator, one chassis (SPY at full weight, decided every session,
fractional shares at Gotrade's real fees -- DAILY_HOLD_FRAC_GOTRADE, M0039's and M0381's preset),
six arms, which are the complete 2x2 for two overlays sharing one pair of baseline cells:

                        switch OFF            switch ON
    overlay none        ALWAYS                SWITCH
    overlay spike       SPIKE                 SPIKE-X
    overlay ts          TS                    TS-X

With B(x) = the de-funded annual return of ALWAYS minus that of arm x, each bill is read off
directly instead of inferred:

    switch's own bill        B(SWITCH)
    overlay's own bill       B(SPIKE),  B(TS)
    the pair's bill          B(SPIKE-X), B(TS-X)
    interaction              B(pair) - B(switch) - B(overlay)

A near-zero interaction means the lab's habit of subtracting the switch arm is sound and every
recorded overlay verdict stands. A large negative interaction means the two habits step aside on
the same days, their bills overlap, and quoting switch-arm-minus-overlay-arm as "what the
overlay costs" has been charging the overlay for days the switch had already paid for.

THE OVERLAYS ARE M0039'S, BAR FOR BAR. ``overlay_allows`` delegates to
``m0039_vix_term_structure_gate.gate_on`` with M0039's own recorded thresholds -- ts at 1.00,
spike at 1.20 over a 63-session trailing mean -- so no dial is fitted here and the alone-cells
are the rule M0039 already registered, not a re-specification of it. A series row older than
``STALE_DAYS`` calendar days is no reading, and no reading never forces cash (M0039's
convention, imported).

    * ``"ts"``    cash when VIX(d) / VIX3M(d) >= 1.00. VIX3M begins 2006-07-17 in the dev store,
                  so this overlay is inert for the window's first thirteen years and covers
                  2006-2015, the 2008 fall included.
    * ``"spike"`` cash when VIX(d) / mean(VIX over the last 63 rows through d) >= 1.20. VIX
                  begins 1993-01-29, so this overlay reads the WHOLE dev window -- both bear
                  markets -- and is the only cell on which the interaction can be measured where
                  the switch actually does its work.

The switch is ``f_index.above_sma``, so SWITCH is the lab's SPY-200 rule bar for bar.

Cash earns nothing (no T-bill credit), as in M0039 and M0381. That is an assumption, not a
finding: crediting idle cash would shrink every bill below, but it would shrink them in the same
direction and cannot create or destroy an interaction term, which is what this method measures.

Market-aware: ``prepare_market`` carries the series. The history-only path has no series and
targets nothing, for every arm including ALWAYS and SWITCH whose params never read a series --
the contract is a property of the allocator, not of the params, and holding all six to it keeps
them on one allocator and so one comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0039_vix_term_structure_gate import (
    DAILY_HOLD_FRAC_GOTRADE,
    GateParams,
    gate_on,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import above_sma

ADDED = date(2026, 10, 26)

FULL_WEIGHT = equal_weight(1)

Overlay = Literal["none", "spike", "ts"]
OVERLAYS: tuple[str, ...] = ("none", "spike", "ts")


@dataclass(frozen=True, slots=True)
class SplitParams:
    """One cell of the 2x2: the switch on or off, crossed with an overlay or none."""

    switch: bool = True  # the SPY-200 switch; False = never steps aside for a trend
    overlay: Overlay = "none"  # M0039's gate, or none
    n: int = 200  # the switch's SMA length, in daily closes
    # M0039's own recorded thresholds, carried as fields so the digest records them. No arm
    # varies them and nothing here sweeps them: they are frozen references, not dials.
    ts_threshold: float = 1.0
    spike_threshold: float = 1.2
    spike_n: int = 63

    def __post_init__(self) -> None:
        if not isinstance(self.switch, bool):
            raise TypeError(f"switch must be a bool, got {type(self.switch).__name__}")
        if not isinstance(self.overlay, str):
            raise TypeError(f"overlay must be a str, got {type(self.overlay).__name__}")
        if self.overlay not in OVERLAYS:
            raise ValueError(f"overlay must be one of {OVERLAYS}, got {self.overlay!r}")
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 2:
            raise ValueError(f"n must be an int >= 2, got {self.n!r}")
        for name in ("ts_threshold", "spike_threshold"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, float) or not v > 0:
                raise ValueError(f"{name} must be a positive float, got {v!r}")
        if isinstance(self.spike_n, bool) or not isinstance(self.spike_n, int) or self.spike_n < 2:
            raise ValueError(f"spike_n must be an int >= 2, got {self.spike_n!r}")

    def as_dict(self) -> dict[str, str]:
        return {"switch": str(self.switch), "overlay": self.overlay, "n": str(self.n),
                "ts_threshold": repr(self.ts_threshold),
                "spike_threshold": repr(self.spike_threshold), "spike_n": str(self.spike_n)}


def _check(params: object) -> SplitParams:
    if not isinstance(params, SplitParams):
        raise TypeError(f"params must be SplitParams, got {type(params).__name__}")
    return params


def overlay_allows(series: MarketSeries, data_date: date, p: SplitParams) -> bool:
    """True when the overlay lets the book stay invested. Delegates to M0039's recorded rule."""
    if p.overlay == "none":
        return True
    if p.overlay == "ts":
        return gate_on(series, data_date, GateParams("spy", "ts", p.ts_threshold))
    return gate_on(series, data_date, GateParams("spy", "spike", p.spike_threshold, p.spike_n))


@dataclass(frozen=True, slots=True, eq=False)
class SplitPrepared:
    history: Mapping[str, History]
    series: MarketSeries


class SplitAllocator:
    """SPY at full weight while the switch is on and the overlay allows it; otherwise cash."""

    id = "M0389"
    market_fields = ("series",)

    def lookback(self, params: Any) -> int:
        # The same for every arm, switch off included: a different warm-up would start the
        # overlay-alone arms on a different session and the 2x2 would no longer be paired.
        return _check(params).n

    def symbols(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return False

    def _run(self, prepared: SplitPrepared, data_date: date, held: frozenset[str],
             p: SplitParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:
            return ()  # market-aware contract: no panel, no target (every arm, not just the gated)
        h = prepared.history.get("SPY")
        if h is None:
            return ()
        state: bool | None = above_sma(h, data_date, p.n) if p.switch else (
            True if h.index_of(data_date) is not None else None)
        if state is None:  # no bar dated d: keep SPY only if it is already held, never a new entry
            if "SPY" not in held:
                return ()
            t = target_from_close("SPY", last_close(h, data_date), FULL_WEIGHT)
            return () if t is None else (t,)
        if not state or not overlay_allows(prepared.series, data_date, p):
            return ()
        t = target_from_close("SPY", last_close(h, data_date), FULL_WEIGHT)
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(SplitPrepared(history, EMPTY_SERIES), data_date, held, _check(params))

    def prepare(self, history: Mapping[str, History]) -> SplitPrepared:
        return SplitPrepared(history, EMPTY_SERIES)

    def prepare_market(self, market: Any) -> SplitPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        return SplitPrepared(market.history, series)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SplitPrepared):
            raise TypeError(f"prepared must be SplitPrepared, got {type(prepared).__name__}")
        return self._run(prepared, data_date, held, _check(params))


SPLIT = SplitAllocator()


def _v(suffix: str, params: SplitParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0389-{suffix}", family="M0389", rules=DAILY_HOLD_FRAC_GOTRADE,
                     allocator=SPLIT, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0389",
    name=("The never-step-aside arm as a standing control: the complete four-cell grid that "
          "splits what the 200-day switch costs from what an overlay on top of it costs"),
    family="market-trend-switch",
    source_kind="variation",
    source_ref="M0381",
    parent_id="M0381",
    hypothesis=(
        "The lab prices a timing overlay against the switch it sits on, and then quotes that "
        "difference as what the overlay costs. Those are the same number only if the two habits "
        "are additive, and the lab has never checked, because the fourth cell of the grid -- the "
        "overlay running with no switch under it, on the same chassis and in the same run -- has "
        "never been registered. This method registers the whole grid at once. Six arms, one "
        "allocator, one pre-registration, no counted look: ALWAYS (SPY held every session, no "
        "switch and no overlay, the standing control with no opinion in it), SWITCH (the SPY-200 "
        "rule alone), SPIKE and TS (each overlay alone on an always-invested book), and SPIKE-X "
        "and TS-X (each overlay on top of the switch, the pair the lab usually runs). Define a "
        "habit's bill as ALWAYS's de-funded annual return minus that arm's. The switch's own bill "
        "is then read off SWITCH, each overlay's own bill off its alone-arm, the pair's off its "
        "X-arm, and the interaction is the pair's bill minus the sum of the two singles. "
        "Hypothesis: the interaction is large and negative -- the two habits are strongly "
        "sub-additive, because a trend switch and a fear overlay sell into the same falls -- so "
        "the lab's standard attribution has been over-charging overlays by counting cash days the "
        "switch had already paid for. Success is a measured interaction term for both overlays "
        "with the whole grid recorded in one run, a statement of the rule (every timing method "
        "registers the always-invested arm, which costs a variant and never a method id), and a "
        "named list of recorded verdicts whose attribution moves once the switch's bill is taken "
        "out. The overlays are M0039's own rules at M0039's own recorded thresholds -- term "
        "structure at 1.00, spike at 1.20 over 63 sessions -- imported rather than re-specified, "
        "so nothing is fitted here. Assumed: cash earns nothing, a series row older than seven "
        "calendar days is no reading and never forces cash, the reading is taken from day d's "
        "close and traded at the next open, every arm warms up on the same 200 bars so the grid "
        "stays paired, and the comparison is de-funded so monthly deposits cannot refill a "
        "falling arm and flatter it. This method is a yardstick, not a candidate: ALWAYS is SPY "
        "minus Gotrade's fees and so cannot beat SPY by construction, and the lab's trend-switch "
        "family has never cleared the luck bar, so no arm is expected to be eligible. The "
        "deliverable is the decomposition, which is reusable by every timing method that follows."
    ),
    expected_failure=(
        "Measured on the dev store BEFORE this ran, and recorded here so nothing is fitted "
        "afterwards. Over the 5,522 sessions from 1993-11-12 to 2015-10-16 on which SPY has a bar "
        "and a 200-close average exists, the switch is off on 1,562 of them (28.3%), the spike "
        "overlay calls for cash on 627 (11.4%) and the term-structure overlay on 352 (6.4%). The "
        "overlap is the whole story: 357 of the spike's 627 cash days (56.9%) are days the switch "
        "was already out, and 249 of the term structure's 352 (70.7%). So on top of the switch "
        "each overlay only adds 270 and 103 new cash days respectively -- 43% and 29% of what it "
        "costs standing alone. If a bill were simply proportional to days out, the interaction "
        "would be about minus half the spike's own bill and minus seven tenths of the term "
        "structure's, and the lab's usual overlay-versus-switch difference would be understating "
        "the overlay's standalone cost by roughly those fractions. The most likely way this "
        "method fails is that the bills turn out not to be proportional to days out at all, "
        "because the days the two habits do NOT share are the expensive ones: an overlay's "
        "non-overlapping days are scares inside rallies, which are exactly the days with the "
        "largest rebounds, so an overlay could easily cost MORE on top of the switch than it does "
        "alone and the interaction could come out positive. Either sign is a result; a near-zero "
        "interaction would be the one outcome that vindicates the lab's current practice, and it "
        "is the outcome I think least likely. The second way it fails is coverage: the term "
        "structure cannot be read before 2006-07-17, so TS and TS-X are ALWAYS and SWITCH trade "
        "for trade over the window's first thirteen years and their whole-window bills are "
        "diluted by about half; only the spike cell carries both bear markets, and the whole-"
        "window interaction for the term structure should be read as a 2006-2015 number wearing "
        "a twenty-three-year coat. The third way is that the grid answers a bookkeeping question "
        "and no arm earns anything: ALWAYS should post the highest return and by far the deepest "
        "fall, holding through 2000-2002 and 2008, and should still lose to total-return SPY "
        "because it pays Gotrade's fees to hold the same thing; SWITCH should post a much "
        "shallower fall and a materially lower return; the four overlay arms should all sit below "
        "SWITCH, repeating M0039 and M0381. No arm is expected to clear the drawdown bar, the "
        "profit-factor bar and the luck bar together, and if one does it will be ALWAYS, which is "
        "a buy-and-hold index book and not a strategy -- it must not be promoted on that ground."
    ),
    candidates=(
        _v("ALWAYS", SplitParams(False, "none"),
           "The standing control: SPY held every session, no opinion, the zero of both bills."),
        _v("SWITCH", SplitParams(True, "none"),
           "The 200-day switch alone: its own bill, with no overlay mixed into it."),
        _v("SPIKE", SplitParams(False, "spike"),
           "M0039's fear-spike rule alone on an always-invested book: the overlay's own bill."),
        _v("SPIKE-X", SplitParams(True, "spike"),
           "The pair the lab usually runs: spike overlay on top of the switch."),
        _v("TS", SplitParams(False, "ts"),
           "M0039's term-structure rule alone on an always-invested book: the overlay's own bill."),
        _v("TS-X", SplitParams(True, "ts"),
           "The pair the lab usually runs: term-structure overlay on top of the switch."),
    ),
    seen_keys=(
        "concept:standing-always-invested-control-for-every-timing-method",
        "concept:two-by-two-switch-overlay-cost-decomposition",
        "concept:interaction-term-between-two-step-aside-habits",
        "data:vix3m-from-2006-07-17-vix-from-1993-in-the-dev-store",
    ),
)
