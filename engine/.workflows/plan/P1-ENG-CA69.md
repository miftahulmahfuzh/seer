> Adopted from `LAB_LUCK_GATE_PLAN.md` phase 6. Source: `.workflows/plan/lab-luck-gate/phase-6.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 6: Every roster entry carries its lab provenance

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R4 — the lab verdict and the paper roster have diverged silently; RM-FR and RMW-FR
trade while both lab methods read `rejected`, and the only record of why is a commit message.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/paper` (with one function in `engine/src/seer_engine/lab`)

---

## Goal

After this phase every paper roster entry that came from a recorded lab candidate states, in
code, which lab method and variant it is, what the lab's status was at the moment it was
admitted, on what basis (`test-passed` or `owner-override`) and why — and a test checks every
line of that against the committed `lab/lab.sqlite`. The admission *policy* does not change
(Decisions D3: paper membership never required a gate pass), and no `spec_digest` moves: the new
field sits outside the spec exactly where `status`, `paper_end`, `gate_note` and
`gate_applicable` already sit. `lab.store.record_promotion` writes the same fact onto the lab
method, so the two databases state one story instead of two.

## Interface Contract

**Creates:**
- `paper.roster.Basis` — `Literal["test-passed", "owner-override"]` (`paper/roster.py`, next to
  `Engine`/`Status`)
- `paper.roster.BASES` — `tuple[Basis, ...]` (`paper/roster.py`, next to `ENGINES`/`STATUSES`)
- `paper.roster.LabProvenance` — frozen slots dataclass with a validating `__post_init__`
  (`paper/roster.py`, immediately above `RosterEntry`)
- `paper.roster.LAB_PROVENANCE` — `dict[str, LabProvenance]` keyed by roster id
  (`paper/roster.py`, immediately after `RESOLVER`)
- `paper.roster.RosterEntry.lab_provenance: LabProvenance | None = None` — a new trailing field
- `lab.store.PROMOTION_BASES` — `tuple[str, ...]` (`lab/store.py`, after `PROMOTION_MARKER`)
- `lab.store.promotion_basis(status) -> str` (`lab/store.py`, after `PROMOTION_BASES`)
- `promote` CLI flag `--lab-override-reason REASON` (`commands/promote.py`)

**Signature changes:**
- `lab.store.record_promotion(...)` gains two keyword-only params: `basis: str | None = None`,
  `reason: str = ""`. Both have defaults, so no existing call site breaks on arity — but the
  function now **raises `LabError`** when the derived or given basis is `owner-override` and
  `reason` is blank. Call sites that promote a non-`test-passed` method must pass a reason.
- `commands.promote.build_promotion(args, data_date, sort)` ->
  `build_promotion(args, data_date, sort, lab_status)`. Only `commands/promote.py:495` calls it;
  no test calls it directly (verified by grep).

**Deletes:** nothing.
**Renames:** nothing.

**Explicitly NOT changed (this is the proof the phase stayed out of the spec):**
- `roster.spec`, `roster.spec_text`, `roster.spec_digest`, `roster.rules_dict`,
  `roster.backtest_gate`, `roster.strategy_params` — not one line. `strategy_params` keeps
  exactly the three keys `{"spec", "digest", "backtest_gate"}` (contract C2).
- `tests/test_paper_roster.py`'s `PINS` dict — every pinned digest stays byte-identical, and
  `test_digests_are_pinned` is not edited.
- `RosterRow`, the `Row` protocol, `SEED_ROWS`' field values, `paper/store.py`, and every
  `db/migrations/*.sql`. No new database column; no migration.

**Requires (from earlier phases):** none. Phase 6 is in wave 1 and assumes nothing.

**Leaves alone (owned by others):**
- `lab/npolicy.py` (Phase 1), `lab/runner.py` (Phases 2, 4), `commands/lab.py` (Phases 3, 5),
  `lab/prereg.py` and all docs/web (Phase 7).
- In `lab/store.py`: `TRANSITIONS`, `DSR_MIN`, `DSR_LABEL`, `_SCHEMA`, `_migrate`,
  `dev_trial_count`, `dev_daily_sharpes`, `best_dev_eligible`, `verdict`, `snapshot` — all of
  Phase 2's and Phase 4's surface. This phase touches **only** the `PROMOTION_MARKER` constant
  block (store.py:82-84) and `record_promotion` (store.py:395-480).
- The committed `lab/lab.sqlite` is **read-only** here (Phase 4 owns the one migration, D5).
- In `tests/test_lab_store.py`: only the `_promote` helper (~line 200) and the promotion section
  that ends at line 250. Phase 4's edits live in the gate/verdict sections.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/roster.py` | modify | module docstring 56-66; `Basis` at 106; `BASES` at ~134; `LabProvenance` before 157; `RosterEntry.lab_provenance` at 191; `LAB_PROVENANCE` after 261; `from_row` return at 457 |
| `engine/src/seer_engine/lab/store.py` | modify | `PROMOTION_BASES` + `promotion_basis` after line 84; `record_promotion` (395-480) takes and records `basis`/`reason` |
| `engine/src/seer_engine/commands/promote.py` | modify | docstring; `build_promotion` 250-287; `render_plan` 289-336; `--lab-override-reason` at ~453; `_run` 480-540 |
| `engine/tests/test_paper_roster.py` | modify | new "lab provenance" section appended after line 498 |
| `engine/tests/test_promote_command.py` | modify | `_args` base at 51-60 gains `lab_override_reason`; one new refusal test after line 316 |
| `engine/tests/test_lab_store.py` | modify | `_promote` base at 202-209 gains `reason`; four new tests after line 250 |

**Six files** — reconciled; the index's draft said 4 and now says 6. The two extra are
`tests/test_promote_command.py` and `tests/test_lab_store.py`, which must move because
`record_promotion` now refuses an unexplained override and `promote` now requires
`--lab-override-reason`. No production file beyond the three the analysis named is touched.

### Shared-file protocol (reconciled — read before editing `store.py` or `test_lab_store.py`)

`lab/store.py` is written by phases **2, 4, 6 and 7**, and `tests/test_lab_store.py` by **2, 4 and
6**. This phase's two `store.py` regions are the `PROMOTION_MARKER` constant block and
`record_promotion`; nothing else in that file is this phase's. Three rules:

1. **Edit only at your named anchors.** Phase 2 owns the docstring, `SCHEMA_VERSION`, the
   `_MOMENTS_*` constants, `_SCHEMA`, `_migrate` and the trial-moments section; phase 4 owns
   `DSR_MIN`/`DSR_LABEL`/`LUCK_LABEL_PREFIX`/`DSR_POLICY`, `TRANSITIONS`, `best_dev_eligible` and
   the derived-verdict section; phase 7 owns `_gate_n` and `snapshot`'s `gate` dict.
2. **Anchor on quoted text, never on a line number.** Phase 2 inserts roughly 60 lines into
   `store.py` and phase 4 several hundred more, so **every `store.py` line number in this file
   (`:84`, `:395-480`) is a pre-phase-2 number and will have moved.** `PROMOTION_MARKER` and
   `record_promotion` are the anchors; the numbers are a hint.
3. **The swarm shares one worktree.** A commit of a shared file may legitimately carry another
   phase's work at other anchors. Keep it; never `git add -A`.

---

## Implementation Steps

### Step 1: The provenance type and its vocabulary

**File:** `engine/src/seer_engine/paper/roster.py:106` and `:134`
**Change:** add the `Basis` literal beside `Engine`/`Status`, and `BASES` beside
`ENGINES`/`STATUSES`. Two bases and no third: either the lab's own test window passed the
variant, or the owner admitted it anyway and said why.

