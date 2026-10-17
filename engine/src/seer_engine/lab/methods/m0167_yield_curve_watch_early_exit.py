"""M0167 — The yield-curve watch with an early way out: buy back once the market proves it is not falling.

Source: variation of M0038 (the two-year yield-curve watch), reserved as an idea row by Sera
20261017-1530.

M0038 sat in cash for two years after the 10-year minus 13-week curve last inverted. On dev it
dodged 2000-2002 and 2007-2009 almost whole, but it missed the 2009 rebound, it made two calls in
twenty years, and public bond-market history says its third call (the 2022-2024 inversion, the
longest on record) brought no bear market and would have kept it in cash through a long rally.
This method keeps the watch and adds a way out: once the watch has been open long enough
(``min_days``, a year), the first session on which the market proves it is not in a bear market
closes the watch early. The watch then stays closed until the curve inverts again.

Two ways to count the year (``anchor``):

    * ``"start"``: from the first inverted day of the episode, as the idea row was written.
    * ``"last"``: from the most recent inverted day. An inversion that drags on keeps the watch
      fully armed for a year after it ends; this is the reading of the literature's 6-18 month
      lead, which runs from the inversion, not from its first day.

Two kinds of proof (``exit``):

    * ``"sma200"``: SPY closes above its 200-day average (strict, as every lab trend gate).
    * ``"high252"``: SPY closes at its highest close of the last 252 sessions. A bear-market rally
      can lift SPY over a falling 200-day average; it rarely makes a new one-year high.

An episode is a run of inverted days with gaps under ``watch_days``, broken also by an early exit:
an inversion after an exit opens a new episode. The watch on ``data_date`` d is open when the last
inverted day dated <= d is less than ``watch_days`` calendar days before d **and** no exit session
lies between the episode's anchor + ``min_days`` (and after its last inverted day) and d. Exit
flags are precomputed per SPY session from bars dated on or before that session, and only flags
dated <= d are read, so the decision reads nothing after d. A spread reading still needs both
yields dated the same day (``inverted_dates`` from M0038).

Watch open -> no targets (cash, earning nothing, as M0038). Watch closed -> the host's targets.
Hosts as M0038: SPY decided every session (evidence only: a handful of trades can never clear the
100-trade bar) and M0076-X-M's big-dividend-raise book with its own SPY-200 switch removed.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0038_yield_curve_watch_gate import DIV_OPEN, inverted_dates
from seer_engine.lab.methods.m0039_vix_term_structure_gate import DAILY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import ANNOUNCED, AnnParams
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close

ADDED = date(2026, 10, 17)

SMA_N = 200
HIGH_N = 252

Host = Literal["spy", "div"]
Short = Literal["T13W", "T5Y"]
Anchor = Literal["start", "last"]
Exit = Literal["sma200", "high252"]


@dataclass(frozen=True, slots=True)
class EarlyParams:
    """Cash while the curve watch is open; the watch closes early on an exit session after ``min_days``."""

    host: Host
    anchor: Anchor
    exit: Exit
    short: Short = "T13W"
    watch_days: int = 730  # M0038's two years, unchanged
    min_days: int = 365  # the year the watch stays fully armed before an exit may close it
    div: AnnParams = DIV_OPEN

    def __post_init__(self) -> None:
        if self.host not in ("spy", "div"):
            raise ValueError(f"host must be 'spy' or 'div', got {self.host!r}")
        if self.anchor not in ("start", "last"):
            raise ValueError(f"anchor must be 'start' or 'last', got {self.anchor!r}")
        if self.exit not in ("sma200", "high252"):
            raise ValueError(f"exit must be 'sma200' or 'high252', got {self.exit!r}")
        if self.short not in ("T13W", "T5Y"):
            raise ValueError(f"short must be 'T13W' or 'T5Y', got {self.short!r}")
        for name in ("watch_days", "min_days"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be an int >= 1, got {v!r}")
        if not isinstance(self.div, AnnParams):
            raise TypeError(f"div must be AnnParams, got {type(self.div).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"host": self.host, "anchor": self.anchor, "exit": self.exit, "short": self.short,
               "watch_days": str(self.watch_days), "min_days": str(self.min_days)}
        for k, v in self.div.as_dict().items():
            out[f"div.{k}"] = v
        return out


@dataclass(frozen=True, slots=True, eq=False)
class ExitFlags:
    """Per SPY session: did the close prove an exit? Each flag reads only bars dated <= its session."""

    dates: tuple[date, ...]
    flags: Mapping[str, np.ndarray]  # exit kind -> bool array aligned with dates

    def any_between(self, exit: str, lo: date, hi: date) -> bool:
        if lo > hi:
            return False
        a = bisect_right(self.dates, lo - timedelta(days=1))
        b = bisect_right(self.dates, hi)
        return a < b and bool(self.flags[exit][a:b].any())


NO_FLAGS = ExitFlags((), {"sma200": np.zeros(0, bool), "high252": np.zeros(0, bool)})


def exit_flags(close: np.ndarray, dates: tuple[date, ...]) -> ExitFlags:
    """SPY above its 200-day average (strict) and at its 252-session closing high, per session."""
    n = close.shape[0]
    above = np.zeros(n, bool)
    high = np.zeros(n, bool)
    if n >= SMA_N:
        csum = np.concatenate(([0.0], np.cumsum(close)))
        sma = (csum[SMA_N:] - csum[:-SMA_N]) / SMA_N  # sma[j] averages close[j .. j+SMA_N-1]
        above[SMA_N - 1:] = close[SMA_N - 1:] > sma
    if n >= HIGH_N:
        win = np.lib.stride_tricks.sliding_window_view(close, HIGH_N).max(axis=1)
        high[HIGH_N - 1:] = close[HIGH_N - 1:] >= win
    finite = np.isfinite(close)
    return ExitFlags(dates, {"sma200": above & finite, "high252": high & finite})


def watch_open(inverted: tuple[date, ...], flags: ExitFlags, data_date: date, p: EarlyParams) -> bool:
    """True when the curve watch is open on ``data_date``, reading nothing dated after it."""
    i = bisect_right(inverted, data_date)
    if i == 0:
        return False
    window = timedelta(days=p.watch_days)
    armed = timedelta(days=p.min_days)
    one = timedelta(days=1)

    def exited(start: date, last: date, end: date) -> bool:
        anchor = start if p.anchor == "start" else last
        return flags.any_between(p.exit, max(anchor + armed, last + one), end)

    start = prev = inverted[0]
    for v in inverted[1:i]:
        if v - prev >= window or exited(start, prev, v - one):
            start = v
        prev = v
    if data_date - prev >= window:
        return False
    return not exited(start, prev, data_date)


@dataclass(frozen=True, slots=True, eq=False)
class EarlyPrepared:
    history: Mapping[str, Any]
    inverted: Mapping[str, tuple[date, ...]]  # short leg -> inverted dates; empty without series
    flags: ExitFlags
    host: Any  # the div host's prepared value; None for the spy host


class EarlyExitAllocator:
    """The host's targets while the curve watch is closed; nothing (cash) while it is open."""

    def __init__(self, id: str, host: Host, market_fields: tuple[str, ...]) -> None:
        self.id = id
        self._host = host
        self.market_fields = market_fields

    def _p(self, params: object) -> EarlyParams:
        if not isinstance(params, EarlyParams):
            raise TypeError(f"params must be EarlyParams, got {type(params).__name__}")
        if params.host != self._host:
            raise ValueError(f"{self.id} gates host {self._host!r}, got params for {params.host!r}")
        return params

    def lookback(self, params: Any) -> int:
        p = self._p(params)
        own = HIGH_N + 1
        return max(own, ANNOUNCED.lookback(p.div)) if p.host == "div" else own

    def symbols(self, params: Any) -> tuple[str, ...]:
        p = self._p(params)
        return tuple(sorted({"SPY", *ANNOUNCED.symbols(p.div)})) if p.host == "div" else ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        p = self._p(params)
        return ANNOUNCED.holds(p.div) if p.host == "div" else ("SPY",)

    def uses_members(self, params: Any) -> bool:
        return self._p(params).host == "div"

    def _run(self, prepared: EarlyPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: EarlyParams) -> tuple[Target, ...]:
        if not prepared.inverted:  # no series: target nothing (market-aware contract)
            return ()
        if watch_open(prepared.inverted.get(p.short, ()), prepared.flags, data_date, p):
            return ()
        if p.host == "div":
            return ANNOUNCED.targets_prepared(prepared.host, members, data_date, held, p.div)
        h = prepared.history.get("SPY")
        if h is None or (h.index_of(data_date) is None and "SPY" not in held):
            return ()  # a symbol with no bar dated d is never a NEW target
        t = target_from_close("SPY", last_close(h, data_date), equal_weight(1))
        return () if t is None else (t,)

    def targets(self, history: Mapping[str, Any], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no series, so no gate reading and no target."""
        p = self._p(params)
        return self._run(EarlyPrepared(history, {}, NO_FLAGS, None), members, data_date, held, p)

    def prepare(self, history: Mapping[str, Any]) -> EarlyPrepared:
        host = ANNOUNCED.prepare(history) if self._host == "div" else None
        return EarlyPrepared(history, {}, NO_FLAGS, host)

    def prepare_market(self, market: Any) -> EarlyPrepared:
        series = getattr(market, "series", EMPTY_SERIES)
        if not isinstance(series, MarketSeries):
            raise TypeError(f"market.series must be a MarketSeries, got {type(series).__name__}")
        inverted = {} if len(series) == 0 else {s: inverted_dates(series, s) for s in ("T13W", "T5Y")}
        spy = market.history.get("SPY")
        flags = NO_FLAGS if spy is None else exit_flags(
            spy.close, tuple(d.item() for d in spy.dates))
        host = ANNOUNCED.prepare_market(market) if self._host == "div" else None
        return EarlyPrepared(market.history, inverted, flags, host)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, EarlyPrepared):
            raise TypeError(f"prepared must be EarlyPrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, self._p(params))


SPY_EARLY = EarlyExitAllocator("M0167", "spy", ("series",))
DIV_EARLY = EarlyExitAllocator("M0167-DIV", "div", ("dividends", "series"))


def _v(suffix: str, allocator: Any, params: Any, rationale: str, rules: Any) -> Candidate:
    return Candidate(id=f"M0167-{suffix}", family="M0167", rules=rules, allocator=allocator,
                     params=params, rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0167",
    name="The yield-curve watch with an early way out: buy back once the market proves it is not falling",
    family="macro-regime-gate",
    source_kind="variation",
    source_ref="variation of M0038",
    parent_id="M0038",
    hypothesis=(
        "M0038's two-year watch after a 10-year/13-week curve inversion (Estrella-Mishkin 1996, "
        "public through the whole dev window) dodged 2000-2002 and 2007-2009 but missed the 2009 "
        "rebound, and by public bond-market history its next call (the 2022-2024 inversion) brought "
        "no bear market and would have kept it in cash through a long rally. Keep the watch and "
        "add a way out: once it has been open min_days (365), the first session on which SPY "
        "proves it is not in a bear market closes the watch early; it stays closed until the curve "
        "inverts again. Two counts of the year: from the episode's first inverted day (START, the "
        "idea row as written) or from its most recent inverted day (LAST, the literature's lead "
        "runs from the inversion). Two proofs: SPY above its 200-day average (E200) or SPY at a "
        "252-session closing high (EHIGH; a bear-market rally can clear a falling 200-day average "
        "but rarely makes a one-year high). Hosts as M0038: SPY, decided daily (evidence only, it "
        "cannot reach 100 trades) and M0076-X-M's big-dividend-raise book without its own SPY-200 "
        "switch, monthly picks, weekly resize, fractional at Gotrade's real fees on the owner's "
        "monthly deposits. Variants: SPY-E200S and DIV-E200S (the row as written), DIV-E200L, "
        "DIV-EHIGHL, DIV-EHIGHL-5Y (the same on the 10-year/5-year curve, which in the dev window "
        "also inverted in 1998, a warning no bear market followed, so it is the only dev-visible "
        "false alarm the exit can be judged on) and SPY-EHIGHL. Equal-weight S&P as a second "
        "yardstick is not run: RSP starts in 2003 and the lab has no such benchmark switch "
        "(assumed). Success: the chosen variant is still flat or better through 2000-2002 and "
        "2007-2009, beats total-return SPY on the owner's money within the worst-fall limit, wins a "
        "majority of walk-forward folds as the variant picked, and is no worse than SPY in "
        "2009-2015; EHIGHL-5Y beats M0038-DIV-2KEY-5Y by re-entering after the 1998 false alarm."
    ),
    expected_failure=(
        "On the 13-week curve the exit can only lose on dev: the two warnings it holds were both "
        "followed by bear markets, so there is no false alarm to rescue. The START count is the "
        "riskiest: the 2006-07 watch opened in mid-2006, so a year later (summer-autumn 2007) SPY "
        "was still near its highs and above its 200-day average; START would buy back right before "
        "2008 and lose the gate's biggest save, and in early 2002 a rally over the 200-day average "
        "could do the same before the 2002 leg down. LAST pushes the earliest exit to early 2002 "
        "and mid-2008, where the 200-day proof may still fire on a bear-market rally (spring 2008 "
        "came close), while the one-year-high proof should not fire before the watch ends anyway, "
        "so DIV-EHIGHL is likely nearly identical to M0038-DIV-WATCH on dev and adds no evidence "
        "on the 13-week curve: its value is only out of sample. The 2009 rebound stays missed: the "
        "watch ended in May 2009 and SPY did not clear its 200-day average until about then, so "
        "the exit cannot buy March-May 2009. If the variants differ in which era they win, the "
        "fold pick changes and the hard gate refuses again, as it did M0038. The two-events "
        "problem remains: whatever the result, the 13-week gate made two calls in twenty years. "
        "Kin: M0038 is the parent and is not test-failed."
    ),
    candidates=(
        _v("SPY-E200S", SPY_EARLY, EarlyParams("spy", "start", "sma200"),
           "SPY, out after a curve inversion, back in once a year has passed since the first "
           "inverted day and SPY is over its 200-day average", DAILY_HOLD_FRAC_GOTRADE),
        _v("DIV-E200S", DIV_EARLY, EarlyParams("div", "start", "sma200"),
           "The big-dividend-raise book under the same watch and exit", MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-E200L", DIV_EARLY, EarlyParams("div", "last", "sma200"),
           "As DIV-E200S, the year counted from the last inverted day", MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-EHIGHL", DIV_EARLY, EarlyParams("div", "last", "high252"),
           "The year counted from the last inverted day; back in once SPY makes a one-year closing high",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("DIV-EHIGHL-5Y", DIV_EARLY, EarlyParams("div", "last", "high252", short="T5Y"),
           "As DIV-EHIGHL on the 10-year minus 5-year curve, whose 1998 warning was a false alarm",
           MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE),
        _v("SPY-EHIGHL", SPY_EARLY, EarlyParams("spy", "last", "high252"),
           "SPY under the DIV-EHIGHL watch and exit", DAILY_HOLD_FRAC_GOTRADE),
    ),
    seen_keys=(
        "concept:yield-curve-gate",
        "concept:term-spread",
        "concept:macro-regime-gate",
        "concept:gate-early-exit",
        "concept:risk-gate-overlay",
    ),
)
