"""M0215 — Calm big dividend raisers with a sector cap: no more than a few from any one industry.

Source: variation of M0168 (its CTRL, which is M0088-C-LIVE-63 bit for bit); Sera batch
20261017-2050 (sector caps), reserved with the cap sizes 3, 4 and 5 and a hash-order control.
Sectors are Fama-French 12 from SEC EDGAR (``seer_engine.sectors``).

Why. Big dividend raisers are not spread evenly over the market. Replaying M0168-CTRL on the dev
store before this file was written (its recorded configuration, 528 trades reproduced): the book
holds 9.5 names on average, not 20; banks and finance (FF12 ``Money``) fill 25% of its slot-months
and retailers (``Shops``) 19%, with utilities at 4%; one industry holds more than 3, 4 and 5 names
in 78, 45 and 22 of its 169 invested months. If the book's 2009-2015 lag behind SPY is a hidden
bet on banks and shops, capping each industry should lift that era and the fold record.

What changes. Only which raisers fill the slots: the live, calm raisers are walked in the
parent's order (held names first, then the newest event) through ``sectors.select_capped`` with
``cap`` names per FF12 industry, unknown sectors sharing one capped bucket. A raiser the cap
skips does not leave a gap the next raiser could not fill: the walk simply moves on, and a slot
nobody can fill goes to SPY with the rest of the money, exactly as the parent parks its unfilled
slots. (The batch's sibling idea rows say "unfilled slots stay cash"; this book has always parked
in SPY and cash would change two things at once, so it parks, and that is the assumption made.)
``cap=None`` is the parent's ``choose`` verbatim, the control.

The placebo. ``order="hash"`` keeps the frame and replaces the names: each month it counts the
slots the uncapped raise book would fill, k, and fills k slots from all screened members in the
order of a fixed blake2b hash of seed, symbol and quarter (M0187's ``draw`` idea, re-keyed by
quarter), held names first so a holding is not re-drawn every month. Same switch, same SPY
parking, same exposure month by month, names that know nothing about dividends. With and without
the cap of 4, it says whether a cap helps any book of this shape or only the raise book.

The sector map is loaded once from the vendored EDGAR files (no network, no clock). EDGAR's SIC
is a filer's latest, not point in time; that blurs a cap, it cannot leak a price.

Rules are ``monthly-hold-frac-gotrade``: fractional shares at Gotrade's real fees, monthly.

Amendment 1 (2026-10-19). The two placebos above are mis-shaped and D17 refuses them: the hash is
re-keyed on the calendar quarter and held names sort first, a double stickiness, so each traded 179
times in twenty years against the 528 of ``CTRL`` and the 500 of ``CAP4`` -- 0.34x trades, 0.43x
turnover. Their slot count was already the raise book's own, so the size axis was matched and only
the churn was not. ``CTRL-PLC`` and ``CAP4-PLC`` keep every other part of the frame and take their
entry count each month from the arm each one controls (``lab.control_draw``, the lab's one
matched-draw rule). They also fix a resolution: ``HASH-CAP4`` resolves to ``CTRL`` because its own
stem is a placebo, while the book it exists to price is ``CAP4``; ``<target>-PLC`` names put both
new arms on the ``sibling-stem`` rung. The six recorded configurations are untouched -- the matched
draw reuses the two replaced arms' own ``CapParams`` values byte for byte and rides behind its own
allocator id, ``M0215-A1``, which is the whole of the difference.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Any

import numpy as np

from seer_engine import sectors
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_DIVIDENDS, DividendCalendar
from seer_engine.lab import control_draw
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0070_dividend_raise_drift import RaisePrepared, _first_bar, live_event
from seer_engine.lab.methods.m0076_dividend_raise_on_announcement import events
from seer_engine.lab.methods.m0088_calm_big_raisers import CalmParams, admits, swing
from seer_engine.lab.methods.m0168_banded_calm_raisers import C63, BandedCalmRaiseAllocator, BandParams
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import EXCLUDED, FactorRow, factor_rows, trend_on

ADDED = date(2026, 10, 17)

ORDERS = ("raise", "hash")


@dataclass(frozen=True, slots=True)
class CapParams:
    """``calm`` is M0088's book and filter; ``cap`` the most names per FF12 industry (None: no
    cap); ``order`` fills the slots with the raisers or, as the placebo, hash-ordered members."""

    calm: CalmParams
    cap: int | None = None
    order: str = "raise"
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.calm, CalmParams):
            raise TypeError(f"calm must be CalmParams, got {type(self.calm).__name__}")
        if self.calm.side != "calm" or self.calm.pool != "live":
            raise ValueError("M0215 caps the calm half of the live raisers only")
        if self.cap is not None and (isinstance(self.cap, bool) or not isinstance(self.cap, int)
                                     or self.cap < 1):
            raise ValueError(f"cap must be a positive int or None, got {self.cap!r}")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {ORDERS}, got {self.order!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {self.seed!r}")

    def as_dict(self) -> dict[str, str]:
        out = {"cap": "none" if self.cap is None else str(self.cap), "order": self.order,
               "seed": str(self.seed), "sectors": "ff12-edgar-latest-sic",
               "hash": "blake2b-8-quarter"}
        for k, v in self.calm.as_dict().items():
            out[f"calm.{k}"] = v
        return out


def _check(params: object) -> CapParams:
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    return params


@lru_cache(maxsize=1)
def sector_map() -> sectors.SectorMap:
    return sectors.load()


def sector_of(symbol: str, on: date) -> str | None:
    return sector_map().sector_of(symbol, on)


def draw(seed: int, symbol: str, data_date: date) -> int:
    """The placebo's order: a fixed 64-bit hash of seed, symbol and the calendar quarter."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-Q{(data_date.month - 1) // 3 + 1}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def calm_raisers(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
                 data_date: date, held: frozenset[str], c: CalmParams) -> list[FactorRow]:
    """The live raisers that pass the calm cut, in the parent's order (held, newest, symbol).
    This is M0168's ``choose`` path at ``keep_q=0.5`` up to the slot cut."""
    a = c.ann
    b = a.base
    live: list[tuple[int, int, str, FactorRow]] = []
    for r in rows:
        if r.symbol in EXCLUDED or r.symbol == b.market:
            continue
        paid, declared = events(calendar, r.symbol, data_date, a.timing)
        if a.declared_only and not declared:
            continue
        e = live_event(paid, _first_bar(history.get(r.symbol)), data_date, b)
        if e is None:
            continue
        live.append((0 if r.symbol in held else 1, -e.toordinal(), r.symbol, r))
    vols = {t[2]: swing(history.get(t[2]), data_date, c.vol_n) for t in live}
    pool = [v for v in vols.values() if v is not None]
    cut = float(np.median(pool)) if pool else None
    live = [t for t in live if admits(vols[t[2]], cut, "calm")]
    live.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[3] for t in live]