**Code:** replace lines 106-107

```python
Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["active", "retired"]
```

with

```python
Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["active", "retired"]
Basis = Literal["test-passed", "owner-override"]
```

and, immediately after the `STATUSES` constant (currently roster.py:133-134):

```python
#: ``strategies.status``'s CHECK, as a Python value.
STATUSES: tuple[Status, ...] = ("active", "retired")

#: :class:`LabProvenance`'s ``basis`` vocabulary, as a Python value. Two bases and no third:
#: either the lab's own test window passed the variant (``test-passed``), or the owner admitted
#: it anyway and said why (``owner-override``). ``lab.store.PROMOTION_BASES`` is the same tuple
#: on the lab's side of the bridge; ``tests/test_paper_roster.py`` checks they agree.
BASES: tuple[Basis, ...] = ("test-passed", "owner-override")
```

**Impact:** none at runtime; two new module constants.

---

### Step 2: `LabProvenance`, validated where it is written

**File:** `engine/src/seer_engine/paper/roster.py:156` (insert immediately before the
`@dataclass(frozen=True, slots=True)` at line 157 that opens `RosterEntry`)
**Change:** a frozen, slotted dataclass whose `__post_init__` refuses a malformed line. The
validation lives here rather than in a test alone because the only way to get a bad value is a
hand-edit of this module, and that edit should fail at import, not at the next paper night.

Note what it deliberately does **not** check: that `candidate_id` starts with `method_id`.
`record_promotion` enforces that for `M*` methods, but the P7a history does not obey it —
`H-P7A-F4`'s candidate is `F4-MOM12-N20-TREND`. The method/candidate pairing is checked against
the database in the test, which is the only place that can check it truthfully.

**Code:**

```python
@dataclass(frozen=True, slots=True)
class LabProvenance:
    """Where a roster entry came from in ``lab/lab.sqlite``, and on what basis it was admitted.

    ``method_id`` and ``candidate_id`` name a row of the lab's append-only ``trials`` table --
    the exact backtest this entry is. ``lab_status`` is the method's status **at the moment of
    admission**, which is a fact about that night and never tracks the live row: the lab's status
    machine moves forward only, so a method admitted at ``'rejected'`` that is later re-judged
    still *was* ``'rejected'`` when the roster took it.

    ``basis`` is the admission rule that was used. ``'test-passed'`` is the lab's own route
    (design §3). ``'owner-override'`` is the roster's: paper membership has never required a gate
    pass, and when it is used ``reason`` must carry the one line that says why -- "the owner
    decided", with no why, is exactly the silence this field exists to end.

    Not part of :func:`spec`, deliberately and for the same reason ``gate_note`` is not:
    recording why an entry was admitted must never move a started entry's frozen digest.
    """

    method_id: str
    candidate_id: str
    lab_status: str
    basis: Basis
    reason: str

    def __post_init__(self) -> None:
        for name in ("method_id", "candidate_id", "lab_status"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"LabProvenance.{name} must be a non-empty string, got {value!r}"
                )
        if self.basis not in BASES:
            raise ValueError(f"LabProvenance.basis {self.basis!r} is not one of {BASES}")
        if not isinstance(self.reason, str):
            raise ValueError(f"LabProvenance.reason must be a string, got {self.reason!r}")
        if self.basis == "owner-override" and not self.reason.strip():
            raise ValueError(
                f"{self.candidate_id}: an owner-override admission must carry a one-line reason. "
                f"The roster's admission rule is the owner's, not the lab's gate, but the basis "
                f"goes on the record -- an unexplained override is the divergence this field "
                f"exists to end"
            )
```

**Impact:** a new public type. Nothing constructs one yet.

---

### Step 3: `RosterEntry` carries it, outside the spec

**File:** `engine/src/seer_engine/paper/roster.py:169-171` (docstring) and `:191` (the field)
**Change:** one trailing optional field, and a docstring sentence that says why it is not spec.

**Code:** replace the docstring paragraph at lines 169-171

```python
    ``status`` and ``paper_end`` are lifecycle, carried here so one value answers "what is this
    portfolio and is it still trading?". Neither is in :func:`spec`: retiring a strategy must
    not move its frozen digest.
    """
```

with

```python
    ``status`` and ``paper_end`` are lifecycle, carried here so one value answers "what is this
    portfolio and is it still trading?". Neither is in :func:`spec`: retiring a strategy must
    not move its frozen digest.

    ``lab_provenance`` is admission history: the lab method and variant this entry is, the lab
    status it was admitted under, and on what basis (:class:`LabProvenance`). ``None`` for an
    entry that did not come from a recorded lab candidate -- the benchmark, the LLM strategy,
    and ``A``, which predates the lab. It is not in :func:`spec` either, for the same reason
    ``gate_note`` is not: a recorded fact about *why* an entry was admitted must never move the
    digest of a strategy that is already running.
    """
```

and replace line 191

```python
    paper_end: date | None = None
```

with

```python
    paper_end: date | None = None
    lab_provenance: LabProvenance | None = None
```

**Impact:** `RosterEntry` gains a field with a default, so every existing construction keeps
working. `ROSTER == from_rows(SEED_ROWS)` and the database-rebuild equality still hold, because
both paths go through `from_row` and read the same table.

---

### Step 4: The provenance table

**File:** `engine/src/seer_engine/paper/roster.py:262` (insert after `RESOLVER`'s closing `}` at
line 261, before `def resolver_names()` at line 263)
**Change:** the second code-side table, keyed by roster id, with every lab-derived entry's line.

Each value was read out of the committed `lab/lab.sqlite` during planning:

| roster id | lab method | lab candidate | method status | recorded dev `failed` |
|---|---|---|---|---|
| `F4-MOM12-N20-TREND` | `H-P7A-F4` | `F4-MOM12-N20-TREND` | `rejected` | `max DD <= 15%` |
| `F1-SPY-SMA200-M` | `H-P7A-F1` | `F1-SPY-SMA200-M` | `rejected` | `max DD <= 15%; >= 100 trades` |
| `F4-MOM12-N20-TREND-FR` | `H-P7A-F4` | `F4-MOM12-N20-TREND` | `rejected` | same row as the whole-share F4 |
| `F1-SPY-SMA200-M-FR` | `H-P7A-F1` | `F1-SPY-SMA200-M` | `rejected` | same row as the whole-share F1 |
| `FND` | `M0005` | `M0005-ALL` | `rejected` | `beats SPY TR; >= 100 trades; DSR >= 0.95` |
| `RM-FR` | `M0011` | `M0011-RAW20-TV14-N21` | `rejected` | `DSR >= 0.95` (0.897 at N=90) |
| `RMW-FR` | `M0022` | `M0022-W-TV16` | `rejected` | `DSR >= 0.95` (0.916 at N=110) |

**Code:**

