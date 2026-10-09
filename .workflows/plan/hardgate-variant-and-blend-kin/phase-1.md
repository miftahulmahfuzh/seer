# Phase 1 — The promoted variant's own folds (D11), ingredients as kin (D12), the buy signal follows (D13)

**Plan index:** `HARDGATE_VARIANT_AND_BLEND_KIN_PLAN.md`
**Satisfies:** R1, R2
**Depends on:** —
**Worktree:** `/home/miftah/.worktrees/seer/hardgate-variant-and-blend-kin` (branch `feature/hardgate-variant-and-blend-kin`, base `9560a6b`)

Paths below are relative to the worktree root unless absolute. `$WT` = the worktree root.

## Ground rules (the owner's, non-negotiable — read before touching anything)

1. **No override of any kind.** No flag, no env variable, no "promote anyway". `tests/test_lab_hardgate.py::test_there_is_no_override` greps `hardgate.py`'s **source** for `force`, `override`, `skip_gate`, `SEER_SKIP`, `getenv`, `environ` after deleting the phrases "no override" / "There is no override". So in `hardgate.py` **never write** the words "enforce", "enforced", "force", "environment", or "override" except inside "no override". The docstring text below is already clean; keep it that way if you reword anything.
2. **Do not edit `engine/src/seer_engine/lab/walkforward.py`** at all — not `buy_signal`, not its docstring, not `BUY_CONDITIONS`. Decision D13 records what the owner has to decide there.
3. **Never write to `lab/lab.sqlite`.** Experiments run on scratch copies in `/tmp/claude-1000/...scratchpad` or `$TMPDIR`. trials and test-failed are final and append-only.
4. **Commit by pathspec, never `git add -A` / `git add .`.** Sera is running in another tmux window and commits `lab/lab.sqlite` to main. Only the files listed under "Files" below are staged.
5. **Run the engine as** `PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python` (the main venv is an editable install of the *main* checkout; `PYTHONPATH` puts this tree in front of it). Tests: `cd $WT/engine && PYTHONPATH=src /home/miftah/seer/engine/.venv/bin/python -m pytest …`.

## Files

| File | Change |
|---|---|
| `engine/src/seer_engine/lab/hardgate.py` | docstring: rule bullets + D11, D12, D13; `import re`; `_INGREDIENT`; `promoted_variant`; `variant_record`; `_lineage`; `ingredients`; `failed_kin` rewritten; `summary`; `check` |
| `engine/src/seer_engine/lab/prereg.py` | `fold_text` records the pre-registered variant's own record; `family_text` wording |
| `engine/src/seer_engine/commands/lab.py` | "Refused by the hard gate" header text (line ~1009); kin comment (line ~2048) |
| `engine/tests/test_lab_hardgate.py` | new tests: D11 unit, D12 kin, docstring markers |
| `engine/tests/test_lab_status.py` | new tests: D11 end to end through `lab status` and `lab promote` |

Nothing else. In particular no schema change: ingredients are already recorded (see D12).

---

## Step 1 — `hardgate.py` module docstring

### 1a. The rule bullets (top of the file)

Replace:

```python
- **(F) the folds.** It beat the recorded benchmark in a strict majority of the walk-forward
  folds (``walkforward.Record.majority``), and it was scoreable on *every* fold the geometry
  yields, and there were at least ``MIN_FOLDS`` of them.
- **(K) the kin.** No other method in its ``family``, and no transitive ancestor through
  ``parent_id``, reads ``test-failed``.
```

with:

```python
- **(F) the folds.** It beat the recorded benchmark in a strict majority of the walk-forward
  folds (``walkforward.Record.majority``), and it was scoreable on *every* fold the geometry
  yields, and there were at least ``MIN_FOLDS`` of them. **And** the variant ``lab promote``
  would pre-register (``store.best_dev_eligible``) clears the same bar on its own curve alone
  -- see **(D11)**.
- **(K) the kin.** No other method in its ``family``, no transitive ancestor through
  ``parent_id``, no **ingredient** -- a lab method whose engine one of its variants runs, a
  blend's parts included -- and nothing in an ingredient's own ``family`` or ancestry reads
  ``test-failed`` -- see **(D12)**.
```

### 1b. New decisions

Insert the following **immediately before the closing `"""`** of the module docstring (i.e. after the paragraph that ends `...because a recorded curve is normalised to its own opening cash.`). Keep the blank line between that paragraph and the new text.

