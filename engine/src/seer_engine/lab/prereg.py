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
