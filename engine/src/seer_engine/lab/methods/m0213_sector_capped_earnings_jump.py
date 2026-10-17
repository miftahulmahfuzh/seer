"""M0213 — The filtered earnings-day book with a sector cap: no more than K picks per industry.

Source: variation of M0072-Z2-RAWRANK (Sera batch 20261017-2050, the sector-cap batch), the first
batch that can read sector labels at all (``seer_engine.sectors``: SEC EDGAR SIC per filer, mapped
to Ken French's 12 industries).

Why. M0072's best book buys the biggest raw three-day jumps among news days that were also large
for the stock's own swing. Earnings seasons are not even across industries: when one industry
reports a strong quarter, many of its members jump in the same few weeks and a ranking by jump
size can hand a 20-slot book eight or ten names from one industry. That is a hidden one-sector
bet, and a book whose edge is a sector bet is a different (and weaker) claim than a book whose
edge is picking news days. Capping each FF12 industry at K of the 20 slots separates the two: if
the capped book keeps its edge, the picking is the edge; if the edge vanishes under the cap, the
edge was the sector tilt.

The frame is M0072-Z2-RAWRANK's byte for byte (``ZParams(JUMP20, z_min=2, rank="raw")``: volume
>= 3x the 60-day median, up gap, three-day jump >= 4 points over SPY and >= 2 of the stock's own
daily swings, 60-session hold, 20 slots of 5%, SPY in the empty slots, the SPY-200 switch, the
monthly real-fee fractional preset). Two things change:

* ``cap``: after ranking (held names first, then by score) the slots are filled with
  ``sectors.select_capped``, which never relaxes the cap; a slot it cannot fill goes to the SPY
  park exactly as an empty slot always has in this frame (the idea row says "cash"; here the
  frame's empty slot is SPY, and keeping that is what makes the parent's trial the uncapped
  control). Held names count against the cap first, so a cap can drop a held name when its
  industry is already full -- the cap is a rule the book obeys every month, not only on entry.
* ``order``: ``"score"`` ranks new names by the raw jump as the parent did; ``"hash"`` ranks them
  by a fixed blake2b hash of (seed, symbol, year-month), as M0187's placebo did. The hash book
  draws from the same live-event pool, so it asks whether the jump-size ranking adds anything
  over "any qualifying news day", capped or not.

The sector is read for the data date (``SectorMap.sector_of(symbol, data_date)``). EDGAR's SIC is
the filer's latest, not point-in-time (the module docstring of ``sectors`` names the cases); that
can blur a cap but cannot leak prices. Unknown sectors share one capped bucket.

Pure: the sector map is vendored files loaded once per process, the hash is a function of its
inputs, and every price read is M0072's (bars dated <= the data date).
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

from seer_engine import sectors
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    StandardisedJumpAllocator,
    ZParams,
    ZPrepared,
    live_event,
)
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 17)

Z2_RAWRANK = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")  # M0072-Z2-RAWRANK's params exactly


@dataclass(frozen=True, slots=True)
class CapParams:
    """``z`` is M0072's event and book; ``cap`` the most slots one FF12 industry may hold (None for
    no cap); ``order`` ranks new names by ``"score"`` (the parent's ranking) or ``"hash"``."""

    z: ZParams
    cap: int | None = 4
    order: str = "score"
    seed: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.z, ZParams):
            raise TypeError(f"z must be ZParams, got {type(self.z).__name__}")
        if self.cap is not None and (isinstance(self.cap, bool) or not isinstance(self.cap, int)
                                     or self.cap < 1):
            raise ValueError(f"cap must be None or an int >= 1, got {self.cap!r}")
        if self.order not in ("score", "hash"):
            raise ValueError(f"order must be 'score' or 'hash', got {self.order!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError(f"seed must be an int, got {type(self.seed).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"cap": "none" if self.cap is None else str(self.cap), "order": self.order,
               "seed": str(self.seed), "sectors": "ff12-edgar-latest-sic",
               "hash": "blake2b-8"}
        for k, v in self.z.as_dict().items():
            out[f"z.{k}"] = v
        return out


def _check(params: object) -> CapParams:
    if not isinstance(params, CapParams):
        raise TypeError(f"params must be CapParams, got {type(params).__name__}")
    return params


@lru_cache(maxsize=1)
def sector_map() -> sectors.SectorMap:
    """The vendored sector map, loaded once per process."""
    return sectors.load()


def draw(seed: int, symbol: str, data_date: date) -> int:
    """The control's score: a fixed 64-bit hash of seed, symbol and the month (M0187's)."""
    key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


class SectorCappedJumpAllocator(StandardisedJumpAllocator):
    """M0072's news-day book with at most ``cap`` slots per FF12 industry; the rest SPY."""

    id = "M0213"

    def lookback(self, params: Any) -> int:
        return super().lookback(_check(params).z)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return super().symbols(_check(params).z)

    def holds(self, params: Any) -> tuple[str, ...]:
        return super().holds(_check(params).z)

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def ranked(self, prepared: ZPrepared, rows: list[Any], data_date: date,
               held: frozenset[str], c: CapParams) -> list[str]:
        """Every symbol with a live event, held first, then by the variant's order."""
        p = c.z
        jp = p.jump
        live: list[tuple[int, float, str]] = []
        for r in rows:
            h = prepared.history.get(r.symbol)
            if h is None or r.symbol == jp.market:
                continue
            i = h.index_of(data_date)
            got = prepared.cols(r.symbol, jp.market, jp.vol_base, p.sd_base)
            if i is None or got is None:
                continue
            ev = live_event(got[0], got[1], i, p)
            if ev is None:
                continue
            if c.order == "hash":
                score = -float(draw(c.seed, r.symbol, data_date))
            else:
                score = ev[0] if p.rank == "z" else ev[1]
            live.append((0 if r.symbol in held else 1, -score, r.symbol))
        return [s for _, _, s in sorted(live)]

    def picks(self, prepared: ZPrepared, rows: list[Any], data_date: date,
              held: frozenset[str], c: CapParams) -> list[str]:
        order = self.ranked(prepared, rows, data_date, held, c)
        top = c.z.jump.inner.top
        if c.cap is None:
            return order[:top]
        return sectors.select_capped(order, data_date, top, c.cap, sector_map().sector_of)

    def _targets(self, prepared: ZPrepared, rows: list[Any], data_date: date,
                 held: frozenset[str], p: Any) -> tuple[Target, ...]:
        c = _check(p)
        jp = c.z.jump
        w = equal_weight(jp.inner.top)
        out: list[Target] = []
        for s in self.picks(prepared, rows, data_date, held, c):
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        if jp.park:
            rest = Decimal(1) - w * len(out)
            mh = prepared.history.get(jp.market)
            if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
                t = target_from_close(jp.market, last_close(mh, data_date), rest)
                if t is not None:
                    out.append(t)
        return tuple(out)

    def targets(self, history: Mapping[str, Any], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        c = _check(params)
        if not trend_on(history, data_date, c.z.jump.inner):
            return ()
        rows = factor_rows(history, members, data_date, c.z.jump.inner)
        return self._targets(ZPrepared(history, None), rows, data_date, held, c)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        c = _check(params)
        if not trend_on(prepared.history, data_date, c.z.jump.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, c.z.jump.inner)
        return self._targets(prepared, rows, data_date, held, c)


CAPJUMP = SectorCappedJumpAllocator()


def _v(suffix: str, params: CapParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0213-{suffix}", family="M0213", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=CAPJUMP, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0213",
    name="Earnings-day book with a sector cap: the filtered news-day picks, no more than a few "
         "from any one industry",
    family="stock-event-drift",
    source_kind="variation",
    source_ref="variation of M0072-Z2-RAWRANK (Brandt, Kishore, Santa-Clara & Venkatachalam 2008, "
               "SSRN 909563); industries are Fama-French 12 from SEC EDGAR SIC codes; the hash-order "
               "control is M0187's placebo order",
    parent_id="M0072",
    hypothesis=(
        "Published 2008 (earnings-day drift), so the dev window can only show the edge from before "
        "and just after it was widely known; 2009-2015 is judged first. M0072-Z2-RAWRANK (news days "
        "on 3x volume with an up gap, a three-day jump >= 4 points over SPY and >= 2 of the stock's "
        "own daily swings, the 20 biggest raw jumps held 60 sessions at 5% each, rest SPY, SPY-200 "
        "switch, monthly, fractional at Gotrade's real fees) earned +12.3% a year on the owner's "
        "deposits vs +7.2% for SPY, DSR 0.914 at N=59, beat SPY by ~3.7 points a year in 2009-2015, "
        "and failed only the worst fall (23.8% funded, 1998). Earnings seasons cluster by industry, "
        "so a ranking by jump size can fill the book from one industry that just reported well: a "
        "hidden sector bet. Cap each Fama-French 12 industry at 3, 4 or 5 of the 20 slots (held "
        "names count first; slots the cap leaves empty go to SPY, as the frame's empty slots always "
        "have). The uncapped control is the parent's recorded trial M0072-Z2-RAWRANK (same frame, "
        "fees and deposits), not re-run. A hash-order control draws new names from the same live "
        "news-day pool in a fixed meaningless order (M0187's hash), uncapped and capped at 4, to "
        "ask whether ranking by jump size adds anything over 'any qualifying news day'. Variants: "
        "CAP3, CAP4, CAP5, HASH, HASH-CAP4. Expectation: CAP4 keeps most of the parent's edge "
        "(within ~1 point a year), the fall shrinks a little because a one-industry slump hits "
        "fewer slots, and 2009-2015 stays ahead of SPY; the hash books trail the score books by "
        "1-2 points a year. If the capped books lose the edge, the edge was a sector bet. Success: "
        "a capped variant with worst fall under the bar, beating total-return SPY with DSR >= 0.90 "
        "and beating SPY in 2009-2015 and in a majority of walk-forward folds."
    ),
    expected_failure=(
        "The parent's worst fall was 1998, a market-wide fall caught late by the monthly SPY-200 "
        "switch, not a one-industry slump; a sector cap cannot fix timing, so the fall likely stays "
        "above 20%. If the jump ranking's best picks cluster in tech in 1998-2000 and 2009-2013, "
        "the cap removes exactly the names that earned the edge and the excess over SPY shrinks, "
        "dragging the luck score under 0.90. A tight cap (3) leaves slots to SPY in hot seasons, "
        "drifting the book toward plain SPY. EDGAR's SIC is the latest, not point-in-time, so a "
        "few companies that changed trade sit in the wrong bucket. The hash control may earn as "
        "much as the ranked book, meaning the frame (news days at all, plus the SPY park) rather "
        "than the ranking carries the edge. And this is a published anomaly, so a strong dev result "
        "may have faded in 2016-2026; its kin (the momentum books that failed their looks) may "
        "move with it."
    ),
    candidates=(
        _v("CAP3", CapParams(Z2_RAWRANK, cap=3),
           "Parent's best book, at most 3 of 20 slots per industry; slots the cap leaves empty go to SPY"),
        _v("CAP4", CapParams(Z2_RAWRANK, cap=4),
           "At most 4 of 20 slots per industry"),
        _v("CAP5", CapParams(Z2_RAWRANK, cap=5),
           "At most 5 of 20 slots per industry: the loosest cap"),
        _v("HASH", CapParams(Z2_RAWRANK, cap=None, order="hash"),
           "Control: the same news-day pool picked in a fixed meaningless order, no cap"),
        _v("HASH-CAP4", CapParams(Z2_RAWRANK, cap=4, order="hash"),
           "Control: the same pool in hash order, capped at 4 per industry like CAP4"),
    ),
    seen_keys=(
        "concept:sector-capped-earnings-jump",
        "concept:industry-concentration-cap",
        "concept:earnings-season-industry-clustering",
    ),
)
