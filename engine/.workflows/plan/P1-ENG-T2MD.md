> Adopted from `/home/miftah/seer/.workflows/orchestration/journal-versioning/PLAN.md` phase 3. Source: `.workflows/plan/journal-versioning/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Auto-link the five journalling writers on `doc_key`

**Plan set:** `JOURNAL_VERSIONING_PLAN.md`
**Analysis:** `docs/analyzer/20261020-162050-J7K2_code_analyzer.md`
**Satisfies:** R2 — a re-run of an auto-journalling command becomes a **new version of the same
document**, not a fifth card on the owner's page; and three different arms of one method stay
three documents.
**Depends on:** Phase 1 (schema 8: `doc_key`, `supersedes`, `store.add_insight(doc_key=,
supersedes=)`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase, every row the five auto-journalling writers append carries a `doc_key` naming
the **document** it is a version of, and a second run of the same command on the same subject
writes a row linked to its own predecessor instead of a sibling card. The key is computed from
what the command actually measured — the arm for `lab costs`, the measured arm set for a narrowed
`lab gate` / `lab exposure`, the method for an un-narrowed roll-up — so the M0260 incident
(insights 466/467/468, three arms, one generated title, 25 seconds apart) replays as **three
documents, not one**.

## The measured bug this phase exists to prevent

`real_costs.insight_text` (`real_costs.py:407`) builds the title from `cmp.method_name` while
`Comparison` carries `cmp.candidate_id` (`real_costs.py:226`) and never uses it. Measured against
the recorded `trials` rows:

| insight | reported max DD / PF | is actually | trial |
|---|---|---|---|
| 466 | 23.8% / 1.98 | `M0260-M-NATIVE` | n=835 |
| 467 | 25.6% / 1.62 | `M0260-M-G12` | n=838 |
| 468 | 33.6% / 1.60 | `M0260-M-G3` | n=836 |

An auto-linker keyed on `method_id` or on the generated title would bury the 23.8%-drawdown arm
underneath the 33.6% one and show the owner only the last. **That is a measurement vanishing off
the page — the precise failure append-only exists to prevent.** The key is therefore the subject,
never the method name and never the title.

## What I measured in the writers, and how it changes the brief

The brief anticipated that all five writers report per-variant and that each key would be
`prefix:candidate_id`. **That is true of exactly one of them.** Read in the worktree:

| Writer | Report type | Covers | Can be narrowed? |
|---|---|---|---|
| `real_costs` | `Comparison` (`real_costs.py:218`) | **one arm** — `pick_candidate` resolves exactly one | always one arm (`--candidate`, else best by MAR) |
| `survivorship_check` | `MethodReport` (`survivorship_check.py:462`), `rows: tuple[VariantRow, ...]` | **every recorded dev variant** of the method | **no** — the `survivorship` parser has no `--only` |
| `gate_probe` | `MethodReport` (`gate_probe.py:1014`), `rows: tuple[VariantRow, ...]` | every recorded dev variant | **yes** — `--only IDS` and `--gated-only` both drop rows (`gate_probe.plan_methods`, `gate_probe.py:742`) |
| `exposure` | `MethodReport` (`exposure.py`, `rows: tuple[VariantRow, ...]`) | every recorded dev variant | **yes** — `--only IDS` (`commands/lab.py:2937`) |
| `prereg` | no report — one `store.add_insight` at `prereg.py:731`, inside `if recorded is None:` | the method | n/a; writes **once per method, ever** |

The three roll-up writers emit **one observation per method covering a set of arms**
(`insight_text` uses `rep.headline` plus `len(rep.rows)` counts). Their document identity is
therefore not a single candidate id. The rule this phase ships:

- **Not narrowed** (the command measured every recorded dev variant it could find) → scope is the
  literal word `all`. The document is *"what this command says about this method"*; a later
  re-run over a grown set of arms is **version 2 of it**, and nothing vanishes because the
  predecessor row stays in the database and phase 5 renders history behind a disclosure.
- **Narrowed** (`--only`, `--gated-only`, or `lab costs`'s inherently single arm) → scope is the
  sorted, `+`-joined list of the arms actually measured. A narrowed run is a deliberate question
  about *those* arms; a second narrowed run about *different* arms must stand beside it, never on
  top of it. **This is the branch that keeps 466/467/468 three documents.**

One grammar for all five: `prefix:method_id:scope`.

## Interface Contract

**Creates:**
- `seer_engine.lab.journal_docs` — new module `engine/src/seer_engine/lab/journal_docs.py`
- `journal_docs.ALL` (`journal_docs.py`)
- `journal_docs.doc_key(prefix, method_id, candidate_ids=None)` (`journal_docs.py`)
- `journal_docs.head_for(conn, key, *, method_id)` (`journal_docs.py`)
- `journal_docs.append(conn, *, kind, title, body, method_id, key, supersede=True)` (`journal_docs.py`)
- `journal_docs.entry_label(new_id, superseded)` (`journal_docs.py`)
- `real_costs.DOC_PREFIX`, `real_costs.doc_key(cmp)` (`real_costs.py`)
- `survivorship_check.DOC_PREFIX`, `survivorship_check.doc_key(rep)` (`survivorship_check.py`)
- `gate_probe.DOC_PREFIX`, `gate_probe.doc_key(rep, *, narrowed=False)` (`gate_probe.py`)
- `exposure.DOC_PREFIX`, `exposure.doc_key(rep, *, narrowed=False)` (`exposure.py`)
- `prereg.DOC_PREFIX` (`prereg.py`)
- `engine/tests/test_lab_journal_docs.py` (new test module)

**Signature changes:**
- `real_costs.journal(conn, cmp)` -> `real_costs.journal(conn, cmp, *, supersede=True)`, return
  `int` -> `tuple[int, int | None]`
- `survivorship_check.journal(conn, rep)` -> `(conn, rep, *, supersede=True)`, return `int` ->
  `tuple[int, int | None]`
- `gate_probe.journal(conn, rep)` -> `(conn, rep, *, narrowed=False, supersede=True)`, return
  `int` -> `tuple[int, int | None]`
- `exposure.journal(conn, rep)` -> `(conn, rep, *, narrowed=False, supersede=True)`, return `int`
  -> `tuple[int, int | None]`

**Deletes:** nothing.
**Renames:** nothing.

**New CLI flags (on the five journalling subcommands' own parsers only):**
- `lab costs --no-supersede` (`commands/lab.py:338`)
- `lab survivorship --no-supersede` (`commands/lab.py:568`)
- `lab exposure --no-supersede` (`commands/lab.py:631`)
- `lab gate --no-supersede` (`commands/lab.py:688`)
- **`lab promote` gets none** — see Step 7 for why a flag there could never change an outcome.

**Requires (from earlier phases):**
- Phase 1: `store.add_insight(conn, *, kind, title, body, method_id=None, doc_key=None,
  supersedes=None) -> int`, which writes both new columns on the **INSERT** (never an UPDATE).
- Phase 1: the `insights.doc_key TEXT` and `insights.supersedes INTEGER REFERENCES insights(id)`
  columns, and the partial unique index `insights_one_successor` on `supersedes`.
- Phase 1: `store.LabError` is still the refusal type, and `store.set_supersedes` exists (this
  phase does **not** call it — see Step 1's note on why the link is written at INSERT time).
- Phase 1 has run the v8 migration and committed the migrated `lab.sqlite` with
  `web/data/lab.json`.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/store.py` — phase 1 (schema, trigger, validation, `add_insight`,
  `set_supersedes`). **No edit of any kind.**
