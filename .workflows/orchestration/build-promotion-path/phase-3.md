# Phase 3: Pre-registration: `lab promote` and `docs/lab/prereg/`

**Plan set:** `BUILD_PROMOTION_PATH_PLAN.md`
**Analysis:** `20261006-115723-B7K2_code_analyzer.md`
**Satisfies:** R3 — the best dev-eligible variant by MAR is pre-registered in
`docs/lab/prereg/MNNNN.md`, with id, candidate id, `config_digest`, gate, window and date,
written and committed before any test number exists.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase a dev-eligible method can be pre-registered: `python -m seer_engine lab promote
M0007` picks that method's single best eligible dev trial by MAR, writes
`docs/lab/prereg/M0007.md` pinning the exact `config_digest` that trial recorded, and moves the
method `dev-eligible → promoted` in the same transaction. The file is the lab's
anti-self-deception device — it is written once and never rewritten, so the configuration the
look is spent on is the configuration that was measured.

Phase 4 gets one function to call, `prereg.require_committed(candidate_id)`, which returns the
parsed pre-registration or raises `prereg.PreregError` (a `store.LabError`, so the existing `lab`
CLI already turns it into exit 2). No trial row is written here, no research store is loaded, and
`test-window looks used` stays 0.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates (new module `engine/src/seer_engine/lab/prereg.py`):**
- `lab.prereg.PREREG_DIR` — `config.REPO_ROOT / "docs" / "lab" / "prereg"`
- `lab.prereg.MARKER` — `"Pre-registered for the test window as "` (the analysis idempotence key)
- `lab.prereg.FIELDS` — the front-matter keys, in file order
- `lab.prereg.PreregError(store.LabError)`
- `lab.prereg.Prereg` — frozen dataclass, **every field `str`**
- `lab.prereg.Promotion` — frozen dataclass `(prereg, path, trial_n, status, wrote_file, moved_status)`
- `lab.prereg.repo_path(path) -> str`
- `lab.prereg.path_for(method_id, directory=None) -> Path`
- `lab.prereg.method_of(candidate_id) -> str`
- `lab.prereg.gate_text() -> str`
- `lab.prereg.test_window_label() -> str`
- `lab.prereg.render(p, name) -> str`
- `lab.prereg.parse(text) -> Prereg`
- `lab.prereg.committed_problem(path) -> str | None`
- **`lab.prereg.require_committed(candidate_id, *, directory=None) -> Prereg`** — the phase-4 gate
- **`lab.prereg.check_digest(p, digest, *, directory=None) -> None`** — the phase-4 digest match
- `lab.prereg.check_source(method_id, row, trial) -> Path`
- `lab.prereg.promote_method(conn, method_id, *, git_sha, today=None, directory=None, check_method_file=True) -> Promotion`

**Creates (in `engine/src/seer_engine/lab/store.py`):**
- `lab.store.best_dev_eligible(conn, method_id) -> sqlite3.Row | None` (`store.py`, after `trials_of`)

**Creates (committed docs):**
- `docs/lab/prereg/README.md` — the format, and the only reason the directory exists in git today
- `docs/lab/prereg/MNNNN.md` — written by `lab promote` at run time, not by this phase

**Creates (CLI):**
- `lab promote <method> [--dir DIR]` subparser and `_promote` handler in `commands/lab.py`
- `_HANDLERS["promote"]`

**Deletes:** none
**Renames:** none
**Signature changes:** none

**Requires (from earlier phases):** nothing. Phases 1 and 2 share no edge with this one.

**Shared file, flagged for the reconciler:** `engine/src/seer_engine/commands/lab.py`. Phase 4
adds its `test` subcommand to the same three regions (the subparser block after the `run`
parser, the handler block after `_run`, and `_HANDLERS`). **This phase is the earlier owner and
lands first** — phase 4 depends on phase 3 — so this phase's anchors are the ones against the
tree at `2d03fd1`, and phase 4's plan has been edited to quote the post-phase-3 state: the
`promote` subparser already present, `_promote` already sitting between `_run` and `_idea`, and
`_HANDLERS` already carrying `"promote": _promote,`. Nothing in this phase changes.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/backtest/dev.py` (Phase 1) — read only, for `FAILURE_LABELS` and `DEV_END`
- `engine/src/seer_engine/research.py`, `commands/research_store.py`, `.gitignore` (Phase 2)
- `engine/src/seer_engine/lab/runner.py` (Phase 4) — read only, for `git_head`
- `lab.store.record_promotion` (`store.py:395`) — the **paper roster** step, already built.
  `lab promote` (dev-eligible → promoted) and `record_promotion` (test-passed → paper) are two
  different transitions; this phase touches neither the second one nor `commands/promote.py`.
- `lab/lab.sqlite`, `web/data/lab.json` — not committed by this phase
- `.claude/skills/explore-and-experiment-new-method/SKILL.md` — see **Handoffs**

**Interface for Phase 4, exactly:**

| Thing | Value |
|---|---|
| File path pattern | `docs/lab/prereg/<METHOD_ID>.md`, e.g. `docs/lab/prereg/M0007.md`; `prereg.path_for("M0007")` |
| Parsed value | `prereg.Prereg` — fields `method`, `candidate`, `config_digest`, `rules_id`, `allocator_id`, `dev_trial`, `dev_window`, `test_window`, `gate`, `mar`, `dsr`, `n_trials_at_run`, `store_fingerprint`, `git_sha`, `date`. **All `str`.** |
| "a committed prereg exists" | `prereg.require_committed(candidate_id) -> Prereg` |
| What it raises | `prereg.PreregError`, a subclass of `lab.store.LabError` → `commands/lab.py:run` already returns exit 2 |
| When it raises | not a `MNNNN-SUFFIX` candidate id; file missing; file untracked / staged-not-committed / modified; file does not parse; file names another method; file names another candidate |
| Digest match | `prereg.check_digest(p, config_digest(candidate))` — raises `PreregError` when the live configuration drifted from the pre-registered one |
| Window the file records | `test_window` = `"2015-10-19..data end"` (from `dates.next_session(dev.DEV_END)`); see **Assumptions** |
| The file's path | `prereg.path_for(p.method)` — `Prereg` has **no** `.path` field |
| The candidate field | `p.candidate` — **not** `p.candidate_id` |
| What `require_committed` already checks | the method/candidate identity *and* the git state. A caller must not re-check either; it must **not** pass a `require_commit=` flag, because there is none |
| Re-checking inside a transaction | re-use the `Prereg` already returned; `check_digest(p, digest)` is pure and cheap to repeat, `require_committed` shells out to git and should be called once |

**Reconciled 2026-10-06.** Phase 4 was written against an assumed
`prereg.read_committed(method_id, *, require_commit=True)` returning `.candidate_id` /
`.config_digest` / `.path`. That name does not exist and will not: this phase owns the module,
and phase 4's plan has been edited to call `require_committed(candidate.id)` +
`check_digest(p, config_digest(candidate))` and to read `p.candidate` / `path_for(p.method)`.
Nothing in this phase changed to accommodate it.

## Assumptions

1. **Phases 1 and 2 have not landed, and do not need to have.** Nothing in this phase imports a
   window value object. The only window fact it needs is the test window's *start*, which is
   already a published constant-of-constants: `dates.next_session(dev.DEV_END)` — the exact
   expression `lab.store.snapshot` already uses at `store.py:815` for `gate.testStart`.
2. **The test window's end is unknowable at pre-registration time** (plan Decisions D3: "latest
   available at build time, recorded in the manifest"). The file therefore records
   `test_window: 2015-10-19..data end`, and the exact end is pinned afterwards by the `trials`
   row `lab test` writes. If phase 1 or 2 introduces a named window value, the reconciler should
   repoint the one-line body of `prereg.test_window_label()` at it and nothing else.
3. **The real lab database has no dev-eligible method today** (verified: 8 `idea`, 20 `rejected`,
   0 test looks). Every test below builds its own temp database with `store.connect(tmp_path /
   "lab.sqlite")`, the fixture style of `engine/tests/test_lab_store.py:18`.
4. `docs/lab/` does not exist yet (verified: `git ls-files docs/lab` is empty). This phase
   creates `docs/lab/prereg/README.md`, which is also what makes the directory exist in git.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/prereg.py` | create | the whole pre-registration format, its writer, its parser and the committed-file gate |
