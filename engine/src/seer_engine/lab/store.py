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
SCHEMA_VERSION = "1"

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
INSIGHT_KINDS: tuple[str, ...] = ("observation", "hypothesis", "data-wish", "feature-wish", "risk")
DSR_MIN = 0.95  # lab eligibility on the dev window, on top of the five P7a D8 conditions
DSR_LABEL = "DSR >= 0.95"


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


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

CREATE TABLE IF NOT EXISTS insights (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT NOT NULL CHECK (kind IN ({_quoted(INSIGHT_KINDS)})),
    title     TEXT NOT NULL CHECK (length(trim(title)) > 0),
    body      TEXT NOT NULL CHECK (length(trim(body)) > 0),
    method_id TEXT REFERENCES methods(id),
    added     TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS insights_no_update BEFORE UPDATE ON insights
BEGIN SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead'); END;

CREATE TRIGGER IF NOT EXISTS insights_no_delete BEFORE DELETE ON insights
BEGIN SELECT RAISE(ABORT, 'insights are append-only'); END;

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
    """Open (creating when missing) the lab database with the schema, triggers and transitions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120)  # parallel explorer sessions share one file
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = DELETE")
    with conn:
        conn.executescript(_SCHEMA)
        conn.executemany("INSERT OR IGNORE INTO transitions (src, dst) VALUES (?, ?)", TRANSITIONS)
        conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
        )
    return conn


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
    testing, data or a feature the lab lacks, or a risk. The food-for-thought record."""
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
