"""Tests for the fundamentals command: scope selection, dated CIK resolution, batching and
resume, restatements, the tag allowlist, the filed cutoff, idempotency, dry run, and the
exit-code contract. No test touches the network -- the SEC client is an injected fake -- and
none of them creates a single row in ``bars``: a symbol with no price history must still get
its fundamentals (Gap A independence).

Two helpers carry every cross-phase assumption, so a contract change is a one-place fix:
``fact()`` is the only place ``sec.Fact``'s field names appear, and ``Mapping`` is the only
place the phase-1 CIK row shape appears.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pytest

from seer_engine import cik as cik_mod
from seer_engine import sec
from seer_engine.commands import fundamentals as fcmd

SINCE = date(2009, 1, 1)
TODAY = date(2026, 10, 5)

Q3_END = date(2015, 9, 30)
Q4_END = date(2015, 12, 31)
FILED_Q3 = date(2015, 10, 30)
FILED_Q4 = date(2016, 2, 26)
FILED_RESTATED = date(2016, 11, 4)
FILED_OLD = date(2008, 5, 7)

ACCN_1 = "0000718877-16-000045"
ACCN_2 = "0000718877-16-000112"


CIK_10 = "0000718877"   # ATVI; the default fact() owner


@dataclass(frozen=True)
class Mapping:
    """Stand-in for phase 1's ``cik.CikRow``: the attributes fundamentals.py actually reads.

    The field names are phase 1's, not a guess (C5): **``symbol``**, not ``ticker``, and
    **``company_name``**, not ``company``. ``source`` is one of phase 1's five tier labels and
    is read by ``sync_ticker_cik``. Getting any of these wrong here would make the fake pass
    while the real ``cik.CikRow`` raised ``AttributeError``, so this is the single place the
    phase-1 row shape appears.
    """

    symbol: str
    cik: str | None
    company_name: str = "Test Co"
    start_date: date = date(1990, 1, 1)
    end_date: date | None = None
    source: str = "manual"
    note: str = ""


def fact(
    tag="Assets",
    *,
    taxonomy="us-gaap",
    unit="USD",
    start=None,
    end=Q4_END,
    val=100.0,
    accn=ACCN_1,
    form="10-K",
    fy=2015,
    fp="FY",
    filed=FILED_Q4,
    frame=None,
):
    """One parsed XBRL fact. The only place sec.Fact's field names are spelled (C4)."""
    return sec.Fact(
        cik=CIK_10,
        taxonomy=taxonomy,
        tag=tag,
        unit=unit,
        period_start=start,
        period_end=end,
        val=val,
        accn=accn,
        form=form,
        fy=fy,
        fp=fp,
        filed=filed,
        frame=frame,
    )


class FakeSec:
    """Injected FactsSource. facts: CIK -> list[Fact]. errors: CIK -> exception to raise.

    Returns a real ``sec.CompanyFacts``, not a bare list (C4): the client's return type is the
    wrapper and ``fetch_cik`` reads ``.facts`` off it, so a fake that returned a list would
    pass here and fail against the shipped client. ``calls`` records every CIK fetched, in
    order -- it is what the share-class tests assert on.
    """

    def __init__(self, facts=None, *, errors=None):
        self.facts = dict(facts or {})
        self.errors = dict(errors or {})
        self.calls: list[str] = []

    def company_facts(self, cik, *, tags=None):
        self.calls.append(cik)
        if cik in self.errors:
            raise self.errors[cik]
        return sec.CompanyFacts(
            cik=cik, entity_name="Test Co", facts=tuple(self.facts.get(cik, []))
        )


def opts(**kw):
    base = dict(today=TODAY, since=SINCE, sync_map=False)
    base.update(kw)
    return fcmd.Options(**base)