- `commands/lab.py`'s `_insight` / `_link` handlers and the `insight` subparser at
  `commands/lab.py:761`, and the `lab insight` usage line at `commands/lab.py:130` — phase 2.
- `store.snapshot` / `summary_rows` and `web/lib/sera/types.ts` — phase 4.
- `web/app/sera/journal/*` — phase 5.
- `lab/lab.sqlite` data and `web/data/lab.json` — phase 6. **This phase writes no lab data and
  runs no `lab stage`.**
- `engine/src/seer_engine/lab/hardgate.py` — a concurrent session owns it.

**Deliberate deviations from the brief's literal strings, flagged for the reconciler:**

| Brief said | This plan ships | Why |
|---|---|---|
| `real-costs:{cmp.candidate_id}` | `real-costs:{method_id}:{candidate_id}` | one grammar `prefix:method:scope` across all five, so phase 4/6 and any future reader parse without a per-writer special case; the method id is redundant inside the candidate id but costs nothing |
| `survivorship:{candidate_id}` | `survivorship:{method_id}:all` | measured: `survivorship_check.MethodReport` covers **every** recorded variant and its parser has no `--only`; there is no single arm to key on |
| `prereg:{method_id}` | `prereg:{method_id}:all` | same grammar; `all` reads as "the whole of this method", which is what a pre-registration covers |

Nothing downstream depends on the literal shape (phase 4 exports `docKey` opaquely, phase 5 never
shows it, phase 6 links by explicit id), so this is safe to reconcile either way; if the
reconciler prefers the brief's literals, change only `doc_key()` in each writer and its unit test.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/journal_docs.py` | create | the one definition of a document key, the head lookup, and the linked append |
| `engine/src/seer_engine/lab/real_costs.py` | modify | `DOC_PREFIX` + `doc_key` + `journal` rewritten (`:434`); import at `:40` |
| `engine/src/seer_engine/lab/survivorship_check.py` | modify | `DOC_PREFIX` + `doc_key` + `journal` rewritten (`:737`); import at `:51` |
| `engine/src/seer_engine/lab/gate_probe.py` | modify | `DOC_PREFIX` + `doc_key` + `journal` rewritten (`:1395`); import at `:107` |
| `engine/src/seer_engine/lab/exposure.py` | modify | `DOC_PREFIX` + `doc_key` + `journal` rewritten (`:1097`); import at `:91` |
| `engine/src/seer_engine/lab/prereg.py` | modify | `DOC_PREFIX`; the `add_insight` call at `:731` becomes a `journal_docs.append` |
| `engine/src/seer_engine/commands/lab.py` | modify | `--no-supersede` on four parsers (`:338`, `:568`, `:631`, `:688`); four usage lines (`:55`, `:87`, `:93`, `:101`); four handler journal blocks (`:2304`, `:2766`, `:2953`, `:3030`) |
| `engine/tests/test_lab_journal_docs.py` | create | the helper's own suite **and the M0260 three-arm regression** |
| `engine/tests/test_lab_costs.py` | modify | tuple return at `:202`, `:252`; new revise/sibling/no-supersede tests |
| `engine/tests/test_lab_survivorship.py` | modify | tuple return at `:285`; revise test; `--no-only` guard test |
| `engine/tests/test_lab_gate_probe.py` | modify | tuple return at `:668`; revise + narrowed-sibling tests |
| `engine/tests/test_lab_exposure.py` | modify | tuple return at `:483`; revise + narrowed-sibling tests |
| `engine/tests/test_lab_prereg.py` | modify | assert the pre-registration row carries `prereg:M0001:all` |

---

## Implementation Steps

### Step 1: the one definition — `lab/journal_docs.py`

**File:** `engine/src/seer_engine/lab/journal_docs.py` (new file)

**Change:** The brief asked for one definition so all five writers get identical semantics, and
preferred it inside `store.add_insight`. **`store.py` belongs to phase 1 and this phase may not
edit it**, so the one definition lives in a new module instead. The property the brief wanted —
one place, five identical callers — holds exactly as well, and there is no cross-phase edit
conflict. If the reconciler would rather fold `head_for`/`append` into `store.add_insight`, it is
a mechanical move of two functions; the writers' call sites do not change shape.

Why the link is written on the **INSERT** and not with `store.set_supersedes`: an INSERT never
reaches the narrowed `insights_no_update` trigger at all. The append-only guarantee is not merely
respected here, it is untouched. `set_supersedes` stays phase 2's tool for linking rows that
already exist (the phase 6 backfill).

**Code:**

```python
"""One definition of what a journal *document* is, shared by every command that journals.

The lab journal is append-only: a row is never rewritten. That is the anti-self-deception rule --
nobody can revise what a method predicted after seeing how it turned out. But append-only says
nothing about how the rows should *read*, and today a command run twice on the same subject puts
two cards in front of the owner. Schema 8 adds ``doc_key`` (what a row is about) and ``supersedes``
(which row this one replaces), so a chain of rows renders as one versioned document while the
store stays immutable. Superseding ADDS a row; it never mutates one.

The hard part is not the linking, it is the KEY, and the lab has a measured incident that settles
it. Insights 466, 467 and 468 share one title, were written 25 and 30 seconds apart, and look
exactly like an accidental triple-write. They are not: they are ``M0260-M-NATIVE``,
``M0260-M-G12`` and ``M0260-M-G3``, confirmed against trials n=835/838/836 by their recorded max
drawdown and profit factor. ``real_costs`` titles on the method NAME and never on the
``candidate_id`` it is holding. A key taken from the method, or from the generated title, would
have buried a 23.8% drawdown underneath a 33.6% one and shown the owner only the last -- a
measurement disappearing off the rendered page, which is the exact failure the append-only rule
exists to prevent, arriving through the front door of the feature written to respect it.

So the key is the SUBJECT the command measured, in one grammar for all five writers:

    <prefix>:<method id>:<scope>

``scope`` is the sorted ``+``-joined list of the arms measured when the run was narrowed to
particular arms, and the literal ``all`` when it was not. See ``doc_key``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from seer_engine.lab import store

#: The scope of a run that was not narrowed to particular arms: everything the command could see
#: of this method. A later run over a grown set of arms is a new VERSION of that document, not a
#: rival to it -- the question ("what does this command say about this method?") did not change.
ALL = "all"


def doc_key(
    prefix: str, method_id: str, candidate_ids: Iterable[str] | None = None
) -> str:
    """The stable identity of the document a journal row is a version of.

    ``candidate_ids`` is ``None`` when the writer measured every recorded dev variant it could
    find. ``prefix`` names the command, so two different commands never collide on one method.

    Pass the arm list whenever the run WAS narrowed -- ``--only``, ``--gated-only``, or
    ``lab costs``, which always reports exactly one arm. A narrowed run is a deliberate question
    about those arms, and a later narrowed run about different arms must stand beside it rather
    than on top of it. That branch is what keeps M0260's three arms three documents.

    The list is sorted and de-duplicated, so ``--only A,B`` and ``--only B,A`` are one document.
    """
    if candidate_ids is None:
        scope = ALL
    else:
        ids = sorted(set(candidate_ids))
        if not ids:
            raise store.LabError(
                "a narrowed journal document needs at least one candidate id; pass None for a "
                "run that measured every recorded variant"
            )
        scope = "+".join(ids)
    return f"{prefix}:{method_id}:{scope}"


def head_for(
    conn: sqlite3.Connection, key: str, *, method_id: str | None
) -> int | None:
    """The id of the current version of document ``key``, or ``None`` if it has none yet.

    The head is the row carrying this ``doc_key`` that no other row supersedes. A well-formed
    chain has exactly one. ``ORDER BY id DESC`` makes the choice deterministic if a second head
    ever exists -- a hand-written row that reused the key, say -- and picking the newest keeps the
    chain single-threaded from here on while leaving the stray visible as its own document.
    Nothing is ever hidden: that is the set's invariant 2.

    ``method_id`` narrows the search to the method the new row belongs to, so a link can never
    cross methods and ``store.set_supersedes``'s cross-method refusal is unreachable from here.

    The 500 rows written before schema 8 carry ``doc_key IS NULL``, and ``doc_key = ?`` never
    matches NULL in SQLite, so no writer can accidentally supersede a historical row.
    """
    row = conn.execute(
        """
        SELECT id FROM insights
         WHERE doc_key = ?
           AND method_id IS ?
           AND id NOT IN (SELECT supersedes FROM insights WHERE supersedes IS NOT NULL)
         ORDER BY id DESC
         LIMIT 1
        """,
        (key, method_id),
    ).fetchone()
    return None if row is None else int(row[0])


def append(
    conn: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    body: str,
    method_id: str | None,
    key: str,
    supersede: bool = True,
) -> tuple[int, int | None]:
    """Write one journal row as the newest version of document ``key``.

    Returns ``(new id, the id it supersedes or None)``. The second element is ``None`` when this
    is version 1 of the document, or when ``supersede`` is False -- the ``--no-supersede`` escape,
    for a genuinely new observation that happens to share a document key and must stand beside its
    predecessor instead of replacing it on the page.

    The link is written on the INSERT, so the narrowed append-only trigger is never reached and no
    row is ever updated. If a concurrent session (``SEER_LAB_DB`` is shared) linked to the same
    head between the read and the insert, the unique index ``insights_one_successor`` refuses this
    row; the head is re-read once and the row is written against theirs, so the two runs chain
    rather than fork. A second failure is a real error and is raised.

    The caller owns the transaction (``with conn:``).
    """
    previous = head_for(conn, key, method_id=method_id) if supersede else None
    try:
        new_id = store.add_insight(
            conn, kind=kind, title=title, body=body, method_id=method_id,
            doc_key=key, supersedes=previous,
        )
    except sqlite3.IntegrityError:
        if previous is None:
            raise
        previous = head_for(conn, key, method_id=method_id)
        new_id = store.add_insight(
            conn, kind=kind, title=title, body=body, method_id=method_id,
            doc_key=key, supersedes=previous,
        )
    return new_id, previous


def entry_label(new_id: int, superseded: int | None) -> str:
    """How a written entry is reported to the owner: ``#471``, or ``#471 (revises #468)``.

    Plain words and plain numbers -- the owner reads this line, so it says what happened to his
    page rather than naming a column.
    """
    return f"#{new_id}" if superseded is None else f"#{new_id} (revises #{superseded})"
```

