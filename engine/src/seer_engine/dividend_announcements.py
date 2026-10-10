"""Match vendor dividend declaration dates onto the research store's own dividends.

Pure. The store's ``dividends.csv`` stays the record of *what* was paid and *when it went ex*;
this module only attaches the day each of those payments was announced, when a vendor knows it.
The rules are deliberately conservative, because a declaration date that is too early would let
a backtest act on news before it was public:

- a store dividend is matched to the vendor row with the same ex-date, else to the nearest
  unused vendor row within ``MAX_EX_GAP_DAYS`` calendar days (vendors disagree by a day now and
  then);
- the declaration must fall on or before the store's ex-date, and no more than
  ``MAX_LEAD_DAYS`` before it -- anything else is refused, counted, and left undated;
- a dividend with no acceptable match stays undated: the lab then knows it only from its
  ex-date, exactly as before. Nothing is ever estimated.

The vendor's amount is never used: matching on the ex-date alone keeps the store's
split-adjusted amount and survives the two sources adjusting differently. A ticker that a later
company reused shows up here as dividends that do not line up, and simply fails to match.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from statistics import median

from seer_engine.eodhd import Declaration

MAX_EX_GAP_DAYS = 4
MAX_LEAD_DAYS = 180


@dataclass(frozen=True)
class YearCoverage:
    year: int
    dividends: int
    dated: int
    median_lead_days: float | None

    @property
    def fraction(self) -> float:
        return self.dated / self.dividends if self.dividends else 0.0


@dataclass(frozen=True)
class MatchResult:
    rows: tuple[tuple[str, date, date], ...]  # (symbol, store ex_date, declared), sorted
    years: tuple[YearCoverage, ...]
    no_vendor_rows: tuple[str, ...]  # store symbols with dividends but nothing from the vendor
    refused_lead: int = 0  # matched, but declared after the ex-date or too long before it
    undated_by_vendor: int = 0  # matched, but the vendor row carries no declaration date
    unmatched: int = 0  # no vendor row near the store's ex-date
    symbols_considered: int = 0
    skipped_symbols: tuple[str, ...] = field(default_factory=tuple)

    @property
    def dividends(self) -> int:
        return sum(y.dividends for y in self.years)

    @property
    def dated(self) -> int:
        return sum(y.dated for y in self.years)

    @property
    def fraction(self) -> float:
        return self.dated / self.dividends if self.dividends else 0.0


def _nearest(ex_date: date, vendor: Sequence[Declaration], used: set[int]) -> int | None:
    best: int | None = None
    best_gap = MAX_EX_GAP_DAYS + 1
    for i, row in enumerate(vendor):
        if i in used:
            continue
        gap = abs((row.ex_date - ex_date).days)
        if gap < best_gap:
            best, best_gap = i, gap
    return best


def match(
    store_dividends: Mapping[str, Mapping[date, Decimal]],
    vendor: Mapping[str, Sequence[Declaration] | None],
    *,
    skip: Collection[str] = (),
    years: tuple[int, int] = (1996, 2015),
) -> MatchResult:
    """Attach vendor declaration dates to ``store_dividends``; report coverage per year.

    ``vendor`` maps a store symbol to its vendor rows (None or absent: nothing downloaded).
    ``skip`` names symbols left out of the match and the report alike (the ETFs: an index fund's
    payout is not a company's decision). ``years`` bounds the coverage table, not the match.
    """
    rows: list[tuple[str, date, date]] = []
    per_year: dict[int, list[int]] = {}  # year -> [dividends, dated]
    leads: dict[int, list[int]] = {}
    no_vendor: list[str] = []
    refused = undated = unmatched = 0
    considered = 0
    for symbol in sorted(store_dividends):
        if symbol in skip:
            continue
        considered += 1
        theirs = sorted(vendor.get(symbol) or (), key=lambda d: d.ex_date)
        if not theirs:
            no_vendor.append(symbol)
            for ex_date in store_dividends[symbol]:
                if years[0] <= ex_date.year <= years[1]:
                    per_year.setdefault(ex_date.year, [0, 0])[0] += 1
            continue
        by_ex = {row.ex_date: i for i, row in enumerate(theirs)}
        used: set[int] = set()
        for ex_date in sorted(store_dividends[symbol]):
            in_table = years[0] <= ex_date.year <= years[1]
            if in_table:
                per_year.setdefault(ex_date.year, [0, 0])[0] += 1
            i = by_ex.get(ex_date)
            if i is None or i in used:
                i = _nearest(ex_date, theirs, used)
            if i is None:
                unmatched += 1
                continue
            used.add(i)
            declared = theirs[i].declared
            if declared is None:
                undated += 1
                continue
            lead = (ex_date - declared).days
            if lead < 0 or lead > MAX_LEAD_DAYS:
                refused += 1
                continue
            rows.append((symbol, ex_date, declared))
            if in_table:
                per_year[ex_date.year][1] += 1
                leads.setdefault(ex_date.year, []).append(lead)
    table = tuple(
        YearCoverage(
            year=y,
            dividends=per_year.get(y, [0, 0])[0],
            dated=per_year.get(y, [0, 0])[1],
            median_lead_days=float(median(leads[y])) if leads.get(y) else None,
        )
        for y in range(years[0], years[1] + 1)
    )
    return MatchResult(
        rows=tuple(sorted(rows)),
        years=table,
        no_vendor_rows=tuple(no_vendor),
        refused_lead=refused,
        undated_by_vendor=undated,
        unmatched=unmatched,
        symbols_considered=considered,
        skipped_symbols=tuple(sorted(s for s in store_dividends if s in skip)),
    )


def format_report(result: MatchResult) -> str:
    """The coverage table the owner reads before deciding the paid month was worth it."""
    lines = [
        "Dividend announcement dates matched onto the research store",
        "",
        f"{'year':>4}  {'dividends':>9}  {'dated':>6}  {'share':>6}  {'median days ahead of ex':>24}",
    ]
    for y in result.years:
        lead = "-" if y.median_lead_days is None else f"{y.median_lead_days:.0f}"
        lines.append(
            f"{y.year:>4}  {y.dividends:>9}  {y.dated:>6}  {y.fraction:>6.1%}  {lead:>24}"
        )
    lines += [
        "",
        f"overall: {result.dated} of {result.dividends} dividends dated ({result.fraction:.1%})",
        f"symbols considered: {result.symbols_considered} "
        f"(ETFs left out: {len(result.skipped_symbols)})",
        f"symbols with no vendor rows: {len(result.no_vendor_rows)}"
        + (f" ({', '.join(result.no_vendor_rows[:20])}{' ...' if len(result.no_vendor_rows) > 20 else ''})"
           if result.no_vendor_rows else ""),
        f"left undated: {result.unmatched} with no vendor row near the ex-date, "
        f"{result.undated_by_vendor} where the vendor has no declaration date, "
        f"{result.refused_lead} refused (declared after the ex-date or over "
        f"{MAX_LEAD_DAYS} days before it)",
        f"rows to write (all years in the store): {len(result.rows)}",
    ]
    return "\n".join(lines)
