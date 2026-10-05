> Adopted from `EDGAR_FUNDAMENTALS_PLAN.md` phase 1. Source: `.workflows/plan/edgar-fundamentals/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Vendored ticker→CIK map and loader

**Plan set:** `EDGAR_FUNDAMENTALS_PLAN.md`
**Analysis:** `20261005-081833-G7K2_code_analyzer.md`
**Satisfies:** R1 — a ticker→CIK bridge that can never resolve a recycled ticker to the wrong company
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/data`, `seer_engine`

---

## Goal

After this phase the repo carries a vendored, hand-audited, **date-scoped** ticker→CIK map
covering every S&P 500 / Nasdaq-100 ever-member since 2015-01-02, plus `seer_engine/cik.py`,
a pure stdlib loader that validates it as hard as `membership.load_aliases` validates
`ticker_aliases.csv`. Phase 4 can turn any `(symbol, date)` into the CIK of the company that
actually traded under that symbol on that date, and a test proves that CA, MON, PLL, ALTR, LLL
and DTV resolve to the historical filer and never to today's holder of the recycled ticker.

---

## Measured facts this plan was written against

Everything below was measured in this worktree on **2026-10-05**. Numbers that disagree with the
analysis file are called out; where they disagree, **these win** (the analysis is a description,
the code and the live endpoints are the fact).

| Fact | Value | How it was measured |
|---|---|---|
| Ever-members since 2015-01-02 | **795** (not 819) | `len(membership.symbols_since(membership.compute_universe(), date(2015,1,2)))` |
| …of which still open intervals | 518 | same, `end_date is None` |
| …of which closed | 277 | 795 − 518 |
| Distinct symbols in `universe`, all time | 1,265 | matches the analysis |
| `company_tickers.json` size | 10,440 pairs / 9,923 distinct normalized tickers | downloaded 2026-10-05 |
| Ever-members resolvable from `company_tickers.json` | **649 / 795** | set intersection after `membership.normalize_ticker` |
| …of the remaining 146, resolvable from `browse-edgar?action=getcompany&CIK=<ticker>&output=atom` | **+51** (cumulative 700) | one request per ticker, 0.2 s apart |
| …plus the `MANUAL` seeds below (`CA`, `DTV` reach no tier) | **702** | — |
| …still unresolved | **93** | these are the long-dead names the Massive → `cik-lookup-data.txt` recipe is for |
| `cik-lookup-data.txt` | 40,236,577 bytes, **1,061,750** lines, latin-1 | downloaded 2026-10-05; matches the analysis |

### This plan's code was executed, not only written

Step 1's `cik.py` and Step 5's `test_cik.py` were run together while planning. All **43**
non-vendored tests pass as written. A partial `ticker_cik.csv` was then built from tiers 1-2
plus the `MANUAL` seeds (705 rows / 702 symbols) and loaded through `load_ticker_cik`:

- the loader accepted the real file (sort order, 10-digit CIKs, the two-row `WRK`/`GOOG`/`GOOGL`
  symbols) with no error;
- `coverage_gaps` returned exactly 93 gaps — one per unresolved symbol — and **zero** for every
  symbol that had a row, which is the behaviour the R1 test depends on;
- all six recycled-ticker assertions passed, both halves (right CIK during membership, `CikError`
  on 2026-10-05);
- `WRK` resolved `0001636023` → `0001732845` across 2018-11-02 and `GOOGL` `0001288776` →
  `0001652044` across 2015-10-02;
- all four share-class pairs resolved to one CIK; every spot check matched, including the
  corrected Kellanova value.

So the only unproven part of this phase is filling the last 93 symbols (Step 3), which needs the
Massive key.

`company_tickers.json` is **not** a superset of the live S&P 500: AVB, EA, JNPR, EQR, CMA, DFS,
HOLX and IPG are all absent from it today. That is why tier 2 exists.

### The recycled-ticker failure, reproduced

`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<TICKER>&output=atom` — EDGAR's
own ticker lookup — answered on 2026-10-05:

| Symbol | Membership span (hull, clipped to ≥ 2015-01-02) | EDGAR answers | Correct historical filer |
|---|---|---|---|
| `CA`   | 2015-01-02 .. 2018-11-06 | *(no match)* | `0000356028` CA, INC. |
| `MON`  | 2015-01-02 .. 2018-06-07 | `0001828325` Monument Circle Acquisition Corp. | `0001110783` MONSANTO CO /NEW/ |
| `PLL`  | 2015-01-02 .. 2015-08-31 | `0001728205` Piedmont Lithium Inc. | `0000075829` PALL CORP |
| `ALTR` | 2015-01-02 .. 2015-12-28 | `0001701732` Altair Engineering Inc. | `0000768251` ALTERA CORP |
| `LLL`  | 2015-01-02 .. 2019-07-01 | `0001546383` JX Luxventure Group Inc. | `0001039101` L3 TECHNOLOGIES, INC. |
| `DTV`  | 2015-01-02 .. 2015-07-27 | *(no match)* | `0001465112` DIRECTV |

Every "correct" CIK above was confirmed against `https://data.sec.gov/submissions/CIK##########.json`
(conformed name + former names). `DTV`'s current holder, per the user's brief, is DTE Energy
corporate units — `DTE ENERGY CO` = `0000936340`, confirmed in `cik-lookup-data.txt`.

### An automated screen that is useful but *not* sufficient

Candidate rule: *a candidate CIK must have filed at least one periodic report
(10-K / 10-Q / 20-F / 40-F / 10-K405) with `filingDate` inside the symbol's span.* Measured on
the six recycled tickers:

| Symbol | Right CIK, filings inside span | Wrong CIK, filings inside span | Screen rejects the wrong one? |
|---|---|---|---|
| MON | 14 | 0 | yes |
| PLL | 2 | 0 | yes |
| ALTR | 4 | 0 | yes |
| LLL | 18 | **5** | **no** |
| DTV | 2 | **3** | **no** |
| CA | 15 | — | n/a |

So the screen is a *net*, not a gate. The six recycled tickers stay a mandatory hand-audit, and
the generator's `MANUAL` table must win over every automated tier.

### Two symbols change filer *inside* the window without changing ticker

Both verified against `data.sec.gov/submissions`:

| Symbol | Rows needed |
|---|---|
| `WRK` | `0001636023` (WestRock Co, renamed WRKCo Inc. 2018-11-01) 2015-07-02 .. 2018-11-02; `0001732845` (Whiskey Holdco → WestRock Co) 2018-11-02 .. 2024-07-08. Old entity's last filing 2018-11-05, new entity's first 2018-11-05; the KapStone close was 2018-11-02. |
| `GOOG` / `GOOGL` | `0001288776` (GOOGLE INC.) 2015-01-02 .. 2015-10-02; `0001652044` (ALPHABET INC.) 2015-10-02 .. open. Alphabet holdco reorg closed 2015-10-02; Google Inc's last 10-K was filed 2016-02-11 as a co-registrant. |

### One CIK legitimately backs several symbols

Share-class pairs present among the 795 ever-members: `GOOG`/`GOOGL`, `FOX`/`FOXA`,
`NWS`/`NWSA`, `UA`/`UAA`, `CMCSA`/`CMCSK`, `BATRA`/`BATRK`. **Do not add a uniqueness check on
`cik`** — it would reject all six pairs.

### Corrections to the brief

- The brief's `KELLANOVA (K) = 0000039899` is **wrong**. `0000039899` is `GANNETT CO INC /DE/` /
  `TEGNA INC`. Kellanova (formerly Kellogg Co) is **`0000055067`**, confirmed by
  `data.sec.gov/submissions/CIK0000055067.json` (`formerNames: KELLOGG CO, 1994-04-29 → 2023-09-28`).
- The brief's scope figure of 819 ever-members measures 795 today. The CSV and the tests must
  derive the set from `membership.symbols_since(...)`, never from a hardcoded count.

---

## Interface Contract

**Creates (data):** `engine/data/ticker_cik.csv`
**CSV header (exact, in this order):** `symbol,cik,start_date,end_date,company_name,source,note`

| Column | Type | Meaning |
|---|---|---|
| `symbol` | canonical dot-form ticker (`membership.normalize_ticker`) | the `universe.symbol` / `bars.symbol` the row is about |
| `cik` | exactly 10 digits, zero-padded — **or** the literal `NONE` | the SEC Central Index Key; `NONE` means "no EDGAR filer, see `note`" |
| `start_date` | ISO date, **inclusive** | first date this CIK is the filer behind `symbol` |
| `end_date` | ISO date, **exclusive**, or empty | first date it is no longer; empty = still current. Same semantics as `universe.end_date` |
| `company_name` | text, required unless `cik` is `NONE` | EDGAR conformed name at vendoring time |
| `source` | one of `current`, `edgar`, `exact`, `fuzzy`, `manual` | which tier produced the row |
| `note` | text, required when `source` is `fuzzy` or `manual`, or `cik` is `NONE` | why a human can trust it |

Rows are sorted by `(symbol, start_date)`; the loader rejects a file that is not.

**Creates (code):** `engine/src/seer_engine/cik.py`