| `engine/src/seer_engine/lab/store.py` | modify | add `best_dev_eligible` after `trials_of` (`store.py:568-569`) |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring line (`:9`), `promote` subparser (after `:78`), `_promote` handler (after `:262`), `_HANDLERS` (`:375`) |
| `docs/lab/prereg/README.md` | create | the committed description of the format |
| `engine/tests/test_lab_prereg.py` | create | 19 tests, including the digest-equality proof |
| `engine/tests/test_lab_store.py` | modify | one added test for `best_dev_eligible` |

---

## Implementation Steps

### Step 1: `store.best_dev_eligible` — one variant per method, deterministically

**File:** `engine/src/seer_engine/lab/store.py:568` — insert immediately after `trials_of`
(which ends at `:569`) and before the `# ---- ideas_seen` divider at `:572`.

**Change:** the selection query design §3 names. It belongs in `store.py` because that module's
contract is "Every lab read and write goes through this module" (`store.py:3-4`).

**Code:**

```python
def best_dev_eligible(conn: sqlite3.Connection, method_id: str) -> sqlite3.Row | None:
    """The method's best eligible dev trial by MAR -- the one variant design §3 pre-registers.

    Highest MAR wins and a tie breaks on the trial number, so the answer is exactly one row and
    the same row every time: "one per method" is a property of this query, not of the caller.

    Only ``window = 'dev'`` is considered. A test trial is the out-of-sample check on a
    configuration this query already chose, so letting one back in here would let a test number
    decide what gets tested. A trial with no MAR is never the answer either -- an eligible trial
    always has one, because ``beats SPY TR`` is among the conditions it passed, so a NULL here
    means a row that cannot be compared rather than a row that compares badly.

    None when the method has no eligible dev trial at all.
    """
    return conn.execute(
        "SELECT * FROM trials WHERE method_id = ? AND window = 'dev' AND eligible = 1 "
        "AND mar IS NOT NULL ORDER BY mar DESC, n ASC LIMIT 1",
        (method_id,),
    ).fetchone()
```

**Impact:** pure addition; no existing caller, no schema change, no query plan any other code
depends on.

---

### Step 2: the pre-registration module

**File:** `engine/src/seer_engine/lab/prereg.py` — new file.

**Change:** the whole format, its writer, its parser, the committed-file gate and the
`dev-eligible → promoted` transition. Written as one module because the three honesty facts
(the digest is copied not recomputed; the live file still produces it; the file is in git) are
one property and splitting them across modules would let one be dropped quietly.

**Code:**