def _fill(ordered: list[str], data_date: date, n: int, cap: int | None) -> list[str]:
    if cap is None:
        out: list[str] = []
        for s in ordered:
            if len(out) >= n:
                break
            if s not in out:
                out.append(s)
        return out
    return sectors.select_capped(ordered, data_date, n, cap, sector_of)


def choose(history: Mapping[str, History], rows: list[FactorRow], calendar: DividendCalendar,
           data_date: date, held: frozenset[str], p: CapParams) -> tuple[Target, ...]:
    b = p.calm.ann.base
    top = b.inner.top
    raisers = calm_raisers(history, rows, calendar, data_date, held, p.calm)
    close = {r.symbol: r.close for r in rows}
    if p.order == "raise":
        picks = _fill([r.symbol for r in raisers], data_date, top, p.cap)
    else:
        k = min(len(raisers), top)
        pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != b.market)
        ordered = sorted(pool, key=lambda s: (0 if s in held else 1, draw(p.seed, s, data_date), s))
        picks = _fill(ordered, data_date, k, p.cap)
    w = equal_weight(top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    if b.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(b.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(b.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class SectorCappedRaiseAllocator(BandedCalmRaiseAllocator):
    """M0168's calm big raisers (its control path), filled through an FF12 sector cap; or the
    same frame filled with hash-ordered members as the placebo. Everything but ``choose`` and the
    params check is M0168's."""

    id = "M0215"

    def lookback(self, params: Any) -> int:
        return super().lookback(_band(params))

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_band(params))

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_band(params))

    def uses_members(self, params: Any) -> bool:
        return super().uses_members(_band(params))

    def _run(self, prepared: Any, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Any) -> tuple[Target, ...]:
        p = _check(p)
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        inner = p.calm.ann.base.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        if prepared.factor is None:
            rows = factor_rows(prepared.history, members, data_date, inner)
        else:
            rows = prepared.factor.rows_on(members, data_date, inner)
        return choose(prepared.history, rows, prepared.calendar, data_date, held, p)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check(params))