```python
#: Where each roster entry came from in the lab, keyed by roster id (lab-luck-gate R4, D3).
#:
#: **The second code-side table, and for the same reason as the first.** A promoted ``strategies``
#: row carries ``promoted_from`` -- the method id and nothing else -- and the rest of the fact
#: (which variant, what the lab said at the time, on what basis, and why) has nowhere on the row
#: to live. Nor could it be read out of ``lab/lab.sqlite`` here: **this module must never import
#: the lab** (see the comment above ``FUNDAMENTAL_PARAMS`` -- a lab import would let a lab-side
#: edit silently re-digest a started paper strategy). So the roster states its own provenance, in
#: its own file, exactly as it states its own params; and ``tests/test_paper_roster.py`` -- where
#: importing the lab is free -- checks every line of it against the committed database.
#:
#: An entry that did not come from a recorded lab candidate has **no key here**: ``SPY`` is the
#: benchmark, ``C`` is the LLM strategy the quant gate does not apply to (design §1 item 5), and
#: ``A`` predates the lab (``H-A`` records the idea but has no trial, so there is no candidate for
#: ``A`` to name; ``H-P7A-REF``'s ``REF-A-V0`` is a reference run, not an admission basis).
#:
#: **Append; never edit a started entry's line to make it read better.** The whole point of the
#: field is that it says what was true on the night of the admission. ``lab_status`` in
#: particular is frozen at that moment and does not follow the method's live status, which the
#: lab's forward-only machine may move later.
LAB_PROVENANCE: dict[str, LabProvenance] = {
    F4_ID: LabProvenance(
        method_id="H-P7A-F4",
        candidate_id=F4_ID,
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "P7a dev-window candidate, on the roster as the book engine's yardstick; it failed "
            "max DD <= 15% (22.2%) and has never had a test-window look"
        ),
    ),
    F1_ID: LabProvenance(
        method_id="H-P7A-F1",
        candidate_id=F1_ID,
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "P7a dev-window candidate, on the roster as the trend yardstick; it failed max DD "
            "<= 15% (18.7%) and >= 100 trades (11), and has never had a test-window look"
        ),
    ),
    FND_ID: LabProvenance(
        method_id="M0005",
        candidate_id="M0005-ALL",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the a-priori four-factor blend, chosen before the numbers rather than as the best "
            "of six; it failed beats SPY TR, >= 100 trades and DSR >= 0.95 on the dev window, "
            "and went on paper to be watched forward"
        ),
    ),
    F4_FR_ID: LabProvenance(
        method_id="H-P7A-F4",
        candidate_id=F4_ID,
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the same method and variant as the whole-share F4 it replaced, traded in fractional "
            "shares; the lab trial behind it is that one dev-window row, run in whole shares"
        ),
    ),
    F1_FR_ID: LabProvenance(
        method_id="H-P7A-F1",
        candidate_id=F1_ID,
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "the same method and variant as the whole-share F1 it replaced, traded in fractional "
            "shares; the lab trial behind it is that one dev-window row, run in whole shares"
        ),
    ),
    RM_ID: LabProvenance(
        method_id="M0011",
        candidate_id="M0011-RAW20-TV14-N21",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "it failed only the luck test -- recorded DSR 0.897 at its recorded N = 90 -- and "
            "passed every owner condition; on paper to test it forward. Retired for RMW-FR "
            "before its first session"
        ),
    ),
    RMW_ID: LabProvenance(
        method_id="M0022",
        candidate_id="M0022-W-TV16",
        lab_status="rejected",
        basis="owner-override",
        reason=(
            "it failed only the luck test -- recorded DSR 0.916 at its recorded N = 110 -- and "
            "passed every owner condition; on paper to test it forward"
        ),
    ),
}
```

**Impact:** `LabProvenance.__post_init__` runs at import for all seven, so a malformed line fails
the whole test run immediately rather than one paper night later.

---

### Step 5: `from_row` attaches it

**File:** `engine/src/seer_engine/paper/roster.py:457`
**Change:** one keyword in the return. A row whose id has no entry in the table gets `None`,
which is the honest answer for every entry that is not lab-derived — and the loud reminder for a
freshly promoted id is printed by `promote` (Step 9) and enforced by the pinned set in the test
(Step 10).

**Code:** replace lines 456-458

```python
        status=status,
        paper_end=paper_end,
    )
```

with

```python
        status=status,
        paper_end=paper_end,
        # Keyed by roster id, not read off the row: the ``strategies`` table has one provenance
        # column (``promoted_from``, the method id) and no room for the rest, and this module may
        # not read ``lab/lab.sqlite`` to fill it in. A row whose id is not in the table gets
        # ``None`` -- correct for SPY, C and A, and caught for anything else by
        # ``tests/test_paper_roster.py``, which pins the set of ids that must carry one.
        lab_provenance=LAB_PROVENANCE.get(sid),
    )
```

**Impact:** `ROSTER`, and any roster rebuilt from the database, now carry provenance. The digests
do not move — `spec()` never reads the field.

---

### Step 6: The doctrine paragraph says both halves

**File:** `engine/src/seer_engine/paper/roster.py:56-66`
**Change:** the module docstring currently states the roster's doctrine in a sentence tacked onto
`FND`'s gate note, and says nothing about the design document it contradicts. Replace it with a
paragraph that states the policy (unchanged), names design §3 and §6, calls the divergence
deliberate, and says what is now recorded. Decisions D3 settles the policy; this is the wording.

**Code:** replace lines 56-66

```
never an edited entry (``paper`` refuses a started id whose stored digest differs). ``status``,
``paper_end``, ``gate_note`` and ``gate_applicable`` are **not** in the spec, deliberately:
retiring a strategy or correcting a note must not move a live digest.

``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
``FND`` is on the roster having failed its gate too (six M0005 dev-window trials, all six failed,
all six recorded in ``lab/lab.sqlite``): passing a gate has never been this roster's admission
criterion, and the gates bind the real-money decision, not paper membership.
An entry with ``gate_applicable=False`` (C, an LLM strategy: design §1 item 5, handover D9)
also says ``applicable: false``; the four quant/benchmark entries' gate dicts are unchanged.
```

with

```
never an edited entry (``paper`` refuses a started id whose stored digest differs). ``status``,
``paper_end``, ``gate_note``, ``gate_applicable`` and ``lab_provenance`` are **not** in the spec,
deliberately: retiring a strategy, correcting a note, or recording why an entry was admitted must
not move a live digest.

``backtest_gate`` is a display fact for the go-live checklist (D12), not part of the spec:
correcting its note does not reset a paper clock. Every entry is ``passed: false`` today.
An entry with ``gate_applicable=False`` (C, an LLM strategy: design §1 item 5, handover D9)
also says ``applicable: false``; the four quant/benchmark entries' gate dicts are unchanged.

**Admission, and the deliberate divergence from the method lab's design (lab-luck-gate D3).**
Passing a gate has never been this roster's admission criterion, and it still is not: the gates
bind the real-money decision (design §1), not paper membership. ``FND`` joined having failed its
gate (six ``M0005`` dev-window trials, all six failed, all six in ``lab/lab.sqlite``), and
``RMW-FR`` trades today while lab method ``M0022`` reads ``rejected``. The method lab's design
reads the other way -- §3 ("Pass -> ``test-passed``, and the skill stops for the owner: a paper
roster entry (new id, own clock) is the owner's call") and §6 ("on a test pass, a paper-roster
entry with its own clock") both put a test pass on the path to this roster. **That divergence is
deliberate, not an oversight.** The rule here is the owner's: a lab test pass is a *sufficient*
basis for a paper entry, never a necessary one, because paper trading is how a near-miss earns
the right to be taken seriously and the lab's gate is tuned for the money decision, not for that.

What changed on 2026-10-07 is that the basis stopped being prose in a commit message.
:data:`LAB_PROVENANCE` gives every lab-derived entry its method, its variant, the lab status it
was admitted under, and the basis -- ``test-passed``, or ``owner-override`` with a one-line
reason -- and ``tests/test_paper_roster.py`` checks all of it against the committed
``lab/lab.sqlite``: the method exists, the variant is one of its recorded trials, and an override
names a trial the lab did not pass. ``lab.store.record_promotion`` writes the same fact onto the
method, so the two databases tell one story. The policy did not move; the silence did.
```

