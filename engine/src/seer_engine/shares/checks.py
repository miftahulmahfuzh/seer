"""Validation of the parsed cover counts: what makes them trustworthy enough to rank on.

A parser that reads free text will sometimes read the wrong number -- a subsidiary's count, a
figure in thousands, the non-affiliates' shares, a post-split pro forma. Each check below is an
independent witness, and every value a witness objects to ends in exactly one of two places:
**fixed** (kept, changed, and ``note`` says from what and why) or **excluded** (listed with its
reason in the excluded csv). Flagged-and-explained values that no witness can refute are kept
with the explanation in ``note``. Nothing flagged is kept silently.

1. **XBRL overlap** (2009-2010). Where the same accession carries a tagged
   ``dei:EntityCommonStockSharesOutstanding``, the two readings of one cover must agree within
   :data:`XBRL_TOL` (or the tag must equal one of the classes read, for filers that tag a class).
   A disagreement is fixed to the tagged value: it is the filer's own reading of its own cover.
   The match rate on this overlap is the parser's measured accuracy.
2. **Series shape.** A filer's counts, restated in common share units with its split list
   (:func:`normalize`), move slowly: buybacks and option exercise are a few percent a quarter.
   A value that leaves both neighbours by more than :data:`SPIKE_JUMP` while they agree with each
   other within :data:`SPIKE_AGREE` is a misread (**spike**, excluded). A jump that persists
   (**level**) is a merger, a spin-off or an issuance and is kept, noted -- unless price says it
   is really a split the split list lacks, which is kept and noted as such.
3. **Split consistency.** Across a listed split the count must move by the split's ratio. Normalizing
   by the split list turns a count that failed to move into a level change of ``1/ratio`` at the
   split; that is flagged ``split_missing`` and the value adjudicated by the same neighbour rule.
4. **Implied market value.** ``shares x raw close`` on the as-of date (``prices``) must lie in
   :data:`MV_HARD` -- outside it no S&P 500 member has ever been -- or the value is excluded;
   outside :data:`MV_SOFT` it is flagged and kept only when the series around it agrees.

Pure: no network, clock or database. ``build`` feeds it parsed rows, XBRL facts and prices.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

#: Relative tolerance for an XBRL match.
XBRL_TOL = 0.005
#: A spike leaves both neighbours by more than this factor ...
SPIKE_JUMP = 1.20
#: ... while the neighbours agree with each other within this one.
SPIKE_AGREE = 1.10
#: A move between consecutive counts beyond this factor is a level change to explain.
LEVEL_JUMP = 1.25
#: Simple ratios a jump is tested against to recognise an unlisted split.
SPLIT_RATIOS = (2.0, 3.0, 1.5, 4.0, 5.0, 1.25, 1.333333, 2.5, 10.0)
SPLIT_TOL = 0.08
#: Implied market value bounds, USD.
MV_HARD = (2.0e7, 1.2e12)
MV_SOFT = (1.0e8, 7.0e11)


@dataclass
class Item:
    """One parsed cover count travelling through the checks. Mutable on purpose: each check
    adds its flags and notes, and may change ``shares`` (fix) or set ``excluded``."""

    cik: str
    accession: str
    filed: date
    as_of: date | None
    symbol: str
    form: str
    shares: int
    classes: tuple[tuple[str, int], ...]
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    excluded: str | None = None
    xbrl: float | None = None
    raw_close: float | None = None
    norm: float | None = None  # shares in common (split-normalized) units

    @property
    def counted(self) -> date:
        return self.as_of or self.filed

    @property
    def mv(self) -> float | None:
        return None if self.raw_close is None else self.shares * self.raw_close


@dataclass(frozen=True)
class Split:
    date: date
    ratio: float


# --- 1. XBRL --------------------------------------------------------------------------------


def xbrl_compare(item: Item, xbrl: float) -> tuple[bool, float]:
    """(match, relative error of the total) of a cover reading against a tagged value."""
    rel = item.shares / xbrl - 1.0
    if abs(rel) <= XBRL_TOL:
        return True, rel
    if any(abs(n / xbrl - 1.0) <= XBRL_TOL for _, n in item.classes):
        return True, rel
    return False, rel


#: Neighbouring filings (by count date) consulted to settle an XBRL disagreement.
NEIGHBOUR_DAYS = 200


def apply_xbrl(items: Sequence[Item], xbrl_by_accn: Mapping[str, float]) -> list[tuple[Item, bool, float]]:
    """Check every item whose accession has a tagged value, and settle each disagreement.

    The tag is not automatically right: measured on the 2009-2010 overlap, filers tagged the
    cover count with a scale error (AEP 2010: 479,437,027,000,000), a single class of several
    (Google), or a stale figure. So a disagreement is settled by the filer's own neighbouring
    filings (count dates within :data:`NEIGHBOUR_DAYS`): whichever reading sits within
    :data:`LEVEL_JUMP` of their median wins. The tag winning is a fix (``fixed_xbrl``); the
    cover winning keeps it, flagged ``xbrl_disagrees`` with the tagged figure in the note; with
    no neighbour to ask, or neither close, the cover reading stays flagged for the series
    checks to judge.
    """
    out: list[tuple[Item, bool, float]] = []
    for it in items:
        x = xbrl_by_accn.get(it.accession)
        if x is None or it.excluded:
            continue
        it.xbrl = x
        ok, rel = xbrl_compare(it, x)
        out.append((it, ok, rel))
        if ok:
            continue
        near = sorted(
            o.shares for o in items
            if o is not it and not o.excluded and abs((o.counted - it.counted).days) <= NEIGHBOUR_DAYS
        )
        ref = near[len(near) // 2] if near else None
        if ref and _ratio(x, ref) <= LEVEL_JUMP and _ratio(x, ref) < _ratio(it.shares, ref):
            it.flags.append("fixed_xbrl")
            it.notes.append(f"cover read {it.shares:,}; XBRL dei for the same filing says {int(x):,}, "
                            f"which agrees with the neighbouring filings ({ref:,})")
            it.shares = int(round(x))
            it.classes = ()
        else:
            it.flags.append("xbrl_disagrees")
            it.notes.append(f"XBRL dei for the same filing says {int(x):,}; "
                            + (f"the cover reading agrees with the neighbouring filings ({ref:,}), kept"
                               if ref and _ratio(it.shares, ref) <= LEVEL_JUMP
                               else "no neighbouring filing settles it; left to the series checks"))
    return out


# --- 2/3. series ----------------------------------------------------------------------------


def factor_after(splits: Sequence[Split], d: date) -> float:
    """Product of split ratios dated after ``d`` (restates a count dated ``d`` in final units)."""
    f = 1.0
    for s in splits:
        if s.date > d:
            f *= s.ratio
    return f


def normalize(items: Sequence[Item], splits: Sequence[Split]) -> None:
    for it in items:
        it.norm = it.shares * factor_after(splits, it.counted)


def _ratio(a: float, b: float) -> float:
    return max(a, b) / min(a, b)


def _simple(r: float) -> float | None:
    """The simple split ratio ``r`` (or its inverse) is close to, else None."""
    for k in SPLIT_RATIOS:
        for target in (k, 1.0 / k):
            if abs(math.log(r / target)) <= SPLIT_TOL:
                return target
    return None


#: A count stated in post-split shares ahead of a split may be dated this many days before it.
PRESPLIT_DAYS = 120


def _far(x: Item, y: Item, k: float = SPIKE_JUMP) -> bool:
    return _ratio(x.norm, y.norm) > k


def _presplit_fix(b: Item, ref: Item, splits: Sequence[Split]) -> bool:
    """Fix ``b`` when it is a count already in post-split shares but dated before the split
    (filers often state the count "after giving effect to" a split declared but not yet
    distributed). ``ref`` is a neighbour it should agree with. True when fixed."""
    for sp in splits:
        if b.counted < sp.date <= b.counted + timedelta(days=PRESPLIT_DAYS):
            if abs(math.log(b.norm / sp.ratio / ref.norm)) < math.log(SPIKE_AGREE):
                new = int(round(b.shares / sp.ratio))
                b.flags.append("fixed_presplit")
                b.notes.append(
                    f"cover stated {b.shares:,} as of {b.counted}, already in post-split shares of the "
                    f"{sp.ratio:g}-for-1 split on {sp.date}; restated as {new:,} pre-split shares to "
                    f"match its date"
                )
                b.classes = tuple((lab, int(round(n / sp.ratio))) for lab, n in b.classes)
                b.shares = sum(n for _, n in b.classes) if b.classes else new
                b.norm = b.norm / sp.ratio
                return True
    return False


def series_checks(items: Sequence[Item], splits: Sequence[Split]) -> None:
    """Spikes fixed or excluded, level changes explained (module docstring). ``items`` is one
    filer's rows; they are ordered here by count date, then filing date."""
    live = sorted((i for i in items if not i.excluded), key=lambda i: (i.counted, i.filed, i.accession))
    normalize(live, splits)
    # Spikes, repeatedly, so two adjacent misreads are both found. The ends of a series have one
    # neighbour, so they are judged against the next two, which must agree.
    changed = True
    while changed:
        changed = False
        live = [i for i in live if not i.excluded]
        n = len(live)
        for k in range(n):
            b = live[k]
            if 0 < k < n - 1:
                a, c = live[k - 1], live[k + 1]
            elif n >= 3 and k == 0:
                a, c = live[1], live[2]
            elif n >= 3 and k == n - 1:
                a, c = live[n - 2], live[n - 3]
            else:
                continue
            end = k in (0, n - 1)
            if (_far(b, a) and _far(b, c) and not _far(a, c, SPIKE_AGREE)
                    and (b.norm > a.norm) == (b.norm > c.norm)
                    # At an end a split-sized step may be a real split the list lacks; only the
                    # level checks below can tell, with price.
                    and not (end and _simple(b.norm / a.norm) is not None)):
                if _presplit_fix(b, a, splits):
                    changed = True
                    break
                b.excluded = (
                    f"spike: {b.shares:,} ({b.counted}) against neighbours {a.shares:,} ({a.counted}) "
                    f"and {c.shares:,} ({c.counted}) after splits"
                )
                changed = True
                break
    live = [i for i in live if not i.excluded]
    for k in range(1, len(live)):
        a, b = live[k - 1], live[k]
        r = b.norm / a.norm
        if _ratio(b.norm, a.norm) <= LEVEL_JUMP:
            continue
        nxt = live[k + 1] if k + 1 < len(live) else None
        simple = _simple(r)
        listed = [s for s in splits if a.counted < s.date <= b.counted]
        price_moved = (
            a.raw_close is not None and b.raw_close is not None and simple is not None
            and abs(math.log((b.raw_close / a.raw_close) * simple)) < math.log(1.35)
        )
        reverts = nxt is not None and not _far(nxt, a, LEVEL_JUMP) and _far(nxt, b, LEVEL_JUMP)
        if simple is not None and price_moved:
            b.flags.append("split_unlisted")
            b.notes.append(
                f"count moved x{r:.3f} from {a.counted} with the raw price moving inversely: "
                f"a {simple:g}-for-1 split the split list lacks"
            )
            for later in live[k:]:
                later.norm = later.norm / simple
        elif listed and abs(math.log(r * math.prod(s.ratio for s in listed))) < SPLIT_TOL:
            b.flags.append("split_missing")
            b.notes.append(
                f"count did not move across the listed split(s) "
                f"{', '.join(str(s.date) for s in listed)}: the earlier count was already stated "
                f"post-split, or the split list is wrong; kept, later counts re-based"
            )
            for later in live[k:]:
                later.norm = later.norm / r
        elif reverts:
            b.flags.append("unstable")
            b.excluded = (
                f"jump x{r:.3f} from {a.shares:,} ({a.counted}) reversed by the next filing "
                f"({nxt.shares:,}, {nxt.counted})"
            )
        else:
            b.flags.append("level")
            b.notes.append(
                f"count moved x{r:.3f} from {a.shares:,} ({a.counted}); "
                + ("the next filing does not reverse it" if nxt else "the filer's last report here")
                + ": a merger, spin-off, issuance or buyback"
            )


