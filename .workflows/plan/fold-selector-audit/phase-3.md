# Phase 3: Measure the era edge on the promoted variant

**Plan set:** `FOLD_SELECTOR_AUDIT_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162754-F0LD_code_analyzer.md` (finding F5)
**Satisfies:** R4 — resolve the M0179 thread: `lab walkforward` said `+0.3%` and `lab survivorship`
said `−5.6%`, and which one the buy signal means is load-bearing for every "no buy signal"
statement the lab has made.
**Depends on:** Phase 1 (soft — see *Assumptions*; the phase builds and passes without it, with one
label missing from one footnote)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/` and `engine/src/seer_engine/commands/`

---

## Goal

After this phase, `lab walkforward`'s `2009-15 edge` column — and the `high_coverage_edge` the buy
signal's fourth condition reads — is measured on **the variant `lab promote` would pre-register**:
the arm the counted look and the owner's money are actually spent on. The hindsight-best arm's
edge, which every record written before today quotes, stays on the row in its own `(hindsight)`
column, and the eighteen dev-eligible methods whose two numbers disagree on sign are named
underneath with both arms and both roles. `BUY_CONDITIONS` and `buy_signal`'s docstring say which
arm they mean, closing the half of hardgate's Decision D13 that is about `walkforward.py`'s prose.

---

## Three measured corrections to the brief — read these first

Everything below was measured today against a **copy** of `lab/lab.sqlite`
(`sha1 f2ff9ce6…`, unchanged before and after). The live file was never opened by a lab command.

### Correction 1 — the buy signal **has** fired, and fires today, on four methods

The brief states *"No buy signal has ever fired, so every past 'no buy signal' statement STANDS."*
That is **false on the committed lab as of 2026-10-20**. `lab walkforward` against the copy prints:

```
  *** BUY SIGNAL ***
  M0092: cleared all 4: dev-eligible, kin clean, 3 of 4 folds, 2009-2015 edge +1.7 pts
  M0197: cleared all 4: dev-eligible, kin clean, 3 of 4 folds, pick changed, 2009-2015 edge +7.0 pts
  M0243: cleared all 4: dev-eligible, kin clean, 3 of 4 folds, pick changed, 2009-2015 edge +1.9 pts
  M0258: cleared all 4: dev-eligible, kin clean, 3 of 4 folds, pick changed, 2009-2015 edge +2.3 pts
```

So the exposure F5 describes is not forward. It is live, and **two of the four firings are on an
arm nobody would trade**:

| method | hindsight arm (what the signal read) | edge | promoted arm (what gets the money) | edge |
|---|---|---|---|---|
| M0092 | `M0092-SQRT-CAP10` | +1.73 | `M0092-SQRT-CAP10` — same arm | **+1.73** |
| M0197 | `M0197-Y20` (treatment, no switch) | +7.02 | `M0197-Y20-SW` | **−3.34** |
| M0243 | `M0243-NEAR20-T3` (**a dose rung**: *"A stricter dose: …"*) | +1.91 | `M0243-NEAR20-SW` | **−3.92** |
| M0258 | `M0258-M-B0` | +2.26 | `M0258-M-B0` — same arm | **+2.26** |

### Correction 2 — the change is **not** monotone. One method starts firing: M0072

Simulated end to end with the real kin rule over the copy:

```
BEFORE fires: ['M0092', 'M0197', 'M0243', 'M0258']
AFTER  fires: ['M0072', 'M0092', 'M0258']
newly firing: ['M0072']
stops firing: ['M0197', 'M0243']
```

`M0072`'s hindsight arm `M0072-Z2` reads **−1.09 pts** while its promoted arm
`M0072-Z2-RAWRANK` reads **+2.26 pts**. Both are treatment arms (*"Parent's news days…"* /
*"The Z2 filter ranked by the raw jump as the parent did"*), so this is not a control bug — it is
the hindsight bug running the other way, and it is the measured proof of F5's sentence *"it is not
merely conservative; it can also suppress a true positive."*

**This does not violate the plan set's invariant 5** (*"No phase makes a currently-refused method
promotable"*). `hardgate.check()` is untouched by this phase and has no era clause; M0072's
promotability is byte-identical before and after. The buy signal is a recommendation to **buy
price data**, not a promotion. But the index's *Why* section claims *"Every change below makes the
lab stricter"*, and the index's phase-3 exit criterion says *"no buy signal fires before or
after"*. Both are wrong. See **Handoffs**.

### Correction 3 — four dev-eligible methods have **no** promotable variant, so `dev-eligible` does *not* catch them first

The brief says *"`buy_signal`'s first condition is `dev-eligible`, so such a method already fails
earlier."* Measured, it does not: **M0007, M0011, M0019 and M0020** carry `status =
'dev-eligible'` while `store.best_dev_eligible` returns `None` for them. The status column is
frozen from the run date; `best_dev_eligible` re-reads `verdict(...).eligible` under the N and DSR
bars **in force now**, and those moved (the N policy went from all-trials to methods on
2026-10-08). The two disagree, by design — see `store.best_dev_eligible`'s own docstring, *"two
trials recorded six weeks apart are ranked against the same bar"*.

They are harmless **today** only by luck: all four are refused one condition earlier, by kin.

```
M0007  3 of 4  yes  +2.7%  kin already failed the test window (M0021, M0022, M0029)
M0011  2 of 4  yes  −2.5%  kin already failed the test window (M0021, M0022, M0029)
M0019  3 of 4   no  +1.6%  kin already failed the test window (M0002, M0021, M0022, M0029)
M0020  3 of 4  yes  +2.4%  kin already failed the test window (M0002, M0021, M0022, M0029)
```

Those are exactly the three methods `buy_signal`'s own docstring records the signal once firing
on. So the design below **states the rule rather than relying on the luck**: no promotable
variant means no promoted-variant edge means `None` means the condition fails, with a message that
says so.

---

## Interface Contract

**Creates:**
- `seer_engine.lab.walkforward.era_edge` (`lab/walkforward.py`, new, after `measure`)
- `seer_engine.lab.walkforward.best_era_arm` (`lab/walkforward.py`, new, after `era_edge`)
- `seer_engine.commands.lab._promoted_variant` (`commands/lab.py`, new, above `_walkforward`)
- `seer_engine.commands.lab._arm_roles` (`commands/lab.py`, new, above `_walkforward`)

**Signature changes:** none. `buy_signal(dev_eligible, record, high_coverage_edge, family_failed)`
is byte-identical.

**Text changes (no behaviour):**
- `walkforward.BUY_CONDITIONS[1]` — `"no kin has test-failed (family union ancestors)"` ->
  `"no kin has test-failed (family union ancestors union blend ingredients union behaviour)"`
  (hardgate D13's other outstanding item; the *rule* is `hardgate.failed_kin` and is unchanged)
- `walkforward.BUY_CONDITIONS[3]` — `"positive 2009-2015 edge"` ->
  `"positive 2009-2015 edge on the variant that would be promoted"`
- `buy_signal`'s three era messages gain *"on the variant that would be promoted"*. Every
  substring the existing tests assert on (`"no 2009-2015 edge"`, `"negative 2009-2015 edge"`,
  `"never" not in why`, `"kin clean"`, `"+2.6"`) survives.

**Behaviour changes:**
- `commands/lab.py:_walkforward` hands `buy_signal` the **promoted variant's** era edge instead of
  the hindsight-best arm's. The firing set over the committed lab goes
  `{M0092, M0197, M0243, M0258}` -> `{M0072, M0092, M0258}`.
- the table grows one column, `(hindsight)`, and gains a sign-disagreement footnote.

**Deletes:** nothing. **Renames:** nothing.

**Requires (from earlier phases):** `seer_engine.lab.control_shape.role_of(arm) -> str` returning
one of `"control" | "dose" | "idea" | "treatment"` (Phase 1). **Soft dependency**: `_arm_roles`
swallows `ImportError`/`AttributeError` and returns `{}`, so phase 3 builds, passes and prints the
footnote without the four role labels if phase 1 has not landed.

**Leaves alone (owned by others, or out of scope by the brief):**
- `engine/src/seer_engine/lab/hardgate.py` — **every line**, including the D13 paragraphs at
  `:307-320` and `:444-452`, whose module docstring Phase 2 owns. See **Handoffs**.
- `hardgate.check()`, `hardgate._dev_curves`, `walkforward.pick`, `store.best_dev_eligible`.
- `commands/lab.py:HIGH_COVERAGE` (`:2541`) and `lab/survivorship_check.py:HIGH_COVERAGE` (`:65`)
  — `test_lab_survivorship.py:239` pins them equal; neither moves.
- `buy_signal`'s conditions 1-3 behaviour; `Record`, `FoldPick`, `Fold`, `Slice`, `folds`,
  `measure`, `pick`, `evaluate`.
- every recorded trial, verdict, digest and lab row. `lab test` and `lab promote` are not run.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/walkforward.py` | modify | `era_edge` + `best_era_arm` after `measure` (`:159`); `BUY_CONDITIONS` (`:252`); `buy_signal` docstring and its three era messages (`:260-311`) |
| `engine/src/seer_engine/commands/lab.py` | modify | `_promoted_variant` + `_arm_roles` above `_walkforward` (`:2542`); the preamble, header, edge computation, row and footnote inside `_walkforward` (`:2596-2658`) |
| `engine/tests/test_lab_walkforward.py` | modify | 6 new tests for `era_edge`, `best_era_arm` and the condition's wording |
| `engine/tests/test_lab_hardgate.py` | modify | 3 new command-level tests, with one new curve helper |