**Impact:** documentation only. No code reads the docstring.

---

### Step 7: The lab records the same fact — `promotion_basis` and `PROMOTION_BASES`

**File:** `engine/src/seer_engine/lab/store.py:84` (insert after `PROMOTION_MARKER`, before
`def _quoted` at line 87)
**Change:** the basis vocabulary and the rule that derives it from a method's status.

**Code:**

```python
# The first words of the analysis section `record_promotion` appends, and its idempotence key:
# a method whose analysis already names this roster id has been recorded and is not recorded twice.
PROMOTION_MARKER = "Promoted to the paper roster as "

#: How a roster entry was admitted (lab-luck-gate R4, D3): either the lab's own test window
#: passed the variant, or the owner took it anyway and said why. The same two words as
#: ``paper.roster.BASES``, which is the roster's side of the same bridge.
PROMOTION_BASES: tuple[str, ...] = ("test-passed", "owner-override")


def promotion_basis(status: str) -> str:
    """The admission basis a method's lab status implies at the moment it is promoted.

    ``'test-passed'`` only from the two statuses on the far side of the lab's own test window;
    everything else -- ``'rejected'`` included -- is an ``'owner-override'``. An override is
    allowed (the paper roster's admission rule is not the lab's gate: ``paper.roster``'s module
    docstring, plan Decisions D3) and must state a reason, which is what
    :func:`record_promotion` enforces.
    """
    return "test-passed" if status in ("test-passed", "paper") else "owner-override"
```

**Impact:** two new names in `lab.store`. Nothing calls them yet.

---

### Step 8: `record_promotion` writes the basis and the reason

**File:** `engine/src/seer_engine/lab/store.py:395-480`
**Change:** two new keyword-only params, a refusal when an override has no reason, and one more
sentence in the appended analysis section. The idempotence contract is untouched: the
`PROMOTION_MARKER` early return still comes first, so a re-run writes nothing and raises nothing
even if the caller passes a different reason. The journal `insights` row is also untouched — it
is written for the owner in plain words, and "basis" is not plain words.

**Code:** replace the whole function (store.py:395 through the `return status` at store.py:480)
with

```python
def record_promotion(
    conn: sqlite3.Connection,
    *,
    method_id: str,
    strategy_id: str,
    candidate_id: str,
    object_name: str,
    spec_digest: str,
    retired_id: str | None = None,
    move_status: bool = True,
    basis: str | None = None,
    reason: str = "",
) -> str:
    """Record that ``candidate_id`` became paper roster entry ``strategy_id``; return the status.

    The lab is append-only (§1), so a promotion is *added*, never stamped over anything:

    - ``analysis`` grows by one dated section (``methods_analysis_grows`` permits only growth);
    - one ``insights`` row is appended (the journal table refuses UPDATE and DELETE outright);
    - ``status`` moves to ``paper`` **only** along the edge ``TRANSITIONS`` already has,
      ``('test-passed', 'paper')``. A method already at ``paper`` is left alone. From any other
      status this raises LabError, because there is no edge and inventing one would make the
      lab's own vocabulary mean less. Pass ``move_status=False`` to record the promotion and
      leave the status where it is -- the honest shape for a roster that is taking a method the
      lab has not passed (the roster's admission rule is not the lab's gate: plan Decisions D3).

    **The basis (lab-luck-gate R4, D3).** ``basis`` is how the roster admitted the variant:
    ``'test-passed'`` when the lab's own test window passed it, ``'owner-override'`` when the
    owner took it anyway. Left ``None`` it is derived from the method's current status by
    :func:`promotion_basis`, which is right for every caller that has just read that status. An
    ``'owner-override'`` **must** carry a one-line ``reason``; without one this raises, because an
    unexplained override is exactly the silent divergence this argument exists to end. The basis,
    the reason and the status at admission are written into the analysis section, so the lab
    records the same fact ``paper.roster.LAB_PROVENANCE`` states on the roster's side.

    ``hypothesis``, ``verdict``, ``parent_id`` and above all ``source_sha`` are never written.
    No ``trials`` row is inserted: a promotion is not a backtest and must not move the lab's N.

    Idempotent: a method whose ``analysis`` already carries ``PROMOTION_MARKER`` followed by
    ``strategy_id`` is already recorded, and this writes nothing and returns the current status --
    including when this call's ``basis`` or ``reason`` differ, because what was recorded is what
    was true on the night of the admission. That is what lets the command be re-run to repair a
    half-finished promotion, since the roster (Neon) and the lab (SQLite) cannot share one
    transaction.

    The caller holds the transaction (``begin_immediate`` / ``with conn``), as every other writer
    in this module does.
    """
    row = get_method(conn, method_id)
    if row is None:
        raise LabError(f"no method {method_id}")
    if not candidate_id.startswith(method_id):
        raise LabError(f"candidate {candidate_id!r} does not belong to method {method_id}")
    status = str(row["status"])
    if PROMOTION_MARKER + f"`{strategy_id}`" in row["analysis"]:
        return status

    if move_status and status != "paper":
        if (status, "paper") not in TRANSITIONS:
            raise LabError(
                f"{method_id} is {status!r} and the lab's TRANSITIONS have no edge "
                f"{status!r} -> 'paper'; only 'test-passed' reaches 'paper'. The roster may still "
                f"take this method -- its admission rule is not the lab's gate -- but say so: "
                f"re-run with --lab-status-stays, which records the promotion and leaves the "
                f"status alone."
            )

    basis = promotion_basis(status) if basis is None else basis
    if basis not in PROMOTION_BASES:
        raise LabError(f"basis {basis!r} is not one of {PROMOTION_BASES}")
    reason = reason.strip()
    if basis == "owner-override" and not reason:
        raise LabError(
            f"{method_id} is {status!r}, so the roster is admitting a method the lab has not "
            f"passed. That is allowed -- the roster's admission rule is not the lab's gate -- but "
            f"the basis goes on the record: pass reason='the one line that says why'."
        )

    retired = "" if retired_id is None else f", replacing `{retired_id}` (retired the same moment)"
    why = f" {reason}" if reason else ""
    body = (
        f"{PROMOTION_MARKER}`{strategy_id}`{retired}.\n\n"
        f"Variant: `{candidate_id}`. Roster object: `{object_name}`. "
        f"Frozen spec digest: `{spec_digest}`.\n\n"
        f"Lab status at admission: `{status}`. Basis: `{basis}`.{why}\n\n"
        f"The roster row is `status='active'` with no `paper_start`: the next paper night freezes "
        f"the spec and starts its own clock, so the paper record begins at the promotion and "
        f"claims nothing earlier. `backtest.registry.REGISTRY` was not appended to -- a promoted "
        f"method reaches the roster through the roster's own resolver, so the lab's "
        f"multiple-testing count is unchanged by this."
    )
    append_analysis(conn, method_id, "# Promotion\n\n" + body)
    # The journal note is read by the owner, not an auditor: plain words, no digests or column names.
    # The technical record above stays in the method's analysis.
    replacing = "" if retired_id is None else f", taking the place of {retired_id}"
    add_insight(
        conn,
        kind="observation",
        title=f"{row['name']} starts paper trading as {strategy_id}",
        body=(
            f"Sera picked this method to trade with pretend money every night, under the short "
            f"name {strategy_id}{replacing}. Its rules are now locked, and its record starts from "
            f"its first night on paper, so nothing before that counts. Month by month against SPY "
            f"is how it earns trust."
        ),
        method_id=method_id,
    )
    if move_status and status != "paper":
        update_method(conn, method_id, status="paper")
        return "paper"
    return status
```

