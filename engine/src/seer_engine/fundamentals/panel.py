"""Point-in-time selection over raw XBRL facts: the panel the lab ranks on.

``fundamental_facts`` stores every fact EDGAR served, restatements included (plan invariant 3).
This module is the only place that decides *which* of them a backtest standing on day ``t`` is
allowed to see, and what metric they add up to. Pure: no database, network, clock or randomness
(tests/test_strategy_purity.py).

**The point-in-time rule.** ``filed`` is the availability date and the only one. ``period_end``
is never an availability date -- a Q4 figure for the period ending 2015-12-31 is typically filed
in February 2016, and a backtest that read it on 2015-12-31 would be trading on a number nobody
had. So every read starts by discarding every fact with ``filed > t``.

**Selection, and its deterministic tiebreak.** Among the visible facts of one concept, of one
period kind, sharing one ``period_end``, the chosen fact is the maximum of

    (filed, -rung, accn)

- **``filed`` descending** -- the latest restatement available at ``t``. This is the rule the
  user asked for: two facts sharing a ``period_end`` and differing in ``filed`` and ``accn``
  resolve to the earlier value at an earlier ``t`` and the later value afterwards.
- **``rung`` ascending** -- same period, same filing date, two different ladder tags: the
  preferred tag wins (``ladder.ConceptSpec.tags`` order).
- **``accn`` descending, lexicographically** -- two facts filed the same day under the same tag.
  An accession number is ``<filer>-<yy>-<serial>``, so the lexicographic maximum is the
  later-assigned accession. Arbitrary, but total and stable, which is all a tiebreak owes.

Selection is **per period**, not per symbol: the ladder preference is only the third key. That
is what makes an ASC 606 tag switch work. A filer that reported ``Revenues`` through 2017 and
``RevenueFromContractWithCustomerExcludingAssessedTax`` from 2018 has both tags visible in 2019;
the 2018 period simply has no ``Revenues`` fact, so the lower rung wins it on its own merits
while the 2017 period keeps the higher rung. No per-symbol tag is ever pinned.

**Fiscal labels are metadata.** ``fy`` and ``fp`` are stored and never read by the selection:
filers disagree about them across restatements and amended filings. A fact's period kind comes
from its own dates -- ``period_start is None`` is an instant, 80-100 days is a quarter, 330-400
days is a fiscal year. Anything else (a 6- or 9-month year-to-date figure) is dropped; this
module does not difference YTD facts.

**Flow metrics are annual.** ``Snapshot``'s income-statement and cash-flow figures are the
latest *fiscal year* visible at ``t``, not a trailing twelve months. Annual coverage is 8/8 in
the measured sample while a clean TTM needs four untroubled quarters, and mixing an annual basis
for some names with a TTM basis for others would put a systematic wedge through the
cross-section. Balance-sheet figures are the latest instant visible, which for cover-page shares
outstanding is usually within days of ``t``. The quarterly series exists -- it is what
``quarters`` builds and ``sue`` consumes -- it is just not what the level metrics use.

**Deriving an untagged Q4.** Most filers never tag a Q4 duration: the 10-K carries the fiscal
year and the three 10-Qs carry Q1-Q3. ``quarters`` reconstructs it as ``FY - (Q1 + Q2 + Q3)``
when the annual fact and exactly three quarters tiling its start are all visible, dating the
synthetic fact ``filed = max(filed of its four inputs)`` so it can never appear before its last
input did. EPS is not exactly additive across quarters (the diluted share count moves), so a
derived Q4 EPS is an approximation -- ``Obs.derived`` flags it and the docstring of
``SymbolFundamentals.quarters`` says so.

**A gap truncates.** The quarterly series is the longest run of quarters ending at the latest
visible one whose consecutive ``period_end`` steps are 60-120 days apart. A filer that skipped a
quarter, changed its fiscal year, or has a hole in the ingest keeps only the run after the hole;
everything older is unreachable until the hole is filled. ``sue`` then returns NaN whenever that
run is shorter than ``sue.MIN_QUARTERS``.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import numpy as np

from seer_engine.fundamentals import ladder
from seer_engine.fundamentals.sue import sue as sue_of

# The column order ``facts_from_rows`` expects. This is the contract with PHASE 6's projection,
# not with phase 2's table: `fundamental_facts` has no `symbol` column (facts are keyed by CIK),
# and phase 6's COPY joins `ticker_cik` to supply one. Phase 6 imports this tuple rather than
# restating it, so there is exactly one owner of the order. A row may also be a Mapping keyed
# by these names.
FACT_COLUMNS: tuple[str, ...] = (
    "symbol",
    "taxonomy",
    "tag",
    "unit",
    "period_start",
    "period_end",
    "val",
    "accn",
    "form",
    "fy",
    "fp",
    "filed",
)

KIND_QUARTER = "Q"
KIND_ANNUAL = "A"
KIND_INSTANT = "I"  # ladder.INSTANT is the spec kind; this is a fact's own classification

QUARTER_MIN_DAYS, QUARTER_MAX_DAYS = 80, 100  # inclusive day count of a fiscal quarter
ANNUAL_MIN_DAYS, ANNUAL_MAX_DAYS = 330, 400  # inclusive day count of a fiscal year
STEP_MIN_DAYS, STEP_MAX_DAYS = 60, 120  # period_end to period_end of consecutive quarters

GROSS_PROFIT_REPORTED = "reported"
GROSS_PROFIT_DERIVED = "derived"
GROSS_PROFIT_NONE = "none"

NAN = float("nan")


class FundamentalsError(ValueError):
    """A fact or a panel is malformed."""


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise FundamentalsError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _check_str(name: str, s: object) -> str:
    if not isinstance(s, str) or not s:
        raise FundamentalsError(f"{name} must be a non-empty str, got {s!r}")
    return s


@dataclass(frozen=True, slots=True)
class Fact:
    """One XBRL fact as EDGAR served it, for one symbol.

    ``period_start`` is None for an instant (a balance-sheet or cover-page figure). ``filed`` is
    the availability date and must not precede ``period_end``: a fact filed before its own
    period closed is look-ahead-shaped and is rejected rather than quietly trusted.
    """

    symbol: str
    taxonomy: str
    tag: str
    unit: str
    period_start: date | None
    period_end: date
    val: float
    accn: str
    form: str
    fy: int | None
    fp: str | None
    filed: date

    def __post_init__(self) -> None:
        _check_str("symbol", self.symbol)
        _check_str("taxonomy", self.taxonomy)
        _check_str("tag", self.tag)
        _check_str("unit", self.unit)
        _check_str("accn", self.accn)
        _check_str("form", self.form)
        _check_date("period_end", self.period_end)
        _check_date("filed", self.filed)
        if self.period_start is not None:
            _check_date("period_start", self.period_start)
            if self.period_start > self.period_end:
                raise FundamentalsError(
                    f"{self.symbol} {self.tag}: period_start {self.period_start} is after "
                    f"period_end {self.period_end}"
                )
        if self.filed < self.period_end:
            raise FundamentalsError(
                f"{self.symbol} {self.tag}: filed {self.filed} precedes period_end {self.period_end}"
            )
        if not isinstance(self.val, float):
            raise FundamentalsError(f"{self.symbol} {self.tag}: val must be a float, got {type(self.val).__name__}")
        if not np.isfinite(self.val):
            raise FundamentalsError(f"{self.symbol} {self.tag}: val must be finite, got {self.val!r}")
        if self.fy is not None and (isinstance(self.fy, bool) or not isinstance(self.fy, int)):
            raise FundamentalsError(f"{self.symbol} {self.tag}: fy must be an int or None, got {self.fy!r}")
        if self.fp is not None and not isinstance(self.fp, str):
            raise FundamentalsError(f"{self.symbol} {self.tag}: fp must be a str or None, got {self.fp!r}")

    def kind(self) -> str | None:
        """``KIND_INSTANT``, ``KIND_QUARTER``, ``KIND_ANNUAL``, or None for a duration that is neither."""
        if self.period_start is None:
            return KIND_INSTANT
        days = (self.period_end - self.period_start).days + 1
        if QUARTER_MIN_DAYS <= days <= QUARTER_MAX_DAYS:
            return KIND_QUARTER
        if ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
            return KIND_ANNUAL
        return None


def _to_float(name: str, v: object) -> float:
    if isinstance(v, bool):
        raise FundamentalsError(f"{name} must be a number, got a bool")
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    raise FundamentalsError(f"{name} must be a number, got {type(v).__name__}")


def fact_from_row(row: Mapping[str, object] | Sequence[object]) -> Fact:
    """A ``Fact`` from one ``fundamental_facts`` row: a Mapping, or a Sequence in ``FACT_COLUMNS`` order."""
    if isinstance(row, Mapping):
        missing = [c for c in FACT_COLUMNS if c not in row]
        if missing:
            raise FundamentalsError(f"row is missing {missing}")
        values = [row[c] for c in FACT_COLUMNS]
    elif isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
        if len(row) != len(FACT_COLUMNS):
            raise FundamentalsError(f"row has {len(row)} values, expected {len(FACT_COLUMNS)} {FACT_COLUMNS}")
        values = list(row)
    else:
        raise FundamentalsError(f"row must be a Mapping or a Sequence, got {type(row).__name__}")
    symbol, taxonomy, tag, unit, period_start, period_end, val, accn, form, fy, fp, filed = values
    # phase 2 stores `period_start = period_end` for an INSTANTANEOUS fact, because the column
    # is NOT NULL and sits in the primary key (one 10-K tags Revenues for both the fiscal year
    # and Q4 under the same accn/tag/unit/period_end, so the period must be keyed). In memory
    # an instant is `period_start is None`, which is what `Fact.kind()` and `quarters()` read.
    # This is the one place the two encodings meet. No us-gaap or dei DURATION fact has a
    # one-day period, so the mapping is lossless.
    if period_start is not None and period_start == period_end:
        period_start = None
    return Fact(
        symbol=symbol,  # type: ignore[arg-type]
        taxonomy=taxonomy,  # type: ignore[arg-type]
        tag=tag,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
        period_start=period_start,  # type: ignore[arg-type]
        period_end=period_end,  # type: ignore[arg-type]
        val=_to_float("val", val),
        accn=accn,  # type: ignore[arg-type]
        form=form,  # type: ignore[arg-type]
        fy=fy,  # type: ignore[arg-type]
        fp=fp,  # type: ignore[arg-type]
        filed=filed,  # type: ignore[arg-type]
    )


def facts_from_rows(
    rows: Iterable[Mapping[str, object] | Sequence[object]],
    *,
    skip_invalid: bool = True,
) -> tuple[tuple[Fact, ...], int]:
    """``(facts, skipped)`` from ``fundamental_facts`` rows.

    ``skip_invalid`` (the default) drops a malformed row and counts it, so one bad fact out of a
    million cannot fail a backtest's data load; the caller decides what to do with the count.
    ``skip_invalid=False`` raises ``FundamentalsError`` on the first bad row instead.
    """
    out: list[Fact] = []
    skipped = 0
    for row in rows:
        try:
            out.append(fact_from_row(row))
        except FundamentalsError:
            if not skip_invalid:
                raise
            skipped += 1
    return tuple(out), skipped


@dataclass(frozen=True, slots=True)
class Obs:
    """One selected observation: the value of a concept for one period, as known at some ``t``."""

    concept: str
    taxonomy: str
    tag: str
    period_start: date | None
    period_end: date
    filed: date
    accn: str
    val: float
    derived: bool = False


def _obs(concept: str, f: Fact) -> Obs:
    return Obs(concept, f.taxonomy, f.tag, f.period_start, f.period_end, f.filed, f.accn, f.val)


def _key(entry: tuple[Fact, int]) -> tuple[date, int, str]:
    f, rung = entry
    return (f.filed, -rung, f.accn)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything the factor layer reads about one symbol on one day.

    Every number is a float64; NaN means "not available at ``t``", never zero. Flow figures
    (``revenue`` .. ``diluted_shares``) are the latest **fiscal year** visible; balance figures
    (``assets``, ``equity``, ``shares_outstanding``) the latest **instant** visible. The two can
    and usually do have different ``period_end``s, which is correct: a balance sheet is newer
    than the fiscal year it closes.

    ``fiscal_period_end`` is the period end of the annual figures; ``filed`` the newest filing
    date behind any figure in the snapshot. ``observations`` maps concept name to the ``Obs``
    actually chosen, so a test or a report can say which tag and which accession a number came
    from. ``sue_quarters`` is the length of the contiguous quarterly EPS run behind ``sue``.
    """

    symbol: str
    asof: date
    fiscal_period_end: date | None
    filed: date | None
    revenue: float
    cost_of_revenue: float
    gross_profit: float
    gross_profit_basis: str
    operating_income: float
    net_income: float
    operating_cash_flow: float
    diluted_eps: float
    diluted_shares: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float
    sue_quarters: int
    observations: Mapping[str, Obs]

    def tag(self, concept: str) -> str | None:
        """The ladder tag behind ``concept`` in this snapshot, or None when it has no value."""
        o = self.observations.get(concept)
        return None if o is None else o.tag

    def value(self, concept: str) -> float:
        """``concept``'s value, or NaN. ``ladder.LadderError`` when the ladder has no such concept."""
        ladder.spec(concept)
        o = self.observations.get(concept)
        if o is None:
            return NAN
        return o.val


