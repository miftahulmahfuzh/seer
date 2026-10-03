"""Apply db/migrations/*.sql in name order, each once.

The Python twin of web/scripts/migrate.mjs: same ``schema_migrations`` table, same key
(the file name), one transaction per file, so either runner can apply any migration and
neither re-applies the other's work. Under --dry-run every pending file is applied inside
a single transaction (later files may depend on earlier ones) that is then rolled back.
"""

from __future__ import annotations

import argparse
import logging
from contextlib import closing
from pathlib import Path

import psycopg

from seer_engine import config, db

HELP = "apply pending db/migrations/*.sql (shares schema_migrations with web's db:migrate)"

MIGRATIONS_DIR = config.REPO_ROOT / "db" / "migrations"

log = logging.getLogger(__name__)

_CREATE_TABLE = """CREATE TABLE IF NOT EXISTS schema_migrations (
  name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"""


def migration_files(migrations_dir: Path) -> list[Path]:
    """``*.sql`` files in ``migrations_dir`` sorted by file name."""
    return sorted(
        (p for p in migrations_dir.iterdir() if p.is_file() and p.suffix == ".sql"),
        key=lambda p: p.name,
    )


def _applied(conn: psycopg.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM schema_migrations").fetchall()}


def _apply_one(conn: psycopg.Connection, path: Path) -> None:
    conn.execute(path.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


def apply_migrations(
    conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR, dry_run: bool = False
) -> list[str]:
    """Apply every pending migration; return the file names applied (or, under dry_run,
    the names that would be applied)."""
    files = migration_files(migrations_dir)
    done: list[str] = []
    if dry_run:
        try:
            conn.execute(_CREATE_TABLE)
            applied = _applied(conn)
            for path in files:
                if path.name in applied:
                    log.info("skip  %s", path.name)
                    continue
                _apply_one(conn, path)
                done.append(path.name)
                log.info("would apply %s", path.name)
        finally:
            conn.rollback()
        return done

    with db.transaction(conn, dry_run=False):
        conn.execute(_CREATE_TABLE)
    with db.transaction(conn, dry_run=False):
        applied = _applied(conn)
    for path in files:
        if path.name in applied:
            log.info("skip  %s", path.name)
            continue
        with db.transaction(conn, dry_run=False):
            _apply_one(conn, path)
        done.append(path.name)
        log.info("apply %s", path.name)
    return done


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--dir",
        type=Path,
        default=MIGRATIONS_DIR,
        help=f"migrations directory (default: {MIGRATIONS_DIR})",
    )


def run(args: argparse.Namespace) -> int:
    # closing(), not the connection's own context manager: that one commits on exit.
    with closing(db.connect()) as conn:
        names = apply_migrations(conn, args.dir, dry_run=args.dry_run)
    if not names:
        log.info("nothing to apply")
    return 0