---

## The column layout decision, with the argument

**Chosen: two columns — `2009-15 edge` (the promoted variant) and `(hindsight)` — plus a
footnote, restricted to dev-eligible methods, naming both arms and both roles wherever the two
disagree on sign.**

The three candidates, and why the others lose:

**(a) One column, replace the number.** Rejected. 168 rows print today and 82 of them have **no
promotable variant at all** — every `H-P7A-F*` row, every rejected method. Replacing the column
blanks half the table, and worse, every insight, handover and analysis in `docs/` quotes the old
number. The index already decided this (*"add, label both"*, rung 6: convention).

**(b) One column plus a note.** Rejected on size. The two arms differ for **46 of the 86** methods
that have both edges. A note that preserved the old number for all of them would be a 46-line
block longer than the useful half of the table, and a reader looking up what M0184 used to report
would be scanning prose instead of a column.

**(c) Two columns, plus a bounded footnote.** Chosen. Measured widths: the header goes from 55 to
69 characters, the underline from 71 to 85, and the long `verdict` text already runs past both.
Every row keeps a number in at least one column, aligned and greppable.

The footnote earns its place because **the defect being fixed is a number printed without saying
which arm it belonged to** — that is the whole of the M0179 thread. Printing a second bare column
of percentages would repeat that mistake in miniature: a reader still could not tell that M0201's
`+1.8%` is a **placebo**. So the footnote names both arms with their roles, and it is bounded two
ways, both argued:

- **only dev-eligible methods** — the buy signal cannot fire on anything else, so for the rest the
  disagreement is decoration on a row whose verdict already reads `not dev-eligible`;
- **only where the two disagree on sign** — a method whose two arms read `+2.1%` and `+3.4%` is
  not a case anybody is misled by. Sign is where the fourth condition's answer changes.

Measured, that is **18 lines** on the committed lab, against 46 for "differs at all" and 39 for
"differs at all, among dev-eligible".

Rendered against the real lab, the result is:

```
  method    folds won   stable   2009-15 edge   (hindsight)   verdict
  -------------------------------------------------------------------------------------
  M0072        3 of 4        yes          +2.3%         −1.1%   cleared all 4: ...
  M0092        3 of 4        yes          +1.7%         +1.7%   cleared all 4: ...
  M0179        2 of 4        yes          −5.6%         +0.3%   fails the folds: 2 of 4 folds
  M0197        3 of 4         no          −3.3%         +7.0%   negative 2009-2015 edge ...
  M0201        2 of 4        yes          −7.8%         +1.8%   fails the folds: 2 of 4 folds
  M0243        3 of 4         no          −3.9%         +1.9%   negative 2009-2015 edge ...
  M0258        3 of 4         no          +2.3%         +2.3%   cleared all 4: ...
  M0007        3 of 4        yes              -         +2.7%   kin already failed ...
```

M0179's row is R4's answer printed side by side: `−5.6%` is `lab survivorship`'s number for
`M0179-N40-SW`, `+0.3%` is the old column's number for `M0179-N20`, and the two commands now agree
about which arm each is talking about.

