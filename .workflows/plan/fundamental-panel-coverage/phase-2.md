# Phase 2: Fix A — re-vendor `ticker_cik.csv` back to real 2009 membership

**Plan set:** `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md`
**Analysis:** `20261005-133648-2XUM_code_analyzer.md`
**Satisfies:** R1 — `ticker_cik.csv` carries each symbol's real first-membership interval, with every §2 invariant still enforced by tests
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/scripts`, `engine/data`, `seer_engine.cik`

---

## Runtime preamble — run this before every command in this phase

Reconciled set-wide (see the index's `## Decisions`, row C2). The worktree has **no venv of its
own**, and `/home/miftah/seer/engine/.venv` is an *editable* install whose
`__editable__.seer_engine-0.1.0.pth` contains the literal `/home/miftah/seer/engine/src` — the
**main checkout**. `engine/pyproject.toml`'s `[tool.pytest.ini_options]` sets only
`testpaths = ["tests"]` and **no `pythonpath`**, so pytest resolves `seer_engine` through that
same editable install. Without the block below, every command in this phase — `pytest`
included — silently exercises `main`'s code and reads `main`'s `engine/data/`.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/fundamental-panel-coverage
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src          # searched before anything `site` adds
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

**Reuse main's venv; do not build one in the worktree.** `PYTHONPATH` wins over the `.pth`
(measured), carries `cik.DATA_DIR` (`Path(cik.__file__).parents[2] / "data"`) to the worktree
with it, and applies uniformly to `pytest` and to `python -m seer_engine`. A second venv would
mean a second dependency resolution, and invariant 1 pins this set to the `2dad9ff` baseline of
2216 passed / 332 skipped measured in *this* interpreter.
`engine/scripts/build_ticker_cik.py:40` does its own
`sys.path.insert(0, Path(__file__).resolve().parents[1] / "src")`, so the generator
self-resolves when invoked by its worktree path — that rescues the generator and nothing else.

The generator additionally needs two free, non-credential values that live only in the main
checkout's `.env.local` (`.env*` is gitignored, so the worktree has neither file). Export them
into the process environment rather than pointing `SEER_ENV_FILE` at the main file:
`SecFetcher` reads `os.environ["SEC_CONTACT_EMAIL"]` directly at construction, *before* anything
calls `config.load_env()`.

```bash
eval "$("$SEER_PY" -c 'import shlex; from dotenv import dotenv_values; v = dotenv_values("/home/miftah/seer/.env.local"); print("\n".join(f"export {k}={shlex.quote(v[k])}" for k in ("SEC_CONTACT_EMAIL", "MASSIVE_API_KEY")))')"
test -n "$SEC_CONTACT_EMAIL" && test -n "$MASSIVE_API_KEY" && echo "env ok"
```

Neither value is sent anywhere but to `sec.gov` (as the `User-Agent` SEC's fair-access policy
requires) and `api.massive.com`. Both services are free. **This phase connects to no database**,
so it needs no `SEER_ENV_FILE`.

---

## Goal

`cik.SINCE` moves from `2015-01-02` to `2009-01-01` and the generator stops copying that clamp
into the data it writes. After this phase `engine/data/ticker_cik.csv` holds **913 symbols**
(up from 795) and **zero rows whose `start_date` is 2015-01-02** — measured: no symbol's real
first-membership date is 2015-01-02, so every one of the 525 shipped rows at that date was the
clamp and not a fact. The dated join at `backtest/io.py:93` can then reach the 181,491 facts
already sitting in the local database with `filed` in 2013–2014, and phase 3's lower ingest
floor has somewhere to land.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**

