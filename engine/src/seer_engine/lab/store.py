"""The method lab's database: ``lab/lab.sqlite``, committed, append-only (method lab design §1).

Impure edge: stdlib ``sqlite3`` and the clock (timestamps). Every lab read and write goes
through this module.

Tables:

- ``methods``: one row per idea. ``H-*`` ids are the historical record (P7a families, A, A2,
  B); ``M0001``… are lab methods. ``status`` only moves along ``TRANSITIONS`` (a trigger refuses
  any other update); ``analysis`` only grows (a trigger refuses a rewrite); ``hypothesis`` is
  frozen once the method leaves ``idea``; ``source_sha`` (the method file's sha256 when it ran)
  is set once.
- ``trials``: one row per backtest, the multiple-testing count. Triggers refuse every UPDATE
  and DELETE. ``UNIQUE(config_digest, window)``: a configuration runs at most once on the dev
  window and gets at most one look at the test window.
- ``ideas_seen``: dedupe keys (``url:…``, ``concept:…``) of sources already explored.
- ``insights``: the lab journal (observations, hypotheses, data and feature wishes, risks, and
  batch syntheses). Triggers refuse every UPDATE and DELETE.

Schema versions (``meta.schema_version``): 1 is the first lab; 2 adds the ``synthesis`` insight
kind. ``connect`` migrates an older database in place; ``connect_readonly`` never does.

``snapshot`` / ``snapshot_json`` turn a database (v1 or v2) into the web's ``web/data/lab.json``
(seertrade.site/sera). ``lab stage`` writes it next to the database and stages both.

``journal_mode`` stays DELETE, so the committed file is the whole database (no ``-wal``).
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from seer_engine import config

COMMITTED_DB = config.REPO_ROOT / "lab" / "lab.sqlite"
# Parallel explorer sessions (sera-the-explorer) run in worktrees and share the main checkout's
# database through SEER_LAB_DB; only the coordinator commits it.
DB_PATH = Path(os.environ.get("SEER_LAB_DB") or COMMITTED_DB)
XLSX_PATH = config.REPO_ROOT / "lab" / "lab.xlsx"  # gitignored
SCHEMA_VERSION = "2"  # 2: the synthesis insight kind (see _migrate)

SOURCE_KINDS: tuple[str, ...] = ("paper", "blog", "github", "knowledge", "variation", "seed")
STATUSES: tuple[str, ...] = (
    "idea",
    "registered",
    "rejected",
    "dev-eligible",
    "promoted",
    "test-passed",
    "test-failed",
    "paper",
    "blocked-data",
)
TRANSITIONS: tuple[tuple[str, str], ...] = (
    ("idea", "registered"),
    ("idea", "rejected"),  # dropped before running (duplicate, untestable for another reason)
    ("idea", "blocked-data"),
    ("registered", "rejected"),
    ("registered", "dev-eligible"),
    ("registered", "blocked-data"),
    ("blocked-data", "idea"),  # the missing data arrived
    ("dev-eligible", "promoted"),
    ("promoted", "test-passed"),
    ("promoted", "test-failed"),
    ("test-passed", "paper"),
)
WINDOWS: tuple[str, ...] = ("dev", "test")
INSIGHT_KINDS: tuple[str, ...] = (
    "observation", "hypothesis", "data-wish", "feature-wish", "risk", "synthesis",
)
DSR_MIN = 0.95  # lab eligibility on the dev window, on top of the five P7a D8 conditions
DSR_LABEL = "DSR >= 0.95"

# The first words of the analysis section `record_promotion` appends, and its idempotence key:
# a method whose analysis already names this roster id has been recorded and is not recorded twice.
PROMOTION_MARKER = "Promoted to the paper roster as "


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The insights table and its two triggers, one statement each. ``_SCHEMA`` creates them on a new
# database; ``_migrate`` recreates them when it rebuilds a v1 table (SQLite cannot alter a CHECK).
_INSIGHTS_TABLE = f"""CREATE TABLE IF NOT EXISTS insights (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT NOT NULL CHECK (kind IN ({_quoted(INSIGHT_KINDS)})),
    title     TEXT NOT NULL CHECK (length(trim(title)) > 0),
    body      TEXT NOT NULL CHECK (length(trim(body)) > 0),
    method_id TEXT REFERENCES methods(id),
    added     TEXT NOT NULL
)"""
_INSIGHTS_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS insights_no_update BEFORE UPDATE ON insights
BEGIN SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead'); END""",
    """CREATE TRIGGER IF NOT EXISTS insights_no_delete BEFORE DELETE ON insights
BEGIN SELECT RAISE(ABORT, 'insights are append-only'); END""",
)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transitions (
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    PRIMARY KEY (src, dst)
);