def _band(params: Any) -> BandParams:
    """M0168's params for the same book, so the inherited lookback and symbols read it."""
    return BandParams(_check(params).calm, 0.5)


CAPPED = SectorCappedRaiseAllocator()


# --------------------------------------------------------------------------- amendment 1
#
# The churn-matched placebo (2026-10-19). See the module docstring's last paragraph and
# ``seer_engine.lab.control_draw`` for the rule itself; what lives here is this method's half of
# it: which arm is being controlled, and how its shape is read off.


def _check_matched(params: object) -> CapParams:
    """``CapParams``, plus the one thing a control's params may not say.

    The matched draw differs from ``HASH`` / ``HASH-CAP4`` in its allocator id and in nothing
    else, so the params must still read ``order="hash"``. Saying ``"raise"`` would record a
    configuration whose text claims the raise ordering this allocator never performs -- it
    *replays* that ordering to count the real book's entries, and then draws blind.

    Reused and not replaced: ``CapParams`` already carries ``calm``, ``cap``, ``order`` and
    ``seed``, which is every input this allocator reads, so a wrapper dataclass would hold
    nothing new. ``backtest.registry._canon`` renders a dataclass by ``dataclasses.fields()``,
    not by ``as_dict()``, so a new field on ``CapParams`` -- even defaulted, even local to this
    file -- would move the ``config_digest`` of all six recorded M0215 trials, and a
    ``compare=False`` field would make the new arm's configuration identical to the old one's,
    which ``Method.__post_init__`` refuses. Reusing the old value under a new allocator id does
    neither.
    """
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    if params.order != "hash":
        raise ValueError(
            f"the matched draw is a control: order must be 'hash', got {params.order!r}"
        )
    return params


def _rows_on(prepared: Any, members: AbstractSet[str], data_date: date,
             inner: Any) -> list[FactorRow]:
    """``_run``'s factor-row read, lifted so a previous session can use it too."""
    if prepared.factor is None:
        return factor_rows(prepared.history, members, data_date, inner)
    return prepared.factor.rows_on(members, data_date, inner)


def _raise_picks(prepared: Any, rows: list[FactorRow], data_date: date, held: frozenset[str],
                 book: CapParams) -> list[str]:
    """What the controlled arm holds on ``data_date``: ``choose``'s raise path, names only."""
    b = book.calm.ann.base
    raisers = calm_raisers(prepared.history, rows, prepared.calendar, data_date, held, book.calm)
    return _fill([r.symbol for r in raisers], data_date, b.inner.top, book.cap)


