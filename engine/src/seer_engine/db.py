"""Postgres connection and the one transaction helper every write goes through."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from seer_engine import config

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 15


def connect(url: str | None = None) -> psycopg.Connection:
    """Open a connection with autocommit off.

    ``url`` defaults to DATABASE_URL_UNPOOLED (Neon's direct endpoint; the pooled one does
    not support session state such as temp tables). Tests pass their own URL.
    """
    dsn = url or config.require("DATABASE_URL_UNPOOLED")
    return psycopg.connect(dsn, autocommit=False, connect_timeout=CONNECT_TIMEOUT_S)


@contextmanager
def transaction(conn: psycopg.Connection, dry_run: bool) -> Iterator[psycopg.Connection]:
    """Run the block in one transaction: commit on success, roll back on error.

    With ``dry_run`` the block runs in full (every read and every write statement) and is
    then rolled back, so nothing persists.
    """
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    if dry_run:
        conn.rollback()
        log.info("dry-run: transaction rolled back")
    else:
        conn.commit()