---

## Implementation Steps

### Step 1: two pure helpers in `walkforward.py`

**File:** `engine/src/seer_engine/lab/walkforward.py:160` — insert after `measure` ends at `:159`
and before `def pick` at `:162`.

**Change:** lift the era arithmetic out of the command so it can be tested without a database, and
give the hindsight arm a name instead of an anonymous `max(...)` expression. `best_era_arm`
reproduces the inline expression **exactly**, quirks included, because its number is in the
archive.

**Code:**

```python
def era_edge(
    curve: Sequence[tuple[date, float]],
    bench: Sequence[tuple[date, float]],
    start: date,
    end: date,
    deposits: Mapping[date, float] | None = None,
) -> float | None:
    """``curve``'s annualised lead over ``bench`` between ``start`` and ``end``; None if unmeasurable.

    De-funded on both sides by ``measure``, so a book that was fed monthly is not credited with its
    own deposits against a benchmark that received none. None when either side has fewer than two
    months in the slice or no computable CAGR -- "nobody could measure it" is not a zero edge, and
    ``buy_signal`` refuses on it rather than treating it as a pass.

    This is the same arithmetic ``lab survivorship`` does per variant (``survivorship_check.py``),
    which is why the two commands can now be quoted in the same sentence about the same arm. They
    disagreed for a year because they were measuring different arms, not different numbers.
    """
    mine = measure(curve, start, end, deposits)
    theirs = measure(bench, start, end)
    if mine is None or theirs is None or mine.cagr is None or theirs.cagr is None:
        return None
    return mine.cagr - theirs.cagr


def best_era_arm(
    curves: Mapping[str, Sequence[tuple[date, float]]],
    bench: Sequence[tuple[date, float]],
    start: date,
    end: date,
    deposits: Mapping[str, Mapping[date, float]] | None = None,
) -> tuple[str | None, float | None]:
    """The arm with the highest MAR **over the era itself**, and its edge. Hindsight, by design.

    Nothing here is a selection rule the lab could have followed: the era is chosen after the fact
    and the arm is ranked on it, so the answer is "which of these arms turned out best in
    2009-2015", not "which arm would a researcher have named". It is kept, and kept under a name
    that says so, because every insight, handover and analysis the lab wrote before 2026-10-20
    quotes this number as the ``2009-15 edge``, and a record whose numbers cannot be reproduced is
    not a record.

    Two details are preserved from the inline expression in ``commands/lab.py`` this replaces,
    deliberately and not as an oversight, because changing either would silently move a figure in
    the archive:

    - ties go to the **first arm in ``curves``** (insertion order, which the caller builds in
      trial order), not to the first by id. ``pick`` sorts and this does not;
    - ``or -1e9`` ranks an arm whose era MAR is exactly ``0.0`` below every other arm, because
      ``0.0`` is falsy. No recorded dev curve hits it; it is written down rather than fixed.
    """
    dep = deposits or {}
    if not curves:
        return None, None

    def rank(cid: str) -> float:
        got = measure(curves[cid], start, end, dep.get(cid))
        return ((got or Slice(0, None, None, None, None)).mar or -1e9)

    best = max((c for c in curves), key=rank)
    return best, era_edge(curves[best], bench, start, end, dep.get(best))
```

**Impact:** pure addition; nothing else in the tree calls these yet. `Mapping` and `Sequence` are
already imported at `:45`, `date` at `:47`.

---

### Step 2: `BUY_CONDITIONS` says which arm, and which kin rule

**File:** `engine/src/seer_engine/lab/walkforward.py:250-257` — replace the block.

**Change:** the fourth condition names the arm. The second condition stops under-describing the
kin rule it is handed, which hardgate D13 has recorded as outstanding twice (`hardgate.py:317` and
`:449`): *"``BUY_CONDITIONS`` and the ``buy_signal`` docstring still describe kin as 'family union
ancestors', which now under-describes the rule they are handed."* The **rule** is
`hardgate.failed_kin` and is not touched — only the sentence that describes it, which is the edit
D13 says is owed.

**Code:**

```python
# --------------------------------------------------------------------------- the buy signal

BUY_CONDITIONS = (
    "dev-eligible",
    "no kin has test-failed (family union ancestors union blend ingredients union behaviour)",
    "majority of folds",
    "positive 2009-2015 edge on the variant that would be promoted",
)
```

**Impact:** `test_the_success_line_counts_the_conditions_it_actually_has` asserts
`len(BUY_CONDITIONS) == 4` — still 4. Nothing else in `engine/`, `web/` or `docs/` reads the
strings; the only references are `engine/package_readme.md` (prose, see **Handoffs**) and
`hardgate.py`'s own D13 prose (not edited here, see **Handoffs**).

---

### Step 3: `buy_signal`'s docstring and its three era messages

**File:** `engine/src/seer_engine/lab/walkforward.py:260-311` — replace the whole function.

**Change:** the body changes only the three strings of the era condition. The docstring gains the
paragraph that records *which arm* and *why*, written in the voice of the clauses above it — dense,
argued, citing the methods that forced it.

**Code:**