CREATE TABLE IF NOT EXISTS methods (
    id            TEXT PRIMARY KEY CHECK (id GLOB 'M[0-9][0-9][0-9][0-9]' OR id GLOB 'H-*'),
    name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
    family        TEXT NOT NULL CHECK (length(trim(family)) > 0),
    parent_id     TEXT REFERENCES methods(id),
    source_kind   TEXT NOT NULL CHECK (source_kind IN ({_quoted(SOURCE_KINDS)})),
    source_ref    TEXT NOT NULL DEFAULT '',
    hypothesis    TEXT NOT NULL CHECK (length(trim(hypothesis)) > 0),
    status        TEXT NOT NULL CHECK (status IN ({_quoted(STATUSES)})),
    analysis      TEXT NOT NULL DEFAULT '',
    verdict       TEXT NOT NULL DEFAULT '',
    blocked_on    TEXT NOT NULL DEFAULT '',
    source_sha    TEXT,
    created       TEXT NOT NULL,
    updated       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trials (
    n                 INTEGER PRIMARY KEY AUTOINCREMENT,
    method_id         TEXT NOT NULL REFERENCES methods(id),
    candidate_id      TEXT NOT NULL,
    config_digest     TEXT NOT NULL,
    config_text       TEXT NOT NULL,
    rules_id          TEXT NOT NULL,
    allocator_id      TEXT NOT NULL,
    window            TEXT NOT NULL CHECK (window IN ({_quoted(WINDOWS)})),
    start             TEXT NOT NULL,
    "end"             TEXT NOT NULL,
    store_fingerprint TEXT NOT NULL,
    git_sha           TEXT NOT NULL,
    run_at            TEXT NOT NULL,
    total_return      REAL,
    cagr              REAL,
    max_drawdown      REAL,
    profit_factor     REAL,
    trades            INTEGER NOT NULL,
    sharpe            REAL,
    exposure          REAL,
    turnover          REAL,
    worst_year        INTEGER,
    worst_year_return REAL,
    spy_tr_return     REAL,
    spy_tr_cagr       REAL,
    mar               REAL,
    failed            TEXT NOT NULL,
    eligible          INTEGER NOT NULL CHECK (eligible IN (0, 1)),
    dsr               REAL,
    n_trials_at_run   INTEGER NOT NULL,
    curve_json        TEXT NOT NULL,
    UNIQUE (config_digest, window),
    UNIQUE (candidate_id, window)
);

CREATE TABLE IF NOT EXISTS ideas_seen (
    key       TEXT PRIMARY KEY CHECK (key GLOB '?*:?*'),
    method_id TEXT REFERENCES methods(id),
    note      TEXT NOT NULL DEFAULT '',
    added     TEXT NOT NULL
);

{_INSIGHTS_TABLE};

{_INSIGHTS_TRIGGERS[0]};

{_INSIGHTS_TRIGGERS[1]};

CREATE TRIGGER IF NOT EXISTS trials_no_update BEFORE UPDATE ON trials
BEGIN SELECT RAISE(ABORT, 'trials are append-only: a trial row is never updated'); END;

CREATE TRIGGER IF NOT EXISTS trials_no_delete BEFORE DELETE ON trials
BEGIN SELECT RAISE(ABORT, 'trials are append-only: a trial row is never deleted'); END;

CREATE TRIGGER IF NOT EXISTS methods_no_delete BEFORE DELETE ON methods
BEGIN SELECT RAISE(ABORT, 'methods are never deleted'); END;

CREATE TRIGGER IF NOT EXISTS methods_status_forward BEFORE UPDATE OF status ON methods
WHEN NEW.status <> OLD.status
 AND NOT EXISTS (SELECT 1 FROM transitions WHERE src = OLD.status AND dst = NEW.status)
BEGIN SELECT RAISE(ABORT, 'method status may only move forward along TRANSITIONS'); END;

CREATE TRIGGER IF NOT EXISTS methods_analysis_grows BEFORE UPDATE OF analysis ON methods
WHEN substr(NEW.analysis, 1, length(OLD.analysis)) IS NOT OLD.analysis
BEGIN SELECT RAISE(ABORT, 'analysis is append-only: add to it, never rewrite it'); END;

CREATE TRIGGER IF NOT EXISTS methods_hypothesis_frozen BEFORE UPDATE OF hypothesis ON methods
WHEN OLD.status <> 'idea' AND NEW.hypothesis IS NOT OLD.hypothesis
BEGIN SELECT RAISE(ABORT, 'the hypothesis is frozen once a method leaves idea'); END;

CREATE TRIGGER IF NOT EXISTS methods_source_sha_once BEFORE UPDATE OF source_sha ON methods
WHEN OLD.source_sha IS NOT NULL AND NEW.source_sha IS NOT OLD.source_sha
BEGIN SELECT RAISE(ABORT, 'source_sha is set once, when the method runs'); END;

CREATE TRIGGER IF NOT EXISTS seen_no_delete BEFORE DELETE ON ideas_seen
BEGIN SELECT RAISE(ABORT, 'ideas_seen is append-only'); END;
"""


class LabError(RuntimeError):
    """A lab operation the database's rules refuse (exit 2 in the CLI)."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open (creating when missing) the lab database with the schema, triggers and transitions,
    migrating an older database to ``SCHEMA_VERSION`` first."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120)  # parallel explorer sessions share one file
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = DELETE")
        with conn:
            conn.executescript(_SCHEMA)
            conn.executemany("INSERT OR IGNORE INTO transitions (src, dst) VALUES (?, ?)", TRANSITIONS)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
            )
        _migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def connect_readonly(path: Path = COMMITTED_DB) -> sqlite3.Connection:
    """Open an existing lab database read-only, exactly as it is: no schema, no migration, no
    write (``mode=ro``). For the snapshot sync guard, which must not touch the committed file."""
    path = Path(path).resolve()
    if not path.is_file():
        raise LabError(f"no lab database at {path}")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def schema_version(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return None if row is None else str(row[0])


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an older database up to ``SCHEMA_VERSION`` in one transaction under the write lock.

    v1 -> v2 adds the ``synthesis`` insight kind. SQLite cannot alter a CHECK, so ``insights`` is
    rebuilt: the v1 table is renamed aside, the v2 table is created from ``_INSIGHTS_TABLE``,
    every row is copied with its id, the AUTOINCREMENT counter is carried over, the v1 table is
    dropped (which drops its triggers and fires none), and the two append-only triggers are
    created on the new table. The triggers come last: while the v1 table exists its triggers
    hold their names, and ``CREATE TRIGGER IF NOT EXISTS`` would silently skip them.

    Parallel sessions may connect at once, so the version is read again after
    ``BEGIN IMMEDIATE``: only the first one migrates, the others find v2 and do nothing.
    """
    if schema_version(conn) == SCHEMA_VERSION:
        return
    begin_immediate(conn)
    try:
        version = schema_version(conn)
        if version == "1":
            seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'insights'").fetchone()
            conn.execute("ALTER TABLE insights RENAME TO insights_v1")
            conn.execute(_INSIGHTS_TABLE)
            conn.execute(
                "INSERT INTO insights (id, kind, title, body, method_id, added) "
                "SELECT id, kind, title, body, method_id, added FROM insights_v1 ORDER BY id"
            )
            conn.execute("DROP TABLE insights_v1")
            if seq is not None:
                cur = conn.execute(
                    "UPDATE sqlite_sequence SET seq = max(seq, ?) WHERE name = 'insights'", (seq[0],)
                )
                if cur.rowcount == 0:
                    conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('insights', ?)", (seq[0],))
            for trigger in _INSIGHTS_TRIGGERS:
                conn.execute(trigger)
            conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (SCHEMA_VERSION,))
        elif version != SCHEMA_VERSION:
            raise LabError(
                f"lab database schema version {version!r} is unknown to this code (expects {SCHEMA_VERSION})"
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


# --------------------------------------------------------------------------- methods


def begin_immediate(conn: sqlite3.Connection) -> None:
    """Take the write lock now, so a read-then-write (next id, lab-wide N) is atomic across sessions."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")