```text

**(D11) Whose folds does (F) score? -- the training slice's pick in each fold, as before, AND
the exact variant ``lab promote`` would pre-register, on its own curve. Both must win a strict
majority, scoreable on every fold.**

``walkforward.evaluate`` asks how the lab's *selection process* did out of sample: in each fold
it scores whichever variant ranked best by MAR on the training slice. ``lab promote`` then spends
the look, and later the money, on something else: ``store.best_dev_eligible``, the highest-MAR
variant the verdict calls eligible over the whole dev window. The two need not be the same
variant, and for M0044 they are not (insight 82). The training slices pick its lighter brakes,
which fail the dev gate on drawdown and so can never be pre-registered; those picks win 3 of 4.
``M0044-TV14-N21``, its only eligible variant and therefore the one that would be promoted, wins
1 of 4 on its own curve -- folds of -5, +24, -42 and -12 points of total return against SPY --
and trails SPY by about 7 points a year over 2009-2015. Under the rule before this one the gate
took it, and ``lab status`` listed it as promotable.

``variant_record`` scores the promoted variant through the **same** ``walkforward.evaluate``,
handed a mapping of one: ``pick`` can then only name that variant, so every fold is that curve,
de-funded by the same ``trial_deposits``, against the same benchmark, on the same geometry,
refused on the same price rule (D10). Nothing about the scoring is new; only the candidate set
is.

Measured on the committed lab (70 methods, 10 dev-eligible), dev-eligible methods each version
of the fold rule blocks:

====================================  ==========  ============================================
fold rule                             blocks      which
====================================  ==========  ============================================
the pick's record only (before)       5 of 10     M0011, M0024, M0028, M0030, M0053
the promoted variant's own only       6 of 10     adds M0019 (2 of 4) and M0044 (1 of 4);
                                                  **drops M0053**, whose own variant wins 3 of 4
                                                  while its picks win 2 of 4
**both**                              **7 of 10**  the union
====================================  ==========  ============================================

Why not the promoted variant alone. ``best_dev_eligible`` chooses on the **whole** dev window,
which contains every fold's evaluation slice, so the chosen variant's own fold record is not out
of sample about the *choice*: it is the record of a variant picked with hindsight over exactly
those slices. The pick's record is the out-of-sample statement about the choosing; the own record
is the statement that the variant actually bet on is not riding on its siblings' wins. Each
answers a question the other cannot, which is why the rule is the conjunction -- and why M0053,
whose choosing loses, stays refused.

Together with (K) the whole gate refused 9 of the 10 dev-eligible methods before this decision
and refuses 10 of 10 after it; M0044 is the one it moves. ``lab status`` prints
``Promotable now: (none)``.

Silent when ``best_dev_eligible`` names nothing. There is then nothing to pre-register, and the
caller one line later is ``prereg.promote_method``, which refuses with the better message it
already has -- the same reason ``check`` is silent for a status other than ``dev-eligible``. The
variant is named by the very call ``promote_method`` makes, on the same connection, so the gate
cannot score one variant while the file pre-registers another.

**(D12) Does (K) look inside a blend? -- Yes. An ingredient is any other lab method whose
allocator one of the method's dev trials runs, read from the recorded ``trials.config_text``;
the ingredient itself, and its own ``family`` union ancestors, are kin. One hop, not the
ingredient's ingredients.**

M0028's ``BLEND-RM`` is half M0028's bounce book and half ``M0007-N20-RAW``'s residual momentum,
whose family's M0022 read ``test-failed``. It cleared the dev gate, and (K) as written read M0028's
kin clean, because the blend shares neither a ``family`` string nor a ``parent_id`` with M0007;
only the fold record (2 of 4) stopped it (insight 84). A blend is a *variant* of a method, not a
method, so nothing in ``methods`` could ever have carried the link.

**The ingredients are already recorded; nothing new is stored.** ``lab/method.py:config_text`` is
each trial's identity, digested and append-only, and ``registry._canon`` writes every allocator in
it -- the top-level one and every one nested anywhere in the params, a blend's parts and a blend of
blends included -- as ``<ID>``. A lab allocator's id is the id of the method whose file defines it
(every ``M*`` allocator in ``lab/methods/mNNNN_*.py`` reads ``id = "MNNNN"``; ``method.py``: "allocator
ids are unique across lab methods"). So ``<M0007>`` in a trial's config text is M0007's engine, and
``ingredients`` is a regular expression over text the lab has written on every trial since the
first. ``BLEND``, ``F1``, ``ROT``, ``VOLTARGET`` and the other seed allocators name no lab method and
are not ingredients; the ``H-*`` seeds they belong to are all ``rejected``, none ``test-failed``.

Measured on the committed lab. The ingredient map: M0004 -> M0001; M0021 -> M0007, M0011;
M0024 -> M0011; M0028 -> M0007; M0029 -> M0007; M0030 -> M0007; M0032 -> M0007; M0033 -> M0011.

=============================================  ===========  ==================================
kin rule                                       of 70        dev-eligible blocked (of 10)
=============================================  ===========  ==================================
``family`` union ancestors (D4, before)        29           6
**+ ingredients and their family union         **31**       **8** -- adds M0024 (via M0011)
ancestors, every dev variant**                              and M0028 (via M0007), both on M0022
+ ingredients of the promoted variant only     --           8, the same two
+ ingredients followed transitively            31           8, the same two
=============================================  ===========  ==================================

It refuses nobody new today -- M0024 and M0028 already lose their picks' folds -- and that is the
point: the next blend with a disproven engine in it will not have a fold record that happens to
catch it.

Why every dev variant and not only the promoted one. The cost is identical today. Every variant is
a candidate in every fold's pick, which is (D10)'s reason for refusing on any one variant; and kin
is a statement about a *method* -- ``family_state``, the buy signal and ``lab test``'s note all ask
it of a method, which has no single variant. The price is stated rather than hidden: a method that
carries a readout blend with a disproven engine is refused whole. M0028's own hypothesis already
said its ``BLEND-RM`` "can never be promoted"; a standalone book that wants a clean kin should not
carry the readout as one of its variants.

Why one hop. The config text already names every engine a variant runs, at any depth of nesting,
so nothing a variant actually runs is missed. What one hop declines to follow is an ingredient
*method's other variants'* ingredients -- engines this method never runs -- which is (D4)'s
connected-component blob arrived at by another road. Measured, it changes nothing today.

**(D13) Does the buy signal follow (D12)? -- Yes, through its caller, with no edit to
``walkforward.buy_signal``. What it does not follow is (D11), and that is the owner's to decide.**

``lab walkforward`` passes ``hardgate.failed_kin`` as the signal's ``family_failed``, and (D9)
aligned the two on purpose: two commands giving opposite answers about one method is worse than
either answer. So ``failed_kin`` stays the one definition of kin, the signal's kin condition
widens with it, and this paragraph is the record that it does. Measured on the committed lab the
report's output is unchanged: no signal fires before or after, and M0024 and M0028 still read
"fails the folds", the first condition they fail.

Left for the owner, because each is an edit to ``walkforward.py``, which this decision does not
make: ``BUY_CONDITIONS`` and the ``buy_signal`` docstring still describe kin as "family union
ancestors", which now under-describes the rule they are handed; and the signal's fold condition
reads the picks' record only. Whether the buy signal should also require (D11)'s own-variant
majority is a change to ``buy_signal`` itself.
```