**Impact:** every caller that promotes a non-`test-passed` method must now pass a reason. There
is exactly one production caller (`commands/promote.py:512`, Step 9) and two test call sites
(Steps 11 and 12). The `insights` row, the idempotence key, `source_sha` and the status machine
are all unchanged.

---

### Step 9: `promote` asks for the basis and prints the roster line to add

**File:** `engine/src/seer_engine/commands/promote.py` — docstring (after line 44's paragraph),
`build_promotion` (250-287), `render_plan` (289-336), `add_arguments` (~453), `_run` (480-540)
**Change:** a required-when-overriding `--lab-override-reason`, provenance on the built entry,
the basis in the printed plan, and a copy-pasteable `LAB_PROVENANCE` line in the closing message
so the roster edit and the lab record land in one commit.

**9a — docstring.** Insert after the "**Two databases, one promotion.**" paragraph (which ends
at line 44 with "...because the lab is append-only."):

```
**The admission basis (lab-luck-gate R4, D3).** The roster's admission rule is not the lab's
gate: a method that has not passed a test window may still be promoted. What this command will
not do is let that happen silently. Whenever the method is not at ``test-passed``,
``--lab-override-reason`` is required: one line saying why. The basis and that line are written
into the method's ``analysis`` by ``lab.store.record_promotion``, and the command prints the
``paper.roster.LAB_PROVENANCE`` entry to add to the roster in the same commit, so the roster
states exactly what the lab records. ``tests/test_paper_roster.py`` is what makes forgetting loud.
```

**9b — `build_promotion`.** Replace its signature line (250) and the `entry = roster.RosterEntry(`
block (261-277) and the `return Promotion(` block (278-285):

```python
def build_promotion(
    args: argparse.Namespace, data_date: date, sort: int, lab_status: str
) -> Promotion:
    """The roster entry and its contract-C2 params, from the named method variant. No I/O.

    ``lab_status`` is the method's status as ``_run`` just read it; it becomes the entry's
    :class:`roster.LabProvenance` together with the basis that status implies and the owner's
    ``--lab-override-reason``. ``LabProvenance`` refuses an override with no reason, so a
    promotion that would leave the divergence unexplained fails here -- before either database
    is opened for writing.
    """
    _method, _path, candidate = find_candidate(args.method, args.candidate)
    obj = candidate.allocator
    rules = fractional_twin(candidate.rules) if getattr(args, "fractional", False) else candidate.rules
    _check_rules(rules)
    object_name = object_name_of(obj)
    _check_evidence(object_name)
    engine = "bracket" if rules.engine == "bracket_v0" else "book"
    lookback = obj.lookback if engine == "bracket" else obj.lookback(candidate.params)
    check_lookback(int(lookback), data_date)
    entry = roster.RosterEntry(
        id=args.id,
        name=args.name,
        sub=args.sub,
        icon=args.icon,
        is_champion=False,  # the champion is SPY (handover D2); a promotion never takes it
        is_benchmark=False,
        sort=sort,
        engine=engine,
        rules=rules,
        obj=obj,
        object_name=object_name,
        params=candidate.params,
        registry_id=None,  # D1: a promoted entry is never a REGISTRY entry
        lookback=int(lookback),
        gate_note=args.gate_note,
        gate_applicable=not args.gate_not_applicable,
        lab_provenance=roster.LabProvenance(
            method_id=args.method,
            candidate_id=candidate.id,
            lab_status=lab_status,
            basis=lab_store.promotion_basis(lab_status),
            reason=str(getattr(args, "lab_override_reason", "") or "").strip(),
        ),
    )
    return Promotion(
        entry=entry,
        params=roster.strategy_params(entry),
        method_id=args.method,
        candidate_id=candidate.id,
        retire_id=args.retire,
        sort=sort,
    )
```

**9c — `render_plan`.** In the `out +=` block that currently reads (promote.py:328-336):

```python
    out += [
        "",
        f"  lab/lab.sqlite, method {p.method_id} (now {lab_status!r})",
        "    methods.analysis  += a dated '# Promotion' section",
        f"    insights          += [observation] "
        f"'<method name> starts paper trading as {e.id}' (plain words)",
        "    methods.status    "
        + ("test-passed -> paper" if lab_move and lab_status == "test-passed"
           else f"{lab_status} (unchanged)"),
        "",
        "  backtest.registry.REGISTRY  untouched (Decisions D1)",
    ]
    return "\n".join(out)
```

replace with

```python
    prov = e.lab_provenance
    out += [
        "",
        f"  lab/lab.sqlite, method {p.method_id} (now {lab_status!r})",
        "    methods.analysis  += a dated '# Promotion' section",
        f"    insights          += [observation] "
        f"'<method name> starts paper trading as {e.id}' (plain words)",
        "    methods.status    "
        + ("test-passed -> paper" if lab_move and lab_status == "test-passed"
           else f"{lab_status} (unchanged)"),
        "",
        "  lab provenance (recorded on both sides, never part of the spec)",
        f"    method/variant  {prov.method_id} / {prov.candidate_id}",
        f"    lab status at admission  {prov.lab_status}",
        f"    basis           {prov.basis}",
        f"    reason          {prov.reason or '(the lab passed it; no override)'}",
        "",
        "  backtest.registry.REGISTRY  untouched (Decisions D1)",
    ]
    return "\n".join(out)
```

(`prov` is never `None` here: `build_promotion` always constructs one.)

**9d — the new flag.** Insert after the `--lab-status-stays` argument (which ends at line 453):

```python
    p.add_argument("--lab-override-reason", default="", metavar="REASON",
                   help="one line saying why the roster is taking a method the lab has not "
                        "passed. Required whenever the method is not at 'test-passed': the "
                        "roster's admission rule is the owner's, not the lab's gate, but the "
                        "basis goes on the record (lab-luck-gate D3). Recorded in the method's "
                        "analysis and in paper.roster.LAB_PROVENANCE")
```

**9e — `_run`.** Replace from the `move = not args.lab_status_stays` block (482-490) through the
closing message (535-540):

```python
        lab_status = str(method_row["status"])
        move = not args.lab_status_stays
        if move and lab_status not in ("test-passed", "paper"):
            raise lab_store.LabError(
                f"{args.method} is {lab_status!r} and the lab's TRANSITIONS have no edge "
                f"{lab_status!r} -> 'paper'; only 'test-passed' reaches 'paper'. The roster may "
                f"still take this method -- its admission rule is not the lab's gate (plan "
                f"Decisions D3) -- but say so: re-run with --lab-status-stays."
            )
        basis = lab_store.promotion_basis(lab_status)
        reason = str(getattr(args, "lab_override_reason", "") or "").strip()
        if basis == "owner-override" and not reason:
            raise PromoteError(
                f"{args.method} is {lab_status!r}, so this is an owner-override: the roster is "
                f"taking a method the lab has not passed. That is allowed (lab-luck-gate D3) but "
                f"it goes on the record -- re-run with --lab-override-reason 'one line saying "
                f"why'. Neither database was touched."
            )

        conn = db.connect()
        try:
            with conn.cursor() as cur:
                sort = args.sort if args.sort is not None else _next_sort(cur)
            p = build_promotion(args, data_date, sort, lab_status)

            retire_end: date | None = None
            with db.transaction(conn, args.dry_run):
                insert = _check_target(conn, p)
                if p.retire_id is not None:
                    retire_end = paper_store.retire(conn, p.retire_id)
                if insert:
                    _insert(conn, p)
                print(render_plan(p, retire_end=retire_end, lab_status=lab_status, lab_move=move))
            if args.dry_run:
                log.info("dry-run: the roster transaction was rolled back; nothing written")
        finally:
            conn.close()

        lab_store.begin_immediate(lab_conn)
        try:
            new_status = lab_store.record_promotion(
                lab_conn,
                method_id=p.method_id,
                strategy_id=p.entry.id,
                candidate_id=p.candidate_id,
                object_name=p.entry.object_name,
                spec_digest=p.digest,
                retired_id=p.retire_id,
                move_status=move,
                basis=basis,
                reason=reason,
            )
            if args.dry_run:
                lab_conn.rollback()
                log.info("dry-run: the lab transaction was rolled back; nothing written")
            else:
                lab_conn.commit()
                log.info("%s recorded in %s (status %s)", p.method_id, args.lab_db, new_status)
        except BaseException:
            lab_conn.rollback()
            raise
    finally:
        lab_conn.close()

    if not args.dry_run:
        prov = p.entry.lab_provenance
        print(
            f"\n{p.entry.id} is on the roster as active with no paper_start. The next paper night "
            f"freezes its spec and starts its clock. Commit {args.lab_db} and "
            f"{lab_store.snapshot_path(Path(args.lab_db))} with `lab stage`."
        )
        print(
            f"\nAdd this to paper.roster.LAB_PROVENANCE in the same commit, or the roster will "
            f"not state what the lab now records:\n"
            f"    {p.entry.id!r}: LabProvenance(\n"
            f"        method_id={prov.method_id!r},\n"
            f"        candidate_id={prov.candidate_id!r},\n"
            f"        lab_status={prov.lab_status!r},\n"
            f"        basis={prov.basis!r},\n"
            f"        reason={prov.reason!r},\n"
            f"    ),"
        )
    return 0
```

**Impact:** `promote` refuses an unexplained override before either database opens for writing.
The dry-run output gains four lines; `test_dry_run_prints_the_rows_and_writes_to_neither_database`
asserts on substrings that are still present, so it keeps passing.

---

### Step 10: The test that would have caught the divergence

**File:** `engine/tests/test_paper_roster.py:499` (append a new section at the end of the file)
**Change:** six tests. The load-bearing one reads the committed `lab/lab.sqlite` read-only and
checks every provenance line against it.

On the status check: the provenance's `lab_status` is a fact about the night of the admission and
must **not** be compared for equality with the method's live status — Phase 4 may move `M0022`
from `rejected` to `dev-eligible`, and the provenance must still read `rejected`. What the
database can still prove is that the live status is that one *or forward of it*, because the
lab's status machine moves forward only. That reachability check holds before Phase 4 (where
`rejected` is terminal, so it degenerates to equality) and after it.