```python
def buy_signal(
    dev_eligible: bool,
    record: Record,
    high_coverage_edge: float | None,
    family_failed: str | None = None,
) -> tuple[bool, str]:
    """Is this the moment survivorship-free price history becomes worth paying for?

    All four must hold: the method is dev-eligible at the bars in force; no method in its family
    has already failed the test window; it beat the benchmark in a majority of walk-forward folds;
    and **the variant that would be promoted** has a positive edge in the highest-coverage era
    (2009-2015), so the edge is not an artefact of the half of the universe the store cannot price.

    **The kin condition was added after running this.** Without it the signal fired on M0007,
    M0019 and M0020 -- and every one of the three is in a family that had *already* failed out of
    sample (``stock-residual-momentum`` and ``stock-momentum-risk-managed``). M0007 in particular
    reads ``dev-eligible`` only because the lab never spent a formal look on it, while its own
    realistic twin M0032 lost 415 million rupiah to a deposit-matched SPY over 2018-2026. A status
    column is not the same thing as the evidence, and a new variant of a family that has been
    disproven is not a fresh candidate.

    ``family_failed`` is whatever the caller's kin rule found. ``lab walkforward`` passes
    ``hardgate.failed_kin``, the **same** rule the promote gate enforces -- family, union transitive
    ancestors, union the blend ingredients a variant runs and their families (hardgate D12), union
    the tested books a variant moves with at 0.85 correlation (hardgate D14). They were briefly
    different: the gate walked ancestry and this did not, so the signal called M0030's family clean
    while the gate refused it on its parent M0029 and grandparent M0021. Two commands giving
    opposite answers about one method is worse than either answer, which is why Decision D9 was
    resolved by aligning them rather than documenting the gap. ``BUY_CONDITIONS`` above said
    "family union ancestors" until 2026-10-20, which under-described it; hardgate D13 is the record
    of that debt and this is the paragraph that pays it.

    The third is what makes the purchase about *data*. The dev store prices 48% of index members
    in 1996 and 74% in 2014, and the 522 it cannot price are disproportionately the companies that
    died. A method whose edge lives in the thin early years and dies by 2009-2015 is probably
    reading that hole, and it can be rejected for free. A method that passes all three has used up
    the free evidence, and the next two things that happen are a counted look and real money.

    **Which arm the era edge is measured on, and why it is the promoted one.** The condition is
    the last thing standing between a report and spending money, so it has to be about the book the
    money goes into: ``store.best_dev_eligible``, the variant ``lab promote`` pre-registers and
    ``lab survivorship`` reports. Until 2026-10-20 ``lab walkforward`` handed in the edge of
    whichever arm had the highest MAR over 2009-2015 **itself** -- chosen with hindsight over the
    very era it is judged on, from every arm including the ones registered to be beaten. Measured
    over the 74 dev-eligible methods where both numbers exist, that was a different arm for 39, a
    **control** arm for 19, and the two disagreed on sign for 18: eleven read positive while the
    arm that would be traded was negative, and seven the reverse. The worst was M0201, reporting
    +1.82 pts on ``M0201-PLC2-MV10`` -- *"Placebo: hash order seed 2, sized by market value"* --
    while ``M0201-Y20-MV10-SW``, the arm it would have promoted, sat at -7.82. It was not merely
    generous: M0072 was **refused** at -1.09 pts on ``M0072-Z2`` while ``M0072-Z2-RAWRANK``, its
    own promoted arm, was at +2.26. A condition that can be wrong in both directions is not a
    conservative condition, it is a condition about the wrong thing.

    ``high_coverage_edge`` is therefore ``None`` for a method with no promotable variant at all --
    ``best_dev_eligible`` returning ``None``, which is true of four ``dev-eligible`` methods today
    (M0007, M0011, M0019, M0020, whose frozen status predates the N policy move of 2026-10-08) --
    and the signal refuses on it. Each of those four is already refused one condition earlier, by
    kin; the rule is written down anyway rather than left resting on that, because the next method
    in that shape may have clean kin. There is no arm to buy data for, so there is nothing to buy.

    Returns ``(fired, why)``; ``why`` names the first condition that failed, so a report can say
    what is missing rather than only that nothing happened.
    """
    if not dev_eligible:
        return False, "not dev-eligible"
    if family_failed:
        return False, f"kin already failed the test window ({family_failed})"
    if not record.majority:
        return False, f"fails the folds: {record.summary()}"
    if high_coverage_edge is None:
        return False, "no 2009-2015 edge for the variant that would be promoted"
    if high_coverage_edge <= 0:
        return False, (
            f"negative 2009-2015 edge on the variant that would be promoted "
            f"({high_coverage_edge * 100:+.1f} pts)"
        )
    return True, (
        f"cleared all {len(BUY_CONDITIONS)}: dev-eligible, kin clean, {record.summary()}, "
        f"2009-2015 edge on the promoted variant {high_coverage_edge * 100:+.1f} pts"
    )
```

**Impact:** every existing assertion in `test_lab_walkforward.py` still holds — `"not
dev-eligible"`, `"fails the folds"`, `"no 2009-2015 edge"` with `"never" not in why`,
`"negative 2009-2015 edge"`, `"kin already failed"`, `"dev-eligible" … "folds" … "+2.6"`,
`f"cleared all {len(wf.BUY_CONDITIONS)}"`, `"kin clean"`.

---

### Step 4: two report-side helpers in `commands/lab.py`

**File:** `engine/src/seer_engine/commands/lab.py:2542` — insert between `HIGH_COVERAGE`
(`:2541`) and `def _walkforward` (`:2544`).

**Change:** one helper to ask the gate which arm would be pre-registered without ever letting it
refuse, and one to read arm roles off the method files for the footnote. Both are readers: a
report warns, it never refuses (the rule `_comparability_warnings` already follows).

**Code:**

```python
def _promoted_variant(conn, method_id: str) -> str | None:
    """The candidate ``lab promote`` would pre-register, or None; never raises.

    ``hardgate.promoted_variant`` and not a second query beside it, for exactly the reason
    Decision D9 gives about the kin rule: two commands giving different answers about one method is
    worse than either answer. The gate and this column must name the same arm, or the number the
    buy signal reads is about a book the owner would not be holding.

    None covers two different situations and the caller treats them the same, because for this
    column they are the same: no eligible dev trial at all (``best_dev_eligible`` returns None --
    four ``dev-eligible`` methods are in that state today), and a lab whose gate cannot be resolved
    at all. Measured at 0.86s for all 168 methods in the committed lab, the per-method gate read
    served from ``store._GATE_CACHE``.
    """
    from seer_engine.lab import hardgate

    try:
        return hardgate.promoted_variant(conn, method_id)
    except store.LabError:
        return None


def _arm_roles(method_ids: Sequence[str]) -> dict[tuple[str, str], str]:
    """``(method, candidate) -> " (control)"`` for every arm of ``method_ids``; ``{}`` when unreadable.

    An arm's role is written in its rationale and nowhere else -- never in its id, which is why
    ``control_shape`` reads the prose (``M0005-ALL-R``'s ``-R`` is a rank weighting, not a
    control). Reading it needs the method files, so this is the one part of ``lab walkforward``
    that opens anything outside the database. It is called **only** when the footnote below has
    rows, so a lab with no sign disagreement -- every test fixture -- never imports a method module
    at all. Measured on the committed lab: 0.96s for the first ``discover()``, 0.005s after.

    It swallows everything. A method with no file, a file that will not import, a
    ``control_shape`` without ``role_of`` because this phase landed before the one that adds it --
    all come back as no label, and the footnote still names both arms and both numbers. The label
    is the adjective on a line that is already complete without it, and a report that crashed
    while annotating a footnote would be a worse answer than a report with a plainer footnote.
    """
    try:
        from seer_engine.lab import control_shape
        from seer_engine.lab.method import discover

        found = discover()
    except Exception:  # noqa: BLE001 -- a reader, deliberately: see the docstring
        return {}
    out: dict[tuple[str, str], str] = {}
    for mid in method_ids:
        entry = found.get(mid)
        if entry is None:
            continue
        method, _path = entry
        for arm in method.all_candidates():
            try:
                out[(mid, arm.id)] = f" ({control_shape.role_of(arm)})"
            except Exception:  # noqa: BLE001
                continue
    return out
```