Note the table's middle row of D12 wraps over two lines; that is how the existing D4/D10 tables wrap too — it is prose in a docstring, not parsed RST, so exact column alignment is cosmetic. Keep each line ≤ 100 chars like the rest of the docstring.

---

## Step 2 — `hardgate.py` code

### 2a. Imports

Replace:

```python
import json
import sqlite3
```

with:

```python
import json
import re
import sqlite3
```

### 2b. The ingredient pattern

Immediately after the `_GATED_STATUS = "dev-eligible"` line (and its comment above it), add:

```python

#: How a recorded configuration names the lab methods whose engines it runs. ``method.config_text``
#: writes every allocator -- top level and nested, a blend's parts included -- as ``<ID>``
#: (``registry._canon``), and a lab allocator's id is its method's id. See (D12).
_INGREDIENT = re.compile(r"<(M\d{4})>")
```

### 2c. `promoted_variant` and `variant_record`

Insert directly **after** `fold_record` (i.e. before `def fold_summary`):

```python
def promoted_variant(conn: sqlite3.Connection, method_id: str) -> str | None:
    """The candidate ``lab promote`` would pre-register, or None when there is none.

    ``store.best_dev_eligible`` -- the very call ``prereg.promote_method`` makes -- so the variant
    the gate scores under (D11) and the variant the file pre-registers cannot be two different
    rows.
    """
    best = store.best_dev_eligible(conn, method_id)
    return None if best is None else str(best["candidate_id"])


def variant_record(
    conn: sqlite3.Connection, method_id: str, candidate_id: str, geo: Geometry | None = None
) -> wf.Record:
    """``candidate_id``'s own walk-forward record: that one variant's curve, alone. See (D11).

    The same ``wf.evaluate`` ``fold_record`` calls, handed a mapping of one, so ``pick`` can only
    name this variant and every fold scores exactly the curve that would be pre-registered --
    de-funded by the same ``trial_deposits``, against the same benchmark, on the same geometry,
    refused on the same price rule (D10). Raises ``store.LabError`` when the variant has no dev
    curve or cannot be compared.
    """
    geo = geometry(conn) if geo is None else geo
    rows = [r for r in _dev_curves(conn, method_id) if r["candidate_id"] == candidate_id]
    if not rows:
        raise store.LabError(
            f"{candidate_id} has no dev trial of {method_id} carrying a monthly curve, so the "
            f"variant that would be pre-registered cannot be scored on the folds. The hard gate "
            f"fails closed on thin evidence"
        )
    problems = mismatches(conn, geo.bench_n, rows)
    if problems:
        raise store.LabError(
            f"{candidate_id} cannot be scored against {regime.BENCH_CANDIDATE}: "
            f"{describe(problems)}. The hard gate compares two curves only when both were "
            f"measured on the same prices (D10). There is no override"
        )
    row = rows[0]
    curve = _curve_of(row)
    deposits = {candidate_id: trial_deposits(conn, row, curve)}
    return wf.Record(
        method_id, wf.evaluate({candidate_id: curve}, list(geo.bench), geo.folds, deposits)
    )
```

(`trials` has `UNIQUE (candidate_id, window)`, so `rows` holds at most one row.)

### 2d. Kin: `_lineage`, `ingredients`, `failed_kin`

Replace the whole of the existing `failed_kin` function (from `def failed_kin(` through its `return tuple(str(r["id"]) for r in bad)`) with:

```python
def _lineage(conn: sqlite3.Connection, row: sqlite3.Row) -> set[str]:
    """``row``'s ``family`` union its transitive ancestors through ``parent_id`` -- (D4)'s set.

    It contains the method itself, which is in its own family; ``failed_kin`` discards it. The
    ancestor walk carries a ``seen`` set: ``methods.parent_id`` is a self-referencing foreign key
    with no cycle constraint, so a cycle would otherwise hang the gate.
    """
    ancestors: set[str] = set()
    cur = row["parent_id"]
    while cur is not None and cur not in ancestors:
        ancestors.add(str(cur))
        parent = store.get_method(conn, str(cur))
        cur = None if parent is None else parent["parent_id"]

    kin = set(ancestors)
    for r in conn.execute("SELECT id FROM methods WHERE family = ?", (row["family"],)):
        kin.add(str(r["id"]))
    return kin


def ingredients(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """Every other lab method whose engine one of ``method_id``'s dev trials runs. See (D12).

    Read from ``trials.config_text`` -- the recorded, digested identity of each trial -- where
    every allocator the configuration runs, at any depth of nesting, is written ``<ID>``. Only ids
    that name a row in ``methods`` count, so a stray ``<M9999>`` is not an ingredient, and the
    method's own allocator is not its own ingredient.
    """
    found: set[str] = set()
    for r in conn.execute(
        "SELECT config_text FROM trials WHERE method_id = ? AND window = 'dev'", (method_id,)
    ):
        found.update(_INGREDIENT.findall(str(r["config_text"])))
    found.discard(method_id)
    if not found:
        return ()
    ids = sorted(found)
    marks = ", ".join("?" for _ in ids)
    known = conn.execute(
        f"SELECT id FROM methods WHERE id IN ({marks}) ORDER BY id", tuple(ids)
    ).fetchall()
    return tuple(str(r["id"]) for r in known)


def failed_kin(conn: sqlite3.Connection, method_id: str) -> tuple[str, ...]:
    """Every method in ``method_id``'s kin that reads ``test-failed``; ``()`` when clean.

    Kin is the ``family`` string **union** the transitive ancestors reached through
    ``parent_id`` (D4), **union** every ingredient -- a lab method whose engine one of its
    variants runs -- together with that ingredient's own ``family`` and ancestors (D12),
    excluding the method itself. One hop: an ingredient's *other* variants' ingredients are not
    followed. See the module docstring for the measurements that decided both.

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
    if not kin:
        return ()

    ids = sorted(kin)
    marks = ", ".join("?" for _ in ids)
    bad = conn.execute(
        f"SELECT id FROM methods WHERE id IN ({marks}) AND status = 'test-failed' ORDER BY id",
        tuple(ids),
    ).fetchall()
    return tuple(str(r["id"]) for r in bad)
```

