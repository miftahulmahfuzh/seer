# Phase 1: The kin gate reads the book that would actually be tested

**Plan set:** `KIN_GATE_PER_VARIANT_PLAN.md`
**Analysis:** `docs/analyzer/20261013-102209-K2M7_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4 — the kin gate stops refusing a method for a variant no look would
ever land on, and says so on the record as a dated owner revision
**Depends on:** none (single-phase set)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (plus two documents)

---

## Goal

After this phase `hardgate.failed_kin` answers about **the book that would actually be tested** —
the variant `lab promote` would pre-register, together with every variant a fold's training slice
picked — instead of about every dev variant a method happens to carry. Lineage and ingredients
become a proxy that defers to that direct reading when the reading can honestly be made, and block
exactly as they do today when it cannot. `KIN_CORRELATION` moves 0.85 → 0.90. The rule, its
measurement and the premise it retires are written into `hardgate.py`'s decision record as `(D16)`
and into the design doc as a dated owner revision.

---

## READ THIS FIRST — the analysis's M4 is wrong, and the exit criteria change

The plan index's exit criterion 2 says *"M0020 and M0024 no longer blocked by kin"*. **M0020 is not
freed.** Measured during planning, read-only, on a copy of `lab/lab.sqlite` at
`2c8c9669ad76642741342f8272a629e125c795f9dd0ab09300f44721dc580086` (the committed hash, unchanged):

| method | its promoted variant | that variant's own max residual correlation |
|---|---|---|
| M0020 | `M0020-W-NOSTOP` | **0.939** (vs M0021's tested book; 0.933 vs M0029) |
| M0030 | `M0030-C50T` | **0.962** |
| M0053 | `M0053-TOTON30-TV16` | 0.879 — clean at 0.90 |
| M0024 | `M0024-SAME-N20-BLEND-RM` | 0.889 — clean at 0.90, a twin at 0.85 |

The analysis's M4 table read "clean" for M0020, M0030 and M0053 because it asked
`behavioural_kin`, which reports **only the best-correlated variant per failed book**. For M0020
that best variant is `M0020-W-S20` at 0.940 — and `M0020-W-NOSTOP` sits 0.001 behind it at 0.939,
a twin by any reading. *Not being named by `behavioural_kin` is not the same as being clean*, and
the implementation below must therefore compute a **per-book** correlation rather than test
membership in `behavioural_kin`'s output. That is the single most important correctness point in
this phase.

**What the change actually does to the committed lab**, measured by running `lab walkforward` over
all 81 methods before and after (prototype rule injected, database copied, nothing written):

```
32c32
<   M0024   2 of 4  yes  −4.7%   kin already failed the test window (M0021, M0022, M0029)
>   M0024   2 of 4  yes  −4.7%   fails the folds: 2 of 4 folds
46c46
<   M0053   3 of 4  yes  +0.5%   kin already failed the test window (M0002, M0021, M0022, M0029)
>   M0053   3 of 4  yes  +0.5%   kin already failed the test window (M0002)
```

Two rows change and nothing else. `24 of 81 methods beat the benchmark in a majority of folds.`
and `No buy signal.` are identical before and after. **Zero methods become promotable**: M0024 is
freed of kin and then fails the fold majority it was already failing, one condition later in the
same report. M0053's kin set shrinks to M0002 alone (the threshold move drops M0021/M0022/M0029,
which it reached at 0.864–0.889) and it stays blocked because all four of its fold picks are
`M0053-TOTON20-NOBRAKE` at 0.922 — the fold-pick condition doing exactly the job it exists for.

This is a modest, honest result and the write-up must say so plainly rather than quote the
three-method estimate the owner was given.

---

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `hardgate.provenance_kin(conn, method_id) -> tuple[str, ...]` (`hardgate.py`, new, before
  `failed_kin`) — the (D4)+(D12) proxy arm, factored out of `failed_kin` unchanged.
- `hardgate.tested_books(conn, method_id, geo=None) -> tuple[str, ...] | None` (`hardgate.py`,
  new) — the promoted variant plus every fold pick; `None` when there is no readable book.
- `hardgate.direct_kin(conn, method_id, failed_ids, geo=None) -> tuple[Twin, ...] | None`
  (`hardgate.py`, new) — the per-book reading. `None` = **not measured**; `()` = measurably clean;
  non-empty = a book moves with a failed tested book.
**Signature changes:** none. `failed_kin(conn, method_id) -> tuple[str, ...]` keeps its signature,
its return type and its `store.LabError` surface exactly.
**Constant changes:** `KIN_CORRELATION` 0.85 -> 0.90 (`hardgate.py:531`).
**Behaviour changes:** `failed_kin`'s answer is now always a **subset** of today's answer, for the
same database. It never blocks anything it did not block before, and it never raises where it did
not raise before. `check`'s kin refusal message gains one sentence naming the blocking book.
**Requires (from earlier phases):** nothing — single-phase set.
**Leaves alone (owned by nobody else, and deliberately untouched):** `walkforward.py` (`(D13)`:
the signal's kin condition widens through its caller), `runner.py`, `commands/lab.py`,
`prereg.py`, `store.py`, every `lab/methods/*` file, `lab/lab.sqlite`, `web/`, every recorded row,
every written `docs/lab/prereg/*.md`.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/hardgate.py` | modify | `KIN_CORRELATION` 0.85→0.90 (`:531`); `(D16)` appended to the module docstring (after `:479`); `provenance_kin`, `tested_books`, `direct_kin` added before `failed_kin` (`:1142`); `failed_kin` rewritten; one sentence added to `check`'s kin refusal (`:1527`) |
| `engine/tests/test_lab_hardgate.py` | modify | one existing assertion updated (`:1004`); a new `(D16)` section of 8 tests appended |
| `docs/plans/2026-10-03-seer-design.md` | modify | `## 16. Revision 2026-10-13 (owner)` appended after `## 15.` (file currently ends at line 480); nothing above it touched |
| `docs/backtests/2026-10-13-kin-gate-per-variant.md` | create | the before/after table and the residual risk |

---

## Implementation Steps

### Step 1: Raise the behavioural threshold to 0.90

**File:** `engine/src/seer_engine/lab/hardgate.py:526-531`
**Change:** replace the constant and its comment. The original measurement sentences are preserved
verbatim; the revision is appended to them, in the style every other constant here uses.
**Code:**

```python
#: The residual correlation at or above which a book is kin of a test-failed one by behaviour
#: (D14). Measured on the committed lab: the highest any unrelated book reaches against a failed
#: tested variant is 0.80 (``H-P7A-F10``, index ETFs), the lowest any momentum book in another
#: family's clothes reaches is 0.85 (M0008), and the plain twelve-month momentum book
#: ``H-P7A-F4`` reads 0.97. The bar sat at 0.85 in that gap from 2026-10-09.
#:
#: **Raised to 0.90 by the owner on 2026-10-13 (D16).** Measured before the decision: of the ten
#: dev-eligible methods the gate blocked, the move admits exactly one book that 0.85 refused --
#: M0024's ``SAME-N20-BLEND-RM`` at 0.889 -- and M0024's edge over the benchmark in the
#: highest-coverage era is **-4.7%**. The owner was told that and chose it anyway. It also drops
#: M0053's links to M0021 (0.864), M0022 (0.889) and M0029 (0.867) while leaving its link to
#: M0002 (0.922) standing. It is not lowered from inside the code.
KIN_CORRELATION = 0.90
```

**Impact:** `behavioural_kin` links fewer books. On the committed lab this changes exactly one
printed row (M0053's kin list) and frees exactly one method (M0024) once Step 4 lands. One existing
test asserts the old value and is updated in Step 7.

---

### Step 2: Add `provenance_kin` — the proxy arm, named

**File:** `engine/src/seer_engine/lab/hardgate.py` — insert after `behavioural_kin` ends
(`:1139`, the `return tuple(twins)` line) and before `def failed_kin` (`:1142`).
**Change:** the lineage+ingredients half of today's `failed_kin`, lifted out verbatim so the two
arms can be spoken about separately — by `(D16)`, by `failed_kin`, and by a test. No behaviour
changes: `failed_kin` calls it and gets the same set it computed inline before.
**Code:**

```python
def provenance_kin(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """The test-failed methods ``method_id``'s **provenance** names: (D4) union (D12).

    The ``family`` string, the transitive ancestors through ``parent_id``, every ingredient -- a
    lab method whose engine one of its dev variants runs -- and each ingredient's own family and
    ancestry, filtered to the ones that read ``test-failed``. The method itself is discarded.

    This is one of the two readings ``failed_kin`` makes, and it is named here because (D16) turns
    it into a **proxy**: provenance is evidence that two books are the same bet, and the residual
    correlation of the book that would actually be tested is the measurement of it. The proxy
    stands wherever the measurement cannot be made. Callers ask ``failed_kin``; this exists so the
    decision record and the tests can say which arm spoke.
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
    if not kin:
        return ()

    ids = sorted(kin)
    marks = ", ".join("?" for _ in ids)
    return tuple(sorted(
        str(r["id"])
        for r in conn.execute(
            f"SELECT id FROM methods WHERE id IN ({marks}) AND status = 'test-failed'",
            tuple(ids),
        )
    ))
```

**Impact:** none on its own. `failed_kin` is rewritten in Step 4 to call it.

---

### Step 3: Add `tested_books` and `direct_kin` — the reading, and the two-case answer

**File:** `engine/src/seer_engine/lab/hardgate.py` — immediately after `provenance_kin`.
**Change:** `tested_books` names every variant a look could actually land on. `direct_kin` reads
those books against the failed books the proxy named, and **distinguishes "measured and clean"
from "could not look"** — the conflation that today's `behavioural_kin` hides behind a bare `()`.
**Code:**

```python
def tested_books(
    conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None
) -> tuple[str, ...] | None:
    """Every variant a look could actually land on, sorted; ``None`` when there is no such book.

    Two variants, and only two, can ever carry the lab's one look (D16):

    - the variant ``lab promote`` would pre-register -- ``promoted_variant``, which is
      ``store.best_dev_eligible``, the very row ``prereg.promote_method`` reads; and
    - every variant a fold's training slice picked, because the fold record that makes the method
      *eligible* is the record those picks earned. (D12) said it first: "every variant is a
      candidate in every fold's pick". A method whose promoted variant is clean but whose majority
      was won by a twin would otherwise launder a disproven book into a fresh look -- which is
      precisely what the gate exists to stop. Measured on the committed lab: M0053's promoted
      variant never won a single fold, and all four of its picks are ``M0053-TOTON20-NOBRAKE``,
      which moves with M0002's tested book at 0.922.

    ``None`` -- there is no book to read, so the caller must fail closed -- when nothing would be
    pre-registered (``promoted_variant`` is None: M0019 and M0044 on the committed lab today) or
    when a fold named no pick at all. Raises ``store.LabError`` from ``fold_record`` when the
    record cannot be built on one price history (D10); ``failed_kin`` catches that and falls back
    to provenance, which is the same fail-closed answer by another road.
    """
    candidate = promoted_variant(conn, method_id)
    if candidate is None:
        return None
    record = fold_record(conn, method_id, geo)
    books = {candidate}
    for pick in record.picks:
        if pick.picked is None:
            return None
        books.add(str(pick.picked))
    return tuple(sorted(books))


def direct_kin(
    conn: sqlite3.Connection,
    method_id: str,
    failed_ids: Sequence[str],
    geo: Geometry | None = None,
) -> tuple[Twin, ...] | None:
    """What ``tested_books`` read against ``failed_ids``; ``None`` when nothing could be read.

    **Three answers, and the difference between the last two is the whole of (D16):**

    - ``None`` -- **not measured.** There is no book to read (``tested_books``), a book has no dev
      curve, a book's or a failed book's residual cannot be computed (a flat curve), one of
      ``failed_ids`` spent no look that left a comparable curve, or a pair shares fewer than
      ``MIN_KIN_MONTHS`` months. The caller must fail closed: provenance blocks exactly as it did
      before this decision.
    - ``()`` -- **measured, and clean.** Every book was compared with every failed book the proxy
      named, and none reached ``KIN_CORRELATION``. This is the only answer that frees a method.
    - a non-empty tuple -- **measured, and kin.** One ``Twin`` per failed book that some book moves
      with, naming the book, the failed book's tested variant and the correlation.

    ``behavioural_kin`` cannot answer this question, and a membership test over its output is a
    bug: it reports the single best-correlated variant per failed book, so a book 0.001 behind a
    sibling is simply not named. M0020's ``W-NOSTOP`` reads 0.939 against M0021's tested book
    while its sibling ``W-S20`` reads 0.940 -- the first is a twin and only the second is named.
    Every book is therefore correlated here in its own right.

    Raises ``store.LabError`` (D10) when a book's prices or a failed tested book's prices are not
    the benchmark's or are unknown -- fail closed, never "no twin", exactly as ``behavioural_kin``
    does. ``failed_kin`` catches it and leaves provenance standing.
    """
    geo = geometry(conn) if geo is None else geo
    books = tested_books(conn, method_id, geo)
    if books is None:
        return None

    rows = {str(r["candidate_id"]): r for r in _dev_curves(conn, method_id)}
    if any(book not in rows for book in books):
        return None
    tested = dict(_tested_curves(conn, method_id))
    wanted = sorted(set(failed_ids))
    if any(failed_id not in tested for failed_id in wanted):
        return None

    problems = mismatches(
        conn, geo.bench_n, [*(rows[b] for b in books), *(tested[f] for f in wanted)]
    )
    if problems:
        raise store.LabError(
            f"{method_id}'s books cannot be compared with the test-failed ones: "
            f"{describe(problems)}. The hard gate compares two curves only when both were "
            f"measured on the benchmark's prices (D10, D16), and fails closed when either side's "
            f"prices differ or are unknown. There is no override"
        )

    bench = monthly_returns(list(geo.bench))

    def residual_of(row: sqlite3.Row) -> dict[Month, float] | None:
        curve = _curve_of(row)
        return residual(monthly_returns(curve, trial_deposits(conn, row, curve)), bench)

    mine: dict[str, dict[Month, float]] = {}
    for book in books:
        series = residual_of(rows[book])
        if series is None:
            return None
        mine[book] = series

    twins: list[Twin] = []
    for failed_id in wanted:
        theirs = residual_of(tested[failed_id])
        if theirs is None:
            return None
        best: Twin | None = None
        for book, series in mine.items():
            rho = correlation(series, theirs)
            if rho is None:
                return None
            if rho < KIN_CORRELATION:
                continue
            if best is None or rho > best.correlation:
                best = Twin(failed_id, book, str(tested[failed_id]["candidate_id"]), rho)
        if best is not None:
            twins.append(best)
    return tuple(twins)
```

**Impact:** nothing calls these yet. Note `Sequence` is already imported (`hardgate.py:488`) and
`Month`, `Twin`, `mismatches`, `describe`, `residual`, `correlation`, `monthly_returns`,
`trial_deposits`, `_curve_of`, `_dev_curves`, `_tested_curves` are all defined above the insertion
point.

---

### Step 4: Rewrite `failed_kin` so the proxy defers to the reading

**File:** `engine/src/seer_engine/lab/hardgate.py:1142-1185` (the whole function, docstring
included).
**Change:** the body becomes "today's answer, then narrowed to nothing when the direct reading is
made and comes back clean". The signature, the return type and the `store.LabError` surface are
unchanged, because all five call sites depend on all three.
**Code:**

```python
def failed_kin(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """Every method in ``method_id``'s kin that reads ``test-failed``; ``()`` when clean.

    Two readings, and the second governs (D16):

    - **The proxy.** ``provenance_kin`` -- the ``family`` string union the transitive ancestors
      through ``parent_id`` (D4), union every ingredient and its own family and ancestry (D12) --
      union every test-failed method some dev variant moves with at ``KIN_CORRELATION`` or more
      (D14, ``behavioural_kin``). This is the answer this function gave before 2026-10-13, and it
      is still the answer it gives whenever the reading below cannot be made.
    - **The reading.** ``direct_kin`` over ``tested_books``: the variant ``lab promote`` would
      pre-register, and every variant a fold's training slice picked. **When that reading is made
      and comes back clean, the proxy defers and this returns ``()``** -- a method is not refused
      for a sibling variant no look would ever land on. When it comes back dirty, or cannot be
      made at all, the proxy's answer stands whole.

    So the answer is always a **subset** of the pre-2026-10-13 answer: this rule frees methods and
    never blocks one it did not block before.

    **Not measured is not clean.** A reading that could not be taken -- no variant to
    pre-register, a fold with no pick, a failed book that left no comparable curve, a flat series,
    too few shared months -- returns ``None`` from ``direct_kin`` and blocks exactly as before. A
    gate that reads "clean" because it could not look is the one failure mode worse than a gate
    that is too strict.

    Raises ``store.LabError`` when the behavioural comparison cannot be made honestly -- no
    benchmark, or a curve on other or unknown prices (D10) -- rather than reading "clean". That
    refusal comes from ``behavioural_kin``, which runs first and is unchanged; a refusal raised
    inside the narrowing step is caught and fails closed instead, so this function raises in
    exactly the cases it raised in before.

    This is the one definition of kin. ``prereg.family_text``, ``lab test``'s note and ``lab
    walkforward``'s buy signal all call it, so they cannot disagree with the gate (D9, D13, D16).
    """
    row = store.get_method(conn, method_id)
    if row is None:
        raise store.LabError(f"no method {method_id}")

    found = set(provenance_kin(conn, method_id))
    found.update(t.failed_id for t in behavioural_kin(conn, method_id))
    if not found:
        return ()
    whole = tuple(sorted(found))

    try:
        reading = direct_kin(conn, method_id, whole)
    except store.LabError:
        return whole
    if reading is None or reading:
        return whole
    return ()
```

**Impact:** this is the phase. On the committed lab it frees M0024 and changes no other method's
kin answer. All five call sites — `check` (`:1527`), `family_state` (`:1194`),
`prereg.family_text` (`prereg.py:567`), `runner.kin_note` (`runner.py:907`) and the buy signal
(`commands/lab.py:2429`) — inherit it without an edit, which is `(D9)`'s single-definition
property working as intended.

---

### Step 5: Name the blocking book in `check`'s refusal

**File:** `engine/src/seer_engine/lab/hardgate.py:1527-1547` (the `bad = failed_kin(...)` block at
the end of `check`).
**Change:** when the direct reading was made and found twins, the message names the book the look
would actually be spent on, and the twins it prints are those books' twins rather than whichever
sibling variant happened to correlate best. When the reading could not be made, the message is
byte-identical to today's.
**Code:**

```python
    bad = failed_kin(conn, method_id)
    if bad:
        try:
            reading = direct_kin(conn, method_id, bad, geo)
        except store.LabError:
            reading = None
        twins = reading if reading else behavioural_kin(conn, method_id, geo)
        moves = (
            ""
            if not twins
            else f" By behaviour (D14): {'; '.join(t.sentence() for t in twins)} -- at or above "
            f"{KIN_CORRELATION:.2f}, what is left of a book's monthly return once the market's "
            f"share is taken out moves with a book that has already lost its look, and a new "
            f"name does not make it a new book."
        )
        books = (
            ""
            if not reading
            else f" {', '.join(sorted({t.candidate_id for t in reading}))} is a book `lab test` "
            f"would spend its look on -- the variant `lab promote` would pre-register, or one a "
            f"fold's training slice picked (D16)."
        )
        raise store.LabError(
            f"{method_id} is not promoted: {', '.join(bad)} already read test-failed, and "
            f"{'they are' if len(bad) > 1 else 'it is'} kin -- same family ({row['family']!r}), "
            f"an ancestor through parent_id, an ingredient one of its variants runs (or that "
            f"ingredient's family or ancestry, D12), or a tested book one of its variants moves "
            f"with (D14).{moves}{books} A new variant of a family that has been disproven out of "
            f"sample is not a fresh candidate, and neither is a blend with a disproven engine in "
            f"it. Nothing was written and no status moved. There is no override -- if this "
            f"family deserves another look, that is an argued change to the rule, in git"
        )
```

**Impact:** `test_a_book_that_moves_with_a_failed_tested_book_is_kin_under_any_name` (`:1008`)
asserts on this message and stays green — its fixture has no promoted variant, so `reading` is
`None` and the old text is produced unchanged. Verified by running the suite with this exact code
installed.

---

### Step 6: Record the decision as `(D16)`

**File:** `engine/src/seer_engine/lab/hardgate.py` — insert after line 479
(`` ``check`` is not touched by any of this and keeps its present behaviour exactly.``) and before
the closing `"""` on line 480. Leave `(D1)`–`(D15)` untouched: `(D12)`'s paragraph at `:292-299`
stays **verbatim**; `(D16)` retires its expired premise on the record rather than editing it away.
**Change:** a new numbered section in the module docstring's established prose style (bold
question-and-answer heading, then the argument, then the measurement).
**Code:**

```
**(D16) Whose behaviour does (K) read -- every dev variant, or the book that would actually be
tested? -- the book that would actually be tested: the variant ``lab promote`` would
pre-register, and every variant a fold's training slice picked. Lineage and ingredients become a
proxy that defers to that reading when it can be taken, and block exactly as before when it
cannot. ``KIN_CORRELATION`` rises 0.85 -> 0.90. Decided by the owner, 2026-10-13.**

The lab had reached a state where (K) refused every method it held: 81 recorded methods, 66 not
dev-eligible, 5 failing the folds, and all 10 of the rest blocked by kin. ``lab walkforward``
printed "No buy signal" with nothing promotable behind it. The owner asked whether the kin
question could be made less strict, and the measurement said the threshold was not the problem:
the correlations run 0.889 to 0.983, which are the same books under different ids. The **scope**
was the problem. A test look is spent on **one variant**, and (K) refused the whole method when
**any** of its dev variants was a twin.

**What (D12) said about exactly this, and which of its reasons survive.** (D12) above argued
"every dev variant and not only the promoted one" on three grounds:

- *"The cost is identical today."* **This premise has expired, and 2026-10-13 is the date it
  did.** It is now false: at method granularity the gate blocks M0024 and M0053's whole kin set;
  at book granularity it frees M0024 and narrows M0053's. The sentence stays where it is because
  it was true when it was written and this file is a record; this paragraph is its retirement.
- *"Every variant is a candidate in every fold's pick."* **Still true, still load-bearing, and it
  is precisely why ``tested_books`` includes the fold picks.** Without that half, the naive
  per-variant rule frees M0053 -- whose promoted variant ``TOTON30-TV16`` never won a single fold,
  while all four picks are ``TOTON20-NOBRAKE``, which moves with M0002's tested book at 0.922 --
  and M0030, whose one winning fold was won by ``SAT100`` at 0.924. Admitting a method on a record
  its twin earned is laundering a disproven book into a fresh look, which is the one thing this
  gate exists to stop.
- *"Kin is a statement about a method, which has no single variant."* True of ``family_state``,
  ``prereg``'s line and the buy signal, and the honest answer for all three is now "the kin state
  of the book that would be tested" -- which is what those three are really asking, since the
  look, the pre-registration and the money all land on one variant. A method with no variant to
  pre-register has no such book, and the answer there is to block (below).

**Not measured is not clean.** ``behavioural_kin`` returns ``()`` for two different situations:
it compared the curves and found nothing, or it could not compare at all -- no failed method has a
tested curve, a series is flat, fewer than ``MIN_KIN_MONTHS`` months are shared. Under the old
per-method rule the difference was invisible, because provenance blocked either way. Under this
one it decides the answer, so ``direct_kin`` returns three things instead of two: ``None`` for
*not measured*, ``()`` for *measured and clean*, and a tuple of ``Twin`` for *measured and kin*.
Only the middle one frees a method. Provenance blocks on ``None`` exactly as it did before this
decision, and on the (D10) price refusal, and when ``promoted_variant`` names nothing -- M0019 and
M0044 today. A gate that reads "clean" because it could not look is worse than a gate that is too
strict, and this is the sentence that says so.

**A membership test over ``behavioural_kin`` would be a bug.** That function names the single
best-correlated variant per failed book, so "the promoted variant is not among the twins" does not
mean it is clean. M0020's ``W-NOSTOP`` reads **0.939** against M0021's tested book; it is not
named only because its sibling ``W-S20`` reads 0.940. ``direct_kin`` therefore correlates every
book in its own right. The first reading of this change, taken that way, reported M0020, M0030 and
M0053's promoted variants "clean"; all three are twins or rest on twins, and the corrected
measurement is below.

**0.85 -> 0.90.** The threshold was never mis-calibrated -- 0.85 sits in a measured gap and (D14)
records it. It moves anyway, by owner decision, and what it buys is small and is stated rather
than dressed up: it admits exactly one book that 0.85 refused, M0024's ``SAME-N20-BLEND-RM`` at
0.889, and **M0024's edge over the benchmark across 2009-2015 is -4.7%**. It also drops M0053's
links to M0021, M0022 and M0029 while leaving M0002's 0.922 standing. The owner was shown both
numbers before choosing.

**Measured on the committed lab, read-only, 2026-10-13.** Per-book maximum residual correlation
against the failed tested books, beside what each method's fold record rests on:

====================  =============================  ==========  ==================  ============
method                promoted variant               its max     fold picks          after (D16)
====================  =============================  ==========  ==================  ============
M0007                 ``N20-RAW``                    0.968       ``N20-RAW`` x4      blocked
M0011                 ``RAW20-TV14-N21``             0.983       own x4              blocked
M0019                 none                           --          --                  blocked
M0020                 ``W-NOSTOP``                   **0.939**   ``W-NOSTOP`` x4     blocked
M0024                 ``SAME-N20-BLEND-RM``          0.889       ``RANKSUM`` x4      **freed**
M0028                 ``BLEND-RM``                   0.945       own x4              blocked
M0030                 ``C50T``                       0.962       ``SAT100`` won 1    blocked
M0033                 ``TV22-N21``                   0.960       own x4              blocked
M0044                 none                           --          --                  blocked
M0053                 ``TOTON30-TV16``               0.879       ``NOBRAKE`` x4      blocked
====================  =============================  ==========  ==================  ============

**What it costs and what it buys.** One method's kin verdict changes. ``lab walkforward`` prints
M0024 as "fails the folds: 2 of 4 folds" where it printed "kin already failed the test window",
and M0053's kin list shrinks to M0002. **Nothing becomes promotable**, no signal fires, and the
report's "24 of 81 methods beat the benchmark in a majority of folds" is unchanged. The owner was
told this change would free three methods; measured properly it frees one, and that one then fails
the fold majority. The gain is not in today's roster but in the rule: the gate no longer refuses a
book for the company its siblings keep.

**(D9) and (D13) still hold.** The new logic lives **inside** ``failed_kin``; there is no
per-variant sibling function for some callers to use and others to miss. ``hardgate.check``,
``family_state``, ``prereg.family_text``, ``runner.kin_note`` and ``lab walkforward``'s buy signal
all read the same answer, and the answer they now read is about the book that would be tested.
``walkforward.py`` is not edited: ``BUY_CONDITIONS`` and the ``buy_signal`` docstring still say
"family union ancestors", and ``prereg.family_text``'s docstring still describes the four arms
without this one -- both now under-describe the rule they are handed, exactly as (D13) recorded
for (D12) and (D14), and both remain the owner's to edit.

**The residual risk, stated.** Choosing the one uncorrelated variant out of eight is itself a
selection. The lab's N policy prices the variant search in the luck test, but it does not make
that cost disappear, and a method freed here has been freed on the strength of one book's
correlation rather than on the family's record. That is why the fold picks are in the reading and
why the threshold stayed a measured number rather than becoming a dial.
```

**Impact:** `test_the_module_records_the_variant_and_ingredient_decisions` (`:161`) keeps passing
— it asserts `(D11)`, `(D12)`, `(D13)`, `M0044-TV14-N21` and `BLEND-RM` are present, and none of
them is removed. A new test asserts `(D16)`'s own markers.

---

### Step 7: Update the one existing assertion this change retires

**File:** `engine/tests/test_lab_hardgate.py:998-1006`
**Change:** `test_the_module_records_the_behavioural_kin_decision` asserts the old threshold. It is
the **only** assertion in the whole 4,725-test suite that this change breaks — measured, by
running the full suite with the new rule and the new `check` installed over `hardgate`:
`1 failed, 4724 passed, 3 skipped`. Update it; do not delete it.
**Code:**

```python
def test_the_module_records_the_behavioural_kin_decision():
    """Insight 92: kin follows what a book does, argued and measured in the docstring (D14)."""
    doc = hardgate.__doc__ or ""
    assert "(D14)" in doc
    assert "F4-MOM12-N20-TREND" in doc   # the plain momentum book it catches, named
    assert "M0060" in doc and "M0062" in doc
    assert hardgate.KIN_CORRELATION == 0.90   # 0.85 until (D16) raised it, 2026-10-13
    assert hardgate.MIN_KIN_MONTHS == 36
```

**Impact:** none beyond the value. The (D14) facts it pins are untouched by this phase.

**Why nothing else in the file has to move, verified rather than assumed.** Every other kin test
keeps asserting what it asserted, and what it asserts is now a *stronger* statement: provenance
blocks when the book cannot be read. Two mechanisms do that work, and the second one was a
surprise worth writing down:

1. The flat-curve fixtures (`_benchmark`, `_method(... annual=...)`) produce constant-growth
   curves whose residual is `None`, so no correlation is computable — `direct_kin` returns `None`.
2. **`promoted_variant` returns `None` for every fixture in this file.** `store.best_dev_eligible`
   resolves eligibility through `verdict(...)`, not the frozen `eligible` column, and the
   fixtures' rows do not clear it. So `tested_books` is `None` and the reading is never even
   attempted unless a test monkeypatches `store.best_dev_eligible` — which is exactly what the
   `(D11)` tests at `:367` and `:376` already do, and what every new test below does.

This is why `test_behaviour_is_one_hop` (`:1103`) — which asserts `failed_kin(conn, "M0070") ==
("M0002",)` on a method whose only book is *measurably* unrelated — stays green: M0070 has no
promoted variant, so the reading is never taken. If a future fixture gives it one, that assertion
becomes the thing (D16) deliberately retires, and the replacement is
`provenance_kin(conn, "M0070") == ("M0002",)`.

---

### Step 8: The new tests

**File:** `engine/tests/test_lab_hardgate.py` — appended at the end of the file (after
`test_lab_tests_note_says_when_the_kin_cannot_be_read`, currently `:1182`).
**Change:** eight tests for the new rule. **All eight were written and run against the
implementation in Steps 2-5 during planning and all eight pass** (`8 passed in 2.48s`), so the
fixtures below are known-good — in particular the fold-pick stability each one asserts.
**Code:**

```python
# ------------------------------------------------------------------ (D16) the book that is tested


def _promotes(monkeypatch, conn, candidate_id: str) -> None:
    """Make ``candidate_id`` the variant `lab promote` would pre-register.

    The same handle the (D11) tests above use: these fixtures' trials do not clear
    ``verdict(...).eligible``, so ``best_dev_eligible`` answers None for every one of them and
    nothing here would otherwise have a book to read.
    """
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = ?", (candidate_id,)).fetchone()
    assert row is not None
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: row)


def test_the_threshold_is_ninety_hundredths():
    """(D16): raised from 0.85 by the owner on 2026-10-13, and not lowered from inside the code."""
    assert hardgate.KIN_CORRELATION == 0.90


def test_the_module_records_the_book_that_would_be_tested_decision():
    """(D16) is argued in the docstring, and it retires (D12)'s expired premise by name."""
    doc = hardgate.__doc__ or ""
    assert "(D16)" in doc
    assert "The cost is identical today" in doc     # (D12)'s premise, still written down
    assert "expired" in doc                         # and recorded as expired, not deleted
    assert "0.939" in doc                           # M0020's promoted variant, measured
    assert "-4.7%" in doc                           # what the threshold move actually buys


def test_a_clean_book_frees_a_method_its_provenance_blocks(conn, monkeypatch):
    """R1/R2: the proxy defers to a reading it can take. M0060 is in a test-failed family and its
    one book moves with nothing; before (D16) the family alone refused it."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="stock-momentum-risk-managed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE))
    _promotes(monkeypatch, conn, "M0060-A")
    assert hardgate.provenance_kin(conn, "M0060") == ("M0002",)
    assert hardgate.tested_books(conn, "M0060") == ("M0060-A",)
    assert hardgate.direct_kin(conn, "M0060", ("M0002",)) == ()
    assert hardgate.failed_kin(conn, "M0060") == ()
    assert hardgate.family_state(conn, "M0060") == "clean"
    hardgate.check(conn, "M0060")   # does not raise


def test_a_twin_fold_pick_refuses_even_when_the_promoted_variant_is_clean(conn, monkeypatch):
    """M0053's shape, and the leak (D12) predicted: the promoted variant is clean, every fold was
    won by a twin, and the record that makes the method eligible is the twin's. Gating on the
    promoted variant alone would admit it on a record it did not earn."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="new", curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE))
    _variant(conn, "M0060", "MOM", annual=0.0,
             curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE, _EDGE, _EDGE))
    _promotes(monkeypatch, conn, "M0060-A")
    assert hardgate.provenance_kin(conn, "M0060") == ()       # family, ancestry, ingredients clean
    assert {p.picked for p in hardgate.fold_record(conn, "M0060").picks} == {"M0060-MOM"}
    assert hardgate.tested_books(conn, "M0060") == ("M0060-A", "M0060-MOM")
    (twin,) = hardgate.direct_kin(conn, "M0060", ("M0002",))
    assert twin.candidate_id == "M0060-MOM"                   # the pick, not the promoted variant
    assert hardgate.failed_kin(conn, "M0060") == ("M0002",)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0060")
    assert "M0060-MOM" in str(e.value) and "D16" in str(e.value)


def test_a_twin_variant_no_look_would_land_on_no_longer_blocks(conn, monkeypatch):
    """R1, the complement of the test above: the same twin variant, never picked and never
    promoted. `behavioural_kin` still names it -- and the method is freed anyway."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="new",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE, _EDGE))
    _variant(conn, "M0060", "MOM", annual=0.0,
             curve_json=_moving(_months(*DEV_SPAN), _IDEA_A, _NOISE))
    _promotes(monkeypatch, conn, "M0060-A")
    (named,) = hardgate.behavioural_kin(conn, "M0060")
    assert named.candidate_id == "M0060-MOM"
    assert {p.picked for p in hardgate.fold_record(conn, "M0060").picks} == {"M0060-A"}
    assert hardgate.tested_books(conn, "M0060") == ("M0060-A",)
    assert hardgate.direct_kin(conn, "M0060", ("M0002",)) == ()
    assert hardgate.failed_kin(conn, "M0060") == ()


def test_a_method_with_no_variant_to_pre_register_stays_blocked(conn):
    """R2, fail closed: M0019 and M0044's live shape. No book would be tested, so the question
    (D16) asks has no answer, and the gate's standing behaviour on one of those is to refuse."""
    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="stock-momentum-risk-managed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE))
    assert hardgate.promoted_variant(conn, "M0060") is None
    assert hardgate.tested_books(conn, "M0060") is None
    assert hardgate.direct_kin(conn, "M0060", ("M0002",)) is None
    assert hardgate.failed_kin(conn, "M0060") == ("M0002",)


def test_a_failed_book_with_no_look_is_not_measured_and_still_blocks(conn, monkeypatch):
    """R2, the quiet half of fail-closed: M0002 never spent a look, so there is no tested curve to
    compare against. `behavioural_kin` returns () for that -- which is "I could not look", not
    "clean" -- and provenance must stand."""
    _moving_benchmark(conn)
    _method(conn, "M0002", family="stock-momentum-risk-managed", status="test-failed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_A))
    _method(conn, "M0060", family="stock-momentum-risk-managed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE))
    _promotes(monkeypatch, conn, "M0060-A")
    assert hardgate.behavioural_kin(conn, "M0060") == ()
    assert hardgate.direct_kin(conn, "M0060", ("M0002",)) is None
    assert hardgate.failed_kin(conn, "M0060") == ("M0002",)


def test_a_book_on_other_prices_refuses_rather_than_frees(conn, monkeypatch):
    """R2, the (D10) path: a comparison across two price histories measures the data, so the
    reading refuses and the proxy keeps blocking."""
    _moving_benchmark(conn)
    _failed_momentum(conn, prices=OTHER_PRICES)
    _method(conn, "M0060", family="stock-momentum-risk-managed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE))
    _promotes(monkeypatch, conn, "M0060-A")
    with pytest.raises(store.LabError) as e:
        hardgate.direct_kin(conn, "M0060", ("M0002",))
    assert "D10" in str(e.value)
    with pytest.raises(store.LabError):
        hardgate.failed_kin(conn, "M0060")


def test_every_caller_reads_the_same_freed_method(conn, monkeypatch):
    """(D9)/(D13)/(D16): one definition. The gate, the pre-registration line, `lab test`'s note
    and `family_state` all answer the same way about one method, because they all call
    `failed_kin` and nothing forked a per-variant sibling for some of them."""
    from seer_engine.lab import prereg, runner

    _moving_benchmark(conn)
    _failed_momentum(conn)
    _method(conn, "M0060", family="stock-momentum-risk-managed",
            curve_json=_moving(_months(*DEV_SPAN), _IDEA_B, _EDGE))
    _promotes(monkeypatch, conn, "M0060-A")
    assert hardgate.failed_kin(conn, "M0060") == ()
    assert hardgate.family_state(conn, "M0060") == "clean"
    hardgate.check(conn, "M0060")
    assert "clean at promotion" in prereg.family_text(conn, "M0060", "stock-momentum-risk-managed")
    with conn:
        store.update_method(conn, "M0060", status="promoted")
    assert runner.kin_note(conn, "M0060") is None
```

**Impact:** +8 tests. The suite goes from 4,725 to 4,733 tests, 3 skipped either way.

---

### Step 9: The dated owner revision in the design doc

**File:** `docs/plans/2026-10-03-seer-design.md` — **append** after the last line of `## 15.`
(the file ends at line 480). Edit nothing above it.
**Change:** a new section in the house shape used by `## 11.` and `## 13.` — what changed with the
original sentence preserved, who and why with the owner quoted, the measurement, and what it does
not change.
**Code:**

```markdown
## 16. Revision 2026-10-13 (owner): the kin gate reads the book that would actually be tested

- **The lab's kin rule now asks about one book, not about every variant a method carries.** The
  rule as it stood, preserved: *"no `test-failed` method's tested variant moves with **any** of its
  dev variants, at a residual correlation of `KIN_CORRELATION` or more"*. It now asks that of the
  variant the lab would actually pre-register and of every variant a fold's training slice picked
  — the only books a look can ever land on. Family, ancestry and blend ingredients stay in the
  rule as a proxy, and the proxy gives way when that reading can honestly be taken.
- **Who and why.** The owner, on a lab that had stopped being able to promote anything: *"i also
  suspects this kin question. can we make it 'less strict'?"* The measurement said the strictness
  was in the wrong place. Of 81 recorded methods, 66 were not development-eligible, 5 failed the
  walk-forward folds, and every one of the remaining 10 was refused as kin of a book that had
  already lost its one out-of-sample look. The similarities were real — the books in question move
  together between 0.89 and 0.98, which means they are the same strategy under different names —
  but the gate was refusing a whole method because a *sibling* version of it was a copy, while the
  look would have been spent on a version that was not.
- **The bar for calling two books the same was raised from 0.85 to 0.90.** This is the owner's
  decision and its value is small: it admits exactly one book the old bar refused, and that book
  lost to the market by **4.7 points a year** over 2009–2015, the years the price history covers
  best. It is recorded here at that size rather than as a general loosening.
- **What it does not do, and this is the important half.**
  - **It promotes nothing and tests nothing.** It makes a method *eligible* to be considered. The
    one out-of-sample look each method gets is still spent only by a deliberate, separate act, and
    four of those looks have already been spent and lost.
  - **The test window was not opened.** It stands at four looks spent, before and after.
  - **It frees one method, not three.** The first reading of the measurement said three methods
    would be freed. Checked properly, two of those three rest on books that *are* copies: one
    would have been pre-registered as a copy outright, and the other won its folds entirely
    through a copy while the version that would have been tested never won a single fold. Both
    stay refused. The one method the change frees then fails the fold majority anyway, so **the
    lab still has nothing it can promote today**, and the report still says so.
  - **It does not weaken the defence it exists for.** A method is still refused when the book that
    would be tested is a copy of a disproven one, *and* when the record that made it eligible was
    earned by one. And whenever the comparison cannot honestly be made — no benchmark, curves
    measured on different price histories, too little shared history, or no version to
    pre-register at all — the old rule applies unchanged. The gate never reads "clean" because it
    could not look.
  - **The real-money bar in §1 does not move**, and no recorded result, pre-registration or
    committed number changes. The rule changes what the gate will say next time it is asked.
- **The honest limit.** Picking the one version of a strategy that does not resemble a failure is
  itself a choice made after seeing the data, and the lab's luck test prices the search across
  versions without making that cost disappear. The fold-pick half of the rule exists because of
  it: a method cannot be freed on a record its copy earned.
- **Where it is implemented.** `engine/src/seer_engine/lab/hardgate.py` — the decision and its
  measurements are recorded there as `(D16)`, and the write-up is
  `docs/backtests/2026-10-13-kin-gate-per-variant.md`.
```

**Impact:** documentation only. No test reads this file (`test_dev_trades_bar.py` cites `§13`'s
numbers, which are untouched).

---

### Step 10: The write-up

**File:** `docs/backtests/2026-10-13-kin-gate-per-variant.md` — new.
**Change:** the before/after measurement in the owner's plain language, with the residual risk.
Follow the house header shape of `docs/backtests/2026-10-12-brakes-and-gate.md`: a bold
**Measured** / **Window** / **Commands** block, then "## The short answer".
**Code:**

```markdown
# The kin gate, read one book at a time

**Measured:** 2026-10-13 · **Lab:** `lab/lab.sqlite`, read-only (`2c8c9669ad76`), 81 methods
**Commands:** `lab walkforward` before and after the rule change · nothing was written, no
research store was opened, and the test window was not read
**Decision:** `docs/plans/2026-10-03-seer-design.md` §16 · `engine/src/seer_engine/lab/hardgate.py`
(D16)

## The short answer

The lab could not promote anything. Ten methods had survived every other test and were refused for
one reason: each was judged too similar to a strategy that had already been tried and failed. That
judgement was right about the similarity and wrong about the scope. It looked at **every** version
of a method, while a real trial is run on **one** version — so a method was being refused for a
version that would never have been used.

The rule now looks at the version that would actually be traded, and at every version the lab's own
selection rule picked during its historical checks. On the committed lab this frees **one** method,
M0024 — and M0024 then fails the next test anyway, because it beat the market in only two of four
historical periods. **Nothing has become promotable.** The report still ends with "No buy signal."

That is a smaller result than the three methods the first reading promised, and the reason is worth
stating: the first reading asked the wrong function. The lab's similarity report names only the
*most* similar version of a method, so a version sitting a thousandth behind it looks unnamed and
therefore innocent. Checked version by version, M0020's traded book is a 0.94 match to a failed one
and M0030's is 0.96. Both stay refused, correctly.

## Before and after

| method | before | after | why |
|---|---|---|---|
| M0024 | kin already failed (M0021, M0022, M0029) | **fails the folds: 2 of 4** | its two books read 0.89 and 0.83 — under the new 0.90 bar, neither is a match |
| M0053 | kin already failed (M0002, M0021, M0022, M0029) | kin already failed (M0002) | the 0.90 bar drops three of the four links; the fourth stands at 0.92 |
| M0007, M0011, M0020, M0028, M0030, M0033 | kin already failed | unchanged | the book that would be traded is itself a match: 0.97, 0.98, **0.94**, 0.95, **0.96**, 0.96 |
| M0019, M0044 | kin already failed | unchanged | neither has a version the lab would pre-register, so there is no book to read and the old rule stands |
| every other method | unchanged | unchanged | — |

`24 of 81 methods beat the benchmark in a majority of folds` before and after. No signal fires.

## The one that mattered most

M0053 is the case that decided the design. The version of it that would have been traded is **not**
a match for anything — 0.88 against the closest failed book, under the bar. But all four of its
historical periods were won by a *different* version, `TOTON20-NOBRAKE`, which is a 0.92 match for a
strategy that already lost its one real trial. The version that would have been traded never won a
single period.

Freeing M0053 on that record would have handed a fresh trial to a book that already failed, wearing
a new name and carrying a record it did not earn. That is the exact thing the rule exists to
prevent, so the rule reads the selected versions too, and M0053 stays refused. M0030 is the same
story in miniature: its one winning period was won by a 0.92 match.

## The residual risk, plainly

Choosing the one version of a strategy that does not resemble a failure **is itself a choice made
after seeing the data**. The lab's luck test charges a method for the number of versions it tried,
which prices the search — but pricing a cost is not removing it. A method freed by this change has
been freed on one book's behaviour, not on its family's record, and its family's record is four
spent trials and four losses.

Two things hold that risk down and neither makes it zero: the selected-version half of the rule,
which stops a method being freed on a record its copy earned; and the fact that the bar is a
measured number sitting in a gap the lab actually observed — unrelated strategies top out at 0.80
and copies start at 0.89 — rather than a dial to be turned when the answer is inconvenient. It was
turned once, on 2026-10-13, by the owner, for one book worth −4.7 points a year, and that is
written down.
```

**Impact:** documentation only.

---

## Verification

**Lint:**

```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

Clean at the base commit; must stay clean. CI lints bugs only (E9, F, minus F401), so the new
code must not leave an unused import or an undefined name.

**Tests (the whole suite — the one command that is authoritative):**

```bash
docker start seer-pg    # if the container is not running
cd /home/miftah/.worktrees/seer/kin-gate-per-variant/engine && \
  PYTHONPATH=/home/miftah/.worktrees/seer/kin-gate-per-variant/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

Baseline at `f390c08` is **4725 passed, 3 skipped**. Expected after this phase: **4733 passed,
3 skipped** — quote the skip count beside the pass count, and never `-o addopts` (that silently
turns the parallel run serial). Without `PG_TEST_URL`, 385 tests skip and CI fails; without
`PYTHONPATH`, pytest imports the main checkout and tests the wrong tree.

**The before/after table — how to produce it without touching the database:**

```bash
S=$(mktemp -d)
cp /home/miftah/.worktrees/seer/kin-gate-per-variant/lab/lab.sqlite "$S/lab.sqlite"
sha256sum /home/miftah/.worktrees/seer/kin-gate-per-variant/lab/lab.sqlite
# expected 2c8c9669ad76642741342f8272a629e125c795f9dd0ab09300f44721dc580086
cd /home/miftah/.worktrees/seer/kin-gate-per-variant && \
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine \
  lab walkforward --db "$S/lab.sqlite" > "$S/after.txt"
```

Run it on the **copy**, not on `lab/lab.sqlite`: every lab command migrates the database on
connect, so even a read dirties the committed file. Compare against the recorded "before" output
in this plan (the two-line diff above). If `lab/lab.sqlite` is dirtied anyway, restore it **by
path**: `git checkout -- lab/lab.sqlite`, and say in the commit message that it was restored. This
phase commits no database change and runs no `lab stage`.

**The test window is not read:**

```bash
cd /home/miftah/.worktrees/seer/kin-gate-per-variant && PYTHONPATH=engine/src \
  /home/miftah/seer/engine/.venv/bin/python -c "
from pathlib import Path
from seer_engine.lab import store
c = store.connect_readonly(Path('lab/lab.sqlite')); print(store.test_looks(c))"
```

**4** before and after.

**The tripwires:**

```bash
cd /home/miftah/.worktrees/seer/kin-gate-per-variant/engine && \
  PYTHONPATH=../engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q \
  tests/test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest
git -C /home/miftah/.worktrees/seer/kin-gate-per-variant status --short lab/ web/data/   # empty
```

**Manual check:** read the `(D16)` section aloud against `(D12)` at `hardgate.py:292-299`. (D12)'s
paragraph must still be there, word for word, and (D16) must name it, say which of its three
reasons expired and which two still hold, and never contradict it silently.

**Exit criteria:**

1. `hardgate.KIN_CORRELATION == 0.90`.
2. `failed_kin` is the only kin verdict function; there is no per-variant sibling, and
   `grep -rn "failed_kin" engine/src` still shows the same five call sites, none of them edited.
3. `lab walkforward` over the 81 methods differs from the recorded "before" in exactly two rows:
   M0024 `kin already failed …` → `fails the folds: 2 of 4 folds`, and M0053's kin list narrowing
   to `M0002`. `24 of 81` and `No buy signal.` unchanged. Zero methods promotable.
4. A test proves the fold-pick leak is closed
   (`test_a_twin_fold_pick_refuses_even_when_the_promoted_variant_is_clean`).
5. Tests prove both fail-closed paths: `promoted_variant` is None, and a failed book with no
   comparable tested curve — plus the (D10) refusal still raising.
6. A test shows `check`, `family_state`, `prereg.family_text` and `runner.kin_note` agreeing about
   one method.
7. The digest tripwire green; `store.test_looks` reads 4; `git status --short lab/ web/data/` empty.
8. `ruff` clean; suite green, pass and skip counts quoted together.
9. The design-doc section states what the change does **not** do, including that it promotes
   nothing and that it frees one method rather than three; the write-up carries the before/after
   table and the residual risk in plain language with no ids, digests or code identifiers where a
   sentence will do.

**GIT — the standing rule of this repo, and it applies to any subagent this phase dispatches
(say so verbatim in such a prompt):** commit by explicit pathspec with `-m` **before** `--`:

```bash
git -C /home/miftah/.worktrees/seer/kin-gate-per-variant commit -m "lab: the kin gate reads the book that would actually be tested" -- \
  engine/src/seer_engine/lab/hardgate.py \
  engine/tests/test_lab_hardgate.py \
  docs/plans/2026-10-03-seer-design.md \
  docs/backtests/2026-10-13-kin-gate-per-variant.md
```

`git reset --hard`, `git clean`, `git checkout .`, `git restore .`, bare `git stash` /
`git stash pop`, `git add .` and `git add -A` are **banned** here. (`git checkout -- lab/lab.sqlite`
— a single named path — is the one restore this phase may use, and only to undo an accidental
migration write.)

---

## Handoffs

- **`walkforward.BUY_CONDITIONS` and the `buy_signal` docstring** still describe kin as "family
  union ancestors", which under-describes the rule they are handed — it has under-described it
  since (D12) and (D14), and (D16) widens the gap again. Editing `walkforward.py` is explicitly
  out of scope for this phase and is the owner's to decide, exactly as (D13) recorded.
- **`prereg.family_text`'s docstring** (`prereg.py:545-563`) lists the kin arms without the book
  reading, and `prereg.py` is out of scope here. Same disposition: recorded in (D16), left for the
  owner. (Note for the reconciler and the index: the analysis names **four** callers of
  `failed_kin`; there are **five** — `prereg.family_text` at `prereg.py:567` calls it directly
  rather than going through `family_state`. It needs no edit, but the "all callers agree" test
  covers it.)
- **Promoting M0024, or anything else.** Out of scope by the index's Decision D5, and in any case
  M0024 now fails the fold majority. A test look is spend-once and four are already gone.
- **The plan index's exit criterion 2** says M0020 and M0024 are freed. M0020 is not; the index
  should be corrected to "M0024 only, and nothing becomes promotable" when the set is reconciled.
  The correction belongs to whoever owns `docs/plans/KIN_GATE_PER_VARIANT_PLAN.md`, not to this
  phase's commit.
- **`lab status`'s `summary` line** still prints `behavioural_kin`'s best-pair twins through
  `family_state`'s text; it reads correctly, but it could usefully name the book that would be
  tested the way `check` now does. Not done here — it is display polish, not the rule.

---

## Rollback

One commit over four files, no database change and no recorded row touched, so `git revert <sha>`
restores the previous gate answer exactly — `failed_kin` is a pure read over `lab/lab.sqlite`, and
nothing it returns was stored anywhere.

The one asymmetry: if the change is reverted **after** a method has been promoted under it, the
promotion is a recorded fact with a pre-registration file behind it. The `## 16.` section must then
stay, with a newer dated section explaining the reversal — the design doc is a record, not a
current-state file. Nothing in this phase makes that situation reachable on its own: it promotes
nothing, and the one method it frees fails the next condition.
