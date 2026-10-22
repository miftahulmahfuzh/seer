"""M0279 — Non-earnings news days: is the jump's drift about earnings, or about any big news?

Source: variation of M0277 (which filtered M0072-Z2-RAWRANK's news-day jumps by the reported
quarter's earnings surprise and found the sign adds nothing); Brandt, Kishore, Santa-Clara &
Venkatachalam (2008), SSRN 909563 (the earnings-day jump drifts); Chan (2003), "Stock price
reaction to news and no-news", J. Financial Economics 70 (big moves *with* news drift, without
news they reverse) -- here "news" is any heavy-volume up gap, so the split asks which news.

Idea: M0277 matched about 55% of 2012-2015's live jumps to a filed quarter; the rest had none.
If the jumps no earnings report explains (upgrades, deals, product days) drift as well as the
earnings jumps, the book's edge is the market's slow reaction to *any* big news, not post-
earnings drift, and the earnings data is not needed at all. Two independent ways to split:

**Filed (SEC EDGAR, from about 2010).** For an event on jump day J, read on data date D: the
*first* filing date of each fiscal period the company has reported (the earliest ``filed`` of
any quarterly or annual duration fact ending on that date, ``filed <= D``). Take the newest
period ending before J.

    * no fact at all filed 100+ days before J: the company is not in the panel yet -> unknown;
    * that period ended more than ``PENDING_DAYS`` before J: a newer quarter had already ended
      and is not reported by D, so the jump may be its release -> unknown (pending; the filed arm
      picks it up once the report lands, if the event is still live);
    * first filed in [J - ``MATCH_LEAD_DAYS``, J + ``MATCH_LAG_DAYS``]: the jump was that
      period's report -> ``filed``;
    * otherwise (reported well before the jump, or long after it) -> ``unfiled``: a news day in
      the middle of the quarter, after the last report and before the next one was due.

**Season (price only, the whole window).** Big companies report in the same weeks every year, and
the report days leave volume spikes. For event bar t, look one, two, three and four quarters back
(63, 126, 189, 252 sessions) and ask whether the stock had a session with volume at least
``SEASON_VOL`` x its 60-day median within ``SEASON_HALF`` sessions of that date. Three or four
hits: the jump fell in the stock's usual reporting week (``season``); none or one: it did not
(``offseason``); two, or too little history: unknown. This reads bars t-252-7-60 .. t-56 only.

Arms (``mode``), all on M0072-Z2-RAWRANK's frame exactly (``m0277_earnings_confirmed_jump``'s
event and book, reused): ``off`` (the unchanged book, the no-opinion arm), ``filed`` /
``unfiled`` (the mirror pair on filings, SPY behind the switch before ~2010) and ``season`` /
``offseason`` (the mirror pair on the price calendar, live from 1997). Unknown drops a jump from
both arms of its pair. Slots the filter leaves empty hold SPY, as in the parent.

Pure: event columns read bars t-max(vol_base, sd_base)..t+1, the season column bars before t-55,
and the book reads only events with t+1 <= i; the panel answers from facts filed on or before D.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.fundamentals import EMPTY_PANEL, KIND_ANNUAL, KIND_QUARTER, FundamentalPanel
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZJUMP, ZParams, ZPrepared
from seer_engine.lab.methods.m0277_earnings_confirmed_jump import RAWRANK, live_event_at
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 22)

MODES: tuple[str, ...] = ("off", "filed", "unfiled", "season", "offseason")
MATCH_LEAD_DAYS = 5  # a report filed up to this many days before the jump is the jump's report
MATCH_LAG_DAYS = 45  # ... and up to this many after (the 10-Q/10-K trails the press release)
PENDING_DAYS = 100  # newest reported period older than this at the jump: a newer one is unreported
COVERED_DAYS = 100  # the company must have filed something this long before the jump
SEASON_LAGS: tuple[int, ...] = (63, 126, 189, 252)  # one to four quarters back, in sessions
SEASON_HALF = 7  # sessions either side of each lag
SEASON_VOL = 2.0  # a reporting-day footprint: volume >= this x the 60-day median
SEASON_MIN = 3  # hits for "in season"; <= SEASON_MAX_OFF hits for "off season"
SEASON_MAX_OFF = 1


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class SplitParams:
    """``z`` is M0072's event and book; ``mode`` says which jumps the book may take."""

    z: ZParams
    mode: str = "off"

    def __post_init__(self) -> None:
        if not isinstance(self.z, ZParams):
            raise TypeError(f"z must be ZParams, got {type(self.z).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode}
        if self.mode in ("filed", "unfiled"):
            out.update(match_lead_days=str(MATCH_LEAD_DAYS), match_lag_days=str(MATCH_LAG_DAYS),
                       pending_days=str(PENDING_DAYS), covered_days=str(COVERED_DAYS))
        if self.mode in ("season", "offseason"):
            out.update(season_lags=",".join(map(str, SEASON_LAGS)), season_half=str(SEASON_HALF),
                       season_vol=str(SEASON_VOL), season_min=str(SEASON_MIN),
                       season_max_off=str(SEASON_MAX_OFF))
        for k, v in self.z.as_dict().items():
            out[f"z.{k}"] = v
        return out


def _check(params: object) -> SplitParams:
    if not isinstance(params, SplitParams):
        raise TypeError(f"params must be SplitParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the two splits


class FilingCalendar:
    """One symbol's fiscal periods and the first date each was reported, for point-in-time reads."""

    def __init__(self, facts: Any) -> None:
        first: dict[date, list[date]] = {}
        earliest: date | None = None
        for f in facts:
            if earliest is None or f.filed < earliest:
                earliest = f.filed
            if f.kind() not in (KIND_QUARTER, KIND_ANNUAL):
                continue
            first.setdefault(f.period_end, []).append(f.filed)
        self.earliest = earliest
        self.periods = tuple(sorted(first))
        self.first_filed = {pe: min(v) for pe, v in first.items()}
        # every filing of a period, ascending: a period is visible at D once its first filing is
        self._filed_sorted = {pe: sorted(v) for pe, v in first.items()}

    def classify(self, jump_day: date, data_date: date) -> str | None:
        if self.earliest is None or self.earliest > jump_day - timedelta(days=COVERED_DAYS):
            return None
        pe = None
        for p in reversed(self.periods):
            if p < jump_day and self.first_filed[p] <= data_date:
                pe = p
                break
        if pe is None or (jump_day - pe).days > PENDING_DAYS:
            return None
        ff = self.first_filed[pe]
        if jump_day - timedelta(days=MATCH_LEAD_DAYS) <= ff <= jump_day + timedelta(days=MATCH_LAG_DAYS):
            return "filed"
        return "unfiled"


def season_class(vratio: np.ndarray, t: int) -> str | None:
    """'season', 'offseason' or None, from volume spikes 1-4 quarters before bar t (bars < t-55)."""
    hits = 0
    for lag in SEASON_LAGS:
        lo, hi = t - lag - SEASON_HALF, t - lag + SEASON_HALF
        if lo < 0:
            return None
        w = vratio[lo : hi + 1]
        if not np.isfinite(w).any():
            return None
        if np.nanmax(w) >= SEASON_VOL:
            hits += 1
    if hits >= SEASON_MIN:
        return "season"
    if hits <= SEASON_MAX_OFF:
        return "offseason"
    return None


# --------------------------------------------------------------------------- the allocator


class SplitPrepared:
    """M0072's prepared columns plus the panel and each symbol's filing calendar, built on first use."""

    def __init__(self, z: ZPrepared, panel: FundamentalPanel) -> None:
        self.z = z
        self.panel = panel
        self._cal: dict[str, FilingCalendar | None] = {}

    def calendar(self, symbol: str) -> FilingCalendar | None:
        if symbol not in self._cal:
            sf = self.panel.get(symbol)
            self._cal[symbol] = None if sf is None else FilingCalendar(sf.facts)
        return self._cal[symbol]


class NewsSplitAllocator:
    """M0072-Z2-RAWRANK's monthly news-day book, keeping only one kind of news day; rest SPY."""

    id = "M0279"
    market_fields = ("fundamentals",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        return max(ZJUMP.lookback(p.z), p.z.jump.hold + max(SEASON_LAGS) + SEASON_HALF + p.z.jump.vol_base + 2)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_check(params).z)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_check(params).z)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _admits(self, prepared: SplitPrepared, symbol: str, h: History, vratio: np.ndarray,
                t: int, data_date: date, mode: str) -> bool:
        if mode == "off":
            return True
        if mode in ("season", "offseason"):
            return season_class(vratio, t) == mode
        cal = prepared.calendar(symbol)
        if cal is None:
            return False
        return cal.classify(h.dates[t].astype(date), data_date) == mode

    def _targets(self, prepared: SplitPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], p: SplitParams) -> tuple[Target, ...]:
        if len(prepared.panel) == 0:
            return ()  # no panel: the lab's contract for a market-aware book, every arm alike
        zp = p.z
        jp = zp.jump
        zprep = prepared.z
        live: list[tuple[int, float, str]] = []
        for r in rows:
            h: History | None = zprep.history.get(r.symbol)
            if h is None or r.symbol == jp.market:
                continue
            i = h.index_of(data_date)
            got = zprep.cols(r.symbol, jp.market, jp.vol_base, zp.sd_base)
            if i is None or got is None:
                continue
            ev = live_event_at(got[0], got[1], i, zp)
            if ev is None:
                continue
            t, raw = ev
            if not self._admits(prepared, r.symbol, h, got[0].vratio, t, data_date, p.mode):
                continue
            score = raw if zp.rank == "raw" else raw / float(got[1][t])
            live.append((0 if r.symbol in held else 1, -score, r.symbol))
        w = equal_weight(jp.inner.top)
        out: list[Target] = []
        for _, _, s in sorted(live)[: jp.inner.top]:
            tg = target_from_close(s, last_close(zprep.history[s], data_date), w)
            if tg is not None:
                out.append(tg)
        if jp.park:
            rest = Decimal(1) - w * len(out)
            mh = zprep.history.get(jp.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                tg = target_from_close(jp.market, last_close(mh, data_date), rest)
                if tg is not None:
                    out.append(tg)
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no panel, so no target (the market-aware contract)."""
        p = _check(params)
        if not trend_on(history, data_date, p.z.jump.inner):
            return ()
        rows = factor_rows(history, members, data_date, p.z.jump.inner)
        return self._targets(SplitPrepared(ZPrepared(history, None), EMPTY_PANEL), rows,
                             data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> SplitPrepared:
        return SplitPrepared(ZPrepared(history, prepare_factor(history)), EMPTY_PANEL)

    def prepare_market(self, market: Any) -> SplitPrepared:
        panel = getattr(market, "fundamentals", EMPTY_PANEL)
        if not isinstance(panel, FundamentalPanel):
            raise TypeError(f"market.fundamentals must be a FundamentalPanel, got {type(panel).__name__}")
        return SplitPrepared(ZPrepared(market.history, prepare_factor(market.history)), panel)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, SplitPrepared) or prepared.z.factor is None:
            raise TypeError(f"prepared must be a prepared SplitPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.z.history, data_date, p.z.jump.inner):
            return ()
        rows = prepared.z.factor.rows_on(members, data_date, p.z.jump.inner)
        return self._targets(prepared, rows, data_date, held, p)


SPLIT = NewsSplitAllocator()


def _v(suffix: str, mode: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0279-{suffix}", family="M0279", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SPLIT, params=SplitParams(RAWRANK, mode=mode),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0279",
    name="Non-earnings news days: take a large-for-the-stock jump only when no earnings filing "
         "explains it",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0277 / M0072-Z2-RAWRANK; Brandt, Kishore, Santa-Clara & "
               "Venkatachalam (2008), SSRN 909563; Chan (2003), Stock price reaction to news and "
               "no-news, J. Financial Economics 70",
    parent_id="M0277",
    hypothesis=(
        "Published 2003 (news days drift, no-news days reverse) and 2008 (the earnings-day jump), "
        "so the dev window can only show an edge from after the crowd knew it. M0277 found the "
        "sign of the year-on-year earnings surprise adds nothing to the news-day book, and that "
        "about 45% of 2012-2015's live jumps had no matching earnings filing. If the jumps no "
        "earnings report explains drift as well as the earnings jumps, the book's edge is a slow "
        "reaction to any big news, not post-earnings drift, and the earnings data is not needed. "
        "Two splits, each a mirror pair beside the unchanged book (OFF, the no-opinion arm, "
        "M0072-Z2-RAWRANK's frame exactly: monthly, 20 slots of 5%, rest SPY, SPY-200 switch, "
        "fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade, the owner's "
        "monthly deposits). FILED/UNFILED: a jump is filed when the newest fiscal period that "
        "ended before it was first reported to the SEC between 5 days before and 45 days after "
        "the jump; unfiled when that period was reported outside that span and no newer quarter "
        "was pending (the period ended at most 100 days before the jump); the company must have "
        "filed something 100+ days before the jump; otherwise unknown and dropped from both. "
        "EDGAR's XBRL starts in 2009, so this pair is SPY behind the switch until about 2010 and "
        "is judged on 2011-2015; it runs knowingly below the 80% panel-coverage floor (lab run "
        "--allow-coverage 0.30, as M0277 did). SEASON/OFFSEASON: price only, the whole window: a "
        "jump is in season when the stock had a session at 2x its 60-day median volume within 7 "
        "sessions of the same point 1, 2, 3 and 4 quarters earlier in at least three of the four, "
        "off season in at most one, unknown at two. I expect UNFILED and OFFSEASON to drift about "
        "as well as their mirrors (within 2 points a year of each other on the book return), "
        "which would say the edge is any news. Success for the idea: OFFSEASON's 1997-2015 book "
        "return within 2 points a year of SEASON's or better, and UNFILED's 2011-2015 within 2 "
        "points of FILED's or better; success for the gate: a variant with worst fall under the "
        "screen, beating total-return SPY, DSR >= 0.90."
    ),
    expected_failure=(
        "OFF is the parent's book again (it should reproduce M0277-OFF) and inherits the 1998 fall "
        "of 23.8%; every arm that keeps a subset of the parent's jumps likely falls about as far "
        "in 1998 and holds fewer names, so the gate may reject them all on the worst fall or the "
        "luck bar. Chan (2003) found news-less big moves reverse, and an off-season gap on heavy "
        "volume in a big company is often a takeover bid (a one-off jump with no drift after it) "
        "or an index-inclusion day, so OFFSEASON may drift less, not as well. Only roughly one "
        "jump in four may be off season, so OFFSEASON may hold few names and be mostly SPY; the "
        "price calendar is a proxy and will misfile companies that moved their report date. The "
        "filing split is judged on about five years with perhaps 15-25 live jumps a pick date "
        "per arm, so its difference may be inside the noise; the 45-day match window can call a "
        "deal announced in the first weeks after a quarter end an earnings jump. A published "
        "anomaly, so even a clean win may have faded since."
    ),
    candidates=(
        _v("OFF", "off",
           "The parent's book unchanged: the no-opinion arm both splits are priced against"),
        _v("FILED", "filed",
           "Keep only jumps an SEC earnings filing explains (reported within 5 days before to 45 after)"),
        _v("UNFILED", "unfiled",
           "Keep only mid-quarter jumps no earnings filing explains: the non-earnings news days"),
        _v("SEASON", "season",
           "Keep only jumps in the stock's usual reporting weeks, read from last year's volume spikes"),
        _v("OFFSEASON", "offseason",
           "The mirror: keep only jumps outside the stock's usual reporting weeks"),
    ),
    seen_keys=(
        "concept:non-earnings-news-drift",
        "concept:news-vs-earnings-announcement-drift",
        "concept:earnings-season-from-volume-calendar",
    ),
)