### 2e. `summary`

Replace the whole `summary` function with:

```python
def summary(conn: sqlite3.Connection, method_id: str, geo: Geometry | None = None) -> str:
    """One display line for ``method_id``: the fold record, the promoted variant's own, the kin.

    ``"3 of 4 folds; M0044-TV14-N21 alone 1 of 4 folds; kin clean"``. The middle clause is
    (D11)'s second condition, and it is printed only when the picks' record could be built and
    there is a variant to pre-register -- when the record itself is not scoreable the reason is
    already on the line, and repeating it for the variant would only make it longer.

    Lenient on purpose -- it catches ``store.LabError`` and returns the reason as text. Its
    caller is ``lab status``, which must keep printing on a lab whose benchmark is missing or
    whose method has no curve. A report that dies on one row is a worse report than one that says
    why that row is blank.
    """
    try:
        folds = fold_record(conn, method_id, geo).summary()
    except store.LabError as e:
        folds = f"not scoreable ({e})"
    else:
        try:
            candidate = promoted_variant(conn, method_id)
            if candidate is not None:
                own = variant_record(conn, method_id, candidate, geo)
                folds = f"{folds}; {candidate} alone {own.summary()}"
        except store.LabError as e:
            folds = f"{folds}; the promoted variant is not scoreable ({e})"
    try:
        kin = family_state(conn, method_id)
    except store.LabError as e:
        kin = f"kin unknown ({e})"
    return f"{folds}; kin {kin}"
```

(`summary` must stay defined **after** `promoted_variant`, `variant_record` and `family_state`
only for readability — Python resolves at call time, so order is not load-bearing.)

### 2f. `check`

In the `check` docstring, replace the paragraph:

```python
    The folds are checked before the kin. (F) is a statement about *this* method's own evidence,
    which is what the researcher asked about; (K) is about the company it keeps, and reads better
    second. Both are cheap -- SQL and arithmetic on recorded curves -- so the order is about the
    message, not the cost.
```

with:

```python
    The folds are checked before the kin. (F) is a statement about *this* method's own evidence,
    which is what the researcher asked about; (K) is about the company it keeps, and reads better
    second. Within (F) the picks' record comes first and the promoted variant's own record second
    (D11): the first says whether the lab's way of choosing works out of sample, the second
    whether the variant actually chosen won its folds itself. All of it is cheap -- SQL and
    arithmetic on recorded curves -- so the order is about the message, not the cost.
```

Then, in the body, **between** the existing `if not record.majority:` block (which ends with `... argue for it in the commit"\n        )`) and the line `    bad = failed_kin(conn, method_id)`, insert:

```python

    candidate = promoted_variant(conn, method_id)
    if candidate is not None:
        own = variant_record(conn, method_id, candidate, geo)
        own_scored = len(own.scored)
        if own_scored < total:
            raise store.LabError(
                f"{method_id}'s variant {candidate} -- the one `lab promote` would pre-register "
                f"-- is scoreable on only {own_scored} of the {total} walk-forward folds on its "
                f"own curve. The hard gate fails closed on thin evidence (D2, D11). Nothing was "
                f"written and no status moved"
            )
        if not own.majority:
            raise store.LabError(
                f"{method_id} wins {record.summary()} on the variants the training slices "
                f"picked, but {candidate} -- the variant `lab promote` would pre-register -- "
                f"wins only {own.won} of {own_scored} on its own curve, and is not promoted. "
                f"The picks' record is about the lab's way of choosing; the look and the money "
                f"are spent on one variant, and that variant has to have won the folds itself "
                f"(D11). Nothing was written and no status moved. There is no override -- if the "
                f"rule is wrong, change it in seer_engine/lab/hardgate.py and argue for it in "
                f"the commit"
            )
```

And replace the kin refusal message:

```python
            f"{method_id} is not promoted: {', '.join(bad)} already read test-failed, and "
            f"{'they are' if len(bad) > 1 else 'it is'} kin -- same family ({row['family']!r}) "
            f"or an ancestor through parent_id. A new variant of a family that has been disproven "
            f"out of sample is not a fresh candidate. Nothing was written and no status moved. "
            f"There is no override -- if this family deserves another look, that is an argued "
            f"change to the rule, in git"
```

with:

```python
            f"{method_id} is not promoted: {', '.join(bad)} already read test-failed, and "
            f"{'they are' if len(bad) > 1 else 'it is'} kin -- same family ({row['family']!r}), "
            f"an ancestor through parent_id, or an ingredient one of its variants runs (or that "
            f"ingredient's family or ancestry, D12). A new variant of a family that has been "
            f"disproven out of sample is not a fresh candidate, and neither is a blend with a "
            f"disproven engine in it. Nothing was written and no status moved. There is no "
            f"override -- if this family deserves another look, that is an argued change to the "
            f"rule, in git"
```