**Impact:** `Sequence` is imported at `:155`, `store` at `:162`. No new module-level import.

---

### Step 5: the preamble says what the two columns are

**File:** `engine/src/seer_engine/commands/lab.py:2596-2599` — replace the four `print` calls.

**Code:**

```python
    print(f"Walk-forward over {len(the_folds)} folds, {the_folds[0].eval_start} to "
          f"{the_folds[-1].eval_end}. Each fold picks the variant the lab's own rule would have")
    print("named knowing nothing past the train end, then scores it on months it has never seen.")
    print("Folds share training data, so they are a sanity check and never a significance test.")
    print("`2009-15 edge` is the variant `lab promote` would pre-register -- the arm the counted")
    print("look and the owner's money are spent on, and the one the buy signal reads. `(hindsight)`")
    print("is the column as it read before 2026-10-20: the arm with the highest MAR over 2009-2015")
    print("itself, chosen after seeing that era. They name different arms for 46 of the 86 methods")
    print("that have both, so every record written before then quotes the right-hand column.\n")
```

**Impact:** five extra preamble lines in a command whose preamble is already three. That is the
house style — this report explains itself before it prints a number.

---

### Step 6: the header and the underline

**File:** `engine/src/seer_engine/commands/lab.py:2605-2607` — replace.

**Code:**

```python
    head = (f"  {'method':<8}{'folds won':>11}{'stable':>9}"
            f"{'2009-15 edge':>15}{'(hindsight)':>14}   verdict")
    print(head)
    print("  " + "-" * (len(head) + 16))
```

**Impact:** header 55 -> 69 characters, underline 71 -> 85. The `verdict` text already runs past
both.

---

### Step 7: the edge handed to the signal, and the row

**File:** `engine/src/seer_engine/commands/lab.py:2609-2656` — replace the loop's head
(`:2609-2628`) and its print (`:2654-2656`). Everything between — the kin block at `:2629-2653` —
is untouched, comment included.

**Code (the whole loop, so there is no ambiguity about what stays):**

```python
    fired: list[str] = []
    majorities = 0
    disagreed: list[tuple[str, str, float, str, float]] = []
    for mid, trials in sorted(by_method.items()):
        curves = {r["candidate_id"]: curve_of(r) for r in trials}
        deps = {
            r["candidate_id"]: hardgate.trial_deposits(conn, r, curves[r["candidate_id"]])
            for r in trials
        }
        rec = wf.Record(mid, wf.evaluate(curves, bench, the_folds, deps))
        # Two era edges, and which one is which is the whole of this report's 2026-10-20 change.
        # `best` is the hindsight arm -- highest MAR over 2009-2015 itself, from every arm the
        # method registered, controls and placebos included. It is printed because the archive
        # quotes it and never handed to the signal. `edge` is the arm `lab promote` would
        # pre-register: the one the counted look and the money are spent on. For M0201 those were
        # a placebo at +1.8 pts and the real book at -7.8.
        best, best_edge = wf.best_era_arm(curves, bench, *HIGH_COVERAGE, deps)
        promoted = _promoted_variant(conn, mid)
        edge = (
            None
            if promoted is None or promoted not in curves
            else wf.era_edge(curves[promoted], bench, *HIGH_COVERAGE, deps.get(promoted))
        )
        row = store.get_method(conn, mid)
        eligible = row is not None and row["status"] == "dev-eligible"
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
        if signal:
            fired.append(f"{mid}: {why}")
        if rec.majority:
            majorities += 1
        if (
            eligible
            and edge is not None
            and best_edge is not None
            and promoted is not None
            and (edge > 0) != (best_edge > 0)
        ):
            disagreed.append((mid, promoted, edge, best, best_edge))
        print(f"  {mid:<8}{rec.won:>6} of {len(rec.scored):<3}"
              f"{('yes' if rec.stable else 'no'):>9}"
              f"{(fmt_signed_pct(edge) if edge is not None else '-'):>15}"
              f"{(fmt_signed_pct(best_edge) if best_edge is not None else '-'):>14}   {why}")
```

**Impact:** this is the behaviour change. Over the committed lab the firing set goes
`{M0092, M0197, M0243, M0258}` -> `{M0072, M0092, M0258}`; 82 of 168 rows print `-` in the left
column because they have no promotable variant, and all 168 keep a number in `(hindsight)`.

---

### Step 8: the sign-disagreement footnote

**File:** `engine/src/seer_engine/commands/lab.py:2658` — insert between the majorities line and
`if fired:`.

**Code:**

```python
    print(f"\n{majorities} of {len(by_method)} methods beat the benchmark in a majority of folds.")
    if disagreed:
        roles = _arm_roles([mid for mid, *_rest in disagreed])
        print(f"\n{len(disagreed)} dev-eligible method(s) where the two columns disagree on sign --")
        print("the only place the fourth buy condition's answer turns on which arm is read. The")
        print("left arm is the one `lab promote` would pre-register and `lab survivorship` reports;")
        print("the right is the arm chosen by hindsight over 2009-2015 itself.")
        for mid, prom, prom_edge, best, best_edge in disagreed:
            print(f"  {mid:<8}promoted {prom}{roles.get((mid, prom), '')} "
                  f"{fmt_signed_pct(prom_edge)}   hindsight {best}{roles.get((mid, best), '')} "
                  f"{fmt_signed_pct(best_edge)}")
    if fired:
        print("\n  *** BUY SIGNAL ***")
```

Rendered on the committed lab, the M0201 line reads:

```
  M0201   promoted M0201-Y20-MV10-SW (treatment) −7.8%   hindsight M0201-PLC2-MV10 (control) +1.8%
```

