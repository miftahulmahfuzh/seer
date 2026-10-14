"""Point-in-time universe membership from month-end dollar-volume ranks.

**Why this module exists.** Every lab method so far ranks the twenty most-traded members of the
S&P 500 or Nasdaq-100, whose membership comes from vendored index snapshots
(``membership.py``). Those snapshots cover large caps and nothing else, so a universe reaching
further down the liquidity ladder cannot be expressed with them at all -- there is no index to
read. This module derives membership from what the market itself did: a symbol is a member on the
days following a month-end at which its dollar volume ranked inside the band.

**The point-in-time rule, and why the obvious shortcut is wrong.** A symbol's rank on month-end
``M`` is known on ``M``, so it may govern membership only from ``M`` until the next sample. It is
tempting instead to keep every symbol that *ever* held the band and screen later, or to require a
symbol to hold the band for a year before admitting it -- both read the future. The second is the
more seductive: it halves the store and looks like prudence. It would mean a name briefly liquid
in 2001 is absent from the 2001 cross-section **because of what happened to it afterwards**, which
is the same shape of error as judging a strategy on a price history that quietly drops the
companies that went bankrupt.

So: no persistence filter, no minimum lifetime, no survivorship screen. A symbol enters on the
first month-end it ranks inside the band and leaves on the first month-end it does not.

**Intervals are ``[start, end)``**, matching ``membership.Interval`` so every downstream reader --
``survivorship.member_sessions`` above all -- works unchanged. ``end`` is ``None`` while the symbol
still holds the band at the last sample.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

#: The rank band this universe admits. 1-2000 keeps the large caps alongside the small ones so a
#: method built here can be compared with one built on the index store, rather than only with
#: other new methods.
DEFAULT_BAND = (1, 2000)


@dataclass(frozen=True, slots=True)
class Sample:
    """One month-end cross-section: the rank each code held on ``sample_date``."""

    sample_date: date
    ranks: dict[str, int]


def read_samples(path: Path) -> list[Sample]:
    """The month-end rank CSV, ascending by date. One row per (date, code)."""
    byday: dict[date, dict[str, int]] = defaultdict(dict)
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d = date.fromisoformat(row["sample_date"])
            byday[d][row["code"]] = int(row["rank"])
    return [Sample(d, byday[d]) for d in sorted(byday)]


def intervals(
    samples: Iterable[Sample],
    band: tuple[int, int] = DEFAULT_BAND,
    index_id: str = "DVOL",
) -> list[tuple[str, str, date, date | None]]:
    """``(index_id, symbol, start, end)`` rows, ``end`` exclusive and ``None`` while still in.

    A symbol's membership begins on the sample at which it first ranks inside ``band`` and ends on
    the first later sample at which it does not. A symbol that leaves and returns gets two
    intervals, which is correct and is why this cannot be collapsed to first-and-last seen.
    """
    lo, hi = band
    samples = list(samples)
    open_since: dict[str, date] = {}
    out: list[tuple[str, str, date, date | None]] = []
    for s in samples:
        inside = {c for c, rk in s.ranks.items() if lo <= rk <= hi}
        for code in sorted(set(open_since) - inside):          # left the band
            out.append((index_id, code, open_since.pop(code), s.sample_date))
        for code in sorted(inside - set(open_since)):          # entered the band
            open_since[code] = s.sample_date
    for code in sorted(open_since):                            # still in at the last sample
        out.append((index_id, code, open_since[code], None))
    out.sort(key=lambda r: (r[1], r[2]))
    return out


def members_on(rows: Iterable[tuple[str, str, date, date | None]], d: date) -> set[str]:
    """Symbols whose membership covers ``d`` -- ``start <= d < end``."""
    return {sym for _i, sym, start, end in rows if start <= d and (end is None or d < end)}
