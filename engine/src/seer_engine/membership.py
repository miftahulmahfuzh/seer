"""Point-in-time S&P 500 / Nasdaq-100 membership.

Source data (vendored in ``engine/data``, see ``SOURCES.md``):

* ``sp500_history.csv`` / ``ndx_history.csv`` -- ``date,tickers`` snapshots; each row is the
  full membership effective on that date, so membership on D is the latest row with
  ``date <= D``.
* ``membership_overrides.csv`` -- ``date,index_id,action,ticker,note`` changes announced after
  a snapshot file's last row (``action`` is ``add`` or ``remove``).
* ``ticker_aliases.csv`` -- ``old,new,effective_date,note``: a historical ticker ``old`` seen
  in a snapshot dated before ``effective_date`` is stored under the current ticker ``new``
  (the symbol yfinance and Massive know, i.e. the ``bars`` symbol).

The output is a list of :class:`Interval` rows for the ``universe`` table. ``end_date`` is
exclusive: it is the date of the first snapshot that no longer contains the symbol, and
``None`` while the symbol is still a member.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

SNAPSHOT_FILES: Mapping[str, str] = {
    "SP500": "sp500_history.csv",
    "NDX": "ndx_history.csv",
}
INDEX_IDS: tuple[str, ...] = tuple(SNAPSHOT_FILES)
OVERRIDES_FILE = "membership_overrides.csv"
ALIASES_FILE = "ticker_aliases.csv"

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]*(\.[A-Z])?$")

Snapshot = tuple[date, frozenset[str]]


class MembershipError(ValueError):
    """The vendored membership data is inconsistent."""


@dataclass(frozen=True, order=True)
class Interval:
    symbol: str
    index_id: str
    start_date: date
    end_date: date | None
    source_symbol: str


@dataclass(frozen=True)
class Override:
    date: date
    index_id: str
    action: str
    ticker: str
    note: str


@dataclass(frozen=True)
class Alias:
    old: str
    new: str
    effective_date: date
    note: str


def normalize_ticker(raw: str) -> str:
    """Canonical dot form: ``brk-b`` -> ``BRK.B``. Raises on anything that is not a ticker."""
    ticker = raw.strip().upper().replace("-", ".").replace("/", ".")
    if not _TICKER_RE.match(ticker):
        raise MembershipError(f"not a ticker: {raw!r}")
    return ticker


def _parse_date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise MembershipError(f"{where}: bad date {raw!r}") from exc


def load_snapshots(path: Path) -> list[Snapshot]:
    """Read a ``date,tickers`` file into ascending ``(date, frozenset)`` snapshots."""
    snapshots: list[Snapshot] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["date", "tickers"]:
            raise MembershipError(f"{path}: expected header date,tickers, got {reader.fieldnames}")
        for lineno, row in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            d = _parse_date(row["date"], where)
            tickers = frozenset(
                normalize_ticker(t) for t in row["tickers"].split(",") if t.strip()
            )
            if not tickers:
                raise MembershipError(f"{where}: empty membership")
            snapshots.append((d, tickers))
    if not snapshots:
        raise MembershipError(f"{path}: no rows")
    dates = [d for d, _ in snapshots]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise MembershipError(f"{path}: dates must be strictly ascending")
    return snapshots


def load_overrides(path: Path) -> list[Override]:
    overrides: list[Override] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["date", "index_id", "action", "ticker", "note"]:
            raise MembershipError(
                f"{path}: expected header date,index_id,action,ticker,note, got {reader.fieldnames}"
            )
        for lineno, row in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            index_id = row["index_id"].strip()
            if index_id not in SNAPSHOT_FILES:
                raise MembershipError(f"{where}: unknown index_id {index_id!r}")
            action = row["action"].strip()
            if action not in ("add", "remove"):
                raise MembershipError(f"{where}: action must be add|remove, got {action!r}")
            overrides.append(
                Override(
                    date=_parse_date(row["date"], where),
                    index_id=index_id,
                    action=action,
                    ticker=normalize_ticker(row["ticker"]),
                    note=(row["note"] or "").strip(),
                )
            )
    return overrides


def load_aliases(path: Path) -> list[Alias]:
    aliases: list[Alias] = []
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["old", "new", "effective_date", "note"]:
            raise MembershipError(
                f"{path}: expected header old,new,effective_date,note, got {reader.fieldnames}"
            )
        for lineno, row in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            alias = Alias(
                old=normalize_ticker(row["old"]),
                new=normalize_ticker(row["new"]),
                effective_date=_parse_date(row["effective_date"], where),
                note=(row["note"] or "").strip(),
            )
            if alias.old == alias.new:
                raise MembershipError(f"{where}: old == new ({alias.old})")
            if alias.old in seen:
                raise MembershipError(f"{where}: duplicate alias for {alias.old}")
            seen.add(alias.old)
            aliases.append(alias)
    olds = {a.old for a in aliases}
    for a in aliases:
        if a.new in olds:
            raise MembershipError(
                f"alias chain {a.old}->{a.new}->...: point every old ticker at the current one"
            )
    return aliases


def apply_overrides(
    snapshots: Sequence[Snapshot], overrides: Iterable[Override], index_id: str
) -> list[Snapshot]:
    """Append one snapshot per override date for ``index_id``.

    Overrides must be dated strictly after the snapshot file's last row; an earlier one would be
    applied twice once the upstream file catches up, so it is rejected.
    """
    result = list(snapshots)
    if not result:
        raise MembershipError(f"{index_id}: no snapshots")
    last_date = result[-1][0]
    by_date: dict[date, list[Override]] = defaultdict(list)
    for o in overrides:
        if o.index_id != index_id:
            continue
        if o.date <= last_date:
            raise MembershipError(
                f"override {o.date} {o.index_id} {o.action} {o.ticker} is not after the "
                f"snapshot file's last row ({last_date}); drop it from {OVERRIDES_FILE}"
            )
        by_date[o.date].append(o)
    members = set(result[-1][1])
    for d in sorted(by_date):
        for o in sorted(by_date[d], key=lambda x: (x.action != "remove", x.ticker)):
            if o.action == "remove":
                if o.ticker not in members:
                    raise MembershipError(f"override {d} {index_id}: remove {o.ticker}, not a member")
                members.remove(o.ticker)
            else:
                if o.ticker in members:
                    raise MembershipError(f"override {d} {index_id}: add {o.ticker}, already a member")
                members.add(o.ticker)
        result.append((d, frozenset(members)))
    return result


def _alias_map(aliases: Iterable[Alias]) -> dict[str, Alias]:
    return {a.old: a for a in aliases}


def resolve_symbol(ticker: str, on: date, aliases: Mapping[str, Alias]) -> str:
    """The bars symbol for ``ticker`` as it appeared in a snapshot dated ``on``."""
    alias = aliases.get(ticker)
    if alias is not None and on < alias.effective_date:
        return alias.new
    return ticker


def build_intervals(
    snapshots: Sequence[Snapshot], index_id: str, aliases: Iterable[Alias] = ()
) -> list[Interval]:
    """Turn ascending snapshots into membership intervals keyed by the current (bars) symbol.

    A symbol's interval runs from the first snapshot containing it to the first later snapshot
    that does not (exclusive). Because aliases are resolved per snapshot, an old ticker followed
    directly by its new one (FB -> META) yields one continuous interval; ``source_symbol`` then
    lists the tickers used, oldest first, joined with ``/`` (``FB/META``).
    """
    amap = _alias_map(aliases)
    open_start: dict[str, date] = {}
    open_sources: dict[str, list[str]] = {}
    intervals: list[Interval] = []
    for d, tickers in snapshots:
        resolved: dict[str, str] = {}
        for ticker in sorted(tickers):
            symbol = resolve_symbol(ticker, d, amap)
            if symbol in resolved:
                raise MembershipError(
                    f"{index_id} {d}: {resolved[symbol]} and {ticker} both resolve to {symbol}"
                )
            resolved[symbol] = ticker
        for symbol in sorted(set(open_start) - set(resolved)):
            intervals.append(
                Interval(
                    symbol=symbol,
                    index_id=index_id,
                    start_date=open_start.pop(symbol),
                    end_date=d,
                    source_symbol="/".join(open_sources.pop(symbol)),
                )
            )
        for symbol, ticker in resolved.items():
            if symbol not in open_start:
                open_start[symbol] = d
                open_sources[symbol] = [ticker]
            elif open_sources[symbol][-1] != ticker:
                open_sources[symbol].append(ticker)
    for symbol in sorted(open_start):
        intervals.append(
            Interval(
                symbol=symbol,
                index_id=index_id,
                start_date=open_start[symbol],
                end_date=None,
                source_symbol="/".join(open_sources[symbol]),
            )
        )
    return sorted(intervals, key=_sort_key)


def _sort_key(iv: Interval) -> tuple[str, str, date]:
    return (iv.index_id, iv.symbol, iv.start_date)


def compute_universe(data_dir: Path = DATA_DIR) -> list[Interval]:
    """Every membership interval of every index, from the vendored files."""
    overrides = load_overrides(data_dir / OVERRIDES_FILE)
    aliases = load_aliases(data_dir / ALIASES_FILE)
    intervals: list[Interval] = []
    for index_id, filename in SNAPSHOT_FILES.items():
        snapshots = load_snapshots(data_dir / filename)
        snapshots = apply_overrides(snapshots, overrides, index_id)
        intervals.extend(build_intervals(snapshots, index_id, aliases))
    return sorted(intervals, key=_sort_key)


def current_members(intervals: Iterable[Interval], index_id: str) -> frozenset[str]:
    """Symbols whose interval in ``index_id`` is still open."""
    return frozenset(
        iv.symbol for iv in intervals if iv.index_id == index_id and iv.end_date is None
    )


def symbols_since(intervals: Iterable[Interval], since: date) -> frozenset[str]:
    """Distinct symbols that were a member of any index on or after ``since``."""
    return frozenset(iv.symbol for iv in intervals if iv.end_date is None or iv.end_date > since)


def stored_intervals(conn) -> set[Interval]:
    """The ``universe`` table as a set of :class:`Interval`."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, index_id, start_date, end_date, source_symbol FROM universe"
        )
        return {Interval(*row) for row in cur.fetchall()}