**Impact:** 18 lines plus a 4-line heading on the committed lab; nothing at all on a lab with no
disagreement, which is every test fixture except the two this phase adds. `_arm_roles` is called
once and only inside this branch, so `discover()` never runs otherwise.

---

### Step 9: pure tests for the two helpers and the wording

**File:** `engine/tests/test_lab_walkforward.py` — append to the `pick and evaluate` section (after
`test_evaluate_on_no_candidates_is_empty_not_an_error`, `:166`) and to the buy-signal section (end
of file, `:260`).

**Code (append after `:166`):**

```python
def test_era_edge_is_the_slice_lead_over_the_benchmark():
    ms = months(date(2000, 1, 1), 60)
    mine, theirs = curve(ms, 0.01), curve(ms, 0.005)
    got = wf.era_edge(mine, theirs, ms[0], ms[-1])
    a = wf.measure(mine, ms[0], ms[-1]).cagr
    b = wf.measure(theirs, ms[0], ms[-1]).cagr
    assert got == pytest.approx(a - b)


def test_era_edge_strips_deposits_before_it_compares():
    """A fed book must not be credited with its own deposits against a benchmark that got none."""
    ms = months(date(2000, 1, 1), 25)
    fed = [(d, 100.0 + 10.0 * i) for i, d in enumerate(ms)]
    flat = [(d, 100.0) for d in ms]
    dep = {d: 10.0 for d in ms[1:]}
    assert wf.era_edge(fed, flat, ms[0], ms[-1], dep) == pytest.approx(0.0, abs=1e-9)
    assert wf.era_edge(fed, flat, ms[0], ms[-1]) > 0.1


def test_era_edge_is_none_rather_than_zero_when_the_slice_cannot_be_read():
    ms = months(date(2000, 1, 1), 24)
    assert wf.era_edge(curve(ms, 0.01), curve(ms, 0.005), ms[3], ms[3]) is None


def test_best_era_arm_ranks_on_the_era_itself_which_is_hindsight():
    """The arm with the best MAR *inside* the era wins, even when another earns far more there.

    This is the measurement the column kept until 2026-10-20 and it is kept, under a name that
    says what it is: `M0072-Z2` beat `M0072-Z2-RAWRANK` on era MAR while earning 3.3 points less.
    """
    ms = months(date(2009, 1, 1), 72)
    smooth = curve(ms, 0.002)                       # never falls: MAR is infinite
    rich = [(d, v) for d, v in curve(ms, 0.012)]
    rich[30] = (rich[30][0], rich[30][1] * 0.6)     # one fall, so its MAR is finite
    bench = curve(ms, 0.005)
    arm, edge = wf.best_era_arm({"RICH": rich, "SMOOTH": smooth}, bench, ms[0], ms[-1])
    assert arm == "SMOOTH"
    assert edge == pytest.approx(wf.era_edge(smooth, bench, ms[0], ms[-1]))
    assert edge < wf.era_edge(rich, bench, ms[0], ms[-1])


def test_best_era_arm_breaks_ties_on_insertion_order_not_on_the_id():
    """`pick` sorts the ids; this does not, and the difference is in the archive. Pinned so a
    later tidy-up cannot silently move a number every recorded insight quotes."""
    ms = months(date(2009, 1, 1), 72)
    bench = curve(ms, 0.005)
    both = {"Z-FIRST": curve(ms, 0.01), "A-SECOND": curve(ms, 0.01)}
    assert wf.best_era_arm(both, bench, ms[0], ms[-1])[0] == "Z-FIRST"


def test_best_era_arm_on_no_curves_is_empty_not_an_error():
    ms = months(date(2009, 1, 1), 24)
    assert wf.best_era_arm({}, curve(ms, 0.005), ms[0], ms[-1]) == (None, None)
```

**Code (append at the end of the file):**

```python
def test_the_era_condition_says_which_arm_it_means():
    """R4: the column said +0.3% for M0179 and `lab survivorship` said -5.6%, and both were right
    -- about different arms. A condition that spends the owner's money has to name its arm."""
    assert "promoted" in wf.BUY_CONDITIONS[3]
    _f, why = wf.buy_signal(True, winner(), -0.021)
    assert "negative 2009-2015 edge on the variant that would be promoted" in why
    _f, why = wf.buy_signal(True, winner(), None)
    assert "no 2009-2015 edge for the variant that would be promoted" in why
    fired, why = wf.buy_signal(True, winner(), 0.026)
    assert fired and "2009-2015 edge on the promoted variant +2.6 pts" in why


def test_the_kin_condition_describes_the_rule_it_is_actually_handed():
    """hardgate D13's other outstanding item: the text said "family union ancestors" while the
    caller hands it `failed_kin`, which is also D12's ingredients and D14's behaviour."""
    kin = wf.BUY_CONDITIONS[1]
    assert "ancestors" in kin and "ingredients" in kin and "behaviour" in kin


def test_a_method_with_no_promotable_variant_cannot_fire():
    """`best_dev_eligible` returns None for four dev-eligible methods today (M0007, M0011, M0019,
    M0020): their status is frozen at their run date and the N policy moved under them. All four
    are refused by kin one condition earlier; the rule does not rest on that."""
    fired, why = wf.buy_signal(True, winner(), None, family_failed=None)
    assert fired is False and "no 2009-2015 edge" in why
```

**Impact:** 9 new tests, no existing test body touched.

---

### Step 10: command-level tests

**File:** `engine/tests/test_lab_hardgate.py` — append a new section at the end of the file. It
reuses `_benchmark`, `_method`, `_variant`, `_curve`, `_months`, `DEV_SPAN` and the autouse
`_at_the_policy_these_fixtures_were_recorded_under` fixture already in the module.

The curves were verified numerically against the real `walkforward` before being written down:
`M0001-A` dipped reads era MAR **0.382** and era edge **+7.0%**; `M0001-Z` monotone at 2% reads era
MAR **inf** and era edge **−6.0%**; all four folds pick `M0001-A` and it wins all four.

**Code:**