def seed_universe(conn, rows):
    """rows: (symbol, index_id, start_date, end_date). Commits."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
            "VALUES (%s, %s, %s, %s, %s)",
            [(s, i, a, b, s) for (s, i, a, b) in rows],
        )
    conn.commit()


def fact_rows(conn):
    rows = conn.execute(
        "SELECT cik, taxonomy, tag, unit, period_start, period_end, accn, filed, val "
        "FROM fundamental_facts ORDER BY cik, tag, period_start, period_end, accn"
    ).fetchall()
    conn.rollback()
    return rows


def log_rows(conn):
    """``fundamentals_log`` keyed by CIK (C2) -- one row per companyfacts fetch, not per symbol.

    Returns ``{cik10: (status, first_filed, last_filed, rows, error)}``. The key is the
    10-digit zero-padded string, because that is what the module works in; the column is a
    ``bigint``. **There is no `symbol` column to key on** -- a test that looked one up by
    ticker would be asserting the contract phase 2 rejected.
    """
    rows = conn.execute(
        'SELECT cik, status, first_filed, last_filed, "rows", error '
        "FROM fundamentals_log ORDER BY cik"
    ).fetchall()
    conn.rollback()
    return {sec.cik10(r[0]): r[1:] for r in rows}


def count(conn, table):
    n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    conn.rollback()
    return n


# ------------------------------------------------------------------ CLI arguments


def parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    fcmd.add_arguments(p)
    return p.parse_args(argv)


def test_arguments_defaults_and_symbol_normalisation():
    args = parse([])
    # One floor, at both ends: the member set and the filed cutoff have to agree or the
    # dated ticker_cik join silently drops whatever falls between them.
    assert args.since == date(2009, 1, 1)
    assert args.since_filed == date(2009, 1, 1)
    assert args.batch_size == 20 and args.symbols is None and args.no_sync_map is False
    args = parse(["--symbols", "brk-b, atvi,ATVI", "--batch-size", "5", "--no-sync-map"])
    assert args.symbols == ["BRK.B", "ATVI"]
    assert args.batch_size == 5 and args.no_sync_map is True


def test_arguments_reject_bad_input():
    with pytest.raises(SystemExit):
        parse(["--batch-size", "0"])
    with pytest.raises(SystemExit):
        parse(["--since", "01/02/2015"])
    with pytest.raises(SystemExit):
        parse(["--symbols", "not a ticker!"])


def test_options_reject_a_filed_cutoff_after_the_window_opens():
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    o = fcmd.options_from_args(parse(["--dry-run"]), now=now)
    assert o.today == date(2026, 10, 5) and o.dry_run is True and o.sync_map is True
    with pytest.raises(fcmd.FundamentalsError, match="since-filed"):
        fcmd.options_from_args(parse(["--since-filed", "2016-01-01"]), now=now)
    with pytest.raises(fcmd.FundamentalsError, match="future"):
        fcmd.options_from_args(parse(["--since", "2030-01-02"]), now=now)


# ------------------------------------------------- dated CIK resolution (invariant 4)


def test_recycled_ticker_resolves_to_the_holder_during_membership():
    rows = [
        Mapping("CA", "0000356028", "CA Inc.", date(1990, 1, 1), date(2018, 11, 6)),
        Mapping("CA", "0001503290", "Xtrackers CA Muni ETF", date(2018, 11, 6), None),
    ]
    assert fcmd.resolve_window_ciks(rows, "CA", SINCE, date(2018, 11, 5)) == (
        ("0000356028",), fcmd.STATUS_OK, None
    )
    held_now = fcmd.resolve_cik(rows, "CA", date(2026, 1, 2))
    assert held_now is not None and held_now.cik == "0001503290"


def test_the_vendored_map_defends_against_recycling_by_truncating_the_interval():
    """Recycling is defended against in the DATA, not by refusing ambiguous windows.

    ``engine/data/ticker_cik.csv`` ends a recycled ticker's row at the handover and simply
    omits the new holder, so only one filer ever covers the membership window. An earlier
    two-endpoint probe refused whenever the window's ends disagreed; because of this
    truncation that could never fire on a recycled ticker, only on a legitimate reorg --
    which cost GOOG, GOOGL and WRK their fundamentals and bought nothing.
    """
    index = cik_mod.load_index()
    for symbol in ("CA", "MON", "PLL", "ALTR", "LLL", "DTV"):
        rows = index[symbol]
        assert len(rows) == 1, f"{symbol} should carry one truncated row, got {len(rows)}"
        assert rows[0].end_date is not None, f"{symbol}'s row must be closed at the handover"
        flat = [r for g in index.values() for r in g]
        numbers, status, _ = fcmd.resolve_window_ciks(
            flat, symbol, rows[0].start_date, rows[0].end_date - timedelta(days=1)
        )
        assert status == fcmd.STATUS_OK and numbers == (rows[0].cik,)


def test_a_reorganised_registrant_yields_both_filers():
    """GOOG/GOOGL across the 2015-10-02 Alphabet holdco reorg, WRK across WestRock's 2018 one.

    Both filers are fetched. Nothing is mixed: facts are CIK-keyed and phase 6's panel joins
    ``ticker_cik`` by date, so any given ``t`` reads the filer that actually held the ticker.
    """
    index = cik_mod.load_index()
    flat = [r for g in index.values() for r in g]
    for symbol in ("GOOG", "GOOGL", "WRK"):
        rows = index[symbol]
        assert len(rows) == 2, f"{symbol} should carry two reorg rows"
        last = rows[-1].end_date - timedelta(days=1) if rows[-1].end_date else TODAY
        numbers, status, _ = fcmd.resolve_window_ciks(flat, symbol, rows[0].start_date, last)
        assert status == fcmd.STATUS_OK
        assert numbers == tuple(r.cik for r in rows), f"{symbol}: {numbers}"


def test_an_unmapped_ticker_says_what_to_do_about_it():
    numbers, status, why = fcmd.resolve_window_ciks([], "NDOI", SINCE, TODAY)
    assert not numbers and status == fcmd.STATUS_FAILED and "ticker_cik.csv" in why


def test_a_none_filer_is_empty_not_failed():
    """The map ANSWERED: there is nothing at EDGAR. That is `empty`, and `empty` exits 0."""
    rows = [Mapping("DEAD", None, "Private LBO", note="no EDGAR filer")]
    numbers, status, why = fcmd.resolve_window_ciks(rows, "DEAD", SINCE, TODAY)
    assert not numbers and status == fcmd.STATUS_EMPTY and "no EDGAR filer" in why


# ---------------------------------------------------------------- fact filtering


def test_select_facts_keeps_only_allowlisted_tags_filed_in_range():
    facts = [
        fact("Assets"),
        fact("NetIncomeLoss", start=date(2015, 1, 1)),
        fact("AccruedLiabilitiesCurrent"),            # not in LADDER_TAGS
        # Before the cutoff. FILED_OLD is 2008, not 2010: the floor is 2009-01-01 now, which
        # is where XBRL begins, so nothing filed on or after it is ever dropped for being old.
        fact("Assets", end=date(2008, 3, 31), filed=FILED_OLD, fy=2008, fp="Q1"),
    ]
    kept = fcmd.select_facts(facts, fcmd.DEFAULT_SINCE_FILED)
    assert [f.tag for f in kept] == ["Assets", "NetIncomeLoss"]


def test_shares_outstanding_comes_from_the_dei_taxonomy():
    from seer_engine.fundamentals import ladder

    assert ("dei", "EntityCommonStockSharesOutstanding") in fcmd.LADDER_TAGS
    assert ("us-gaap", "EntityCommonStockSharesOutstanding") not in fcmd.LADDER_TAGS
    # The allowlist is phase 5's object, not a copy of it: a drift between the ingest and the
    # ladder is the one failure mode this import exists to make impossible.
    assert fcmd.LADDER_TAGS is ladder.LADDER_TAGS
    kept = fcmd.select_facts(
        [fact("EntityCommonStockSharesOutstanding", taxonomy="dei", unit="shares")],
        fcmd.DEFAULT_SINCE_FILED,
    )
    assert len(kept) == 1


# ------------------------------------------------------------------- ingest (DB)


def test_batches_resume_and_skip_already_logged(pg):
    seed_universe(
        pg,
        [
            ("AAA", "SP500", date(2014, 1, 2), None),
            ("BBB", "SP500", date(2015, 3, 2), date(2019, 6, 3)),
            ("CCC", "NDX", date(2016, 1, 4), None),
            ("SPY", "SP500", date(2014, 1, 2), None),
        ],
    )
    # The log is keyed by cik (C2): a bigint, and there is NO symbol column to seed.
    pg.execute("INSERT INTO fundamentals_log (cik, status, \"rows\") VALUES (1, 'ok', 2)")
    pg.commit()
    rows = [Mapping(t, f"000000000{i}") for i, t in enumerate(["AAA", "BBB", "CCC"], start=1)]
    source = FakeSec({f"000000000{i}": [fact()] for i in (1, 2, 3)})

    s = fcmd.ingest(pg, opts(batch_size=1), source=source, mappings=rows)

    assert source.calls == ["0000000002", "0000000003"]   # AAA skipped, SPY never a candidate
    assert s.ok == ["BBB", "CCC"] and s.skipped == 1 and s.exit_code() == 0
    assert s.ciks_fetched == 2
    assert count(pg, "fundamental_facts") == 2
    assert set(log_rows(pg)) == {"0000000001", "0000000002", "0000000003"}
    assert log_rows(pg)["0000000002"][:4] == ("ok", FILED_Q4, FILED_Q4, 1)

    again = FakeSec({f"000000000{i}": [fact()] for i in (1, 2, 3)})
    s2 = fcmd.ingest(pg, opts(batch_size=1), source=again, mappings=rows)
    assert again.calls == [] and s2.skipped == 3 and s2.facts_written == 0


# --------------------------------------------------- the share-class fan-out (C2's reason)


def test_a_share_class_pair_is_one_fetch_and_one_log_row(pg):
    """GOOG and GOOGL are one CIK. One companyfacts call, one fundamentals_log row, and the
    summary still reports BOTH symbols -- that is the whole point of C2."""
    seed_universe(
        pg,
        [
            ("GOOG", "SP500", date(2015, 1, 2), None),
            ("GOOGL", "SP500", date(2015, 1, 2), None),
        ],
    )
    rows = [
        Mapping("GOOG", "0001652044", "Alphabet Inc."),
        Mapping("GOOGL", "0001652044", "Alphabet Inc."),
    ]
    source = FakeSec({"0001652044": [fact(), fact("NetIncomeLoss", start=date(2015, 1, 1))]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=rows)

    assert source.calls == ["0001652044"]          # ONE fetch, not two
    assert s.ciks_fetched == 1
    assert s.ok == ["GOOG", "GOOGL"]               # but BOTH symbols reported
    assert set(log_rows(pg)) == {"0001652044"}     # ONE log row
    assert log_rows(pg)["0001652044"][3] == 2      # "rows" counted once, not doubled
    assert s.facts_fetched == 2                    # not 4
    assert count(pg, "fundamental_facts") == 2


def test_a_second_run_skips_a_share_class_cik_for_both_symbols(pg):
    """Resume is per CIK, so naming either twin on a later run re-fetches nothing."""
    seed_universe(
        pg,
        [
            ("GOOG", "SP500", date(2015, 1, 2), None),
            ("GOOGL", "SP500", date(2015, 1, 2), None),
        ],
    )
    rows = [Mapping("GOOG", "0001652044"), Mapping("GOOGL", "0001652044")]
    data = {"0001652044": [fact()]}
    fcmd.ingest(pg, opts(), source=FakeSec(data), mappings=rows)

    again = FakeSec(data)
    s = fcmd.ingest(pg, opts(), source=again, mappings=rows)
    assert again.calls == [] and s.skipped == 2 and s.ciks_fetched == 0

    # ...and naming only ONE twin on a fresh log fetches the CIK once and reports only it.
    pg.execute("DELETE FROM fundamentals_log")
    pg.commit()
    solo = FakeSec(data)
    s2 = fcmd.ingest(pg, opts(symbols=("GOOG",)), source=solo, mappings=rows)
    assert solo.calls == ["0001652044"] and s2.ok == ["GOOG"]
    assert set(log_rows(pg)) == {"0001652044"}


def test_the_benchmark_is_never_fetched(pg):
    seed_universe(pg, [("SPY", "SP500", date(2014, 1, 2), None)])
    source = FakeSec()
    with pytest.raises(fcmd.FundamentalsError, match="universe refresh"):
        fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("SPY", "0000884394")])
    assert source.calls == []


def test_a_symbol_with_no_bars_still_gets_fundamentals(pg):
    """Gap A independence: 133 ever-members have zero rows in bars and must still load."""
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), date(2023, 10, 16))])
    source = FakeSec({"0000718877": [fact(), fact("NetIncomeLoss", start=date(2015, 1, 1))]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    assert count(pg, "bars") == 0
    assert s.ok == ["ATVI"] and count(pg, "fundamental_facts") == 2


def test_a_restatement_is_a_new_row_not_an_overwrite(pg):
    """Invariant 3: accn is part of the fact identity."""
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec(
        {
            "0000718877": [
                fact("Assets", val=1000.0, accn=ACCN_1, filed=FILED_Q4),
                fact("Assets", val=1100.0, accn=ACCN_2, filed=FILED_RESTATED),
            ]
        }
    )

    fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    rows = fact_rows(pg)
    assert len(rows) == 2
    assert {(r[6], r[7], float(r[8])) for r in rows} == {
        (ACCN_1, FILED_Q4, 1000.0),
        (ACCN_2, FILED_RESTATED, 1100.0),
    }


def test_annual_and_quarterly_in_one_filing_do_not_collide(pg):
    """Same cik/tag/unit/period_end/accn, different period_start: both must survive (C1)."""
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec(
        {
            "0000718877": [
                fact("Revenues", start=date(2015, 1, 1), end=Q4_END, val=4600.0, fp="FY"),
                fact("Revenues", start=date(2015, 10, 1), end=Q4_END, val=1350.0, fp="Q4"),
            ]
        }
    )

    fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    rows = fact_rows(pg)
    assert len(rows) == 2
    assert {(r[4], float(r[8])) for r in rows} == {
        (date(2015, 1, 1), 4600.0),
        (date(2015, 10, 1), 1350.0),
    }


def test_an_instantaneous_fact_stores_period_start_equal_to_period_end(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec({"0000718877": [fact("Assets", start=None, end=Q4_END)]})

    fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    (row,) = fact_rows(pg)
    assert row[4] == Q4_END and row[5] == Q4_END


def test_a_filer_with_no_usable_facts_is_empty_not_an_error(pg):
    seed_universe(pg, [("DEAD", "SP500", date(2015, 1, 2), date(2016, 1, 4))])
    source = FakeSec({"0000000009": [fact("AccruedLiabilitiesCurrent")]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("DEAD", "0000000009")])

    assert s.empty == ["DEAD"] and s.failed == [] and s.exit_code() == 0
    status, first, last, n, error = log_rows(pg)["0000000009"]
    assert (status, first, last, n) == ("empty", None, None, 0)
    assert "ingest tag set" in error


def test_a_symbol_the_map_marks_NONE_is_empty_and_gets_no_log_row(pg):
    """The map answered "no EDGAR filer". No CIK means no fetch and no row to log against a
    bigint primary key -- and `empty` means exit 0 (Summary.exit_code is unchanged)."""
    seed_universe(pg, [("DEAD", "SP500", date(2015, 1, 2), date(2016, 1, 4))])
    source = FakeSec()

    s = fcmd.ingest(
        pg, opts(), source=source,
        mappings=[Mapping("DEAD", None, note="taken private, no filer")],
    )

    assert source.calls == [] and s.empty == ["DEAD"] and s.exit_code() == 0
    assert count(pg, "fundamentals_log") == 0


def test_one_failure_does_not_lose_the_rest_of_the_run(pg):
    seed_universe(
        pg,
        [
            ("AAA", "SP500", date(2015, 1, 2), None),
            ("BAD", "SP500", date(2015, 1, 2), None),
            ("CCC", "SP500", date(2015, 1, 2), None),
        ],
    )
    rows = [
        Mapping("AAA", "0000000001"),
        Mapping("BAD", "0000000002"),
        Mapping("CCC", "0000000003"),
    ]
    source = FakeSec(
        {"0000000001": [fact()], "0000000003": [fact()]},
        errors={"0000000002": sec.SecError("HTTP 503 from data.sec.gov")},
    )

    s = fcmd.ingest(pg, opts(batch_size=2), source=source, mappings=rows)

    assert s.ok == ["AAA", "CCC"] and s.failed == ["BAD"] and s.exit_code() == 1
    assert count(pg, "fundamental_facts") == 2
    assert log_rows(pg)["0000000002"][0] == "failed"
    assert "503" in log_rows(pg)["0000000002"][4]


def test_an_unmapped_symbol_fails_and_is_retried_every_run(pg):
    """No row in the map means no CIK, so there is nothing to log against a bigint PK. The
    symbol stays `failed` and is re-attempted on the next run with no `--retry-failed`, which
    is what makes phase 1's coverage criterion machine-checkable (C8)."""
    seed_universe(pg, [("NDOI", "SP500", date(2015, 1, 2), date(2015, 7, 1))])
    source = FakeSec()

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("AAA", "0000000001")])

    assert source.calls == [] and s.failed == ["NDOI"] and s.exit_code() == 1
    assert count(pg, "fundamentals_log") == 0

    again = fcmd.ingest(pg, opts(), source=FakeSec(), mappings=[Mapping("AAA", "0000000001")])
    assert again.failed == ["NDOI"] and again.skipped == 0


