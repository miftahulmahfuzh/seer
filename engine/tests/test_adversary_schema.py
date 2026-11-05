"""Migration 027 (Seer Adversarial): the tables, their checks, the append-only verdicts, A-GT.

Every row in this file is written straight in SQL: the schema is what is under test, and mcp-notes
(not this repo) is the writer of the three adversary tables.
"""

from __future__ import annotations

from datetime import date

import psycopg
import pytest
from psycopg.types.json import Jsonb

SESSION = date(2026, 11, 4)
NIGHT = date(2026, 11, 3)
SOURCES = [
    {
        "url": "https://www.sec.gov/Archives/edgar/data/0000000000/000000000000000000/x8k.htm",
        "title": "Form 8-K",
        "publisher": "SEC",
        "published_at": "2026-11-03T21:05:00Z",
        "fetched_at": "2026-11-04T08:01:00Z",
    }
]


def columns(pg, table):
    return [
        r[0]
        for r in pg.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
            (table,),
        ).fetchall()
    ]


def verdict(
    pg,
    *,
    symbol="NVDA",
    verdict="object",
    reason="The drop follows a lowered forecast, which is news, not noise.",
    sources=SOURCES,
    started="2026-11-04T08:00:00Z",
    decided="2026-11-04T08:05:00Z",
    strategy="C-GT",
    session=SESSION,
) -> int:
    return pg.execute(
        "INSERT INTO adversary_verdicts (strategy_id, session_date, symbol, verdict, reason, sources, lens, "
        "model, prompt_version, host, started_at, decided_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'a-dip@1', 'claude-opus-x', 'pv-1', 'lenovo', %s, %s) RETURNING id",
        (strategy, session, symbol, verdict, reason, Jsonb(sources), started, decided),
    ).fetchone()[0]


def refused(pg, error, sql, params=(), match=None):
    with pytest.raises(error, match=match):
        pg.execute(sql, params)
    pg.rollback()


# ---- shape ---------------------------------------------------------------------------------------


def test_027_adds_every_c1_table_and_column(pg):
    assert columns(pg, "strategy_candidates") == [
        "strategy_id", "session_date", "data_date", "kind", "rank", "symbol", "weight", "evidence", "created_at",
    ]
    assert columns(pg, "adversary_verdicts") == [
        "id", "strategy_id", "session_date", "symbol", "verdict", "reason", "sources", "lens", "model",
        "prompt_version", "host", "started_at", "decided_at", "superseded_by", "created_at",
    ]
    assert columns(pg, "adversary_marks") == ["strategy_id", "session_date", "mark", "host", "created_at"]
    assert columns(pg, "adversary_leases") == ["strategy_id", "session_date", "host", "claimed_at", "expires_at"]
    assert "twin_of" in columns(pg, "strategies")
    assert columns(pg, "book_previews")[-1] == "next_decision_session"


def test_027_admits_a_gt_with_no_clock_and_inserts_no_twin(pg):
    row = pg.execute(
        "SELECT engine, rules_id, object_name, status, paper_start, params, twin_of, is_benchmark, "
        "is_champion, gate_applicable, promoted_from, sort FROM strategies WHERE id = 'A-GT'"
    ).fetchone()
    assert row == ("bracket", "design-v0-gotrade", "STRATEGY_A", "active", None, {}, None, False, False, True, None, 5)
    assert pg.execute("SELECT count(*) FROM strategies WHERE twin_of IS NOT NULL").fetchone()[0] == 0
    # plain A stays retired, on its own flat-fee rule set, with every row it wrote
    assert pg.execute("SELECT status, rules_id FROM strategies WHERE id = 'A'").fetchone() == ("retired", "design-v0")


# ---- twins ---------------------------------------------------------------------------------------


def add_twin(pg, sid, of, status="active"):
    pg.execute(
        "INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, "
        "object_name, gate_note, gate_applicable, status, twin_of) "
        "SELECT %s, name, sub, icon, false, false, 90, engine, rules_id, object_name, gate_note, false, %s, id "
        "FROM strategies WHERE id = %s",
        (sid, status, of),
    )


def test_an_original_has_at_most_one_active_twin(pg):
    add_twin(pg, "A-GT-CX", "A-GT")
    pg.commit()
    refused(pg, psycopg.errors.UniqueViolation,
            "INSERT INTO strategies (id, name, sub, icon, sort, engine, rules_id, object_name, gate_note, twin_of) "
            "VALUES ('A-GT-CX2', 'x', 'x', 'x', 91, 'bracket', 'design-v0-gotrade', 'STRATEGY_A', 'x', 'A-GT')")
    # a retired twin beside an active one is history, not a second twin
    add_twin(pg, "A-GT-CX0", "A-GT", status="retired")
    pg.commit()
    assert pg.execute("SELECT count(*) FROM strategies WHERE twin_of = 'A-GT'").fetchone()[0] == 2