**Impact:** new module, no existing behaviour changes until Steps 2-7 call it. Imports only
`store` and `sqlite3`, so it cannot create a cycle with the four writers (which all import
`real_costs`, and `gate_probe` additionally imports `exposure`).

---

### Step 2: `real_costs` — keyed on the arm, always

**File:** `engine/src/seer_engine/lab/real_costs.py:40` (import) and `:434` (the function)

**Change:** add `journal_docs` to the lab imports, then replace `journal` wholesale and add
`DOC_PREFIX` / `doc_key` above it. `insight_text` and the title string at `:407` are **not
touched** — changing a generated title would make rows written before and after this phase
disagree, and the set's invariant 2 forbids it.

At `real_costs.py:40`, replace:

```python
from seer_engine.lab import store
```

with:

```python
from seer_engine.lab import journal_docs, store
```

Then replace the whole of `journal` (`real_costs.py:434-438`):

```python
def journal(conn: sqlite3.Connection, cmp: Comparison) -> int:
    """Append the comparison to the lab journal as one ``observation`` on the method. The caller
    owns the transaction (``with conn:``). Returns the insight id."""
    title, body = insight_text(cmp)
    return store.add_insight(conn, kind="observation", title=title, body=body, method_id=cmp.method_id)
```

with:

```python
#: The command half of this writer's document keys. See ``lab/journal_docs.py``.
DOC_PREFIX = "real-costs"


def doc_key(cmp: Comparison) -> str:
    """The document this comparison is a version of: the real-fee reading of THIS ARM.

    Keyed on the arm and never on the method, because `lab costs` reports one variant's numbers
    and nothing else, so two runs on two arms are two measurements and must be two documents.
    Insights 466, 467 and 468 are ``M0260-M-NATIVE``, ``M0260-M-G12`` and ``M0260-M-G3``, written
    25 and 30 seconds apart under one generated title (this module titles on ``method_name`` and
    has never used the ``candidate_id`` it is holding at ``Comparison.candidate_id``). A
    method-keyed document would have buried a 23.8% drawdown underneath a 33.6% one and shown the
    owner only the last.
    """
    return journal_docs.doc_key(DOC_PREFIX, cmp.method_id, [cmp.candidate_id])


def journal(
    conn: sqlite3.Connection, cmp: Comparison, *, supersede: bool = True
) -> tuple[int, int | None]:
    """Append the comparison to the lab journal as one ``observation`` on the method, as the
    newest version of this arm's real-fee document.

    The caller owns the transaction (``with conn:``). Returns ``(insight id, the id it supersedes
    or None)``. ``supersede=False`` is the ``--no-supersede`` escape: the row is written as a
    sibling, for a genuinely new observation that happens to share a document key.
    """
    title, body = insight_text(cmp)
    return journal_docs.append(
        conn, kind="observation", title=title, body=body, method_id=cmp.method_id,
        key=doc_key(cmp), supersede=supersede,
    )
```

**Impact:** `real_costs.journal` now returns a 2-tuple. Call sites: `commands/lab.py:2304`
(Step 6) and `engine/tests/test_lab_costs.py:202` (Step 9). No other caller exists — verified by
`grep -rn "real_costs.journal\|rc.journal" engine/`.

---

### Step 3: `survivorship_check` — method-wide, because it cannot be narrowed

**File:** `engine/src/seer_engine/lab/survivorship_check.py:51` (import) and `:737` (the function)

**Change:** This writer is the one the brief flagged as possibly knowing only its method, and the
measurement says it does: `MethodReport.rows` is **every** recorded dev variant, the `survivorship`
parser (`commands/lab.py:538-571`) has `method`, `--store`, `--sv-store`, `--no-journal`, `--csv`
and no `--only`, and `insight_text` reports the headline arm plus a roll-up over all of them. So
the scope is `all`, permanently — and Step 10 adds a test that fails the day someone adds an
`--only`, pointing back here.

At `survivorship_check.py:51`, replace:

```python
from seer_engine.lab import hardgate, runner, store
```

with:

```python
from seer_engine.lab import hardgate, journal_docs, runner, store
```

Then replace the whole of `journal` (`survivorship_check.py:737-740`):

```python
def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(conn, kind="observation", title=title, body=body, method_id=rep.method_id)
```

with:

