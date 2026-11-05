"""Seed a verify-seer run's OWN database so a real `paper` night can run, and file test verdicts.

Usage (from the checkout being verified):
  engine/.venv/bin/python .claude/skills/verify-seer/features/steps/twin-world.py world RUN
  engine/.venv/bin/python .claude/skills/verify-seer/features/steps/twin-world.py verdict RUN ORIGINAL SESSION SYMBOL VERDICT DECIDED_AT

`world` writes the engine suite's synthetic market -- tests/test_paper_command.py: 24 random-walk
stocks and SPY, 2025-01-02..2026-10-09, USD/IDR, an SP500 universe, one SPY dividend -- and the
successful bars-run row `nightly` would write for each night 2026-09-23..2026-10-02. `verdict`
inserts one adversary_verdicts row the way mcp-notes' reviewer does (migration 027).

Why a script and not `verify.sh sql`: `sql` is read-only on purpose, and a real night needs bars
that only a 10-year backfill or this fixture can give. The URL comes from the run's own
engine.env and anything that is not a verify-seer run database (127.0.0.1:55437/v_*) is refused,
so this can never reach Neon.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / "engine" / "src"), str(ROOT / "engine" / "tests")]

import psycopg  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

import test_paper_command as tp  # noqa: E402
from seer_engine import bars, dates, fx  # noqa: E402

VERIFY_HOME = Path(os.environ.get("VERIFY_HOME", str(Path.home() / ".local" / "state" / "seer-verify")))
RUN_DB = "postgresql://postgres@127.0.0.1:55437/v_"
NIGHTS = tuple(dates.sessions(date(2026, 9, 23), date(2026, 10, 2)))


def run_url(run: str) -> str:
    env = VERIFY_HOME / run / "engine.env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip()
            if not url.startswith(RUN_DB):
                sys.exit(f"refusing {url!r}: not a verify-seer run database")
            return url
    sys.exit(f"no DATABASE_URL in {env}")


def world(conn: psycopg.Connection) -> str:
    bars.upsert_bars(conn, tp.synthetic_bars())
    fx.upsert_fx(conn, [(d, tp.fx_rate(d)) for d in tp._sessions()])
    for s in tp.STOCKS:
        conn.execute(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
            "VALUES (%s, 'SP500', '2020-01-02', NULL, %s) ON CONFLICT DO NOTHING",
            (s, s),
        )
    conn.execute(
        "INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s) ON CONFLICT DO NOTHING",
        (tp.DIV_DATE, tp.DIV_AMT),
    )
    for d in NIGHTS:
        rd = dates.run_dates(datetime(d.year, d.month, d.day, 23, tzinfo=timezone.utc))
        conn.execute(
            "INSERT INTO runs (status, data_date, session_date, is_demo, finished_at) "
            "VALUES ('success', %s, %s, false, now()) ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING",
            (rd.data_date, rd.session_date),
        )
    return f"{len(tp.STOCKS) + 1} symbols of bars, {len(NIGHTS)} bars runs ({NIGHTS[0]}..{NIGHTS[-1]})"


def verdict(conn: psycopg.Connection, original: str, session: str, symbol: str, what: str, decided: str) -> str:
    decided_at = datetime.fromisoformat(decided)
    if decided_at.utcoffset() is None:
        sys.exit("DECIDED_AT needs a UTC offset, e.g. 2026-10-01T12:00:00+00:00")
    sources = [] if what == "unsure" else [{
        "url": "https://example.invalid/verify-seer",
        "title": "verify-seer fixture",
        "publisher": "verify-seer",
        "published_at": None,
        "fetched_at": decided_at.isoformat(),
    }]
    (vid,) = conn.execute(
        "INSERT INTO adversary_verdicts (strategy_id, session_date, symbol, verdict, reason, sources, lens, "
        "model, prompt_version, host, started_at, decided_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            original, date.fromisoformat(session), symbol, what, "verify-seer fixture verdict.", Jsonb(sources),
            "verify@1", "verify-model", "verify-v1", "verify-seer", decided_at - timedelta(minutes=5), decided_at,
        ),
    ).fetchone()
    return f"adversary_verdicts id {vid}: {original} {session} {symbol} {what}, decided {decided_at.isoformat()}"


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "world":
        cmd, run, rest = "world", argv[1], argv[2:]
    elif len(argv) == 7 and argv[0] == "verdict":
        cmd, run, rest = "verdict", argv[1], argv[2:]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    with psycopg.connect(run_url(run)) as conn:
        out = world(conn) if cmd == "world" else verdict(conn, *rest)
        conn.commit()
    print(f"seeded {run}: {out}" if cmd == "world" else out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