def test_a_twin_names_a_real_original_and_never_itself(pg):
    refused(pg, psycopg.errors.CheckViolation, "UPDATE strategies SET twin_of = id WHERE id = 'A-GT'")
    refused(pg, psycopg.errors.ForeignKeyViolation, "UPDATE strategies SET twin_of = 'NOPE' WHERE id = 'A'")


# ---- strategy_candidates -----------------------------------------------------------------------------

INSERT_CANDIDATE = (
    "INSERT INTO strategy_candidates (strategy_id, session_date, data_date, kind, rank, symbol, weight) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


def test_a_candidate_row_is_a_bracket_rank_or_a_weighted_book_target(pg):
    pg.execute(INSERT_CANDIDATE, ("A-GT", SESSION, NIGHT, "bracket", 1, "NVDA", None))
    pg.execute(INSERT_CANDIDATE, ("COSK-FR-GT", SESSION, NIGHT, "book", 1, "XOM", "0.05"))
    pg.commit()
    refused(pg, psycopg.errors.CheckViolation, INSERT_CANDIDATE, ("A-GT", SESSION, NIGHT, "bracket", 2, "AAPL", "0.5"))
    refused(pg, psycopg.errors.CheckViolation, INSERT_CANDIDATE, ("COSK-FR-GT", SESSION, NIGHT, "book", 2, "CVX", None))
    refused(pg, psycopg.errors.CheckViolation, INSERT_CANDIDATE, ("COSK-FR-GT", SESSION, NIGHT, "book", 2, "CVX", "1.5"))
    refused(pg, psycopg.errors.CheckViolation, INSERT_CANDIDATE, ("A-GT", SESSION, NIGHT, "veto", 2, "AAPL", None))
    refused(pg, psycopg.errors.CheckViolation, INSERT_CANDIDATE, ("A-GT", SESSION, NIGHT, "bracket", 0, "AAPL", None))
    refused(pg, psycopg.errors.CheckViolation, INSERT_CANDIDATE, ("A-GT", SESSION, SESSION, "bracket", 2, "AAPL", None))
    refused(pg, psycopg.errors.UniqueViolation, INSERT_CANDIDATE, ("A-GT", SESSION, NIGHT, "bracket", 1, "AAPL", None))
    refused(pg, psycopg.errors.UniqueViolation, INSERT_CANDIDATE, ("A-GT", SESSION, NIGHT, "bracket", 2, "NVDA", None))
    refused(pg, psycopg.errors.ForeignKeyViolation, INSERT_CANDIDATE, ("NOPE", SESSION, NIGHT, "bracket", 1, "NVDA", None))


def test_a_preview_names_a_rank_session_after_its_own_night(pg):
    sql = (
        "INSERT INTO book_previews (strategy_id, data_date, rank, symbol, weight, last, next_decision_session) "
        "VALUES ('COSK-FR-GT', %s, 1, 'XOM', 0.05, 110, %s)"
    )
    pg.execute(sql, (NIGHT, date(2026, 12, 1)))
    pg.rollback()
    refused(pg, psycopg.errors.CheckViolation, sql, (NIGHT, NIGHT))


# ---- adversary_verdicts ----------------------------------------------------------------------------


def test_a_verdict_must_cite_a_source_unless_it_cannot_tell(pg):
    verdict(pg, verdict="unsure", sources=[])
    verdict(pg, symbol="AAPL", verdict="agree")
    pg.commit()
    for v in ("object", "agree"):
        with pytest.raises(psycopg.errors.CheckViolation):
            verdict(pg, symbol="MSFT", verdict=v, sources=[])
        pg.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):  # an object, not an array: refused, not an error
        verdict(pg, symbol="MSFT", verdict="unsure", sources={"url": "https://example.com"})
    pg.rollback()


def test_a_verdict_is_short_plain_ordered_in_time_and_one_of_three(pg):
    verdict(pg, reason="x" * 600)
    pg.commit()
    for kwargs in ({"reason": ""}, {"reason": "x" * 601}, {"verdict": "veto"},
                   {"started": "2026-11-04T08:05:00Z", "decided": "2026-11-04T08:00:00Z"}):
        with pytest.raises(psycopg.errors.CheckViolation):
            verdict(pg, symbol="MSFT", **kwargs)
        pg.rollback()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        verdict(pg, strategy="NOPE")
    pg.rollback()