**Code:**

```python
# ---- lab provenance (lab-luck-gate R4, phase 6) --------------------------------------------------
#
# The roster states where each of its lab-derived entries came from; these tests check that
# statement against the committed lab database. Importing the lab here is free -- it is
# `paper/roster.py` that must never do it (a lab-side edit would otherwise re-digest a started
# paper strategy), which is exactly why the check lives in the test file and not in the module.

import sqlite3  # noqa: E402

from seer_engine.lab import store as lab_store  # noqa: E402
from seer_engine.paper.roster import (  # noqa: E402
    BASES,
    LAB_PROVENANCE,
    LabProvenance,
)

#: Every roster entry admitted from a recorded lab candidate. A promotion adds a SEED_ROWS row
#: AND a LAB_PROVENANCE entry in the same commit; this tuple is the third place that has to name
#: it, and that is the point -- forgetting is a failing test, not a silent gap.
LAB_DERIVED = (F4, F1, FND, F4_FR, F1_FR, RM, RMW)
#: And the three that are not: SPY is the benchmark, C is the LLM strategy the quant gate does not
#: apply to, and A predates the lab (H-A records the idea but has no trial).
NOT_LAB_DERIVED = ("SPY", "A", "C")


def _lab_reachable(src: str) -> set[str]:
    """Every lab status reachable from ``src`` along ``TRANSITIONS``, ``src`` included."""
    seen, stack = {src}, [src]
    while stack:
        cur = stack.pop()
        for a, b in lab_store.TRANSITIONS:
            if a == cur and b not in seen:
                seen.add(b)
                stack.append(b)
    return seen


def test_every_entry_either_names_its_lab_candidate_or_has_none():
    assert set(LAB_DERIVED) | set(NOT_LAB_DERIVED) == set(ROSTER_IDS)
    assert not set(LAB_DERIVED) & set(NOT_LAB_DERIVED)
    assert set(LAB_PROVENANCE) == set(LAB_DERIVED)
    assert {e.id for e in ROSTER if e.lab_provenance is not None} == set(LAB_DERIVED)
    assert all(entry(i).lab_provenance is None for i in NOT_LAB_DERIVED)


def test_the_entries_name_the_variants_the_roster_advertises():
    assert (entry(RM).lab_provenance.method_id, entry(RM).lab_provenance.candidate_id) == (
        "M0011", "M0011-RAW20-TV14-N21")
    assert (entry(RMW).lab_provenance.method_id, entry(RMW).lab_provenance.candidate_id) == (
        "M0022", "M0022-W-TV16")
    assert (entry(FND).lab_provenance.method_id, entry(FND).lab_provenance.candidate_id) == (
        "M0005", "M0005-ALL")
    # the fractional twins trade the same lab candidate as the whole-share entries they replaced
    assert entry(F4_FR).lab_provenance.candidate_id == entry(F4).lab_provenance.candidate_id == F4
    assert entry(F1_FR).lab_provenance.candidate_id == entry(F1).lab_provenance.candidate_id == F1


def test_every_override_states_its_basis_and_a_reason():
    for sid, p in LAB_PROVENANCE.items():
        assert p.basis in BASES, sid
        assert p.lab_status in lab_store.STATUSES, sid
        if p.basis == "owner-override":
            assert p.reason.strip(), f"{sid}: an override must say why"
    # today every roster entry is an override admitted at 'rejected': not one of them has had a
    # test-window look. When that stops being true, this assertion is the place to say so.
    assert {p.basis for p in LAB_PROVENANCE.values()} == {"owner-override"}
    assert {p.lab_status for p in LAB_PROVENANCE.values()} == {"rejected"}
    assert set(BASES) == set(lab_store.PROMOTION_BASES)


def test_a_malformed_provenance_is_refused_where_it_is_written():
    with pytest.raises(ValueError, match="basis"):
        LabProvenance(method_id="M0001", candidate_id="M0001-A", lab_status="rejected",
                      basis="vibes", reason="r")
    with pytest.raises(ValueError, match="reason"):
        LabProvenance(method_id="M0001", candidate_id="M0001-A", lab_status="rejected",
                      basis="owner-override", reason="   ")
    with pytest.raises(ValueError, match="method_id"):
        LabProvenance(method_id="", candidate_id="M0001-A", lab_status="rejected",
                      basis="owner-override", reason="r")
    passed = LabProvenance(method_id="M0001", candidate_id="M0001-A", lab_status="test-passed",
                           basis="test-passed", reason="")
    assert (passed.basis, passed.reason) == ("test-passed", "")


def test_lab_provenance_is_not_in_the_spec():
    """Invariant 5. Provenance is a recorded fact about admission, like gate_note -- never spec."""
    other = LabProvenance(method_id="M0099", candidate_id="M0099-X", lab_status="test-passed",
                          basis="test-passed", reason="")
    for e in ROSTER:
        moved = dataclasses.replace(e, lab_provenance=other)
        assert spec_digest(spec(moved)) == PINS[e.id]
        assert strategy_params(moved) == strategy_params(e)
        assert set(strategy_params(e)) == {"spec", "digest", "backtest_gate"}


def test_every_provenance_matches_the_committed_lab_database():
    """The check that would have caught the RM/RMW divergence on the night it happened.

    The committed database, not ``SEER_LAB_DB``: a sera worktree's shared database holds sibling
    methods this tree does not have (the same reason ``test_lab_methods.py`` reads it this way).
    """
    if not lab_store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    conn = sqlite3.connect(f"file:{lab_store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for sid, p in sorted(LAB_PROVENANCE.items()):
            method = conn.execute(
                "SELECT id, status FROM methods WHERE id = ?", (p.method_id,)
            ).fetchone()
            assert method is not None, f"{sid}: no lab method {p.method_id} in the lab database"
            dev = conn.execute(
                "SELECT eligible, failed FROM trials WHERE method_id = ? AND candidate_id = ? "
                "AND window = 'dev'",
                (p.method_id, p.candidate_id),
            ).fetchone()
            assert dev is not None, (
                f"{sid}: {p.candidate_id!r} is not a recorded dev trial of {p.method_id}"
            )
            # `lab_status` is the status AT ADMISSION and never tracks the live row. What the
            # database can still prove is that the live status is that one or forward of it,
            # because the lab's status machine moves forward only.
            assert str(method["status"]) in _lab_reachable(p.lab_status), (
                f"{sid}: admitted at lab status {p.lab_status!r}, but {p.method_id} now reads "
                f"{method['status']!r}, which is not that status or forward of it"
            )
            if p.basis == "owner-override":
                assert dev["eligible"] == 0, (
                    f"{sid}: the basis says owner-override, but {p.candidate_id} passed the dev "
                    f"gate (failed={dev['failed']!r}). Nothing was overridden -- fix the basis"
                )
            else:
                passed = conn.execute(
                    "SELECT eligible FROM trials WHERE candidate_id = ? AND window = 'test'",
                    (p.candidate_id,),
                ).fetchone()
                assert passed is not None and passed["eligible"] == 1, (
                    f"{sid}: the basis says test-passed, but no passed test-window trial for "
                    f"{p.candidate_id} is recorded"
                )
    finally:
        conn.close()


def test_lab_provenance_agrees_with_the_promoted_from_column(pg):
    """The roster's own record and the one column ``promote`` writes name the same method."""
    rows = {r.id: r for r in store.read_roster_rows(pg)}
    for sid, p in LAB_PROVENANCE.items():
        if rows[sid].promoted_from is not None:
            assert rows[sid].promoted_from == p.method_id, sid
    # the three rows `promote` wrote are the only ones with a column to agree with; F4, F1 and
    # their fractional twins were seeded by migration before `promote` existed.
    assert {i for i, r in rows.items() if r.promoted_from is not None} == {FND, RM, RMW}
```