- `build_ticker_cik.periodic_dates(fetcher, cik) -> tuple[str, ...]` (`engine/scripts/build_ticker_cik.py`) — memoised list of every periodic-report `filingDate` a CIK has; `filed_inside` becomes a thin filter over it.
- `build_ticker_cik.EARLY_WINDOW_DAYS = 450` and `build_ticker_cik.EARLY_EXEMPT: dict[str, str]` (`engine/scripts/build_ticker_cik.py`) — the second screen and its exemption table. **This is an addition the index did not name; see `## Decisions I took` for why it is inside R1 and not scope creep.**
- `build_ticker_cik._PERIODIC_CACHE: dict[str, tuple[str, ...]]` — module-level memo.
- New tests in `engine/tests/test_cik.py`, **five** of them (step 8b writes five; the verification
  section's `+5` delta counts these): `test_vendored_floor_is_2009_and_no_row_precedes_it`,
  `test_vendored_no_row_starts_before_the_floor`,
  `test_vendored_carries_no_row_at_the_retired_2015_clamp`, `test_vendored_has_no_fuzzy_row`,
  `test_vendored_none_row_is_ndoi_and_it_is_alone`.

**Signature changes:**

- `build_ticker_cik.filed_inside(fetcher, cik, start, end) -> int` — **signature unchanged**, body re-expressed over `periodic_dates`.

**Value changes (the whole point):**

- `seer_engine.cik.SINCE`: `date(2015, 1, 2)` -> `date(2009, 1, 1)` (`engine/src/seer_engine/cik.py:44`). Its three consumers are `cik.coverage_gaps`'s default (`cik.py:329`), `build_ticker_cik` (`:43,716,717,737,746`) and the `ever_members` fixture (`test_cik.py:316`). Measured: **no other module in `engine/` reads it.**
- `build_ticker_cik.MANUAL`: an empty `start` cell now means *"the symbol's membership start, from `spans()`"*. 56 entries change their literal `"2015-01-02"` to `""`. Every `end` is untouched.
- `engine/data/ticker_cik.csv`: regenerated, 798 rows / 795 symbols -> **≥916 rows / 913 symbols**.

**Requires (from earlier phases):** nothing. This phase has no `depends_on`.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/commands/fundamentals.py` — `DEFAULT_SINCE`, `DEFAULT_SINCE_FILED`, the module docstring, the two `--since*` help strings (**Phase 3**). This phase does not lower either ingest floor and does not run the ingest.
- `engine/src/seer_engine/fundamentals/**` (**Phase 1**).
- `engine/src/seer_engine/research.py`, `engine/src/seer_engine/commands/research_store.py` (**Phases 1 and 4**).
- `docs/**` — including `docs/runbooks/data-pipeline.md:12,15,44,51,169-175,245-247`, which still say "ever-members since 2015-01-02" and still carry the copy-paste re-vendoring recipe (**Phase 5**). See `## Handoffs`.
- `db/migrations/005_fundamentals.sql` and the `ticker_cik` **table**. The `source` CHECK is already the five tier labels; it stays.
- Any database. Nothing in this phase connects to Postgres.
- `engine/src/seer_engine/universe.py` and `backfill`'s `DEFAULT_START = 2015-01-02`. **That constant is not `cik.SINCE`** — it is the *bars* scope, it is unrelated, and lowering `cik.SINCE` does not widen it. Bars stay at 2015-01-02.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/cik.py` | modify | `:43-44` — `SINCE` -> `date(2009, 1, 1)` and the comment that says what the floor now means |
| `engine/scripts/build_ticker_cik.py` | modify | `:1-23` module docstring counts; `:36` import `timedelta`; `:56` `EARLY_WINDOW_DAYS`; `:63-66` the `MANUAL` comment documents the sentinel; `:70-463` 56 literal starts -> `""`; `:475-491` `SCREEN_EXEMPT` additions; new `EARLY_EXEMPT` after it; `:685-706` `periodic_dates` + `filed_inside`; `:743-755` tier-0 honours the sentinel; `:807-825` two screens reported together |
| `engine/data/ticker_cik.csv` | regenerate | 798 rows / 795 symbols -> ≥916 rows / 913 symbols; zero rows at `2015-01-02` |
| `engine/data/SOURCES.md` | modify | `:149` Scope, `:150` Rows, `:152` sha256, `:190-209` the re-vendoring recipe, `:211-245` the hand-audit section gains a 2026-10-05 re-floor subsection |
| `engine/tests/test_cik.py` | modify | `:319-321` widen the floor assertion; four new vendored-file tests appended after `:424` |

---

## Implementation Steps

### Step 0: Pre-flight — the runtime preamble, and prove which `cik.SINCE` you are editing

**Reconciled:** the venv question is settled set-wide in the **Runtime preamble** above —
`PYTHONPATH` over main's venv, **no worktree venv**. Run that block, and the `.env.local`
export beside it, before anything else. Without it the generator would import main's
`seer_engine`, the regenerated CSV would be built against main's `cik.SINCE`, and the file would
come out silently unchanged.

The generator itself is the one script that would survive the omission —
`engine/scripts/build_ticker_cik.py:40` does `sys.path.insert(0, parents[1] / "src")`, so it
self-resolves when invoked by its worktree path. **That rescues nothing else**, pytest and
`python -m seer_engine` included, which is why the preamble is not optional.

```bash
"$SEER_PY" -c 'import seer_engine.cik as c, pathlib; print(pathlib.Path(c.__file__).resolve()); print("SINCE:", c.SINCE); print("DATA_DIR:", c.DATA_DIR)'
```

All three must name paths inside `$SEER_WT`. After step 1, `SINCE` must read `2009-01-01`.

**Impact:** nothing is written. Without this step every later step is wrong in a way that does
not announce itself.

---

### Step 1: Lower the floor

**File:** `engine/src/seer_engine/cik.py:43-44`
**Change:** `SINCE` becomes 2009-01-01, and the comment stops describing it as "the backtest
window" (it never was — bars start 2015-01-02 and that is a different constant) and starts
recording why 2009 and not 1996.

**Code:** replace lines 43–44 in full with:

```python
#: First day the map is guaranteed from, and the floor every membership start is clipped to.
#: 2009-01-01, because SEC XBRL company facts do not exist before it at any price: large
#: accelerated filers phased in from FY2009 and everyone else by FY2011, so a map reaching
#: further back would buy no fundamentals. It costs what it is worth and no more --
#: ``membership.symbols_since`` counts 1265 ever-members at 1996-01-02 against 913 here and 795
#: at the retired floor, so 1996 would mean ~470 further hand-audited rows for nothing.
#: It was ``date(2015, 1, 2)`` until 2026-10-05. That value was the first day of the *bars*
#: window borrowed as a *map* floor, and ``build_ticker_cik.spans()`` wrote it into 525 rows as
#: though it were those companies' first membership date. Because the projection in
#: ``backtest/io.py`` joins ``fundamental_facts.filed >= ticker_cik.start_date``, those 525 rows
#: discarded every fact filed before 2015 -- 181,491 of them already in the local database.
SINCE = date(2009, 1, 1)
```

**Impact:** `coverage_gaps`'s default widens, so `test_vendored_has_no_coverage_gap` now demands
cover back to 2009 — which only the regenerated CSV supplies. **Between this step and step 7 the
tests are red.** That is expected and it is why the whole of phase 2 is one commit; do not commit
here.

---

### Step 2: Teach `MANUAL` the empty-start sentinel

**File:** `engine/scripts/build_ticker_cik.py:63-66` (the comment above `MANUAL`)
**Change:** document that an empty `start` means "take it from `spans()`".

**Code:** replace lines 63–66 (the four comment lines immediately above
`MANUAL: dict[str, ...] = {`) with:

```python
# symbol -> ((cik, start, end, company_name, note), ...).
#
# ``start`` empty means "the symbol's membership start, from spans()" -- the sentinel. Use it
# whenever the filer held the ticker for the whole of the symbol's membership; write a literal
# date only when the tenure genuinely begins later than the membership does (a spinoff that
# started trading mid-membership, or the second row of a mid-membership handover). Until
# 2026-10-05 some 56 entries carried a literal "2015-01-02", which was not a tenure date at all
# but a copy of the old cik.SINCE clamp; they are sentinels now.
#
# ``end`` empty means still current, and ``end`` is ALWAYS literal. A start may be extended
# backwards; an end may never be extended forwards, because a truncated end is the entire
# defence against a recycled ticker resolving to a later holder.
#
# Hand-audited; wins over every automated tier. Every CIK below was confirmed against
# https://data.sec.gov/submissions/CIK<cik>.json.
```

**Impact:** documentation only; the mechanism lands in step 5.

---

### Step 3: Turn the 56 copied clamps into sentinels

**File:** `engine/scripts/build_ticker_cik.py:70-463` (inside `MANUAL`, which spans `:67-467`)
**Change:** every `MANUAL` start that is exactly `"2015-01-02"` becomes `""`.

**Measured, so this is mechanical and safe:** the literal string `"2015-01-02"` occurs **56
times** in the file, all of them between lines 70 and 463, and **all 56 are start cells** — none
is an `end`, a `cik`, a `company_name` or a `note` (verified by parsing `MANUAL` and searching
every other field). So:

```bash
cd "$SEER_WT"
sed -i '67,467s/, "2015-01-02", /, "", /' engine/scripts/build_ticker_cik.py
grep -c '"2015-01-02"' engine/scripts/build_ticker_cik.py   # must print 0
```

The 56 symbols this touches, exactly:

```
AABA ADS ADT AET ALTR APC BCR BRCM CA CAM CCE CELG COV CTRX CVC DISCK DNB DTV EMC FLIR GMCR
GOOG GOOGL HAR KORS KRFT LLL LLTC LMCA LMCK LO MJN MNK MON NDOI NE NFX PCL PETM PLL POM PX RTN
SE SNI SPLS STI TE TEG TWC TWX VIP WFM WFMI WYND XL
```

**The 14 that must keep their literal start, and must not be touched by anything**, with the
membership hull start they would otherwise take (measured under the new floor — identical, so
leaving them literal changes nothing and documents the handover explicitly):

| symbol | literal start | hull start at 2009 | why literal |
|---|---|---|---|
| `BATRA`, `BATRK` | 2016-04-18 | 2016-04-18 | Liberty Braves tracking stocks created 2016-04 |
| `BXLT` | 2015-07-01 | 2015-07-01 | Baxter spinoff |
| `CMCSK` | 2015-09-21 | 2015-09-21 | Comcast class K |
| `CPGX` | 2015-07-02 | 2015-07-02 | NiSource spinoff |
| `CSRA` | 2015-11-30 | 2015-11-30 | CSC spinoff |
| `DAY` | 2021-09-20 | 2021-09-20 | Ceridian/Dayforce |
| `DINO` | 2018-06-18 | 2018-06-18 | HollyFrontier |
| `EVHC` | 2016-12-02 | 2016-12-02 | AmSurg/Envision merger |
| `INFO` | 2017-06-02 | 2017-06-02 | IHS Markit |
| `LILA`, `LILAK` | 2015-07-02 | 2015-07-02 | LiLAC tracking stocks |
| `SHPG` | 2016-10-19 | 2016-10-19 | Shire ADSs |
| `WRK` | 2015-07-02 | 2015-07-02 | WestRock spinoff; its **second** row keeps 2018-11-02 |

`GOOG` and `GOOGL` each have a second row starting `2015-10-02` (the Alphabet reorg). The sed's
pattern cannot match those, and must not.

Verify the sentinel landed where it should and nowhere else:

```bash
"$SEER_PY" - <<'PY'
import ast
from pathlib import Path
src = Path("engine/scripts/build_ticker_cik.py").read_text()
s = src.index("MANUAL: dict"); e = src.index("\n}\n", s)
d = ast.literal_eval(src[src.index("{", s):e] + "\n}")
print("symbols:", len(d), "rows:", sum(len(v) for v in d.values()))
print("sentinel starts:", sum(1 for v in d.values() for r in v if r[1] == ""))
print("literal starts :", sorted({s for s, v in d.items() if v[0][1]}))
print("sentinel on a non-first row (must be []):",
      [s for s, v in d.items() for i, r in enumerate(v) if i and not r[1]])
PY
```

Expected: `symbols: 70  rows: 73`, `sentinel starts: 56`, the literal list exactly the 14 above
(plus `WRK` once), and an empty last line.

**Impact:** `MANUAL` alone; the generator still ignores the sentinel until step 5.

---

### Step 4: One `periodic_dates` fetch, two screens

**File:** `engine/scripts/build_ticker_cik.py:685-706` (replacing `filed_inside` in full) and
`:36`, `:56`

**Why a second screen exists at all.** The existing screen asks *"did this CIK file a periodic
report somewhere inside the span?"*. Moving 541 starts backwards cannot make that question fail:
a row whose start slides from 2015 to 2009 still has its 2015+ filings inside the span, so the
screen passes it in silence even when the filer did not hold the ticker — or did not exist — in
2009. That is not a hypothetical. Measured against the shipped file and the new hulls:

| symbol | shipped row | new span start | the company that actually held the ticker then |
|---|---|---|---|
| `Q` | `0002058873` Qnity Electronics, 2025-11-03 | 2009-01-01 | Qwest Communications International, until 2011-04-01 |
| `DELL` | `0001571996` Dell Technologies, 2024-09-23 | 2009-01-01 | Dell Inc., until 2013-10-29 |
| `CEG` | `0001868275` Constellation Energy Corp, 2022-02-02 | 2009-01-01 | Constellation Energy Group, until 2012-03-13 |
| `MRVL` | `0001835632` Marvell Technology, Inc., 2020-12-21 | 2009-01-01 | Marvell Technology Group Ltd., until 2012-12-24 |
| `SNDK` | `0002023554` Sandisk Corp, 2015-01-02 | 2009-01-01 | SanDisk Corp (the 2016-acquired one) — **already wrong in the shipped file** |
| `DD`, `DOW`, `IR`, `LBTYA` | the post-2017 successor entity, 2015-01-02 | 2009-01-01 | the pre-merger predecessor |

Every one of these would ship silently. What they have in common is the one thing the submissions
JSON can answer for free: **the CIK filed no periodic report anywhere near the start of the span
it claims.** So the second screen asks *"did this CIK file a periodic report in the first 450
days of the span?"*. A quarterly filer answers with 3–5; an annual-only foreign private issuer
(20-F) with 1; an entity that did not exist yet, with none. Where the span is shorter than 450
days the question is identical to the first screen's and is skipped, so short spans produce no
new flags.

It costs **no extra network**: both screens read the same `submissions-<cik>.json`, which the
fetcher already caches on disk and which `_PERIODIC_CACHE` now also memoises in process.

**Code:** at `:36`, replace

```python
from datetime import date
```

with

```python
from datetime import date, timedelta
```

At `:56`, immediately after the `PERIODIC_FORMS` line, add:

```python
#: The second screen's window. A row's CIK must have filed a periodic report within this many
#: days of the span's start, not merely somewhere inside it. A quarterly filer files 3-5 in the
#: window and an annual-only foreign private issuer (20-F) files 1, so a zero means the filer
#: was not reporting when the span opens -- the signature of a start extended back past a
#: handover, which the first screen cannot see because the later filings still fall inside.
EARLY_WINDOW_DAYS = 450
```

Replace lines 685–706 — the whole of `filed_inside`, from its `def` line through `return count` —
with:

```python
#: cik -> every periodic filingDate it has, ascending. Filled by periodic_dates; the submissions
#: JSON is parsed once per run however many screens ask about it.
_PERIODIC_CACHE: dict[str, tuple[str, ...]] = {}


def periodic_dates(fetcher: SecFetcher, cik: str) -> tuple[str, ...]:
    """Every periodic-report ``filingDate`` ``cik`` has on EDGAR, ascending ISO strings.

    The ``recent`` block holds only the newest 1000 filings; everything older lives in the
    overflow files the submissions JSON lists under ``filings.files``, and a long-lived filer's
    2009 reports are always in there. Both are read.
    """
    cached = _PERIODIC_CACHE.get(cik)
    if cached is not None:
        return cached
    data = fetcher.json(SUBMISSIONS_URL.format(cik=cik), f"submissions-{cik}.json")
    found: list[str] = []

    def take(block: dict[str, Any]) -> None:
        for form, filed in zip(block.get("form", []), block.get("filingDate", [])):
            if form in PERIODIC_FORMS:
                found.append(filed)

    take(data.get("filings", {}).get("recent", {}))
    for extra in data.get("filings", {}).get("files", []):
        take(fetcher.json(
            "https://data.sec.gov/submissions/" + extra["name"], f"submissions-{extra['name']}"
        ))
    dates = tuple(sorted(found))
    _PERIODIC_CACHE[cik] = dates
    return dates


def filed_inside(fetcher: SecFetcher, cik: str, start: date, end: date | None) -> int:
    """How many periodic reports ``cik`` filed with filingDate in ``[start, end)``."""
    lo, hi = start.isoformat(), (end.isoformat() if end else "9999-12-31")
    return sum(1 for filed in periodic_dates(fetcher, cik) if lo <= filed < hi)
```

**Impact:** `filed_inside` keeps its signature and its meaning, so the first screen behaves
exactly as before. Nothing calls `periodic_dates` yet until step 6.

---

### Step 5: Tier 0 honours the sentinel

**File:** `engine/scripts/build_ticker_cik.py:743-755`
**Change:** an empty `start` is filled from `span[symbol]`; a sentinel on a non-first row is a
build error, because only a symbol's *first* tenure can begin when its membership does.

**Code:** replace lines 743–755 — from the `# tier 0 -- manual` comment through
`counts["manual"] += 1` — with:

```python
    # tier 0 -- manual
    for symbol, entries in MANUAL.items():
        if symbol not in span:
            raise BuildError(f"MANUAL has {symbol}, which is not an ever-member since {SINCE}")
        for position, (cik, start, end, name, note) in enumerate(entries):
            if not start and position:
                raise BuildError(
                    f"MANUAL {symbol}: only the first row may leave start empty; row "
                    f"{position + 1} is a handover and must carry its literal start date"
                )
            rows.append(
                {
                    "symbol": symbol,
                    "cik": cik,
                    "start_date": start or span[symbol][0].isoformat(),
                    "end_date": end,
                    "company_name": name,
                    "source": "manual",
                    "note": note,
                }
            )
        resolved.add(symbol)
        counts["manual"] += 1
```

**Impact:** the 56 sentinel symbols now inherit the same hull start that tiers 1–4 get from
`_row(..., span)` at `:839`. Measured, the starts they will take:

- 41 of the 56 take **2009-01-01** (the floor).
- The other 15 take their real, later first-membership date: `ADS` 2013-12-23, `ADT`
  2012-10-02, `CTRX` 2012-12-24, `CVC` 2010-12-20, `GMCR` 2011-05-27, `KORS` 2013-11-13, `KRFT`
  2012-10-02, `LMCA` 2012-12-24, `MJN` 2009-12-21, `MNK` 2014-08-19, `NFX` 2010-12-20, `PETM`
  2012-10-05, `TWC` 2009-03-30, `VIP` 2013-10-29, `WFMI` 2010-12-20.
- **None** takes 2015-01-02, because no symbol in the universe has 2015-01-02 as its real first
  membership date.

Each of those 56 widened `manual` rows is a claim that the hand-audited CIK held the ticker back
to that date. Step 7's audit loop is where that claim is checked; the second screen is what makes
checking it tractable.

---

### Step 6: Run both screens and report them together

**File:** `engine/scripts/build_ticker_cik.py:807-825`
**Change:** collect both screens' findings in one pass and print both before returning 1, so the
operator sees the whole workload per run instead of discovering the second list only after
clearing the first.

**Code:** replace lines 807–825 — from the `# the screen` comment through the `return 1` that
follows the `SCREEN` block — with:

```python
    # the screens. Two questions, one submissions JSON per CIK:
    #   1. did this filer file a periodic report anywhere inside the span?  (wrong company)
    #   2. did it file one near the START of the span?                      (start extended back
    #      past a handover -- invisible to question 1, because the later filings still count)
    suspect: list[str] = []
    late: list[str] = []
    for row in rows:
        if row["cik"] == NO_FILER:
            continue  # no filer to screen; the NONE row is itself the audited answer
        start = date.fromisoformat(row["start_date"])
        end = date.fromisoformat(row["end_date"]) if row["end_date"] else None
        if row["symbol"] not in SCREEN_EXEMPT:
            if filed_inside(fetcher, row["cik"], start, end) == 0:
                suspect.append(f"{row['symbol']} -> {row['cik']} {row['company_name']}")
        if row["symbol"] in EARLY_EXEMPT:
            continue  # hand-verified silence at the span's open; see EARLY_EXEMPT
        window_end = start + timedelta(days=EARLY_WINDOW_DAYS)
        if end is not None and end <= window_end:
            continue  # the span is shorter than the window; question 1 already asked this
        if filed_inside(fetcher, row["cik"], start, window_end) == 0:
            known = periodic_dates(fetcher, row["cik"])
            first = known[0] if known else "never"
            late.append(
                f"{row['symbol']} -> {row['cik']} {row['company_name']}: span opens "
                f"{start}, first periodic filing {first}"
            )
    if suspect:
        log("")
        log(f"SCREEN ({len(suspect)}) -- no periodic filing inside the span; wrong company, a "
            f"filer change mid-span, or a genuinely silent filer. Resolve each in MANUAL:")
        for line in suspect:
            log(f"  {line}")
    if late:
        log("")
        log(f"EARLY ({len(late)}) -- no periodic filing in the first {EARLY_WINDOW_DAYS} days "
            f"of the span, so the start reaches back past this filer. Split the tenure into two "
            f"dated MANUAL rows, or exempt it in EARLY_EXEMPT with the reason:")
        for line in late:
            log(f"  {line}")
    if suspect or late:
        return 1
```

**Note the deliberate change in shape:** a symbol in `SCREEN_EXEMPT` is no longer skipped
wholesale — it is still asked question 2, because the eleven recorded reasons are about a
*short or just-opened* span, not about a filer that did not exist. Two of them (`FRC`, `SBNY`)
*do* answer "never" and are therefore pre-seeded into `EARLY_EXEMPT` in step 7.

**Impact:** the generator now refuses to write a file in which any row claims a tenure beginning
before its filer was reporting, unless a human has written down why.

---

### Step 7: The audit loop — the bulk of this phase

This is the part that cannot be written in advance. What follows is the loop, the decision rule,
and the exact shape of every edit it produces.

#### 7a. Seed `EARLY_EXEMPT` before the first run

**File:** `engine/scripts/build_ticker_cik.py`, immediately after `SCREEN_EXEMPT`'s closing
brace at `:491`.

**Code:**

```python
# Symbols whose absence of a periodic filing in the FIRST EARLY_WINDOW_DAYS of the span was
# hand-verified and explained. Separate from SCREEN_EXEMPT because the questions differ: that
# table waives "filed nothing anywhere in the span", this one waives "filed nothing at the span's
# open". A symbol here is still subject to SCREEN_EXEMPT's screen and vice versa. Every entry
# records what was checked against data.sec.gov/submissions. Add; never remove, never weaken.
EARLY_EXEMPT: dict[str, str] = {
    "FRC": "First Republic Bank is a bank, not a holding company: it filed its periodic reports "
           "with the FDIC under Exchange Act s12(i), so EDGAR holds none at any date in the span",
    "SBNY": "Signature Bank is a bank, not a holding company: periodic reports went to the FDIC "
            "under Exchange Act s12(i), not EDGAR, for the whole span",
}
```

#### 7b. The loop

```bash
cd "$SEER_WT"
"$SEER_PY" engine/scripts/build_ticker_cik.py \
    --out engine/data/ticker_cik.csv --cache engine/.cache/cik
```

Exit 1 with one or more of `UNRESOLVED`, `SCREEN`, `EARLY` → resolve every line → re-run. Exit 0
→ the file is written. Nothing is written on a non-zero exit, so the loop is safe to interrupt.

**Cost, measured.** `engine/.cache/cik` does not exist, so pass 1 fetches everything:
`company_tickers.json`, `cik-lookup-data.txt` (39 MB), one browse-edgar call per symbol tiers 0–1
did not resolve (expect ~110 of the 118 newcomers), up to 50 Massive pages at 12.5 s each
(~24 pages ≈ 5 min) and one submissions JSON per screened CIK (~900 at 0.15 s ≈ 2.5 min, plus
overflow files for long-lived filers — and in 2009 nearly all of them are long-lived). **Budget
20–40 minutes for pass 1.** Later passes re-read the cache and re-parse it; expect under a
minute each, plus one fetch per newly named CIK. Everything is free. Delete nothing from the
cache between passes.

#### 7c. The decision rule

For each flagged line, open `https://data.sec.gov/submissions/CIK<cik>.json` and read `name`,
`formerNames`, `tickers`, and the first and last periodic `filingDate`. Then exactly one of:

1. **The filer is right and held the ticker for the whole span; it simply filed nothing in the
   flagged window.** Three reasons recur and only these three have ever been accepted: a *bank*
   rather than a bank holding company files with the FDIC under Exchange Act §12(i) and never
   with EDGAR; a *span shorter than the next filing's due date*; a *member whose span opened
   weeks ago* with nothing yet due. → add the symbol to `SCREEN_EXEMPT` (flagged by `SCREEN`) or
   `EARLY_EXEMPT` (flagged by `EARLY`), with a one-sentence reason naming the evidence. Copy the
   existing entries' voice exactly — they say *what* was checked, never "verified":

   ```python
       "SWY": "Safeway Inc; 25-day span, acquired by Albertsons 2015-01-30 before the FY2014 10-K",
   ```

2. **A different company held the ticker earlier in the span.** → **split the tenure into two
   `MANUAL` rows.** The earlier row's `end` must equal the later row's `start` exactly:
   `cik._check_intervals` rejects any overlap, and `coverage_gaps` rejects any hole. The later
   row's `end` is whatever it already was and is never pushed forward.

   ```python
       "Q": (
           ("0001037949", "", "2011-04-01", "QWEST COMMUNICATIONS INTERNATIONAL INC",
            "Qwest held Q until CenturyLink closed the acquisition 2011-04-01; the ticker was "
            "reissued to Qnity Electronics at the 2025 DuPont spinoff, and tier 1 answers with "
            "that one, whose filings start 2025 -- which is why the EARLY screen caught it"),
           ("0002058873", "2025-11-03", "", "Qnity Electronics, Inc.",
            "the 2025 DuPont electronics spinoff; its first periodic filing postdates the "
            "earlier tenure by 14 years, so the two rows cannot overlap"),
       ),
   ```

   The CIKs above are the ones to check first, not ones to paste on trust: confirm each against
   the submissions JSON before writing it, and record in `note` what the JSON said.

3. **The automated tier picked the wrong company outright** — a namesake, a subsidiary, a
   defunct same-name entity, a `fuzzy` match. → one `MANUAL` row with the right CIK, `start`
   **empty** (the sentinel) unless the tenure genuinely begins later, and a `note` naming the
   wrong CIK that was picked and why it is wrong. This is the voice of the existing entries:

   ```python
       "LLTC": (
           ("0000791907", "", "2017-03-13", "LINEAR TECHNOLOGY CORP /CA/",
            "name match picked 0001160656 CLEAR TECHNOLOGY INC, an unrelated company with 6 "
            "filings ending 2007; Linear Technology is CIK 0000791907, acquired by Analog "
            "Devices 2017-03-10; 9 periodic filings inside the span"),
       ),
   ```

4. **`UNRESOLVED`: no tier answered at all.** Find the CIK by hand — EDGAR full-text search on
   the company name, or `cik-lookup-data.txt` which is already in the cache — then write a
   `MANUAL` entry as in (3). The seven bankruptcy-era `Q` suffixes (`ANRZQ`, `BTUUQ`, `CITGQ`,
   `EKDKQ`, `MTLQQ`, `RSHCQ`, `SUNEQ`) are the pink-sheet tickers of Alpha Natural Resources,
   Peabody Energy, CIT Group, Eastman Kodak, Motors Liquidation (old GM), RadioShack and SunEdison
   — the filer is the *company*, under the ticker it had before the `Q` was appended, and the
   `note` must say so.

5. **Nothing is wrong.** A tier row whose CIK held the ticker for the whole span and which both
   screens pass needs no entry anywhere. Adding a `MANUAL` row "to be safe" is the wrong move: it
   freezes a value that `spans()` would otherwise keep correct as the membership CSVs are
   re-vendored.

**Never**, under any of the five: push an `end` forward, merge two tenures into one row, write a
`note` that does not say what was checked, remove a `SCREEN_EXEMPT` entry, or weaken one.

#### 7d. The backstop list the screens cannot produce

The `EARLY` screen catches a handover to a filer that *did not exist* at the span's open. It
cannot catch a handover between two filers that were both reporting throughout — ticker X held by
A until 2012 and by B from 2016, both long-lived. The membership data names those candidates:
they are the symbols whose hull now stretches across a multi-year gap in membership. Produce the
list once, before the first run, and hand-audit every entry whose two stretches might plausibly
be two different companies:

```bash
cd /home/miftah/.worktrees/seer/fundamental-panel-coverage
"$SEER_PY" - <<'PY'
from collections import defaultdict
from datetime import date
from seer_engine import membership

FLOOR = date(2009, 1, 1)
per: dict[str, list[tuple[date, date]]] = defaultdict(list)
for iv in membership.compute_universe(membership.DATA_DIR):
    end = iv.end_date or date(9999, 12, 31)
    if end <= FLOOR:
        continue
    per[iv.symbol].append((max(iv.start_date, FLOOR), end))

out = []
for symbol, spans in per.items():
    spans.sort()
    merged: list[list[date]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    for i in range(1, len(merged)):
        gap = (merged[i][0] - merged[i - 1][1]).days
        if gap > 365:
            out.append((gap, symbol, merged[i - 1][1], merged[i][0]))
for gap, symbol, left, right in sorted(out, reverse=True):
    print(f"{symbol:8s} out of every index {left} .. {right}  ({gap} days)")
print(f"\n{len(out)} hull stretches over a membership gap longer than a year")
PY
```

Measured today it prints **37** lines, led by `CIEN` (5894 days), `Q` (5330), `FLEX` (4928),
`STLD` (4749), `DELL` (3982), `CEG` (3613), `SNDK` (3487), `JBL` (3330), `MRVL` (2919), `CCEP`
(2757), `TER` (2464), `LDOS` (2146), `FSLR` (2100), `HOLX` (1927), `JBHT` (1654). Most are one
company throughout (`CIEN` is Ciena, `FLEX` is Flextronics renamed Flex on the same CIK, `STLD`
is Steel Dynamics, `JBL` is Jabil, `TER` is Teradyne, `JBHT` is J.B. Hunt) and need no entry; the
ones already named in step 4's table are not. Audit all 37; `EARLY` will have flagged the
easy half.

#### 7e. The 118 newcomers

Listed in full in the analysis document's Measurements section and reproduced here with the spans
`spans()` will give them, because the span is what each audit has to confirm:

```
ACAS  2009-01-01..2009-03-04   ACS   2009-01-01..2010-02-08   AKS   2009-01-01..2011-12-19
ANF   2009-01-01..2013-12-23   ANRZQ 2011-06-02..2012-10-02   APOL  2009-01-01..2013-07-01
ATGE  2009-06-09..2012-10-01   AYE   2009-01-01..2011-02-28   BDK   2009-01-01..2010-03-15
BEAM  2009-01-01..2014-05-01   BIG   2009-01-01..2013-02-14   BJS   2009-01-01..2010-04-29
BMC   2009-01-01..2013-09-11   BMS   2009-01-01..2014-12-05   BNI   2009-01-01..2010-02-16
BTUUQ 2009-01-01..2014-09-22   CBE   2009-01-01..2012-12-03   CEPH  2009-01-01..2011-10-14
CITGQ 2009-01-01..2009-07-27   CLF   2009-12-21..2014-04-02   CPWR  2009-01-01..2012-01-03
CTX   2009-01-01..2009-08-19   CVG   2009-01-01..2009-12-21   CVH   2009-01-01..2013-05-07
DDR   2009-01-01..2009-03-30   DF    2009-01-01..2013-05-24   DYN   2009-01-01..2009-12-21
EKDKQ 2009-01-01..2010-12-20   EP    2009-01-01..2012-05-25   EQ    2009-01-01..2009-07-01
FHN   2009-01-01..2013-06-24   FII   2009-01-01..2013-01-02   FMCN  2009-01-01..2009-01-20
FRX   2009-01-01..2014-07-01   FWLT  2009-01-01..2010-12-20   GENZ  2009-01-01..2011-04-04
GHC   2009-01-01..2014-09-22   GOLD  2011-12-19..2013-11-18   GR    2009-01-01..2012-07-27
HANS  2009-01-01..2012-01-05   HNZ   2009-01-01..2013-06-07   HSH   2009-01-01..2012-06-29
IACI  2009-01-01..2009-12-21   IGT   2009-01-01..2014-06-20   INFY  2009-01-01..2012-12-12
ITT   2009-01-01..2011-11-01   JAVA  2009-01-01..2010-01-27   JCP   2009-01-01..2013-12-02
JNS   2009-01-01..2011-11-23   JNY   2009-01-01..2009-03-04   JOYG  2009-01-01..2011-12-06
KBH   2009-01-01..2009-12-21   KFT   2012-07-23..2012-10-02   KG    2009-01-01..2010-12-20
LIFE  2009-01-01..2014-01-24   LOGI  2009-01-01..2010-12-20   LSI   2009-01-01..2014-05-07
LXK   2009-01-01..2012-10-01   MBI   2009-01-01..2009-12-21   MDP   2009-01-01..2011-01-04
MEE   2009-01-01..2011-06-02   MER   2009-01-01..2009-01-02   MFE   2009-01-01..2011-03-01
MHS   2009-01-01..2012-04-02   MI    2009-01-01..2011-07-06   MICC  2009-01-01..2011-05-27
MIL   2009-01-01..2010-07-15   MMI   2011-01-04..2012-05-22   MOLX  2009-01-01..2013-12-09
MTLQQ 2009-01-01..2009-06-03   MTW   2009-01-01..2009-09-01   MWW   2009-01-01..2011-12-19
NCC   2009-01-01..2009-01-02   NIHD  2009-01-01..2011-12-19   NOVL  2009-01-01..2011-04-28
NSM   2009-01-01..2011-09-26   NUAN  2011-12-19..2013-12-23   NVLS  2009-01-01..2012-06-05
NYT   2009-01-01..2010-12-20   NYX   2009-01-01..2013-11-13   ODP   2009-01-01..2010-12-20
PBG   2009-01-01..2010-03-01   PGN   2009-01-01..2012-07-02   PPDI  2009-01-01..2009-12-21
PTV   2009-01-01..2010-11-17   QGEN  2009-12-21..2011-12-19   QLGC  2009-01-01..2011-01-18
RDC   2009-01-01..2014-08-19   RIMM  2009-01-01..2012-12-24   ROH   2009-01-01..2009-04-02
RRD   2009-01-01..2012-12-12   RSHCQ 2009-01-01..2011-07-01   RX    2009-01-01..2010-02-26
RYAAY 2009-01-01..2009-12-21   S     2009-01-01..2013-07-09   SGP   2009-01-01..2009-11-04
SHLD  2009-01-01..2013-12-23   SII   2009-01-01..2010-08-27   SLM   2009-01-01..2014-05-01
SOV   2009-01-01..2009-01-30   STR   2009-01-01..2010-07-01   STRZA 2013-01-15..2013-03-18
SUN   2009-01-01..2012-10-05   SUNEQ 2009-01-01..2011-12-19   SVU   2009-01-01..2012-05-01
TEVA  2009-01-01..2012-05-30   TIE   2009-01-01..2012-12-24   TLAB  2009-01-01..2011-12-21
UST   2009-01-01..2009-01-06   VIAV  2009-01-01..2013-12-23   VMED  2009-12-21..2013-06-05
WB    2009-01-01..2009-01-02   WCRX  2009-01-01..2012-12-24   WFT   2009-01-01..2009-02-26
WPX   2012-01-03..2014-03-24   WYE   2009-01-01..2009-10-16   X     2009-01-01..2014-07-02
XTO   2009-01-01..2010-06-28
```

Three traps in that list worth naming before they cost an hour each:

- **`GOLD` 2011-12-19..2013-11-18** is Randgold Resources in that window. The ticker is Barrick
  Gold today and tier 1 will answer with Barrick (`0000756894`), whose filings cover the span —
  so **the first screen will pass it and the second will too**. It is a recycled ticker that only
  a human catches. Resolve it as case (3), a `MANUAL` row with Randgold's CIK.
- **`S` 2009-01-01..2013-07-09** is Sprint Nextel. The ticker later belonged to SentinelOne.
  Same shape as `GOLD`.
- **`EQ`, `MER`, `NCC`, `WB`, `UST`, `SOV`** have spans of days (the 2008–09 crisis closings).
  Their rows will be flagged by the first screen for having no filing in a 2–30 day window and
  belong in `SCREEN_EXEMPT` as case (1), short span — not in `MANUAL`.

#### 7f. What "done" looks like for step 7

The generator exits 0 and prints its two summary lines. Record them: they are the numbers
`SOURCES.md` needs in step 9.

**Impact:** `engine/data/ticker_cik.csv` is rewritten. This is the phase's product.

---

### Step 8: Assert the new invariants in the test suite

**File:** `engine/tests/test_cik.py`

**8a — widen the size floor.** Replace lines 319–321:

```python
def test_vendored_file_loads_and_is_big_enough(vendored_index, ever_members):
    assert len(ever_members) >= 780
    assert len(vendored_index) == len(ever_members)
```

with:

```python
def test_vendored_file_loads_and_is_big_enough(vendored_index, ever_members):
    """913 ever-members at the 2009 floor, measured 2026-10-05; 795 at the retired 2015 one."""
    assert len(ever_members) >= 900
    assert len(vendored_index) == len(ever_members)
```

**8b — four new vendored-file tests.** Append to the end of the file, after
`test_vendored_notes_are_present_where_required` (`:417-424`):

```python
def test_vendored_floor_is_2009_and_no_row_precedes_it():
    """R1: the map's floor is the first year SEC XBRL company facts exist at all."""
    assert c.SINCE == D("2009-01-01")


def test_vendored_no_row_starts_before_the_floor(vendored_index):
    early = [
        (row.symbol, row.start_date)
        for group in vendored_index.values()
        for row in group
        if row.start_date < c.SINCE
    ]
    assert early == []


def test_vendored_carries_no_row_at_the_retired_2015_clamp(vendored_index):
    """The old cik.SINCE wrote 525 rows claiming a start that was not the symbol's.

    Measured 2026-10-05: no symbol in the universe has 2015-01-02 as its real first-membership
    date, so after Fix A the date must not appear as a start_date at all. If a future
    re-vendoring produces a genuine 2015-01-02 handover, name it here rather than deleting the
    test -- the point is that the date is never again a default.
    """
    clamped = sorted(
        row.symbol
        for group in vendored_index.values()
        for row in group
        if row.start_date == D("2015-01-02")
    )
    assert clamped == []


def test_vendored_has_no_fuzzy_row(vendored_index):
    """SOURCES.md requires it. HAR is why: difflib matched 'Harman International Industries'
    to 'AMERICAN INTERNATIONAL INDUSTRIES' (0001073146), which filed 4 periodic reports inside
    the span and so passed the screen. The screen is a net, not a gate.
    """
    fuzzy = sorted(
        row.symbol
        for group in vendored_index.values()
        for row in group
        if row.source == "fuzzy"
    )
    assert fuzzy == []


def test_vendored_none_row_is_ndoi_and_it_is_alone(vendored_index):
    """NDOI is a phantom in the Wikipedia-derived ndx_history.csv and the file's only NONE."""
    none_rows = sorted(
        row.symbol
        for group in vendored_index.values()
        for row in group
        if row.cik is None
    )
    assert none_rows == ["NDOI"]
    assert len(vendored_index["NDOI"]) == 1
```

**Impact:** five assertions that would have caught the clamp, the `fuzzy` miss and the `NONE`
drift. `test_vendored_has_no_coverage_gap`, `RECYCLED`, `SPOT_CHECKS`, `SHARE_CLASSES`, the
WestRock test and the Alphabet test are **not modified** and must pass with their existing
expected values — that is the phase's real gate.

---

### Step 9: Update the generator's docstring and `SOURCES.md`

**9a — `engine/scripts/build_ticker_cik.py:1-23`.** Replace the module docstring in full. The
three bracketed values are filled from the generator's own last two log lines; everything else is
known now:

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

Measured 2026-10-05 over the 913 ever-members since cik.SINCE = 2009-01-01: MANUAL covers
[N_MANUAL] symbols, tier 1 resolves [N_CURRENT] of the rest, tier 2 a further [N_EDGAR], leaving
[N_NAME] for tiers 3-4.

A ticker alone never identifies a company: tiers 1-2 answer with whoever holds the ticker TODAY,
and tiers 1-4 take their start from spans(), which clips membership to [SINCE, ...). Two screens
guard the result, and neither is a gate:

  SCREEN  a candidate must have filed a periodic report somewhere inside the symbol's span. It
          rejected the wrong answers for MON, PLL and ALTR but NOT for LLL, DTV or HAR, so the
          six recycled tickers and the one fuzzy match stay in MANUAL permanently.
  EARLY   a candidate must also have filed one within EARLY_WINDOW_DAYS of the span's START.
          Lowering SINCE from 2015-01-02 to 2009-01-01 moved 541 starts backwards, and SCREEN
          cannot see a start that reaches back past a handover because the later filings still
          fall inside the span. EARLY can, whenever the earlier holder's successor did not exist
          yet -- Q, DELL, CEG, MRVL, SNDK among them. It still cannot see a handover between two
          filers that both reported throughout; GOLD (Randgold, now Barrick) and S (Sprint
          Nextel, now SentinelOne) are that case and are in MANUAL for it.
"""
```

**9b — `engine/data/SOURCES.md`.** Four edits.

Line 149, the Scope row:

```markdown
| Scope | every S&P 500 / Nasdaq-100 ever-member on or after 2009-01-01 — `membership.symbols_since(membership.compute_universe(), date(2009, 1, 1))`, **913** symbols on 2026-10-05. The floor is `seer_engine.cik.SINCE`; it was 2015-01-02 until 2026-10-05, which clamped 525 starts to a date that was not theirs. |
```

Line 150, the Rows row — fill from the generator's `wrote …` and tier-count lines:

```markdown
| Rows | [N_ROWS] rows covering 913 symbols (`manual` [N_MANUAL], `current` [N_CURRENT], `edgar` [N_EDGAR], `exact` [N_EXACT], `fuzzy` 0); 540 rows start at the 2009-01-01 floor and **none** starts at 2015-01-02 |
```

Line 152, the sha256 row — `sha256sum engine/data/ticker_cik.csv`:

```markdown
| sha256 | `[NEW_SHA256]` |
```

Lines 190–209, the `### Re-vendoring` section — replace its two prose paragraphs (from
"Network artifacts are cached" through "come from the name-matching path") with:

```markdown
Network artifacts are cached under `--cache` (gitignored), so re-runs after editing `MANUAL`
cost nothing; delete the cache to refetch. From a cold cache the first pass takes 20–40 minutes,
almost all of it SEC's 10 req/s fair-access pacing and Massive's free-tier 5 calls/min.

The script exits 1 and writes nothing when any of three lists is non-empty:

- **`UNRESOLVED`** — no tier answered. Find the CIK by hand and add a `MANUAL` entry.
- **`SCREEN`** — the candidate filed no periodic report anywhere inside the span. Wrong company,
  a filer change mid-span, or a genuinely silent filer.
- **`EARLY`** — the candidate filed none within `EARLY_WINDOW_DAYS` (450) of the span's **start**,
  so the start reaches back past this filer. Split the tenure into two dated `MANUAL` rows, or
  exempt it in `EARLY_EXEMPT` with the reason.

Resolve each against `https://data.sec.gov/submissions/CIK<cik>.json` and record what you read in
the row's `note` — that column is the audit trail, and
`awk -F, '$6=="manual" || $6=="fuzzy"' ticker_cik.csv` is the review. In a `MANUAL` entry an
**empty `start` means "the symbol's membership start, from `spans()`"**; write a literal date only
when the tenure genuinely begins later. An `end` is always literal, and **an end is never pushed
forward** — a truncated end is the whole defence against a recycled ticker resolving to a later
holder. Then update the Scope, Rows and sha256 lines above and run
`"$SEER_PY" -m pytest engine/tests/test_cik.py -q`.
```

Finally, append to the end of the `ticker_cik.csv` section (after the `NDOI` paragraph) a short
subsection recording this re-vendoring:

```markdown
### The 2026-10-05 re-floor, from 2015-01-02 to 2009-01-01

`cik.SINCE` was the first day of the **bars** window borrowed as a **map** floor. `spans()`
clips every membership start to it, so 525 of the 798 shipped rows claimed a `start_date` of
2015-01-02 that was not those companies' first membership date — and because the projection in
`backtest/io.py` joins `fundamental_facts.filed >= ticker_cik.start_date`, the map discarded
every fact filed before 2015, 181,491 of which were already stored. The floor is now 2009-01-01,
the first year SEC XBRL company facts exist at all; 1996 was rejected because no fundamentals
exist there at any price and it would cost ~470 further hand audits (1265 ever-members against
913).

Measured: 913 symbols (up from 795), 118 entirely new, **0 lost**, 541 existing starts moved
earlier, 540 rows now sitting at the floor, and **0 rows at 2015-01-02** — no symbol in the
universe has that as its real first-membership date, which is what made the clamp visible.

Moving starts backwards creates a hazard the old file did not have: a start that reaches back
past a handover attributes the *later* filer's fundamentals to the *earlier* company's prices.
The `SCREEN` net cannot see it, because the later filings still fall inside the span. That is
what `EARLY_WINDOW_DAYS` and the `EARLY` screen are for, and what the `EARLY_EXEMPT` table
records exceptions to. `EARLY` still cannot see a handover between two filers that both reported
throughout — `GOLD` (Randgold in 2011–2013, Barrick's ticker today) and `S` (Sprint Nextel, now
SentinelOne) are that case and live in `MANUAL`.
```

**Impact:** the vendored data and its documentation agree again.

---

## Verification

**Build:** nothing to compile. `"$SEER_PY" -m compileall -q engine/scripts/build_ticker_cik.py engine/src/seer_engine/cik.py`

**Generator:** exit 0, with no `UNRESOLVED`, `SCREEN` or `EARLY` line.

```bash
cd "$SEER_WT"
"$SEER_PY" engine/scripts/build_ticker_cik.py \
    --out engine/data/ticker_cik.csv --cache engine/.cache/cik
echo "exit $?"
```

**The direct check the phase is graded on:**

```bash
"$SEER_PY" - <<'PY'
from collections import Counter
from datetime import date
from seer_engine import cik, membership

index = cik.load_index()
rows = [r for g in index.values() for r in g]
print("SINCE                :", cik.SINCE)
print("symbols              :", len(index))
print("rows                 :", len(rows))
gaps = cik.coverage_gaps(index, membership.compute_universe(membership.DATA_DIR))
print("coverage gaps        :", len(gaps), gaps[:3])
print("rows at 2015-01-02   :", sum(1 for r in rows if r.start_date == date(2015, 1, 2)))
print("rows at the floor    :", sum(1 for r in rows if r.start_date == cik.SINCE))
print("rows before the floor:", sum(1 for r in rows if r.start_date < cik.SINCE))
print("fuzzy rows           :", sum(1 for r in rows if r.source == "fuzzy"))
print("NONE rows            :", [r.symbol for r in rows if r.cik is None])
print("sources              :", dict(Counter(r.source for r in rows)))
print("K on 2020-01-02      :", cik.resolve("K", date(2020, 1, 2), index))
PY
```

Required output: `SINCE 2009-01-01`; `symbols 913`; `rows` ≥ 916; `coverage gaps 0 ()`; `rows at
2015-01-02 0`; `rows at the floor 540`; `rows before the floor 0`; `fuzzy rows 0`; `NONE rows
['NDOI']`; `sources` keys a subset of the five labels; `K` `0000055067`.

**Tests:** `"$SEER_PY" -m pytest engine/tests -q`

**The test delta, not an absolute.** This phase adds **5** tests (step 8b), modifies one in
place (step 8a) and removes none. Against the `2dad9ff` baseline of 2216 passed / 332 skipped
that is **2221 passed, 332 skipped** *when this phase runs first*; in a swarm the inherited
count depends on what has already merged, so report `+5` and the fact that no existing test
changed its result. The binding rule is invariant 1: the passing count may only go up.

The DB tests stay skipped — this phase touches no database. If
`PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres` is exported they must pass too;
`conftest.py` gives each one a throwaway schema `t_<hex>` and never touches `public`.

Narrower while iterating: `"$SEER_PY" -m pytest engine/tests/test_cik.py -q`.

**Lint:** `"$SEER_PY" -m ruff check engine/scripts/build_ticker_cik.py engine/src/seer_engine/cik.py engine/tests/test_cik.py` (CI selects `E9,F` only).

**Manual check:** read the diff of `engine/data/ticker_cik.csv` for the rows your audits touched,
and read every `note` you wrote. `git diff --stat engine/data/ticker_cik.csv` should show a large
rewrite; `git diff engine/data/ticker_cik.csv | grep '^-' | grep -c '2015-01-02'` should be
roughly 525.

**Exit criteria:**

1. `cik.SINCE == date(2009, 1, 1)`.
2. `cik.load_index()` yields **913** symbols and
   `cik.coverage_gaps(index, membership.compute_universe(membership.DATA_DIR))` is **empty**.
3. Zero rows with `source == "fuzzy"`; zero rows with `start_date == 2015-01-02`; zero rows
   before the floor; `NDOI` the only `NONE` and alone.
4. `RECYCLED`, `SPOT_CHECKS`, `SHARE_CLASSES`, the WestRock test and the Alphabet test pass
   **with their existing expected values, unmodified**.
5. The generator exits 0 from a clean run, and every `SCREEN_EXEMPT` / `EARLY_EXEMPT` entry
   carries a reason naming what was checked.
6. `SOURCES.md`'s Scope, Rows and sha256 match the file on disk.
7. `"$SEER_PY" -m pytest engine/tests -q` is green with **+5** collected tests and no existing
   test changed; 2221 passed / 332 skipped when this phase runs first off `2dad9ff`.

---

## Handoffs

- **Phase 3 (R2)** owns both ingest floors. This phase does **not** touch
  `commands/fundamentals.py:63,67`, its module docstring at `:4`, or the `--since*` help strings
  at `:210-224`. Phase 3 consumes the regenerated CSV; without it a pre-2015 filer cannot be
  resolved and `--since 2009-01-01` would still fetch only the 795 old members. One concrete
  number for phase 3: `cik.filers` now reaches roughly **890** distinct CIKs, up from 776.
- **Phase 5 (R4)** owns every `docs/` file. Left for it, found here:
  - `docs/runbooks/data-pipeline.md:12,15,44,51` — "ever-members since 2015-01-02" for
    `fundamentals` is now 2009-01-01 (lines 12 and 44 describe **bars**, whose `DEFAULT_START`
    is genuinely still 2015-01-02 and must not be changed).
  - `docs/runbooks/data-pipeline.md:169-175` — the re-vendoring steps duplicate
    `SOURCES.md`'s recipe and do not mention the `EARLY` screen or the `MANUAL` start sentinel.
  - `docs/runbooks/data-pipeline.md:245-247` — "every `ticker_cik` interval starts on or after
    2015-01-02 … the join therefore drops the ~181k facts filed before 2015-01-02" is the
    description of the bug this phase fixed, and is now false.
  - `docs/runbooks/data-pipeline.md:151-175` — the `### Re-vendoring engine/data/ticker_cik.csv`
    numbered recipe. It duplicates `SOURCES.md`'s, quotes **"the automated pass resolved 98 of
    133"** against a 133-symbol delisted residue that this phase's 795 → 913 re-scope moves, and
    mentions neither the `EARLY` screen nor the `MANUAL` start sentinel. **RECONCILED: phase 5
    owns it** (it owns the file), and phase 5 replaces the stale counts with a pointer to
    `SOURCES.md` — which this phase keeps current — rather than restating a figure it did not
    run. Do not edit it here.
- **A membership-data defect, deliberately not fixed here.** `TMUS`'s hull now opens
  2009-06-30, but the ticker `TMUS` did not exist until the 2013 MetroPCS/T-Mobile combination
  (`0001283699` was MetroPCS Communications and did file throughout, so the row is defensible
  under the hull doctrine and both screens pass it). Likewise `DXC` before 2017 and `LDOS`
  before 2013. Correcting these belongs in `engine/data/membership_overrides.csv`, which is the
  membership owner's file, exactly as the `NDOI` note already argues. **RECONCILED: out of this
  plan set's scope, no phase owns it, and no card is invented for it.** It is recorded as a
  follow-up in the index's `## Decisions` (row C7i); do not fold it in and do not cite a card id.
- **`SNDK`'s shipped row is already wrong today**, before anything in this phase: it gives the
  2025 SanDisk spinoff `0002023554` a start of 2015-01-02, when the 2015–2016 SNDK was the
  SanDisk Corp that Western Digital acquired. The regeneration fixes it as a side effect of the
  `EARLY` screen. Worth one sentence in phase 5's honest-reporting section: the clamp was hiding
  a wrong answer, not only a missing one.

---

## Rollback

This phase is one commit on `feature/fundamental-panel-coverage` and touches five tracked files
and nothing else — no database, no network write, no `engine/.research/`, no Neon. `git revert`
backs it out completely, and the previous `ticker_cik.csv` returns with it.

Two untracked side effects, both harmless and both gitignored:

- `engine/.cache/cik/` fills with ~1 GB of SEC JSON and the 39 MB `cik-lookup-data.txt`.
  `rm -rf engine/.cache/cik` if you want the space; the only cost of deleting it is that the next
  generator run is slow again.
- No venv is created: the reconciled set-wide rule is `PYTHONPATH` over the main checkout's
  venv, so there is nothing to remove here.

Partial rollback while iterating: `git checkout -- engine/data/ticker_cik.csv` restores the
shipped file without undoing the code edits, which is the right move if a generator run produced
a file you do not yet trust. Nothing downstream has read it yet — phase 3 is gated on this phase
landing.

---

## Decisions I took

**The `EARLY` screen and `EARLY_EXEMPT` — ACCEPTED by the reconciler, inside R1.** It was an
addition the plan index did not name; it is now named, in the index's phase table and in its
`## Decisions` (row C5). Two things were checked before accepting it:

- **It is genuinely free of network cost.** `SecFetcher.bytes` caches every artifact on disk
  under `--cache` by name, and both screens read the same `submissions-<cik>.json` (plus the same
  overflow files). The `EARLY` screen therefore issues no request the `SCREEN` screen has not
  already issued, and `_PERIODIC_CACHE` additionally stops the JSON being re-parsed per row.
- **It does not weaken `SCREEN_EXEMPT` (invariant 6).** All eleven entries keep their recorded
  reason verbatim and none is removed; `EARLY_EXEMPT` is a *separate* table answering a
  *different* question, and applying question 2 to a `SCREEN_EXEMPT` symbol only ever adds a
  check. `FRC` and `SBNY` are pre-seeded into `EARLY_EXEMPT` with their own FDIC §12(i) reasons,
  which restates their `SCREEN_EXEMPT` notes rather than replacing them.

The rung: the decision doc §2 in terms — *"Expect new cases: the further back the intervals
reach, the more recycling they cross"* — and invariant 2, which makes the screen the only audit a
start date gets. The stated fallback (keep `periodic_dates`, drop the `EARLY` block) is **not**
taken, and the files/row for it are in the index's phase table.

**The 14 literal `MANUAL` starts stay literal even though `spans()` would now produce the same
dates.** Measured: all 14 match their hull start exactly under the new floor. Replacing them with
the sentinel would be a no-op today and would silently drift if the membership CSVs are
re-vendored. A spinoff date is a fact about the company; leaving it written down is the point.

**`SCREEN_EXEMPT` entries are no longer skipped by the second screen.** The eleven recorded
reasons are all about a span that is short or has just opened — not about a filer that never
reported. Two of them (`FRC`, `SBNY`) genuinely never filed with EDGAR and are seeded into
`EARLY_EXEMPT`; the rest have short spans and the window rule skips them anyway. No existing note
is removed or weakened.