```python
# ------------------------------------------------------------------ the era edge names its arm
#
# F5 of the 2026-10-20 fold-selector audit. The column reported whichever arm had the highest MAR
# over 2009-2015 itself; the buy signal spends its recommendation on the arm `lab promote` would
# pre-register. Over the committed lab those were different arms for 39 of 74 dev-eligible
# methods and disagreed on sign for 18. Both directions are pinned here, because the defect is
# not that the old number was generous -- it was wrong in both directions.

_ERA = (date(2009, 1, 1), date(2015, 10, 16))


def _dipped(months: list[date], annual: float, dip: date, depth: float, recover: int = 6) -> str:
    """``_curve``'s trend with one temporary fall of ``depth`` beginning at ``dip``.

    The book leaves the fall exactly back on trend, so the slice's CAGR is the trend's and only its
    max drawdown -- and therefore its MAR -- moves. That is how an arm can earn the most over an
    era and still not be the era's highest-MAR arm, which is the whole shape of M0072.
    """
    def idx(d: date) -> int:
        return d.year * 12 + d.month

    out, v = [], 1.0
    for d in months:
        f = 1.0
        if idx(d) >= idx(dip):
            k = idx(d) - idx(dip)
            if k < recover:
                f = 1.0 - depth * (1.0 - k / recover)
        out.append([d.isoformat(), round(v * f, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _wf_args(db):
    return argparse.Namespace(
        db=db, lab_command="walkforward", method=[], min_train_years=None, eval_years=None,
    )


def test_the_era_column_reports_the_promoted_variant_and_keeps_the_hindsight_arm(
    tmp_path, capsys, monkeypatch
):
    """M0197's and M0243's live shape: the hindsight arm is positive, the promoted arm is not.

    `M0001-A` grows 15% a year and wins every fold; `M0001-Z` grows 2%. The hindsight column names
    A at +7.0% -- and a buy signal fired on that number until 2026-10-20. The arm that would be
    pre-registered is Z, at -6.0%, and that is what the signal is now handed.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    _variant(c, "M0001", "Z", annual=0.02)
    z = c.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-Z'").fetchone()
    c.close()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: z)

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0001"))
    assert "6.0%" in row and "+7.0%" in row          # promoted left, hindsight right
    assert row.index("6.0%") < row.index("+7.0%")
    assert "negative 2009-2015 edge on the variant that would be promoted" in row
    assert "No buy signal" in out
    assert "(hindsight)" in out
    assert "Nothing was recorded. No research store was opened." in out


def test_the_era_column_can_release_a_method_the_hindsight_arm_was_suppressing(tmp_path, capsys):
    """M0072's live shape, and the reason this is a correction rather than a tightening.

    `M0001-A` earns 15% a year through the era but falls 40% inside it, so its era MAR is 0.38;
    `M0001-Z` creeps along at 2% and never falls, so its era MAR is infinite and it is the
    hindsight arm at -6.0%. A is what `lab promote` would pre-register -- same `mar` column, lower
    trial number -- and it reads +7.0%. The old column refused this method on an arm nobody would
    have traded.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", curve_json=_dipped(_months(*DEV_SPAN), 0.15, date(2013, 3, 31), 0.40))
    _variant(c, "M0001", "Z", annual=0.02)
    assert hardgate.promoted_variant(c, "M0001") == "M0001-A"
    c.close()

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0001"))
    assert "+7.0%" in row and "6.0%" in row
    assert row.index("+7.0%") < row.index("6.0%")
    assert "*** BUY SIGNAL ***" in out
    assert "2009-2015 edge on the promoted variant +7.0 pts" in out
    # and the two arms are named underneath, because the signs disagree
    note = next(line for line in out.splitlines() if "hindsight M0001-Z" in line)
    assert "promoted M0001-A" in note


def test_a_method_with_no_promotable_variant_shows_a_dash_and_cannot_fire(
    tmp_path, capsys, monkeypatch
):
    """Four dev-eligible methods are in this state today. The hindsight column still carries their
    number, so no row loses information; the signal gets None and refuses."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _benchmark(c)
    _method(c, "M0001", annual=0.15)
    c.close()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: None)

    from seer_engine.commands import lab as lab_cmd

    assert lab_cmd.run(_wf_args(db)) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.strip().startswith("M0001"))
    assert "+7.0%" in row                               # the hindsight arm is still reported
    assert "no 2009-2015 edge for the variant that would be promoted" in row
    assert "No buy signal" in out
```

**Impact:** 3 new tests, one new helper. No existing test body touched. The two existing
command-level walk-forward tests (`:911`, `:932`, `:1153`) keep passing: their fixtures have at
most one variant per method, so the two columns agree and no footnote prints.

---

## Verification

**Lint:**
```bash
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

**The lab is untouched — run this *before* pytest** (plan-set invariant 1, and
`lab stage` writes into the main checkout):
```bash
cd /home/miftah/seer
sha1sum lab/lab.sqlite                                        # f2ff9ce6... — note it
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab stage
git status --porcelain lab/lab.sqlite web/data/lab.json
```
This phase records no row, so `web/data/lab.json` must come back identical. **`lab/lab.sqlite`
may still read as modified**: a lab command migrates the database on connect, so even a read
dirties the file. That is expected and is not this phase's change — restore it by path
(`git checkout -- lab/lab.sqlite`) and commit neither file. If `web/data/lab.json` has a diff,
something recorded a row and this phase did not do it.

**Tests — the files this phase touches, then the suite:**
```bash
cd /home/miftah/seer
engine/.venv/bin/pytest engine/tests/test_lab_walkforward.py engine/tests/test_lab_hardgate.py \
  engine/tests/test_lab_survivorship.py engine/tests/test_lab_status.py \
  engine/tests/test_lab_shortfall.py engine/tests/test_lab_prereg.py
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
engine/.venv/bin/pytest engine/tests
```

**Manual check — against a COPY, never `lab/lab.sqlite`:**
```bash
SCRATCH=$(mktemp -d)
cp /home/miftah/seer/lab/lab.sqlite "$SCRATCH/lab-copy.sqlite"
sha1sum /home/miftah/seer/lab/lab.sqlite                      # f2ff9ce6... — note it
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine \
  lab --db "$SCRATCH/lab-copy.sqlite" walkforward | tee "$SCRATCH/wf_after.txt"