def _target_shape(prepared: Any, members: AbstractSet[str], rows: list[FactorRow],
                  data_date: date, book: CapParams) -> tuple[list[str], list[str]]:
    """(the controlled arm's book now, its book at the previous monthly decision session).

    One allocator cannot see another candidate's ``held`` set, so the previous session is replayed
    from an empty book and its result is fed forward as ``held`` for the current one. That is a
    one-step replay and not a guess: all ``held`` buys inside ``calm_raisers`` and ``_fill`` is the
    ordering rule "a name already in the book sorts first", and one month of it is exactly what
    separates an entry from a hold. It reads no bar dated after ``data_date``.
    """
    b = book.calm.ann.base
    prev_date = control_draw.previous_decision_date(data_date)
    prev: list[str] = []
    if trend_on(prepared.history, prev_date, b.inner):
        prev = _raise_picks(prepared, _rows_on(prepared, members, prev_date, b.inner), prev_date,
                            frozenset(), book)
    now = _raise_picks(prepared, rows, data_date, frozenset(prev), book)
    return now, prev


def _parked(history: Mapping[str, History], rows: list[FactorRow], data_date: date,
            picks: list[str], book: CapParams) -> tuple[Target, ...]:
    """``choose``'s tail for an already-chosen list: ``1/top`` each, the rest parked in SPY.

    A copy of ``choose``'s last twelve lines and deliberately not a refactor of them: ``choose`` is
    the recorded path of six closed trials and this file does not touch it. An empty ``picks``
    parks the whole book in SPY, which is what the controlled arm does on a month with no raiser.
    """
    b = book.calm.ann.base
    top = b.inner.top
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(top)
    out: list[Target] = []
    for s in picks:
        t = target_from_close(s, close[s], w)
        if t is not None:
            out.append(t)
    if b.park:
        rest = Decimal(1) - w * len(out)
        mh = history.get(b.market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(b.market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
    return tuple(out)


class MatchedCapPlaceboAllocator(SectorCappedRaiseAllocator):
    """M0215's frame filled by a churn-matched blind draw (amendment 1, 2026-10-19).

    The original placebo (``order="hash"``) re-keys its hash on the calendar *quarter* and sorts
    held names first, so its book changes about once a quarter: 179 trades against the 528 of the
    arm it controls, 0.34x, which D17 refuses. Its slot count was already the real book's own
    (``choose`` takes ``k = min(len(raisers), top)``), so the size axis was never the problem --
    only the stickiness was. This allocator keeps everything else and replaces that stickiness with
    the controlled arm's own: each decision session it replays that arm at this date and at the
    previous one, counts the names it *entered*, keeps all but that many of its own holdings in a
    date-free hash order, and draws the rest from the screened members in a month-keyed hash order,
    through the same ``_fill`` (and so the same FF12 cap). Entries match by construction; exits
    follow, because the book's size is the real arm's size that day and the placebo's previous size
    was the real arm's previous size.

    Everything else is ``SectorCappedRaiseAllocator``'s and so M0168's: the same ``prepare``, the
    same ``prepare_market``, the same ``market_fields = ("dividends",)``, the same SPY-200 switch,
    the same SPY parking, the same ``1/20`` slots, the same screened member pool, the same seed.

    A new id, ``M0215-A1``: a trial's configuration is its rules, its allocator id and its params,
    and the six recorded M0215 configurations keep the digests they were recorded under.
    """

    id = "M0215-A1"

    def lookback(self, params: Any) -> int:
        return control_draw.lookback_for(CAPPED.lookback(_check_matched(params)))

    def symbols(self, params: Any) -> tuple[str, ...]:
        return CAPPED.symbols(_check_matched(params))

    def holds(self, params: Any) -> tuple[str, ...]:
        return CAPPED.holds(_check_matched(params))

    def uses_members(self, params: Any) -> bool:
        return CAPPED.uses_members(_check_matched(params))

    def _run(self, prepared: Any, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Any) -> tuple[Target, ...]:
        book = _check_matched(p)
        b = book.calm.ann.base
        if len(prepared.calendar) == 0:  # no panel: target nothing (market-aware contract)
            return ()
        if not trend_on(prepared.history, data_date, b.inner):
            return ()
        rows = _rows_on(prepared, members, data_date, b.inner)
        now, prev = _target_shape(prepared, members, rows, data_date, book)
        n = len(now)
        pool = sorted(r.symbol for r in rows if r.symbol not in EXCLUDED and r.symbol != b.market)
        keep, tail = control_draw.matched_partition(
            pool=pool, held=held, keep_n=max(0, n - control_draw.churn(now, prev)),
            tag="M0215", seed=book.seed, data_date=data_date,
        )
        # keep + tail is the whole pool in take order, fresh names ahead of dropped holdings;
        # `_fill` truncates it to n under the FF12 cap, exactly as it truncates the raise order.
        return _parked(prepared.history, rows, data_date,
                       _fill(keep + tail, data_date, n, book.cap), book)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._run(RaisePrepared(history, None, EMPTY_DIVIDENDS), members, data_date, held,
                         _check_matched(params))

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, RaisePrepared):
            raise TypeError(f"prepared must be RaisePrepared, got {type(prepared).__name__}")
        return self._run(prepared, members, data_date, held, _check_matched(params))


MATCHED = MatchedCapPlaceboAllocator()


def _v(suffix: str, params: CapParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0215-{suffix}", family="M0215", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPPED, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


AMENDED = date(2026, 10, 19)


def _a1(suffix: str, params: CapParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never
    inferred. It is what pairs each new arm with the right old one here -- ``HASH`` and
    ``HASH-CAP4`` BOTH resolve to ``M0215-CTRL``, so a rule that matched targets would have let
    ``CTRL-PLC`` excuse the capped arm as well, which was never scored against ``CTRL`` in
    spirit."""
    return Candidate(id=f"M0215-{suffix}", family="M0215", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_DRAW_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "Both hash-order placebos trade a third as often as the books they control (179 against "
        "528 and 500: 0.34x trades, 0.43x turnover), so neither quoted lead is evidence -- "
        "re-draw each to the shape of the arm it actually controls"
    ),
    hypothesis=(
        "Written and committed before the run. M0215's two placebos re-key their hash on the "
        "calendar quarter (`draw`) and sort held names first (`choose`), a double stickiness, so "
        "each turned over 179 times in twenty years against M0215-CTRL's 528 and M0215-CAP4's "
        "500 -- 0.34x trades and 0.43x turnover, outside the [0.50, 2.00] band D17 refuses on. "
        "Their slot count was already the raise book's own (k = min(len(raisers), top)), so the "
        "size axis was matched and only the churn was not; that is all this amendment changes. "
        "CTRL-PLC and CAP4-PLC keep the whole frame -- the SPY-200 switch, the SPY parking, "
        "twenty 1/20 slots, the screened member pool, the FF12 cap where the controlled arm has "
        "one, seed 1 -- and take their entry count each month from the arm each one controls, "
        "keeping the rest of the book in a date-free hash order. They also repair a resolution: "
        "HASH-CAP4 today resolves to CTRL because its own stem is a placebo, while the book it "
        "exists to price is CAP4; CTRL-PLC and CAP4-PLC resolve to CTRL and CAP4 on the "
        "sibling-stem rung. Three predictions, in trial_funding.mwr against SPY TR 7.19%/yr on "
        "the same deposits. (1) SHAPE: both arms land inside 0.80-1.25 of their own target on "
        "both axes -- CTRL-PLC near 528 trades and 4.78 turnover, CAP4-PLC near 500 and 4.56. "
        "(2) DIRECTION: an honestly-shaped blind book trades about three times as often and pays "
        "about three times the Gotrade fee bill, so both new arms earn LESS than the 8.66% and "
        "8.62% the sticky draws recorded, and both quoted leads WIDEN -- CTRL's +1.96 points over "
        "its placebo and CAP4's +1.72 each grow by between 0.3 and 1.5 points a year. (3) THE "
        "SUCCESS CONDITION: this method's own bar is a difference between two placebos ('its gain "
        "over CTRL is larger than HASH-CAP4's over HASH'), so re-drawing the pair re-states the "
        "verdict and not merely a margin. The real half does not move -- CAP4 minus CTRL is -0.28 "
        "points and stays there. The placebo half, -0.04 today, is predicted to stay within 0.15 "
        "points of zero, because a cap of four over twenty slots drawn blind from the whole "
        "screened pool binds in far fewer months than it does on a book that is 25% banks and 19% "
        "retailers. So the re-stated condition, -0.28 > (CAP4-PLC minus CTRL-PLC), still FAILS by "
        "roughly the 0.2 to 0.3 points it fails by today, and M0215's standing verdict survives "
        "its honest control unchanged."
    ),
    expected_failure=(
        "The honest draws may earn MORE, not less. The quarter-keyed draw froze a 2008-era book it "
        "could not exit and fell 21.9% against CTRL's 18.7%; a book re-drawn every month rides the "
        "recovery and pays its fees out of a bigger number, so both leads could NARROW or reverse. "
        "If they do, the finding is that the +1.96 in this file was an artifact of a handicapped "
        "opponent and that the frame -- twenty equal slots behind the SPY-200 switch with the rest "
        "parked in SPY -- is what the book earns, not the raise signal. That is reported as the "
        "finding and not re-drawn (design section 4). Second, the churn match is estimated rather "
        "than known: one candidate's allocator cannot see another's held set, so the previous "
        "decision session is replayed from an empty book and fed forward one step, and if that "
        "one-step replay mis-states the entry count the ratios miss the 0.80-1.25 match band. The "
        "measured ratios are then recorded and the work stops; the seed and the re-key period are "
        "not dials. Third, a cap of four may bind more often on a blind draw than predicted if the "
        "screened pool is itself concentrated, which would make the placebo half of the "
        "difference-in-differences larger than 0.15 points and could flip the re-stated condition "
        "on what is noise rather than a cap effect -- in which case the honest reading is that "
        "twenty names cannot resolve a 0.3 point cap effect at all. Fourth, the extra replay "
        "roughly triples the allocator's per-session work: the run is slower and nothing else."
    ),
    candidates=(
        _a1("CTRL-PLC", CapParams(C63, None, "hash", 1),
            "Placebo, re-drawn to M0215-CTRL's own shape: as many slots and as many fresh names "
            "each month as the uncapped raise book, filled in hash order by members that know "
            "nothing about dividends",
            supersedes=("M0215-HASH",)),
        _a1("CAP4-PLC", CapParams(C63, 4, "hash", 1),
            "Placebo capped at 4 per industry, re-drawn to M0215-CAP4's own shape and filled in "
            "hash order, to price what a cap does to any book this shape",
            supersedes=("M0215-HASH-CAP4",)),
    ),
)


METHOD = Method(
    id="M0215",
    name="Dividend raisers with a sector cap: no more than a few utilities or banks in the book",
    family="stock-dividend-change-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0168 (CTRL = M0088-C-LIVE-63); Sera batch 20261017-2050 (sector caps); "
        "FF12 industries from SEC EDGAR SIC (Ken French's Siccodes12); Michaely, Thaler & Womack "
        "(1995), JF 50(2); placebo after M0187"
    ),
    parent_id="M0168",
    hypothesis=(
        "Published 1995 (dividend-change drift) and 2006 (low volatility); sector caps are "
        "standard practice, not an anomaly. M0168-CTRL (= M0088-C-LIVE-63: big raisers seen on "
        "the ex-date, held while the raise is under 182 days old, calm half of the live raisers "
        "by 63-session swing, up to 20 F4-screened members at 5%, held first then newest event, "
        "rest in SPY, monthly, behind the SPY-200 switch, fractional at Gotrade's real fees on "
        "the owner's deposits) beats SPY on dev (+10.6% vs +7.2% funded, 18.7% worst fall) but "
        "wins 2 of 4 walk-forward folds and lags SPY by 2.6 points a year in 2009-2015. A replay "
        "of that recorded configuration before this file was written (528 trades reproduced) "
        "shows the book is concentrated: 9.5 names on average, banks and finance 25% of slot-"
        "months and retailers 19% (utilities only 4%, so the idea row's 'utilities' guess is "
        "wrong and banks are the real lean), and one industry holds more than 3/4/5 names in "
        "78/45/22 of 169 invested months. Cap each FF12 industry at 3, 4 or 5 names (unknowns "
        "share one capped bucket), walking the parent's order; a skipped raiser's slot goes to "
        "the next raiser or to SPY, as the parent parks. Variants: CTRL (no cap; must reproduce "
        "M0168-CTRL: 528 trades, 18.7%, +35.1% CAGR), CAP3, CAP4, CAP5, and a placebo of the "
        "same frame and month-by-month exposure filled with hash-ordered screened members, "
        "uncapped (HASH) and capped at 4 (HASH-CAP4). Success: a capped variant beats CTRL "
        "funded with the worst fall at or under 20%, a positive or less negative 2009-2015 edge "
        "and a majority of folds, and its gain over CTRL is larger than HASH-CAP4's over HASH "
        "(so the cap helps the raise book specifically). Assumption: unfilled slots park in "
        "SPY, not cash, because that is the parent's shape."
    ),
    expected_failure=(
        "The 2009-2015 lag is the SPY-200 switch selling in the 2010, 2011 and 2015 dips "
        "(M0096's diagnosis), which no rule about which raisers to hold touches, so the folds "
        "likely stay 2 of 4 and the era gap near -2.6 points. Banks were the book's lean in "
        "2007-2009 too: a cap may cut the 2008 hit (the switch was mostly out by then, so maybe "
        "not much) but it also moves capped slots into SPY, so a capped book drifts toward SPY "
        "and its lead shrinks along with its risk -- a cap that 'helps' by turning the book "
        "into more SPY is not a better picker, and the placebo pair is there to show that. "
        "The cap binds in a minority of months (45 of 169 at 4), so CAP5 and maybe CAP4 are "
        "near-nulls. The hash placebo likely earns about as much as the raise book (as M0187's "
        "did for its frame), which would say the frame, not the raise signal, is the lead. A "
        "widely published 1990s anomaly: a dev edge is likely to fade after 2015. EDGAR's SIC "
        "is latest, not point in time; dividends' withholding tax is not modelled; survivorship "
        "flatters dividend books."
    ),
    candidates=(
        _v("CTRL", CapParams(C63, None),
           "Paired control: no sector cap (= M0168-CTRL = M0088-C-LIVE-63)"),
        _v("CAP3", CapParams(C63, 3), "At most 3 calm raisers from any one FF12 industry"),
        _v("CAP4", CapParams(C63, 4), "At most 4 calm raisers from any one FF12 industry"),
        _v("CAP5", CapParams(C63, 5), "At most 5 calm raisers from any one FF12 industry"),
        _v("HASH", CapParams(C63, None, "hash", 1),
           "Placebo: as many slots as the raise book fills, filled with hash-ordered members"),
        _v("HASH-CAP4", CapParams(C63, 4, "hash", 1),
           "Placebo capped at 4 per industry, to price what a cap does to any book this shape"),
    ),
    seen_keys=(
        "concept:dividend-increase-drift",
        "concept:dividend-change",
        "concept:low-volatility-filter",
        "concept:sector-cap",
        "concept:hash-order-yardstick",
    ),
    amendments=(MATCHED_DRAW_AMENDMENT,),
)