**Grep after editing:** `grep -n -i "force\|environ\|getenv\|skip_gate" engine/src/seer_engine/lab/hardgate.py` must print nothing, and every `override` hit must be inside "no override".

---

## Step 3 — `prereg.py`

### 3a. `fold_text`

Replace the body's tail — from `    try:\n        rec = hardgate.fold_record(conn, method_id)` to the end of the function — with:

```python
    try:
        rec = hardgate.fold_record(conn, method_id)
    except store.LabError as e:
        return one_line(f"not recorded: the fold record could not be built ({e})")
    scored = len(rec.scored)
    try:
        candidate = hardgate.promoted_variant(conn, method_id)
        if candidate is None:
            own = "the pre-registered variant's own record not recorded: no eligible variant"
        else:
            o = hardgate.variant_record(conn, method_id, candidate)
            own = f"{candidate} alone won {o.won} of {len(o.scored)}"
    except store.LabError as e:
        own = f"the pre-registered variant's own record not recorded ({e})"
    return one_line(
        f"{rec.won} of {scored} scoreable walk-forward fold(s) won, "
        f"pick {'stable' if rec.stable else 'changed'} across folds; {own}; the bar this method "
        f"cleared was a strict majority of at least {hardgate.MIN_FOLDS} scoreable folds, for "
        f"the picks and for the pre-registered variant alone (hardgate D11)"
    )
```

and in the `fold_text` docstring replace the sentence

```
    pre-registration to add: how many folds the pick won, how many could be scored at all, and
    whether the training slice kept choosing the same variant.
```

with

```
    pre-registration to add: how many folds the pick won, how many could be scored at all, and
    whether the training slice kept choosing the same variant -- plus, since hardgate (D11), how
    many the pre-registered variant won on its own curve, which is the second half of the bar.
```

(`tests/test_lab_prereg.py` monkeypatches `hardgate.fold_record` and asserts the line starts with `"3 of 4 "`, contains `"pick changed across folds"` and `str(MIN_FOLDS)`, and is one line — all still true; `variant_record` on that fixture raises `LabError` (no benchmark) and is caught.)

### 3b. `family_text`

Replace the docstring's first paragraph sentence

```
    ``hardgate.failed_kin`` is the one definition of kin -- the method's ``family`` string together
    with its transitive ancestors through ``parent_id`` (plan Decision D4) -- and this line quotes
    its answer rather than re-deriving it, so the file and the rule cannot disagree.
```

with

```
    ``hardgate.failed_kin`` is the one definition of kin -- the method's ``family`` string together
    with its transitive ancestors through ``parent_id`` (plan Decision D4), and its ingredients
    with theirs (hardgate D12) -- and this line quotes its answer rather than re-deriving it, so
    the file and the rule cannot disagree.
```

and the two returned strings:

```python
        return one_line(
            f"clean at promotion: no method in {method_id}'s family '{family}' or ancestry read "
            f"test-failed"
        )
    return one_line(
        f"blocked at promotion: {', '.join(failed)} in {method_id}'s family '{family}' or "
        f"ancestry read test-failed"
    )
```

with

```python
        return one_line(
            f"clean at promotion: no method in {method_id}'s family '{family}', ancestry or "
            f"ingredients (or theirs) read test-failed"
        )
    return one_line(
        f"blocked at promotion: {', '.join(failed)} in {method_id}'s family '{family}', ancestry "
        f"or ingredients (or theirs) read test-failed"
    )
```

---

## Step 4 — `commands/lab.py`

### 4a. The "Refused by the hard gate" header (`_promotable_now`, ~line 1009)

Replace:

```python
            "  Refused by the hard gate (dev-eligible, but `lab promote` exits 2 on these -- it "
            "wants a majority of walk-forward folds and no kin that has test-failed; there is no "
            "override):"
```

with:

```python
            "  Refused by the hard gate (dev-eligible, but `lab promote` exits 2 on these -- it "
            "wants a majority of walk-forward folds, won by the picks and by the variant it would "
            "pre-register, and no kin -- family, ancestry or blend ingredient -- that has "
            "test-failed; there is no override):"
```

Also in `_promotable_now`'s docstring, the sentence ``lab promote`` also refuses a method that lost a majority of its walk-forward folds, or whose kin has already failed the test window`` — append after "walk-forward folds" the words ", or whose variant that would be pre-registered lost them on its own curve". (Text only.)

### 4b. The kin comment in `lab walkforward` (~line 2048)

Replace:

```python
        # The SAME kin rule the promote gate uses (hardgate.failed_kin: family union transitive
        # ancestors), not a second family-only query beside it. Decision D9 is what happens when
        # these two disagree: the signal said M0030's family was clean while the gate refused it
        # on ancestry, which is a worse answer than either one alone.
```

with:

```python
        # The SAME kin rule the promote gate uses (hardgate.failed_kin: family union transitive
        # ancestors union blend ingredients and theirs, hardgate D12), not a second query beside
        # it. Decision D9 is what happens when these two disagree: the signal said M0030's family
        # was clean while the gate refused it on ancestry, which is a worse answer than either one
        # alone. That the signal widens with D12 is recorded as hardgate Decision D13.
```

---

## Step 5 — Tests

### 5a. `engine/tests/test_lab_hardgate.py`

1. After `test_the_module_answers_the_four_open_questions`, add:

```python
def test_the_module_records_the_variant_and_ingredient_decisions():
    """Insights 82 and 84: each rule change is argued, measured, in the docstring (D11-D13)."""
    doc = hardgate.__doc__ or ""
    for marker in ("(D11)", "(D12)", "(D13)"):
        assert marker in doc
    assert "M0044-TV14-N21" in doc       # D11's live case, named
    assert "BLEND-RM" in doc             # D12's live case, named
```

