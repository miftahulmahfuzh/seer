> Adopted from `HARDGATE_BEHAVIOURAL_KIN_PLAN.md` phase 1. Source: `.workflows/plan/hardgate-behavioural-kin/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Behavioural kin (D14), skill text, idea re-file

**Plan set:** `HARDGATE_BEHAVIOURAL_KIN_PLAN.md`
**Analysis:** `20261009-215504-K7Q2_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4 — the hard gate's kin check (K) follows what a method's books do (R1), argued as decision D14 in `hardgate.py` (R2), the two queued idea rows re-filed (R3), the explore skill's kin text brought in line (R4)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase `hardgate.failed_kin` — still the one definition of kin — also links a method to every `test-failed` method whose **tested** variant moves with any of the method's dev variants: monthly returns, de-funded, minus each series' own OLS fit on `REF-SPY-HOLD`'s monthly return, Pearson correlation of 0.85 or more over at least 36 shared months. A plain momentum book filed under a brand-new family with a non-momentum parent (insight 92's M0060/M0062 shape) is then kin of M0002 as soon as it has a curve. The rule is argued and measured as **(D14)** in the module docstring. `lab status` still prints `Promotable now: (none)`, `walkforward.py` is byte-identical, the explore skill describes the new kin, and idea rows M0060 and M0062 are re-filed to `p7a-f4` on the main checkout's lab db, with an insight that records why.

**Pre-verified.** Every code block below was run on a scratch copy of the worktree's engine and a scratch copy of the committed `lab/lab.sqlite` (@ `461580a`) before this plan was written. Results: `ruff check` clean; `tests/test_lab_hardgate.py` 68 passed (54 existing tests unchanged plus 14 new); the `-k lab` suite failed exactly the same 120 environment-only tests (no git repo / no docs in the scratch copy) as an unmodified scratch copy did, so nothing regressed. `failed_kin` on the real lab matched the analysis table exactly: 76 methods, D4∪D12 31, behavioural 26, union 43, dev-eligible blocked 8 → 10 of 10, newly linked = H-P7A-F4, H-P7A-F9, M0008, M0022, M0034, M0035, M0036, M0044, M0050, M0053, M0054, M0056. `lab status` printed `Promotable now ... (none)`; `lab walkforward` printed `No buy signal.`

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates (all in `engine/src/seer_engine/lab/hardgate.py`):**
- `KIN_CORRELATION: float = 0.85` (module constant)
- `MIN_KIN_MONTHS: int = 36` (module constant)
- `_FLAT: float = 1e-6` (private constant)
- `Month = tuple[int, int]` (type alias, `(year, month)`)
- `@dataclass(frozen=True, slots=True) class Twin(failed_id: str, candidate_id: str, failed_candidate_id: str, correlation: float)` with method `Twin.sentence() -> str`
- `def monthly_returns(curve: Sequence[tuple[date, float]], deposits: dict[date, float] | None = None) -> dict[Month, float]`
- `def residual(series: dict[Month, float], bench: dict[Month, float]) -> dict[Month, float] | None`
- `def correlation(a: dict[Month, float], b: dict[Month, float]) -> float | None`
- `def _tested_curves(conn, method_id: str) -> list[tuple[str, sqlite3.Row]]` (private)
- `def _flat(values: np.ndarray) -> bool` (private)
- `def behavioural_kin(conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None) -> tuple[Twin, ...]`

**Signature changes:** none. `failed_kin(conn, method_id) -> tuple[str, ...]` keeps its signature (tests monkeypatch it as `lambda _c, _m: ...`); its result now also includes behavioural twins' failed ids, and it can now raise `store.LabError` for a reason other than an unknown method (no benchmark, or a price-fingerprint mismatch/unknown on compared rows, or a de-funding refusal from `trial_deposits`) — only when at least one test-failed method has a recorded test trial with a dev curve **and** the method has a dev curve.
**Behaviour changes at callers:**
- `hardgate.check` — kin refusal message names behavioural links with their numbers.
- `commands/lab.py:_walkforward` — catches `store.LabError` from `failed_kin`, passes `"kin unknown (<reason>)"` as `family_failed`.
- `runner.kin_note` — catches `store.LabError` from `failed_kin`, returns a note (never raises, D3).
- `prereg.family_text`, `hardgate.summary` — already catch `LabError`; wording only.
**Requires (from earlier phases):** none.
**Leaves alone:** `engine/src/seer_engine/lab/walkforward.py` (byte-identical, owner's: `buy_signal`, its docstring, `BUY_CONDITIONS`); method files under `lab/methods/` (frozen); schema; `trials` and test-failed rows; D11 fold rule; `web/`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/hardgate.py` | modify | `import numpy as np` (after `:329`); constants after `_INGREDIENT` (`:361`); new block `Month`..`behavioural_kin` inserted before `failed_kin` (`:777`); `failed_kin` body/docstring (`:777-809`); `check`'s kin refusal (`:931-942`); module docstring (K) bullet (`:10-13`) and new (D14) section after (D13) (`:319`, before the closing `"""` at `:320`) |
| `engine/tests/test_lab_hardgate.py` | modify | `import numpy as np` (`:15`); optional `curve_json` kwarg on `_benchmark` (`:84-95`), `_method` (`:100-115`), `_variant` (`:304-313`); new D14 section appended after the last test (`:930`) |
| `engine/src/seer_engine/commands/lab.py` | modify | usage text (`:26-27`), status header (`:1013-1014`), `_promote` docstring (`:1308`), `_walkforward` kin call + comment (`:2050-2056`) |
| `engine/src/seer_engine/lab/prereg.py` | modify | `family_text` docstring (`:538-541`) and its two `one_line` messages (`:560-566`) |
| `engine/src/seer_engine/lab/runner.py` | modify | `kin_note` docstring (`:562-565`) and a `try/except store.LabError` around `failed_kin` (`:569`) |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | modify | kin text only: `:90-91`, `:242-245`, `:262`, `:278-284` |
| `/home/miftah/seer/lab/lab.sqlite` + `/home/miftah/seer/web/data/lab.json` (MAIN checkout) | data | last step, after merge: M0060/M0062 `family` → `p7a-f4` if still `idea`; one `lab insight`; `lab stage`; pathspec commit |

## Implementation Steps

All engine commands use `PYTHONPATH=<tree>/engine/src /home/miftah/seer/engine/.venv/bin/python` (the worktree has no venv of its own). `W=/home/miftah/.worktrees/seer/hardgate-behavioural-kin`.

### Step 1: Import numpy in hardgate
**File:** `engine/src/seer_engine/lab/hardgate.py:329`
**Change:** add a third-party import block between `from datetime import date` and `from seer_engine.backtest import regime`. NumPy is already an engine dependency (`pyproject.toml`: `numpy>=2`).
**Code:** the import block becomes
```python
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from seer_engine.backtest import regime
from seer_engine.lab import store
from seer_engine.lab import walkforward as wf
```
**Impact:** none on its own.

### Step 2: The D14 constants
**File:** `engine/src/seer_engine/lab/hardgate.py:361` (directly after `_INGREDIENT = re.compile(r"<(M\d{4})>")`, one blank line between)
**Change:** add three constants.
**Code:**
```python
#: The residual correlation at or above which a book is kin of a test-failed one by behaviour
#: (D14). Measured on the committed lab: the highest any unrelated book reaches against a failed
#: tested variant is 0.80 (``H-P7A-F10``, index ETFs), the lowest any momentum book in another
#: family's clothes reaches is 0.85 (M0008), and the plain twelve-month momentum book
#: ``H-P7A-F4`` reads 0.97. The bar sits in that gap, and it is not lowered from inside the code.
KIN_CORRELATION = 0.85

#: The fewest common months a residual correlation is computed on (D14). Three years of monthly
#: returns; fewer is "not measured", never kin -- a correlation on a handful of months is noise
#: wearing a number. Every comparable dev curve in the lab today shares 100 months or more with
#: every failed tested one, so this is a floor against a thin curve, not a quota on a method.
MIN_KIN_MONTHS = 36

#: Below this standard deviation a monthly series is flat -- a constant-growth curve whose
#: "returns" differ only by the rounding of its recorded values -- and has no correlation with
#: anything (D14). A real book's monthly returns move by percent; this is a ten-thousandth of one.
_FLAT = 1e-6
```
**Impact:** none on its own. `_FLAT` exists because `_curve` in the test fixtures rounds values to 8 decimals, so a "constant-growth" curve's monthly returns are not exactly equal — they differ at ~1e-8. A plain `np.std(...) == 0` test would let rounding noise through to `np.polyfit`/`np.corrcoef`; 1e-6 is far below any real book (monthly sd ~0.04) and far above the rounding.

### Step 3: Behavioural kin — the new block
**File:** `engine/src/seer_engine/lab/hardgate.py:777` (insert immediately **before** `def failed_kin`, i.e. after `ingredients()` ends at `:774`, with two blank lines on each side)
**Change:** add the type alias, `Twin`, the three measuring helpers, `_tested_curves` and `behavioural_kin`. Order of checks inside `behavioural_kin` is load-bearing: (1) unknown method → `LabError`; (2) no test-failed method with a tested dev curve → `()`; (3) method has no dev curve → `()`; only then (4) `geometry` (raises with no benchmark) and (5) price mismatches → `LabError`. Steps 2–3 before 4 are what keep every existing fixture (whose test-failed methods have no test trial, and many of which have no benchmark) out of the new code path.
**Code:**
```python
Month = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Twin:
    """One behavioural link (D14): a variant of the method that moves with a failed tested book.

    ``failed_id`` read ``test-failed``; ``failed_candidate_id`` is the variant it spent its look
    on; ``candidate_id`` is the method's own dev variant that tracks it best, and ``correlation``
    is their residual correlation -- always at or above ``KIN_CORRELATION``, or there is no twin.
    """

    failed_id: str
    candidate_id: str
    failed_candidate_id: str
    correlation: float

    def sentence(self) -> str:
        """``"M0002 (M0060-X moves with M0002's tested M0002-REL-85 at 0.97 residual correlation)"``."""
        return (
            f"{self.failed_id} ({self.candidate_id} moves with {self.failed_id}'s tested "
            f"{self.failed_candidate_id} at {self.correlation:.2f} residual correlation)"
        )


def _flat(values: np.ndarray) -> bool:
    return float(np.std(values)) < _FLAT


def monthly_returns(
    curve: Sequence[tuple[date, float]], deposits: dict[date, float] | None = None
) -> dict[Month, float]:
    """``curve``'s month-on-month returns, de-funded, keyed ``(year, month)``. See (D14).

    A recorded lab curve is already one point per month (``regime.month_ends``), so a return is
    the step between two consecutive points; the key is the month the step ends in. ``deposits``
    is ``trial_deposits``' answer for the trial, and ``regime.defunded`` takes them out first --
    the same de-funding path the folds use -- so a funded book's deposits never read as moves.
    A step from a non-positive value is left out rather than divided by.
    """
    by_month: dict[Month, float] = {}
    for d, v in regime.defunded(curve, deposits):
        by_month[(d.year, d.month)] = float(v)
    months = sorted(by_month)
    out: dict[Month, float] = {}
    for prev, cur in zip(months, months[1:]):
        if by_month[prev] > 0:
            out[cur] = by_month[cur] / by_month[prev] - 1.0
    return out


def residual(series: dict[Month, float], bench: dict[Month, float]) -> dict[Month, float] | None:
    """What ``series`` did that the market did not: its monthly return minus its own fit on SPY's.

    An ordinary least-squares line, intercept and slope, of ``series`` on the benchmark's monthly
    return over the months the two share; the residual is what the line does not explain. Every
    book in the lab is long US stocks, so two raw series correlate through the market alone, and
    subtracting SPY one-for-one (an "active" return) leaves each book's own market sensitivity
    behind -- (D14) measures both and neither separates momentum from the rest.

    None -- not measured -- when the two share fewer than ``MIN_KIN_MONTHS`` months, or when the
    series, the benchmark or the residual is flat (``_FLAT``). Checked before the fit, so a
    constant-growth curve never reaches ``np.polyfit`` and raises no warning.
    """
    months = sorted(set(series) & set(bench))
    if len(months) < MIN_KIN_MONTHS:
        return None
    x = np.array([bench[m] for m in months])
    y = np.array([series[m] for m in months])
    if _flat(x) or _flat(y):
        return None
    fit = np.polyfit(x, y, 1)
    left = y - np.polyval(fit, x)
    if _flat(left):
        return None
    return dict(zip(months, (float(v) for v in left)))


def correlation(a: dict[Month, float], b: dict[Month, float]) -> float | None:
    """Pearson correlation of two monthly series over the months they share. See (D14).

    None -- not measured, and therefore never kin -- below ``MIN_KIN_MONTHS`` common months, or
    when either side is flat over them. Checked before ``np.corrcoef``, which would otherwise
    divide by a zero variance and warn.
    """
    months = sorted(set(a) & set(b))
    if len(months) < MIN_KIN_MONTHS:
        return None
    x = np.array([a[m] for m in months])
    y = np.array([b[m] for m in months])
    if _flat(x) or _flat(y):
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _tested_curves(conn: sqlite3.Connection, method_id: str) -> list[tuple[str, sqlite3.Row]]:
    """Each test-failed method but ``method_id``, with the dev trial of the variant it tested.

    The tested variant is the candidate of the method's earliest ``window='test'`` trial -- the
    look it spent and lost. A test-failed method with no recorded test trial, or whose tested
    variant has no dev curve, has nothing to be compared with and is left out: it is still kin by
    (D4) and (D12) to whatever its family, ancestry or ingredients link it to. Sorted by id.
    """
    out: list[tuple[str, sqlite3.Row]] = []
    for f in conn.execute(
        "SELECT id FROM methods WHERE status = 'test-failed' AND id <> ? ORDER BY id",
        (method_id,),
    ).fetchall():
        fid = str(f["id"])
        tested = conn.execute(
            "SELECT candidate_id FROM trials WHERE method_id = ? AND window = 'test' "
            "ORDER BY n LIMIT 1",
            (fid,),
        ).fetchone()
        if tested is None:
            continue
        rows = [r for r in _dev_curves(conn, fid) if r["candidate_id"] == tested["candidate_id"]]
        if rows:
            out.append((fid, rows[0]))
    return out


def behavioural_kin(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> tuple[Twin, ...]:
    """The test-failed methods ``method_id`` moves with, one ``Twin`` each; ``()`` when none. (D14)

    For every test-failed method but this one, its tested variant's dev curve is compared with
    **every** dev variant of ``method_id`` that carries a curve: monthly returns, de-funded
    (``monthly_returns``), less each series' own fit on the benchmark's (``residual``), correlated
    over the months they share (``correlation``). The best-correlated pair at or above
    ``KIN_CORRELATION`` is the twin. One hop: only test-failed tested variants are compared, never
    a method that is itself only kin of one.

    ``()`` -- nothing measured -- when no test-failed method has a tested curve, or when
    ``method_id`` has no dev curve yet; its kin is then (D4) and (D12) alone. Otherwise the
    benchmark is needed (``geometry`` raises ``store.LabError`` without it), and every row
    compared must carry the benchmark's price fingerprint: a mismatch or an unknown on the
    method's rows or on a failed tested row raises ``store.LabError`` (D10) -- fail closed, never
    "no twin".
    """
    if store.get_method(conn, method_id) is None:
        raise store.LabError(f"no method {method_id}")
    targets = _tested_curves(conn, method_id)
    if not targets:
        return ()
    rows = _dev_curves(conn, method_id)
    if not rows:
        return ()
    geo = geometry(conn) if geo is None else geo
    problems = mismatches(conn, geo.bench_n, [*rows, *(r for _f, r in targets)])
    if problems:
        raise store.LabError(
            f"{method_id}'s behaviour cannot be compared with the test-failed books: "
            f"{describe(problems)}. The hard gate compares two curves only when both were "
            f"measured on the benchmark's prices (D10, D14), and fails closed when either side's "
            f"prices differ or are unknown. There is no override"
        )
    bench = monthly_returns(list(geo.bench))

    def residual_of(row: sqlite3.Row) -> dict[Month, float] | None:
        curve = _curve_of(row)
        return residual(monthly_returns(curve, trial_deposits(conn, row, curve)), bench)

    mine = [(str(r["candidate_id"]), residual_of(r)) for r in rows]
    twins: list[Twin] = []
    for failed_id, frow in targets:
        theirs = residual_of(frow)
        if theirs is None:
            continue
        best: Twin | None = None
        for candidate, series in mine:
            if series is None:
                continue
            rho = correlation(series, theirs)
            if rho is None or rho < KIN_CORRELATION:
                continue
            if best is None or rho > best.correlation:
                best = Twin(failed_id, candidate, str(frow["candidate_id"]), rho)
        if best is not None:
            twins.append(best)
    return tuple(twins)
```
**Impact:** new public API; no caller yet until Step 4.

### Step 4: `failed_kin` unions the twins
**File:** `engine/src/seer_engine/lab/hardgate.py:777-809` (the whole function, after Step 3 it sits below the new block)
**Change:** replace the function with the version below — docstring updated, the SQL now feeds a set, and the behavioural twins' failed ids are added. The early `return ()` on an empty name-kin set is gone (behaviour may still link).
**Code:**
```python
def failed_kin(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """Every method in ``method_id``'s kin that reads ``test-failed``; ``()`` when clean.

    Kin is the ``family`` string **union** the transitive ancestors reached through
    ``parent_id`` (D4), **union** every ingredient -- a lab method whose engine one of its
    variants runs -- together with that ingredient's own ``family`` and ancestors (D12),
    **union** every test-failed method whose tested variant one of its dev variants moves with,
    at a residual correlation of at least ``KIN_CORRELATION`` (D14, ``behavioural_kin``),
    excluding the method itself. One hop each: an ingredient's *other* variants' ingredients are
    not followed, and behaviour is compared only with the failed books themselves, never with
    their kin. See the module docstring for the measurements that decided all three.

    Raises ``store.LabError`` when the behavioural comparison cannot be made honestly -- no
    benchmark, or a curve on other or unknown prices (D10) -- rather than reading "clean".

    This is the one definition of kin. ``prereg.family_text``, ``lab test``'s note and ``lab
    walkforward``'s buy signal all call it, so they cannot disagree with the gate (D9, D13).
    """
    row = store.get_method(conn, method_id)
    if row is None:
        raise store.LabError(f"no method {method_id}")

    kin = _lineage(conn, row)
    for ing in ingredients(conn, method_id):
        kin.add(ing)
        ing_row = store.get_method(conn, ing)
        if ing_row is not None:
            kin |= _lineage(conn, ing_row)
    kin.discard(method_id)

    found: set[str] = set()
    if kin:
        ids = sorted(kin)
        marks = ", ".join("?" for _ in ids)
        found.update(
            str(r["id"])
            for r in conn.execute(
                f"SELECT id FROM methods WHERE id IN ({marks}) AND status = 'test-failed'",
                tuple(ids),
            )
        )
    found.update(t.failed_id for t in behavioural_kin(conn, method_id))
    return tuple(sorted(found))
```
**Impact:** every reader of kin widens (`family_state`, `summary`, `check`, `prereg.family_text`, `runner.kin_note`, `lab walkforward`). Existing fixtures are unaffected by construction (their test-failed methods record no test trial and their curves are flat).

### Step 5: `check`'s kin refusal names the behavioural links
**File:** `engine/src/seer_engine/lab/hardgate.py:931-942` (the final `bad = failed_kin(...)` block of `check`)
**Change:** replace the block. Existing asserted substrings are preserved: the failed ids, `"ingredient"`, `"override"`, `"There is no override"` (the no-override test strips exactly that phrase and `"no override"`). Do **not** introduce the words `force`, `enforce`, `override` (outside "no override"), `environ`, `getenv`, `skip_gate` anywhere in `hardgate.py` — `test_there_is_no_override` greps the module source.
**Code:**
```python
    bad = failed_kin(conn, method_id)
    if bad:
        twins = behavioural_kin(conn, method_id, geo)
        moves = (
            ""
            if not twins
            else f" By behaviour (D14): {'; '.join(t.sentence() for t in twins)} -- at or above "
            f"{KIN_CORRELATION:.2f}, what is left of a book's monthly return once the market's "
            f"share is taken out moves with a book that has already lost its look, and a new "
            f"name does not make it a new book."
        )
        raise store.LabError(
            f"{method_id} is not promoted: {', '.join(bad)} already read test-failed, and "
            f"{'they are' if len(bad) > 1 else 'it is'} kin -- same family ({row['family']!r}), "
            f"an ancestor through parent_id, an ingredient one of its variants runs (or that "
            f"ingredient's family or ancestry, D12), or a tested book one of its variants moves "
            f"with (D14).{moves} A new variant of a family that has been disproven out of sample "
            f"is not a fresh candidate, and neither is a blend with a disproven engine in it. "
            f"Nothing was written and no status moved. There is no override -- if this family "
            f"deserves another look, that is an argued change to the rule, in git"
        )
```
**Impact:** refusal text only. `check` passes its own `geo` to `behavioural_kin`, so the twins it prints are the ones `failed_kin` found.

### Step 6: Module docstring — the (K) bullet
**File:** `engine/src/seer_engine/lab/hardgate.py:10-13`
**Change:** replace the (K) bullet.
**Before:**
```text
- **(K) the kin.** No other method in its ``family``, no transitive ancestor through
  ``parent_id``, no **ingredient** -- a lab method whose engine one of its variants runs, a
  blend's parts included -- and nothing in an ingredient's own ``family`` or ancestry reads
  ``test-failed`` -- see **(D12)**.
```
**After:**
```text
- **(K) the kin.** No other method in its ``family``, no transitive ancestor through
  ``parent_id``, no **ingredient** -- a lab method whose engine one of its variants runs, a
  blend's parts included -- and nothing in an ingredient's own ``family`` or ancestry reads
  ``test-failed`` -- see **(D12)**; and no ``test-failed`` method's tested variant moves with any
  of its dev variants, at a residual correlation of ``KIN_CORRELATION`` or more -- see **(D14)**.
```

### Step 7: Module docstring — the (D14) section
**File:** `engine/src/seer_engine/lab/hardgate.py:319-320` — insert after the last line of (D13) (`majority is a change to ``buy_signal`` itself.`) and before the closing `"""`, with one blank line before the bold question line.
**Change:** add the full section below, verbatim. Numbers are as measured at `461580a`; Step 12 re-measures and updates them if the lab has moved.
**Code (docstring text):**
```text
**(D14) Does (K) read what a method does, as well as what it is called? -- Yes. A test-failed
method is kin when any dev variant's monthly return, de-funded and less its own fit on SPY's,
correlates with that method's tested variant at ``KIN_CORRELATION = 0.85`` or more, over at least
``MIN_KIN_MONTHS = 36`` shared months. Behaviour alone, no declared signal. One hop.**

Insight 92 found the hole the names leave. Two queued ideas are plain momentum books filed under
new family names with a non-momentum parent: M0060, "quiet twelve-month winners"
(``stock-low-volume-momentum``, parent M0057, short-term momentum, ``rejected``), and M0062,
"momentum among the most heavily traded members" (``stock-liquidity-tilt``, parent M0058,
illiquidity, ``rejected``). Neither shares a ``family``, a ``parent_id`` or an ingredient with M0002
(``stock-momentum-risk-managed``), M0022 (``stock-residual-momentum``) or M0021 and M0029
(``stock-multi-factor-blend``), all four ``test-failed``, so (D4) and (D12) would read both clean.
Nobody meant to dodge the gate; the filing let it happen. Three ways to close it:

- **(a) a declared signal.** Each method states the main thing it ranks on, machine-readably, and
  kin is "same signal".
- **(b) behaviour.** Kin is a measured similarity between the method's recorded curves and the
  failed methods' -- the books themselves, not their labels.
- **(c) both**, either one linking.

**Why not (a), and so not (c).** The field cannot live in the method files: a file that has run is
frozen by its ``source_sha`` (``runner.preflight``, ``test_a_method_that_ran_is_frozen``), and
that is all 30 files on disk, the four ``test-failed`` methods among them -- so the very methods
kin has to point at could never carry it. It would have to be a second registry kept by hand for
76 rows, labelled by the same filer whose family label slipped, which moves the hole from one
string to another. Its one edge, that it works before a method has a curve, buys nothing here:
``check`` is silent below ``dev-eligible``, and (F) refuses a method with no dev curve before (K)
is read. (c) carries (a)'s registry and catches nothing at the gate that (b) misses.

**Which correlation.** Measured on the committed lab: 76 methods; ``test-failed`` M0002 (tested
``M0002-REL-85``), M0021 (``M0021-B70-RAW``), M0022 (``M0022-W-TV14``) and M0029
(``M0029-B70-RAW-FRAC``); 42 methods carry dev curves, every one on price fingerprint
``5451195fd552``. Each figure is the best over a method's dev variants against any failed tested
variant, for the lab's books that are not momentum (``H-P7A-F1``, F3, F5, F7, F10, F11, M0005,
M0057, M0058) and its momentum books in other families' clothes (``H-P7A-F4``, F9, M0008, M0034,
M0035, M0036, M0044, M0050, M0053, M0054, M0056):

================================================  ==================  ====================  =========
correlation of monthly de-funded returns          not momentum,       momentum,             gap
                                                  highest             lowest
================================================  ==================  ====================  =========
raw                                               0.87 (F1)           0.88 (M0054)          none
active -- minus SPY's return                      0.90 (F3)           0.83 (M0054)          inverted
**residual -- less each series' fit on SPY's**    **0.8033 (F10)**    **0.8522 (M0008)**    **0.049**
================================================  ==================  ====================  =========

Every book in the lab is long US stocks, so two raw series correlate through the market alone;
subtracting SPY one for one leaves each book's own market sensitivity behind, and the active
column ranks the wrong way round. The residual -- what a line, intercept and slope, fitted on
SPY's monthly return over the series' own months does not explain -- is the only one with a gap.
Among the failed books themselves it reads M0021 to M0029 0.99, M0021 and M0029 to M0022 0.91, and
M0002 to the other three 0.72 to 0.75: M0002 is plain risk-managed momentum, and the other three
are residual-momentum engines.

**The threshold, and which variants.** Methods linked, of 76. (D4) union (D12) alone links 31 and
blocks 8 of the 10 ``dev-eligible`` methods (M0007, M0011, M0019, M0020, M0024, M0028, M0030, M0033,
M0044, M0053) -- all but M0044 and M0053:

======================  ==========  =========  ======  ============  ==========================================
variants compared       threshold   behaviour  union   dev-eligible  newly linked
                                                       blocked
======================  ==========  =========  ======  ============  ==========================================
promoted only           0.80, 0.85  13         34      10            M0022, M0044, M0053
promoted only           0.90        10         32      8             M0022
promoted only           0.95        7          31      8             --
every dev variant       0.80        29         45      10            the twelve below, and ``H-P7A-F10``
                                                                     (index ETFs, unrelated) and M0015
**every dev variant**   **0.85**    **26**     **43**  **10**        ``H-P7A-F4``, ``H-P7A-F9``, M0008, M0022,
                                                                     M0034, M0035, M0036, M0044, M0050, M0053,
                                                                     M0054, M0056
every dev variant       0.90        20         39      9             drops F9, M0008, M0053 and M0054
every dev variant       0.95        14         35      8             only ``H-P7A-F4``, M0034, M0035, M0050
======================  ==========  =========  ======  ============  ==========================================

0.85 sits in the gap: 0.047 above the highest unrelated book, and below every momentum book the lab
has -- M0008 clears it by 0.002, which is said here rather than hidden; the next momentum book can
land either side of a bar, and the plain one reads 0.97. 0.80 takes in the index-ETF book; 0.90 and
above let momentum books through.

Every dev variant, for (D12)'s reason: kin is a statement about a method, and every variant is a
candidate in every fold's pick. The promoted variant alone would also miss the very book this
decision exists for. A ``rejected`` method has no variant to promote, and a promoted variant is
often the braked one while the plain book sits beside it as another variant. The failed side is
each ``test-failed`` method's **tested** variant -- the candidate of its first ``window='test'``
trial, the book that actually lost its look -- on its dev curve.

**What it catches.** ``H-P7A-F4``'s ``F4-MOM12-N20-TREND`` -- plain twelve-month momentum behind the
SPY trend gate, 20 names, the exact F4-MOM12 book M0060's hypothesis names as its starting point
-- moves with M0002's tested ``M0002-REL-85`` at 0.97. That is the M0060 and M0062 shape: a plain
momentum book under any family name, with any parent, is kin of M0002 the moment it has a curve.
M0062's pick, twelve-one momentum inside the 60 most heavily traded members, has no recorded curve
and no proxy in the lab is that book; its own curve decides when it runs, and this rule makes no
claim about it before then.

**Why this is not (D4)'s blob.** Each link is a measured similarity between this method's books and
one failed **tested** book -- one hop, never kin of kin: a method that is only kin of a failure is
not a book anything is compared with. So the unrelated books stay free: index timing (F1, 0.79),
sector rotation (F3, 0.79), leveraged ETFs (F10, 0.80), low volatility (F5, 0.52), RSI(2) (F7,
0.32), turn of the month (F11, 0.39), fundamentals (M0005, 0.06), illiquidity (M0058, 0.68) and
short-term momentum (M0057, 0.76). What the rule links is the momentum the lab has already tested
and lost on, under whatever name it was filed.

**A method with no curve.** Nothing is measured: ``behavioural_kin`` returns ``()`` and its kin is
(D4) union (D12) alone. The gate never reaches (K) for such a method anyway -- ``check`` is silent
below ``dev-eligible``, and (F) refuses a method with no dev curve first. The same holds for any
pair a correlation cannot be computed on: a flat series (a constant-growth curve, the shape every
test fixture records), fewer than ``MIN_KIN_MONTHS`` shared months, or a failed method with no
recorded look. Not measured is never kin, and never a pass on the other rules either.

**Comparability and the cost.** Every row compared must carry the benchmark's price fingerprint;
a mismatch or an unknown on the method's rows or on a failed tested row raises (D10) -- the gate
refuses, and ``lab status`` prints "kin unknown" with the reason. It is still SQL and arithmetic
on recorded curves: no store, no backtest, no look.

**It refuses nobody new today.** The two ``dev-eligible`` methods it newly links, M0044 and M0053,
already fail (F) under (D11), and M0022 is itself ``test-failed`` and not gated. ``lab status``
still prints ``Promotable now: (none)``. As with (D12), that is the point: the next momentum book
under a new name will not have a fold record that happens to catch it.

**(D13) still holds.** ``lab walkforward`` passes ``failed_kin`` to ``walkforward.buy_signal``, so
the signal's kin condition widens with (D14) through its caller and ``buy_signal`` is not edited.
The one change at the caller is that ``lab walkforward`` now catches a ``store.LabError`` from
``failed_kin`` -- (D14) compares curves, so it can refuse on prices (D10) -- and hands
"kin unknown (...)" to the signal as the failed kin: the signal cannot fire on a kin nobody could
check, and the report still prints the row. ``BUY_CONDITIONS`` and the ``buy_signal`` docstring
still say "family union ancestors", which under-describes the rule further; they remain the
owner's to edit.
```
**Impact:** docstring only. `test_the_module_records_the_behavioural_kin_decision` (Step 11) asserts `(D14)`, `F4-MOM12-N20-TREND`, `M0060`, `M0062` in it.

### Step 8: `prereg.family_text` wording
**File:** `engine/src/seer_engine/lab/prereg.py:535-567`
**Change:** replace the whole function with the version below — the docstring names D14, and both `one_line` messages add ", or moving with it by behaviour,". Asserted substrings in `tests/test_lab_prereg.py:676-689` (`"blocked at promotion"`, `"clean at promotion"`, `"test-failed"`, the family string, the failed ids) are all preserved. It already catches `LabError`, so a D14 refusal is recorded as "not recorded: the kin walk could not be run (...)".
**Code:**
```python
def family_text(conn: sqlite3.Connection, method_id: str, family: str) -> str:
    """The state of ``method_id``'s kin at promotion, as the file states it.

    ``hardgate.failed_kin`` is the one definition of kin -- the method's ``family`` string together
    with its transitive ancestors through ``parent_id`` (plan Decision D4), its ingredients with
    theirs (hardgate D12), and the test-failed books one of its variants moves with (hardgate
    D14) -- and this line quotes its answer rather than re-deriving it, so the file and the rule
    cannot disagree.

    ``family`` is passed in because every caller already holds the ``methods`` row and a second
    query inside the write lock would buy nothing. It is named in the line so a reader knows which
    string the rule walked.

    This is the state **at promotion** and nothing re-checks it afterwards (plan Decision D3);
    ``render``'s prose says so to the file's reader, and this docstring says so to the next
    implementer who wonders why ``lab test`` does not call it.

    Never raises, and always one line.
    """
    from seer_engine.lab import hardgate

    try:
        failed = tuple(hardgate.failed_kin(conn, method_id))
    except store.LabError as e:
        return one_line(f"not recorded: the kin walk could not be run ({e})")
    if not failed:
        return one_line(
            f"clean at promotion: no method in {method_id}'s family '{family}', ancestry or "
            f"ingredients (or theirs), or moving with it by behaviour, read test-failed"
        )
    return one_line(
        f"blocked at promotion: {', '.join(failed)} in {method_id}'s family '{family}', ancestry "
        f"or ingredients (or theirs), or moving with it by behaviour, read test-failed"
    )
```
**Impact:** text of the `family_state` line in future pre-registration files only. Committed pre-registrations are not touched.

### Step 9: `runner.kin_note` copes with a kin it cannot read
**File:** `engine/src/seer_engine/lab/runner.py:545-580`
**Change:** today `kin_note` calls `failed_kin` with no `try`, and `preflight_test` (`runner.py:674`) calls `kin_note` — so a D14 `LabError` (no benchmark, other prices) would become a **refusal** of `lab test`, which D3 forbids ("a note and never a refusal"). Decision: catch `store.LabError` and return a note saying the kin could not be read today. `store` is already imported at module level (`runner.py:66`). Replace the whole function:
**Code:**
```python
def kin_note(conn: sqlite3.Connection, method_id: str) -> str | None:
    """One line for ``lab test`` when ``method_id``'s kin has failed since it was promoted.

    ``None`` when the kin is clean, which is the normal case and prints nothing.

    **This is a note and never a refusal** (plan Decision D3). The pre-registration is a promise:
    ``promoted`` has only two exits and both are final, so refusing here would strand the method in
    a state it can never leave -- the exact failure the gate was put at ``lab promote`` to avoid,
    and the reason the hard gate refuses *before* the commitment rather than after it. What the
    owner is owed is the information before the one look is spent, not a door that closes behind
    them.

    The method's ``family_state`` line in ``docs/lab/prereg/MNNNN.md`` records what was true the day
    the promise was made; this says what is true today. When the two differ, that difference is the
    whole content of the note, and the pre-registration is still the correct record of what was
    known then.

    Kin is ``hardgate.failed_kin``'s definition -- the ``family`` string union the transitive
    ancestors through ``parent_id`` (D4), the blend ingredients and theirs (hardgate D12), and the
    test-failed books one of its variants moves with (hardgate D14) -- read from the one place that
    defines it, so the note and the gate can never disagree about who counts as kin. It names
    **every** failed relative, not the first: M0030's two are M0021 and M0029.

    When the kin cannot be read today -- D14 compares recorded curves, and ``failed_kin`` raises
    ``store.LabError`` on a curve measured on other or unknown prices (D10) -- the note says so
    instead. It is still a note: a kin walk that cannot run is information before the look, and
    turning it into a refusal here would break the promise exactly as a failed kin would.
    """
    from seer_engine.lab import hardgate

    try:
        failed = hardgate.failed_kin(conn, method_id)
    except store.LabError as e:
        return (
            f"note: {method_id}'s kin could not be read today ({e}). The pre-registration is a "
            f"promise and is not re-opened, so this look still runs and its family_state line "
            f"still records what was true the day it was written. This is information before "
            f"the look is spent, not a refusal"
        )
    if not failed:
        return None
    names = ", ".join(failed)
    return (
        f"note: {names} {'have' if len(failed) > 1 else 'has'} read test-failed since "
        f"{method_id} was promoted. The pre-registration is a promise and is not re-opened, so "
        f"this look still runs and its family_state line still records what was true the day it "
        f"was written. This is information before the look is spent, not a refusal"
    )
```
**Impact:** `lab test` never refuses on kin, as before. Existing asserted strings in `tests/test_lab_test_window.py:451-505` (`"has read test-failed since"`, `"not a refusal"`, `None` for clean kin) are unchanged.

### Step 10: `commands/lab.py` — `lab walkforward` catches a kin `LabError`; kin wording
**File:** `engine/src/seer_engine/commands/lab.py`
**Change (a) `:2050-2056`, in `_walkforward`'s per-method loop.** Replace
```python
        # The SAME kin rule the promote gate uses (hardgate.failed_kin: family union transitive
        # ancestors union blend ingredients and theirs, hardgate D12), not a second query beside
        # it. Decision D9 is what happens when these two disagree: the signal said M0030's family
        # was clean while the gate refused it on ancestry, which is a worse answer than either one
        # alone. That the signal widens with D12 is recorded as hardgate Decision D13.
        kin = hardgate.failed_kin(conn, mid) if row is not None else ()
        signal, why = wf.buy_signal(eligible, rec, edge, ", ".join(kin) if kin else None)
```
with
```python
        # The SAME kin rule the promote gate uses (hardgate.failed_kin: family union transitive
        # ancestors union blend ingredients and theirs, hardgate D12, union the tested books one
        # of its variants moves with, hardgate D14), not a second query beside it. Decision D9 is
        # what happens when these two disagree: the signal said M0030's family was clean while
        # the gate refused it on ancestry, which is a worse answer than either one alone. That
        # the signal widens with D12 and D14 is recorded as hardgate Decision D13. When the kin
        # cannot be read -- D14 compares curves, and refuses on other or unknown prices (D10) --
        # the reason goes in as the failed kin, so the signal cannot fire on a kin nobody could
        # check, and the report still prints the row.
        if row is None:
            family_failed = None
        else:
            try:
                kin = hardgate.failed_kin(conn, mid)
            except store.LabError as e:
                family_failed = f"kin unknown ({e})"
            else:
                family_failed = ", ".join(kin) if kin else None
        signal, why = wf.buy_signal(eligible, rec, edge, family_failed)
```
`wf.buy_signal` is called exactly as before (positional `family_failed: str | None`); `walkforward.py` is not edited.

**Change (b) `:26-27`, the module usage text for `lab promote`.** Replace
```text
                                    prices other than the benchmark's, or whose family or ancestry
                                    already reads test-failed (lab/hardgate.py). The refusal
```
with
```text
                                    prices other than the benchmark's, or whose kin -- family,
                                    ancestry, blend ingredient or behaviour -- already reads
                                    test-failed (lab/hardgate.py). The refusal
```

**Change (c) `:1013-1014`, `lab status`'s "Refused by the hard gate" header.** Replace
```python
            "pre-register, and no kin -- family, ancestry or blend ingredient -- that has "
            "test-failed; there is no override):"
```
with
```python
            "pre-register, and no kin -- family, ancestry, blend ingredient or behaviour -- that "
            "has test-failed; there is no override):"
```
(`tests/test_lab_status.py` splits on the substring `"Refused by the hard gate"` only; unaffected.)

**Change (d) `:1307-1308`, `_promote`'s docstring.** Replace
```text
    walk-forward folds, that is scoreable on fewer folds than the geometry yields, or whose
    family or ancestry already reads `test-failed`. It raises `store.LabError`, which `run` turns
```
with
```text
    walk-forward folds, that is scoreable on fewer folds than the geometry yields, or whose
    kin -- family, ancestry, blend ingredients or behaviour (hardgate D4, D12, D14) -- already
    reads `test-failed`. It raises `store.LabError`, which `run` turns
```
**Impact:** (a) is the only behavioural caller change; (b)–(d) are kin wording in the same file.

### Step 11: Tests — fixture kwargs and the D14 section
**File:** `engine/tests/test_lab_hardgate.py`

**(a) `:15`** — add `import numpy as np` above `import pytest`:
```python
import numpy as np
import pytest
```

**(b) `:84-125`** — replace `_benchmark` and `_method` with the versions below (a backwards-compatible optional `curve_json` kwarg; every existing call is unchanged):
```python
def _benchmark(conn, *, prices: str | None = SAME_PRICES, stamped: bool = True,
               curve_json: str | None = None) -> None:
    """The lab's REF-SPY-HOLD dev trial, recorded -- like the real trial #1 -- under the P7a store
    fingerprint while every method below carries ``399d0d25``. Same prices, different store: the
    committed lab's own shape, and the case D10 says must stay comparable."""
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            store_fingerprint="5451195f",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08) if curve_json is None else curve_json,
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)


def _method(conn, mid="M0001", *, family="trend", parent=None, status="dev-eligible",
            annual=0.15, span=DEV_SPAN, curves=True, prices: str | None = SAME_PRICES,
            stamped: bool = True, curve_json: str | None = None) -> None:
    """One method with one dev trial, walked to ``status`` through the real transitions.

    The trial is stamped with provenance on ``prices`` unless ``stamped`` is False -- the gate
    refuses an unstamped trial (D10), which is a test of its own below, not a default.
    """
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=(
                "[]" if not curves
                else curve_json if curve_json is not None
                else _curve(_months(*span), annual)
            ),
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)
        for step in {
            "registered": (),
            "dev-eligible": ("dev-eligible",),
            "promoted": ("dev-eligible", "promoted"),
            "test-failed": ("dev-eligible", "promoted", "test-failed"),
            "rejected": ("rejected",),
        }[status]:
            store.update_method(conn, mid, status=step)
```

**(c) `:304-313`** — replace `_variant` with:
```python
def _variant(conn, mid: str, suffix: str, *, annual: float, config_text: str = "t",
             curves: bool = True, curve_json: str | None = None) -> None:
    """A second dev trial of an existing method -- another variant -- stamped on the lab's prices."""
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            config_text=config_text,
            curve_json=(
                "[]" if not curves
                else curve_json if curve_json is not None
                else _curve(_months(*DEV_SPAN), annual)
            ),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)
```

**(d) after the last test (`:930`, end of file)** — append this whole section (two blank lines before the first comment line). The fixture curves elsewhere are flat, so this section builds moving curves from seeded NumPy draws (deterministic). `_EDGE` adds a constant monthly return to the tracking book so its fold record wins (the refusal is then (K), not (F)); a constant is absorbed by the regression's intercept and changes no residual correlation. Verified: all 14 tests pass, deterministic, no warnings under `-W error`.
```python
# ------------------------------------------------------------------ (D14) behaviour is kin
#
# The fixtures above record constant-growth curves, whose monthly returns are flat: they have no
# correlation with anything, which is exactly why every kin test before this section is untouched
# by (D14). The curves here move. ``_MARKET`` is one seeded draw of monthly returns, the benchmark
# is that draw alone, and a book is the market plus its own seeded "idea" -- two books that share
# an idea move together once the market is taken out; two that do not, do not.

_BENCH_MONTHS = _months(*BENCH_SPAN)


def _draw(seed: int, *, mean: float, sd: float) -> dict[date, float]:
    rng = np.random.default_rng(seed)
    return dict(zip(_BENCH_MONTHS, (float(r) for r in rng.normal(mean, sd, len(_BENCH_MONTHS)))))


_MARKET = _draw(0, mean=0.007, sd=0.04)
_IDEA_A = _draw(1, mean=0.006, sd=0.03)     # the failed book's idea
_IDEA_B = _draw(2, mean=0.006, sd=0.03)     # an unrelated idea
_NOISE = _draw(3, mean=0.0, sd=0.006)       # small, so a copy of an idea still tracks it
_EDGE = {d: 0.01 for d in _BENCH_MONTHS}    # a steady extra point a month: wins the folds, and
                                            # moves nothing, so it changes no correlation


def _moving(months: list[date], *ideas: dict[date, float]) -> str:
    """A recorded monthly curve that moves: the market's return plus each idea's, every month."""
    out, v = [], 1.0
    for i, d in enumerate(months):
        if i:
            v *= 1.0 + _MARKET[d] + sum(idea[d] for idea in ideas)
        out.append([d.isoformat(), round(v, 8)])
    return json.dumps(out)


def _moving_benchmark(conn) -> None:
    _benchmark(conn, curve_json=_moving(_BENCH_MONTHS))


def _tested(conn, mid: str) -> None:
    """``mid``'s one look at the test window, spent on its ``-A`` variant (the look it lost)."""
    with conn:
        store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}", window="test",
            start="2016-01-04", end="2026-09-30", eligible=False,
        )])


def _failed_momentum(conn, *, prices: str | None = SAME_PRICES) -> None:
    """M0002, a momentum book that read ``test-failed`` -- with the look it spent, recorded."""
    _method(conn, "M0002", family="stock-momentum-risk-managed", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A), prices=prices)
    _tested(conn, "M0002")


def test_the_module_records_the_behavioural_kin_decision():
    """Insight 92: kin follows what a book does, argued and measured in the docstring (D14)."""
    doc = hardgate.__doc__ or ""
    assert "(D14)" in doc
    assert "F4-MOM12-N20-TREND" in doc   # the plain momentum book it catches, named
    assert "M0060" in doc and "M0062" in doc
    assert hardgate.KIN_CORRELATION == 0.85
    assert hardgate.MIN_KIN_MONTHS == 36


def test_a_book_that_moves_with_a_failed_tested_book_is_kin_under_any_name(conn):
    """Insight 92's shape: a momentum book under a brand-new family, its parent a non-momentum
    method. Family, ancestry and ingredients all read clean; its curve does not."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0057", family="stock-short-term-momentum", status="rejected")
    _method(conn, "M0060", family="stock-low-volume-momentum", parent="M0057",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE, _EDGE))
    assert hardgate.fold_record(conn, "M0060").majority   # so the refusal below is (K), not (F)
    twins = hardgate.behavioural_kin(conn, "M0060")
    assert [(t.failed_id, t.candidate_id, t.failed_candidate_id) for t in twins] == [
        ("M0002", "M0060-A", "M0002-A")
    ]
    assert twins[0].correlation >= hardgate.KIN_CORRELATION
    assert hardgate.failed_kin(conn, "M0060") == ("M0002",)
    assert hardgate.family_state(conn, "M0060") == "blocked: M0002 read test-failed"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0060")
    msg = str(e.value)
    assert f"M0060-A moves with M0002's tested M0002-A at {twins[0].correlation:.2f}" in msg
    assert "residual correlation" in msg and "D14" in msg
    assert "override" in msg


def test_a_book_with_its_own_idea_is_clean(conn):
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="stock-low-volume-momentum",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.failed_kin(conn, "M0060") == ()


def test_every_dev_variant_is_compared_and_the_best_pair_is_named(conn):
    """Kin is about a method, not one variant (D12's reason): a tracking variant anywhere in it
    links the method, and the twin names that variant."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    _variant(conn, "M0060", "MOM", annual=0.0,
             curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE))
    (twin,) = hardgate.behavioural_kin(conn, "M0060")
    assert twin.candidate_id == "M0060-MOM"


def test_a_failed_method_with_no_recorded_look_contributes_no_behaviour(conn):
    """The tested variant is the one the look was spent on; with no test trial there is none to
    compare -- the method is still kin by family, ancestry and ingredients (D4, D12)."""
    _moving_benchmark(conn)
    _method(conn, "M0002", family="momentum", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE))
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.failed_kin(conn, "M0060") == ()


def test_flat_curves_are_not_measured_and_raise_no_warning(conn):
    """A constant-growth curve -- every fixture above -- has no variance, so no correlation. It is
    "not measured", never kin, and it never reaches np.polyfit or np.corrcoef to warn."""
    import warnings

    _benchmark(conn)                      # flat benchmark
    _method(conn, "M0002", family="momentum", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _tested(conn, "M0002")
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _method(conn, "M0061", family="other", annual=0.15)  # flat book
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert hardgate.behavioural_kin(conn, "M0060") == ()   # the benchmark is flat
        assert hardgate.behavioural_kin(conn, "M0061") == ()
        flat = hardgate.monthly_returns(hardgate._curve_of(conn.execute(
            "SELECT curve_json FROM trials WHERE candidate_id = 'M0061-A'").fetchone()))
        moving = hardgate.monthly_returns([(d, 1.0 + 0.01 * (i % 7)) for i, d in
                                           enumerate(_months(*DEV_SPAN))])
        assert hardgate.residual(flat, moving) is None
        assert hardgate.correlation(flat, moving) is None


def test_fewer_than_the_minimum_common_months_is_not_measured(conn):
    _moving_benchmark(conn)
    _failed_momentum(conn)
    short = _months(date(2013, 1, 1), date(2015, 10, 16))  # 34 points, 33 monthly returns
    _method(conn, "M0060", family="new", span=(short[0], short[-1]),
            curve_json=_moving(short, _IDEA_A, _NOISE))
    assert len(short) - 1 < hardgate.MIN_KIN_MONTHS
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    months = [(2000 + i // 12, 1 + i % 12) for i in range(hardgate.MIN_KIN_MONTHS)]
    a = {m: float(i % 5) for i, m in enumerate(months)}
    b = {m: float(i % 5) + 0.1 * (i % 3) for i, m in enumerate(months)}
    assert hardgate.correlation(a, b) is not None
    del a[months[0]]
    assert hardgate.correlation(a, b) is None


def test_behaviour_is_one_hop(conn):
    """Only failed tested books are compared. M0070 is M0002's kin by family; M0080 moves with
    M0070 and not with M0002, so it is nobody's kin -- kin of kin is (D4)'s blob."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0070", family="stock-momentum-risk-managed", status="rejected",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    _method(conn, "M0080", family="unrelated",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _NOISE))
    assert hardgate.failed_kin(conn, "M0070") == ("M0002",)
    assert hardgate.behavioural_kin(conn, "M0080") == ()
    assert hardgate.failed_kin(conn, "M0080") == ()


def test_a_failed_tested_book_on_other_prices_refuses_rather_than_reads_clean(conn):
    """Fail closed (D10): a comparison across two price histories measures the data."""
    _moving_benchmark(conn)
    _failed_momentum(conn, prices=OTHER_PRICES)
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    with pytest.raises(store.LabError) as e:
        hardgate.behavioural_kin(conn, "M0060")
    assert "M0002-A" in str(e.value) and "D10" in str(e.value)
    with pytest.raises(store.LabError):
        hardgate.failed_kin(conn, "M0060")
    with pytest.raises(store.LabError):
        hardgate.check(conn, "M0060")
    assert "kin unknown (" in hardgate.summary(conn, "M0060")


def test_the_method_itself_is_never_its_own_behavioural_kin(conn):
    _moving_benchmark(conn)
    _failed_momentum(conn)
    assert hardgate.behavioural_kin(conn, "M0002") == ()
    assert hardgate.failed_kin(conn, "M0002") == ()


def test_a_method_with_no_curve_has_nothing_measured(conn):
    """Nothing to compare, so its kin is (D4) and (D12) alone -- and no benchmark is needed to
    say so. The gate never reaches (K) for it anyway: (F) refuses a method with no curve."""
    _failed_momentum(conn)                # no benchmark at all
    _method(conn, "M0060", family="new", curves=False)
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.failed_kin(conn, "M0060") == ()
    with pytest.raises(store.LabError):
        hardgate.behavioural_kin(conn, "M9999")


def test_lab_walkforward_prints_a_kin_it_cannot_read_and_fires_nothing(tmp_path, capsys):
    """The report catches the kin's refusal (D10, D14) and hands it to the signal as the failed
    kin, so the signal cannot fire on a kin nobody could check -- walkforward.py unedited (D13)."""
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _moving_benchmark(c)
    _failed_momentum(c, prices=OTHER_PRICES)
    _method(c, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    c.close()

    rc = lab_cmd.run(argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0060"))
    assert "kin unknown (" in row
    assert "No buy signal" in out


def test_lab_tests_note_says_when_the_kin_cannot_be_read(conn):
    """A note, never a refusal (D3): a kin walk that cannot run is still information."""
    from seer_engine.lab import runner

    _moving_benchmark(conn)
    _failed_momentum(conn, prices=OTHER_PRICES)
    _method(conn, "M0060", family="new", status="promoted",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B))
    note = runner.kin_note(conn, "M0060")
    assert note is not None
    assert "could not be read" in note and "not a refusal" in note
```
**Impact:** 14 new tests; the 54 existing ones in this file are untouched in body and still pass.

### Step 12: The explore skill's kin text
**File:** `.claude/skills/explore-and-experiment-new-method/SKILL.md` (at the worktree root)

**(a) `:90-91`.** Before:
```text
     - **Name the family by what it ranks on**, not by the idea that inspired it (insight 92). A
       momentum book filed under a new family name escapes the kin check by accident.
```
After:
```text
     - **Name the family by what it ranks on**, not by the idea that inspired it (insight 92). The
       gate no longer depends on the name -- since hardgate D14 it also reads how a book moves, so
       a momentum book under a new family is kin of the failed momentum books once it has a curve
       -- but `lab status`, the lab's families and anyone reading the lab before a curve exists
       still go by it. The runner copies the family from the method file when the idea runs, so
       the file must carry the family the idea row was given.
```

**(b) `:242-245`.** Before:
```text
     - **(K) kin.** **No kin reads `test-failed`** -- kin being the method's `family` *and* its
       transitive ancestors through `parent_id`. A parent that failed out of sample disproves a
       method as surely as a sibling that failed; M0032 is M0007's realistic twin by `parent_id`
       and not by family string.
```
After:
```text
     - **(K) kin.** **No kin reads `test-failed`** -- kin being the method's `family`, its
       transitive ancestors through `parent_id`, every lab method whose engine one of its variants
       runs (a blend's ingredients, with their own family and ancestry -- D12), **and** every
       test-failed method whose tested variant moves with one of its dev variants: monthly
       returns de-funded, less each one's fit on SPY's, correlated at 0.85 or more over at least
       36 shared months (D14). A parent that failed out of sample disproves a method as surely as
       a sibling that failed; M0032 is M0007's realistic twin by `parent_id` and not by family
       string. And a plain momentum book is kin of the failed momentum books whatever its family
       is called, because it moves with them. A method with no curve yet has nothing measured;
       its kin is the names alone until it runs.
```

**(c) `:262`.** Before:
```text
   > **(a)** dev-eligible at the bars in force, **(b)** no method in its family has test-failed,
```
After:
```text
   > **(a)** dev-eligible at the bars in force, **(b)** no kin has test-failed (the gate's (K) kin),
```

**(d) `:278-285`** (the paragraph that starts "**The buy signal's (b) and the hard gate's (K) are not the same test**" and ends "rather than quietly widened."). Before:
```text
   **The buy signal's (b) and the hard gate's (K) are not the same test, and that is deliberate.**
   The buy signal checks the `family` string only (`lab/walkforward.py`'s `BUY_CONDITIONS`, and
   `lab walkforward`'s own query); the gate also walks `parent_id`. A method can therefore read
   clean in `lab walkforward` and still be refused by `lab promote` — M0030's family is clean while
   its parent M0029 and grandparent M0021 both read `test-failed`. The gate is the stricter of the
   two and it is the one that decides whether a look is spent. The buy signal is a separate,
   owner-decided rule about when to **buy data**, not about when to promote, so it was left as it
   is rather than quietly widened.
```
After:
```text
   **The buy signal's (b) and the hard gate's (K) read the same kin.** `lab walkforward` hands the
   signal `hardgate.failed_kin` -- family, ancestry, blend ingredients and behaviour (hardgate D9,
   D13, D14) -- so a method cannot read clean in `lab walkforward` and be refused on kin by `lab
   promote`. When the kin cannot be read (a curve on other prices), the report prints "kin
   unknown" on that row and the signal does not fire. What still differs is the folds: the signal
   reads the picks' record only, while the gate also wants the promoted variant's own majority
   (D11). The buy signal is a separate, owner-decided rule about when to **buy data**, not about
   when to promote; its wording in `lab/walkforward.py` (`BUY_CONDITIONS` still says "family union
   ancestors") is the owner's to change.
```
Before editing, `sed -n 276,286p` the file and confirm the paragraph spans exactly those lines; replace the whole paragraph regardless of the line count.
**Impact:** skill text only.

### Step 13: Re-measure on a fresh scratch copy and reconcile D14's numbers
Sera sessions may have moved `lab/lab.sqlite` on main since `461580a`. D14's numbers must describe the lab at merge time.

1. Fresh scratch copy of the **committed** db (not the working file, which a live Sera session may be writing):
   ```bash
   SCR=/tmp/claude-1000/-home-miftah-seer/hgbk-remeasure; rm -rf "$SCR"; mkdir -p "$SCR"
   git -C /home/miftah/seer fetch origin
   git -C /home/miftah/seer show origin/main:lab/lab.sqlite > "$SCR/lab.sqlite"
   git -C /home/miftah/seer log -1 --format='%h %s' origin/main -- lab/lab.sqlite
   ```
2. The analysis's script (per-method residual correlations):
   ```bash
   cd "$W/.workflows/plan/hardgate-behavioural-kin" && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python measure_kin.py "$SCR/lab.sqlite" > "$SCR/measure.txt"
   ```
3. Write `$SCR/threshold_table.py` (scratch only, never committed) and run it:
   ```python
   """D14's threshold table on a scratch copy of lab.sqlite: promoted-only vs every dev variant."""
   import sqlite3, sys, warnings
   warnings.simplefilter("error")
   from seer_engine.lab import hardgate, store

   conn = sqlite3.connect(sys.argv[1]); conn.row_factory = sqlite3.Row
   geo = hardgate.geometry(conn)
   ids = [r[0] for r in conn.execute("SELECT id FROM methods ORDER BY id")]
   status = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM methods")}
   dev_el = [m for m in ids if status[m] == "dev-eligible"]
   bench = hardgate.monthly_returns(list(geo.bench))

   def resid(row):
       c = hardgate._curve_of(row)
       return hardgate.residual(hardgate.monthly_returns(c, hardgate.trial_deposits(conn, row, c)), bench)

   def old_kin(mid):
       row = store.get_method(conn, mid); kin = hardgate._lineage(conn, row)
       for ing in hardgate.ingredients(conn, mid):
           kin.add(ing); r = store.get_method(conn, ing)
           if r is not None: kin |= hardgate._lineage(conn, r)
       kin.discard(mid)
       return {m for m in kin if status.get(m) == "test-failed"}

   old = {m: old_kin(m) for m in ids}
   best = {}  # (method, set) -> best correlation against any failed tested variant
   for m in ids:
       targets = [(f, resid(r)) for f, r in hardgate._tested_curves(conn, m)]
       rows = hardgate._dev_curves(conn, m)
       promo = hardgate.promoted_variant(conn, m)  # best_dev_eligible, whatever the status (as measured)
       for label, chosen in (("promoted only", [r for r in rows if r["candidate_id"] == promo]),
                             ("every dev variant", rows)):
           rhos = [hardgate.correlation(s, t) for r in chosen if (s := resid(r)) is not None
                   for _f, t in targets if t is not None]
           rhos = [x for x in rhos if x is not None]
           best[(m, label)] = max(rhos) if rhos else None
   print(f"D4+D12 alone: {sum(bool(v) for v in old.values())} of {len(ids)}, "
         f"dev-eligible {sum(bool(old[m]) for m in dev_el)} of {len(dev_el)}")
   for label in ("promoted only", "every dev variant"):
       for t in (0.80, 0.85, 0.90, 0.95):
           beh = {m for m in ids if (b := best[(m, label)]) is not None and b >= t}
           union = beh | {m for m in ids if old[m]}
           newly = sorted(m for m in beh if not old[m])
           print(f"{label:18s} {t:.2f} behaviour {len(beh):2d} union {len(union):2d} "
                 f"dev-eligible {sum(m in union for m in dev_el):2d}  newly: {', '.join(newly) or '-'}")
   ```
   ```bash
   PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python "$SCR/threshold_table.py" "$SCR/lab.sqlite"
   ```
   Expected at `461580a` (check every line against D14's threshold table):
   ```text
   D4+D12 alone: 31 of 76, dev-eligible 8 of 10
   promoted only      0.80 behaviour 13 union 34 dev-eligible 10  newly: M0022, M0044, M0053
   promoted only      0.85 behaviour 13 union 34 dev-eligible 10  newly: M0022, M0044, M0053
   promoted only      0.90 behaviour 10 union 32 dev-eligible  8  newly: M0022
   promoted only      0.95 behaviour  7 union 31 dev-eligible  8  newly: -
   every dev variant  0.80 behaviour 29 union 45 dev-eligible 10  newly: H-P7A-F10, H-P7A-F4, H-P7A-F9, M0008, M0015, M0022, M0034, M0035, M0036, M0044, M0050, M0053, M0054, M0056
   every dev variant  0.85 behaviour 26 union 43 dev-eligible 10  newly: H-P7A-F4, H-P7A-F9, M0008, M0022, M0034, M0035, M0036, M0044, M0050, M0053, M0054, M0056
   every dev variant  0.90 behaviour 20 union 39 dev-eligible  9  newly: H-P7A-F4, M0022, M0034, M0035, M0036, M0044, M0050, M0056
   every dev variant  0.95 behaviour 14 union 35 dev-eligible  8  newly: H-P7A-F4, M0034, M0035, M0050
   ```
4. Write `$SCR/verify_kin.py` and run it — it calls the **implemented** `failed_kin` and `behavioural_kin` for every method, asserts `failed_kin == (D4 ∪ D12) ∪ twins` per method, and prints each twin sentence plus the totals:
   ```python
   """Verify D14 on a scratch copy of lab.sqlite: per-method behavioural twins, union counts, dev-eligible."""
   import sqlite3, sys, warnings
   warnings.simplefilter("error")
   from seer_engine.lab import hardgate, store

   conn = sqlite3.connect(sys.argv[1]); conn.row_factory = sqlite3.Row
   geo = hardgate.geometry(conn)
   ids = [r[0] for r in conn.execute("SELECT id FROM methods ORDER BY id")]
   status = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM methods")}
   dev_el = [m for m in ids if status[m] == "dev-eligible"]

   def old_kin(mid):
       row = store.get_method(conn, mid)
       kin = hardgate._lineage(conn, row)
       for ing in hardgate.ingredients(conn, mid):
           kin.add(ing); r = store.get_method(conn, ing)
           if r is not None: kin |= hardgate._lineage(conn, r)
       kin.discard(mid)
       return {m for m in kin if status.get(m) == "test-failed"}

   old_b, beh_b, new_b, newly = set(), set(), set(), []
   for m in ids:
       twins = hardgate.behavioural_kin(conn, m, geo)
       new = set(hardgate.failed_kin(conn, m))
       o = old_kin(m)
       assert new == o | {t.failed_id for t in twins}, m
       if o: old_b.add(m)
       if twins: beh_b.add(m)
       if new: new_b.add(m)
       if twins and not o: newly.append(m)
       if twins: print(f"{m:10s} {status[m]:12s} " + "; ".join(t.sentence() for t in twins))
   print(f"methods {len(ids)}; D4+D12 {len(old_b)}; behavioural {len(beh_b)}; union {len(new_b)}")
   print("dev-eligible blocked before", sum(m in old_b for m in dev_el), "after", sum(m in new_b for m in dev_el), "of", len(dev_el))
   print("newly linked:", ", ".join(newly))
   ```
   ```bash
   PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python "$SCR/verify_kin.py" "$SCR/lab.sqlite"
   ```
   Expected tail at `461580a`:
   ```text
   methods 76; D4+D12 31; behavioural 26; union 43
   dev-eligible blocked before 8 after 10 of 10
   newly linked: H-P7A-F4, H-P7A-F9, M0008, M0022, M0034, M0035, M0036, M0044, M0050, M0053, M0054, M0056
   ```
   and the line `H-P7A-F4   rejected     M0002 (F4-MOM12-N20-TREND moves with M0002's tested M0002-REL-85 at 0.97 residual correlation)`.
5. **If any number differs** (new methods, a new test-failed method, a new dev-eligible one): update every affected figure in D14 (method count, the four test-failed and their tested variants, the 42-curve count, the metric table if a non-momentum or momentum book moved its extreme, the threshold table, "refuses nobody new", the newly linked list) so the docstring states what the committed lab measures. If a newly dev-eligible method becomes refused **only** by D14, D14's "refuses nobody new" paragraph must say so by name instead. If `KIN_CORRELATION = 0.85` no longer sits in a gap between the highest non-momentum and lowest momentum book, stop and report — that is a re-decision, not an update. If nothing differs, leave D14 as written.

### Step 14: Verification on the worktree (before the completion step merges)
Run the commands in **Verification** below, all of them. Then the completion step merges `feature/hardgate-behavioural-kin` to main and pushes (it owns that; this phase does not merge).

### Step 15 (LAST — after the code is merged to main and pushed): re-file M0060/M0062 and record why
Runs on the **MAIN checkout** `/home/miftah/seer`, never the worktree. Order matters: the code that makes the family irrelevant to the gate lands first, then the data.

1. Sync main and confirm the merge is there:
   ```bash
   git -C /home/miftah/seer pull --rebase origin main
   git -C /home/miftah/seer log -1 --format=%h -- engine/src/seer_engine/lab/hardgate.py
   grep -n "KIN_CORRELATION = 0.85" /home/miftah/seer/engine/src/seer_engine/lab/hardgate.py
   git -C /home/miftah/seer status --short
   ```
   `status --short` must show nothing staged and `lab/lab.sqlite` / `web/data/lab.json` unmodified (the untracked zip is the owner's; leave it). If `lab/lab.sqlite` is modified by a live Sera session, do not proceed: wait for its commit, pull, then continue.
2. Read and re-file, inside the write lock (no trigger guards `family`: `methods_hypothesis_frozen` guards only `hypothesis`, `methods_status_forward` only `status`, and `update_method` allows `family`):
   ```bash
   cd /home/miftah/seer && SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
   from seer_engine.lab import store

   conn = store.connect(store.DB_PATH)
   store.begin_immediate(conn)
   try:
       for mid in ("M0060", "M0062"):
           row = store.get_method(conn, mid)
           print(mid, row["status"], row["family"], row["parent_id"])
           if row["status"] == "idea":
               store.update_method(conn, mid, family="p7a-f4")
               print(f"  {mid}: family -> p7a-f4 (parent {row['parent_id']} unchanged)")
           else:
               print(f"  {mid}: left alone -- status is {row['status']!r}, not 'idea'")
       conn.commit()
   except Exception:
       conn.rollback()
       raise
   for mid in ("M0060", "M0062"):
       r = store.get_method(conn, mid)
       print("after:", mid, r["status"], r["family"], r["parent_id"])
   conn.close()
   PY
   ```
   Expected (if both are still ideas): `M0060 idea stock-low-volume-momentum M0057` → `p7a-f4`; `M0062 idea stock-liquidity-tilt M0058` → `p7a-f4`; parents unchanged.
3. Record one insight (plain words — the owner is not a trader; no code, ids of rules or digests). The body below assumes both rows were re-filed; if one was left alone, replace its sentence with "<the idea's plain name> had already started running, so its family was left as the method file set it." — `--method` is omitted (the insight covers two methods; `--method` takes one):
   ```bash
   cd /home/miftah/seer && SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab insight --kind observation \
     --title "Two momentum ideas now filed as momentum, and the gate now reads how a strategy moves" \
     --body "The two queued ideas \"quiet twelve-month winners\" and \"momentum among the most heavily traded members\" both pick stocks by how much they rose over the past twelve months. That is plain momentum, so their family now says so: they are filed with the lab's plain-momentum family, the same one as the original twelve-month momentum test, instead of the new names they were queued under. Their parents are unchanged. This changes no verdict today: neither idea has run yet, and nothing in that family has failed its real test. What closes the hole Sera found is a change to the gate itself. It now compares how a strategy's month-to-month results move, once the market's own ups and downs are taken out, with the strategies that already failed their one real test; a strategy that moves almost in step with one of them (a match of 0.85 or more on a scale where 1 is identical) counts as its relative, whatever it is called. Measured on the lab today, the original twelve-month momentum strategy matches one failed strategy at 0.97, while unrelated ideas such as sector rotation, low-volatility stocks or company fundamentals stay well below the line. So a filing name can no longer let a momentum strategy slip past by accident. One thing to keep: when one of these ideas is written up and run, the runner copies the family from the method file, so the file must keep the plain-momentum family."
   ```
   It prints the new insight id.
4. Stage under the write lock and verify exactly what is staged:
   ```bash
   cd /home/miftah/seer && SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage
   git -C /home/miftah/seer diff --cached --name-only
   ```
   `lab stage` prints `staged .../lab/lab.sqlite` and `staged .../web/data/lab.json`; `diff --cached --name-only` must list exactly `lab/lab.sqlite` and `web/data/lab.json`. If anything else is staged (a Sera session's work), do not commit it — the pathspec below commits only these two.
5. Commit by pathspec only (never `git add -A` / `git add .`), then push:
   ```bash
   git -C /home/miftah/seer commit -m "lab: file M0060 and M0062 under plain momentum (p7a-f4); insight on D14

   Both queued ideas rank on plain twelve-month momentum, so their family says
   so (skill rule: name the family by what it ranks on). No gate verdict moves:
   neither has a curve and p7a-f4 holds no test-failed method. hardgate D14 now
   links momentum books by behaviour, so the filing no longer decides kin.

   Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" -- lab/lab.sqlite web/data/lab.json
   git -C /home/miftah/seer push origin main
   ```
   If the push is rejected because Sera committed meanwhile: `git -C /home/miftah/seer pull --rebase origin main`, then push. If that rebase conflicts on `lab/lab.sqlite` (a binary file), never merge it by hand. Instead: `git -C /home/miftah/seer rebase --abort`; check `git -C /home/miftah/seer status --short` shows nothing but the owner's untracked zip (if anything else is there, stop and report); then `git -C /home/miftah/seer reset --hard origin/main` — this drops only this step's own local db commit — and re-run sub-steps 2–5 on the fresh db. The re-file is idempotent; before re-adding the insight, read `SELECT id, title FROM insights ORDER BY id DESC LIMIT 3` (read-only connection) to be sure it is not already recorded.
6. Confirm: `git -C /home/miftah/seer log -1 --stat` shows only the two files; `git -C /home/miftah/seer status --short` is clean apart from the untracked zip.

## Verification

**Build/lint:** `cd $W/engine && /home/miftah/seer/engine/.venv/bin/ruff check src tests` — must print `All checks passed!`.
**Tests (full suite):** `cd $W/engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q` — green. Focused: `PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q -n0 -W error tests/test_lab_hardgate.py tests/test_lab_prereg.py tests/test_lab_status.py tests/test_lab_test_window.py tests/test_lab_walkforward.py`.
**walkforward.py untouched:** `git -C $W diff --stat origin/main -- engine/src/seer_engine/lab/walkforward.py` prints nothing.
**No override path:** `grep -nE "force|environ|getenv|skip_gate" $W/engine/src/seer_engine/lab/hardgate.py` prints nothing; `grep -n override $W/engine/src/seer_engine/lab/hardgate.py | grep -v "no override"` prints nothing.
**`lab status` on the committed lab** (`--db` is a global `lab` option, before the subcommand; `SEER_LAB_DB` also works):
```bash
SCR=/tmp/claude-1000/-home-miftah-seer/hgbk-remeasure; mkdir -p "$SCR"
git -C /home/miftah/seer show origin/main:lab/lab.sqlite > "$SCR/status.sqlite"
cd $W && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db "$SCR/status.sqlite" status | grep -A1 "Promotable now"
```
must print `  Promotable now (`lab promote` would take these):` followed by `    (none)`.
**`lab walkforward` on the committed lab:**
```bash
cd $W && PYTHONPATH=$W/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --db "$SCR/status.sqlite" walkforward | tail -4
```
must run to completion and print `No buy signal. Survivorship-free price history is not worth buying yet.` (no traceback; no row reads `kin unknown` on the committed lab, which has 0 price mismatches).
**D14 numbers:** Step 13's `verify_kin.py` assertion passes for every method, and its totals equal D14's tables.
**Manual check:** read the D14 section once in the file for alignment of the two RST tables and for the words banned by `test_there_is_no_override`.
**Exit criteria:** suite green; `walkforward.py` diff empty; `Promotable now: (none)`; `lab walkforward` prints `No buy signal`; `failed_kin` on the committed lab equals D14's table; D14 present; skill updated; and (after merge) M0060/M0062 handled on main with one insight, committed by pathspec through `lab stage`, pushed.

## Handoffs

- **Owner (not this phase, not any phase): `walkforward.py`.** `BUY_CONDITIONS[1]` ("no kin has test-failed (family union ancestors)") and the `buy_signal` docstring (`walkforward.py:282-289`) now under-describe kin further (D12 and D14). D13 records that; editing them is the owner's call.
- **Future idea filing (process, Sera children).** When M0060 or M0062 is written up as a method file, the file's `family` must be `p7a-f4`; `runner.py:446-452` overwrites the idea row's family from the file when it runs. The insight and the skill text (Step 12a) say so; nothing in code enforces it, and nothing needs to — D14 links the book by behaviour either way.
- **Possible follow-up (unscheduled):** the web app's method pages describe kin from the snapshot (`web/data/lab.json`) only through text the engine already writes; no web change is needed for this phase. If a page hard-codes the phrase "family, ancestry or blend ingredient", that is a web edit for another task.

## Rollback

Code: revert the merge commit of `feature/hardgate-behavioural-kin` on main (`git revert -m 1 <merge sha>`); that restores `hardgate.py`, the tests, `commands/lab.py`, `prereg.py`, `runner.py` and the skill together — they only make sense together. Data: separately `git revert <db commit sha>` on main for `lab/lab.sqlite` + `web/data/lab.json` (insights are append-only, so the insight is removed by reverting the file, never by a DELETE). The two are independent: reverting the code alone leaves M0060/M0062 under `p7a-f4`, which is harmless (p7a-f4 holds no test-failed method).