```python
#: The command half of this writer's document keys. See ``lab/journal_docs.py``.
DOC_PREFIX = "survivorship"


def doc_key(rep: MethodReport) -> str:
    """The document this report is a version of: the survivorship reading of the whole method.

    Method-wide rather than per-arm, and that is a measured choice rather than a shortcut.
    ``MethodReport.rows`` is every recorded dev variant of the method -- ``lab survivorship`` has
    no ``--only`` and cannot be narrowed -- and ``insight_text`` reports the headline arm beside a
    roll-up over all of them. There is no single arm this document is about. A re-run after new
    dev trials land covers a grown set and is version 2 of the same question; the earlier row
    stays in the store and is read as the earlier version, so no measurement is hidden.

    If this command ever gains an ``--only``, this function must gain the narrowed branch the
    other writers have, or a narrowed run would bury an un-narrowed one. A test pins that.
    """
    return journal_docs.doc_key(DOC_PREFIX, rep.method_id)


def journal(
    conn: sqlite3.Connection, rep: MethodReport, *, supersede: bool = True
) -> tuple[int, int | None]:
    """One ``observation`` on the method, as the newest version of its survivorship document.

    The caller owns the transaction. Returns ``(insight id, the id it supersedes or None)``.
    ``supersede=False`` writes a sibling instead (``--no-supersede``).
    """
    title, body = insight_text(rep)
    return journal_docs.append(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id,
        key=doc_key(rep), supersede=supersede,
    )
```

**Impact:** return type change; call sites `commands/lab.py:2770` (Step 6) and
`engine/tests/test_lab_survivorship.py:285` (Step 9).

---

### Step 4: `gate_probe` — narrowed by `--only` **and** by `--gated-only`

**File:** `engine/src/seer_engine/lab/gate_probe.py:107` (import) and `:1395` (the function)

**Change:** `gate_probe.plan_methods(conn, ids, only, gated_only=...)` (`gate_probe.py:742`) drops
variants for **both** flags — `--only` by name (`:766-782`) and `--gated-only` by dropping every
variant with no gate site (`:784-791`). Both narrow the measured set, so both set `narrowed`.

At `gate_probe.py:107`, replace:

```python
from seer_engine.lab import hardgate, runner, store
```

with:

```python
from seer_engine.lab import hardgate, journal_docs, runner, store
```

Then replace the whole of `journal` (`gate_probe.py:1395-1400`):

```python
def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id
    )
```

with:

```python
#: The command half of this writer's document keys. See ``lab/journal_docs.py``.
DOC_PREFIX = "gate"


def doc_key(rep: MethodReport, *, narrowed: bool = False) -> str:
    """The document this report is a version of.

    ``narrowed`` is True when the run was restricted to particular arms -- ``--only`` names them,
    and ``--gated-only`` drops every variant the walk found no gate in; ``plan_methods`` applies
    both. A narrowed run is a deliberate question about the arms it kept, so it is keyed on them
    and a later narrowed run about different arms stands beside it. An un-narrowed run measured
    everything the method has, so it is keyed on the method and a later one is its next version.
    """
    ids = [r.variant.candidate.id for r in rep.rows] if narrowed else None
    return journal_docs.doc_key(DOC_PREFIX, rep.method_id, ids)


def journal(
    conn: sqlite3.Connection,
    rep: MethodReport,
    *,
    narrowed: bool = False,
    supersede: bool = True,
) -> tuple[int, int | None]:
    """One ``observation`` on the method, as the newest version of its gate document.

    The caller owns the transaction. Returns ``(insight id, the id it supersedes or None)``.
    ``narrowed`` must be True whenever the run was restricted by ``--only`` or ``--gated-only``.
    ``supersede=False`` writes a sibling instead (``--no-supersede``).
    """
    title, body = insight_text(rep)
    return journal_docs.append(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id,
        key=doc_key(rep, narrowed=narrowed), supersede=supersede,
    )
```

**Impact:** return type change; call sites `commands/lab.py:3034` (Step 6) and
`engine/tests/test_lab_gate_probe.py:668` (Step 9).

---

### Step 5: `exposure` — narrowed by `--only`

**File:** `engine/src/seer_engine/lab/exposure.py:91` (import) and `:1097` (the function)

At `exposure.py:91`, replace:

```python
from seer_engine.lab import hardgate, runner, store
```

with:

```python
from seer_engine.lab import hardgate, journal_docs, runner, store
```

Then replace the whole of `journal` (`exposure.py:1097-1102`):

```python
def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id
    )
```

with:

```python
#: The command half of this writer's document keys. See ``lab/journal_docs.py``.
DOC_PREFIX = "exposure"


def doc_key(rep: MethodReport, *, narrowed: bool = False) -> str:
    """The document this report is a version of.

    ``narrowed`` is True when ``--only`` restricted the run to particular recorded variants. A
    narrowed run is keyed on the arms it kept, so a later narrowed run about different arms stands
    beside it rather than burying it; an un-narrowed run measured every recorded variant and is
    keyed on the method, so a later one is its next version.
    """
    ids = [r.variant.candidate.id for r in rep.rows] if narrowed else None
    return journal_docs.doc_key(DOC_PREFIX, rep.method_id, ids)


def journal(
    conn: sqlite3.Connection,
    rep: MethodReport,
    *,
    narrowed: bool = False,
    supersede: bool = True,
) -> tuple[int, int | None]:
    """One ``observation`` on the method, as the newest version of its exposure document.

    The caller owns the transaction. Returns ``(insight id, the id it supersedes or None)``.
    ``narrowed`` must be True whenever ``--only`` restricted the run. ``supersede=False`` writes a
    sibling instead (``--no-supersede``).
    """
    title, body = insight_text(rep)
    return journal_docs.append(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id,
        key=doc_key(rep, narrowed=narrowed), supersede=supersede,
    )
```

**Impact:** return type change; call sites `commands/lab.py:2957` (Step 6) and
`engine/tests/test_lab_exposure.py:483` (Step 9).

---

### Step 6: the four commands — `--no-supersede`, and a line that says what happened

**File:** `engine/src/seer_engine/commands/lab.py`

Six edits. Note that `help=` strings are `%`-interpolated by argparse — none of the strings below
contains a literal `%`, so nothing needs escaping, but keep it that way.

**6a. `lab costs` parser** — `commands/lab.py:338`, after the `--store` argument of the `costs`
parser (the block that ends `"a test-window store is refused"`), add:

```python
    s.add_argument("--no-supersede", action="store_true",
                   help="write the observation as a new entry beside the previous one for this "
                        "variant instead of as its next version; for a genuinely new reading that "
                        "happens to be about the same thing")
```

**6b. `lab survivorship` parser** — `commands/lab.py:568`, immediately after the `--no-journal`
argument, add:

```python
    s.add_argument("--no-supersede", action="store_true",
                   help="write each observation as a new entry beside the previous one for this "
                        "method instead of as its next version")
```

**6c. `lab exposure` parser** — `commands/lab.py:631`, immediately after the `--no-journal`
argument, add the identical three lines as 6b.

**6d. `lab gate` parser** — `commands/lab.py:688`, immediately after the `--no-journal` argument,
add the identical three lines as 6b.

**6e. the four usage lines in the top help block.** At `commands/lab.py:55`, replace:

```
    lab costs M0007 [--candidate M0007-N20-RAW] [--store DIR]
```

with:

```
    lab costs M0007 [--candidate M0007-N20-RAW] [--store DIR] [--no-supersede]
```

At `commands/lab.py:87`, replace:

```
    lab survivorship M0069 [M0007 ...] [--store DIR] [--sv-store DIR] [--csv PATH] [--no-journal]
```

with:

```
    lab survivorship M0069 [M0007 ...] [--store DIR] [--sv-store DIR] [--csv PATH]
                     [--no-journal] [--no-supersede]
```

At `commands/lab.py:93`, replace:

```
    lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]
```

with:

```
    lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]
                 [--no-supersede]
```

At `commands/lab.py:100-101`, replace:

```
    lab gate [M0030 ...] [--all] [--only IDS] [--store DIR] [--csv PATH] [--gated-only]
             [--no-journal] [--dry-run]
```