```python
"""Pre-registration: the file that pins what ``lab test`` is allowed to look at (design §3).

    The best dev-eligible variant by MAR (one per method) is pre-registered in
    ``docs/lab/prereg/MNNNN.md``, committed and pushed before any test number exists.

The lab gets **one** look at the test window per configuration, and the database already
enforces that much: ``UNIQUE(config_digest, window)`` plus the append-only triggers
(``lab.store``). What a database cannot enforce is *which* configuration the look is spent on.
Nothing in SQLite stops a promotion that pre-registers one variant and a test run that quietly
measures a better-looking sibling, and nothing in SQLite stops a disappointing answer from
retroactively becoming a different question. The committed markdown file is that missing half.

So the property this module exists for is a conjunction of three facts, none of which is
sufficient alone:

1. the file's ``config_digest`` is **copied out of the recorded dev ``trials`` row**, never
   recomputed from the live method file (``promote_method``);
2. the live method file still hashes to the ``source_sha`` frozen when the method ran, and the
   named candidate still digests to the recorded digest (``check_source``);
3. the file is in git, unmodified, before the look (``require_committed``, which ``lab test``
   calls and which refuses otherwise).

And one rule on top of those: **a pre-registration is written once and never rewritten.** A
re-run with a better variant available is a refusal, not an update. A re-run on a later day does
not move the ``date`` line, because rewriting identical-but-for-the-date bytes would un-commit a
file whose whole value is that it was committed first.

Format: a strict ``key: value`` block between two ``---`` lines at the very top of the file,
then free markdown for a human reader. ``parse`` reads only the block; it requires every key in
``FIELDS``, refuses an unknown one and refuses a repeated one, so a typo in ``config_digest``
can never read as "no digest given". Every field is a ``str`` -- the file is the record, and
``parse(render(p, name)) == p`` exactly, with no number formatting in the round trip.

Nothing here loads a research store, runs a backtest or writes a ``trials`` row: pre-registering
costs no test-window look.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from typing import Any

from seer_engine import config
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, config_digest, source_sha

log = logging.getLogger(__name__)

PREREG_DIR = config.REPO_ROOT / "docs" / "lab" / "prereg"
FENCE = "---"
# The first words of the analysis section ``promote_method`` appends, and its idempotence key: a
# method whose analysis already names a pre-registered candidate is not pre-registered twice.
MARKER = "Pre-registered for the test window as "

_KEY = re.compile(r"[a-z_]+")
_RECORDED = re.compile(re.escape(MARKER) + r"`([^`]+)`")


class PreregError(store.LabError):
    """A pre-registration the lab's rules refuse.

    A ``store.LabError``, so ``commands/lab.py:run`` already turns it into exit 2 and no caller
    needs a second ``except`` clause.
    """


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


@dataclass(frozen=True)
class Promotion:
    """What ``promote_method`` did, for the caller to print."""

    prereg: Prereg
    path: Path
    trial_n: int
    status: str  # the method's status afterwards; always 'promoted'
    wrote_file: bool  # False when the pre-registration was already on disk and was left alone
    moved_status: bool  # False on a re-run: the method was already 'promoted'


# --------------------------------------------------------------------------- paths and labels


def repo_path(path: Path) -> str:
    """``path`` relative to the repository root in POSIX form, or absolute when outside it.

    Same shape as ``commands.backtest_dev._repo_path``; duplicated rather than imported because
    that one is private to a command module and this one appears in refusal messages a user
    reads.
    """
    p = Path(path).resolve()
    try:
        return p.relative_to(config.REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def path_for(method_id: str, directory: Path | None = None) -> Path:
    """Where ``method_id``'s pre-registration lives: ``docs/lab/prereg/MNNNN.md``."""
    return (PREREG_DIR if directory is None else Path(directory)) / f"{method_id}.md"


def method_of(candidate_id: str) -> str:
    """The method a candidate id belongs to (``M0007-V2`` -> ``M0007``).

    The suffix is required: ``lab test`` spends the look on one variant, so being handed a bare
    method id is an ambiguity to refuse, not a thing to guess at.
    """
    head, sep, rest = candidate_id.partition("-")
    if not sep or not rest or METHOD_ID.fullmatch(head) is None:
        raise PreregError(
            f"{candidate_id!r} is not a lab candidate id: a test-window look is spent on one "
            f"variant (MNNNN-SUFFIX, e.g. M0007-V2), not on a method id"
        )
    return head


def gate_text() -> str:
    """The **dev** gate this variant passed, in the lab's own words.

    Built from ``dev.FAILURE_LABELS`` and ``store.DSR_LABEL`` rather than retyped, so a file
    written next year cannot claim a condition the code stopped applying.

    This is what the variant passed to become ``dev-eligible``; it is **not** the gate the one
    test-window look is judged by. That one is the five P7a D8 conditions alone -- DSR is
    recorded on the test trial and is not a condition, because a pre-registered look has no
    selection among results to deflate (phase 4, ``runner.test_trial_row``). ``render`` says so
    in the file's prose, so a reader of the pre-registration cannot mistake one for the other.
    """
    from seer_engine.backtest import dev

    conditions = "; ".join(dev.FAILURE_LABELS[:-1])
    return (
        f"dev-eligible = the five P7a D8 conditions ({conditions}; no {dev.FAILURE_LABELS[-1]}) "
        f"and {store.DSR_LABEL} with N = every dev trial in the lab"
    )


def test_window_label() -> str:
    """The window ``lab test`` will run on, as the file records it.

    The start is fixed and already published: the first NYSE session after ``dev.DEV_END``, the
    same expression ``lab.store.snapshot`` publishes as ``gate.testStart``. The end is not a date
    this step can know -- the test-window store is built on first promotion and reaches the
    latest session available then (plan Decisions D3) -- so the file records ``data end``, and
    the exact end is pinned afterwards by the ``trials`` row ``lab test`` writes.
    """
    from seer_engine import dates
    from seer_engine.backtest import dev

    return f"{dates.next_session(dev.DEV_END).isoformat()}..data end"


# --------------------------------------------------------------------------- the file


def render(p: Prereg, name: str) -> str:
    """The exact bytes of ``docs/lab/prereg/<method>.md``: the parsed block, then prose."""
    block = "\n".join(f"{k}: {getattr(p, k)}" for k in FIELDS)
    return f"""{FENCE}
{block}
{FENCE}

# {p.method} {name} — pre-registration

`{p.candidate}` is this method's best dev-eligible variant by MAR, and it is the only
configuration the lab may spend a test-window look on. It is identified here by its
`config_digest`, copied from dev trial #{p.dev_trial}: the digest is the canonical text of what
the variant *does* (rules, allocator id, params), not what it is called, so a renamed or
re-tuned variant has a different digest and this file does not name it.

**Gate passed, on the dev window {p.dev_window}:** {p.gate}.
MAR {p.mar}, DSR {p.dsr} at N = {p.n_trials_at_run}.
Research store `{p.store_fingerprint}`, engine `{p.git_sha}`.

**The look that follows.** `python -m seer_engine lab test {p.candidate}` runs this
configuration once on the test window ({p.test_window}) and records one `trials` row with
`window='test'`. The database refuses a second one (`UNIQUE(config_digest, window)`), so there
is no re-roll: pass or fail, the number that comes back is the number that stands.

**What the look is judged by, written down before it happens.** The five P7a D8 go-live
conditions above, applied to the test window, and nothing else. The deflated Sharpe is
*recorded* on the test trial and is **not** a condition: this look is pre-registered, so there
is no selection among test results to deflate, and the lab's multiple-testing N does not move
(a look is not a search). The gate line above is the **dev** gate this variant passed to get
here; it is not the test gate.

This file is written before any test number exists and is committed and pushed before the look
is spent (design §3). `lab test` refuses to run while it is missing, uncommitted or naming a
different candidate, and `lab promote` never rewrites it.

Pre-registered {p.date}.
"""


def parse(text: str) -> Prereg:
    """Read a pre-registration file's front-matter block.

    Strict on purpose. The block must be the first thing in the file, must be closed, must carry
    every key in ``FIELDS`` exactly once, and must carry nothing else. An unknown key is an error
    rather than a shrug: a misspelled ``config_digest`` must never be read as "no digest given".
    """
    lines = text.split("\n")
    if lines[0].strip() != FENCE:
        raise PreregError(
            f"a pre-registration starts with a {FENCE!r} line; found {lines[0]!r}"
        )
    values: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == FENCE:
            break
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or _KEY.fullmatch(key) is None:
            raise PreregError(f"line {i} of the pre-registration is not `key: value`: {line!r}")
        if key not in FIELDS:
            raise PreregError(
                f"line {i}: unknown pre-registration field {key!r} (fields: {', '.join(FIELDS)})"
            )
        if key in values:
            raise PreregError(f"line {i}: pre-registration field {key!r} appears twice")
        values[key] = value.strip()
    else:
        raise PreregError(f"the pre-registration's {FENCE!r} block is not closed")
    missing = [k for k in FIELDS if k not in values]
    if missing:
        raise PreregError(f"the pre-registration is missing {', '.join(missing)}")
    return Prereg(**values)


# --------------------------------------------------------------------------- the gate


def committed_problem(path: Path) -> str | None:
    """None when ``path`` is a file git tracks with no uncommitted change; otherwise why not.

    ``registry_problem`` is the same check ``lab run`` makes on a method file (``runner.py:51``),
    and it shells out with ``cwd=path.parent``. A missing ``docs/lab/prereg/`` would surface
    there as ``FileNotFoundError`` and come back as "git is not installed", which is the wrong
    answer to the wrong question, so the file's existence is settled first.
    """
    from seer_engine.commands.backtest_dev import registry_problem

    path = Path(path)
    if not path.is_file():
        return f"{repo_path(path)} does not exist"
    return registry_problem(path)


def require_committed(candidate_id: str, *, directory: Path | None = None) -> Prereg:
    """The committed pre-registration for ``candidate_id``, or ``PreregError``.

    This is the gate ``lab test`` calls before it spends the look, and the only reason it exists:
    a test number must not be reachable unless the thing being tested was named, in git, first.
    It refuses when

    - ``candidate_id`` is not a lab candidate id;
    - ``docs/lab/prereg/<method>.md`` does not exist;
    - it exists but git does not track it, or it has staged or unstaged changes;
    - it does not parse;
    - it pre-registers a different method, or a different candidate.

    It deliberately does **not** look at the database: the method's status and the one-look rule
    are the caller's refusals, and keeping them apart means a missing file and a wrong status
    give different messages rather than one vague one.
    """
    method_id = method_of(candidate_id)
    path = path_for(method_id, directory)
    problem = committed_problem(path)
    if problem is not None:
        raise PreregError(
            f"{candidate_id}: {problem}. A test-window look is spent only on a configuration "
            f"pre-registered in git first (design §3): run `python -m seer_engine lab promote "
            f"{method_id}`, then commit and push {repo_path(path)} before `lab test`"
        )
    p = parse(path.read_text(encoding="utf-8"))
    if p.method != method_id:
        raise PreregError(f"{repo_path(path)} pre-registers method {p.method}, not {method_id}")
    if p.candidate != candidate_id:
        raise PreregError(
            f"{repo_path(path)} pre-registers {p.candidate}, not {candidate_id}: one method gets "
            f"one pre-registered variant and one look, and this is not it"
        )
    return p


def check_digest(p: Prereg, digest: str, *, directory: Path | None = None) -> None:
    """Refuse a configuration whose digest is not the pre-registered one.

    ``require_committed`` matched the candidate's *id*; this matches what the candidate *does*,
    which is the match that counts -- an id can be reused, a digest cannot. The caller passes the
    digest of the thing it is about to run.
    """
    if digest != p.config_digest:
        raise PreregError(
            f"{p.candidate} now digests to {digest}, but "
            f"{repo_path(path_for(p.method, directory))} pre-registered {p.config_digest}. The "
            f"configuration changed after it was pre-registered; a changed configuration is a "
            f"new method with its own dev trials, not a different thing to spend this method's "
            f"one look on"
        )


def check_source(method_id: str, row: sqlite3.Row, trial: sqlite3.Row) -> Path:
    """The method file still is what the trial measured; returns its path.

    Two equalities, both ``PreregError`` when broken:

    - the file's sha256 is the ``source_sha`` frozen when the method ran, so nothing has edited
      it since (``lab run`` set it once; ``methods_source_sha_once`` keeps it);
    - the candidate the trial names still digests to the trial's ``config_digest``, so the thing
      about to be pre-registered is the thing that was measured.

    The second is implied by the first for most edits, and is checked anyway: ``config_digest``
    canonicalizes ``TradeRules`` and allocator params defined in *other* files, so the method
    file's own bytes do not pin it.

    No git call. ``lab run`` already refused an uncommitted method file before recording these
    trials, and ``source_sha`` answers "has it changed since" exactly, without a subprocess.
    """
    from seer_engine.lab.method import discover

    methods = discover()
    if method_id not in methods:
        raise PreregError(f"no method file for {method_id} in seer_engine/lab/methods/")
    method, path = methods[method_id]
    recorded = row["source_sha"]
    actual = source_sha(path)
    if recorded and actual != recorded:
        raise PreregError(
            f"{repo_path(path)} has changed since {method_id} ran (sha256 {actual[:12]}, "
            f"recorded {str(recorded)[:12]}). Pre-registering it would name a file that is no "
            f"longer what produced these trials: restore the file from git, or make the change a "
            f"new variation method with its own dev trials"
        )
    candidates = {c.id: c for c in method.candidates}
    cid = str(trial["candidate_id"])
    if cid not in candidates:
        raise PreregError(
            f"{repo_path(path)} no longer defines {cid}, which dev trial #{trial['n']} ran"
        )
    digest = config_digest(candidates[cid])
    if digest != trial["config_digest"]:
        raise PreregError(
            f"{cid} now digests to {digest[:12]}, but dev trial #{trial['n']} recorded "
            f"{str(trial['config_digest'])[:12]}: its rules, allocator or params changed after "
            f"it ran"
        )
    return path


# --------------------------------------------------------------------------- promoting


def _fmt(x: Any) -> str:
    """A metric as the file records it: six decimals, or ``-`` when the trial has none."""
    return "-" if x is None else f"{float(x):.6f}"


def _recorded_candidate(analysis: str) -> str | None:
    """The candidate a method's analysis already pre-registers, or None."""
    m = _RECORDED.search(analysis)
    return None if m is None else m.group(1)


def _existing(path: Path, method_id: str) -> Prereg | None:
    """The pre-registration already on disk, or None when there is none.

    A file that exists but does not parse raises rather than returning None: silently
    overwriting it would destroy a record the lab is supposed to keep forever.
    """
    if not Path(path).is_file():
        return None
    p = parse(Path(path).read_text(encoding="utf-8"))
    if p.method != method_id:
        raise PreregError(f"{repo_path(path)} pre-registers method {p.method}, not {method_id}")
    return p


def _analysis_body(p: Prereg, path: Path) -> str:
    return (
        f"{MARKER}`{p.candidate}` (dev trial #{p.dev_trial}, config digest "
        f"`{p.config_digest}`, MAR {p.mar}, DSR {p.dsr} at N = {p.n_trials_at_run}).\n\n"
        f"Pre-registration: `{repo_path(path)}`, written before any test number exists and "
        f"committed before the look is spent (design §3). The test window is {p.test_window}; "
        f"`lab test {p.candidate}` spends the one look this configuration gets, and the database "
        f"refuses a second (`UNIQUE(config_digest, window)`). No `trials` row was written here: "
        f"a pre-registration is not a backtest and does not move the lab's N."
    )


def promote_method(
    conn: sqlite3.Connection,
    method_id: str,
    *,
    git_sha: str,
    today: date | None = None,
    directory: Path | None = None,
    check_method_file: bool = True,
) -> Promotion:
    """Pre-register ``method_id``'s best dev-eligible variant and move it to ``promoted``.

    Design §3 in one step, and it spends nothing: no research store is loaded, no backtest runs,
    no ``trials`` row is inserted, so ``store.test_looks`` is unchanged by this call.

    **Order.** The file is written first, inside the write lock, and the status moves second, in
    the same transaction. A crash between them leaves a pre-registration on disk for a method
    still reading ``dev-eligible``, which a re-run finishes. The reverse order would leave a
    method reading ``promoted`` with nothing pre-registered, which is the one state design §3
    forbids. The file write is not rolled back by the transaction; that asymmetry is the point.

    **Idempotent, and more than idempotent.** A method already at ``promoted`` is not moved again
    (the forward-only trigger would refuse it anyway) and its analysis is not appended to twice.
    A pre-registration already on disk is read, checked and **left byte-for-byte alone** -- not
    rewritten with today's date, because a file whose value is that it was committed first must
    not be un-committed by a re-run. A missing file is rewritten, which repairs a half-finished
    promotion the way ``store.record_promotion`` does.

    **And it refuses to change its mind.** If the file, or the analysis, already pre-registers a
    different candidate than the one the database now ranks best, that is an error. The first
    choice is the one the look is spent on; a genuinely better variant is a new method with its
    own dev trials, not an edit to this file.

    ``check_method_file=False`` skips ``check_source`` -- for tests, which build ``trials`` rows
    with no method file behind them. Nothing in the CLI passes it.
    """
    today = date.today() if today is None else today
    store.begin_immediate(conn)  # the status read, the file and the transition, atomic
    try:
        row = store.get_method(conn, method_id)
        if row is None:
            raise PreregError(f"no method {method_id}")
        status = str(row["status"])
        if status not in ("dev-eligible", "promoted"):
            raise PreregError(
                f"{method_id} is {status!r}, and only a dev-eligible method is pre-registered. "
                f"The gate is: {gate_text()}"
            )
        trial = store.best_dev_eligible(conn, method_id)
        if trial is None:
            raise PreregError(
                f"{method_id} is {status!r} but has no eligible dev trial carrying a MAR, so "
                f"there is nothing to pre-register"
            )
        if check_method_file:
            check_source(method_id, row, trial)

        p = Prereg(
            method=method_id,
            candidate=str(trial["candidate_id"]),
            config_digest=str(trial["config_digest"]),
            rules_id=str(trial["rules_id"]),
            allocator_id=str(trial["allocator_id"]),
            dev_trial=str(trial["n"]),
            dev_window=f"{trial['start']}..{trial['end']}",
            test_window=test_window_label(),
            gate=gate_text(),
            mar=_fmt(trial["mar"]),
            dsr=_fmt(trial["dsr"]),
            n_trials_at_run=str(trial["n_trials_at_run"]),
            store_fingerprint=str(trial["store_fingerprint"]),
            git_sha=git_sha,
            date=today.isoformat(),
        )
        path = path_for(method_id, directory)
        existing = _existing(path, method_id)
        recorded = _recorded_candidate(str(row["analysis"]))
        for already, where in ((existing.candidate if existing else None, repo_path(path)),
                               (recorded, f"{method_id}'s analysis")):
            if already is not None and already != p.candidate:
                raise PreregError(
                    f"{where} already pre-registers {already}, but the best dev-eligible variant "
                    f"now reads {p.candidate}. A pre-registration is written once and never "
                    f"rewritten (design §3): the first choice is the one the look is spent on. "
                    f"If the first one is genuinely wrong, that is a new method with its own dev "
                    f"trials, not a new version of this file"
                )
        if existing is not None:
            if existing.config_digest != p.config_digest:
                raise PreregError(
                    f"{repo_path(path)} pre-registers {existing.candidate} at digest "
                    f"{existing.config_digest}, but dev trial #{p.dev_trial} recorded "
                    f"{p.config_digest} for it. One of the two has been edited; neither is "
                    f"overwritten here"
                )
            p = existing  # the committed record wins, date line and all
            wrote = False
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(p, str(row["name"])), encoding="utf-8")
            wrote = True

        if recorded is None:
            store.append_analysis(
                conn, method_id, "# Pre-registration\n\n" + _analysis_body(p, path)
            )
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
        moved = status == "dev-eligible"
        if moved:
            store.update_method(conn, method_id, status="promoted")
        done = Promotion(
            prereg=p,
            path=path,
            trial_n=int(trial["n"]),
            status="promoted",
            wrote_file=wrote,
            moved_status=moved,
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return done
```

**Impact:** a new module with no importers yet. `commands/lab.py` (step 3) and phase 4's
`lab test` are its only callers. It reads `backtest.dev`, `dates`, `lab.method` and
`commands.backtest_dev.registry_problem` — all inside functions except `lab.method`, which
`lab/runner.py` already imports at module level, so no new import cycle is introduced.

---

### Step 3: the `lab promote` subcommand

**File:** `engine/src/seer_engine/commands/lab.py` — four edits.

**Change 3a — the module docstring**, `commands/lab.py:9`. Insert one line after the `lab run`
block (which ends at `:8`) and before `lab idea` at `:9`:

```python
    lab promote M0007               pre-register the best dev-eligible variant by MAR in
                                    docs/lab/prereg/M0007.md and move the method to promoted;
                                    commit that file before `lab test` will spend the one look
```

**Change 3b — the subparser.** Insert after the `run` subparser's `--allow-coverage` block,
i.e. after `commands/lab.py:78` and before the `idea` subparser at `:80`:

```python
    s = sub.add_parser(
        "promote", help="pre-register a dev-eligible method's best variant for the test window"
    )
    s.add_argument("method")
    s.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="where the pre-registration file goes (default: docs/lab/prereg/ in this checkout)",
    )
```

**Change 3c — the handler.** Insert after `_run` ends at `commands/lab.py:262` and before
`_idea` at `:265`:

```python
def _promote(conn, args) -> int:
    """`lab promote M0007`: pre-register the best dev-eligible variant and move it to promoted.

    Writes one markdown file and one status transition. It loads no research store, runs no
    backtest and inserts no trial, so the test-window look count it prints is the one it found.

    Like every other `lab` subcommand, the global `--dry-run` is ignored: there is no roll-back
    half of this to show, and a dry run that printed a pre-registration without writing it would
    be exactly the artefact design §3 exists to prevent.
    """
    from seer_engine.lab import prereg
    from seer_engine.lab.runner import git_head

    done = prereg.promote_method(
        conn,
        args.method,
        git_sha=git_head(config.REPO_ROOT),
        directory=None if args.dir is None else Path(args.dir),
    )
    p = done.prereg
    rel = prereg.repo_path(done.path)
    print(f"wrote {rel}" if done.wrote_file else f"{rel} already pre-registers {p.candidate}")
    print(f"{p.method} is {done.status}" + ("" if done.moved_status else " (already)"))
    print(f"  candidate      {p.candidate}  (dev trial #{p.dev_trial})")
    print(f"  config digest  {p.config_digest}")
    print(f"  dev window     {p.dev_window}  MAR {p.mar}  DSR {p.dsr} at N = {p.n_trials_at_run}")
    print(f"  test window    {p.test_window}")
    print(f"  gate           {p.gate}")
    print()
    print(f"Commit and push {rel} before the look is spent (design §3):")
    print(f"    git add {rel}")
    print(f"    git commit -m 'lab: pre-register {p.candidate} for the test window'")
    print(f"    python -m seer_engine lab test {p.candidate}")
    print(f"\ntest-window looks used: {store.test_looks(conn)}")
    return 0
```

**Change 3d — the dispatch table.** In `_HANDLERS` (`commands/lab.py:375`), add the entry
between `"run"` and `"idea"` so the table reads in the same order as the docstring:

```python
_HANDLERS = {
    "status": _status,
    "show": _show,
    "run": _run,
    "promote": _promote,
    "idea": _idea,
    "note": _note,
    "block": _block,
    "drop": _drop,
    "seen": _seen,
    "insight": _insight,
    "stage": _stage,
    "next-id": _next_id,
    "export": _export,
    "export-json": _export_json,
    "seed": _seed,
}
```

**Impact:** one new subcommand. `run()` (`:124`) already catches `store.LabError` and returns 2,
and `PreregError` is one, so no exception handling changes. `config` and `Path` are already
imported at `:33`/`:35`. No existing subcommand's behaviour changes.

---

### Step 4: the committed README that makes `docs/lab/prereg/` exist

**File:** `docs/lab/prereg/README.md` — new file (and new directory).

**Change:** git stores no empty directory, so without this the directory first appears on the day
of the first promotion. The README both documents the format and lets the directory be reviewed
before anything is at stake.

**Code:**

````markdown
# Pre-registrations

One file per promoted method: `MNNNN.md`, written by

    python -m seer_engine lab promote MNNNN

and committed and pushed **before** `python -m seer_engine lab test MNNNN-VARIANT` is run
(method lab design §3).

## Why the file exists

The lab gets one look at the test window per configuration. The database enforces the *count*
(`UNIQUE(config_digest, window)` on `trials`, plus triggers that refuse every UPDATE and DELETE).
It cannot enforce *which* configuration the look is spent on, and it cannot stop a disappointing
answer from retroactively becoming a different question.

This file is that half. It names one variant and its `config_digest` before any test number
exists. `lab test` refuses to run while the file is missing, uncommitted, modified, or naming a
different candidate, and `lab promote` never rewrites a file that is already here — a better
variant found later is a new method with its own dev trials, not an edit.

## Format

A strict `key: value` block between two `---` lines at the top of the file, then prose. The
block is machine-read (`seer_engine.lab.prereg.parse`); the prose is not.

| Key | What it is |
|---|---|
| `method` | the method id, `MNNNN` — matches the file name |
| `candidate` | the one pre-registered variant, `MNNNN-SUFFIX` |
| `config_digest` | sha256 of the variant's canonical configuration, **copied from the recorded dev trial** |
| `rules_id`, `allocator_id` | what the variant trades with, for a reader |
| `dev_trial` | the `trials.n` the digest was copied from |
| `dev_window` | that trial's `start..end` |
| `test_window` | `2015-10-19..data end` — the start is the first session after `DEV_END`; the end is pinned by the test trial, because the test store reaches the latest session available when it is built |
| `gate` | the conditions the variant passed on the dev window |
| `mar`, `dsr`, `n_trials_at_run` | the dev numbers it passed with, and the N the DSR deflated by |
| `store_fingerprint`, `git_sha` | the research store and the engine that produced them |
| `date` | the day it was pre-registered; it does not move on a re-run |

Every value is read as text. The file is the record.

## Reading one back

```python
from seer_engine.lab import prereg

p = prereg.require_committed("M0007-V2")  # PreregError unless it exists, parses and is committed
p.config_digest
```
````

**Impact:** documentation only. Nothing imports it.

---

### Step 5: tests

**File:** `engine/tests/test_lab_prereg.py` — new file.

**Change:** the full behaviour, including the test the phase exists for — the file's
`config_digest` equals the recorded dev trial's `config_digest` for that candidate, and equals no
other trial's.

**Code:**

```python
"""Pre-registration (method lab design §3): `lab promote`, docs/lab/prereg/ and the gate.

Every test builds its own temp lab database. The real one has no dev-eligible method, and these
tests must keep passing on the day it does.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest

from seer_engine import dates
from seer_engine.backtest import dev
from seer_engine.lab import prereg, store
from seer_engine.lab.method import config_digest, discover, source_sha


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


@pytest.fixture()
def prereg_dir(tmp_path):
    """Where a test's pre-registrations go.

    Its own directory, not `tmp_path`: the `conn` fixture puts `lab.sqlite` in `tmp_path`, and
    several tests below assert that *nothing* was written, which has to mean nothing.
    It is deliberately not created -- `promote_method` creating it is part of what is tested.
    """
    return tmp_path / "prereg"


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=60, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


_PATH_TO: dict[str, tuple[str, ...]] = {
    "idea": (),
    "registered": ("registered",),
    "rejected": ("registered", "rejected"),
    "blocked-data": ("blocked-data",),
}


def _at_status(conn, status: str, mid: str = "M0001") -> None:
    with conn:
        store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                         hypothesis="h")
        for s in _PATH_TO[status]:
            store.update_method(conn, mid, status=s)


def _eligible(conn, mid: str = "M0001", trials=None) -> None:
    """A method at `dev-eligible` with trials recorded, the way `lab run` leaves one."""
    with conn:
        store.add_method(conn, id=mid, name="SMA test", family="trend",
                         source_kind="knowledge", hypothesis="h", status="registered")
        store.insert_trials(conn, list(trials if trials is not None else [_trial()]))
        store.update_method(conn, mid, status="dev-eligible")


def _real_method(conn, mid: str = "M0001"):
    """What `lab run` would have left behind for the committed `mNNNN_*.py` file `mid`.

    The real file is used so `check_source` has something true to check: the trial's digest is
    the file's own `config_digest` and `source_sha` is the file's sha256.
    """
    method, path = discover()[mid]
    c = method.candidates[0]
    with conn:
        store.add_method(conn, id=mid, name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [_trial(method_id=mid, candidate_id=c.id,
                                          config_digest=config_digest(c), rules_id=c.rules.id,
                                          allocator_id=str(c.allocator.id))])
        store.update_method(conn, mid, source_sha=source_sha(path), status="dev-eligible")
    return c, path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=seer-test", "-c", "user.email=seer-test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _repo(tmp_path: Path) -> Path:
    """A git repo with an empty docs/lab/prereg/; returns that directory."""
    repo = tmp_path / "repo"
    directory = repo / "docs" / "lab" / "prereg"
    directory.mkdir(parents=True)
    _git(repo, "init", "-q")
    return directory


# ------------------------------------------------------------------ choosing the variant


def test_promote_pre_registers_the_best_eligible_variant_by_mar(conn, prereg_dir):
    _eligible(conn, trials=[
        _trial(candidate_id="M0001-A", config_digest="da", mar=0.60),
        _trial(candidate_id="M0001-B", config_digest="db", mar=0.90),
        _trial(candidate_id="M0001-C", config_digest="dc", mar=1.50, eligible=False,
               failed="max DD <= 15%"),
    ])
    done = prereg.promote_method(conn, "M0001", git_sha="deadbeef", today=date(2026, 10, 6),
                                 directory=prereg_dir, check_method_file=False)
    assert done.prereg.candidate == "M0001-B"
    assert done.prereg.config_digest == "db"
    assert done.path == prereg_dir / "M0001.md"
    assert done.prereg.date == "2026-10-06"
    assert store.get_method(conn, "M0001")["status"] == "promoted"


def test_the_pre_registered_digest_is_the_recorded_dev_trials_digest(conn, prereg_dir):
    """The property this whole phase exists for.

    Not "a digest is present": the digest in the written file is byte-equal to the `trials`
    row's digest for that candidate, and equal to no other trial's, so the one look cannot be
    spent on a sibling that happens to look better.
    """
    _eligible(conn, trials=[
        _trial(candidate_id="M0001-A", config_digest="a" * 64, mar=0.60),
        _trial(candidate_id="M0001-B", config_digest="b" * 64, mar=0.90),
        _trial(candidate_id="M0001-C", config_digest="c" * 64, mar=1.50, eligible=False,
               failed="PF >= 1.3"),
    ])
    prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir,
                          check_method_file=False)
    p = prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8"))
    row = conn.execute(
        "SELECT * FROM trials WHERE candidate_id = ? AND window = 'dev'", (p.candidate,)
    ).fetchone()
    assert p.config_digest == row["config_digest"]
    assert p.dev_trial == str(row["n"])
    assert p.dev_window == f"{row['start']}..{row['end']}"
    assert p.n_trials_at_run == str(row["n_trials_at_run"])
    assert p.store_fingerprint == row["store_fingerprint"]
    others = [r["config_digest"] for r in store.trials_of(conn, "M0001")
              if r["candidate_id"] != p.candidate]
    assert others and p.config_digest not in others


def test_the_digest_is_checked_against_the_live_method_file(conn, prereg_dir):
    c, _ = _real_method(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir)
    assert done.prereg.candidate == c.id
    assert done.prereg.config_digest == config_digest(c)


def test_promote_refuses_a_method_file_that_changed_since_it_ran(conn, prereg_dir):
    """`source_sha` is written wrong from the start, never re-written.

    `methods_source_sha_once` (store.py:208) fires on any change once the column is non-NULL --
    NULL included -- so a test cannot set it and then correct it. It sets the sha of a file that
    is not this one, which is exactly the state a post-run edit would leave behind.
    """
    method, path = discover()["M0001"]
    c = method.candidates[0]
    with conn:
        store.add_method(conn, id="M0001", name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [_trial(candidate_id=c.id, config_digest=config_digest(c))])
        store.update_method(conn, "M0001", source_sha="0" * 64, status="dev-eligible")
    with pytest.raises(prereg.PreregError, match="has changed since"):
        prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir)
    assert not prereg_dir.exists()
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"


def test_promote_refuses_a_variant_whose_configuration_drifted(conn, prereg_dir):
    method, path = discover()["M0001"]
    c = method.candidates[0]
    with conn:
        store.add_method(conn, id="M0001", name=method.name, family=method.family,
                         source_kind=method.source_kind, source_ref=method.source_ref,
                         hypothesis="h", status="registered")
        store.insert_trials(conn, [_trial(candidate_id=c.id, config_digest="stale")])
        store.update_method(conn, "M0001", source_sha=source_sha(path), status="dev-eligible")
    with pytest.raises(prereg.PreregError, match="now digests to"):
        prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir)
    assert not prereg_dir.exists()


# ------------------------------------------------------------------ refusals


@pytest.mark.parametrize("status", sorted(_PATH_TO))
def test_promote_refuses_a_method_that_is_not_dev_eligible(conn, prereg_dir, status):
    _at_status(conn, status)
    with pytest.raises(prereg.PreregError, match="only a dev-eligible method"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not prereg_dir.exists()
    assert store.get_method(conn, "M0001")["status"] == status


def test_promote_refuses_an_unknown_method(conn, prereg_dir):
    with pytest.raises(prereg.PreregError, match="no method M0099"):
        prereg.promote_method(conn, "M0099", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not prereg_dir.exists()


def test_promote_refuses_a_dev_eligible_method_with_no_eligible_trial(conn, prereg_dir):
    _eligible(conn, trials=[_trial(eligible=False, failed="PF >= 1.3")])
    with pytest.raises(prereg.PreregError, match="nothing to pre-register"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not prereg_dir.exists()


# ------------------------------------------------------------------ idempotence


def test_promote_is_idempotent_and_does_not_move_the_date(conn, prereg_dir):
    _eligible(conn)
    first = prereg.promote_method(conn, "M0001", git_sha="deadbeef", today=date(2026, 10, 6),
                                  directory=prereg_dir, check_method_file=False)
    assert first.wrote_file and first.moved_status
    text = (prereg_dir / "M0001.md").read_text(encoding="utf-8")

    second = prereg.promote_method(conn, "M0001", git_sha="cafe", today=date(2026, 12, 25),
                                   directory=prereg_dir, check_method_file=False)
    assert not second.wrote_file and not second.moved_status
    assert second.status == "promoted"
    assert second.prereg == first.prereg
    assert (prereg_dir / "M0001.md").read_text(encoding="utf-8") == text
    assert sorted(p.name for p in prereg_dir.iterdir()) == ["M0001.md"]
    assert store.get_method(conn, "M0001")["status"] == "promoted"
    assert store.get_method(conn, "M0001")["analysis"].count(prereg.MARKER) == 1
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 1


def test_promote_rewrites_a_pre_registration_that_went_missing(conn, prereg_dir):
    _eligible(conn)
    prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir,
                          check_method_file=False)
    (prereg_dir / "M0001.md").unlink()
    done = prereg.promote_method(conn, "M0001", git_sha="deadbeef", directory=prereg_dir,
                                 check_method_file=False)
    assert done.wrote_file and not done.moved_status
    assert (prereg_dir / "M0001.md").is_file()
    assert store.get_method(conn, "M0001")["analysis"].count(prereg.MARKER) == 1
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 1


def test_a_pre_registration_is_never_rewritten_for_a_better_variant(conn, prereg_dir):
    _eligible(conn, trials=[_trial(candidate_id="M0001-A", config_digest="da", mar=0.60)])
    prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                          check_method_file=False)
    with conn:
        store.insert_trials(conn, [_trial(candidate_id="M0001-B", config_digest="db", mar=0.99)])
    with pytest.raises(prereg.PreregError, match="already pre-registers M0001-A"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    p = prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8"))
    assert p.candidate == "M0001-A" and p.config_digest == "da"


def test_a_lost_file_is_not_an_opening_to_pre_register_a_different_variant(conn, prereg_dir):
    """The analysis remembers the choice even when the file does not."""
    _eligible(conn, trials=[_trial(candidate_id="M0001-A", config_digest="da", mar=0.60)])
    prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                          check_method_file=False)
    (prereg_dir / "M0001.md").unlink()
    with conn:
        store.insert_trials(conn, [_trial(candidate_id="M0001-B", config_digest="db", mar=0.99)])
    with pytest.raises(prereg.PreregError, match="already pre-registers M0001-A"):
        prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                              check_method_file=False)
    assert not (prereg_dir / "M0001.md").exists()


# ------------------------------------------------------------------ it spends nothing


def test_promote_writes_no_trial_and_spends_no_look(conn, prereg_dir):
    _eligible(conn)
    before = store.dev_trial_count(conn)
    prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                          check_method_file=False)
    assert store.dev_trial_count(conn) == before
    assert store.test_looks(conn) == 0


# ------------------------------------------------------------------ the gate phase 4 calls


def test_require_committed_refuses_a_missing_pre_registration(tmp_path):
    with pytest.raises(prereg.PreregError, match="does not exist"):
        prereg.require_committed("M0007-V2", directory=tmp_path)


def test_require_committed_wants_a_candidate_id_not_a_method_id(tmp_path):
    for bad in ("M0001", "M0001-", "momentum-A", "H-A"):
        with pytest.raises(prereg.PreregError, match="not a lab candidate id"):
            prereg.require_committed(bad, directory=tmp_path)


def test_require_committed_refuses_until_the_file_is_committed(conn, tmp_path):
    directory = _repo(tmp_path)
    _eligible(conn)
    prereg.promote_method(conn, "M0001", git_sha="x", directory=directory,
                          check_method_file=False)
    with pytest.raises(prereg.PreregError, match="uncommitted"):
        prereg.require_committed("M0001-A", directory=directory)  # untracked
    _git(directory, "add", "M0001.md")
    with pytest.raises(prereg.PreregError, match="uncommitted"):
        prereg.require_committed("M0001-A", directory=directory)  # staged is not committed
    _git(directory, "commit", "-q", "-m", "prereg")
    p = prereg.require_committed("M0001-A", directory=directory)
    assert p.candidate == "M0001-A" and p.config_digest == "d1"
    (directory / "M0001.md").write_text("---\n", encoding="utf-8")
    with pytest.raises(prereg.PreregError, match="uncommitted"):
        prereg.require_committed("M0001-A", directory=directory)  # modified after the commit


def test_require_committed_refuses_a_file_naming_another_candidate(conn, tmp_path):
    directory = _repo(tmp_path)
    _eligible(conn)
    prereg.promote_method(conn, "M0001", git_sha="x", directory=directory,
                          check_method_file=False)
    _git(directory, "add", "M0001.md")
    _git(directory, "commit", "-q", "-m", "prereg")
    with pytest.raises(prereg.PreregError, match="pre-registers M0001-A, not M0001-Z"):
        prereg.require_committed("M0001-Z", directory=directory)


def test_check_digest_matches_only_the_pre_registered_configuration(conn, prereg_dir):
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    prereg.check_digest(done.prereg, "d1", directory=prereg_dir)  # no raise
    with pytest.raises(prereg.PreregError, match="pre-registered d1"):
        prereg.check_digest(done.prereg, "d2", directory=prereg_dir)


# ------------------------------------------------------------------ the format itself


def test_parse_round_trips_render(conn, prereg_dir):
    _eligible(conn)
    done = prereg.promote_method(conn, "M0001", git_sha="x", directory=prereg_dir,
                                 check_method_file=False)
    assert prereg.parse(prereg.render(done.prereg, "SMA test")) == done.prereg
    assert prereg.parse((prereg_dir / "M0001.md").read_text(encoding="utf-8")) == done.prereg


@pytest.mark.parametrize("text, message", [
    ("no front matter\n", "starts with"),
    ("---\nmethod: M0001\n", "is not closed"),
    ("---\nmethod: M0001\n---\n", "missing candidate"),
    ("---\nmethod M0001\n---\n", "not `key: value`"),
])
def test_parse_refuses_a_malformed_pre_registration(text, message):
    with pytest.raises(prereg.PreregError, match=re.escape(message)):
        prereg.parse(text)


def test_parse_refuses_an_unknown_or_repeated_field():
    good = "\n".join(f"{k}: x" for k in prereg.FIELDS)
    with pytest.raises(prereg.PreregError, match="unknown pre-registration field 'digest'"):
        prereg.parse(f"{prereg.FENCE}\n{good}\ndigest: x\n{prereg.FENCE}\n")
    with pytest.raises(prereg.PreregError, match="appears twice"):
        prereg.parse(f"{prereg.FENCE}\n{good}\nmethod: y\n{prereg.FENCE}\n")


def test_the_recorded_gate_names_every_condition_the_lab_applies():
    """The gate line is built from the engine's own labels, so it cannot drift from the code."""
    text = prereg.gate_text()
    for label in dev.FAILURE_LABELS:
        assert label in text
    assert store.DSR_LABEL in text


def test_the_recorded_test_window_starts_the_session_after_dev_end():
    label = prereg.test_window_label()
    assert label == f"{dates.next_session(dev.DEV_END).isoformat()}..data end"
    assert label.startswith("2015-10-19")


# ------------------------------------------------------------------ the CLI


def test_lab_promote_command_writes_the_file_and_names_the_next_step(
    tmp_path, prereg_dir, capsys, monkeypatch
):
    from seer_engine.commands import lab as lab_cmd
    from seer_engine.lab import runner

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    candidate, _ = _real_method(c)
    c.close()
    # `_promote` imports git_head inside the function, so the attribute is read at call time.
    monkeypatch.setattr(runner, "git_head", lambda cwd: "deadbeef")
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    assert candidate.id in out
    assert f"lab test {candidate.id}" in out
    assert "test-window looks used: 0" in out
    written = prereg_dir / "M0001.md"
    assert written.is_file()
    assert prereg.parse(written.read_text(encoding="utf-8")).candidate == candidate.id


def test_lab_promote_command_exits_2_when_the_lab_refuses(tmp_path, prereg_dir):
    from seer_engine.commands import lab as lab_cmd

    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _at_status(c, "registered")
    c.close()
    args = argparse.Namespace(db=db, lab_command="promote", method="M0001", dir=prereg_dir)
    assert lab_cmd.run(args) == 2
    assert not prereg_dir.exists()
```

**Impact:** new tests only. `test_promote_refuses_a_method_file_that_changed_since_it_ran` writes
`source_sha` with raw SQL in two statements because `methods_source_sha_once` (`store.py:208`)
refuses a second value through `update_method` — NULL first, then the wrong value, is what the
trigger permits (it fires only when `OLD.source_sha IS NOT NULL`).

---

### Step 6: one test for `best_dev_eligible`

**File:** `engine/tests/test_lab_store.py` — append after
`test_a_configuration_runs_once_per_window` (ends at `:66`), before
`test_status_only_moves_forward` at `:69`.

**Change:** the selection rule belongs to `store.py`, so its test belongs beside the other store
rules. `_trial` and `_method` already exist in that file (`:23`, `:28`); `_trial`'s default is
`eligible=False`, so each eligible row names it explicitly.

**Code:**

```python
def test_best_dev_eligible_is_the_highest_mar_and_breaks_ties_on_the_trial_number(conn):
    _method(conn)
    assert store.best_dev_eligible(conn, "M0001") is None
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, eligible=True, failed=""),
            _trial(candidate_id="M0001-B", config_digest="db", mar=0.9, eligible=True, failed=""),
            _trial(candidate_id="M0001-C", config_digest="dc", mar=1.4),  # not eligible
            _trial(candidate_id="M0001-D", config_digest="dd", mar=None, eligible=True, failed=""),
            _trial(candidate_id="M0001-E", config_digest="de", window="test", mar=2.0,
                   eligible=True, failed=""),
        ])
    best = store.best_dev_eligible(conn, "M0001")
    assert best["candidate_id"] == "M0001-A"  # the tie breaks on n, and the test trial is not it
    assert store.best_dev_eligible(conn, "M0002") is None
