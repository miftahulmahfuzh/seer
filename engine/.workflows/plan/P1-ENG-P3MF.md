> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-hard-gate/PLAN.md` phase 2. Source: `.workflows/plan/lab-hard-gate/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: The pre-registration records what it cleared

**Plan set:** `LAB_HARD_GATE_PLAN.md`
**Analysis:** `docs/analyzer/20261009-161956-K3QD_code_analyzer.md`
**Satisfies:** R3 (the pre-registration states that the family state is *at promotion* and is not
re-checked at `lab test`, **and `lab test` prints the one note that follows from that choice** —
assigned here by reconciliation), R6 (the file records the folds won and scored, pick stability,
and the family's state at promotion)
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase, every pre-registration `lab promote` writes carries two more lines — `folds:` and
`family_state:` — so the committed record says what the walk-forward gate found the day the method
was promoted, not merely that it was promoted. The four pre-registrations already in git keep
parsing, unedited, and report both fields as not recorded. `parse(render(p, name)) == p` still holds
exactly, for a freshly rendered file and for a legacy file read back and re-rendered.

Reconciliation added two items to this phase, both of which follow from Decision D3 and from the
two new fields rather than sitting beside them: **`lab test` prints one line** (never a refusal)
when a promoted method's kin has failed since the promise was made, and
**`docs/lab/prereg/README.md`'s Format table gains the two rows** that keep it from going stale
the moment `render` writes them.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `prereg.LEGACY` (`lab/prereg.py`) — the stated legacy value both new fields take when absent
- `prereg.Prereg.folds: str` (`lab/prereg.py`) — dataclass field, **defaulted to `LEGACY`**
- `prereg.Prereg.family_state: str` (`lab/prereg.py`) — dataclass field, **defaulted to `LEGACY`**
- `prereg.REQUIRED: tuple[str, ...]` (`lab/prereg.py`) — the fields `parse` still demands (the
  original fifteen), derived from which dataclass fields carry a default
- `prereg.one_line(text) -> str` (`lab/prereg.py`) — collapse any whitespace run to one space
- `prereg.fold_text(conn, method_id) -> str` (`lab/prereg.py`)
- `prereg.family_text(conn, method_id, family) -> str` (`lab/prereg.py`)
- `runner.kin_note(conn, method_id) -> str | None` (`lab/runner.py`) — the D3 printed line, or
  `None` when the kin is clean. **Assigned to this phase by reconciliation** (the index's draft
  left it unowned; phase 1 forbids itself `runner.py`, phase 3 hands it back here)

**Signature changes:** none. `Prereg` gains two fields **with defaults**, appended after `date`, so
every existing keyword construction keeps working — specifically
`engine/tests/test_lab_test_window.py:59` builds a `Prereg` with exactly the fifteen current
keywords and must not be edited.

**Behaviour changes:**
- `prereg.FIELDS` grows from 15 to 17 entries; `render` writes all 17
- `prereg.parse` demands `REQUIRED` (15) rather than `FIELDS` (17); unknown and repeated keys are
  still errors, for all 17
- `prereg.render`'s prose gains one paragraph and two explanatory paragraphs
- `prereg.promote_method` populates the two new fields from `hardgate`
- `commands/lab.py:_promote` prints two more lines, appended to the block **phase 1 leaves behind**
- `runner.preflight_test` prints one line when the kin has failed since promotion (D3). **No exit
  code moves, no refusal is added, no transition changes** — it is a sentence, the same shape as
  `_ratchet_warning`. Its five existing refusals are untouched and still run first
- `docs/lab/prereg/README.md`'s Format table gains a `folds` row and a `family_state` row

**Deletes:** none.
**Renames:** none.

**Requires (from Phase 1) — the three names this phase imports from `seer_engine.lab.hardgate`:**

| Name | Signature | What this phase does with it |
|---|---|---|
| `hardgate.MIN_FOLDS` | `int` | printed in the `folds:` line as the bar this method cleared |
| `hardgate.fold_record(conn, method_id)` | `-> walkforward.Record` | `rec.won`, `len(rec.scored)`, `rec.stable` |
| `hardgate.failed_kin(conn, method_id)` | `-> tuple[str, ...]` of method ids reading `test-failed`, in id order, empty when clean | the `family_state:` line, and `runner.kin_note` |

**The `failed_kin` shape is confirmed, and the risk this section used to carry is closed.** Phase 1
ships exactly `failed_kin(conn, method_id) -> tuple[str, ...]`, raising `store.LabError` only for an
unknown method and returning `()` when clean — verified against phase 1's Interface Contract and its
module code. Every message in this plan set that names kin therefore names **all** of them:
`hardgate.family_state` and `hardgate.check` both `", ".join(bad)`, and so do `prereg.family_text`
and `runner.kin_note` below. That matters because D4's live case M0030 has two (M0021 **and**
M0029), and the shape `commands/lab.py:1863-1866` uses today — one row, `LIMIT 1`, `str | None` —
would lose one of them. That query is a *report* feeding `wf.buy_signal` and is deliberately left
alone (index Decision D9); nothing in this phase reads it.

**Also requires (from Phase 1):** this phase's new CLI test and the existing
`test_lab_promote_command_writes_the_file_and_names_the_next_step` (`tests/test_lab_prereg.py:490`)
both reach `_promote` through `lab_cmd.run`, and phase 1 puts `hardgate.check` in that path. The
existing one must pass with its **body unchanged** (plan invariant 2), and phase 1 owns that: it
edits three *fixture helpers* so the fixture lab becomes one that could actually promote
(`_real_method`, plus new `_months` / `_curve` / `_benchmark`), measured at 31 passed. This phase's
new CLI test monkeypatches `hardgate.check` to a no-op so it pins **its own two print lines** and
not phase 1's resolution of that problem.