def test_a_failed_attempt_never_downgrades_a_filer_already_ok(pg):
    seed_universe(pg, [("AAA", "SP500", date(2015, 1, 2), None)])
    rows = [Mapping("AAA", "0000000001")]
    fcmd.ingest(pg, opts(), source=FakeSec({"0000000001": [fact()]}), mappings=rows)
    broken = FakeSec(errors={"0000000001": sec.SecError("HTTP 500")})

    fcmd.ingest(pg, opts(symbols=("AAA",)), source=broken, mappings=rows)

    assert log_rows(pg)["0000000001"][0] == "ok"
    assert count(pg, "fundamental_facts") == 1


def test_retry_failed_reattempts_failed_and_empty_only(pg):
    seed_universe(
        pg,
        [
            ("AAA", "SP500", date(2015, 1, 2), None),
            ("BBB", "SP500", date(2015, 1, 2), None),
            ("CCC", "SP500", date(2015, 1, 2), None),
        ],
    )
    pg.execute(
        'INSERT INTO fundamentals_log (cik, status, "rows") VALUES '
        "(1, 'ok', 1), (2, 'failed', 0), (3, 'empty', 0)"
    )
    pg.commit()
    rows = [Mapping(t, f"000000000{i}") for i, t in enumerate(["AAA", "BBB", "CCC"], start=1)]
    data = {f"000000000{i}": [fact()] for i in (1, 2, 3)}

    plain = FakeSec(data)
    fcmd.ingest(pg, opts(), source=plain, mappings=rows)
    assert plain.calls == []

    retry = FakeSec(data)
    s = fcmd.ingest(pg, opts(retry_failed=True), source=retry, mappings=rows)
    assert retry.calls == ["0000000002", "0000000003"]
    assert s.ok == ["BBB", "CCC"] and log_rows(pg)["0000000002"][0] == "ok"