def get_method(conn: sqlite3.Connection, method_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM methods WHERE id = ?", (method_id,)).fetchone()


def next_method_id(conn: sqlite3.Connection) -> str:
    """The next free ``M0001``-style id (one above the highest used)."""
    row = conn.execute(
        "SELECT max(CAST(substr(id, 2) AS INTEGER)) FROM methods WHERE id GLOB 'M[0-9][0-9][0-9][0-9]'"
    ).fetchone()
    return f"M{(row[0] or 0) + 1:04d}"


def add_method(
    conn: sqlite3.Connection,
    *,
    id: str,
    name: str,
    family: str,
    source_kind: str,
    hypothesis: str,
    source_ref: str = "",
    parent_id: str | None = None,
    status: str = "idea",
    analysis: str = "",
    verdict: str = "",
    allow_any_status: bool = False,
) -> None:
    """Insert a method. New lab methods start as ``idea`` or ``registered``; only the seed
    import (``allow_any_status``) inserts a closed historical record directly."""
    if not allow_any_status and status not in ("idea", "registered"):
        raise LabError(f"a new method starts as idea or registered, not {status}")
    if get_method(conn, id) is not None:
        raise LabError(f"method {id} already exists")
    stamp = now_iso()
    conn.execute(
        "INSERT INTO methods (id, name, family, parent_id, source_kind, source_ref, hypothesis, "
        "status, analysis, verdict, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (id, name, family, parent_id, source_kind, source_ref, hypothesis, status, analysis, verdict, stamp, stamp),
    )


def update_method(conn: sqlite3.Connection, method_id: str, **values: Any) -> None:
    """Set columns of one method (the triggers still apply) and bump ``updated``."""
    allowed = {"status", "verdict", "blocked_on", "source_sha", "hypothesis", "name", "family",
               "source_kind", "source_ref", "parent_id"}
    bad = set(values) - allowed
    if bad:
        raise LabError(f"cannot set {sorted(bad)} through update_method")
    if get_method(conn, method_id) is None:
        raise LabError(f"no method {method_id}")
    cols = ", ".join(f"{k} = ?" for k in values)
    try:
        conn.execute(
            f"UPDATE methods SET {cols}, updated = ? WHERE id = ?",
            (*values.values(), now_iso(), method_id),
        )
    except sqlite3.IntegrityError as e:
        raise LabError(f"{method_id}: {e}") from e


def append_analysis(conn: sqlite3.Connection, method_id: str, text: str) -> None:
    """Append a dated section to a method's analysis (never rewrites what is there)."""
    row = get_method(conn, method_id)
    if row is None:
        raise LabError(f"no method {method_id}")
    text = text.strip()
    if not text:
        raise LabError("empty analysis")
    head = f"### {date.today().isoformat()}\n\n"
    new = (row["analysis"] + "\n\n" if row["analysis"] else "") + head + text + "\n"
    conn.execute(
        "UPDATE methods SET analysis = ?, updated = ? WHERE id = ?", (new, now_iso(), method_id)
    )


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
      lab has not passed (the roster's admission rule is not the lab's gate: plan Decisions D5).

    ``hypothesis``, ``verdict``, ``parent_id`` and above all ``source_sha`` are never written.
    No ``trials`` row is inserted: a promotion is not a backtest and must not move the lab's N.

    Idempotent: a method whose ``analysis`` already carries ``PROMOTION_MARKER`` followed by
    ``strategy_id`` is already recorded, and this writes nothing and returns the current status.
    That is what lets the command be re-run to repair a half-finished promotion, since the roster
    (Neon) and the lab (SQLite) cannot share one transaction.

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

    retired = "" if retired_id is None else f", replacing `{retired_id}` (retired the same moment)"
    body = (
        f"{PROMOTION_MARKER}`{strategy_id}`{retired}.\n\n"
        f"Variant: `{candidate_id}`. Roster object: `{object_name}`. "
        f"Frozen spec digest: `{spec_digest}`.\n\n"
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



# --------------------------------------------------------------------------- trials


@dataclass(frozen=True)
class TrialRow:
    """One ``trials`` row before insertion (``n`` is assigned by SQLite)."""

    method_id: str
    candidate_id: str
    config_digest: str
    config_text: str
    rules_id: str
    allocator_id: str
    window: str
    start: str
    end: str
    store_fingerprint: str
    git_sha: str
    run_at: str
    total_return: float | None
    cagr: float | None
    max_drawdown: float | None
    profit_factor: float | None
    trades: int
    sharpe: float | None
    exposure: float | None
    turnover: float | None
    worst_year: int | None
    worst_year_return: float | None
    spy_tr_return: float | None
    spy_tr_cagr: float | None
    mar: float | None
    failed: str  # "; "-joined failure labels, "" when eligible
    eligible: bool
    dsr: float | None
    n_trials_at_run: int
    curve_json: str


TRIAL_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(TrialRow))


def has_trial(conn: sqlite3.Connection, config_digest: str, window: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM trials WHERE config_digest = ? AND window = ?", (config_digest, window)
        ).fetchone()
        is not None
    )


