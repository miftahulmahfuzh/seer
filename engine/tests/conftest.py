"""Shared fixtures.

DB tests need a real Postgres at PG_TEST_URL. Locally::

    docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
    export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres

Each DB test gets its own throwaway schema (``t_<hex>``), dropped afterwards, so tests
never see each other's rows and never touch ``public``.

Native thread pools are capped at one thread before numpy, scipy or scikit-learn load.
The suite's arrays are small, so the pools buy nothing alone, and several suites running
at once (one per swarm phase) oversubscribed 24 cores into ~200x slowdowns. An explicit
value in the environment still wins.
"""

from __future__ import annotations

import os

for _var in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_var, "1")

import logging
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from seer_engine import config

MIGRATIONS_DIR = config.REPO_ROOT / "db" / "migrations"

_PG_TEST_URL = os.environ.get("PG_TEST_URL")
_SKIP_REASON = (
    "PG_TEST_URL is not set; start Postgres with "
    "`docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16` and "
    "export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres"
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Keep every test away from the real .env.local and the real Neon database."""
    missing = tmp_path_factory.getbasetemp() / "no-such.env"
    monkeypatch.setenv("SEER_ENV_FILE", str(missing))
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", "postgresql://tests-must-not-use-this.invalid/none")
    monkeypatch.setattr(config, "_loaded", False)


@pytest.fixture(autouse=True)
def _drop_cli_log_handler() -> Iterator[None]:
    """cli.main() installs a stderr handler bound to the current (captured) stream;
    remove it after each test so later tests never log to a closed stream."""
    yield
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_seer_engine_handler", False):
            root.removeHandler(h)


@dataclass(frozen=True)
class PgSchema:
    conn: psycopg.Connection
    name: str
    url: str  # conninfo that lands in this schema; for code that opens its own connection


@pytest.fixture
def pg_url() -> str:
    if not _PG_TEST_URL:
        pytest.skip(_SKIP_REASON)
    return _PG_TEST_URL


@pytest.fixture
def pg_schema(pg_url: str) -> Iterator[PgSchema]:
    """A connection whose search_path is a fresh, empty schema (no migrations applied)."""
    name = f"t_{uuid.uuid4().hex[:12]}"
    conn = psycopg.connect(pg_url, autocommit=False, connect_timeout=15)
    conn.execute(f'CREATE SCHEMA "{name}"')
    conn.execute(f'SET search_path TO "{name}"')
    conn.commit()  # a SET inside a rolled-back transaction would be undone
    try:
        yield PgSchema(conn, name, make_conninfo(pg_url, options=f"-c search_path={name}"))
    finally:
        conn.close()
        with psycopg.connect(pg_url, autocommit=True, connect_timeout=15) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


@pytest.fixture
def pg_empty(pg_schema: PgSchema) -> psycopg.Connection:
    """Connection to an empty throwaway schema."""
    return pg_schema.conn


@pytest.fixture
def pg(pg_schema: PgSchema) -> psycopg.Connection:
    """Connection to a throwaway schema with every db/migrations/*.sql applied, committed."""
    conn = pg_schema.conn
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name):
        conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()
    return conn


@pytest.fixture
def utc() -> Callable[..., datetime]:
    """Fixed-clock factory: utc(2026, 10, 2, 23) -> 2026-10-02T23:00:00+00:00."""

    def make(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

    return make