**Impact:** seven more tests in `test_paper_roster.py`. One (`..._promoted_from_column`) needs the
`pg` fixture; the rest are pure or read the committed SQLite file read-only. No test-window look
is spent: every query is a `SELECT`.

---

### Step 11: `test_lab_store.py` — the basis is recorded, and an override must explain itself

**File:** `engine/tests/test_lab_store.py:202-209` (the `_promote` helper) and `:250` (append)
**Change:** the helper's base gains a reason — every call in that section promotes a method that
is not `test-passed` — plus four new tests directly after the idempotence test.

**Code:** replace the `_promote` helper (test_lab_store.py:202-209)

```python
def _promote(conn, **kw):
    base = dict(
        method_id="M0001", strategy_id="FND", candidate_id="M0001-A",
        object_name="FUNDAMENTAL", spec_digest="d" * 64,
        reason="the lab has not passed it; on paper to test it forward",
    )
    base.update(kw)
    with conn:
        return store.record_promotion(conn, **base)
```

and append after `test_record_promotion_is_idempotent_and_never_touches_source_sha` (ends at
line 250):

```python
def test_promotion_basis_is_derived_from_the_lab_status():
    assert store.promotion_basis("test-passed") == "test-passed"
    assert store.promotion_basis("paper") == "test-passed"
    for s in ("idea", "registered", "rejected", "dev-eligible", "promoted", "blocked-data"):
        assert store.promotion_basis(s) == "owner-override"
    assert set(store.PROMOTION_BASES) == {"test-passed", "owner-override"}


def test_record_promotion_writes_the_basis_the_status_and_the_reason(conn):
    _method(conn, status="idea")
    assert _promote(conn, move_status=False) == "idea"
    analysis = store.get_method(conn, "M0001")["analysis"]
    assert "Lab status at admission: `idea`" in analysis
    assert "Basis: `owner-override`" in analysis
    assert "on paper to test it forward" in analysis


def test_an_override_with_no_reason_is_refused_and_writes_nothing(conn):
    _method(conn, status="idea")
    with pytest.raises(store.LabError, match="reason"):
        _promote(conn, move_status=False, reason="   ")
    row = store.get_method(conn, "M0001")
    assert store.PROMOTION_MARKER not in row["analysis"]
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 0


def test_a_test_passed_method_needs_no_reason_and_says_so(conn):
    _method(conn, status="idea")
    with conn:
        for nxt in ("registered", "dev-eligible", "promoted", "test-passed"):
            store.update_method(conn, "M0001", status=nxt)
    assert _promote(conn, reason="") == "paper"
    analysis = store.get_method(conn, "M0001")["analysis"]
    assert "Basis: `test-passed`" in analysis
    assert "Lab status at admission: `test-passed`" in analysis
```

**Impact:** the existing four promotion tests keep passing unchanged (the helper now supplies a
reason). `test_lab_test_window.py:370` calls `record_promotion` on a `test-passed` method, so its
basis derives to `test-passed`, no reason is needed and that file is **not** edited.

---

### Step 12: `test_promote_command.py` — the flag, and the refusal

**File:** `engine/tests/test_promote_command.py:51-60` and `:317` (append after
`test_a_rejected_method_needs_the_acknowledgement`)
**Change:** the shared `_args` base gains the new flag (the fixture method is at status `idea`,
so every test in the file is an owner-override), and one test proves the refusal.

**Code:** replace `_args` (test_promote_command.py:51-60)

```python
def _args(**kw) -> argparse.Namespace:
    base = dict(
        method=METHOD, candidate=VARIANT, id="TEST-FND", name="T · Fundamentals",
        sub="Top 20 on filed fundamentals, monthly", icon="book-open", sort=None,
        gate_note="No backtest gate: the dev window predates usable XBRL coverage",
        gate_not_applicable=False, retire=None, lab_db=None, lab_status_stays=True,
        lab_override_reason="the lab has not passed it; on paper to test it forward",
        dry_run=False, verbose=0,
    )
    base.update(kw)
    return argparse.Namespace(**base)
```

and append after line 316:

```python
def test_an_override_with_no_reason_is_refused_before_writing(pg, monkeypatch, lab, tmp_path):
    """The roster may take a method the lab has not passed -- but not silently (D3)."""
    _wire(monkeypatch, pg=pg, lab=lab)
    with pytest.raises(promote.PromoteError, match="--lab-override-reason"):
        promote._run(_args(lab_override_reason="", lab_db=tmp_path / "lab.sqlite"))
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_the_plan_prints_the_basis_and_the_roster_line_to_add(pg, monkeypatch, lab, tmp_path, capsys):
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    text = capsys.readouterr().out
    assert "basis           owner-override" in text
    assert f"method/variant  {METHOD} / {VARIANT}" in text
    assert "LAB_PROVENANCE" in text and "lab_status='idea'" in text
```