# --- 4. market value ------------------------------------------------------------------------


#: A count below this on an S&P 500 member's cover is a count printed in thousands.
THOUSANDS_BELOW = 2_000_000
#: The smallest total count an S&P 500 member can have.
MIN_MEMBER_SHARES = 1_000_000


def unit_checks(items: Sequence[Item]) -> None:
    """Before the series checks, so a unit error cannot pass for a spike or a level change.

    * A count under :data:`THOUSANDS_BELOW` whose implied market value is implausibly small and
      lands inside :data:`MV_SOFT` when read in thousands was printed in thousands without
      saying so (Nordstrom 2005-2007: "136,559 shares of common stock"): **fixed** x1000.
    * Any other count under :data:`MIN_MEMBER_SHARES` is **excluded**: no S&P 500 member has
      had fewer than a million shares, so it is a subsidiary's count, a class fragment or a unit
      error, whatever the price says (or when there is none).
    """
    for it in items:
        if it.excluded:
            continue
        mv = it.mv
        if (mv is not None and it.shares < THOUSANDS_BELOW and mv < MV_SOFT[0]
                and MV_SOFT[0] <= mv * 1000 <= MV_SOFT[1]):
            it.flags.append("fixed_thousands")
            it.notes.append(f"cover printed {it.shares:,} shares, a count in thousands; "
                            f"read as {it.shares * 1000:,}")
            it.shares *= 1000
            it.classes = tuple((lab, n * 1000) for lab, n in it.classes)
        elif it.shares < MIN_MEMBER_SHARES:
            it.excluded = f"count {it.shares:,} is below any S&P 500 member's ({MIN_MEMBER_SHARES:,})"