**Leaves alone (owned by others):**
- `lab/hardgate.py` (Phase 1) — imported, never edited
- `lab/walkforward.py`, `backtest/walkforward.py` — not read, not edited by this phase
- `commands/lab.py:_promotable_now`, `_promotion_path`, `_regime`, `_walkforward`, the module help
  block (Phases 1 and 3)
- `engine/package_readme.md`, the two `.claude/skills/*/SKILL.md`,
  `docs/plans/WALK_FORWARD_EVALUATION_PLAN.md` (Phase 3)
- every pre-existing **test body** in `engine/tests/test_lab_prereg.py` and
  `engine/tests/test_lab_test_window.py` — additions only. The three fixture helpers phase 1 added
  to `test_lab_prereg.py` (`_months`, `_curve`, `_benchmark`) are **reused, never redefined**
- `docs/lab/prereg/{M0002,M0021,M0022,M0029}.md` — committed records, never edited or migrated
- `lab/hardgate.py`'s rule, and `runner.preflight_test`'s five existing refusals — this phase adds
  a printed line beside them and changes neither
- `lab/lab.sqlite`

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/prereg.py` | modify | two defaulted `Prereg` fields; `REQUIRED` derived from the defaults; `parse` relaxed for exactly those two; `render` writes them and explains them; two new text builders; `promote_method` fills them |
| `engine/src/seer_engine/commands/lab.py` | modify | two `print` lines appended to `_promote`'s labelled block, **as phase 1 left it** |
| `engine/src/seer_engine/lab/runner.py` | modify | `kin_note`, and one `print` in `preflight_test` before it returns (D3). No refusal, no exit code, no transition |
| `engine/tests/test_lab_prereg.py` | modify (append only) | one new section, eleven tests, appended at the end of the post-phase-1 file |
| `engine/tests/test_lab_test_window.py` | modify (append only) | two tests for the `lab test` note |
| `docs/lab/prereg/README.md` | modify | two rows in the Format table, for `folds` and `family_state` |

Six files. Nothing is created, nothing is deleted.

## Implementation Steps

### Step 1: Two defaulted fields, and the parse rule that follows from the default

**File:** `engine/src/seer_engine/lab/prereg.py:43` (the import), `:54-61` (constants), `:72-97`
(the dataclass and `FIELDS`)

**Change:** `MISSING` joins the `dataclasses` import. `LEGACY` is declared next to `FENCE` and
`MARKER`. `Prereg` gains `folds` and `family_state`, **appended after `date`** — appended because a
frozen dataclass may not put a defaulted field before an undefaulted one, and the two call sites
that build a `Prereg` positionally would break if they existed (they do not; both build by keyword).
`REQUIRED` is then derived from which fields carry a default, so the parse rule cannot drift from
the dataclass: *a field with a stated default is tolerated absent; every other field is demanded.*

**Code:** replace line 43

```python
from dataclasses import dataclass, fields
```

with

```python
from dataclasses import MISSING, dataclass, fields
```

Then replace lines 54-61

```python
PREREG_DIR = config.REPO_ROOT / "docs" / "lab" / "prereg"
FENCE = "---"
# The first words of the analysis section ``promote_method`` appends, and its idempotence key: a
# method whose analysis already names a pre-registered candidate is not pre-registered twice.
MARKER = "Pre-registered for the test window as "

_KEY = re.compile(r"[a-z_]+")
_RECORDED = re.compile(re.escape(MARKER) + r"`([^`]+)`")
```

with

```python
PREREG_DIR = config.REPO_ROOT / "docs" / "lab" / "prereg"
FENCE = "---"
# The first words of the analysis section ``promote_method`` appends, and its idempotence key: a
# method whose analysis already names a pre-registered candidate is not pre-registered twice.
MARKER = "Pre-registered for the test window as "

#: What ``folds`` and ``family_state`` read when a committed file predates the walk-forward hard
#: gate (``lab/hardgate.py``). Four such files are in git -- M0002, M0021, M0022, M0029 -- and
#: their whole value is that they were committed before a number existed, so they are never edited
#: and never migrated. ``parse`` fills this in rather than refusing them, and ``render`` writes it
#: back unchanged, which is why a legacy file still round-trips exactly.
LEGACY = "not recorded: this pre-registration predates the walk-forward hard gate"

_KEY = re.compile(r"[a-z_]+")
_RECORDED = re.compile(re.escape(MARKER) + r"`([^`]+)`")
_WS = re.compile(r"\s+")
```

Then replace lines 72-97 (the `Prereg` dataclass and `FIELDS`)

```python
@dataclass(frozen=True)
class Prereg:
    """One pre-registration file's front-matter block.

    Every field is the text that is in the file. The file is the record; this value is a reading
    of it, not a parallel source of truth, which is why nothing here is parsed into a number.
    """

    method: str
    candidate: str
    config_digest: str
    rules_id: str
    allocator_id: str
    dev_trial: str
    dev_window: str
    test_window: str
    gate: str
    mar: str
    dsr: str
    n_trials_at_run: str
    store_fingerprint: str
    git_sha: str
    date: str


FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Prereg))
```

with

```python
@dataclass(frozen=True)
class Prereg:
    """One pre-registration file's front-matter block.

    Every field is the text that is in the file. The file is the record; this value is a reading
    of it, not a parallel source of truth, which is why nothing here is parsed into a number.

    **A field with a default is a field written after some committed file already existed.** The
    two at the bottom -- ``folds`` and ``family_state`` -- record what the walk-forward hard gate
    (``lab/hardgate.py``) found at promotion, and the gate is younger than four committed records.
    Making them required would invalidate those four, and migrating them is forbidden by this
    module's own rule, so they default to ``LEGACY`` and ``parse`` demands only ``REQUIRED``.
    They are appended rather than slotted beside ``gate`` because a frozen dataclass cannot put a
    defaulted field before an undefaulted one.

    Both are **single-line** values. ``parse`` splits the block on newlines and refuses a line that
    is not ``key: value``, so a wrapped value would make the file unreadable; ``one_line`` is what
    guarantees it, and ``gate`` has the same constraint for the same reason.
    """

    method: str
    candidate: str
    config_digest: str
    rules_id: str
    allocator_id: str
    dev_trial: str
    dev_window: str
    test_window: str
    gate: str
    mar: str
    dsr: str
    n_trials_at_run: str
    store_fingerprint: str
    git_sha: str
    date: str
    folds: str = LEGACY
    family_state: str = LEGACY


#: Every key ``render`` writes, in file order.
FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Prereg))