```

**Impact:** one added test. No existing test in the file is edited, including none of the three
`DEV_END` pins (which live in `test_fundamentals_coverage.py:107` and `test_research_store.py`
and are untouched by this phase).

---

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/build-promotion-path/engine && python -c "import seer_engine.lab.prereg, seer_engine.commands.lab"
cd /home/miftah/.worktrees/seer/build-promotion-path/engine && python -m ruff check src tests
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/build-promotion-path/engine && python -m pytest -q tests/test_lab_prereg.py tests/test_lab_store.py tests/test_lab_runner.py tests/test_lab_snapshot.py tests/test_cli.py
cd /home/miftah/.worktrees/seer/build-promotion-path/engine && python -m pytest -q
```

**Manual check:**

```
cd /home/miftah/.worktrees/seer/build-promotion-path/engine && python -m seer_engine lab promote --help
cd /home/miftah/.worktrees/seer/build-promotion-path/engine && python -m seer_engine lab promote M0007   # expects exit 2: M0007 is 'rejected'
cd /home/miftah/.worktrees/seer/build-promotion-path && git status --porcelain
```

The last one must show only the files this phase adds and edits. It must **not** show
`lab/lab.sqlite` or `web/data/lab.json`: `lab promote` on the real database is refused before it
writes anything, because no method is dev-eligible.