def mv_checks(items: Sequence[Item]) -> None:
    """Market-value bounds, judged together with the filer's other counts (after the series).

    * Outside :data:`MV_HARD`, the count is **excluded** -- unless another count of the same
      filer, within :data:`LEVEL_JUMP` of it in split-normalized units, prices inside
      :data:`MV_SOFT`: then the count agrees with a plausible neighbour and it is the price that
      day which is wrong (a vendor level error, a reverse-split-adjusted "raw" close), so it is
      kept, flagged ``price_suspect``.
    * Outside :data:`MV_SOFT` only, it is kept and flagged ``mv_extreme`` with the value noted.
    """
    def plausible(x: Item) -> bool:
        return x.mv is not None and not x.excluded and MV_SOFT[0] <= x.mv <= MV_SOFT[1]

    for it in items:
        if it.excluded or it.mv is None:
            continue
        mv = it.mv
        if not (MV_HARD[0] <= mv <= MV_HARD[1]):
            ok = [x for x in items if x is not it and plausible(x) and x.norm and it.norm
                  and _ratio(x.norm, it.norm) <= LEVEL_JUMP]
            if ok:
                it.flags.append("price_suspect")
                it.notes.append(f"implied market value ${mv / 1e9:,.3f}bn, but the count agrees with "
                                f"{ok[0].shares:,} ({ok[0].counted}), which prices plausibly: the raw "
                                f"close is wrong that day, the count is kept")
            else:
                it.excluded = f"implied market value ${mv / 1e9:,.3f}bn outside any S&P 500 member's"
        elif not (MV_SOFT[0] <= mv <= MV_SOFT[1]):
            it.flags.append("mv_extreme")
            it.notes.append(f"implied market value ${mv / 1e9:,.2f}bn; series consistent, kept")


def finalize(items: Sequence[Item]) -> None:
    """Flags without a note get one, so no flagged value is kept without its reason."""
    for it in items:
        if it.excluded:
            continue
        for f in it.flags:
            if f == "ambiguous" and not any("ambiguous" in n for n in it.notes):
                it.notes.append("ambiguous cover (several unlabeled counts); the one nearest "
                                "'outstanding' kept and confirmed by the series checks")
            if f == "no_date" and not any("no as-of" in n for n in it.notes):
                it.notes.append("no as-of date on the cover; the filing date stands in for it")