**Impact:** two new tests; one edited fixture line.

---

## Verification

**Build:** nothing to build (pure Python package, editable install).

**Tests** — run from the worktree against the main checkout's venv, with this tree's `src` first
on `PYTHONPATH` so it shadows the editable install (the worktree has no `.venv`):

```bash
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest \
  tests/test_paper_roster.py tests/test_promote_command.py tests/test_lab_store.py \
  tests/test_lab_test_window.py tests/test_strategy_purity.py tests/test_paper_fnd.py -q
```

then the whole suite:

```bash
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

**Manual check:**

1. **The spec did not move.** `git diff` must show no change inside `roster.spec`,
   `roster.spec_text`, `roster.spec_digest`, `roster.strategy_params`, `roster.backtest_gate`, or
   anywhere in `tests/test_paper_roster.py`'s `PINS` dict:
   ```bash
   cd /home/miftah/.worktrees/seer/lab-luck-gate && \
   git diff -- engine/tests/test_paper_roster.py | grep -E '^[-+].*(PINS|[0-9a-f]{64})' ; echo "exit $?"
   ```
   must print nothing (grep exit 1).
2. **No test-window look was spent:**
   ```bash
   cd /home/miftah/.worktrees/seer/lab-luck-gate && \
   python3 -c "import sqlite3;print(sqlite3.connect('lab/lab.sqlite').execute(\"SELECT count(*) FROM trials WHERE window='test'\").fetchone()[0])"
   ```
   must print `0`.
3. **`lab/lab.sqlite` is byte-identical:** `git status --porcelain lab/lab.sqlite` prints nothing.
4. Eyeball the new doctrine paragraph in `roster.py`: it must say the policy stands *and* that
   the basis is now recorded, and must name design §3 and §6.

**Exit criteria:**

- `RM-FR` and `RMW-FR` carry `owner-override` provenance naming `M0011`/`M0022`, their variants
  `M0011-RAW20-TV14-N21`/`M0022-W-TV16`, and the `rejected` status they were admitted under.
- `test_every_provenance_matches_the_committed_lab_database` passes against the committed
  `lab/lab.sqlite`, and fails if any provenance line is changed to name a method, variant or
  basis the database does not support.
- `test_digests_are_pinned` passes **unedited**, and so does every other pre-existing test in
  `test_paper_roster.py`.
- `lab.store.record_promotion` refuses an `owner-override` with no reason, and records the status
  at admission, the basis and the reason in the method's analysis.
- `pytest` green in `engine/`; `trials WHERE window='test'` still `0`; `lab/lab.sqlite` unchanged.

## Handoffs

**To Phase 7 (docs) — the wording design §3 needs.** Phase 7 owns
`docs/plans/2026-10-04-method-lab-design.md`; I did not touch it. The sentence that needs
amending is **line 66**, the last bullet of §3:

> Fail → `test-failed`, final. Pass → `test-passed`, and the skill stops for the owner: a paper
> roster entry (new id, own clock) is the owner's call; real money still needs all of design §1.

The one line Phase 7 should append to it (D3 is the decision this encodes):

> **A test pass is a sufficient basis for a paper roster entry, never a necessary one** — paper
> membership is the owner's call under the roster's own admission rule, not this gate
> (`paper/roster.py`'s doctrine; plan `lab-luck-gate` D3) — but the basis is recorded either way:
> `paper.roster.LAB_PROVENANCE` names the method, the variant, the lab status at admission and
> the basis (`test-passed` or `owner-override`, with a reason), and `lab.store.record_promotion`
> writes the same fact onto the method.

And at **line 103** in §6, where the skill's behaviour is described ("and, on a test pass, a
paper-roster entry with its own clock"), a parenthetical: *"(a test pass is one basis for a paper
entry; an owner-override with recorded provenance is the other — see §3)"*.

Phase 7 may also want `engine/package_readme.md` and the explore skill's promotion step to
mention `--lab-override-reason`. I did not edit either.

**To Phase 4 (the verdict) — verified compatible.** When `M0022` **and now `M0020`** are
re-evaluated to `dev-eligible`, **do not touch** `LAB_PROVENANCE["RMW-FR"].lab_status` — it
records `rejected` because that is what the lab said on the night of the admission. My database
test uses forward-reachability along `TRANSITIONS` rather than equality precisely so Phase 4's new
`("rejected", "dev-eligible")` edge keeps it green. `dev-eligible` is reachable from `rejected`
once that edge exists, so the assertion holds for RMW-FR after phase 4 runs. If Phase 4 added a
*backward* edge (it must not — the status machine is forward-only), that test is the one that
would fail.

**One assertion this phase must keep honest.** `test_every_override_states_its_basis_and_a_reason`
asserts `{p.lab_status for p in LAB_PROVENANCE.values()} == {"rejected"}` — a statement about the
status **at admission**, which phase 4 does not change for any existing entry. It stays true. What
would break it is a *new* promotion recorded after phase 4 has moved a method; that is a line
added to `LAB_PROVENANCE` and to this assertion in the same commit, by whoever promotes.

**To Phase 8 (the drawdown bar) — this phase records history and must not be re-synced to it.**
`F4-MOM12-N20-TREND`'s reason says it "failed max DD <= 15% (22.2%)" and `F1-SPY-SMA200-M`'s says
"(18.7%)". The first is still outside the owner's new 20% bar; the second is now **inside** it.
Neither string changes: `LAB_PROVENANCE` states why an entry was admitted **on the night it was
admitted**, under the bar in force then, exactly as `paper/roster.py`'s three historical
`"DSR >= 0.95"` gate notes do. Re-writing them to today's bar would falsify the record. The same
goes for `test_every_provenance_matches_the_committed_lab_database`, which asserts
`dev["eligible"] == 0` for an override — that reads the **recorded** column, which is append-only
and never moves, so it is unaffected by either owner-set bar.

**Not done, deliberately:**
- A `lab_provenance` column on `strategies` with a migration. That would persist provenance to
  Neon, but it needs `db/migrations/012_*.sql`, `paper/store.StrategyRow`, `RosterRow`, the `Row`
  protocol and `ROW_COLUMNS` — far outside this phase, and nothing reads it. The existing
  `promoted_from` column already carries the method id, and the new pg test ties the code table
  to it. Worth a separate card.
- A fourth key in `strategies.params` (`lab_provenance` next to `spec`/`digest`/`backtest_gate`).
  That would rewrite the stored jsonb of started rows and change contract C2 for a display fact.
  Rejected.
- `A`'s P3 gate record (`gate_note`: "P3 gate failed out of sample…") is not a lab trial and has
  no `trials` row; `A` therefore carries `None`. If the owner ever wants P3 in the lab, that is a
  new method row, not a provenance edit.

## Rollback

`git revert` the phase's single commit. Everything in it is additive:

- `paper/roster.py` loses one optional field, one type, one dict and a docstring paragraph. No
  digest moves on the way out any more than on the way in — `spec()` never read any of it.
- `lab/store.py` loses two keyword params with defaults, one constant and one function;
  `record_promotion` goes back to not asking for a reason. **Analysis sections already written
  keep their "Lab status at admission / Basis" line** — the lab is append-only and that line is
  now history, not configuration. Nothing reads it back.
- `commands/promote.py` loses a flag. A script passing `--lab-override-reason` after a revert
  fails with an argparse error, which is loud and immediate.
- No database changed: `lab/lab.sqlite` is read-only in this phase and no migration was written,
  so there is nothing to undo on either side.