**Exit criteria:**

1. `python -m pytest -q` passes in `engine/` with no existing test edited.
2. `lab promote <method>` exits 2 for every status except `dev-eligible` and `promoted`, writing
   no file and moving no status.
3. For a dev-eligible method it writes exactly one `docs/lab/prereg/MNNNN.md` carrying `method`,
   `candidate`, `config_digest`, `gate`, `test_window` and `date`, and moves the method to
   `promoted`.
4. The file's `config_digest` is byte-equal to the recorded dev `trials` row's `config_digest`
   for that candidate and equal to no other trial's
   (`test_the_pre_registered_digest_is_the_recorded_dev_trials_digest`).
5. A second `lab promote` of the same method writes no second file, leaves the first file
   byte-identical including its `date`, appends no second analysis section and no second insight,
   and attempts no second transition.
6. `prereg.require_committed` raises `PreregError` for missing, untracked, staged-only, modified
   and mismatched files, and returns the `Prereg` once the file is committed.
7. `store.test_looks(conn)` reads 0 in the real database and `trials` is unchanged
   (`git status` shows no `lab/lab.sqlite`).

## Handoffs

- **Phase 4 wires the gate.** `lab test <candidate>` calls
  `prereg.require_committed(candidate_id)` before anything else, then
  `prereg.check_digest(p, config_digest(candidate))` once it has resolved the live candidate, and
  only then loads the test-window store. Both refusals are `PreregError`, already exit 2.
  Phase 4 also owns the `promoted → test-passed|test-failed` transition; this phase deliberately
  stops at `promoted`.
