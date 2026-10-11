"""M0101 — Calm big raisers behind a gentler safety switch.

Source: variation of M0088 (its C-LIVE-63 book, unchanged); Michaely, Thaler & Womack (1995),
JF 50(2) for the drift; Ang, Hodrick, Xing & Zhang (2006), JF 61(1) for the calm filter; the
banded moving-average filter of Brock, Lakonishok & LeBaron (1992), JF 47(5); Faber (2007), "A
Quantitative Approach to Tactical Asset Allocation", for the month-end 10-month average.
Idea: M0096 split the calm big-raise book's record by era and found the SPY-200 switch, not the
raisers, behind its 2009-2015 lag: the more switched SPY a book held, the wider the gap, because
the switch sold in the 2010, 2011 and 2015 dips and bought back higher. The same switch earned the
family's 2002-2008 edge by sitting out 2008. Keep the book and change only how the switch reads
SPY, so it needs a clear break to leave and a clear recovery to return.

Why a new allocator: M0088's ``_run`` hard-wires F4's ``trend_on`` (strict close > SMA200 on
``data_date``). ``BandedSwitchAllocator`` runs M0088's ``choose`` verbatim on M0088's prepared panel
and replaces only the gate:

    * ``switch="sma"``: ``trend_on`` unchanged (the paired control; must reproduce
      M0088-C-LIVE-63's 528 trades and 18.7% worst fall, under a new digest because the allocator
      id differs).
    * ``switch="band"`` with ``band=b``: hysteresis on the daily ratio r = close / SMA200 of SPY.
      Scanning back from ``data_date``, the newest session with r < 1-b sets the switch off and
      the newest with r > 1+b sets it on; whichever is newer wins. The state is read on daily
      closes, though the book only acts on it at the monthly re-pick. With no crossing in the last
      ``SCAN`` sessions (or in all the bars there are) it falls back to the plain strict test.
      ``lookback`` does not add ``SCAN``: that would move the dev window's first session off the
      parent's and break the paired control. A crossing older than the bars on hand is only
      possible in the first months of a run, and on the dev store SPY has years of run-up.
    * ``switch="faber"``: Faber's rule. The last close of each calendar month through
      ``data_date`` (``data_date``'s own close standing for its month), on when the newest is
      strictly above the mean of the last 10. Read only at the monthly re-pick, as Faber did.

When the switch is off the whole book targets nothing (cash), as M0088 does. Everything else is
M0088-C-LIVE-63. Reads only bars and dividends dated <= ``data_date``.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared
from seer_engine.lab.methods.m0088_calm_big_raisers import CALM, X, CalmParams, choose
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.sim.book import Target
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 11)

Switch = Literal["sma", "band", "faber"]
_SWITCHES: tuple[str, ...] = ("sma", "band", "faber")
SCAN = 504  # sessions of band history searched for the last crossing (about two years)
FABER_MONTHS = 10


@dataclass(frozen=True, slots=True)
class SwitchParams:
    """``book`` is M0088's book; ``switch`` how SPY's trend is read; ``band`` the hysteresis half-width."""

    book: CalmParams
    switch: Switch = "sma"
    band: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if not isinstance(self.book, CalmParams):
            raise TypeError(f"book must be CalmParams, got {type(self.book).__name__}")
        if self.book.ann.base.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the switch to read")
        if not isinstance(self.switch, str) or self.switch not in _SWITCHES:
            raise ValueError(f"switch must be one of {_SWITCHES}, got {self.switch!r}")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise ValueError(f"band must be a finite Decimal, got {self.band!r}")
        if self.switch == "band" and not Decimal(0) < self.band < Decimal("0.2"):
            raise ValueError(f"band must be in (0, 0.2) for switch='band', got {self.band}")
        if self.switch != "band" and self.band != 0:
            raise ValueError(f"band must be 0 unless switch='band', got {self.band}")

    def as_dict(self) -> dict[str, str]:
        out = {"switch": self.switch, "band": format(self.band.normalize(), "f")}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> SwitchParams:
    if not isinstance(params, SwitchParams):
        raise TypeError(f"params must be SwitchParams, got {type(params).__name__}")
    return params


def band_on(h: History | None, data_date: date, n: int, band: float) -> bool:
    """Hysteresis on close / SMA(n): off below 1-band, on above 1+band, else the last crossing's side."""
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None or i + 1 < n:
        return False
    lo = max(n - 1, i - SCAN)
    c = np.asarray(h.close[lo + 1 - n : i + 1], dtype=float)
    cs = np.concatenate(([0.0], np.cumsum(c)))
    sma = (cs[n:] - cs[:-n]) / n  # SMA ending at each session lo..i
    r = c[n - 1:] / sma
    if not np.all(np.isfinite(r)):
        return False
    for x in r[::-1]:
        if x < 1.0 - band:
            return False
        if x > 1.0 + band:
            return True
    return bool(r[-1] > 1.0)