with:

```
    lab gate [M0030 ...] [--all] [--only IDS] [--store DIR] [--csv PATH] [--gated-only]
             [--no-journal] [--no-supersede] [--dry-run]
```

**6f. the four handler blocks.**

In `_costs` (`commands/lab.py:2270`), change the import line:

```python
    from seer_engine.lab import real_costs, runner
```

to:

```python
    from seer_engine.lab import journal_docs, real_costs, runner
```

and replace `commands/lab.py:2303-2310`:

```python
    with conn:
        entry = real_costs.journal(conn, cmp)
    print(
        f"\njournal entry #{entry} written (an observation on {method.id}). Lab N (dev trials): "
        f"{n_before} before, {store.dev_trial_count(conn)} after; test-window looks used: "
        f"{looks_before} before, {store.test_looks(conn)} after."
    )
```

with:

```python
    with conn:
        entry, revised = real_costs.journal(conn, cmp, supersede=not args.no_supersede)
    print(
        f"\njournal entry {journal_docs.entry_label(entry, revised)} written (an observation on "
        f"{method.id}). Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after."
    )
```

In `_survivorship` (`commands/lab.py:2733`), replace `commands/lab.py:2769-2774`:

```python
        with conn:
            entries = [svc.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
```

with:

```python
        from seer_engine.lab import journal_docs

        with conn:
            written = [
                svc.journal(conn, rep, supersede=not args.no_supersede) for rep in reports
            ]
        labels = ", ".join(journal_docs.entry_label(n, prev) for n, prev in written)
        tail = (
            f"journal entries {labels} written (one observation per method). Solo: "
            f"`python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