- **`SKILL.md`'s "Promotion" section** (`.claude/skills/explore-and-experiment-new-method/SKILL.md:123`–`:143`)
  names no command for either half. It must name `lab promote`, the commit of the prereg file,
  and `lab test` — but that is one coherent edit describing both commands, so it belongs to
  **phase 4**, after `lab test` exists. Left untouched here so two phases do not edit one file.
  **Reconciled 2026-10-06:** phase 4 now owns the **whole** section (its Step 10 replaces lines
  123–143 outright), including the `lab promote` step this phase's command makes possible, and
  including the now-false "if `lab test` and the test-window store don't exist yet, build them
  first". Documenting `lab promote` there is R2 work, not R3 work: `lab test` *refuses* without
  a committed pre-registration, so an agent that is never told how to produce one has a
  `lab test` that cannot run. This phase's **Satisfies** stays R3 and phase 4's stays R2.
  `/sera-the-explorer`'s SKILL.md says only "promotes eligible methods" (`:11`) and names no
  command, so it is already accurate and needs no edit from any phase.
- **`lab status` / `lab show` do not mention pre-registrations.** A line under
  "Dev-eligible / promoted" saying which methods have a committed prereg would be useful; it is
  not needed by R3 and would touch the status output phase 4 also prints to. Leave it to a later
  pass, or fold it into phase 4's `test-window looks used` work.