2. Add a helper and the D11 unit tests after the kin tests (after `test_a_parent_cycle_does_not_hang_the_kin_walk`):

```python
# ------------------------------------------------------------------ (D11) the promoted variant


def _variant(conn, mid: str, suffix: str, *, annual: float, config_text: str = "t",
             curves: bool = True) -> None:
    """A second dev trial of an existing method -- another variant -- stamped on the lab's prices."""
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}", config_digest=f"d-{mid}-{suffix}",
            config_text=config_text,
            curve_json=_curve(_months(*DEV_SPAN), annual) if curves else "[]",
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def test_a_variant_is_scored_on_its_own_curve_not_on_its_siblings_picks(conn):
    """Insight 82's shape: the picks win every fold, the variant that would be promoted loses all.

    Both curves are monotone, so every training slice ranks both at an infinite MAR and `pick`
    breaks the tie on the candidate id: `M0001-A` (the 15% curve) is picked in every fold. The
    2% curve `M0001-Z` is never picked -- and is what `variant_record` must score.
    """
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _variant(conn, "M0001", "Z", annual=0.02)
    picks = hardgate.fold_record(conn, "M0001")
    own = hardgate.variant_record(conn, "M0001", "M0001-Z")
    assert picks.won == 4 and picks.majority
    assert own.won == 0 and not own.majority
    assert len(own.scored) == hardgate.MIN_FOLDS
    assert {p.picked for p in own.picks} == {"M0001-Z"}


def test_a_variant_with_no_curve_cannot_be_scored(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    with pytest.raises(store.LabError) as e:
        hardgate.variant_record(conn, "M0001", "M0001-Q")
    assert "M0001-Q" in str(e.value)


def test_a_variant_on_other_prices_is_refused(conn):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-Z", config_digest="d-z",
            curve_json=_curve(_months(*DEV_SPAN), 0.15),
        )])
        stamp_provenance(conn, ns, price_fingerprint=OTHER_PRICES)
    with pytest.raises(store.LabError) as e:
        hardgate.variant_record(conn, "M0001", "M0001-Z")
    assert "D10" in str(e.value)


def test_the_gate_is_silent_on_the_variant_when_nothing_would_be_pre_registered(conn, monkeypatch):
    """`promote_method` refuses a method with no eligible variant one line later (D11)."""
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: None)
    assert hardgate.promoted_variant(conn, "M0001") is None
    hardgate.check(conn, "M0001")  # the picks win 4 of 4, kin clean, no variant: no refusal here


def test_the_gate_refuses_when_the_promoted_variant_loses_its_own_folds(conn, monkeypatch):
    _benchmark(conn)
    _method(conn, "M0001", annual=0.15)
    _variant(conn, "M0001", "Z", annual=0.02)
    best = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-Z'").fetchone()
    monkeypatch.setattr(store, "best_dev_eligible", lambda _c, _m, **_k: best)
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0001")
    msg = str(e.value)
    assert "M0001-Z" in msg and "0 of 4" in msg and "D11" in msg
    assert "4 of 4 folds" in msg            # the picks' record, which alone would have passed
    line = hardgate.summary(conn, "M0001")
    assert "M0001-Z alone 0 of 4 folds" in line
```

3. The D12 tests, after the D11 block:

```python
# ------------------------------------------------------------------ (D12) ingredients are kin

BLEND_OF = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\nallocator=<BLEND>\n"
    "params=BlendParams(parts=(BlendPart(allocator=<{own}>,share=0.5),"
    "BlendPart(allocator=<{other}>,share=0.5)))\n"
)


def test_a_blend_with_a_disproven_engine_in_it_is_kin_of_the_failure(conn):
    """Insight 84's case: M0028-BLEND-RM runs M0007's engine; M0007's family failed via M0022."""
    _benchmark(conn)
    _method(conn, "M0022", family="residual", status="test-failed")
    _method(conn, "M0007", family="residual", annual=0.15)
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "BLEND-RM", annual=0.15,
             config_text=BLEND_OF.format(own="M0028", other="M0007"))
    assert hardgate.ingredients(conn, "M0028") == ("M0007",)
    assert hardgate.failed_kin(conn, "M0028") == ("M0022",)
    assert hardgate.family_state(conn, "M0028") == "blocked: M0022 read test-failed"
    with pytest.raises(store.LabError) as e:
        hardgate.check(conn, "M0028")
    assert "M0022" in str(e.value) and "ingredient" in str(e.value)


def test_a_disproven_ingredient_is_itself_kin(conn):
    _benchmark(conn)
    _method(conn, "M0029", family="blended", status="test-failed")
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "BLEND", annual=0.15,
             config_text=BLEND_OF.format(own="M0028", other="M0029"))
    assert hardgate.failed_kin(conn, "M0028") == ("M0029",)


def test_only_lab_methods_are_ingredients(conn):
    """`<BLEND>`, `<F1>` name seed allocators, not methods; `<M9999>` names no row; and a method's
    own allocator is not its own ingredient."""
    _benchmark(conn)
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "X", annual=0.15,
             config_text="allocator=<BLEND>\nparams=(<F1>,<M9999>,<M0028>)\n")
    assert hardgate.ingredients(conn, "M0028") == ()
    assert hardgate.failed_kin(conn, "M0028") == ()


def test_an_ingredients_other_variants_are_not_followed(conn):
    """One hop (D12): M0028 runs M0030's engine; a *different* variant of M0030 blends M0007,
    whose family failed. M0028 never runs M0007, so it is not M0007's kin. M0030 itself is."""
    _benchmark(conn)
    _method(conn, "M0022", family="residual", status="test-failed")
    _method(conn, "M0007", family="residual", annual=0.15)
    _method(conn, "M0030", family="core-satellite", annual=0.15)
    _variant(conn, "M0030", "C50", annual=0.15,
             config_text=BLEND_OF.format(own="M0030", other="M0007"))
    _method(conn, "M0028", family="reversal", annual=0.15)
    _variant(conn, "M0028", "ON-M0030", annual=0.15, config_text="allocator=<M0030>\n")
    assert hardgate.failed_kin(conn, "M0030") == ("M0022",)
    assert hardgate.failed_kin(conn, "M0028") == ()


def test_a_nested_blend_names_every_engine_it_runs(conn):
    """The config text renders nesting in full, so a blend of a blend still names M0007."""
    _benchmark(conn)
    _method(conn, "M0022", family="residual", status="test-failed")
    _method(conn, "M0007", family="residual", annual=0.15)
    _method(conn, "M0028", family="reversal", annual=0.15)
    nested = ("allocator=<BLEND>\nparams=BlendParams(parts=(BlendPart(allocator=<M0028>),"
              "BlendPart(allocator=<BLEND>,params=BlendParams(parts=(BlendPart(allocator=<M0007>),"
              "))),))\n")
    _variant(conn, "M0028", "NEST", annual=0.15, config_text=nested)
    assert hardgate.failed_kin(conn, "M0028") == ("M0022",)
```