def faber_on(h: History | None, data_date: date, months: int) -> bool:
    """Faber: the newest month-end close (``data_date``'s close for its month) above the mean of the last ``months``."""
    if h is None:
        return False
    i = h.index_of(data_date)
    if i is None:
        return False
    d = h.dates[: i + 1].astype("datetime64[M]")
    last = np.flatnonzero(np.append(d[1:] != d[:-1], True))  # last bar of each month through i
    if last.shape[0] < months:
        return False
    c = np.asarray(h.close[last[-months:]], dtype=float)
    if not np.all(np.isfinite(c)):
        return False
    return bool(c[-1] > float(np.mean(c)))


class BandedSwitchAllocator:
    """M0088's calm big-raise book behind a choice of SPY trend switch."""

    id = "M0101"
    market_fields = ("dividends",)

    def lookback(self, params: Any) -> int:
        p = _check(params)
        n = p.book.ann.base.inner.trend[1]
        return max(CALM.lookback(p.book), n, 23 * (FABER_MONTHS + 1))

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CALM.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return CALM.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def _on(self, history: Mapping[str, History], data_date: date, p: SwitchParams) -> bool:
        inner = p.book.ann.base.inner
        if p.switch == "sma":
            return trend_on(history, data_date, inner)
        symbol, n = inner.trend
        if p.switch == "band":
            return band_on(history.get(symbol), data_date, n, float(p.band))
        return faber_on(history.get(symbol), data_date, FABER_MONTHS)

    def _run(self, prepared: RaisePrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SwitchParams) -> tuple[Target, ...]:
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not self._on(prepared.history, data_date, p):
            return ()
        inner = p.book.ann.base.inner
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p.book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path: no calendar, so no event and no target."""
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


BANDED = BandedSwitchAllocator()
BOOK = CalmParams(X, "calm", "live", 63)  # M0088-C-LIVE-63, verbatim


def _v(suffix: str, params: SwitchParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0101-{suffix}", family="M0101", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=BANDED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0101",
    name="Calm big raisers behind a gentler safety switch: leave only when SPY is 3% under its 200-day average, return only when 3% over",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0088 (C-LIVE-63 unchanged); Michaely, Thaler & Womack (1995), JF 50(2); "
        "Ang, Hodrick, Xing & Zhang (2006), JF 61(1); Brock, Lakonishok & LeBaron (1992), JF 47(5) "
        "banded moving-average rule; Faber (2007), 10-month average"
    ),
    parent_id="M0088",
    hypothesis=(
        "Published 1995 (dividend-change drift), 2006 (low volatility), 1992 and 2007 (banded and "
        "10-month trend switches). M0096 showed the calm big-raise book's 2009-2015 lag belongs to "
        "the SPY-200 switch: more switched SPY widened the gap (-5.6 points a year at an 85% core "
        "vs -2.7 for M0088-C-LIVE-63), while the switch's 2008 exit earned about +9 points a year "
        "in 2002-2008. Keep M0088-C-LIVE-63 unchanged (big dividend raisers seen on the ex-date, "
        "calm half of the live raisers on a 63-session swing, up to 20 F4-screened members at 5% "
        "while the event is under 182 days old, rest in SPY, monthly, fractional at Gotrade's real "
        "fees) and replace only the switch. Variants: CTRL the unchanged strict close > SMA200 "
        "(paired control; must reproduce M0088-C-LIVE-63: 528 trades, 18.7% worst fall); BAND-3 "
        "hysteresis on SPY's daily close/SMA200, off below 0.97, back on above 1.03 (the idea); "
        "BAND-5 the same at 0.95/1.05; FABER month-end close above its 10-month average, read "
        "monthly. It ranks on dividend raises, so the family stays dividend-change-drift. "
        "Success: BAND-3 keeps a funded edge over SPY, a worst fall under 20%, a 2009-2015 gap "
        "under 1 point a year and a majority of walk-forward folds."
    ),
    expected_failure=(
        "The band exits later in 1998 and 2008 and returns later in 2003 and 2009, so the worst "
        "fall rises over 20% and the 2002-2008 edge shrinks; the 2010, 2011 and 2015 dips were "
        "deep enough (SPY fell 7-10% under its average) to cross a 3% band anyway, so the "
        "2009-2015 lag barely moves. A wider band (BAND-5) trades fewer whipsaws for a deeper "
        "fall. Faber's monthly reading is the most published switch of all and may simply match "
        "the control. Trend switches and the dividend drift are widely published, so even a dev "
        "edge is likely to fade after 2015. Withholding tax on dividends is not modelled."
    ),
    candidates=(
        _v("CTRL", SwitchParams(BOOK, "sma"),
           "Paired control: M0088-C-LIVE-63 behind its unchanged SPY-200 switch"),
        _v("BAND-3", SwitchParams(BOOK, "band", Decimal("0.03")),
           "Leave when SPY closes 3% under its 200-day average, return when 3% over"),
        _v("BAND-5", SwitchParams(BOOK, "band", Decimal("0.05")),
           "Leave when SPY closes 5% under its 200-day average, return when 5% over"),
        _v("FABER", SwitchParams(BOOK, "faber"),
           "Faber's switch: SPY's month-end close above its 10-month average"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:low-volatility-filter",
        "concept:banded-trend-switch",
        "concept:faber-10-month-sma",
    ),
)