- **`repo_path` is duplicated** from `commands.backtest_dev._repo_path` (`:547`), six lines, because
  that one is private to a command module. If the reconciler wants one copy, promote it to
  `seer_engine/config.py` — but that is a cleanup, not this phase's work.
- **The web snapshot does not publish pre-registrations.** `store.snapshot` has `gate.testStart`
  but no notion of a prereg file. Showing one on seertrade.site/sera is a separate, later change;
  nothing here changes `SNAPSHOT_VERSION` or the snapshot's shape, so `web/data/lab.json` is
  byte-identical after this phase.
- **Phase 1/2 window naming.** If either introduces a named test-window value, repoint the single
  return statement of `prereg.test_window_label()` at it. The file format does not change — the
  value is text either way.

## Rollback

One commit on `feature/build-promotion-path`; `git revert` it. The revert deletes
`engine/src/seer_engine/lab/prereg.py`, `engine/tests/test_lab_prereg.py` and
`docs/lab/prereg/README.md`, removes `best_dev_eligible` from `store.py` and removes the
`promote` subcommand from `commands/lab.py`. No other subcommand's behaviour changes, so
`lab run`, `lab status` and `lab stage` are untouched either way.

There is no lab state to unwind: this phase spends no test-window look, inserts no `trials` row,
does not commit `lab/lab.sqlite` or `web/data/lab.json`, and changes no schema. If `lab promote`
has been run against the real database before the revert, the method's `promoted` status and its
appended analysis are append-only and stay — which is correct, since the pre-registration file it
wrote is also still in git. Reverting the code does not un-pre-register a method, and must not.