def _ratio(num: float, den: float) -> float:
    """``num / den``, NaN unless both are finite and ``den`` is non-zero."""
    if not np.isfinite(num) or not np.isfinite(den) or den == 0.0:
        return NAN
    return num / den


def gross_profitability(s: Snapshot) -> float:
    """Novy-Marx gross profitability: gross profit over total assets. NaN when either is missing."""
    return _ratio(s.gross_profit, s.assets)


def return_on_equity(s: Snapshot) -> float:
    """Net income over common equity. NaN when either is missing or equity is zero."""
    return _ratio(s.net_income, s.equity)


def return_on_assets(s: Snapshot) -> float:
    """Net income over total assets. NaN when either is missing."""
    return _ratio(s.net_income, s.assets)


def accrual_ratio(s: Snapshot) -> float:
    """``(net income - operating cash flow) / assets``: the Sloan accrual quality screen."""
    if not np.isfinite(s.net_income) or not np.isfinite(s.operating_cash_flow):
        return NAN
    return _ratio(s.net_income - s.operating_cash_flow, s.assets)


def book_value_per_share(s: Snapshot) -> float:
    """Common equity per share outstanding -- the book half of book-to-price (price is the caller's)."""
    return _ratio(s.equity, s.shares_outstanding)


@dataclass(frozen=True, eq=False)
class SymbolFundamentals:
    """One symbol's facts, indexed for point-in-time reads.

    ``facts`` may hold tags the ladder ignores; they are kept (the panel is the raw record) and
    skipped by every read. Construction is O(n log n); a read is a bisect to the visible prefix
    plus a scan of it.
    """

    symbol: str
    facts: tuple[Fact, ...]
    _entries: Mapping[tuple[str, str], tuple[tuple[Fact, int], ...]] = field(init=False, repr=False)
    _filed: Mapping[tuple[str, str], tuple[date, ...]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _check_str("symbol", self.symbol)
        if not isinstance(self.facts, tuple):
            raise FundamentalsError("facts must be a tuple")
        buckets: dict[tuple[str, str], list[tuple[Fact, int]]] = {}
        for f in self.facts:
            if not isinstance(f, Fact):
                raise FundamentalsError(f"expected a Fact, got {type(f).__name__}")
            if f.symbol != self.symbol:
                raise FundamentalsError(f"fact for {f.symbol!r} in the facts of {self.symbol!r}")
            kind = f.kind()
            if kind is None:
                continue  # a 6- or 9-month year-to-date duration: not a quarter, not a year
            for concept, rung in ladder.concepts_for(f.taxonomy, f.tag):
                cs = ladder.LADDER[concept]
                if f.unit != cs.unit:
                    continue  # a EUR filer's Revenues never joins a USD cross-section
                if cs.kind == ladder.INSTANT and kind != KIND_INSTANT:
                    continue
                if cs.kind == ladder.DURATION and kind == KIND_INSTANT:
                    continue
                buckets.setdefault((concept, kind), []).append((f, rung))
        entries: dict[tuple[str, str], tuple[tuple[Fact, int], ...]] = {}
        filed: dict[tuple[str, str], tuple[date, ...]] = {}
        for bucket, items in buckets.items():
            items.sort(key=lambda e: (e[0].filed, e[0].period_end, e[1], e[0].accn))
            entries[bucket] = tuple(items)
            filed[bucket] = tuple(e[0].filed for e in items)
        object.__setattr__(self, "_entries", entries)
        object.__setattr__(self, "_filed", filed)

    def _visible(self, concept: str, kind: str, t: date) -> tuple[tuple[Fact, int], ...]:
        items = self._entries.get((concept, kind))
        if not items:
            return ()
        cut = bisect_right(self._filed[(concept, kind)], t)
        return items[:cut]

    def _best_by_period(self, concept: str, kind: str, t: date) -> dict[date, tuple[Fact, int]]:
        best: dict[date, tuple[Fact, int]] = {}
        for entry in self._visible(concept, kind, t):
            period_end = entry[0].period_end
            current = best.get(period_end)
            if current is None or _key(entry) > _key(current):
                best[period_end] = entry
        return best

    def latest(self, concept: str, kind: str, t: date) -> Obs | None:
        """The newest period of ``concept`` (``kind`` is ``KIND_INSTANT``/``KIND_QUARTER``/``KIND_ANNUAL``) visible at ``t``."""
        ladder.spec(concept)
        _check_date("t", t)
        best = self._best_by_period(concept, kind, t)
        if not best:
            return None
        period_end = max(best)
        return _obs(concept, best[period_end][0])

    def instant(self, concept: str, t: date) -> Obs | None:
        """The newest balance of ``concept`` visible at ``t``."""
        if ladder.spec(concept).kind != ladder.INSTANT:
            raise FundamentalsError(f"{concept} is a duration concept, not an instant")
        return self.latest(concept, KIND_INSTANT, t)

    def annual(self, concept: str, t: date) -> Obs | None:
        """The newest fiscal-year figure of ``concept`` visible at ``t``."""
        if ladder.spec(concept).kind != ladder.DURATION:
            raise FundamentalsError(f"{concept} is an instant concept, not a duration")
        return self.latest(concept, KIND_ANNUAL, t)

    def _derived_q4(self, concept: str, t: date, quarterly: dict[date, tuple[Fact, int]]) -> list[Obs]:
        out: list[Obs] = []
        for period_end, (annual_fact, _) in self._best_by_period(concept, KIND_ANNUAL, t).items():
            if period_end in quarterly:
                continue
            start = annual_fact.period_start
            if start is None:
                continue
            legs = [
                f
                for pe, (f, _r) in quarterly.items()
                if f.period_start is not None and f.period_start >= start and pe < period_end
            ]
            if len(legs) != 3:
                continue
            legs.sort(key=lambda f: f.period_end)
            if legs[0].period_start != start:
                continue
            one_day = timedelta(days=1)
            if legs[1].period_start != legs[0].period_end + one_day:
                continue
            if legs[2].period_start != legs[1].period_end + one_day:
                continue
            val = annual_fact.val - legs[0].val
            val = val - legs[1].val
            val = val - legs[2].val
            filed = annual_fact.filed
            for leg in legs:
                if leg.filed > filed:
                    filed = leg.filed
            out.append(
                Obs(
                    concept=concept,
                    taxonomy=annual_fact.taxonomy,
                    tag=annual_fact.tag,
                    period_start=legs[2].period_end + one_day,
                    period_end=period_end,
                    filed=filed,
                    accn=annual_fact.accn,
                    val=val,
                    derived=True,
                )
            )
        return out

    def quarters(self, concept: str, t: date, *, derive_q4: bool = True) -> tuple[Obs, ...]:
        """``concept``'s quarterly series visible at ``t``: ascending, contiguous, ending at the newest.

        A quarter the filer never tagged is reconstructed from the fiscal year when the year and
        exactly three quarters tiling its start are all visible (``derive_q4``); the synthetic
        observation carries ``derived=True`` and is dated by the newest of its four inputs, so it
        appears no earlier than the last of them. EPS is only approximately additive across
        quarters -- the diluted share count moves -- so a derived EPS quarter is an estimate.

        The run is cut at the first step outside 60-120 days walking back from the newest
        quarter, so a skipped quarter or a fiscal-year change hides everything before it.
        """
        if ladder.spec(concept).kind != ladder.DURATION:
            raise FundamentalsError(f"{concept} is an instant concept and has no quarterly series")
        _check_date("t", t)
        quarterly = self._best_by_period(concept, KIND_QUARTER, t)
        by_period: dict[date, Obs] = {pe: _obs(concept, f) for pe, (f, _r) in quarterly.items()}
        if derive_q4:
            for o in self._derived_q4(concept, t, quarterly):
                by_period.setdefault(o.period_end, o)
        if not by_period:
            return ()
        series = [by_period[pe] for pe in sorted(by_period)]
        first = len(series) - 1
        while first > 0:
            step = (series[first].period_end - series[first - 1].period_end).days
            if not STEP_MIN_DAYS <= step <= STEP_MAX_DAYS:
                break
            first -= 1
        return tuple(series[first:])

    def as_of(self, t: date) -> Snapshot:
        """Everything known about this symbol on ``t``, with every unavailable figure NaN."""
        _check_date("t", t)
        obs: dict[str, Obs] = {}
        for concept in ladder.DURATION_CONCEPTS:
            o = self.annual(concept, t)
            if o is not None:
                obs[concept] = o
        for concept in ladder.INSTANT_CONCEPTS:
            o = self.instant(concept, t)
            if o is not None:
                obs[concept] = o

        basis = GROSS_PROFIT_NONE
        gp = obs.get(ladder.GROSS_PROFIT)
        if gp is not None:
            basis = GROSS_PROFIT_REPORTED
        else:
            rev = obs.get(ladder.REVENUE)
            cost = obs.get(ladder.COST_OF_REVENUE)
            if rev is not None and cost is not None and rev.period_end == cost.period_end:
                gp = Obs(
                    concept=ladder.GROSS_PROFIT,
                    taxonomy=rev.taxonomy,
                    tag=f"{rev.tag}-{cost.tag}",
                    period_start=rev.period_start,
                    period_end=rev.period_end,
                    filed=max(rev.filed, cost.filed),
                    accn=max(rev.accn, cost.accn),
                    val=rev.val - cost.val,
                    derived=True,
                )
                obs[ladder.GROSS_PROFIT] = gp
                basis = GROSS_PROFIT_DERIVED

        eps_series = self.quarters(ladder.DILUTED_EPS, t)
        eps = np.array([o.val for o in eps_series], dtype=np.float64)

        annual_ends = [o.period_end for c, o in obs.items() if ladder.LADDER[c].kind == ladder.DURATION]
        filed_dates = [o.filed for o in obs.values()]
        return Snapshot(
            symbol=self.symbol,
            asof=t,
            fiscal_period_end=max(annual_ends) if annual_ends else None,
            filed=max(filed_dates) if filed_dates else None,
            revenue=obs[ladder.REVENUE].val if ladder.REVENUE in obs else NAN,
            cost_of_revenue=obs[ladder.COST_OF_REVENUE].val if ladder.COST_OF_REVENUE in obs else NAN,
            gross_profit=gp.val if gp is not None else NAN,
            gross_profit_basis=basis,
            operating_income=obs[ladder.OPERATING_INCOME].val if ladder.OPERATING_INCOME in obs else NAN,
            net_income=obs[ladder.NET_INCOME].val if ladder.NET_INCOME in obs else NAN,
            operating_cash_flow=(
                obs[ladder.OPERATING_CASH_FLOW].val if ladder.OPERATING_CASH_FLOW in obs else NAN
            ),
            diluted_eps=obs[ladder.DILUTED_EPS].val if ladder.DILUTED_EPS in obs else NAN,
            diluted_shares=obs[ladder.DILUTED_SHARES].val if ladder.DILUTED_SHARES in obs else NAN,
            assets=obs[ladder.ASSETS].val if ladder.ASSETS in obs else NAN,
            equity=obs[ladder.EQUITY].val if ladder.EQUITY in obs else NAN,
            shares_outstanding=(
                obs[ladder.SHARES_OUTSTANDING].val if ladder.SHARES_OUTSTANDING in obs else NAN
            ),
            sue=sue_of(eps),
            sue_quarters=len(eps_series),
            observations=obs,
        )


@dataclass(frozen=True, eq=False)
class FundamentalPanel:
    """Every symbol's facts: what ``Market.fundamentals`` holds and what the factor layer reads.

    Empty is a normal state -- a store with no ``fundamental_facts`` rows yields ``EMPTY_PANEL``
    and every read returns None, so a backtest that predates the ingest keeps working.
    """

    symbols: Mapping[str, SymbolFundamentals]

    def __post_init__(self) -> None:
        if not isinstance(self.symbols, Mapping):
            raise FundamentalsError(f"symbols must be a Mapping, got {type(self.symbols).__name__}")
        for symbol, sf in self.symbols.items():
            if not isinstance(sf, SymbolFundamentals):
                raise FundamentalsError(f"symbols[{symbol!r}] must be a SymbolFundamentals")
            if sf.symbol != symbol:
                raise FundamentalsError(f"symbols[{symbol!r}] holds facts for {sf.symbol!r}")

    def __len__(self) -> int:
        return len(self.symbols)

    def __contains__(self, symbol: object) -> bool:
        return symbol in self.symbols

    def names(self) -> tuple[str, ...]:
        """Every symbol with at least one fact, sorted."""
        return tuple(sorted(self.symbols))

    def get(self, symbol: str) -> SymbolFundamentals | None:
        """``symbol``'s facts, or None when the panel has none."""
        return self.symbols.get(symbol)

    def as_of(self, symbol: str, t: date) -> Snapshot | None:
        """``symbol``'s snapshot on ``t``, or None when the panel has no facts for it."""
        sf = self.symbols.get(symbol)
        if sf is None:
            return None
        return sf.as_of(t)

    def snapshots_on(self, t: date, symbols: Iterable[str] | None = None) -> dict[str, Snapshot]:
        """``{symbol: Snapshot}`` on ``t`` for ``symbols`` (default: every symbol in the panel)."""
        _check_date("t", t)
        names = self.names() if symbols is None else tuple(symbols)
        out: dict[str, Snapshot] = {}
        for symbol in names:
            sf = self.symbols.get(symbol)
            if sf is not None:
                out[symbol] = sf.as_of(t)
        return out

    @staticmethod
    def from_facts(facts: Iterable[Fact]) -> FundamentalPanel:
        """A panel from facts in any order, grouped by symbol and sorted canonically."""
        grouped: dict[str, list[Fact]] = {}
        for f in facts:
            if not isinstance(f, Fact):
                raise FundamentalsError(f"expected a Fact, got {type(f).__name__}")
            grouped.setdefault(f.symbol, []).append(f)
        symbols: dict[str, SymbolFundamentals] = {}
        for symbol in sorted(grouped):
            rows = grouped[symbol]
            rows.sort(key=lambda f: (f.taxonomy, f.tag, f.period_end, f.filed, f.accn))
            symbols[symbol] = SymbolFundamentals(symbol, tuple(rows))
        return FundamentalPanel(symbols)


EMPTY_PANEL = FundamentalPanel({})