def test_a_second_run_with_the_same_arguments_writes_zero_rows(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    rows = [Mapping("ATVI", "0000718877")]
    data = {
        "0000718877": [
            fact("Assets", val=1000.0),
            fact("Revenues", start=date(2015, 1, 1), val=4600.0),
        ]
    }

    s1 = fcmd.ingest(pg, opts(symbols=("ATVI",)), source=FakeSec(data), mappings=rows)
    before = fact_rows(pg)
    logged_before = log_rows(pg)
    s2 = fcmd.ingest(pg, opts(symbols=("ATVI",)), source=FakeSec(data), mappings=rows)

    assert s1.facts_written == 2 and s2.facts_written == 0
    assert fact_rows(pg) == before and log_rows(pg) == logged_before


def test_a_duplicated_fact_in_one_response_does_not_abort_the_batch(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec({"0000718877": [fact("Assets"), fact("Assets")]})

    s = fcmd.ingest(pg, opts(), source=source, mappings=[Mapping("ATVI", "0000718877")])

    assert s.ok == ["ATVI"] and count(pg, "fundamental_facts") == 1


def test_dry_run_writes_nothing(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    source = FakeSec({"0000718877": [fact(), fact("NetIncomeLoss", start=date(2015, 1, 1))]})

    s = fcmd.ingest(
        pg,
        opts(dry_run=True, sync_map=True),
        source=source,
        mappings=[Mapping("ATVI", "0000718877")],
    )

    assert s.facts_written == 2 and s.map_rows == 1 and s.map_changed is True
    assert count(pg, "fundamental_facts") == 0
    assert count(pg, "fundamentals_log") == 0
    assert count(pg, "ticker_cik") == 0


def test_sync_ticker_cik_replaces_then_is_a_no_op(pg):
    seed_universe(pg, [("CA", "SP500", date(2015, 1, 2), date(2018, 11, 6))])
    rows = [
        Mapping("CA", "0000356028", "CA Inc.", date(1990, 1, 1), date(2018, 11, 6),
                "manual", "member"),
        Mapping("CA", "0001503290", "Xtrackers CA Muni ETF", date(2018, 11, 6), None,
                "current", "recycled"),
    ]
    source = FakeSec({"0000356028": [fact()]})

    s1 = fcmd.ingest(pg, opts(sync_map=True), source=source, mappings=rows)
    assert (s1.map_rows, s1.map_changed) == (2, True)
    assert count(pg, "ticker_cik") == 2
    assert source.calls == ["0000356028"]   # the holder during membership, not today's

    s2 = fcmd.ingest(
        pg,
        opts(sync_map=True, symbols=("CA",)),
        source=FakeSec({"0000356028": [fact()]}),
        mappings=rows,
    )
    assert (s2.map_rows, s2.map_changed) == (2, False)


def test_an_empty_vendored_map_is_an_exit_2_condition(pg):
    seed_universe(pg, [("AAA", "SP500", date(2015, 1, 2), None)])
    with pytest.raises(fcmd.FundamentalsError, match="ticker_cik.csv"):
        fcmd.ingest(pg, opts(), source=FakeSec(), mappings=[])


def test_summary_text_reports_counts_and_table_size(pg):
    seed_universe(pg, [("ATVI", "SP500", date(2015, 1, 2), None)])
    o = opts()
    s = fcmd.ingest(pg, o, source=FakeSec({"0000718877": [fact()]}),
                    mappings=[Mapping("ATVI", "0000718877")])
    assert s.facts_bytes is not None and s.facts_bytes > 0
    text = fcmd.format_summary(s, o)
    assert "1 ok, 0 empty, 0 failed" in text
    assert "fundamental_facts table:" in text


def test_the_real_vendored_map_syncs_without_crashing_on_its_none_row():
    """The fixture above types ``cik`` as ``str | None`` because that is what phase 1's
    loader produces -- ``_parse_cik_cell`` returns ``None`` for the CSV token ``NONE``,
    while ``cik.NO_FILER`` is the token itself.

    Comparing a parsed row against the token therefore never matches, which crashed
    ``sync_ticker_cik`` on ``int(None)`` and made ``resolve_window_cik`` call NDOI
    ``failed`` instead of ``empty``. Every unit test passed anyway, because the fake
    passed the token where the loader passes ``None``. So this test reads the REAL
    vendored file: it is the only one that can catch a fixture disagreeing with the loader.
    """
    index = cik_mod.load_index()
    rows = [r for group in index.values() for r in group]
    none_rows = [r for r in rows if r.cik is None]
    assert none_rows, "the vendored CSV is expected to carry at least one NONE row"

    # The sync set must simply exclude them -- no exception, and none of them present.
    wanted = {m.symbol for m in rows if m.cik is not None}
    assert all(r.symbol not in wanted or any(
        o.cik is not None for o in index[r.symbol]) for r in none_rows)
    # Probe each NONE row across ITS OWN validity interval, which is what the command
    # does: the window comes from membership, and a NONE symbol's membership is the span
    # the row covers. Probing outside it hits the "no row on that date" branch first,
    # which is a different (and correct) failure.
    for r in none_rows:
        last = r.end_date - timedelta(days=1) if r.end_date else TODAY
        numbers, status, why = fcmd.resolve_window_ciks(rows, r.symbol, r.start_date, last)
        assert not numbers
        assert status == fcmd.STATUS_EMPTY, f"{r.symbol} should be empty, got {status}"
        assert "no EDGAR filer" in why