```
seer_engine.cik.DATA_DIR              : Path            = engine/data
seer_engine.cik.TICKER_CIK_FILE       : str             = "ticker_cik.csv"
seer_engine.cik.SINCE                 : date            = 2015-01-02
seer_engine.cik.HEADER                : tuple[str, ...]
seer_engine.cik.SOURCES               : tuple[str, ...] = ("current","edgar","exact","fuzzy","manual")
seer_engine.cik.NOTE_REQUIRED         : frozenset[str]  = {"fuzzy","manual"}
seer_engine.cik.NO_FILER              : str             = "NONE"
seer_engine.cik.CikError(ValueError)
seer_engine.cik.CikRow                : frozen dataclass(symbol, cik: str|None, start_date,
                                                         end_date: date|None, company_name,
                                                         source, note); .covers(on: date) -> bool
seer_engine.cik.Gap                   : frozen dataclass(symbol, start_date, end_date: date|None)
seer_engine.cik.Index                 : TypeAlias = Mapping[str, tuple[CikRow, ...]]
seer_engine.cik.normalize_cik(raw, where="") -> str
seer_engine.cik.load_ticker_cik(path: Path) -> list[CikRow]
seer_engine.cik.build_index(rows: Iterable[CikRow]) -> dict[str, tuple[CikRow, ...]]
seer_engine.cik.load_index(data_dir: Path = DATA_DIR) -> dict[str, tuple[CikRow, ...]]
seer_engine.cik.resolve_row(symbol, on: date, index: Index) -> CikRow     # raises CikError
seer_engine.cik.resolve(symbol, on: date, index: Index) -> str            # raises CikError
seer_engine.cik.filers(symbol, index, start=None, end=None) -> tuple[str, ...]
seer_engine.cik.missing_symbols(index, symbols: Iterable[str]) -> tuple[str, ...]
seer_engine.cik.no_filer_symbols(index) -> tuple[str, ...]
seer_engine.cik.coverage_gaps(index, intervals, since: date = SINCE) -> tuple[Gap, ...]
```

**Creates (script):** `engine/scripts/build_ticker_cik.py` — the committed one-off generator
(new directory `engine/scripts/`).
**Creates (test):** `engine/tests/test_cik.py`
**Modifies:** `engine/data/SOURCES.md` — intro line + one new section.
**Deletes:** none. **Renames:** none. **Signature changes:** none.

**Requires (from earlier phases):** nothing — this phase has no dependencies.

**Leaves alone (owned by others):**
- `db/migrations/*` and the `ticker_cik` **table** (Phase 2). This phase writes only the CSV.
- `seer_engine/sec.py`, `config.SEC_CONTACT_EMAIL`, `.env.example` (Phase 3). The generator reads
  `SEC_CONTACT_EMAIL` straight from `os.environ` / a `--contact` flag so it does not need
  `config.py` to know the name yet, and keeps working unchanged once Phase 3 adds it.
- `seer_engine/commands/*` (Phase 4). No command module here.
- `seer_engine/membership.py` — **imported, never edited**. `cik.py` reuses
  `membership.normalize_ticker` and types `coverage_gaps` against `membership.Interval`.
  `membership.py` must never import `cik.py` (one-way dependency).
- `docs/runbooks/data-pipeline.md` (Phase 7).

**Reconciled — the index records "Files: 4" for this phase. It is **5**.**
`engine/scripts/build_ticker_cik.py` is the committed one-off the phase scope calls for, and
`engine/scripts/` is a new directory. `python -m ruff check engine` lints it, so it must be
E9/F-clean. The index's Files column now says 5.

**Reconciled — how this CSV reaches the `ticker_cik` table (phases 2 and 4).** Phase 2 owns the
table and phase 4 owns the writer (`sync_ticker_cik`). This phase writes **only** the CSV and
`cik.py`; it opens no connection and issues no SQL. The mapping the two downstream phases are
built against, settled here so nobody re-derives it:

| `ticker_cik.csv` column (this phase) | `ticker_cik` table column (phase 2) |
|---|---|
| `symbol` | `symbol` |
| `cik` (10-digit zero-padded text, or `NONE`) | `cik` (`bigint`, unpadded) |
| `start_date` | `start_date` |
| `end_date` (empty = still current) | `end_date` (NULL = still current) |
| `company_name` | `company` |
| `source` ∈ `current, edgar, exact, fuzzy, manual` | `source`, whose CHECK phase 2 widened to exactly this set |
| `note` | `note` |

**The `NONE` sentinel is a CSV-only value.** `cik` is `NOT NULL bigint` in the table, so phase 4's
`sync_ticker_cik` **skips** every `NONE` row, and `resolve_window_cik` maps a `NONE` row to
status `empty` ("this symbol has no EDGAR filer"), never `failed`. That is settled in the index's
Decisions table; `cik.no_filer_symbols(index)` is the accessor phase 4 calls.

**Reconciled — phases 1 and 4 must land together for a green `fundamentals` run.** Phase 4
classifies a symbol with no row in the map as `failed`, so the command exits 1 against an
incomplete `ticker_cik.csv`. That is deliberate — it is what makes this phase's "covers every
ever-member" criterion machine-checkable — but it means `python -m seer_engine fundamentals`
is only expected to exit 0 once **both** phases are merged. Neither phase's own
`pytest engine/tests -q` depends on the other: this phase's tests read the vendored CSV directly
and phase 4's tests use a fake map. See phase 4's matching note.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/cik.py` | create | loader + hard validation + date-scoped lookups |
| `engine/scripts/build_ticker_cik.py` | create | one-off generator, with the hand-audited `MANUAL` table |
| `engine/data/ticker_cik.csv` | create (generated, committed as data) | ~800+ rows covering all 795 ever-members |
| `engine/data/SOURCES.md` | modify — line 3-5 (intro) and append after line 139 | one new documentation section in the house format |
| `engine/tests/test_cik.py` | create | unit tests on synthetic CSVs + vendored-data tests |

---

## Implementation Steps

### Step 1: `seer_engine/cik.py`

**File:** `engine/src/seer_engine/cik.py` (new file)
**Change:** The whole module. Pure stdlib (`csv`, `dataclasses`, `datetime`, `pathlib`, `typing`)
plus `seer_engine.membership` for `normalize_ticker` and `Interval`. No `requests`, no
`psycopg`, no clock read — so it stays usable from both the command layer (Phase 4) and tests.

**Code:**

```python
"""Point-in-time ticker -> SEC CIK map.

Vendored source (``engine/data``, documented in ``SOURCES.md``):

* ``ticker_cik.csv`` -- ``symbol,cik,start_date,end_date,company_name,source,note``. One row per
  (symbol, filer) tenure: the SEC Central Index Key of the company whose shares traded under
  ``symbol`` over ``[start_date, end_date)``. ``end_date`` is **exclusive** and empty while the
  mapping is still current, exactly like ``universe.end_date``. ``cik`` is the literal ``NONE``
  for a symbol with no EDGAR filer at all; ``note`` then says why.

**A ticker alone never identifies a company.** Measured 2026-10-05, EDGAR's own ticker lookup
(``browse-edgar?action=getcompany&CIK=<ticker>``) answers MON with Monument Circle Acquisition
Corp (0001828325), PLL with Piedmont Lithium (0001728205), ALTR with Altair Engineering
(0001701732) and LLL with JX Luxventure (0001546383) -- in every case the company holding the
recycled ticker *today*, not the index member that held it in the backtest window. Two symbols
also change filer *inside* the window without changing ticker: WRK (WestRock 0001636023 ->
0001732845 at the 2018-11-02 KapStone close) and GOOG/GOOGL (Google Inc 0001288776 -> Alphabet
0001652044 at the 2015-10-02 holdco reorg). Every lookup here is therefore scoped by date, and
there is deliberately no bare-ticker API.

The reverse is not true: one CIK legitimately backs several symbols at once. Among the
ever-members GOOG/GOOGL, FOX/FOXA, NWS/NWSA, UA/UAA, CMCSA/CMCSK and BATRA/BATRK are share
classes of a single filer, so no uniqueness check is applied to ``cik``.

Nothing in this module reads the network, the clock or the database. ``membership`` is imported
for ``normalize_ticker`` and ``Interval``; ``membership`` must never import this module.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from seer_engine import membership
from seer_engine.membership import Interval, MembershipError

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TICKER_CIK_FILE = "ticker_cik.csv"

#: First day of the backtest window. The map is only guaranteed from here on.
SINCE = date(2015, 1, 2)

HEADER: tuple[str, ...] = (
    "symbol",
    "cik",
    "start_date",
    "end_date",
    "company_name",
    "source",
    "note",
)

#: How a row was produced. ``current`` = SEC company_tickers.json, ``edgar`` = EDGAR's
#: browse-edgar ticker lookup, ``exact``/``fuzzy`` = company-name match against
#: cik-lookup-data.txt, ``manual`` = hand-audited in build_ticker_cik.py.
SOURCES: tuple[str, ...] = ("current", "edgar", "exact", "fuzzy", "manual")

#: Sources whose rows a human must justify in ``note``.
NOTE_REQUIRED = frozenset({"fuzzy", "manual"})

#: ``cik`` sentinel: this symbol has no EDGAR filer. ``note`` is then mandatory.
NO_FILER = "NONE"

#: Internal stand-in for an open ``end_date`` so interval arithmetic stays total.
_OPEN = date.max


class CikError(ValueError):
    """The vendored ticker -> CIK data is inconsistent, or a lookup has no answer."""


@dataclass(frozen=True, order=True)
class CikRow:
    """One (symbol, filer) tenure. ``end_date`` is exclusive; None means still current."""

    symbol: str
    cik: str | None
    start_date: date
    end_date: date | None
    company_name: str
    source: str
    note: str

    def covers(self, on: date) -> bool:
        """True when ``on`` falls in ``[start_date, end_date)``."""
        if on < self.start_date:
            return False
        return self.end_date is None or on < self.end_date


@dataclass(frozen=True, order=True)
class Gap:
    """A stretch of a symbol's membership that ``ticker_cik.csv`` does not answer for."""

    symbol: str
    start_date: date
    end_date: date | None


Index = Mapping[str, tuple[CikRow, ...]]


def normalize_cik(raw: str, where: str = "") -> str:
    """``'356028'`` -> ``'0000356028'``. Raises on anything that is not a CIK.

    The vendored file must already carry the 10-digit form -- ``load_ticker_cik`` rejects
    anything else. This helper exists for the ingest path (Phase 4), which sees CIKs as bare
    integers in SEC payloads and on the command line.
    """
    text = raw.strip()
    prefix = f"{where}: " if where else ""
    if text.upper().startswith("CIK"):
        text = text[3:]
    if not text or not text.isdigit() or len(text) > 10:
        raise CikError(f"{prefix}not a CIK: {raw!r}")
    padded = text.zfill(10)
    if padded == "0" * 10:
        raise CikError(f"{prefix}not a CIK: {raw!r}")
    return padded