#: Every key ``parse`` refuses a file for missing -- the fields with no default, which is the
#: original fifteen. Derived rather than retyped, so adding a defaulted field to ``Prereg`` can
#: never accidentally tighten the parser, and removing a default can never silently loosen it.
REQUIRED: tuple[str, ...] = tuple(
    f.name for f in fields(Prereg) if f.default is MISSING and f.default_factory is MISSING
)
```

**Impact:** `FIELDS` becomes 17 entries, so `render` writes two more lines and
`test_parse_refuses_an_unknown_or_repeated_field` (`:450`) still builds a complete block from
`FIELDS` and still gets its two refusals. `test_lab_test_window.py:59`'s fifteen-keyword `Prereg`
keeps working, with both new fields reading `LEGACY`.

### Step 2: `parse` demands `REQUIRED`; `render` writes and explains the two new lines

**File:** `engine/src/seer_engine/lab/prereg.py:214-290` (`render` and `parse`), plus one helper

**Change:** one word in `parse` (`FIELDS` -> `REQUIRED` in the missing check, and only there — the
unknown-key check still spans all 17). `render` gains one recorded paragraph and two paragraphs of
reasoning: that the fold record is the bar *this* method cleared and never a significance test, and
— plan Decision D3 — that the family state is the state **at promotion** and is not re-opened by
`lab test`. `one_line` is added above `gate_text`, beside the other single-line-field machinery.

**Code:** insert `one_line` immediately before `def gate_text(` (currently line 149), after
`method_of`:

```python
def one_line(text: str) -> str:
    """``text`` with every whitespace run collapsed to one space, and the ends trimmed.

    A ``key: value`` field in a committed file lives on one line: ``parse`` splits the block on
    newlines and refuses anything that is not ``key: value``, so a value that wraps makes the file
    unparseable -- and a pre-registration that cannot be read is a record the lab has lost.
    ``gate_text`` states the same constraint in prose and relies on ``npolicy`` to honour it;
    ``fold_text`` and ``family_text`` compose a message out of a database error's words, which are
    not theirs to trust, so they enforce it instead of asking.
    """
    return _WS.sub(" ", str(text)).strip()
```

Then replace the `render` body's prose, lines 229-234 — the paragraph that currently reads

```python
**Gate passed, on the dev window {p.dev_window}:** {p.gate}.
MAR {p.mar}, DSR {p.dsr}, recorded at `n_trials_at_run` = {p.n_trials_at_run} on dev trial
#{p.dev_trial}. The bar that DSR cleared and the N it was deflated by are both stated in the gate
line above, because both are settings the owner can move (design §7) and a number without them is
not a record of a pass.
Research store `{p.store_fingerprint}`, engine `{p.git_sha}`.
```

with

```python
**Gate passed, on the dev window {p.dev_window}:** {p.gate}.
MAR {p.mar}, DSR {p.dsr}, recorded at `n_trials_at_run` = {p.n_trials_at_run} on dev trial
#{p.dev_trial}. The bar that DSR cleared and the N it was deflated by are both stated in the gate
line above, because both are settings the owner can move (design §7) and a number without them is
not a record of a pass.
Research store `{p.store_fingerprint}`, engine `{p.git_sha}`.

**The hard gate, as it stood the day this was written.** Folds: {p.folds}. Family:
{p.family_state}.

The fold record is the lab's own selection rule scored out of sample several times over, on curves
it already had (`lab/walkforward.py`). It costs no counted look, and it is a sanity check and never
a significance test: the folds share training data, so they are not independent observations and
nothing in them may be fed into a DSR. It is also **the bar this method cleared**, not today's
bar. `lab/hardgate.py` holds the rule in force now; if the owner later argues the rule down or up,
that is a commit in git and it does not reach back into this file.

The family state is the state **at promotion**, and `lab test` does not re-check it. A
pre-registration is a promise: re-opening it after the fact would strand a promoted method in a
state it can never leave, which is the exact failure the gate was put at `promote` to avoid. If a
relative of this method fails the test window after this file is written, `lab test` says so above
the look and refuses nothing — the line above is still the true record of what was known here.
```

Then replace line 287 inside `parse`

```python
    missing = [k for k in FIELDS if k not in values]
```

with

```python
    missing = [k for k in REQUIRED if k not in values]
```

and replace `parse`'s docstring (lines 257-262) with one that says why the two differ:

```python
    """Read a pre-registration file's front-matter block.

    Strict on purpose. The block must be the first thing in the file, must be closed, must carry
    every key in ``REQUIRED`` exactly once, and must carry nothing outside ``FIELDS``. An unknown
    key is an error rather than a shrug: a misspelled ``config_digest`` must never be read as "no
    digest given".

    The two lists differ by exactly the two fields that carry a default (``folds``,
    ``family_state``). They are younger than four committed records, and a file written before the
    walk-forward hard gate existed is a correct record of what was claimed before a look -- not a
    file to migrate, which this module's central rule forbids. Such a file parses, and both fields
    read ``LEGACY``. Everything else is unchanged: the original fifteen are still demanded, an
    unknown key is still refused, a repeat is still refused.
    """
```

**Impact:** `render(p, name)` now emits 17 block lines, and `parse` round-trips all 17 — a legacy
file too, because the value `render` writes for an absent field is the same `LEGACY` the default
supplied. `test_parse_round_trips_render` (`:431`) and
`test_parse_refuses_a_malformed_pre_registration`'s `"missing candidate"` case (`:442`) both keep
passing: `REQUIRED` preserves declaration order, so `candidate` is still the first name in the
missing list.

### Step 3: `promote_method` fills both from `hardgate`

**File:** `engine/src/seer_engine/lab/prereg.py` — two new builders after `_fmt` (currently
`:417-419`), and two lines inside the `Prereg(...)` construction at `:511-527`

**Change:** `fold_text` and `family_text` ask `hardgate` and turn the answer into one line.
**Neither raises.** By the time `promote_method` runs, `commands/lab.py:_promote` has already called
`hardgate.check` on the same connection and it passed, so in production these cannot fail; the
`except` is there for the test path (fixture labs record `curve_json="[]"` and no `REF-SPY-HOLD`
row) and for a hypothetical second caller, and it writes down *what went wrong* rather than
inventing a pass. Recording "not recorded, because X" is honest; raising here would move the
refusal out of phase 1's gate and into the file-writing step, where a half-written promotion is the
one state design §3 forbids.

**Code:** insert after `_fmt` (after line 419, before `_recorded_candidate`):

```python
def fold_text(conn: sqlite3.Connection, method_id: str) -> str:
    """The walk-forward record this method was promoted on, as the file states it.

    Built from ``lab/hardgate.py`` rather than retyped -- the same reasoning as ``gate_text``: a
    file written next year must not be able to claim a fold record the code never computed, or a
    minimum the owner has since moved. Three facts, which is exactly what the brief asks the
    pre-registration to add: how many folds the pick won, how many could be scored at all, and
    whether the training slice kept choosing the same variant.

    ``Record.summary()`` is deliberately not used. It appends ", pick changed" only when the pick
    moved, so a stable record says nothing about stability, and a record is not a record when one
    of its three facts is conveyed by absence.

    The minimum is named because it is the bar **this** method cleared. ``hardgate.MIN_FOLDS`` is
    the bar in force the day this runs; a later commit may argue it elsewhere, and this line is
    what lets a reader of the committed file tell the two apart.

    Never raises, and always one line. See ``promote_method`` for why a refusal here would be in
    the wrong place.
    """
    from seer_engine.lab import hardgate

    try:
        rec = hardgate.fold_record(conn, method_id)
    except store.LabError as e:
        return one_line(f"not recorded: the fold record could not be built ({e})")
    scored = len(rec.scored)
    return one_line(
        f"{rec.won} of {scored} scoreable walk-forward fold(s) won, "
        f"pick {'stable' if rec.stable else 'changed'} across folds; the bar this method cleared "
        f"was a strict majority of at least {hardgate.MIN_FOLDS} scoreable folds"
    )


def family_text(conn: sqlite3.Connection, method_id: str, family: str) -> str:
    """The state of ``method_id``'s kin at promotion, as the file states it.

    ``hardgate.failed_kin`` is the one definition of kin -- the method's ``family`` string together
    with its transitive ancestors through ``parent_id`` (plan Decision D4) -- and this line quotes
    its answer rather than re-deriving it, so the file and the rule cannot disagree.

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
            f"clean at promotion: no method in {method_id}'s family '{family}' or ancestry read "
            f"test-failed"
        )
    return one_line(
        f"blocked at promotion: {', '.join(failed)} in {method_id}'s family '{family}' or "
        f"ancestry read test-failed"
    )
```

Then, inside `promote_method`, replace the `Prereg(...)` construction at lines 511-527

```python
        p = Prereg(
            method=method_id,
            candidate=str(trial["candidate_id"]),
            config_digest=str(trial["config_digest"]),
            rules_id=str(trial["rules_id"]),
            allocator_id=str(trial["allocator_id"]),
            dev_trial=str(trial["n"]),
            dev_window=f"{trial['start']}..{trial['end']}",
            test_window=test_window_label(),
            gate=gate_text(conn),
            mar=_fmt(trial["mar"]),
            dsr=_fmt(trial["dsr"]),
            n_trials_at_run=str(trial["n_trials_at_run"]),
            store_fingerprint=str(trial["store_fingerprint"]),
            git_sha=git_sha,
            date=today.isoformat(),
        )
```

with

```python
        p = Prereg(
            method=method_id,
            candidate=str(trial["candidate_id"]),
            config_digest=str(trial["config_digest"]),
            rules_id=str(trial["rules_id"]),
            allocator_id=str(trial["allocator_id"]),
            dev_trial=str(trial["n"]),
            dev_window=f"{trial['start']}..{trial['end']}",
            test_window=test_window_label(),
            gate=gate_text(conn),
            mar=_fmt(trial["mar"]),
            dsr=_fmt(trial["dsr"]),
            n_trials_at_run=str(trial["n_trials_at_run"]),
            store_fingerprint=str(trial["store_fingerprint"]),
            git_sha=git_sha,
            date=today.isoformat(),
            folds=fold_text(conn, method_id),
            family_state=family_text(conn, method_id, str(row["family"])),
        )
```

Finally, add one paragraph to `promote_method`'s docstring, immediately after the
**"And it refuses to change its mind."** paragraph (currently ending at line 487):

```python
    **It records the hard gate; it does not apply it.** ``folds`` and ``family_state`` are read
    from ``lab/hardgate.py`` here, but the refusal lives in ``commands/lab.py:_promote``, which
    calls ``hardgate.check`` on this same connection *before* this function (plan Decision D1). So
    by the time these two lines are built the gate has already passed, and ``fold_text`` and
    ``family_text`` never raise: a refusal at this point would be after the decision, not before
    it, and would leave the half-written state design §3 exists to forbid. A caller that reaches
    ``promote_method`` without calling the gate gets a file that says what it could and could not
    establish, which is the honest record of that caller's mistake.
```

**Impact:** every pre-registration written from here on carries both lines. Of the **31** existing
tests in `test_lab_prereg.py`, the ones that call `promote_method` directly do so on fixture labs
built by `_real_method` — which after phase 1 *does* carry a `REF-SPY-HOLD` benchmark and a real
curve, so both lines will read a real record there rather than `not recorded`. Either way, none of
those tests asserts on the file's field set or its byte length, so all 31 keep passing with their
bodies untouched.

### Step 4: `_promote` prints the two lines

**File:** `engine/src/seer_engine/commands/lab.py`, inside `_promote`

**Anchor on the post-phase-1 file, not on `origin/main`.** Phase 1 replaces the whole `_promote`
handler (its Step 2): the docstring gains the hard-gate paragraphs and the body gains
`from seer_engine.lab import hardgate, prereg` and `hardgate.check(conn, args.method)` before
`prereg.promote_method`. Line numbers have moved; the anchor is the `gate` line inside the labelled
print block, which phase 1 leaves byte-identical.

**Change:** two `print` calls appended to that block, directly after the `gate` line. The label
column is 15 characters wide throughout the block; `folds` and `family` are padded to match.
Nothing else in this file changes in this phase — `hardgate.check`, the import line and the
docstring are phase 1's and are left exactly as phase 1 wrote them.

**Code:** the block as phase 1 leaves it, with the two lines added (the `gate` line is the one to
search for):

```python
    print(f"  test window    {p.test_window}")
    print(f"  gate           {p.gate}")
    print(f"  folds          {p.folds}")
    print(f"  family         {p.family_state}")
    print()
```

**Impact:** `lab promote` prints seven labelled lines instead of five. No exit code moves, nothing
new is written. `test_lab_promote_command_writes_the_file_and_names_the_next_step` (`:490`, body
unedited by both phases) asserts only on substrings that are still present.

### Step 5: Tests — additions only, appended to `test_lab_prereg.py`

**File:** `engine/tests/test_lab_prereg.py` — append at the end of the file, **as phase 1 leaves
it**. No existing test body is touched, by either phase.

**Anchor on the post-phase-1 file.** Phase 1 edits three *fixture helpers* near `:135` —
`_real_method`, plus new module-level `_months`, `_curve` and `_benchmark` — and adds
`timedelta` to the `datetime` import at `:12`. Those three helpers are **reused here, never
redefined**: a second `_curve` in the same module would shadow phase 1's and silently change what
the file's other tests build. Phase 1's append point moves by the size of its helper block; the
anchor is "after the last test in the file", not a line number.

**Change:** one new section with eleven tests. The module's existing imports cover everything
except `store` (already imported at `:19`) — no import line is edited by this phase; the tests that
need `hardgate` import it inside the test body, matching the file's existing style of importing
`lab_cmd` and `runner` inside the CLI tests.

**Code:** append

```python
# ------------------------------------------------------------------ the hard gate's two fields


def _block(**over) -> str:
    """A front-matter block carrying only the fifteen fields that predate the hard gate.

    This is the shape of the four files committed under docs/lab/prereg/ before the gate existed,
    rebuilt from `prereg.REQUIRED` rather than retyped so it cannot drift from the parser.
    """
    values = {k: f"<{k}>" for k in prereg.REQUIRED}
    values.update(over)
    body = "\n".join(f"{k}: {v}" for k, v in values.items())
    return f"{prereg.FENCE}\n{body}\n{prereg.FENCE}\n\n# prose\n"


def test_the_two_new_fields_are_written_and_round_trip(conn, prereg_dir):
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    p = done.prereg
    assert p.folds and p.family_state
    assert "\n" not in p.folds and "\n" not in p.family_state  # one `key: value` line each
    text = (prereg_dir / "M0001.md").read_text(encoding="utf-8")
    assert f"folds: {p.folds}" in text
    assert f"family_state: {p.family_state}" in text
    assert prereg.parse(text) == p
    assert prereg.parse(prereg.render(p, "SMA test")) == p


def test_a_file_written_before_the_gate_still_parses_and_says_so(conn):
    """Decision D5: the four committed records are never migrated, so `parse` tolerates absence."""
    p = prereg.parse(_block(method="M0001", candidate="M0001-A"))
    assert p.method == "M0001"
    assert p.folds == prereg.LEGACY
    assert p.family_state == prereg.LEGACY


def test_a_legacy_file_read_back_and_re_rendered_round_trips_exactly(conn):
    p = prereg.parse(_block(method="M0001", candidate="M0001-A"))
    assert prereg.parse(prereg.render(p, "SMA test")) == p


def test_parse_still_refuses_a_file_missing_any_of_the_original_fifteen():
    for key in prereg.REQUIRED:
        if key == "method":
            continue  # the first line is what `_block` keys off; its absence is covered at :442
        text = "\n".join(
            line for line in _block().split("\n") if not line.startswith(f"{key}:")
        )
        with pytest.raises(prereg.PreregError, match=f"missing .*{key}"):
            prereg.parse(text)


def test_the_four_committed_pre_registrations_still_parse(conn):
    """The reason this module exists: a committed record stays readable forever.

    Not a fixture -- the real files in docs/lab/prereg/, which this phase must not edit. All four
    predate the hard gate, so all four report both new fields as not recorded.
    """
    files = sorted(prereg.PREREG_DIR.glob("M[0-9][0-9][0-9][0-9].md"))
    assert [f.stem for f in files] == ["M0002", "M0021", "M0022", "M0029"]
    for path in files:
        p = prereg.parse(path.read_text(encoding="utf-8"))
        assert p.method == path.stem
        assert p.folds == prereg.LEGACY
        assert p.family_state == prereg.LEGACY
        assert prereg.parse(prereg.render(p, "n")) == p


def test_the_fold_line_names_the_folds_won_the_folds_scored_and_the_stability(conn, monkeypatch):
    """R6's three facts, each present as a word rather than by absence."""
    from seer_engine.lab import hardgate, walkforward as wf

    def record(_conn, mid):
        fold = wf.Fold(1, date(2006, 1, 1), date(2006, 1, 31), date(2008, 12, 31))
        won = wf.Slice(36, 1.0, 0.2, 0.1, 2.0)
        lost = wf.Slice(36, 0.1, 0.03, 0.1, 0.3)
        return wf.Record(mid, (
            wf.FoldPick(fold, "M0001-A", 1.0, won, lost),
            wf.FoldPick(fold, "M0001-A", 1.0, won, lost),
            wf.FoldPick(fold, "M0001-A", 1.0, lost, won),
            wf.FoldPick(fold, "M0001-B", 1.0, won, lost),
        ))

    monkeypatch.setattr(hardgate, "fold_record", record)
    line = prereg.fold_text(conn, "M0001")
    assert line.startswith("3 of 4 ")
    assert "pick changed across folds" in line
    assert str(hardgate.MIN_FOLDS) in line
    assert "\n" not in line


def test_the_family_line_names_every_failed_relative(conn, monkeypatch):
    from seer_engine.lab import hardgate

    monkeypatch.setattr(hardgate, "failed_kin", lambda _c, _m: ("M0021", "M0029"))
    blocked = prereg.family_text(conn, "M0030", "stock-core-satellite")
    assert "blocked at promotion" in blocked
    assert "M0021" in blocked and "M0029" in blocked  # D4's live case has two, not one
    assert "stock-core-satellite" in blocked

    monkeypatch.setattr(hardgate, "failed_kin", lambda _c, _m: ())
    clean = prereg.family_text(conn, "M0030", "stock-core-satellite")
    assert "clean at promotion" in clean
    assert "test-failed" in clean


def test_a_gate_that_cannot_answer_is_recorded_rather_than_invented(conn, prereg_dir, monkeypatch):
    """The refusal belongs to `_promote` (Decision D1); this step records, and never raises.

    A fixture lab has no REF-SPY-HOLD curve, which is exactly the shape of the real refusal, so
    this also pins that a caller which reaches `promote_method` past the gate still writes a
    readable file -- and that the 31 pre-existing tests in this file keep passing either way.
    """
    from seer_engine.lab import hardgate

    def boom(_conn, _mid):
        raise store.LabError("no REF-SPY-HOLD dev trial")

    monkeypatch.setattr(hardgate, "fold_record", boom)
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    assert done.prereg.folds.startswith("not recorded")
    assert "REF-SPY-HOLD" in done.prereg.folds
    assert "\n" not in done.prereg.folds
    assert prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8")) == done.prereg


def test_one_line_collapses_anything_a_refusal_message_can_carry():
    assert prereg.one_line("a\nb") == "a b"
    assert prereg.one_line("  a \n\n  b  ") == "a b"
    assert prereg.one_line("a") == "a"


def test_the_prose_says_the_family_state_is_not_rechecked_at_lab_test(conn, prereg_dir):
    """Decision D3, stated to the file's reader and not only in a plan."""
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    text = (prereg_dir / "M0001.md").read_text(encoding="utf-8")
    assert "state **at promotion**" in text
    assert "`lab test` does not re-check it" in text
    assert "never a significance test" in text


def test_the_promote_command_prints_the_fold_record_and_the_family_state(
    tmp_path, prereg_dir, capsys, monkeypatch
):
    """The two lines phase 2 adds to `_promote`'s block, and nothing else in that file.

    `hardgate.check` is stubbed out so this test pins *these two printed lines* rather than phase
    1's refusal, which has its own tests in test_lab_hardgate.py.
    """
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import hardgate, runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _real_method(c)
    c.close()
    monkeypatch.setattr(runner, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(hardgate, "check", lambda _conn, _mid: None)
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    p = prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8"))
    assert f"  folds          {p.folds}" in out
    assert f"  family         {p.family_state}" in out
```

**Impact:** `test_lab_prereg.py` goes from **31** tests to **42** — eleven appended, and the loop
in `test_parse_still_refuses_a_file_missing_any_of_the_original_fifteen` is one test, not fourteen.
No pre-existing test body is edited, and the three fixture helpers phase 1 added are reused rather
than redefined.


### Step 6: `lab test` says it, and refuses nothing — Decision D3's one printed line

**File:** `engine/src/seer_engine/lab/runner.py` — a new module-level `kin_note` above
`preflight_test` (`:494`), and one `print` inside `preflight_test` immediately before its
`return pre`.

**Assigned to this phase by reconciliation.** The index's draft promised this line under D3 and
gave it to no phase: phase 1's scope forbids itself `runner.py`, and phase 3 handed it back to
phase 1. It belongs here, with the `family_state` field whose meaning it completes — the file says
"this was the state **at promotion**", and this line is what a reader sees when the world has moved
since. **It is a sentence, not a gate.** No exit code moves, no transition changes, and
`preflight_test`'s five existing refusals run first and are untouched.

**Why a print and not a return value.** `preflight_test` returns the pre-registration so the caller
can print what it is about to honour; a second return value would change a signature three test
modules build against. `_ratchet_warning` in `commands/lab.py` is the same shape — information
above the action, in the command's own output. `kin_note` is split out so the sentence is testable
without a promoted method and a committed pre-registration.

**Why it cannot raise.** `hardgate.failed_kin` raises `store.LabError` only for an unknown method,
and `preflight_test` has already refused an unknown method three refusals earlier. It opens no
research store and cuts no folds — it is one `methods` read plus the ancestor walk — so the
benchmark-missing path that `fold_record` has does not exist here.

**Code:** insert immediately above `def preflight_test(`:

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
    ancestors through ``parent_id`` -- read from the one place that defines it, so the note and the
    gate can never disagree about who counts as kin. It names **every** failed relative, not the
    first: M0030's two are M0021 and M0029.
    """
    from seer_engine.lab import hardgate

    failed = hardgate.failed_kin(conn, method_id)
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

and inside `preflight_test`, replace its final

```python
    return pre
```

with

```python
    note = kin_note(conn, method.id)
    if note is not None:
        print(note)
    return pre
```

**Impact:** R3's second half. `lab test` on a promoted method whose kin has since failed prints one
line and then behaves exactly as before. `sqlite3` is already imported at the top of `runner.py`.
The five refusals above are unreached by this change, and the seventeen tests in
`test_lab_test_window.py` keep passing: none of them asserts on the absence of output, and none of
their fixture labs carries a `test-failed` relative.

### Step 7: two tests for the note, appended to `test_lab_test_window.py`

**File:** `engine/tests/test_lab_test_window.py` — append at the end. **No existing test is
touched**, and no fixture is edited: both tests use the module's own `conn` and `promoted`
fixtures as they are.

**Code:** append

```python
# ---- the kin note: a sentence, never a refusal (plan Decision D3) -------------------------------


def test_lab_test_prints_a_note_when_the_kin_failed_after_the_promise(
    conn, prereg_ok, promoted, tmp_path, capsys
):
    """D3: the promise is not re-opened, so this is a line above the look and nothing else.

    M0001 is promoted (the module's `promoted` fixture, family `trend`). A sibling in that same
    family then reads `test-failed` -- after the promise was made, which is the whole point.

    **One failed relative, deliberately.** `kin_note` says "has" for one and "have" for several,
    and the assertion below reads the singular; adding a second kin to this fixture changes the
    verb and breaks it. That the note names *every* failed relative is `kin_note`'s `", ".join`
    and is covered where the join is -- `test_lab_hardgate.py`'s M0030 case (M0021 **and**
    M0029) and `prereg.family_text`'s own test above.
    """
    with conn:
        store.add_method(conn, id="M0090", name="n", family="trend", source_kind="knowledge",
                         hypothesis="h", status="registered")
        for s in ("dev-eligible", "promoted", "test-failed"):
            store.update_method(conn, "M0090", status=s)

    c = promoted.candidates[0]
    pre = runner.preflight_test(conn, promoted, tmp_path / "x.py", c, require_commit=False)

    out = capsys.readouterr().out
    assert "M0090" in out
    assert "has read test-failed since" in out
    assert "not a refusal" in out
    assert pre.candidate == c.id          # it returned, and refused nothing


def test_a_clean_kin_prints_nothing_at_all(conn, prereg_ok, promoted, tmp_path, capsys):
    """The normal case. A note that fires when there is nothing to say is noise, not information."""
    assert runner.kin_note(conn, "M0001") is None
    runner.preflight_test(conn, promoted, tmp_path / "x.py", promoted.candidates[0],
                          require_commit=False)
    assert capsys.readouterr().out == ""
```

**Impact:** `test_lab_test_window.py` goes from 17 tests to 19, with nothing above the appended
section changed.

### Step 8: `docs/lab/prereg/README.md` — the Format table stops being stale

**File:** `docs/lab/prereg/README.md`, the Format table (`:28-41`)

**Assigned to this phase by reconciliation.** The table documents every key in the block, and this
phase adds two to it; a table that lists fifteen of seventeen keys is worse than no table, because
a reader uses it to decide whether a key is legitimate. It is **not** one of the four committed
records — it is the directory's documentation, and editing it is exactly as safe as editing
`prereg.py`'s own prose.

**Change:** two rows appended after the `date` row, in `FIELDS` order (both new fields are appended
after `date` in the dataclass, so the table's order still matches the file's).

**Code:**

```markdown
| `folds` | the walk-forward record at promotion: folds won, folds scoreable, whether the pick was stable, and the minimum in force that day (`seer_engine.lab.hardgate`). `not recorded: …` on a file written before the gate existed |
| `family_state` | whether any method in this one's `family` or ancestry read `test-failed` when it was promoted. The state **at promotion**; `lab test` does not re-check it, it prints a note |
```

**Do not type a DSR threshold or a percentage as a literal into this file.**
`engine/tests/test_lab_gate_wording.py:141` scans it, and a hard-coded bar is what that test
exists to catch. Neither row above carries a number, deliberately.

**Impact:** the directory's documentation and the parser agree again. No code changes; no committed
pre-registration is touched.

## Verification

**Build:**
```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c \
  "from seer_engine.lab import prereg; print(len(prereg.FIELDS), len(prereg.REQUIRED))"
```
expects `17 15`.

**Tests:**
```
cd /home/miftah/.worktrees/seer/lab-hard-gate/engine && \
  PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_lab_*.py
```
`PYTHONPATH` is not optional: without it pytest silently tests `/home/miftah/seer`, not this
worktree. The baseline at `origin/main` 7708350 for `test_lab_prereg.py` +
`test_lab_walkforward.py` + `test_lab_status.py` is **68 passed** — quote the count, not the
seconds (8.99s for the analyst, 11.35s for phase 1, same 68 tests). After phase 1,
`test_lab_prereg.py` reads **31**; this phase takes it to **42**, and
`test_lab_test_window.py` from **17** to **19**. The glob also picks up
`test_lab_gate_wording.py` (it scans `lab/prereg.py` *and* `docs/lab/prereg/README.md` for a stated
luck bar — neither this phase's new prose nor its two README rows states a DSR threshold or a
percentage, so it stays green).

**Manual check:** `git diff --stat` must list exactly the six files in the Files table, and
`git status --porcelain docs/lab/prereg/` must show **only** `README.md` — the four committed
records `M0002`, `M0021`, `M0022`, `M0029` are untouched.

**Exit criteria:**
- a promotion writes a pre-registration carrying `folds:` and `family_state:`, each on one line
- `parse(render(p, name)) == p` holds for a freshly rendered file **and** for a legacy file read
  back and re-rendered
- `prereg.parse` reads all four committed files and both new fields read `prereg.LEGACY`
- `promote_method` still refuses to rewrite an existing file and a re-run still does not move the
  `date` line (`test_promote_is_idempotent_and_does_not_move_the_date`, unedited, passes)
- every pre-existing **test body** in `test_lab_prereg.py` (31) and `test_lab_test_window.py` (17)
  is byte-identical and passes; the counts read 42 and 19
- `lab promote` prints `folds` and `family` in its labelled block
- `lab test` on a promoted method whose kin has since failed prints one line naming **every** failed
  relative, and **still runs**: same exit code, same transition, no new refusal
- `lab test` on a method with clean kin prints nothing extra
- `docs/lab/prereg/README.md`'s Format table lists all seventeen keys, with no DSR threshold and no
  percentage typed as a literal

## Handoffs

- **`docs/lab/prereg/README.md` is now this phase's** (reconciliation; Step 8). It was flagged here
  as unowned and recommended to phase 3; the reconciler put it where the fields are written
  instead, so the table and `FIELDS` move in one commit.
- **The `lab test` printed note is now this phase's** (reconciliation; Steps 6 and 7). It was
  unowned in the index's draft — phase 1 forbids itself `runner.py`, phase 3 handed it back to
  phase 1. It completes R3, which this phase already carried.
- **`engine/package_readme.md`'s `prereg` API block** (`:2543-2560`) names the fifteen fields —
  Phase 3 owns it and the plan index already assigns it. The two names to document are exactly
  `folds` and `family_state`; this phase will not rename them.
- **`_promotable_now` printing the fold record** (R7) is Phase 3's and is not touched here, even
  though `prereg.fold_text` would serve it. Phase 3 should prefer `hardgate`'s own summary for a
  live status read: `fold_text`'s line names the bar *as recorded*, which is the wrong tense for
  `lab status`.
- **The `_analysis_body` paragraph** (`prereg.py:442`) still summarises only the dev gate. Adding
  the fold record to the method's analysis text would be a second, drifting copy of the file's own
  line; deliberately not done.

## Rollback

`git revert` this phase's single commit on `feature/lab-hard-gate`. It restores the fifteen-field
`Prereg`, the `FIELDS`-based missing check, `render`'s original prose and `_promote`'s five-line
block; removes `runner.kin_note` and its `print`, leaving `preflight_test`'s five refusals exactly
as phase 1 left them; restores `docs/lab/prereg/README.md`'s fifteen-row table; and drops the
thirteen appended tests.

**One ordering constraint, from the plan's Rollback section.** After the revert, `parse` refuses a
file carrying `folds:` or `family_state:` as an *unknown key* — and a pre-registration written
while this phase was live is a committed record that must not be deleted or edited. So revert this
phase only **before any method is promoted under it**. Nothing in the lab is promotable today (plan
Decision D8: all seven dev-eligible methods fail the conjunction), so that window is currently
unbounded. If a promotion has happened, revert phase 1 instead and leave this phase in place — the
two extra lines are inert without the gate.

Nothing outside git is touched: no `lab.sqlite` write, no `web/data/lab.json`, no Neon, no research
store.