def insert_trials(conn: sqlite3.Connection, rows: Sequence[TrialRow]) -> list[int]:
    """Insert trials (the caller holds the transaction). Returns their trial numbers."""
    out: list[int] = []
    cols = ", ".join(f'"{c}"' for c in TRIAL_COLUMNS)
    marks = ", ".join("?" for _ in TRIAL_COLUMNS)
    for r in rows:
        if r.window not in WINDOWS:
            raise LabError(f"unknown window {r.window!r}")
        if has_trial(conn, r.config_digest, r.window):
            raise LabError(
                f"{r.candidate_id}: this configuration already has a {r.window} trial "
                "(no re-rolls: a change of params, rules or allocator is a new method)"
            )
        values = [getattr(r, c) for c in TRIAL_COLUMNS]
        values[TRIAL_COLUMNS.index("eligible")] = int(r.eligible)
        cur = conn.execute(f"INSERT INTO trials ({cols}) VALUES ({marks})", values)
        out.append(int(cur.lastrowid))
    return out


def dev_trial_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM trials WHERE window = 'dev'").fetchone()[0])


def test_looks(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM trials WHERE window = 'test'").fetchone()[0])


def dev_daily_sharpes(conn: sqlite3.Connection) -> list[float]:
    """Every dev trial's daily Sharpe (annualized Sharpe / sqrt(252)), for the DSR's variance."""
    rows = conn.execute("SELECT sharpe FROM trials WHERE window = 'dev' AND sharpe IS NOT NULL")
    return [float(r[0]) / math.sqrt(252) for r in rows]


def trials_of(conn: sqlite3.Connection, method_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM trials WHERE method_id = ? ORDER BY n", (method_id,)).fetchall()


# --------------------------------------------------------------------------- ideas_seen


def mark_seen(conn: sqlite3.Connection, key: str, method_id: str | None = None, note: str = "") -> bool:
    """Record a dedupe key; False when it was already there."""
    key = key.strip()
    if ":" not in key:
        raise LabError(f"a seen key looks like kind:value (url:…, concept:…), got {key!r}")
    cur = conn.execute(
        "INSERT OR IGNORE INTO ideas_seen (key, method_id, note, added) VALUES (?, ?, ?, ?)",
        (key, method_id, note, now_iso()),
    )
    return cur.rowcount == 1


def seen(conn: sqlite3.Connection, pattern: str) -> list[sqlite3.Row]:
    """Seen keys containing ``pattern`` (case-insensitive)."""
    return conn.execute(
        "SELECT * FROM ideas_seen WHERE lower(key) LIKE ? OR lower(note) LIKE ? ORDER BY key",
        (f"%{pattern.lower()}%", f"%{pattern.lower()}%"),
    ).fetchall()


# --------------------------------------------------------------------------- insights


def add_insight(conn: sqlite3.Connection, *, kind: str, title: str, body: str,
                method_id: str | None = None) -> int:
    """Append one entry to the lab journal: an observation across methods, a hypothesis worth
    testing, data or a feature the lab lacks, a risk, or a batch synthesis (the state of the
    search after a batch of methods). The food-for-thought record, shown at seertrade.site/sera."""
    if kind not in INSIGHT_KINDS:
        raise LabError(f"insight kind must be one of {INSIGHT_KINDS}, got {kind!r}")
    if method_id is not None and get_method(conn, method_id) is None:
        raise LabError(f"no method {method_id}")
    cur = conn.execute(
        "INSERT INTO insights (kind, title, body, method_id, added) VALUES (?, ?, ?, ?, ?)",
        (kind, title.strip(), body.strip(), method_id, now_iso()),
    )
    return int(cur.lastrowid)


# --------------------------------------------------------------------------- export


def _sheet_rows(conn: sqlite3.Connection, sql: str) -> tuple[list[str], list[list[Any]]]:
    cur = conn.execute(sql)
    header = [d[0] for d in cur.description]
    return header, [list(r) for r in cur.fetchall()]


LEADERBOARD_SQL = """
SELECT t.n, t.candidate_id, t.method_id, m.name AS method, m.family, t.window, t.start, t."end",
       t.total_return, t.spy_tr_return, t.cagr, t.max_drawdown, t.profit_factor, t.trades,
       t.sharpe, t.mar, t.dsr, t.n_trials_at_run, t.eligible, t.failed
FROM trials t JOIN methods m ON m.id = t.method_id
ORDER BY t.mar IS NULL, t.mar DESC, t.n
"""


def export_xlsx(conn: sqlite3.Connection, path: Path = XLSX_PATH) -> Path:
    """Write the lab as a workbook: summary, leaderboard, methods, trials (without curves), ideas_seen."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    summary = wb.active
    summary.title = "summary"
    for row in summary_rows(conn):
        summary.append(list(row))
    trial_cols = ", ".join(f't."{c}"' for c in ("n",) + TRIAL_COLUMNS if c != "curve_json")
    sheets = (
        ("leaderboard", LEADERBOARD_SQL),
        ("methods", "SELECT * FROM methods ORDER BY id"),
        ("trials", f"SELECT {trial_cols} FROM trials t ORDER BY t.n"),
        ("ideas_seen", "SELECT * FROM ideas_seen ORDER BY key"),
        ("insights", "SELECT * FROM insights ORDER BY id"),
    )
    for title, sql in sheets:
        ws = wb.create_sheet(title)
        header, rows = _sheet_rows(conn, sql)
        ws.append(header)
        for r in rows:
            ws.append([None if isinstance(v, float) and not math.isfinite(v) else v for v in r])
        ws.freeze_panes = "A2"
        for i, name in enumerate(header, start=1):
            ws.column_dimensions[get_column_letter(i)].width = min(60, max(10, len(name) + 2))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def summary_rows(conn: sqlite3.Connection) -> list[tuple[str, Any]]:
    by_status = conn.execute("SELECT status, count(*) FROM methods GROUP BY status ORDER BY status").fetchall()
    out: list[tuple[str, Any]] = [
        ("dev trials (N for the DSR)", dev_trial_count(conn)),
        ("test-window looks used", test_looks(conn)),
        ("methods", int(conn.execute("SELECT count(*) FROM methods").fetchone()[0])),
        ("insights", int(conn.execute("SELECT count(*) FROM insights").fetchone()[0])),
    ]
    out += [(f"methods {r[0]}", r[1]) for r in by_status]
    return out


def curve_json(curve: Iterable[tuple[date, float]]) -> str:
    return json.dumps([[d.isoformat(), round(v, 6)] for d, v in curve], separators=(",", ":"))


def as_mapping(row: sqlite3.Row) -> Mapping[str, Any]:
    return {k: row[k] for k in row.keys()}


# --------------------------------------------------------------------------- web snapshot

SNAPSHOT_VERSION = 1
EXPECTED_FAILURE_SEP = "\n\nExpected failure: "  # how lab ideas write their hypothesis


def snapshot_path(db: Path) -> Path:
    """The web snapshot of a database: ``<repo>/web/data/lab.json`` for ``<repo>/lab/lab.sqlite``.

    Derived from the database's own checkout, not from this code's: a worktree session with
    ``SEER_LAB_DB`` pointing at the main checkout writes the snapshot into that checkout, next to
    the database it exports, and ``lab stage`` stages both there."""
    return Path(db).resolve().parent.parent / "web" / "data" / "lab.json"


def _num(x: Any) -> float | None:
    """A JSON-safe number: None and non-finite values become None, the rest rounds to 6 dp."""
    if x is None:
        return None
    x = float(x)
    return round(x, 6) if math.isfinite(x) else None


def _dicts(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    """Rows as dicts, whatever the connection's row_factory."""
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _snapshot_method(m: Mapping[str, Any]) -> dict[str, Any]:
    hypothesis, sep, expected = m["hypothesis"].partition(EXPECTED_FAILURE_SEP)
    return {
        "id": m["id"],
        "name": m["name"],
        "family": m["family"],
        "parentId": m["parent_id"],
        "sourceKind": m["source_kind"],
        "sourceRef": m["source_ref"],
        "hypothesis": hypothesis,
        "expectedFailure": expected if sep else None,
        "status": m["status"],
        "analysis": m["analysis"],
        "verdict": m["verdict"],
        "blockedOn": m["blocked_on"],
        "created": m["created"],
        "updated": m["updated"],
        "historical": m["id"].startswith("H-"),
    }


def _snapshot_curve(text: str) -> list[list[Any]]:
    out: list[list[Any]] = []
    for day, value in json.loads(text):
        v = _num(value)
        if v is not None:
            out.append([str(day), v])
    return out


def _snapshot_trial(t: Mapping[str, Any]) -> dict[str, Any]:
    pf = t["profit_factor"]
    return {
        "n": int(t["n"]),
        "methodId": t["method_id"],
        "candidateId": t["candidate_id"],
        "rulesId": t["rules_id"],
        "allocatorId": t["allocator_id"],
        "configText": t["config_text"],
        "window": t["window"],
        "start": t["start"],
        "end": t["end"],
        "gitSha": t["git_sha"],
        "runAt": t["run_at"],
        "totalReturn": _num(t["total_return"]),
        "cagr": _num(t["cagr"]),
        "maxDrawdown": _num(t["max_drawdown"]),
        "profitFactor": _num(pf),
        "pfInfinite": pf is not None and float(pf) == math.inf,
        "trades": int(t["trades"]),
        "sharpe": _num(t["sharpe"]),
        "exposure": _num(t["exposure"]),
        "turnover": _num(t["turnover"]),
        "worstYear": None if t["worst_year"] is None else int(t["worst_year"]),
        "worstYearReturn": _num(t["worst_year_return"]),
        "spyTrReturn": _num(t["spy_tr_return"]),
        "spyTrCagr": _num(t["spy_tr_cagr"]),
        "mar": _num(t["mar"]),
        "failed": [f for f in t["failed"].split("; ") if f],
        "eligible": bool(t["eligible"]),
        "dsr": _num(t["dsr"]),
        "nTrialsAtRun": int(t["n_trials_at_run"]),
        "curve": _snapshot_curve(t["curve_json"]),
    }


def snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    """The whole lab as the web's ``LabSnapshot`` (SERA_LAB_SITE_PLAN.md Interface Contract).

    Deterministic: the same database gives the same value; there is no wall-clock time in it
    (``asOf`` is the latest timestamp found in the data, "" for an empty lab). Reads only what
    schema v1 and v2 share and never touches ``meta``, so it works on a read-only connection to
    a database that has not been migrated. Gate and data facts come from the engine's constants.
    """
    from seer_engine import dates, research
    from seer_engine.backtest import dev, tuning
    from seer_engine.lab import seed

    def count(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    by_status: dict[str, int] = dict.fromkeys(STATUSES, 0)
    for status, n in conn.execute("SELECT status, count(*) FROM methods GROUP BY status ORDER BY status"):
        by_status[str(status)] = int(n)
    as_of = conn.execute(
        "SELECT max(ts) FROM (SELECT max(updated) AS ts FROM methods UNION ALL "
        "SELECT max(run_at) FROM trials UNION ALL SELECT max(added) FROM insights UNION ALL "
        "SELECT max(added) FROM ideas_seen)"
    ).fetchone()[0]
    bench = seed.benchmark_curves()
    return {
        "version": SNAPSHOT_VERSION,
        "asOf": as_of or "",
        "gate": {
            "maxDrawdown": tuning.MAX_DRAWDOWN,
            "minProfitFactor": tuning.MIN_PROFIT_FACTOR,
            "minTrades": dev._MIN_TRADES,
            "dsrMin": DSR_MIN,
            "devStart": research.STORE_START.isoformat(),
            "devEnd": dev.DEV_END.isoformat(),
            "testStart": dates.next_session(dev.DEV_END).isoformat(),
        },
        "data": {
            "storeStart": research.STORE_START.isoformat(),
            "membershipStart": dev.MEMBERSHIP_START.isoformat(),
            "fxStart": dev.FX_START.isoformat(),
            "fingerprints": [
                str(r[0]) for r in conn.execute(
                    "SELECT DISTINCT store_fingerprint FROM trials ORDER BY store_fingerprint"
                )
            ],
            "barRows": seed.P7A_BAR_ROWS,
            "symbolsRequested": seed.P7A_SYMBOLS_REQUESTED,
            "symbolsServed": seed.P7A_SYMBOLS_SERVED,
            "dividendRows": seed.P7A_DIVIDEND_ROWS,
        },
        "summary": {
            "devTrials": count("SELECT count(*) FROM trials WHERE window = 'dev'"),
            "testLooks": count("SELECT count(*) FROM trials WHERE window = 'test'"),
            "methods": count("SELECT count(*) FROM methods"),
            "labMethods": count("SELECT count(*) FROM methods WHERE id GLOB 'M*'"),
            "historicalMethods": count("SELECT count(*) FROM methods WHERE id GLOB 'H-*'"),
            "insights": count("SELECT count(*) FROM insights"),
            "byStatus": by_status,
        },
        "benchmark": {
            "spyTr": [[d, v] for d, v in bench["spy_tr"]],
            "spyPrice": [[d, v] for d, v in bench["spy_price"]],
        },
        "methods": [_snapshot_method(m) for m in _dicts(conn, "SELECT * FROM methods ORDER BY id")],
        "trials": [_snapshot_trial(t) for t in _dicts(conn, "SELECT * FROM trials ORDER BY n")],
        "insights": [
            {"id": int(i["id"]), "kind": i["kind"], "title": i["title"], "body": i["body"],
             "methodId": i["method_id"], "added": i["added"]}
            for i in _dicts(conn, "SELECT * FROM insights ORDER BY id")
        ],
        "ideasSeen": [
            {"key": s["key"], "methodId": s["method_id"], "note": s["note"], "added": s["added"]}
            for s in _dicts(conn, "SELECT * FROM ideas_seen ORDER BY key")
        ],
    }


def snapshot_json(conn: sqlite3.Connection) -> str:
    """``snapshot`` as the exact bytes of ``web/data/lab.json``: compact, key order as built,
    UTF-8 kept, one trailing newline. ``allow_nan=False``: a stray NaN/inf fails loudly."""
    return json.dumps(snapshot(conn), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"


def write_snapshot(conn: sqlite3.Connection, path: Path) -> bool:
    """Write ``snapshot_json(conn)`` to ``path`` (temp file + atomic replace). False when the
    file already held exactly that, in which case it is left untouched."""
    data = snapshot_json(conn).encode("utf-8")
    path = Path(path)
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True