def _parse_date(raw: str, where: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise CikError(f"{where}: bad date {raw!r}") from exc


def _parse_cik_cell(raw: str, where: str) -> str | None:
    text = raw.strip()
    if text == NO_FILER:
        return None
    if len(text) != 10 or not text.isdigit() or text == "0" * 10:
        raise CikError(
            f"{where}: cik must be 10 digits or {NO_FILER}, got {raw!r}"
        )
    return text


def _parse_symbol(raw: str, where: str) -> str:
    try:
        return membership.normalize_ticker(raw)
    except MembershipError as exc:
        raise CikError(f"{where}: {exc}") from exc


def load_ticker_cik(path: Path) -> list[CikRow]:
    """Read ``ticker_cik.csv`` into rows, rejecting anything inconsistent.

    Rejected: a header that is not exactly :data:`HEADER`; a symbol that is not a ticker; a
    ``cik`` that is not 10 digits (or ``NONE``); a bad or non-increasing date; an unknown
    ``source``; a missing ``note`` where one is required; a missing ``company_name`` on a row
    that has a CIK; a file not sorted by ``(symbol, start_date)``; a duplicate
    ``(symbol, start_date)``; two overlapping intervals for one symbol; an open interval that is
    not the symbol's last row; and a ``NONE`` row that is not the symbol's only row.
    """
    rows: list[CikRow] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise CikError(
                f"{path}: expected header {','.join(HEADER)}, got {reader.fieldnames}"
            )
        for lineno, raw in enumerate(reader, start=2):
            where = f"{path.name}:{lineno}"
            symbol = _parse_symbol(raw["symbol"], where)
            cik = _parse_cik_cell(raw["cik"], where)
            start_date = _parse_date(raw["start_date"], where)
            end_text = (raw["end_date"] or "").strip()
            end_date = _parse_date(end_text, where) if end_text else None
            if end_date is not None and end_date <= start_date:
                raise CikError(
                    f"{where}: end_date {end_date} must be after start_date {start_date}"
                )
            source = (raw["source"] or "").strip()
            if source not in SOURCES:
                raise CikError(
                    f"{where}: source must be one of {'|'.join(SOURCES)}, got {source!r}"
                )
            company_name = (raw["company_name"] or "").strip()
            if cik is not None and not company_name:
                raise CikError(f"{where}: company_name is required")
            note = (raw["note"] or "").strip()
            if not note and (source in NOTE_REQUIRED or cik is None):
                reason = f"source {source}" if source in NOTE_REQUIRED else NO_FILER
                raise CikError(f"{where}: note is required for {reason}")
            rows.append(
                CikRow(
                    symbol=symbol,
                    cik=cik,
                    start_date=start_date,
                    end_date=end_date,
                    company_name=company_name,
                    source=source,
                    note=note,
                )
            )
    if not rows:
        raise CikError(f"{path}: no rows")
    _check_order(rows, path)
    _check_intervals(rows, path)
    return rows


def _check_order(rows: Sequence[CikRow], path: Path) -> None:
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if (cur.symbol, cur.start_date) < (prev.symbol, prev.start_date):
            raise CikError(
                f"{path.name}:{i + 2}: rows must be sorted by (symbol, start_date); "
                f"{cur.symbol} {cur.start_date} follows {prev.symbol} {prev.start_date}"
            )


def _check_intervals(rows: Sequence[CikRow], path: Path) -> None:
    grouped: dict[str, list[CikRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)
    for symbol, group in grouped.items():
        if any(r.cik is None for r in group) and len(group) > 1:
            raise CikError(
                f"{path.name}: {symbol} has a {NO_FILER} row alongside {len(group) - 1} other "
                f"row(s); {NO_FILER} must be the symbol's only row"
            )
        for i in range(1, len(group)):
            prev, cur = group[i - 1], group[i]
            if prev.start_date == cur.start_date:
                raise CikError(f"{path.name}: duplicate row for {symbol} {cur.start_date}")
            if prev.end_date is None:
                raise CikError(
                    f"{path.name}: {symbol} has an open interval from {prev.start_date} "
                    f"before the row starting {cur.start_date}; only the last row may be open"
                )
            if prev.end_date > cur.start_date:
                raise CikError(
                    f"{path.name}: {symbol} intervals overlap: "
                    f"[{prev.start_date}, {prev.end_date}) and [{cur.start_date}, "
                    f"{cur.end_date or ''})"
                )


def build_index(rows: Iterable[CikRow]) -> dict[str, tuple[CikRow, ...]]:
    """Group rows by symbol, each group ascending by ``start_date``."""
    grouped: dict[str, list[CikRow]] = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)
    return {
        symbol: tuple(sorted(group, key=lambda r: r.start_date))
        for symbol, group in sorted(grouped.items())
    }


def load_index(data_dir: Path = DATA_DIR) -> dict[str, tuple[CikRow, ...]]:
    """The vendored map, loaded and validated, ready for :func:`resolve`."""
    return build_index(load_ticker_cik(data_dir / TICKER_CIK_FILE))


def resolve_row(symbol: str, on: date, index: Index) -> CikRow:
    """The row covering ``symbol`` on ``on``. Raises :class:`CikError` when there is none."""
    group = index.get(symbol)
    if not group:
        raise CikError(f"{symbol}: no row in {TICKER_CIK_FILE}")
    for row in group:
        if row.covers(on):
            if row.cik is None:
                raise CikError(f"{symbol} on {on}: no EDGAR filer ({row.note})")
            return row
    spans = ", ".join(
        f"[{r.start_date}, {r.end_date or ''})" for r in group
    )
    raise CikError(
        f"{symbol} on {on}: outside every known interval ({spans}); the ticker may have been "
        f"reissued -- do not fall back to a bare-ticker lookup"
    )


def resolve(symbol: str, on: date, index: Index) -> str:
    """The 10-digit CIK of the company trading as ``symbol`` on ``on``."""
    return resolve_row(symbol, on, index).cik  # type: ignore[return-value]


def filers(
    symbol: str, index: Index, start: date | None = None, end: date | None = None
) -> tuple[str, ...]:
    """Every distinct CIK behind ``symbol`` whose tenure meets ``[start, end)``, oldest first.

    ``start`` defaults to the beginning of time and ``end`` to the end of it, so a bare call
    returns every filer the symbol ever had. This is the ingest entry point: Phase 4 fetches
    ``companyfacts`` once per CIK returned here.
    """
    lo = date.min if start is None else start
    hi = _OPEN if end is None else end
    out: list[str] = []
    for row in index.get(symbol, ()):
        if row.cik is None:
            continue
        row_end = _OPEN if row.end_date is None else row.end_date
        if row.start_date < hi and lo < row_end and row.cik not in out:
            out.append(row.cik)
    return tuple(out)


def missing_symbols(index: Index, symbols: Iterable[str]) -> tuple[str, ...]:
    """Those of ``symbols`` with no row at all, sorted."""
    return tuple(sorted(s for s in set(symbols) if s not in index))


def no_filer_symbols(index: Index) -> tuple[str, ...]:
    """Symbols deliberately recorded as having no EDGAR filer, sorted."""
    return tuple(
        sorted(s for s, group in index.items() if any(r.cik is None for r in group))
    )


def _merge(spans: Sequence[tuple[date, date]]) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def coverage_gaps(
    index: Index, intervals: Iterable[Interval], since: date = SINCE
) -> tuple[Gap, ...]:
    """Membership time on or after ``since`` that the map does not answer for.

    Each :class:`~seer_engine.membership.Interval` is clipped to ``[since, ...)`` and matched
    against the symbol's rows. A ``NONE`` row counts as covered: it is an explicit answer.
    An empty result is the R1 guarantee -- every ever-member has a CIK (or a documented
    absence) for every day it was in an index inside the backtest window.
    """
    wanted: dict[str, list[tuple[date, date]]] = {}
    for iv in intervals:
        start = max(iv.start_date, since)
        end = _OPEN if iv.end_date is None else iv.end_date
        if start < end:
            wanted.setdefault(iv.symbol, []).append((start, end))
    gaps: list[Gap] = []
    for symbol in sorted(wanted):
        covered = sorted(
            (row.start_date, _OPEN if row.end_date is None else row.end_date)
            for row in index.get(symbol, ())
        )
        for start, end in _merge(wanted[symbol]):
            cursor = start
            for c_start, c_end in covered:
                if cursor >= end:
                    break
                if c_end <= cursor:
                    continue
                if c_start > cursor:
                    gap_end = min(c_start, end)
                    gaps.append(
                        Gap(symbol, cursor, None if gap_end == _OPEN else gap_end)
                    )
                    cursor = gap_end
                cursor = max(cursor, min(c_end, end))
            if cursor < end:
                gaps.append(Gap(symbol, cursor, None if end == _OPEN else end))
    return tuple(gaps)
```

**Impact:** a new public module. Nothing imports it yet; Phases 2 and 4 will.

---

### Step 2: `engine/scripts/build_ticker_cik.py` — the one-off generator

**File:** `engine/scripts/build_ticker_cik.py` (new file; new directory `engine/scripts/`)
**Change:** The whole script. It is committed so the map is reproducible and the `MANUAL` table
is reviewable in the diff; it is **not** imported by `seer_engine` and runs only by hand.

Tier order, highest wins:

0. `MANUAL` — hand-audited, overrides everything. Seeded below with the six recycled tickers and
   the two in-window filer changes.
1. `current` — SEC `company_tickers.json` (649/795 measured).
2. `edgar` — `browse-edgar?action=getcompany&CIK=<ticker>&output=atom` (+51 measured).
3. `exact` / `fuzzy` — Massive delisted reference → company name → `cik-lookup-data.txt` with
   corporate-suffix stripping, then `difflib` ≥ 0.90 (the remaining 95).

Then the periodic-filing screen (a net, not a gate: it rejected MON/PLL/ALTR's wrong answers and
missed LLL's and DTV's), then the CSV write. Any symbol left unresolved makes the script exit 1
and print the list, so a human adds it to `MANUAL` rather than the file silently shipping a hole.

**Code:**

```python
"""One-off generator for engine/data/ticker_cik.csv. Run by hand, never imported.

    export MASSIVE_API_KEY=...  SEC_CONTACT_EMAIL=you@example.com
    python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv

Every network artifact is cached under --cache (default engine/.cache/cik, gitignored), so a
re-run after editing MANUAL costs nothing. Tier order, highest first:

  0 manual   MANUAL below -- hand-audited, wins over everything
  1 current  https://www.sec.gov/files/company_tickers.json
  2 edgar    https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<ticker>&output=atom
  3 exact    Massive delisted reference -> company name -> cik-lookup-data.txt, suffixes stripped
  4 fuzzy    the same, difflib ratio >= 0.90

Measured 2026-10-05 over the 795 ever-members: MANUAL covers 9 symbols (CA and DTV reach no
tier at all), tier 1 resolves 649 of the rest and tier 2 a further 51, leaving 93 for tiers 3-4.

A ticker alone never identifies a company: tiers 1-2 answer with whoever holds the ticker TODAY.
The screen below (a candidate must have filed a periodic report inside the symbol's membership
span) rejected the wrong answers for MON, PLL and ALTR but NOT for LLL or DTV, so the six
recycled tickers stay in MANUAL permanently.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from seer_engine import config, http, membership  # noqa: E402
from seer_engine.cik import HEADER, SINCE  # noqa: E402

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CIK_LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
BROWSE_EDGAR_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
MASSIVE_TICKERS_URL = "https://api.massive.com/v3/reference/tickers"

SEC_MIN_INTERVAL = 0.15  # SEC allows 10 req/s; stay under it
MASSIVE_MIN_INTERVAL = 12.5  # free tier: 5 calls/min
MASSIVE_MAX_PAGES = 50
FUZZY_CUTOFF = 0.90
PERIODIC_FORMS = frozenset({"10-K", "10-K405", "10-KSB", "10-Q", "20-F", "40-F"})

SUFFIXES = (
    "INC", "CORP", "CORPORATION", "CO", "COMPANY", "PLC", "LTD", "LIMITED", "LP", "LLC",
    "HOLDINGS", "HOLDING", "GROUP", "THE", "CLASS A", "CLASS B", "CLASS C", "COM", "NEW",
)
_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_SPACE = re.compile(r"\s+")

# symbol -> ((cik, start, end, company_name, note), ...). end "" means still current.
# Hand-audited; wins over every automated tier. Every CIK below was confirmed against
# https://data.sec.gov/submissions/CIK<cik>.json on 2026-10-05.
MANUAL: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {
    # --- recycled tickers: EDGAR's ticker lookup answers with today's holder -------------
    "CA": (
        ("0000356028", "2015-01-02", "2018-11-06", "CA, INC.",
         "recycled: CA is now an Xtrackers ETF share class; CA Inc (ex-Computer Associates) "
         "was acquired by Broadcom 2018-11-05"),
    ),
    "MON": (
        ("0001110783", "2015-01-02", "2018-06-07", "MONSANTO CO /NEW/",
         "recycled: browse-edgar answers 0001828325 Monument Circle Acquisition Corp; "
         "Monsanto was acquired by Bayer 2018-06-07"),
    ),
    "PLL": (
        ("0000075829", "2015-01-02", "2015-08-31", "PALL CORP",
         "recycled: browse-edgar answers 0001728205 Piedmont Lithium; Pall Corp was acquired "
         "by Danaher 2015-08-31"),
    ),
    "ALTR": (
        ("0000768251", "2015-01-02", "2015-12-28", "ALTERA CORP",
         "recycled: browse-edgar answers 0001701732 Altair Engineering; Altera was acquired "
         "by Intel 2015-12-28"),
    ),
    "LLL": (
        ("0001039101", "2015-01-02", "2019-07-01", "L3 TECHNOLOGIES, INC.",
         "recycled: browse-edgar answers 0001546383 JX Luxventure, which also filed 5 periodic "
         "reports inside the span, so the filing screen does NOT catch it; L3 merged with "
         "Harris 2019-06-29"),
    ),
    "DTV": (
        ("0001465112", "2015-01-02", "2015-07-27", "DIRECTV",
         "recycled: the ticker now carries DTE Energy corporate units (0000936340), which filed "
         "3 periodic reports inside the span, so the filing screen does NOT catch it; DIRECTV "
         "was acquired by AT&T 2015-07-24"),
    ),
    # --- filer changes inside the window, same ticker -------------------------------------
    "WRK": (
        ("0001636023", "2015-07-02", "2018-11-02", "WRKCo Inc.",
         "WestRock Co until the KapStone close on 2018-11-02, then renamed WRKCo Inc."),
        ("0001732845", "2018-11-02", "2024-07-08", "WestRock Co",
         "Whiskey Holdco became the WestRock registrant at the 2018-11-02 KapStone close; "
         "acquired by Smurfit Kappa 2024-07-05"),
    ),
    "GOOGL": (
        ("0001288776", "2015-01-02", "2015-10-02", "GOOGLE INC.",
         "Google Inc was the registrant until the Alphabet holdco reorg closed 2015-10-02"),
        ("0001652044", "2015-10-02", "", "ALPHABET INC.", "Alphabet holdco reorg 2015-10-02"),
    ),
    "GOOG": (
        ("0001288776", "2015-01-02", "2015-10-02", "GOOGLE INC.",
         "class C of the same filer as GOOGL; Google Inc until 2015-10-02"),
        ("0001652044", "2015-10-02", "", "ALPHABET INC.", "Alphabet holdco reorg 2015-10-02"),
    ),
}


# --- plumbing -----------------------------------------------------------------------------


class BuildError(RuntimeError):
    """The generator cannot produce a trustworthy file."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class SecFetcher:
    """GET from sec.gov with the contact-carrying User-Agent SEC's fair-access policy wants."""

    def __init__(self, contact: str, cache: Path) -> None:
        if "@" not in contact:
            raise BuildError(
                "SEC_CONTACT_EMAIL (or --contact) must be a contact email address; SEC's "
                "fair-access policy requires one in the User-Agent"
            )
        self.user_agent = f"seer-engine ticker_cik builder {contact}"
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self._last = 0.0

    def _pace(self) -> None:
        wait = self._last + SEC_MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def bytes(self, url: str, name: str) -> bytes:
        path = self.cache / name
        if path.exists():
            return path.read_bytes()
        self._pace()
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            body = urllib.request.urlopen(req, timeout=120).read()
        finally:
            self._last = time.monotonic()
        path.write_bytes(body)
        return body

    def text(self, url: str, name: str, encoding: str = "utf-8") -> str:
        return self.bytes(url, name).decode(encoding, "replace")

    def json(self, url: str, name: str) -> Any:
        return json.loads(self.text(url, name))


# --- name normalisation --------------------------------------------------------------------


def canonical_name(raw: str) -> str:
    """Upper-case, punctuation-free, corporate suffixes stripped."""
    text = _PUNCT.sub(" ", raw.upper())
    text = _SPACE.sub(" ", text).strip()
    changed = True
    while changed:
        changed = False
        for suffix in SUFFIXES:
            if text == suffix:
                continue
            if text.startswith(suffix + " "):
                text, changed = text[len(suffix) + 1:].strip(), True
            if text.endswith(" " + suffix):
                text, changed = text[: -len(suffix) - 1].strip(), True
    return text


def load_cik_lookup(fetcher: SecFetcher) -> dict[str, list[str]]:
    """``canonical_name -> [cik, ...]`` from cik-lookup-data.txt (39 MB, latin-1)."""
    text = fetcher.text(CIK_LOOKUP_URL, "cik-lookup-data.txt", encoding="latin-1")
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        parts = line.rstrip(":").rsplit(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            continue
        key = canonical_name(parts[0])
        if not key:
            continue
        cik = parts[1].zfill(10)
        bucket = out.setdefault(key, [])
        if cik not in bucket:
            bucket.append(cik)
    log(f"cik-lookup-data.txt: {len(out)} canonical names")
    return out


# --- tiers ----------------------------------------------------------------------------------


def tier_current(fetcher: SecFetcher) -> dict[str, tuple[str, str]]:
    """``symbol -> (cik, title)`` from company_tickers.json."""
    raw = fetcher.json(COMPANY_TICKERS_URL, "company_tickers.json")
    out: dict[str, tuple[str, str]] = {}
    for entry in raw.values():
        try:
            symbol = membership.normalize_ticker(str(entry["ticker"]))
        except membership.MembershipError:
            continue
        out.setdefault(symbol, (str(entry["cik_str"]).zfill(10), str(entry["title"])))
    log(f"company_tickers.json: {len(out)} tickers")
    return out


_ATOM_CIK = re.compile(r"<cik>(\d+)</cik>")
_ATOM_NAME = re.compile(r"<conformed-name>([^<]*)</conformed-name>")


def tier_edgar(fetcher: SecFetcher, symbol: str) -> tuple[str, str] | None:
    """``(cik, conformed name)`` from EDGAR's ticker lookup, or None."""
    query = urllib.parse.urlencode(
        {
            "action": "getcompany",
            "CIK": symbol.replace(".", "-"),
            "type": "10-K",
            "dateb": "",
            "owner": "include",
            "count": "1",
            "output": "atom",
        }
    )
    body = fetcher.text(f"{BROWSE_EDGAR_URL}?{query}", f"browse-{symbol}.atom")
    cik, name = _ATOM_CIK.search(body), _ATOM_NAME.search(body)
    if cik is None:
        return None
    return cik.group(1).zfill(10), (name.group(1) if name else "")


def massive_delisted_names(api_key: str, cache: Path) -> dict[str, str]:
    """``symbol -> company name`` for every inactive US stock ticker Massive knows.

    ~23,500 tickers over ~24 pages. The free tier allows 5 calls/min, so this takes ~5 minutes
    on a cold cache.
    """
    path = cache / "massive_delisted.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        log(f"massive delisted (cached): {len(data)} tickers")
        return data
    out: dict[str, str] = {}
    url = MASSIVE_TICKERS_URL
    params: dict[str, Any] = {"market": "stocks", "active": "false", "limit": 1000}
    last = 0.0
    for page in range(MASSIVE_MAX_PAGES):
        wait = last + MASSIVE_MIN_INTERVAL - time.monotonic()
        if wait > 0 and page:
            time.sleep(wait)
        try:
            data = http.get_json(url, {**params, "apiKey": api_key}, retries=4, backoff=15.0)
        finally:
            last = time.monotonic()
        for row in data.get("results") or []:
            raw_ticker, name = row.get("ticker"), row.get("name")
            if not raw_ticker or not name:
                continue
            try:
                symbol = membership.normalize_ticker(str(raw_ticker))
            except membership.MembershipError:
                continue
            out.setdefault(symbol, str(name))
        log(f"massive delisted page {page + 1}: {len(out)} tickers so far")
        next_url = data.get("next_url")
        if not next_url:
            break
        url, params = next_url, {}
    else:
        raise BuildError(f"massive delisted: more than {MASSIVE_MAX_PAGES} pages")
    path.write_text(json.dumps(out, indent=0, sort_keys=True), encoding="utf-8")
    return out


def match_name(name: str, lookup: dict[str, list[str]]) -> tuple[str, str, str] | None:
    """``(cik, matched name, 'exact'|'fuzzy')`` for a company name, or None."""
    key = canonical_name(name)
    if not key:
        return None
    hit = lookup.get(key)
    if hit and len(hit) == 1:
        return hit[0], key, "exact"
    if hit:
        return hit[0], key, "exact"
    close = difflib.get_close_matches(key, lookup.keys(), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return lookup[close[0]][0], close[0], "fuzzy"
    return None


# --- the periodic-filing screen ---------------------------------------------------------------


def filed_inside(fetcher: SecFetcher, cik: str, start: date, end: date | None) -> int:
    """How many periodic reports ``cik`` filed with filingDate in ``[start, end)``."""
    data = fetcher.json(SUBMISSIONS_URL.format(cik=cik), f"submissions-{cik}.json")
    lo, hi = start.isoformat(), (end.isoformat() if end else "9999-12-31")
    count = 0

    def take(block: dict[str, Any]) -> None:
        nonlocal count
        for form, filed in zip(block.get("form", []), block.get("filingDate", [])):
            if form in PERIODIC_FORMS and lo <= filed < hi:
                count += 1

    take(data.get("filings", {}).get("recent", {}))
    for extra in data.get("filings", {}).get("files", []):
        take(fetcher.json(
            "https://data.sec.gov/submissions/" + extra["name"], f"submissions-{extra['name']}"
        ))
    return count


# --- assembly -----------------------------------------------------------------------------


def spans(intervals: Iterable[membership.Interval]) -> dict[str, tuple[date, date | None]]:
    """``symbol -> (start, end)``: the hull of its membership, clipped to ``[SINCE, ...)``.

    The hull, not the individual intervals: a symbol that leaves an index and rejoins still had
    a filer in between, so covering the gap is both correct and simpler.
    """
    out: dict[str, tuple[date, date | None]] = {}
    for iv in intervals:
        start = max(iv.start_date, SINCE)
        if iv.end_date is not None and iv.end_date <= SINCE:
            continue
        prev = out.get(iv.symbol)
        if prev is None:
            out[iv.symbol] = (start, iv.end_date)
            continue
        p_start, p_end = prev
        new_end = None if (p_end is None or iv.end_date is None) else max(p_end, iv.end_date)
        out[iv.symbol] = (min(p_start, start), new_end)
    return out


def build(args: argparse.Namespace) -> int:
    cache = Path(args.cache).resolve()
    contact = args.contact or os.environ.get("SEC_CONTACT_EMAIL") or ""
    fetcher = SecFetcher(contact, cache)

    intervals = membership.compute_universe(membership.DATA_DIR)
    span = spans(intervals)
    symbols = sorted(span)
    log(f"ever-members since {SINCE}: {len(symbols)}")

    rows: list[dict[str, str]] = []
    resolved: set[str] = set()
    counts: dict[str, int] = {s: 0 for s in ("manual", "current", "edgar", "exact", "fuzzy")}

    # tier 0 -- manual
    for symbol, entries in MANUAL.items():
        if symbol not in span:
            raise BuildError(f"MANUAL has {symbol}, which is not an ever-member since {SINCE}")
        for cik, start, end, name, note in entries:
            rows.append(
                {
                    "symbol": symbol, "cik": cik, "start_date": start, "end_date": end,
                    "company_name": name, "source": "manual", "note": note,
                }
            )
        resolved.add(symbol)
        counts["manual"] += 1

    # tier 1 -- company_tickers.json
    current = tier_current(fetcher)
    for symbol in symbols:
        if symbol in resolved or symbol not in current:
            continue
        cik, name = current[symbol]
        rows.append(_row(symbol, cik, name, "current", "", span))
        resolved.add(symbol)
        counts["current"] += 1

    # tier 2 -- EDGAR's ticker lookup
    for symbol in symbols:
        if symbol in resolved:
            continue
        hit = tier_edgar(fetcher, symbol)
        if hit is None:
            continue
        cik, name = hit
        rows.append(_row(symbol, cik, name, "edgar", "", span))
        resolved.add(symbol)
        counts["edgar"] += 1

    # tiers 3-4 -- Massive delisted name -> cik-lookup-data.txt
    remaining = [s for s in symbols if s not in resolved]
    if remaining:
        log(f"{len(remaining)} symbols need the name-matching path")
        names = massive_delisted_names(config.require("MASSIVE_API_KEY"), cache)
        lookup = load_cik_lookup(fetcher)
        for symbol in remaining:
            raw_name = names.get(symbol)
            if not raw_name:
                continue
            hit = match_name(raw_name, lookup)
            if hit is None:
                continue
            cik, matched, kind = hit
            note = f"massive name {raw_name!r} -> cik-lookup {matched!r} ({kind})"
            rows.append(_row(symbol, cik, raw_name, kind, note, span))
            resolved.add(symbol)
            counts[kind] += 1

    unresolved = [s for s in symbols if s not in resolved]
    if unresolved:
        log("")
        log(f"UNRESOLVED ({len(unresolved)}) -- add each to MANUAL after checking EDGAR by hand:")
        for symbol in unresolved:
            start, end = span[symbol]
            log(f"  {symbol:8s} {start} .. {end or 'open'}")
        return 1

    # the screen
    suspect: list[str] = []
    for row in rows:
        start = date.fromisoformat(row["start_date"])
        end = date.fromisoformat(row["end_date"]) if row["end_date"] else None
        if filed_inside(fetcher, row["cik"], start, end) == 0:
            suspect.append(f"{row['symbol']} -> {row['cik']} {row['company_name']}")
    if suspect:
        log("")
        log(f"SCREEN ({len(suspect)}) -- no periodic filing inside the span; wrong company, a "
            f"filer change mid-span, or a genuinely silent filer. Resolve each in MANUAL:")
        for line in suspect:
            log(f"  {line}")
        return 1

    rows.sort(key=lambda r: (r["symbol"], r["start_date"]))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(HEADER), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    log("")
    log(f"wrote {out_path}: {len(rows)} rows, {len(resolved)} symbols")
    log("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def _row(
    symbol: str,
    cik: str,
    name: str,
    source: str,
    note: str,
    span: dict[str, tuple[date, date | None]],
) -> dict[str, str]:
    start, end = span[symbol]
    return {
        "symbol": symbol,
        "cik": cik,
        "start_date": start.isoformat(),
        "end_date": end.isoformat() if end else "",
        "company_name": name,
        "source": source,
        "note": note,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="engine/data/ticker_cik.csv")
    parser.add_argument("--cache", default="engine/.cache/cik")
    parser.add_argument("--contact", default=None, help="defaults to $SEC_CONTACT_EMAIL")
    try:
        return build(parser.parse_args(argv))
    except (BuildError, config.ConfigError) as exc:
        log(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

**Impact:** new directory `engine/scripts/`. `python -m ruff check engine` now lints it; the
`# noqa: E402` comments are required because `sys.path` must be set before the `seer_engine`
imports (ruff's `E402` is not in the selected rule set today, but the comments keep it safe if
the set ever widens).

---

### Step 3: generate and commit `engine/data/ticker_cik.csv`

**File:** `engine/data/ticker_cik.csv` (new, generated)
**Change:** Run the generator, hand-audit every `fuzzy` and `manual` row, iterate on `MANUAL`
until the script exits 0, then commit the CSV as data.

```sh
cd /home/miftah/.worktrees/seer/edgar-fundamentals
export SEC_CONTACT_EMAIL='<your contact address>'
export MASSIVE_API_KEY='<from .env.local>'
python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv --cache engine/.cache/cik
```

Expect two or three passes — the first will leave roughly 93 symbols for the name-matching path
and surface the mid-span filer changes through the screen. Each non-zero exit prints either the unresolved symbols or the
screen's suspects; for each one, open
`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>&type=10-K&output=atom`
and `https://data.sec.gov/submissions/CIK<cik>.json`, confirm the conformed name and the filing
dates, and add a `MANUAL` entry with a note that records what you checked. **Never** paste a tier
1/2 answer into `MANUAL` without that check — that is the whole failure this file exists to stop.

Known cases to expect in the first pass:

- `NDOI` — an NDX member 2007-02-01 .. 2016-07-18 (replaced by `MCHP`). The ticker is not
  resolvable through any tier; it is almost certainly a transcription artifact in the
  Wikipedia-derived `ndx_history.csv`. Identify the company from the Wikipedia Nasdaq-100 change
  table for 2016-07-18 before adding it to `MANUAL`. If it turns out to be a phantom with no
  filer, give it a `cik` of `NONE` with a note saying so — the loader accepts exactly one such
  row per symbol and `resolve` then raises instead of guessing.
- `ADS` (→ Bread Financial Holdings, **0001101215** — same CIK, a pure rename) and
  `CCE` (Coca-Cola Enterprises Inc, **0001491675**; the Coca-Cola European Partners entity that
  took over in 2016 is **0001650107** and trades as `CCEP`, which is its own ever-member). Both
  verified in `cik-lookup-data.txt` on 2026-10-05; they are renames rather than delistings and
  so are absent from Massive's delisted list.
- Any symbol whose filer changed mid-span surfaces through the screen as "no periodic filing
  inside the span" for the part of the span the single row does not cover — split it into two
  `MANUAL` rows the way `WRK` and `GOOGL` already are.

The committed head of the file looks like this (the first rows, alphabetically):

```csv
symbol,cik,start_date,end_date,company_name,source,note
A,0001090872,2015-01-02,,"Agilent Technologies, Inc.",current,
AABA,0001011006,2015-01-02,2017-06-19,ALTABA INC.,exact,"massive name 'Altaba Inc.' -> cik-lookup 'ALTABA' (exact)"
AAL,0000006201,2015-01-02,,American Airlines Group Inc.,current,
```

**Impact:** ~800+ committed rows (795 symbols; `WRK`, `GOOG`, `GOOGL` and any other mid-span
filer change contribute a second row each). The file is text, diffable, and sorted so a
re-vendoring diff is reviewable.

---

### Step 4: document it in `engine/data/SOURCES.md`

**File:** `engine/data/SOURCES.md` — two edits.

**Edit 4a — the intro, lines 3-5.** Replace:

```markdown
Vendored inputs for `seer_engine.membership` / `python -m seer_engine universe refresh`, and the
SPY dividend history for the backtest benchmark (`seer_engine.backtest`).
Owner of this directory: the engine. Read by nothing else.
```

with:

```markdown
Vendored inputs for `seer_engine.membership` / `python -m seer_engine universe refresh`, the
SPY dividend history for the backtest benchmark (`seer_engine.backtest`), and the ticker -> SEC
CIK map for the fundamentals pipeline (`seer_engine.cik`).
Owner of this directory: the engine. Read by nothing else.
```

**Edit 4b — append after the final line of the file (line 139, the closing ``` of the
spy_dividends refresh heredoc):**

```markdown

## ticker_cik.csv: ticker -> SEC CIK, point in time

| | |
|---|---|
| Upstream | SEC EDGAR: `https://www.sec.gov/files/company_tickers.json`, `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<ticker>&output=atom`, `https://www.sec.gov/Archives/edgar/cik-lookup-data.txt`, `https://data.sec.gov/submissions/CIK<cik>.json`; company names for dead tickers from Massive `/v3/reference/tickers?market=stocks&active=false` |
| Generated by | `engine/scripts/build_ticker_cik.py` (committed; run by hand, never imported) |
| Fetched | 2026-10-05 |
| Scope | every S&P 500 / Nasdaq-100 ever-member on or after 2015-01-02 — `membership.symbols_since(membership.compute_universe(), date(2015, 1, 2))`, **795** symbols on 2026-10-05 |
| Rows | _(fill from the generator's last line)_ |
| License | US government work, public domain (SEC). Massive is used only for company names, which are facts, not for redistributed data. |
| sha256 | _(fill with `sha256sum engine/data/ticker_cik.csv`)_ |

`symbol,cik,start_date,end_date,company_name,source,note`, sorted by `(symbol, start_date)`.
One row per **(symbol, filer) tenure**: `cik` is the SEC Central Index Key of the company whose
shares traded under `symbol` over `[start_date, end_date)`. `end_date` is **exclusive** and
empty while the mapping is still current — the same semantics as `universe.end_date`. `cik` is
exactly 10 digits, zero-padded, or the literal `NONE` for a symbol with no EDGAR filer at all
(`note` is then mandatory and the row must be the symbol's only one). `source` is how the row
was produced: `current` (company_tickers.json), `edgar` (EDGAR's ticker lookup), `exact` /
`fuzzy` (company-name match against cik-lookup-data.txt), `manual` (hand-audited in
`build_ticker_cik.py`). `note` is mandatory for `fuzzy` and `manual`.

**Why there is an interval and not a bare pair.** A ticker alone never identifies a company.
Measured 2026-10-05, EDGAR's own ticker lookup answers `MON` with Monument Circle Acquisition
Corp (`0001828325`), `PLL` with Piedmont Lithium (`0001728205`), `ALTR` with Altair Engineering
(`0001701732`) and `LLL` with JX Luxventure (`0001546383`) — in every case the company holding
the recycled ticker today, not the index member that held it in the backtest window. `CA` and
`DTV` have been reissued too (an Xtrackers ETF share class and DTE Energy corporate units).
Separately, two symbols change filer *inside* the window without changing ticker: `WRK`
(WestRock `0001636023` → `0001732845` at the 2018-11-02 KapStone close) and `GOOG`/`GOOGL`
(Google Inc `0001288776` → Alphabet `0001652044` at the 2015-10-02 holdco reorg).

The reverse is not an error: **one CIK legitimately backs several symbols.** Among the
ever-members `GOOG`/`GOOGL`, `FOX`/`FOXA`, `NWS`/`NWSA`, `UA`/`UAA`, `CMCSA`/`CMCSK` and
`BATRA`/`BATRK` are share classes of a single filer. No uniqueness check is applied to `cik`.

`seer_engine.cik.load_ticker_cik` rejects a header that is not exactly the seven columns above,
a `cik` that is not 10 digits (or `NONE`), a bad or non-increasing date, an unknown `source`, a
missing required `note`, a file not sorted by `(symbol, start_date)`, a duplicate
`(symbol, start_date)`, two overlapping intervals for one symbol, an open interval that is not
the symbol's last row, and a `NONE` row that shares its symbol with another row.
`tests/test_cik.py` additionally asserts that the vendored file covers every ever-member with no
coverage gap, and that each of `CA`, `MON`, `PLL`, `ALTR`, `LLL` and `DTV` resolves to the
company that held the ticker during its membership and raises for a date after it.

### Re-vendoring

```sh
export SEC_CONTACT_EMAIL='<a contact address, as SEC's fair-access policy requires>'
export MASSIVE_API_KEY='<from .env.local>'
python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv --cache engine/.cache/cik
```

Network artifacts are cached under `--cache` (gitignored), so re-runs after editing `MANUAL`
cost nothing; delete the cache to refetch. The script exits 1 and prints a list when a symbol is
unresolved or when a candidate CIK filed no periodic report inside the symbol's span — resolve
each by hand against `https://data.sec.gov/submissions/CIK<cik>.json` and add a `MANUAL` entry
with a note recording what you checked. Measured 2026-10-05, the tiers resolved 649 / 51 / 95 of
the 795 symbols. The filing screen is a net, not a gate: it rejected the wrong candidates for
`MON`, `PLL` and `ALTR` but **not** for `LLL` or `DTV`, so the six recycled tickers stay in
`MANUAL` permanently. Then update the Rows and sha256 lines above and run
`pytest engine/tests/test_cik.py`.

Measured on 2026-10-05, tiers 1-2 plus the `MANUAL` seeds resolve 702 of the 795 symbols; the
remaining 93 come from the name-matching path.
```

**Impact:** documentation only.

---

### Step 5: `engine/tests/test_cik.py`

**File:** `engine/tests/test_cik.py` (new file)
**Change:** The whole test module. No database, no network, no skips — CI fails the run if
anything skips.

**Code:**

```python
"""Phase 1: the vendored ticker -> CIK map (engine/src/seer_engine/cik.py)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from seer_engine import cik as c
from seer_engine import membership as m
from seer_engine.cik import CikError, CikRow, Gap

D = date.fromisoformat

HEADER_LINE = ",".join(c.HEADER)


def write(path: Path, *rows: str) -> Path:
    path.write_text("\n".join((HEADER_LINE, *rows)) + "\n", encoding="utf-8")
    return path


def csv_file(tmp_path: Path, *rows: str) -> Path:
    return write(tmp_path / "ticker_cik.csv", *rows)


# --- normalize_cik ---------------------------------------------------------------------


def test_normalize_cik_pads_and_strips():
    assert c.normalize_cik("356028") == "0000356028"
    assert c.normalize_cik(" 0000356028 ") == "0000356028"
    assert c.normalize_cik("CIK0000356028") == "0000356028"


@pytest.mark.parametrize("bad", ["", "   ", "abc", "12345678901", "0000000000", "35,028"])
def test_normalize_cik_rejects_rubbish(bad):
    with pytest.raises(CikError, match="not a CIK"):
        c.normalize_cik(bad)


# --- loading ---------------------------------------------------------------------------


def test_load_reads_a_row(tmp_path):
    path = csv_file(tmp_path, "MON,0001110783,2015-01-02,2018-06-07,MONSANTO CO /NEW/,manual,bayer")
    assert c.load_ticker_cik(path) == [
        CikRow("MON", "0001110783", D("2015-01-02"), D("2018-06-07"),
               "MONSANTO CO /NEW/", "manual", "bayer")
    ]


def test_load_empty_end_date_means_open(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2015-01-02,,Apple Inc.,current,")
    (row,) = c.load_ticker_cik(path)
    assert row.end_date is None
    assert row.covers(D("2015-01-02")) and row.covers(D("2099-01-01"))
    assert not row.covers(D("2015-01-01"))


def test_load_rejects_a_bad_header(tmp_path):
    path = tmp_path / "ticker_cik.csv"
    path.write_text("symbol,cik\nAAPL,0000320193\n", encoding="utf-8")
    with pytest.raises(CikError, match="expected header"):
        c.load_ticker_cik(path)


def test_load_rejects_an_empty_file(tmp_path):
    with pytest.raises(CikError, match="no rows"):
        c.load_ticker_cik(csv_file(tmp_path))


@pytest.mark.parametrize("cell", ["320193", "00003201930", "abcdefghij", "0000000000", ""])
def test_load_rejects_a_cik_that_is_not_ten_digits(tmp_path, cell):
    path = csv_file(tmp_path, f"AAPL,{cell},2015-01-02,,Apple Inc.,current,")
    with pytest.raises(CikError, match="cik must be 10 digits"):
        c.load_ticker_cik(path)


def test_load_rejects_a_bad_symbol(tmp_path):
    path = csv_file(tmp_path, "Apple Inc,0000320193,2015-01-02,,Apple Inc.,current,")
    with pytest.raises(CikError, match="not a ticker"):
        c.load_ticker_cik(path)


def test_load_rejects_an_unknown_source(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2015-01-02,,Apple Inc.,guessed,")
    with pytest.raises(CikError, match="source must be one of"):
        c.load_ticker_cik(path)


@pytest.mark.parametrize("source", ["fuzzy", "manual"])
def test_load_requires_a_note_for_fuzzy_and_manual(tmp_path, source):
    path = csv_file(tmp_path, f"AAPL,0000320193,2015-01-02,,Apple Inc.,{source},")
    with pytest.raises(CikError, match="note is required"):
        c.load_ticker_cik(path)


def test_load_requires_a_company_name_when_there_is_a_cik(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2015-01-02,,,current,")
    with pytest.raises(CikError, match="company_name is required"):
        c.load_ticker_cik(path)


def test_load_rejects_end_before_start(tmp_path):
    path = csv_file(tmp_path, "AAPL,0000320193,2016-01-02,2015-01-02,Apple Inc.,current,")
    with pytest.raises(CikError, match="must be after start_date"):
        c.load_ticker_cik(path)


def test_load_rejects_a_duplicate_row(tmp_path):
    path = csv_file(
        tmp_path,
        "AAPL,0000320193,2015-01-02,2016-01-02,Apple Inc.,current,",
        "AAPL,0000320193,2015-01-02,,Apple Inc.,current,",
    )
    with pytest.raises(CikError, match="duplicate row for AAPL"):
        c.load_ticker_cik(path)


def test_load_rejects_overlapping_intervals_for_one_symbol(tmp_path):
    path = csv_file(
        tmp_path,
        "WRK,0001636023,2015-07-02,2019-01-01,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    with pytest.raises(CikError, match="intervals overlap"):
        c.load_ticker_cik(path)


def test_load_rejects_an_open_interval_that_is_not_last(tmp_path):
    path = csv_file(
        tmp_path,
        "WRK,0001636023,2015-07-02,,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    with pytest.raises(CikError, match="only the last row may be open"):
        c.load_ticker_cik(path)


def test_load_rejects_an_unsorted_file(tmp_path):
    path = csv_file(
        tmp_path,
        "MSFT,0000789019,2015-01-02,,Microsoft Corp,current,",
        "AAPL,0000320193,2015-01-02,,Apple Inc.,current,",
    )
    with pytest.raises(CikError, match="must be sorted"):
        c.load_ticker_cik(path)


def test_load_accepts_adjacent_intervals(tmp_path):
    path = csv_file(
        tmp_path,
        "WRK,0001636023,2015-07-02,2018-11-02,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    assert [r.cik for r in c.load_ticker_cik(path)] == ["0001636023", "0001732845"]


def test_none_row_must_be_the_only_row_for_its_symbol(tmp_path):
    path = csv_file(
        tmp_path,
        "NDOI,NONE,2015-01-02,2016-01-01,,manual,phantom",
        "NDOI,0000320193,2016-01-01,2016-07-18,Apple Inc.,manual,x",
    )
    with pytest.raises(CikError, match="must be the symbol's only row"):
        c.load_ticker_cik(path)


def test_none_row_requires_a_note(tmp_path):
    path = csv_file(tmp_path, "NDOI,NONE,2015-01-02,2016-07-18,,manual,")
    with pytest.raises(CikError, match="note is required"):
        c.load_ticker_cik(path)


# --- resolving -------------------------------------------------------------------------


def index(*rows: str) -> dict[str, tuple[CikRow, ...]]:
    import io

    import csv as _csv

    text = "\n".join((HEADER_LINE, *rows)) + "\n"
    reader = _csv.DictReader(io.StringIO(text))
    return c.build_index(
        CikRow(
            symbol=r["symbol"],
            cik=None if r["cik"] == c.NO_FILER else r["cik"],
            start_date=D(r["start_date"]),
            end_date=D(r["end_date"]) if r["end_date"] else None,
            company_name=r["company_name"],
            source=r["source"],
            note=r["note"],
        )
        for r in reader
    )


WRK_ROWS = (
    "WRK,0001636023,2015-07-02,2018-11-02,WRKCo Inc.,manual,old",
    "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
)


def test_resolve_picks_the_interval_the_date_falls_in():
    ix = index(*WRK_ROWS)
    assert c.resolve("WRK", D("2016-01-04"), ix) == "0001636023"
    assert c.resolve("WRK", D("2018-11-01"), ix) == "0001636023"
    assert c.resolve("WRK", D("2018-11-02"), ix) == "0001732845"
    assert c.resolve("WRK", D("2024-07-07"), ix) == "0001732845"


def test_resolve_before_and_after_every_interval_raises():
    ix = index(*WRK_ROWS)
    with pytest.raises(CikError, match="outside every known interval"):
        c.resolve("WRK", D("2015-01-02"), ix)
    with pytest.raises(CikError, match="outside every known interval"):
        c.resolve("WRK", D("2024-07-08"), ix)


def test_resolve_an_unknown_symbol_raises():
    with pytest.raises(CikError, match="no row in"):
        c.resolve("ZZZZ", D("2016-01-04"), index(*WRK_ROWS))


def test_resolve_a_no_filer_row_raises_with_the_note():
    ix = index("NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom ticker in ndx_history.csv")
    with pytest.raises(CikError, match="phantom ticker"):
        c.resolve("NDOI", D("2016-01-04"), ix)


def test_filers_lists_each_cik_once_oldest_first():
    ix = index(*WRK_ROWS)
    assert c.filers("WRK", ix) == ("0001636023", "0001732845")
    assert c.filers("WRK", ix, D("2019-01-01"), D("2020-01-01")) == ("0001732845",)
    assert c.filers("WRK", ix, D("2015-01-02"), D("2016-01-02")) == ("0001636023",)
    assert c.filers("WRK", ix, D("2024-07-08"), None) == ()
    assert c.filers("ZZZZ", ix) == ()


def test_filers_skips_no_filer_rows():
    ix = index("NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom")
    assert c.filers("NDOI", ix) == ()


def test_missing_and_no_filer_symbols():
    ix = index(*WRK_ROWS, "NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom")
    assert c.missing_symbols(ix, ["WRK", "NDOI", "AAPL", "MSFT"]) == ("AAPL", "MSFT")
    assert c.no_filer_symbols(ix) == ("NDOI",)


# --- coverage --------------------------------------------------------------------------


def iv(symbol: str, start: str, end: str | None) -> m.Interval:
    return m.Interval(symbol, "SP500", D(start), D(end) if end else None, symbol)


def test_coverage_gaps_is_empty_when_the_rows_span_the_membership():
    ix = index(*WRK_ROWS)
    assert c.coverage_gaps(ix, [iv("WRK", "2015-07-02", "2024-07-08")]) == ()


def test_coverage_gaps_reports_an_uncovered_head():
    ix = index("WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new")
    assert c.coverage_gaps(ix, [iv("WRK", "2015-07-02", "2024-07-08")]) == (
        Gap("WRK", D("2015-07-02"), D("2018-11-02")),
    )


def test_coverage_gaps_reports_an_uncovered_tail_as_open():
    ix = index("AAPL,0000320193,2015-01-02,2020-01-02,Apple Inc.,current,")
    assert c.coverage_gaps(ix, [iv("AAPL", "2015-01-02", None)]) == (
        Gap("AAPL", D("2020-01-02"), None),
    )


def test_coverage_gaps_reports_a_hole_between_two_rows():
    ix = index(
        "WRK,0001636023,2015-07-02,2017-01-02,WRKCo Inc.,manual,old",
        "WRK,0001732845,2018-11-02,2024-07-08,WestRock Co,manual,new",
    )
    assert c.coverage_gaps(ix, [iv("WRK", "2015-07-02", "2024-07-08")]) == (
        Gap("WRK", D("2017-01-02"), D("2018-11-02")),
    )


def test_coverage_gaps_ignores_membership_before_since():
    ix = index("CA,0000356028,2015-01-02,2018-11-06,\"CA, INC.\",manual,recycled")
    assert c.coverage_gaps(ix, [iv("CA", "1996-01-02", "2018-11-06")]) == ()


def test_coverage_gaps_counts_a_no_filer_row_as_an_answer():
    ix = index("NDOI,NONE,2015-01-02,2016-07-18,,manual,phantom")
    assert c.coverage_gaps(ix, [iv("NDOI", "2007-02-01", "2016-07-18")]) == ()


def test_coverage_gaps_merges_a_leave_and_rejoin():
    ix = index("AAPL,0000320193,2015-01-02,,Apple Inc.,current,")
    intervals = [iv("AAPL", "2015-01-02", "2017-01-02"), iv("AAPL", "2019-01-02", None)]
    assert c.coverage_gaps(ix, intervals) == ()


# --- the vendored file -------------------------------------------------------------------


@pytest.fixture(scope="module")
def vendored_index() -> dict[str, tuple[CikRow, ...]]:
    return c.load_index(c.DATA_DIR)


@pytest.fixture(scope="module")
def ever_members() -> frozenset[str]:
    return m.symbols_since(m.compute_universe(m.DATA_DIR), c.SINCE)


def test_vendored_file_loads_and_is_big_enough(vendored_index, ever_members):
    assert len(ever_members) >= 780
    assert len(vendored_index) == len(ever_members)


def test_vendored_covers_every_ever_member(vendored_index, ever_members):
    assert c.missing_symbols(vendored_index, ever_members) == ()


def test_vendored_has_no_coverage_gap(vendored_index):
    gaps = c.coverage_gaps(vendored_index, m.compute_universe(m.DATA_DIR))
    assert gaps == (), f"{len(gaps)} uncovered stretches, first: {gaps[:5]}"


def test_vendored_has_no_symbol_outside_the_universe(vendored_index, ever_members):
    assert set(vendored_index) <= set(ever_members)


def test_vendored_every_cik_is_ten_digits(vendored_index):
    bad = [
        (row.symbol, row.cik)
        for group in vendored_index.values()
        for row in group
        if row.cik is not None and (len(row.cik) != 10 or not row.cik.isdigit())
    ]
    assert bad == []


# symbol -> (a date inside its membership, the historical filer, the company EDGAR's ticker
# lookup answers with today -- None where EDGAR has no answer at all). Every CIK below was
# confirmed against data.sec.gov/submissions on 2026-10-05.
RECYCLED: dict[str, tuple[date, str, str | None]] = {
    "CA": (D("2016-06-01"), "0000356028", None),
    "MON": (D("2016-06-01"), "0001110783", "0001828325"),
    "PLL": (D("2015-06-01"), "0000075829", "0001728205"),
    "ALTR": (D("2015-06-01"), "0000768251", "0001701732"),
    "LLL": (D("2016-06-01"), "0001039101", "0001546383"),
    "DTV": (D("2015-06-01"), "0001465112", "0000936340"),
}


@pytest.mark.parametrize("symbol", sorted(RECYCLED))
def test_vendored_recycled_ticker_resolves_to_the_historical_company(symbol, vendored_index):
    """R1: during membership the map answers with the index member, never today's holder."""
    on, historical, current_holder = RECYCLED[symbol]
    assert c.resolve(symbol, on, vendored_index) == historical
    if current_holder is not None:
        assert c.resolve(symbol, on, vendored_index) != current_holder


@pytest.mark.parametrize("symbol", sorted(RECYCLED))
def test_vendored_recycled_ticker_has_no_answer_today(symbol, vendored_index):
    """And after the membership ended it refuses to answer rather than guessing."""
    with pytest.raises(CikError, match="outside every known interval"):
        c.resolve(symbol, D("2026-10-05"), vendored_index)


# symbol -> (date inside membership, CIK). Confirmed against data.sec.gov/submissions 2026-10-05.
SPOT_CHECKS: dict[str, tuple[date, str]] = {
    "ATVI": (D("2020-01-02"), "0000718877"),  # ACTIVISION BLIZZARD, INC.
    "TWTR": (D("2020-01-02"), "0001418091"),  # TWITTER, INC.
    "SIVB": (D("2020-01-02"), "0000719739"),  # SVB FINANCIAL GROUP
    "CELG": (D("2016-06-01"), "0000816284"),  # CELGENE CORP /DE/
    "K": (D("2020-01-02"), "0000055067"),     # KELLANOVA, formerly KELLOGG CO
    "PXD": (D("2020-01-02"), "0001038357"),   # PIONEER NATURAL RESOURCES CO
    "AAPL": (D("2020-01-02"), "0000320193"),  # Apple Inc.
}


@pytest.mark.parametrize("symbol", sorted(SPOT_CHECKS))
def test_vendored_spot_checks(symbol, vendored_index):
    on, expected = SPOT_CHECKS[symbol]
    assert c.resolve(symbol, on, vendored_index) == expected


def test_vendored_westrock_changes_filer_mid_membership(vendored_index):
    """WRK keeps its ticker across the 2018-11-02 KapStone close but changes registrant."""
    assert c.resolve("WRK", D("2016-01-04"), vendored_index) == "0001636023"
    assert c.resolve("WRK", D("2020-01-02"), vendored_index) == "0001732845"
    assert c.filers("WRK", vendored_index) == ("0001636023", "0001732845")


def test_vendored_alphabet_reorg_is_dated(vendored_index):
    for symbol in ("GOOG", "GOOGL"):
        assert c.resolve(symbol, D("2015-06-01"), vendored_index) == "0001288776"
        assert c.resolve(symbol, D("2020-01-02"), vendored_index) == "0001652044"


SHARE_CLASSES = [("GOOG", "GOOGL"), ("FOX", "FOXA"), ("NWS", "NWSA"), ("UA", "UAA")]


@pytest.mark.parametrize("a,b", SHARE_CLASSES)
def test_vendored_share_classes_share_a_cik(a, b, vendored_index):
    """One CIK backing two symbols is correct, not a duplicate to be de-duplicated."""
    on = D("2020-01-02")
    assert c.resolve(a, on, vendored_index) == c.resolve(b, on, vendored_index)


def test_vendored_notes_are_present_where_required(vendored_index):
    missing = [
        (row.symbol, row.source)
        for group in vendored_index.values()
        for row in group
        if not row.note and (row.source in c.NOTE_REQUIRED or row.cik is None)
    ]
    assert missing == []
```

**Impact:** 50-odd new tests, no DB fixture, no network, no skips.

A note on `test_vendored_file_loads_and_is_big_enough`: it asserts `len(ever_members) >= 780`
rather than `== 795`. The membership overrides move with Wikipedia, so an exact count would
break on an unrelated `universe` refresh. Coverage is asserted exactly, by
`missing_symbols(...) == ()` and `coverage_gaps(...) == ()` — those are the real R1 guarantees
and they stay correct as the universe grows, provided `ticker_cik.csv` is regenerated alongside.

---

## Verification

**Build:**

```sh
cd /home/miftah/.worktrees/seer/edgar-fundamentals
python -m pip install -e 'engine[dev]'
python -m ruff check engine
```

**Tests:**

```sh
python -m pytest engine/tests/test_cik.py -q -rs
python -m pytest engine/tests -q -rs    # nothing else may regress, nothing may SKIP
```

**Manual check:**

```sh
# the file is sorted, has the right header, and its CIKs are all 10 digits
head -1 engine/data/ticker_cik.csv
wc -l engine/data/ticker_cik.csv
sha256sum engine/data/ticker_cik.csv        # paste into SOURCES.md
awk -F, 'NR>1 && $2 != "NONE" && $2 !~ /^[0-9]{10}$/ {print NR": "$0}' engine/data/ticker_cik.csv
grep -E '^(CA|MON|PLL|ALTR|LLL|DTV|WRK|GOOG|GOOGL),' engine/data/ticker_cik.csv

# the generator is idempotent on a warm cache: a re-run must leave the file byte-identical
cp engine/data/ticker_cik.csv /tmp/ticker_cik.before
python engine/scripts/build_ticker_cik.py --out engine/data/ticker_cik.csv --cache engine/.cache/cik
diff /tmp/ticker_cik.before engine/data/ticker_cik.csv && echo IDEMPOTENT
```

Read every `source=fuzzy` and `source=manual` row before committing:

```sh
awk -F, '$6=="fuzzy" || $6=="manual"' engine/data/ticker_cik.csv
```

**Exit criteria:**

1. `python -m pytest engine/tests -q` passes with zero failures and zero skips.
2. `python -m ruff check engine` is clean.
3. `cik.missing_symbols(cik.load_index(), membership.symbols_since(membership.compute_universe(), date(2015,1,2))) == ()`.
4. `cik.coverage_gaps(cik.load_index(), membership.compute_universe()) == ()`.
5. `cik.resolve(s, d, index)` returns the historical filer for each of CA, MON, PLL, ALTR, LLL,
   DTV on a date inside its membership, and raises `CikError` for 2026-10-05.
6. `SOURCES.md` carries a `ticker_cik.csv` section with the real row count and the real sha256.

---

## Handoffs

- **Phase 2 — the `ticker_cik` table, settled; this paragraph is the reconciled version.** This
  phase ships only the CSV. Phase 2's shipped table does **not** mirror the CSV one-for-one, and
  the draft of this handoff (which asked for `cik char(10)` and `company_name`) was wrong on two
  columns. The real shape, which phase 4's `sync_ticker_cik` maps onto:
  `symbol text`, **`cik bigint`** (`int(row.cik)`; the CSV's zero padding is presentation, not
  data), `start_date date`, `end_date date NULL`, **`company text`** (from the CSV's
  `company_name`), `source text` with a CHECK over this phase's five tier labels
  (`current, edgar, exact, fuzzy, manual`), `note text`, `PRIMARY KEY (symbol, start_date)` and
  `CHECK (end_date IS NULL OR end_date > start_date)` — `universe`'s exclusive-end convention.
  Because the column is `NOT NULL bigint`, the `NONE` sentinel **cannot** be stored: phase 4
  skips those rows and they stay CSV-only, which is where `resolve_window_cik` reads them from
  anyway. **No unique constraint on `cik`** — share classes legitimately share one, and phase
  6's panel join depends on the fan-out.
- **Phase 3 — `SEC_CONTACT_EMAIL`.** The generator already reads the env var of that exact name
  (falling back to `--contact`). Phase 3 adds it to `config.py` and `.env.example`; nothing here
  needs to change when it does.
- **Phase 4 — the ingest.** Use `cik.load_index()` once, then `cik.filers(symbol, index)` to get
  the CIKs to fetch per symbol and `cik.resolve(symbol, on, index)` on any read path that needs
  a point-in-time answer. Call `cik.coverage_gaps(index, intervals)` as a pre-flight and refuse
  to run on a non-empty result — that turns a stale map into a loud failure instead of a silently
  missing filer. `cik.normalize_cik` is there for CIKs arriving as bare integers from SEC
  payloads or `--symbols`-style flags.
- **Phase 7 — the runbook.** `docs/runbooks/data-pipeline.md` should point at
  `engine/data/SOURCES.md § ticker_cik.csv` for the re-vendoring recipe rather than restating it.
- **Not done here, deliberately:** `NDOI`'s identity is unresolved (see Step 3). If it turns out
  to be a phantom in `ndx_history.csv`, the right long-term fix is a `membership_overrides.csv`
  correction, which belongs to the membership owner, not to this phase. The `NONE` sentinel keeps
  this phase unblocked either way.
- **Not done here, deliberately:** the generator could also emit a `delisted_utc` column from
  Massive, which Gap A would want. Gap A is out of scope for the whole plan set; the column is
  not added.

---

## Rollback

This phase is one commit on `feature/edgar-fundamentals` and nothing imports it yet, so
`git revert <sha>` undoes it completely: the new files disappear and `SOURCES.md` returns to its
previous text. No schema, no behaviour, no shipped output changes — `pytest engine/tests -q`
passes identically before and after. The only side effect outside git is the gitignored
`engine/.cache/cik/` download cache; `rm -rf engine/.cache/cik` clears it.
