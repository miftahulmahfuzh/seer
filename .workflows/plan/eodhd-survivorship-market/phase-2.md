# Phase 2: Alias fill for the empty members

**Plan set:** `EODHD_SURVIVORSHIP_MARKET_PLAN.md`
**Analysis:** `20261010-181548-E7HD_code_analyzer.md`
**Satisfies:** R7 (the "spend calls on the empty members?" half: yes, targeted per-code calls), R3 (refreshed coverage report after the fill)
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine` (`eodhd.py`, new `survivorship_alias.py`, `commands/survivorship_store.py`)

---

## Goal

Every index member that phase 1's build leaves `dropped` gets an offline, recorded answer: the
other EODHD code it trades under and why, or why there is none. **The target set is phase 1's 200
dropped symbols** (the handover's "201" counted the `unserved.csv` lines with its header): 199 with
no row on any of their member days — 111 whose code has a series only after 2015-10-16, 47 that
never trade inside their membership (reused ticker), 41 with no EODHD series at all (`null` file or
an empty list) — plus FBF, dropped as absurd. Accepted codes are fetched once (`/eod` per
candidate, `/splits` per overlapping candidate, `/div` per accepted member) into
`engine/.cache/eodhd/alias/` only, the SV store is rebuilt offline with those series passed to
phase 1's `plan_build(..., extra_sources=...)` as second candidates (phase 1's `best_of` keeps
whichever covers more member days), and `alias_report.csv` (through `write_store(...,
extra_reports=...)`) plus the refreshed `coverage_report.txt` record the gain.

## Measured while planning (read-only probes over the cache, no API calls)

Probe scripts: `/tmp/claude-1000/p2/probe1.py … probe7.py`. Membership from
`research.research_membership(engine/data)`, unserved list from `engine/.research/unserved.csv`.

| Fact | Value |
|---|---|
| Unserved members with a cached `eod/<SYM>.json` | 522 |
| … with **zero** rows on their own member days (the "201" of the handover; 199 by this count) | **199** (23 of them are `null` files: EODHD 404'd the store symbol; phase 1's 41 "no daily series" also counts empty lists and rows with no valid date). These 199 are exactly phase 1's 111 + 47 + 41; phase 1's 200th drop, FBF (absurd), is a target too, so `--resolve-aliases` lists **200** members |
| … of those, membership ended on or before 1997-12-31 (EODHD's delisted history mostly starts 1997-12-31, so no code can help much) | 32 |
| EODHD's convention for a reused ticker | the old company keeps a **suffixed code** in `symbols-US-delisted.json`: `DELL_old` (Dell Inc), `AT_old1` (Alltel), `TRW1` (TRW Inc), `SE1` (Spectra Energy), `EQ1` (Embarq), `UK1` (Union Carbide). 1,958 delisted codes carry `_old…` |
| Of the 199, with **at least one other EODHD code** by the rules below (code variants, bankruptcy stem, class spelling, `ticker_aliases.csv`, `ticker_cik.csv` names, 13 hand-checked hints) | **157** — measured by running this plan's `survivorship_alias.candidates` over the real lists (best match: code-variant 94, name 45, hint 13, class 3, bankruptcy 1, alias 1). Over the 200 targets expect 157 or 158 (FBF not measured) |
| … with no other code at all | 42 (26 of the 32 pre-1998, plus `AFS.A`, `AZA.A`, `BNL`, `CFL`, `GP`, `JH`, `LDW.B`, `LU`, `MDR`, `MST`, `MTL`, `NLTI`, `NLV`, `RDS.A`, `UAWGQ`, `UMG`) |
| Candidate codes to probe (capped at 4 per member) | 220 `/eod` calls; then ≤1 `/splits` per candidate with member-day rows and 1 `/div` per accepted member: **≈500 calls total** of the 100,000/day |
| `ticker_cik.csv` company names cover | 60 of the 199 (the post-2000 ones); pre-2000 departures have no name in `engine/data` |

Worked examples (what the resolver should produce; acceptance still needs the fetched series):

| Store symbol | Membership | Candidates (match kind) | Expected answer |
|---|---|---|---|
| `WCOEQ` (WorldCom) | 1996-04-01..2002-05-15 | `MCWEQ` "WorldCom, Inc" (hint), `WCO…` (bankruptcy stem, none listed) | `MCWEQ` |
| `DELL` | 1996..2013 | `DELL_old` "Dell Inc", `DLLTV`, `DVMT` (all by name; the last two are 2016+ tracking stock) | `DELL_old` (the others have no member-day rows) |
| `DOW` | 1996..2015 | `DOW-WI`, `DOW_old` "The Dow Chemical Company" (name) | `DOW_old` (`DOW-WI` is the 2019 when-issued line) |
| `LEHMQ` (Lehman) | 1998-01-12..2008-09-17 | `LEH` (hint) | `LEH` |
| `MTLQQ` (GM) | 1996..2009 | `GM_old` (hint), `MTL` Mechel (bankruptcy stem; NYSE from 2004, so it overlaps!) | `GM_old`: two series fit, exactly one is named, the named one wins |
| `HWM` (Alcoa/Arconic history) | 1996..2015 | `ARNC`, `ARNC_old` (via `ticker_aliases.csv` ARNC→HWM) | whichever single one covers 1996-2015 |
| `AT` (Alltel) | 1996..2007 | `AT_old` Atlantic Power (2010+), `AT_old1` Alltel, `AT_old2` Aroundtown | `AT_old1` |
| `GFS.A` (Giant Food) | 1996..1998 | `GFS`, `GFSA` "Giant Food Inc", `GFS_old` (class) | `GFSA` if its history reaches into 1998 |
| `SUNEQ` (MEMC/SunEdison) | 2007..2011 | `SDSNQ`, `SUNE_old`, `WFR_old` (name), `SUN` (bankruptcy stem; Sunoco, overlaps) | `WFR_old` if it is the only named series with member-day rows; if `SUNE_old` also covers 2007-2011 and is a different series → ambiguous, recorded |
| `BEV` (Beverly) | 1996..1997-12-04 | none | "no candidate code" — membership ends before EODHD's history |

The client code of step 1 and the resolver/chooser/fetch half of step 3 were run in a scratch copy
of the package during planning: 19 passed, `ruff --select E9,F` clean. The reconciler then rewrote
the seam to phase 1 (`phase1_clean`, `targets`, `series_of`, `alias_sources`, `report_rows`, the
build wiring in step 4 and the tests that touch them) against phase 1's tested contract; those
pieces are new and must be proven by step 6's run.

Not measurable offline: whether EODHD's `/eod` serves the `_old` codes verbatim (`DELL_old.US`).
Step 9 smoke-tests that with four symbols before the full fetch and says what to do if it does not.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `eodhd.EOD_FROM` (`eodhd.py`), `eodhd.exchange_code(code)` (`eodhd.py`)
- `eodhd.Client.eod(code, *, start=EOD_FROM)`, `eodhd.Client.splits(code, *, start=HISTORY_FROM)`, `eodhd.Client.dividends_by_code(code, *, start=HISTORY_FROM)`, private `eodhd.Client._get_list(endpoint, target, start, *, what, extra=None)`
- new module `seer_engine.survivorship_alias` (`survivorship_alias.py`): constants `ALIAS_DIR = "alias"`, `PROBE_DIR = "probe"`, `ALIAS_SOURCE = "eodhd-alias"`, `REPORT_FILE = "alias_report.csv"`, `REPORT_HEADER`, `HINTS_FILE = "eodhd_alias_hints.csv"`, `USABLE_ACTIONS` (= phase 1's `KEPT/REPAIRED/TRIMMED`), `MIN_MEMBER_ROWS`, `MAX_CANDIDATES`, `MATCH_ORDER`; types `Listing`, `Listings`, `Sources`, `Candidate`, `Resolution`, `ReportRow`, `FetchStats`; functions `code_root`, `normalize_name`, `load_listings`, `load_sources`, `candidates`, `member_closes`, `same_series`, `series_of`, `choose`, `read_probe`, `read_alias`, `intervals_by_symbol`, `phase1_clean`, `targets`, `resolve`, `fetch`, `alias_sources`, `report_rows`, `report_text`, `summary`
- `commands/survivorship_store.py`: `add_alias_arguments(p)`, `AliasFill` (frozen dataclass: `sources`, `resolutions`, `alias_dir`, `by_symbol`; `report(plan) -> str`), `alias_fill(args) -> AliasFill | None`, `run_aliases(args)`; flags `--resolve-aliases`, `--fetch-aliases`, `--refetch`, `--symbols`, `--no-aliases`; phase 1's `run()` rewired so `--build` (and the no-flag dry print) passes `extra_sources=fill.sources` to `plan_build` and `extra_reports={"alias_report.csv": fill.report(plan)}` to `write_store` — **on by default**, `--no-aliases` turns it off
- data file `engine/data/eodhd_alias_hints.csv` (`symbol,code,note`), documented in `engine/data/SOURCES.md`
- cache files (gitignored, main checkout via symlink): `engine/.cache/eodhd/alias/probe/<CODE>.json` = `{code, name, fetched, eod[, splits]}`, `engine/.cache/eodhd/alias/<SYM>.json` = `{symbol, code, name, matched_by, fetched, eod, splits, dividends}`
- store file (outside the manifest): `alias_report.csv` = `symbol,code,name,matched_by,accepted,reason`

**Signature changes:** `eodhd.Client.dividends(symbol, *, start)` — unchanged signature and behaviour; its body now delegates to `_get_list`. Error texts keep their shape (`non-JSON answer for KO.US`, `expected a dividend list for KO.US, got …`, `HTTP 403 for KO.US: …`).

**Requires (from Phase 1)** — phase 1's tested contract (phase-1.md is authoritative):
1. `survivorship.SourceSeries(symbol, source, code, bars: tuple[RawBar, ...], splits: tuple[Split, ...] = (), dividends: tuple[RawDividend, ...] = ())`, built from vendor JSON with `survivorship.parse_bars(rows)`, `parse_splits(rows)`, `parse_dividend_rows(rows)` (each accepts None or a list).
2. `survivorship.clean_symbol(series, member_days: Sequence[date], sessions: Sequence[date]) -> Cleaned`, with `member_days` from `survivorship.member_sessions(intervals: Iterable[(symbol, start, end|None)], symbol, sessions)` over the sessions on or after `research.MEMBERSHIP_START`, and `sessions = dates.sessions(research.STORE_START, research.DEV_END)` — exactly what `plan_build` does. `Cleaned` is frozen with `symbol, source, code, action` (one of `survivorship.ACTIONS`), `reason`, `covered_days`, `bars`, `dividends`, … ; it never raises on vendor data and accepts empty dividends.
3. `survivorship.best_of(candidates) -> Cleaned`: the candidate covering the most member days; ties and all-dropped go to the first (the original cache).
4. `survivorship.read_series(cache, symbol) -> SourceSeries | None` (None: never fetched).
5. `commands.survivorship_store.plan_build(source_dir, cache, *, data_dir=None, extra_sources: Mapping[str, Sequence[SourceSeries]] | None = None) -> BuildPlan` (`plan.cleaned: Mapping[str, Cleaned]`, the chosen candidate per unserved symbol) and `write_store(plan, out, cache, *, data_dir=None, extra_reports: Mapping[str, str] | None = None) -> dict` (each extra report written inside the store, outside the manifest). `cleaning_report.csv` and `coverage_report.txt` are computed from `plan.cleaned`, i.e. after the alias candidates competed.
6. Phase 1's `add_arguments(p)` and `run(args)` as quoted in Step 4; `--cache` is the EODHD cache root, `--source` the dev store, `--out` the SV store.
7. The real SV store has been built once at `/home/miftah/seer/engine/.research-sv` with `coverage_report.txt` inside.

**Leaves alone (owned by others):** `research.py`, `backtest/*`, `commands/lab.py`, `lab/*` (phases 1, 3, 4); the cleaning rules inside `survivorship.py` (phase 1); `docs/lab/survivorship/` and lab journaling (phase 5); the original cache files under `engine/.cache/eodhd/{eod,splits,dividends,market}/` and the two symbol lists (read only).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/eodhd.py` | modify | `EOD_FROM`, `exchange_code`; `Client._get_list` generic GET; `eod`, `splits`, `dividends_by_code`; `dividends` delegates (lines 33-38, 58-62, 138-181) |
| `engine/src/seer_engine/survivorship_alias.py` | create | offline resolution, probe/alias cache IO, injected-client fetch, build substitution, report |
| `engine/src/seer_engine/commands/survivorship_store.py` | modify (phase-1 file) | imports; alias flags, `AliasFill`, `alias_fill`, `run_aliases`; one line appended to phase 1's `add_arguments`; phase 1's `run` replaced (Step 4 quotes it as phase 1 leaves it) |
| `engine/data/eodhd_alias_hints.csv` | create | 13 hand-checked `symbol,code,note` hints (each verified against the symbol list's `Name`) |
| `engine/data/SOURCES.md` | modify | one section documenting the hints file |
| `engine/tests/test_survivorship_alias.py` | create | client endpoints (fake transport), resolver, chooser, fetch (fake client), substitution, command (offline + dry run) |

## Implementation Steps

### Step 0: Environment (the executor runs this first)

```bash
WT=/home/miftah/.worktrees/seer/eodhd-survivorship-market
cd "$WT"
git branch --show-current            # must print feature/eodhd-survivorship-market
# phase 1 Step 0's recipe, idempotent: own venv (main's venv would test main's tree), read-only
# symlinks, and the exclude lines phase 1 added for them
[ -x engine/.venv/bin/python ] || { /home/miftah/.pyenv/versions/3.11.0/bin/python -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'; }
[ -e engine/.research ] || ln -s /home/miftah/seer/engine/.research engine/.research
[ -e engine/.cache ]    || ln -s /home/miftah/seer/engine/.cache engine/.cache
EXCL=$(git rev-parse --git-path info/exclude)
for p in engine/.cache engine/.research; do grep -qxF "$p" "$EXCL" || echo "$p" >> "$EXCL"; done
git status --short                    # must not list engine/.cache or engine/.research
# SEER_LAB_DB is not set: this phase writes no lab row. The token is read through
# SEER_ENV_FILE=/home/miftah/seer/.env.local on the network steps only (8-10).
# fingerprint the original cache folders: phase 2 must leave them byte-identical
( cd /home/miftah/seer/engine/.cache/eodhd && find eod splits dividends market -type f | sort | xargs sha256sum | sha256sum ) > /tmp/claude-1000/p2-cache-before.sha
```

**Note on the symlink:** `config.REPO_ROOT` in the worktree is the worktree, so every default
cache path (`$WT/engine/.cache/eodhd/alias/`) resolves through the symlink to
`/home/miftah/seer/engine/.cache/eodhd/alias/`. That is intended: the alias cache lives with the
rest of the paid pull on the PC. Pass `--cache /home/miftah/seer/engine/.cache/eodhd` explicitly
anyway on every real run, so nothing depends on the link. Stores are always addressed by absolute
main-checkout path (invariant 4), never through `$WT/engine/.research`.

### Step 1: Generic GET in the EODHD client

**File:** `engine/src/seer_engine/eodhd.py:33` (constants) and `:58` (after `ticker`) and `:138-181` (`Client.dividends` → `_get_list`)
**Change:** add `EOD_FROM` and `exchange_code`; move the retry loop into `_get_list`; add the three
by-code endpoints. `ticker()` is unchanged (it uppercases and turns `.` into `-`, which would break
`DELL_old`; `exchange_code` passes the vendor's code through verbatim).

**Code** — insert after line 38 (`MAX_ERROR_BODY = 200`):

```python
EOD_FROM = date(1993, 1, 1)  # the original eod/ pull's start (handover §2)
```

Insert after `ticker` (after line 62):

```python
def exchange_code(code: str) -> str:
    """An EODHD symbol-list ``Code`` with the US suffix, verbatim: ``DELL_old`` -> ``DELL_old.US``.

    The store's symbols go through ``ticker`` (``BRK.B`` -> ``BRK-B.US``); a vendor code from
    ``symbols-US-*.json`` is already in EODHD's spelling and must keep its case (``_old``)."""
    if not code or not code.strip():
        raise ValueError("code is empty")
    code = code.strip()
    if "." in code:
        raise ValueError(f"{code!r} is not an EODHD code (has a '.'); store symbols go through ticker()")
    return code + ".US"
```

Replace `Client.dividends` (lines 138-181) with:

```python
    def dividends(self, symbol: str, *, start: date = HISTORY_FROM) -> list[Any] | None:
        """The raw ``/div`` list for ``symbol`` since ``start``; None when EODHD has no such ticker."""
        return self._get_list("div", ticker(symbol), start, what="dividend list")

    def dividends_by_code(self, code: str, *, start: date = HISTORY_FROM) -> list[Any] | None:
        """``/div`` for an EODHD code from its symbol lists (``DELL_old``); None on 404."""
        return self._get_list("div", exchange_code(code), start, what="dividend list")

    def eod(self, code: str, *, start: date = EOD_FROM) -> list[Any] | None:
        """The raw daily ``/eod`` list for an EODHD code since ``start``; None on 404.

        Rows are ``{date, open, high, low, close, adjusted_close, volume}`` with RAW (not
        split-adjusted) OHLC, exactly like ``engine/.cache/eodhd/eod/``."""
        return self._get_list("eod", exchange_code(code), start, what="price list", extra={"period": "d"})

    def splits(self, code: str, *, start: date = HISTORY_FROM) -> list[Any] | None:
        """The raw ``/splits`` list (``[{date, split: "2.000000/1.000000"}]``) for a code; None on 404."""
        return self._get_list("splits", exchange_code(code), start, what="split list")

    def _get_list(
        self,
        endpoint: str,
        target: str,
        start: date,
        *,
        what: str,
        extra: dict[str, str] | None = None,
    ) -> list[Any] | None:
        """GET ``<base>/<endpoint>/<target>`` expecting a JSON list; None on 404.

        Paced by ``min_interval``; 429, 5xx and connection errors retry with exponential
        backoff up to ``retries`` times. Every message that can reach a log line or an
        exception goes through ``scrub`` so the token never leaves this object."""
        url = f"{self.base_url}/{endpoint}/{target}"
        params: dict[str, Any] = {"fmt": "json", "from": start.isoformat()}
        params.update(extra or {})
        params["api_token"] = self._token
        attempt = 0
        while True:
            attempt += 1
            if self._last_call is not None:
                wait = self._last_call + self.min_interval - self._clock()
                if wait > 0:
                    self._sleep(wait)
            self.calls += 1
            retryable = False
            try:
                resp = self._transport.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                message = scrub(f"{type(exc).__name__}: {exc}", self._token)
                retryable = True
            else:
                status = resp.status_code
                if status == 200:
                    self._last_call = self._clock()
                    try:
                        data = resp.json()
                    except ValueError as exc:
                        raise EodhdError(f"non-JSON answer for {target}") from exc
                    if not isinstance(data, list):
                        raise EodhdError(
                            f"expected a {what} for {target}, got "
                            f"{scrub(str(data)[:MAX_ERROR_BODY], self._token)}"
                        )
                    return data
                if status == 404:
                    self._last_call = self._clock()
                    return None
                body = scrub(str(getattr(resp, "text", ""))[:MAX_ERROR_BODY], self._token)
                message = f"HTTP {status} for {target}: {body}"
                retryable = status == 429 or status >= 500
            self._last_call = self._clock()
            if not retryable or attempt > self.retries:
                raise EodhdError(message)
            delay = self.backoff * (2 ** (attempt - 1))
            log.warning("eodhd: %s; retry %d/%d in %.1fs", message, attempt, self.retries, delay)
            self._sleep(delay)
```

Also update the module docstring's first line (line 1) to:
`"""EODHD REST client: dividends (with declaration dates), daily prices and splits per code.`
and add one sentence after line 6: ``The by-code endpoints (``eod``, ``splits``, ``dividends_by_code``) take a vendor code from the symbol lists verbatim (``exchange_code``); the alias fill in ``survivorship_alias`` is their only caller.``

**Impact:** none on existing callers. `test_dividend_announcements.py`'s client tests (URL ends
`/div/MSFT.US`, params carry `api_token` and `fmt`, 429/connection retry count 3, token scrub) pass
unchanged; its command test monkeypatches `eodhd.Client` wholesale.

### Step 2: The hints file

**File:** `engine/data/eodhd_alias_hints.csv` (new)
**Change:** 13 rows, each code verified during planning to exist in `symbols-US-delisted.json` /
`symbols-US-live.json` with the company name in the note. A hint is only a candidate: it is
accepted on the same series test as every other code.

```csv
symbol,code,note
AAMRQ,AMR_old,AMR Corporation (American Airlines parent); traded as AMR until the 2011 bankruptcy
ABKFQ,ABK,Ambac Financial Group Inc; traded as ABK until the 2010 bankruptcy
AEOS,AEO,American Eagle Outfitters Inc; Nasdaq AEOS moved to NYSE AEO in 2007
BHMSQ,BS,Bethlehem Steel Corp; traded as BS until the 2001 bankruptcy
HANS,MNST,Hansen Natural renamed Monster Beverage Corp in 2012
HSH,SLE_old,Sara Lee Corp renamed Hillshire Brands in 2012; the store symbol is the post-rename ticker
LEHMQ,LEH,Lehman Brothers Holdings Inc; traded as LEH until the 2008 bankruptcy
MTLQQ,GM_old,General Motors Corp; traded as GM until the 2009 bankruptcy (then Motors Liquidation)
RIMM,BB,Research In Motion renamed BlackBerry Ltd in 2013
RSHCQ,RSH,RadioShack Corp; traded as RSH until the 2015 bankruptcy
UAUA,UAL,UAL Corp on Nasdaq 2006-2010; became United Continental (UAL)
WCOEQ,MCWEQ,WorldCom Inc; EODHD lists it as MCWEQ
WYND,WYN,Wyndham Worldwide Corporation traded as WYN; WYND is the 2018 Wyndham Destinations ticker
```

**File:** `engine/data/SOURCES.md` (append at the end)

```markdown
## eodhd_alias_hints.csv

`symbol,code,note`. Hand-checked EODHD codes for index members whose store symbol is not the code
EODHD keeps their history under (a bankruptcy `Q` ticker, a rename, a re-listing). Read only by
`seer_engine.survivorship_alias`, which treats each row as one more *candidate*: it is accepted only
when the fetched series has rows on the member's own index days and passes the survivorship-check
cleaning, exactly like a code found by name or suffix. Each `code` was checked against the `Name`
in EODHD's `exchange-symbol-list/US` (live and delisted) on 2026-10-10; the note says which company
it is. Owner of this file: the engine. No vendor data in it, codes and names only.
```

**Impact:** none on existing loaders (nothing enumerates `engine/data`).

### Step 3: The resolver module

**File:** `engine/src/seer_engine/survivorship_alias.py` (new)

```python
"""survivorship_alias -- the EODHD code an index member with no usable series trades under.

The survivorship-check store (``commands/survivorship_store``) fills the dev store's unserved
members from ``engine/.cache/eodhd/eod/<SYM>.json``, fetched under the store's own symbol. About
two hundred come back with nothing on their member days: the code now belongs to someone else
(``DOW`` is Dow Inc since 2019) or the company traded under another one (WorldCom is ``MCWEQ``).
EODHD keeps old companies under suffixed codes in its symbol lists -- ``DELL_old``, ``AT_old1``,
``TRW1`` -- so this module, offline:

1. lists candidate codes per member from ``symbols-US-delisted.json`` / ``symbols-US-live.json``:
   a hand-checked hint (``engine/data/eodhd_alias_hints.csv``), the normalized company name from
   ``ticker_cik.csv``, ``ticker_aliases.csv``, the class-share spelling (``GFS.A`` -> ``GFSA``),
   the bankruptcy stem (``ABKFQ`` -> ``ABKF``), and the vendor's own suffixes (``_old``,
   ``_oldN``, ``N``) -- never the store symbol's own code, which is what came back empty;
2. accepts a candidate only when its fetched series has at least ``MIN_MEMBER_ROWS`` rows on the
   member's index days and passes the same cleaning every other symbol gets. Two fitting
   candidates that are different price series resolve to none ("ambiguous"), unless exactly one
   of them was found by hint or name.

``fetch`` is the only network path (through an injected ``eodhd.Client``-like object) and writes
under ``<cache>/alias/`` only: ``probe/<CODE>.json`` per candidate and ``<SYM>.json`` per accepted
member. ``alias_sources`` turns the accepted alias files into ``survivorship.SourceSeries`` that
``commands/survivorship_store.plan_build`` takes as ``extra_sources``: each is cleaned there like
the cache's own series and ``survivorship.best_of`` keeps whichever covers more member days.
``report_rows`` then says, per target, what happened (``alias_report.csv``). ``eod/``, ``splits/``
and ``dividends/`` are only ever read.
"""

from __future__ import annotations

import csv
import functools
import io
import json
import logging
import os
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from seer_engine import dates, eodhd, research
from seer_engine import survivorship as sv
from seer_engine.backtest.market import Membership

log = logging.getLogger(__name__)

ALIAS_DIR = "alias"
PROBE_DIR = "probe"
ALIAS_SOURCE = "eodhd-alias"  # SourceSeries.source / Cleaned.source of an alias series
DELISTED_FILE = "symbols-US-delisted.json"
LIVE_FILE = "symbols-US-live.json"
NAMES_FILE = "ticker_cik.csv"
ALIASES_FILE = "ticker_aliases.csv"
HINTS_FILE = "eodhd_alias_hints.csv"
REPORT_FILE = "alias_report.csv"
REPORT_HEADER = ("symbol", "code", "name", "matched_by", "accepted", "reason")

#: Symbol-list types that are never an operating company's common stock. "ETF" stays allowed:
#: EODHD mislabels some delisted stocks (``PWER_old`` Power-One is typed ETF); the series test
#: rejects real funds, which do not trade on a 1990s member's days under its old code.
SKIP_TYPES = frozenset(
    {"FUND", "Mutual Fund", "Preferred Stock", "Warrant", "Unit", "Notes", "Bond", "BOND", "INDEX"}
)
MAX_CANDIDATES = 4  # per member, best match kinds first; caps the /eod probes at ~4 calls
MIN_MEMBER_ROWS = 20  # a month of sessions on member days before a code counts as overlapping
SAME_CLOSE_TOL = 0.005  # two codes whose closes agree within 0.5% ...
SAME_SERIES_SHARE = 0.95  # ... on 95% of shared member days are one company listed twice
EODHD_DELISTED_FROM = date(1997, 12, 31)  # where most delisted series begin (handover §3)
MATCH_ORDER = ("hint", "name", "alias", "class", "bankruptcy", "code-variant")
NAMED = frozenset({"hint", "name"})

#: Phase 1's classifications that put a symbol's bars into the store (everything but DROPPED).
USABLE_ACTIONS = frozenset({sv.KEPT, sv.REPAIRED, sv.TRIMMED})

NAME_STOP = frozenset(
    {
        "A", "AG", "AND", "B", "CL", "CO", "COMPANY", "CORP", "CORPORATION", "DE", "DEL", "GROUP",
        "HOLDING", "HOLDINGS", "INC", "INTERNATIONAL", "INTL", "LIMITED", "LLC", "LP", "LTD", "NEW",
        "NV", "NW", "OLD", "PLC", "SA", "THE",
    }
)

#: ``clean(series, intervals) -> result`` where ``result.action`` / ``result.reason`` are phase
#: 1's classification (``phase1_clean`` in production; a fake in the resolver tests).
Clean = Callable[[sv.SourceSeries, Sequence[tuple[date, date | None]]], Any]

_TAIL = re.compile(r"(.+?)(?:_old\d*|\d)")
_STATE = re.compile(r"/[A-Z]{2,3}/")


# ---- listings and names --------------------------------------------------------------------


@dataclass(frozen=True)
class Listing:
    code: str
    name: str
    type: str
    exchange: str
    delisted: bool


@dataclass(frozen=True)
class Listings:
    by_code: Mapping[str, Listing]
    by_root: Mapping[str, tuple[str, ...]]
    by_name: Mapping[str, tuple[str, ...]]

    @classmethod
    def of(cls, listings: Iterable[Listing]) -> Listings:
        by_code: dict[str, Listing] = {}
        for item in listings:
            by_code.setdefault(item.code, item)
        roots: dict[str, list[str]] = {}
        names: dict[str, list[str]] = {}
        for code, item in by_code.items():
            roots.setdefault(code_root(code), []).append(code)
            key = normalize_name(item.name)
            if key:
                names.setdefault(key, []).append(code)
        return cls(
            by_code=by_code,
            by_root={k: tuple(sorted(v)) for k, v in roots.items()},
            by_name={k: tuple(sorted(v)) for k, v in names.items()},
        )


@dataclass(frozen=True)
class Sources:
    """Everything the resolver reads besides the probes: the vendor's lists and engine/data."""

    listings: Listings
    names: Mapping[str, tuple[str, ...]]  # store symbol -> company names (ticker_cik.csv)
    aliases: Mapping[str, frozenset[str]]  # store symbol -> other tickers (ticker_aliases.csv, both ways)
    hints: Mapping[str, tuple[str, ...]]  # store symbol -> hinted codes


def code_root(code: str) -> str:
    """A vendor code without EODHD's re-listing suffix: ``DELL_old`` / ``AT_old1`` / ``TRW1`` -> stem."""
    m = _TAIL.fullmatch(code)
    return m.group(1) if m else code


def normalize_name(name: str | None) -> str:
    """Company name reduced for equality: ``DOW CHEMICAL CO /DE/`` == ``The Dow Chemical Company``."""
    text = (name or "").upper().replace("&", " AND ")
    text = _STATE.sub(" ", text)
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(w for w in text.split() if w not in NAME_STOP)


def load_listings(cache_root: Path) -> Listings:
    """Both symbol lists, delisted first (a code in both keeps its delisted row); funds etc. skipped."""
    items: list[Listing] = []
    for filename, delisted in ((DELISTED_FILE, True), (LIVE_FILE, False)):
        path = Path(cache_root) / filename
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{path}: expected a JSON list of symbols")
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("Code") or "").strip()
            kind = str(raw.get("Type") or "")
            if not code or kind in SKIP_TYPES:
                continue
            items.append(
                Listing(code, str(raw.get("Name") or ""), kind, str(raw.get("Exchange") or ""), delisted)
            )
    return Listings.of(items)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_sources(cache_root: Path, data_dir: Path) -> Sources:
    names: dict[str, list[str]] = {}
    for row in _csv_rows(Path(data_dir) / NAMES_FILE):
        if row.get("company_name"):
            names.setdefault(row["symbol"], []).append(row["company_name"])
    aliases: dict[str, set[str]] = {}
    for row in _csv_rows(Path(data_dir) / ALIASES_FILE):
        old, new = row.get("old", ""), row.get("new", "")
        if old and new:
            aliases.setdefault(old, set()).add(new)
            aliases.setdefault(new, set()).add(old)
    hints: dict[str, list[str]] = {}
    for row in _csv_rows(Path(data_dir) / HINTS_FILE):
        if row.get("symbol") and row.get("code"):
            hints.setdefault(row["symbol"], []).append(row["code"].strip())
    return Sources(
        listings=load_listings(cache_root),
        names={k: tuple(v) for k, v in names.items()},
        aliases={k: frozenset(v) for k, v in aliases.items()},
        hints={k: tuple(v) for k, v in hints.items()},
    )


# ---- candidates ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str
    matched_by: str  # one of MATCH_ORDER


def _base_code(symbol: str) -> str:
    return eodhd.ticker(symbol)[: -len(".US")]


def candidates(symbol: str, sources: Sources) -> tuple[Candidate, ...]:
    """Other EODHD codes ``symbol`` may trade under, best match kind first, at most MAX_CANDIDATES.

    The store symbol's own code is excluded: its series is ``eod/<SYM>.json``, already tried."""
    listings = sources.listings
    base = _base_code(symbol)
    found: dict[str, str] = {}

    def add(codes: Iterable[str], kind: str) -> None:
        for code in codes:
            if code != base and code in listings.by_code and code not in found:
                found[code] = kind

    add(sources.hints.get(symbol, ()), "hint")
    for company in sources.names.get(symbol, ()):
        key = normalize_name(company)
        if key:
            add(listings.by_name.get(key, ()), "name")
    for other in sorted(sources.aliases.get(symbol, ())):
        add(listings.by_root.get(_base_code(other), ()), "alias")
    if "." in symbol:
        head, _, tail = symbol.partition(".")
        for stem in (head + tail, head):  # GFS.A -> GFSA, GFS
            add(listings.by_root.get(stem, ()), "class")
    if len(base) >= 4 and base.endswith("Q"):
        stem = base.rstrip("Q")  # ABKFQ -> ABKF, MTLQQ -> MTL
        stems = [stem] + ([stem[:-1]] if stem.endswith("E") and len(stem) >= 4 else [])  # WCOEQ -> WCO
        for s in stems:
            for q in ("", "Q", "QQ"):
                add(listings.by_root.get(s + q, ()), "bankruptcy")
    add(listings.by_root.get(base, ()), "code-variant")
    ranked = sorted(found.items(), key=lambda kv: (MATCH_ORDER.index(kv[1]), kv[0]))
    return tuple(
        Candidate(code, listings.by_code[code].name, kind) for code, kind in ranked[:MAX_CANDIDATES]
    )


# ---- series tests --------------------------------------------------------------------------


def _on_member_day(day: date, intervals: Sequence[tuple[date, date | None]], end: date) -> bool:
    if day < research.MEMBERSHIP_START or day > end:
        return False
    return any(start <= day and (stop is None or day < stop) for start, stop in intervals)


def member_closes(
    rows: Any, intervals: Sequence[tuple[date, date | None]], end: date = research.DEV_END
) -> dict[date, float]:
    """Raw closes of ``rows`` (an /eod list) on the member's index days inside the dev window."""
    out: dict[date, float] = {}
    if not isinstance(rows, list):
        return out
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        try:
            day = date.fromisoformat(str(raw.get("date"))[:10])
            close = float(raw.get("close"))
        except (TypeError, ValueError):
            continue
        if close > 0 and _on_member_day(day, intervals, end):
            out[day] = close
    return out


def same_series(a: Mapping[date, float], b: Mapping[date, float]) -> bool:
    """One company under two codes: closes within SAME_CLOSE_TOL on SAME_SERIES_SHARE of shared days."""
    common = a.keys() & b.keys()
    if len(common) < MIN_MEMBER_ROWS:
        return False
    agree = sum(1 for d in common if abs(a[d] / b[d] - 1.0) <= SAME_CLOSE_TOL)
    return agree >= SAME_SERIES_SHARE * len(common)


def series_of(symbol: str, code: str, doc: Mapping[str, Any], *, dividends: bool = True) -> sv.SourceSeries:
    """A probe or alias doc as phase 1's ``SourceSeries`` for the store symbol ``symbol``.

    ``doc["dividends"]`` is the raw ``/div`` list (same row shape as the cached
    ``dividends/<SYM>.json`` rows); ``dividends=False`` while choosing, when it is not fetched yet."""
    return sv.SourceSeries(
        symbol=symbol,
        source=ALIAS_SOURCE,
        code=eodhd.exchange_code(code),
        bars=sv.parse_bars(doc.get("eod")),
        splits=sv.parse_splits(doc.get("splits")),
        dividends=sv.parse_dividend_rows(doc.get("dividends")) if dividends else (),
    )


@dataclass(frozen=True)
class Resolution:
    symbol: str
    code: str | None
    name: str
    matched_by: str
    accepted: bool
    reason: str
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class _Fit:
    cand: Candidate
    closes: Mapping[date, float]


def choose(
    symbol: str,
    cands: Sequence[Candidate],
    probes: Mapping[str, Mapping[str, Any]],
    intervals: Sequence[tuple[date, date | None]],
    *,
    clean: Clean,
    end: date = research.DEV_END,
) -> Resolution:
    """The one code whose series fits ``symbol``'s membership, or None with the reason."""
    cands = tuple(cands)
    if not cands:
        return Resolution(symbol, None, "", "", False, "no candidate code in EODHD's symbol lists")
    fits: list[_Fit] = []
    notes: list[str] = []
    for cand in cands:
        doc = probes.get(cand.code)
        if doc is None:
            notes.append(f"{cand.code} not fetched")
            continue
        closes = member_closes(doc.get("eod"), intervals, end)
        if len(closes) < MIN_MEMBER_ROWS:
            notes.append(f"{cand.code} has {len(closes)} rows on member days")
            continue
        if "splits" not in doc:
            notes.append(f"{cand.code} splits not fetched")
            continue
        result = clean(series_of(symbol, cand.code, doc, dividends=False), intervals)
        if result.action not in USABLE_ACTIONS:
            notes.append(f"{cand.code} {result.action} ({result.reason})")
            continue
        fits.append(_Fit(cand, closes))
    if not fits:
        return Resolution(symbol, None, "", "", False, "no candidate fits: " + "; ".join(notes), cands)

    groups: list[list[_Fit]] = []
    for fit in fits:
        for group in groups:
            if same_series(group[0].closes, fit.closes):
                group.append(fit)
                break
        else:
            groups.append([fit])
    note = ""
    if len(groups) > 1:
        named = [g for g in groups if any(f.cand.matched_by in NAMED for f in g)]
        others = lambda keep: ", ".join(f.cand.code for g in groups if g is not keep for f in g)  # noqa: E731
        if len(named) != 1:
            listed = " vs ".join("/".join(f.cand.code for f in g) for g in groups)
            return Resolution(symbol, None, "", "", False, f"ambiguous: {listed} all fit", cands)
        chosen = named[0]
        note = f"; named match preferred over {others(chosen)}"
    else:
        chosen = groups[0]
    best = min(chosen, key=lambda f: (-len(f.closes), MATCH_ORDER.index(f.cand.matched_by), f.cand.code))
    if len(chosen) > 1:
        note += "; same series as " + ", ".join(f.cand.code for f in chosen if f is not best)
    return Resolution(
        symbol,
        best.cand.code,
        best.cand.name,
        best.cand.matched_by,
        True,
        f"{len(best.closes)} rows on member days{note}",
        cands,
    )


# ---- cache IO ------------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def probe_path(alias_dir: Path, code: str) -> Path:
    return Path(alias_dir) / PROBE_DIR / f"{code}.json"


def alias_path(alias_dir: Path, symbol: str) -> Path:
    return Path(alias_dir) / f"{symbol}.json"


def read_probe(alias_dir: Path, code: str) -> dict[str, Any] | None:
    doc = _read_json(probe_path(alias_dir, code))
    return doc if isinstance(doc, dict) else None


def read_alias(alias_dir: Path, symbol: str) -> dict[str, Any] | None:
    doc = _read_json(alias_path(alias_dir, symbol))
    return doc if isinstance(doc, dict) else None


# ---- membership and targets ----------------------------------------------------------------


def intervals_by_symbol(members: Membership) -> dict[str, tuple[tuple[date, date | None], ...]]:
    out: dict[str, list[tuple[date, date | None]]] = {}
    for symbol, start, end in members.intervals:
        out.setdefault(symbol, []).append((start, end))
    return {k: tuple(sorted(v, key=lambda iv: iv[0])) for k, v in out.items()}


@functools.lru_cache(maxsize=1)
def _sessions() -> tuple[tuple[date, ...], tuple[date, ...]]:
    """(every NYSE session STORE_START..DEV_END, those on or after MEMBERSHIP_START) -- the two
    sequences ``commands/survivorship_store.plan_build`` hands ``clean_symbol``."""
    sessions = tuple(dates.sessions(research.STORE_START, research.DEV_END))
    return sessions, tuple(d for d in sessions if d >= research.MEMBERSHIP_START)


def phase1_clean(series: sv.SourceSeries, intervals: Sequence[tuple[date, date | None]]) -> sv.Cleaned:
    """Phase 1's cleaning of one series against one member's intervals, exactly as ``plan_build``
    calls it (same sessions, same member days)."""
    sessions, member_window = _sessions()
    days = sv.member_sessions(
        ((series.symbol, start, end) for start, end in intervals), series.symbol, member_window
    )
    return sv.clean_symbol(series, days, sessions)


def targets(
    cache_root: Path,
    symbols: Iterable[str],
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    *,
    clean: Clean,
) -> list[str]:
    """The unserved members whose original pull does not clean to a usable series, sorted.

    The same verdict phase 1's build reaches: a symbol never fetched (``read_series`` None) or
    cleaned to ``dropped``. On the real cache: phase 1's 200 drops."""
    out: list[str] = []
    for symbol in sorted(set(symbols)):
        if symbol in research.RESEARCH_ETFS:
            continue
        primary = sv.read_series(Path(cache_root), symbol)
        if primary is None or clean(primary, by_symbol.get(symbol, ())).action not in USABLE_ACTIONS:
            out.append(symbol)
    return out


def resolve(
    symbols: Iterable[str],
    *,
    sources: Sources,
    alias_dir: Path,
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    clean: Clean,
    end: date = research.DEV_END,
) -> list[Resolution]:
    """Offline: candidates for every symbol and the choice the cached probes support."""
    out: list[Resolution] = []
    for symbol in symbols:
        cands = candidates(symbol, sources)
        probes = {c.code: p for c in cands if (p := read_probe(alias_dir, c.code)) is not None}
        out.append(choose(symbol, cands, probes, by_symbol.get(symbol, ()), clean=clean, end=end))
    return out


# ---- network: the injected client ----------------------------------------------------------


@dataclass
class FetchStats:
    calls: int = 0
    accepted: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)


def fetch(
    client: Any,
    alias_dir: Path,
    symbols: Sequence[str],
    *,
    sources: Sources,
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    clean: Clean,
    refetch: bool = False,
    end: date = research.DEV_END,
) -> FetchStats:
    """Probe every candidate's /eod, fetch /splits where it overlaps, /div for the accepted code.

    Resumable: a member with ``alias/<SYM>.json`` is skipped and a cached probe is reused unless
    ``refetch``. A failed call skips that member (recorded in ``failed``); the rest go on."""
    stats = FetchStats()
    alias_dir = Path(alias_dir)
    for n, symbol in enumerate(symbols, 1):
        if not refetch and alias_path(alias_dir, symbol).is_file():
            stats.skipped += 1
            continue
        cands = candidates(symbol, sources)
        intervals = by_symbol.get(symbol, ())
        try:
            probes: dict[str, dict[str, Any]] = {}
            for cand in cands:
                doc = None if refetch else read_probe(alias_dir, cand.code)
                if doc is None:
                    doc = {"code": cand.code, "name": cand.name, "fetched": _now(), "eod": client.eod(cand.code)}
                    stats.calls += 1
                    _write_json(probe_path(alias_dir, cand.code), doc)
                if "splits" not in doc and len(member_closes(doc.get("eod"), intervals, end)) >= MIN_MEMBER_ROWS:
                    doc = {**doc, "splits": client.splits(cand.code)}
                    stats.calls += 1
                    _write_json(probe_path(alias_dir, cand.code), doc)
                probes[cand.code] = doc
            res = choose(symbol, cands, probes, intervals, clean=clean, end=end)
            if res.accepted and res.code is not None:
                dividends = client.dividends_by_code(res.code)
                stats.calls += 1
                chosen = probes[res.code]
                _write_json(
                    alias_path(alias_dir, symbol),
                    {
                        "symbol": symbol,
                        "code": res.code,
                        "name": res.name,
                        "matched_by": res.matched_by,
                        "fetched": _now(),
                        "eod": chosen.get("eod"),
                        "splits": chosen.get("splits"),
                        "dividends": dividends,
                    },
                )
                stats.accepted += 1
        except eodhd.EodhdError as exc:
            log.error("alias fetch: %s failed: %s", symbol, exc)
            stats.failed.append(symbol)
        if n % 25 == 0:
            log.info("alias fetch: %d of %d members, %d calls", n, len(symbols), stats.calls)
    return stats


# ---- the build's second source -------------------------------------------------------------


@dataclass(frozen=True)
class ReportRow:
    symbol: str
    code: str
    name: str
    matched_by: str
    accepted: bool
    reason: str


def _fetched_alias(alias_dir: Path, res: Resolution) -> dict[str, Any] | None:
    """The alias file for an accepted resolution, only when it holds the resolved code."""
    if not res.accepted or res.code is None:
        return None
    doc = read_alias(alias_dir, res.symbol)
    return doc if doc is not None and doc.get("code") == res.code else None


def alias_sources(
    alias_dir: Path, resolutions: Iterable[Resolution]
) -> dict[str, tuple[sv.SourceSeries, ...]]:
    """``plan_build``'s ``extra_sources``: one alias ``SourceSeries`` per accepted, fetched
    resolution, cleaned in the build with the alias code's own splits and dividends (the cached
    ``dividends/<SYM>.json`` belongs to whoever holds the store symbol now). A stale alias file
    whose code is not the resolution's is not offered."""
    out: dict[str, tuple[sv.SourceSeries, ...]] = {}
    for res in resolutions:
        doc = _fetched_alias(alias_dir, res)
        if doc is not None and res.code is not None:
            out[res.symbol] = (series_of(res.symbol, res.code, doc),)
    return out


def report_rows(
    resolutions: Iterable[Resolution],
    chosen: Mapping[str, Any],
    *,
    alias_dir: Path,
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
    clean: Clean,
) -> list[ReportRow]:
    """One ``alias_report.csv`` row per target, after the build chose: ``chosen`` is
    ``BuildPlan.cleaned`` (``Cleaned.source == ALIAS_SOURCE`` when ``best_of`` took the alias)."""
    rows: list[ReportRow] = []
    for res in resolutions:
        if not res.accepted or res.code is None:
            rows.append(ReportRow(res.symbol, "", "", "", False, res.reason))
            continue
        doc = _fetched_alias(alias_dir, res)
        if doc is None:
            held = read_alias(alias_dir, res.symbol)
            state = "is missing" if held is None else f"holds {held.get('code')}"
            rows.append(
                ReportRow(
                    res.symbol, res.code, res.name, res.matched_by, False,
                    f"{res.code} fits but alias/{res.symbol}.json {state}; run --fetch-aliases",
                )
            )
            continue
        result = chosen.get(res.symbol)
        if result is not None and getattr(result, "source", None) == ALIAS_SOURCE:
            rows.append(
                ReportRow(res.symbol, res.code, res.name, res.matched_by, True, f"{result.action}: {res.reason}")
            )
            continue
        alias = clean(series_of(res.symbol, res.code, doc), by_symbol.get(res.symbol, ()))
        why = (
            f"cleaning with dividends: {alias.action} ({alias.reason})"
            if alias.action not in USABLE_ACTIONS
            else f"not used: the original series covers at least as many member days ({alias.reason})"
        )
        rows.append(ReportRow(res.symbol, res.code, res.name, res.matched_by, False, why))
    return rows


def report_text(rows: Iterable[ReportRow]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(REPORT_HEADER)
    for r in sorted(rows, key=lambda r: r.symbol):
        writer.writerow([r.symbol, r.code, r.name, r.matched_by, "yes" if r.accepted else "no", r.reason])
    return buf.getvalue()


def summary(
    resolutions: Sequence[Resolution],
    by_symbol: Mapping[str, Sequence[tuple[date, date | None]]],
) -> list[str]:
    """Plain counts: how many members appear under another code at all, and how many fit."""
    total = len(resolutions)
    early = sum(
        1
        for r in resolutions
        if by_symbol.get(r.symbol) and all(stop is not None and stop <= EODHD_DELISTED_FROM for _, stop in by_symbol[r.symbol])
    )
    with_code = [r for r in resolutions if r.candidates]
    kinds = {k: sum(1 for r in with_code if r.candidates[0].matched_by == k) for k in MATCH_ORDER}
    accepted = sum(r.accepted for r in resolutions)
    ambiguous = sum(r.reason.startswith("ambiguous") for r in resolutions)
    prefix = "no candidate fits: "
    unfetched = sum(
        1
        for r in resolutions
        if r.reason.startswith(prefix)
        and all(note.endswith(" not fetched") for note in r.reason[len(prefix):].split("; "))
    )
    return [
        f"alias resolution over {total} members with no usable series "
        f"({early} left the index on or before {EODHD_DELISTED_FROM}, where EODHD's delisted history mostly starts)",
        f"  appear under another EODHD code: {len(with_code)} "
        f"(best match: " + ", ".join(f"{k} {v}" for k, v in kinds.items()) + ")",
        f"  under no other code at all: {total - len(with_code)}",
        f"  accepted {accepted}, ambiguous {ambiguous}, not fetched yet {unfetched}, "
        f"no candidate fits {len(with_code) - accepted - ambiguous - unfetched}",
    ]
```

**Impact:** new module; imports phase 1's `survivorship` at module top (phase 1 has landed).

Two small correctness notes for the implementer:
- `summary`'s "not fetched yet" counts members none of whose candidates has a probe yet (every note reads `<CODE> not fetched`), so a half-done fetch is visible before step 10.
- `choose` cleans with no dividends (`series_of(..., dividends=False)`): dividends are fetched only for the chosen code. Phase 1's `clean_symbol` takes an empty `dividends` tuple as it does for the 404 `dividends/` files.

### Step 4: Command flags and the build hook

**File:** `engine/src/seer_engine/commands/survivorship_store.py` (phase 1's file; as it stands after phase 1)
**Change:** (a) imports; (b) one line at the end of phase 1's `add_arguments`; (c) phase 1's `run`
replaced; (d) the alias section appended at the end of the module.

**(a) Imports.** Phase 1's import block reads:
```python
from seer_engine import config, dates, research
from seer_engine import dividend_announcements as da
from seer_engine import survivorship as sv
from seer_engine.commands.dividend_announcements import read_cache
```
Make it:
```python
from seer_engine import config, dates, eodhd, membership, research, survivorship_alias
from seer_engine import dividend_announcements as da
from seer_engine import survivorship as sv
from seer_engine.commands.dividend_announcements import read_cache
```
(`argparse`, `logging`/`log`, `dataclass`, `Mapping`, `Sequence`, `Path` are already imported by phase 1.)

**(b) `add_arguments`.** Phase 1's function ends with
```python
    p.add_argument("--cache", type=Path, default=CACHE_DIR, help=f"EODHD cache (default {CACHE_DIR})")
```
Append one line after it:
```python
    add_alias_arguments(p)
```

**(c) `run`.** Phase 1's `run` (quoted as phase 1 leaves it):
```python
def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if args.report:
        return _print_store_reports(out)
    try:
        plan = plan_build(Path(args.source), Path(args.cache))
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(coverage_report(plan), end="")
    if not args.build:
        print(f"\nnothing written; pass --build to write {out}")
        return 0
    if getattr(args, "dry_run", False):
        print(f"\ndry run: would write {len(plan.added)} added symbols into {out}")
        return 0
    try:
        manifest = write_store(plan, out, Path(args.cache))
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(
        f"\nwrote {out}: {manifest['symbols_served']} of {manifest['symbols_requested']} symbols served, "
        f"{manifest['bar_rows']} bar rows, price fingerprint {research.price_fingerprint_of(manifest['files'])}, "
        f"purpose {manifest[research.PURPOSE_KEY]!r}"
    )
    return 0
```
Replace it whole with:
```python
def run(args: argparse.Namespace) -> int:
    if getattr(args, "resolve_aliases", False) or getattr(args, "fetch_aliases", False):
        return run_aliases(args)
    out = Path(args.out)
    if args.report:
        return _print_store_reports(out)
    try:
        fill = alias_fill(args)  # None with --no-aliases, or a cache without the symbol lists
        plan = plan_build(
            Path(args.source), Path(args.cache), extra_sources=fill.sources if fill else None
        )
    except (OSError, ValueError) as exc:  # SurvivorshipStoreError is a RuntimeError: below
        print(f"survivorship_store: alias inputs: {exc}")
        return 2
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(coverage_report(plan), end="")
    if fill is not None:
        used = sum(1 for c in plan.cleaned.values() if c.source == survivorship_alias.ALIAS_SOURCE)
        print(f"\nalias fill: {len(fill.sources)} fetched alias series offered, {used} used")
    if not args.build:
        print(f"\nnothing written; pass --build to write {out}")
        return 0
    if getattr(args, "dry_run", False):
        print(f"\ndry run: would write {len(plan.added)} added symbols into {out}")
        return 0
    try:
        manifest = write_store(
            plan, out, Path(args.cache),
            extra_reports={survivorship_alias.REPORT_FILE: fill.report(plan)} if fill else None,
        )
    except SurvivorshipStoreError as exc:
        print(f"survivorship_store: {exc}")
        return 2
    print(
        f"\nwrote {out}: {manifest['symbols_served']} of {manifest['symbols_requested']} symbols served, "
        f"{manifest['bar_rows']} bar rows, price fingerprint {research.price_fingerprint_of(manifest['files'])}, "
        f"purpose {manifest[research.PURPOSE_KEY]!r}"
    )
    return 0
```
`SurvivorshipStoreError` subclasses `RuntimeError`, so the two `except` clauses never overlap. A
cache without `symbols-US-delisted.json` (phase 1's test fixtures) skips the alias fill instead of
failing, so phase 1's tests stay green unchanged; the real cache has both lists.

**(d) Append (end of file):**

```python
# ---- alias fill (phase 2) ------------------------------------------------------------------
#
#     python -m seer_engine survivorship_store --resolve-aliases              # offline report
#     python -m seer_engine survivorship_store --fetch-aliases [--symbols A,B] [--refetch]
#     python -m seer_engine survivorship_store --build ...                    # reads <cache>/alias/ (default)
#     python -m seer_engine survivorship_store --build --no-aliases ...       # phase 1's build alone
#
# --fetch-aliases is the only network path in this command (EODHD_API_TOKEN, from $SEER_ENV_FILE
# in a worktree). It writes under <cache>/alias/ only. The global --dry-run fetches nothing and
# writes nothing. Exit codes: 0 ok; 1 some members failed to fetch (the rest are cached);
# 2 no token, a missing input, or --symbols names a member that already has a usable series.


def add_alias_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--resolve-aliases",
        action="store_true",
        help="offline: list other EODHD codes for every member with no usable series, and which fit",
    )
    p.add_argument(
        "--fetch-aliases",
        action="store_true",
        help="network: fetch eod/splits/dividends for candidate codes into <cache>/alias/ (resumable)",
    )
    p.add_argument("--refetch", action="store_true", help="with --fetch-aliases: fetch cached codes again")
    p.add_argument(
        "--symbols", default=None, help="comma-separated members to resolve or fetch instead of all of them"
    )
    p.add_argument("--no-aliases", action="store_true", help="with --build: ignore <cache>/alias/")


def _alias_inputs(args: argparse.Namespace):
    cache_root = Path(args.cache)
    data_dir = Path(getattr(args, "data_dir", None) or membership.DATA_DIR)
    source = Path(args.source) if getattr(args, "source", None) else research.STORE_DIR
    by_symbol = survivorship_alias.intervals_by_symbol(research.research_membership(data_dir))
    unserved = research._read_unserved(source / research.UNSERVED_FILE)
    sources = survivorship_alias.load_sources(cache_root, data_dir)
    return cache_root, by_symbol, unserved, sources


def run_aliases(args: argparse.Namespace) -> int:
    sa = survivorship_alias
    dry_run = bool(getattr(args, "dry_run", False))
    try:
        cache_root, by_symbol, unserved, sources = _alias_inputs(args)
    except (OSError, ValueError) as exc:
        print(f"survivorship_store: {exc}")
        return 2
    alias_dir = cache_root / sa.ALIAS_DIR
    members = sa.targets(cache_root, unserved, by_symbol, clean=sa.phase1_clean)
    if args.symbols:
        wanted = [s.strip() for s in args.symbols.split(",") if s.strip()]
        unknown = sorted(set(wanted) - set(members))
        if unknown:
            print(f"survivorship_store: not an unserved member without a usable series: {', '.join(unknown)}")
            return 2
        members = [s for s in members if s in set(wanted)]
    status = 0
    if args.fetch_aliases:
        token = config.get(eodhd.TOKEN_ENV)
        if not token:
            print(
                f"survivorship_store: {eodhd.TOKEN_ENV} is not set (checked the environment and "
                f"{config.env_file()}); in a worktree set SEER_ENV_FILE=/home/miftah/seer/.env.local"
            )
            return 2
        if dry_run:
            codes = {
                c.code
                for s in members
                for c in sa.candidates(s, sources)
                if args.refetch or sa.read_probe(alias_dir, c.code) is None
            }
            print(
                f"dry run: would probe {len(codes)} codes for {len(members)} members into {alias_dir} "
                f"(plus one splits call per code with member-day rows, one dividends call per accepted member)"
            )
        else:
            stats = sa.fetch(
                eodhd.Client(token),
                alias_dir,
                members,
                sources=sources,
                by_symbol=by_symbol,
                clean=sa.phase1_clean,
                refetch=args.refetch,
            )
            print(
                f"alias fetch: {stats.calls} calls, {stats.accepted} members accepted, "
                f"{stats.skipped} already cached, {len(stats.failed)} failed"
                + (f": {', '.join(stats.failed)}" if stats.failed else "")
            )
            if stats.failed:
                status = 1
    resolutions = sa.resolve(members, sources=sources, alias_dir=alias_dir, by_symbol=by_symbol, clean=sa.phase1_clean)
    for line in sa.summary(resolutions, by_symbol):
        print(line)
    for r in resolutions:
        print(f"  {r.symbol:8} {r.code or '-':10} {r.matched_by or '-':12} {'yes' if r.accepted else 'no '} {r.reason}")
    return status


@dataclass(frozen=True)
class AliasFill:
    """The alias fill for one build: phase 1's ``extra_sources`` and what to report afterwards."""

    sources: Mapping[str, tuple[sv.SourceSeries, ...]]
    resolutions: tuple[survivorship_alias.Resolution, ...]
    alias_dir: Path
    by_symbol: Mapping[str, tuple[tuple[date, date | None], ...]]

    def report(self, plan: BuildPlan) -> str:
        """``alias_report.csv`` after ``plan_build`` chose between each original and its alias."""
        rows = survivorship_alias.report_rows(
            self.resolutions, plan.cleaned, alias_dir=self.alias_dir,
            by_symbol=self.by_symbol, clean=survivorship_alias.phase1_clean,
        )
        return survivorship_alias.report_text(rows)


def alias_fill(args: argparse.Namespace) -> AliasFill | None:
    """The fetched aliases ``--build`` offers ``plan_build``; None with ``--no-aliases``, or when
    the cache has no EODHD symbol lists (a test fixture: the real cache always has them).

    Offline. Re-resolves every target from the cached probes, so only an alias file whose code is
    still the resolver's choice is offered."""
    if getattr(args, "no_aliases", False):
        return None
    sa = survivorship_alias
    if not (Path(args.cache) / sa.DELISTED_FILE).is_file():
        log.warning("survivorship_store: %s has no %s; alias fill skipped", args.cache, sa.DELISTED_FILE)
        return None
    cache_root, by_symbol, unserved, sources = _alias_inputs(args)
    alias_dir = cache_root / sa.ALIAS_DIR
    members = sa.targets(cache_root, unserved, by_symbol, clean=sa.phase1_clean)
    resolutions = tuple(
        sa.resolve(members, sources=sources, alias_dir=alias_dir, by_symbol=by_symbol, clean=sa.phase1_clean)
    )
    return AliasFill(sa.alias_sources(alias_dir, resolutions), resolutions, alias_dir, by_symbol)
```

**Impact:** `--build` picks up `<cache>/alias/` by default (phase 5 relies on "no extra flag");
`--no-aliases` turns it off. With no `alias/` directory, the fill offers nothing and
`alias_report.csv` is still written, its rows saying "not fetched" or "no candidate code". The
alias series enter phase 1's `plan_build` through `extra_sources` and compete in `best_of`, so a
filled symbol's `cleaning_report.csv` row carries `source = eodhd-alias` and `code = <ALIAS>.US`
(phase 1's report columns), with phase 1's own reason text.

### Step 5: Tests (no network)

**File:** `engine/tests/test_survivorship_alias.py` (new)

```python
"""Alias fill: the EODHD client's by-code endpoints (fake transport), candidate codes, the
series test, the fetch (fake client), the alias series as phase 1's second source, the report and
the command. No network."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
import requests

from seer_engine import eodhd, research
from seer_engine import survivorship_alias as sa
from seer_engine.commands import survivorship_store as cmd
import test_research_store as rs
from test_dividend_announcements import FakeTransport, Resp, client

IV = ((date(2000, 1, 3), date(2002, 1, 2)),)


def weekdays(start, end):
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def eod_rows(start, end, close=10.0):
    return [
        {"date": d.isoformat(), "open": close, "high": close, "low": close, "close": close,
         "adjusted_close": close, "volume": 1000}
        for d in weekdays(start, end)
    ]


@dataclass(frozen=True)
class FakeResult:
    action: str
    reason: str


def fake_clean(series, intervals):
    """Stands in for ``sa.phase1_clean``: kept when the series has bars."""
    return FakeResult("kept", "clean") if series.bars else FakeResult("dropped", "no rows")


def L(code, name="X Corp", kind="Common Stock", delisted=True):
    return sa.Listing(code, name, kind, "NYSE", delisted)


def sources(listings, names=None, aliases=None, hints=None):
    return sa.Sources(
        listings=sa.Listings.of(listings),
        names={k: tuple(v) for k, v in (names or {}).items()},
        aliases={k: frozenset(v) for k, v in (aliases or {}).items()},
        hints={k: tuple(v) for k, v in (hints or {}).items()},
    )


# ---- client --------------------------------------------------------------------------------


def test_exchange_code_is_verbatim_and_refuses_store_symbols():
    assert eodhd.exchange_code("DELL_old") == "DELL_old.US"
    assert eodhd.exchange_code(" BRK-B ") == "BRK-B.US"
    with pytest.raises(ValueError):
        eodhd.exchange_code("BRK.B")
    with pytest.raises(ValueError):
        eodhd.exchange_code("")


def test_eod_splits_and_dividends_by_code_hit_their_endpoints():
    t = FakeTransport(
        Resp(200, [{"date": "2000-01-03", "close": 1.0}]),
        Resp(200, [{"date": "1999-03-01", "split": "2.000000/1.000000"}]),
        Resp(200, []),
        Resp(404, text="Ticker Not Found"),
    )
    c = client(t)
    assert c.eod("DELL_old") == [{"date": "2000-01-03", "close": 1.0}]
    assert c.splits("DELL_old") == [{"date": "1999-03-01", "split": "2.000000/1.000000"}]
    assert c.dividends_by_code("DELL_old") == []
    assert c.eod("GONE_old") is None
    (u1, p1), (u2, p2), (u3, p3), (u4, _) = t.calls
    assert u1.endswith("/eod/DELL_old.US") and p1["period"] == "d" and p1["from"] == "1993-01-01"
    assert u2.endswith("/splits/DELL_old.US") and p2["from"] == "1990-01-01"
    assert u3.endswith("/div/DELL_old.US")
    assert u4.endswith("/eod/GONE_old.US")
    assert all(p["api_token"] == "secret-token" and p["fmt"] == "json" for _, p in t.calls)


def test_eod_retries_and_never_leaks_the_token():
    t = FakeTransport(Resp(503), requests.ConnectionError("down"), Resp(200, []))
    assert client(t).eod("X_old") == []
    assert len(t.calls) == 3
    t = FakeTransport(Resp(403, text="Forbidden for api_token=secret-token"))
    with pytest.raises(eodhd.EodhdError) as exc:
        client(t).splits("X_old")
    assert "secret-token" not in str(exc.value)
    t = FakeTransport(Resp(200, {"message": "bad secret-token"}))
    with pytest.raises(eodhd.EodhdError) as exc:
        client(t).eod("X_old")
    assert "secret-token" not in str(exc.value) and "price list" in str(exc.value)


def test_dividends_by_store_symbol_is_unchanged():
    t = FakeTransport(Resp(200, []))
    assert client(t).dividends("BRK.B") == []
    assert t.calls[0][0].endswith("/div/BRK-B.US")
    assert "period" not in t.calls[0][1]


# ---- names and codes -----------------------------------------------------------------------


def test_code_root_strips_the_vendor_suffixes():
    assert sa.code_root("DELL_old") == "DELL"
    assert sa.code_root("AT_old1") == "AT"
    assert sa.code_root("TRW1") == "TRW"
    assert sa.code_root("MCWEQ") == "MCWEQ"
    assert sa.code_root("BRK-B") == "BRK-B"


def test_normalize_name_ignores_legal_forms_and_state_tags():
    assert sa.normalize_name("DOW CHEMICAL CO /DE/") == "DOW CHEMICAL"
    assert sa.normalize_name("The Dow Chemical Company") == "DOW CHEMICAL"
    assert sa.normalize_name("AT&T Inc.") == "AT T"
    assert sa.normalize_name("Inc.") == ""


def test_load_listings_skips_funds_and_prefers_the_delisted_row(tmp_path):
    (tmp_path / sa.DELISTED_FILE).write_text(json.dumps([
        {"Code": "DELL_old", "Name": "Dell Inc", "Type": "Common Stock", "Exchange": "NASDAQ"},
        {"Code": "PWER_old", "Name": "Power One Inc", "Type": "ETF", "Exchange": "NASDAQ"},
        {"Code": "ZZFUND", "Name": "Some Fund", "Type": "FUND", "Exchange": "PINK"},
        {"Code": "CHK", "Name": "Chesapeake Energy Corporation", "Type": "Common Stock", "Exchange": "NASDAQ"},
    ]))
    (tmp_path / sa.LIVE_FILE).write_text(json.dumps([
        {"Code": "DELL", "Name": "Dell Technologies Inc", "Type": "Common Stock", "Exchange": "NYSE"},
        {"Code": "CHK", "Name": "Somebody Else", "Type": "Common Stock", "Exchange": "NYSE"},
    ]))
    listings = sa.load_listings(tmp_path)
    assert set(listings.by_code) == {"DELL_old", "PWER_old", "CHK", "DELL"}
    assert listings.by_code["CHK"].delisted and listings.by_code["CHK"].name.startswith("Chesapeake")
    assert listings.by_root["DELL"] == ("DELL", "DELL_old")


def test_candidates_rank_by_match_kind_and_never_repeat_the_store_code():
    src = sources(
        [L("DELL", "Dell Technologies Inc", delisted=False), L("DELL_old", "Dell Inc"), L("DELL1"),
         L("MCWEQ", "WorldCom, Inc"), L("WCO", "Wco Holdings"),
         L("GFS", "Globalfoundries Inc"), L("GFSA", "Giant Food Inc"),
         L("ARNC", "Arconic"), L("ARNC_old", "Arconic Old"),
         L("AT_old"), L("AT_old1"), L("AT_old2"), L("AT1"), L("AT2")],
        names={"DELL": ["DELL INC"]},
        aliases={"HWM": {"ARNC"}},
        hints={"WCOEQ": ["MCWEQ"]},
    )
    assert [(c.code, c.matched_by) for c in sa.candidates("DELL", src)] == [
        ("DELL_old", "name"), ("DELL1", "code-variant")]
    assert [(c.code, c.matched_by) for c in sa.candidates("WCOEQ", src)] == [
        ("MCWEQ", "hint"), ("WCO", "bankruptcy")]
    assert [(c.code, c.matched_by) for c in sa.candidates("GFS.A", src)] == [
        ("GFS", "class"), ("GFSA", "class")]
    assert [(c.code, c.matched_by) for c in sa.candidates("HWM", src)] == [
        ("ARNC", "alias"), ("ARNC_old", "alias")]
    at = sa.candidates("AT", src)
    assert len(at) == sa.MAX_CANDIDATES and all(c.matched_by == "code-variant" for c in at)
    assert sa.candidates("NOPE", src) == ()


def test_a_hint_for_a_code_not_in_the_lists_is_not_a_candidate():
    src = sources([L("LEH")], hints={"LEHMQ": ["LEH", "NOTLISTED"]})
    assert [c.code for c in sa.candidates("LEHMQ", src)] == ["LEH"]


# ---- the series test -----------------------------------------------------------------------


def test_member_closes_keep_only_member_days_inside_the_dev_window():
    rows = eod_rows(date(1999, 12, 27), date(2002, 1, 4))
    closes = sa.member_closes(rows, IV)
    assert min(closes) == date(2000, 1, 3) and max(closes) == date(2002, 1, 1)  # 2002-01-02 is the exclusive end
    open_ended = sa.member_closes(eod_rows(date(2015, 10, 1), date(2015, 10, 30)), ((date(2015, 1, 2), None),))
    assert max(open_ended) == research.DEV_END  # clipped to the dev window
    assert sa.member_closes(None, IV) == {}


def probe(rows, splits=()):
    return {"eod": rows, "splits": list(splits)}


CANDS = (sa.Candidate("A_old", "A Inc", "code-variant"), sa.Candidate("A1", "A One", "code-variant"))


def test_choose_without_candidates_or_overlap_says_why():
    r = sa.choose("A", (), {}, IV, clean=fake_clean)
    assert not r.accepted and r.reason.startswith("no candidate code")
    r = sa.choose("A", CANDS, {"A_old": probe(eod_rows(date(2010, 1, 4), date(2011, 1, 4)))}, IV, clean=fake_clean)
    assert not r.accepted and "A_old has 0 rows on member days" in r.reason and "A1 not fetched" in r.reason


def test_choose_needs_splits_and_phase_one_cleaning():
    rows = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    r = sa.choose("A", CANDS[:1], {"A_old": {"eod": rows}}, IV, clean=fake_clean)
    assert not r.accepted and "splits not fetched" in r.reason
    r = sa.choose("A", CANDS[:1], {"A_old": probe(rows)}, IV, clean=lambda *a: FakeResult("dropped", "splice"))
    assert not r.accepted and "dropped (splice)" in r.reason


def test_choose_accepts_the_single_fit():
    rows = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    r = sa.choose("A", CANDS, {"A_old": probe(rows), "A1": probe(eod_rows(date(2012, 1, 2), date(2013, 1, 2)))}, IV, clean=fake_clean)
    assert r.accepted and r.code == "A_old" and r.matched_by == "code-variant"


def test_two_different_fitting_series_are_ambiguous_unless_one_is_named():
    a = eod_rows(date(2000, 1, 3), date(2001, 12, 31), close=10.0)
    b = eod_rows(date(2000, 1, 3), date(2001, 12, 31), close=50.0)
    r = sa.choose("A", CANDS, {"A_old": probe(a), "A1": probe(b)}, IV, clean=fake_clean)
    assert not r.accepted and r.code is None and r.reason.startswith("ambiguous")
    named = (sa.Candidate("GM_old", "General Motors Corp", "hint"), sa.Candidate("MTL", "Mechel", "bankruptcy"))
    r = sa.choose("MTLQQ", named, {"GM_old": probe(a), "MTL": probe(b)}, IV, clean=fake_clean)
    assert r.accepted and r.code == "GM_old" and "preferred over MTL" in r.reason


def test_one_company_under_two_codes_is_not_ambiguous():
    long = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    short = eod_rows(date(2000, 1, 3), date(2001, 6, 29))
    r = sa.choose("A", CANDS, {"A_old": probe(short), "A1": probe(long)}, IV, clean=fake_clean)
    assert r.accepted and r.code == "A1" and "same series as A_old" in r.reason


# ---- fetch ---------------------------------------------------------------------------------


class FakeClient:
    def __init__(self, eod, splits=None, divs=None, fail=()):
        self.eod_rows, self.split_rows, self.div_rows, self.fail = eod, splits or {}, divs or {}, set(fail)
        self.log = []

    def eod(self, code):
        self.log.append(("eod", code))
        if code in self.fail:
            raise eodhd.EodhdError(f"HTTP 500 for {code}.US")
        return self.eod_rows.get(code)

    def splits(self, code):
        self.log.append(("splits", code))
        return self.split_rows.get(code, [])

    def dividends_by_code(self, code):
        self.log.append(("div", code))
        return self.div_rows.get(code, [])


def fetch_setup():
    src = sources([L("AAA_old", "Aaa Inc"), L("AAA1", "Aaa One")])
    rows = eod_rows(date(2000, 1, 3), date(2001, 12, 31))
    fake = FakeClient({"AAA_old": rows, "AAA1": eod_rows(date(2010, 1, 4), date(2010, 6, 30))},
                      divs={"AAA_old": [{"date": "2000-06-01", "value": 0.1}]})
    return src, fake, rows


def test_fetch_probes_candidates_and_writes_the_accepted_alias(tmp_path):
    src, fake, rows = fetch_setup()
    stats = sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    # both are code variants, ranked by code: "AAA1" < "AAA_old"
    assert fake.log == [("eod", "AAA1"), ("eod", "AAA_old"), ("splits", "AAA_old"), ("div", "AAA_old")]
    assert (stats.calls, stats.accepted, stats.failed) == (4, 1, [])
    doc = sa.read_alias(tmp_path, "AAA")
    assert doc["code"] == "AAA_old" and doc["eod"] == rows and doc["splits"] == []
    assert doc["dividends"] == [{"date": "2000-06-01", "value": 0.1}] and doc["matched_by"] == "code-variant"
    assert "splits" not in sa.read_probe(tmp_path, "AAA1")  # no member-day rows: no splits call

    fake.log.clear()
    again = sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    assert fake.log == [] and again.skipped == 1
    sa.alias_path(tmp_path, "AAA").unlink()
    sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    assert fake.log == [("div", "AAA_old")]  # probes reused, only the dividends call repeats
    fake.log.clear()
    sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean, refetch=True)
    assert ("eod", "AAA_old") in fake.log and ("eod", "AAA1") in fake.log


def test_fetch_records_a_failure_and_goes_on(tmp_path):
    src, fake, _ = fetch_setup()
    fake.fail = {"AAA_old"}
    stats = sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    assert stats.failed == ["AAA"] and sa.read_alias(tmp_path, "AAA") is None


# ---- the second source and the report ------------------------------------------------------


@dataclass(frozen=True)
class Chosen:
    """Stands in for phase 1's ``Cleaned`` as ``BuildPlan.cleaned`` holds it."""

    action: str
    source: str


def test_alias_sources_offer_only_fetched_accepted_codes_and_the_report_follows_the_build(tmp_path):
    src, fake, rows = fetch_setup()
    sa.fetch(fake, tmp_path, ["AAA"], sources=src, by_symbol={"AAA": IV}, clean=fake_clean)
    by_symbol = {"AAA": IV, "CCC": IV}
    res = sa.resolve(["AAA", "CCC"], sources=src, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    extra = sa.alias_sources(tmp_path, res)
    assert list(extra) == ["AAA"]
    (series,) = extra["AAA"]
    assert (series.symbol, series.source, series.code) == ("AAA", sa.ALIAS_SOURCE, "AAA_old.US")
    assert len(series.bars) == len(rows) and series.splits == ()
    assert [d.ex_date for d in series.dividends] == [date(2000, 6, 1)]

    taken = {"AAA": Chosen("kept", sa.ALIAS_SOURCE), "CCC": Chosen("dropped", "eodhd")}
    report = sa.report_rows(res, taken, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    assert [(r.symbol, r.code, r.accepted) for r in report] == [("AAA", "AAA_old", True), ("CCC", "", False)]
    assert report[0].reason.startswith("kept: ") and report[1].reason.startswith("no candidate code")

    kept_original = {"AAA": Chosen("kept", "eodhd")}
    (row,) = sa.report_rows(res[:1], kept_original, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    assert not row.accepted and row.reason.startswith("not used")

    sa.alias_path(tmp_path, "AAA").unlink()
    assert sa.alias_sources(tmp_path, res) == {}
    (row,) = sa.report_rows(res[:1], {}, alias_dir=tmp_path, by_symbol=by_symbol, clean=fake_clean)
    assert not row.accepted and "--fetch-aliases" in row.reason


def test_report_text_quotes_names_with_commas():
    text = sa.report_text([sa.ReportRow("WCOEQ", "MCWEQ", "WorldCom, Inc", "hint", True, "kept: 1000 rows")])
    assert text == (
        "symbol,code,name,matched_by,accepted,reason\n"
        'WCOEQ,MCWEQ,"WorldCom, Inc",hint,yes,kept: 1000 rows\n'
    )


# ---- the command (phase 1's real cleaning on a tiny cache) ---------------------------------


@pytest.fixture
def members(tmp_path):
    return rs.members_dir.__wrapped__(tmp_path)


def command_cache(tmp_path):
    cache = tmp_path / "eodhd"
    for sub in ("eod", "splits", "dividends"):
        (cache / sub).mkdir(parents=True)
    (cache / "eod" / "GONE.json").write_text("null")
    (cache / "splits" / "GONE.json").write_text("null")
    (cache / "dividends" / "GONE.json").write_text(json.dumps({"symbol": "GONE", "rows": None}))
    (cache / sa.DELISTED_FILE).write_text(json.dumps([
        {"Code": "GONE_old", "Name": "Gone Corp", "Type": "Common Stock", "Exchange": "NYSE"}]))
    (cache / sa.LIVE_FILE).write_text("[]")
    return cache


def cmd_args(store, cache, members, **kw):
    base = dict(cache=cache, source=store, data_dir=members, resolve_aliases=True, fetch_aliases=False,
                refetch=False, symbols=None, no_aliases=False, dry_run=False, verbose=0)
    return argparse.Namespace(**{**base, **kw})


def test_command_resolves_offline_from_cached_probes(tmp_path, members, capsys):
    store = tmp_path / "store"
    rs.build(store, members)
    cache = command_cache(tmp_path)
    rows = eod_rows(date(1997, 12, 31), date(1999, 12, 31), close=20.0)  # GONE is a member 1996..2000-01-03
    sa._write_json(sa.probe_path(cache / sa.ALIAS_DIR, "GONE_old"), {"code": "GONE_old", "eod": rows, "splits": []})
    assert cmd.run(cmd_args(store, cache, members)) == 0
    out = capsys.readouterr().out
    assert "appear under another EODHD code: 1" in out
    assert "GONE     GONE_old" in out and " yes " in out


def test_command_fetch_dry_run_makes_no_call_and_no_token_exits_2(tmp_path, members, monkeypatch, capsys):
    store = tmp_path / "store"
    rs.build(store, members)
    cache = command_cache(tmp_path)
    monkeypatch.setattr(cmd.config, "get", lambda name: "tok")

    def boom(*a, **k):
        raise AssertionError("no client in a dry run")

    monkeypatch.setattr(eodhd, "Client", boom)
    # the fixture store's unserved list is GONE and DDD (DDD has bars only after DEV_END and no
    # cache file, so it is a target with no candidate); --symbols keeps the count exact
    assert cmd.run(cmd_args(store, cache, members, fetch_aliases=True, dry_run=True, symbols="GONE")) == 0
    assert "dry run: would probe 1 codes for 1 members" in capsys.readouterr().out
    assert not (cache / sa.ALIAS_DIR).exists()

    monkeypatch.setattr(cmd.config, "get", lambda name: None)
    assert cmd.run(cmd_args(store, cache, members, fetch_aliases=True)) == 2
    assert eodhd.TOKEN_ENV in capsys.readouterr().out


def test_the_build_takes_a_fetched_alias_as_phase_ones_second_source(tmp_path, members):
    store = tmp_path / "store"
    rs.build(store, members)
    cache = command_cache(tmp_path)
    rows = eod_rows(date(1997, 12, 31), date(1999, 12, 31), close=20.0)  # GONE: member 1996..2000-01-03
    alias_dir = cache / sa.ALIAS_DIR
    sa._write_json(sa.probe_path(alias_dir, "GONE_old"), {"code": "GONE_old", "eod": rows, "splits": []})
    sa._write_json(sa.alias_path(alias_dir, "GONE"), {
        "symbol": "GONE", "code": "GONE_old", "name": "Gone Corp", "matched_by": "code-variant",
        "fetched": "2026-10-10T00:00:00+00:00", "eod": rows, "splits": [], "dividends": [],
    })
    fill = cmd.alias_fill(cmd_args(store, cache, members, resolve_aliases=False))
    assert list(fill.sources) == ["GONE"]
    plan = cmd.plan_build(store, cache, data_dir=members, extra_sources=fill.sources)
    gone = plan.cleaned["GONE"]
    assert (gone.source, gone.code) == (sa.ALIAS_SOURCE, "GONE_old.US") and gone.action in sa.USABLE_ACTIONS
    out = tmp_path / "store-sv"
    manifest = cmd.write_store(plan, out, cache, data_dir=members,
                               extra_reports={sa.REPORT_FILE: fill.report(plan)})
    assert sa.REPORT_FILE not in manifest["files"]
    report = (out / sa.REPORT_FILE).read_text(encoding="utf-8")
    assert "GONE,GONE_old,Gone Corp,code-variant,yes," in report
    assert "GONE" in research.load_store(out, data_dir=members).market.history
    assert cmd.alias_fill(cmd_args(store, cache, members, resolve_aliases=False, no_aliases=True)) is None
```

**Impact:** the two command tests and the build test exercise phase 1's real `clean_symbol` (a
`null` pull must come out unusable; a flat 1998-1999 series with no splits must come out `kept`)
and phase 1's real `plan_build` / `write_store` / `best_of`. Every other test injects `fake_clean`.
`rs.build` puts `GONE` in the store's `unserved.csv` (as `test_dividend_announcements` relies on).
Phase 1's `test_survivorship_store.py` must stay green unchanged: its fake cache has no symbol
lists, so `alias_fill` returns None there.

### Step 6: Lint and the full suite (before any network)

```bash
cd "$WT"
engine/.venv/bin/ruff check engine
engine/.venv/bin/python -m pytest engine/tests/test_survivorship_alias.py engine/tests/test_survivorship_store.py engine/tests/test_dividend_announcements.py -q
engine/.venv/bin/python -m pytest engine/tests -q        # whole suite (≈4,040+ tests), must pass
```

Commit on the feature branch (code only, before the real fetch):

```bash
git add engine/src/seer_engine/eodhd.py engine/src/seer_engine/survivorship_alias.py \
        engine/src/seer_engine/commands/survivorship_store.py engine/data/eodhd_alias_hints.csv \
        engine/data/SOURCES.md engine/tests/test_survivorship_alias.py
git status --short          # must NOT list lab/lab.sqlite as staged, nor engine/.cache or engine/.research
git commit -m "feat(survivorship): alias fill for index members with no usable EODHD series"
```
(end the message with the attribution line from the session's system reminder). Never
`git add lab/lab.sqlite`; never commit anything under `engine/.cache`.

### Step 7: Offline resolution, before any call

```bash
cd "$WT"
C=/home/miftah/seer/engine/.cache/eodhd
engine/.venv/bin/python -m seer_engine survivorship_store --resolve-aliases \
  --cache $C --source /home/miftah/seer/engine/.research | tee /tmp/claude-1000/p2-resolve-before.txt | head -8
```

Expected: "alias resolution over 200 members" (phase 1's 200 drops; if it differs, stop: the
cache or phase 1's cleaning differs from what phase 1 measured); "appear under another EODHD code"
157 or 158; "accepted 0 … not fetched yet" the same 157-158. This line is the handover's question ("how many of the 201
appear under another code at all") answered offline — copy it into the commit message of step 11.

### Step 8: Dry run

```bash
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine --dry-run \
  survivorship_store --fetch-aliases --cache $C --source /home/miftah/seer/engine/.research
```
Expected: `dry run: would probe ≈220 codes for 200 members`. No `alias/` directory appears.

### Step 9: Smoke fetch (network; key valid until 2026-11-10)

```bash
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine \
  survivorship_store --fetch-aliases --symbols WCOEQ,DELL,MTLQQ,HWM \
  --cache $C --source /home/miftah/seer/engine/.research
ls $C/alias $C/alias/probe
python3 -c "import json;d=json.load(open('$C/alias/probe/DELL_old.json'));print(d['code'], None if d['eod'] is None else (d['eod'][0]['date'], d['eod'][-1]['date'], len(d['eod'])))"
grep -rl "$(sed -n 's/^EODHD_API_TOKEN=//p' /home/miftah/seer/.env.local)" $C/alias && echo "TOKEN LEAKED" || echo "no token in alias files"
```

Expected: ≈10-14 calls; `DELL_old` has rows from ≤1998 to 2013; WCOEQ → MCWEQ, DELL → DELL_old,
MTLQQ → GM_old accepted. **If `DELL_old.json` holds `"eod": null`** (EODHD does not serve suffixed
codes by that spelling), stop the `_old` path: re-check one code by hand with
`curl -s "https://eodhd.com/api/eod/DELL_old.US?fmt=json&from=2000-01-01&to=2000-01-10&api_token=…"`
(never paste the token into a log or commit), and if it 404s, record in the commit message that
suffixed codes are list-only, and continue with the full fetch anyway — hint, name, alias, class and
bankruptcy-stem codes (`MCWEQ`, `LEH`, `ABK`, `GFSA`, `TRW1`…) are plain codes and still resolve.

### Step 10: Full fetch, then the offline report

```bash
SEER_ENV_FILE=/home/miftah/seer/.env.local engine/.venv/bin/python -m seer_engine \
  survivorship_store --fetch-aliases --cache $C --source /home/miftah/seer/engine/.research
# exit 1 means some members failed: run the same command again (resumable) until exit 0 or the same
# members keep failing; list persistent failures in the commit message
engine/.venv/bin/python -m seer_engine survivorship_store --resolve-aliases \
  --cache $C --source /home/miftah/seer/engine/.research | tee /tmp/claude-1000/p2-resolve-after.txt | head -8
( cd $C && find eod splits dividends market -type f | sort | xargs sha256sum | sha256sum ) | diff - /tmp/claude-1000/p2-cache-before.sha && echo "original cache untouched"
```

Expected: ≈500 calls in total (≤ ~10 minutes at the 0.1 s pace); accepted roughly 100-140 of the
≈157 with candidates (the rest: no member-day rows, or ambiguous); the original cache's hash
unchanged.

### Step 11: Rebuild the SV store offline and record the gain

```bash
SV=/home/miftah/seer/engine/.research-sv
cp $SV/coverage_report.txt /tmp/claude-1000/p2-coverage-before.txt      # phase 1's build
cp $SV/cleaning_report.csv /tmp/claude-1000/p2-cleaning-before.csv
python3 -c "import json;print(json.load(open('$SV/manifest.json'))['fingerprint'])" > /tmp/claude-1000/p2-sv-fp-before.txt
python3 -c "import json;print(json.load(open('/home/miftah/seer/engine/.research/manifest.json'))['fingerprint'])"   # must start fd2bc190
# the rebuild swaps the SV store directory: wait until no session is reading it (phase 4's smoke
# run may be live in parallel). Monitor until-loop, never a foreground sleep:
#   until ! pgrep -f '[s]eer_engine.*( lab .*survivorship|market_series|survivorship_store)'; do sleep 60; done
# (phase 4's smoke run is `seer_engine -v lab --db … survivorship …`, so the pattern allows flags
# between `lab` and `survivorship`)
engine/.venv/bin/python -m seer_engine survivorship_store --build \
  --out $SV --source /home/miftah/seer/engine/.research --cache $C
diff /tmp/claude-1000/p2-coverage-before.txt $SV/coverage_report.txt | head -60
wc -l $SV/alias_report.csv && awk -F, 'NR>1{print $(NF-1)}' $SV/alias_report.csv | sort | uniq -c
python3 -c "import json;print(json.load(open('/home/miftah/seer/engine/.research/manifest.json'))['fingerprint'])"   # still fd2bc190…
engine/.venv/bin/python -c "
from pathlib import Path; from seer_engine import research
d = research.load_store(Path('$SV')); print(d.price_fingerprint, len(d.market.history))"
```

(This is phase 1's Step 9 invocation exactly; alias pickup is the default, `--no-aliases` turns it
off. The SV store does not carry `market_series.csv` at this point; phase 5 adds it after its own
final rebuild, Decision D9.)

Then commit a small derived-numbers note in the commit message only (no vendor rows): the step-7
"appear under another code" line, accepted/ambiguous/no-fit counts, total calls, and the
whole-window plus 1996/1997/1998/2008 member-day coverage before → after from the two
`coverage_report.txt` files:

```bash
git commit --allow-empty -m "survivorship: alias fill fetched and SV store rebuilt — <counts and coverage before→after>"
```
(attribution line appended). `alias_report.csv` stays inside the store (gitignored); phase 5
copies the derived tables into `docs/lab/survivorship/`.

## Verification

**Build:** `engine/.venv/bin/ruff check engine` and `engine/.venv/bin/python -c "import seer_engine.survivorship_alias, seer_engine.commands.survivorship_store"`
**Tests:** `engine/.venv/bin/python -m pytest engine/tests -q` (full suite; the new file needs no network — the client tests use `FakeTransport`, the fetch tests a fake client, the command dry-run test replaces `eodhd.Client` with a function that fails if called)
**Manual check:** `alias_report.csv` in `/home/miftah/seer/engine/.research-sv` has one row per target (200 + header); spot-check WCOEQ/MCWEQ, DELL/DELL_old, MTLQQ/GM_old, LEHMQ/LEH accepted, and BEV "no candidate code"; `cleaning_report.csv` shows those symbols with `source = eodhd-alias` and `code = <ALIAS>.US` (e.g. `MCWEQ.US`) and an action other than `dropped`; `coverage_report.txt` member-day coverage is higher than phase 1's in every year from 1998 on; no file under `alias/` contains the token.
**Exit criteria:**
- every originally empty member has a resolution line (code + why, or "no candidate code" / "no candidate fits: …" / "ambiguous: …") in `alias_report.csv`;
- accepted series were fetched with ≤ 4 `/eod` probes + 1 `/splits` per overlapping probe + 1 `/div` per member, and passed phase 1's cleaning with their own dividends;
- the SV store was rebuilt offline, loads with `research.load_store`, and its coverage report shows the gain; `engine/.research`'s fingerprint is still `fd2bc190…` and its price fingerprint `5451195f…`;
- the original `eod/`, `splits/`, `dividends/`, `market/` cache files hash identically before and after;
- the full engine suite passes; commits are on `feature/eodhd-survivorship-market` only.

## Handoffs

- **Phase 1 (resolved by the reconciler):** this plan now uses phase 1's real seam — `SourceSeries`, `clean_symbol(series, member_days, sessions)`, `best_of`, `plan_build(extra_sources=)`, `write_store(extra_reports=)` — and replaces phase 1's `run()` whole (Step 4c quotes it). The worktree exclude lines for the symlinks moved into phase 1 Step 0.
- **Phase 5:** reads `alias_report.csv` and the step-11 numbers for the plain-words insight ("the alias fill found another code for «a» of the «200» members…"); its own offline rebuild picks up `alias/` with no flag (`--no-aliases` exists to turn it off). Copying `alias_report.csv`-derived counts into `docs/lab/survivorship/` is phase 5's.
- **Not done (Decision D11):** the 39 dev-served symbols with no bar on a member day (phase 1's handoff). `plan_build` only cleans `data.unserved`, and replacing dev rows is refused by `merge_sorted_lines`; they stay in the "still missing" list.
- **R7, gate half (phase 5):** this phase only decides and spends the calls; whether the gate uses the store stays Decision D1.
- **Not done, deliberately:** `eod-bulk-last-day` (Decision D2) and the 26 pre-1998 members with no code at all — their gap is EODHD's history start, which no call fixes; phase 5's insight should name it.

## Rollback

`git revert` the phase's commits; `rm -rf /home/miftah/seer/engine/.cache/eodhd/alias`; rebuild
the SV store with phase 1's command (or with `--no-aliases` before reverting). The dev store and the
original cache were never written, so nothing else moves. The calls spent are not recoverable and
need not be.