def replace_universe(conn, intervals: Sequence[Interval]) -> int:
    """Replace the whole ``universe`` table; caller owns the transaction. Returns rows inserted."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM universe")
        cur.executemany(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                (iv.symbol, iv.index_id, iv.start_date, iv.end_date, iv.source_symbol)
                for iv in intervals
            ],
        )
    return len(intervals)


# --- Wikipedia current components (used by `universe check`) -------------------------------

WIKIPEDIA_PAGES: Mapping[str, str] = {
    "SP500": "List of S&P 500 companies",
    "NDX": "List of NASDAQ-100 companies",
}

_CONSTITUENTS_TABLE_RE = re.compile(r'\{\|[^\n]*id="constituents"[^\n]*\n(.*?)\n\|\}', re.S)
_ROW_SEPARATOR_RE = re.compile(r"^\|-[^\n]*$", re.M)
_CELL_SEPARATOR_RE = re.compile(r"\|\||\n\|")
_TEMPLATE_RE = re.compile(r"\{\{([^{}]*)\}\}")
_WIKILINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_REF_RE = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S)


def parse_constituents(wikitext: str) -> frozenset[str]:
    """Tickers in the first column of the ``id="constituents"`` table of a Wikipedia page.

    Handles both layouts in use on 2026-10-03: one cell per line with a
    ``{{NyseSymbol|MMM}}`` template (S&P 500) and ``| ADBE || [[Adobe Inc.]] || ...`` rows
    (Nasdaq-100).
    """
    match = _CONSTITUENTS_TABLE_RE.search(wikitext)
    if match is None:
        raise MembershipError('no {| ... id="constituents" table in the page wikitext')
    tickers: set[str] = set()
    for row in _ROW_SEPARATOR_RE.split(match.group(1)):
        row = row.strip()
        if not row.startswith("|"):
            continue  # header row ("!") or table caption/attributes
        first = _CELL_SEPARATOR_RE.split(row.lstrip("|"), maxsplit=1)[0]
        first = _REF_RE.sub("", first)
        template = _TEMPLATE_RE.search(first)
        if template is not None:
            first = template.group(1).split("|")[-1]
        first = _WIKILINK_RE.sub(r"\1", first)
        tickers.add(normalize_ticker(first))
    if not tickers:
        raise MembershipError("constituents table has no rows")
    return frozenset(tickers)


def diff_members(
    computed: Mapping[str, frozenset[str]], reference: Mapping[str, frozenset[str]]
) -> dict[str, tuple[list[str], list[str]]]:
    """Per index: (in reference but not computed, in computed but not reference). Only indexes
    with a difference are returned."""
    diffs: dict[str, tuple[list[str], list[str]]] = {}
    for index_id in INDEX_IDS:
        ours = computed.get(index_id, frozenset())
        theirs = reference.get(index_id, frozenset())
        missing = sorted(theirs - ours)
        extra = sorted(ours - theirs)
        if missing or extra:
            diffs[index_id] = (missing, extra)
    return diffs