sha1sum /home/miftah/seer/lab/lab.sqlite                      # unchanged
```
A lab command migrates its database on connect, which is why the copy exists. **Do not run
`lab survivorship`** anywhere in this phase: it journals on every invocation and the journal is
append-only — journal 500 is already a duplicate of 499 from exactly that mistake. **Do not run
`lab test` or `lab promote`**: test-window looks read 4 and must stay 4.

Read in `wf_after.txt`:
- the header carries both `2009-15 edge` and `(hindsight)`;
- `M0179   2 of 4   yes   −5.6%   +0.3%` — R4's two numbers side by side, each against its arm;
- `M0201   … −7.8%   +1.8%` and a footnote line naming `M0201-PLC2-MV10 (control)`;
- the footnote heading says **18** methods;
- the buy-signal block names exactly `M0072`, `M0092`, `M0258`;
- the last line is still `Nothing was recorded. No research store was opened.`

**Exit criteria:**
1. `lab walkforward`'s left edge column is `wf.era_edge` of `hardgate.promoted_variant`'s curve,
   and that same value is what `wf.buy_signal` receives. Pinned by
   `test_the_era_column_reports_the_promoted_variant_and_keeps_the_hindsight_arm`.
2. The hindsight arm's edge is still printed for every row that has one — 168 of 168 on the
   committed lab — under a header that says it is hindsight.
3. `BUY_CONDITIONS[3]` and all three of `buy_signal`'s era messages name the promoted variant;
   `BUY_CONDITIONS[1]` describes the kin rule it is actually handed.
4. **No promotion outcome moves.** `hardgate.check()` has no era clause and is not edited; verify
   with `git diff --stat engine/src/seer_engine/lab/hardgate.py` printing **nothing**, and with
   `test_lab_hardgate.py` and `test_lab_prereg.py` green and their bodies unchanged.
5. The buy-signal set on the committed lab goes `{M0092, M0197, M0243, M0258}` ->
   `{M0072, M0092, M0258}` — two stop, one starts, as measured. (The index says "no buy signal
   fires before or after"; that was wrong before this phase and is wrong after it. See
   **Handoffs**.)
6. `lab walkforward` still opens no research store, records nothing, and prints
   `Nothing was recorded. No research store was opened.`; `lab/lab.sqlite` ends the phase at
   `sha1 f2ff9ce6…` — restored by path if a `lab stage` migrated it on connect — and the commit
   contains no `lab/` or `web/data/` file.
7. Test-window looks read 4.

**The commit message must carry** the before/after firing sets and the M0072 argument. The brief's
rule — *"Any change to `engine/src/seer_engine/lab/hardgate.py` must be argued in the commit
message"* — does not literally bind here, because this phase edits no line of `hardgate.py`. It
binds in spirit: this phase changes what the lab recommends the owner spend money on.

---

## Handoffs

1. **`hardgate.py`'s D13 paragraphs are now out of date — Phase 2.** `hardgate.py:317-320` and
   `:444-452` both say *"``BUY_CONDITIONS`` and the ``buy_signal`` docstring still describe kin as
   'family union ancestors' … they remain the owner's to edit."* Step 2 makes that edit. Phase 2
   owns `hardgate.py`'s module docstring (it adds D18 there), so it should strike those two
   sentences in the same commit rather than this phase reaching into a file another phase is
   editing. D13's **other** outstanding item — *"the signal's fold condition reads the picks'
   record only"*, i.e. whether `buy_signal` should also require D11b's own-variant majority — is
   deliberately **not** done here: it is a change to `buy_signal`'s conditions, which this phase's
   brief forbids. Measured for whoever picks it up: of the three methods that still fire after
   this phase, `M0072`, `M0092` and `M0258`, that clause would be the next thing to ask.
2. **The plan index needs two corrections — the reconciler.** (a) Phase 3's exit criterion *"no
   buy signal fires before or after"* is measured false: four fire today. Replace it with the
   before/after sets. (b) The *Why* section's *"Every change below makes the lab stricter"* needs
   a carve-out: phase 3 makes the fourth buy condition **correct**, which releases M0072 as well
   as suppressing M0197 and M0243. No promotion outcome moves either way, so invariant 5 holds.
3. **`engine/package_readme.md` — the readme-updater.** `:166` lists `walkforward.py`'s exports
   and must gain `era_edge()` and `best_era_arm()`; `:3376` says *"`walkforward.py` is untouched.
   Its `BUY_CONDITIONS` text still says 'family union ancestors'"*, which stops being true.
4. **M0258's promoted arm is a dose rung.** `M0258-M-B0` is *"The dose-response ladder's zero rung
   and the paired bare gate"*, and it is what `best_dev_eligible` would pre-register. That is
   Phase 2's D18 territory (R3), not this phase's — recorded here because this phase is what made
   it visible, and because M0258 is one of the two methods still firing afterwards.
5. **`M0007`, `M0011`, `M0019`, `M0020` carry a stale `dev-eligible` status** that
   `best_dev_eligible` no longer agrees with. Nothing here fixes it and nothing should: the status
   column is frozen history and the verdict is the live bar, and `store.best_dev_eligible`'s
   docstring argues that they are meant to differ. Worth an insight note, not a code change.

---

## Assumptions

- **Phase 1 has landed** and `seer_engine.lab.control_shape` exports `role_of(arm) -> str`
  returning `"control" | "dose" | "idea" | "treatment"`, taking the same `Arm` protocol
  (`.id`, `.rationale`) that `kind_of` takes. `_arm_roles` is written so that a missing `role_of`
  costs only the parenthesised label in one footnote; every test in step 10 passes without it
  except the one assertion on `(control)`, which is not asserted — step 10 asserts only arm ids.
- **Phase 2 has not changed `check()`'s era behaviour**, because `check()` has no era clause. This
  is checked directly in exit criterion 4 rather than assumed.
- The lab database is at `lab/lab.sqlite` with `sha1 f2ff9ce6…` and 168 methods carrying dev
  curves, 78 of them `dev-eligible`. Every count quoted above was measured against a copy of that
  file on 2026-10-20. If a lab run lands between planning and implementation, re-measure: the
  counts move, the shape does not.

---

## Rollback

One commit touching four files, no migration, no recorded row, no lab state, no method id:

```bash
git revert <sha>
```

The report returns to reading the hindsight arm and the buy signal to firing on
`{M0092, M0197, M0243, M0258}`. Nothing promoted, tested or recorded depends on this phase, so a
revert cannot strand a row. The only durable consequence of leaving it in place is that the owner
may act on `M0072`'s firing by buying survivorship-free price history — which is the decision the
condition exists to put in front of him, now measured on the arm he would actually hold.
