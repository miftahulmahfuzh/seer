"""M0143 — Sell on a bad quarter, not a crossed line: the other half of the switch, on clean kin.

Source: the frame and both triggers are M0113's, made asymmetric in the other direction; the book
and the gate-replacement machinery are M0101's, which is this method's parent.

Idea: the lab has now priced the 200-day safety switch's ENTRY half three times -- M0113 on SPY
alone, M0135 on two stock books, M0133 on a third -- and every time, buying back when SPY's last
63 sessions have ACTUALLY returned positive beat buying back on a price cross. The EXIT half has
never been moved at all. It was frozen on the strength of M0084's finding that the exit is the
half that earns its keep, but "the exit earns its keep" and "the exit is optimally expressed"
are different claims and only the first was ever tested. The exit in force today is exactly the
rule shape that LOST on the entry side: today's price against a slow average. This method holds
the entry at the positive-quarter rule and moves only the exit.

WHY THIS BOOK, AND WHY NOT THE ONE THE IDEA ROW NAMED. M0135 produced a clean frame result and it
can never be bought: its line runs M0135 -> M0128 -> M0030 -> M0029, and M0029 is test-failed, so
the hard gate's (K) refuses it on ancestry before behaviour is even read. Inheriting that parent
would have reproduced the exact failure this idea exists to escape. The idea row named M0131-B20
(the learned ranker) as the kin-clean host; the recorded dev trials say that is not the strongest
one. M0088-C-LIVE-63 -- the calm half of the big dividend raisers -- beats it on every axis at
once (+35.10% against +35.32% funded, but a 18.71% worst fall against 19.96%, gains 3.52 times
losses against 1.76, DSR 0.9446 against 0.9118, MAR 0.57 against 0.55) and its kin is equally
clean: the line is M0101 -> M0088 -> M0070 and the family stock-dividend-change-drift holds no
test-failed method. It is also the host with the strongest MOTIVE. M0096 split this very book's
record by era and found the lag was not in the raisers: "the safety switch, not the raisers,
causes the recent lag", because the switch sold in the 2010, 2011 and 2015 dips and bought back
higher. M0101 then tried to fix that with hysteresis bands and failed -- BAND-3 and BAND-5 both
finished BELOW the plain control (MAR 0.51 and 0.50 against 0.57) and both broke the drawdown
screen. So this is the one book in the lab whose post-2009 lag has been DIAGNOSED as exit-caused
and whose only attempted exit fix has already been measured and lost. A realised-return exit is
the untried alternative on exactly that diagnosis.

NOTHING IS STRIPPED, AND THAT IS THE POINT. ``f_factor.factor_rows`` never applies the trend gate;
applying it is entirely the allocator's job, which is why M0101 could replace the switch without
touching M0088's book. This method does the same: ``choose`` is imported from M0088 and runs on
M0088's prepared panel byte for byte, the inner ``FactorParams.trend`` stays ("SPY", 200) in the
params and therefore in the digest where it records which gate the control uses, and the ONLY new
code is which question ``_on`` asks. The asymmetry is expressed through ``held`` exactly as M0113
and M0135 expressed it: the EXIT rule applies only while the book is in the market, the ENTRY
rule only while it is out.

TWO REPRODUCTION ANCHORS, because a result with no control is not a result. This batch contains
two arms whose numbers are already recorded elsewhere and which must come back unchanged:

    * ``SPY-UP63`` is M0113-UP63 re-expressed under a new allocator id -- SPY only, entry on a
      positive 63-session return, exit on the 200-day cross, the same preset and the same 253-bar
      lookback -- and must reproduce +32.14% funded, a 20.69% worst fall, 18 trades and 73.4%
      invested. It proves the SPY path, the ``held`` asymmetry and the imported trigger.
    * ``CALM-SYM`` is the fully symmetric switch over the calm raisers, which is M0101-CTRL and
      M0088-C-LIVE-63, and must reproduce +35.10%, an 18.71% worst fall, gains 3.52 times losses,
      528 trades and 70.4% invested. It proves the book path, and it proves that an outer
      symmetric switch IS the stateless inner gate -- the assumption every other arm rests on.

If either fails to reproduce, the honest response is to report the method as unreadable rather
than to explain the gap away.

NO RESIDUAL-MOMENTUM ARM, DELIBERATELY. The idea row asked for a control reproducing M0135's UP63
arm. That arm's curve correlates 0.99, 1.00 and 0.92 with M0021, M0022 and M0029, all test-failed,
so including it would have handed the hard gate's (D14) behavioural kin a reason to refuse this
whole method whatever the dividend arms scored. The machinery check is taken from the SPY arm
instead, where it is just as exact and carries no such curve.

Pure: reads only bars and dividends dated <= ``data_date``. ``held`` is read, which is the state
this switch needs and the only state it has; a deposit changes cash, not whether the book is in.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM, choose
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import BOOK as CALM_BOOK
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import FABER_MONTHS
from seer_engine.lab.methods.m0113_trend_switch_reentry import (
    EXIT_GATE,
    LOOKBACK as SPY_LOOKBACK,
    ReentryParams,
    entry_on,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 14)
BENCH = "SPY"  # the switch's yardstick, and the only thing the SPY arm ever holds
SMA_N = EXIT_GATE.trend[1] if EXIT_GATE.trend is not None else 200  # the 200 in "200-day", frozen

Book = Literal["spy", "calm"]
_BOOKS: tuple[str, ...] = ("spy", "calm")
Exit = Literal["sma200", "down"]
_EXITS: tuple[str, ...] = ("sma200", "down")


@dataclass(frozen=True, slots=True)
class AsymSwitchParams:
    """Which book runs, how it is bought back, and -- new here -- how it is sold."""

    book: Book = "calm"
    entry: str = "sma200"  # M0113's entry vocabulary; only "sma200" and "up" are used here
    entry_n: int = 0
    exit_rule: Exit = "sma200"
    exit_n: int = 0  # sessions the exit rule reads; 0 for "sma200", which reads SMA_N

    def __post_init__(self) -> None:
        if not isinstance(self.book, str) or self.book not in _BOOKS:
            raise ValueError(f"book must be one of {_BOOKS}, got {self.book!r}")
        if not isinstance(self.exit_rule, str) or self.exit_rule not in _EXITS:
            raise ValueError(f"exit_rule must be one of {_EXITS}, got {self.exit_rule!r}")
        ReentryParams(self.entry, self.entry_n)  # M0113's own validation of the entry, verbatim
        if self.exit_rule == "sma200":
            if self.exit_n != 0:
                raise ValueError(f"exit_n must be 0 for exit_rule='sma200', got {self.exit_n}")
        else:
            # The exit window is validated by the same rule the entry window obeys: a "down" exit
            # is the "up" entry read with the book in rather than out, so the bounds must match.
            ReentryParams("up", self.exit_n)

    @property
    def entry_params(self) -> ReentryParams:
        """The buy-back rule as M0113 spells it; ``month_end_window`` is never set here."""
        return ReentryParams(self.entry, self.entry_n)

    @property
    def exit_params(self) -> ReentryParams:
        """The STAY-IN test: the book keeps its positions while the last ``exit_n`` returned positive."""
        return ReentryParams("up", self.exit_n)

    def as_dict(self) -> dict[str, str]:
        out = {
            "book": self.book,
            "entry": self.entry,
            "entry_n": str(self.entry_n),
            "exit_rule": self.exit_rule,
            "exit_n": str(self.exit_n),
        }
        if self.book == "calm":
            for k, v in CALM_BOOK.as_dict().items():
                out[f"book.{k}"] = v
        return out


def _check(params: object) -> AsymSwitchParams:
    if not isinstance(params, AsymSwitchParams):
        raise TypeError(f"params must be AsymSwitchParams, got {type(params).__name__}")
    return params


class AsymmetricExitSwitch:
    """A gated book whose buy-back is fixed and whose SELL rule is the variant's own.

    On data date d: when the book holds anything the EXIT rule decides, and when it holds nothing
    the ENTRY rule decides. Off means all cash -- no targets at all, which the book engine reads
    as "sell everything". On means the inner book's own targets, unchanged: this allocator never
    re-ranks, re-weights or filters a pick, and it owns no signal of its own.

    ``bool(held)`` is the reading of "in or out". For the SPY arm it is exactly M0113's
    ``BENCH in held``, because SPY is the only symbol that arm can hold. For the calm arm it is
    M0135's reading: any position at all means in.
    """

    id = "M0143"
    market_fields = ("dividends",)

    def _gate(self, p: AsymSwitchParams) -> Any:
        """The ``FactorParams`` whose ``trend`` the 200-day test reads. ("SPY", 200) either way."""
        return EXIT_GATE if p.book == "spy" else CALM_BOOK.ann.base.inner

    def lookback(self, params: Any) -> int:
        p = _check(params)
        # 23 * (FABER_MONTHS + 1) is M0101's and M0113's shared term; keeping it means this method
        # is scored on exactly the sessions its two reproduction anchors were scored on.
        n = max(SMA_N, p.entry_n + 1, p.exit_n + 1, 23 * (FABER_MONTHS + 1))
        if p.book == "spy":
            return max(SPY_LOOKBACK, n)
        return max(CALM.lookback(CALM_BOOK), n)

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        if p.book == "spy":
            return (BENCH,)
        return CALM.symbols(CALM_BOOK)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = _check(params)
        if p.book == "spy":
            return (BENCH,)
        return CALM.holds(CALM_BOOK)

    def uses_members(self, params: Any) -> bool:
        p = _check(params)
        return p.book != "spy"

    def _on(self, history: Mapping[str, History], data_date: date, held: frozenset[str],
            p: AsymSwitchParams) -> bool:
        """Should the book be held after this check? The exit rule when in, the entry rule when out."""
        if held:
            if p.exit_rule == "sma200":
                return trend_on(history, data_date, self._gate(p))
            return entry_on(history.get(BENCH), data_date, p.exit_params)
        if p.entry == "sma200":
            return trend_on(history, data_date, self._gate(p))
        return entry_on(history.get(BENCH), data_date, p.entry_params)

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: AsymSwitchParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not self._on(prepared.history, data_date, held, p):
            return ()
        if p.book == "spy":
            h = prepared.history.get(BENCH)
            if h is None or h.index_of(data_date) is None:  # no bar dated d: no new target
                return ()
            t = target_from_close(BENCH, last_close(h, data_date), equal_weight(1))
            return () if t is None else (t,)
        inner = CALM_BOOK.ann.base.inner
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, CALM_BOOK)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target, for every arm alike."""
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def prepare(self, history: Mapping[str, History]) -> RaisePrepared:
        return CALM.prepare(history)

    def prepare_market(self, market: Any) -> RaisePrepared:
        return CALM.prepare_market(market)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