Notes for the implementer on these fixtures:
- `_method` in this file always gives the first variant the candidate id `<mid>-A` and the default `config_text="t"`; `_variant` adds more. Both stamp provenance on `SAME_PRICES`.
- In `test_a_blend_with_a_disproven_engine_in_it_is_kin_of_the_failure`, `check` reaches (K): both M0028 curves win every fold, and `best_dev_eligible` on these fixtures returns `None` (verified while planning — the hardgate fixtures are not verdict-eligible), so (D11) is silent and the refusal is the kin's.
- The existing `test_a_failed_descendant_does_not_reach_up_through_parent_id`, `test_the_method_itself_is_never_its_own_kin`, `test_a_parent_cycle_does_not_hang_the_kin_walk` must keep passing unchanged — they pin D4, which D12 extends and does not replace.

### 5b. `engine/tests/test_lab_status.py` — D11 end to end, on fixtures the real verdict calls eligible

Add after `test_a_method_whose_kin_test_failed_is_refused_and_the_kin_is_named`:

```python
def _lab_where_the_pick_is_not_the_promoted_variant(c) -> None:
    """Insight 82's shape on a lab the real verdict can judge.

    ``M0001-B`` fails the dev gate on drawdown (0.35), so it can never be pre-registered; its
    curve compounds at 0.009 a month and wins every fold. ``M0001-Z`` is the only eligible
    variant -- the one `lab promote` would pre-register -- and compounds at 0.001, below the
    benchmark's 0.004, so it loses every fold. Both curves are monotone, so every training slice
    ranks both at an infinite MAR and `pick` breaks the tie on the id: ``B`` is picked every time.
    Three dev trials, so ``n_trials_at_run=3`` (see the note under ``_trial``).
    """
    days = _month_ends(date(1993, 2, 1), date(2015, 9, 30))
    n = 3
    _method_at(c, "M0001", status="dev-eligible", family="fam", trials=[
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", mar=0.5,
               max_drawdown=0.35, eligible=False, failed="max DD <= 20%", sharpe=0.8,
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n,
               curve_json=_curve(days, 0.009)),
        _trial(method_id="M0001", candidate_id="M0001-Z", config_digest="z", mar=0.9,
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n,
               curve_json=_curve(days, 0.001)),
    ])
    _method_at(c, "M0009", status="rejected", family="bench", trials=[
        _trial(method_id="M0009", candidate_id="REF-SPY-HOLD", config_digest="spy",
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n, eligible=False,
               failed=OLD_LUCK_LABEL, dsr=0.10, sharpe=0.7, curve_json=_curve(days, 0.004)),
    ])


def test_a_method_whose_promoted_variant_lost_its_own_folds_is_refused(tmp_path, status):
    """(D11): the picks win 4 of 4, the variant that would be pre-registered wins 0 of 4.

    Before D11 this lab printed M0001 under "Promotable now" on "4 of 4 folds; kin clean" --
    verified while planning, and the exact shape of M0044 on the committed lab.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_where_the_pick_is_not_the_promoted_variant(c)
    assert store.best_dev_eligible(c, "M0001")["candidate_id"] == "M0001-Z"
    c.close()
    out = status(db)
    ready = out.split("Promotable now")[1].split("Refused by the hard gate")[0]
    assert "(none)" in ready and "M0001 " not in ready
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001-Z alone 0 of 4 folds" in blocked
    assert "D11" in blocked


def test_lab_promote_exits_2_and_writes_nothing_when_the_promoted_variant_lost(tmp_path):
    db, prereg_dir = tmp_path / "lab.sqlite", tmp_path / "prereg"
    c = store.connect(db)
    _lab_where_the_pick_is_not_the_promoted_variant(c)
    c.close()
    before = db.read_bytes()
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 2
    assert not prereg_dir.exists()
    assert db.read_bytes() == before
```

(`argparse`, `lab_cmd`, `store`, `date`, `_month_ends`, `_curve`, `_method_at`, `_trial`, `OLD_LUCK_LABEL` are already in scope in this module.)

If `lab_cmd.run(...)` for `promote` needs more namespace attributes than `db/lab_command/method/dir`, copy the exact `argparse.Namespace` shape from `tests/test_lab_hardgate.py::_cli` — that is the shape `_promote` already accepts.