```

In `_exposure` (`commands/lab.py:2922`), replace `commands/lab.py:2956-2961` with the same block,
substituting `exp` for `svc` and passing `narrowed`:

```python
        from seer_engine.lab import journal_docs

        with conn:
            written = [
                exp.journal(
                    conn, rep,
                    narrowed=args.only is not None,
                    supersede=not args.no_supersede,
                )
                for rep in reports
            ]
        labels = ", ".join(journal_docs.entry_label(n, prev) for n, prev in written)
        tail = (
            f"journal entries {labels} written (one observation per method). Solo: "
            f"`python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
```

In `_gate` (`commands/lab.py:2971`), replace `commands/lab.py:3033-3038` with the same block,
substituting `gp` for `exp`, and setting `narrowed` from **both** narrowing flags:

```python
        from seer_engine.lab import journal_docs

        # Both flags narrow which recorded variants were measured: --only names them and
        # --gated-only drops the ones with no gate site (gate_probe.plan_methods). A narrowed run
        # must not supersede an un-narrowed one -- it did not measure the same book.
        narrowed = args.only is not None or bool(args.gated_only)
        with conn:
            written = [
                gp.journal(
                    conn, rep, narrowed=narrowed, supersede=not args.no_supersede
                )
                for rep in reports
            ]
        labels = ", ".join(journal_docs.entry_label(n, prev) for n, prev in written)
        tail = (
            f"journal entries {labels} written (one observation per method). Solo: "
            f"`python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
```

**Impact:** the owner's confirmation line now reads
`journal entry #471 (revises #468) written` on a re-run. `--no-journal` still short-circuits
before any of this, unchanged. `lab costs` gains `--no-supersede` but still has no `--no-journal`
(unchanged behaviour).

---

### Step 7: `prereg` — a key, and no flag

**File:** `engine/src/seer_engine/lab/prereg.py:731`

**Change:** give the pre-registration row a `doc_key` so phases 4-6 can group it, and route it
through `journal_docs.append` so the one definition applies here too.

**No `--no-supersede` on `lab promote`**, and that is deliberate rather than an omission: the call
sits inside `if recorded is None:` (`prereg.py:730`), and `recorded` is read back from the
method's own analysis, which this same block writes. A second pre-registration row for one method
is therefore unreachable, the head lookup always returns `None`, and a flag that can never change
an outcome is dead UI. The `append` call is still used rather than a bare `add_insight` so the
guarantee holds by construction if that guard is ever relaxed.

First, add the import. `prereg.py` already imports `store` from the lab package; add
`journal_docs` to that import (the exact line reads `from seer_engine.lab import store` or lists
siblings — add `journal_docs` alphabetically into whichever form is present).

Then, near the other module constants at the top of `prereg.py`, add:

```python
#: The command half of this writer's document keys. See ``lab/journal_docs.py``.
DOC_PREFIX = "prereg"
```

Then replace `prereg.py:730-743` — the whole `store.add_insight(...)` call, leaving the
`if recorded is None:` guard and the `store.append_analysis` call above it untouched:

```python
            # The journal note is read by the owner, not an auditor: plain words, no digests.
            store.add_insight(
                conn,
                kind="observation",
                title=f"{row['name']} is pre-registered for its one test-window look",
                body=(
                    f"Sera picked {p.candidate} -- this method's best variant on the practice "
                    f"years -- and wrote down, before looking, exactly what it will test. The "
                    f"note is {repo_path(path)} and it goes into git before the test runs. The "
                    f"unseen years can be looked at once per setup, so writing the choice down "
                    f"first is what stops a disappointing answer from quietly becoming a "
                    f"different question."
                ),
                method_id=method_id,
            )
```

with:

```python
            # The journal note is read by the owner, not an auditor: plain words, no digests.
            #
            # Keyed on the method, not on the chosen variant: a pre-registration is written once
            # per method and never rewritten (design §3), and the guard above makes a second row
            # for this key unreachable. The key is still carried so the reader can group it, and
            # the write still goes through `journal_docs.append` so that if the guard is ever
            # relaxed a second note becomes version 2 rather than a second card.
            journal_docs.append(
                conn,
                kind="observation",
                title=f"{row['name']} is pre-registered for its one test-window look",
                body=(
                    f"Sera picked {p.candidate} -- this method's best variant on the practice "
                    f"years -- and wrote down, before looking, exactly what it will test. The "
                    f"note is {repo_path(path)} and it goes into git before the test runs. The "
                    f"unseen years can be looked at once per setup, so writing the choice down "
                    f"first is what stops a disappointing answer from quietly becoming a "
                    f"different question."
                ),
                method_id=method_id,
                key=journal_docs.doc_key(DOC_PREFIX, method_id),
            )
```

**Impact:** the row's text is byte-identical to what it is today; only `doc_key` is new. The
return value was discarded before and still is.

---

### Step 8: the regression suite — `test_lab_journal_docs.py`

**File:** `engine/tests/test_lab_journal_docs.py` (new file)

**Change:** This is the phase's reason to exist. The M0260 replay needs no research store and no
backtest: `real_costs.Comparison` and `real_costs.Side` are plain frozen dataclasses, as
`test_lab_costs.py:216-243` already demonstrates. The three arms carry **the measured drawdowns
and profit factors from trials n=835/838/836**, so the test documents the incident as well as
guarding it.

**Code:**

```python
"""Journal documents: what a `doc_key` is, and the M0260 incident that defines it.

The headline test here is `test_m0260s_three_arms_stay_three_documents`. Insights 466, 467 and 468
in the committed lab share one generated title, were written 25 and 30 seconds apart, and are NOT
duplicates: they are M0260-M-NATIVE, M0260-M-G12 and M0260-M-G3, matched to trials n=835, 838 and
836 by their recorded max drawdown and profit factor. An auto-linker keyed on the method or on the
title would have buried a 23.8% drawdown underneath a 33.6% one and shown the owner only the last.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from seer_engine.lab import journal_docs, real_costs, store
from seer_engine.lab.seed import seed


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    conn.execute(
        "INSERT INTO methods (id, name, family, source_kind, source_ref, hypothesis, "
        "expected_failure, status, added) VALUES "
        "('M0001', 'a method', 'trend', 'knowledge', '', 'h', 'f', 'idea', '2026-10-20')"
    )
    conn.commit()
    yield conn
    conn.close()


def _write(conn, key, body="a body", *, supersede=True, method_id="M0001"):
    with conn:
        return journal_docs.append(
            conn, kind="observation", title="a title", body=body,
            method_id=method_id, key=key, supersede=supersede,
        )


def _row(conn, insight_id):
    return conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()


# ---- the key ------------------------------------------------------------------------------


def test_an_unnarrowed_run_is_keyed_on_the_method():
    assert journal_docs.doc_key("gate", "M0260") == "gate:M0260:all"


def test_a_narrowed_run_is_keyed_on_the_arms_it_measured():
    assert journal_docs.doc_key("gate", "M0260", ["M0260-M-G3"]) == "gate:M0260:M0260-M-G3"


def test_the_arm_list_is_sorted_and_deduplicated_so_order_is_not_identity():
    a = journal_docs.doc_key("exposure", "M0260", ["M0260-B", "M0260-A"])
    b = journal_docs.doc_key("exposure", "M0260", ["M0260-A", "M0260-B", "M0260-A"])
    assert a == b == "exposure:M0260:M0260-A+M0260-B"


def test_a_narrowed_run_with_no_arms_is_a_refusal_not_a_method_wide_key():
    with pytest.raises(store.LabError, match="at least one candidate id"):
        journal_docs.doc_key("gate", "M0260", [])


def test_two_commands_never_collide_on_one_method():
    assert journal_docs.doc_key("gate", "M0007") != journal_docs.doc_key("exposure", "M0007")


# ---- the head -----------------------------------------------------------------------------


def test_a_document_with_no_rows_has_no_head(lab):
    assert journal_docs.head_for(lab, "gate:M0001:all", method_id="M0001") is None


def test_the_head_is_the_row_nothing_supersedes(lab):
    first, _ = _write(lab, "gate:M0001:all", "one")
    assert journal_docs.head_for(lab, "gate:M0001:all", method_id="M0001") == first
    second, revised = _write(lab, "gate:M0001:all", "two")
    assert revised == first
    assert journal_docs.head_for(lab, "gate:M0001:all", method_id="M0001") == second


def test_a_row_written_before_schema_8_can_never_be_superseded_by_a_writer(lab):
    """The 500 historical rows carry doc_key NULL, and `doc_key = ?` never matches NULL."""
    with lab:
        old = store.add_insight(
            lab, kind="observation", title="a title", body="an old body", method_id="M0001",
        )
    assert _row(lab, old)["doc_key"] is None
    new_id, revised = _write(lab, "gate:M0001:all", "a new body")
    assert revised is None
    assert new_id != old
    assert _row(lab, old)["supersedes"] is None


# ---- the chain ----------------------------------------------------------------------------


def test_rerunning_the_same_subject_makes_one_document_at_version_two(lab):
    first, none_yet = _write(lab, "real-costs:M0001:M0001-A", "the first reading")
    second, revised = _write(lab, "real-costs:M0001:M0001-A", "the second reading")
    assert none_yet is None and revised == first
    before, after = _row(lab, first), _row(lab, second)
    # The predecessor is still there, and every byte of its content is untouched.
    assert before["body"] == "the first reading"
    assert before["supersedes"] is None and before["doc_key"] == "real-costs:M0001:M0001-A"
    assert after["supersedes"] == first
    heads = lab.execute(
        "SELECT count(*) FROM insights WHERE doc_key = ? AND id NOT IN "
        "(SELECT supersedes FROM insights WHERE supersedes IS NOT NULL)",
        ("real-costs:M0001:M0001-A",),
    ).fetchone()[0]
    assert heads == 1


def test_no_supersede_writes_a_sibling_and_leaves_the_head_alone(lab):
    first, _ = _write(lab, "real-costs:M0001:M0001-A", "the first reading")
    second, revised = _write(lab, "real-costs:M0001:M0001-A", "beside it", supersede=False)
    assert revised is None
    assert _row(lab, second)["supersedes"] is None
    assert _row(lab, first)["supersedes"] is None


def test_a_third_run_chains_onto_the_second_not_the_first(lab):
    first, _ = _write(lab, "gate:M0001:all", "one")
    second, _ = _write(lab, "gate:M0001:all", "two")
    third, revised = _write(lab, "gate:M0001:all", "three")
    assert revised == second
    assert [_row(lab, i)["supersedes"] for i in (first, second, third)] == [None, first, second]


def test_a_concurrent_link_to_the_same_head_chains_instead_of_forking(lab, monkeypatch):
    """`insights_one_successor` refuses the second link; `append` re-reads and chains on."""
    first, _ = _write(lab, "gate:M0001:all", "one")
    rival, _ = _write(lab, "gate:M0001:all", "a rival session got there first")
    assert _row(lab, rival)["supersedes"] == first

    # Force `append` to see the stale head exactly once, the way a racing session would.
    real_head = journal_docs.head_for
    seen = {"n": 0}

    def stale(conn, key, *, method_id):
        seen["n"] += 1
        return first if seen["n"] == 1 else real_head(conn, key, method_id=method_id)

    monkeypatch.setattr(journal_docs, "head_for", stale)
    mine, revised = _write(lab, "gate:M0001:all", "mine")
    assert revised == rival and _row(lab, mine)["supersedes"] == rival


def test_the_entry_label_says_what_happened_to_the_page():
    assert journal_docs.entry_label(471, None) == "#471"
    assert journal_docs.entry_label(471, 468) == "#471 (revises #468)"


# ---- the M0260 incident --------------------------------------------------------------------


def _side(model, candidate_id, dd, pf):
    return real_costs.Side(
        model=model, candidate_id=candidate_id, total_return=0.5, cagr=0.1, max_drawdown=dd,
        profit_factor=pf, trades=120, sharpe=0.8, mar=0.6, exposure=0.9, costs_usd=10.0,
        cost_drag=0.02, spy_tr_return=0.4, spy_tr_cagr=0.08, beats_spy=True, failed=(),
    )


def _comparison(candidate_id, dd, pf):
    """One `lab costs` reading of one arm, with the numbers the lab actually recorded."""
    return real_costs.Comparison(
        method_id="M0001", method_name="one method, three arms", candidate_id=candidate_id,
        recorded_model="flat", trial_n=1, recorded_total_return=0.5,
        start=date(1996, 1, 2), end=date(2015, 10, 16), fingerprint="smoke",
        flat=_side("flat", candidate_id, dd, pf),
        real=_side("gotrade", f"{candidate_id}-GT", dd, pf),
    )


#: The three arms of M0260 that insights 466, 467 and 468 really are, with the max drawdown and
#: profit factor each one reported, matched to trials n=835, 838 and 836.
M0260_ARMS = (
    ("M0001-M-NATIVE", 0.238, 1.98),
    ("M0001-M-G12", 0.256, 1.62),
    ("M0001-M-G3", 0.336, 1.60),
)


def test_m0260s_three_arms_stay_three_documents(lab):
    """The measured bug, replayed. Three arms, one generated title, three documents.

    Keyed on the method or on the title, the 23.8% arm would be buried under the 33.6% one and
    the owner would see only the last. That is a measurement vanishing off the page.
    """
    written = []
    for candidate_id, dd, pf in M0260_ARMS:
        cmp = _comparison(candidate_id, dd, pf)
        with lab:
            written.append(real_costs.journal(lab, cmp))

    ids = [i for i, _ in written]
    assert [prev for _, prev in written] == [None, None, None], "no arm may supersede another"
    rows = [_row(lab, i) for i in ids]
    assert len({r["doc_key"] for r in rows}) == 3
    assert [r["supersedes"] for r in rows] == [None, None, None]
    # One generated title across all three, which is exactly why the title is not the key.
    assert len({r["title"] for r in rows}) == 1
    # And all three are still readable as their own documents.
    heads = lab.execute(
        "SELECT count(*) FROM insights WHERE doc_key IS NOT NULL AND id NOT IN "
        "(SELECT supersedes FROM insights WHERE supersedes IS NOT NULL)"
    ).fetchone()[0]
    assert heads == 3


def test_rerunning_one_of_m0260s_arms_revises_only_that_arm(lab):
    """The mirror of the test above: the same arm twice is one document at version 2."""
    for candidate_id, dd, pf in M0260_ARMS:
        with lab:
            real_costs.journal(lab, _comparison(candidate_id, dd, pf))
    g3_first = lab.execute(
        "SELECT id FROM insights WHERE doc_key = ?", ("real-costs:M0001:M0001-M-G3",)
    ).fetchone()[0]

    with lab:
        again, revised = real_costs.journal(lab, _comparison("M0001-M-G3", 0.336, 1.60))

    assert revised == g3_first
    assert _row(lab, again)["supersedes"] == g3_first
    # The first reading is still there, byte for byte.
    assert _row(lab, g3_first)["body"] == real_costs.insight_text(
        _comparison("M0001-M-G3", 0.336, 1.60)
    )[1]
    # The other two arms were not touched.
    untouched = lab.execute(
        "SELECT count(*) FROM insights WHERE doc_key IN (?, ?) AND supersedes IS NOT NULL",
        ("real-costs:M0001:M0001-M-NATIVE", "real-costs:M0001:M0001-M-G12"),
    ).fetchone()[0]
    assert untouched == 0


def test_the_doc_key_is_the_arm_not_the_method(lab):
    cmp = _comparison("M0001-M-G3", 0.336, 1.60)
    assert real_costs.doc_key(cmp) == "real-costs:M0001:M0001-M-G3"
```

**Impact:** a new test module, no production behaviour. If `seed(conn)` already provides a method
row the `lab` fixture can use, drop the explicit INSERT; the fixture shape otherwise mirrors
`test_lab_costs.py:60-66`.

---

### Step 9: update the four existing journal tests for the tuple return

**Files:** `engine/tests/test_lab_costs.py:202`, `engine/tests/test_lab_survivorship.py:285`,
`engine/tests/test_lab_gate_probe.py:668`, `engine/tests/test_lab_exposure.py:483`

**Change:** each of those lines reads `entry = <module>.journal(conn, rep)`. Replace with
`entry, revised = <module>.journal(conn, rep)` and add `assert revised is None` — a first write of
a document supersedes nothing, and asserting it keeps the four modules honest about which case
they are testing. Every other assertion in those tests is about the title and body and stays
exactly as it is; this phase does not touch a single generated string.

In `test_lab_costs.py:200-204`, replace:

```python
    before = _untouched(conn)
    with conn:
        entry = real_costs.journal(conn, cmp)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
```

with:

```python
    before = _untouched(conn)
    with conn:
        entry, revised = real_costs.journal(conn, cmp)
    assert revised is None  # the first version of this arm's document supersedes nothing
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["doc_key"] == f"real-costs:M0001:{cmp.candidate_id}"
```

Apply the same two-line change in the other three (`svc.journal`, `gp.journal`, `exp.journal`),
with the `doc_key` assertion reading `"survivorship:M0001:all"`, `"gate:M0001:all"` and
`"exposure:M0001:all"` respectively — those three tests all call the un-narrowed `_measure`
helper.

**Impact:** four one-line signature updates plus four new assertions.

---

### Step 10: the per-command behaviour tests

**Files:** `test_lab_costs.py`, `test_lab_survivorship.py`, `test_lab_gate_probe.py`,
`test_lab_exposure.py`, `test_lab_prereg.py`

**10a. `test_lab_costs.py`** — append after the existing journal tests:

```python
def test_a_second_run_of_the_same_arm_revises_rather_than_repeats(lab, data, recorded):
    conn, _ = lab
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    kw = dict(
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
        initial_idr=runner.recorded_capital(conn, int(trial["n"])),
    )
    cmp = real_costs.measure(recorded, c, trial, data, **kw)
    with conn:
        first, _ = real_costs.journal(conn, cmp)
    with conn:
        second, revised = real_costs.journal(conn, cmp)
    assert revised == first
    rows = conn.execute(
        "SELECT id, supersedes FROM insights WHERE doc_key = ? ORDER BY id", (real_costs.doc_key(cmp),)
    ).fetchall()
    assert [tuple(r) for r in rows] == [(first, None), (second, first)]


def test_a_different_arm_of_the_same_method_is_a_sibling_not_a_version(lab, data, recorded):
    conn, _ = lab
    kw_for = lambda t: dict(  # noqa: E731
        contributions=runner.recorded_contributions(conn, int(t["n"])),
        initial_idr=runner.recorded_capital(conn, int(t["n"])),
    )
    a, ta = real_costs.pick_candidate(conn, recorded, "M0001-A")
    b, tb = real_costs.pick_candidate(conn, recorded, "M0001-B")
    with conn:
        first, _ = real_costs.journal(conn, real_costs.measure(recorded, a, ta, data, **kw_for(ta)))
    with conn:
        second, revised = real_costs.journal(
            conn, real_costs.measure(recorded, b, tb, data, **kw_for(tb))
        )
    assert revised is None, "two arms are two measurements and must be two documents"
    rows = conn.execute("SELECT id, title, doc_key FROM insights ORDER BY id").fetchall()
    rows = [r for r in rows if r["id"] in (first, second)]
    assert rows[0]["title"] == rows[1]["title"], "the generated title is the same for both"
    assert rows[0]["doc_key"] != rows[1]["doc_key"], "and that is why the title is not the key"


def test_cli_no_supersede_writes_a_sibling(lab, data, recorded, monkeypatch, capsys, tmp_path):
    conn, path = lab
    monkeypatch.setattr(research, "load_store", lambda *a, **k: data)
    monkeypatch.setattr(real_costs, "discover", lambda: {"M0001": (recorded, HERE)})
    argv = ["lab", "--db", str(path), "costs", "M0001", "--store", str(tmp_path / "store")]
    assert cli.main(argv) == 0
    assert cli.main(argv) == 0
    assert "revises #" in capsys.readouterr().out
    assert cli.main([*argv, "--no-supersede"]) == 0
    out = capsys.readouterr().out
    assert "revises #" not in out
    assert conn.execute(
        "SELECT count(*) FROM insights WHERE supersedes IS NULL AND doc_key IS NOT NULL"
    ).fetchone()[0] == 2


def test_the_costs_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "costs", "--help"])
    assert e.value.code == 0
    assert "--no-supersede" in capsys.readouterr().out
```

**10b. `test_lab_survivorship.py`** — append:

```python
def test_a_second_run_revises_the_same_document(lab, dev_data, sv_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), *_ = _measure(conn, dev_data, sv_data, tmp_path, monkeypatch)
    with conn:
        first, _ = svc.journal(conn, rep)
    with conn:
        second, revised = svc.journal(conn, rep)
    assert revised == first
    assert svc.doc_key(rep) == "survivorship:M0001:all"
    with conn:
        third, nothing = svc.journal(conn, rep, supersede=False)
    assert nothing is None
    assert conn.execute(
        "SELECT supersedes FROM insights WHERE id = ?", (third,)
    ).fetchone()[0] is None
    assert second != third


def test_survivorship_cannot_be_narrowed_so_its_key_may_stay_method_wide(capsys):
    """If `lab survivorship` ever gains --only, `svc.doc_key` must gain the narrowed branch the
    other writers have, or a narrowed run would bury an un-narrowed one. This is that alarm."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "survivorship", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--only" not in out, "survivorship gained --only: give svc.doc_key the narrowed branch"
    assert "--no-supersede" in out
```

**10c. `test_lab_gate_probe.py`** — append:

```python
def test_a_narrowed_run_is_a_sibling_of_an_unnarrowed_one(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    with conn:
        wide, _ = gp.journal(conn, rep)
    with conn:
        narrow, revised = gp.journal(conn, rep, narrowed=True)
    assert revised is None, "a narrowed run did not measure the same book as a wide one"
    assert gp.doc_key(rep) == "gate:M0001:all"
    assert gp.doc_key(rep, narrowed=True).startswith("gate:M0001:M0001-")
    assert conn.execute(
        "SELECT supersedes FROM insights WHERE id = ?", (narrow,)
    ).fetchone()[0] is None
    with conn:
        again, revised_again = gp.journal(conn, rep)
    assert revised_again == wide


def test_the_gate_help_strings_still_format_with_no_supersede(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "gate", "--help"])
    assert e.value.code == 0
    assert "--no-supersede" in capsys.readouterr().out
```

**10d. `test_lab_exposure.py`** — append the same pair, substituting `exp` for `gp`,
`"exposure:M0001:all"` for the wide key, and `["lab", "exposure", "--help"]`.

**10e. `test_lab_prereg.py`** — in whichever test asserts the pre-registration journal row today,
add:

```python
    assert row["doc_key"] == "prereg:M0001:all"
    assert row["supersedes"] is None
```

(substituting the method id that test uses). If no test reads that row today, add:

```python
def test_the_prereg_note_carries_its_document_key(...):
    """One pre-registration per method is correct, so the key is the method and nothing else."""
    row = conn.execute(
        "SELECT * FROM insights WHERE title LIKE ? ORDER BY id DESC LIMIT 1",
        ("%is pre-registered for its one test-window look",),
    ).fetchone()
    assert row["doc_key"] == f"prereg:{method_id}:all"
    assert row["supersedes"] is None
```

**Impact:** no production code. These are the tests that make the contract observable.

---

## Verification

Run from the worktree root. There is no venv in this worktree, so use the main checkout's and set
`PYTHONPATH` — without it pytest silently tests `/home/miftah/seer` instead of this branch.

**Lint:**

```bash
cd /home/miftah/.worktrees/seer/journal-versioning && \
  /home/miftah/seer/engine/.venv/bin/ruff check engine
```

**Tests (the phase's own, first):**

```bash
cd /home/miftah/.worktrees/seer/journal-versioning && \
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_journal_docs.py engine/tests/test_lab_costs.py \
  engine/tests/test_lab_survivorship.py engine/tests/test_lab_gate_probe.py \
  engine/tests/test_lab_exposure.py engine/tests/test_lab_prereg.py -q -n auto
```

**Tests (the whole suite):**

```bash
cd /home/miftah/.worktrees/seer/journal-versioning && \
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q -n auto
```

`test_lab_snapshot.py` must be green without running `lab stage`: this phase writes no lab data.
If it is red, something in this phase touched `lab.sqlite` — find it, because that is phase 1's
and phase 6's ground, not this one's.

**Manual check:** `lab --help`, `lab costs --help`, `lab survivorship --help`, `lab exposure
--help` and `lab gate --help` all format (argparse `%`-interpolates `help=`), and each of the four
lists `--no-supersede`. The help-string tests above cover this, but run `lab --help` once by hand
because the top-level usage block is hand-wrapped text with no test.

**Budgets, checked before the phase is called done:**

```bash
cd /home/miftah/.worktrees/seer/journal-versioning && \
  PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab status | \
  grep -i "test-window looks"
```

must still read **4**. No `lab test`, no `lab promote`, no `lab next-id`, no method id spent.

**Exit criteria:**

1. Replaying M0260's three arms through `real_costs.journal` produces **three documents with
   three distinct `doc_key`s and no `supersedes` link between them** — one generated title, three
   measurements, three cards.
2. Re-running the **same** arm produces **one document at version 2**: two rows, the second
   pointing at the first, the first still present with its `body`, `title`, `kind`, `method_id`
   and `added` unchanged.
3. All five writers set `doc_key` on every row they write; none of them changes one byte of a
   generated title or body.
4. `--no-supersede` writes a sibling on `lab costs`, `lab survivorship`, `lab exposure` and
   `lab gate`.
5. `ruff check engine` clean and `pytest engine/tests` green, with `lab.sqlite` and
   `web/data/lab.json` untouched by this phase.
6. `git status` shows no modification to `store.py`, `hardgate.py`, any `web/` file, or
   `lab/lab.sqlite`.

---

## Handoffs

- **R1 (phases 4 and 5).** `doc_key` and `supersedes` are now written but nothing exports or
  renders them. The owner still sees one card per row until phase 4 emits `docKey`/`version` and
  phase 5 renders heads with a version chip. **This phase deliberately ships no user-visible
  change beyond the one confirmation line** (`#471 (revises #468)`), because rendering is R1 and
  R1 is not mine.
- **R3 (phase 6).** The 500 historical rows keep `doc_key IS NULL` and `head_for` can never match
  them, so this phase cannot and does not thread any existing duplicate. The five byte-identical
  pairs are phase 6's, through `lab link`.
- **Phase 4 should count heads, not rows.** `summary.insights` counting rows is R5's problem, and
  the SQL that finds heads is in `journal_docs.head_for`'s docstring if phase 4 wants the same
  shape: `id NOT IN (SELECT supersedes FROM insights WHERE supersedes IS NOT NULL)`.
- **For the reconciler, if it prefers the brief's "put the lookup in the store".** Move
  `head_for` and `append` from `lab/journal_docs.py` into `store.py` and have
  `store.add_insight(doc_key=...)` do the lookup itself. The five call sites keep their shape;
  only the import changes. I did not do it because `store.py` is phase 1's file and this phase may
  not edit it.
- **Not done, deliberately, and not mine:** `real_costs.insight_text` could put the arm in the
  title, which would make the M0260 trio legible to a human reading the committed journal. That
  would make rows written before and after this phase disagree, which invariant 2 forbids. If the
  owner wants it, it is a separate decision about new rows only.
- **`lab remeasure`'s `--only` (`commands/lab.py:2214`) is unrelated** — it narrows a re-measure,
  not a journal write, and that command does not journal. Left alone.

## Rollback

`git revert` the single commit. Nothing in this phase writes to `lab/lab.sqlite`,
`web/data/lab.json`, or any committed record, so a revert restores the tree exactly: the writers
go back to `store.add_insight` with no `doc_key`, `journal_docs.py` and
`test_lab_journal_docs.py` disappear, and the four `--no-supersede` flags with them. Rows written
by this phase before a revert keep a `doc_key` the reverted code ignores and a `supersedes` link
the reverted exporter does not emit — harmless, and invisible until phase 4 lands. Phase 1's
schema 8 stays; it is the one-way door, and it is not this phase's.