def test_a_verdict_is_never_deleted_or_rewritten(pg):
    vid = verdict(pg)
    pg.commit()
    before = pg.execute("SELECT to_jsonb(v) FROM adversary_verdicts v WHERE id = %s", (vid,)).fetchone()
    refused(pg, psycopg.errors.RaiseException, "DELETE FROM adversary_verdicts WHERE id = %s", (vid,), match="append-only")
    for sql in (
        "UPDATE adversary_verdicts SET reason = 'rewritten after the fact' WHERE id = %s",
        "UPDATE adversary_verdicts SET verdict = 'agree' WHERE id = %s",
        "UPDATE adversary_verdicts SET decided_at = decided_at - interval '1 hour' WHERE id = %s",
    ):
        refused(pg, psycopg.errors.RaiseException, sql, (vid,), match="append-only")
    assert pg.execute("SELECT to_jsonb(v) FROM adversary_verdicts v WHERE id = %s", (vid,)).fetchone() == before


def test_a_re_review_supersedes_the_old_verdict_once_and_keeps_it(pg):
    old = verdict(pg, verdict="object")
    new = verdict(pg, verdict="agree", started="2026-11-04T09:00:00Z", decided="2026-11-04T09:04:00Z")
    pg.commit()
    pg.execute("UPDATE adversary_verdicts SET superseded_by = %s WHERE id = %s", (new, old))
    pg.commit()
    assert pg.execute("SELECT id, verdict, superseded_by FROM adversary_verdicts ORDER BY id").fetchall() == [
        (old, "object", new),
        (new, "agree", None),
    ]
    third = verdict(pg, verdict="unsure", sources=[], started="2026-11-04T10:00:00Z", decided="2026-11-04T10:01:00Z")
    pg.commit()
    refused(pg, psycopg.errors.RaiseException,
            "UPDATE adversary_verdicts SET superseded_by = %s WHERE id = %s", (third, old), match="already superseded")


def test_only_a_later_verdict_on_the_same_pick_can_supersede(pg):
    nvda = verdict(pg)
    aapl = verdict(pg, symbol="AAPL")
    later_nvda = verdict(pg, decided="2026-11-04T08:30:00Z")
    pg.commit()
    match = "superseded by a later verdict"
    refused(pg, psycopg.errors.RaiseException,
            "UPDATE adversary_verdicts SET superseded_by = %s WHERE id = %s", (aapl, nvda), match=match)
    refused(pg, psycopg.errors.RaiseException,
            "UPDATE adversary_verdicts SET superseded_by = %s WHERE id = %s", (nvda, later_nvda), match=match)
    refused(pg, psycopg.errors.RaiseException,
            "UPDATE adversary_verdicts SET superseded_by = %s WHERE id = %s", (nvda, nvda), match=match)


# ---- marks and leases ------------------------------------------------------------------------------


def test_a_paused_mark_is_once_per_decision(pg):
    sql = (
        "INSERT INTO adversary_marks (strategy_id, session_date, mark, host) VALUES ('C-GT', %s, %s, 'gpd') "
        "ON CONFLICT (strategy_id, session_date) DO NOTHING"
    )
    assert pg.execute(sql, (SESSION, "paused")).rowcount == 1
    assert pg.execute(sql, (SESSION, "paused")).rowcount == 0
    pg.commit()
    refused(pg, psycopg.errors.CheckViolation, sql, (NIGHT, "absent"))


CLAIM = """
INSERT INTO adversary_leases (strategy_id, session_date, host, expires_at)
VALUES ('C-GT', %(session)s, %(host)s, now() + interval '20 minutes')
ON CONFLICT (strategy_id, session_date) DO UPDATE
  SET host = EXCLUDED.host, claimed_at = now(), expires_at = EXCLUDED.expires_at
  WHERE adversary_leases.expires_at < now() OR adversary_leases.host = EXCLUDED.host
RETURNING host
"""


def claim(pg, host):
    row = pg.execute(CLAIM, {"session": SESSION, "host": host}).fetchone()
    pg.commit()
    return None if row is None else row[0]


def test_contract_c4s_lease_claim_holds_on_this_schema(pg):
    """The claim statement mcp-notes runs (plan C4), against the table 027 makes: one host at a
    time, the holder may renew, and an expired lease -- by this database's clock -- passes on."""
    assert claim(pg, "lenovo") == "lenovo"
    assert claim(pg, "gpd") is None
    assert claim(pg, "lenovo") == "lenovo"
    pg.execute("UPDATE adversary_leases SET expires_at = now() - interval '1 minute'")
    pg.commit()
    assert claim(pg, "gpd") == "gpd"