---

## Step 6 — Verify (all must pass before committing)

```bash
WT=/home/miftah/.worktrees/seer/hardgate-variant-and-blend-kin
PY=/home/miftah/seer/engine/.venv/bin/python
cd $WT/engine

# 1. lint (the repo's CI selection)
/home/miftah/seer/engine/.venv/bin/ruff check src/seer_engine/lab/hardgate.py src/seer_engine/lab/prereg.py src/seer_engine/commands/lab.py tests/test_lab_hardgate.py tests/test_lab_status.py

# 2. the no-override grep (must print nothing)
grep -n -i "force\|environ\|getenv\|skip_gate" src/seer_engine/lab/hardgate.py

# 3. the touched suites, then the whole lab suite
PYTHONPATH=src $PY -m pytest -q tests/test_lab_hardgate.py tests/test_lab_status.py tests/test_lab_prereg.py tests/test_lab_walkforward.py
PYTHONPATH=src $PY -m pytest -q tests -k "lab" -x

# 4. the measurement, on a SCRATCH COPY of the live lab (never the live file)
SCR=$(mktemp -d) && cp /home/miftah/seer/lab/lab.sqlite $SCR/lab.sqlite
PYTHONPATH=src $PY -m seer_engine lab --db $SCR/lab.sqlite status | sed -n '/Promotable now/,/Refused by the hard gate/p'
#    must show "    (none)" under Promotable now; M0044's refusal must read "M0044-TV14-N21 alone 1 of 4 folds" and name D11
PYTHONPATH=src $PY -m seer_engine lab --db $SCR/lab.sqlite status | grep -E "M0024|M0028" -A1 | grep -o "kin [^;]*"
#    both must read "kin blocked: M0022 read test-failed"
PYTHONPATH=src $PY -m seer_engine lab --db $SCR/lab.sqlite walkforward | tail -6
#    must still read "No buy signal." (D13: output unchanged)
PYTHONPATH=src $PY - <<EOF
import sqlite3
from seer_engine.lab import hardgate
c = sqlite3.connect("$SCR/lab.sqlite"); c.row_factory = sqlite3.Row
ids = [r[0] for r in c.execute("select id from methods")]
dev = [r[0] for r in c.execute("select id from methods where status='dev-eligible' order by id")]
print("kin-blocked of all:", sum(1 for m in ids if hardgate.failed_kin(c, m)), "of", len(ids))
for m in dev:
    try:
        hardgate.check(c, m); print(m, "TAKEN")
    except Exception as e:
        print(m, "refused:", str(e)[:90])
EOF
#    expect every dev-eligible method refused; kin-blocked 31 of 70 on the 9560a6b-era lab
rm -rf $SCR
```

**If Sera has changed the lab since planning** (new methods, new test-failed), the counts in the D11/D12 tables can move. Re-run the measurement; if a number differs, update the docstring table to the measured value and say in the commit message which lab state (`git log -1 --format=%h -- lab/lab.sqlite` on main) it was measured on. Do **not** change the rule to fit the old number. **If `lab status` on the scratch copy lists anything under "Promotable now"**, do not commit: that is a measurement the owner must see — stop and report it.

## Step 7 — Commit by pathspec (two commits, one per requirement)

Sera commits `lab/lab.sqlite` to main concurrently. Stage **only** these paths:

```bash
cd $WT
git add -- engine/src/seer_engine/lab/hardgate.py engine/src/seer_engine/lab/prereg.py \
           engine/src/seer_engine/commands/lab.py engine/tests/test_lab_hardgate.py \
           engine/tests/test_lab_status.py
git status --short    # must show nothing staged outside those five files; lab/lab.sqlite untouched
```

A single commit is acceptable if splitting the hunks per requirement is impractical (both live in the same functions' docstrings); the message must then carry both decisions:

```
lab(hardgate): D11 the promoted variant must win its own folds; D12 blend ingredients are kin

Insight 82: (F) scored the training slices' picks, not the variant `lab promote`
pre-registers. M0044's picks won 3 of 4; M0044-TV14-N21 alone wins 1 of 4 and the
gate took it -- `lab status` listed it as promotable. The gate now also requires the
promoted variant's own de-funded curve to win a strict majority of the folds. Measured:
picks-only blocks 5 of 10 dev-eligible, own-only 6 (and lets M0053 through), both 7;
whole gate 9 of 10 -> 10 of 10. Promotable now: (none).

Insight 84: (K) followed family and parent_id only, so M0028-BLEND-RM, half
M0007's engine, read kin clean. Ingredients are read from the recorded config_text
(`<ID>` per allocator, nested included); an ingredient and its own family union
ancestors are kin, one hop. Measured: 29 -> 31 of 70 kin-blocked; adds M0024, M0028
(already refused on folds). No schema change.

D13: the buy signal follows through `lab walkforward`'s call to failed_kin (D9);
walkforward.py untouched; its label and fold condition are left to the owner.

No override. lab.sqlite not touched.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
```

Then hand the branch back per the plan index (merge to main by fast-forward/rebase onto the current `origin/main`, again never staging `lab/lab.sqlite`; push per the owner's standing "auto commit & push once verified" rule).

## Exit criteria

- All suites in Step 6.3 green; ruff clean; the no-override grep empty.
- On a scratch copy of the current lab: `Promotable now: (none)`; M0044 refused naming D11 and `M0044-TV14-N21 alone 1 of 4 folds`; M0024 and M0028 read `kin blocked: M0022`; `lab walkforward` still "No buy signal."
- `hardgate.py` docstring carries D11, D12, D13 with the measured tables; `walkforward.py` byte-identical to base; `lab/lab.sqlite` not in any commit on this branch.