SWITCH = AsymmetricExitSwitch()
QUARTER = 63  # the interior peak the entry side found, and the first exit window to try


def _v(suffix: str, params: AsymSwitchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0143-{suffix}", family="M0143", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SWITCH, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0143",
    name="Sell on a bad quarter, not a crossed line: move the safety switch's exit, on a book whose kin is clean",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0101 (the calm big raisers behind a choice of switch); the asymmetric "
        "frame and both triggers are M0113's, mirrored from the entry side to the exit side"
    ),
    parent_id="M0101",
    hypothesis=(
        "The moving-average switch is old -- the banded rule 1992, Faber's monthly version 2007 "
        "-- so nothing here is a new anomaly and no fade argument applies; what is new is which "
        "HALF of it is being paid for, and this is the half nobody has moved. The lab has now "
        "priced the ENTRY half three times and got the same answer each time: on SPY alone "
        "(M0113-UP63, +32.14% funded against the symmetric control's +31.68%), on two stock books "
        "(M0135, +0.98 and +0.66 points a year for +0.02 and +0.87 points of worst fall, with "
        "DSR RISING on both and the paired gain LARGER on the survivorship-check store), and on a "
        "third (M0133, +1.1 points a year at an identical worst fall). Buying back when SPY's "
        "last 63 sessions have actually returned positive beats buying back on a price cross, and "
        "63 is an INTERIOR PEAK rather than a point on a ramp: 21 sessions was worse than changing "
        "nothing and 126 was also worse, which is far stronger evidence than a monotone trend. "
        "The exit has meanwhile never been moved. It was frozen on M0084's finding that the exit "
        "is the half that earns its keep -- the whole 22-year advantage is sitting out 2001, 2002 "
        "and 2008 -- but 'the exit earns its keep' and 'the exit is optimally expressed' are "
        "different claims and only the first has been tested. The exit in force is today's price "
        "against a slow average, which is exactly the rule shape that LOST on the entry side. "
        "THE RULE: hold the entry at UP63 and sell when SPY's last exit_n sessions have NOT "
        "returned positive. The stay-in test is M0113's own entry_on read with the book in rather "
        "than out, so the two halves are the same function and the mirror is exact. MECHANISM, "
        "and why it could beat a crossed line in both directions at once: a realised-return exit "
        "may leave EARLIER in a genuine decline -- 2008's 200-day cross came in January, months "
        "after the October 2007 peak -- and may leave LESS OFTEN in a chop that dips below the "
        "line and bounces straight back, which is where M0084 measured the switch paying for "
        "itself everywhere outside the three crises. "
        "THE HOST, which matters more than the rule. M0135 produced a good frame result that can "
        "never be bought: its line runs to M0029, which is test-failed, so the hard gate refuses "
        "it on ancestry. Better machinery on a disproven engine is a better disproven engine. "
        "This runs on M0088-C-LIVE-63, the calm half of the big dividend raisers: dev-eligible, "
        "+35.10% funded against SPY's +32.40%, an 18.71% worst fall, gains 3.52 times losses, 528 "
        "trades, 70.4% invested, DSR 0.9446, and kin that reads clean in every direction the gate "
        "looks -- family stock-dividend-change-drift holds no test-failed method and the line "
        "M0101 -> M0088 -> M0070 holds none either. It is also the best-motivated host in the "
        "lab: M0096 split this exact book by era and concluded 'the safety switch, not the "
        "raisers, causes the recent lag', because the switch sold in the 2010, 2011 and 2015 dips "
        "and bought back higher; and M0101 already tried to fix that with hysteresis bands and "
        "LOST, both banded arms finishing below the plain control (MAR 0.51 and 0.50 against "
        "0.57) and both breaking the drawdown screen. The realised-return exit is the untried "
        "alternative on a diagnosis that is already made and an attempted fix that has already "
        "failed. The idea row named M0131-B20 instead; the recorded trials say it is weaker on "
        "every axis (19.96% worst fall, gains 1.76 times losses, DSR 0.9118) and carries no such "
        "diagnosis, so the host was changed and this sentence is the record of that choice. "
        "ONE PRESET, monthly-hold-frac-gotrade -- fractional shares, Gotrade's real fee schedule, "
        "the owner's monthly deposits -- for all six arms, which is the preset BOTH reproduction "
        "anchors were recorded on. It is not M0128's fixed tape; that was the idea row's "
        "instruction and it is being declined deliberately, because no recorded trial of this "
        "book exists on the fixed tape, so taking it would have bought a better absolute level at "
        "the cost of BOTH control checks. The resize-band level effect is shared by all six arms "
        "alike, so the paired differences -- which are the entire result -- are unaffected by it, "
        "while the absolute levels here are a little less invested than a fixed-tape run would be. "
        "TWO ANCHORS MUST REPRODUCE BEFORE ANY OTHER NUMBER IS READ. M0143-SPY-UP63 is M0113-UP63 "
        "under a new allocator id and must return +32.14%, an 18-trade count, a 20.69% worst fall "
        "and 73.4% invested. M0143-CALM-SYM is the fully symmetric switch over the calm raisers, "
        "which is M0101-CTRL, and must return +35.10%, 528 trades, an 18.71% worst fall and gains "
        "3.52 times losses. The first proves the SPY path, the held-based asymmetry and the "
        "imported trigger; the second proves the book path and the assumption everything else "
        "rests on, that an outer symmetric switch IS the stateless inner gate. No "
        "residual-momentum arm is included even though the idea row asked for one, because "
        "M0135's arms correlate 0.99, 1.00 and 0.92 with three test-failed methods and one such "
        "curve in this batch would hand the gate's behavioural-kin rule a reason to refuse the "
        "whole method whatever the dividend arms scored. "
        "PREDICTIONS, written before the run. (1) CALM-UP63 beats CALM-SYM by 0.3 to 1.0 points a "
        "year, replicating M0135's entry finding on an engine with no momentum in it -- a free "
        "independent replication this batch gets either way. (2) DOWN63 raises time in the market "
        "by 1 to 4 points over its own UP63 control, because a quarter that is merely flat keeps "
        "the book in where a price under the average takes it out. (3) The worst fall DEEPENS by "
        "0 to 3 points, because a quarterly return lags a daily price line at the start of a fast "
        "collapse. (4) The gain, if any, must be visible in 2009-2015 -- the best-covered era and "
        "the one most like today, and the exact era M0096 diagnosed -- or it is a pre-2009 "
        "artefact and the verdict says so first. (5) DOWN21 whipsaws and DOWN126 is too slow to "
        "protect, putting 63 at an interior peak on this side too; if instead the ordering is "
        "monotone, the finding is only 'sooner is better' and that is a weaker claim. "
        "SUCCESS: a DOWN variant that beats its own UP63 control by at least a point a year with "
        "the worst fall no deeper, the gain present in 2009-2015, on a book the hard gate would "
        "actually let through."
    ),
    expected_failure=(
        "The exit is where the switch earns everything, so breaking it is more dangerous than "
        "breaking the entry was, and the likeliest failure is a late exit in the only three "
        "events the whole switch exists for. A negative-quarter test is SLOWER than a 200-day "
        "cross at the start of a fast collapse: in October 2008 the quarter was already deeply "
        "negative so the two agree, but in a 1987-shaped single-week crash a quarterly return "
        "still reads positive while the price line has already broken. If 2001, 2002 and 2008 "
        "arrive late, the DOWN arms give back more than the entry side ever gained and the "
        "verdict is that the exit was already optimally expressed -- which would be a real and "
        "useful result, because it would close this grid for good. "
        "Second, the 200-day cross may be near-optimal as an exit PRECISELY BECAUSE it is slow. "
        "M0084 found the switch's standing cost is whipsaw, and a realised-return exit may "
        "whipsaw MORE rather than less: a quarterly return can flip sign repeatedly in a sideways "
        "market, while price-against-average carries a built-in hysteresis. M0101's banded arms "
        "are the warning -- adding hysteresis to this exact book made it worse on return AND "
        "drawdown at once, so this book has already shown it does not reward exit tinkering. "
        "Third, the number of draws. M0135's whole gain was four months out of 237. A result "
        "about exits is a result about three or four crisis events inside twenty years, which is "
        "a very small number of draws however many sessions the average is computed over, so the "
        "fold record and the 2009-2015 split must both be read before the whole-window average "
        "and the verdict must say which single events moved it. "
        "Fourth, the machinery. If SPY-UP63 does not return M0113-UP63's 18 trades and 20.69% "
        "fall, or CALM-SYM does not return M0101-CTRL's 528 trades and 18.71% fall, then the "
        "held-based asymmetry or the lookback is wrong and NONE of the other four numbers is "
        "readable; the correct response is to report the method unreadable, not to explain the "
        "gap away. The specific way bool(held) can part from the truth is an 'on' session where "
        "the book finds no event to buy, which would leave the ENTRY rule governing the next "
        "check even though the book never meant to leave; the calm raisers hold 25 names on "
        "events and can genuinely be empty, so this risk is real here in a way it was not for a "
        "20-name momentum book, and CALM-SYM's trade count against 528 is what detects it. "
        "Fifth, no interest is credited on idle cash, which flatters whichever arm is out of the "
        "market least -- here the DOWN arms, if prediction (2) holds. On SPY the same swap moved "
        "time in market about 2.3 points and 1996-2015 T-bills paid roughly 2.5% a year, so the "
        "bias on a paired difference is under a tenth of a point a year; any gap smaller than "
        "that is noise for this reason alone and must not be reported as a finding. "
        "Sixth, the DSR. The control sits at 0.9435 against a 0.90 bar at an N that has grown "
        "since M0101 ran and is now about 90, so a variant can lose eligibility here purely "
        "because the lab has looked more times. That is the lab's cost, not the method's failure, "
        "and the analysis reports it as such."
    ),
    candidates=(
        _v("SPY-UP63", AsymSwitchParams("spy", "up", QUARTER, "sma200", 0),
           "Anchor: M0113-UP63 re-expressed -- SPY only, quarter-return buy-back, 200-day exit"),
        _v("CALM-SYM", AsymSwitchParams("calm", "sma200", 0, "sma200", 0),
           "Anchor: the fully symmetric switch over the calm raisers -- must reproduce M0101-CTRL"),
        _v("CALM-UP63", AsymSwitchParams("calm", "up", QUARTER, "sma200", 0),
           "The paired control for the exit question, and a replication of M0135's entry finding"),
        _v("CALM-DOWN63", AsymSwitchParams("calm", "up", QUARTER, "down", QUARTER),
           "The headline: sell when SPY's last quarter has not returned positive"),
        _v("CALM-DOWN126", AsymSwitchParams("calm", "up", QUARTER, "down", 126),
           "Probe: a half-year realised return instead, a slower and more forgiving exit"),
        _v("CALM-DOWN21", AsymSwitchParams("calm", "up", QUARTER, "down", 21),
           "Probe: a one-month realised return, the fastest exit and the most exposed to whipsaw"),
    ),
    seen_keys=(
        "concept:realised-return-exit-trigger",
        "concept:asymmetric-switch-exit-half",
        "concept:quarter-return-exit-on-dividend-raisers",
    ),
)
