"""M0277 — Earnings news confirmed twice: an earnings-day jump the accounts also agree with.

Source: variation of M0072-Z2-RAWRANK (earnings-day jumps large for the stock's own swing, ranked
by the raw jump); Chan, Jegadeesh & Lakonishok (1996), "Momentum strategies", Journal of Finance
51(5) -- the price reaction to an announcement and the accounting surprise each carry their own
drift; Bernard & Thomas (1989) and Foster, Olsen & Shevlin (1984) for the surprise itself.

Idea: M0072's signal is the price reaction alone. A big up gap on heavy volume is usually an
earnings report, but it can also be a takeover rumour, an upgrade or a product day. SEC EDGAR's
diluted EPS gives an independent reading of the same news: the standardised unexpected earnings
(SUE) of the quarter that day reported -- this quarter's EPS minus the same quarter a year
earlier, over the spread of the last up-to-eight such changes (``fundamentals.sue``). A jump the
accounts agree with (SUE > 0) is news confirmed twice; one they contradict (SUE < 0) is a price
move the earnings do not explain.

**Which quarter belongs to a jump.** The press release that moves the price usually precedes the
10-Q or 10-K that carries the XBRL figure by days to weeks. So on each pick date the book reads
the diluted-EPS series visible on that date (``SymbolFundamentals.quarters``, ``filed <= t``),
takes its newest quarter that ended before the jump day, and counts it only if it was filed no
more than ``MATCH_LEAD_DAYS`` calendar days before the jump (``matched_sue``). Anything else -- no filing yet, a stale
quarter, a series too short for a SUE (nine contiguous quarters) -- is *unknown*, never a sign.
EDGAR's XBRL starts in 2009 and a SUE needs nine quarters, so in the dev window the filter can
act only from about 2011; before that every event is unknown.

The arms differ only in what they do with that reading (``mode``):

    * ``off``           M0072-Z2-RAWRANK's book exactly, the panel never read (the no-opinion arm);
    * ``veto``          drop a jump only when its quarter is known and contradicts it (SUE < 0);
                        unknown passes, so before ~2011 this is the control bar for bar;
    * ``confirmed``     keep a jump only when its quarter is known and agrees (SUE > 0);
                        unknown is dropped, so before ~2011 the book is SPY behind the switch;
    * ``contradicted``  the mirror: keep only known-and-contradicting jumps.

Everything else -- F4's screen, the SPY-200 switch, 20 slots of 5%, SPY in the empty slots, the
60-session event life, monthly re-picks, fractional shares at Gotrade's real fees -- is M0072's,
reused rather than copied (``m0072_standardised_earnings_jump``). With no panel at all (the
history-only ``prepare`` path) every arm targets nothing, ``off`` included: that is the lab's
contract for a market-aware allocator, and ``lab run`` always hands it the store's panel.

Pure: the event columns read bars t-max(vol_base, sd_base)..t+1 and the book reads only entries
with t+1 <= i; the panel answers from facts filed on or before the data date.
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
from seer_engine.fundamentals import EMPTY_PANEL, FundamentalPanel
from seer_engine.fundamentals.ladder import DILUTED_EPS
from seer_engine.fundamentals.sue import sue as sue_of
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0063_earnings_day_jump import EventCols
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    ZJUMP,
    ZParams,
    ZPrepared,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, prepare_factor, trend_on

ADDED = date(2026, 10, 22)

MODES: tuple[str, ...] = ("off", "veto", "confirmed", "contradicted")
MATCH_LEAD_DAYS = 5  # a filing up to this many calendar days before the jump still reports it


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ConfirmParams:
    """``z`` is M0072's event and book; ``mode`` says what the earnings reading does to it."""

    z: ZParams
    mode: str = "confirmed"

    def __post_init__(self) -> None:
        if not isinstance(self.z, ZParams):
            raise TypeError(f"z must be ZParams, got {type(self.z).__name__}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "match_lead_days": str(MATCH_LEAD_DAYS)}
        for k, v in self.z.as_dict().items():
            out[f"z.{k}"] = v
        return out


def _check(params: object) -> ConfirmParams:
    if not isinstance(params, ConfirmParams):
        raise TypeError(f"params must be ConfirmParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the event and its quarter


def live_event_at(cols: EventCols, sd: np.ndarray, i: int, p: ZParams) -> tuple[int, float] | None:
    """(bar t, raw jump) of the most recent live event with i - hold < t <= i - 1, or None.

    M0072's ``live_event`` with the event's bar returned too, so its date can be matched to a
    filing. The filters are M0072's, term for term.
    """
    jp = p.jump
    lo = max(i - jp.hold + 1, jp.vol_base, p.sd_base)
    hi = i - 1
    if hi < lo:
        return None
    v = cols.vratio[lo : hi + 1]
    g = cols.gap[lo : hi + 1]
    j = cols.jump[lo : hi + 1]
    s = sd[lo : hi + 1]
    ok = np.isfinite(v) & np.isfinite(g) & np.isfinite(j) & np.isfinite(s)
    if jp.vol_min is not None:
        ok &= v >= float(jp.vol_min)
    if jp.vol_max is not None:
        ok &= v < float(jp.vol_max)
    ok &= g > float(jp.gap_min)
    ok &= j >= float(jp.jump_min)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(ok, j / s, np.nan)
    ok &= np.isfinite(z) & (z >= float(p.z_min))
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return None
    k = int(idx[-1])
    return lo + k, float(j[k])


def matched_sue(panel: FundamentalPanel, symbol: str, jump_day: date, data_date: date) -> float | None:
    """SUE of the quarter the jump on ``jump_day`` reported, as known on ``data_date``; None if unknown.

    The jump's quarter is the newest visible quarter that ended before the jump day (a later one
    is the next season's report, which can already be filed when the event is weeks old). It
    counts only when it was filed no more than ``MATCH_LEAD_DAYS`` before the jump; one filed
    earlier was already old news on the day, so the jump was about something else. The SUE is
    read on the series up to that quarter, which ``fundamentals.sue`` makes bit-identical to the
    SUE as it stood when that quarter was the newest.
    """
    sf = panel.get(symbol)
    if sf is None:
        return None
    series = sf.quarters(DILUTED_EPS, data_date)
    k = len(series) - 1
    while k >= 0 and series[k].period_end >= jump_day:
        k -= 1
    if k < 0 or series[k].filed < jump_day - timedelta(days=MATCH_LEAD_DAYS):
        return None
    s = sue_of(np.array([o.val for o in series[: k + 1]], dtype=np.float64))
    return s if np.isfinite(s) else None


def admits(mode: str, s: float | None) -> bool:
    if mode == "off":
        return True
    if mode == "veto":
        return s is None or s >= 0.0
    if mode == "confirmed":
        return s is not None and s > 0.0
    return s is not None and s < 0.0  # contradicted


# --------------------------------------------------------------------------- the allocator


class ConfirmPrepared:
    """M0072's prepared columns plus the market's point-in-time fundamental panel."""

    def __init__(self, z: ZPrepared, panel: FundamentalPanel) -> None:
        self.z = z
        self.panel = panel


class ConfirmedJumpAllocator:
    """M0072-Z2-RAWRANK's monthly news-day book, filtered by the reported quarter's surprise; rest SPY."""

    id = "M0277"
    market_fields = ("fundamentals",)

    def lookback(self, params: Any) -> int:
        return ZJUMP.lookback(_check(params).z)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_check(params).z)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_check(params).z)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _targets(self, prepared: ConfirmPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], p: ConfirmParams) -> tuple[Target, ...]:
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
            if p.mode != "off":
                jump_day = h.dates[t].astype(date)
                if not admits(p.mode, matched_sue(prepared.panel, r.symbol, jump_day, data_date)):
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
        return self._targets(ConfirmPrepared(ZPrepared(history, None), EMPTY_PANEL), rows,
                             data_date, held, p)

    def prepare(self, history: Mapping[str, History]) -> ConfirmPrepared:
        return ConfirmPrepared(ZPrepared(history, prepare_factor(history)), EMPTY_PANEL)

    def prepare_market(self, market: Any) -> ConfirmPrepared:
        panel = getattr(market, "fundamentals", EMPTY_PANEL)
        if not isinstance(panel, FundamentalPanel):
            raise TypeError(f"market.fundamentals must be a FundamentalPanel, got {type(panel).__name__}")
        return ConfirmPrepared(ZPrepared(market.history, prepare_factor(market.history)), panel)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ConfirmPrepared) or prepared.z.factor is None:
            raise TypeError(f"prepared must be a prepared ConfirmPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not trend_on(prepared.z.history, data_date, p.z.jump.inner):
            return ()
        rows = prepared.z.factor.rows_on(members, data_date, p.z.jump.inner)
        return self._targets(prepared, rows, data_date, held, p)


CONFIRM = ConfirmedJumpAllocator()

RAWRANK = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")  # M0072-Z2-RAWRANK's event, filter and ranking


def _v(suffix: str, mode: str, rationale: str) -> Candidate:
    return Candidate(id=f"M0277-{suffix}", family="M0277", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CONFIRM, params=ConfirmParams(RAWRANK, mode=mode),
                     rationale=rationale, added=ADDED, owner_inputs=())


METHOD = Method(
    id="M0277",
    name="Earnings news confirmed twice: take a large-for-the-stock earnings-day jump only when the "
         "company's reported earnings also beat the same quarter last year",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0072-Z2-RAWRANK; Chan, Jegadeesh & Lakonishok (1996), Momentum "
               "strategies, J. Finance 51(5); Bernard & Thomas (1989), J. Accounting Research 27; "
               "Foster, Olsen & Shevlin (1984), The Accounting Review 59",
    parent_id="M0072",
    hypothesis=(
        "Published 1984-1996 (the earnings surprise and the price reaction as separate drifts) and "
        "2008 (the earnings-day jump), so the dev window can only show an edge from after the crowd "
        "knew it. M0072-Z2-RAWRANK beat SPY on dev (+12.3% a year vs +7.2% on the owner's deposits, "
        "luck score 0.914) and beat SPY in 2009-2015, failing only the worst fall (23.8%). Its "
        "signal is the price reaction alone. Adding the accounts' own reading of the quarter -- "
        "standardised unexpected earnings from SEC EDGAR diluted EPS (this quarter minus the same "
        "quarter a year earlier, over the spread of up to eight earlier such changes), gated on the "
        "filing date and matched to the jump as the newest quarter that ended before the jump day, "
        "counted only if it was filed no more than 5 days before the jump -- should keep the jumps that are "
        "really earnings news and drop the ones the earnings contradict. EDGAR's XBRL starts in "
        "2009 and a surprise needs nine quarters, so the filter can act only from about 2011; this "
        "runs knowingly below the 80% panel-coverage floor (lab run --allow-coverage) and is judged "
        "on 2012-2015, where the arms differ, against the control in the same years. Four arms on "
        "M0072-Z2-RAWRANK's frame exactly (monthly, 20 slots of 5%, rest SPY, SPY-200 switch, "
        "fractional shares at Gotrade's real fees on monthly-hold-frac-gotrade, the owner's monthly "
        "deposits): OFF (the parent's book, panel never read: the no-opinion arm, a re-run that "
        "should reproduce the parent's recorded trial), VETO (drop a jump only when its quarter "
        "is known and negative; unknown passes, so identical to OFF before ~2011), CONFIRMED (keep "
        "only known-and-positive; before ~2011 the book is SPY behind the switch) and CONTRADICTED "
        "(the mirror: keep only known-and-negative). I expect CONFIRMED > VETO > OFF > CONTRADICTED "
        "on the 2012-2015 book return. Success for the idea: VETO beats OFF in 2012-2015 and "
        "CONFIRMED beats CONTRADICTED there; success for the gate: a variant with worst fall under "
        "the screen, beating total-return SPY, DSR >= 0.90."
    ),
    expected_failure=(
        "The gate will very likely reject every arm on the 1998 fall, which no earnings filter can "
        "touch (no panel before 2009): VETO inherits OFF's 23.8%, and CONFIRMED is SPY behind the "
        "switch for fifteen years, so it will not beat SPY over the whole window. The real question "
        "lives in about four years, with perhaps 20-40 live jumps a month, so the difference between "
        "arms may be within noise. Most big up-gaps on heavy volume in large caps are earnings beats "
        "already, so CONTRADICTED may hold only a handful of names and VETO may barely differ from "
        "OFF. The 10-Q often arrives weeks after the release, so on many pick dates the quarter is "
        "still unknown; CONFIRMED then waits a month to buy, losing the early part of the drift the "
        "jump book lives on. The year-on-year surprise is a crude stand-in for the analyst consensus "
        "the price actually reacted to, and a published anomaly, so even a clean 2012-2015 win may "
        "have faded since."
    ),
    candidates=(
        _v("OFF", "off",
           "The parent's book exactly, earnings never read: the no-opinion arm the others are priced against"),
        _v("VETO", "veto",
           "Drop a jump only when the reported quarter's earnings fell short of last year's; unknown passes"),
        _v("CONFIRMED", "confirmed",
           "Keep a jump only when the reported quarter beat the same quarter last year"),
        _v("CONTRADICTED", "contradicted",
           "The mirror: keep only jumps whose reported quarter missed last year's"),
    ),
    seen_keys=(
        "concept:earnings-jump-confirmed-by-sue",
        "concept:price-reaction-and-accounting-surprise",
        "concept:sue-filtered-announcement-return",
    ),
)
